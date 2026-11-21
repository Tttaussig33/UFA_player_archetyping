"""Audit saved CP and prior-game coverage; no fitting, database writes, or app edits.

Run: python3 research/thrower_history_cp/audit_feasibility.py
Uses only the Python standard library and verifies the preserved export hashes.
History counts are computed before each calendar date, never within a game/day.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXPORT = ROOT / 'data/database-exports/2026-10-12'
PHYSICAL = {'18', '19', '20', '22', '23'}
UNKNOWN = {'', 'unknown', 'null', 'none', 'nan'}
EXPECTED = {
    '18': (0, 0, 0), '19': (0, 0, 0), '20': (1, 1, 0),
    '22': (1, 0, 0), '23': (1, 0, 0), '24': (1, 0, 1),
}
FIELDS = ['Thrower', 'Receiver', 'ThrowerX', 'ThrowerY', 'ReceiverX',
          'ReceiverY', 'turnover', 'DroppedThrow', 'stall', 'cp', 'throw_sig_id']


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def rows(name):
    with (EXPORT / (name + '.csv')).open(newline='', encoding='utf-8-sig') as f:
        yield from csv.DictReader(f)


def number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def split(date):
    if date <= '2026-06-14':
        return 'train'
    if date <= '2026-07-05':
        return 'validation'
    return 'test'


def distribution(values):
    a = sorted(values)
    if not a:
        return None
    def q(p):
        at = (len(a) - 1) * p
        lo, hi = math.floor(at), math.ceil(at)
        return a[lo] + (at - lo) * (a[hi] - a[lo])
    return {'n': len(a), 'min': a[0], 'p25': q(.25), 'median': q(.5),
            'p75': q(.75), 'max': a[-1]}


def main():
    manifest = json.loads((EXPORT / 'manifest.json').read_text())
    hashes = {}
    for name, meta in manifest['tables'].items():
        hashes[name] = digest(EXPORT / meta['file'])
        assert hashes[name] == meta['sha256'], name
    consulted = [
        ROOT / 'data/database-metadata/2026-11-04/throw-metric-validation.json',
        ROOT / 'analysis/multiseason_release_validation.json',
        ROOT / 'research/oline_possessions/cohort_audit.json',
        ROOT.parent / 'Nature_AI_in_Sports/journal_of_statistics_and_data_science_in_sports/submission/JSDSS_manuscript.docx',
    ]
    reference_hashes = {str(p): digest(p) for p in consulted}

    game_rows = list(rows('games'))
    games = {r['GameID']: r for r in game_rows}
    assert len(games) == len(game_rows), 'duplicate GameID'
    roster = list(rows('players'))
    id_names, name_ids, roster_counts = defaultdict(set), defaultdict(set), Counter()
    for r in roster:
        if r['PlayerID'].lower() not in UNKNOWN:
            id_names[r['PlayerID']].add(r['full_name'])
            name_ids[r['full_name']].add(r['PlayerID'])
            roster_counts[(r['Year'], r['PlayerID'])] += 1

    years, year_games, types = defaultdict(Counter), defaultdict(set), Counter()
    missing, physical_missing, cp_extremes = defaultdict(Counter), defaultdict(Counter), Counter()
    seen_ids, seen_exact = set(), set()
    source_hashes, event_keys = Counter(), Counter()
    duplicates = Counter()
    cp_min, cp_max = 1.0, 0.0
    missing_cp_rows, absent_player_ids, geometry_examples = [], set(), []
    gp = {'all_physical_cp': defaultdict(Counter), 'distance_ge_1_5_cp': defaultdict(Counter)}
    unknown_gp = {k: Counter() for k in gp}
    cohorts = {k: defaultdict(Counter) for k in gp}
    raw_columns = None

    for r in rows('throws'):
        raw_columns = raw_columns or list(r)
        assert None not in r and all(v is not None for v in r.values()), 'malformed CSV'
        gid, tid, kind = r['GameID'], r['throw_sig_id'], r['source_event_type']
        assert gid in games, 'orphan throw'
        y = games[gid]['Year']
        s = years[y]
        s['rows'] += 1
        year_games[y].add(gid)
        types[kind] += 1
        flags = tuple(number(r[f]) for f in ['turnover', 'DroppedThrow', 'stall'])
        assert kind in EXPECTED and flags == EXPECTED[kind], (gid, tid, kind, flags)
        assert tid, 'missing throw ID'
        key = (gid, tid)
        duplicates['game_throw_id'] += key in seen_ids
        seen_ids.add(key)
        row_hash = hashlib.sha256(json.dumps(r, sort_keys=True).encode()).digest()
        duplicates['exact_rows'] += row_hash in seen_exact
        seen_exact.add(row_hash)
        if r['source_throw_hash']:
            source_hashes[(gid, r['source_throw_hash'])] += 1
        event_keys[(gid, r['source_side'], r['source_side_idx'])] += 1
        for f in FIELDS:
            if r[f].lower() in UNKNOWN:
                missing[y][f] += 1
                if kind in PHYSICAL:
                    physical_missing[y][f] += 1

        cp = number(r['cp'])
        cp_ok = cp is not None and 0 <= cp <= 1
        s['cp_missing'] += not r['cp']
        s['cp_invalid_nonmissing'] += bool(r['cp']) and not cp_ok
        if cp_ok:
            cp_min, cp_max = min(cp_min, cp), max(cp_max, cp)
        xy = [number(r[f]) for f in ['ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY']]
        finite_xy = all(v is not None for v in xy)
        dist = math.hypot(xy[2] - xy[0], xy[3] - xy[1]) if finite_xy else None
        s['missing_geometry'] += not finite_xy
        if finite_xy:
            in_bounds = all(-26.67000001 <= xy[i] <= 26.67000001 for i in [0, 2]) and all(0 <= xy[i] <= 120 for i in [1, 3])
            s['out_of_bounds_geometry'] += not in_bounds
            for field, actual in [('throw_distance', dist), ('x_diff', xy[2]-xy[0]), ('y_diff', xy[3]-xy[1])]:
                saved = number(r[field])
                if saved is None or abs(saved - actual) > 1e-6:
                    s['geometry_mismatch_' + field] += 1
                    geometry_examples.append({'game': gid, 'id': tid, 'field': field})
        if cp in (0, 1):
            cp_extremes[(y, kind, str(cp), 'short' if dist is not None and dist < 1.5 else 'other')] += 1
        if kind not in PHYSICAL:
            s['stalls_excluded'] += 1
            continue

        s['physical_throws'] += 1
        caught, drop = kind in {'18', '19'}, kind == '20'
        s['caught'] += caught
        s['drops'] += drop
        s['drop_rows_with_stored_cpoe_one'] += drop and number(r['cpoe']) == 1
        s['distance_below_1_5'] += dist is not None and dist < 1.5
        known = r['Thrower'].lower() not in UNKNOWN
        s['unknown_thrower'] += not known
        if known and r['Thrower'] not in id_names:
            absent_player_ids.add(r['Thrower'])
        if not cp_ok:
            s['physical_invalid_or_missing_cp'] += 1
            missing_cp_rows.append({'game': gid, 'throw_id': tid, 'type': kind,
                                    'thrower': r['Thrower'], 'cp': r['cp']})
            continue
        huck = finite_xy and dist > 40 and xy[3] - xy[1] > 30
        for variant in gp:
            if variant == 'distance_ge_1_5_cp' and (dist is None or dist < 1.5):
                continue
            cs = cohorts[variant][gid]
            cs['throws'] += 1
            cs['caught'] += caught
            cs['drops'] += drop
            cs['hucks'] += huck
            cs['unknown_thrower'] += not known
            cs['missing_receiver'] += r['Receiver'].lower() in UNKNOWN
            if known:
                gp[variant][gid][r['Thrower']] += 1
            else:
                unknown_gp[variant][gid] += 1

    assert sum(s['rows'] for s in years.values()) == manifest['tables']['throws']['rows']
    assert duplicates['game_throw_id'] == 0 and duplicates['exact_rows'] == 0
    history = {}
    for variant, game_players in gp.items():
        result = {}
        for use_older in [False, True]:
            prior_n, prior_g = Counter(), Counter()
            bins = defaultdict(Counter)
            at_first_2026, by_split = {}, defaultdict(list)
            by_date = defaultdict(list)
            for gid in cohorts[variant]:
                y = games[gid]['Year']
                if use_older or y == '2026':
                    by_date[games[gid]['StartTimestamp'][:10]].append(gid)
            for date, gids in sorted(by_date.items()):
                # Read the frozen state for ALL games today, then update after today.
                for gid in sorted(gids):
                    if games[gid]['Year'] != '2026':
                        continue
                    part = split(date)
                    for pid, n in game_players[gid].items():
                        pn, pgames = prior_n[pid], prior_g[pid]
                        at_first_2026.setdefault(pid, {'throws': pn, 'games': pgames})
                        by_split[part].append({'n': n, 'prior_throws': pn, 'prior_games': pgames})
                        for group in ['all_2026', part]:
                            b = bins[group]
                            b['named_throws'] += n
                            b['player_games'] += 1
                            for threshold in [1, 50, 100, 200, 500]:
                                b[f'throws_with_at_least_{threshold}_prior_throws'] += n if pn >= threshold else 0
                            for threshold in [1, 3, 5, 10]:
                                b[f'throws_with_at_least_{threshold}_prior_games'] += n if pgames >= threshold else 0
                for gid in gids:
                    for pid, n in game_players[gid].items():
                        prior_n[pid] += n
                        prior_g[pid] += 1
            result['all_available_seasons' if use_older else '2026_only'] = {
                'throw_weighted_coverage': dict(bins),
                'first_2026_appearance': {
                    'players': len(at_first_2026),
                    'with_prior_history': sum(v['throws'] > 0 for v in at_first_2026.values()),
                    'prior_throws': distribution([v['throws'] for v in at_first_2026.values()]),
                    'prior_games': distribution([v['games'] for v in at_first_2026.values()]),
                },
                'player_game_history_distribution': {
                    part: {field: distribution([r[field] for r in rr]) for field in ['prior_throws', 'prior_games']}
                    for part, rr in by_split.items()
                },
            }
        history[variant] = result

    schedule_without_throws = [
        {k: r[k] for k in ['GameID', 'Status', 'RegularSeasonWeek', 'PlayoffRound']}
        for r in game_rows if r['Year'] == '2026' and r['GameID'] not in year_games['2026']
    ]
    split_counts = {}
    cohort_counts = {}
    for variant, gc in cohorts.items():
        parts = defaultdict(Counter)
        pids = defaultdict(set)
        for gid, c in gc.items():
            y = games[gid]['Year']
            if y != '2026':
                continue
            phase = 'regular' if games[gid]['RegularSeasonWeek'] else 'playoffs' if games[gid]['PlayoffRound'] else 'unclassified'
            for part in [split(games[gid]['StartTimestamp'][:10]), 'all']:
                parts[part].update(c)
                parts[part]['games'] += 1
                parts[part][phase + '_games'] += 1
                pids[part].update(gp[variant][gid])
        for part in parts:
            parts[part]['named_throwers'] = len(pids[part])
        split_counts[variant] = dict(parts)
        for field in ['throws', 'games', 'caught', 'drops', 'unknown_thrower']:
            assert sum(parts[p][field] for p in ['train', 'validation', 'test']) == parts['all'][field]
        annual = defaultdict(Counter)
        for gid, c in gc.items():
            annual[games[gid]['Year']].update(c)
            annual[games[gid]['Year']]['games'] += 1
        cohort_counts[variant] = dict(annual)

    cp_meta_names = [c for c in raw_columns if any(s in c.lower() for s in ['model', 'train', 'fold', 'predict'])]
    out = {
        'purpose': 'Feasibility only: data audit and prospective split proposal; no models fitted or test performance compared.',
        'source': {'snapshot': manifest['snapshot'], 'manifest': str((EXPORT / 'manifest.json').relative_to(ROOT)), 'verified_sha256': hashes,
                   'live_count_check': 'See database_readonly_receipt.json. Count agreement does not prove identical row contents.'},
        'consulted_reference_sha256': reference_hashes,
        'scope': 'All recorded lines, possession numbers, field locations and phases. No earlier O-line or long-field filters imported.',
        'seasons': [{**dict(years[y]), 'year': int(y), 'games': len(year_games[y])} for y in sorted(years)],
        'event_types': dict(types),
        'duplicates': {**dict(duplicates), 'duplicate_game_ids': 0,
                       'repeated_source_hash_extra_rows': sum(v-1 for v in source_hashes.values() if v > 1),
                       'repeated_source_side_index_extra_rows': sum(v-1 for v in event_keys.values() if v > 1)},
        'missing_or_unknown_fields': dict(missing),
        'physical_missing_or_unknown_fields': dict(physical_missing),
        'cp_range': [cp_min, cp_max],
        'cp_zero_one_by_year_type_and_distance': [{'year': k[0], 'type': k[1], 'cp': float(k[2]), 'distance_band': k[3], 'n': v} for k, v in sorted(cp_extremes.items())],
        'missing_cp_rows': missing_cp_rows,
        'unknown_roster_thrower_ids': sorted(absent_player_ids),
        'roster': {'conflicting_names_per_id': {k: sorted(v) for k, v in id_names.items() if len(v) > 1},
                   'names_with_multiple_ids': {k: sorted(v) for k, v in name_ids.items() if len(v) > 1},
                   'extra_year_player_rows': sum(v-1 for v in roster_counts.values() if v > 1)},
        'missing_2026_scheduled_games': schedule_without_throws,
        'game_date_disagreements': [{'game': gid, 'StartTimestamp': g['StartTimestamp']} for gid, g in games.items() if gid[:10] != g['StartTimestamp'][:10]],
        'games_with_throws_missing_start_date': [gid for gid in seen_game_ids(year_games) if not games[gid]['StartTimestamp']],
        'training_provenance': {'fields_in_export': cp_meta_names, 'cp_training_labels_verified': False,
                                 '2026_excluded_from_cp_training': 'working assumption, unverified',
                                 'older_predictions_out_of_sample': 'unverified; neither values nor aggregate metrics prove this'},
        'cohort_counts': cohort_counts,
        'proposed_2026_splits': {'date_source': 'StartTimestamp calendar date; all games on same date remain together',
                                 'train': 'through 2026-06-14', 'validation': '2026-06-15 through 2026-07-05',
                                 'test': '2026-07-06 onward', 'counts': split_counts},
        'history_coverage': history,
        'checks': {'source_hashes_verified': True, 'outcomes_match_event_codes': True,
                   'unique_game_throw_ids': True, 'all_throws_join_games': True,
                   'no_current_game_or_same_date_history': 'All reads precede all updates within each date',
                   'no_model_fit_or_test_scores': True},
    }
    (HERE / 'audit.json').write_text(json.dumps(out, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'seasons': out['seasons'], 'duplicates': out['duplicates'],
                      'cp_range': out['cp_range'], 'split_counts': split_counts,
                      'history_primary_test': history['distance_ge_1_5_cp']['2026_only']['throw_weighted_coverage']['test']}, indent=2))


def seen_game_ids(by_year):
    return set().union(*by_year.values())


if __name__ == '__main__':
    main()
