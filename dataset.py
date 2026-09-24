#!/usr/bin/env python3
"""Deterministic Mockup Campus dataset for spaces-mockup-mcp.

Mimics Cisco Spaces Firehose EventRecord envelopes plus Webex Workspaces
Control Hub inventory (locations, workspaces, RoomOS devices, metrics).
All identities are synthetic (@mockup.example). No live Cisco APIs.
"""

from __future__ import annotations

import json
from pathlib import Path

HOUR = 3_600_000
DAY = 24 * HOUR
MINUTE = 60_000

TENANT = {
    "spacesTenantId": "tenant-mockup-001",
    "spacesTenantName": "Mockup Campus",
    "partnerTenantId": "partner-glam-mockup",
}

SUBSCRIBED_EVENTS = [
    "DEVICE_LOCATION_UPDATE",
    "DEVICE_PRESENCE",
    "USER_PRESENCE",
    "PROFILE_UPDATE",
    "DEVICE_COUNT",
    "DEVICE_ASSOCIATION",
    "CAMERA_COUNT",
    "RAW_CAMERA_COUNT",
    "IOT_TELEMETRY",
    "WEBEX_TELEMETRY",
    "SPACE_OCCUPANCY",
    "SPACE_OCCUPANCY_CHANGE",
    "KEEP_ALIVE",
    "APP_ACTIVATION",
]


def loc(location_id: str, name: str, kinds: list[str], parent=None, **extra) -> dict:
    row = {
        "locationId": location_id,
        "name": name,
        "inferredLocationTypes": kinds,
    }
    if parent:
        row["parent"] = parent
    row.update(extra)
    return row


NORTH_BLDG = {
    "locationId": "loc-bldg-north",
    "name": "North Building",
    "inferredLocationTypes": ["BUILDING"],
}
SOUTH_BLDG = {
    "locationId": "loc-bldg-south",
    "name": "South Building",
    "inferredLocationTypes": ["BUILDING"],
}


def ref(row: dict, kinds: list[str], *, include_parent: bool = False) -> dict:
    out = {
        "locationId": row["locationId"],
        "name": row["name"],
        "inferredLocationTypes": kinds,
    }
    if include_parent and row.get("parent"):
        out["parent"] = row["parent"]
    return out


def build_locations() -> list[dict]:
    campus = loc(
        "loc-campus-mockup",
        "Mockup Campus",
        ["CAMPUS"],
        city="Sydney",
        address="1 Mockup Lane, Pyrmont NSW 2009",
        country="Australia",
        floor_count=3,
        latitude=-33.8688,
        longitude=151.2093,
    )
    north = loc(
        "loc-bldg-north",
        "North Building",
        ["BUILDING"],
        parent=ref(campus, ["CAMPUS"]),
        city="Sydney",
        address="1 Mockup Lane, North Wing",
        country="Australia",
        floor_count=2,
        apCount=8,
    )
    south = loc(
        "loc-bldg-south",
        "South Building",
        ["BUILDING"],
        parent=ref(campus, ["CAMPUS"]),
        city="Sydney",
        address="1 Mockup Lane, South Wing",
        country="Australia",
        floor_count=1,
        apCount=4,
    )
    n1 = loc(
        "loc-floor-n1",
        "North L1",
        ["FLOOR"],
        parent=ref(north, ["BUILDING"], include_parent=True),
        floorNumber=1,
        apCount=4,
        mapId="map-north-l1",
    )
    n2 = loc(
        "loc-floor-n2",
        "North L2",
        ["FLOOR"],
        parent=ref(north, ["BUILDING"], include_parent=True),
        floorNumber=2,
        apCount=4,
        mapId="map-north-l2",
    )
    s1 = loc(
        "loc-floor-s1",
        "South L1",
        ["FLOOR"],
        parent=ref(south, ["BUILDING"], include_parent=True),
        floorNumber=1,
        apCount=4,
        mapId="map-south-l1",
    )
    return [campus, north, south, n1, n2, s1]


