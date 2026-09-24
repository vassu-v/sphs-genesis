# Synthesis — Adversarial Web Content vs. Autonomous Browsing Agents

Sources: `01-agent-attacks/FINDINGS.md`, `02-dark-patterns/FINDINGS.md`,
`03-prevalence/FINDINGS.md`, `04-mitigations/FINDINGS.md`, `05-citations/VERIFICATION.md`.
Tags like `[A-10]`, `[DP-10]`, `[M-08]` refer to those workstreams' own `sources.json`
entries — look them up there for full citation metadata; this document does not
re-mint tags.

## 1. The threat, with numbers

Two attack families are both real and both measured, and they are not the same
attack surface.

**Agent-targeted (indirect prompt injection).** This is the best-evidenced class.
A live crawl of ~1.2 billion URLs / ~24.8M hosts found 15,300 validated injection
instances across 11,700 pages on 2,042 distinct hosts — roughly 0.008% of hosts, so
not yet a majority phenomenon, but ~70% of confirmed payloads sit in non-rendered
HTML (comments, metadata, headers), meaning invisible to a human but visible to any
agent reading raw DOM/HTML [A-09/A-10 in 03-prevalence]. Benchmark attack-success
rates range wildly by what "success" means (see §4): InjecAgent reports 24% baseline
/ up to ~47% enhanced on GPT-4 over 1,054 tool-hijack cases [A-06]; Agent Security
Bench reports a best-case aggregate of 84.3% ASR across 13 backbones and 400+ tools
[A-07]; WASP, the most methodologically careful benchmark (live GitLab/Reddit apps,
not toy pages), reports intermediate ASR of 16-86% but end-to-end ASR of only 0-17%
[A-10 in 01-agent-attacks / M-02 in 04-mitigations]. There is exactly one confirmed
real-world (non-laboratory) incident: Unit 42's December 2025 report of a live site
manipulating an AI ad-review pipeline [A-14]. Everything else reported as an "attack
on agents" in press coverage (Brave/Comet, BragJack, OpenAI Atlas) is a disclosed
proof-of-concept, not an observed compromise — this distinction is easy to blur and
we did not blur it.

**Human-targeted dark patterns transferring to agents.** This is a newer (2025-2026)
but now directly measured literature, not speculation. DECEPTICON (Stanford,
arXiv:2512.22894) found dark patterns steer agent trajectories to malicious outcomes
in over 70% of 700 tested tasks vs. a 31% human baseline — agents roughly 2.3x more
susceptible than humans on the same tasks [DP-10]. Ersoy et al. (Purdue, IEEE S&P
2026, arXiv:2510.18113) found agents fall for an individual dark pattern ~41% of the
time on average across six agents and three LLMs, and that both visual rendering and
underlying HTML/DOM encoding independently move susceptibility, with stacked
patterns compounding the effect [DP-11]. Both papers were verified to the highest
standard by the citations workstream (verbatim abstract match, no overstatement).

**Does it get better or worse with capability?** Worse, on the dark-pattern side —
directly against intuition. DECEPTICON found susceptibility *increases* with model
size and test-time reasoning budget: bigger, more-reasoning models are more fooled,
not less [DP-10]. On the injection side, WASP's authors attribute agents' current
low end-to-end success rate to "security by incompetence" — agents fail complex
multi-step attacker goals because they are bad at complex multi-step tasks in
general, not because anything is defending them — and warn end-to-end ASR should be
expected to rise as base capability improves, with no change in attacker
sophistication [A-10 / M-02]. Both findings point the same direction: whatever
margin of safety exists today is capability-limited, not defense-derived, and is
shrinking as models improve.

## 2. What has been tried as a defence, and what measurably failed

- **Spotlighting / provenance-marking** (Microsoft, arXiv:2403.14720): marking
  untrusted content so the model can distinguish it from instructions. Measured:
  ASR falls from >50% to <2% on GPT-family models [M-01]. Real, cheap, weekend-
  buildable — but it is an LLM-side mitigation (depends on the model honoring the
  marking), not a deterministic guarantee.
- **Instruction-hierarchy training** (OpenAI): 10-63% ASR reduction depending on
  benchmark, vendor-reported, requires owning model training — not applicable to an
  external proxy [04-mitigations §1.2].
- **CaMeL** (Google DeepMind, arXiv:2503.18813): capability-based control/data-flow
  separation, the most rigorous architectural defence measured. On AgentDojo:
  77% task success under CaMeL's structural protection vs. 84% undefended — an
  8-point utility cost even in the best published defence [M-07]. Requires owning
  the agent's planner/interpreter; not something an external proxy can retrofit.
- **Fine-tuned classifier guard** (ProtectAI DeBERTa-based PI Detector): cut ASR to
  7.95% on AgentDojo but collapsed task utility from 83.02% to 41.49%, because it
  also blocked large amounts of legitimate content [M-08]. **This is the single
  most important cautionary number in the whole literature review**: a detector
  that "works" by the attack-success metric can simultaneously fail the thing that
  actually matters, which is task completion without compromise.
