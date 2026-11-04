#!/usr/bin/env python3
"""Unit and HTTP tests for spaces-mockup-mcp. No live Cisco APIs. No cluster."""

from __future__ import annotations

import collections
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("spaces_mockup_mcp", HERE / "server.py")
srv = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(srv)

srv.TOKEN = "mcp-bearer"
srv.DATASET = srv.load_dataset(HERE / "dataset.json")

WORKSPACE_TOOLS = [
    "location_search",
    "workspace_search",
    "workspace_metrics",
    "workspace_aggregated_usage_metrics",
    "workspace_aggregated_capacity_utilization",
    "workspace_aggregated_popularity_metrics",
    "device_search",
    "device_event_history",
    "device_aggregated_event_history",
    "device_error_code_detail_search",
    "product_lifecycle",
    "device_configuration_list",
    "device_configuration_template_list",
    "device_configuration_diff",
    "device_configuration_template_diff",
    "device_configuration_schema",
]
FIREHOSE_TOOLS = [
    "firehose_health",
    "firehose_events",
    "firehose_latest",
]
REQUIRED_EVENT_TYPES = {
    "DEVICE_LOCATION_UPDATE",
    "DEVICE_PRESENCE",
    "USER_PRESENCE",
    "DEVICE_COUNT",
    "CAMERA_COUNT",
    "WEBEX_TELEMETRY",
    "SPACE_OCCUPANCY",
    "SPACE_OCCUPANCY_CHANGE",
    "KEEP_ALIVE",
}


