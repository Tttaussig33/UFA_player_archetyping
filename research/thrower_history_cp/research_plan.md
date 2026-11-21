**Does prior thrower performance improve predictions beyond ShownSpace CP?**  
Feasibility assessment and proposed research plan — November 20, 2026

**Assessment: feasible to start with saved probabilities.** We can compare ShownSpace CP, a general recalibration, and a small history-based extension without recovering or retraining the original model. The most defensible first experiment uses only 2026 for fitting the extension and forming player histories, then evaluates later 2026 games. This remains conditional on the **unverified working assumption that 2026 was excluded from CP fitting and tuning**. No predictive models were fitted and no comparative test scores were inspected for this assessment.

This concerns pass prediction across ultimate situations, using UFA observations. It does not inherit the earlier O-line, possession-number, timeout, end-of-quarter, or long-field restrictions. Results would support conclusions about this UFA sample, not automatic generalization to all ultimate leagues.

**What the data support.** The preserved October 12 export has 490,688 records across 901 games in 2021–2026. November 20 live database counts agree by season; that verifies counts, not unchanged row contents. The 2026 audit found:

| Check | Finding and decision |
|---|---|
| Coverage | 78,847 records in 142 games: 131 regular-season and 11 playoff games. |
| Physical attempts | 78,784 after excluding 63 stalls. Retain completed passes, goals, drops, throwaways/interceptions, and passes intercepted for Callahans (event codes 18, 19, 20, 22, 23). Pulls and administrative events are not in this eligible set. |
| CP availability | 18 missing values, all in May 2 SLC–OAK; 17 completions and one throwaway. No out-of-range or exact-zero/one CP values. Use one common valid-CP cohort for every model. |
| Duplicates | None by game–throw ID, exact row, game–source hash, or game–source-side/index. Game metadata also has unique IDs. |
| Geometry | All 2026 coordinates are present and within the recorded field bounds; stored distances/displacements agree with coordinates. This does not verify that manually recorded locations are accurate. |
| Player identity | 12 physical attempts have unknown throwers. Use the general-model fallback for these; never pool them as one player. Known thrower IDs all join the roster. Do not join repeated roster rows directly or merge people by name. |
| Receiver identity | 4,363 valid-CP physical attempts lack a named receiver. Retain them: requiring a receiver would preferentially remove unsuccessful passes. |
| Missing games | July 18 PIT–CHI is marked Final but has no throws. Two other empty schedule entries remain Upcoming and may be stale/rescheduled fixtures, not two additional missing completed games. |

The updated manuscript trains CP on distances **at least 1.5 yards**. Recommend a manuscript-aligned primary cohort with this minimum: **77,686 throws, 142 games, 746 named throwers**, plus nine unknown-thrower attempts. This excludes 1,082 short physical attempts and then 16 remaining missing-CP attempts. Analyze all 78,766 valid-CP physical attempts as a prespecified sensitivity. The minimum is a model-domain choice, not a long-field or O-line filter; confirm that it also applies to the production model.

**Drops: keep three definitions distinct.** Let C be caught passes, D recorded drops, and A physical attempts.

| Quantity | Treatment of drops | Role in this project |
|---|---|---|
| Actual catch outcome | Caught = 1; drop or other failed pass = 0 | Proposed primary binary target, matching the ordinary meaning of pass completion. |
| Thrower-credited success | Caught or dropped = 1; other failed pass = 0 | Required separate target sensitivity; aligns with confirmed CPOE credit. |
| ShownSpace reported completion percentage | C / (A − D) | Descriptive statistic; verified live for all 5,378 comparable 2026 player-game rows, including 639 with drops. |

Braden's message confirms the credit convention; the live comparison establishes the percentage denominator. Neither proves CP's training labels. Do not drop failed catches from the primary prediction sample to imitate the displayed percentage: that would condition inclusion on the outcome. For each binary target, refit both extensions and score all three versions on the same throws. If provenance establishes a different CP target, finalize the primary target before fitting or inspecting model performance and document the decision.

