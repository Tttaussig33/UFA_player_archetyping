"""Archive film labels and audit their implications without refitting outcomes."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RAW = ROOT / 'research/dead_disc_study/raw_events'
BATCH_GAME = '2026-05-09-PHI-CAR'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    library = json.loads((HERE / 'film_library.json').read_text())
    cases = {c['possessionId']: c for c in library['cases']}
    followup_path = HERE / 'review_followup_2026-11-12.json'
    followup = json.loads(followup_path.read_text()) if followup_path.exists() else {'checks': []}
    next_batch_path = HERE / 'next_review_batch_2026-11-12.json'
    next_batch = json.loads(next_batch_path.read_text()) if next_batch_path.exists() else None
    checks_by_case = {}
    for check in followup['checks']:
        checks_by_case.setdefault(check['caseId'], []).append(check)
    decisions = {}
    exports = []
    for path in sorted((HERE / 'annotations').glob('*-browser-export.json')):
        payload = json.loads(path.read_text())
        exports.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(path)})
        for review in payload['reviews']:
            pid = review['possessionId']
            assert pid in cases and cases[pid]['id'] == review['caseId']
            assert review.get('decision') in {'setup1', 'attack1', 'no_attack', 'other', 'unclear', 'mismatch'}
            previous = decisions.get(pid)
            if previous is None or review.get('reviewedOn', '') >= previous.get('reviewedOn', ''):
                decisions[pid] = review
    batch = [r for pid, r in decisions.items() if pid.startswith(BATCH_GAME + '|')]
    assert len(batch) == 14
    (HERE / 'annotations/reviewed_decisions.json').write_text(json.dumps({
        'updatedOn': '2026-11-12', 'sourceExports': exports,
        'reviews': list(decisions.values()),
        'policy': 'Verbatim user selections and notes; no inferred film labels. Browser edits take precedence in the review UI.'
    }, ensure_ascii=False, indent=2) + '\n')

    ppath = ROOT / 'research/oline_possessions/possessions.csv'
    p = pd.read_csv(ppath)
    receipts = json.loads((RAW / 'source_receipt.json').read_text())
    raw_cache = {}
    contexts = {}
    lineup_counts = Counter()
    for q in p.itertuples(index=False):
        if q.GameID not in raw_cache:
            path = RAW / (q.GameID + '.json')
            assert sha(path) == receipts[q.GameID]['sha256']
            raw_cache[q.GameID] = json.loads(path.read_text())['data']
        side = q.possession_id.split('|')[1]
        es = raw_cache[q.GameID][side + 'Events']
        point_idx = int(q.point_id.rsplit('|', 1)[1])
        initial = es[point_idx].get('line', [])
        valid = lambda line: len(line) == 7 and len(set(line)) == 7
        latest = initial
        lineup_events = []
        timeouts_before = []
        for i in range(point_idx, int(q.start_idx) + 1):
            event = es[i]
            if 'line' in event:
                latest = event['line']
                if i != point_idx:
                    lineup_events.append({'sourceIndex': i, 'type': event['type'], 'line': latest, 'clockElapsed': event.get('time')})
            if event['type'] in {3, 5}:
                timeouts_before.append(i)
        overlap = len(set(initial) & set(latest)) if valid(initial) and valid(latest) else None
        during = [i for i in range(int(q.start_idx) + 1, int(q.end_idx) + 1) if es[i]['type'] in {3, 5}]
        assert bool(timeouts_before) == bool(q.prior_timeout)
        assert bool(during) == bool(q.has_timeout)
        context = {'possessionId': q.possession_id, 'openingLine': initial, 'lineAtPossessionStart': latest,
            'playersFromOpeningLine': overlap, 'lineupEventsBefore': lineup_events,
            'timeoutBefore': bool(timeouts_before), 'timeoutDuring': bool(during),
            'timeoutSourceIndicesBefore': timeouts_before, 'timeoutSourceIndicesDuring': during,
            'rawPointStartIndex': point_idx, 'rawPossessionStartIndex': int(q.start_idx),
            'recordedPointStartSecondsRemaining': 720 - int(q.point_start_time) if q.quarter <= 4 else None,
            'clockLimit': 'This is the point-start clock, not the start time of each later possession. Wall-clock operator timestamps are not elapsed playing time.'}
        contexts[q.possession_id] = context
        if not q.has_timeout and q.prior_timeout:
            lineup_counts['unknown' if overlap is None else 'same_seven' if overlap == 7 else 'changed_players'] += 1

    all_rows = []
    p_by_id = p.set_index('possession_id')
    for review in decisions.values():
        c = cases[review['possessionId']]
        q = p_by_id.loc[review['possessionId']]
        first = c['throws'][0]
        x, y, rx, ry = first['xy']
        review_checks = checks_by_case.get(c['id'], [])
        label_on_hold = any(check.get('blocksAttackingCount') for check in review_checks)
        attack_number = None if label_on_hold else 2 if review['decision'] == 'setup1' else 1 if review['decision'] == 'attack1' else None
        attacking = c['throws'][attack_number - 1:] if attack_number else []
        attack_xy = attacking[0]['xy'][:2] if attacking else None
        all_rows.append({'caseId': c['id'], 'possessionId': c['possessionId'], 'team': c['team'],
            'point': c['point'], 'ownPossession': c['ownPossession'], 'review': review,
            'reviewChecks': review_checks,
            'attackingCountStatus': 'Held: clip-to-possession match unresolved' if any(check['category'] == 'clip_alignment' and check.get('blocksAttackingCount') for check in review_checks) else 'Unresolved film classification' if attack_number is None else 'Derived from human label; cohort eligibility remains separate',
            'fieldPositionMatchStatus': 'Held: start location requires reconciliation' if any(check.get('blocksFieldPositionMatch') for check in review_checks) else 'Not independently verified by this label',
            'originalThrows': int(q['throws']), 'attackingThrows': len(attacking) if attack_number else None,
            'firstAttackingThrow': attack_number, 'firstThrowXY': first['xy'],
            'firstThrowDistance': round(math.hypot(rx - x, ry - y), 2), 'firstPassMovesInward': abs(rx) < abs(x),
            'attackStartXY': attack_xy, 'attackStartYardsToGoal': 100 - attack_xy[1] if attack_xy else None,
            'originalStartYardsToGoal': 100 - y, 'originalOutcome': q['outcome'],
            'originalPointHold': int(q.point_hold), 'originalHucks': int(q.hucks),
            'context': contexts[c['possessionId']]})
    all_rows.sort(key=lambda r: r['caseId'])
    rows = [r for r in all_rows if r['possessionId'].startswith(BATCH_GAME + '|')]
    opens = [r for r in rows if r['ownPossession'] == 1]
    later = [r for r in rows if r['ownPossession'] > 1]
    counts = lambda rr: dict(Counter(r['review']['decision'] for r in rr))
    by_context = {}
    for r in rows:
        by_context.setdefault(r['review']['context'], Counter())[r['review']['decision']] += 1
    by_id = {r['caseId']: r for r in rows}
    assert by_id['R024']['context']['playersFromOpeningLine'] == 0
    assert by_id['R025']['context']['playersFromOpeningLine'] == 0
    assert by_id['R033']['context']['recordedPointStartSecondsRemaining'] == 4
    assert sum(r['originalThrows'] - r['attackingThrows'] for r in rows) == 5

    next_reasons = {
        'R038': 'Short inward pass from near the sideline: does the start already belong to the attack?',
        'R047': 'An ordinary-looking Toronto opening: check the rule on a different team.',
        'R052': 'Recorded at brick coordinates: confirm the actual restart and the first attacking throw.',
        'R053': 'Same point, later possession, again at brick coordinates: does the film support that location?',
        'R060': 'Recorded point start has four seconds left, yet the first pass is short: confirm the clock and how the attack starts.',
        'R075': 'Short inward Seattle opening: identify setup from the action, not direction alone.',
        'R076': 'Short Seattle opening moving away from the middle: could this still be setup?',
        'R094': 'First pass is incomplete: was the attempted pass setup or attack? Keep the turnover either way.',
        'R097': 'A later Oregon possession begins with a short inward pass and includes a stoppage: inspect the transition.'
    }
    next_cases = []
    for cid, reason in next_reasons.items():
        c = next(c for c in library['cases'] if c['id'] == cid)
        assert c['libraryGroup'] == 'Definition development'
        next_cases.append({'caseId': cid, 'possessionId': c['possessionId'], 'gameId': c['gameSource']['game'], 'reason': reason})

    contrasting = [r for r in all_rows if r['caseId'] in next_reasons]
    cumulative_opens = [r for r in all_rows if r['ownPossession'] == 1]
    cumulative_later = [r for r in all_rows if r['ownPossession'] > 1]
    assert len(contrasting) == 9
    released_ids = set(next_batch['caseIds']) if next_batch else set()
    assert all(cases[r['possessionId']]['libraryGroup'] != 'Reserved validation' or r['caseId'] in released_ids for r in decisions.values())
    assisted = [r for r in all_rows if r['review'].get('reviewMode') == 'assisted']
    assisted_checks = [check for check in followup['checks'] if check['caseId'] in {r['caseId'] for r in assisted}]
    if assisted:
        assert len(assisted) == 12
        assert next(r for r in assisted if r['caseId'] == 'R003')['review']['decision'] == 'setup1'
        assert next(r for r in assisted if r['caseId'] == 'R005')['context']['playersFromOpeningLine'] == 0
        assert all(r['attackingThrows'] is None for r in assisted if any(c.get('blocksAttackingCount') for c in r['reviewChecks']))
    timeout_policy = {
        'status': 'Adopted by user on 2026-11-12; full-cohort implementation pending',
        'unit': 'The original receiving-point lineup, followed across its offensive possessions.',
        'rule': 'Keep completed possessions before a timeout substitution changes the original lineup. Exclude possessions played by replacement players from the original-line comparison; label them not applicable because of substitution, never zero or unsuccessful.',
        'completedBeforeChange': 'Keep physical throws, identified attacking throws, hucks and the observed goal or turnover from each completed original-line possession.',
        'interruptedPossession': 'If the lineup changes during a possession, preserve the earlier actions as a partial record. Do not treat that partial record as a completed possession, use it in mean completed-possession length or scoring rate, or attach a later lineup\u2019s goal/turnover to it.',
        'unresolvedOutcome': 'An eventual hold, break or defensive recovery resolved after the original players are replaced is not applicable to the original-line outcome analysis. Do not recode it as a failed recovery or a break. Preserve the actual receiving-team outcome in the source record.',
        'timeoutWithoutSubstitution': 'A timeout alone does not establish a new lineup. Flag it separately because rest or tactical changes can still affect behavior; do not silently equate it with a replacement line.',
        'partialSubstitution': 'For the primary comparison, use the conservative implementation of the same original seven. Flag any recorded substitution, including partial changes. Stop the original-line sequence at its first lineup change; do not resume it by renumbering later possessions.',
        'unknownLineup': 'Unknown personnel remain unverified; do not assume the original seven continued.',
        'reporting': 'Report retained complete possessions, interrupted partial possessions and excluded later possessions separately. Explain that later-possession results apply only to original groups that recover the disc and remain on the field.',
        'example': {'included': ['R023'], 'notApplicableAfterSubstitution': ['R024', 'R025'], 'originalPhysicalThrows': 6, 'originalAttackingThrows': 5, 'originalPossessionOutcome': 'turnover'}
    }

    definition = (
        'Opening setup is the first transfer after an in-bounds pull is caught or picked up, when that transfer hands the disc to the player who starts the offense. '
        'It need not move toward the middle. If the pull receiver attacks directly, including when the defense prevents an opening transfer, recorded throw 1 is already attacking. '
        'After one confirmed setup transfer, all later passes count as attacking, including handler weaves, resets, and passes to an open handler. '
        'For a confirmed brick or sideline restart, or a later possession after a turnover, count the first pass as attacking. '
        'Bringing a turnover to the goal line or tapping it in does not create a pull setup. '
        'A failed setup attempt remains a turnover in the full-possession record; it can have zero attacking throws. '
        'Caught-versus-grounded pull handling may be unclear even when setup is clear. A penalty before the first brick-start pass does not turn that pass into setup. '
        'Use an uncertain label when the film does not settle the distinction. Opening setup is a working expectation with explicit exceptions, not a reason to remove every opening pass automatically.'
    )
    audit = {'updatedOn': '2026-11-12', 'gameId': BATCH_GAME, 'batchSize': 14,
        'totalArchivedDecisions': len(decisions), 'openingPossessions': len(opens), 'subsequentPossessions': len(later),
        'decisionCounts': counts(rows), 'openingDecisions': counts(opens), 'subsequentDecisions': counts(later),
        'contextCounts': {k: dict(v) for k, v in by_context.items()}, 'rows': rows,
        'allReviewedRows': all_rows,
        'definition': definition, 'classificationStatus': f'{len(decisions)} archived user decisions, including unclear labels and records held for alignment checks. Assisted reviews are development data; no held-out accuracy or league-wide automatic labels.',
        'cumulativeSummary': {'reviewedPossessions': len(all_rows), 'games': len({r['possessionId'].split('|')[0] for r in all_rows}),
            'openingPossessions': len(cumulative_opens), 'subsequentPossessions': len(cumulative_later),
            'openingDecisions': counts(cumulative_opens), 'subsequentDecisions': counts(cumulative_later),
            'limit': 'Raw saved label counts, including unclear labels and unresolved clip-to-record matches. Purposefully selected development examples, including replacement-line cases. These are not validated-label totals, league prevalence, accuracy or eligible outcome denominators.'},
        'assistedBatch': {'reviewedPossessions': len(assisted), 'games': len({r['possessionId'].split('|')[0] for r in assisted}),
            'status': 'All twelve reviews archived; follow-up checks remain', 'rows': assisted,
            'decisionCounts': counts(assisted), 'openingDecisions': counts([r for r in assisted if r['ownPossession'] == 1]),
            'subsequentDecisions': counts([r for r in assisted if r['ownPossession'] > 1]),
            'unclearCaseIds': [r['caseId'] for r in assisted if r['review']['decision'] == 'unclear'],
            'alignmentHoldCaseIds': [r['caseId'] for r in assisted if any(c['category'] == 'clip_alignment' and c.get('blocksAttackingCount') for c in r['reviewChecks'])],
            'checks': assisted_checks, 'clarifications': followup.get('clarifications', []),
            'limit': 'Original suggestions were visible during review. Agreement is not an independent accuracy estimate. Saved labels remain separate from verified clip alignment, field position and lineup eligibility.'},
        'contrastingBatch': {'reviewedPossessions': len(contrasting), 'rows': contrasting,
            'openingDecisions': counts([r for r in contrasting if r['ownPossession'] == 1]),
            'subsequentDecisions': counts([r for r in contrasting if r['ownPossession'] > 1]),
            'contextChecks': [
                {'caseId': 'R047', 'issue': 'Setup label is clear; whether the pull was caught or grounded remains unknown. Preserve that distinction.'},
                {'caseId': 'R052', 'issue': 'Film note reports a brick start plus a ten-yard penalty before the first pass. Reconcile the recorded start location before using this possession in field-position matching.'},
                {'caseId': 'R053', 'issue': 'Film note reports retrieving a turnover and bringing it to a goal line. Verify that the recorded brick-like coordinates reflect the actual first attacking location before matching.'},
                {'caseId': 'R060', 'issue': 'Setup is confirmed even though the point-start record has four seconds left. The review does not independently confirm that clock; late-clock eligibility remains separate.'}
            ]},
        'timeoutPolicy': timeout_policy,
        'simpleRuleChecks': {
            'alwaysRemoveOpeningPass': {'wrongCaseIds': [r['caseId'] for r in opens if r['review']['decision'] != 'setup1'], 'checked': len(opens)},
            'caughtOrGroundedPullAlwaysSetup': {'wrongCaseIds': [r['caseId'] for r in opens if r['review']['context'] in {'caught_pull', 'grounded_pull'} and r['review']['decision'] != 'setup1'], 'checked': sum(r['review']['context'] in {'caught_pull', 'grounded_pull'} for r in opens)},
            'geometryCounterexample': ['R021', 'R023'], 'limit': 'These checks reject simple blanket rules; they do not estimate a trained classifier’s performance.'},
        'scopeIssues': {
            'timeout': {'cases': ['R023', 'R024', 'R025'], 'pointHold': True, 'openingPlayersRemainingInLaterLineup': 0,
                'record': 'Carolina home event 29 is a timeout lineup update; the seven IDs differ from home event 22. Later possessions start at home indices 30 and 40.',
                'metricPolicyAdopted': timeout_policy['rule']},
            'lateQuarter': {'caseId': 'R033', 'pointStartSecondsRemaining': 4, 'status': 'Flagged for a separate end-of-quarter category. No league-wide cutoff selected or applied.',
                'clockLimit': 'Point-start clock cannot identify every later possession that begins near the horn; do not substitute it for possession-start elapsed time.'},
            'contextClarification': {'caseId': 'R020', 'issue': 'Dropdown says grounded pull; note says caught pull. Setup decision is consistent. Keep both original fields and verify start context before using caught-versus-grounded features.'}},
        'existingCohortAudit': {'possessions': len(p), 'retainedByOldWithinPossessionTimeoutFilter': int((~p.has_timeout).sum()),
            'retainedDespiteEarlierTimeout': int((~p.has_timeout & p.prior_timeout).sum()),
            'lineupsForThosePossessions': dict(lineup_counts),
            'note': 'Existing comparisons exclude timeouts within a possession but retain possessions following an earlier timeout. They describe receiving-team roles and do not isolate the original O-line personnel.',
            'action': 'Replacement-line exclusion is now adopted. Existing figures have not yet been recalculated under that policy.'},
        'nextReview': {'title': 'Completed: nine contrasting starts', 'status': 'complete', 'cases': next_cases, 'games': len({c['gameId'] for c in next_cases}),
            'purpose': 'All nine labels archived. These deliberately selected development examples refined the rule; they are not an accuracy sample. The next validation step is to test the written rule on the four reserved games.'},
        'sources': {'exports': exports, 'followup': {'path': str(followup_path.relative_to(ROOT)), 'sha256': sha(followup_path)} if followup_path.exists() else None, 'possessionsSha256': sha(ppath),
            'rawGames': {gid: receipts[gid] for gid in raw_cache},
            'filmSource': next(c['filmSource']['url'] for c in library['cases'] if c.get('gameSource', {}).get('game') == BATCH_GAME)},
        'checks': [f'All {len(decisions)} decision keys resolve to one library possession.', 'All browser exports preserved verbatim; latest timestamp used for repeated decisions.',
            'Raw source hashes match the capture receipts.', 'Prior and within-possession timeout flags independently reconciled against source event indices.',
            'Two post-timeout Carolina lineups have zero overlap with the point-start seven.',
            'Five confirmed setup transfers produce five fewer attacking throws in this batch; original throws and outcomes are retained.',
            'All nine contrasting starts and twelve assisted reviews are development cases; only the explicitly released new-game cases may be reviewed from the reserved games.',
            'Unresolved clip matches have no derived attacking-throw count; raw user choices and original possession records remain intact.',
            'R003 is setup after explicit user clarification; R002 note refers to the second pass.',
            'Houston R005 has zero overlap with the opening seven after a timeout; its attack label does not establish original-line eligibility.']}
    if next_batch:
        reviewed_ids = {r['caseId'] for r in decisions.values()}
        reviewed_new = [cid for cid in next_batch['caseIds'] if cid in reviewed_ids]
        audit['nextReview'] = {
            'title': next_batch['title'],
            'status': 'reviewed' if len(reviewed_new) == len(next_batch['caseIds']) else next_batch['status'],
            'cases': [{'caseId': c['caseId'], 'possessionId': c['possessionId'], 'gameId': c['gameId']} for c in next_batch['clips']],
            'games': len({c['gameId'] for c in next_batch['clips']}),
            'reviewed': len(reviewed_new), 'total': len(next_batch['caseIds']),
            'purpose': next_batch['purpose'], 'limit': next_batch['classificationStatus'],
            'source': {'path': str(next_batch_path.relative_to(ROOT)), 'sha256': sha(next_batch_path)},
            'note': 'Completing a review does not resolve every unclear label or establish automatic classification accuracy.'
        }
    (HERE / 'review_batch_2026-11-12.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: audit[k] for k in ['batchSize', 'totalArchivedDecisions', 'openingDecisions', 'subsequentDecisions', 'existingCohortAudit']}, indent=2))


if __name__ == '__main__':
    main()
