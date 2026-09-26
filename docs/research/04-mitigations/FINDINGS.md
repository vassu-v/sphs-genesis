# Mitigations against agent-targeted and human-targeted web attacks — literature findings

## Summary (read this first)

1. No defence in the literature is close to solved. Every measured defence we found reduces attack success rate (ASR) without eliminating it, and every measured defence trades off against task utility, false positives, or is itself bypassed in the same paper or a follow-up. [M-01][M-02][M-08]
2. Deterministic/structural detection is real, published, and works well specifically for the narrow class of attacks it targets (hidden/invisible text, overlay/hit-testing mismatches) — but the published structural work is almost entirely about hidden text in documents, not general UI deception on the live web. We found essentially no peer-reviewed, benchmarked paper doing pixel/DOM/computed-style structural detection of deceptive web UI (fake buttons, overlay hijacking, clickjacking) specifically for agents. The adjacent literature (dark-pattern detection, clickjacking detection) is mature for humans but has not been re-validated against agent-driven interaction in a measured way that we could find. This is the biggest gap between our plan and what is published — treat our structural-detection core as plausible and partially precedented, not proven. [M-05][M-06][P-01]
3. LLM-based guards inspecting untrusted content can themselves be attacked through that content. This is directly demonstrated, not merely theorized: guardrail evasion attacks achieve up to 100% bypass on commercial systems (Azure Prompt Shield, Meta Prompt Guard) [M-03]; optimization-based attacks on LLM-as-a-Judge succeed at high rates and defeat perplexity-based defenses [M-04]; a separate paper shows a simpler injected-suffix attack on judge LLMs exceeding 30% ASR [M-09]. This directly supports keeping any LLM component advisory only, never the sole/final gate — the literature agrees with our design thesis on this specific point.
4. Architectural isolation (dual-LLM / capability-based control-flow separation) is the most rigorous defence measured so far, and even it does not fully close the gap. Google's CaMeL reduces the attack surface by construction (untrusted data structurally cannot alter control flow) but only preserves task success on 77% of AgentDojo tasks vs. 84% undefended — an 8-point utility cost even in the best published architectural defence. [M-07][P-02]
5. A rigorous 2025 re-evaluation found that published prompt-injection defences perform worse than their own papers claim once tested against adaptive attackers and utility-preserving criteria simultaneously — this is an important corrective to the whole field and to us: don't trust a defence's headline number without checking if it was evaluated adaptively. [M-08]
6. Dark-pattern / deceptive-UI prevalence is a mature, well-measured HCI field for human targets (thousands of sites crawled, taxonomies validated), but there is very little work asking whether these same measured dark patterns transfer to, or are specifically exploited against, autonomous agents. That transfer is assumed by us and by some 2025 agent-security papers, but not yet measured at scale. [M-10]

---

## 1. Defences against indirect prompt injection

### 1.1 Spotlighting / delimiting / datamarking (measured)
Hines et al. (Microsoft, 2024) propose spotlighting: transforming untrusted input (e.g., encoding it, marking it, or replacing whitespace with a warning token) so the model has a reliable provenance signal distinguishing instructions from data. Measured on GPT-family models: attack success rate falls from >50% to below 2%, with the authors reporting "minimal detrimental impact" on the underlying task. [M-01]

- What it was evaluated against: indirect prompt injection payloads embedded in third-party data fed to GPT-family models.
- Limitation stated by the authors: the core problem being patched is that LLMs otherwise cannot distinguish which prompt segments come from which source — spotlighting is a mitigation for a structural gap in the model, not a proof of unbreakability, and it depends on the model correctly interpreting the marking convention (an LLM-side, not deterministic, guarantee).
- Implementable in a weekend: Yes — prompt engineering (delimiters, marking conventions), applicable directly to any proxy that assembles page content into a prompt. No training required.

### 1.2 Instruction hierarchy training (OpenAI; measured, partial)
OpenAI's instruction-hierarchy work trains models to prioritize system/user instructions over third-party/tool content. Reported effect: roughly 10-63% reduction in attack success depending on the benchmark, deployed in GPT-4o-mini. Independent commentary echoed in the critical-evaluation literature notes it reduces but does not eliminate vulnerability, and combined/adaptive attacks still achieve high ASR against it. Treat exact OpenAI numbers as vendor-reported rather than third-party peer-reviewed.
- Implementable in a weekend: No — requires model (re)training/fine-tuning; only usable by consuming a vendor's already-trained model, not something we can add to a proxy ourselves.

