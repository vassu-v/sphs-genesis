# progress.md

Append-only log of what has been built, in order. Newest stage at the bottom. Edit old entries only to fix mistakes.
Dates are 2026-09-25 unless stated. Times are local.

## Where we are right now

Stage 13: minimal tool profile built and verified with a real Claude Code agent (see Stages section 13).
Docker removal done. Still open: compact mode build, `browser_open`/click-by-text tools,
tracing defaults, `.github` CI references to deleted compose files. Nothing committed or pushed.

Working and verified: visible Chromium, live view UI, session banner, Claude Code and agy both driving the MCP.
Not built yet: anything under "Open decisions".

## How we started

Started in `external/automcp/` containing a stock upstream clone `auto-browser/` (an MCP server that drives Chromium,
normally in Docker). The user supplied a third-party guide about running it locally and asked for a review of this
clone only, then targeted edits. The first attempt read files outside the folder; the user corrected that and the scope
was fixed to `automcp/`.

## Stages

### 1. Review of the clone (done)
- Read the guide and the clone. The guide describes a differently modified copy (stdio server, `genesis.ping`, tags).
  None of that exists here. What matches: the architecture (transport, gateway, registry, packs).
- Findings on this clone: MCP over HTTP at `/mcp`; 36 tools in the curated profile; defaults assume Docker
  (`session_isolation_mode=shared_browser_node`, `/data/...` paths, restricted `allowed_hosts`).

### 2. Headed local browser (done, verified)
- Changed: `controller/app/config.py` (`headless`, default False), `controller/app/browser/services/runtime.py`
  (`_should_launch_local`, launches Chromium itself when no browser node is configured).
- Verified on port 18431: no `--headless` flag on the Chromium process; create, observe, click, close worked.
- Findings: click-driven navigation is not checked against the host allowlist. Every result carries a long `session` block.
  `execute_action` requires `reason` (not mentioned in its description).

### 3. Live view design and contract (done)
- Wrote `auto-browser/live-ui/CONTRACT.md`: ports, tool phases (session, read, screenshot, act, other), event shapes,
  `/live-api` endpoints, persistence, banner format, redaction rules.
- Assumptions made: "Chatshare" means shadcn/ui. "Archive and restart" means a closed session becomes a read-only page
  at the same link with a Restart button that opens a new session at the same start URL.

### 4. Parallel build by two subagents (done)
- Backend agent: `app/live/{phases,banner,recorder,calls}.py`, `routes/live_api.py`, gateway hooks, SSE ids, CORS,
  config, instructions text, 42 tests. Baseline suite 1003 passed; after 1051 passed.
  Bug it found and fixed: implicit session targeting counted closed sessions as live.
- Frontend agent: Next.js 16 app, sessions list, session page (screenshot pane, timeline, Tools tab), archived state with
  Restart, reducer and hook with tests, mock controller, Playwright screenshots. Lint, typecheck, vitest passed.
- Also written by me: `scripts/start-local.ps1` (start, status, stop, native), `.gitignore` additions,
  `.agents/skills/auto-browser/SKILL.md`, `AGENTS.md`. Fixed a PowerShell parse bug in the script.

### 5. Independent review and fixes (done)
- A separate reviewer agent reported 16 findings, none blocking. Fixed by the backend agent: writes to closed sessions,
  URL query secret redaction, `eval_js` result redaction, over-redaction of `passed`, lone surrogate crash, restart CSRF
  check (Origin), lazy archive of sessions closed by other routes, timeline paging and byte budget, close race,
  cancellation shield, top-level-only key dropping. Suite after: 1067 passed, 5 skipped.
- Frontend follow-up: paged timeline loading, ignore legacy events without `type` and `seq`.
- Not fixed (decided out of scope): UI cannot work when the controller requires a bearer token; password field behind an
  opaque element id is not detected; error messages not URL-scrubbed; SSE queue drops give no gap signal.

### 6. Real agent runs (done)
- Claude Code with no built-in tools, only the MCP: Google then YouTube task. 13 calls, 114 s. Google returned a bot check
  (HTTP 429) and the agent stopped there and said so; YouTube search, ad skip and playback worked.
- First run had an empty tool list: PowerShell 5.1 dropped `--tools ""`. Fixed in `mcp-test/run-claude.ps1`.
- Defect found: the banner did not reach the agent (only content block 0 is passed through by Claude Code).
  Fix: `_notice` and `live_view` are now the first keys of block 0 for every session-creating call.
- Even then Claude Code did not show the banner to the user in three tries (terse notice, explicit notice, explicit user
  request). Conclusion: an MCP cannot force a client to print; agents follow `AGENTS.md` and the skill instead.

### 7. agy (Antigravity) support (done, verified)
- Root cause of "0 tools": agy rejects tool names containing a dot.
- Added `mcp_tool_name_style` setting (`MCP_TOOL_NAME_STYLE`, default dotted). Registry advertises underscore names when set
  and accepts both spellings on call. `start-local.ps1` sets underscore. New test file `tests/test_tool_name_style.py`.
