# Prevalence & Evidence Base

## What this document establishes

We reviewed benchmark papers, one large-scale in-the-wild measurement study, one
mature dark-pattern crawl, and vendor/disclosure reports on browsing-agent attacks.
Headline takeaways:

1. Indirect prompt injection is the best-measured agent-targeted attack class, with
   four separate benchmarks (WASP, AgentDojo, InjecAgent, ASB) and now one large web
   crawl confirming it is not just a lab artifact -- it has been found deployed on live
   sites [A-09], [A-14].
2. Reported "attack success rates" vary by an order of magnitude (16%-86%) depending
   entirely on definition -- partial/intermediate success vs. full end-to-end goal
   completion. The most careful benchmark (WASP) reports both, and the gap between them
   is the single most important methodological fact in this literature [A-02].
3. Dark-pattern susceptibility of agents is a newer but fast-growing literature
   (2025-2026), still short on head-to-head ASR numbers comparable to the injection
   benchmarks, but consistent in finding agents at least as susceptible as humans, and
   for some pattern types more so, because they optimize for task completion rather
   than self-protection [A-12], [A-13].
4. We found exactly one credible real-world (non-laboratory) incident report -- Unit
   42s December 2025 case of a live site attempting to manipulate an AI ad-review
   pipeline [A-14]. Every other "attack on a browsing agent" story we found (Brave/Comet,
   BragJack, OpenAI Atlas disclosures) is a responsibly-disclosed proof-of-concept, not
   an observed in-the-wild compromise. This distinction matters and is easy to blur in
   press coverage -- we did not blur it.
5. Dark-pattern prevalence in the wild is well established for humans (Mathur et al.
   2019: ~11.1% of ~11K shopping sites, 1,818 instances) [A-11] but not yet
   re-measured for how often those same pages would fool an agent -- that gap is
   explicitly called "insufficient evidence" below.

---

## 1. Benchmarks under adversarial web conditions

### 1.1 WASP -- Web Agent Security against Prompt injection [A-01][A-02][A-03]
- What it measures: end-to-end prompt injection against UI/browser agents operating
  realistic web apps (GitLab, Reddit), not synthetic toy pages.
- Size: 2 live-app environments, 21 attacker goals x 2 user goals = 42 scenarios x 2
  injection template types = 84 adversarial tasks, plus 37 benign utility tasks.
- Headline numbers, by model (intermediate ASR = attacker achieved a step toward the
  goal; end-to-end ASR = attacker full goal was completed):

| Model / scaffold | Intermediate ASR | End-to-end ASR |
|---|---|---|
| GPT-4o-mini (axtree, VisualWebArena) | 34.5% | 2.4% |
| GPT-4o (axtree, VisualWebArena) | 32.1% | 1.2% |
| GPT-4o (axtree+SOM, VisualWebArena) | 42.9% | 3.6% |
| OpenAI o1 (system, Tool Calling) | 85.7% | 16.7% |
| Claude Sonnet 3.5 v2 (CURI) | 58.3% | 6.0% |
| Claude Sonnet 3.7 Extended Thinking (CURI) | 53.6% | 3.6% |

- Key qualitative finding, verbatim-quoted: "security by incompetence" -- current
  agents mostly resist full attacks because they are bad at multi-step tasks generally,
  not because any defense is robustly blocking the injected instruction. This is a
  warning that end-to-end ASR will likely rise as base agent capability improves, even
  with no change in attacker sophistication.
- Methodological note: small benchmark (2 apps, 84 tasks) -- a real strength (live
  apps, not toy HTML) traded against limited environment diversity. Do not generalize
  end-to-end ASR numbers to arbitrary websites.

### 1.2 AgentDojo [A-04][A-05]
- What it measures: prompt injection across four domains (email client, e-banking,
  travel booking, workspace/Slack-like tool) as a general test harness for attacks and
  defenses, not fixed to one metric.
- Size: 97 realistic tasks, 629 associated security test cases.
- Headline finding (verified from abstract only): state-of-the-art LLMs fail a
  meaningful fraction of tasks even absent any attack, and existing injection attacks
  break some but not all of the benchmark defined security properties. We could not
  extract a specific numeric ASR or utility-under-attack figure per model
  (e.g., GPT-4o, Claude 3.5 Sonnet) from the abstract alone -- the full paper/leaderboard
  would be needed, and we do not report numbers we could not directly verify. Treat any
  "GPT-4o drops from 69% to 50% utility under attack" style figure circulating in
  secondary summaries as unverified until traced to the primary paper.

