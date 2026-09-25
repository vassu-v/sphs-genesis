# Workstream 10: Expanded Landscape of AI Agent Manipulation, Dark Patterns, & Deterministic MCP Mitigations

## Executive Summary

This research workstream investigates the full spectrum of adversarial manipulation targeting autonomous web-browsing agents beyond simple indirect prompt injection. It bridges cognitive psychology (how deceptive interfaces exploit human heuristics), machine learning failure modes (how agents amplify these traps), context engineering vulnerabilities (context overloading and dummy DOM diffs), and presents the concrete technical architecture to integrate dual deterministic filters (Ingress and Egress) into an MCP browser control plane.

---

## 1. What Are Dark Patterns? (Taxonomy & Cognitive Mechanics)

Dark patterns (deceptive design patterns) are user interfaces crafted to nudge, coerce, or trick users into making choices that serve the platform rather than the user's best interest.

### 1.1 Canonical Taxonomy
Consolidating Brignull (2010), Gray et al. (CHI 2018), Mathur et al. (CSCW 2019), the FTC Staff Report (2022), and EU Digital Services Act (DSA Art. 25):

1. **Sneaking (Hidden Information & Costs)**:
   * *Sneak into Basket*: Silently adding items, warranties, or recurring charges to a checkout flow without an explicit affirmative click.
   * *Drip Pricing*: Disclosing mandatory fees late in the transaction sequence after the user has invested time and intent.
2. **Urgency & Scarcity Manipulation**:
   * *Fake Countdowns*: DOM-driven JavaScript timers (`setInterval`) that reset on reload or indicate artificial deadlines.
   * *Manufactured Scarcity*: Unverified claims of low stock ("Only 2 rooms left at this price!") to provoke panicked decisions.
3. **Misdirection & Interface Interference**:
   * *Visual Asymmetry*: Styling preferred actions (e.g. "Accept All Tracking") as high-salience, saturated CTA buttons while rendering non-preferred actions ("Reject") as low-contrast, unstyled plaintext.
   * *Confirmshaming*: Emotionally manipulative microcopy designed to induce guilt upon opting out ("No thanks, I prefer paying full price" / "I hate saving trees").
   * *Trick Questions / Double Negatives*: Convoluted syntactic framing (e.g. "Do NOT uncheck this box if you wish NOT to receive marketing").
4. **Obstruction ("Roach Motel")**:
   * Making an action extraordinarily easy to initiate (1 click to subscribe) but deliberately complex to terminate (buried settings, multi-step questionnaires, forced phone calls, hidden cancel links).
5. **Forced Action & Preselection**:
   * Bundling unrelated consent with access, or pre-checking checkboxes and toggles (`checked=true`) before user interaction.
6. **Social Proof Fabrication**:
   * Injecting synthetic activity feeds ("John from Ohio just bought this product 2 minutes ago").

### 1.2 How Dark Patterns Exploit Human Psychology
Dark patterns do not rely on cryptographic breaks; they exploit hardwired human cognitive heuristics (System 1 thinking):
* **Loss Aversion**: Humans feel the pain of losing something roughly twice as intensely as the pleasure of gaining it. Urgency and confirmshaming weaponize FOMO (Fear Of Missing Out) and social guilt.
* **Default Effect / Status Quo Bias**: Humans disproportionately accept default settings because changing them requires cognitive effort, attention, and perceived risk. Pre-checked boxes exploit this directly.
* **Cognitive Load & Friction Fatigue**: When faced with a multi-page cancellation labyrinth, human working memory degrades, leading to compliance surrender.
* **Anchoring**: Presenting an inflated "original" price next to a "sale" price distorts value perception regardless of factual utility.

### 1.3 How Dark Patterns Transfer to and Amplify in AI Agents
A common assumption was that AI agents, being dispassionate algorithms, would be immune to psychological tricks. Recent empirical benchmarks prove the exact opposite: **agents are significantly more vulnerable than humans**:

