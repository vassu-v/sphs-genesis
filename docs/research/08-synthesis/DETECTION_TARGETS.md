# Detection Targets — Prioritised

Ranking = (evidence of impact x structural detectability) / implementation difficulty,
judged qualitatively (we do not have numbers precise enough for a real formula — see
`OPEN_QUESTIONS.md`). "FULLY structural" = decidable from DOM/computed-style/geometry/
form-state/origin/arithmetic alone, no text meaning required. Difficulty is for a
two-person team over one weekend, assuming access to the rendered page (DOM + computed
style + layout boxes), not just raw HTML.

Citation tags refer to the originating workstream's `sources.json` (01-agent-attacks,
02-dark-patterns, 03-prevalence, 04-mitigations).

## Tier 1 — build first

### 1. Hidden/invisible instruction content (CSS-hiding, off-screen, zero-size, zero-width Unicode)
- **Evidence it matters:** ~70% of confirmed real-world injection payloads sit in
  non-rendered HTML, invisible to a human but read by agents [A-09/A-10,
  03-prevalence]. This is the highest-prevalence, only-confirmed-real-world-incident
  attack class [A-14]. PhantomLint demonstrates this exact detection mechanism
  deterministically for documents [M-05].
- **Structural signal:** for every text-bearing DOM node, compare computed style
  (`display`, `visibility`, `opacity`, `font-size`, `color` vs. `background-color`
  contrast, off-screen position via bounding rect vs. viewport) against whether the
  node's text is present in the rendered/accessibility-tree output the agent
  actually consumed. Also scan for zero-width Unicode characters and HTML comments
  containing imperative-mood sentences. A "content in DOM/AX-tree but not
  rendered-visible" flag is the core rule.
- **Structural/semantic:** FULLY structural (the CSS-hiding/geometry part). Note:
  distinguishing an *injected instruction* from ordinary hidden content (e.g., a
  screen-reader-only skip link, or a collapsed accordion panel) still needs a light
  content check — but the geometry/style test itself is 100% structural and can run
  first as a pre-filter before any semantic step.
- **Difficulty:** Low-medium. A weekend is enough for the computed-style/geometry
  scan; matching this to what the agent's ingestion pipeline actually sees requires
  instrumenting that pipeline, which is the real work.
- **False-positive risk:** Legitimate uses of hidden content are common —
  screen-reader-only text (`sr-only` classes), progressively-disclosed UI
  (accordions, tabs, tooltips not yet opened), lazy-loaded content, and
  loading skeletons. A naive "hidden = malicious" rule will over-fire constantly;
  the rule must be "hidden AND contains an imperative/instructional string" or
  "hidden AND present in agent-consumed text but never becomes visible under any
  user interaction," not hidden alone.

### 2. Overlay / hit-target mismatch (clickjacking-style UI redressing)
- **Evidence it matters:** classic, well-understood web-security attack class;
  Ersoy et al. show DOM-level changes alone (independent of visual rendering) move
  agent susceptibility to manipulation [DP-11]; a partially-verified mobile-agent
  paper documents transparent/`FLAG_NOT_FOCUSABLE` overlays visible to an agent's
  capture pipeline but excluded from the interactive hierarchy — exactly this
  mismatch [P-04, low confidence]. No dedicated live-web agent study exists yet
  (a stated gap), but the mechanism is precedented pre-LLM web-security literature.
- **Structural signal:** for the element the agent intends to click (by
  id/selector/coordinates), run an `elementFromPoint`-style check at the target's
  center and corners; compare the topmost hit-target against the element the agent
  believes it is clicking. Flag mismatches, plus any element with
  `pointer-events: none` masking a differently-targeted element beneath it, high
  z-index transparent/near-transparent (`opacity` near 0) elements over interactive
  controls, and cross-origin iframes stacked over a decoy target.
- **Structural/semantic:** FULLY structural.
- **Difficulty:** Low. `elementFromPoint` + z-index/opacity checks are a few hours
  of work; this is one of the cheapest, highest-confidence rules to build.
- **False-positive risk:** Legitimate overlay UI is everywhere — modal dialogs,
  cookie banners, toast notifications, sticky headers, intentional tooltips. The
  rule must fire on *mismatch between intended and actual hit-target*, not on
  "an overlay exists" — a modal that is the actual top-most and intended target is
  not a violation.

