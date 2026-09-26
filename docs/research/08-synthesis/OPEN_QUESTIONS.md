# Open Questions

Written for two engineers who have not read the underlying papers. Each item: what
we don't know, what would resolve it, what it would cost, and whether we are about
to make an architectural bet on thin evidence.

## 1. Does structural detection actually work against general deceptive UI, or only against hidden text?

**What we don't know:** PhantomLint proves deterministic detection works for hidden
LLM instructions in documents [M-05]. Nothing in the literature proves the same
approach (DOM/computed-style/geometry rules) catches general deceptive UI — overlay
tricks, drip pricing, obstructed flows — when pitted against a real agent pipeline.
The mitigations workstream's own verdict: our core is "plausible and partially
precedented, not proven" [M-05, 04-mitigations §3].

**What would resolve it:** building targets 1-3 from `DETECTION_TARGETS.md` and
running them against a benchmark environment that already exists for exactly this
purpose — DECEPTICON or Ersoy et al.'s LiteAgent/TrickyArena — rather than inventing
our own eval harness. This also avoids the "we invented both the attack and the
detector" failure mode from the prior attempt.

**Cost:** this is most of the weekend. It is also the project's actual contribution
if it works — nobody else has published this measurement.

**Architectural bet risk: HIGH.** The entire project is staked on this being true.
We should say so plainly to stakeholders rather than implying it is precedented.

## 2. What is the false-positive rate of each detection rule on ordinary, benign sites?

**What we don't know:** none of the three source workstreams found or ran a
false-positive study for the specific rules in `DETECTION_TARGETS.md` against a
sample of ordinary commercial sites. We have qualitative reasoning about likely
false positives (accordions, cookie banners, shipping calculators) but no measured
rate.

**What would resolve it:** run each Tier-1 rule against ~20-50 real, non-adversarial
sites (e.g., a sample of top e-commerce/SaaS sites) and count flags. This is cheap —
a few hours — and should happen before the weekend's remaining time goes into Tier 2.

**Cost:** low (hours, no infra).

**Architectural bet risk: MEDIUM.** The project's own pass/fail rule (task completed
AND zero compromise) makes false positives just as fatal as missed attacks, but we
have not yet measured this for anything we plan to build.

## 3. Does detection reducing attack success actually preserve task utility for our specific design?

**What we don't know:** the one directly relevant data point (ProtectAI's classifier:
7.95% ASR, but utility collapse from 83% to 41% [M-08]) is for a text/ML classifier
gating an agent's inputs, not for a structural/geometry rule gating actions. It is
unknown whether a narrower, structural-only rule set has the same failure mode or a
much smaller one — plausibly smaller, since structural rules target narrow,
well-defined signals rather than broadly filtering "suspicious-looking" content, but
this is a hypothesis, not a result.

**What would resolve it:** measure task-success rate on a benign task set with the
detector active vs. inactive, alongside the ASR measurement in question 1. Same
benchmark run, additional metric — should not cost much beyond question 1's build.

**Cost:** marginal on top of question 1.

**Architectural bet risk: HIGH.** We are implicitly betting that "structural = fewer
false positives than an ML classifier" without evidence. This is a reasonable
hypothesis (structural rules are narrower and more targeted than a general
classifier) but it is our hypothesis, not a cited finding.

## 4. Should the advisory LLM layer see the whole page, or only content flagged by structural rules?

**What we don't know:** the literature is unambiguous that an LLM inspecting
untrusted content can itself be attacked through that content — up to 100%
guardrail-evasion rates are documented [M-03], and LLM-as-judge attacks succeed at
>30% ASR against the judge itself [M-09]. What is not established is whether
restricting the LLM's exposure (e.g., only showing it structurally-flagged snippets,
never the raw page) meaningfully reduces its own attack surface, or whether a
sufficiently adversarial snippet still compromises it regardless of scope.

