"""Independent Newton-method check of the frozen classifier diagnostic.

Does not import the model implementation or alter reviews/research metrics.
Run with the existing possession-analysis Python environment.
"""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
data = json.loads((HERE / 'database_classifier_check_2026-11-15.json').read_text())
rows = {r['possession_id']: r for r in data['rows']}
errors = []
for fold in data['folds']:
    test = rows[fold['testId']]
    train = [rows[i] for i in fold['fit']['training_ids']]
    assert all(r['game_id'] != fold['heldOutGame'] for r in train)
    features = fold['fit']['features']
    x = np.array([[r[f] for f in features] for r in train])
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale == 0] = 1
    z = np.column_stack([np.ones(len(train)), (x - mean) / scale])
    y = np.array([int(r['human_label'] == 'setup1') for r in train])
    penalty = np.diag([0.] + [fold['fit']['penalty']] * len(features))
    beta = np.zeros(len(features) + 1)
    for iteration in range(100):
        probability = 1 / (1 + np.exp(-(z @ beta)))
        gradient = z.T @ (probability - y) + penalty @ beta
        hessian = z.T @ ((probability * (1-probability))[:, None] * z) + penalty
        step = np.linalg.solve(hessian, gradient)
        beta -= step
        if np.max(np.abs(step)) < 1e-10:
            break
    else:
        raise AssertionError('Independent Newton fit did not converge')
    test_x = np.r_[1, (np.array([test[f] for f in features]) - mean) / scale]
    score = float(1 / (1 + np.exp(-(test_x @ beta))))
    errors.append(abs(score - test['heldOutScore']))
    assert ('setup1' if score >= .5 else 'attack1') == test['heldOutPrediction']

assert max(errors) < 1e-5
assert sum(r['human_label'] == r['heldOutPrediction'] for r in rows.values()) == 7
assert sum(r['human_label'] == 'attack1' and r['heldOutPrediction'] == 'setup1' for r in rows.values()) == 3
assert sum(r['human_label'] == 'setup1' and r['heldOutPrediction'] == 'attack1' for r in rows.values()) == 2
for record in data['inputs'].values():
    assert hashlib.sha256((ROOT / record['path']).read_bytes()).hexdigest() == record['sha256'], record['path']

receipt_path = HERE / 'database_classifier_validation_2026-11-15.json'
receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
receipt.update({
    'checkedOn': '2026-11-15',
    'independentModel': 'Newton-method penalized logistic regression; training-fold-only standardization',
    'heldOutGames': 12,
    'matchingDecisions': 12,
    'maximumProbabilityDifference': max(errors),
    'groupSeparationPassed': True,
    'inputHashesUnchanged': True,
    'aggregateCountsVerified': True,
})
receipt.setdefault('uiVerification', 'pending')
receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
