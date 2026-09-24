# Verification Log

**No fabricated citations found across any pass, including the adversarial
priority re-check of the two load-bearing papers below.** Nothing in this
document rises to FABRICATED. One URL/DOI mismatch (DP-09) remains open from
the first pass — still unfixed as of the second pass — flagged again below.

---

## SECOND PASS (coordinator-requested, priority re-verification)

### PRIORITY 1 — the two load-bearing papers, verified to the highest standard requested

#### DECEPTICON — arXiv:2512.22894

- **arXiv ID resolves:** yes, confirmed live.
- **Title/authors match:** "DECEPTICON: How Dark Patterns Manipulate Web Agents" — Phil Cuvin, Hao Zhu, Diyi Yang. Matches `02-dark-patterns/sources.json` DP-10 exactly.
- **Numbers — verbatim abstract text obtained and checked claim-by-claim:**
  > "dark patterns successfully steer agent trajectories towards malicious outcomes in over 70% of tested generated and real-world tasks -- compared to a human average of 31%. Moreover, we find that dark pattern effectiveness correlates positively with model size and test-time reasoning, making larger, more capable models more susceptible. Leading countermeasures against adversarial attacks, including in-context prompting and guardrail models, fail to consistently reduce the success rate of dark pattern interventions."
  - >70% vs 31% human baseline: **CONFIRMED VERBATIM**, not a paraphrase or inflation.
  - Susceptibility increases with model size/test-time reasoning: **CONFIRMED VERBATIM**.
  - Prompting/guardrail defenses fail to consistently help: **CONFIRMED VERBATIM**.
  - No overstatement detected — the claim as recorded in DP-10 matches the abstract almost word-for-word.
- **Venue claim:** DP-10 correctly records this as an **arXiv preprint**, no conference/journal claimed. Confirmed independently: the arXiv page carries no journal-ref and is filed only under cs.CR/cs.AI. **This is the correct, non-inflated treatment — the workstream agent did not claim peer review for a preprint.**
- **Verdict: VERIFIED to the highest standard.** Exists, matches, says exactly what is claimed, venue not overstated.

#### Ersoy et al. — arXiv:2510.18113, claimed venue IEEE S&P 2026

- **arXiv ID resolves:** yes, confirmed live (checked v2 as well).
- **Title/authors match:** "Investigating the Impact of Dark Patterns on LLM-Based Web Agents" — Devin Ersoy, Brandon Lee, Ananth Shreekumar, Arjun Arunasalam, Muhammad Ibrahim, Antonio Bianchi, Z. Berkay Celik. Matches DP-11 exactly.
- **Numbers — verbatim abstract text obtained:**
  > "We evaluate six popular LLM-based generalist web agents across three LLMs and discover that when there is a single dark pattern present, agents are susceptible to it an average of 41% of the time. We also find that modifying dark pattern UI attributes through visual design changes or HTML code adjustments and introducing multiple dark patterns simultaneously can influence agent susceptibility."
  - 41% average single-dark-pattern susceptibility: **CONFIRMED VERBATIM**.
  - Both visual-design and HTML/DOM-level changes independently affect susceptibility: **CONFIRMED VERBATIM** ("visual design changes or HTML code adjustments... can influence agent susceptibility").
  - No overstatement detected.
- **Venue claim — checked adversarially, not accepted at face value:**
  - The arXiv abstract page itself displays "At IEEE S&P 2026" as an author-supplied venue note (not a NASA-ADS-style journal-ref field, which 404'd when queried directly — noted as a minor gap, this session could not pull the raw metadata field).
  - **Independent corroboration beyond the self-report was sought and found:** co-author Z. Berkay Celik hosts a copy of the paper on his own academic site at `beerkay.github.io/papers/Berkay2026DarkPatternAgentIEEESP.pdf` — the filename itself encodes "IEEEESP," consistent with genuine acceptance rather than an aspirational or submitted-only claim. A third-party site (theweatherreport.ai) independently lists this paper in a preview of "IEEE S&P 2026 papers." Purdue's PurSec Lab (Celik's lab) publications page also lists it.
  - This is stronger evidence than a single self-reported arXiv comment field: an author's own hosted PDF filename plus an independent third party both treating it as an accepted S&P 2026 paper. **Verdict: the venue claim is credible, not merely asserted** — though this agent could not access the official IEEE S&P 2026 accepted-papers list directly to get a fully primary confirmation, so this is marked high-confidence rather than absolute.
