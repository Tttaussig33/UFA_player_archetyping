"""Reconcile completed film labels and score the predictions frozen before review.

Keep the original development archive and pilot untouched. Current labels and
source-based inventory updates are derived files, not changes to source events.
"""
from collections import Counter
from datetime import datetime
from pathlib import Path
import hashlib
import json
import math

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp(review):
    value = review.get('reviewedOn') or review.get('date') or '1970-01-01'
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def metrics(rows):
    valid = [r for r in rows if r['scorable']]
    centering = [r for r in valid if r['review']['decision'] == 'setup1']
    other = [r for r in valid if r['review']['decision'] == 'attack1']
    return {'n': len(valid), 'correct': sum(r['correct'] for r in valid),
            'centering': len(centering), 'centering_correct': sum(r['correct'] for r in centering),
            'no_centering': len(other), 'no_centering_correct': sum(r['correct'] for r in other),
            'false_centering': [r['caseId'] for r in other if not r['correct']],
            'missed_centering': [r['caseId'] for r in centering if not r['correct']]}


def main():
    paths = {
        'frozen_pilot': HERE / 'opening_classifier_pilot.json',
        'original_archive': HERE / 'annotations/reviewed_decisions.json',
        'browser_export': HERE / 'annotations/2026-11-13-classifier-pilot-browser-export.json',
        'chat_confirmations': HERE / 'annotations/classifier-pilot-chat-confirmations.json',
        'definition': HERE / 'centering_definition.json',
        'inventory': HERE / 'opening_pass_feasibility.json',
        'library': HERE / 'film_library.json',
    }
    inputs = {k: {'path': str(p.relative_to(ROOT)), 'sha256': sha(p)} for k, p in paths.items()}
    loaded = {k: json.loads(p.read_text()) for k, p in paths.items()}
    pilot, batch = loaded['frozen_pilot'], loaded['frozen_pilot']['prospective_batch']
    assert inputs['original_archive']['sha256'] == pilot['inputs']['reviews']['sha256']
    assert inputs['inventory']['sha256'] == pilot['inputs']['inventory']['sha256']
    cases = {c['possessionId']: c for c in loaded['library']['cases']}
    current, provenance = {}, {}
    # Preserve each reviewed object verbatim; no timestamp stamping to make an
    # older or incomplete browser version appear to be the latest decision.
    for source in ['original_archive', 'browser_export', 'chat_confirmations']:
        seen = set()
        for review in loaded[source]['reviews']:
            pid = review['possessionId']
            assert pid not in seen
            seen.add(pid)
            assert pid in cases and cases[pid]['id'] == review['caseId']
            if pid not in current or stamp(review) >= stamp(current[pid]):
                current[pid], provenance[pid] = review, inputs[source]
    old = loaded['original_archive']['reviews']
    assert all(current[r['possessionId']] == r for r in old), 'Older reviews changed: audit the differences.'
    assert len(current) == 65
    consolidated = {
        'updatedOn': '2026-11-13', 'timezone': 'America/New_York',
        'policy': 'Latest explicit review wins by timestamp. Preserve the original development archive and predictions. Adjacent-play Callahan is not a sampled pilot case.',
        'reviews': list(current.values()), 'provenance': provenance, 'inputs': inputs,
    }
    write(HERE / 'annotations/current_reviewed_decisions.json', consolidated)
    inv = {r['possession_id']: r for r in loaded['inventory']['rows'] if r['physical_throws']}
    rows = []
    for clip in batch['clips']:
        review = current[clip['possessionId']]
        source = inv[clip['possessionId']]
        assert clip['possessionId'] not in pilot['model']['full_fit']['training_ids']
        assert review.get('currentReviewExposesSuggestion') is False
        assert cases[clip['possessionId']]['ownPossession'] == 1
        scorable = review['decision'] in ('setup1', 'attack1') and not source['label_alignment_hold']
        first = cases[clip['possessionId']]['throws'][0]
        if review['decision'] == 'setup1':
            assert source['first_attempt_event_type'] in (18, 19)
        rows.append({
            'caseId': clip['caseId'], 'possessionId': clip['possessionId'], 'gameId': clip['gameId'],
            'team': clip['team'], 'selectionGroup': clip['selectionGroup'],
            'frozenPrediction': clip['frozenPrediction'], 'review': review,
            'scorable': scorable, 'correct': scorable and clip['frozenPrediction'] == review['decision'],
            'firstThrow': first, 'sourceCompleted': source['first_attempt_event_type'] in (18, 19),
            'contextRuleApplies': review.get('context') in ('brick', 'sideline'),
            'source': provenance[clip['possessionId']],
        })
    assert len(rows) == 12 and all(r['scorable'] for r in rows)
    groups = {k: metrics([r for r in rows if r['selectionGroup'] == k])
              for k in sorted({r['selectionGroup'] for r in rows})}
    # These subsets are diagnostics defined after film review, not new tests.
    geometry_needed = [r for r in rows if not r['contextRuleApplies'] and r['sourceCompleted']]
    evaluation = {
        'id': 'completed-opening-pilot-20261113', 'updatedOn': '2026-11-13',
        'status': 'All 12 sampled openings classified; not ready for automatic centering deductions.',
        'definitionVersion': loaded['definition']['version'],
        'overall': metrics(rows), 'bySelectionGroup': groups,
        'completedNonRestartSubset': metrics(geometry_needed),
        'newGameCount': len({r['gameId'] for r in rows if r['selectionGroup'] == 'new_game_check'}),
        'borderlineNoteCaseId': 'R163',
        'limitations': [
            'Only 12 selected openings from five games; the four new-game openings all come from one game.',
            'The batch mixes random available clips, selected near-threshold cases, and a new-game check. It does not estimate league-wide accuracy.',
            'Two first attempts were incomplete and three were film-confirmed brick/sideline starts. Removing those easy exclusions leaves seven completed, non-restart openings.',
            'The target was clarified during review to require a completed centering transfer. Predictions were not refit; this is a diagnostic under the clarified definition, not validation of an unchanged protocol.',
            'The Houston point-13 Callahan was an adjacent play; the intended point 14 was separately confirmed. Only point 14 is scored in this batch.',
        ],
        'nextStep': 'Use existing explicit rules and verified labels; keep geometry predictions as review suggestions. Check how unresolved centering labels could change the possession comparisons before expanding film review.',
        'rows': rows, 'inputs': inputs,
        'validation': {'predictionsUnchanged': True, 'original52ReviewsUnchanged': True,
                       'all12IdsMatched': True, 'predictionsHiddenDuringReview': True,
                       'noModelRefit': True, 'noLeaguePredictedLabels': True},
    }
    assert evaluation['overall']['correct'] == 10
    assert evaluation['overall']['false_centering'] == ['R007', 'R062']
    write(HERE / 'completed_classifier_pilot_2026-11-13.json', evaluation)

    # Refresh a separate working inventory. Incompletions cannot be completed
    # transfers under the user's clarified definition; this is not an intent label.
    inventory_rows = []
    for pid, row in inv.items():
        review = current.get(pid)
        label = review.get('decision') if review else None
        exact_brick = math.isclose(row['tx'], 0, abs_tol=1e-8, rel_tol=0) and math.isclose(row['ty'], 40, abs_tol=1e-8, rel_tol=0)
        incomplete = row['first_attempt_event_type'] in (20, 22, 23)
        context_rule = bool(review and review.get('context') in ('brick', 'sideline'))
        reasons = [name for name, applies in [('exact_brick_user_rule', exact_brick),
                    ('film_confirmed_brick_or_sideline', context_rule),
                    ('first_attempt_incomplete', incomplete)] if applies]
        conflict = label == 'setup1' and bool(reasons)
        blocked = bool(row['coordinate_hold'] or row['label_alignment_hold'])
        effective = None if conflict or blocked else label if label in ('setup1', 'attack1') else 'attack1' if reasons else None
        status = 'conflict' if conflict else 'source_hold' if blocked else 'reviewed' if label in ('setup1', 'attack1') else 'rule_labeled' if reasons else 'needs_review'
        inventory_rows.append({
            'possession_id': pid, 'game_id': row['game_id'], 'team': row['team'],
            'source_first_attempt_type': row['first_attempt_event_type'],
            'review_case': review['caseId'] if review else row['review_case'],
            'human_label': label, 'human_context': review.get('context') if review else None,
            'effective_label': effective, 'status': status, 'rule_basis': reasons,
            'first_attempt_original_line': row['first_attempt_original_line'],
            'opening_missing_from_film': row['opening_missing_from_film'],
            'original_start': [row['tx'], row['ty']],
        })
    counts = Counter(r['status'] for r in inventory_rows)
    working = {
        'updatedOn': '2026-11-13', 'definitionVersion': loaded['definition']['version'],
        'scope': 'Same 5,720 recorded first throws. No new original-line or field-position exclusions.',
        'counts': {'total': len(inventory_rows), 'statuses': dict(counts),
                   'classified': sum(r['effective_label'] is not None for r in inventory_rows),
                   'unresolved': sum(r['effective_label'] is None for r in inventory_rows),
                   'first_attempt_incomplete': sum('first_attempt_incomplete' in r['rule_basis'] for r in inventory_rows),
                   'new_incomplete_rule_labels': sum(r['status'] == 'rule_labeled' and r['rule_basis'] == ['first_attempt_incomplete'] for r in inventory_rows)},
        'policy': 'Preserve exact-brick conflict and coordinate/alignment holds. No back-line, near-brick or sideline coordinate-only extrapolation. Incomplete first attempts mean no completed centering transfer, not no throw and not known attacking intent.',
        'leagueMetricsChanged': False, 'modelLabelsUsed': False, 'rows': inventory_rows, 'inputs': inputs,
    }
    assert len(inventory_rows) == 5720 and sum(counts.values()) == 5720
    write(HERE / 'current_opening_label_inventory.json', working)
    assert all(sha(paths[k]) == v['sha256'] for k, v in inputs.items())
    print(json.dumps({'pilot': evaluation['overall'], 'completedNonRestartSubset': evaluation['completedNonRestartSubset'],
                      'selectionGroups': groups, 'inventory': working['counts']}, indent=2))


if __name__ == '__main__':
    main()
