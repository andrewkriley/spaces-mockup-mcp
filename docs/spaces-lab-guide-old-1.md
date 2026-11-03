# Spaces Mockup MCP — Lab Guide: Easy to Advanced

Oct 14, 2026 · @Jason Churchill

## Overview

This guide covers all 19 tools on the `spaces-mockup` MCP server and nothing else. There are five labs, each with an Easy track and an Advanced track, and stretch goals at the end. Allow 45 minutes for the Easy track only, or about 2 hours for everything.

**You need:** Claude Code with the `spaces-mockup` server connected. Run `/mcp` to confirm it's listed. No other connectors are used.

**How the tracks work**

- **Easy:** one question, usually one tool. You learn what each data source returns.
- **Advanced:** several tools chained together, joins on IDs, or reasoning across time. You learn to combine data sources to explain something.
- **Stretch goals:** open-ended challenges with success criteria instead of a single expected answer.

**Checking your answers:** each exercise lists the expected result from the sample data. If yours differs, ask *"Which tool did you call, and with what arguments?"* Metric timestamps move with the clock, so read times relative to now, for example "about an hour ago".

## Data sources

The server serves one sample tenant, Ghost Campus in Sydney. It is read-only: nothing you ask can change bookings or devices. You don't call the tools directly. Ask a question and Claude picks the tool.

### Tools

| Tool | Area | What it returns | Input |
| --- | --- | --- | --- |
| `location_search` | Sites | Campus → building → floor tree, with address and floor count | optional filter |
| `workspace_search` | Rooms | Rooms: type, capacity, floor, devices, capacity note | optional filter |
| `workspace_metrics` | Rooms | Hourly series for one room: people, presence, booked, temperature °C, humidity %, noise, used and booked minutes | `workspace_id` |
| `workspace_aggregated_usage_metrics` | Utilization | Used and booked minutes and peak headcount per room, plus campus totals | — |
| `workspace_aggregated_popularity_metrics` | Utilization | Rooms ranked by minutes used | — |
| `workspace_aggregated_capacity_utilization` | Utilization | Overcrowded and under-utilized rooms with peak ratio | — |
| `firehose_latest` | Live | Current headcount per room and positions of tracked phones | — |
| `firehose_events` | Live | Raw `EventRecord` stream (50 per pull) | — |
| `firehose_health` | Live | Stream status, tenant, subscribed event types | — |
| `device_search` | Devices | Model, serial, RoomOS version, room, connection status | optional filter |
| `device_event_history` | Devices | Recent events for one device | `device_id` |
| `device_aggregated_event_history` | Devices | Event counts by severity and by code across the organization | — |
| `device_error_code_detail_search` | Devices | Error code meaning, severity and recommended action | optional code |
| `product_lifecycle` | Devices | End-of-sale, software-maintenance and last-support dates per model | — |
| `device_configuration_schema` | Config | Setting keys, types, allowed values, supported models | — |
| `device_configuration_template_list` | Config | Templates and the keys each one controls | — |
| `device_configuration_list` | Config | Current settings on one device, and its template | `device_id` |
| `device_configuration_diff` | Config | Settings that differ between two devices | `device_id_a`, `device_id_b` |
| `device_configuration_template_diff` | Config | Settings where a device differs from a template | `device_id`, `template_id` |

To join data across tools, use the shared IDs: `locationId`, workspace `id` / `workspaceId`, and `deviceId`.

### Locations

- Ghost Campus (`loc-campus-ghost`), 1 Ghost Lane, Pyrmont NSW 2009
  - North Building (`loc-bldg-north`): North L1 (`loc-floor-n1`) and North L2 (`loc-floor-n2`)
  - South Building (`loc-bldg-south`): South L1 (`loc-floor-s1`)

### Rooms and devices

| Room | Room ID | Floor | Seats | Device | Device ID | RoomOS | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Boardroom North | `ws-board` | North L1 | 10 | Room Bar Pro | `dev-roombar-board` | 11.32.1.5 | connected |
| Huddle A | `ws-huddle` | North L1 | 4 | Room Kit Mini | `dev-kitmini-huddle` | 11.28.1.3 | connected |
| Focus Desk 12 | `ws-focus` | North L2 | 1 | Desk Pro | `dev-deskpro-focus` | 11.32.1.5 | connected |
| Phone Booth N2 | `ws-phone` | North L2 | 1 | none | — | — | — |
| Lab Bench | `ws-lab` | South L1 | 6 | Board Pro 55 | `dev-boardpro-lab` | 11.26.1.1 | warning |
| Workshop Bay | `ws-workshop` | South L1 | 8 | Room Bar | `dev-roombar-workshop` | 11.32.1.5 | connected |