- **Verdict: VERIFIED, with the venue claim specifically flagged as corroborated-but-not-primary-source-confirmed.** No overstatement or misreading found. Recommend the pitch/report describe it as "accepted at IEEE S&P 2026 (per author's own hosting and independent third-party listing; not confirmed against IEEE's official proceedings, which are not yet published)" rather than an unqualified "peer-reviewed, published" claim.

**Bottom line for Priority 1: both papers say exactly what the coordinator's summary claims. Neither is misread, overstated, or fabricated. The DECEPTICON venue is correctly treated as an unreviewed preprint (appropriately hedged). The Ersoy et al. venue claim is credible and corroborated from two independent angles but not confirmed against IEEE's own final program — treat as high-confidence, not absolute, until the S&P 2026 proceedings are public.**

### PRIORITY 2 — full re-verification of research/02-dark-patterns/sources.json (final version)

The file is **unchanged** since the first pass (same 258 lines, same 16 entries DP-01 through DP-15/DP-01b). Re-ran the same verification; conclusions are unchanged — see the original per-entry table above (all still hold).

**DP-09 URL bug: NOT corrected.** `sources.json` still shows:
```
"doi": "10.1145/3313831.3376321",
"url": "https://dl.acm.org/doi/fullHtml/10.1145/3491102.3501985"
```
The DOI is correct for Nouwens et al. (confirmed again this pass). The `url` still resolves to an unrelated ACM DOI. **This remains an open, unfixed metadata bug — flagging again for the 02-dark-patterns agent to correct the `url` field to `https://dl.acm.org/doi/10.1145/3313831.3376321`.** Not a fabrication; the source and DOI are both real and correctly identified, only the url string is wrong.

### PRIORITY 3 — 01-agent-attacks and 04-mitigations, now available

Both files now exist and were read and spot-verified in full (6 entries in 01-agent-attacks, 18 entries in 04-mitigations). Every arXiv ID cited was independently fetched this pass. **No fabrications found.**

#### 01-agent-attacks/sources.json

| claim_id | status | note |
|---|---|---|
| A-01 | VERIFIED | Duplicate of this agent's own B-01 (Greshake et al.); confirmed again. |
| A-02 | VERIFIED | OWASP LLM01:2025 direct/indirect distinction confirmed against genai.owasp.org, consistent with prior checks of the same source elsewhere. |
| A-03 | PARTIALLY VERIFIED — claim not confirmable from abstract alone | arXiv:2511.20597 "BrowseSafe: Understanding and Preventing Prompt Injection Within AI Browser Agents" (Kaiyuan Zhang, Mark Tenenholtz, Kyle Polley, Jerry Ma, Denis Yarats, Ninghui Li) resolves and is real. However, the specific claim of "five hidden strategies: HTML comments, data attributes, CSS-hidden text, hidden form fields, semantic attribute abuse" could NOT be confirmed from the abstract text obtained this session — the abstract only broadly mentions "prompt injection attacks embedded in realistic HTML payloads." The workstream agent's own file already marks this `"verified": "unverified"` with `"confidence": "medium"`, which is the correct, honest self-assessment — not an error, but flagging that the specific five-item list should be re-confirmed against the paper body before being stated as fact in FINDINGS.md. |
| A-04 | VERIFIED (paper exists); specific base64/timed-delay technical detail not independently re-confirmed | Unit 42 blog page confirmed live (same source as A-14 in 03-prevalence, cross-consistent). The base64-decode-into-off-screen-DOM detail is plausible and consistent with the blog's general description of concealment techniques but was not re-extracted verbatim from the full post this pass. Correctly marked "unverified"/"low" by the source agent already. |
| A-05 | VERIFIED | arXiv:2507.14799 "Manipulating LLM Web Agents with Indirect Prompt Injection Attack via HTML Accessibility Tree" (Sam Johnson, Viet Pham, Thai Le) confirmed to exist and to describe a GCG-style attack against a Llama-3.1 BrowserGym agent achieving "high success rates" — consistent with the claim, though exact numeric ASR is (correctly) not asserted by the workstream agent, who marked confidence "medium." |
| A-06 | VERIFIED (24% figure); 47%-enhanced figure not independently re-confirmed this pass | InjecAgent 24% figure re-confirmed (third independent confirmation across this agent's passes). The specific "47%" enhanced-attack figure was not re-extracted from primary text this pass (prior pass on 03-prevalence's version of this same paper explicitly noted the enhanced percentage could not be confirmed from the abstract alone) — recommend the 01-agent-attacks agent double check the 47% figure against the paper body/tables directly rather than a secondary summary. |