def build_workspaces() -> list[dict]:
    return [
        {
            "id": "ws-board",
            "name": "Boardroom North",
            "type": "meetingRoom",
            "capacity": 10,
            "locationId": "loc-floor-n1",
            "deviceIds": ["dev-roombar-board"],
            "capacityNote": "overcrowded at peak stand-up",
        },
        {
            "id": "ws-huddle",
            "name": "Huddle A",
            "type": "huddle",
            "capacity": 4,
            "locationId": "loc-floor-n1",
            "deviceIds": ["dev-kitmini-huddle"],
            "capacityNote": "most popular small room",
        },
        {
            "id": "ws-focus",
            "name": "Focus Desk 12",
            "type": "desk",
            "capacity": 1,
            "locationId": "loc-floor-n2",
            "deviceIds": ["dev-deskpro-focus"],
            "capacityNote": "under-utilized",
        },
        {
            "id": "ws-phone",
            "name": "Phone Booth N2",
            "type": "phoneBooth",
            "capacity": 1,
            "locationId": "loc-floor-n2",
            "deviceIds": [],
            "capacityNote": "under-utilized",
        },
        {
            "id": "ws-lab",
            "name": "Lab Bench",
            "type": "openWorkspace",
            "capacity": 6,
            "locationId": "loc-floor-s1",
            "deviceIds": ["dev-boardpro-lab"],
            "capacityNote": "afternoon lab sessions",
        },
        {
            "id": "ws-workshop",
            "name": "Workshop Bay",
            "type": "openWorkspace",
            "capacity": 8,
            "locationId": "loc-floor-s1",
            "deviceIds": ["dev-roombar-workshop"],
            "capacityNote": "hardware bring-up",
        },
    ]


def build_devices() -> list[dict]:
    return [
        {
            "id": "dev-roombar-board",
            "displayName": "Boardroom North - Room Bar Pro",
            "product": "Cisco Room Bar Pro",
            "productType": "roombar-pro",
            "serial": "MOCKBAR001",
            "macAddress": "02:00:00:00:10:01",
            "ipAddress": "10.54.90.11",
            "softwareVersion": "RoomOS 11.32.1.5",
            "workspaceId": "ws-board",
            "locationId": "loc-floor-n1",
            "connectionStatus": "connected",
            "config": {
                "Audio.DefaultVolume": 50,
                "Video.Selfview.Default": "Off",
                "Bookings.Enabled": "True",
                "Standby.Control": "On",
                "Proximity.Mode": "On",
            },
            "templateId": "tpl-meeting-standard",
        },
        {
            "id": "dev-kitmini-huddle",
            "displayName": "Huddle A - Room Kit Mini",
            "product": "Cisco Room Kit Mini",
            "productType": "roomkit-mini",
            "serial": "MOCKKIT002",
            "macAddress": "02:00:00:00:10:02",
            "ipAddress": "10.54.90.12",
            "softwareVersion": "RoomOS 11.28.1.3",
            "workspaceId": "ws-huddle",
            "locationId": "loc-floor-n1",
            "connectionStatus": "connected",
            "config": {
                "Audio.DefaultVolume": 40,
                "Video.Selfview.Default": "Off",
                "Bookings.Enabled": "True",
                "Standby.Control": "On",
                "Proximity.Mode": "On",
            },
            "templateId": "tpl-meeting-standard",
        },
        {
            "id": "dev-deskpro-focus",
            "displayName": "Focus Desk 12 - Desk Pro",
            "product": "Cisco Desk Pro",
            "productType": "desk-pro",
            "serial": "MOCKDESK003",
            "macAddress": "02:00:00:00:10:03",
            "ipAddress": "10.54.90.13",
            "softwareVersion": "RoomOS 11.32.1.5",
            "workspaceId": "ws-focus",
            "locationId": "loc-floor-n2",
            "connectionStatus": "connected",
            "config": {
                "Audio.DefaultVolume": 30,
                "Video.Selfview.Default": "Current",
                "Bookings.Enabled": "False",
                "Standby.Control": "On",
                "Proximity.Mode": "Off",
            },
            "templateId": "tpl-desk-standard",
        },
        {
            "id": "dev-boardpro-lab",
            "displayName": "Lab Bench - Board Pro 55",
            "product": "Cisco Board Pro 55",
            "productType": "board-pro-55",
            "serial": "MOCKBRD004",
            "macAddress": "02:00:00:00:10:04",
            "ipAddress": "10.54.90.21",
            "softwareVersion": "RoomOS 11.26.1.1",
            "workspaceId": "ws-lab",
            "locationId": "loc-floor-s1",
            "connectionStatus": "warning",
            "config": {
                "Audio.DefaultVolume": 45,
                "Video.Selfview.Default": "Off",
                "Bookings.Enabled": "True",
                "Standby.Control": "Off",
                "Proximity.Mode": "On",
            },
            "templateId": "tpl-meeting-standard",
        },
        {
            "id": "dev-roombar-workshop",
            "displayName": "Workshop Bay - Room Bar",
            "product": "Cisco Room Bar",
            "productType": "roombar",
            "serial": "MOCKBAR005",
            "macAddress": "02:00:00:00:10:05",
            "ipAddress": "10.54.90.22",
            "softwareVersion": "RoomOS 11.32.1.5",
            "workspaceId": "ws-workshop",
            "locationId": "loc-floor-s1",
            "connectionStatus": "connected",
            "config": {
                "Audio.DefaultVolume": 40,
                "Video.Selfview.Default": "Off",
                "Bookings.Enabled": "True",
                "Standby.Control": "On",
                "Proximity.Mode": "On",
            },
            "templateId": "tpl-meeting-standard",
        },
    ]


