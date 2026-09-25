# context.md

What we did in this session, what was asked, what was output, what was discussed, what was executed.
Mostly append-only. Date: 2026-09-25. Companion files: `progress.md` (stages), `CLAUDE.md` (rules), `AGENTS.md` (agent usage).

## 1. Goal in one paragraph

Take the cloned Auto Browser MCP server (in `auto-browser/`), make it run natively with a visible Chromium, and add a
live view: every agent session gets an id and a link, and the user can open the link to watch the agent's tool calls,
their phase (read, screenshot, act), arguments, results and latest screenshot, live and later as an archive.
Test it with real agents (Claude Code using only the MCP, and agy). Then make navigation cheaper in tokens.

## 2. Standing instructions from the user

- Stay inside `external/automcp`. Do not read the wider project. (Learned the hard way, see 3.1.)
- Discuss before major steps; the user gave explicit go-ahead for each task as it was stated.
- Do not change global settings. The user later asked to remove agy's global `auto-browser` registration; done.
- Use subagents freely, including independent reviewers. Self-review the code.
- Look like real engineering, not generated filler: standard libraries (Next.js, shadcn), restrained UI.
- Give the live-view link every time an agent is started.
- "Plan only, do not build" is in force for the efficiency work in section 6.
- Keep `context.md`, `progress.md`, `CLAUDE.md` up to date in this folder.

## 3. Chronological record

### 3.1 First request and the scope correction
- Input: a pasted brief said to read a third-party skill (an "Auto Browser MCP guide"), review the clone, and get ready
  for targeted edits. agy would be attached later to test.
- I read the guide and the clone, and also read files outside `automcp` (`external/auto-browser`, `shoav-mcp/`, the
  parent `context.md`). The user objected: they never asked for that and had started me in `automcp` to constrain me.
  Output: I withdrew those findings (they described the wrong tree), and re-reviewed only `automcp/auto-browser`.
- Result of the proper review: stock upstream clone, HTTP MCP, 36 curated tools, Docker-oriented defaults.
  The guide's custom parts (stdio server, `genesis.ping`, tags, local defaults) are not in this clone.

### 3.2 Change 1: only visible browsers
- Input: run normal (headed) browsers, verify, use another port because the user's server holds 8000.
- Executed: added `headless` setting (default False) and a local launch branch in `runtime.py`. Started on 18431
  (8765 was taken by an unrelated `http.server`). Verified: no `--headless` flag; create, observe, click, close worked.
- Output to the user: 36 tools; snags an agent hits (`reason` required, session limit 1, click navigation skips allowlist,
  Docker-shaped defaults).

### 3.3 Live view feature (large request)
- Input (paraphrased): on MCP start or agent call, print the session id and a link; user sees the agent's work in a UI
  separate from the browser window; show reads vs screenshots; explain how an agent learns the commands; use Next.js and
  shadcn; archive and restart; test with agents from a test folder with local settings only; use multiple agents,
  QA and review; boxed colored banner if possible.
- Discussion and assumptions: "Chatshare" = shadcn/ui; "archive and restart" = read-only archive at the same link plus a
  Restart button. Said plainly that colour in a CLI cannot be forced through MCP.
- Executed: wrote `live-ui/CONTRACT.md`; spawned a backend agent and a frontend agent in parallel; then an independent
  reviewer; then sent fixes back to the backend agent and a follow-up to the frontend agent (see `progress.md` stages 4 to 5).
- Skill and `AGENTS.md`: the user also asked (mid-task) for a local, non-global skill under `.agents/skills` and an
  `AGENTS.md`. Written. Also wrote `scripts/start-local.ps1` so an agent can start the server without Docker.

### 3.4 Claude Code run (Google, then YouTube)
- Input: run Claude Code attached to the MCP with no built-in tools, go to google.com, then YouTube, search and play a video,
  show the output, and show the website.