### 1.3 Dual-LLM / quarantined-LLM pattern (proposed, partially measured via CaMeL)
Willison's dual-LLM pattern separates a privileged LLM (has tool access, sees only the trusted user query) from a quarantined LLM (sees untrusted content, has no tool access, and can only return opaque references like $email-summary-1 back to the privileged LLM, never raw content). This pattern itself is a design proposal, not independently benchmarked in isolation — its only rigorous, measured instantiation we found is CaMeL (below). [P-02]

### 1.4 CaMeL — capability-based control/data-flow separation (measured)
Debenedetti et al. (Google DeepMind/Google, 2025), "Defeating Prompt Injections by Design." CaMeL implements the dual-LLM pattern plus a capability system: it explicitly extracts control flow and data flow from the trusted query so that untrusted retrieved data can never influence program/control flow, and enforces security policies on data flows at tool-call time (traditional information-flow-control ideas applied to agents). [M-07]
- Measured result on AgentDojo: CaMeL achieves provable security on 77% of tasks, versus an 84% task-success rate for the undefended baseline — a real but bounded utility cost (~8 points) in exchange for structural (not merely statistical) protection against control-flow hijack via untrusted data.
- Limitation: requires restructuring the agent's execution model around an explicit planner/interpreter and capability system — real engineering work, not a prompt tweak, and not addable to an off-the-shelf agent from outside its architecture inside a weekend.
- Implementable in a weekend: Partially — the capability check at tool-call time idea (a policy engine gating tool calls, see Section 2) is exactly the shape of what an MCP proxy can do without owning the agent's planner; the full control/data-flow separation is not achievable from outside the agent.

### 1.5 Human-in-the-loop gating (widely recommended, OWASP; not independently benchmarked as a standalone number)
OWASP's LLM Top 10 guidance and multiple vendor writeups converge on: require human approval for high-risk/irreversible actions, combined with least-privilege tooling and input/output filtering, as "defense in depth." [M-12] This is consistently recommended but we found no controlled study measuring what fraction of attacks a human-approval gate actually stops in practice.
- Implementable in a weekend: Yes — trivially, as a proxy-level confirmation prompt on flagged actions. Cheap, but its real-world effectiveness against habituation is unmeasured for this specific use case.

---

## 2. Architectural defences

- Least-privilege tool access / capability restriction / action allowlists: recommended across OWASP guidance and the CaMeL/Design-Patterns papers as the highest-leverage mitigation for impact (as opposed to detection) — restrict what the agent can do regardless of whether an injection succeeds. [M-07][M-11][M-12]
- "Design Patterns for Securing LLM Agents against Prompt Injections" (Beurer-Kellner, Debenedetti, Tramer et al., 2025) catalogs five patterns: Dual LLM, Plan-Then-Execute, Action-Selector (an intermediary validates/filters proposed actions before execution), Map-Reduce (compartmentalized processing), and Dual LLM with Quarantine. These are explicitly presented as architectural recommendations, not empirically validated solutions — the authors state directly that deterministic defenses (input filtering, syntactic constraints) are more predictable but brittle, while LLM-based defenses are more flexible but introduce new uncertainty, and that no single pattern universally prevents sophisticated injection and most proposals still partially rely on the very systems (LLMs) they are trying to defend. [P-01]
  - The Action-Selector and Plan-Then-Execute patterns are the most directly relevant to an MCP proxy design: an external, non-LLM component validating/filtering proposed tool calls before they execute is exactly a policy-engine-over-tool-calls architecture. This is proposed, not benchmarked, in this paper.
- Policy engines over tool calls / confirmation gates on irreversible actions: consistently recommended (OWASP, Design Patterns paper) as the most implementable, lowest-risk mitigation. No paper we found benchmarks a specific policy-engine implementation's catch rate — it is treated as an architectural best practice, not a measured detector.
- Implementable in a weekend: action allowlisting, a policy engine gating tool calls, and confirmation gates are all realistically buildable by two people in a weekend, since they require no model training — they are the most implementable items in this entire review.

---

## 3. Deterministic / structural detection (our intended core) — what the literature actually supports

This is the most important section for our design decision, so we report it plainly.

