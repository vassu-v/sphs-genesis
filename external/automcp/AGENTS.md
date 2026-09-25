# AGENTS.md

Instructions for any coding or browsing agent working in this folder
(`external/automcp`). Stay inside this folder. Do not change global agent, CLI or git settings.

## What is here

- `auto-browser/` : Auto Browser, an MCP server that drives a visible Chromium.
  - `controller/` : Python (FastAPI) server. MCP endpoint `/mcp`, health `/healthz`.
  - `live-ui/` : Next.js live view. Page per session at `/s/<session_id>`. Spec: `live-ui/CONTRACT.md`.
  - `scripts/start-local.ps1` : run the controller natively on Windows, no Docker.
- `.agents/skills/auto-browser/SKILL.md` : how to connect, start, and use it. **Read it before using the browser tools.**
- `.agents/mcp_config.json` : workspace-local MCP registration for agy (HTTP, port 18480 for tests). Edit the port to match your server.
- `mcp-test/` : Claude Code test harness (`run-claude.ps1` runs it with only this MCP and no built-in tools; `.mcp.json` sets the port).
- `screenshot` returns a real image you can see (JPEG, about 800 tokens; `image:false` for a path only). Read pages with `snapshot` (compact tree with refs usable as `element_id`), `find_elements` and `observe`. See the skill's "Navigate efficiently".

## Using the browser

1. Check: `.\auto-browser\scripts\start-local.ps1 -Port 8000 -Status`. If down, start with `-Background`.
   If the port is used by something else, pick another port. Never kill processes you did not start.
2. Connect your client to `http://127.0.0.1:<port>/mcp` (see the skill for configs).
3. `browser.create_session` first. It returns a session id and a watch link in a boxed banner.
   Print that banner to the user verbatim, then continue.
4. `browser.observe` (`preset: text`) to read, `browser.execute_action` to act. Every action needs a `reason`.
5. `browser.close_session` when finished.

Full tool list: `tools/list`, the `initialize.instructions` text, or `GET /live-api/tools`.

## Working on the code

- Backend tests: `cd auto-browser/controller; python -m pytest -q` (Python 3.10+; deps in `requirements.txt` and `requirements-dev.txt`).
- Frontend: `cd auto-browser/live-ui; npm install; npm run build; npm test`.
- Tool events, phases (`session`, `read`, `screenshot`, `act`, `other`), the API and the banner format are
  defined in `auto-browser/live-ui/CONTRACT.md`. Change the contract and both sides together.
- Test servers: use an uncommon port and stop exactly the process tree you started
  (`start-local.ps1 -Port N -Stop`). Data lives in `auto-browser/.local-data/<port>/` (git-ignored).
- Do not commit or push unless the user asks.

## SHOAV guard demo template

- Agent entry pack for the guarded demo lives in `shoav-mcp/MCP/agent-template/`:
  `AGENT_START.md` (start here), `SETUP.md`, `OUTPUTS.md`, `REVIEW_NPS.md`,
  `mcp_config.json`, `settings.json`.
- Guard demo runs on port 18550 with `-Guard enforce`. Never use port 8000.
- Guard modes: `off` (no guard), `observe` (verdicts only), `enforce` (rewrite and block).