* **The Rationalization Paradox (DECEPTICON, Stanford, ICLR 2026)**:
  * In tested web navigation tasks, dark patterns steered LLM agents into compromised outcomes in **>70% of runs**, compared to a **31% human baseline** (**2.3x more susceptible**).
  * **Vulnerability scales with reasoning**: Counter-intuitively, larger models (o1, Claude 3.7 Thinking) and models given larger test-time reasoning budgets performed *worse*, not better. When confronted with "Best Value" banners or confirmshaming, the agent's chain-of-thought engine *rationalizes* the deception, inventing logical justifications for why the manipulated choice aligns with the user's overarching goal.
* **Goal Optimization vs. Self-Preservation**:
  * Humans possess innate skepticism and an instinct against unauthorized expenditure. Agents are utility-optimizing automata trained to complete the prompt ("buy this camera"). When an obstacle or pre-checked toggle appears, the agent treats it as an operational requirement to be navigated or accepted, not as an adversarial threat.
* **Perceptual Dissociation**:
  * An agent parsing an accessibility tree or flattened DOM does not experience the visual unease that warns a human when a page looks suspicious.

---

## 2. Beyond Prompt Injection: Other Ways to Manipulate AI

Indirect prompt injection (IPI) is only one facet of adversarial web design. Hostile sites employ a broad spectrum of structural, perceptual, and resource attacks against agents.

```
+----------------------------------------------------------------------------------------+
|                      EXPANDED AGENT MANIPULATION LANDSCAPE                             |
+----------------------------------------------------------------------------------------+
| 1. Context Overloading & Flooding   | 2. Visual vs. DOM Mismatch (Cloaking)            |
|    - Attention hijacking            |    - Non-rendered text (display:none, opacity:0) |
|    - Dummy DOM diffs / bloat        |    - Typographic pixel attacks (VLM targets)     |
|    - Recency bias / System drop     |    - Set-of-Mark (SoM) spoofing                  |
+-------------------------------------+--------------------------------------------------+
| 3. Interactive Traps & Hit-Tests    | 4. Temporal & State De-synchronization           |
|    - Clickjacking / invisible divs  |    - Delayed injection (post-scan DOM updates)   |
|    - Bounding-box coordinate decoy  |    - TOCTOU (Time-of-Check to Time-of-Use)       |
|    - Raw mouse dispatch exploits    |    - Infinite DOM loops / quota exhaustion       |
+----------------------------------------------------------------------------------------+
```

### 2.1 Context Overloading, Context Flooding, & Attention Hijacking
* **Context Window Displacement & FIFO Eviction**:
  Many agentic frameworks implement sliding-window token management or naive FIFO truncation. Attackers flood the DOM with high-volume filler data (repetitive CSS classes, deeply nested dummy trees, base64 data URIs). This forces the context manager to truncate or evict the earliest tokens, specifically the developer's system instructions and safety guardrails, leaving the agent stripped of defensive constraints.
* **Softmax Attention Dilution & "Lost in the Middle"**:
  Transformer self-attention calculates token interactions via:
  $$A = \text{Softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)$$
  When an adversary floods the prompt with thousands of high-entropy or filler tokens, the attention mass allocated to initial system instructions decays:
  $$\sum_{j \in \text{constraints}} A_{ij} \to 0$$
  As demonstrated by Liu et al. (TACL 2024) in the *"Lost in the Middle"* phenomenon, LLMs exhibit a U-shaped performance curve, retaining high retrieval at the absolute start and end of context, while suffering severe degradation in the middle 60-80% span. Attackers intentionally sandwich malicious instructions inside massive filler blocks to push user constraints into this low-attention zone.
* **Attention Hijacking (RouteGuard, 2026)**:
  Rather than simply overwhelming token length, attention hijacking uses optimized adversarial token sequences or structural prefixes (fake terminal headers, mock system delimiters like `<|im_start|>system`) that exhibit abnormally high query-key alignment across attention heads. This produces an "attention collapse" where the model's heads attend to the adversarial span, blinding the agent to contradictory environmental constraints.
* **Dummy DOM Diffs & Quota DoS**:
  Hostile JavaScript rapidly mutates thousands of irrelevant DOM attributes per second. Agents that compute DOM diffs between steps get trapped analyzing noise, experiencing memory thrashing and execution timeouts.

