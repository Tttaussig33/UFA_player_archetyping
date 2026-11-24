**Testing whether thrower history improves ShownSpace xCP**  
Research plan

**1 Research question and available data**

Does a thrower's performance in earlier games improve pass predictions beyond ShownSpace xCP? We can test this using the saved probabilities, outcomes, player identifiers, and game dates. The design assumes **2026 was excluded from the original xCP model's fitting and tuning; this still needs verification**. Model fitting has yet to begin.

Our ShownSpace paper (the October JSDSS submission) [1] supplies the outcome definitions and modeling context. Noel's NHL paper [2] combines baseline probabilities with earlier player performance. We adapt that comparison to throwers and evaluate on later games.

**Data and eligibility**

The export contains 490,688 records across 901 games in 2021–2026. Live database checks matched the season totals. The initial analysis uses 2026:

| Check | Finding and decision |
|---|---|
| Coverage | 78,847 records in 142 games: 131 regular-season and 11 playoff games. |
| Eligible events | 78,784 physical attempts after excluding 63 stalls. Use pass-event codes 18, 19, 20, 22, and 23; exclude pulls and administrative events. |
| Missing xCP | 18 attempts, all in May 2 SLC–OAK. Exclude these from every model's evaluation. All available probabilities are between 0 and 1. |
| Duplicates and coordinates | No duplicates under the audited throw-ID, row, or source-event checks. Coordinates are complete, within field bounds, and consistent with stored distances. |
| Player identifiers | 12 attempts have unknown throwers. Use the general model for them. Join by stable player ID and deduplicate roster records before joining. |
| Missing receivers | 4,363 valid-xCP attempts lack a named receiver. Keep them; requiring a receiver would disproportionately remove unsuccessful passes. |
| Missing games | July 18 PIT–CHI is marked Final with no throws. Two other empty schedule entries remain Upcoming and need clarification. |

Use a primary cohort of throws **at least 1.5 yards**, matching the training range described in our ShownSpace paper: **77,686 throws in 142 games, with 746 named throwers** and nine unknown-thrower attempts. Confirm that the production model uses the same minimum. Repeat the analysis on all 78,766 physical attempts with valid xCP to assess the effect of this cutoff.

Player history is available for **98.8% of named-thrower test attempts**. The median history at a test player-game is **93 attempts across eight games**. Older seasons would provide prior-season history for 555 of 746 players, but we first need to establish which older predictions were produced on the xCP model's own training data.

**2 Outcome and models**

**Outcome definition**

For the outcome, **a completion or recorded receiver drop gives the thrower completion credit (y = 1)**; another incomplete pass has y = 0. This follows xCP's training outcome and CPOE convention.

Build history directly from `y − xCP`. Keep ShownSpace’s original xCP and CPOE unchanged. Save and clearly label each research model’s predictions and corresponding above-expected results separately.

**Model comparison**

| Model | Purpose |
|---|---|
| A Original xCP | Evaluate the saved probabilities. |
| B General recalibration | Fit `logit(q) = a + b × logit(xCP)` to correct shared probability errors. |
| C1 History summary | Add one measure of the thrower's earlier performance to B's predictors. |
| C2 Partially pooled player model | Estimate a player adjustment, pulling uncertain estimates toward the population average. |

**C1 and the choice of k**

Before each game, calculate `h = sum(y − xCP) / (n + k)` from eligible attempts on earlier dates. Here n is the number of those attempts. Fit `logit(q) = a + b × logit(xCP) + c × h`. The coefficients a, b, and c are shared across players.

The setting **k controls how much short histories are pulled toward zero**. With k = 0, h is the raw average; with k = n, the history summary is halved. Use the candidate grid **0, 10, 25, 50, 100, 200, 400, 800**, spanning no shrinkage through strong shrinkage. Fitting and validation player-game histories have medians of 19 and 61 attempts, respectively. These counts motivate the range; validation log loss selects k.

Noel uses Optuna to tune boosted-tree models [2]. Our initial C1 model has one tuning setting, so evaluating every value in a small grid is straightforward. Optuna becomes useful if later models introduce several interacting settings.

**C2 and empirical Bayes**

Soccer's Bayes-xG study [3] provides a precedent for hierarchical player adjustments. We will compare C1 with an empirical-Bayes logistic model: `logit(q) = a + b × logit(xCP) + u_i`, where player adjustments follow `u_i ~ Normal(0, τ²)`. Estimate a, b, and τ by marginal likelihood on fitting games. This learns the amount of pooling from the data. Before each predicted game, average probabilities over the player's updated adjustment distribution using only earlier games.

For both C candidates, players with no usable history and unknown throwers receive B's prediction. Start with cumulative 2026 history and retain players with short histories. Choose k and the preferred C candidate on validation log loss, then lock the choice before testing. If neither C improves on B during validation, retain B as the preferred model and still report both C candidates' test results.

**3 Chronological testing and evaluation**

**Training validation and test periods**