### Reference data

- **Templates:** Meeting Room Standard (`tpl-meeting-standard`) and Personal Desk Standard (`tpl-desk-standard`).
- **Config keys:** `Audio.DefaultVolume`, `Video.Selfview.Default`, `Bookings.Enabled`, `Standby.Control`, `Proximity.Mode`.
- **Error codes:** `CAM_HDMI_SIGNAL_LOST` (error), `SIGNAGE_CONTENT_STALE` (warning), `PROXIMITY_PAIRING_FAIL` (warning).
- **Firehose event types (14):** `SPACE_OCCUPANCY`, `SPACE_OCCUPANCY_CHANGE`, `DEVICE_PRESENCE`, `USER_PRESENCE`, `DEVICE_LOCATION_UPDATE`, `DEVICE_ASSOCIATION`, `DEVICE_COUNT`, `CAMERA_COUNT`, `RAW_CAMERA_COUNT`, `WEBEX_TELEMETRY`, `IOT_TELEMETRY`, `PROFILE_UPDATE`, `KEEP_ALIVE`, `APP_ACTIVATION`.

## Lab 1 — Rooms and environment

Tools: `workspace_search`, `workspace_metrics`, `firehose_events`.

### Easy

1. **Temperature everywhere.** *"Show me the temperature in all the rooms."*
   - Expected: every room reads 22.4–22.9 °C. Workshop Bay is the warmest (22.85 °C, 3 people).
2. **One room over the day.** *"Show Boardroom North's temperature history."*
   - Expected: it starts at 22.4 °C, peaks at 24.2 °C and ends back at 22.4 °C.
3. **Quietest rooms.** *"Which rooms are quietest?"*
   - Expected: Focus Desk 12 and Phone Booth N2. Their noise never goes above 30.

### Advanced

1. **Comfort alerts.** *"Flag any hour in any room where temperature went over 24 °C or humidity reached 60%."*
   - Expected: one hour only. Boardroom North hit 24.2 °C and 60% with 12 people present.
2. **Build a model.** *"Across all rooms, how do temperature, humidity and noise change with headcount?"*
   - Expected: the same rule fits every room. Temperature is 22.4 °C + 0.15 °C per person, humidity is 48% + 1% per person, and noise is 28 + 2 per person.
   - To check it: 7 people in Workshop Bay predicts 23.45 °C, 55% and 42, which matches the data.
3. **Two sources, one room.** *"Compare Boardroom North's temperature in workspace\_metrics with the WEBEX\_TELEMETRY ambientTemp for the same hour."*
   - Expected: they disagree. The metrics say 24.2 °C at the 12-person peak, while device telemetry says 22.8 °C.
   - Discuss: which source would you trust for a comfort complaint, and why?
4. **Data freshness.** *"How many readings does each room have, and how old is each room's latest one?"*
   - Expected: Boardroom North has 11 hourly points and Phone Booth N2 has only 3. Phone Booth's latest reading is about 2 hours older than Boardroom's.

## Lab 2 — Utilization and occupancy

Tools: `firehose_latest`, `workspace_aggregated_usage_metrics`, `workspace_aggregated_popularity_metrics`, `workspace_aggregated_capacity_utilization`, `workspace_metrics`.

### Easy

1. **Who's in now.** *"How many people are in each room right now?"*
   - Expected: Workshop Bay 3, Huddle A 1, Lab Bench 1, all others 0. No room is booked right now.
2. **Most popular.** *"Rank rooms by actual use."*
   - Expected: Boardroom North 450 min, Huddle A 400, Lab Bench 250, Workshop Bay 200, then Focus Desk 12 and Phone Booth N2 at 50 each.
3. **Wrong-sized rooms.** *"Which rooms are overcrowded or under-utilized?"*
   - Expected: Boardroom North is overcrowded (peak 12 people in 10 seats, ratio 1.2). Focus Desk 12 and Phone Booth N2 are under-utilized.

### Advanced

1. **Booking accuracy.** *"For each room, divide used minutes by booked minutes and explain what the ratio means."*
   - Expected: Boardroom 1.07, Huddle A 0.95, Lab Bench 2.08, Workshop Bay 1.67. Focus Desk and Phone Booth are never booked.
   - A ratio well above 1 means most use comes from walk-ins. That's true for the South Building rooms.
2. **No-shows and walk-ins, hour by hour.** *"Using workspace\_metrics, find hours that were booked but empty, and hours that were used without a booking."*
   - Expected: no booked-but-empty hours.
   - Hours used without a booking: Lab Bench 3, Boardroom North 2, Workshop Bay 2, and 1 each for Huddle A, Focus Desk 12 and Phone Booth N2.