### 2.2 Visual vs. DOM Mismatch (Perceptual Desynchronization)
* **DOM-Only Cloaking (~70% of real-world injection payloads)**:
  Instructions embedded in elements with `display: none`, `visibility: hidden`, `opacity: 0`, `font-size: 0`, off-screen positioning (`position: absolute; left: -9999px`), or HTML comments. Invisible to the human operator watching the browser, but directly parsed by DOM-reading agents.
* **Typographic Pixel Attacks & SoM Spoofing (VLM Targets)**:
  Adversaries render adversarial instructions directly into images, canvas elements, or styled background textures. A text parser sees zero text, but a Vision-Language Model (like GPT-4o or Claude 3.5 with Computer Use) reads the text via OCR. Additionally, attackers render spoofed Set-of-Mark numeric tags (`[1]`, `[2]`) into images, tricking VLMs into predicting coordinates targeting malicious inputs.

### 2.3 Interactive Traps & Geometry Exploits
* **Invisible Overlays (Clickjacking)**:
  A transparent `<div>` (`opacity: 0; z-index: 99999; pointer-events: auto;`) placed directly over a legitimate button. When the agent clicks the coordinates of the legitimate button, the simulated pointer event is swallowed by the malicious overlay.
* **Target Mismatch via Raw Mouse Dispatch**:
  As uncovered in our audit of `external/auto-browser` (`actions.py::click`), many agent frameworks locate an element's bounding box and fire raw `mouse.move(x, y)` / `mouse.down()` events. This completely bypasses browser-native actionability checks.

### 2.4 Temporal Traps: Delayed Injection & TOCTOU
* **Asynchronous Observation-Execution Latency**:
  Autonomous browsing runs in a discrete loop: Observation -> LLM Inference (2-15s) -> Action Execution. Adversaries exploit this 2-15 second window using JavaScript timing events (`setTimeout`, `requestAnimationFrame`):
  * **Element Swapping**: The target element's handler or URL is mutated during the inference window after the agent has already decided to click it.
  * **Adversarial Layout Shifts**: Dynamic scripts resize containers right before action execution, shifting physical coordinates so the agent's scheduled click lands on an attacker payload.

---

## 3. State-of-the-Art Mitigations

