"""Audit restart candidates without treating all first-possession throws as dead discs.

Inputs: preserved ShownSpace export plus captured public UFA game event arrays.
The timeout cohort has explicit stoppage evidence. Injury and penalty cohorts
retain their source labels; no whistle/advantage or ordinary OB flag exists.
"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
import shutil

ROOT = Path(__file__).resolve().parent
SOURCE = Path('/Users/teddytaussig/Desktop/Work/UFA_player_archetyping/data/database-exports/2026-10-12')
CAPTURE = Path('/tmp/ufa-dead-disc-audit-20261104')
RAW = ROOT / 'raw_events'
ATTEMPTS = {18, 19, 20, 22, 23, 24}
MARKERS = {3: 'team_timeout', 5: 'team_timeout', 16: 'penalty', 17: 'penalty', 25: 'injury'}
# Any change in possession, point, period, pull, delay, or ambiguous new context
# terminates a pending marker. This never labels routine turnover pickups.
BOUNDARIES = {1, 2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 21, 28, 29, 30, 31, 32, 33, 34, 35}


def number(x):
    try:
        y = float(x)
        return y if math.isfinite(y) else None
    except (ValueError, TypeError):
        return None


def read_csv(name):
    with (SOURCE / (name + '.csv')).open() as f:
        yield from csv.DictReader(f)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_csv(path, rows):
    if not rows:
        return
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def matched(row, event):
    if (str(event.get('type')) != row['source_event_type']
            or event.get('thrower', '') != row['Thrower']
            or event.get('receiver', '') != row['Receiver']):
        return False
    # Verify throwaway landing positions as well as pass/catch positions.
    pairs = [('throwerX', 'ThrowerX'), ('throwerY', 'ThrowerY')]
    if event.get('type') in {22, 23}:
        pairs += [('turnoverX', 'ReceiverX'), ('turnoverY', 'ReceiverY')]
    else:
        pairs += [('receiverX', 'ReceiverX'), ('receiverY', 'ReceiverY')]
    for raw_name, stored_name in pairs:
        if raw_name in event:
            a, b = number(event[raw_name]), number(row[stored_name])
            if a is None or b is None or abs(a - b) > 1e-6:
                return False
    return True


def summarize(rows, names):
    players = defaultdict(list)
    for r in rows:
        if r['Thrower'].lower() not in {'', 'unknown', 'none', 'null', 'nan'}:
            players[r['Thrower']].append(r)
    output = []
    for pid, group in players.items():
        hucks = [r for r in group if r['project_huck']]
        hc = [r for r in hucks if r['cp'] is not None and 0 <= r['cp'] <= 1]
        aecs = [r['thrower_aec'] for r in group if r['thrower_aec'] is not None]
        output.append({
            'PlayerID': pid, 'name': names.get(pid, pid),
            'restart_events_including_stalls': len(group),
            'throws': sum(not r['stall'] for r in group),
            'stalls': sum(r['stall'] for r in group),
            'games': len({r['GameID'] for r in group}),
            'assists': sum(r['assist'] for r in group),
            'thrower_aec': sum(aecs) if aecs else None,
            'aec_covered_events': len(aecs),
            'thrower_aec_per_100_events': 100 * sum(aecs) / len(group) if len(aecs) == len(group) else None,
            'huck_attempts': len(hucks),
            'huck_completions': sum(r['complete'] for r in hucks),
            'huck_drops': sum(r['drop'] for r in hucks),
            'huck_assists': sum(r['assist'] for r in hucks),
            'huck_cp_covered': len(hc),
            'huck_completion_rate': sum(r['complete'] for r in hucks) / len(hucks) if hucks else None,
            'huck_mean_cp': sum(r['cp'] for r in hc) / len(hc) if hc else None,
            'huck_cpoe_pp': 100 * sum(int(r['complete'] or r['drop']) - r['cp'] for r in hc) / len(hc) if hc else None,
        })
    output.sort(key=lambda r: r['PlayerID'])
    return output


def main():
    RAW.mkdir(exist_ok=True)
    receipt_path = RAW / 'source_receipt.json'
    if not receipt_path.exists():
        shutil.copy2(CAPTURE / 'source_receipt.json', receipt_path)
    receipts = json.loads(receipt_path.read_text())
    for gid, receipt in receipts.items():
        path = RAW / (gid + '.json')
        if not path.exists():
            shutil.copy2(CAPTURE / path.name, path)
        assert sha(path) == receipt['sha256'], gid
    manifest = json.loads((SOURCE / 'manifest.json').read_text())
    for name in ['throws', 'games', 'players']:
        assert sha(SOURCE / (name + '.csv')) == manifest['tables'][name]['sha256']
    games = {r['GameID']: r for r in read_csv('games') if r['Year'] == '2026'
             and r['RegularSeasonWeek'] and not r['PlayoffRound']
             and r['is_final'].lower() == 'true'}
    names = {}
    for r in read_csv('players'):
        if r['Year'] == '2026':
            name = ' '.join(r['full_name'].split())
            if r['PlayerID'] in names:
                assert names[r['PlayerID']] == name
            names[r['PlayerID']] = name
    grouped = defaultdict(list)
    keys = set()
    for r in read_csv('throws'):
        if r['GameID'] in games:
            key = (r['GameID'], r['throw_sig_id'])
            assert key not in keys
            keys.add(key)
            grouped[r['GameID']].append(r)
    checks = Counter()
    unmatched = []
    candidates = []
    candidate_keys = set()
    for gid, stored in sorted(grouped.items()):
        raw = json.loads((RAW / (gid + '.json')).read_text())['data']
        lookup = {}
        for r in stored:
            side, idx = r['source_side'], int(r['source_side_idx'])
            events = raw[side + 'Events']
            e = events[idx] if 0 <= idx < len(events) else {}
            ok = matched(r, e)
            checks['source_rows_matched' if ok else 'source_rows_unmatched'] += 1
            if ok:
                assert (side, idx) not in lookup
                lookup[(side, idx)] = r
            else:
                unmatched.append({'GameID': gid, 'side': side, 'index': idx,
                                  'throw_sig_id': r['throw_sig_id'], 'stored_type': r['source_event_type'],
                                  'raw_type': e.get('type')})
        for side in ['home', 'away']:
            pending = []
            for i, e in enumerate(raw[side + 'Events']):
                typ = e['type']
                if typ in MARKERS:
                    pending.append({'index': i, 'type': typ, 'category': MARKERS[typ]})
                elif typ in BOUNDARIES:
                    pending = []
                elif typ in ATTEMPTS:
                    if pending:
                        checks['candidate_raw_attempts'] += 1
                        r = lookup.get((side, i))
                        if r is not None:
                            key = (gid, r['throw_sig_id'])
                            assert key not in candidate_keys
                            candidate_keys.add(key)
                            complete = number(r['turnover']) == 0
                            drop = number(r['DroppedThrow']) == 1
                            stall = number(r['stall']) == 1
                            assert number(r['turnover']) in {0, 1}
                            assert number(r['DroppedThrow']) in {0, 1}
                            assert not (drop and complete)
                            aec = number(r['aec'])
                            taec = None if aec is None else (0.0 if drop else aec)
                            xy = [number(r[k]) for k in ['ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY']]
                            located = all(x is not None for x in xy)
                            distance = math.hypot(xy[2] - xy[0], xy[3] - xy[1]) if located else None
                            forward = xy[3] - xy[1] if located else None
                            categories = {p['category'] for p in pending}
                            assist = typ == 19
                            assert not assist or complete
                            candidates.append({
                                'GameID': gid, 'throw_sig_id': r['throw_sig_id'], 'source_side': side,
                                'source_side_idx': i, 'source_event_type': typ, 'Thrower': r['Thrower'],
                                'Receiver': r['Receiver'], 'markers': pending.copy(),
                                'has_team_timeout': 'team_timeout' in categories,
                                'has_injury': 'injury' in categories, 'has_penalty': 'penalty' in categories,
                                'complete': complete, 'drop': drop, 'stall': stall, 'assist': assist,
                                'cp': number(r['cp']), 'source_aec': aec, 'thrower_aec': taec,
                                'distance_yards': distance, 'forward_yards': forward,
                                'project_huck': bool(not stall and located and distance > 40 and forward > 30),
                                'ufa_documented_huck': bool(not stall and located and forward > 40),
                            })
                        else:
                            checks['candidate_attempts_unmatched'] += 1
                    pending = []
                else:
                    checks['unrecognized_raw_events'] += 1
                    pending = []
    cohorts = {
        'team_timeout': [r for r in candidates if r['has_team_timeout']],
        'team_timeout_or_injury': [r for r in candidates if r['has_team_timeout'] or r['has_injury']],
        'all_recorded_markers': candidates,
    }
    result = {}
    for name, rows in cohorts.items():
        all_rows = rows
        rows = [r for r in all_rows if r['Thrower'].lower() not in {'', 'unknown', 'none', 'null', 'nan'}]
        ps = summarize(rows, names)
        h = [r for r in rows if r['project_huck']]
        summary = {
            'candidate_events_before_player_attribution': len(all_rows),
            'unattributed_events': len(all_rows) - len(rows),
            'restart_events_including_stalls': len(rows), 'throws': sum(not r['stall'] for r in rows),
            'stalls': sum(r['stall'] for r in rows), 'players': len(ps),
            'assists': sum(r['assist'] for r in rows),
            'project_hucks': len(h),
            'ufa_documented_hucks': sum(r['ufa_documented_huck'] for r in rows),
            'huck_players': sum(p['huck_attempts'] > 0 for p in ps),
            'max_hucks_one_player': max(p['huck_attempts'] for p in ps),
            'players_at_least_5_hucks': sum(p['huck_attempts'] >= 5 for p in ps),
            'players_at_least_10_hucks': sum(p['huck_attempts'] >= 10 for p in ps),
            'missing_aec': sum(r['thrower_aec'] is None for r in rows),
            'missing_cp_hucks': sum(r['cp'] is None for r in h),
        }
        assert sum(p['restart_events_including_stalls'] for p in ps) == len(rows)
        assert sum(p['assists'] for p in ps) == summary['assists']
        assert sum(p['huck_attempts'] for p in ps) == summary['project_hucks']
        result[name] = {'summary': summary, 'players': ps}
        write_csv(ROOT / (name + '_players.csv'), ps)
    rawtypes = Counter(str(e['type']) for gid in grouped for events in
                       json.loads((RAW / (gid + '.json')).read_text())['data'].values()
                       if isinstance(events, list) for e in events)
    final = {
        'executed_at': datetime.now(timezone.utc).isoformat(),
        'scope': '2026 regular season, 131 games in preserved October 12 ShownSpace export',
        'missing_game': '2026-07-18-PIT-CHI',
        'user_definition': 'First throw after a stoppage such as timeout, foul or out-of-bounds restart. Routine turnover fast breaks are separate.',
        'source_link_checks': dict(checks), 'unmatched_source_rows': unmatched,
        'raw_event_type_counts': dict(rawtypes), 'cohorts': result,
        'definitions': {
            'huck': 'Project definition: Euclidean endpoint distance >40 yards AND forward gain >30 yards; non-stall.',
            'huck_sensitivity': 'UFA API documentation: forward gain >40 yards; counted separately, not silently substituted.',
            'assists': 'Actual source Goal event, type 19. No goal-line coordinate proxy.',
            'thrower_aec': 'Sum stored aEC, with zero thrower credit on drops, including stalls. Prior project reconciliation reproduced official player-game totals.',
            'huck_cpoe': 'Mean of (actual completion OR drop) minus stored CP on valid-CP hucks; percentage points. Raw stored cpoe is never averaged.',
            'event_link': 'Exact game, source side and source index; verify type, thrower, receiver and every present raw coordinate, including throwaway landing coordinates.',
            'sequence': 'Within the same side array, first attempt after recorded marker(s), with no intervening possession/point/period/pull boundary; clear after first attempt. Deduplicate by GameID+throw_sig_id.',
        },
        'limitations': [
            'Markers identify an operational subset. No restart-whistle or advantage flag exists; penalty-only records require validation before a confirmed dead-disc interpretation.',
            'Ordinary OB returns, technical timeouts and unmarked stoppages are not recoverable reliably from this schema. Normal pull receptions and routine turnover pickups are excluded.',
            'Injury timing follows recorded ordering; the feed has no explicit whistle timestamp.',
            'No inference of upline cuts, player momentum, defensive pressure or causal individual skill.',
            'Incomplete one-game coverage and possibly incomplete event recording limit any league-wide total ranking.',
            'No minimum-sample skill ranking fitted. Totals describe recorded contribution and exposure; they do not establish the best hucker.',
        ],
        'sources': {
            'export_manifest': str(SOURCE / 'manifest.json'),
            'raw_event_receipt': str(receipt_path),
            'event_documentation': 'https://www.docs.ufastats.com/events',
            'rules': 'https://watchufa.com/sites/default/files/UFA%20Rule%20Book%202026.pdf',
            'known_database_raw_table': 'prod.game_events_raw; schema inspected in earlier DBeaver audit, rows not queried here.',
        },
    }
    (ROOT / 'restart_candidates.json').write_text(json.dumps(candidates, indent=2))
    (ROOT / 'results.json').write_text(json.dumps(final, indent=2, allow_nan=False))
    print(json.dumps({'checks': dict(checks), 'cohorts': {k: v['summary'] for k, v in result.items()},
                      'top_observed_totals': {k: {
                          'assists': sorted(v['players'], key=lambda p: (-p['assists'], p['PlayerID']))[:5],
                          'thrower_aec': sorted(v['players'], key=lambda p: (-(p['thrower_aec'] or 0), p['PlayerID']))[:5],
                      } for k, v in result.items()}}, indent=2))


if __name__ == '__main__':
    main()
