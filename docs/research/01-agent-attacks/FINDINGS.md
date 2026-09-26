# Track 01 -- Attacks that target the agent itself

## Summary of what we actually established

Indirect prompt injection (IPI) against web/tool-using LLM agents is a real, actively
measured phenomenon with a growing benchmark literature (InjecAgent, WASP, Agent
Security Bench, WAInjectBench), not a theoretical worry. The field traces to Greshake
et al. 2023 [A-01], which named the threat and produced the first taxonomy. Reported
attack success rates vary enormously by what is being measured -- this is the single
most important methodological fact in the literature: "the agent started following
the injected instruction" (intermediate/partial hijack) and "the attacker's full goal
was achieved" (end-to-end) are different metrics that can differ by 5-10x [A-10].
Delivery mechanisms for human-invisible-but-parser-legible instructions are well
documented and fairly narrow in number (CSS/off-screen hiding, ARIA/alt-text abuse,
HTML comments, hidden form fields, metadata, base64/encoding obfuscation) [A-03][A-04].
Tool-call hijacking and goal/task drift are measured with dedicated benchmarks and at
least one white-box detection method with reported near-perfect AUC on its own test
distribution [A-09]. The literature also shows, repeatedly, that defenses which look
good against static/non-adaptive attacks collapse against adaptive attackers -- this
is a recurring finding, not a single paper claim. Typographic/image-embedded
injection against VLM-based (screenshot) agents is a distinct and separately measured
attack surface [A-11]. Where the literature is genuinely thin: architecture-by-
architecture comparison (DOM vs accessibility-tree vs screenshot agents) is mostly
done informally inside individual papers rather than as a dedicated controlled
comparison; most named "taxonomies" for agentic AI are very recent (2025-2026)
surveys/SoKs rather than mature, widely-cited standards, so treat naming conventions
as still settling.

---

## 1. Foundational concept and taxonomy: indirect prompt injection

Greshake, Abdelnabi, Mishra, Endres, Holz and Fritz, "Not what you have signed up for:
Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection"
(arXiv 2302.12173, 2023) is the paper that named and systematized indirect prompt
injection: an adversary places instructions in content that the LLM will retrieve
during normal operation (a web page, a document, a search result), rather than typing
them into the chat box directly [A-01]. Their taxonomy of impacts includes information
gathering/exfiltration, fraud, malware-like propagation ("worming" -- one compromised
agent infects the data another agent will later read), intentional misinformation
("information ecosystem contamination"), and manipulated content/availability attacks
[A-01]. This impact taxonomy (theft / fraud / propagation / contamination) recurs,
often relabeled, across almost every later paper in this space.

OWASP's Gen AI Security Project LLM01:2025 entry formalizes the direct vs. indirect
distinction that the field now uses as vocabulary: direct injection is the user's own
prompt altering model behavior; indirect injection is external content (a website, a
file) doing the same when the model ingests it [A-02]. OWASP's write-up also lists
concrete injection techniques worth aligning our detector vocabulary to: hidden or
imperceptible text, multimodal injection (instructions embedded in images alongside
benign text), payload splitting across document sections, adversarial suffixes, and
multilingual/encoded obfuscation (base64, homoglyphs, emoji) to evade keyword filters
[A-02]. Note OWASP's LLM Top 10 is a practitioner consensus document, not a
peer-reviewed benchmark -- treat its claims as "proposed/consensus," not "measured."

A 2026 SoK, "SoK: The Attack Surface of Agentic AI -- Tools and Autonomy" (Dehghantanha
and Homayoun, arXiv 2603.22928, first submitted March 2026), attempts a comprehensive
taxonomy spanning prompt-level injection, knowledge-base/RAG poisoning, tool/plugin
exploits, and multi-agent/cross-agent manipulation, synthesizing more than 20 prior
studies [A-12]. This is useful as a vocabulary-alignment reference but is itself a
very recent secondary source (a survey of the primary literature), not a new empirical
measurement -- we should cite the primary benchmarks it summarizes wherever possible
rather than the survey alone.

---

## 2. Delivery mechanisms: instructions hidden from humans but legible to parsers

This is well documented and the concrete techniques are narrower than one might
expect. Consolidating across sources [A-03][A-04][A-02]:

