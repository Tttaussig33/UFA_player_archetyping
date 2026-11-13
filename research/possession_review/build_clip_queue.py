"""Prepare provisional, assisted-review cases without changing human labels."""
from pathlib import Path
import hashlib
import json
import math
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEST = HERE / 'assisted_clip_queue.json'
SELECTED = ['R002', 'R003', 'R005', 'R006', 'R034', 'R035', 'R039', 'R040', 'R073', 'R074', 'R077', 'R082']


def seconds(value):
    total = 0
    for part in value.split(':'):
        total = total * 60 + int(part)
    return total


def main():
    path = HERE / 'film_library.json'
    library = json.loads(path.read_text())
    by_id = {c['id']: c for c in library['cases']}
    if DEST.exists() and any(by_id[cid].get('savedReview') for cid in SELECTED):
        # Never recreate suggestions or original watch windows after seeing labels.
        queue = json.loads(DEST.read_text())
        assert [c['caseId'] for c in queue['clips']] == SELECTED
        followup = json.loads((HERE / 'review_followup_2026-11-12.json').read_text())
        for clip in queue['clips']:
            saved = by_id[clip['caseId']].get('savedReview', {})
            clip['reviewStatus'] = 'archived' if saved.get('decision') else 'awaiting_review'
            clip['reviewChecks'] = [c for c in followup['checks'] if c['caseId'] == clip['caseId']]
            replay = next((c['replayWindow'] for c in clip['reviewChecks'] if c.get('replayWindow')), None)
            if replay:
                clip['replayWindow'] = replay
        queue['reviewedCount'] = sum(c['reviewStatus'] == 'archived' for c in queue['clips'])
        queue['status'] = 'Reviews archived; follow-up checks remain'
        queue['provenanceNote'] = 'Original suggestions, reasons, source hash and watch windows are frozen. Replay windows are separate corrections; raw reviews retain the window presented during annotation.'
        write_queue(queue)
        print(f'Preserved all {len(queue["clips"])} original suggestions; {queue["reviewedCount"]} reviews archived. No prediction regenerated from labels.')
        return
    timing_path = HERE / 'clip_timing_checks.json'
    timing_checks = json.loads(timing_path.read_text()) if timing_path.exists() else {'cases': {}}
    clips = []
    for case_id in SELECTED:
        c = by_id[case_id]
        assert c['libraryGroup'] == 'Definition development'
        assert not c.get('savedReview') and not c.get('filmUnavailable')
        t = c['throws'][0]
        x, y, rx, ry = t['xy']
        distance = math.hypot(rx-x, ry-y)
        if c['ownPossession'] > 1:
            prediction, reason = 'attack1', 'This is a later possession after a turnover. A short transfer still counts as attacking under our definition.'
        elif x == 0 and y == 40:
            prediction, reason = 'attack1', 'The record starts at brick coordinates. Check the film: coordinates alone do not confirm a brick restart.'
        elif abs(x) >= 23 and y >= 35:
            prediction, reason = 'attack1', 'The opening is recorded near the sideline and farther upfield. A sideline restart is plausible; confirm it from the pull.'
        elif t['huck']:
            prediction, reason = 'attack1', 'The first recorded throw goes deep, which suggests the pull receiver attacks directly.'
        else:
            prediction, reason = 'setup1', f'The opening pass is a {distance:.1f}-yard transfer near the receiving end. It may hand the disc to the initiator, but pressure could make it an attacking pass.'
        f = c['film']
        checked_timing = timing_checks['cases'].get(case_id)
        clips.append({
            'caseId':case_id, 'possessionId':c['possessionId'], 'gameId':c['gameSource']['game'],
            'gameTitle':c['gameSource']['label'], 'videoUrl':c['filmSource']['url'],
            'videoPath':c['filmSource']['url'].split('/videos/')[-1],
            'start':seconds(f['start']), 'end':seconds(f['end']), 'timingStatus':'estimated',
            'timingSource':c.get('timestampEvidence'), 'team':c['team'],
            'possessionNumber':c['ownPossession'], 'score':c['scoreLabel'], 'pointClock':c['pointClock'],
            'firstPass':f"{t['from']} → {t['to']}", 'suggestion':prediction, 'reason':reason,
            'suggestionMethod':'rule-guided-event-estimate-v1', 'suggestionStatus':'unconfirmed',
            'contextDefault':'turnover' if c['ownPossession'] > 1 else 'unclear',
            'firstThrowXY':t['xy'], 'selectionGroup':'Assisted development review',
            'cohortEligibility':'Not assigned by this label; lineup, timeout, field-position and clock exclusions remain separate.'
        })
        if checked_timing:
            clips[-1].update(start=checked_timing['start'], end=checked_timing['end'],
                timingStatus=checked_timing['status'], timingCheck=checked_timing)
    queue = {
        'id':'ufa-assisted-clips-20261112-v1', 'createdOn':'2026-11-12', 'clips':clips,
        'sourceSha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'sourcePath':'research/possession_review/film_library.json',
        'method':'Provisional labels from recorded context and the user-defined setup rule. No trained computer-vision classifier or calibrated confidence scores.',
        'reviewDesign':'Predictions are shown before annotation. These assisted labels are development data, not an independent accuracy test. Reserved games are not included.',
        'timingNote':'Two windows were shortened after agent spot-checks on UFA.tv. The other ten retain estimated boundaries. Timing checks are separate from human classifications; wrong windows can be flagged and boundaries corrected.'
    }
    write_queue(queue)
    print(f'Prepared {len(clips)} unreviewed development cases across {len({c["gameId"] for c in clips})} games; human labels unchanged.')


def write_queue(queue):
    DEST.write_text(json.dumps(queue,ensure_ascii=False,indent=2)+'\n')
    canvas = ROOT / 'research/previews/UFA-possession-review.canvas.tsx'
    source = canvas.read_text()
    declaration = 'const ASSISTED = '+json.dumps(queue,ensure_ascii=False,separators=(',',':'))+';\n'
    if re.search(r'^const ASSISTED = .*;\n', source, re.M):
        source = re.sub(r'^const ASSISTED = .*;\n',lambda _: declaration,source,flags=re.M)
    else:
        source = source.replace('export default function PossessionReview()',declaration+'\nexport default function PossessionReview()',1)
    canvas.write_text(source)


if __name__ == '__main__':
    main()