Preserve supplied `cp`, supplied `cpoe`, and official aggregate CPOE unchanged. Earlier reconciliation supports official CPOE as `(C + D)/A − mean(available CP)`; stored per-throw `cpoe` equals 1 on drops and must not be averaged as a residual. Call new outputs `research_recalibrated_probability`, `research_history_probability`, and target-specific **research residuals**. Personalized residuals answer a different question from official CPOE.

**What the references change.** Noel's NHL paper combines an existing expected probability with player performance from previous games, uses out-of-fold baseline predictions for its training histories, and evaluates held-out seasons. Adopt that basic comparison and history cutoff. Its recency weighting, spatial bins, Gower distance, LightGBM, skill brackets, and goaltender features are not prerequisites. Out-of-fold predictions alone do not establish chronological independence; time ordering must also be verified. [NHL reference](https://arxiv.org/pdf/2511.07703), §§3.3–3.5.

The current ShownSpace reference is the **October 20 JSDSS submission**, rather than the older September JSDSS TeX draft. It describes 2021–2025 data, a spline-expanded logistic CP model, a 1.5-yard minimum, temporal/player/game holdouts, and game-bootstrap uncertainty. Those manuscript experiments do not identify the model that generated production `cp`. Its stated 450,000-plus pre-2026 throws also differ from our 411,841 pre-2026 exported records; dataset equivalence needs confirmation.

**Live database investigation.** `public.model_files` has `filename`, binary `file_data`, and `insert_timestamp` columns. It is a plausible artifact location, but this account cannot read the filenames or binaries. `dd_metrics.throws` has `model_version`, but that schema is access-denied. The inspected CP columns have no explanatory comments; the scoped function-name search found no training/prediction routine. This does not rule out application-side training code. Therefore older saved CP predictions remain **unverified as in-sample versus out-of-fold/held-out**. Do not label them out-of-sample merely because they are saved predictions, or infer their training status from calibration scores.

**First model: one shared adjustment with conservative history.** Compare:

| Version | Inputs and purpose |
|---|---|
| A. Original CP | Saved probability, unchanged. |
| B. General recalibration | Logistic regression using only logit(CP), with a fitted intercept and slope. Tests whether a common correction already explains improvement. |
| C. History extension | The same CP terms plus one shrunken measure of the thrower's prior-game performance relative to CP. |

For thrower i before game g, define `h = sum(y − CP) / (n + k)` using only eligible attempts from earlier games; n is their count. Fit `logit(q) = a + b × logit(CP) + c × h`. This is a single pooled model, not a separate model per player. With no history, h = 0; with little history, k pulls the adjustment toward zero. Unknown throwers use B directly. Fit coefficients on the fitting period; choose k from a small prespecified grid (50, 200, 800), with B itself as the no-history candidate, using validation log loss. Start with cumulative 2026 history, without recency or location tuning. Use no class rebalancing or arbitrary minimum-history exclusions.

History availability supports this approach but argues against complex player models: among 18,156 named-thrower test attempts in the primary cohort, **98.8%** have some earlier 2026 history, **72.0%** have at least 100 prior attempts, and **88.9%** have at least five earlier games. At the player-game level, median test history is 93 attempts across eight games. Older data would give 555 of 746 players prior-season history at their first 2026 appearance, but historical CP provenance must be resolved before making that the main design. Available histories are left-truncated at 2021, not full careers.

**Chronological plan, selected from dates and coverage.**

| Stage | 2026 dates | Games | Primary-cohort throws |
|---|---|---:|---:|
| Fit | April 24–June 14 | 80 | 43,791 |
| Validate | June 15–July 5 | 29 | 15,737 |
| Test | July 6 onward, through August 28 | 33 | 18,158 |

Use `StartTimestamp`, not row order, insertion time, or blindly parsed GameID: one older game ID disagrees with its scheduled date. Freeze history before each game; conservatively update only after all games on a calendar date. Never use the current game's partial/final results, final season totals, future roster summaries, or test-based feature selection. During validation, keep fitted coefficients fixed while updating histories from completed earlier dates. After choosing the specification, refit coefficients on fit+validation, freeze them, and replay the test dates. Earlier test-game outcomes may update later histories under this declared online rule, but never retune coefficients or hyperparameters. Also report a sensitivity with histories frozen at July 5.