- Executed: `mcp-test/run-claude.ps1` with `--tools '""'`, `--mcp-config .mcp.json --strict-mcp-config`.
  First attempt had no tools because PowerShell dropped the empty argument; fixed and rerun.
- Output (readable transcript in `mcp-test/last-run.txt` at the time): 13 calls, 114 s, about $0.70. Google returned an
  "unusual traffic" page (HTTP 429); the agent reported it and did not try to bypass. YouTube search worked, it skipped two
  pre-roll ads and confirmed playback by watching the player timer (0:08 to 0:17). `eval_js` was refused (needs governed profile).
- UI screenshot showed the archived session with all 13 calls, phase chips, the last screenshot and a Restart button.
- Defect: the agent said "The tool didn't show a live-view banner".

### 3.5 Banner delivery investigation
- The server sent the banner as content block 2 plus `structuredContent.live_view`; Claude Code passed only block 0.
- Fix: `_notice` and `live_view` became the first keys inside block 0 for explicit, implicit and fork session creation.
- Three further Claude Code runs (short example.com task): the agent still did not show the banner, even when the notice was
  made explicit and when the user prompt asked for the link. Its thinking noted the link but its reply omitted it.
- Conclusion given to the user: an MCP cannot make a client print. Options offered: auto-open the link in the default
  browser (opt-in), a Claude Code PostToolUse hook in `mcp-test/`, or rely on `AGENTS.md`/skill. The user then asked whether
  the tool could print in the CLI or the banner could carry a relay line; answered that no protocol channel exists
  (MCP log notifications untested), and the notice already says it.

### 3.6 agy test
- Input: run the agy check, verify `AGENTS.md` behaviour, remove the global `auto-browser` registration, give the UI link.
- Findings: workspace `.agents/mcp_config.json` was loaded but showed no tools. agy's log:
  `tool name ... violates ^[a-zA-Z0-9_-]{1,64}$` because tools are named `browser.create_session`. Also print mode
  auto-denied MCP calls without an allow rule.
- Executed: `MCP_TOOL_NAME_STYLE` (underscore advertised, both accepted), tests, restart; renamed the workspace server to
  `auto-browser` so agy's existing allow rule `mcp(auto-browser/*)` applies; `agy mcp remove auto-browser` (global entry,
  pointed at port 8000; user's request). Claude Code had no such registration.
- Results: agy listed 33 browser tools, opened example.com and Wikipedia (Alan Turing: born 23 June 1912, Maida Vale,
  London), and printed the boxed banner itself both times. It quoted `AGENTS.md` and the skill when asked what it knew.
- Bug found in the UI screenshot: phases showed `other` for underscore-named calls. Fixed in `gateway.py` (record canonical
  name) with a regression test. 122 related tests passed.
- Links given: list `http://127.0.0.1:3100/`; agy Wikipedia `.../s/f370da25d3b1`; agy example `.../s/f82a19a38ea1`;
  Claude YouTube `.../s/5ef051a88dbb`.

### 3.7 Efficiency questions and measurements
- Input: is there a screenshot option, how easy is navigation, can the skill teach cheaper navigation.
- Measured on the Alan Turing article (one call each, tokens are chars/4 estimates):
  `find_elements` 64 to 175; `observe` fast 900; text limit 5: 2,100; limit 10: 2,500; default text 4,600; normal 4,700;
  rich 8,100; `screenshot` 670 (a path, not an image); `get_html` about 436,000; `create_session` 800.
- Inside a default text `observe`: `interactables` 11,181 chars, `text_excerpt` 2,036, `dom_outline` 1,554, `session` 2,298,
  `remote_access` 460, everything else small. About 60 percent of an observe is the interactables list, about 12 percent
  is the repeated `session` block.
- Skill updated with a "Navigate efficiently" section.
- Findings reported: screenshot tools return only a file path and URL (zero image blocks), so a model cannot see them.

