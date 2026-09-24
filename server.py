#!/usr/bin/env python3
"""spaces-mockup-mcp: query a synthetic Cisco Spaces + Webex Workspaces dataset.

Read-only workstation MCP. Does not call mcp.webexapis.com or the live Firehose
API. Dataset timestamps are offset_ms from query time so occupancy looks live.
"""

from __future__ import annotations

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_LISTEN = "127.0.0.1:8080"
DEFAULT_DATASET_PATH = HERE / "dataset.json"
DEFAULT_TOKEN = "local-dev"

LISTEN = os.environ.get("LISTEN", DEFAULT_LISTEN)
TOKEN = os.environ.get("MCP_BEARER_TOKEN", "")
DATASET_PATH = Path(os.environ.get("DATASET_PATH", str(DEFAULT_DATASET_PATH)))
DAY = 24 * 3_600_000
MAX_EVENTS = 50

TOOLS = [
    {
        "name": "location_search",
        "description": (
            "Search Mockup Campus locations by name, city, address, "
            "locationId, or floor count. Workspaces MCP location_search mockup."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "city": {"type": "string"},
                "address": {"type": "string"},
                "locationId": {"type": "string"},
                "floor_count": {"type": "integer"},
            },
        },
    },
    {
        "name": "workspace_search",
        "description": "Search workspaces by name, type, or locationId.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "type": {"type": "string"},
                "locationId": {"type": "string"},
            },
        },
    },
    {
        "name": "workspace_metrics",
        "description": "Historical utilization and environmental metrics for one workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "now_ms": {"type": "integer"},
            },
            "required": ["workspace_id"],
        },
    },
    {
        "name": "workspace_aggregated_usage_metrics",
        "description": "Aggregate workspace use and booking minutes over the live window.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "workspace_aggregated_capacity_utilization",
        "description": "Find overcrowded or under-utilized workspaces.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "workspace_aggregated_popularity_metrics",
        "description": "Rank workspaces by actual use time.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "device_search",
        "description": "Search Webex devices by name, product, workspace, location, or status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "product": {"type": "string"},
                "workspaceId": {"type": "string"},
                "locationId": {"type": "string"},
                "connectionStatus": {"type": "string"},
            },
        },
    },
    {
        "name": "device_event_history",
        "description": "Recent history events for one device id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string"},
                "now_ms": {"type": "integer"},
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "device_aggregated_event_history",
        "description": "Organization-wide device event counts by severity and code.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "device_error_code_detail_search",
        "description": "Search device and workspace issue definitions.",
        "inputSchema": {
            "type": "object",
            "properties": {"code": {"type": "string"}, "query": {"type": "string"}},
        },
    },
    {
        "name": "product_lifecycle",
        "description": "Lifecycle milestones for Cisco device product types in the mockup catalog.",
        "inputSchema": {
            "type": "object",
            "properties": {"product": {"type": "string"}, "productType": {"type": "string"}},
        },
    },
    {
        "name": "device_configuration_list",
        "description": "Current configuration keys and values for one device.",
        "inputSchema": {
            "type": "object",
            "properties": {"device_id": {"type": "string"}},
            "required": ["device_id"],
        },
    },
    {
        "name": "device_configuration_template_list",
        "description": "Configuration templates in the mockup organization.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "device_configuration_diff",
        "description": "Compare configuration values between two devices.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id_a": {"type": "string"},
                "device_id_b": {"type": "string"},
            },
            "required": ["device_id_a", "device_id_b"],
        },
    },
    {
        "name": "device_configuration_template_diff",
        "description": "Compare a device's actual configuration against its named template.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string"},
                "template_id": {"type": "string"},
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "device_configuration_schema",
        "description": "Search possible configuration keys and allowed values.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key_contains": {"type": "string"},
                "productType": {"type": "string"},
            },
        },
    },
    {
        "name": "firehose_health",
        "description": (
            "Mockup Firehose health: subscribed event types and tenant. "
            "Mimics GET /api/partners/v1/firehose/health."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "firehose_events",
        "description": (
            "Pull Firehose EventRecords from the mockup replay. Filter by "
            "eventType, locationId, deviceId, workspaceId, fromTimestamp."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "eventType": {"type": "string"},
                "locationId": {"type": "string"},
                "deviceId": {"type": "string"},
                "workspaceId": {"type": "string"},
                "fromTimestamp": {"type": "integer"},
                "limit": {"type": "integer"},
                "now_ms": {"type": "integer"},
            },
        },
    },
    {
        "name": "firehose_latest",
        "description": "Latest device locations and space occupancy snapshot.",
        "inputSchema": {
            "type": "object",
            "properties": {"now_ms": {"type": "integer"}},
        },
    },
]


