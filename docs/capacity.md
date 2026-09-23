# Capacity: 100 users, 50 concurrent MCP questions

Planning note for hosting `spaces-ghost-mcp` beyond a single workstation.
Target: **~100 named users**, **~50 concurrent MCP questions**, each question using **multiple tools**.
Hosting options to compare: **(1) AWS** and **(2) a dedicated server** (or equivalent always-on VPS).

This is not an implementation spec. Open a GitHub issue assigned to `mrchurchi` when the tracker allows it.

## Target load

Do not treat “50 concurrent questions” as 50 HTTP requests.

A typical question from Cursor, Claude, or another agent is a **burst**:

1. `initialize` (and often `notifications/initialized`)
2. `tools/list` (sometimes cached after the first call)
3. Several `tools/call`s — often 2–8 tools, sometimes in parallel (search → metrics → firehose → config diff)

So 50 concurrent questions with multiple tools is closer to:

- **50 concurrent agent sessions**
- **~100–400 concurrent `POST /mcp` requests** at the peak of a burst
- Plus long-lived connections if we adopt Streamable HTTP + SSE

100 users is the named population. Only a subset will be asking at once; 50 concurrent is the design peak.

The expensive part of that picture is almost never this process. Ghost Campus is a **~110 KB in-memory JSON file** (6 locations, 6 workspaces, 5 devices, 77 firehose rows). Tool handlers are CPU-bound filters plus `json.dumps` over tiny lists. The LLM that *asks* the questions is a separate cost.

If we later swap the ghost dataset for live Control Hub / Spaces Firehose, **upstream Cisco rate limits and pull-channel backpressure become the real ceiling**, not Python.

## Current stack

From `server.py` and `README.md` today:

| Area | Today | Why it matters at this load |
| --- | --- | --- |
| Runtime | Python 3.12, **stdlib only** | Fine for a workstation; no production ASGI, workers, or timeouts |
| Transports | **stdio** (one client per process) or **loopback HTTP** (`ThreadingHTTPServer` on `127.0.0.1:8080`) | stdio cannot be shared by 100 users. HTTP is the only multi-client path |
| HTTP shape | `POST /mcp` → one JSON-RPC object; `GET /health` | Not full [Streamable HTTP](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports): no `Accept` negotiation, no SSE, no `Mcp-Session-Id`, no `MCP-Protocol-Version`, `GET /mcp` is 404 |
| Auth | Single shared `MCP_BEARER_TOKEN` | One leaked token = every tool for every user. No per-user identity, scopes, or revocation |
| Concurrency | One process, one thread per request, GIL | Tiny dataset means this is *probably* enough for 50 bursts, but there is no accept queue, request timeout, body-size cap, or graceful shutdown |
| Bind / TLS | Loopback by default; no TLS | Cannot be a remote MCP URL until it sits behind HTTPS |
| Process mgmt | `./run.sh` | No systemd / container restart, no rolling deploy |
| Observability | stderr access log + `/health` | No metrics (in-flight, latency, tool name, 401s), no structured logs, no tracing |
| Dataset | Read-only in-process `dataset.json` | Good: no lock contention. Cheap to copy per worker. Not enough if we grow toward a live firehose |

`ThreadingHTTPServer` can take concurrent POSTs, and the handlers do not mutate shared state, so **raw compute is not the first problem**. Protocol compatibility, auth, TLS, process lifecycle, and client-era session behavior are.

## What the application stack likely needs

### Must-have before a shared hostname