- Bug caused by the change and fixed: recorder used the raw name so phases showed `other`. Gateway now records the canonical
  name; regression test added. Related tests: 122 passed. The full suite was not re-run after this change.
- Removed agy's global `auto-browser` registration at the user's request (`agy mcp remove auto-browser`).
  Workspace config is `.agents/mcp_config.json` (HTTP to 18480, server named `auto-browser` so agy's existing allow rule matches).
- agy runs: example.com and Wikipedia (Alan Turing). agy read `AGENTS.md` and the skill by itself and printed the banner both times.
  Client name in the controller: `antigravity-client`.

### 8. Skill update for efficient navigation (done)
- Measured costs on the Alan Turing article and added a "Navigate efficiently" section to the skill (find_elements first,
  direct search URLs, cap `limit`, never `get_html`, screenshots are files not images).
- Skill's agy config now uses the tested HTTP form; documents the underscore names and the print-mode allow rule.

### 9. Efficiency investigation and plan (in progress, no code)
- Explained the "0 screenshots" counter (it counts explicit screenshot calls; automatic before/after action captures are
  not counted). Explained the preview pane (latest screenshot attached to a tool event, not a live feed).
- Measured image and HTML costs. Plan and open decisions are in `context.md`.
- Measured the tool catalogue: 36 tools, about 8,900 tokens per model turn (largest fixed cost). The first attempt failed
  with `KeyError: 'result'`, likely the controller's rate limiter during a burst of calls; retry succeeded.
- The user asked for `context.md`, `progress.md` and `CLAUDE.md` in this folder; created them.

### 10. Approved builds after the efficiency discussion (in progress)
- User answers: yes to a screenshot the agent can see (opt-in, callable by any agent); yes to a real browser frame feed
  instead of refresh; yes to a DOM service if none exists; compact mode liked but implementation questions asked first.
- Checked before building: the accessibility tree is dead (`accessibility_outline` is always `available: false`,
  Playwright 1.62 removed `page.accessibility`). `Locator.aria_snapshot(mode="ai", depth=, boxes=)` works but is huge unpruned
  (Alan Turing article: 459,000 chars default, 737,000 with refs, 15,000 at depth 6). Data is all local files plus SQLite.
- Subagents launched: BACKEND-TOOLS (`browser.screenshot` image block, new `browser.snapshot` tool, recorder must not store
  base64, skill and AGENTS.md updates) and STREAM (CDP screencast MJPEG route `/live-api/sessions/{id}/stream`, UI live feed with
  fallback, fix misleading screenshot counter). They own separate files; test ports 18490, 18491, 3111, 18451.
- Not started, waiting for approval: compact result mode, smaller default tool profile, `browser_open`/click-by-text tools,
  tracing off by default.

### 11. Continuation: interrupted work closed out (done, verified only, no new code)
- The "small snapshot fix" Claude was doing at interruption was already in the working tree:
  scoped-table text fallback (`snapshot_script.py`), image alt for scoped snapshots, tiny-body hint in
  `snapshot.py`, one-line doc touches, regression test `test_scoped_infobox_keeps_facts_and_alt`.
- Verified by a subagent: `test_screenshot_snapshot.py` 31 passed, `test_live_screencast.py` 15 passed.
  Live e2e on port 18492 (Grace Hopper page, `table.infobox`): body 1457 chars, Born/Died/1906/1992 present.
- Deployed state checked: 18480 (`/healthz`, stream-stats) and 3100 both answer and already run the new code;
  the UI build contains `live-feed`. Port 8000 untouched. A server on 18492 was already up (not ours, left running).
- Checklist: picked compact result mode (6.1) as the one item. Researched only: compact after `live_call.finish`
  in `gateway.py` so the recorder keeps full data; observe about 4,600 to about 2,000 tokens; env plus per-call
  `verbosity` escape hatch; risky tests and UI-safe fields listed. Plan presented for discussion, nothing built.

#### Stage 10 results
- STREAM agent done: CDP screencast MJPEG at `/live-api/sessions/{id}/stream` (about 6 fps, about 37 KB/s per viewer, lazy start/stop,
  viewer caps 5 per session and 20 total), UI Live/Captures toggle with fallback, counter renamed `captures`. 15 new tests.
- BACKEND-TOOLS agent done: `browser.screenshot` returns a real JPEG image block (about 62 KB, about 800 tokens; `image:false` for path only),
  new `browser.snapshot` (pruned tree, refs equal to `element_id`, hidden text skipped and counted, 8,000 chars default), observe
  `accessibility_outline` now says why it is unavailable, element ids are now deterministic (`op-s1`...). 30 new tests. Suite 1122 passed.
- Verified with a real Claude Code run: the image reaches the model (its description matched the actual screenshot).
- Defect found in that run: Claude Code passes `structuredContent` and ignores the text block when both exist, so the snapshot tree never
  reached the model. Fixed (snapshot responses omit structuredContent; recorder still sees the metadata) and verified with a real Claude Code run on Hacker News: the tree arrived, 4 calls, titles read correctly. 117 related tests pass; full suite not re-run after this fix. ruff flags one unused variable in `runtime.py:107` (not from this change).
- Independent review of these three features was started and cut off by the usage limit; NOT done. Re-run when budget allows.
- Test controller (18480) and UI (3100) run the new code except the pending snapshot fix.

### 12. Docker removal (done)
- Deleted 12 paths: 5 Dockerfiles incl. reverse-ssh dir, 5 compose files, `scripts/compose_local.sh`, parity test file.
- Kept `browser-node/` (has real `server.mjs` code).
- Makefile / `.devcontainer` / smoke scripts stubbed to NOTEs (native guidance, no Docker).
- Controller `docker_ephemeral` neutralized to explicit errors: `session_isolation.py`, `readiness.py`, `runtime_policy.py`, `compliance.py`, `sessions.py`, `takeover.py`, `remote_access.py`, `runtime.py`.
- Takeover tool kept (tests demand success).
- Docs repointed native-first: README, deployment, convergence-harness, production-hardening, 2 examples, packaging README. CHANGELOG untouched (history).
- Reviewer verdict FIX LIST, then cleared by 2 fix crews: `doctor.sh` native health check, smoke stubs, `.env.example`, cron comment, client bridge test string.
- Full suite 1111 passed, 9 skipped; live e2e example.com on 18495 (~3.3s): create ok, observe ~8806 chars, snapshot h1 ~415 chars text present, screenshot image block ~11k base64 chars, close confirmed; server stopped after. Zero Dockerfiles/compose remain (sweep verified).

### 13. Minimal tool profile (done, verified with a real agent)
- `MCP_TOOL_PROFILE=minimal|curated|full`, default curated. Minimal is exactly 10 tools
  (create_session, observe, find_elements, execute_action, snapshot, screenshot, list_tabs, activate_tab,
  close_session, wait_for_selector). Gating is listing-only in `registry.py`; handlers intact.
- Catalogue: 37 tools / 38,205 chars curated vs 10 tools / 16,620 chars minimal (about 56 percent smaller).
  Note: curated count is 37 now, not 36 (stop_trace and witness additions since the audit).
- Tests: new `tests/test_tool_profile.py` (5 tests) plus name-style suite, 10 passed.
- Live MCP e2e on 18496 (minimal): tools/list 10, create/observe/close on example.com ok.
- Real Claude Code run on 18497 (minimal, example.com): tools=10, 4 turns, 9.7 s, $0.0966
  (vs $0.1319 for the same task on curated), correct title/heading, banner still not pasted by the client
  (known defect, unchanged). `.mcp.json` port swap restored byte-identical; 18497 stopped after.

### 14. SHOAV guard agent template (D-1 setup and docs, done, no code)

- New pack in `shoav-mcp/MCP/agent-template/`: `mcp_config.json` (port 18550), `settings.json`
  (guard mode, filters path, fail mode, underscore names), `AGENT_START.md`, `OUTPUTS.md`, `SETUP.md`, `REVIEW_NPS.md`.
- Notes added to `AGENTS.md`, the skill, and `context.md`. No controller logic changed. Port 8000 never used.

## Changed files, cumulative

Backend (`auto-browser/controller/`): `app/config.py`, `app/browser/services/runtime.py`, `app/browser/services/sessions.py`,
`app/events.py`, `app/main.py`, `app/app_factory.py`, `app/mcp_transport.py`, `app/routes/session_diagnostics.py`,
`app/tool_gateway/gateway.py`, `app/tool_gateway/registry.py`, `app/tool_gateway/packs/core.py`.
New: `app/live/*`, `app/routes/live_api.py`, `tests/test_live_view.py`, `tests/test_live_view_review.py`, `tests/test_tool_name_style.py`, `tests/test_tool_profile.py`, `tests/test_screenshot_snapshot.py`, `tests/test_live_screencast.py`.
Frontend: everything in `auto-browser/live-ui/` (new).
Other: `auto-browser/scripts/start-local.ps1`, `auto-browser/.gitignore`, `.agents/skills/auto-browser/SKILL.md`,
`.agents/mcp_config.json`, `AGENTS.md`, `CLAUDE.md`, `context.md`, `progress.md`, `mcp-test/*`.
Nothing is committed or pushed.
Docker removal: deleted 12 paths (5 Dockerfiles incl. reverse-ssh dir, 5 compose files, scripts/compose_local.sh, parity test file); modified Makefile, .devcontainer, smoke scripts (NOTEs), controller docker_ephemeral files (session_isolation, readiness, runtime_policy, compliance, sessions, takeover, remote_access, runtime), README, deployment, convergence-harness, production-hardening, 2 examples, packaging README, doctor.sh, .env.example, cron, client bridge test.
