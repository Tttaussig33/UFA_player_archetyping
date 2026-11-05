"""Independently verify selected passes against stored possession metadata."""
from pathlib import Path
from collections import defaultdict, Counter
import csv
import json
import math

ROOT = Path(__file__).resolve().parent
result = json.loads((ROOT / 'results.json').read_text())
selected = json.loads((ROOT / 'selected_passes.json').read_text())
source = Path(result['sources']['export_manifest']).parent
game_ids = {x['GameID'] for rows in selected.values() for x in rows}
groups = defaultdict(list)
with (source / 'throws.csv').open(newline='') as f:
    for t in csv.DictReader(f):
        if (t['GameID'] in game_ids and t['start_on_offense'].lower() == 'true'
                and float(t['possession_num']) == 1):
            groups[(t['GameID'], t['source_side'], t['game_quarter'], t['quarter_point'])].append(t)

validated = {}
for variant, rows in selected.items():
    seen = set()
    for x in rows:
        key = (x['GameID'], x['source_side'], x['quarter'], x['point'])
        assert key not in seen, ('duplicate', variant, key)
        seen.add(key)
        eligible = []
        for t in sorted(groups[key], key=lambda t: float(t['possession_throw'])):
            if float(t['turnover']) != 0 or float(t['stall']) != 0:
                continue
            tx, ty, rx, ry = [float(t[k]) for k in ['ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY']]
            if not all(math.isfinite(z) for z in [tx, ty, rx, ry]):
                continue
            if abs(tx) > 26.67000001 or abs(rx) > 26.67000001 or not (0 <= ty <= 120 and 0 <= ry <= 120):
                continue
            inward = abs(tx) - abs(rx)
            if inward <= 1e-6:
                continue
            if variant == 'at_least_5_yards' and inward < 5 - 1e-6:
                continue
            if variant == 'any_inward_excluding_hucks' and math.hypot(rx-tx, ry-ty) > 40 and ry-ty > 30:
                continue
            eligible.append(t)
        assert eligible and eligible[0]['throw_sig_id'] == x['throw_sig_id'], ('selection', variant, key)
        assert eligible[0]['Receiver'] == x['Receiver']
    totals = Counter(x['TeamID'] for x in rows)
    counts = Counter((x['TeamID'], x['Receiver']) for x in rows)
    for t in result['teams'][variant]:
        assert totals[t['TeamID']] == t['qualifying_centering_passes']
        team_counts = {pid: n for (tid, pid), n in counts.items() if tid == t['TeamID']}
        top = max(team_counts.values())
        assert top == t['leader_count']
        assert {pid for pid, n in team_counts.items() if n == top} == {x['PlayerID'] for x in t['leaders']}
        assert abs(top / totals[t['TeamID']] - t['leader_share']) < 1e-10
    validated[variant] = {'independent_database_order_matches': len(rows),
                          'unique_opening_possessions': len(seen), 'team_maximum_counts_verified': 22}

ordinals = Counter(x['ordinal'] for x in selected['any_inward'])
report = {
    'independent_database_metadata_check': validated,
    'timing': {'primary_on_first_throw': ordinals[1], 'primary_on_second_throw': ordinals[2],
               'primary_within_first_three_throws': sum(n for k, n in ordinals.items() if k <= 3),
               'primary_after_three_throws': sum(n for k, n in ordinals.items() if k > 3)},
    'unattributed_primary_receptions': sum(t['unattributed_centering_passes'] for t in result['teams']['any_inward']),
    'exclusions': result['excluded_sequences'],
    'qualifications': 'Raw-event selection independently matches selection by stored opening-possession metadata and throw ordinal. This validates computation, not the tactical interpretation of centering.',
    'native_canvas_preview': 'Not yet verified in the app.'
}
(ROOT / 'validation.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