**Timing limitation:** the new history features and learned coefficients can be restricted to information preceding each predicted game. The target throw's saved CP itself uses that throw's recorded context, including destination coordinates. Thus this is a retrospective, context-conditional prediction study—not a literal prediction of individual passes before the game. Outcome-influenced endpoints, imputed clocks, later data corrections, and prediction timestamps need investigation before claiming live/pre-throw deployment. A strict requirement that *every* input exist before the game cannot be met with these saved per-throw CP values.

**Evaluation and uncertainty.** Primary contrast: **C versus B in mean log loss**; C versus A is secondary. Report Brier score, calibration plots with counts, and descriptive calibration intercept/slope for all three. Lower log loss/Brier is better; calibration asks whether, for example, 90% predictions succeed about 90% of the time. Fit no test-set calibration correction. Accuracy at a 0.5 cutoff is uninformative in this completion-heavy sample; AUC can be supplementary.

Use 10,000 **paired whole-game bootstrap** resamples: select the same games with replacement for all models and keep every included throw in each selected game. Report 95% intervals for score differences, preserving pairing; do not bootstrap individual throws. The primary estimand weights throws equally; equal-game weighting is a sensitivity. These intervals condition on the fitted models and recorded history path. Repeated players/teams and histories updated between test games can create cross-game dependence, so also inspect calendar-block sensitivity and the frozen-history result. Thirty-three test games, not 18,158 independent throws, limit confidence in small improvements.

Prespecify secondary views: the two outcome definitions, all-distance cohort, history-size groups, regular season versus playoffs, and hucks (distance **>40 yards** and forward gain **>30 yards**; 858 test attempts). Do not tune a new model separately on the test hucks. Use a modest flexible CP-only recalibration and history-volume controls as development-stage checks if C appears beneficial, to test whether it is merely correcting residual calibration or role/volume differences. Defer detailed location effects, recency, receivers, and Gower distance until the simple comparison earns that complexity.

**What can start, and what still needs clarification.** Start now with the frozen cohort, auditable prior-game features, a locked small model comparison, and a prediction ledger keyed by game and throw. Before a strong paper claim, obtain from the model owner: (1) production model version and training/tuning game cutoff, including explicit 2026 exclusion; (2) label code for drops and short throws; (3) older prediction provenance and fold/version identifiers; (4) availability/timing of CP inputs and saved predictions. An authorized artifact/metadata export from the discovered tables is a concrete next lead; changing database permissions is unnecessary for this assessment.

Prior audit flags also need tracking: four 2026 games have raw event-stream/final-score discrepancies; check results excluding these games without importing the old possession filters. The older `gamesWithMissingCp: 7` field counts **player-game groups** in its code: the 18 affected throws belong to seven players in **one game**. Record that correction here without rewriting the earlier evidence. Repeated roster identities and same-name/different-ID players must not inflate joins or merge histories.

A positive result would show incremental predictive information under this design—not isolated innate throwing skill, causal player effects, or a better official CPOE metric. Team systems, receiver quality, throw selection, and recording practices remain possible explanations. Prior project work has already examined 2026; describe this as a locked retrospective comparison, not a newly untouched prospective season. A later season should confirm any promising result. A small or null improvement is a defensible finding.

**Evidence and reproduction.** Run `python3 research/thrower_history_cp/audit_feasibility.py` from the project root. It verifies all five export hashes and writes `audit.json`; it does not fit models, alter exports, or touch the website. Companion files: `database_checks.sql` and `database_readonly_receipt.json`. Prior evidence consulted: `data/database-metadata/2026-11-04/throw-metric-validation.json`, `analysis/multiseason_release_validation.json`, `research/oline_possessions/cohort_audit.json`, and the corresponding source scripts. Current manuscript: `/Users/teddytaussig/Desktop/Work/Nature_AI_in_Sports/journal_of_statistics_and_data_science_in_sports/submission/JSDSS_manuscript.docx` (Methods §§4.1–4.2; Limitations §7.1).