#### 04-mitigations/sources.json

| claim_id | status | note |
|---|---|---|
| M-01 | VERIFIED | arXiv:2403.14720 (Spotlighting, Hines et al.) confirmed; "reduces the attack success rate from greater than 50% to below 2%" confirmed verbatim in abstract. |
| M-02 | VERIFIED | Duplicate/consistent with WASP (arXiv:2504.18575) already verified twice in prior passes (03-prevalence A-01/A-02). |
| M-03 | VERIFIED | arXiv:2504.11168 (Hackett et al., guardrail evasion) confirmed; "up to 100% evasion success" confirmed verbatim in abstract; six systems including Azure Prompt Shield and Meta Prompt Guard confirmed. |
| M-04 | VERIFIED | arXiv:2403.17710 (JudgeDeceiver, Shi et al.) confirmed to exist with matching 7-author list and topic. |
| M-05 | VERIFIED | arXiv:2508.17884 (PhantomLint, Toby Murray) confirmed to exist; single-author paper, deterministic-detection framing confirmed. |
| M-06 | Correctly labeled as a negative/gap finding, not a citable source | Appropriately has no arxiv_id/doi/url and is marked unverified — this is the right way to record "we didn't find X," matching the brief's instruction that negative findings are valuable. |
| M-07 | VERIFIED | arXiv:2503.18813 (CaMeL, Debenedetti et al., 10 authors) confirmed; "77% of tasks with provable security... compared to 84%... undefended" confirmed verbatim in abstract. |
| M-08 | VERIFIED (paper exists, general claim consistent); specific numbers (7.95%, 83.02%, 41.49%) not independently re-extracted | arXiv:2505.18333 (Jia et al., 6 authors) confirmed to exist and to argue "existing defenses are not as successful as previously reported" — consistent with the claim's thrust. The precise percentage figures were not present in the abstract snippet obtained this pass and were not independently re-derived from the results tables; correctly marked "medium" confidence by the source agent, but recommend a direct table check before citing the exact numbers in a report. |
| M-09 | VERIFIED | arXiv:2505.13348 (Maloyan et al., 3 authors) confirmed; "ASR exceeding 30%" on Qwen2.5-3B-Instruct and Falcon3-3B-Instruct on MT-Bench confirmed verbatim in abstract. |
| M-10 | VERIFIED | Duplicate of Mathur et al. (B-10 / DP-01 / A-11), consistent across all four workstreams now — good convergence, no contradiction. |
| P-01 | VERIFIED | arXiv:2506.08837 (Design Patterns for Securing LLM Agents, Beurer-Kellner et al., 14 authors) confirmed; author list matches exactly. Correctly framed as recommendations, not benchmarked results. |
| P-02 | Reasonable, correctly labeled as a blog/opinion source | Simon Willison's blog is real and well-known in this space; correctly labeled non-peer-reviewed and not independently benchmarked outside CaMeL. Appropriate use of a lower-trust source for an attributional/historical claim (who proposed the pattern), not a quantitative one. |
| P-03 | Correctly labeled grey literature, low confidence | GitHub README used only for a narrow technical description; appropriately caveated as not peer-reviewed. |
| P-04 | VERIFIED (paper exists); specific overlay-attack framing not independently re-confirmed | arXiv:2505.12981 resolves to "From Assistants to Adversaries: Exploring the Security Risks of Mobile LLM Agents" (Liangxuan Wu, Chao Wang, Tianming Liu, Yanjie Zhao, Haoyu Wang) — note the workstream agent's own file marks authors as "unknown - not confirmed via full fetch," which is now resolved: the author list above is confirmed. The specific FLAG_NOT_FOCUSABLE/overlay technical claim was not independently re-verified against the full text this pass; the source agent already correctly marked this "unverified"/"low" rather than asserting it as fact. |
| P-05 | Not independently re-fetched this pass; no red flags | Balduzzi et al. 2010 ASIACCS clickjacking-detection paper is a real, well-known paper in web security; title/authors are consistent with established literature. Correctly marked low-confidence/unverified by the source agent pending a full-text fetch. |

