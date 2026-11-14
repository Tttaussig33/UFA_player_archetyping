"""Apply the user's brick-start rule without overwriting saved film decisions.

This is a derived opening-label inventory, not a rewrite of source throws or
chart metrics. Sideline coordinates alone do not identify a roller pull.
"""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import json
import math


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inventory_path = HERE / 'opening_pass_feasibility.json'
    inventory = json.loads(inventory_path.read_text())
    # Refuse to apply the rule to an inventory whose underlying cohort changed.
    for name in ['possessions', 'throws', 'review_audit', 'film_library', 'raw_receipt']:
        record = inventory['inputs'][name]
        assert sha(REPO / record['path']) == record['sha256'], name
    raw_folder = HERE.parent / 'dead_disc_study/raw_events'
    pull_keys = Counter()
    raw_pull_types = Counter()
    for gid, expected in inventory['rawGameHashes'].items():
        path = raw_folder / f'{gid}.json'
        assert sha(path) == expected, gid
        data = json.loads(path.read_text())['data']
        for side in ('home', 'away'):
            for event in data[side + 'Events']:
                if event['type'] in (7, 8):
                    pull_keys.update(event.keys())
                    raw_pull_types[event['type']] += 1
    export = REPO / 'data/database-exports/2026-10-12/throws.csv'
    assert sha(export) == inventory['source_export_throws_sha256']
    with export.open(newline='') as handle:
        export_fields = next(csv.reader(handle))
    roller_fields = [key for key in set(export_fields) | set(pull_keys)
                     if 'roll' in key.lower()]
    assert not roller_fields, 'New roller information exists: revisit this audit.'

    rows = []
    for opening in inventory['rows']:
        if opening['physical_throws'] == 0:
            continue
        exact_brick = (math.isclose(opening['tx'], 0, rel_tol=0, abs_tol=1e-8)
                       and math.isclose(opening['ty'], 40, rel_tol=0, abs_tol=1e-8))
        human = opening['human_label']
        # The review UI defines sideline as a roller going out at the sideline.
        # It is a saved human context, never a prediction from x coordinates.
        confirmed_roller = opening['human_context'] == 'sideline' and bool(human)
        if confirmed_roller:
            assert human == 'attack1'
        rule_attack = exact_brick or confirmed_roller
        conflict = bool(rule_attack and human and human != 'attack1')
        status = ('rule_film_conflict' if conflict else
                  'reviewed' if human else
                  'rule_labeled' if rule_attack else 'needs_label')
        effective = None if conflict else human or ('attack1' if rule_attack else None)
        rows.append({
            'possession_id': opening['possession_id'],
            'game_id': opening['game_id'], 'team': opening['team'],
            'tx': opening['tx'], 'ty': opening['ty'],
            'exact_brick_coordinates': exact_brick,
            'film_confirmed_sideline_roller': confirmed_roller,
            'rule_label': 'attack1' if rule_attack else None,
            'rule_basis': [name for name, applies in [
                ('user_exact_brick_coordinate_rule', exact_brick),
                ('film_confirmed_sideline_roller', confirmed_roller)] if applies],
            'saved_human_label': human or None,
            'saved_human_context': opening['human_context'] or None,
            'review_case': opening['review_case'] or None,
            'effective_label': effective, 'status': status,
            'coordinate_hold': opening['coordinate_hold'],
            'label_alignment_hold': opening['label_alignment_hold'],
            'opening_missing_from_film': opening['opening_missing_from_film'],
            'first_attempt_original_line': opening['first_attempt_original_line'],
        })
    ids = {r['possession_id'] for r in rows}
    brick = {r['possession_id'] for r in rows if r['exact_brick_coordinates']}
    reviewed = {r['possession_id'] for r in rows if r['saved_human_label']}
    rollers = {r['possession_id'] for r in rows if r['film_confirmed_sideline_roller']}
    conflicts = [r for r in rows if r['status'] == 'rule_film_conflict']
    unlabeled = ids - brick - reviewed - rollers
    assert len(rows) == len(ids) == 5720
    assert len(brick) == 404 and len(rollers) == 3
    assert len(reviewed) == 38 and len(brick & reviewed) == 5
    assert len(unlabeled) == 5283 and len(conflicts) == 1
    assert len([r for r in rows if r['effective_label']]) + len(conflicts) + len(unlabeled) == len(rows)
    result = {
        'createdOn': '2026-11-13',
        'status': 'User-specified brick rule applied in this derived label inventory; original film decisions and published metrics unchanged.',
        'scope': 'The same 5,720 recorded first throws of receiving-team opening possessions used in the feasibility audit; no additional original-line or field-position filtering.',
        'rules': {
            'exact_brick': {'x': 0, 'y': 40, 'numeric_comparison_tolerance': 1e-8,
                            'first_throw': 'attack1', 'source': 'User instruction in chat, 2026-11-13'},
            'sideline_roller': {'first_throw': 'attack1',
                                'available_evidence': 'Saved film context sideline, defined in the review interface as roller pull goes out of bounds on the sideline.',
                                'automatic_league_wide_count': None},
            'conflicts': 'Keep both the rule suggestion and the saved human label; withhold an effective label until reconciled.',
            'near_brick': 'Starts within one yard are not automatically included in the exact-coordinate rule.'
        },
        'counts': {
            'recorded_opening_first_throws': len(rows),
            'exact_brick_matches': len(brick),
            'remaining_after_exact_brick_only': len(ids - brick),
            'film_confirmed_sideline_rollers': len(rollers),
            'brick_roller_overlap': len(brick & rollers),
            'remaining_after_brick_and_confirmed_rollers': len(ids - brick - rollers),
            'already_reviewed_openings': len(reviewed),
            'already_reviewed_at_exact_brick': len(reviewed & brick),
            'already_reviewed_outside_exact_brick': len(reviewed - brick),
            'new_rule_labels_for_previously_unlabeled': len(brick - reviewed),
            'still_unlabeled': len(unlabeled),
            'rule_film_conflicts': len(conflicts),
            'unlabeled_plus_rule_film_conflicts': len(unlabeled) + len(conflicts),
            'status_counts': dict(Counter(r['status'] for r in rows)),
        },
        'roller_availability': {
            'export_fields': export_fields,
            'raw_pull_event_fields': dict(sorted(pull_keys.items())),
            'raw_pull_event_type_counts': dict(raw_pull_types),
            'explicit_roller_fields_found': roller_fields,
            'sideline_coordinate_candidates_abs_x_at_least_23': sum(abs(r['tx']) >= 23 for r in rows),
            'limitation': 'A sideline first-throw location alone does not distinguish a rolled-out pull from an ordinary pull received near the sideline. Do not subtract all sideline candidates as confirmed rollers.'
        },
        'conflicts': conflicts,
        'inputs': {
            'feasibility_inventory': {'path': str(inventory_path.relative_to(REPO)), 'sha256': sha(inventory_path)},
            'source_export': {'path': str(export.relative_to(REPO)), 'sha256': sha(export)},
            'calculation': {'path': str(Path(__file__).relative_to(REPO)), 'sha256': sha(Path(__file__))},
        },
        'source_freshness': 'Preserved DBeaver export dated 2026-10-12 and previously captured raw events; no live database refresh.',
        'validation': {'source_hashes_verified': True, 'unique_opening_ids': True,
                       'overlap_deduplicated': True, 'all_statuses_reconcile': True,
                       'original_annotations_not_modified': True},
        'rows': rows,
    }
    (HERE / 'opening_start_rule_audit.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result['counts'], indent=2))


if __name__ == '__main__':
    main()
