# First modeling results

These are development results from the agreed fitting and validation periods. The 33-game final test period remains unscored. Validation helps choose the model and settings; its results do not establish a final improvement.

The original xCP model's exclusion of 2026 remains unverified. Drops receive thrower completion credit. The original cp and cpoe values are retained unchanged.

## Data and timing

| Period | Observed game dates | Games | Throws |
|---|---|---:|---:|
| Fit | 2026-04-24 to 2026-06-14 | 80 | 43,791 |
| Validate | 2026-06-18 to 2026-07-05 | 29 | 15,737 |
| Reserved test | 2026-07-10 to 2026-08-28 | 33 | 18,158 |

The split boundaries remain June 14 and July 5; the first recorded validation and test games occur on June 18 and July 10, respectively.

Player histories use eligible 2026 throws on strictly earlier game dates. All games on the same date share frozen history. Unknown throwers and players without history receive B. No O-line, possession-number, long-field, or receiver-availability restrictions are applied.

## Validation probability scores

Lower log loss and Brier score are better. All four versions are scored on the same 15,737 throws.

| Model | Log loss | Brier score | Mean prediction | Completion-credit rate |
|---|---:|---:|---:|---:|
| A Original xCP | 0.153543 | 0.039914 | 94.86% | 95.09% |
| B General recalibration | 0.153631 | 0.039898 | 94.77% | 95.09% |
| C1 History summary | 0.152928 | 0.039710 | 94.80% | 95.09% |
| C2 Partially pooled player model | 0.153085 | 0.039770 | 94.80% | 95.09% |

Validation selected **k = 800** for C1. The better history candidate was **C1**; the preferred model including the general recalibration was **C1**.

The selected k is at the upper end of the prespecified grid. Its advantage remains uncertain, and this grid does not establish an optimal k. Check the effect of history length before final testing. The fitted history coefficient also changes with k, so k alone does not describe how much the final prediction changes.

## Game-level uncertainty

Differences below are new model minus reference, so negative values favor the new model. Each of 10,000 bootstrap samples resamples whole games with the same sampled games for both models. These descriptive intervals use validation data that also selected the models and condition on the fitted coefficients and recorded history path. Final testing also requires the planned calendar-week and frozen-history checks.

| Comparison | Log-loss difference | 95% game-bootstrap interval |
|---|---:|---:|
| B minus A | +0.000089 | [-0.000041, +0.000212] |
| C1 minus B | -0.000704 | [-0.001920, +0.000212] |
| C2 minus B | -0.000546 | [-0.002113, +0.000652] |

## Model details

B fits a shared logistic recalibration of saved xCP. C1 adds the shrunk history summary and fits shared coefficients on all fitting rows. At prediction time, its explicit no-history fallback uses B. C2 estimates a normal distribution of player adjustments by marginal likelihood on known-thrower fitting rows, then averages probabilities over each player’s posterior using only earlier games. Unknown-thrower rows do not form a shared player group.

C2 estimated a player-adjustment standard deviation of 0.4593 on the log-odds scale. Numerical integration was checked at a higher quadrature order using only fitting likelihoods.

| C1 k | Validation log loss | Validation Brier | History coefficient c |
|---:|---:|---:|---:|
| 0 | 0.153405 | 0.039856 | 1.6137 |
| 10 | 0.153281 | 0.039828 | 4.3000 |
| 25 | 0.153213 | 0.039805 | 6.2334 |
| 50 | 0.153147 | 0.039783 | 8.8093 |
| 100 | 0.153073 | 0.039758 | 13.2080 |
| 200 | 0.153006 | 0.039736 | 21.0789 |
| 400 | 0.152957 | 0.039720 | 35.7926 |
| 800 | 0.152928 | 0.039710 | 64.2201 |

## Calibration

The calibration intercept and slope describe the validation predictions; they are never applied to change those probabilities. Their ideal values are 0 and 1. The plot uses the prespecified probability bins and shows the number of throws in each bin.

| Model | Calibration intercept | Calibration slope | Observed minus predicted |
|---|---:|---:|---:|
| A Original xCP | 0.0528 | 1.0019 | +0.230 pp |
| B General recalibration | 0.0244 | 1.0249 | +0.327 pp |
| C1 History summary | 0.0197 | 1.0239 | +0.297 pp |
| C2 Partially pooled player model | 0.0417 | 1.0138 | +0.294 pp |

Plot: `artifacts/validation_calibration.png`. Bin counts and means: `artifacts/validation_calibration.csv`.

## What remains before final conclusions

- Verify the original xCP training/tuning cutoff, model version, and production minimum distance.
- Complete the planned development checks for flexible xCP-only recalibration and history length; settle their exact specifications before final test scoring.
- Refit the settled models on fitting plus validation games, then evaluate the later games with whole-game uncertainty and the planned sensitivity analyses.
- Interpret any gain as predictive information in earlier performance. Team systems, receiver quality, and throw selection can contribute to that information.

## Reproduction

Run `python -m unittest discover -s research/thrower_history_cp -p "test_modeling.py"`, then `python research/thrower_history_cp/run_modeling.py` in the project environment. The protocol, code hashes, package versions, convergence diagnostics, and model selection are recorded in `modeling_results.json`. Throw-level extracts and predictions stay in the Git-ignored `artifacts/` folder. This command never fits on, predicts, or scores the final test period.
