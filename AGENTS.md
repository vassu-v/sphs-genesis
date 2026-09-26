# Connect an agent to S.H.O.A.V.

S.H.O.A.V. is a browser MCP server with a guard in the path. Any agent that can call an MCP tool over HTTP
(Antigravity CLI `agy`, Claude Code, Gemini CLI, Cursor, OpenCode) can use it.

## Ports

| What | URL |
|---|---|
| MCP endpoint | `http://127.0.0.1:18500/mcp` |
| Health | `http://127.0.0.1:18500/healthz` |
| Guard mode and counters | `http://127.0.0.1:18500/live-api/guard` |
| Live view (watch link per session) | `http://127.0.0.1:3200/s/<session_id>` |

Never use 8000, 18480 or 3100 for this project. Those belong to the upstream defaults and other tools.

## 1. Start the server

From `shoav-mcp/MCP/auto-browser`. Pick one guard mode:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-local.ps1 -Port 18500 -Guard enforce -Background
```

`-Guard` is `off` (no guard), `observe` (checks run and are logged, nothing changes) or `enforce` (rewrites and blocks apply).
Add `-Headless` to hide the browser window. Stop with `-Stop`, check with `-Status`.

Live view, in a second terminal from `shoav-mcp/MCP/auto-browser/live-ui`:

```powershell
npm install
npm run build
npm start
```

## 2. Register the MCP with your agent

```bash
# Antigravity CLI
agy mcp add --type http auto-browser http://127.0.0.1:18500/mcp

# Claude Code
claude mcp add --transport http auto-browser http://127.0.0.1:18500/mcp
```

Or drop `shoav-mcp/MCP/agent-template/mcp_config.json` into your client config:

```json
{ "mcpServers": { "auto-browser": { "type": "http", "url": "http://127.0.0.1:18500/mcp" } } }
```

The start script sets `MCP_TOOL_NAME_STYLE=underscore`, so tools appear as `browser_observe`, `browser_execute_action` and so on.
Clients such as `agy` reject dotted names.

## 3. What the agent sees

Typical loop: `browser_create_session`, then `browser_observe` or `browser_snapshot`, then `browser_execute_action`.
Every session result carries a watch link.

| Verdict | What comes back |
|---|---|
| ALLOW | The normal result. |
| REWRITE | The normal result with dangerous text removed and a leading `_shoav` note (`verdict`, `findings`, `summary`). Carry on with the cleaned content. |
| BLOCK | `isError: true`. The `error` says what was in the way (for example an invisible layer over the button). Do not retry the click. Re-observe the page, or ask for human takeover. |
| ESCALATE | `isError: true`. Suspicious but not provable, for example a form submitted with an untouched pre-ticked consent box. Re-observe the form, tick or untick it on purpose, or ask a human. |

## 4. What the human sees

Open the watch link. Each tool call is a row, with a guard badge (REWRITE amber, BLOCK red, ESCALATE orange). Expand a row for
the reason and findings. The header chip shows running counters. After `browser_close_session` the same link is a read-only archive.

## 5. Quick check

```powershell
curl http://127.0.0.1:18500/healthz
curl http://127.0.0.1:18500/live-api/guard
python shoav-mcp/t5_e2e/run_t5.py --controller http://127.0.0.1:18500 --fixture-port 18631 --mode enforce
```

The last command serves the synthetic fixtures and runs the whole matrix. See [`shoav-mcp/MCP/README.md`](shoav-mcp/MCP/README.md)
for every mode and [`shoav-mcp/MCP/REPORT.md`](shoav-mcp/MCP/REPORT.md) for the measured results.

## 6. The skill

Agents that already have their own browser can install the skill instead. It is advice, not enforcement.

```bash
node shoav-skill/bin/cli.js --target claude    # or --target cursor, --target agy
```

Once the package is published this is `npx shoav-skill --target claude`.

See [`shoav-skill/README.md`](shoav-skill/README.md).

## 7. Tool reference

The tool list and their arguments come from the MCP itself (`tools/list`). The upstream project, its docs and its licence are in `shoav-mcp/MCP/auto-browser/` (`README.md`, `docs/`, `LICENSE`).