1. **Remote transport = Streamable HTTP**, not stdio and not the current custom JSON POST door.
   - Official production path: one HTTPS URL, typically `POST`/`GET` `/mcp`.
   - Prefer staying **stateless / JSON-response** while tools stay request/response. That lets any replica answer any request (especially on spec `2026-07-28`, which is sessionless by construction).
   - If we keep supporting current Cursor/Claude **sessionful** clients (`Mcp-Session-Id`, initialize handshake), either:
     - sticky sessions on that header, **or**
     - `stateless_http=True` on the legacy leg (loses server-to-client back-channel / resumability).
   - Strongly consider the **MCP Python SDK** (`MCPServer` + `streamable_http_app()`) instead of growing `http.server`. See [Deploy & scale](https://py.sdk.modelcontextprotocol.io/run/deploy/).

2. **A real HTTP server in front of the app**
   - ASGI: uvicorn (optionally gunicorn + UvicornWorker), 2–4 workers.
   - Timeouts, keep-alive, `limit_concurrency`, graceful drain.
   - Bind **loopback only**; terminate TLS at a proxy / load balancer.
   - Behind a proxy: `--proxy-headers` plus a tight `forwarded-allow-ips` so redirects do not downgrade HTTPS → HTTP.

3. **Host / Origin allowlisting**
   - Streamable HTTP **must** validate `Origin` (DNS rebinding).
   - SDK default only allows localhost until `TransportSecuritySettings(allowed_hosts=..., allowed_origins=...)` is set. Missing this looks like “the server is up but every client gets 421”.

4. **Auth that can survive 100 people**
   - Per-user or per-client credentials, not one shared `local-dev` bearer.
   - HTTP MCP is specified as an **OAuth 2.1 resource server**: verify bearer on **every** request, publish RFC 9728 protected-resource metadata, `WWW-Authenticate` on 401. See [Authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization) and [Python SDK auth](https://py.sdk.modelcontextprotocol.io/run/authorization/).
   - Pragmatic stepping stone: issued API keys in a secret store, hashed at rest, rate-limited per key — then OAuth (Cognito / Entra / Auth0 / Keycloak) if clients can do the discovery dance.
   - Rate limit by identity so one looping agent cannot crowd out the other 49.

5. **Production HTTP hygiene**
   - Max body size, request timeout, concurrency cap (queue + 429, not unbounded threads).
   - Structured logs: `request_id`, tool name, latency, status, caller id (never the token).
   - Metrics: in-flight requests, p95/p99 per tool, 401/429/5xx, worker count.
   - Keep `/health` unauthenticated for probes; do not put dataset internals on it.

6. **Packaging**
   - Dockerfile (Python 3.12-slim, non-root, `dataset.json` baked or mounted).
   - Pin runtime deps if we leave “stdlib only”.
   - Keep `make lint` / `make test` and add a **load test** that models the real burst: 50 virtual users × 3–6 sequential/parallel `tools/call`s (k6, Locust, or an MCP stress tester).

### Nice-to-have / only if we grow past ghost data

- Shared secret for `RequestStateSecurity` **if** we add multi-round-trip tools (elicitation / `Resolve`). Default per-process keys break across workers.
- Redis / NATS `SubscriptionBus` **only if** we add live subscriptions.
- If Firehose becomes a real partner stream: one pull/consumer process, durable offset, backpressure, and a cache — **do not** open 50 Cisco streams for 50 questions.
- Horizontal scale is optional at this size. One box with 2 workers is likely enough for the ghost dataset.

### Load-test acceptance sketch

Treat a hosting spike as done when a candidate deploy can show:

- 50 concurrent “questions”, each calling ≥3 tools (mix of cheap search + `firehose_events` + a diff)
- p95 tool-call under 100 ms on ghost data (should be easy); p99 connection errors ≈ 0
- 401s for bad tokens; 429s under a deliberate stampede
- Rolling restart does not 5xx the health check for more than a few seconds

## Option 1 — AWS

**Fit:** team already in AWS, wants TLS + HA + secrets without SSH, or expects this to sit next to other company services.

Recommended shape (always-on, low CPU, HTTP/SSE-friendly):

| Piece | Suggestion | Why |
| --- | --- | --- |
| Compute | **ECS Fargate** 2 tasks, **0.5–1 vCPU / 1–2 GB** each, or one **t4g.small / t3.small** if we accept a single instance | Ghost data will not use this CPU. Two tasks buy restart cover, not compute |
| Edge | **ALB** + ACM cert on a public hostname, HTTP/2, idle timeout raised if we use SSE | TLS and health checks (`/health`) without managing nginx |
| Scaling | Target tracking on CPU or ALB request count; min 1–2, max 4 | 50 concurrent questions should not need max 4 on ghost data |
| Secrets | **Secrets Manager** or SSM for bearer/OAuth verifier keys | Stop shipping `MCP_BEARER_TOKEN` in `.env` on a public bind |
| Logs / metrics | CloudWatch logs + Container Insights; later ALB access logs | Need tool-level latency, not just 2xx counts |
| Network | Private subnets, public ALB only; security group: 443 from clients | Matches “do not bind `0.0.0.0` naked” |
| Optional | WAF rate rules; Route 53 | Only if the URL is on the public internet |

**Avoid Lambda** as the first choice: Streamable HTTP / possible SSE / initialize sessions fight the protocol. Fargate or EC2 is the boring match.

**Ballpark (us-east-1, always-on, order-of-magnitude):**

- 2× Fargate 0.5 vCPU / 1 GB ≈ **$35–40/mo** compute
- ALB ≈ **$16–25/mo** + LCU (this traffic is tiny)
- Logs / NAT / secrets: another **$5–20/mo**
- **About $60–90/mo** for a proper small HA service
- Cheaper path: single `t4g.small` (~$12/mo) + ALB, or an instance with Caddy and no ALB (~$15–25/mo) if HA is not required

**AWS-specific work in the app:** health-check path, container listen on `0.0.0.0:$PORT` *behind* the ALB, `transport_security` host allowlist = the public hostname, task definition for 2 workers **or** 2 tasks with 1 worker each.

If clients are still sessionful, ALB stickiness must hash `Mcp-Session-Id` (not only client IP). Stateless/JSON mode avoids that.

## Option 2 — dedicated server (or one VPS)

**Fit:** one team-owned box, lowest cost, SSH is acceptable, HA can wait.

A **2 vCPU / 4 GB** host (Hetzner CX22-class, OVH, an existing colo VM, or a single EC2) is oversized for ghost data and still the right minimum so nginx + 2 workers + logs have headroom.

Classic stack:

```
Internet → :443 nginx/Caddy (TLS, HTTP/2, rate limit)
         → 127.0.0.1:8080 uvicorn --workers 2
         → systemd (restart, journald)
```

| Piece | Suggestion |
| --- | --- |
| TLS | certbot or Caddy; HTTP → HTTPS redirect |
| Process | systemd unit, non-root user, `Restart=on-failure`, env file mode 0600 |
| Proxy | `proxy_http_version 1.1`; if SSE: `proxy_buffering off`, long `proxy_read_timeout` |
| Firewall | 22/80/443 only (plus the provider firewall, not only ufw) |
| Deploy | git pull / docker compose on the box, or a tiny CI rsync job |
| Backup | image or restic; dataset is in git so the important backup is **secrets + nginx config** |
| Observe | journald + nginx access log; optional Prometheus node exporter |

**Ballpark:** **$5–25/mo** for a VPS, or $0 incremental on a server we already run.

### Tradeoffs vs AWS

| | AWS (ALB + 2 Fargate tasks) | Dedicated / VPS |
| --- | --- | --- |
| Monthly cost | Higher (~$60–90 if done “properly”) | Lower |
| TLS / DNS | ACM + ALB | You run certbot/Caddy |
| Patching | AWS patches the host | You patch Ubuntu |
| HA | Two tasks, easy | One box = one outage |
| SSE / sticky sessions | ALB idle timeout + stickiness to configure | nginx `hash $http_mcp_session_id consistent` |
| Compliance / VPC | Easier to drop beside existing AWS apps | Easier if the campus already has a rack/VPN |
| Blast radius | Security group + optional WAF | One public IP; harden SSH |

For **100 users / 50 concurrent ghost questions**, option 2 is technically enough. Choose AWS if we need org-standard networking, secrets, and a second task more than we need $50/mo.

## Recommendation to validate

1. **Do not scale Kubernetes.** This repo is not a cluster service; the load does not justify it.
2. **Fix the app for a shared HTTP URL first** (Streamable HTTP, TLS-ready ASGI, per-client auth, limits, health, load test).
3. **Host on one 2 vCPU box or two tiny Fargate tasks** — compute-equivalent. Pick AWS vs dedicated from **ops preference**, not from CPU.
4. Revisit size only if (a) we attach live Cisco APIs, (b) we add streaming subscriptions, or (c) load test shows GIL/JSON saturation (unlikely on this dataset).

## Open questions

1. Confirm the load model (50 concurrent *questions* vs 50 concurrent *HTTP requests*; expected tools per question).
2. Which clients must work (Cursor URL transport, Claude, custom agents) and whether they are sessionful today.
3. App-stack change list (SDK vs keep stdlib; auth approach).
4. Hosting pick: **AWS** vs **dedicated**, with a sketched bill and an ops owner.
5. What we would load-test before calling the design done.

## References

- Current process: `server.py` (`ThreadingHTTPServer`, `/mcp` POST, shared bearer)
- [MCP transports (2025-06-18)](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
- [MCP authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)
- [MCP Python SDK — deploy & scale](https://py.sdk.modelcontextprotocol.io/run/deploy/)
- [MCP Python SDK — authorization](https://py.sdk.modelcontextprotocol.io/run/authorization/)
- [Streamable HTTP 2026-07-28 (sessionless)](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)
- [AWS Fargate pricing](https://aws.amazon.com/fargate/pricing/)
