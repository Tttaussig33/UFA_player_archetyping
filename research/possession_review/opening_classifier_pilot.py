"""Small, retrospective geometry pilot and a frozen prospective film batch.

No inferred labels enter research metrics. Predictions are hidden from the
review form. The existing, deliberately selected labels are development data;
holding out games here does not make this a league accuracy estimate.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import random

import numpy as np
from scipy.optimize import minimize, check_grad
from scipy.special import expit


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FEATURES = ['ty', 'distance', 'inward_gain']
PENALTY = 1.0
SEED = 20261113
BATCH_ID = 'opening-classifier-pilot-20261113-v2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matrix(rows):
    return np.asarray([[r[f] for f in FEATURES] for r in rows], dtype=float)


def fit(rows):
    x = matrix(rows)
    y = np.asarray([r['human_label'] == 'setup1' for r in rows], dtype=float)
    assert len(set(y)) == 2
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale = np.where(scale == 0, 1, scale)
    z = np.column_stack([np.ones(len(rows)), (x-mean)/scale])

    def objective(beta):
        logits = z @ beta
        return np.sum(np.logaddexp(0, logits) - y * logits) + PENALTY/2 * np.dot(beta[1:], beta[1:])

    def gradient(beta):
        grad = z.T @ (expit(z @ beta) - y)
        grad[1:] += PENALTY * beta[1:]
        return grad

    check = float(check_grad(objective, gradient, np.zeros(len(FEATURES)+1)))
    assert check < 1e-5
    optimized = minimize(objective, np.zeros(len(FEATURES)+1), jac=gradient,
                         method='L-BFGS-B', options={'gtol': 1e-9, 'ftol': 1e-12})
    assert optimized.success and np.max(np.abs(gradient(optimized.x))) < 1e-5
    return {'features': FEATURES, 'training_mean': mean.tolist(),
            'training_scale': scale.tolist(), 'coefficients': optimized.x.tolist(),
            'penalty': PENALTY, 'gradient_check_error': check,
            'training_ids': [r['possession_id'] for r in rows]}


def predict(model, rows):
    z = (matrix(rows) - np.asarray(model['training_mean'])) / np.asarray(model['training_scale'])
    return expit(np.column_stack([np.ones(len(rows)), z]) @ np.asarray(model['coefficients']))


def metrics(rows, prediction_key):
    counts = Counter((r['human_label'], r[prediction_key]) for r in rows)
    setup = sum(r['human_label'] == 'setup1' for r in rows)
    attack = len(rows) - setup
    return {'n': len(rows), 'centering_cases': setup, 'immediate_attack_cases': attack,
            'correct_centering': counts['setup1', 'setup1'],
            'correct_immediate_attack': counts['attack1', 'attack1'],
            'attacks_wrongly_called_centering': counts['attack1', 'setup1'],
            'centering_wrongly_called_attack': counts['setup1', 'attack1'],
            'correct_total': counts['setup1', 'setup1'] + counts['attack1', 'attack1']}


def seconds(value):
    total = 0
    for part in value.split(':'):
        total = total * 60 + int(part)
    return total


def main():
    paths = {name: HERE / file for name, file in [
        ('inventory', 'opening_pass_feasibility.json'),
        ('start_rules', 'opening_start_rule_audit.json'),
        ('library', 'film_library.json'),
        ('reviews', 'annotations/reviewed_decisions.json')]}
    original_review_hash = sha(paths['reviews'])
    inventory = json.loads(paths['inventory'].read_text())
    rules = json.loads(paths['start_rules'].read_text())
    library = json.loads(paths['library'].read_text())
    assert rules['inputs']['feasibility_inventory']['sha256'] == sha(paths['inventory'])
    for key in ('possessions', 'throws', 'review_audit', 'film_library'):
        record = inventory['inputs'][key]
        assert sha(REPO / record['path']) == record['sha256']
    rows = {r['possession_id']: r for r in inventory['rows'] if r['physical_throws']}
    rule_rows = {r['possession_id']: r for r in rules['rows']}
    development = [r for r in rows.values()
                   if r['coordinate_development_label'] and r['first_attempt_original_line']
                   and r['human_context'] not in ('brick', 'sideline')
                   and not rule_rows[r['possession_id']]['exact_brick_coordinates']]
    assert len(development) == 27
    assert Counter(r['human_label'] for r in development) == {'setup1': 21, 'attack1': 6}
    assert np.isfinite(matrix(development)).all()
    games = sorted({r['game_id'] for r in development})
    predictions, folds = [], []
    for game in games:
        training = [r for r in development if r['game_id'] != game]
        testing = [r for r in development if r['game_id'] == game]
        model = fit(training)
        assert {r['game_id'] for r in training}.isdisjoint({game})
        for r, score in zip(testing, predict(model, testing)):
            predictions.append({
                'possession_id': r['possession_id'], 'case_id': r['review_case'],
                'game_id': game, 'human_label': r['human_label'],
                'features': {f: r[f] for f in FEATURES},
                'geometry_score_for_centering': float(score),
                'geometry_prediction': 'setup1' if score >= .5 else 'attack1',
                'always_centering_prediction': 'setup1',
                'short_pass_prediction': 'setup1' if r['distance'] <= 30 else 'attack1',
            })
        folds.append({'held_out_game': game, 'test_ids': [r['possession_id'] for r in testing], 'model': model})
    full_model = fit(development)
    excluded = [{ 'case_id': r['review_case'], 'possession_id': r['possession_id'],
                  'human_label': r['human_label'],
                  'reason': 'Film visibility, alignment or coordinate hold' if not r['coordinate_development_label'] else
                            'Known brick or roller context evaluated separately'}
                for r in rows.values() if r['human_label'] and r not in development]

    # Build the prospective pool from the existing accessible-film library.
    # This is not a random sample of the league: these games and Q1s were selected previously.
    candidates = []
    for case in library['cases']:
        r = rows.get(case['possessionId'])
        if (not r or r['human_label'] or case.get('savedReview', {}).get('decision')
                or not case.get('film') or case.get('filmUnavailable')
                or rule_rows[r['possession_id']]['exact_brick_coordinates']
                or not r['first_attempt_original_line'] or r['distance'] <= 0):
            continue
        score = float(predict(full_model, [r])[0])
        candidates.append({'case': case, 'row': r, 'score': score})
    candidates.sort(key=lambda x: x['case']['id'])
    rng = random.Random(SEED)
    # A game with only a reviewed brick/roller still has prior human review.
    # Keep that game out of the genuinely new-game check as well.
    reviewed_games = {r['game_id'] for r in rows.values() if r['human_label']}
    unseen = [c for c in candidates if c['row']['game_id'] not in reviewed_games]
    assert len(unseen) >= 4
    selected = [(c, 'new_game_check') for c in rng.sample(unseen, 4)]
    selected_ids = {c['case']['id'] for c, _ in selected}
    ordinary = [c for c in candidates if c['case']['id'] not in selected_ids and c['row']['game_id'] in reviewed_games]
    # Uniform sample without using outcomes or geometry scores.
    random_sample = rng.sample(ordinary, 4)
    selected.extend((c, 'random_available_opening') for c in random_sample)
    selected_ids.update(c['case']['id'] for c in random_sample)
    uncertain = sorted([c for c in candidates if c['case']['id'] not in selected_ids
                        and c['row']['game_id'] in reviewed_games],
                       key=lambda c: (abs(c['score']-.5), c['case']['id']))
    targeted_per_game = Counter()
    for c in uncertain:
        if targeted_per_game[c['row']['game_id']] >= 2:
            continue
        selected.append((c, 'uncertain_geometry'))
        targeted_per_game[c['row']['game_id']] += 1
        if sum(group == 'uncertain_geometry' for _, group in selected) == 4:
            break
    assert len(selected) == len({c['case']['id'] for c, _ in selected}) == 12
    selected.sort(key=lambda x: (x[0]['row']['game_id'], seconds(x[0]['case']['film']['start'])))
    clips = []
    for c, group in selected:
        case, r = c['case'], c['row']
        clips.append({
            'caseId': case['id'], 'possessionId': r['possession_id'], 'gameId': r['game_id'],
            'team': case['team'], 'videoUrl': case['filmSource']['url'],
            'start': seconds(case['film']['start']), 'end': seconds(case['film']['end']),
            'timingStatus': 'estimated',
            'cue': f"Quarter {case['quarter']}, point starts with {case['pointClock']} remaining. Watch the pull and first two passes; match {case['throws'][0]['from']} to {case['throws'][0]['to']}.",
            'selectionGroup': group,
            'frozenPrediction': 'setup1' if c['score'] >= .5 else 'attack1',
            'uncalibratedGeometryScore': c['score'],
            'predictionShownBeforeReview': False,
            'reviewStatus': 'awaiting_review',
        })
    cohort_counts = Counter(r['human_label'] for r in development)
    result = {
        'id': BATCH_ID, 'createdOn': '2026-11-13',
        'status': 'Exploratory pilot only; no automatic centering labels authorized for research metrics.',
        'question': 'Can first-pass coordinates distinguish centering from immediate attack outside known brick and roller starts?',
        'development': {'n': len(development), 'games': len(games), 'labels': dict(cohort_counts),
                        'eligible_ids': [r['possession_id'] for r in development], 'excluded_reviewed': excluded},
        'model': {'type': 'L2-penalized logistic regression', 'features': FEATURES,
                  'target': 'setup1 = 1; attack1 = 0', 'penalty': PENALTY,
                  'objective': 'sum of binary negative log likelihood + penalty/2 * sum of squared slopes; intercept unpenalized',
                  'standardization': 'Mean and standard deviation calculated on training games only in each fold.',
                  'threshold': .5, 'tuning': 'None; feature set, penalty and threshold fixed before running this pilot.',
                  'excluded_features': ['throw timestamps', 'player/team identity', 'human pull context', 'completion outcome', 'huck outcome', 'possession length', 'eventual score', 'later throws'],
                  'score_warning': 'An uncalibrated ranking score, not a verified probability that the label is correct.',
                  'full_fit': full_model},
        'retrospective_evaluation': {
            'design': 'Leave one entire game out, including both teams; fit and standardize on all other games.',
            'geometry_model': metrics(predictions, 'geometry_prediction'),
            'always_centering': metrics(predictions, 'always_centering_prediction'),
            'short_pass_baseline': metrics(predictions, 'short_pass_prediction'),
            'limit': 'Small, purposefully selected development labels; some past suggestions were visible. These counts are a diagnostic, not independent or league-wide accuracy.',
            'predictions': predictions, 'folds': folds},
        'prospective_batch': {'id': BATCH_ID, 'title': 'Classification pilot · 12 new clips',
            'candidate_pool': len(candidates), 'candidate_games': len({c['row']['game_id'] for c in candidates}),
            'random_seed': SEED, 'caseIds': [c['caseId'] for c in clips], 'clips': clips,
            'selection': 'Four randomly selected openings from a game with no prior human opening labels, four uniformly sampled other available openings, and four near-threshold cases with at most two targeted cases per game.',
            'new_game_ids': sorted({c['row']['game_id'] for c in unseen}),
            'reviewDesign': 'Predictions frozen before review and not shown in the form. Keep new-game, random and targeted checks separate when scoring.',
            'limits': ['The film library consists of purposefully chosen games, mainly first quarters.',
                       'Windows estimated from existing recording anchors; confirm players and point before labeling.',
                       'Do not change model settings after seeing this batch and still describe the batch as untouched validation.',
                       'Wrong-play or invisible-opening responses remain unresolved, never model errors or successes.']},
        'method_references': [
            {'title': 'scikit-learn: Leave One Group Out', 'url': 'https://scikit-learn.org/stable/modules/cross_validation.html#leave-one-group-out'},
            {'title': 'scikit-learn: logistic regression objective', 'url': 'https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression'}],
        'inputs': {name: {'path': str(path.relative_to(REPO)), 'sha256': sha(path)} for name, path in paths.items()},
        'calculation': {'path': str(Path(__file__).relative_to(REPO)), 'sha256': sha(Path(__file__))},
        'validation': {'source_hashes_checked': True, 'game_folds_disjoint': True,
                       'training_only_standardization': True, 'optimizer_and_gradient_verified': True,
                       'review_batch_all_unreviewed': True, 'original_labels_preserved': True,
                       'league_metrics_unchanged': True},
    }
    assert sha(paths['reviews']) == original_review_hash
    out = HERE / 'opening_classifier_pilot.json'
    if out.exists():
        old = json.loads(out.read_text())
        assert old['inputs'] == result['inputs'], 'Pilot already frozen. Start a new version if inputs change.'
        assert old['prospective_batch']['caseIds'] == result['prospective_batch']['caseIds']
    out.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({
        'development_n': len(development), 'games': len(games),
        'geometry': result['retrospective_evaluation']['geometry_model'],
        'always_centering': result['retrospective_evaluation']['always_centering'],
        'short_pass': result['retrospective_evaluation']['short_pass_baseline'],
        'clips': [{k: c[k] for k in ['caseId', 'team', 'start', 'end', 'selectionGroup', 'frozenPrediction']} for c in clips],
        'candidate_pool': len(candidates)}, indent=2))


if __name__ == '__main__':
    main()