**What would resolve it:** test the advisory LLM component specifically for guard-
injection susceptibility using the same style of adversarial content from [M-03]/
[M-04]/[M-09], not just functional testing on benign flagged content.

**Cost:** low-medium; mostly a matter of adapting existing published attack strings
rather than devising new ones.

**Architectural bet risk: MEDIUM.** We already treat the LLM as advisory-only per
the brief, which is the right design given the evidence — but "advisory" does not
automatically mean "safe to expose to untrusted content," and we have not tested
that boundary.

## 5. Which perception modality does our target agent use, and do we need to screen both DOM and rendered pixels?

**What we don't know:** the literature has no controlled study varying perception
modality while holding the attack constant [01-agent-attacks §6]. Separate attack
literatures exist per modality (CSS-hiding for DOM/AX-tree agents, typographic
pixel-injection for VLM/screenshot agents [A-11]), and a proxy that screens only one
channel will miss attacks aimed at the other.

**What would resolve it:** simply establishing, up front, which perception path the
demo/target agent actually uses (DOM text, accessibility tree, or screenshot/VLM).
If unknown or mixed, budget for both channels, which roughly doubles the Tier-1
detection-rule implementation surface (a text/DOM scan plus a rendered-pixel scan).

**Cost:** near-zero to determine; potentially doubles build cost if both channels
are needed and were not planned for.

**Architectural bet risk: HIGH if unaddressed** — this is not a research gap so much
as a scoping decision we can and should make immediately, before writing detection
code, since it changes what "Tier 1" even means.

## 6. Are the headline ASR numbers we plan to cite comparable, or would recomputation shrink them?

**What we don't know:** the critical re-evaluation paper found a widely-used
benchmark's own attack-injection design inflated reported ASR from ~9.25% (corrected)
to a padded ~70% [M-08]. We do not know whether the four benchmarks we cite most
prominently (InjecAgent, ASB, WASP, WAInjectBench) share this specific artifact or
are clean of it — WASP is explicitly the most methodologically careful of the four
[03-prevalence §1.1], but we have not independently re-audited InjecAgent or ASB's
construction.

**What would resolve it:** a focused read of InjecAgent's and ASB's methodology
sections (not just abstracts) checking specifically for forced-tool-injection or
similar artifacts before we repeat their headline numbers in a pitch deck.

**Cost:** a few hours of reading, no code.

**Architectural bet risk: LOW for the build, MEDIUM for anything we say publicly.**
This doesn't change what we build, but it could change what numbers we're willing to
put in front of a reviewer.

## 7. Does dark-pattern susceptibility break down by pattern type for agents, or only in aggregate?

**What we don't know:** DECEPTICON (70%+) and Ersoy et al. (41% average) report
aggregate susceptibility; neither source, at the abstract level fetched, breaks
results out per-pattern-type with enough granularity to confirm which specific
patterns (pre-checked boxes vs. drip pricing vs. obstruction) drive the number
[02-dark-patterns "Known gaps"]. SusBench's qualitative ranking (Preselection, Trick
Wording, Hidden Information fool agents and humans alike) is the closest thing we
have to a breakdown, but without agent-specific percentages [03-prevalence §3].

**What would resolve it:** read the full results tables/appendices of DECEPTICON and
Ersoy et al. (not just abstracts) — both are fetchable arXiv papers, this is a
reading task, not new research.

**Cost:** low (a few hours), high value — this would directly firm up the
`DETECTION_TARGETS.md` ranking, which currently relies partly on qualitative
reasoning (SusBench's ranking) rather than hard agent-specific percentages per
pattern.

**Architectural bet risk: MEDIUM.** Our Tier-1/Tier-2 ranking in
`DETECTION_TARGETS.md` is defensible from what's published, but a full read of these
two papers could reorder it — e.g., if pre-checked boxes turn out to be a small
fraction of DECEPTICON's 70%, that changes target #3's priority.