- **The same paper's own "Sanitizer" defense was bypassed by its own authors** using
  Braille encoding: GPT-4o correctly decoded Braille-encoded instructions and
  followed them even after the sanitizer had flagged the content as dangerous — the
  removal step failed even though detection succeeded [M-08]. Detection and
  mitigation are not the same event.
- **LLM guardrails as the gate**: demonstrably breakable through the content they
  inspect. Hackett et al. bypass six commercial guardrail systems (Azure Prompt
  Shield, Meta Prompt Guard) at up to 100% evasion via character-injection and
  adversarial-ML tricks [M-03]. JudgeDeceiver and the Comparative Undermining
  Attack independently break LLM-as-judge defenses, the latter at >30% ASR against
  instruction-tuned judges, and all three tested defenses (known-answer, perplexity,
  windowed-perplexity detection) proved inadequate [M-04][M-09]. This is convergent,
  multi-paper evidence, not a single result, and it is the strongest support in the
  literature for our own design thesis: an LLM in the loop must stay advisory, never
  the sole or final gate.
- **Adaptive attackers break published defenses generally.** A 2025 re-evaluation
  found published prompt-injection defenses perform worse than their own papers
  claim once tested against adaptive attackers and utility-preserving criteria
  simultaneously — and separately showed a widely-used benchmark's forced-tool-
  injection design artificially inflated ASR from ~9.25% (corrected) up to a padded
  ~70%, meaning published defense-effectiveness numbers may not be comparable across
  papers even within the same benchmark family unless the methodology is checked
  [M-08]. Treat every headline "our defense achieves X% reduction" claim as
  provisional until you know whether it was tested adaptively.

## 3. Where the genuine research gap is

Nobody has published a deterministic/structural detector evaluated against general
deceptive web UI (fake buttons, overlay hijacking, drip-pricing, obstructed cancel
flows) specifically in an agent-action-pipeline context. What exists instead:

- **Hidden-text detection is solved-ish and precedented.** PhantomLint (arXiv:
  2508.17884) does exactly this for structured documents/PDFs using purely
  deterministic signals (CSS-hiding, zero/near-zero font size, color-matches-
  background, zero-width Unicode, layered content) [M-05]. The mechanism and stated
  limitations (false positives from legitimate small-font/layered design; evasion by
  sophisticated obfuscation) are confirmed; exact precision/recall numbers were not
  extractable and are marked low-confidence.
- **Dark-pattern detection is mature for humans, unvalidated for agents.** Mathur et
  al.'s text/DOM classifier (CSCW 2019) hits ~83% accuracy on page text with no
  rendering required [DP-12]; screenshot-based detectors (AidUI, UIGuard) reach
  F1 ~0.65-0.83 depending on pattern type [DP-13][DP-14] — but none of these three
  detectors were built for, or evaluated against, an agent-facing DOM/AX-tree
  consumption pipeline. This is a stated gap, not an inference.
- **Overlay/hit-testing mismatch detection** (checking whether the element that
  will actually receive a click matches the element perceived as clickable) is
  well-understood 2010s clickjacking-era web security, and has at least one
  partially-verified analogue on mobile LLM agents (transparent/FLAG_NOT_FOCUSABLE
  overlays visible to an agent's capture pipeline but excluded from the interactive
  hierarchy) [P-04, low confidence] — but has not been re-validated for agent action
  safety on the general web in any measured paper we found.
- **No controlled study varies perception modality (DOM-text vs. AX-tree vs.
  screenshot/VLM) while holding the attack constant** — the literature has separate
  per-modality attack studies (CSS-hiding for DOM agents, ARIA/alt-text abuse for
  AX-tree agents [A-05], typographic pixel-injection for VLM/screenshot agents
  [A-11]) but no head-to-head comparison [01-agent-attacks §6].
- **No study re-runs Mathur et al.'s 11K-site human dark-pattern corpus against a
  browsing agent** to get an apples-to-apples "does the same page that fools a human
  also fool an agent" prevalence number [03-prevalence §3].

**The plausible gap we could fill:** a deterministic, structural detector that
screens both the raw DOM/AX-tree and geometry/computed-style for the *specific,
already-catalogued* palette of concealment and mismatch techniques (CSS-hiding,
ARIA-only content, off-screen positioning, hit-target/visual-target mismatch,
pre-checked form state, DOM-diffable late-appearing costs), evaluated end-to-end
against an actual agent pipeline rather than only against static content — combined
honestly with the finding that detection alone (per [M-08]) does not equal
mitigation, so any such detector must be evaluated on task-utility-preserved as well
as attack-blocked.

## 4. Contradictions and inconvenient findings

This section is deliberately prominent, per the brief. Do not soften it.