def build_templates() -> list[dict]:
    return [
        {
            "id": "tpl-meeting-standard",
            "name": "Meeting Room Standard",
            "config": {
                "Audio.DefaultVolume": 40,
                "Video.Selfview.Default": "Off",
                "Bookings.Enabled": "True",
                "Standby.Control": "On",
                "Proximity.Mode": "On",
            },
        },
        {
            "id": "tpl-desk-standard",
            "name": "Personal Desk Standard",
            "config": {
                "Audio.DefaultVolume": 30,
                "Video.Selfview.Default": "Current",
                "Bookings.Enabled": "False",
                "Standby.Control": "On",
                "Proximity.Mode": "Off",
            },
        },
    ]


def build_schema() -> list[dict]:
    return [
        {
            "key": "Audio.DefaultVolume",
            "type": "integer",
            "min": 0,
            "max": 100,
            "products": ["roombar-pro", "roomkit-mini", "desk-pro", "board-pro-55", "roombar"],
        },
        {
            "key": "Video.Selfview.Default",
            "type": "enum",
            "values": ["Off", "Current", "PIP"],
            "products": ["roombar-pro", "roomkit-mini", "desk-pro", "board-pro-55", "roombar"],
        },
        {
            "key": "Bookings.Enabled",
            "type": "enum",
            "values": ["True", "False"],
            "products": ["roombar-pro", "roomkit-mini", "desk-pro", "board-pro-55", "roombar"],
        },
        {
            "key": "Standby.Control",
            "type": "enum",
            "values": ["On", "Off"],
            "products": ["roombar-pro", "roomkit-mini", "desk-pro", "board-pro-55", "roombar"],
        },
        {
            "key": "Proximity.Mode",
            "type": "enum",
            "values": ["On", "Off"],
            "products": ["roombar-pro", "roomkit-mini", "desk-pro", "board-pro-55", "roombar"],
        },
    ]


def build_error_codes() -> list[dict]:
    return [
        {
            "code": "CAM_HDMI_SIGNAL_LOST",
            "severity": "error",
            "appliesTo": ["workspace", "device"],
            "description": "Camera HDMI input lost sync.",
            "recommendedAction": (
                "Reseat the HDMI cable and reboot the codec if the camera stays dark."
            ),
        },
        {
            "code": "SIGNAGE_CONTENT_STALE",
            "severity": "warning",
            "appliesTo": ["workspace"],
            "description": "Digital signage playlist has not refreshed in 24 hours.",
            "recommendedAction": "Push the workspace signage playlist from Control Hub.",
        },
        {
            "code": "PROXIMITY_PAIRING_FAIL",
            "severity": "warning",
            "appliesTo": ["device"],
            "description": "Ultrasound pairing failed for a nearby client.",
            "recommendedAction": "Confirm Proximity.Mode is On and ultrasound is not blocked.",
        },
    ]