def now_ms(args: dict | None = None) -> int:
    raw = (args or {}).get("now_ms")
    if raw is None:
        return int(time.time() * 1000)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(time.time() * 1000)


def load_dataset(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


DATASET: dict = {}


def data() -> dict:
    return DATASET


def public_location(row: dict) -> dict:
    return {
        "locationId": row.get("locationId"),
        "name": row.get("name"),
        "inferredLocationTypes": list(row.get("inferredLocationTypes") or []),
        "city": row.get("city") or "",
        "address": row.get("address") or "",
        "country": row.get("country") or "",
        "floor_count": row.get("floor_count") or row.get("floorNumber") or 0,
        "parent": row.get("parent") or {},
    }


def public_workspace(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "type": row.get("type"),
        "capacity": row.get("capacity"),
        "locationId": row.get("locationId"),
        "deviceIds": list(row.get("deviceIds") or []),
        "capacityNote": row.get("capacityNote") or "",
    }


def public_device(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "displayName": row.get("displayName"),
        "product": row.get("product"),
        "productType": row.get("productType"),
        "serial": row.get("serial"),
        "softwareVersion": row.get("softwareVersion"),
        "workspaceId": row.get("workspaceId"),
        "locationId": row.get("locationId"),
        "connectionStatus": row.get("connectionStatus"),
    }


def location_search(args: dict) -> dict:
    name = str(args.get("name") or "").strip().lower()
    city = str(args.get("city") or "").strip().lower()
    address = str(args.get("address") or "").strip().lower()
    location_id = str(args.get("locationId") or "").strip()
    floor_count = args.get("floor_count")
    rows = []
    for row in data().get("locations") or []:
        if location_id and row.get("locationId") != location_id:
            continue
        if name and name not in str(row.get("name") or "").lower():
            continue
        if city and city not in str(row.get("city") or "").lower():
            continue
        if address and address not in str(row.get("address") or "").lower():
            continue
        if floor_count is not None:
            try:
                want = int(floor_count)
            except (TypeError, ValueError):
                return {"error": "floor_count must be an integer"}
            have = row.get("floor_count")
            if have != want:
                continue
        rows.append(public_location(row))
    return {"locations": rows, "count": len(rows)}


def workspace_search(args: dict) -> dict:
    name = str(args.get("name") or "").strip().lower()
    kind = str(args.get("type") or "").strip().lower()
    location_id = str(args.get("locationId") or "").strip()
    rows = []
    for row in data().get("workspaces") or []:
        if name and name not in str(row.get("name") or "").lower():
            continue
        if kind and str(row.get("type") or "").lower() != kind:
            continue
        if location_id and row.get("locationId") != location_id:
            continue
        rows.append(public_workspace(row))
    return {"workspaces": rows, "count": len(rows)}


def _workspace(workspace_id: str) -> dict | None:
    for row in data().get("workspaces") or []:
        if row.get("id") == workspace_id:
            return row
    return None


def _device(device_id: str) -> dict | None:
    for row in data().get("devices") or []:
        if row.get("id") == device_id:
            return row
    return None


def _template(template_id: str) -> dict | None:
    for row in data().get("templates") or []:
        if row.get("id") == template_id:
            return row
    return None


def workspace_metrics(args: dict) -> dict:
    workspace_id = str(args.get("workspace_id") or "").strip()
    if not workspace_id:
        return {"error": "workspace_id required"}
    ws = _workspace(workspace_id)
    if not ws:
        return {"error": f"unknown workspace {workspace_id}"}
    clock = now_ms(args)
    points = []
    for row in (data().get("metrics") or {}).get(workspace_id) or []:
        points.append(
            {
                "timestamp": clock + int(row["offset_ms"]),
                "peopleCount": row.get("peopleCount"),
                "presence": row.get("presence"),
                "booked": row.get("booked"),
                "temperatureC": row.get("temperatureC"),
                "humidityPct": row.get("humidityPct"),
                "ambientNoise": row.get("ambientNoise"),
                "useMinutes": row.get("useMinutes"),
                "bookedMinutes": row.get("bookedMinutes"),
            }
        )
    points.sort(key=lambda p: p["timestamp"])
    return {"workspace": public_workspace(ws), "points": points}


def _usage_rows() -> list[dict]:
    rows = []
    for ws in data().get("workspaces") or []:
        series = (data().get("metrics") or {}).get(ws["id"]) or []
        use = sum(int(p.get("useMinutes") or 0) for p in series)
        booked = sum(int(p.get("bookedMinutes") or 0) for p in series)
        peak = max((int(p.get("peopleCount") or 0) for p in series), default=0)
        capacity = int(ws.get("capacity") or 0) or 1
        rows.append(
            {
                "id": ws["id"],
                "name": ws["name"],
                "capacity": ws.get("capacity"),
                "useMinutes": use,
                "bookedMinutes": booked,
                "peakPeopleCount": peak,
                "peakRatio": round(peak / capacity, 2),
            }
        )
    return rows


def workspace_aggregated_usage_metrics(_args: dict) -> dict:
    rows = _usage_rows()
    return {
        "workspaces": rows,
        "totals": {
            "useMinutes": sum(r["useMinutes"] for r in rows),
            "bookedMinutes": sum(r["bookedMinutes"] for r in rows),
        },
    }


def workspace_aggregated_capacity_utilization(_args: dict) -> dict:
    rows = _usage_rows()
    overcrowded = [r for r in rows if r["peakRatio"] > 1.0]
    under = [r for r in rows if r["useMinutes"] < 80]
    return {"overcrowded": overcrowded, "under_utilized": under}


def workspace_aggregated_popularity_metrics(_args: dict) -> dict:
    rows = sorted(_usage_rows(), key=lambda r: r["useMinutes"], reverse=True)
    return {"workspaces": rows}


def device_search(args: dict) -> dict:
    name = str(args.get("name") or "").strip().lower()
    product = str(args.get("product") or "").strip().lower()
    workspace_id = str(args.get("workspaceId") or "").strip()
    location_id = str(args.get("locationId") or "").strip()
    status = str(args.get("connectionStatus") or "").strip().lower()
    rows = []
    for row in data().get("devices") or []:
        if name and name not in str(row.get("displayName") or "").lower():
            continue
        if product and product not in str(row.get("product") or "").lower():
            continue
        if workspace_id and row.get("workspaceId") != workspace_id:
            continue
        if location_id and row.get("locationId") != location_id:
            continue
        if status and str(row.get("connectionStatus") or "").lower() != status:
            continue
        rows.append(public_device(row))
    return {"devices": rows, "count": len(rows)}


def device_event_history(args: dict) -> dict:
    device_id = str(args.get("device_id") or "").strip()
    if not device_id:
        return {"error": "device_id required"}
    clock = now_ms(args)
    events = []
    for row in data().get("device_events") or []:
        if row.get("deviceId") != device_id:
            continue
        events.append(
            {
                "deviceId": row["deviceId"],
                "timestamp": clock + int(row["offset_ms"]),
                "type": row.get("type"),
                "code": row.get("code") or "",
                "severity": row.get("severity"),
                "message": row.get("message"),
            }
        )
    events.sort(key=lambda e: e["timestamp"])
    return {"events": events, "count": len(events)}


def device_aggregated_event_history(_args: dict) -> dict:
    by_severity: dict[str, int] = {}
    by_code: dict[str, int] = {}
    total = 0
    for row in data().get("device_events") or []:
        total += 1
        sev = str(row.get("severity") or "info")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        code = str(row.get("code") or "none")
        by_code[code] = by_code.get(code, 0) + 1
    return {"totals": {"events": total}, "by_severity": by_severity, "by_code": by_code}


def device_error_code_detail_search(args: dict) -> dict:
    needle = str(args.get("code") or args.get("query") or "").strip().lower()
    rows = []
    for row in data().get("error_codes") or []:
        hay = " ".join(
            [
                str(row.get("code") or ""),
                str(row.get("description") or ""),
                str(row.get("recommendedAction") or ""),
            ]
        ).lower()
        if needle and needle not in hay:
            continue
        rows.append(row)
    return {"errors": rows, "count": len(rows)}


def product_lifecycle(args: dict) -> dict:
    product = str(args.get("product") or "").strip().lower()
    product_type = str(args.get("productType") or "").strip().lower()
    rows = []
    for row in data().get("products") or []:
        if product_type and str(row.get("productType") or "").lower() != product_type:
            continue
        if product and product not in str(row.get("name") or "").lower():
            continue
        rows.append(row)
    return {"products": rows, "count": len(rows)}


def device_configuration_list(args: dict) -> dict:
    device_id = str(args.get("device_id") or "").strip()
    if not device_id:
        return {"error": "device_id required"}
    device = _device(device_id)
    if not device:
        return {"error": f"unknown device {device_id}"}
    return {
        "device_id": device_id,
        "templateId": device.get("templateId"),
        "config": dict(device.get("config") or {}),
    }


def device_configuration_template_list(_args: dict) -> dict:
    rows = [
        {"id": t["id"], "name": t["name"], "keys": sorted((t.get("config") or {}).keys())}
        for t in data().get("templates") or []
    ]
    return {"templates": rows, "count": len(rows)}


def _diff_maps(left: dict, right: dict, left_label: str, right_label: str) -> list[dict]:
    keys = sorted(set(left) | set(right))
    diffs = []
    for key in keys:
        if left.get(key) != right.get(key):
            diffs.append({"key": key, left_label: left.get(key), right_label: right.get(key)})
    return diffs


def device_configuration_diff(args: dict) -> dict:
    a_id = str(args.get("device_id_a") or "").strip()
    b_id = str(args.get("device_id_b") or "").strip()
    if not a_id or not b_id:
        return {"error": "device_id_a and device_id_b required"}
    a = _device(a_id)
    b = _device(b_id)
    if not a or not b:
        return {"error": "unknown device"}
    return {
        "device_id_a": a_id,
        "device_id_b": b_id,
        "diffs": _diff_maps(a.get("config") or {}, b.get("config") or {}, "a", "b"),
    }


def device_configuration_template_diff(args: dict) -> dict:
    device_id = str(args.get("device_id") or "").strip()
    if not device_id:
        return {"error": "device_id required"}
    device = _device(device_id)
    if not device:
        return {"error": f"unknown device {device_id}"}
    template_id = str(args.get("template_id") or device.get("templateId") or "").strip()
    template = _template(template_id)
    if not template:
        return {"error": f"unknown template {template_id}"}
    return {
        "device_id": device_id,
        "template_id": template_id,
        "diffs": _diff_maps(
            device.get("config") or {},
            template.get("config") or {},
            "device",
            "template",
        ),
    }


def device_configuration_schema(args: dict) -> dict:
    needle = str(args.get("key_contains") or "").strip().lower()
    product_type = str(args.get("productType") or "").strip().lower()
    rows = []
    for row in data().get("config_schema") or []:
        if needle and needle not in str(row.get("key") or "").lower():
            continue
        products = [str(p).lower() for p in (row.get("products") or [])]
        if product_type and product_type not in products:
            continue
        rows.append(row)
    return {"keys": rows, "count": len(rows)}


def firehose_health(_args: dict) -> dict:
    meta = data().get("meta") or {}
    return {
        "status": "ok",
        "channel": "pull",
        "spacesTenantId": meta.get("spacesTenantId"),
        "spacesTenantName": meta.get("spacesTenantName"),
        "partnerTenantId": meta.get("partnerTenantId"),
        "subscribedEventTypes": list(meta.get("subscribedEventTypes") or []),
        "replay": True,
        "note": "Mockup pull channel. Not Cisco Spaces live Firehose.",
    }


def _walk_values(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_values(item)


def _event_matches(
    row: dict, event_type: str, location_id: str, device_id: str, workspace_id: str
) -> bool:
    if event_type and row.get("eventType") != event_type:
        return False
    if not (location_id or device_id or workspace_id):
        return True
    found_loc = found_dev = found_ws = False
    for key, value in _walk_values(row):
        if location_id and key in {"locationId", "floorId"} and str(value) == location_id:
            found_loc = True
        if device_id and key in {"deviceId"} and str(value) == device_id:
            found_dev = True
        if workspace_id and key in {"workspaceId", "id"} and str(value) == workspace_id:
            found_ws = True
    if location_id and not found_loc:
        return False
    if device_id and not found_dev:
        return False
    if workspace_id and not found_ws:
        return False
    return True


def _live_event(row: dict, clock: int) -> dict:
    out = {k: v for k, v in row.items() if k != "offset_ms"}
    out["recordTimestamp"] = clock + int(row.get("offset_ms") or 0)
    payload = None
    for key in (
        "spaceOccupancy",
        "spaceOccupancyChange",
        "devicePresence",
        "deviceLocationUpdate",
        "userPresence",
        "webexTelemetryUpdate",
    ):
        if isinstance(out.get(key), dict):
            payload = out[key]
            break
    if payload and "windowStartOffset_ms" in payload:
        payload = dict(payload)
        payload["windowStartTimestamp"] = clock + int(payload.pop("windowStartOffset_ms"))
        if row.get("eventType") == "SPACE_OCCUPANCY":
            out["spaceOccupancy"] = payload
    return out


def firehose_events(args: dict) -> dict:
    event_type = str(args.get("eventType") or "").strip()
    location_id = str(args.get("locationId") or "").strip()
    device_id = str(args.get("deviceId") or "").strip()
    workspace_id = str(args.get("workspaceId") or "").strip()
    try:
        limit = int(args.get("limit") or MAX_EVENTS)
    except (TypeError, ValueError):
        return {"error": "limit must be an integer"}
    limit = min(max(limit, 1), MAX_EVENTS)
    from_ts = args.get("fromTimestamp")
    try:
        from_ts_i = int(from_ts) if from_ts is not None else None
    except (TypeError, ValueError):
        return {"error": "fromTimestamp must be an integer"}
    clock = now_ms(args)
    events = []
    for row in data().get("firehose") or []:
        if not _event_matches(row, event_type, location_id, device_id, workspace_id):
            continue
        live = _live_event(row, clock)
        if from_ts_i is not None and live["recordTimestamp"] < from_ts_i:
            continue
        events.append(live)
    events.sort(key=lambda e: e["recordTimestamp"])
    events = events[:limit]
    return {"events": events, "count": len(events)}


def firehose_latest(args: dict) -> dict:
    clock = now_ms(args)
    locations: dict[str, dict] = {}
    occupancy: dict[str, dict] = {}
    for row in data().get("firehose") or []:
        live = _live_event(row, clock)
        if live.get("eventType") == "DEVICE_LOCATION_UPDATE":
            payload = live.get("deviceLocationUpdate") or {}
            device = payload.get("device") or {}
            device_id = str(device.get("deviceId") or "")
            if device_id:
                locations[device_id] = {
                    "deviceId": device_id,
                    "timestamp": live["recordTimestamp"],
                    "locationId": (payload.get("location") or {}).get("locationId"),
                    "xPos": payload.get("xPos"),
                    "yPos": payload.get("yPos"),
                    "ssid": payload.get("ssid"),
                }
        if live.get("eventType") in {"SPACE_OCCUPANCY", "SPACE_OCCUPANCY_CHANGE"}:
            payload = live.get("spaceOccupancy") or live.get("spaceOccupancyChange") or {}
            space = payload.get("space") or {}
            workspace_id = str(space.get("id") or "")
            if workspace_id:
                occupancy[workspace_id] = {
                    "workspaceId": workspace_id,
                    "name": space.get("name"),
                    "timestamp": live["recordTimestamp"],
                    "peopleCount": payload.get("peopleCount", payload.get("peakPeopleCount")),
                    "peoplePresence": payload.get("peoplePresence"),
                    "bookingStatus": payload.get("bookingStatus"),
                }
    return {
        "locations": sorted(locations.values(), key=lambda r: r["deviceId"]),
        "occupancy": sorted(occupancy.values(), key=lambda r: r["workspaceId"]),
    }


HANDLERS = {
    "location_search": location_search,
    "workspace_search": workspace_search,
    "workspace_metrics": workspace_metrics,
    "workspace_aggregated_usage_metrics": workspace_aggregated_usage_metrics,
    "workspace_aggregated_capacity_utilization": workspace_aggregated_capacity_utilization,
    "workspace_aggregated_popularity_metrics": workspace_aggregated_popularity_metrics,
    "device_search": device_search,
    "device_event_history": device_event_history,
    "device_aggregated_event_history": device_aggregated_event_history,
    "device_error_code_detail_search": device_error_code_detail_search,
    "product_lifecycle": product_lifecycle,
    "device_configuration_list": device_configuration_list,
    "device_configuration_template_list": device_configuration_template_list,
    "device_configuration_diff": device_configuration_diff,
    "device_configuration_template_diff": device_configuration_template_diff,
    "device_configuration_schema": device_configuration_schema,
    "firehose_health": firehose_health,
    "firehose_events": firehose_events,
    "firehose_latest": firehose_latest,
}


def looks_secret(text: str) -> bool:
    if TOKEN and TOKEN in text:
        return True
    lower = text.lower()
    return "mcp_bearer_token" in lower or "webex_token" in lower


def rpc(body: dict) -> dict:
    rid = body.get("id", 1)
    method = body.get("method") or ""
    params = body.get("params") or {}
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "spaces-mockup", "version": "0.1.0"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = (params.get("name") or "").strip()
        handler = HANDLERS.get(name)
        if handler is None:
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "error": {"code": -32601, "message": f"unknown tool {name}"},
            }
        arguments = params.get("arguments") or {}
        result = handler(arguments if isinstance(arguments, dict) else {})
        dumped = json.dumps(result, default=str)
        if looks_secret(dumped):
            result = {"error": "refusing to return credential-shaped fields"}
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {"content": [{"type": "text", "text": json.dumps(result, default=str)}]},
        }
    return {
        "jsonrpc": "2.0",
        "id": rid,
        "error": {"code": -32601, "message": f"unknown method {method}"},
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "spaces-mockup-mcp/0.1"

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        sys.stderr.write(f"{self.address_string()} - {fmt % args}\n")

    def _send(self, code: int, payload) -> None:
        data = json.dumps(payload, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authed(self) -> bool:
        if not TOKEN:
            return False
        return self.headers.get("Authorization", "") == f"Bearer {TOKEN}"

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] in ("/health", "/healthz"):
            self._send(200, {"status": "ok", "server": "spaces-mockup"})
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0].rstrip("/") != "/mcp":
            self._send(404, {"error": "not found"})
            return
        if not self._authed():
            self._send(401, {"error": "bearer required"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(
                400,
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}},
            )
            return
        if not isinstance(body, dict):
            self._send(
                400,
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32600, "message": "invalid request"},
                },
            )
            return
        self._send(200, rpc(body))


