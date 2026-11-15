"""Activate twelve fresh cases from the preserved, unreviewed 100-case pool.

This is targeted definition development, not a prevalence or accuracy sample.
The frozen geometry score only prioritizes film navigation; it is not a label.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json
import random
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CANVAS = ROOT / 'research/previews/UFA-possession-review.canvas.tsx'
MANAGED = Path('/Users/teddytaussig/.cursor/projects/Users-teddytaussig-Desktop-Work-UFA-player-archetyping/canvases/UFA-possession-review.canvas.tsx')
BATCH_ID = 'opening-pattern-review-12-20261114-v1'
SEED = 2026111403


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def main():
    source = CANVAS.read_text()
    assert source == MANAGED.read_text(), 'Reconcile user edits first.'
    data = json.loads(re.search(r'^const DATA = (.*);$', source, re.M).group(1))
    source_path = HERE / 'pattern_review_batch_100_2026-11-14.json'
    reviews_path = HERE / 'annotations/2026-11-14-completed-100-browser-export.json'
    pool = json.loads(source_path.read_text())
    reviews = json.loads(reviews_path.read_text())['reviews']
    reviewed = {r['possessionId'] for r in reviews}
    fingerprints = {str(p.relative_to(ROOT)): sha(p) for p in [source_path, reviews_path,
        HERE / 'annotations/current_reviewed_decisions.json',
        HERE / 'pattern_review_batch_100_2026-11-13.json']}
    game_ids = list(dict.fromkeys(c['gameId'] for c in pool['clips']))
    broader_games = {'2026-05-02-CHI-MIN', '2026-05-09-MTL-TOR',
                     '2026-06-05-CAR-DC', '2026-06-13-SD-COL'}
    rng = random.Random(SEED)
    selected = []
    for gid in game_ids:
        candidates = [c for c in pool['clips'] if c['gameId'] == gid and c['start'] > 0
                      and c['possessionId'] not in reviewed]
        # This navigation filter avoids obvious short-clock review examples;
        # it does not label/exclude whole-league possessions from analysis.
        candidates = [c for c in candidates if (lambda m: int(m[1])*60+int(m[2]) > 60)(
            re.search(r'with (\d+):(\d+) remaining', c['cue']))]
        earlier = [c for c in candidates if c['quarter'] < 3]
        candidates = earlier or candidates
        if gid in broader_games:
            broader = [c for c in candidates if c['selectionGroup'] == 'broader_example']
            chosen = rng.choice(broader or candidates)
            reason = 'broader_example'
        else:
            chosen = min(candidates, key=lambda c: (abs(c['uncalibratedGeometryScore']-.5), c['caseId']))
            reason = 'geometry_priority'
        selected.append({**chosen, 'next12SelectionGroup': reason})
    assert len(selected) == len({c['possessionId'] for c in selected}) == 12
    assert all(c['possessionId'] not in reviewed for c in selected)
    display = {'id': BATCH_ID, 'title': 'New · 12 possessions',
               'caseIds': [c['caseId'] for c in selected],
               'clips': [{k:c[k] for k in ['caseId','start','end','cue','timingStatus']} for c in selected]}
    counts = {'games': len(game_ids), 'teams': len({c['team'] for c in selected}),
              'byQuarter': dict(Counter(c['quarter'] for c in selected)),
              'bySelectionGroup': dict(Counter(c['next12SelectionGroup'] for c in selected))}
    batch = {'id': BATCH_ID, 'createdOn': '2026-11-14', 'size': 12,
             'status': 'Ready for user film review', 'seed': SEED,
             'selection': 'One fresh opening per recording: eight geometry-prioritized and four broader examples. Prefer Q1–Q2 where available; skip clipped zero-second navigation windows and points starting with <=60 seconds. This is a targeted development sample, not a random league audit.',
             'timing': 'Approximate windows inherited from the prepared pool; match the displayed score, clock and passer. Clips have not all been individually film-verified.',
             'counts': counts, 'displayBatch': display, 'clips': selected,
             'preservedInputs': fingerprints,
             'inactivePreparedPool': str(source_path.relative_to(ROOT)),
             'definitionVersion': data['centeringDefinition']['version']}
    out = HERE / 'next_review_batch_12_2026-11-14.json'
    if out.exists():
        assert json.loads(out.read_text())['displayBatch']['caseIds'] == display['caseIds']
    write(out, batch)
    data['activeFilmReviewBatch'] = {'id': BATCH_ID, 'size': 12,
        'games': counts['games'], 'teams': counts['teams'], 'borderlinePriority': 8,
        'broaderExamples': 4, 'predictionsHidden': True, 'timingStatus': 'estimated'}
    data['inactivePreparedFilmReviewBatch'] = {'id': pool['id'], 'size': 100,
        'status': 'Preserved candidate pool; superseded as the active set by user request',
        'replacementId': BATCH_ID}
    source = re.sub(r'^const DATA = .*;$', lambda _: 'const DATA = '+json.dumps(data, ensure_ascii=False, separators=(',', ':'))+';', source, flags=re.M)
    source = re.sub(r'^const NEXT_REVIEW = .*;$', lambda _: 'const NEXT_REVIEW = '+json.dumps(display, ensure_ascii=False, separators=(',', ':'))+';', source, flags=re.M)
    source = source.replace('100 new openings · 22 teams · 12 games. Earlier reviews are saved in the review-set menu.',
                            '12 fresh openings · 12 games. Your completed reviews remain in the review-set menu.')
    CANVAS.write_text(source)
    MANAGED.write_text(source)
    notes_path = HERE / 'review_notes.json'
    notes = json.loads(notes_path.read_text())
    notes.setdefault('supersededFilmReviewWorkflowPreference', notes['filmReviewWorkflowPreference'])
    notes['filmReviewWorkflowPreference'] = {
        'source': 'User clarification in chat, November 14, 2026: Replace it with 12 next.',
        'afterSetFinished': 'Preserve completed labels. Do not automatically queue another batch; assess whether targeted review or analysis is the useful next step.',
        'defaultBatchSize': 12, 'currentRequestedBatchSize': 12,
        'selectionPreference': 'Small targeted batches with difficult cases and some broader examples; prioritize reducing unnecessary manual review.',
        'display': 'Preserve notes, dictation, labels and earlier sets. Keep unvalidated predictions hidden.'}
    notes['inactivePreparedReviewBatch'] = {'id': pool['id'], 'path': str(source_path.relative_to(ROOT)),
        'size': 100, 'status': 'Archived candidate pool, not the active review assignment'}
    notes['activeReviewBatch'] = {'id': BATCH_ID, 'path': str(out.relative_to(ROOT)), 'size': 12,
        'status': 'Ready for user film review', 'priorCompletedBatch': 'opening-pattern-review-100-20261113-v1'}
    write(notes_path, notes)
    assert all(sha(ROOT/p) == digest for p,digest in fingerprints.items())
    after = json.loads(re.search(r'^const DATA = (.*);$', CANVAS.read_text(), re.M).group(1))
    embedded = {c['possessionId']:c.get('currentReviewedReview') for c in after['cases']}
    assert all(embedded[r['possessionId']] == r for r in reviews)
    print(json.dumps({'activeSize':12, **counts, 'caseIds':display['caseIds'],
                      'savedReviewsPreserved':len(reviews), 'archived100Unchanged':True}))


if __name__ == '__main__':
    main()