def build_products() -> list[dict]:
    return [
        {
            "productType": "roombar-pro",
            "name": "Cisco Room Bar Pro",
            "endOfSale": "2028-03-31",
            "lastDateOfSupport": "2033-03-31",
            "softwareMaintenance": "2031-03-31",
        },
        {
            "productType": "roomkit-mini",
            "name": "Cisco Room Kit Mini",
            "endOfSale": "2026-10-31",
            "lastDateOfSupport": "2031-10-31",
            "softwareMaintenance": "2029-10-31",
        },
        {
            "productType": "desk-pro",
            "name": "Cisco Desk Pro",
            "endOfSale": "2027-06-30",
            "lastDateOfSupport": "2032-06-30",
            "softwareMaintenance": "2030-06-30",
        },
        {
            "productType": "board-pro-55",
            "name": "Cisco Board Pro 55",
            "endOfSale": "2028-12-31",
            "lastDateOfSupport": "2033-12-31",
            "softwareMaintenance": "2031-12-31",
        },
        {
            "productType": "roombar",
            "name": "Cisco Room Bar",
            "endOfSale": "2027-11-30",
            "lastDateOfSupport": "2032-11-30",
            "softwareMaintenance": "2030-11-30",
        },
    ]


def envelope(uid: str, offset_ms: int, event_type: str, payload_key: str, payload: dict) -> dict:
    row = {
        "recordUid": uid,
        "offset_ms": offset_ms,
        "eventType": event_type,
        **TENANT,
    }
    if payload_key:
        row[payload_key] = payload
    return row


def wifi_device(idx: int) -> dict:
    return {
        "deviceId": f"mockup-phone-{idx:02d}",
        "userId": f"mockup-user-{idx:02d}",
        "macAddress": f"02:00:00:aa:00:{idx:02d}",
        "manufacturer": "MockupPhone",
        "os": "MockupOS",
        "osVersion": "1.0",
        "type": "MOBILE",
        "deviceModel": "Mockup Phone",
        "email": f"visitor-{idx:02d}@mockup.example",
        "firstName": "Visitor",
        "lastName": f"{idx:02d}",
    }


def floor_n1() -> dict:
    return loc(
        "loc-floor-n1",
        "North L1",
        ["FLOOR"],
        parent=NORTH_BLDG,
        floorNumber=1,
        apCount=4,
    )


def floor_s1() -> dict:
    return loc(
        "loc-floor-s1",
        "South L1",
        ["FLOOR"],
        parent=SOUTH_BLDG,
        floorNumber=1,
        apCount=4,
    )


def occupancy_curve() -> dict[str, list[tuple[int, int, bool, bool]]]:
    """Per workspace: (hour, people, presence, booked) for a weekday."""
    return {
        "ws-board": [
            (7, 0, False, False),
            (8, 3, True, True),
            (9, 8, True, True),
            (10, 12, True, True),
            (11, 9, True, True),
            (12, 2, True, False),
            (13, 6, True, True),
            (14, 10, True, True),
            (15, 4, True, True),
            (16, 2, True, False),
            (17, 0, False, False),
        ],
        "ws-huddle": [
            (8, 2, True, True),
            (9, 4, True, True),
            (10, 4, True, True),
            (11, 3, True, True),
            (12, 0, False, False),
            (13, 4, True, True),
            (14, 4, True, True),
            (15, 2, True, True),
            (16, 1, True, False),
        ],
        "ws-focus": [
            (9, 0, False, False),
            (11, 0, False, False),
            (14, 1, True, False),
            (16, 0, False, False),
        ],
        "ws-phone": [
            (10, 0, False, False),
            (13, 1, True, False),
            (15, 0, False, False),
        ],
        "ws-lab": [
            (8, 1, True, False),
            (10, 2, True, False),
            (13, 3, True, True),
            (15, 5, True, True),
            (17, 1, True, False),
        ],
        "ws-workshop": [
            (8, 2, True, False),
            (11, 5, True, True),
            (14, 7, True, True),
            (16, 3, True, False),
        ],
    }


def hour_offset(hour: int) -> int:
    """Map local hour 0-23 onto the last 24h window. Hour 17 is near now."""
    return -((23 - hour) * HOUR)