### 3.8 The "0 screenshots" question (this turn)
- Input: UI shows 0 screenshots but at least 2 were used; can the agent read a screenshot; will the pane show a live feed?
- Investigated session `f370da25d3b1` (agy, Wikipedia). Files on disk: 4 PNGs (before-type, after-type, before-click,
  after-click). The action pipeline captures before and after every action automatically. The timeline attaches only the
  after image to the `execute_action` row (2 rows have `screenshot_url`).
  The UI counter counts calls whose phase is `screenshot` (explicit `screenshot` tool or non-text `observe`). agy made none.
  So 0 is literally right for that definition but misleading: 2 shown, 4 captured.
- Preview pane: shows the `screenshot_url` of the most recent timeline row that has one. It updates only when a tool call
  ends. It is not a live feed. The live feed today is the real Chromium window on the desktop.
- Agent access: the agent never receives image data. `screenshot` returns `screenshot_path` and `screenshot_url` only.
  Screenshots are served by the controller at `/artifacts/...`, but agents have no fetch tool, so they cannot read them.

### 3.9 Measurements for the plan (throwaway scripts, not part of the product)
- Image cost: the 1280x800 PNG is 198,599 bytes, about 1,365 image tokens (w*h/750). Scaled to 75 percent as JPEG q60:
  66,282 bytes, about 770 tokens.
- Page content (chars; a separate headless Playwright, not the MCP):
  | page | raw HTML | HTML with scripts, styles, svg, comments and most attributes removed | visible text | markdown with tables and links | tables |
  |---|---|---|---|---|---|
  | Wikipedia Alan Turing | 1,675,853 | 634,029 | 109,406 | 210,889 | 10 |
  | Wikipedia countries by population | 1,072,726 | 279,399 | 22,052 | 37,437 | 2 |
  | Hacker News | 34,204 | 23,726 | 3,856 | 8,040 | 4 |
  | example.com | 559 | 220 | 129 | 167 | 0 |
  Table structure survives a markdown conversion (pipe tables with headers and rows). My throwaway converter inlines link
  URLs, which is why its output is larger than visible text; a real one would make links optional.
  Even visible text of a long article is about 27,000 tokens, so reading needs scoping and paging, not only cleaning.
- Tool catalogue (`tools/list`): 36 tools, 35,487 chars, about 8,900 tokens, carried in every model turn unless the client
  defers tools. That is more than one whole default observe. Largest entries: `execute_action` 4,181 chars (about 1,045 tokens),
  `create_session` 2,051, `find_elements` 1,952, `drag_drop` 1,379, `observe` 1,280. `initialize.instructions` is 911 chars.
  A first attempt failed with `KeyError: 'result'`; the controller was healthy, and the likely cause was its rate limiter
  (120 requests per minute) during a burst of measurement calls. It succeeded on retry.

### 3.10 Latest user request (record keeping)
- Asked for `progress.md`, `Claude.md` (`CLAUDE.md`) and `context.md`, with the contents described in sections 1 to 2 of
  this file and `progress.md`. Created in `external/automcp/`.

### 3.11 Tool audit, DOM, storage and approvals (user message with many questions)
- Asked: are all 36 tools needed, which are redundant, does the agent get the DOM, how would compact mode be implemented and
  what does it risk, how would fewer rounds work, where are screenshots and logs stored and is there a database; approved
  the screenshot image tool, the real frame feed, and a DOM service if missing.
- Tool audit (all 36): core browsing 10 (create_session, close_session, observe, find_elements, execute_action, screenshot,
  wait_for_selector, list_tabs, activate_tab, close_tab); diagnostics 4 to merge (get_console, get_page_errors,
  get_request_failures, get_network_log); sometimes useful 7 (get_html, eval_js, set_viewport, list_downloads, fork_session,
  list_sessions, get_session, where get_session duplicates list_sessions); drag_drop belongs inside execute_action;
  request_human_takeover points at a VNC desktop that does not exist in native mode; stop_trace rarely needed; memory (3) and
  auth (3) profile tools could be one; verify_witness, export_witness_bundle, readiness_check and harness_* (3) are for
  operators and research, not browsing agents.