What is supported:
- Hidden-text detection in structured documents is a published, principled, deterministic technique. PhantomLint (Murray, 2025) detects concealed LLM instructions in structured documents (primarily PDFs) using purely structural/deterministic signals: CSS-hiding abuse (display:none, opacity:0), zero/near-zero font size, text-color-matches-background, zero-width Unicode characters, and content layered behind visible elements. [M-05] The paper explicitly frames this as principled deterministic detection, not machine learning, and states the limitation any structural detector will have: legitimate documents sometimes use small fonts or layering for real design reasons (false-positive risk), and sophisticated obfuscation may evade specific rules (evasion risk). We could not extract exact precision/recall numbers from the available text via automated fetch — flagged as a gap; the qualitative mechanism and stated limitations are confirmed, the quantitative results are not (mark low confidence on numbers, higher confidence on mechanism).
- The general technique of scanning for CSS/DOM-based text-hiding (opacity, font-size, off-screen positioning, display:none, zero-width characters) as a deterministic pre-filter is corroborated by grey-literature/industry write-ups (Palo Alto Unit 42, promptfoo, and open-source tools such as promptinjectionradar) describing exactly this approach for web content, though these are not peer-reviewed sources and should be weighted lower than PhantomLint. [P-03 — unverified/grey literature, included for completeness only]
- Overlay/hit-testing mismatches are a recognized attack surface with at least one concrete demonstrated instance on mobile agents: a 2025 paper on mobile LLM agent security describes attacks using FLAG_NOT_FOCUSABLE overlay windows and transparent overlays that are fully visible to an agent's screen capture/OCR pipeline while being deliberately excluded from the interactive view hierarchy — exactly the "geometry says visible/clickable, structure says something else" mismatch our design targets. We could not fully extract this paper's text via automated fetch (PDF binary parsing failed) and could not confirm whether they measured or merely demonstrated this, so this claim is marked low-confidence/partially unverified. [P-04 — partially unverified]
- Hit-testing as a defence against classic clickjacking/UI-redressing (checking whether the element a human/agent perceives as clickable is the element that will actually receive the click, and flagging overlapping elements with pointer-events: none disabled) is described in web-security literature but is a pre-LLM, pre-agent technique (2010s-era clickjacking research) that has not, as far as we found, been re-validated specifically for agent action-safety in a measured paper. [P-05 — general web-security background, not agent-specific, not independently re-verified for this review]

What is NOT supported, or is a real gap:
- We found no peer-reviewed or arXiv paper that measures a deterministic/structural detector against realistic deceptive web UI (fake close buttons, disguised links, drip-pricing overlays, obstructed cancel flows) specifically in the context of an autonomous browsing agent. The closest adjacent work — Mathur et al.'s "Dark Patterns at Scale" (CSCW 2019) — is rigorous and large-scale (11,000 shopping sites, 1,818 dark-pattern instances across 15 types) [M-10], and later work builds ML classifiers over DOM structure for dark-pattern detection generally, but this body of work targets protecting human shoppers, was not evaluated against agent action pipelines, and (per our search) has not been extended in a measured way to ask "does this detector stop an agent from clicking the deceptive element." This is a genuine, citable gap, not an oversight on our part — treat any claim that "structural dark-pattern detection transfers directly to agent protection" as unproven, an assumption we would be making, not a result we can cite.
- The single strongest and most explicit statement on this general tension comes from the Design Patterns paper itself: deterministic defenses are "predictable but brittle," LLM-based ones are "flexible but introduce new uncertainty," and no pattern of either kind fully prevents sophisticated attacks. [P-01] The literature does not say structural/deterministic detection is sufficient on its own; it says it's one necessary layer, most validated so far for the narrow "hidden text" sub-problem, not for general deceptive-UI detection.

Honest bottom line for our design: the deterministic/structural core is well-precedented for hidden-content detection (strong, published, matches our thesis) and plausible-but-unvalidated for general deceptive-UI detection on the live web against agents specifically (no benchmark exists yet — we would be the first to measure it, which is a legitimate contribution, but we cannot claim the literature already proves it works).

---

## 4. Model-based detection: classifiers and LLM judges

