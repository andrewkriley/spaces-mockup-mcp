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
(12 in a 10-seat room).

## Self-host

Python 3.12+ only. No Make, Xcode, or extra packages. Set `MCP_BEARER_TOKEN`
(HTTP will not start without it), then run the server:

```bash
cp .env.example .env
export MCP_BEARER_TOKEN=   # same value as in .env
python3 server.py
```

`./run.sh` does the same thing and sources `.env` if you have a POSIX shell.

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

Optional: `python server.py --stdio` for one local client. That path does not use a bearer.

## Demo server

Hosted instance: `https://spaces-mockup.apps.andrewriley.info`. Do not run the
server. `/health` is open; `/mcp` needs a bearer. That bearer is **only** for
this host. It is not `local-dev` and it is not a token from another spaces-mockup
server.

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
