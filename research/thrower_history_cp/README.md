# Thrower history modeling

This folder tests whether earlier thrower performance improves probabilities beyond ShownSpace xCP. The research plan specifies the comparison. The initial executable stage fits A/B/C1/C2 through validation and leaves the later test games unscored.

## Run

From the project root, use a Python 3.12 environment with `requirements.txt` installed:

```sh
.venv/bin/python -m unittest discover -s research/thrower_history_cp -p 'test_modeling.py'
.venv/bin/python research/thrower_history_cp/run_modeling.py
```

The preserved database exports must be present under `data/database-exports/2026-10-12/`. Their SHA-256 hashes and cohort counts must match the prior audit. The program does not query or write to the production database.

## Outputs

- `modeling_protocol.json`: dates, eligibility, labels, history rules, candidate settings, numerical tolerances, scoring and selection rules recorded before fitting.
- `modeling_results.md`: readable first-run results and remaining work.
- `modeling_results.json`: scores, paired game-bootstrap comparisons, fitted coefficients, convergence checks, code/input hashes, and package versions.
- `validation_selection.json`: settings selected from validation, with the protocol hash.
- `artifacts/eligible_2026_throws.csv.gz`: audited cohort, split assignments, original cp/cpoe, and new history fields.
- `artifacts/validation_predictions.csv.gz`: the same validation throws with each model's probability and separately labeled outcome-minus-prediction measure.
- `artifacts/validation_calibration.csv` and `.png`: calibration summaries with sample counts.

Throw-level artifacts remain local and are excluded from Git. Running the command again replaces this stage's derived outputs; source exports and original statistics remain unchanged. No test predictions or test metrics are produced.

## Interpretation and next stage

The exclusion of 2026 from the original xCP fitting/tuning remains a working assumption. Older seasons are excluded from player history until their prediction provenance is established. Completion credit follows the confirmed xCP outcome rule.

Validation selects the history setting and model, so the reported validation differences are preliminary. Before final test scoring, settle the planned flexible xCP-only and history-length checks, then refit on fitting plus validation games. The final comparison needs the research plan's game-grouped uncertainty, cross-game sensitivity checks, and secondary analyses.

The older `audit.json` is retained as the original feasibility record. Its training-label status predates the later confirmation; the current outcome definition is in `research_plan.md` and `modeling_protocol.json`.

## Numerical implementation

C2 integrates the Bernoulli likelihood over a normal player adjustment using Gauss-Hermite quadrature. It fits the shared intercept, xCP slope and player standard deviation by marginal likelihood, checks higher quadrature orders using fitting data only, then integrates predictions over each player's earlier-game posterior. It uses three starting spread values to reduce dependence on initialization. A numerical upper bound of 5 on the log-odds standard deviation is a failure guard: a fit reaching it is rejected.

Independent checks compare the quadrature likelihood and posterior prediction with numerical integration, compare its analytical gradient with finite differences, and verify zero player variation recovers the logistic likelihood. Leakage checks cover same-game/same-date exclusion, future outcome changes, and unknown-player fallbacks.

Implementation references: [SciPy Gauss-Hermite quadrature](https://docs.scipy.org/doc/scipy/reference/generated/scipy.special.roots_hermitenorm.html) and [SciPy optimization](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.minimize.html). The sports-method references are listed in the research plan.