- DOM finding: `accessibility_outline` is always unavailable (see progress stage 10). Existing pieces are `dom_outline`
  (headings, forms), `interactables`, `text_excerpt`. ARIA snapshot numbers in progress stage 10.
- Compact mode implementation answer: a post-processing step in the gateway after the handler returns; protocol, transport,
  tools and handlers unchanged; recorder still gets the full result; default and per-call `verbosity=full` escape hatch.
- Fewer rounds answer: thin server-side tools that chain existing steps (open URL and return compact state; action that can
  return the new page state; click or type by visible text). Example: "search Wikipedia and read the result" goes from 6 calls to about 2.
- Storage answer: all local under `auto-browser/.local-data/<port>/`. `artifacts/<session_id>/` holds PNG captures, `trace.zip`
  (about 13 MB per session), `timeline.jsonl`, `actions.jsonl`, `summary.json`; `state.db` (SQLite: audit_events, approvals);
  `audit/`, `witness/`, `sessions/`, `mcp/sessions.json`; process logs `controller.log`, `controller.log.err`, `ui.log`.
  150 MB after a handful of sessions. No database server; nothing uploaded.
- Questions put to the user: approve the 10-tool default; compact default on; image default on; tracing off by default and
  JPEG automatic captures.

### 3.12 Continuation in a new host (this session)
- Verified deployed state with two read-only subagents: 18480 answers `/healthz` and stream-stats, 3100 answers,
  UI build contains `live-feed`. Port 8000 untouched. A server on 18492 was already up (not ours, left running).
- Snapshot text gap root-caused (scoped `table.infobox` hits the `tableItem()` fast path in `snapshot_script.py`,
  cells clip to empty, alt dropped) but the fix was already in the tree, so no code was written. Verified only:
  31 snapshot tests and 15 screencast tests passed; live e2e on 18492 returned 1457 chars with Born/Died/1906/1992.
- Picked compact result mode as the one checklist item: research only, plan presented for discussion, nothing built.
  Key finding: compact in `gateway.py` after `live_call.finish` so the recorder keeps full results; UI reads only
  the event envelope and opaque result, so it is safe if `current_url`, `url`, `title`, `screenshot_url` survive.

### 3.13 Docker removal
- Deleted 12 paths: 5 Dockerfiles incl. reverse-ssh dir, 5 compose files, `scripts/compose_local.sh`, parity test file; kept `browser-node/` (real `server.mjs`).
- Makefile / `.devcontainer` / smoke scripts stubbed to NOTEs; controller `docker_ephemeral` neutralized to explicit errors (`session_isolation`, `readiness`, `runtime_policy`, `compliance`, `sessions`, `takeover`, `remote_access`, `runtime`).
- Takeover tool kept (tests demand success); docs repointed native-first (README, deployment, convergence-harness, production-hardening, 2 examples, packaging README); CHANGELOG untouched.
- Reviewer verdict FIX LIST, cleared by 2 fix crews (`doctor.sh` native health check, smoke stubs, `.env.example`, cron comment, client bridge test string).
- Full suite 1111 passed, 9 skipped; e2e: see session report.
- Known open: `.github` CI (controller-tests, compose-smoke) still references deleted compose files; will fail on push. Nothing committed or pushed.
- Live e2e example.com on 18495 (~3.3s): create ok, observe ~8806 chars, snapshot h1 ~415 chars text present, screenshot image block ~11k base64 chars, close confirmed.
- Server stopped after e2e; zero Dockerfiles/compose remain (sweep verified).

### 3.14 Minimal tool profile (built and agent-verified)
- `MCP_TOOL_PROFILE=minimal|curated|full`, default curated. Minimal is exactly 10 tools; gating is
  listing-only in `registry.py`, handlers intact. Catalogue: 37 tools / 38,205 chars curated vs 10 tools /
  16,620 chars minimal (about 56 percent smaller). Curated is 37 now, not 36.
