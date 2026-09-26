# Verification Closeout

Scope: the 25 claims across `01-agent-attacks`, `02-dark-patterns`, `03-prevalence`, `04-mitigations`, and `05-citations` marked `"verified": "unverified"` or `"confidence": "low"` in their `sources.json`, plus the specific numeric chases and excluded-lead re-checks the task called out by name. Full attempt-by-attempt trail is in `LOG.md`. Merged, report-ready bibliography is in `resolved_sources.json`.

Result: 22 of 25 originally-flagged entries are now RESOLVED-CONFIRMED, 2 are RESOLVED-CORRECTED (venue/source swap), 2 remain STILL-UNVERIFIABLE (ACM pages blocked this tool, no alternate full text found), and 1 is N/A-BY-DESIGN (an absence-of-evidence statement with nothing to fetch). No claim was REFUTED outright, but several numbers needed correction or a narrower scope than the original phrasing implied — see below.

---

## REPORT-SAFETY — do not use these claims as currently stated

1. **"12 defenses broken" / adaptive-attack claims — do not cite arXiv:2503.00061 for the "12 defenses, >90% ASR" figure.**
   That number belongs to a *different* paper: arXiv:2510.09023, "The Attacker Moves Second" (Nasr, Carlini, Sitawarin, Schulhoff, Tramèr, et al.). arXiv:2503.00061 ("Adaptive Attacks Break Defenses Against Indirect Prompt Injection Attacks on LLM Agents," Zhan et al.) is a real, separate paper reporting **8 defenses bypassed, >50% ASR**. A web search performed during this pass actively conflated the two papers' arXiv IDs — proof that this mix-up is easy to make and likely already latent in earlier drafts. Safe wording: cite 2503.00061 for "8 defenses / >50%" (agent-specific IPI defenses) and 2510.09023 for "12 defenses / >90%" (broader jailbreak+injection defenses, not agent-specific) — never merge the two into one sentence.

2. **GCG accessibility-tree attack (arXiv:2507.14799) — do not attach a specific success-rate percentage.**
   The paper (Johnson, Pham, Le) confirms the attack and describes results only as "high success rates across real websites in both targeted and general attacks." No numeric ASR could be extracted from the abstract or found via search. Safe wording: "achieves high attack success rates in the authors' evaluation (exact figure not stated in the abstract)" — do not invent or borrow a percentage from a different paper.

