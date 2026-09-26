# LOG — TrickyArena / LiteAgent research

2026-09-24T00:00Z — Started. Read BRIEF.md (00-shared) for source rules and output contract. Created 07-trickyarena directory.

2026-09-24T00:05Z — WebFetch on arxiv.org/abs/2510.18113 abstract page. Got title/authors/abstract and the headline 41% stat, but table numbers were not rendered from the abstract page (need PDF).

2026-09-24T00:06Z — WebFetch on github.com/LiteAgent/liteagent (README). Confirmed: no LICENSE file mentioned, TrickyArena hosted at agenttrickydps.vercel.app, dp query param format, requires OpenAI keys per README note. This org (LiteAgent) appears to be a mirror/fork; paper's own repo link is purseclab/liteagent.

2026-09-24T00:07Z — Navigated hosted site agenttrickydps.vercel.app with browser tool. Confirmed reachable (200, renders "Dark Patterns" page with 4 site selectors: News, Music, Health, Shopping).

2026-09-24T00:10Z — Used GitHub REST API (curl, no auth) against LiteAgent/liteagent repo. Root file listing has no LICENSE file. Confirmed via `contents/LICENSE` -> 404, and repo API field `"license": null`.

2026-09-24T00:12Z — Pulled raw README.md (full 226 lines) from LiteAgent/liteagent main branch. Confirms: dp query format `?dp=<pat1>_<pat2>_...`, evaluation via `evaluation.checkers.custom_checker`, TSR/DPSR/confusion-matrix definitions (EF/EC/DF/DC), requires OpenAI keys for agent submodules, no license section in README.

2026-09-24T00:14Z — Pulled evaluation/enums.py and evaluation/consts.py from repo. consts.py gives the authoritative dp code -> name mapping per site (site_dp_mapping dict), confirming 6 sites total in the codebase: shopping, news, spotify (=Music), wiki, health, linkedin. Note wiki/linkedin patterns are marked "# TODO Remove wiki dark patterns" and are NOT part of the hosted 4-site homepage (News/Music/Health/Shopping) — likely legacy/unused in the published paper's 14-pattern set.

2026-09-24T00:16Z — Pulled evaluation/dp_checks.py. CONFIRMS scoring is 100% DOM-action based (element ID click/exists/absent checks against an action-trace DB), never an outcome check like "was a charge processed" — critical for Q5.

2026-09-24T00:18Z — WebFetch on arxiv.org/pdf/2510.18113 via small model — got partial info (Table I overall structure, confirmed the 5 Gray et al. taxonomy categories, DPSR/TSR per-agent numbers, per-model Table II). Some fields (full Appendix B list) not captured by the summarizing model.

2026-09-24T00:20Z — Read the full cached PDF directly with the Read tool (multimodal PDF ingestion) to get verbatim text of the paper. Got the FULL paper text including: Table 1 (agent x category DPSR), Table 2 (per-LLM metrics), Table 5 in Appendix B (complete list of the 14 dark patterns integrated in TrickyArena, with IDs, website, description, goal, and category checkmarks), Appendix C (extensibility/CSP notes), Appendix D (per-agent integration details — confirms LiteAgent is agent-agnostic, not OpenAI-locked at the framework level, but agent *submodules* need their own configured LLM API keys), Appendix F (countermeasure postscripts), and the Meta-Review (no human baseline — an acknowledged limitation).

2026-09-24T00:24Z — Checked purseclab/liteagent (paper's actual cited repo) via GitHub API. Confirmed same result: `"license": null`, no LICENSE file. Two orgs/repos (LiteAgent/liteagent mirror and purseclab/liteagent canonical) both have no license file.

2026-09-24T00:26Z — Live-verified the hosted TrickyArena URL scheme by driving the actual site in a browser: clicked the News site's dark-pattern dropdown, saw 6 selectable patterns (Bait and Switch, Obfuscation, Sponsored Ad, Confusion, Big Donate Button, Combo Donate Button — the last two are NOT in the paper's Table 5 or in consts.py, suggesting patterns added to the live site after publication for follow-on ablation experiments), selected "Bait and Switch", clicked "Go to News Site", and confirmed the resulting URL is exactly `https://agenttrickydps.vercel.app/news?dp=bs` — matching the paper's and README's documented format.

2026-09-24T00:30Z — Cross-checked codebase's site_dp_mapping codes (news: sa/cf/ob/bs; spotify: du/ds/am; health: cs/tos/cf; shopping: tu/p1/p2/s/w/t1-t8) against paper's Appendix B Table 5. Table 5 lists exactly 14 patterns across News(4: bs,ob,sa,cf), Spotify(3: du,ds,am), Health(3: cs,tos,cf — NOTE: health "cf" = Confirm Shaming, a DIFFERENT pattern reusing the same short code as news "cf" = Confusion), Shopping(4 core: p1,p2,w,s — the t1-t8 "tu" family are NOT in Table 5; they are UI-attribute-modification variants used only in the RQ4 ablation study, not part of the core 14). 4+3+3+4=14. Confirmed count matches paper's stated "14 specific dark patterns."

2026-09-24T00:35Z — Writing FINDINGS.md and sources.json now. No code written, no repo cloned, nothing committed — research only, per instructions.
