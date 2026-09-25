# Lab guide

How to use **spaces-mockup-mcp** as a data door while you build another
application or an agent that already talks to other tools. This server is a
synthetic **Mockup Campus** (`@mockup.example`, `Australia/Sydney`).
This server is not a live Cisco API.
Tool names match Webex Workspaces MCP plus a Firehose pull replay so a
harness can practice the same questions you would ask a real Control Hub
org or Spaces partner channel.

Reads only. No bookings, no device PATCH, no partner stream.

## Data sources

The process loads `dataset.json` into memory. Timestamps are stored as
`offset_ms` from query time, so occupancy always looks like the last 24 hours.

| Source | Record type | What you get | Tools |
| --- | --- | --- | --- |
| Locations | Campus / building / floor tree | Six rows: Mockup Campus (Sydney, Pyrmont), North and South buildings, North L1 / L2, South L1. Fields: `locationId`, `name`, `inferredLocationTypes`, city, address, `floor_count` / `floorNumber`, parent. | `location_search` |
| Workspaces | Room inventory | Six rooms: Boardroom North (`ws-board`, meetingRoom, cap 10), Huddle A (`ws-huddle`, 4), Focus Desk 12 (`ws-focus`, desk), Phone Booth N2 (`ws-phone`), Lab Bench (`ws-lab`), Workshop Bay (`ws-workshop`). Fields: `id`, `name`, `type`, `capacity`, `locationId`, `deviceIds`, `capacityNote`. | `workspace_search` |
| Workspace metrics | Clock-shifted time series | Per workspace: `peopleCount`, `presence`, `booked`, `temperatureC`, `humidityPct`, `ambientNoise`, `useMinutes`, `bookedMinutes`. Aggregates expose peak ratio, overcrowded vs under-utilized, and popularity rank. Boardroom North overcrowds at stand-up (12 in a 10-seat room). Huddle A is the popular small room. Focus Desk and Phone Booth are quiet. | `workspace_metrics`, `workspace_aggregated_usage_metrics`, `workspace_aggregated_capacity_utilization`, `workspace_aggregated_popularity_metrics` |
| RoomOS devices | Device inventory | Five codecs: Room Bar Pro (board), Room Kit Mini (huddle), Desk Pro (focus), Board Pro 55 (lab, `connectionStatus=warning`), Room Bar (workshop). Fields: `id`, `displayName`, `product`, `productType`, serial, RoomOS version, `workspaceId`, `locationId`, `connectionStatus`. | `device_search` |
| Device events | Per-device history | HDMI camera loss/recovery on the Kit Mini, stale signage on the Board Pro, proximity pairing fail on the workshop Room Bar, booked call on the board Room Bar Pro. Fields: `deviceId`, `timestamp`, `type`, `code`, `severity`, `message`. | `device_event_history`, `device_aggregated_event_history` |
| Issue catalog | Error definitions | `CAM_HDMI_SIGNAL_LOST`, `SIGNAGE_CONTENT_STALE`, `PROXIMITY_PAIRING_FAIL` with severity and `recommendedAction`. | `device_error_code_detail_search` |
| Product lifecycle | EOS / support dates | Room Bar Pro, Room Kit Mini, Desk Pro, Board Pro 55, Room Bar. Fields: `endOfSale`, `lastDateOfSupport`, `softwareMaintenance`. | `product_lifecycle` |
| Device configuration | Key/value + templates | Live keys: `Audio.DefaultVolume`, `Video.Selfview.Default`, `Bookings.Enabled`, `Standby.Control`, `Proximity.Mode`. Templates `tpl-meeting-standard` and `tpl-desk-standard`. Schema lists types and allowed values. The board Room Bar Pro volume is 50 vs template 40; Lab Bench standby is Off vs On. | `device_configuration_list`, `device_configuration_template_list`, `device_configuration_diff`, `device_configuration_template_diff`, `device_configuration_schema` |
| Firehose EventRecords | Pull replay (`EventRecord` envelope) | Subscribed types: `DEVICE_LOCATION_UPDATE`, `DEVICE_PRESENCE`, `USER_PRESENCE`, `PROFILE_UPDATE`, `DEVICE_COUNT`, `DEVICE_ASSOCIATION`, `CAMERA_COUNT`, `RAW_CAMERA_COUNT`, `IOT_TELEMETRY`, `WEBEX_TELEMETRY`, `SPACE_OCCUPANCY`, `SPACE_OCCUPANCY_CHANGE`, `KEEP_ALIVE`, `APP_ACTIVATION`. Envelope: `recordUid`, `recordTimestamp`, tenant ids, `eventType`, plus a camelCase payload (`spaceOccupancy`, `deviceLocationUpdate`, `webexTelemetryUpdate`, …). Nested `location` / `device` / `space` reuse the same ids as Workspaces tools. | `firehose_health`, `firehose_events`, `firehose_latest` |

