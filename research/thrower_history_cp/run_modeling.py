"""Run the prespecified first fitting/validation comparison. Never scores test throws.

Run from the project root:
    .venv/bin/python research/thrower_history_cp/run_modeling.py
"""
from __future__ import annotations

import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy.special import expit

from modeling_data import HERE, ROOT, load_cohort, sha256
from modeling_evaluation import calibration_table, paired_game_bootstrap, plot_calibration, score
from modeling_models import c1_design, fit_c2, fit_logistic, predict_c1, predict_c2_online, xcp_design


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def write_report(result):
    models = result['validation_scores']
    selection = result['selection']
    lines = [
        '# First modeling results', '',
        'These are development results from the agreed fitting and validation periods. '
        'The 33-game final test period remains unscored. Validation helps choose the model and settings; '
        'its results do not establish a final improvement.', '',
        f"The original xCP model's exclusion of 2026 remains unverified. Drops receive thrower completion credit. "
        'The original cp and cpoe values are retained unchanged.', '',
        '## Data and timing', '',
        '| Period | Observed game dates | Games | Throws |', '|---|---|---:|---:|']
    for part, title in [('fit', 'Fit'), ('validation', 'Validate'), ('test', 'Reserved test')]:
        row = result['cohort']['splits'][part]
        lines.append(f"| {title} | {row['first_date']} to {row['last_date']} | {row['games']} | {row['throws']:,} |")
    lines.extend(['', 'The split boundaries remain June 14 and July 5; the first recorded validation and test games '
                  'occur on June 18 and July 10, respectively.', '',
                  'Player histories use eligible 2026 throws on strictly earlier game dates. '
                  'All games on the same date share frozen history. Unknown throwers and players without history '
                  'receive B. No O-line, possession-number, long-field, or receiver-availability restrictions are applied.', '',
                  '## Validation probability scores', '',
                  'Lower log loss and Brier score are better. All four versions are scored on the same 15,737 throws.', '',
                  '| Model | Log loss | Brier score | Mean prediction | Completion-credit rate |',
                  '|---|---:|---:|---:|---:|'])
    for name, row in models.items():
        lines.append(f"| {name} | {row['log_loss']:.6f} | {row['brier']:.6f} | {100*row['mean_prediction']:.2f}% | {100*row['completion_credit_rate']:.2f}% |")
    lines.extend(['', f"Validation selected **k = {selection['c1_k']}** for C1. "
                  f"The better history candidate was **{selection['history_candidate']}**; "
                  f"the preferred model including the general recalibration was **{selection['preferred_model']}**.", '',
                  ('The selected k is at the upper end of the prespecified grid. Its advantage remains uncertain, '
                   'and this grid does not establish an optimal k. Check the effect of history length before final '
                   'testing. The fitted history coefficient also changes with k, so k alone does not describe '
                   'how much the final prediction changes.' if selection['c1_upper_grid_boundary'] else
                   'The selected k is inside the prespecified grid.'), '',
                  '## Game-level uncertainty', '',
                  'Differences below are new model minus reference, so negative values favor the new model. '
                  'Each of 10,000 bootstrap samples resamples whole games with the same sampled games for both models. '
                  'These descriptive intervals use validation data that also selected the models and condition on '
                  'the fitted coefficients and recorded history path. Final testing also requires the planned '
                  'calendar-week and frozen-history checks.', '',
                  '| Comparison | Log-loss difference | 95% game-bootstrap interval |',
                  '|---|---:|---:|'])
    for name, row in result['validation_comparisons'].items():
        metric = row['metrics']['log_loss']
        low, high = metric['game_bootstrap_95_interval']
        lines.append(f"| {name} | {metric['difference']:+.6f} | [{low:+.6f}, {high:+.6f}] |")
    lines.extend(['', '## Model details', '',
                  'B fits a shared logistic recalibration of saved xCP. C1 adds the shrunk history summary '
                  'and fits shared coefficients on all fitting rows. At prediction time, its explicit no-history '
                  'fallback uses B. C2 estimates a normal distribution of player adjustments by marginal likelihood '
                  'on known-thrower fitting rows, then averages probabilities over each player’s posterior '
                  'using only earlier games. Unknown-thrower rows do not form a shared player group.', '',
                  f"C2 estimated a player-adjustment standard deviation of {result['coefficients']['C2']['tau']:.4f} "
                  'on the log-odds scale. Numerical integration was checked at a higher quadrature order using '
                  'only fitting likelihoods.', '',
                  '| C1 k | Validation log loss | Validation Brier | History coefficient c |',
                  '|---:|---:|---:|---:|'])
    for row in result['c1_grid']:
        lines.append(f"| {row['k']} | {row['validation']['log_loss']:.6f} | {row['validation']['brier']:.6f} | {row['coefficients']['c']:.4f} |")
    lines.extend(['', '## Calibration', '',
                  'The calibration intercept and slope describe the validation predictions; they are never applied '
                  'to change those probabilities. Their ideal values are 0 and 1. The plot uses the prespecified '
                  'probability bins and shows the number of throws in each bin.', '',
                  '| Model | Calibration intercept | Calibration slope | Observed minus predicted |',
                  '|---|---:|---:|---:|'])
    for name, row in models.items():
        lines.append(f"| {name} | {row['calibration_intercept']:.4f} | {row['calibration_slope']:.4f} | {row['observed_minus_predicted_percentage_points']:+.3f} pp |")
    lines.extend(['', 'Plot: `artifacts/validation_calibration.png`. Bin counts and means: `artifacts/validation_calibration.csv`.', '',
                  '## What remains before final conclusions', '',
                  '- Verify the original xCP training/tuning cutoff, model version, and production minimum distance.',
                  '- Complete the planned development checks for flexible xCP-only recalibration and history length; '
                  'settle their exact specifications before final test scoring.',
                  '- Refit the settled models on fitting plus validation games, then evaluate the later games with '
                  'whole-game uncertainty and the planned sensitivity analyses.',
                  '- Interpret any gain as predictive information in earlier performance. Team systems, receiver '
                  'quality, and throw selection can contribute to that information.', '',
                  '## Reproduction', '',
                  'Run `python -m unittest discover -s research/thrower_history_cp -p "test_modeling.py"`, then '
                  '`python research/thrower_history_cp/run_modeling.py` in the project environment. '
                  'The protocol, code hashes, package versions, convergence diagnostics, and model selection '
                  'are recorded in `modeling_results.json`. Throw-level extracts and predictions stay in the '
                  'Git-ignored `artifacts/` folder. This command never fits on, predicts, or scores the final test period.', ''])
    (HERE / 'modeling_results.md').write_text('\n'.join(lines))