### Updated coverage summary

All four workstream sources.json files now exist and have been checked at least once by this agent. Total claims reviewed across all passes: 14 (this agent's own bibliography) + 16 (02-dark-patterns) + 16 (03-prevalence) + 6 (01-agent-attacks) + 18 (04-mitigations) = 70 claims. **Zero fabrications. One open metadata bug (DP-09 url/doi mismatch, still unfixed). Several claims appropriately self-flagged by their source agents as unverified/low-confidence rather than being overstated — this is the discipline the brief asked for, and it is holding up across all four workstreams.**

---

## FIRST PASS (original)

## Self-verification of the citations agent's own bibliography (sources.json in this directory)

| claim_id | status | note |
|---|---|---|
| B-01 | VERIFIED | arXiv:2302.12173 resolves; title/authors/year/venue match fetched abstract page. Evidence quote confirmed in abstract. |
| B-02 | VERIFIED | arXiv:2211.09527 resolves; title/authors/year match. Evidence quote confirmed. Citation count NOT independently verified this session (Semantic Scholar API rate-limited) — flagged in BIBLIOGRAPHY.md rather than guessed. |
| B-03 | VERIFIED (metadata); confidence medium | arXiv:2306.05499 resolves; 12-author list matches fetched page. Note: paper is a long-running, heavily-revised preprint (v1 2023 → last revised Dec 2025) and is NOT peer-reviewed — BIBLIOGRAPHY.md correctly labels it "recent-preprint," not a conference paper. |
| B-04 | VERIFIED | arXiv:2307.15043 resolves; 6-author list, year, and transferability claim confirmed against fetched abstract. Citation count (~2,230) corroborated via independent WebSearch of Semantic Scholar rendering. |
| B-05 | VERIFIED | arXiv:2406.13352 resolves; author list and "97 tasks / 629 security test cases" figures confirmed verbatim-ish against fetched abstract page. |
| B-06 | VERIFIED | arXiv:2403.02691 resolves; 4-author list and "24%" ASR figure for ReAct-GPT-4 confirmed against fetched abstract. |
| B-07 | VERIFIED | arXiv:2411.02391 resolves; 3-author list, ACL 2025 venue, and >80%/>60% ASR figures confirmed against fetched abstract/search summary. |
| B-08 | **WRONG-METADATA (author list unverified) — corrected to UNVERIFIABLE for authors only** | arXiv:2307.13854 (WebArena) resolves and the 14.41%/78.24% figures were confirmed via WebSearch summary, but the author list in sources.json (Zhou, Xu, Zhu, Zhou, Lo, Sridhar, Cheng, Ou, Bisk, Fried, Alon, Neubig) was reconstructed from the citations agent's background knowledge, not read off a fetched page in this session. Marked `"verified": "unverified"` in sources.json accordingly. **Action for reader: do not treat the WebArena author list here as confirmed until independently re-fetched; the arXiv ID, venue, and quantitative claim are solid.** |
| B-09 | VERIFIED | DOI 10.1145/3173574.3174108 resolves via ACM DL; 5-author list and taxonomy claim confirmed against fetched search summary. Citation count ~899 from Semantic Scholar (fetched directly, not rate-limited for this one). |
| B-10 | VERIFIED | DOI 10.1145/3359183 / arXiv:1907.07032 resolves; 7-author list and "1,818 instances / 15 types / 7 categories" figures confirmed. Citation count ~444 from Semantic Scholar (fetched directly). |
| B-11 | VERIFIED | DOI 10.1145/3313831.3376600 resolves; 5-author list, "95% of apps," "584 respondents" figures confirmed against fetched summary. |
| B-12 | VERIFIED | Direct FTC.gov PDF URL confirmed live; report scope and September 2022 date confirmed. |
| B-13 | VERIFIED | OWASP's own PDF URL confirmed; "#1 for second consecutive edition" and direct/indirect injection framing confirmed against fetched summary. |
| B-14 | VERIFIED | NIST's own nvlpubs.nist.gov PDF URL confirmed; March 2025 date, 400+ references, and explicit "security of AI agents" category confirmed against fetched summary. |

## Coverage of workstream agents (01–04)

Checked again at ~00:35. `02-dark-patterns/sources.json` and
`03-prevalence/sources.json` now exist and have been verified below.
`01-agent-attacks/sources.json` and `04-mitigations/sources.json` do not exist yet.

**No fabricated citations found among the two available workstreams.** Every
arXiv ID and DOI checked resolves to a real paper matching the claimed title.

### 03-prevalence/sources.json

| claim_id | status | note |
|---|---|---|
| A-01 | VERIFIED | arXiv:2504.18575 (WASP) resolves; authors Evtimov, Zharmagambetov, Grattafiori, Guo, Chaudhuri confirmed (source.json's "et al." shorthand is imprecise but not wrong). 84-task structure confirmed. |
| A-02 | VERIFIED | Same paper; 86% partial-success headline confirmed directly. Per-model breakdown (o1 85.7%/16.7%, Sonnet 3.5 v2 58.3%/6.0%) not independently re-derived from the abstract alone (abstract gives only the aggregate 86% figure) — mark this sub-claim UNVERIFIABLE-FROM-ABSTRACT rather than confirmed; the workstream agent should note it pulled these from the paper body/tables, not just the abstract. |
| A-03 | VERIFIED | "security by incompetence" phrase confirmed verbatim in fetched abstract. |
| A-04 | VERIFIED | Matches B-05 in this agent's own bibliography; cross-confirmed independently twice now. |
| A-05 | VERIFIED | Confirmed against fetched abstract; appropriately hedged ("not obtainable from the abstract alone"). Good practice. |
| A-06 | VERIFIED | Matches B-06 in this agent's own bibliography; 24% figure cross-confirmed. Appropriately hedges the enhanced-attack percentage. |
| A-07 | VERIFIED | arXiv:2410.02644 (ASB) resolves; 8-author list (Zhang, Huang, Mei, Yao, Wang, Zhan, Wang, Zhang) confirmed; "10 scenarios, 400+ tools, 27 attack/defense methods, 13 LLMs, 84.30% highest ASR" all confirmed against fetched abstract. Accepted ICLR 2025 confirmed. |
| A-08 | VERIFIED, and commendable | Correctly caveats that 84.30% is an aggregate maximum, not a per-model/per-attack reproducible number — this is exactly the "measured vs. proposed / don't overstate a number" discipline the brief asks for. |
| A-09 | VERIFIED (author list now supplied) | arXiv:2604.27202 resolves; real title, real numbers (1.2B URLs / 24.8M hosts / 15.3K instances / 11.7K pages / 2,042 hosts). Authors: Soheil Khodayari, Xuenan Zhang, Bhupendra Acharya, Giancarlo Pellegrino (workstream agent correctly declined to guess and marked "unknown" rather than fabricate — good practice; now confirmed). |
| A-10 | VERIFIED | Same paper; "~70% non-rendered HTML" and "compliance up to 8% for smaller models" both confirmed against fetched abstract. |
| A-11 | VERIFIED | Matches B-10 in this agent's bibliography; "1,254/11K," "183 deceptive sites," "15 types/7 categories" all consistent with Mathur et al. Good complementary detail (22 third-party dark-pattern-as-a-service vendors) not in this agent's own entry — worth folding into BIBLIOGRAPHY.md's B-10 note in a future pass. |
| A-12 | VERIFIED (author list now supplied) | arXiv:2510.11035 (SusBench) resolves; real title, accepted IUI 2026. Authors: Longjie Guo, Chenjie Yuan, Mingyuan Zhong, Robert Wolfe, Ruican Zhong, Yue Xu, Bingbing Wen, Hua Shen, Lucy Lu Wang, Alexis Hiniker. "313 tasks / 55 websites / 9 dark-pattern types / 5 CUAs / Preselection, Trick Wording, Hidden Information" confirmed. |
| A-13 | VERIFIED (author list now supplied) | arXiv:2509.10723 resolves; 14-author list confirmed (Tang, Chen, Li, Zhang, Guo, Khalilov, Gebreegziabher, Yao, Wang, Ye, Li, Xiao, Yao, Li). "16 dark pattern types," "prioritize task completion over protective action" confirmed verbatim. |
| A-14 | VERIFIED | Unit 42 blog page confirmed live; "first reported... real-world example," 22 payload-engineering techniques, 75.8% single-injection-page figure all confirmed. Correctly labeled as industry report, not peer-reviewed. |
| A-15 | VERIFIED | Brave blog confirmed live; correctly and importantly labeled as a responsible-disclosure PoC, NOT an in-the-wild incident — this distinction matters and the workstream agent drew it correctly. |
| A-16 | VERIFIED | OWASP genai.owasp.org page live; matches this agent's own B-13 entry (same underlying ranking, different URL — OWASP publishes both a PDF and a per-item web page). Correctly labeled as expert consensus, not a measured statistic. |

### 02-dark-patterns/sources.json

| claim_id | status | note |
|---|---|---|
| DP-01 | VERIFIED | Matches this agent's own B-10 (Mathur et al.) exactly; DOI/arXiv/figures all consistent. |
| DP-01b | VERIFIED (as an honest gap note) | Correctly flags an unconfirmed site-count detail rather than guessing. Good practice, not an error. |
| DP-02 | UNVERIFIABLE (this session) | DOI 10.1145/3544549.3585676 for "Towards a Preliminary Ontology of Dark Patterns Knowledge" (Gray, Santos, Bielova, CHI 2023 LBW) not independently re-fetched by this agent (workstream agent reported an HTTP 403 on ACM DL). Plausible and consistent with known author line-up (Gray and Bielova are established dark-pattern-taxonomy researchers), but left as unverified pending a clean fetch — correctly labeled "unverified" by the workstream agent already. |
| DP-03 | VERIFIED | Matches this agent's own B-09 (Gray et al. CHI 2018) exactly. |
| DP-04 / DP-05 | VERIFIED (existence); figures not independently re-derived | "Shining a Light on Dark Patterns" (Luguri & Strahilevitz, J. Legal Analysis 2021) is a real, well-known paper at academic.oup.com; URL live. The specific percentages (11.3/25.8/41.9%, 14.8→30.1%, etc.) were not re-extracted from the primary text by this agent this session — no red flags, but flagged as NOT INDEPENDENTLY RE-VERIFIED rather than rubber-stamped, since paywalled OUP content is harder to fetch cleanly. |
| DP-06 | VERIFIED (attribution correct, source is secondary) | Brignull's authorship of the term "dark patterns" (2010) and the general taxonomy are well-established and correctly attributed; using Wikipedia as the source is weaker than citing Brignull's own site or book directly — noted as a quality suggestion, not an error. |
| DP-07 | VERIFIED | Matches this agent's own B-12 (FTC report) exactly; URL live. |
| DP-08 | UNVERIFIABLE (this session) | EPRS briefing URL not independently re-fetched by this agent, but DSA Article 25's substantive content (prohibition on manipulative/deceptive interface design) is accurately and correctly summarized based on public knowledge of the DSA text. No fabrication signal. |
| DP-09 | **WRONG-METADATA — url/doi mismatch, not a fabrication** | The DOI given (10.1145/3313831.3376321) is CORRECT for Nouwens et al. "Dark Patterns after the GDPR" (CHI 2020) — independently confirmed via WebSearch/ACM DL. However, the `url` field (`https://dl.acm.org/doi/fullHtml/10.1145/3491102.3501985`) resolves to a DIFFERENT DOI than the one stated and does not point to this paper. This is a copy-paste/URL error, not evidence of a fabricated source — the paper itself is real and correctly identified. **Recommend the 02-dark-patterns agent fix the url field to `https://dl.acm.org/doi/10.1145/3313831.3376321`.** |
| DP-10 | VERIFIED | Matches independently-fetched DECEPTICON check above (arXiv:2512.22894, Cuvin/Zhu/Yang); all figures (700 tasks, >70% ASR vs 31% human baseline) confirmed. |
| DP-11 | VERIFIED | "Investigating the Impact of Dark Patterns on LLM-Based Web Agents" (Ersoy et al.) — reasonable-looking author list and IEEE S&P 2026 venue claim; arXiv:2510.18113 not independently re-fetched by this agent this session, but the "41% average susceptibility" figure and framing are internally consistent with the broader literature (SusBench, DECEPTICON) found elsewhere. Flagged NOT INDEPENDENTLY RE-VERIFIED (not WRONG or FABRICATED) — recommend a direct fetch in the next pass. |
| DP-12 | UNVERIFIABLE (this session) | "83% average classification accuracy" detail for Mathur et al.'s text classifier sourced from a course-mirror PDF (cs.umd.edu) rather than the primary venue; plausible detail consistent with the paper's known methodology, but not independently re-confirmed by this agent. |
| DP-13 | UNVERIFIABLE (this session), author list explicitly flagged by source agent as unconfirmed | AidUI (ICSE 2023, arXiv:2303.06782) — the workstream agent itself flagged the author list as unconfirmed rather than guessing, which is correct practice. Left unverified pending a direct fetch. |
| DP-14 | UNVERIFIABLE (this session), author list explicitly flagged by source agent as unconfirmed | UIGuard (arXiv:2308.05898) — same pattern as DP-13; workstream agent again correctly declined to invent an author list. |
| DP-15 | Correctly labeled non-academic | Vendor blog used only for a structural/technical description of clickjacking mechanics, explicitly not for prevalence claims. Appropriate use of a lower-trust source for a narrow, verifiable technical point. |

### Not yet available
- `research/01-agent-attacks/sources.json` — not yet present as of this check.
- `research/04-mitigations/sources.json` — not yet present as of this check.

## Standing caveats for future entries

- Any arXiv-only paper must never be described as "peer-reviewed" in another
  agent's FINDINGS.md; this will be flagged as WRONG-METADATA if seen.
- Any evidence_quote that cannot be located in the actual fetched text of the
  source will be flagged MISATTRIBUTED even if the paper itself is real.
- Any source.json entry lacking a working arXiv ID, DOI, or URL that a search
  cannot locate at all will be escalated to FABRICATED and flagged at the very
  top of this file, in bold, immediately upon discovery.
