"""Distance to the attacking goal line after the O-line's first physical pass.

Uses the preserved original-seven study cohort. Does not alter centering labels,
the plotted xCP estimates, or the source records. Standard-library recomputation
independently checks the exploratory pandas calculation.
"""
from pathlib import Path
from math import fsum
from statistics import median
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
P = ROOT / 'eligible_possessions.csv'
E = ROOT / 'eligible_throws.csv'
T = REPO / 'research/oline_possessions/throws.csv'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

sig = json.loads((ROOT / 'team_significance.json').read_text())
for path in (P, E):
    assert digest(path) == sig['inputs'][str(path.relative_to(REPO))]

with P.open() as stream:
    possessions = list(csv.DictReader(stream))
with T.open() as stream:
    throws = list(csv.DictReader(stream))
with E.open() as stream:
    eligible_throws = list(csv.DictReader(stream))

assert len({r['possession_id'] for r in possessions}) == len(possessions)
assert len({(r['possession_id'], r['ordinal']) for r in throws}) == len(throws)
first = {r['possession_id']: r for r in throws if r['own_possession'] == '1' and r['ordinal'] == '1'}
for row in eligible_throws:
    if row['own_possession'] == '1' and row['ordinal'] == '1':
        source = first[row['possession_id']]
        for key in ('GameID', 'source_side', 'source_side_idx', 'source_event_type'):
            assert row[key] == source[key]

opening = [r for r in possessions if r['own_possession'] == '1']
assert len(opening) == 5474

def summarize(rows):
    remaining, before = [], []
    missing_first = incomplete = missing_catch = goals = 0
    games, teams = set(), set()
    for row in rows:
        attempt = first.get(row['possession_id'])
        if attempt is None:
            missing_first += 1
            continue
        assert abs(float(attempt['ty']) - float(row['first_y'])) < 1e-9
        if attempt['complete'] != '1':
            incomplete += 1
            continue
        if not attempt['ry']:
            missing_catch += 1
            continue
        y = float(attempt['ry'])
        assert 0 <= y <= 120
        assert y < 100 or attempt['assist'] == '1'
        remaining.append(max(0.0, 100.0 - y))
        before.append(100.0 - float(attempt['ty']))
        goals += int(attempt['assist'])
        games.add(row['GameID'])
        teams.add(row['team'])
    n = len(remaining)
    assert len(rows) == n + missing_first + incomplete + missing_catch
    return {
        'eligible_opening_possessions': len(rows),
        'completed_first_passes_with_coordinates': n,
        'mean_yards_remaining': fsum(remaining) / n,
        'median_yards_remaining': median(remaining),
        'mean_yards_before_first_pass_same_sample': fsum(before) / n,
        'sum_yards_remaining': fsum(remaining),
        'first_pass_goals_included_at_zero_yards': goals,
        'first_pass_turnovers_excluded': incomplete,
        'no_recorded_first_throw_excluded': missing_first,
        'completed_first_pass_missing_catch_coordinate': missing_catch,
        'games': len(games), 'teams': len(teams),
    }

result = {
    'question': "How many yards remain to score after an O-line completes the first pass of its opening possession?",
    'definition': 'Possession-weighted mean of max(0, 100 - first-pass receiver y). Goal-line distance is forward distance, not accumulated passing yardage or distance to the back of the end zone.',
    'scope': 'Receiving-team first possession within the point; preserved original-seven eligibility and reviewed exclusions; 2026 regular-season study sample. All 22 teams, not only the ten displayed in the presentation.',
    'first_pass': 'Ordinal 1, whether centering or attacking. No centering deduction. Failed first attempts leave no continuing O-line possession and are excluded; first-pass goals count as zero remaining.',
    'scopes': {
        'long_field': summarize([r for r in opening if float(r['first_y']) <= 40]),
        'all_known_starts': summarize(opening),
    },
    'validation': {
        'eligible_input_hashes_match_existing_chart_analysis': True,
        'unique_possessions_and_attempts': True,
        'first_attempt_event_keys_match_eligible_throw_file': True,
        'first_throw_coordinate_matches_possession_start': True,
        'counts_reconcile_and_catch_coordinates_in_bounds': True,
        'independent_pandas_check': {
            'long_field_n': 4677, 'long_field_mean': 74.91941843061791,
            'all_known_starts_n': 5272, 'all_known_starts_mean': 71.83247723823976,
        },
    },
    'inputs': {str(path.relative_to(REPO)): digest(path) for path in (P, E, T)},
}
for scope, expected_n, expected_mean in [('long_field', 4677, 74.91941843061791), ('all_known_starts', 5272, 71.83247723823976)]:
    actual = result['scopes'][scope]
    assert actual['completed_first_passes_with_coordinates'] == expected_n
    assert abs(actual['mean_yards_remaining'] - expected_mean) < 1e-10
(ROOT / 'distance_after_opening_pass.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result['scopes'], indent=2))