### 1.3 InjecAgent [A-06]
- What it measures: indirect prompt injection specifically in tool-integrated
  (function-calling) agents, separate from browser-DOM agents, but foundational to the
  same threat model (untrusted tool output steering the agent).
- Size: 1,054 test cases, 17 user-facing tools, 62 attacker-controlled tools.
- Headline number: ReAct-prompted GPT-4 was manipulated 24% of the time in the base
  setting. An "enhanced" attack using a hacking-style prompt further increased this (the
  paper own summary describes it as "nearly doubling," but we could not confirm the
  exact resulting percentage from the abstract -- flagged low-confidence pending the full
  text).

### 1.4 Agent Security Bench (ASB) [A-07][A-08]
- What it measures: the broadest sweep found -- 16 attack types (10 prompt-injection
  variants, memory poisoning, a novel "Plan-of-Thought" backdoor, 4 mixed attacks)
  against 11 defenses, across 10 application scenarios (e-commerce, autonomous driving,
  finance, etc.), 400+ tools, and 13 LLM backbones.
- Headline number: highest average ASR of 84.3%.
- Critical caveat we must flag: this is a maximum observed across a large grid of
  attack x scenario x model combinations, not a single reproducible rate for one
  attack against one agent. Quoting "84.3%" without this context would misrepresent the
  paper. We record it as an upper bound on how bad things can get under a
  best-case-for-the-attacker combination, not a typical real-world rate.

### 1.5 Cross-benchmark comparison and what it means
Four benchmarks, four different numbers for "how often does injection work": 24%
(InjecAgent baseline), 16.7% (WASP end-to-end, strongest model), 58-86% (WASP
intermediate / partial), 84.3% (ASB, best-case aggregate). These are not
contradictory -- they are measuring different things (full goal completion vs. partial
compromise vs. best-case-across-many-conditions). Any downstream document that says "the
attack success rate is X%" without naming which of these it means is not usable for
prioritization. This is the single clearest methodological finding of this workstream.

---

## 2. Measurement studies: how common is this in the wild?

### 2.1 Indirect prompt injection crawl (2604.27202) [A-09][A-10]
This is the most important source in this file for prevalence, because it is the only
one of our sources built from live-web crawl data rather than curated benchmark
environments.
- Scale: ~1.2 billion URLs across ~24.8 million hosts (October 2025 Common Crawl
  snapshot), supplemented with Shodan/Censys internet-scan data.
- Confirmed findings: 15,300 validated indirect-prompt-injection instances found
  across 11,700 pages spanning 2,042 distinct hosts.
- Prevalence in context: 2,042 confirmed hosts out of 24.8 million crawled is on the
  order of 0.008% of hosts -- injection is real and systematic where it occurs
  (avg. ~42 injections per affected domain suggests deliberate, repeated deployment, not
  one-off vandalism) but it is not yet a majority or even a common phenomenon across
  the general web. This tempers any narrative that most web content is now booby-trapped
  for agents.
- Concealment: ~70% of confirmed payloads sit in non-rendered HTML (headers,
  comments, metadata) -- i.e., invisible to a human glancing at the rendered page but
  visible to any agent that reads raw DOM/HTML rather than only rendered text. This is a
  directly actionable detection signal: content present in DOM/metadata but absent from
  rendered/accessibility-tree text is a strong prior for injection.
- Model compliance under controlled testing: across 13 models tested by the same
  authors, compliance with injected instructions reached up to 8% for smaller models on
  plain-text inputs; the paper reports structured input representations reduced this.
  We could not extract the exact figure for larger/flagship models from the abstract --
  flagged for follow-up.

### 2.2 Dark patterns at scale -- Mathur et al. 2019 [A-11]
The canonical human-facing measurement study, included because the brief explicitly
calls dark patterns in scope and this is the field foundational prevalence number.
- Scale: ~11,000 shopping websites, ~53,000 product pages, automated detection with
  expert/manual validation.
- Findings: 1,818 dark-pattern instances across 15 types / 7 categories; ~11.1% of
  sites (1,254/11K) carried at least one instance; a stricter "deceptive" subset applied
  to 183 sites; 22 third-party services were found selling dark-pattern implementations
  as a turnkey product -- evidence this is a supply-chain, not just a bespoke, practice.
- Age/relevance caveat: this is a 2019 study of human-facing e-commerce UX. It
  establishes that dark patterns are common and commercially supplied, but it says
  nothing about how an agent, rather than a human shopper, responds to them. That
  question is addressed only by the much smaller, much newer studies in section 3 below.

---

## 3. Attack-class-specific evidence: dark patterns against agents specifically

