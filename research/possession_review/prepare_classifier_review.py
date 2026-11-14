"""Put the frozen pilot batch into the existing film reviewer, without hints."""
from pathlib import Path
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CANVAS = REPO / 'research/previews/UFA-possession-review.canvas.tsx'
MANAGED = Path('/Users/teddytaussig/.cursor/projects/Users-teddytaussig-Desktop-Work-UFA-player-archetyping/canvases/UFA-possession-review.canvas.tsx')


def main():
    source = CANVAS.read_text()
    assert source == MANAGED.read_text(), 'Reconcile user edits before updating the review batch.'
    pilot_path = HERE / 'opening_classifier_pilot.json'
    pilot = json.loads(pilot_path.read_text())
    batch = pilot['prospective_batch']
    timing_path = HERE / 'classifier_clip_timing_checks_2026-11-13.json'
    timings = json.loads(timing_path.read_text())['cases'] if timing_path.exists() else {}
    data_before = re.search(r'^const DATA = (.*);$', source, re.M).group(1)
    assisted_before = re.search(r'^const ASSISTED = (.*);$', source, re.M).group(1)
    data = json.loads(data_before)
    by_id = {c['id']: c for c in data['cases']}
    archived_before = {c['id']: c.get('savedReview') for c in data['cases']}
    definition_path = HERE / 'centering_definition.json'
    confirmations_path = HERE / 'annotations/classifier-pilot-chat-confirmations.json'
    confirmations = json.loads(confirmations_path.read_text()) if confirmations_path.exists() else {'reviews': []}
    for confirmation in confirmations['reviews']:
        case = by_id[confirmation['caseId']]
        assert case['possessionId'] == confirmation['possessionId']
        assert confirmation['reviewBatch'] == batch['id']
        case['chatConfirmedReview'] = confirmation
    for check in confirmations.get('alignmentChecks', []):
        case = by_id[check['caseId']]
        assert case['possessionId'] == check['possessionId']
        assert check['reviewBatch'] == batch['id']
        if check.get('alignmentStatus') != 'resolved':
            case['chatConfirmedReview'] = check
    data['chatConfirmedPilotCount'] = len(confirmations['reviews'])
    current_path = HERE / 'annotations/current_reviewed_decisions.json'
    current_reviews = json.loads(current_path.read_text())['reviews'] if current_path.exists() else []
    for review in current_reviews:
        case = by_id[review['caseId']]
        assert case['possessionId'] == review['possessionId']
        if not case.get('savedReview'):
            case['currentReviewedReview'] = review
    evaluation_path = HERE / 'completed_classifier_pilot_2026-11-13.json'
    evaluation = json.loads(evaluation_path.read_text()) if evaluation_path.exists() else None
    if evaluation:
        assert evaluation['inputs']['frozen_pilot']['sha256'] == hashlib.sha256(pilot_path.read_bytes()).hexdigest()
        data['completedPilot'] = evaluation
    bounds_path = REPO / 'research/oline_possessions/centering_sensitivity_bounds.json'
    if bounds_path.exists():
        data['centeringSensitivity'] = json.loads(bounds_path.read_text())
    if definition_path.exists():
        data['centeringDefinition'] = json.loads(definition_path.read_text())
    assert {c['id']: c.get('savedReview') for c in data['cases']} == archived_before
    source = re.sub(r'^const DATA = .*;$', lambda _: 'const DATA = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';', source, flags=re.M)
    clips = []
    for clip in batch['clips']:
        case = by_id[clip['caseId']]
        assert not case.get('savedReview', {}).get('decision')
        assert case['ownPossession'] == 1 and not case.get('filmUnavailable')
        # Do not embed predictions, feature scores or selection categories in the form.
        displayed = {key: clip[key] for key in ('caseId', 'start', 'end', 'cue', 'timingStatus')}
        if case['throws'][0]['to'] == 'Unknown target':
            displayed['cue'] = f"Quarter {case['quarter']}, point starts with {case['pointClock']} remaining. Follow the pull and {case['throws'][0]['from']}'s first throw. The intended receiver is not named in the record."
        if clip['caseId'] in timings:
            displayed.update({key: timings[clip['caseId']][key]
                              for key in ('start', 'end', 'cue', 'timingStatus')})
        check = next((r for r in confirmations.get('alignmentChecks', [])
                      if r['caseId'] == clip['caseId']), None)
        if check:
            displayed['cue'] = check['correctedCue']
        clips.append(displayed)
    display_batch = {'id': batch['id'], 'title': 'Pilot · 12 clips', 'caseIds': batch['caseIds'], 'clips': clips}
    source, count = re.subn(r'^const NEXT_REVIEW = .*;$',
                           lambda _: 'const NEXT_REVIEW = ' + json.dumps(display_batch, separators=(',', ':'), ensure_ascii=False) + ';',
                           source, flags=re.M)
    assert count == 1
    old = '<div className="film-brand"><span className="film-eyebrow">UFA · Film room</span><H1>Opening throws</H1></div>'
    new = '<div className="film-brand"><span className="film-eyebrow">UFA · Film room</span><H1>Opening throws</H1><p className="film-note-status">Classify whether the opening pass is a clear centering pass. Predictions stay hidden during this check.</p></div>'
    if old in source:
        source = source.replace(old, new, 1)
    assert new in source
    assert re.search(r'^const ASSISTED = (.*);$', source, re.M).group(1) == assisted_before
    CANVAS.write_text(source)
    MANAGED.write_text(source)
    record = {'id': batch['id'], 'createdOn': '2026-11-13', 'status': 'All 12 labels archived and evaluated' if evaluation else 'Awaiting user film labels',
              'displayBatch': display_batch, 'predictionsShown': False,
              'frozenPilot': {'path': str(pilot_path.relative_to(REPO)),
                              'sha256': hashlib.sha256(pilot_path.read_bytes()).hexdigest()},
              'chatConfirmedReviews': len(confirmations['reviews']),
              'alignmentChecks': len(confirmations.get('alignmentChecks', [])),
              'unresolvedAlignmentChecks': sum(r.get('alignmentStatus') != 'resolved' for r in confirmations.get('alignmentChecks', [])),
              'sampledPilotLabels': evaluation['overall']['n'] if evaluation else sum(r['caseId'] in batch['caseIds'] for r in confirmations['reviews']),
              'definition': str(definition_path.relative_to(REPO)) if definition_path.exists() else None,
              'preservation': {'archivedReviews': 52, 'originalArchivedReviewObjectsUnchanged': True,
                               'pastSuggestionsUnchanged': True, 'reviewStorageKeyUnchanged': True,
                               'storedDecisionCodesAndDictationUnchanged': True},
              'timing': 'Existing estimated windows unless separately checked in the timing audit.'}
    (HERE / 'next_classifier_review_2026-11-13.json').write_text(json.dumps(record, indent=2, ensure_ascii=False)+'\n')
    notes_path = HERE / 'review_notes.json'
    notes = json.loads(notes_path.read_text())
    if definition_path.exists():
        notes['currentCenteringDefinition'] = data['centeringDefinition']
        notes['pilotChatConfirmations'] = {'path': str(confirmations_path.relative_to(REPO)), 'count': len(confirmations['reviews']), 'alignmentChecks': len(confirmations.get('alignmentChecks', []))}
    notes['classificationPilot2026_11_13'] = {
        'pilot': str(pilot_path.relative_to(REPO)),
        'batch': 'research/possession_review/next_classifier_review_2026-11-13.json',
        'developmentOpenings': 27, 'developmentGames': 10,
        'centeringCorrect': '21 of 21', 'immediateAttacksCorrect': '1 of 6',
        'interpretation': 'The geometry pilot misses most no-centering cases. Do not use it to subtract opening throws across the league.',
        'nextStep': evaluation['nextStep'] if evaluation else 'Continue the twelve-opening pilot with predictions hidden. Keep current chat confirmations separate from the frozen development labels and predictions.',
        'oldDraftSamplingCorrection': 'Draft v1 called a game with only reviewed rollers unseen because it was absent from the geometric training set. V2 excludes all games with prior human opening labels from the new-game subset. Corrected before the new review was presented.',
        'leagueMetricsRecalculated': False,
    }
    if evaluation:
        notes['classificationPilot2026_11_13']['completedPilot'] = {'path': str(evaluation_path.relative_to(REPO)), 'overall': evaluation['overall'], 'completedNonRestartSubset': evaluation['completedNonRestartSubset']}
        notes['classificationPilot2026_11_13']['currentReviewArchive'] = str(current_path.relative_to(REPO))
        notes['classificationPilot2026_11_13']['nextAnalysis'] = str(bounds_path.relative_to(REPO))
    notes_path.write_text(json.dumps(notes, indent=2, ensure_ascii=False)+'\n')
    print(f"Prepared 12 opening reviews; 52 earlier decisions preserved; {len(confirmations['reviews'])} new chat confirmations included.")


if __name__ == '__main__':
    main()