Join on `locationId`, workspace `id` / `workspaceId`, and `deviceId`. A typical
agent turn is `workspace_search` → `workspace_metrics` → `firehose_events`
(or `device_search` → `device_event_history` → `device_error_code_detail_search`).

`firehose_latest` is the cheap snapshot: last Wi-Fi `xPos`/`yPos` per device
and last occupancy (`peopleCount`, `peoplePresence`, `bookingStatus`) per
workspace. Use `firehose_events` when you need a typed replay
(`eventType`, `fromTimestamp`, `limit` ≤ 50).

## Building with other apps

Treat this MCP as a **read model**, not a Cisco tenant.

| You are building | How to use Mockup Campus |
| --- | --- |
| Occupancy or workplace analytics | Poll `workspace_aggregated_*` and `firehose_latest`. Join `ws-*` ids into your own dashboard or warehouse. The clock-shift means a demo always has a “today”. |
| Room finder / desk booking UI | `workspace_search` + capacity utilization. Show overcrowded vs empty. Do not write bookings back here — pair a real calendar or booking API for writes. |
| Device health / RoomOS ops | `device_search` (`connectionStatus=warning`), event history, error catalog, config diffs vs template. Open a ticket in Jira/ServiceNow/GitLab with the `code` and `recommendedAction`. |
| Firehose consumer / SIEM lab | Pull `SPACE_OCCUPANCY` or `DEVICE_LOCATION_UPDATE` and map the envelope into Splunk, a queue, or your own schema. Practice `fromTimestamp` replay without a partner key. |
| Multi-MCP agent | Keep spaces-mockup for campus facts. Use another server for mail, wiki, tickets, or code. Pass `ws-board` / `dev-boardpro-lab` as stable ids in the prompt so the agent does not invent rooms. |
| Eval / prompt lab | Fixed dataset + known story (overcrowded boardroom, warning Board Pro). Score whether the agent called the right tools and cited `CAM_HDMI_SIGNAL_LOST` or peak ratio > 1. |

Do not point a production Control Hub integration at this door and expect
real 54NR / 26WR people. Identities stay `@mockup.example`.

## Self-host

Run the server on your laptop, then point the harness at loopback.

