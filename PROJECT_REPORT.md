# S.H.O.A.V. — Project Report
**Genesis Hackathon 2026** · **Track 03:** AI Bodyguard  
**Team:** Vassu-V & str-VaibhavThakkar

---

### 1. The Problem Statement

* **The Challenge:**  
  Autonomous web-browsing agents rely on raw DOM trees and coordinate grids rather than human visual intuition, making them exceptionally vulnerable to deceptive interfaces and dark patterns. Empirical research shows agents are ~2.3× more susceptible to dark patterns than humans (>70% vs. 31% compromise rate, Stanford DECEPTICON), with vulnerability paradoxically worsening in reasoning models that actively rationalize manipulative choices. Furthermore, ~70% of validated prompt injections sit in non-rendered HTML (metadata, comments, zero-size CSS) invisible to humans but consumed by agents. Existing defenses either fail against simple evasion or collapse legitimate task completion by 50%, leaving real-world agentic workflows unprotected.

* **Target Audience:**  
  * **Agent Developers:** Teams building browser agents with Playwright, Puppeteer, or MCP.  
  * **Enterprises:** Organizations automating procurement, form submissions, and SaaS management.  
  * **End-Users:** Individuals delegating sensitive tasks (e-commerce checkout, privacy settings) to AI agents.

---

### 2. The Solution & Core Features

* **Value Proposition:**  
  S.H.O.A.V. (Shield for Hostile Operations & Agent Vulnerability) is a deterministic-core "AI Bodyguard" sitting at the Model Context Protocol (MCP) boundary between the agent and the browser. Instead of vulnerable LLM guards that can be prompt-injected, S.H.O.A.V. enforces mathematical and geometric invariants—computed CSS visibility, physical coordinate hit-testing (`elementFromPoint`), and form-state tracking. By sanitizing threats rather than bluntly blocking pages, it protects the agent while preserving 100% of task utility (*PASS = Task Completed AND Zero Compromise*).

* **Completed Features:**
  * **Native Headed Browser MCP:** Decoupled Auto-Browser from Docker to run natively on Windows with visible Chromium automation and loopback MCP endpoints.
  * **Live Ephemeral Dashboard:** Built a real-time web UI (`/live/{session_id}`) streaming screenshots, agent actions, and live security badges via Server-Sent Events (SSE).
  * **Automated Benchmark Runner:** Built `benchmark_runner.py` to evaluate Antigravity CLI (`agy`) against the live [TrickyArena](https://agenttrickydps.vercel.app) benchmark with SQLite trace logging.
  * **`shoav-skill` Package & CLI:** Published a cross-agent defense skill (`npx shoav-skill`) supporting Antigravity CLI, Claude Code, and Cursor.
  * **Deterministic Inspection Scripts:** Implemented standalone checkers for `elementFromPoint` hit-testing, WCAG contrast calculation, cart item delta tracking, and confirmshaming text normalization.
  * **Dual Ingress/Egress Filter Specs:** Defined structured schemas for Ingress DOM sanitization (`ALLOW`, `REWRITE`, `BLOCK`) and Egress action validation.

* **Incomplete Features:**
  * **Inline Gateway Proxy Hook:** Standalone inspection scripts are fully functional, but direct in-process hooking into Auto-Browser's internal `call_tool()` remains a prototype; checks currently run via modular scripts and skill checkpoints.
  * **Fast Local Embeddings (Jev):** Vector similarity scoring for linguistic framing traps was designed, but deferred to prioritize 100% deterministic structural defenses.
  * **Multi-Page Drip Pricing Memory:** Multi-step cumulative fee tracking across navigation flows was scoped out to ensure rock-solid stability on single-page cart invariants.

---

### 3. Technical Architecture & Tech Stack

* **Frontend:** Vanilla JavaScript (ES2022), HTML5, CSS3 (modern dark UI), Server-Sent Events (`EventSource` API) for real-time telemetry streaming.
* **Backend & Database:** Python 3.10+ (FastAPI, Uvicorn ASGI), Node.js (CLI tooling), SQLite3 (action trace logging), local loopback hosting (`127.0.0.1:8000`).
* **APIs & Third-Party Tools:** Auto-Browser ([LvcidPsyche/auto-browser](https://github.com/LvcidPsyche/auto-browser)), Playwright Core (Microsoft), Antigravity CLI (`agy`), TrickyArena Benchmark ([PurSecLab](https://agenttrickydps.vercel.app)).
* **System Architecture:**  
  Data flows in four streamlined stages:
  1. **Agent Dispatch:** The agent sends standard JSON-RPC tool calls (`browser.observe`, `browser.execute_action`) to the S.H.O.A.V. gateway.
  2. **Ingress Sanitization:** Incoming DOM snapshots are filtered—invisible CSS nodes (`display:none`, `opacity:0`), comments, and context-flooding tokens are stripped (`REWRITE`) before reaching the agent.
  3. **Egress Hit-Testing:** Before any click executes, S.H.O.A.V. runs `document.elementFromPoint(x, y)` on the live page to verify that the physical click target matches the intended element, deflecting transparent clickjacking overlays.
  4. **Execution & Telemetry:** Verified actions execute in Playwright Chromium, while live events, diffs, and security alerts stream via SSE to the Live Dashboard and commit to local SQLite traces.
