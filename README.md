# spaces-mockup-mcp

Read-only MCP for a synthetic **Mockup Campus**. Same tool names as Webex
Workspaces MCP plus Cisco Spaces Firehose pulls. No live Cisco APIs. Identities
are `@mockup.example` only.

Python 3.12+, standard library only. HTTP door: public `/health`, `/mcp` needs
`Authorization: Bearer` from `MCP_BEARER_TOKEN` set when the process starts.

## Tools

Nineteen reads.

| Group | Tools |
| --- | --- |
| Locations | `location_search` |
| Workspaces | `workspace_search`, `workspace_metrics`, `workspace_aggregated_usage_metrics`, `workspace_aggregated_capacity_utilization`, `workspace_aggregated_popularity_metrics` |
| Devices | `device_search`, `device_event_history`, `device_aggregated_event_history`, `device_error_code_detail_search`, `product_lifecycle`, `device_configuration_*` |
| Firehose | `firehose_health`, `firehose_events`, `firehose_latest` |

Occupancy is a clock-shifted weekday. Boardroom North overcrowds at stand-up
(12 in a 10-seat room). Data map, other-app ideas, and a Claude/Cursor
setup prompt: [docs/lab-guide.md](docs/lab-guide.md).

## Self-host

Python 3.12+ only. No Make, Xcode, or extra packages. Clone this repo, set
`MCP_BEARER_TOKEN` (HTTP will not start without it), then run the server.

```bash
cp .env.example .env
export MCP_BEARER_TOKEN=   # same value as in .env
python3 server.py          # http://127.0.0.1:8080
```

`./run.sh` sources `.env` and starts the same process if you have a POSIX shell.

```bash
curl -sS http://127.0.0.1:8080/health
```

```json
{
  "mcpServers": {
    "spaces-mockup": {
      "url": "http://127.0.0.1:8080/mcp",
      "headers": {
        "Authorization": "Bearer ${MCP_BEARER_TOKEN}"
      }
    }
  }
}
```

To publish your own URL, set a non-loopback `LISTEN` (for example `0.0.0.0:8080`)
and terminate TLS on a reverse proxy. Do not expose the process on the public
internet without HTTPS.

`dataset.py` rewrites `dataset.json`. Capacity notes:
[docs/capacity.md](docs/capacity.md).

Optional: `python3 server.py --stdio` for one local client. That path does not use a bearer.

## Demo server

The hosted URL is for **specific demo use cases** only. Do not run the
server. Point a client at `https://spaces-mockup.apps.andrewriley.info`.
`/health` is open; `/mcp` needs a bearer.

The maintainer provides that bearer for those demos. It is **only** for this
host. It is not `local-dev` and it is not a token from another spaces-mockup
server.

```bash
export MCP_BEARER_TOKEN=   # token from the maintainer
curl -sS https://spaces-mockup.apps.andrewriley.info/health
```

```json
{
  "mcpServers": {
    "spaces-mockup": {
      "url": "https://spaces-mockup.apps.andrewriley.info/mcp",
      "headers": {
        "Authorization": "Bearer ${MCP_BEARER_TOKEN}"
      }
    }
  }
}
```

Do not paste the token into the file. Some clients want `"type": "http"`.

## Data and timestamps

`python3 dataset.py` rewrites `dataset.json`. That file is a fixed Mockup
Campus: locations, rooms, RoomOS devices, and a weekday occupancy curve.
The running server loads it once and does not update Spaces data.

Timestamps are stored as `offset_ms` from query time. Each read adds that
offset to now, so occupancy and firehose events always look like the last
24 hours. Inventory and counts stay the same until you run `dataset.py`
again.