- CSS-based hiding: text placed in the DOM with display:none, visibility:hidden,
  zero font-size, or moved off-screen (observed in the wild as e.g. left: -9999px
  positioning) [A-03]. The reason this works reliably: most agent ingestion pipelines
  strip script/style tags but pass the remaining DOM text through untouched, and the
  model is never shown the CSS, so a hidden div reads identically to visible body text
  once serialized to plain text or markdown [A-03].
- ARIA/accessibility-tree-only content: aria-label, alt attributes on images, and
  other accessibility metadata can carry instructions that an accessibility-tree-based
  agent will read even though nothing is rendered visually for a human [A-03][A-04].
- HTML comments, hidden form fields, data-* attributes, and other semantic-attribute
  abuse -- a 2025 paper on hidden-content injection strategies enumerates five concrete
  hiding techniques used in a systematic evaluation: HTML comments, data attributes,
  CSS-hidden text, hidden form fields, and semantic attribute abuse [A-03].
- Encoding/obfuscation combined with delayed execution: at least one observed
  real-world case used base64-encoded payloads decoded at runtime into off-screen DOM
  nodes, with a timing delay so the payload only appears after an initial safety scan
  has already passed -- deliberately exploiting time-bounded inspection pipelines [A-04].
- HTML accessibility-tree-targeted adversarial triggers: "Manipulating LLM Web Agents
  with Indirect Prompt Injection Attack via HTML Accessibility Tree" (arXiv 2507.14799,
  EMNLP 2025 System Demonstrations) goes further than hand-written hidden text: it uses
  the Greedy Coordinate Gradient (GCG) algorithm to generate universal adversarial
  triggers embedded in accessibility-tree elements, tested against a BrowserGym agent
  powered by Llama-3.1, and reports "high success rates across real websites" for both
  targeted attacks (e.g., forced ad clicks, credential theft) and general disruption --
  but the material we could access did not give an exact percentage or sample size, so
  treat the specific ASR number as unverified/thin even though the mechanism itself is
  credible and demonstrated with a public demo and MIT-licensed code [A-05].

Practical implication for our detector: because the actual palette of hiding
techniques is small and well-catalogued (CSS visibility properties, off-screen
positioning, zero-size, aria-*/alt text, HTML comments, hidden inputs, data
attributes), a rule-based DOM/AX-tree diff (what is in the accessibility tree /
extracted text vs. what a human would actually see rendered) is a defensible,
literature-grounded first detection rule -- this is explicitly the mechanism multiple
papers identify as the root cause, not a spectrum of infinite novel tricks.

---

## 3. Tool-call / function-call hijacking

InjecAgent (Zhan et al., arXiv 2403.02691, ACL Findings 2024) is the benchmark most
consistently cited for this exact attack: it constructs 1,054 test cases spanning 17
user-facing tools and 62 "attacker" tools, and defines an attack as successful when the
agent fully executes all steps of the injected (attacker) task [A-06]. Reported
numbers: ReAct-prompted GPT-4 was vulnerable 24% of the time under the base setting;
under an "enhanced" setting where the injected instruction is reinforced with an
explicit hacking-style prompt, susceptibility rose to 47% [A-06]. This is a concrete,
sample-sized, peer-reviewed (ACL Findings) number we can cite with confidence.

Agent Security Bench (ASB) (arXiv 2410.02644, ICLR 2025) is broader: 10 application
scenarios (e-commerce, autonomous driving, finance, etc.), 10 agent implementations,
over 400 tools, 27 attack/defense method variants, and 7 evaluation metrics, evaluated
across 13 LLM backbones [A-07]. It reports a highest average attack success rate of
84.30% for the strongest attack/target combination, while noting that the 11 defenses
it tested had "limited effectiveness" overall [A-07]. This is a substantially higher
number than InjecAgent's 24-47%, consistent with our overall finding that ASR is
extremely method- and metric-dependent -- ASB's headline number is a best-case (for
the attacker) figure across many scenarios, not a typical-case one.

Adaptive-attack robustness is a documented, recurring failure mode for defenses in this
exact space: "Adaptive Attacks Break Defenses Against Indirect Prompt Injection Attacks
on LLM Agents" (arXiv 2503.00061) is titled and abstracted around exactly this claim,
though we were unable to extract the full-text numeric details (the PDF did not parse
cleanly through our fetch tool) -- mark the specific "how many defenses, what ASR"
numbers as unverified even though the paper's existence and headline claim are
confirmed via its arXiv listing [A-08]. Separately, a search-engine-generated summary
described a related, higher-profile claim -- a joint red-team exercise across OpenAI,
Anthropic, and Google DeepMind that reportedly broke twelve published defenses, most
above 90% ASR -- but we could not independently locate and fetch a primary source for
this claim in the time available. This specific claim is NOT included in sources.json
and should not be cited without a direct primary source, even though it is consistent
with the adaptive-attack pattern seen in [A-08].

