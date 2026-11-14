"""Build 100 new opening reviews, emphasizing borderline pass geometry.

Extend the frozen first-quarter library without rewriting it or its labels.
Eighty examples are selected by uncertainty in the existing geometry model;
twenty are broader team-balanced examples. This is definition development,
not a representative estimate of accuracy or centering prevalence.
"""
from collections import Counter, defaultdict
from pathlib import Path
import copy
import csv
import hashlib
import json
import math
import random
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RAW = HERE.parent / 'dead_disc_study/raw_events'
CANVAS = ROOT / 'research/previews/UFA-possession-review.canvas.tsx'
MANAGED = Path('/Users/teddytaussig/.cursor/projects/Users-teddytaussig-Desktop-Work-UFA-player-archetyping/canvases/UFA-possession-review.canvas.tsx')
BATCH_ID = 'opening-pattern-review-100-20261113-v1'
SEED = 2026111302
TYPES = {18: 'Complete', 19: 'Goal', 20: 'Drop', 22: 'Throwaway', 23: 'Callahan'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def clock(seconds):
    n = max(0, round(seconds))
    return f'{n//3600}:{n//60%60:02}:{n%60:02}' if n >= 3600 else f'{n//60}:{n%60:02}'


def geometry_score(model, row):
    x = [(row[k] - m) / s for k, m, s in zip(model['features'], model['training_mean'], model['training_scale'])]
    logit = model['coefficients'][0] + sum(b * v for b, v in zip(model['coefficients'][1:], x))
    return 1 / (1 + math.exp(-logit))


def main():
    source = CANVAS.read_text()
    assert source == MANAGED.read_text(), 'Reconcile user edits before preparing the batch.'
    data = json.loads(re.search(r'^const DATA = (.*);$', source, re.M).group(1))
    original_cases = copy.deepcopy(data['cases'])
    original_by_pid = {c['possessionId']: c for c in original_cases}
    assisted = re.search(r'^const ASSISTED = (.*);$', source, re.M).group(1)
    paths = {
        'manifest': HERE / 'film_library_manifest.json',
        'inventory': HERE / 'opening_pass_feasibility.json',
        'original_library': HERE / 'film_library.json',
        'current_reviews': HERE / 'annotations/current_reviewed_decisions.json',
        'latest_browser_export': HERE / 'annotations/2026-11-13-before-100-browser-export.json',
        'frozen_model': HERE / 'opening_classifier_pilot.json',
        'possessions': HERE.parent / 'oline_possessions/possessions.csv',
        'throws': HERE.parent / 'oline_possessions/throws.csv',
        'players': ROOT / 'data/database-exports/2026-10-12/players.csv',
        'raw_receipt': RAW / 'source_receipt.json',
    }
    inputs = {k: {'path': str(v.relative_to(ROOT)), 'sha256': sha(v)} for k, v in paths.items()}
    manifest = json.loads(paths['manifest'].read_text())
    inventory = json.loads(paths['inventory'].read_text())
    reviews = json.loads(paths['current_reviews'].read_text())['reviews']
    browser_reviews = json.loads(paths['latest_browser_export'].read_text())['reviews']
    assert {r['possessionId'] for r in reviews} == {r['possessionId'] for r in browser_reviews}
    assert {r['possessionId']: r['decision'] for r in reviews} == {r['possessionId']: r['decision'] for r in browser_reviews}
    reviewed = {r['possessionId'] for r in browser_reviews}
    games = {g['gameId']: g for g in manifest['games']}
    game_order = {g['gameId']: i for i, g in enumerate(manifest['games'])}
    frozen = json.loads(paths['frozen_model'].read_text())
    model = frozen['model']['full_fit']
    frozen_case_ids = {c['possessionId'] for c in json.loads(paths['original_library'].read_text())['cases']}
    for key in ('possessions', 'throws'):
        assert sha(paths[key]) == inventory['inputs'][key]['sha256']
    with paths['possessions'].open() as handle:
        possessions = {r['possession_id']: r for r in csv.DictReader(handle)}
    throws = defaultdict(list)
    with paths['throws'].open() as handle:
        for r in csv.DictReader(handle):
            throws[r['possession_id']].append(r)
    names = {}
    with paths['players'].open() as handle:
        for r in csv.DictReader(handle):
            if r['Year'] == '2026':
                names.setdefault(r['PlayerID'], r['full_name'])
    receipts = json.loads(paths['raw_receipt'].read_text())
    raw, point_ranges = {}, {}
    for gid in games:
        path = RAW / (gid + '.json')
        assert sha(path) == receipts[gid]['sha256']
        raw[gid] = json.loads(path.read_text())['data']
        lookup = defaultdict(list)
        for side in ('home', 'away'):
            events = raw[gid][side + 'Events']
            quarter = 1
            for i, event in enumerate(events):
                if event['type'] in (1, 2):
                    end = next((j for j in range(i + 1, len(events)) if events[j]['type'] in {1, 2, 28, 29, 30, 31, 32, 33}), len(events))
                    lookup[side, quarter, event.get('time')].append((i, end))
                if event['type'] in {28, 29, 30, 31, 32, 33}:
                    quarter = event['type'] - 26
        point_ranges[gid] = lookup

    candidates, exclusions = [], Counter()
    for row in inventory['rows']:
        pid, gid = row['possession_id'], row['game_id']
        if gid not in games or row['quarter'] not in (1, 2) or pid in reviewed:
            continue
        if (not row['physical_throws'] or not row['first_attempt_original_line']
                or row['first_attempt_event_type'] not in (18, 19)
                or row['distance'] <= 0 or row['coordinate_hold'] or row['label_alignment_hold']):
            exclusions['not_eligible_for_completed_transfer_review'] += 1
            continue
        if math.isclose(row['tx'], 0, abs_tol=1e-8, rel_tol=0) and math.isclose(row['ty'], 40, abs_tol=1e-8, rel_tol=0):
            exclusions['existing_exact_brick_rule'] += 1
            continue
        pos, game = possessions[pid], games[gid]
        side, point_idx = pid.split('|')[1], int(pid.split('|')[2])
        events = raw[gid][side + 'Events']
        assert events[point_idx]['type'] == 2 and int(pos['own_possession']) == 1
        attempts = sorted(throws[pid], key=lambda r: int(r['ordinal']))
        first_idx = int(attempts[0]['source_side_idx'])
        opposite = 'away' if side == 'home' else 'home'
        peer = point_ranges[gid].get((opposite, row['quarter'], int(pos['point_start_time'])), [])
        peer_events = raw[gid][opposite + 'Events']
        pulls = [(i, peer_events[i]) for i in range(*peer[0]) if peer_events[i]['type'] in (7, 8)] if len(peer) == 1 else []
        pull = pulls[0] if len(pulls) == 1 else None
        timestamp = events[first_idx].get('timestamp')
        time_source = {'side': side, 'eventIndex': first_idx, 'kind': 'First physical throw'}
        if timestamp is None and pull:
            timestamp = pull[1].get('timestamp')
            time_source = {'side': opposite, 'eventIndex': pull[0], 'kind': 'Opposing pull; first-throw timestamp unavailable'}
        if timestamp is None:
            exclusions['missing_navigation_timestamp'] += 1
            continue
        anchors = [a for a in game['anchors'] if a['sourceSide'] == time_source['side']] or game['anchors']
        anchor = min(anchors, key=lambda a: abs(timestamp - a['sourceTimestamp']))
        estimate = anchor['videoSeconds'] + timestamp - anchor['sourceTimestamp']
        if not 0 <= estimate < game['durationSeconds'] - 10:
            exclusions['outside_recording'] += 1
            continue
        old_case = original_by_pid.get(pid)
        if old_case and old_case.get('filmUnavailable'):
            exclusions['known_missing_footage'] += 1
            continue
        score = geometry_score(model, row)
        candidates.append({'row': row, 'pos': pos, 'attempts': attempts, 'pull': pull,
                           'timestamp': timestamp, 'time_source': time_source, 'anchor': anchor,
                           'estimate': estimate, 'score': score})
    assert len(candidates) >= 100
    rng = random.Random(SEED)
    teams = sorted({c['row']['team'] for c in candidates})
    rng.shuffle(teams)
    assert len(teams) == 22
    by_team = {team: sorted([c for c in candidates if c['row']['team'] == team], key=lambda c: c['row']['possession_id']) for team in teams}
    selected, used, team_counts = [], set(), Counter()
    # The broad sample is chosen without looking at scores or later outcomes.
    for team in teams[:20]:
        c = rng.choice(by_team[team])
        selected.append((c, 'broader_example'))
        used.add(c['row']['possession_id'])
        team_counts[team] += 1
    # Balance teams while emphasizing scores closest to the frozen boundary.
    for _ in range(80):
        available = [team for team in teams if any(c['row']['possession_id'] not in used for c in by_team[team])]
        team = min(available, key=lambda t: (team_counts[t], teams.index(t)))
        c = min([c for c in by_team[team] if c['row']['possession_id'] not in used],
                key=lambda c: (abs(c['score'] - .5), c['row']['possession_id']))
        selected.append((c, 'borderline_priority'))
        used.add(c['row']['possession_id'])
        team_counts[team] += 1
    selected.sort(key=lambda pair: (game_order[pair[0]['row']['game_id']], pair[0]['row']['quarter'],
                                   int(pair[0]['pos']['point_start_time']), pair[0]['row']['possession_id']))
    next_number = max(int(c['id'][1:]) for c in original_cases if c['id'].startswith('R'))
    added, extension_cases, private_clips, display_clips = [], [], [], []
    for c, group in selected:
        row, pos = c['row'], c['pos']
        pid, gid, quarter = row['possession_id'], row['game_id'], row['quarter']
        game, side, idx = games[gid], pid.split('|')[1], int(pid.split('|')[2])
        events = raw[gid][side + 'Events']
        own_score = sum(e['type'] in (12, 19) for e in events[:idx])
        other_score = sum(e['type'] in (15, 23) for e in events[:idx])
        point_in_quarter = int(c['attempts'][0]['quarter_point'])
        time_left = 720 - int(pos['point_start_time'])
        start, end = max(0, round(c['estimate'] - 60)), min(round(game['durationSeconds']), round(c['estimate'] + 35))
        case = original_by_pid.get(pid)
        if case is None:
            next_number += 1
            first_rows, previous = [], idx
            for t in c['attempts']:
                event_idx = int(t['source_side_idx'])
                event = events[event_idx]
                xy = [float(t[k]) for k in ('tx', 'ty', 'rx', 'ry')]
                expected = [event['throwerX'], event['throwerY'], event.get('receiverX', event.get('turnoverX')), event.get('receiverY', event.get('turnoverY'))]
                assert all(math.isclose(a, b, abs_tol=1e-8) for a, b in zip(xy, expected))
                assert event['type'] == int(t['source_event_type'])
                first_rows.append({'n': int(t['ordinal']), 'from': names.get(t['Thrower'], t['Thrower']),
                                   'to': names.get(t['Receiver'], t['Receiver']) if t['Receiver'] else 'Unknown target',
                                   'xy': xy, 'outcome': TYPES[event['type']], 'huck': bool(int(t['huck'])),
                                   'sourceIndex': event_idx, 'before': [e['type'] for e in events[previous + 1:event_idx]]})
                previous = event_idx
            assert len(first_rows) == int(pos['throws'])
            pull = c['pull']
            case = {'id': f'R{next_number:03}', 'title': f"{row['team']} · Q{quarter} point {point_in_quarter} · opening possession",
                    'team': row['team'], 'quarter': quarter, 'point': point_in_quarter,
                    'gamePoint': sum(e['type'] in (1, 2) for e in events[:idx + 1]),
                    'pointNumberMeaning': 'Point within the quarter; use score and players to match video.',
                    'ownPossession': 1, 'sourceSide': side, 'pointStartIndex': idx,
                    'start': 'Opening receiving possession',
                    'prompt': 'Review the pull and first transfer before choosing a label.', 'throws': first_rows,
                    'film': {'start': clock(start), 'end': clock(end), 'score': f"Q{quarter} · {row['team']} {own_score}–{other_score} opponent",
                             'approximate': True, 'estimatedActionSeconds': round(c['estimate'], 1),
                             'timingSource': c['time_source'], 'reviewStatus': 'Awaiting film review.',
                             'observation': 'Estimated from preserved event timestamps and the existing game anchor; not frame-verified.'},
                    'possessionId': pid, 'libraryGroup': 'Pattern review expansion', 'libraryTags': ['Opening possession', f'Quarter {quarter}'],
                    'pointClock': clock(time_left), 'scoreLabel': f"{row['team']} {own_score}–{other_score} opponent",
                    'sourceCue': f"Q{quarter} · point begins {clock(time_left)} · {row['team']} {own_score}–{other_score}",
                    'possessionOutcome': pos['outcome'], 'sourceEndType': int(pos['end_type']),
                    'librarySelection': 'Unreviewed completed opening first throw; team-balanced targeted pattern review. No selection by later possession outcome.',
                    'timestampEvidence': {'timestamp': c['timestamp'], **c['time_source']}, 'filmUnavailable': None,
                    'pullEvidence': {'sourceSide': 'away' if side == 'home' else 'home', 'sourceIndex': pull[0], **pull[1]} if pull else None,
                    'recordedStoppage': any(pos[k] == 'True' for k in ('has_timeout', 'has_injury', 'has_penalty')),
                    'gameSource': {'game': gid, 'label': f"{game['title']} · {gid[:10]}", 'url': f'https://shownspace.com/game-center/{gid}',
                                   'source': 'Preserved ShownSpace export and hash-verified UFA event capture.',
                                   'rawSha256': receipts[gid]['sha256'], 'rawReceipt': receipts[gid]},
                    'filmSource': {'url': game['url'], 'title': game['title'], 'coverageNote': game.get('coverageNote'),
                                   'reviewMethod': 'Existing recording and anchor; new sequence windows are estimated, not individually replay-verified.',
                                   'timeNote': 'Confirm the scoreboard and first passer. Use Cannot tell or This is the wrong play when needed.'}}
            added.append(case)
        if pid not in frozen_case_ids:
            extension_cases.append(case)
        cue = f"Q{quarter}, point starts with {clock(time_left)} remaining; {row['team']} {own_score}–{other_score} opponent. Find {case['throws'][0]['from']} → {case['throws'][0]['to']}. Match this score and pass if the window includes another point."
        display = {'caseId': case['id'], 'start': start, 'end': end, 'cue': cue, 'timingStatus': 'estimated'}
        display_clips.append(display)
        private_clips.append({**display, 'possessionId': pid, 'gameId': gid, 'team': row['team'], 'quarter': quarter,
                              'selectionGroup': group, 'uncalibratedGeometryScore': c['score'],
                              'frozenPrediction': 'setup1' if c['score'] >= .5 else 'attack1',
                              'geometry': {k: row[k] for k in ('tx', 'ty', 'rx', 'ry', 'distance', 'forward_gain', 'inward_gain')},
                              'videoUrl': game['url'], 'anchor': c['anchor'], 'sourceTimestamp': c['timestamp'],
                              'predictionShownBeforeReview': False})
    assert len(display_clips) == len({c['caseId'] for c in display_clips}) == len(used) == 100
    assert used.isdisjoint(reviewed)
    assert Counter(c['selectionGroup'] for c in private_clips) == {'borderline_priority': 80, 'broader_example': 20}
    assert len({c['team'] for c in private_clips}) == 22
    display_batch = {'id': BATCH_ID, 'title': 'New · 100 possessions', 'caseIds': [c['caseId'] for c in display_clips], 'clips': display_clips}
    batch = {'id': BATCH_ID, 'createdOn': '2026-11-13', 'timezone': 'America/New_York', 'status': 'Ready for user film review',
             'size': 100, 'seed': SEED, 'candidatePool': len(candidates), 'exclusions': dict(exclusions),
             'selection': '20 broader examples, one randomly sampled opening per shuffled team for 20 teams; 80 uncertainty-prioritized examples allocated to the least represented teams. First-half openings from the existing 12-game recording library.',
             'scope': 'First completed physical throw on an unreviewed opening possession by the original lineup. Exclude exact-brick starts, prior labels, repeated-coordinate passes, missing navigation times and known unavailable footage.',
             'meaning': 'Targeted definition-development sample. Borderline priority is a geometry clue, not a claim that the film is necessarily ambiguous. Do not use this batch to estimate league centering prevalence or unbiased model accuracy.',
             'timing': 'Approximate 95-second windows from existing video anchors. Match score, quarter clock and passer; not 100 frame-verified clips.',
             'counts': {'teams': len(team_counts), 'games': len({c['gameId'] for c in private_clips}),
                        'byTeam': dict(sorted(team_counts.items())), 'byQuarter': dict(Counter(c['quarter'] for c in private_clips)),
                        'bySelectionGroup': dict(Counter(c['selectionGroup'] for c in private_clips)), 'newLibraryCases': len(extension_cases)},
             'displayBatch': display_batch, 'clips': private_clips, 'inputs': inputs,
             'validation': {'all100Unreviewed': True, 'uniquePossessions': True, 'originalSourceHashesChecked': True,
                            'all22TeamsCovered': True, 'firstHalfOnly': True, 'predictionsHidden': True,
                            'originalLibraryAndModelUnchanged': True, 'existingReviewsPreserved': True}}
    out = HERE / 'pattern_review_batch_100_2026-11-13.json'
    if out.exists():
        prior = json.loads(out.read_text())
        assert prior['displayBatch']['caseIds'] == display_batch['caseIds'], 'Existing batch is frozen; create a new version.'
        assert prior['inputs'] == inputs
    write(out, batch)
    write(HERE / 'film_library_extension_2026-11-13.json', {'createdOn': '2026-11-13', 'batchId': BATCH_ID,
          'purpose': 'Additional cases only; preserve the frozen original library and stable case IDs.', 'cases': extension_cases, 'inputs': inputs})
    data['cases'].extend(added)
    assert data['cases'][:len(original_cases)] == original_cases
    # Newly captured review metadata may change without changing its decision.
    # Preserve any such latest browser details in the derived UI layer.
    for review in browser_reviews:
        case = next(c for c in data['cases'] if c['possessionId'] == review['possessionId'])
        if case.get('currentReviewedReview') and case['currentReviewedReview'] != review:
            case['currentReviewedReview'] = review
    data['activeFilmReviewBatch'] = {'id': BATCH_ID, 'size': 100, 'games': batch['counts']['games'],
                                    'teams': 22, 'borderlinePriority': 80, 'broaderExamples': 20,
                                    'predictionsHidden': True, 'timingStatus': 'estimated'}
    source = re.sub(r'^const DATA = .*;$', lambda _: 'const DATA = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';', source, flags=re.M)
    if 'const PREVIOUS_REVIEW =' not in source:
        old_next = re.search(r'^const NEXT_REVIEW = (.*);$', source, re.M).group(1)
        source = re.sub(r'^const NEXT_REVIEW = .*;$', lambda _: 'const PREVIOUS_REVIEW = ' + old_next + ';\nconst NEXT_REVIEW = ' + json.dumps(display_batch, ensure_ascii=False, separators=(',', ':')) + ';', source, flags=re.M)
    else:
        source = re.sub(r'^const NEXT_REVIEW = .*;$', lambda _: 'const NEXT_REVIEW = ' + json.dumps(display_batch, ensure_ascii=False, separators=(',', ':')) + ';', source, flags=re.M)
    assert re.search(r'^const ASSISTED = (.*);$', source, re.M).group(1) == assisted
    CANVAS.write_text(source)
    MANAGED.write_text(source)
    notes_path = HERE / 'review_notes.json'
    notes = json.loads(notes_path.read_text())
    notes['filmReviewWorkflowPreference'] = {
        'source': 'User instruction in chat, November 13, 2026',
        'afterSetFinished': 'Archive the completed labels and prepare a fresh set of unreviewed possessions in the same reviewer. Do not replace the requested next set with analysis only.',
        'currentRequestedBatchSize': 100,
        'selectionPreference': 'Emphasize borderline examples where film judgment can distinguish centering from a reset or other non-centering pass. Retain some broader examples.',
        'display': 'Keep model predictions hidden. Preserve notes, dictation, saved labels and earlier review sets.',
    }
    notes['activeReviewBatch'] = {'id': BATCH_ID, 'path': str(out.relative_to(ROOT)), 'size': 100,
                                 'status': 'Ready for user film review', 'priorCompletedBatch': frozen['id']}
    write(notes_path, notes)
    assert all(sha(paths[k]) == v['sha256'] for k, v in inputs.items())
    print(json.dumps({'size': 100, 'candidatePool': len(candidates), **batch['counts']}, indent=2))


if __name__ == '__main__':
    main()