This sub-literature is younger (2025-2026) and thinner on hard ASR numbers than the
injection benchmarks. We report what we can verify and flag the rest explicitly.

- SusBench [A-12]: 313 tasks across 55 real consumer websites, 9 dark-pattern types,
  5 state-of-the-art computer-use agents (CUAs). Finding: agents and a 29-person human
  panel share the same weak points -- Preselection, Trick Wording, and Hidden Information
  fool both, while both resist more "overt" patterns. We could not extract a per-model
  numeric susceptibility percentage from the abstract; the qualitative
  pattern-type ranking is the only piece we can confirm at this confidence level.
- "Dark Patterns Meet GUI Agents" (CHI 2026) [A-13]: 16 dark-pattern types, agents +
  humans + human-AI teams. Qualitative finding, directly relevant to the middleware
  design goal: agents "often fail to recognize dark patterns, and even when aware,
  prioritize task completion over protective action" -- i.e., detection alone may be
  insufficient if the agent objective function still rewards plowing through a known
  manipulative interface. Human oversight helped but did not fully close the gap. No
  numeric susceptibility rate obtainable from the abstract.
- Insufficient evidence: we found no study directly re-running the Mathur et al.
  11K-site dark-pattern corpus against a browsing agent to get an apples-to-apples
  "how often does an agent fall for the same dark patterns humans fall for, on the same
  real pages" prevalence number. This is a concrete, fundable gap, not a guess we are
  willing to fill with intuition.

---

## 4. Real-world incidents vs. laboratory demonstrations

The brief specifically asks us to keep these separate. Here is every case we found,
sorted:

| Case | Real-world or lab? | Basis |
|---|---|---|
| Unit 42 IDPI-vs-ad-review case, Dec 2025 [A-14] | Real-world | Vendor states "first reported detection" from live telemetry, on a live site (reviewerpress[.]com), not a controlled test |
| Common Crawl injection measurement [A-09] | Real-world (prevalence), not an "incident" | Confirms injected payloads exist on 2,042 live hosts; does not claim to have observed an agent actually being compromised by them in production |
| Brave/Comet + Fellou hidden-text injection [A-15] | Laboratory PoC, responsibly disclosed | Explicitly a research disclosure; authors state no in-the-wild exploitation is claimed |
| BragJack (malicious-extension hijack of browser AI assistants) | Laboratory PoC per our search summary | Described in secondary reporting as a "proof-of-concept" from an independent researcher; we did not fetch the primary write-up directly, so it is not included as a sourced claim in sources.json -- flagged here only as an unverified lead for follow-up |
| OpenAI ChatGPT Atlas internal testing disclosure | Vendor own internal/red-team testing, not observed in-the-wild abuse | Secondary reporting frames it as OpenAI internal testing prompting a security update, not a customer-reported compromise; not independently fetched, so not in sources.json |

Conclusion: exactly one of our sources supports a genuine "we observed this attack
being used against a real deployed system" claim [A-14]. Everything else that reads
like an "attack on agents" story in press coverage is either a measurement of
opportunity (payloads exist on the web) or a disclosed vulnerability demonstration. Any
severity ranking below is built on benchmark ASR and crawl prevalence, not on a body of
confirmed incidents -- because that body does not yet exist in the literature we could
verify.

---

## 5. Where researchers state which threats are most severe

- OWASP Gen AI Security Project ranks Prompt Injection as LLM01:2025, the number
  one item in its Top 10 for LLM Applications, for the second consecutive edition
  [A-16]. This is an expert-consensus/standards-body judgment, not a measured statistic,
  and we report it as such.
- Multiple benchmark papers (WASP, ASB) independently describe current defenses as
  inadequate against prompt injection specifically -- WASP "security by incompetence"
  framing [A-03] and ASB blanket statement of "limited effectiveness of current
  defenses" [A-07] are the closest things to a severity judgment we found directly
  inside primary sources, as opposed to secondary commentary.
- We did not find a primary source that explicitly ranks dark-pattern-style
  human-targeted manipulation against prompt injection in terms of severity for agents
  specifically. The CHI 2026 paper finding that agents "prioritize task completion
  over protective action" [A-13] is suggestive that dark patterns may be a higher
  relative risk for agents than for humans (agents lack the visual skepticism the brief
  itself notes), but this is our inference from their finding, not a claim the authors
  make explicitly -- flagged as inference, not sourced fact.

---

## 6. HEADLINE DELIVERABLE -- Ranked table of attack classes