def main():
    protocol_path = HERE / 'modeling_protocol.json'
    protocol = json.loads(protocol_path.read_text())
    if protocol['c1_k_grid'] != [0, 10, 25, 50, 100, 200, 400, 800]:
        raise ValueError('Changing the declared model grid requires a reviewed protocol revision')
    artifacts = HERE / 'artifacts'
    artifacts.mkdir(exist_ok=True)
    print('Verifying export hashes and building the audited cohort...', flush=True)
    cohort, cohort_summary = load_cohort()
    # The raw extract has already been audited. Save its split assignments, then remove test rows
    # from the entire fitting/validation pipeline, including posterior updates and diagnostics.
    cohort.to_csv(artifacts / 'eligible_2026_throws.csv.gz', index=False)
    development = cohort.loc[cohort.research_split.ne('test')].reset_index(drop=True)
    if not development.research_date.le(protocol['validation_end']).all():
        raise AssertionError('Later throws entered development')
    fit = development.loc[development.research_split.eq('fit')].copy()
    valid_mask = development.research_split.eq('validation').to_numpy()
    validation = development.loc[valid_mask].copy()
    del cohort
    y_fit, y_valid = fit.research_y.to_numpy(), validation.research_y.to_numpy()
    print(f'Fitting B on {len(fit):,} throws; validation contains {len(validation):,} throws.', flush=True)
    b, b_diagnostics = fit_logistic(xcp_design(fit), y_fit, [0, 1])
    b_all = expit(xcp_design(development) @ b)
    b_valid = b_all[valid_mask]
    grid, candidates = [], {}
    for k in protocol['c1_k_grid']:
        beta, diagnostics = fit_logistic(c1_design(fit, k), y_fit, [*b, 0])
        predictions = predict_c1(validation, beta, k, b_valid)
        metrics = score(y_valid, predictions)
        grid.append({'k': k, 'coefficients': {'a': float(beta[0]), 'b': float(beta[1]), 'c': float(100*beta[2])},
                     'validation': metrics, 'fit_diagnostics': diagnostics})
        candidates[k] = (beta, predictions)
        print(f"C1 k={k}: validation log loss {metrics['log_loss']:.6f}", flush=True)
    minimum = min(row['validation']['log_loss'] for row in grid)
    chosen_k = max(row['k'] for row in grid if row['validation']['log_loss'] <= minimum + 1e-10)
    print('Fitting C2 population parameters and checking numerical integration...', flush=True)
    c2, order, c2_diagnostics = fit_c2(fit, b, protocol['quadrature_orders'],
                                     protocol['quadrature_mean_log_likelihood_tolerance'])
    c2_all = predict_c2_online(development, c2, order, b_all)
    probabilities = {'A Original xCP': validation.cp.to_numpy(), 'B General recalibration': b_valid,
                     'C1 History summary': candidates[chosen_k][1], 'C2 Partially pooled player model': c2_all[valid_mask]}
    scores = {name: score(y_valid, values) for name, values in probabilities.items()}
    b_name, c1_name, c2_name = list(probabilities)[1:]
    history_choice = 'C1' if scores[c1_name]['log_loss'] <= scores[c2_name]['log_loss'] + 1e-10 else 'C2'
    history_name = c1_name if history_choice == 'C1' else c2_name
    preferred = history_choice if scores[history_name]['log_loss'] < scores[b_name]['log_loss'] - 1e-10 else 'B'
    selection = {'c1_k': chosen_k, 'history_candidate': history_choice, 'preferred_model': preferred,
                 'c1_upper_grid_boundary': chosen_k == max(protocol['c1_k_grid']),
                 'selected_using': 'Validation mean log loss only', 'test_performance_inspected': False}
    comparisons = {}
    for label, new, reference in [('B minus A', b_name, 'A Original xCP'),
                                   ('C1 minus B', c1_name, b_name), ('C2 minus B', c2_name, b_name)]:
        comparisons[label] = paired_game_bootstrap(y_valid, probabilities[new], probabilities[reference],
                                                   validation.GameID.to_numpy(), protocol['bootstrap_replicates'],
                                                   protocol['bootstrap_seed'])
    output_columns = ['GameID', 'throw_sig_id', 'research_date', 'research_player_id',
                      'cp', 'cpoe', 'research_y', 'research_prior_n', 'research_prior_games',
                      'research_prior_residual_sum', 'research_latest_history_date',
                      'research_huck', 'research_playoff']
    saved_predictions = validation[output_columns].copy()
    for key, values in zip(['A', 'B', 'C1', 'C2'], probabilities.values()):
        saved_predictions[f'research_{key}_probability'] = values
        saved_predictions[f'research_{key}_outcome_minus_prediction'] = y_valid - values
    saved_predictions.to_csv(artifacts / 'validation_predictions.csv.gz', index=False)
    calibration = calibration_table(y_valid, probabilities, protocol['calibration_bin_edges'])
    calibration.to_csv(artifacts / 'validation_calibration.csv', index=False)
    plot_calibration(calibration, artifacts / 'validation_calibration.png')
    code_files = ['modeling_data.py', 'modeling_models.py', 'modeling_evaluation.py', 'run_modeling.py', 'test_modeling.py']
    result = {'created_at_utc': datetime.now(timezone.utc).isoformat(), 'protocol': protocol,
              'protocol_sha256': sha256(protocol_path), 'research_plan_sha256': sha256(HERE / 'research_plan.md'),
              'code_sha256': {name: sha256(HERE / name) for name in code_files},
              'environment': {'python': platform.python_version(), 'numpy': np.__version__,
                              'pandas': pd.__version__, 'scipy': scipy.__version__},
              'git_head_at_run': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'cohort': cohort_summary, 'test_scored': False,
              'validation_scores': scores, 'validation_comparisons': comparisons,
              'c1_grid': grid, 'selection': selection,
              'coefficients': {'B': {'a': float(b[0]), 'b': float(b[1])},
                               'C1': next(row['coefficients'] for row in grid if row['k'] == chosen_k),
                               'C2': {'a': float(c2[0]), 'b': float(c2[1]), 'tau': float(c2[2]),
                                      'prediction_quadrature_order': order}},
              'fit_diagnostics': {'B': b_diagnostics, 'C2': c2_diagnostics}}
    write_json(HERE / 'modeling_results.json', result)
    write_json(HERE / 'validation_selection.json', {'protocol_sha256': result['protocol_sha256'],
                                                  **selection, 'coefficients': result['coefficients']})
    write_report(result)
    print(json.dumps({'validation_scores': scores, 'selection': selection, 'test_scored': False}, indent=2), flush=True)


if __name__ == '__main__':
    main()