### 3. Pre-checked / pre-set form state (opt-outs pre-ticked, add-ons pre-added)
- **Evidence it matters:** Nouwens et al. found pre-ticked consent patterns on most
  of a 10K-site UK sample [DP-09]; Luguri & Strahilevitz's controlled experiment
  found "hidden information" and similar manipulations raised acceptance from 14.8%
  to 30.1% [DP-05]. Directly relevant to agents: an agent that fills a form
  field-by-field without diffing "state as delivered" vs. "state after I acted" will
  silently submit attacker-favorable defaults (this is stated as plausible inference
  in [02-dark-patterns], not yet directly agent-tested in isolation).
- **Structural signal:** snapshot `checked`/`value`/`selected` state of every
  form control at page-load time (before any agent interaction), and diff against
  the state at submission time attributable to the agent's own actions. Any field
  that is checked/selected/pre-filled at load and that the agent did not explicitly
  toggle is a flagged default, especially for fields tied to consent, marketing
  opt-in, add-on products, or subscription auto-renew.
- **Structural/semantic:** FULLY structural — form state is a boolean/string DOM
  property, no rendering or NLP needed.
- **Difficulty:** Low. Straightforward DOM property read at two points in time.
- **False-positive risk:** Many legitimate defaults exist (a shipping-method radio
  defaulting to standard shipping, a "remember me" checkbox defaulting on for UX
  reasons, required fields pre-filled from a user profile). The rule needs a
  narrower target list (consent/marketing/add-on/negative-option fields) rather
  than flagging every pre-set default on the page, or it will flag nearly every
  commercial site.

## Tier 2 — build if time remains

### 4. Late-appearing / DOM-injected costs (drip pricing)
- **Evidence it matters:** Luguri & Strahilevitz measured "hidden information"
  manipulation raising signup acceptance from 14.8% to 30.1% [DP-05]; Mathur et al.
  count "Sneaking" (incl. hidden costs) as one of 7 top-level dark-pattern
  categories from real-site crawl data [DP-01].
- **Structural signal:** DOM-diff the price/total-bearing element(s) across
  checkout steps; flag a cost node that appears, or a total that increases, at a
  step later than the one where the agent last observed and "accepted" a total.
  Also flag price elements with unusually small font-size/low-contrast relative to
  the page's other price elements (visual-hierarchy de-emphasis).
- **Structural/semantic:** PARTIALLY structural. The existence and timing of a
  late-appearing cost node is structural (DOM diff across steps); judging whether a
  disclosed-but-de-emphasized cost counts as "hidden" vs. "reasonably disclosed"
  needs some visual-hierarchy/semantic judgment.
- **Difficulty:** Medium. Requires tracking a running "total the agent last
  confirmed" across a multi-step flow, which means state-tracking, not just a
  single-page rule.
- **False-positive risk:** Legitimate late-appearing costs are extremely common
  (shipping calculated after address entry, tax calculated after location, tip
  screens). The rule will over-fire heavily unless scoped to "cost increased
  without an intervening user-facing disclosure event," which is a judgment call
  that pushes this toward semantic territory.

### 5. Obstructed cancellation / roach motel (step-count asymmetry)
- **Evidence it matters:** Luguri & Strahilevitz found obstruction (extra steps to
  decline) raised acceptance to 23.6% vs. baseline [DP-05]; FTC's 2022 report names
  hard-to-cancel subscriptions as one of four core harm categories and has brought
  enforcement on it [DP-07, unverified snippet].
- **Structural signal:** count DOM state-transitions / distinct pages required to
  reach a cancel action vs. the signup/purchase equivalent, when both flows are
  reachable and crawlable. Flag large asymmetries (e.g., 1-click signup vs. 5+ step
  cancel, or a cancel action gated behind a modal requiring a phone call with no
  further DOM path).
- **Structural/semantic:** PARTIALLY structural. Step-counting is structural once
  you have located the cancel flow; *finding* the cancel flow when it is
  deliberately buried in navigation, or requires an off-DOM channel (phone call),
  is a navigation/semantic problem the structural rule cannot solve on its own.
- **Difficulty:** Medium-high. Requires the agent (or the proxy) to actually
  traverse both flows to count steps, which is real crawl/navigation work.
- **False-positive risk:** Some services legitimately require more steps to cancel
  than to sign up for account-security or retention-offer reasons (e.g., an
  identity re-confirmation step). Step-count asymmetry alone is a weak signal
  without a reasonable threshold and without excluding security-driven friction.

## Tier 3 — explicitly out of scope for this weekend

### 6. Confirmshaming (guilt-laden decline-button copy)
- **Evidence it matters:** documented qualitatively in every taxonomy (Brignull,
  Mathur et al.) but with no isolated prevalence percentage or agent-specific ASR
  found [DP-06, DP-01].