- New `tests/test_tool_profile.py` (5 tests) green; live MCP e2e on 18496 ok; real Claude Code run on 18497
  (example.com): tools=10, 4 turns, 9.7 s, $0.0966 vs $0.1319 curated, correct answer, banner still not pasted
  (known client defect). `.mcp.json` restored byte-identical; 18497 stopped after.

## 4. Current state

- Processes I started that are still running: test controller on 18480 (visible Chromium), UI on 3100.
  The user's server on 8000 is untouched.
- Nothing committed or pushed.
- Full backend suite last run: 1111 passed, 9 skipped, 257 subtests passed (after Docker removal).
- New since: minimal tool profile (`MCP_TOOL_PROFILE`, default curated) verified with a real Claude Code run.
- Known gaps: UI cannot talk to a controller that requires a bearer token; screenshot counter semantics; preview is not live;
  results are verbose. Closed since: agents can now get image screenshots (opt-in `image: true`), `browser.snapshot`
  exists with scoped-table text fallback, live MJPEG feed route exists.

## 5. Explanations the user asked for

- What "observe" is: a snapshot of the current page for the agent. Presets: `text` (accessibility tree, text excerpt, DOM
  outline, clickable elements), `fast` (screenshot only), `normal` (text plus screenshot plus OCR), `rich` (normal with more
  text and outline). `find_elements` is a targeted query. `get_html` is the entire serialized page. `execute_action` performs
  navigate, click, type, press, scroll and so on. The `session` block in results is the full record of the browser session
  (ids, timestamps, paths, isolation settings, auth state, witness settings, remote access), repeated on most results.

## 6. Plan (no code written for this)

Not started. Presented to the user for decisions.

### 6.1 Compact result mode (define first)
- Definition: a setting `MCP_RESULT_STYLE=compact|full` (and optionally a per-call `verbosity`). Full keeps today's payloads.
  Compact changes only the shape, not the information an agent needs:
  - `session` becomes `{id, status, current_url, title}` (about 120 chars instead of 2,298).
  - Drop keys that are empty or constant: `remote_access`, `takeover_url`, `isolation`, `auth_state`, `witness_remote`,
    `artifact_dir`, `trace_path`, `proxy_persona`, empty lists, nulls, `ocr` when empty, `screenshot_path` (keep the URL).
  - `interactables` as one line each, for example `op-a0hr1e48 input "Search Wikipedia"` or `op-otvj1lzy a "Alan Turing" /wiki/Alan_Turing`,
    instead of a JSON object with `selector_hint`, `bbox`, `disabled`, `type`, `role`.
    Full mode can still be requested when bounding boxes are needed.
- Estimated effect on a default text observe: about 4,600 tokens to about 2,000. On an action result: about 700 to about 150.
- Risk: the live UI and tests read some of these fields. The recorder must keep receiving the full result and compact only what
  is returned to the client.

### 6.2 Reading content without losing tables
- Keep information, drop markup. New read tool (working name `browser_read`): returns markdown, keeping headings, lists,
  links (optional), and tables as pipe tables. Removes scripts, styles, svg, comments, hidden nodes, and attributes.
- Scope and page it: parameters `selector` (for example `table.infobox`, `main`), `max_chars` (default about 6,000),
  `offset` or `section` for paging, and an `outline` mode that lists headings and tables with sizes so the agent can pick.
- `get_html` stays for debugging but gains `selector`, `strip` (default on) and a hard `max_chars` so it cannot return 1.7 MB.
- Why: numbers in 3.9. Cleaning alone is not enough for long pages; scoping is.

### 6.3 Fewer round trips
- Each agent turn re-reads the whole conversation, so calls cost more than their payload. Ideas, in order of value:
  1. `browser_open(url)`: reuse or create the session, navigate, return compact state plus the top interactables. Replaces
     create, navigate, observe.
  2. Let actions return an optional compact observation (`then: "observe"`) so the agent does not call observe next.
  3. Text-based targeting: `browser_click(text=...)` and `browser_type(label=..., text=..., submit=true)` that resolve elements
     server-side. Removes the observe-to-get-ids step for simple pages.
  4. Make `reason` optional (default to a generated string, still audited). It is a required field that failed the first call.