def stdio_write_message(payload: dict) -> bytes:
    data = json.dumps(payload, default=str).encode()
    return f"Content-Length: {len(data)}\r\n\r\n".encode() + data


def stdio_read_message(stream) -> dict | None:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if line in (b"", b"\r\n", b"\n"):
            if line == b"":
                return None
            break
        decoded = line.decode()
        if ":" in decoded:
            key, value = decoded.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length") or "0")
    body = stream.read(length) if length else b"{}"
    return json.loads(body.decode())


def serve_stdio() -> None:
    while True:
        message = stdio_read_message(sys.stdin.buffer)
        if message is None:
            return
        if not isinstance(message, dict):
            continue
        if message.get("id") is None:
            continue
        reply = rpc(message)
        sys.stdout.buffer.write(stdio_write_message(reply))
        sys.stdout.buffer.flush()


def main(argv: list[str] | None = None) -> None:
    global DATASET, TOKEN
    args = list(sys.argv[1:] if argv is None else argv)
    TOKEN = os.environ.get("MCP_BEARER_TOKEN", "") or DEFAULT_TOKEN
    DATASET = load_dataset(DATASET_PATH)
    if "--stdio" in args:
        serve_stdio()
        return
    host, port_s = LISTEN.rsplit(":", 1)
    httpd = ThreadingHTTPServer((host, int(port_s)), Handler)
    print(f"spaces-mockup-mcp listening on {LISTEN}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