- **"Plausible and partially precedented, not proven."** This is the mitigations
  workstream's own verdict on our structural-detection core, quoted directly: the
  deterministic approach is well-precedented for the narrow hidden-text sub-problem
  (PhantomLint) but "plausible-but-unvalidated for general deceptive-UI detection on
  the live web against agents specifically (no benchmark exists yet — we would be
  the first to measure it...but we cannot claim the literature already proves it
  works)" [M-05, 04-mitigations §3]. We are building on precedent for one narrow
  slice and speculation for the rest.
- **Detection succeeding is not mitigation succeeding.** The ProtectAI classifier
  cut ASR to 7.95% while collapsing task utility from 83% to 41% [M-08]. A guard
  that blocks the attack by blocking almost everything is not a working defense
  under this project's own benchmark rule (PASS = task completed AND zero
  compromise) — it fails that rule as hard as a guard that misses attacks entirely.
  Any detector we build must report both its catch rate and its false-positive/
  utility cost, or the number is not usable.
- **Detection can succeed and the mitigation step can still fail.** The Braille-
  encoding bypass of the "Sanitizer" defense — flagged as dangerous, then decoded
  and followed anyway by GPT-4o — shows that "we detected it" and "we stopped it"
  are two different engineering problems, and the second one is not automatically
  solved by the first [M-08].
- **Bigger/smarter models are more vulnerable to dark patterns, not less** [DP-10].
  This directly undercuts any argument of the form "use a stronger model and the
  problem gets smaller." It gets bigger.
- **Attack-success rates are incomparable across papers.** InjecAgent 24-47%, ASB
  84.3% best-case aggregate, WASP 16-86% intermediate / 0-17% end-to-end — these are
  not disagreeing measurements of one true number, they are different metrics on
  different threat models, and quoting any one without its exact definition
  misrepresents the field [01-agent-attacks §7, 03-prevalence §1.5]. The WASP
  partial-vs-full distinction specifically (16-86% vs. 0-17%) is the sharpest
  illustration: a single-digit "attack succeeded" headline can be hiding an
  80-point rate of partial compromise.
- **Fake urgency/scarcity, the dark pattern most people assume is dangerous, tested
  as ineffective on humans.** Luguri & Strahilevitz found countdown/scarcity framing
  had no significant effect on acceptance (14.3%, ~= control), while hidden-
  information and obstruction patterns had far larger effects (14.8%→30.1%, and
  →23.6%, respectively) [DP-05]. We should not let intuitive salience (countdown
  timers "feel" manipulative) override the measured effect-size ranking when
  prioritizing detection targets.
- **A pattern that helps a non-visual agent, not just hurts it.** Misdirection via
  visual hierarchy (color/size/position emphasis on a decoy button) may be
  genuinely invisible — and therefore harmless — to a DOM/AX-tree-only agent that
  never weighs computed CSS salience the way human vision does. This cuts the
  opposite direction from every other pattern in the review: greater agent
  "blindness" here is protective, not exploitable. This is inference from
  first-principles reasoning about detection mechanism, not a directly tested
  agent-specific finding — flagged as such in [02-dark-patterns] and carried
  forward with the same caveat here.
- **Benchmark methodology itself is shaky.** The critical-evaluation paper showed a
  widely-used benchmark's own attack-injection design artificially inflated
  reported ASR (padded ~70% vs. corrected ~9.25%) [M-08]. This means some of the
  "headline" numbers in section 1 of this document may themselves need re-checking
  against the specific benchmark's construction before being repeated in a pitch.
- **Only one confirmed real-world incident exists** [A-14] against a much larger
  body of lab demonstrations and benchmark numbers. We should not imply this threat
  is currently rampant in production when the evidence base is overwhelmingly
  laboratory/benchmark, not observed compromise — while still taking the crawl
  data (2,042 hosts with real injected payloads) seriously as evidence of intent
  and capability, not just as a hypothetical.

## 5. Methodological warnings to carry into any pitch or report

1. **Always name the metric.** "Attack success rate" alone is not a citable number;
   state intermediate vs. end-to-end, and the benchmark name, every time (WASP
   16-86% vs. 0-17% is the canonical example to cite when explaining this).
2. **Distinguish measured from proposed.** OWASP's Top 10, the Design Patterns
   paper's five architectural patterns, and human-in-the-loop gating are all
   consensus/recommended, not independently benchmarked as standalone numbers —
   say so rather than implying they are measured defenses [P-01, M-12].
3. **Distinguish real-world incident from disclosed PoC from benchmark.** Only
   Unit 42's case [A-14] is a real-world incident; everything else is lab or
   benchmark, including all the ASR numbers quoted above.
4. **A same-paper self-comparison is weaker evidence than independent replication.**
   The activation-delta task-drift detector's >0.99 AUC beats commercial filters on
   the *authors'* own held-out set [A-09 in 01-agent-attacks] — encouraging, not
   independently adjudicated.
5. **Grey literature and unfetched claims are excluded from our evidence base.**
   Several claims (a rumored OpenAI/Anthropic/DeepMind joint red-team breaking
   twelve defenses; several 2026 arXiv preprints found only via search snippet)
   could not be verified against primary text and are explicitly not cited as
   fact anywhere in this synthesis.