1. Clone [andrewkriley/spaces-mockup-mcp](https://github.com/andrewkriley/spaces-mockup-mcp).
2. `cp .env.example .env` and set `MCP_BEARER_TOKEN` to a value you minted.
3. `export MCP_BEARER_TOKEN=` the same value. HTTP will not start if it is empty.
4. `python3 server.py` → `http://127.0.0.1:8080`. `./run.sh` does the same if you have a POSIX shell.
5. `curl -sS http://127.0.0.1:8080/health` should mention spaces-mockup.

Client URL: `http://127.0.0.1:8080/mcp`. Header:
`Authorization: Bearer` plus that token. Optional `python3 server.py --stdio`
is one local client and does not use a bearer.

To publish your own hostname, set `LISTEN=0.0.0.0:8080` and terminate TLS
on a reverse proxy. Do not expose the process on the public internet without
HTTPS.

## Demo server

Do not run the server. Point the harness at
`https://spaces-mockup.apps.andrewriley.info`. `/health` is public.
`/mcp` needs the bearer issued **for that host only**. It is not a token
from another spaces-mockup and it is not the value in `.env.example`.

Client URL: `https://spaces-mockup.apps.andrewriley.info/mcp`.

Ask the person who shared the demo for the bearer. Put it in your shell
environment as `MCP_BEARER_TOKEN`. Do not paste it into git, tickets, or
chat.

## Configure from Claude or Cursor

Do not hand-edit JSON if you can avoid it. Paste the block below into a new
Claude or Cursor chat (Agent / Composer). The assistant writes
`mcp.json` or runs the client’s add-server command. You only supply the
bearer when asked, via the environment, not in the file.

```text
Configure my MCP connection to spaces-mockup. Do not ask me to edit JSON by hand. Do not invent a token. Do not write the bearer into any file that can be committed.

Which door (pick one and say it back):
- Self-host: http://127.0.0.1:8080/mcp  (I already have python3 server.py running with MCP_BEARER_TOKEN set)
- Demo: https://spaces-mockup.apps.andrewriley.info/mcp

Server name: spaces-mockup
Transport: Streamable HTTP (or type http if the client requires it)
Auth header: Authorization: Bearer ${env:MCP_BEARER_TOKEN}
Health (no auth): same host, path /health

If you are Cursor:
1. Prefer Settings → MCP → add a remote / HTTP server named spaces-mockup with that URL.
2. If you must write a file, use ~/.cursor/mcp.json (global) or .cursor/mcp.json (this project only).
3. Interpolate the token. Example header value: Bearer ${env:MCP_BEARER_TOKEN}
4. Do not put a literal secret in mcp.json.

If you are Claude Code / Claude Desktop:
1. Prefer the native add-server / MCP settings UI, or `claude mcp add` with transport http and an Authorization header that reads the env var.
2. If you write claude_desktop_config.json, use the same mcpServers shape and env interpolation. Do not dump a raw token.

After you write the config, tell me exactly which file or setting changed, remind me to export MCP_BEARER_TOKEN in the environment that launches the app, then ask me to restart the client. Then I will send a test prompt from the lab guide. If tools/list is empty or /mcp returns 401, fix the URL path (/mcp) and the Bearer header — do not guess a new token.
```

Cursor interpolates `${env:MCP_BEARER_TOKEN}` in `url` and `headers`.
Some clients also want `"type": "http"`. The README has the raw
`mcpServers` shape if you later need it.

## Suggested prompts

Use these after the harness shows spaces-mockup tools. Ask the agent to
call tools; do not answer from memory.

**Campus walkthrough**

- List every workspace on Mockup Campus. For each room give type, capacity, floor, and attached device.
- Walk the location tree from campus → buildings → floors. Which floors have access points?

**Occupancy and space use**

- Which rooms are overcrowded or under-utilized right now? Cite peak ratio and use minutes.
- Is Boardroom North over capacity at stand-up? Compare `workspace_metrics` for `ws-board` with the latest `SPACE_OCCUPANCY` Firehose records.
- Rank rooms by actual use. Where should I sit if I want a quiet desk?

**Devices and config drift**

- Which RoomOS devices are not `connected`? What does the issue catalog say I should do?
- Diff Lab Bench (`dev-boardpro-lab`) against its configuration template. What drifted?
- Compare Boardroom North’s Room Bar Pro config to Huddle A’s Room Kit Mini.
- Which products are closest to end of sale?

**Firehose / other apps**

- Pull the last `DEVICE_LOCATION_UPDATE` events and plot who is on North L1.
- Give me a JSON sketch of a Splunk event I could index from one `SPACE_OCCUPANCY` record (no secrets).
- You also have my ticketing MCP. Open a draft incident for the Board Pro warning using the error code and recommended action. Do not file it until I say so.

**Harness smoke**

- Call `firehose_health`, then `tools/list` style inventory: how many tools do you have, and which ones are Firehose?
