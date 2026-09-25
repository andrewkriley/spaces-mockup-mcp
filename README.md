# spaces-mockup-mcp

Read-only MCP for a synthetic **Mockup Campus**. Same tool names as Webex
Workspaces MCP plus Cisco Spaces Firehose pulls. No live Cisco APIs. Identities
are `@mockup.example` only.

Python 3.12+, standard library only. Use the hosted demo or run your own.

## Tools

Nineteen reads.

| Group | Tools |
| --- | --- |
| Locations | `location_search` |
| Workspaces | `workspace_search`, `workspace_metrics`, `workspace_aggregated_usage_metrics`, `workspace_aggregated_capacity_utilization`, `workspace_aggregated_popularity_metrics` |
| Devices | `device_search`, `device_event_history`, `device_aggregated_event_history`, `device_error_code_detail_search`, `product_lifecycle`, `device_configuration_*` |
| Firehose | `firehose_health`, `firehose_events`, `firehose_latest` |

Occupancy is a clock-shifted weekday. Boardroom North overcrowds at stand-up
(12 in a 10-seat room).

## Demo server

Hosted instance: `https://spaces-mockup.apps.andrewriley.info`. `/health` is
open; `/mcp` needs a bearer. That bearer is **only** for this host. It is not `local-dev`
and it is not a token from another spaces-mockup server.

```bash
export MCP_BEARER_TOKEN=   # demo-host token
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

## Self-host

```bash
make venv && make lint && make test
```

Stdio (no bearer; one client per process):

```json
{
  "mcpServers": {
    "spaces-mockup": {
      "command": "${workspaceFolder}/.venv/bin/python",
      "args": ["${workspaceFolder}/server.py", "--stdio"]
    }
  }
}
```

Loopback HTTP: `cp .env.example .env && ./run.sh` then
`Authorization: Bearer local-dev` at `http://127.0.0.1:8080/mcp`.

To publish your own URL, set a non-default `MCP_BEARER_TOKEN` and `LISTEN`
(for example `0.0.0.0:8080`) and terminate TLS on a reverse proxy. Do not
expose the process on the public internet without HTTPS.

`dataset.py` rewrites `dataset.json`. Capacity notes:
[docs/capacity.md](docs/capacity.md).