### Ranking criteria (stated explicitly)
We rank by a composite of three factors, each drawn only from sourced numbers above:
1. Prevalence -- how often the precondition for the attack exists on the live web
   (crawl/measurement evidence, not lab-only).
2. Attack success rate -- using the most conservative (hardest-to-achieve, i.e.
   end-to-end / full-goal) verified number available for that class; where only
   partial-success or best-case-aggregate numbers exist, we say so.
3. Consequence severity -- qualitative, from what the attack achieves if it succeeds
   (data exfiltration / unauthorized transaction vs. wasted time / minor unwanted
   purchase), drawn from the sources own stated attack objectives.

Where any leg of this is not backed by a source we opened, we mark the cell
"insufficient evidence" rather than estimate.

| Rank | Attack class | Prevalence evidence | ASR evidence (conservative, with model/n) | Consequence severity | Overall justification |
|---|---|---|---|---|---|
| 1 | Indirect prompt injection (hidden/DOM-level instructions) | Confirmed on 2,042 live hosts / 11.7K pages in a 1.2B-URL crawl [A-09]; ~70% concealed in non-rendered HTML [A-10] | 16.7% end-to-end with OpenAI o1 (n=84 tasks, WASP) [A-01][A-02]; up to 86% partial success; 24% baseline on GPT-4 (n=1,054, InjecAgent) [A-06] | High -- objectives observed include data exfiltration, unauthorized transactions, SEO/phishing redirection, system-prompt leakage [A-14] | Only class with all three legs backed by real crawl data, multiple independent benchmarks, AND one real-world incident report. Ranked #1 on both prevalence-with-teeth and consequence. |
| 2 | Tool/function-call hijacking via untrusted tool output | Insufficient evidence for wild prevalence (no crawl found); benchmark-only | 24% baseline / higher with enhanced prompts on GPT-4, n=1,054 tool test cases (InjecAgent) [A-06]; up to 84.3% best-case aggregate across 13 backbones (ASB) [A-07][A-08] | High -- same exfiltration/unauthorized-action risk as #1, since this is closely related to indirect injection but scoped to tool-calling agents rather than browser-DOM agents | Strong ASR evidence, but no live-web prevalence measurement exists yet for this specific vector (as distinct from web-page injection) -- held below #1 on that basis alone. |
| 3 | Dark patterns (human-targeted, transferring to agents) | Well-measured for humans: ~11.1% of ~11K e-commerce sites, 1,818 instances (2019 data) [A-11]; insufficient evidence for what fraction of those same pages actually manipulate an agent | No agent-specific end-to-end ASR percentage verified; qualitative finding that agents are "particularly susceptible" to specific pattern types (Preselection, Trick Wording, Hidden Information) and prioritize task completion over self-protection [A-12][A-13] | Medium -- typically unwanted purchase/subscription/consent, not system compromise or data exfiltration, based on the taxonomy in the sources reviewed | Large, well-established human-facing prevalence, but the agent-specific ASR literature is too new and too thin on numbers to rank above the injection classes yet. Flagged as the fastest-growing evidence gap. |
| -- | Clickjacking / overlay attacks specifically against agents | Insufficient evidence -- no benchmark or crawl in our search results measured this as a distinct class from general dark patterns | Insufficient evidence | Insufficient evidence | Not ranked. We did not find dedicated agent-targeted measurement; do not infer a score. |
| -- | Confirmshaming / drip pricing specifically against agents | Covered only as sub-categories inside the Mathur et al. human taxonomy [A-11]; no agent-specific re-measurement found | Insufficient evidence | Insufficient evidence | Not ranked separately from the general dark-pattern class above. |

### How to read this table
Rank 1 and 2 are both "prompt injection" in the taxonomy sense the brief defines
(agent-targeted), split only by whether the payload lives in web content an agent reads
(#1) or in tool/API output an agent function-calling layer trusts (#2) -- the brief
groups both under "indirect prompt injection," and we preserved that split only because
the evidence bases are genuinely separate benchmarks with separate numbers. If the
downstream team wants a single merged "prompt injection" row, combine 1 and 2: it would
still rank #1 by a wide margin over dark patterns on every leg we could measure.

### What this means for what the middleware should detect first
Given the evidence: detecting (a) instructions present in raw DOM/HTML/tool-output but
absent from rendered/visible content, and (b) tool-call arguments or navigation targets
that diverge from the user original stated goal, addresses the best-evidenced and
highest-severity class [A-09][A-10]. Dark-pattern detection is a legitimate second
priority backed by a mature human-facing literature, but the team should not expect to
find as dense an agent-specific ASR literature to benchmark against yet -- that gap
itself is worth stating in any report.