def build_firehose(workspaces: list[dict]) -> list[dict]:
    events: list[dict] = []
    ws_by_id = {w["id"]: w for w in workspaces}
    seq = 0

    def next_uid(prefix: str) -> str:
        nonlocal seq
        seq += 1
        return f"evt-{prefix}-{seq:04d}"

    events.append(
        envelope(
            next_uid("aa"),
            -23 * HOUR,
            "APP_ACTIVATION",
            "appActivation",
            {
                **TENANT,
                "name": "Mockup Firehose Replay",
                "referenceId": "ref-mockup-001",
                "instanceName": "mockup-replay",
                "appId": "app-spaces-mockup",
                "region": "ap-southeast-2",
            },
        )
    )

    for hour, people, presence, booked in occupancy_curve()["ws-board"]:
        offset = hour_offset(hour)
        space = {
            "id": "ws-board",
            "name": "Boardroom North",
            "floorId": "loc-floor-n1",
            "type": "ROOM",
            "spaceType": {
                "isPrivate": True,
                "type": "MEETING_ROOM",
                "meetingRoom": "MR_MEETING_ROOM",
            },
            "capacity": 10,
            "occupancyType": "BOTH",
        }
        events.append(
            envelope(
                next_uid("so"),
                offset,
                "SPACE_OCCUPANCY",
                "spaceOccupancy",
                {
                    "location": floor_n1(),
                    "space": space,
                    "windowStartOffset_ms": offset - 15 * MINUTE,
                    "timeZone": "Australia/Sydney",
                    "peakPeopleCount": people,
                    "peoplePresence": presence,
                    "bookingStatus": booked,
                },
            )
        )
        events.append(
            envelope(
                next_uid("soc"),
                offset + 30 * MINUTE,
                "SPACE_OCCUPANCY_CHANGE",
                "spaceOccupancyChange",
                {
                    "location": floor_n1(),
                    "space": space,
                    "peopleCount": max(people - 1, 0) if hour != 10 else 12,
                    "peoplePresence": presence,
                    "bookingStatus": booked,
                },
            )
        )

    for ws_id, series in occupancy_curve().items():
        if ws_id == "ws-board":
            continue
        ws = ws_by_id[ws_id]
        floor = (
            floor_s1()
            if ws["locationId"] == "loc-floor-s1"
            else (
                loc(
                    ws["locationId"],
                    "North L2" if ws["locationId"] == "loc-floor-n2" else "North L1",
                    ["FLOOR"],
                    parent=NORTH_BLDG,
                )
            )
        )
        for hour, people, presence, booked in series:
            events.append(
                envelope(
                    next_uid("so"),
                    hour_offset(hour),
                    "SPACE_OCCUPANCY",
                    "spaceOccupancy",
                    {
                        "location": floor,
                        "space": {
                            "id": ws_id,
                            "name": ws["name"],
                            "floorId": ws["locationId"],
                            "type": "ROOM",
                            "capacity": ws["capacity"],
                            "occupancyType": "BOTH",
                        },
                        "timeZone": "Australia/Sydney",
                        "peakPeopleCount": people,
                        "peoplePresence": presence,
                        "bookingStatus": booked,
                    },
                )
            )

    # Wi-Fi presence and locations for three mockup visitors.
    for idx, hour, x, y, kind in (
        (1, 8, 20.0, 30.0, "DEVICE_ENTRY_EVENT"),
        (2, 8, 22.0, 28.0, "DEVICE_ENTRY_EVENT"),
        (3, 9, 40.0, 18.0, "DEVICE_ENTRY_EVENT"),
        (1, 12, 21.0, 31.0, "DEVICE_INACTIVE_EVENT"),
        (1, 13, 21.5, 30.5, "DEVICE_ACTIVE_EVENT"),
        (2, 17, 22.0, 28.0, "DEVICE_EXIT_EVENT"),
    ):
        offset = hour_offset(hour)
        device = wifi_device(idx)
        events.append(
            envelope(
                next_uid("dp"),
                offset,
                "DEVICE_PRESENCE",
                "devicePresence",
                {
                    "presenceEventType": kind,
                    "device": device,
                    "location": floor_n1(),
                    "ssid": "MockupCampus",
                    "visitId": f"visit-{idx:02d}",
                    "deviceClassification": "ASSOCIATED",
                    "activeDevicesCount": 12 if "EXIT" not in kind else 9,
                    "inActiveDevicesCount": 3,
                },
            )
        )
        events.append(
            envelope(
                next_uid("dlu"),
                offset + 5 * MINUTE,
                "DEVICE_LOCATION_UPDATE",
                "deviceLocationUpdate",
                {
                    "device": device,
                    "location": floor_n1(),
                    "ssid": "MockupCampus",
                    "visitId": f"visit-{idx:02d}",
                    "mapId": "map-north-l1",
                    "xPos": x,
                    "yPos": y,
                    "confidenceFactor": 0.88,
                    "latitude": -33.8688 + (y / 100000),
                    "longitude": 151.2093 + (x / 100000),
                    "unc": 6.5,
                    "maxDetectedRssi": -48,
                    "ipv4": f"10.54.90.{100 + idx}",
                    "deviceClassification": "ASSOCIATED",
                },
            )
        )
        if kind == "DEVICE_ENTRY_EVENT":
            events.append(
                envelope(
                    next_uid("up"),
                    offset + MINUTE,
                    "USER_PRESENCE",
                    "userPresence",
                    {
                        "presenceEventType": "USER_ENTRY_EVENT",
                        "user": {
                            "userId": device["userId"],
                            "deviceIds": [device["deviceId"]],
                            "email": device["email"],
                            "firstName": device["firstName"],
                            "lastName": device["lastName"],
                        },
                        "location": floor_n1(),
                        "visitId": f"visit-user-{idx:02d}",
                        "timeZone": "Australia/Sydney",
                        "activeUsersCount": {
                            "usersWithUserId": 8,
                            "usersWithoutUserId": 4,
                            "totalUsers": 12,
                        },
                        "connection": "CONN_WIRELESS",
                    },
                )
            )

    events.append(
        envelope(
            next_uid("dc"),
            hour_offset(10),
            "DEVICE_COUNT",
            "deviceCount",
            {
                "location": floor_n1(),
                "associatedCount": 18,
                "probingCount": 5,
                "associatedCountDelta": 3,
            },
        )
    )
    events.append(
        envelope(
            next_uid("da"),
            hour_offset(8) + 2 * MINUTE,
            "DEVICE_ASSOCIATION",
            "deviceAssociation",
            {
                "device": wifi_device(1),
                "location": floor_n1(),
                "ssid": "MockupCampus",
                "associationState": "ASSOCIATED",
            },
        )
    )
    events.append(
        envelope(
            next_uid("pu"),
            hour_offset(9),
            "PROFILE_UPDATE",
            "profileUpdate",
            {
                "device": wifi_device(2),
                "location": floor_n1(),
                "changedFields": ["osVersion"],
            },
        )
    )
    events.append(
        envelope(
            next_uid("cc"),
            hour_offset(10),
            "CAMERA_COUNT",
            "cameraCounts",
            {"location": floor_n1(), "count": 14, "countDelta": 2},
        )
    )
    events.append(
        envelope(
            next_uid("rcc"),
            hour_offset(10) + MINUTE,
            "RAW_CAMERA_COUNT",
            "rawCameraCounts",
            {
                "location": floor_n1(),
                "cameraId": "cam-mockup-n1-lobby",
                "cameraZoneId": "zone-lobby",
                "count": 6,
            },
        )
    )
    events.append(
        envelope(
            next_uid("iot"),
            hour_offset(15),
            "IOT_TELEMETRY",
            "iotTelemetry",
            {
                "device": {
                    "deviceId": "mockup-sensor-lab-01",
                    "macAddress": "02:00:00:bb:00:01",
                    "type": "SENSOR",
                    "manufacturer": "MockupSense",
                },
                "location": floor_s1(),
                "temperatureC": 23.4,
                "humidityPct": 48,
                "batteryPct": 91,
            },
        )
    )

    webex_samples = (
        ("dev-roombar-board", "ws-board", "loc-floor-n1", 10, 12, True, 38, 1),
        ("dev-kitmini-huddle", "ws-huddle", "loc-floor-n1", 11, 4, True, 32, 1),
        ("dev-boardpro-lab", "ws-lab", "loc-floor-s1", 15, 5, True, 41, 0),
        ("dev-deskpro-focus", "ws-focus", "loc-floor-n2", 14, 1, True, 28, 0),
        ("dev-roombar-workshop", "ws-workshop", "loc-floor-s1", 14, 7, True, 44, 1),
    )
    devices = {d["id"]: d for d in build_devices()}
    for dev_id, ws_id, loc_id, hour, people, presence, noise, calls in webex_samples:
        device = devices[dev_id]
        events.append(
            envelope(
                next_uid("wt"),
                hour_offset(hour),
                "WEBEX_TELEMETRY",
                "webexTelemetryUpdate",
                {
                    "deviceInfo": {
                        "deviceId": device["id"],
                        "macAddress": device["macAddress"],
                        "ipAddress": device["ipAddress"],
                        "product": device["product"],
                        "displayName": device["displayName"],
                        "serialNumber": device["serial"],
                        "softwareVersion": device["softwareVersion"],
                        "workspaceId": ws_id,
                        "orgId": "org-mockup-001",
                    },
                    "location": {
                        "locationId": loc_id,
                        "name": loc_id,
                        "inferredLocationTypes": ["FLOOR"],
                    },
                    "telemetries": [
                        {"peopleCount": people},
                        {"presence": presence},
                        {"ambientNoise": noise},
                        {"soundLevel": noise + 8},
                        {"airQuality": 44.0},
                        {"airQualityStatus": "GOOD"},
                        {"ambientTemp": 22.8},
                        {"relativeHumidity": 50},
                        {"activeCalls": calls},
                    ],
                },
            )
        )

    for minutes_ago in (45, 30, 15):
        events.append(envelope(next_uid("ka"), -minutes_ago * MINUTE, "KEEP_ALIVE", "", {}))
    return events


