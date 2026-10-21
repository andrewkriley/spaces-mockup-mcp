#!/usr/bin/env python3
"""Unit and HTTP tests for spaces-mockup-mcp. No live Cisco APIs. No cluster."""

from __future__ import annotations

import importlib.util
import io
import json
import os
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
            self.assertEqual(exc.exception.code, 401)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)


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
