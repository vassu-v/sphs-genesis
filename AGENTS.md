# Universal Agent Integration Guide — Auto-Browser MCP & S.H.O.A.V.

This workspace connects autonomous AI agents (Antigravity CLI `agy`, Gemini CLI, Claude Code, Cursor, Copilot, etc.) with the native **Auto-Browser MCP** server and the **S.H.O.A.V.** (*Shield for Hostile Operations & Agent Vulnerability*) security engine.

---

## Quick Reference

- **MCP Endpoint**: `http://127.0.0.1:8000/mcp`
- **Global Admin Dashboard**: `http://127.0.0.1:8000/dashboard`
- **Per-Session Live Dashboard**: `http://127.0.0.1:8000/live/{session_id}`
- **Subdirectory Reference**: See [`external/auto-browser/AGENTS.md`](file:///d:/work/genesishackathon/external/auto-browser/AGENTS.md) for full MCP tool definitions.

### Quick Commands
- Start MCP Controller: `cd external/auto-browser/controller && py -3.12 -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- MCP Endpoint: `http://127.0.0.1:8000/mcp`
- Live Per-Session Monitor: `http://127.0.0.1:8000/live/<session_id>`
- Admin Dashboard: `http://127.0.0.1:8000/dashboard`

---

## 1. Registration with Antigravity CLI (`agy`)

To register the local MCP with `agy`:
```bash
agy mcp add --type http auto-browser http://127.0.0.1:8000/mcp
```

To run a task with `agy` using the browser:
```bash
agy "Use the auto-browser MCP to create a session, navigate to https://agenttrickydps.vercel.app/shopping?dp=w, find the rating for 'Dell Inspiron 15', take a screenshot, and report the score."
```

---

## 2. Ephemeral Live Per-Session Dashboard

For every session created via `browser.create_session`:
1. The agent receives the `session_id` and `dashboard_url` (`http://127.0.0.1:8000/live/{session_id}`).
2. Anyone opening that URL sees a dedicated, real-time live monitor:
   - Live browser screenshot stream with HUD telemetry.
   - Action feed showing each action (`navigate`, `click`, `type`, `evaluate`), target selector/coordinates, execution result, and response sent.
   - S.H.O.A.V. security badges verifying whether each step was clean or contained hostile injections / clickjacking overlays.
3. Lifecycle: The dashboard remains active and live while the MCP session is open. Once `browser.close_session` is called or the agent disconnects, the dashboard automatically transitions to an archived session state.

---

## 3. Key Architecture & File Structure

All MCP and browser modifications reside under `external/auto-browser/`:
- `external/auto-browser/controller/app/browser/services/runtime.py` — Native headed Chromium execution (Playwright, no Docker).
- `external/auto-browser/controller/app/ui/session_dashboard.html` — Live per-session monitor UI.
- `external/auto-browser/controller/app/routes/session_diagnostics.py` — Live dashboard routes (`/live/{session_id}`, `/sessions/{session_id}/dashboard`).
- `external/auto-browser/controller/app/browser/services/sessions.py` — Session lifecycle and SSE event dispatching.
- `external/auto-browser/controller/app/browser/services/observation.py` — Real-time screenshot and observation dispatching.