def build_device_events() -> list[dict]:
    return [
        {
            "deviceId": "dev-kitmini-huddle",
            "offset_ms": hour_offset(7),
            "type": "camera.error",
            "code": "CAM_HDMI_SIGNAL_LOST",
            "severity": "error",
            "message": "Camera HDMI input lost sync during morning boot.",
        },
        {
            "deviceId": "dev-kitmini-huddle",
            "offset_ms": hour_offset(8),
            "type": "camera.recovered",
            "code": "CAM_HDMI_SIGNAL_LOST",
            "severity": "info",
            "message": "Camera HDMI input restored after reseat.",
        },
        {
            "deviceId": "dev-boardpro-lab",
            "offset_ms": hour_offset(14),
            "type": "signage.stale",
            "code": "SIGNAGE_CONTENT_STALE",
            "severity": "warning",
            "message": "Lab Bench playlist has not refreshed.",
        },
        {
            "deviceId": "dev-roombar-board",
            "offset_ms": hour_offset(9),
            "type": "call.started",
            "code": "",
            "severity": "info",
            "message": "Booked stand-up joined from Room Bar Pro.",
        },
        {
            "deviceId": "dev-roombar-workshop",
            "offset_ms": hour_offset(14),
            "type": "proximity.fail",
            "code": "PROXIMITY_PAIRING_FAIL",
            "severity": "warning",
            "message": "Ultrasound pairing failed for a nearby mockup client.",
        },
    ]