| Stage | 2026 dates | Games | Primary-cohort throws |
|---|---|---:|---:|
| Fit | April 24–June 14 | 80 | 43,791 |
| Validate | June 15–July 5 | 29 | 15,737 |
| Test | July 6–August 28 | 33 | 18,158 |

Use game `StartTimestamp` to order observations. Freeze player history before each game and update it only after all games on that calendar date have finished. During validation, hold model coefficients and C2's population spread fixed while updating player histories. After selecting the settings and preferred C candidate, refit population parameters on fit-plus-validation games and freeze them for testing. Earlier test games may update histories for later test games. This preserves the order in which information becomes available [4].

Saved xCP uses the recorded context of each throw, including destination coordinates. We are evaluating how well earlier player performance helps predict outcomes **given that throw context**. Live prediction would also require checking when those inputs become available.

**Accuracy calibration and uncertainty**

The primary comparison is the validation-selected **C versus B in mean log loss**. A comparison with original xCP shows the total change from the production baseline. Report A, B, C1, and C2 on exactly the same later-game throws, with the unselected C candidate treated as a secondary comparison.

Report log loss and Brier score, where lower values indicate better probability predictions [5]. Use calibration plots with sample counts and calibration intercept/slope [6]. For example, throws assigned 90% should receive the defined outcome about 90% of the time. Keep the evaluated probabilities fixed during test scoring.

Use **10,000 paired whole-game bootstrap resamples**: sample the same games for all models and retain every throw within each sampled game. Report approximate 95% intervals for score differences [7]. Weight throws equally in the primary estimate and repeat with equal game weights. These intervals condition on the fitted models and histories. Repeated players and history updates can connect games, so also check calendar-week blocks and histories frozen on July 5. With **33 test games**, small improvements may remain uncertain.

Before test scoring, specify checks using a more flexible xCP-only calibration and history-length controls. These help determine whether gains reflect player performance, remaining calibration errors, or experience. Keep the original completion-heavy outcome frequencies during fitting.

Secondary analyses cover all valid distances, history-size groups, regular season versus playoffs, and hucks (**distance >40 yards and forward gain >30 yards; 858 test attempts**). Evaluate the locked models on these subsets. Repeat the main comparison after excluding the four games flagged for event-stream/final-score discrepancies. Consider detailed locations, recency, Gower distance, and receiver effects after this comparison.

**4 Next steps and references**

**What still needs clarification**

Confirm the production xCP model version and its training/tuning cutoff, including the exclusion of 2026. Establish whether older saved predictions came from throws used to fit that model or from held-out throws. Obtain the production eligibility rules, input definitions, prediction timestamps, and any existing player-history features. Resolve the empty game records, player-ID corrections, and the difference between the paper's pre-2026 sample and the export's 411,841 pre-2026 records.

The database contains model-artifact and model-version tables, but the current account cannot read their contents. Access to those records or the training code could resolve several of these items.

**Immediate work**

Create the fixed eligible-throw dataset and build histories in game-date order. Score original xCP and fit the recalibration and two history candidates. Use validation to settle the tuning and comparison rules before inspecting test scores. Save predictions by game and throw so the comparisons can be reproduced.

A positive result would show that earlier player performance adds predictive information. Team systems, receiver quality, and throw selection may contribute to that signal. Prior project work has already examined 2026, so describe the evaluation as retrospective and seek confirmation in a later season.

Audit counts and export hashes can be reproduced with `python3 research/thrower_history_cp/audit_feasibility.py`. Supporting records are `audit.json`, `database_checks.sql`, and `database_readonly_receipt.json` in the same research folder.

**References**

[1] Our ShownSpace paper (the October JSDSS submission), §§4.1.1, 4.2, and 4.3.1. Files: `JSDSS_manuscript.docx` and `JSDSS_manuscript.pdf` in `Nature_AI_in_Sports/journal_of_statistics_and_data_science_in_sports/submission/`.

[2] Noel, J. T. P. (2025). *Expected by Whom? A Skill-Adjusted Expected Goals Model for NHL Shooters and Goaltenders*, §§3.3–3.5. [Paper](https://arxiv.org/abs/2511.07703v2).

[3] Scholtes, A., and Karakuş, O. (2024). *Bayes-xG: player and position correction on expected goals (xG) using Bayesian hierarchical approach*. [Paper](https://doi.org/10.3389/fspor.2024.1348983).

[4] Roberts, D. R., et al. (2017). *Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure*. [Paper](https://doi.org/10.1111/ecog.02881).

[5] Gneiting, T., and Raftery, A. E. (2007). *Strictly proper scoring rules, prediction, and estimation*. [Paper](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jasa.pdf).

[6] Van Calster, B., et al. (2019). *Calibration: the Achilles heel of predictive analytics*. [Paper](https://doi.org/10.1186/s12916-019-1466-7).

[7] Field, C. A., and Welsh, A. H. (2007). *Bootstrapping clustered data*. [Paper](https://doi.org/10.1111/j.1467-9868.2007.00593.x).