3. **DP-02 (ACM ontology paper) and DP-03 (Gray et al., CHI 2018, "The Dark (Patterns) Side of UX Design") — full text could not be read.**
   ACM Digital Library returned HTTP 403 to this tool on both DOIs, on this pass and the prior one. The papers are real (the DOIs resolve, and both are well-known, frequently-cited works), but no fetch of this session independently confirmed their claimed content past the DOI/title match. Safe wording: attribute only what is already independently corroborated elsewhere (e.g., Gray et al.'s dark-pattern-strategies taxonomy is widely re-cited by papers this session *did* fetch, like the Wikipedia dark-patterns article and Mathur et al.) rather than quoting DP-02/DP-03 directly as if their full text had been read.

4. **DP-15 (edgemesh.com blog on clickjacking) — replace with the academic primary source.**
   The blog is real but is vendor marketing content with no peer review, used to support a technical security claim. A proper primary source exists and was confirmed this pass: Balduzzi, Egele, Balzarotti, Kirda, Krügel, "A Solution for the Automated Detection of Clickjacking Attacks," ACM ASIACCS 2010 (dl.acm.org/doi/10.1145/1755688.1755706; also mirrored by the authors at UCSB). Use the ASIACCS paper, not the blog, for any report-facing clickjacking citation. (This also applies to P-05 in 04-mitigations, which cited a ResearchGate mirror of the same paper that 403'd — use the ACM DL link instead.)

5. **P-03 (github.com/neshboy/promptinjectionradar) — do not cite as evidence of adoption, effectiveness, or maturity.**
   The repository exists and its README is as described, but it has 0 stars and 5 commits — an essentially unused hobby project. Safe wording, if mentioned at all: "at least one open-source prompt-injection filter tool exists (e.g., promptinjectionradar)" — do not imply community adoption or validated effectiveness.

6. **Ersoy et al. (arXiv:2510.18113) — say "accepted, to appear at IEEE S&P 2026," never "peer-reviewed and published."**
   This pass reached a primary source the prior pass could not: the conference's own official accepted-papers page (sp2026.ieee-security.org/accepted-papers.html) lists the exact paper and author list. This is real acceptance, not just author/lab self-report — stronger evidence than before. But the proceedings are not yet published (no page numbers/DOI yet), so "published" or "peer-reviewed" (past tense, implying the review+publication cycle is complete) overstates the current status. Use: "accepted to appear at the 47th IEEE Symposium on Security and Privacy (S&P 2026)."

7. **A-11 (arXiv:2604.12371) — name it as a workshop paper if citing a venue at all.**
   The paper exists and matches its cited title/authors, but its stated acceptance is to the *ICLR 2026 Workshop on Agents in the Wild*, not the ICLR 2026 main conference. If the report names a venue, it must say "workshop paper" — presenting it as a main-track ICLR paper would overstate its review bar.

8. **SnapGuard (arXiv:2604.25562) numbers, if used anywhere in the final report, must be attributed precisely.**
   Confirmed figures: F1 = 0.75, TPR = 0.66, FPR = 0.09, evaluated across eight prompt-injection attacks and two benign settings (April 2026). This claim_id was not found in any of the five sources.json files this agent was authorized to read — it likely lives in a later workstream (06/07/08) or is only mentioned informally in a FINDINGS.md. Flagging here so whoever owns that citation uses the confirmed numbers above rather than a rounded or remembered figure.

9. **FTC "Bringing Dark Patterns to Light" and the EPRS "Regulating dark patterns in the EU" PDFs — cite the landing pages, not claims of having read the full PDF text.**
   Both PDFs came back as unparseable binary through this tool chain (twice, on two different fetch attempts). Corroboration here comes from the issuing bodies' own secondary pages (ftc.gov's report landing page and press release; europarl.europa.eu's think-tank page), which is solid evidence the documents exist and say what's claimed, but is not the same as having directly quote-checked the PDF body. If the report quotes specific numbers from deep inside either PDF (beyond the headline points corroborated here), flag those specific quotes as needing one more direct-PDF check with a different tool (e.g., a local PDF-to-text conversion) before publication.

---

## Resolution ledger (by claim_id)

| Claim ID | Workstream | Outcome | Note |
|---|---|---|---|
| A-03 | 01-agent-attacks | RESOLVED-CONFIRMED | BrowseSafe (2511.20597); 5-technique taxonomy quoted from Sec. III-D of the HTML version |
| A-04 | 01-agent-attacks | RESOLVED-CONFIRMED | Unit42 blog fetched directly; author/date/stats confirmed |
| A-07 | 01-agent-attacks | RESOLVED-CONFIRMED | ASB (2410.02644), ICLR 2025, 84.30% ASR confirmed |
| A-08 | 01-agent-attacks | RESOLVED-CONFIRMED | Adaptive Attacks (2503.00061): >50% ASR vs 8 defenses — see REPORT-SAFETY #1 for the paper it must not be confused with |
| A-10 | 01-agent-attacks | RESOLVED-CONFIRMED | WASP (2504.18575): 86% partial-success figure confirmed from full abstract |
| A-11 | 01-agent-attacks | RESOLVED-CORRECTED | 2604.12371 exists; is a workshop paper, not main-track — see REPORT-SAFETY #7 |
| A-12 | 01-agent-attacks | RESOLVED-CONFIRMED | SoK 2603.22928 confirmed to exist with cited title/authors |
| (InjecAgent 47%) | 01-agent-attacks / 03-prevalence | RESOLVED-CONFIRMED | Table 3 of 2403.02691: base 23.6%→"24%", enhanced 47.0% |
| (GCG AX-tree ASR) | 01-agent-attacks | STILL-UNVERIFIABLE (number only) | 2507.14799 confirmed to exist and make the qualitative claim; no numeric ASR found — see REPORT-SAFETY #2 |
| DP-01b / DP-12 | 02-dark-patterns | RESOLVED-CONFIRMED | Mathur et al. 1907.07032, CSCW 2019: 1,818 instances / 15 types / 7 categories / 183 sites / 22 vendors |
| DP-02 | 02-dark-patterns | STILL-UNVERIFIABLE | ACM DL 403's this tool; DOI resolves, content not independently re-read — see REPORT-SAFETY #3 |
| DP-03 | 02-dark-patterns | STILL-UNVERIFIABLE | Same as DP-02 — see REPORT-SAFETY #3 |
| DP-06 | 02-dark-patterns | RESOLVED-CONFIRMED | Wikipedia dark_pattern article fetched directly, Brignull taxonomy + regulatory uptake confirmed with inline citations |
| DP-07 | 02-dark-patterns | RESOLVED-CONFIRMED | FTC report — confirmed via ftc.gov's own landing/press pages; PDF itself unreadable by this tool — see REPORT-SAFETY #9 |
| DP-08 | 02-dark-patterns | RESOLVED-CONFIRMED | EPRS report — confirmed via europarl.europa.eu's own pages; PDF itself unreadable by this tool — see REPORT-SAFETY #9 |
| DP-09 | 02-dark-patterns | RESOLVED-CONFIRMED | Nouwens et al., CHI 2020: "only 11.8% meet minimal requirements" |
| DP-13 | 02-dark-patterns | RESOLVED-CONFIRMED | AidUI, ICSE 2023: precision 0.66 / recall 0.67 / F1 0.65 (subset F1 up to 0.82) |
| DP-14 | 02-dark-patterns | RESOLVED-CONFIRMED | UIGuard, UIST 2023: precision 0.82 / recall 0.77 / F1 0.79 |
| DP-15 | 02-dark-patterns | RESOLVED-CONFIRMED (source swap recommended) | Blog exists and says what's claimed, but see REPORT-SAFETY #4 for the better academic source |
| M-06 | 04-mitigations | N/A-BY-DESIGN | Absence-of-evidence analytical statement, nothing to fetch; keep labeled as interpretation, not citation |
| P-03 | 04-mitigations | RESOLVED-CONFIRMED (weak source) | Repo exists, 0 stars — see REPORT-SAFETY #5 |
| P-04 | 04-mitigations | RESOLVED-CONFIRMED | 2505.12981 confirmed to exist with cited title/authors |
| P-05 | 04-mitigations | RESOLVED-CORRECTED | Same paper as DP-15's better source (Balduzzi et al., ASIACCS 2010); swap ResearchGate link for ACM DL / author page |
| M-11 | 04-mitigations | RESOLVED-CONFIRMED | Official OWASP Top 10 for LLM Applications project page |
| M-12 | 04-mitigations | RESOLVED-CONFIRMED | Mend.io blog accurately reflects the official OWASP Top 10 list |
| B-08 | 05-citations | RESOLVED-CONFIRMED | WebArena, 2307.13854: GPT-4 14.41% vs human 78.24% |
| Ersoy venue | 05-citations | RESOLVED-CONFIRMED | Found on IEEE's own official accepted-papers page — see REPORT-SAFETY #6 for exact phrasing |
| BragJack (excluded lead) | 03-prevalence | RESOLVED-CONFIRMED (now citable) | Primary source (forever.security) now exists; original exclusion was correct at the time |
| OpenAI Atlas (excluded lead) | 03-prevalence | RESOLVED-CONFIRMED (now citable) | Primary source (openai.com's own blog) now exists; original exclusion was correct at the time |
| "12 defenses" (excluded lead) | 01-agent-attacks | RESOLVED-CONFIRMED (now citable) | Primary source is arXiv:2510.09023 — see REPORT-SAFETY #1, do not conflate with 2503.00061 |

See `resolved_sources.json` for the full merged, deduplicated bibliography with per-source verification status and workstream attribution.