3. **Live vs. history.** *"Does firehose\_latest agree with the latest workspace\_metrics point for each room?"*
   - Expected: yes for headcount (for example Workshop Bay 3, Boardroom 0). The timestamps differ by up to about an hour per room.
4. **Make the case.** *"Recommend one change to the room mix. Cite the numbers from at least two tools."*
   - A strong answer uses the capacity tool (Boardroom at 1.2×) and the usage tool (Focus Desk and Phone Booth at 50 min, never booked). It might suggest moving large meetings to Workshop Bay (8 seats, peak 7).

## Lab 3 — Devices, errors and lifecycle

Tools: `device_search`, `device_event_history`, `device_aggregated_event_history`, `device_error_code_detail_search`, `product_lifecycle`.

### Easy

1. **Fleet status.** *"List all devices with status and RoomOS version."*
   - Expected: 5 devices. Four are connected, and the Lab Bench Board Pro 55 shows warning.
2. **Explain an error.** *"What does SIGNAGE\_CONTENT\_STALE mean and how do I fix it?"*
   - Expected: the signage playlist hasn't refreshed in 24 hours. Push the workspace playlist from Control Hub.
3. **End of sale.** *"Which device models reach end-of-sale soonest?"*
   - Expected: Room Kit Mini on 31 Oct 2026, then Desk Pro on 30 Jun 2027.

### Advanced

1. **Open vs. resolved.** *"Summarize events across the organization, then check each device's history and tell me which issues are still open."*
   - Expected: 5 events (1 error, 2 warnings, 2 info).
   - Huddle A's `CAM_HDMI_SIGNAL_LOST` is resolved, because a recovery event followed about an hour later.
   - Still open: Lab Bench `SIGNAGE_CONTENT_STALE` and Workshop Bay `PROXIMITY_PAIRING_FAIL`.
2. **Triage table.** *"Build a triage table: device, serial, room, open issue, severity and recommended action."*
   - Expected: 2 rows. `GHOSTBRD004` at Lab Bench (warning, push the signage playlist), and `GHOSTBAR005` at Workshop Bay (warning, confirm `Proximity.Mode` is On and that ultrasound isn't blocked).
3. **Risk by usage.** *"Combine lifecycle dates with room popularity. Which replacement matters most?"*
   - Expected: the Room Kit Mini. It reaches end-of-sale in 17 days and sits in Huddle A, the second-most-used room (400 min). Software maintenance for it ends 31 Oct 2029.
4. **Software currency.** *"Which devices are behind on RoomOS, and does that line up with any device issues?"*
   - Expected: the Board Pro 55 (11.26.1.1) and Room Kit Mini (11.28.1.3) trail 11.32.1.5.
   - Both have had events, and the Board Pro 55 is the only device in warning. That's a correlation worth checking, not proof of a cause.

## Lab 4 — Configuration and drift

Tools: `device_configuration_schema`, `device_configuration_template_list`, `device_configuration_list`, `device_configuration_diff`, `device_configuration_template_diff`.

### Easy

1. **What can be set.** *"List the configuration keys and their allowed values."*
   - Expected: 5 keys. `Audio.DefaultVolume` takes 0–100, `Video.Selfview.Default` takes Off / Current / PIP, and `Bookings.Enabled`, `Standby.Control` and `Proximity.Mode` are on/off or true/false. All 5 apply to every model.
2. **Templates.** *"What configuration templates exist?"*
   - Expected: Meeting Room Standard and Personal Desk Standard. Both control the same 5 keys.
3. **One device.** *"Show the Boardroom Room Bar Pro's settings."*
   - Expected: volume 50, self-view Off, bookings True, standby On, proximity On. Its template is Meeting Room Standard.

### Advanced

1. **Fleet drift report.** *"Check every device against its template and tabulate the drift."*

| Device | Template | Drift |
| --- | --- | --- |
| Lab Bench Board Pro 55 | Meeting Room Standard | Volume 45 (template 40); Standby Off (template On) |
| Boardroom North Room Bar Pro | Meeting Room Standard | Volume 50 (template 40) |
| Huddle A Room Kit Mini | Meeting Room Standard | none |
| Workshop Bay Room Bar | Meeting Room Standard | none |
| Focus Desk 12 Desk Pro | Personal Desk Standard | none |

2. **Rule out config.** *"Workshop Bay reported PROXIMITY\_PAIRING\_FAIL. Is its configuration the cause?"*
   - Expected: no. `Proximity.Mode` is On and the device matches its template, so check the room for something blocking ultrasound.
3. **Same model, different rooms.** *"Diff the two Room Bars (Boardroom and Workshop)."*
   - Expected: one key, `Audio.DefaultVolume` (50 vs. 40). Discuss whether a bigger room justifies the louder default.
4. **Remediation plan.** *"Write the exact changes needed to bring every device back to template, and validate each value against the schema."*
   - Expected: Lab Bench needs `Audio.DefaultVolume` 40 and `Standby.Control` On. Boardroom needs `Audio.DefaultVolume` 40. All values are valid under the schema.
   - The server is read-only, so this is a plan, not a change.
5. **Question the template.** *"Lab Bench is an open workspace but uses the meeting-room template. Is that the right template?"*
   - There's no single right answer. Good answers weigh Standby Off (likely deliberate, to keep the board's display on) against keeping to the standard.

