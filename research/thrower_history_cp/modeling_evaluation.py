"""Probability scoring and paired whole-game uncertainty for development data."""
from __future__ import annotations

import numpy as np
import pandas as pd

from modeling_models import fit_logistic, log_odds


def losses(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError('Invalid predicted probabilities')
    clipped = np.clip(p, 1e-12, 1 - 1e-12)
    return {'log_loss': -(y * np.log(clipped) + (1 - y) * np.log1p(-clipped)),
            'brier': (y - p) ** 2}


def score(y, p):
    per_throw = losses(y, p)
    coefficients, _ = fit_logistic(np.column_stack([np.ones(len(p)), log_odds(p)]), y, [0, 1])
    return {'n': len(y), **{key: float(value.mean()) for key, value in per_throw.items()},
            'mean_prediction': float(np.mean(p)), 'completion_credit_rate': float(np.mean(y)),
            'observed_minus_predicted_percentage_points': float(100 * (np.mean(y) - np.mean(p))),
            'calibration_intercept': float(coefficients[0]), 'calibration_slope': float(coefficients[1])}


def paired_game_bootstrap(y, new, reference, game_ids, replicates=10000, seed=20261124):
    new_losses, ref_losses = losses(y, new), losses(y, reference)
    frame = pd.DataFrame({'game': game_ids, 'n': np.ones(len(y), dtype=int),
                          **{metric: new_losses[metric] - ref_losses[metric] for metric in new_losses}})
    games = frame.groupby('game', sort=True).sum()
    n_games = len(games)
    # Multinomial counts are equivalent to sampling n_games whole games with replacement.
    weights = np.random.default_rng(seed).multinomial(n_games, np.full(n_games, 1 / n_games), size=replicates)
    sample_n = weights @ games.n.to_numpy()
    results = {}
    for metric in new_losses:
        sums, n = games[metric].to_numpy(), games.n.to_numpy()
        sampled = (weights @ sums) / sample_n
        game_means = sums / n
        sampled_game_weighted = weights @ game_means / n_games
        results[metric] = {
            'difference': float(sums.sum() / n.sum()),
            'game_bootstrap_95_interval': np.quantile(sampled, [.025, .975]).tolist(),
            'equal_game_weight_difference': float(game_means.mean()),
            'equal_game_weight_95_interval': np.quantile(sampled_game_weighted, [.025, .975]).tolist()}
    return {'games': n_games, 'replicates': replicates, 'seed': seed,
            'direction': 'new minus reference; negative favors new',
            'limitation': 'Development intervals; validation was used to select models. Conditional on fitted models and recorded history path.',
            'metrics': results}


def calibration_table(y, predictions, edges):
    rows = []
    y = np.asarray(y)
    for model, probabilities in predictions.items():
        p = np.asarray(probabilities)
        bins = np.minimum(np.searchsorted(edges, p, side='right') - 1, len(edges) - 2)
        for index, (low, high) in enumerate(zip(edges[:-1], edges[1:])):
            mask = bins == index
            if mask.any():
                rows.append({'model': model, 'lower': low, 'upper': high, 'n': int(mask.sum()),
                             'mean_prediction': float(p[mask].mean()), 'observed_rate': float(y[mask].mean())})
    return pd.DataFrame(rows)


def plot_calibration(table, destination):
    import os
    from pathlib import Path
    cache = Path(destination).parent / 'matplotlib-cache'
    cache.mkdir(exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(cache))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    models = list(dict.fromkeys(table.model))
    fig, (ax, counts_ax) = plt.subplots(1, 2, figsize=(12, 5.8),
                                       gridspec_kw={'width_ratios': [1.25, 1]}, constrained_layout=True)
    colors = ['#6c757d', '#1864ab', '#2b8a3e', '#9c36b5']
    ax.plot([0, 1], [0, 1], '--', color='#a0a0a0', linewidth=1, label='Ideal calibration')
    labels = ['A Original xCP', 'B General recalibration', 'C1 History summary', 'C2 Player model']
    for model, color, label in zip(models, colors, labels):
        rows = table.loc[table.model.eq(model)]
        ax.plot(rows.mean_prediction, rows.observed_rate, 'o-', color=color, linewidth=1.5,
                markersize=4, alpha=.9, label=label)
    ax.set_xlim(0, 1.03); ax.set_ylim(0, 1.03)
    ax.grid(alpha=.15)
    ax.set_xlabel('Mean predicted probability')
    ax.set_ylabel('Observed completion-credit rate')
    ax.legend(loc='lower right', fontsize=9, framealpha=1)
    counts_ax.axis('off')
    counts_ax.set_title('Throws in each probability bin', fontsize=12, pad=15)
    bins = sorted(set(zip(table.lower, table.upper)))
    cells = []
    for low, high in bins:
        label = f'{100*low:g}–<{100*high:g}%' if high < 1 else f'{100*low:g}–{100*high:g}%'
        counts = [int(table.loc[table.model.eq(model) & table.lower.eq(low) & table.upper.eq(high), 'n'].sum()) for model in models]
        cells.append([label, *[f'{count:,}' for count in counts]])
    t = counts_ax.table(cellText=cells, colLabels=['Bin', 'A', 'B', 'C1', 'C2'],
                        loc='center', cellLoc='right', colWidths=[.24, .19, .19, .19, .19])
    t.auto_set_font_size(False); t.set_fontsize(10); t.scale(1, 1.8)
    for (row, col), cell in t.get_celld().items():
        cell.set_edgecolor('#d9d9d9')
        if row == 0:
            cell.set_facecolor('#edf0f2'); cell.set_text_props(weight='bold')
    counts_ax.text(.5, .13, '15,737 throws in 29 games\nBin membership follows each model’s probability.',
                    transform=counts_ax.transAxes, ha='center', fontsize=10)
    fig.suptitle('Validation calibration\nJune 15–July 5, 2026 • Development results used for model selection', fontsize=13)
    fig.savefig(destination, dpi=170)
    plt.close(fig)