def build_metrics(workspaces: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    curve = occupancy_curve()
    for ws in workspaces:
        series = []
        for hour, people, presence, booked in curve.get(ws["id"], []):
            series.append(
                {
                    "offset_ms": hour_offset(hour),
                    "peopleCount": people,
                    "presence": presence,
                    "booked": booked,
                    "temperatureC": 22.4 + (people * 0.15),
                    "humidityPct": 48 + people,
                    "ambientNoise": 28 + people * 2,
                    "useMinutes": 50 if presence else 0,
                    "bookedMinutes": 60 if booked else 0,
                }
            )
        out[ws["id"]] = series
    return out


def build_dataset() -> dict:
    locations = build_locations()
    workspaces = build_workspaces()
    devices = build_devices()
    return {
        "meta": {
            **TENANT,
            "window_ms": DAY,
            "timezone": "Australia/Sydney",
            "subscribedEventTypes": SUBSCRIBED_EVENTS,
            "note": "Synthetic Mockup Campus. Timestamps are offset_ms from query time.",
        },
        "locations": locations,
        "workspaces": workspaces,
        "devices": devices,
        "templates": build_templates(),
        "config_schema": build_schema(),
        "error_codes": build_error_codes(),
        "products": build_products(),
        "metrics": build_metrics(workspaces),
        "device_events": build_device_events(),
        "firehose": build_firehose(workspaces),
    }


def write_dataset(path: Path | None = None) -> Path:
    dest = path or Path(__file__).with_name("dataset.json")
    dest.write_text(json.dumps(build_dataset(), indent=2) + "\n", encoding="utf-8")
    return dest


if __name__ == "__main__":
    out = write_dataset()
    print(f"wrote {out}", flush=True)