- **Structural signal:** none. The DOM signature of a confirmshaming button is
  identical to a neutral one — same tag, same role, same position; only the text
  content differs, and it differs by tone/sentiment, not by a checkable property.
- **Structural/semantic:** REQUIRES SEMANTICS. This is the clearest example in the
  whole review of a pattern that cannot be caught by geometry/DOM-state alone —
  explicitly called out as such in [02-dark-patterns].
- **Difficulty:** N/A for a structural-only build; would require an NLP/LLM text
  classifier, which reintroduces the exact "LLM inspecting untrusted content"
  weakness this project is trying to avoid as a sole gate [M-03][M-04][M-09].
- **Recommendation:** declare explicitly out of scope for the structural core; at
  most, surface the raw decline-button text to the advisory LLM layer for a
  non-blocking suspicion flag.

### 7. Misdirection via visual hierarchy (color/size/position emphasis on a decoy button)
- **Evidence it matters:** documented qualitatively across all taxonomies, no
  isolated prevalence number [DP-01][DP-03][DP-06].
- **Structural signal:** computed style differences (font-size, color, position)
  between two semantically-equivalent buttons are technically readable — so this is
  not undetectable in principle — but interpreting *which* visual treatment counts
  as manipulative "emphasis" vs. ordinary UI design hierarchy requires a judgment
  call closer to semantics/visual design sense than a fixed threshold can honestly
  provide.
- **Structural/semantic:** PARTIALLY structural, judgment-heavy in practice.
- **Note specific to this project's threat model:** a DOM/AX-tree-only agent may
  already be structurally blind to this pattern in a way that is *protective* —
  it typically sees two equivalent button elements and doesn't weight the CSS
  salience a human's eye would. This cuts the opposite direction from every other
  row in this table: agent "blindness" here helps rather than hurts. (Inference
  from mechanism, not a directly tested finding — see `SYNTHESIS.md` §4.)
- **Recommendation:** out of scope. Low measured payoff, ambiguous structural
  signal, and the one thing we do know suggests our target agent may not need
  protecting from this pattern in the first place.

### 8. Fake urgency / scarcity (countdown timers, "N left in stock")
- **Evidence it matters:** Luguri & Strahilevitz's controlled experiment found this
  pattern had *no significant effect* on human acceptance (14.3%, ~= control) —
  the weakest measured effect of any pattern in that study [DP-05]. No agent-
  specific study found. This is a case where the literature actively argues
  *against* prioritizing a pattern that looks intuitively dangerous.
- **Structural signal:** a `setInterval`-driven countdown with no server-verified
  deadline is detectable (re-check displayed deadline against wall-clock behavior,
  note if it resets on reload) — mostly structural for the timer variant; "N items
  left" requires a ground-truth inventory oracle we don't have.
- **Structural/semantic:** MOSTLY structural for timers, semantics/oracle-dependent
  for stock-count claims.
- **Recommendation:** out of scope for the weekend build despite being technically
  easy, because the measured evidence says this pattern doesn't work well even on
  humans — building it would spend budget on the least-justified target in the set.

## Summary ranking (best evidence x structural detectability, over difficulty)

| Rank | Target | Tier | Structural? | Difficulty | Priority reason |
|---|---|---|---|---|---|
| 1 | Hidden/invisible instruction content | 1 | Fully | Low-Med | Highest real-world prevalence + only confirmed live incident |
| 2 | Overlay/hit-target mismatch | 1 | Fully | Low | Cheapest to build, classic well-understood mechanism |
| 3 | Pre-checked/pre-set form state | 1 | Fully | Low | Trivial DOM read, measured human-harm evidence, plausible agent amplification |
| 4 | Late-appearing costs (drip pricing) | 2 | Partial | Medium | Real measured human harm, needs step-tracking |
| 5 | Obstructed cancellation | 2 | Partial | Med-High | Real measured harm, but flow-discovery is the hard part |
| — | Confirmshaming | 3 (out) | Needs semantics | N/A | No structural signal exists at all |
| — | Visual-hierarchy misdirection | 3 (out) | Partial/judgment | N/A | Possibly self-mitigating for non-visual agents |
| — | Fake urgency/scarcity | 3 (out) | Mostly structural | Low | Easy to build, but literature says it barely works on anyone |

**Recommendation:** build targets 1-3 first; they are fully structural, cheap, and
carry the strongest evidence. Attempt 4-5 only if 1-3 are solid and time remains.
Explicitly do not attempt 6-8 in this cycle — say so if asked, rather than quietly
shipping a weak or absent detector for them.