## Lab 5 — Locations and the Firehose replay

Tools: `location_search`, `firehose_health`, `firehose_latest`, `firehose_events`.

### Easy

1. **Site map.** *"Show me the location hierarchy."*
   - Expected: Ghost Campus contains North Building (L1, L2) and South Building (L1).
2. **Stream health.** *"Is the Firehose healthy, and what does it subscribe to?"*
   - Expected: status ok, pull channel, replay on, 14 event types. It is a sample replay, not the live Cisco Spaces Firehose.
3. **Who's on which floor.** *"Where are the tracked phones right now?"*
   - Expected: 3 phones, all on North L1, with x/y map positions.

### Advanced

1. **Event mix.** *"Pull Firehose events and count them by type."*
   - Expected: 50 events per pull. `SPACE_OCCUPANCY` is the most common type, at roughly 20 of the 50.
2. **Rebuild a meeting.** *"Using SPACE\_OCCUPANCY\_CHANGE events only, trace Boardroom North's headcount."*
   - Expected: 0 → 2 → 7 → 12 → 8 → 1 → 5. This matches the 12-person peak from Labs 1 and 2.
3. **Visitor journey.** *"Follow ghost-phone-01 across all event types in time order."*
   - Expected: device entry, user entry (`ghost-user-01`), Wi-Fi association, position (20, 30), inactive, position (21, 31), active, then position (21.5, 30.5).
4. **Reconcile the counts.** *"North L1 reports DEVICE\_COUNT, CAMERA\_COUNT and USER\_PRESENCE totals. Why don't they agree?"*
   - Expected: 18 associated plus 5 probing devices, a camera count of 14, and 12 users (8 identified, 4 anonymous).
   - A good answer explains that people carry several devices, cameras miss some people, and identified users depend on sign-in.
5. **Spot personal data.** *"Which Firehose fields would be personal data in a real tenant?"*
   - Expected: email, first and last name, user ID, MAC address, IPv4, and latitude/longitude.

## Stretch goals

These have no single expected answer. Each one lists what a complete result includes.

1. **Campus health report in one prompt.** Ask for a full report covering environment, utilization, device issues, drift and lifecycle.
   - [ ] Boardroom North overcrowded: 12 in 10 seats, 24.2 °C
   - [ ] Focus Desk 12 and Phone Booth N2 under-used: 50 min, never booked
   - [ ] Lab Bench Board Pro: stale signage, oldest RoomOS, two drifted keys
   - [ ] Workshop Bay proximity failure ruled out as a config problem
   - [ ] Room Kit Mini end-of-sale 31 Oct 2026, in the second-busiest room
2. **Room profile.** Pick one room and build a one-page profile by joining every tool on its IDs. A complete profile has 8 parts: location path, device, RoomOS, config drift, open issues, lifecycle dates, utilization and environment peak.
3. **Anomaly hunt.** Find at least three things in the data that don't add up, with the tool output that shows each one. Starting points:
   - Device telemetry and room metrics disagree on temperature.
   - Phone Booth N2 has environment readings but no device.
   - Lab Bench uses a meeting-room template.
4. **Predict and flag.** Use your Lab 1 model to predict Boardroom North's conditions with 15 people. Expected: about 24.65 °C, 63% humidity and noise 58. Then propose a headcount limit that keeps the room under 24 °C (10 people or fewer, which is exactly its seat count).
5. **Repeatable report.** Write one prompt that produces the same weekly report every time. Success: run it twice in fresh sessions and get the same numbers and the same structure.
6. **Runbook per error code.** For each of the three error codes, write the tool sequence an on-call engineer should follow, from detection to fix. Success: each runbook names the tools in order and ends with the catalog's recommended action.
7. **Design the next tool.** Name one question you couldn't answer in these labs, such as who booked a room or what the HVAC set point is. Specify the tool that would answer it: name, inputs, output fields, and which existing IDs it joins on.