class LocalDefaultsTest(unittest.TestCase):
    def test_dataset_path_defaults_next_to_server(self):
        self.assertEqual(srv.DEFAULT_DATASET_PATH, HERE / "dataset.json")
        self.assertTrue(srv.DEFAULT_DATASET_PATH.is_file())

    def test_listen_defaults_to_loopback(self):
        self.assertTrue(srv.DEFAULT_LISTEN.startswith("127.0.0.1:"))

    def test_no_cluster_paths_in_defaults(self):
        self.assertNotIn("/data/", str(srv.DEFAULT_DATASET_PATH))
        self.assertNotIn("agents.svc", srv.DEFAULT_LISTEN)

    def test_http_has_no_baked_bearer(self):
        self.assertFalse(hasattr(srv, "DEFAULT_TOKEN"))
        source = (HERE / "server.py").read_text(encoding="utf-8")
        self.assertNotIn("DEFAULT_TOKEN", source)
        self.assertNotIn("local-dev", source)

    def test_http_main_exits_without_bearer(self):
        env = {k: v for k, v in os.environ.items() if k != "MCP_BEARER_TOKEN"}
        proc = subprocess.run(
            [sys.executable, str(HERE / "server.py")],
            cwd=HERE,
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("MCP_BEARER_TOKEN", proc.stderr)


class DatasetContractTest(unittest.TestCase):
    def test_dataset_has_inventory_and_firehose_types(self):
        data = srv.DATASET
        self.assertGreaterEqual(len(data["locations"]), 6)
        self.assertGreaterEqual(len(data["workspaces"]), 6)
        self.assertGreaterEqual(len(data["devices"]), 5)
        types = {row["eventType"] for row in data["firehose"]}
        self.assertTrue(REQUIRED_EVENT_TYPES.issubset(types), types)
        self.assertEqual(data["meta"]["spacesTenantName"], "Mockup Campus")

    def test_dataset_json_matches_generator(self):
        gen_spec = importlib.util.spec_from_file_location("dataset", HERE / "dataset.py")
        gen = importlib.util.module_from_spec(gen_spec)
        gen_spec.loader.exec_module(gen)
        on_disk = json.loads((HERE / "dataset.json").read_text(encoding="utf-8"))
        self.assertEqual(
            gen.build_dataset(), on_disk, "dataset.json is stale: run python3 dataset.py"
        )

    def test_dataset_is_synthetic(self):
        blob = json.dumps(srv.DATASET)
        self.assertIn("@mockup.example", blob)
        self.assertNotIn("andreril@", blob)
        self.assertNotIn("jdoe@example.com", blob)
        self.assertNotIn("+14155551234", blob)
        self.assertNotIn("WEBEX_TOKEN", blob)
        self.assertNotIn("MCP_BEARER_TOKEN", blob)


class LocationWorkspaceTest(unittest.TestCase):
    def test_location_search_by_name_and_city(self):
        out = srv.location_search({"name": "North"})
        ids = [row["locationId"] for row in out["locations"]]
        self.assertIn("loc-bldg-north", ids)
        self.assertIn("loc-floor-n1", ids)
        city = srv.location_search({"city": "Sydney"})
        self.assertGreaterEqual(city["count"], 3)

    def test_workspace_search_filters(self):
        huddle = srv.workspace_search({"name": "Huddle"})
        self.assertEqual([w["id"] for w in huddle["workspaces"]], ["ws-huddle"])
        desks = srv.workspace_search({"type": "desk"})
        self.assertEqual([w["id"] for w in desks["workspaces"]], ["ws-focus"])

    def test_workspace_metrics_shift_to_live_clock(self):
        now = 1_800_000_000_000
        out = srv.workspace_metrics({"workspace_id": "ws-board", "now_ms": now})
        self.assertGreater(len(out["points"]), 3)
        self.assertTrue(all(p["timestamp"] <= now for p in out["points"]))
        self.assertTrue(all(p["timestamp"] > now - srv.DAY for p in out["points"]))
        peak = max(p["peopleCount"] for p in out["points"])
        self.assertEqual(peak, 12)

    def test_capacity_and_popularity(self):
        cap = srv.workspace_aggregated_capacity_utilization({})
        over = {w["id"] for w in cap["overcrowded"]}
        under = {w["id"] for w in cap["under_utilized"]}
        self.assertIn("ws-board", over)
        self.assertIn("ws-focus", under)
        pop = srv.workspace_aggregated_popularity_metrics({})
        self.assertEqual(pop["workspaces"][0]["id"], "ws-board")

    def test_usage_metrics_roll_up(self):
        out = srv.workspace_aggregated_usage_metrics({})
        self.assertGreater(out["totals"]["useMinutes"], 0)
        self.assertIn("ws-huddle", {w["id"] for w in out["workspaces"]})


class DeviceTest(unittest.TestCase):
    def test_device_search_and_config(self):
        found = srv.device_search({"product": "Room Bar Pro"})
        self.assertEqual(found["devices"][0]["id"], "dev-roombar-board")
        cfg = srv.device_configuration_list({"device_id": "dev-roombar-board"})
        self.assertEqual(cfg["config"]["Audio.DefaultVolume"], 50)

    def test_template_diff_and_device_diff(self):
        vs_tpl = srv.device_configuration_template_diff({"device_id": "dev-roombar-board"})
        keys = {d["key"] for d in vs_tpl["diffs"]}
        self.assertIn("Audio.DefaultVolume", keys)
        match = srv.device_configuration_template_diff({"device_id": "dev-kitmini-huddle"})
        self.assertEqual(match["diffs"], [])
        pair = srv.device_configuration_diff(
            {"device_id_a": "dev-roombar-board", "device_id_b": "dev-kitmini-huddle"}
        )
        self.assertTrue(any(d["key"] == "Audio.DefaultVolume" for d in pair["diffs"]))

    def test_schema_templates_errors_lifecycle(self):
        schema = srv.device_configuration_schema({"key_contains": "Volume"})
        self.assertEqual(schema["keys"][0]["key"], "Audio.DefaultVolume")
        tpls = srv.device_configuration_template_list({})
        self.assertEqual(len(tpls["templates"]), 2)
        err = srv.device_error_code_detail_search({"code": "CAM_HDMI"})
        self.assertEqual(err["errors"][0]["code"], "CAM_HDMI_SIGNAL_LOST")
        life = srv.product_lifecycle({"product": "Room Kit Mini"})
        self.assertEqual(life["products"][0]["productType"], "roomkit-mini")

    def test_device_event_history(self):
        hist = srv.device_event_history({"device_id": "dev-kitmini-huddle"})
        self.assertGreaterEqual(len(hist["events"]), 2)
        self.assertEqual(hist["events"][0]["deviceId"], "dev-kitmini-huddle")
        agg = srv.device_aggregated_event_history({})
        self.assertGreater(agg["totals"]["events"], 0)
        self.assertIn("error", agg["by_severity"])


class FirehoseTest(unittest.TestCase):
    def test_health_lists_subscribed_types(self):
        out = srv.firehose_health({})
        self.assertTrue(REQUIRED_EVENT_TYPES.issubset(set(out["subscribedEventTypes"])))
        self.assertEqual(out["spacesTenantName"], "Mockup Campus")
        self.assertEqual(out["channel"], "pull")

    def test_events_filter_and_live_clock(self):
        now = 1_800_000_000_000
        occ = srv.firehose_events(
            {"eventType": "SPACE_OCCUPANCY", "locationId": "loc-floor-n1", "now_ms": now}
        )
        self.assertGreaterEqual(occ["count"], 1)
        for row in occ["events"]:
            self.assertEqual(row["eventType"], "SPACE_OCCUPANCY")
            self.assertNotIn("offset_ms", row)
            self.assertLessEqual(row["recordTimestamp"], now)
            self.assertGreater(row["recordTimestamp"], now - srv.DAY)

    def test_events_device_and_limit(self):
        out = srv.firehose_events({"deviceId": "mockup-phone-01", "limit": 3})
        self.assertLessEqual(out["count"], 3)
        self.assertTrue(out["events"])
        blob = json.dumps(out)
        self.assertIn("mockup-phone-01", blob)

    def test_events_device_filter_matches_user_device_ids(self):
        out = srv.firehose_events({"deviceId": "mockup-phone-01"})
        types = [row["eventType"] for row in out["events"]]
        self.assertIn("USER_PRESENCE", types)
        users = [
            row["userPresence"]["user"]
            for row in out["events"]
            if row["eventType"] == "USER_PRESENCE"
        ]
        self.assertEqual([u["userId"] for u in users], ["mockup-user-01"])
        self.assertEqual(out["count"], 8)

    def test_latest_snapshot(self):
        now = 1_800_000_000_000
        out = srv.firehose_latest({"now_ms": now})
        self.assertIn("mockup-phone-01", {row["deviceId"] for row in out["locations"]})
        board = next(row for row in out["occupancy"] if row["workspaceId"] == "ws-board")
        self.assertIn("peopleCount", board)
        self.assertLessEqual(board["timestamp"], now)


class RpcAndHttpTest(unittest.TestCase):
    def call(self, name: str, args: dict | None = None) -> dict:
        body = srv.rpc(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": args or {}},
            }
        )
        return json.loads(body["result"]["content"][0]["text"])

    def test_tools_list_covers_workspaces_and_firehose(self):
        body = srv.rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        names = [t["name"] for t in body["result"]["tools"]]
        self.assertEqual(names, WORKSPACE_TOOLS + FIREHOSE_TOOLS)

    def test_rpc_workspace_search(self):
        out = self.call("workspace_search", {"name": "Boardroom"})
        self.assertEqual(out["workspaces"][0]["id"], "ws-board")

    def test_rpc_firehose_events(self):
        out = self.call("firehose_events", {"eventType": "WEBEX_TELEMETRY"})
        self.assertGreaterEqual(out["count"], 1)
        self.assertEqual(out["events"][0]["eventType"], "WEBEX_TELEMETRY")

    def test_unknown_tool(self):
        body = srv.rpc(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "confirm_post", "arguments": {}},
            }
        )
        self.assertEqual(body["error"]["code"], -32601)

    def test_refuses_token_echo(self):
        orig = srv.HANDLERS["location_search"]

        def leak(_args):
            return {"token": srv.TOKEN}

        srv.HANDLERS["location_search"] = leak
        try:
            out = self.call("location_search", {})
        finally:
            srv.HANDLERS["location_search"] = orig
        self.assertEqual(out["error"], "refusing to return credential-shaped fields")

    def test_handle_http_health_and_auth(self):
        code, payload = srv.handle_http("GET", "/health", "")
        self.assertEqual(code, 200)
        self.assertEqual(payload, {"status": "ok", "server": "spaces-mockup"})
        guide = (HERE / "docs" / "spaces-lab-guide.md").read_text(encoding="utf-8")
        self.assertIn(json.dumps(payload), guide, "guide's /health sample must match the reply")
        code, payload = srv.handle_http("POST", "/mcp", "")
        self.assertEqual(code, 401)
        self.assertEqual(payload, {"error": "bearer required"})
        code, payload = srv.handle_http(
            "POST",
            "/mcp",
            "Bearer mcp-bearer",
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        )
        self.assertEqual(code, 200)
        self.assertEqual(payload["result"]["serverInfo"]["name"], "spaces-mockup")

    def test_http_health_and_mcp_roundtrip(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            base = f"http://{host}:{port}"
            health = json.loads(urllib.request.urlopen(base + "/health", timeout=5).read())
            self.assertEqual(health["status"], "ok")
            self.assertEqual(health["server"], "spaces-mockup")
            req = urllib.request.Request(
                base + "/mcp",
                data=json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "firehose_events",
                            "arguments": {"eventType": "KEEP_ALIVE", "limit": 2},
                        },
                    }
                ).encode(),
                headers={
                    "Authorization": "Bearer mcp-bearer",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            raw = json.loads(urllib.request.urlopen(req, timeout=5).read())
            payload = json.loads(raw["result"]["content"][0]["text"])
            self.assertGreaterEqual(payload["count"], 1)
            self.assertEqual(payload["events"][0]["eventType"], "KEEP_ALIVE")
            bad = urllib.request.Request(
                base + "/mcp",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(bad, timeout=5)
            exc.exception.close()
            self.assertEqual(exc.exception.code, 401)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)


class LabGuideToolsTest(unittest.TestCase):
    def test_guide_tool_table_matches_server(self):
        text = (HERE / "docs" / "spaces-lab-guide.md").read_text(encoding="utf-8")
        server_tools = {tool["name"] for tool in srv.TOOLS}
        self.assertEqual(server_tools, set(srv.HANDLERS))
        table_tools = set(re.findall(r"^\| `([a-z_]+)` \|", text, re.M))
        self.assertEqual(table_tools, server_tools)
        claimed = re.search(r"covers all (\d+) tools", text)
        self.assertIsNotNone(claimed, "guide overview should state the tool count")
        self.assertEqual(int(claimed.group(1)), len(server_tools))


class ClockAndPagingTest(unittest.TestCase):
    NOW = 1_800_000_000_000

    def test_nothing_is_dated_in_the_future(self):
        d = srv.DATASET
        offsets = [r["offset_ms"] for r in d["firehose"] + d["device_events"]]
        offsets += [p["offset_ms"] for series in d["metrics"].values() for p in series]
        self.assertLess(max(offsets), 0)

    def test_latest_readings_are_recent(self):
        newest = max(
            p["timestamp"]
            for ws in srv.DATASET["metrics"]
            for p in srv.workspace_metrics({"workspace_id": ws, "now_ms": self.NOW})["points"]
        )
        self.assertLessEqual(self.NOW - newest, 3_600_000)
        snap = srv.firehose_latest({"now_ms": self.NOW})["occupancy"]
        self.assertLessEqual(min(self.NOW - r["timestamp"] for r in snap), 3_600_000)

    def test_events_page_through_everything_once(self):
        first = srv.firehose_events({"now_ms": self.NOW})
        self.assertEqual((first["count"], first["truncated"], first["nextOffset"]), (50, True, 50))
        second = srv.firehose_events({"now_ms": self.NOW, "offset": first["nextOffset"]})
        self.assertFalse(second["truncated"])
        self.assertNotIn("nextOffset", second)
        uids = [e["recordUid"] for e in first["events"] + second["events"]]
        self.assertEqual(len(uids), len(set(uids)))
        self.assertEqual(len(uids), first["total"])
        self.assertEqual(len(uids), len(srv.DATASET["firehose"]))
        stamps = [e["recordTimestamp"] for e in first["events"] + second["events"]]
        self.assertEqual(stamps, sorted(stamps))
        self.assertIn("error", srv.firehose_events({"offset": "x"}))

    def test_schemas_hide_the_test_clock(self):
        for tool in srv.TOOLS:
            self.assertNotIn("now_ms", tool["inputSchema"].get("properties", {}), tool["name"])
        props = next(x for x in srv.TOOLS if x["name"] == "firehose_events")["inputSchema"]
        self.assertIn("offset", props["properties"])

    def test_descriptions_state_the_rules_the_code_uses(self):
        desc = {tool["name"]: tool["description"] for tool in srv.TOOLS}
        self.assertIn("at most 50", desc["firehose_events"])
        self.assertIn("nextOffset", desc["firehose_events"])
        self.assertEqual(srv.MAX_EVENTS, 50)
        self.assertIn("above 1.0", desc["workspace_aggregated_capacity_utilization"])
        self.assertIn("under 80", desc["workspace_aggregated_capacity_utilization"])
        self.assertNotIn("Workspaces MCP location_search mockup", desc["location_search"])
        for name, text in desc.items():
            self.assertGreaterEqual(len(text), 40, name)


class LabGuideAnswerKeyTest(unittest.TestCase):
    """Each answer-key number is computed from the server and must appear in the guide."""

    NOW = 1_800_000_000_000

    @classmethod
    def setUpClass(cls):
        text = (HERE / "docs" / "spaces-lab-guide.md").read_text(encoding="utf-8")
        cls.key = text[text.index("## Answer key") :]
        cls.guide = text

    def say(self, phrase):
        self.assertTrue(phrase in self.key, f"answer key no longer says: {phrase}")

    def metrics(self, workspace_id):
        return srv.workspace_metrics({"workspace_id": workspace_id, "now_ms": self.NOW})["points"]

    def events(self, **filters):
        return srv.firehose_events({"now_ms": self.NOW, **filters})["events"]

    def test_lab1_environment(self):
        ids = [w["id"] for w in srv.workspace_search({})["workspaces"]]
        points = {i: self.metrics(i) for i in ids}
        latest = {i: p[-1]["temperatureC"] for i, p in points.items()}
        self.assertEqual(round(min(latest.values()), 2), 22.4)
        self.assertEqual(round(max(latest.values()), 2), 22.85)
        self.assertEqual(max(latest, key=latest.get), "ws-workshop")
        self.say("latest reading is 22.4–22.85 °C.")
        self.say("Workshop Bay is the warmest (22.85 °C, 3 people)")
        ages_h = {round((self.NOW - p[-1]["timestamp"]) / 3_600_000) for p in points.values()}
        self.assertEqual((min(ages_h), max(ages_h)), (1, 3))
        self.say("which is 1 to 3 hours old depending on the room; see 1.A4")

        board = points["ws-board"]
        self.assertEqual([board[0]["temperatureC"], board[-1]["temperatureC"]], [22.4, 22.4])
        self.assertEqual(max(p["temperatureC"] for p in board), 24.2)
        self.say("starts at 22.4 °C, peaks at 24.2 °C and ends back at 22.4 °C")

        quiet = {i for i, p in points.items() if max(x["ambientNoise"] for x in p) <= 30}
        self.assertEqual(quiet, {"ws-focus", "ws-phone"})

        alerts = [
            (i, x)
            for i, p in points.items()
            for x in p
            if x["temperatureC"] > 24 or x["humidityPct"] >= 60
        ]
        self.assertEqual(len(alerts), 1)
        self.assertEqual((alerts[0][0], alerts[0][1]["peopleCount"]), ("ws-board", 12))
        self.say("One hour only. Boardroom North hit 24.2 °C and 60% with 12 people")

        for p in points.values():
            for x in p:
                n = x["peopleCount"]
                self.assertAlmostEqual(x["temperatureC"], 22.4 + 0.15 * n)
                self.assertEqual(x["humidityPct"], 48 + n)
                self.assertEqual(x["ambientNoise"], 28 + 2 * n)
        self.say("22.4 °C + 0.15 °C per person, humidity is 48% + 1% per person")
        self.say("predicts 23.45 °C, 55% and 42")

        self.assertEqual((len(board), len(points["ws-phone"])), (11, 3))
        gap = board[-1]["timestamp"] - points["ws-phone"][-1]["timestamp"]
        self.assertAlmostEqual(gap / srv.DAY * 24, 2, delta=0.1)
        self.say("Boardroom North has 11 hourly points, Huddle A 9, Lab Bench 5")
        counts = {i: len(p) for i, p in points.items()}
        self.assertEqual(
            counts,
            {
                "ws-board": 11,
                "ws-huddle": 9,
                "ws-lab": 5,
                "ws-focus": 4,
                "ws-workshop": 4,
                "ws-phone": 3,
            },
        )
        ages = {i: round((self.NOW - p[-1]["timestamp"]) / srv.DAY * 24) for i, p in points.items()}
        self.assertEqual(
            ages,
            {
                "ws-board": 1,
                "ws-lab": 1,
                "ws-huddle": 2,
                "ws-focus": 2,
                "ws-workshop": 2,
                "ws-phone": 3,
            },
        )
        self.say("about 1 hour old for Boardroom North and Lab Bench, about 2 hours for Huddle A")

    def test_lab1_telemetry_and_s3(self):
        telemetry = self.events(eventType="WEBEX_TELEMETRY")
        self.assertEqual(len(telemetry), 5)
        readings = []
        for row in telemetry:
            t = {k: v for d in row["webexTelemetryUpdate"]["telemetries"] for k, v in d.items()}
            readings.append(t)
            self.assertEqual((t["ambientTemp"], t["relativeHumidity"]), (22.8, 50))
        board = next(t for t in readings if t["peopleCount"] == 12)
        self.assertEqual(board["ambientNoise"], 38)
        peak = max(self.metrics("ws-board"), key=lambda x: x["peopleCount"])
        self.assertEqual(peak["ambientNoise"], 52)
        self.say("the metrics say 52 and the telemetry's `ambientNoise` says 38")

        noise = {}
        for row in telemetry:
            info = row["webexTelemetryUpdate"]["deviceInfo"]
            t = {k: v for d in row["webexTelemetryUpdate"]["telemetries"] for k, v in d.items()}
            point = min(
                self.metrics(info["workspaceId"]),
                key=lambda x, ts=row["recordTimestamp"]: abs(x["timestamp"] - ts),
            )
            noise[info["workspaceId"]] = (t["ambientNoise"], point["ambientNoise"])
        self.assertTrue(all(a != b for a, b in noise.values()))
        self.assertEqual((noise["ws-workshop"], noise["ws-lab"]), ((44, 42), (41, 38)))
        gaps = {w: abs(a - b) for w, (a, b) in noise.items()}
        self.assertEqual(max(gaps, key=gaps.get), "ws-board")
        self.say("Noise disagrees in every room")
        self.say("Workshop Bay 44 vs. 42 and Lab Bench 41 vs. 38")

        counts = {}
        for row in telemetry:
            info = row["webexTelemetryUpdate"]["deviceInfo"]
            t = {k: v for d in row["webexTelemetryUpdate"]["telemetries"] for k, v in d.items()}
            point = min(
                self.metrics(info["workspaceId"]),
                key=lambda x, ts=row["recordTimestamp"]: abs(x["timestamp"] - ts),
            )
            counts[info["workspaceId"]] = (t["peopleCount"], point["peopleCount"])
        self.assertEqual({w for w, (a, b) in counts.items() if a != b}, {"ws-huddle"})
        self.assertEqual(counts["ws-huddle"], (4, 3))
        self.say("Huddle A's `WEBEX_TELEMETRY` counts 4 people while `workspace_metrics` says 3")
        self.assertIn("disagree on headcount in one room", self.guide)

        (iot,) = self.events(eventType="IOT_TELEMETRY")
        sensor = iot["iotTelemetry"]
        self.assertEqual(sensor["device"]["deviceId"], "mockup-sensor-lab-01")
        self.assertEqual(sensor["location"]["locationId"], "loc-floor-s1")
        self.assertNotIn("workspaceId", json.dumps(sensor))
        lab = min(
            self.metrics("ws-lab"), key=lambda x: abs(x["timestamp"] - iot["recordTimestamp"])
        )
        self.assertEqual((sensor["temperatureC"], lab["temperatureC"]), (23.4, 23.15))
        self.say("`mockup-sensor-lab-01` reports 23.4 °C while Lab Bench's metrics say 23.15 °C")
        self.assertIn("Its event names only the floor, not a room", self.guide)

    def test_lab2_utilization(self):
        usage = {w["id"]: w for w in srv.workspace_aggregated_usage_metrics({})["workspaces"]}
        ranked = [
            w["useMinutes"] for w in srv.workspace_aggregated_popularity_metrics({})["workspaces"]
        ]
        self.assertEqual(ranked, [450, 400, 250, 200, 50, 50])
        self.say("Boardroom North 450 min, Huddle A 400, Lab Bench 250, Workshop Bay 200")
        ratios = {
            i: round(w["useMinutes"] / w["bookedMinutes"], 2)
            for i, w in usage.items()
            if w["bookedMinutes"]
        }
        self.assertEqual(
            ratios, {"ws-board": 1.07, "ws-huddle": 0.83, "ws-lab": 2.08, "ws-workshop": 1.67}
        )
        self.say("Boardroom 1.07, Huddle A 0.83, Lab Bench 2.08, Workshop Bay 1.67")
        self.assertEqual(round(50 / 60, 2), 0.83)
        self.say("scores 0.83, not 1")

        cap = srv.workspace_aggregated_capacity_utilization({})
        self.assertEqual([w["id"] for w in cap["overcrowded"]], ["ws-board"])
        self.assertEqual({w["id"] for w in cap["under_utilized"]}, {"ws-focus", "ws-phone"})
        for w in cap["under_utilized"]:
            self.assertEqual((w["useMinutes"], w["peakRatio"]), (50, 1.0))
        self.say("flagged on minutes used (50 each, under the tool's 80-minute line)")

        walk_ins, no_shows, used = {}, {}, {}
        for i in usage:
            p = self.metrics(i)
            no_shows[i] = sum(1 for x in p if x["booked"] and not x["presence"])
            walk_ins[i] = sum(1 for x in p if x["presence"] and not x["booked"])
            used[i] = sum(1 for x in p if x["presence"])
        self.assertEqual({i: n for i, n in no_shows.items() if n}, {"ws-huddle": 1})
        huddle = self.metrics("ws-huddle")
        gap = next(k for k, x in enumerate(huddle) if x["booked"] and not x["presence"])
        self.assertTrue(huddle[gap - 1]["booked"] and huddle[gap + 1]["booked"])
        self.assertEqual(round((self.NOW - huddle[gap]["timestamp"]) / srv.DAY * 24), 6)
        self.say(
            "One booked-but-empty hour: Huddle A, about 6 hours ago, between two runs of bookings"
        )
        self.assertEqual((walk_ins["ws-lab"], used["ws-lab"]), (3, 5))
        self.assertEqual((walk_ins["ws-workshop"], used["ws-workshop"]), (2, 4))
        self.say("Lab Bench is the only room where most use is unbooked, 3 of its 5 hours")
        self.say("Huddle A no-show: one booked hour with nobody there")
        biggest = max(w["capacity"] for w in srv.workspace_search({})["workspaces"])
        self.assertEqual(biggest, usage["ws-board"]["capacity"])
        self.assertLess(biggest, usage["ws-board"]["peakPeopleCount"])
        self.say("No room can take the 12-person stand-up: Boardroom North is the biggest room")
        self.assertNotIn("moving large meetings to Workshop Bay", self.key)
        self.assertEqual(
            [i for i in used if walk_ins[i] * 2 > used[i] and usage[i]["bookedMinutes"]],
            ["ws-lab"],
        )
        self.assertEqual(
            walk_ins,
            {
                "ws-lab": 3,
                "ws-board": 2,
                "ws-workshop": 2,
                "ws-huddle": 1,
                "ws-focus": 1,
                "ws-phone": 1,
            },
        )
        self.say("Lab Bench 3, Boardroom North 2, Workshop Bay 2, and 1 each")

        latest = srv.firehose_latest({"now_ms": self.NOW})
        live = {row["workspaceId"]: row for row in latest["occupancy"]}
        self.assertEqual(
            {i: r["peopleCount"] for i, r in live.items() if r["peopleCount"]},
            {"ws-workshop": 3, "ws-huddle": 1, "ws-lab": 1},
        )
        self.assertFalse(any(r["bookingStatus"] for r in live.values()))
        for i, row in live.items():
            last = self.metrics(i)[-1]
            self.assertEqual(row["peopleCount"], last["peopleCount"], i)
            skew_min = (row["timestamp"] - last["timestamp"]) / 60_000
            if i == "ws-board":
                self.assertAlmostEqual(skew_min, 30, delta=1)
            else:
                self.assertLess(abs(skew_min), 0.2, i)
        self.say("Most timestamps agree within a few seconds")

    def test_lab3_devices(self):
        devices = srv.device_search({})["devices"]
        self.assertEqual(len(devices), 5)
        self.assertEqual(
            [d["id"] for d in devices if d["connectionStatus"] != "connected"],
            ["dev-boardpro-lab"],
        )
        agg = srv.device_aggregated_event_history({})
        self.assertEqual(agg["totals"]["events"], 5)
        self.assertEqual(agg["by_severity"], {"error": 1, "warning": 2, "info": 2})
        self.assertEqual(agg["by_code"]["none"], 1)
        (call,) = srv.device_event_history({"device_id": "dev-roombar-board"})["events"]
        self.assertEqual((call["type"], call["code"]), ("call.started", ""))
        self.say('5 events (1 error, 2 warnings, 2 info). The `"none"` code')

        huddle = srv.device_event_history({"device_id": "dev-kitmini-huddle"})["events"]
        self.assertEqual([e["type"] for e in huddle], ["camera.error", "camera.recovered"])
        self.assertEqual(agg["by_code"]["CAM_HDMI_SIGNAL_LOST"], 2)
        self.assertEqual(
            [(e["code"], e["severity"]) for e in huddle],
            [("CAM_HDMI_SIGNAL_LOST", "error"), ("CAM_HDMI_SIGNAL_LOST", "info")],
        )
        self.say("`CAM_HDMI_SIGNAL_LOST` counts 2 in the totals, but only one is an error")

        life = {p["productType"]: p for p in srv.product_lifecycle({})["products"]}
        self.assertEqual(life["roomkit-mini"]["endOfSale"], "2026-10-31")
        self.assertEqual(life["roomkit-mini"]["softwareMaintenance"], "2029-10-31")
        soonest = sorted(life.values(), key=lambda p: p["endOfSale"])
        self.assertEqual([p["productType"] for p in soonest[:2]], ["roomkit-mini", "desk-pro"])
        self.say("end-of-sale on 31 Oct 2026. Next is the Desk Pro on 30 Jun 2027")

    def test_lab4_open_workspace_templates(self):
        open_rooms = {
            w["id"] for w in srv.workspace_search({"type": "openWorkspace"})["workspaces"]
        }
        self.assertEqual(open_rooms, {"ws-lab", "ws-workshop"})
        for d in srv.device_search({})["devices"]:
            if d["workspaceId"] in open_rooms:
                cfg = srv.device_configuration_list({"device_id": d["id"]})
                self.assertEqual(cfg["templateId"], "tpl-meeting-standard")
        self.assertIn("Lab Bench and Workshop Bay are open workspaces", self.guide)
        self.say("Workshop Bay matches the template exactly")

    def test_lab4_drift(self):
        drift = {
            d["id"]: {
                x["key"]: (x["device"], x["template"])
                for x in srv.device_configuration_template_diff({"device_id": d["id"]})["diffs"]
            }
            for d in srv.device_search({})["devices"]
        }
        self.assertEqual(
            drift,
            {
                "dev-boardpro-lab": {
                    "Audio.DefaultVolume": (45, 40),
                    "Standby.Control": ("Off", "On"),
                },
                "dev-roombar-board": {"Audio.DefaultVolume": (50, 40)},
                "dev-kitmini-huddle": {},
                "dev-roombar-workshop": {},
                "dev-deskpro-focus": {},
            },
        )
        self.say("Volume 45 (template 40); Standby Off (template On)")
        diff = srv.device_configuration_diff(
            {"device_id_a": "dev-roombar-board", "device_id_b": "dev-roombar-workshop"}
        )["diffs"]
        self.assertEqual(
            [(x["key"], x["a"], x["b"]) for x in diff], [("Audio.DefaultVolume", 50, 40)]
        )

    def test_lab5_firehose(self):
        first = self.events()
        self.assertEqual(len(first), 50)
        types = [row["eventType"] for row in first]
        most = max(set(types), key=types.count)
        self.assertEqual((most, types.count(most)), ("SPACE_OCCUPANCY", 22))
        self.assertNotIn("IOT_TELEMETRY", types)
        self.assertNotIn("KEEP_ALIVE", types)
        self.say("`SPACE_OCCUPANCY` is the most common type, at 22 of the 50")
        self.assertEqual(len(self.events(eventType="IOT_TELEMETRY")), 1)
        self.assertEqual(len(self.events(eventType="KEEP_ALIVE")), 3)
        self.say("to find 1 and 3 of them")

        def board_counts(rows):
            return [
                r["spaceOccupancyChange"]["peopleCount"]
                for r in rows
                if r["eventType"] == "SPACE_OCCUPANCY_CHANGE"
            ]

        self.assertEqual(
            board_counts(self.events(eventType="SPACE_OCCUPANCY_CHANGE")),
            [0, 2, 7, 12, 8, 1, 5, 9, 3, 1, 0],
        )
        self.say("0 → 2 → 7 → 12 → 8 → 1 → 5 → 9 → 3 → 1 → 0")
        self.assertEqual(board_counts(first)[-1], 5)
        self.say("If the answer stops at 5")

        phones = {
            r["deviceId"]: r["timestamp"]
            for r in srv.firehose_latest({"now_ms": self.NOW})["locations"]
        }
        self.assertEqual(len(phones), 3)
        gap_h = (phones["mockup-phone-02"] - phones["mockup-phone-03"]) / 3_600_000
        self.assertAlmostEqual(gap_h, 8, delta=0.1)
        self.say("`mockup-phone-03`'s is 8 hours older than `mockup-phone-02`'s")

        presence_rows = self.events(eventType="DEVICE_PRESENCE")
        (exit_row,) = [
            r
            for r in presence_rows
            if r["devicePresence"]["presenceEventType"] == "DEVICE_EXIT_EVENT"
        ]
        self.assertEqual(exit_row["devicePresence"]["device"]["deviceId"], "mockup-phone-02")
        after_min = (phones["mockup-phone-02"] - exit_row["recordTimestamp"]) / 60_000
        self.assertAlmostEqual(after_min, 5, delta=0.5)
        self.say("shows it left North L1 about 5 minutes before that position was recorded")
        self.say("exit event is followed about 5 minutes later by a `DEVICE_LOCATION_UPDATE`")
        self.assertIn("A phone's latest position comes after its exit event", self.guide)

        last = presence_rows[-1]["devicePresence"]
        self.assertIs(presence_rows[-1], exit_row)
        self.assertEqual((last["activeDevicesCount"], last["inActiveDevicesCount"]), (9, 3))
        self.say("drops to 9 active plus 3 inactive")

        (raw,) = self.events(eventType="RAW_CAMERA_COUNT")
        raw = raw["rawCameraCounts"]
        self.assertEqual((raw["cameraZoneId"], raw["count"]), ("zone-lobby", 6))
        self.say("A `RAW_CAMERA_COUNT` of 6 may also turn up. It's one camera zone (`zone-lobby`)")

        by_type = {}
        for row in first:
            by_type.setdefault(row["eventType"], row)
        counts = by_type["DEVICE_COUNT"]["deviceCount"]
        self.assertEqual((counts["associatedCount"], counts["probingCount"]), (18, 5))
        self.assertEqual(by_type["CAMERA_COUNT"]["cameraCounts"]["count"], 14)
        users = by_type["USER_PRESENCE"]["userPresence"]["activeUsersCount"]
        self.assertEqual((users["usersWithUserId"], users["usersWithoutUserId"]), (8, 4))
        presence = by_type["DEVICE_PRESENCE"]["devicePresence"]
        self.assertEqual(
            (presence["activeDevicesCount"], presence["inActiveDevicesCount"]), (12, 3)
        )
        self.say("12 active plus 3 inactive devices, 15 in all")

    def test_lab2_snapshot_ages(self):
        snap = srv.firehose_latest({"now_ms": self.NOW})["occupancy"]
        ages = {r["workspaceId"]: round((self.NOW - r["timestamp"]) / 60_000) for r in snap}
        self.assertEqual(
            ages,
            {
                "ws-board": 30,
                "ws-lab": 60,
                "ws-huddle": 120,
                "ws-focus": 120,
                "ws-workshop": 120,
                "ws-phone": 180,
            },
        )
        self.say("Boardroom North about 30 minutes, Lab Bench about 1 hour")
        self.say("and Phone Booth N2 about 3 hours")
        self.say("up to 3 hours old; see 2.A5")

    def test_lab5_pages(self):
        first = self.events_page()
        self.assertEqual((first["count"], first["total"], first["nextOffset"]), (50, 77, 50))
        self.say(
            "The first pull returns 50 of 77 events, with `truncated: true` and `nextOffset: 50`"
        )
        rest = srv.firehose_events({"now_ms": self.NOW, "offset": 50})["events"]
        types = {e["eventType"] for e in rest}
        self.assertTrue({"IOT_TELEMETRY", "KEEP_ALIVE"} <= types)
        self.say("They're in the second page (`offset: 50`)")

        everything = self.events() + rest
        tally = collections.Counter(e["eventType"] for e in everything)
        self.assertEqual(sum(tally.values()), 77)
        top = {
            "SPACE_OCCUPANCY": 36,
            "SPACE_OCCUPANCY_CHANGE": 11,
            "DEVICE_PRESENCE": 6,
            "DEVICE_LOCATION_UPDATE": 6,
            "WEBEX_TELEMETRY": 5,
            "USER_PRESENCE": 3,
            "KEEP_ALIVE": 3,
        }
        self.assertEqual({k: tally[k] for k in top}, top)
        others = {k: v for k, v in tally.items() if k not in top}
        self.assertEqual((len(others), set(others.values())), (7, {1}))
        self.say(
            "`SPACE_OCCUPANCY` 36, `SPACE_OCCUPANCY_CHANGE` 11, `DEVICE_PRESENCE` 6, "
            "`DEVICE_LOCATION_UPDATE` 6, `WEBEX_TELEMETRY` 5, `USER_PRESENCE` 3, "
            "`KEEP_ALIVE` 3, and 1 each of the other seven types"
        )

    def events_page(self, **filters):
        return srv.firehose_events({"now_ms": self.NOW, **filters})

    def test_s4_prediction(self):
        n = 15
        self.assertAlmostEqual(22.4 + 0.15 * n, 24.65)
        self.assertEqual((48 + n, 28 + 2 * n), (63, 58))
        limit = max(k for k in range(30) if 22.4 + 0.15 * k < 24)
        self.assertEqual(limit, 10)
        self.say("About 24.65 °C, 63% humidity and noise 58 with 15 people")
        self.say("keep it to 10 people or fewer")


class StdioTest(unittest.TestCase):
    def test_stdio_initialize_and_tools_list(self):
        init = srv.rpc(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "t"},
                },
            }
        )
        self.assertEqual(init["result"]["serverInfo"]["name"], "spaces-mockup")
        listed = srv.rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = [t["name"] for t in listed["result"]["tools"]]
        self.assertIn("workspace_search", names)
        self.assertIn("firehose_latest", names)

    def test_stdio_frame_roundtrip(self):
        message = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        framed = srv.stdio_write_message(message)
        parsed = srv.stdio_read_message(io.BytesIO(framed))
        self.assertEqual(parsed["method"], "tools/list")


if __name__ == "__main__":
    unittest.main()