- The user said to leave `create_session` as it is; not included.

### 6.4 Screenshots the agent can see
- Return a real MCP `image` content block from `screenshot`, opt-in per call (`image: true`, default off) because clients do not
  declare vision support. Default encoding JPEG q60 at 75 percent scale (about 770 tokens, 66 KB) instead of PNG (1,365 tokens).
- To verify before building: whether Claude Code and agy pass image blocks through to the model.
- Keep saving the full PNG for the human view.

### 6.5 Live view improvements
- Counter: count screenshot captures (files and events with `screenshot_url`) rather than only explicit calls; show both
  `agent screenshots` and `auto captures`, and attach before and after images to action rows.
- Live feed: options (a) refresh the preview every 1 s while a session is live (simple), (b) stream frames from the browser
  (CDP screencast, roughly 5 to 10 fps) over SSE or WebSocket (real feed), (c) keep relying on the real Chromium window.
  Recommendation: (a) first, (b) if the user wants a true feed.

### 6.6 AGENTS.md and settings
- `AGENTS.md` today lists tool groups by pointing to the skill and the live catalogue; it does not list every tool.
  Plan: generate a table of all tools (name, phase, cost class, when to use) from `tools/list` and put it in `AGENTS.md`.
  Settings suggestions already exist in the skill, `.agents/mcp_config.json` (agy) and `mcp-test/.mcp.json` (Claude Code).

### 6.7 Estimate of current cost-effectiveness (labelled estimate)
- A typical five-step task today: create 800, one default observe 4,600, three actions about 700 each, close about 700,
  so about 8,200 tokens of tool output, of which about 4,000 is the repeated `session` block and unused fields.
  With 6.1 and 6.3 the same task is estimated at 2,500 to 3,000.
- Fixed cost: the tool catalogue is about 8,900 tokens per turn (see 3.9). Over a 10-turn task that is about 89,000 tokens,
  more than all tool results combined. This is the largest single cost.

### 6.8 Shrinking the catalogue (added after measuring it)
- A smaller default profile (working name `minimal`, about 10 tools: create_session, observe, find_elements, execute_action,
  read, screenshot, list_tabs, activate_tab, close_session, wait_for_selector) with `curated` and `full` still selectable.
  The rest remain reachable by a `browser_more_tools` style listing if wanted. Estimated catalogue: about 2,500 tokens.
- Shorten descriptions and the `execute_action` schema (about 1,045 tokens alone: many optional fields per action type could
  become a compact per-action schema; long prose descriptions cut to one line).
- Note: clients that defer or search tools (some Claude Code configurations) pay less of this; agy loaded all of them.

## 7. Open decisions for the user

1. Approve 6.1 (compact mode) as defined, and whether default should be compact or full.
2. Approve 6.2 (reader tool plus scoped `get_html`).
3. Which of 6.3 items to build (1 to 4).
4. 6.4 image return: build after confirming clients pass image blocks?
5. 6.5 counter and live feed: choose (a), (b) or (c).
6. Whether to expand `AGENTS.md` with the full tool table (6.6).
7. Whether to add auto-open of the live link, or a Claude Code hook (from 3.5).
8. Approve 6.8 (smaller default tool profile and shorter schemas). Recommended first, since it is the largest fixed cost.

### 3.15 SHOAV guard agent template (D-1 setup and docs)

- Built `shoav-mcp/MCP/agent-template/` with `mcp_config.json` (port 18550), `settings.json`
  (guard mode, filters path, fail mode, underscore names), `AGENT_START.md`, `OUTPUTS.md`, `SETUP.md`, `REVIEW_NPS.md`.
- No controller logic changed. Guard demo uses `-Guard enforce`; port 8000 is never used.