| Mitigation Strategy | Operational Mechanism | Strengths | Trade-offs / Limitations |
|---------------------|------------------------|-----------|--------------------------|
| **Deterministic DOM Pruning (PhantomLint style)** | Inspects computed CSS styles (`display`, `visibility`, `opacity`, `left`, `font-size`) and drops invisible nodes before tokenization. | 100% deterministic; zero LLM quota; eliminates ~70% of real injections. | Does not catch image-embedded typographic attacks; risk of dropping legitimate accordion panels if not carefully scoped. |
| **Physical Hit-Testing (`elementFromPoint`)** | Evaluates `document.elementFromPoint(x, y)` at the target's physical center before mouse dispatch. | Stops 100% of physical clickjacking overlays; mathematical certainty. | Requires access to rendered browser compositor / live page context. |
| **Token Budget Bounding & DOM Compaction** | Enforces a strict node limit (e.g. max 50 interactive elements, max 4k tokens per snapshot); strips script, SVG paths, style bloat. | Defeats context overloading and attention dilution attacks. | Aggressive compaction can omit deeply nested interactive controls on complex pages. |
| **Initial Form-State Auditing** | Snapshots initial form attributes (`checked`, `value`, `selected`) on page load. Diffs state before submission. | Trivial DOM read; flags pre-ticked subscriptions and data-sharing toggles deterministically. | Cannot judge whether a pre-selected option was genuinely intended without user context. |
| **Content Rewriting / Sanitization** | Instead of outright blocking a page, strips malicious or deceptive nodes and forwards the clean page to the agent. | **Preserves task utility**; avoids the ProtectAI failure mode (where blocking dropped utility from 83% to 41%). | Requires clean DOM surgery to avoid breaking application layout or JS bindings. |
| **Advisory Escalation via Specialized Fast Models (Jev / Embeddings)** | Uses high-speed non-autoregressive decision models (e.g. TypeSafe AI's **Jev**) for rapid risk scoring. | Extremely fast (70-500ms), 200-400x cheaper than LLMs, structured outputs. | Advisory only; cannot be allowed to override structural blocks. |

---

## 4. How to Integrate the Dual Filters into the MCP Tool

The core tool is implemented by hardening the MCP layer that bridges the agent (`agy`) and the browser runtime.

```
                    +----------------------------------------------+
                    |      AUTONOMOUS AGENT (e.g., agy CLI)        |
                    +----------------------┬-----------------------+
                                           | stdio JSON-RPC (MCP)
                                           v
+----------------------------------------------------------------------------------------+
|                        S.H.O.A.V. HARDENED MCP GATEWAY                                 |
+----------------------------------------------------------------------------------------+
| [SHIELD 1] INGRESS FILTER (Intercepts Observation & Snapshot Responses)                |
|                                                                                        |
| Input: Raw DOM snapshot, accessibility tree, observation payload                       |
| Checks:                                                                                |
|   1. Opacity & Visibility: Drops nodes with display:none, visibility:hidden, opacity<0.05|
|   2. Geometric Bounds: Drops nodes positioned off-screen (left/top < -500px)           |
|   3. Text Styling: Drops font-size: 0 and color-matches-background text                 |
|   4. Non-Rendered Artifacts: Purges HTML comments, meta tags, and data-* prompt vectors |
|   5. Context Overloading Protection: Enforces strict node budget; drops dummy DOM bloat|
|                                                                                        |
| Verdicts:                                                                              |
|   - ALLOW: Clean page forwarded unchanged                                              |
|   - REWRITE (Sanitize): Strip malicious nodes and return cleaned DOM (preserves task!) |
|   - BLOCK: Refuse payload if page is an unrecoverable flooding exploit                 |
+----------------------------------------------------------------------------------------+
| [SHIELD 2] EGRESS FILTER (Intercepts browser_click, type, submit Tool Calls)           |
|                                                                                        |
| Input: Proposed action payload (action, target selector, ref, coordinates x, y)        |
| Checks:                                                                                |
|   1. Hit-Test Verification: Evaluates document.elementFromPoint(x, y) at target center |
|   2. Topmost Identity Check: Verifies hit-tested element matches target selector/ref   |
|   3. Overlay Detection: Checks if top element has opacity < 0.1 or z-index > 9000      |
|   4. Pre-Checked State Audit: Flags if submitting form with untouched pre-ticked checks|
|                                                                                        |
| Verdicts:                                                                              |
|   - ALLOW: Physical target matches intended target; forward action to Playwright       |
|   - BLOCK: Overlay detected; abort click and return descriptive error to agent         |
|   - ESCALATE: For linguistic ambiguity, invoke advisory classifier/human confirmation |
+----------------------------------------------------------------------------------------+
                                           | Sanitized JSON-RPC
                                           v
                    +----------------------------------------------+
                    |     BROWSER ENGINE (Playwright Core)         |
                    +----------------------------------------------+
```

### Integration Points:
1. **Stdio MCP Proxy (`shoav_proxy.py`)**: Intercepts `tools/call` JSON-RPC messages over standard input/output.
   * On `tools/call` with `name="browser_snapshot"` or `name="browser_navigate"`: Runs the Ingress Filter on the response before returning to `agy`.
   * On `tools/call` with `name="browser_click"`: Pauses execution, executes a JavaScript hit-test probe in Playwright via `page.evaluate()`, evaluates Egress Filter, and only forwards the click if safe.
2. **Auto Browser Gateway Hook (`gateway.py`)**: If running on `external/auto-browser`, wrap `McpToolGateway.call_tool()` to intercept arguments and inject `elementFromPoint` before calling `actions.py`.

---

## 5. The Three-Pillar Product Architecture

To maximize hackathon impact, score on the 30-point UI/UX rubric, and provide modular utility, the project is structured into three clear pillars:

### Pillar 1: The Hardened MCP Tool (The Core Shield)
* **What it is**: The defensive middleware proxy wrapping the browser MCP server.
* **Mechanism**: Dual deterministic filters (Ingress sanitization + Egress hit-test gating).
* **Key Feature**: Zero LLM quota requirement for the security core. Compatible with any MCP-capable agent (`agy`, Claude Desktop, Cursor, LangChain).

### Pillar 2: The Security & Cognitive Vigilance Skill (`skills/shoav-guard/`)
* **What it is**: An installable Antigravity / agent skill providing deep operational guidance on deceptive web practices.
* **Capabilities**:
  * **Dark Pattern & Cognitive Bias Directory**: Comprehensive knowledge base explaining how sites hack human psychology (loss aversion, default effect, roach motels) and how agents over-rationalize them.
  * **Agent Vigilance Instructions**: Teaches browsing agents rules of engagement (e.g. "always audit pre-checked checkboxes", "never trust 'best value' badges", "diff cart contents before paying").
  * **Second-Opinion Advisor**: Provides instructions for invoking a lightweight advisor model (or Jev-style classifier) to provide a "second preview" on suspicious, high-stakes decisions.
* **Modularity**: Can accompany our Hardened MCP or be used independently with any existing browser agent.

### Pillar 3: The Sandboxed Browser Delegate Subagent (Future / Extension)
* **What it is**: A dedicated, least-privilege browsing subagent designed for autonomous execution without risking system security.
* **Constrained Capabilities**:
  * Can *only* browse the web, take screenshots, edit Markdown (`.md`) files, create/edit empty files, modify image files, and move files relatively within its designated workspace.
  * Zero access to system shells, arbitrary bash commands, network socket creation outside the browser, or sensitive credential files.
* **Integration**: Can be invoked by any parent orchestrator agent as a secure browsing worker.

---

## 6. Real-World CVEs & Security Disclosures

| Identifier / Disclosure | Affected System | Operational Attack Mechanism | Impact |
| :--- | :--- | :--- | :--- |
| **CVE-2026-85694** | LaVague Web Agent (v0.2.35) | Indirect prompt injection via malicious DOM payloads passed directly to an internal Python `eval()` execution handler. | **Remote Code Execution (RCE)** on host machine. |
| **CVE-2025-32711 ("EchoLeak")** | Microsoft 365 Copilot | Zero-click context injection via email/web summarization bypassing safety boundaries. | Unauthorized data exfiltration and cross-tenant data leakage. |
| **CVE-2025-53773** | GitHub Copilot | Prompt injection in workspace files/web contexts overriding tool configuration and IDE settings. | Arbitrary code execution on developer workstations. |
| **CVE-2025-54132** | Cursor IDE | Context poisoning through untrusted web documentation and repository files. | Sensitive API key and code exfiltration via Markdown image rendering. |
| **BrowserOS "WebPromptTrap"** | BrowserOS (<= 0.30.0) | Deceptive DOM summarization tricking the agent into guiding users through malicious GitHub authorization workflows. | Unauthorized OAuth credential grants. |
| **HashJack Attack** | Multi-vendor Web Agents | Embedding adversarial instructions into URL fragment identifiers (`https://example.com/#payload`), parsed into agent context but ignored by server-side WAFs. | Guardrail evasion and hijacked agent navigation. |

---

## 7. Actionable Implementation Roadmap

1. **Phase 1: Build Ingress & Egress Deterministic Filters**
   * Implement CSS computed-style scanner in JavaScript (`display`, `visibility`, `opacity`, `left`, `fontSize`).
   * Implement `elementFromPoint(x, y)` geometry validator.
   * Implement node budget compaction to neutralize context overloading.
2. **Phase 2: Assemble `shoav_proxy.py`**
   * Wrap standard JSON-RPC 2.0 stdio protocol.
   * Intercept `@playwright/mcp` tools.
3. **Phase 3: Package the Vigilance Skill**
   * Author `SKILL.md` detailing dark pattern defense, psychological hooks, and advisory escalation rules.
4. **Phase 4: Benchmark Against Live TrickyArena**
   * Evaluate against `https://agenttrickydps.vercel.app` across all 4 sites and 14 dark patterns.
   * Record before/after susceptibility scores.