- Fine-tuned classifiers (e.g., ProtectAI's DeBERTa-v3-based "PI Detector") measured in a 2025 critical re-evaluation: achieved only 7.95% ASR on AgentDojo (stopped most attacks) but caused severe utility collapse — task success dropped from 83.02% (baseline) to 41.49% — when the detector was in the loop, because it also blocked large amounts of legitimate content. [M-08] This is a clean, quantified illustration of the detection/utility trade-off our design must budget for.
- The same paper's own proposed "Sanitizer" defense was bypassed by the authors themselves using Braille encoding of the injected instructions — GPT-4o correctly decoded the Braille and followed the hidden instruction even though the sanitizer had flagged the content as dangerous, because rare-token encodings broke the sanitizer's removal step even after detection succeeded. [M-08] This is a directly relevant, measured example of detection succeeding but the mitigation still failing.
- Benchmark validity itself is contested: the same paper shows that a widely used benchmark's forced-tool-injection design artificially inflates measured attack success rates (from a padded ~70% down to ~9.25% once the artifact is corrected), meaning published defense-effectiveness numbers across the field may not be comparable to each other unless the underlying benchmark methodology is checked. [M-08]
- Guardrail evasion (measured, high severity for our design): Hackett et al. (2025) empirically bypass six prominent LLM guardrail/detection systems — including Microsoft Azure Prompt Shield and Meta Prompt Guard — using character-injection tricks and adversarial-ML evasion methods, achieving up to 100% evasion success in some instances, and show black-box attacks can be strengthened using word-importance rankings computed from offline white-box models. [M-03] This is one of the most important sources for our thesis: commercial, deployed LLM-based guardrails are demonstrably and severely bypassable via crafted input content.

---

## 5. Security of the guard itself — can a defensive LLM be prompt-injected through the content it inspects?

Yes — this is demonstrated, not merely hypothesized, in multiple independent papers. This directly underwrites our design thesis that an LLM must stay advisory, not the sole gate.

- JudgeDeceiver (Shi, Yuan, Liu, Huang, Zhou, Sun, Gong — 2024): an optimization-based (gradient-driven) prompt injection attack that embeds a crafted sequence inside an attacker-controlled candidate response so that an LLM-as-a-Judge selects that response regardless of competing options. The authors report the attack is "much more effective than existing prompt injection attacks," and critically, tested three defenses — known-answer detection, perplexity detection, and windowed-perplexity detection — and found all three inadequate. [M-04]
- Comparative Undermining Attack / Justification Manipulation Attack (Maloyan, Ashinov, Namiot, 2025): two formalized attack strategies against LLM-as-a-Judge, one targeting the final verdict directly, one targeting the reasoning trace. The Comparative Undermining Attack achieved an ASR exceeding 30% against instruction-tuned judge models (Qwen2.5-3B-Instruct, Falcon3-3B-Instruct) on the MT-Bench Human Judgments dataset. [M-09]
- Generalization to our proxy design: these are LLM-as-judge papers (evaluating candidate text), not literally "LLM inspects a webpage for an agent," but the mechanism is identical in kind — an LLM asked to evaluate/gate untrusted content is exposed to that same content and can be steered by it. Combined with the guardrail-evasion result above (up to 100% bypass of deployed commercial guardrails) [M-03], the literature gives strong, convergent, measured support to the position that an LLM-based guard is not a safe sole line of defense against the exact content it is inspecting.

---

## 6. What's realistically buildable in a two-person weekend vs. not

Feasible without training or heavy infra (buildable this weekend):
- Spotlighting / delimiting / provenance-marking of untrusted content before it reaches any LLM step [M-01]
- Deterministic hidden-text scanning (CSS/opacity/font-size/zero-width-Unicode/color-contrast checks) modeled on PhantomLint's approach [M-05]
- Action allowlists, least-privilege tool scoping, and a policy engine gating tool calls before execution (Action-Selector pattern) [P-01]
- Confirmation/human-in-the-loop gates on irreversible actions [M-12]
- Using an LLM strictly in an advisory role (flag-only, never auto-execute or auto-block) given the demonstrated guard-injection risk [M-03][M-04][M-09]

Not feasible this weekend (needs training, large infra, or agent-architecture ownership):
- Instruction-hierarchy-style model fine-tuning (OpenAI's approach, vendor-only)
- Full CaMeL-style capability/control-flow separation, which requires owning the agent's planner/interpreter rather than sitting as an external proxy [M-07]
- Training a bespoke classifier for deceptive-UI or injection detection, and validating it against adaptive attackers the way the critical-evaluation paper insists is necessary [M-08]
- Large-scale benchmark construction (WASP-style isolated environments, thousands-of-sites crawls) to actually measure our own detector's precision/recall the way the field expects

---

## Additional measured data point: WASP benchmark (agent hijacking success rates)

Evtimov, Zharmagambetov, Grattafiori, Guo, Chaudhuri (Meta, 2025), "WASP: Benchmarking Web Agent Security Against Prompt Injection Attacks." Introduces a realistic, isolated web-agent-hijacking benchmark (VisualWebArena, Claude Computer Use, and other agentic systems with state-of-the-art models). Reports two metrics per model: intermediate ASR (agent begins executing the injected instruction) ranging 16-86% across tested systems/models, and end-to-end ASR (attacker's actual goal achieved) ranging 0-17%. [M-02] Conclusion stated by authors: even agents built on models with advanced reasoning and instruction-hierarchy mitigations remain susceptible to low-effort, human-written injections at the intermediate-hijack level, though the gap between intermediate and end-to-end success shows agents often lack the follow-through capability to complete complex attacker objectives — a form of accidental partial protection, not a designed defence.
