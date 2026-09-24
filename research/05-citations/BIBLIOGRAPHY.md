# Canonical Bibliography — Adversarial Web Content vs. Autonomous Agents

Compiled independently by the citations agent per BRIEF.md. Every entry below was
fetched directly (arXiv abstract page, ACM DL / Semantic Scholar search results, or
the issuing agency's own site) on 2026-09-24. Citation counts are approximate,
snapshot counts from Semantic Scholar (via search-result rendering, not a raw API
pull — API access returned HTTP 429 throughout this session; treat counts as
directionally correct, not exact). Grouped by theme, most important first within
each group.

---

## 1. Prompt injection — agent-targeted attacks (seminal → recent)

### [B-01] Greshake et al., "Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection"
- Authors: Kai Greshake, Sahar Abdelnabi, Shailesh Mishra, Christoph Endres, Thorsten Holz, Mario Fritz
- Venue: ACM Workshop on Artificial Intelligence and Security (AISec) 2023; arXiv:2302.12173 (submitted Feb 2023, revised May 2023)
- Why it matters: Coined and formalized **indirect prompt injection** — the term the entire field now uses — and demonstrated it against real deployed systems (Bing Chat/GPT-4, code-completion engines). The taxonomy (data theft, worming, ecosystem contamination) is the reference taxonomy this project's brief explicitly follows.
- Citation count: ~761 (Semantic Scholar, checked 2026-09-24 via web search rendering of S2 page)
- Category: **seminal**

### [B-02] Perez & Ribeiro, "Ignore Previous Prompt: Attack Techniques For Language Models"
- Authors: Fábio Perez, Ian Ribeiro
- Venue: NeurIPS 2022 ML Safety Workshop; arXiv:2211.09527 (Nov 2022)
- Why it matters: Earliest widely-cited formal study of **direct** prompt injection (goal hijacking, prompt leaking) against GPT-3, predates and sets vocabulary for "ignore previous instructions" style attacks. The PromptInject framework is a common baseline.
- Citation count: unverified exact figure this session (S2 lookup rate-limited); widely cited as a founding prompt-injection paper — flagged for follow-up count check.
- Category: **seminal**

### [B-03] Liu et al., "Prompt Injection attack against LLM-integrated Applications"
- Authors: Yi Liu, Gelei Deng, Yuekang Li, Kailong Wang, Zihao Wang, Xiaofeng Wang, Tianwei Zhang, Yepang Liu, Haoyu Wang, Yan Zheng, Leo Yu Zhang, Yang Liu
- Venue: arXiv:2306.05499 (v1 June 2023; last revised Dec 2025)
- Why it matters: Introduces HouYi, a black-box prompt-injection methodology tested against 36 real production LLM apps (31 vulnerable), with vendor-confirmed impact (10 vendors incl. Notion). Good source for real-world attack-success numbers.
- Category: **recent-preprint** (long-running, actively revised)

### [B-04] Zou et al., "Universal and Transferable Adversarial Attacks on Aligned Language Models"
- Authors: Andy Zou, Zifan Wang, Nicholas Carlini, Milad Nasr, J. Zico Kolter, Matt Fredrikson
- Venue: arXiv:2307.15043 (July 2023, revised Dec 2023)
- Why it matters: The GCG suffix attack — automated, gradient-based, and transfers across GPT/Claude/Bard/open models. Not agent-specific but foundational to any discussion of automated/transferable adversarial content against LLMs, including content that could be embedded in a page.
- Citation count: ~2,230 (Semantic Scholar, checked 2026-09-24)
- Category: **seminal**

### [B-05] Debenedetti et al., "AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents"
- Authors: Edoardo Debenedetti, Jie Zhang, Mislav Balunović, Luca Beurer-Kellner, Marc Fischer, Florian Tramèr
- Venue: NeurIPS 2024 Datasets & Benchmarks track; arXiv:2406.13352 (June 2024, revised Nov 2024)
- Why it matters: The reference **benchmark** for prompt injection against tool-using agents — 97 realistic tasks, 629 security test cases, extensible attack/defense harness. Directly relevant to "what should the MCP proxy detect."
- Category: **survey/benchmark**

### [B-06] Zhan et al., "InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents"
- Authors: Qiusi Zhan, Zhixiang Liang, Zifan Ying, Daniel Kang
- Venue: ACL Findings 2024; arXiv:2403.02691 (March 2024, revised Aug 2024)
- Why it matters: 1,054 test cases across 17 user tools / 62 attacker tools, 30 agents evaluated. Concrete numbers: ReAct-prompted GPT-4 compromised 24% of the time, roughly doubling with an explicit "hacking prompt" enhancement.
- Category: **benchmark**

### [B-07] Zhang, Yu & Yang, "Attacking Vision-Language Computer Agents via Pop-ups"
- Authors: Yanzhe Zhang, Tao Yu, Diyi Yang
- Venue: ACL 2025 (main); arXiv:2411.02391 (Nov 2024)
- Why it matters: Directly on-topic for a **browsing** agent (not just tool-calling): adversarial pop-ups that a human would dismiss but a VLM agent clicks. ASR >80% on OSWorld, >60% on VisualWebArena; naive defenses ("ignore pop-ups" instructions) fail. Strong evidence for the brief's claim that agents lack visual skepticism.
- Category: **recent-preprint** (peer-reviewed at ACL 2025)

### [B-08] Zeng et al. / WebArena team, "WebArena: A Realistic Web Environment for Building Autonomous Agents"
- Venue: ICLR 2024; arXiv:2307.13854 (July 2023)
- Why it matters: The standard realistic web-agent benchmark (four functional site domains, 812 tasks). Not a security paper itself, but the environment most agent-attack papers (including B-07-adjacent work) build on; establishes baseline agent competence (GPT-4 agent ~14% success vs. 78% human) against which attack success rates should be read.
- Category: **survey/benchmark**

---

## 2. Dark patterns / deceptive design (mature HCI field — order by foundational status)

### [B-09] Gray, Kou, Battles, Hoggatt & Toombs, "The Dark (Patterns) Side of UX Design"
- Venue: ACM CHI 2018; DOI 10.1145/3173574.3174108
- Why it matters: One of the two papers that formalized "dark patterns" as an academic HCI category (alongside Brignull's original practitioner coinage) and produced the widely reused taxonomy (nagging, obstruction, sneaking, interface interference, forced action) built from 118 practitioner-identified examples.
- Citation count: ~899 (Semantic Scholar, checked 2026-09-24)
- Category: **seminal**

### [B-10] Mathur, Acar, Friedman, Lucherini, Mayer, Chetty & Narayanan, "Dark Patterns at Scale: Findings from a Crawl of 11K Shopping Websites"
- Venue: ACM CSCW 2019 (Proc. ACM Hum.-Comput. Interact. Vol 3); DOI 10.1145/3359183; arXiv:1907.07032
- Why it matters: The prevalence-measurement landmark — automated crawl of ~53K product pages across ~11K sites, 1,818 dark-pattern instances across 15 types / 7 categories. This is the paper to cite for "how common is this" with a real denominator.
- Citation count: ~444 (Semantic Scholar, checked 2026-09-24)
- Category: **seminal**

### [B-11] Di Geronimo, Braz, Fregnan, Palomba & Bacchelli, "UI Dark Patterns and Where to Find Them: A Study on Mobile Applications and User Perception"
- Venue: ACM CHI 2020; DOI 10.1145/3313831.3376600
- Why it matters: Mobile-app analogue to Mathur et al. — 240 apps, 95% contained at least one dark pattern, average 7 types per popular app — plus a 584-respondent user study showing most dark patterns go unnoticed by human users. Directly supports the brief's claim that dark patterns are effective on humans and worth testing on agents.
- Category: **survey/measurement**

### [B-12] FTC Bureau of Consumer Protection Staff Report, "Bringing Dark Patterns to Light"
- Publisher: U.S. Federal Trade Commission, September 2022
- URL: https://www.ftc.gov/reports/bringing-dark-patterns-light (PDF: https://www.ftc.gov/system/files/ftc_gov/pdf/P214800+Dark+Patterns+Report+9.14.2022+-+FINAL.pdf)
- Why it matters: Authoritative U.S. regulatory framing — ties dark patterns to actual legal exposure (FTC Act Section 5) across e-commerce, cookie consent, children's apps, and subscription cancellation ("negative option") flows. This is the citation to use when arguing a detection needs to matter beyond academia.
- Category: **regulatory**

### [B-13] OWASP Top 10 for LLM Applications 2025 — LLM01: Prompt Injection
- Publisher: OWASP GenAI Security Project, 2025
- URL: https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf
- Why it matters: Industry-standard vulnerability ranking; prompt injection is #1 for the second consecutive edition. Distinguishes direct vs. indirect injection and recommends defense-in-depth (input/output filtering, privilege restriction, human-in-the-loop, segregating untrusted external content) — directly actionable for the MCP-proxy design goal.
- Category: **regulatory/industry-standard**

### [B-14] NIST AI 100-2e2025, "Adversarial Machine Learning: A Taxonomy and Terminology of Attacks and Mitigations"
- Publisher: National Institute of Standards and Technology, March 2025
- URL: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-2e2025.pdf
- Why it matters: The U.S. government reference taxonomy; the 2025 edition explicitly extends coverage to generative-AI supply-chain attacks, direct/indirect prompt injection, and **security of AI agents** as a named category, with 400+ literature references. Useful as a neutral umbrella citation tying our two attack families (agent-targeted, human-targeted-that-transfers) into one recognized framework.
- Category: **regulatory/standard**

---

## Notes and gaps

- Citation counts were obtained largely via WebSearch-rendered Semantic Scholar pages rather than the raw Semantic Scholar API, which returned HTTP 429 (rate-limited) throughout this session for direct WebFetch calls. Two entries (B-02, B-03) are missing a verified count and are flagged rather than guessed.
- European Commission dark-pattern guidance (under the Digital Services Act / UCPD) was identified as a relevant regulatory category but not yet independently fetched and verified — deliberately omitted rather than filled in with an unverified citation. Will add if verified in a later pass.
- This bibliography will be cross-referenced against the four workstream sources.json files as they appear; overlaps will be noted in VERIFICATION.md rather than duplicated here.