---

## 4. Goal hijacking and task drift in multi-step agent runs

"Get my drift? Catching LLM Task Drift with Activation Deltas" (arXiv 2406.00799)
defines task drift operationally as the LLM's deviation from the user's original
instruction(s) after processing external data that contains embedded natural-language
instructions [A-09]. Their detection approach reads internal activations (comparing
last-token activations before vs. after the model processes potentially-poisoned
external content) rather than reading the model's output text. Reported numbers: a
dataset of over 500,000 instances across train/validation/test; a linear probe on
activation deltas achieves ROC AUC greater than 0.99 on out-of-distribution test data,
which the authors report as outperforming two commercial/production filters they
compared against (Prompt Guard: 0.974 AUC; Prompt Shields: 0.988 AUC) on their test
set [A-09]. Caveat: this is the paper's own benchmark and own held-out set -- a
same-paper comparison against other tools on the authors' data should be read as
encouraging but not independently adjudicated; performance on genuinely held-out,
adversarially-adapted red-team data was not established by what we could verify.

More recent, narrower work targets this exact multi-step phenomenon on web agents
specifically: "WebTrap: Stealthy Mid-Task Hijacking of Browser Agents During
Navigation" (arXiv 2605.08310) and "AgentDrift: A Step-Labeled Benchmark of
Injection-Hijacked LLM Agent Trajectories" (arXiv 2609.06972) both appeared in search
results as dedicated benchmarks/datasets for detecting where in a multi-step
trajectory an injection took hold and diverted the agent. We surfaced these via search
but did not fetch and verify their content in depth (not fetched, not in sources.json);
they are flagged here as promising leads for a follow-up pass rather than cited claims.

---

## 5. WASP: the clearest evidence for the partial-vs-full-hijack distinction

"WASP: Benchmarking Web Agent Security Against Prompt Injection Attacks" (arXiv
2504.18575, NeurIPS 2025 poster) is the single most load-bearing benchmark for our
threat model, because it evaluates end-to-end web-browsing agents rather than isolated
tool calls, and explicitly separates two metrics: ASR-intermediate (did the agent
start following the injected instruction / get diverted from the user's goal at all)
and ASR-end-to-end (did the attacker's full multi-step goal actually get completed)
[A-10]. Reported ranges: agents begin executing the adversarial instruction
(ASR-intermediate) between 16% and 86% of the time depending on agent and scenario,
but achieve the attacker's full goal (ASR-end-to-end) only between 0% and 17% of the
time [A-10]. The authors characterize this gap as agents being saved largely by their
own general incompetence at completing multi-step tasks, not by any security property
-- a framing worth stating plainly to stakeholders since it is an optimistic-sounding
number (single-digit percent) hiding a much larger underlying hijack rate. This is the
strongest, most directly citable evidence that "attack success rate" must always be
reported with its exact definition attached -- a defense proxy or a headline number
without specifying intermediate-vs-end-to-end is likely being cherry-picked, favorably
or unfavorably, by whoever is quoting it.

Other web-agent-specific benchmarks in the same family surfaced but not deeply
verified: WAInjectBench (arXiv 2510.01354, benchmarking prompt-injection detectors for
web agents specifically), AdInject (arXiv 2505.21499, black-box attacks via real-world
ad content injected into pages), and Prismata (arXiv 2607.08147, a proposed
containment/confinement defense for cross-site prompt injection in web agents). These
are named here as leads; we did not fetch full text for them and their numeric claims
are not in sources.json and should be independently verified before citing.

---

## 6. Attacks specific to how agents perceive pages (DOM vs. AX-tree vs. screenshot/VLM)

The literature does not yet contain, as far as we found, a single controlled study
that holds the attack constant and varies only the perception modality (DOM-text vs.
accessibility-tree vs. screenshot) to directly compare susceptibility -- this is a gap.
What exists instead is separate attack literatures per modality that, taken together,
imply the following differences:

- DOM/text-based agents (the agent reads raw or lightly-cleaned HTML/markdown):
  vulnerable to any hidden-but-parsed DOM content -- CSS-hidden divs, comments, hidden
  inputs -- because these pipelines typically only strip script/style tags and pass
  the rest of the text through [A-03].
- Accessibility-tree-based agents (agent acts on the AX tree the OS/browser exposes, as
  used by many "computer use" and browser-automation agents): vulnerable to
  aria-label/alt/role-based content that has no visual rendering at all, and is the
  specific target of the GCG-optimized adversarial-trigger attack in [A-05], which was
  built and tested specifically against an accessibility-tree-driven BrowserGym agent.
- Screenshot/VLM-based agents (agent reasons over a rendered image of the page):
  immune to pure-CSS hiding (a display:none div renders nothing, so it is invisible in
  a screenshot too) but newly vulnerable to typographic/image-embedded text injection
  -- instructions rendered as pixels, exploiting the same OCR-like text-reading
  capability that lets a VLM read a page at all. "Reading Between the Pixels: Linking
  Text-Image Embedding Alignment to Typographic Attack Success on Vision-Language
  Models" (arXiv 2604.12371) empirically tested this across four VLMs including GPT-4o
  and Claude, twelve font sizes, and ten image transformations, finding that
  multimodal (text-image) embedding distance strongly predicts attack success, and
  that rendering conditions alone (font size, blur) can swing attack success by "tens
  of percentage points" [A-11]. A closely related paper, "One Perturbation, Two
  Failure Modes: Probing VLM Safety via Embedding-Guided Typographic Perturbations"
  (arXiv 2604.25102), covers the same general attack class but we did not fetch its
  full text; its specific numbers are not in sources.json and should be treated as
  unverified.

Practical implication: our MCP proxy's detection strategy should differ by which
perception path the agent uses. A proxy that only screens the DOM/AX-tree text will
miss image-embedded typographic injection aimed at a VLM/screenshot agent, and a proxy
that only screens rendered pixels/OCR will miss ARIA-only or CSS-hidden DOM content
aimed at a DOM/AX-tree agent. If we do not know which perception modality the
downstream agent uses, we likely need to screen both channels.

---

## 7. Where the evidence is thin, contradictory, or toy-only

- Exact ASR numbers vary by 3-4x across benchmarks measuring "the same" attack
  (InjecAgent's 24-47% vs. ASB's up to 84.30% vs. WASP's 16-86% intermediate / 0-17%
  end-to-end) [A-06][A-07][A-10]. This is not a contradiction to resolve by picking a
  winner -- it reflects genuinely different threat models, tool sets, and success
  definitions. Any number we quote publicly must carry its benchmark name and exact
  metric definition attached.
- Several claims found only in search-engine-summarized form (the "OpenAI/Anthropic/
  DeepMind broke twelve defenses" claim; specific numeric details of arXiv 2503.00061)
  could not be verified against a primary source we could actually open in this
  session. These are explicitly excluded from sources.json (or marked unverified) and
  should be treated as leads for a follow-up fetch, not citable facts.
- Most attack-surface "taxonomies" we found (the layered-attack-surface survey, the SoK
  on agentic AI) are themselves from 2026, i.e., very recent secondary literature
  synthesizing a field that is only about two to three years old. There is not yet a
  single widely-adopted standard taxonomy the way, say, STRIDE is for classical threat
  modeling -- OWASP's Top 10 for LLM Applications is the closest thing to an
  industry-consensus vocabulary, but it is a practitioner document, not a
  peer-reviewed empirical taxonomy.
- A specific, exact attack-success-rate figure for the GCG-optimized accessibility-tree
  attack [A-05] was not obtainable from the material available to us -- the paper's
  existence, mechanism, and public demo/code are confirmed, but the quantitative claim
  is not, and should be re-verified from the full PDF before use in a formal report.
- We did not find dedicated, controlled comparisons of attack success by agent
  perception modality holding the attack fixed (see Section 6) -- this is a real gap
  in the literature, not just a gap in our search.
- All arXiv IDs above were found via live web search in September 2026 and
  cross-checked against at least one arXiv-hosted URL; several (2604.x, 2605.x,
  2608.x, 2609.x range) are 2026 preprints that postdate this model's training
  cutoff, so they could not be checked against prior knowledge -- only against what
  WebFetch and WebSearch actually returned this session.
