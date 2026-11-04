"""Attach original Shown Space season totals and simple throwing-view provenance."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'data/source-api/leaderboard-2026-2026-11-03.json'


def add_throwing_focus(snapshot):
    original = json.loads(SOURCE.read_text())['data']
    assert len({r['PlayerID'] for r in original}) == len(original)
    teams = {r['id']: r['name'] for r in snapshot['queries']['teams']['rows']}
    events = snapshot['queries']['events']['rows']
    by_player = {}
    for event in events:
        if event['thrower'] and event['thrower'] != 'unknown':
            by_player.setdefault(event['thrower'], []).append(event)
    rows = []
    for r in original:
        if r['PlayerID'] not in by_player:
            continue
        local = by_player[r['PlayerID']]
        # The direct season totals include stalls. The directional view does not.
        total = sum(e['throwAec'] for e in local if e['throwAec'] is not None)
        assert abs(total-r['thrower_aec']) < 1e-7, r['PlayerID']
        rows.append(dict(id=r['PlayerID'], name=r['full_name'], team=r['TeamID'],
                         teamName=teams.get(r['TeamID'], r['TeamID']), games=r['Games'],
                         throwerAec=r['thrower_aec'], lagContribution=r['lag_contribution'],
                         sourceAttempts=r['ThrowAttempts'], sourceCompletions=r['Completions'],
                         recordedAttempts=sum(not e['stall'] for e in local),
                         recordedCompletions=sum(e['complete'] and not e['stall'] for e in local)))
    snapshot['queries']['shownSpaceThrowers'] = dict(rows=rows, source=dict(
        label='Shown Space · 2026 season player totals',
        url='https://shownspace.com/api/leaderboard?season=2026',
        executedAt='2026-11-03T23:42:39.322223+00:00', files=[str(SOURCE.relative_to(ROOT))],
        links=[dict(label='Shown Space player leaderboard', href='https://shownspace.com/players'),
               dict(label='Shown Space metric definitions', href='https://shownspace.com/about')],
        sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        filters=['2026 regular season plus playoffs; all lines; season totals, not per game or per 100 possessions.',
                 'Players with named throwing records in the preserved export. No minimum attempts or custom archetype qualification.'],
        metricDefinitions=[
            dict(label='Thrower aEC', definition='The original thrower_aec value from Shown Space. Adjusted Expected Contribution measures modeled scoring contribution credited to throwing. Season sum; includes stalls. This is not a percentage or aEC per attempt.'),
            dict(label='Lag contribution (LC)', definition='The original lag_contribution value from Shown Space. Its metric catalog describes setup value from the following throw’s aEC. It is a season total here; it is not reconstructed or assigned to individual passes.'),
        ],
        caveats=['Season aEC and LC remain fixed when selecting a throw length or direction. They depend on playing time.',
                 'The throw explorer uses the October 12 export. Source summary counts differ for eight players; five also differ in completions. Show the discrepancy for the affected selected player. All 747 imported thrower-aEC totals match the export within 1e-7.',
                 'The export covers 131 of 132 regular-season games plus recorded playoffs. Pittsburgh at Chicago on July 18 is missing.'],
        evidenceFlow=[dict(title='Source values', detail='GET the public leaderboard on November 3, 2026. Preserve the complete response and its SHA-256; copy thrower_aec and lag_contribution without recalculation.'),
                      dict(title='Endpoint', detail='https://shownspace.com/api/leaderboard?season=2026; the preserved response file is the evidence for this snapshot.'),
                      dict(title='Meaning', detail='https://shownspace.com/about, metric catalog inspected November 3, 2026.'),
                      dict(title='Reconciliation', detail='For every imported named thrower, sum the already-reviewed event throwAec, including stalls, and assert agreement with the source season value. Never silently replace source attempt or completion totals.')]),
        methods=[dict(language='text', code='python3 tools/throwing_focus.py')])
    query = snapshot['queries']['events']
    definitions = [
        dict(label='Simple throwing view', componentIds=['ufa-throwing-explorer'], definition='All 2026 recorded non-stall passes by the selected thrower, including playoffs, drops and incomplete throws. No arbitrary sample-size minimum. Completion = completed / attempted throws, with drops incomplete. Zero attempts means unavailable, not zero percent.'),
        dict(label='Throw length', componentIds=['ufa-throwing-explorer'], definition='Straight-line endpoint distance sqrt((rx-tx)^2+(ry-ty)^2). Display groups: 0 ≤ distance <10, 10 ≤ distance <20, 20 ≤ distance <40, and distance ≥40 yards. These are explicit display ranges, not learned player types. A 40+ yard throw is not necessarily a huck.'),
        dict(label='Throw direction', componentIds=['ufa-throwing-explorer'], definition='Use the supplied throwAngle, normalized modulo 360, in twelve lower-inclusive 30-degree bins from prod.get_player_throw_directions. 0° is forward, 90° points toward decreasing source X (drawn to the left), 180° backward, 270° right. Draw each slice over its true angular range, centered at the midpoint. This new display uses the source bins with a field-oriented orientation, not the mirrored appearance of the old Shown Space reproduction. Zero-distance passes have no spatial direction and are excluded from the directional chart. Missing angles remain unavailable.'),
        dict(label='aEC for selected throws', componentIds=['ufa-throwing-explorer'], definition='Sum the existing reviewed throwAec for exactly the displayed non-stall passes. It uses the supplied aec with drops credited zero to the thrower, following the source convention. Season aEC above additionally includes stalls. Never compute or imply a filtered LC from these records.'),
    ]
    labels={d['label'] for d in definitions}
    query['source']['metricDefinitions']=[d for d in query['source'].get('metricDefinitions',[]) if d.get('label') not in labels]+definitions


if __name__ == '__main__':
    path=ROOT/'src/data.json'
    snapshot=json.loads(path.read_text())
    add_throwing_focus(snapshot)
    snapshot['buildStatus']='updating'
    snapshot['generatedAt']=datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(snapshot,separators=(',',':'),allow_nan=False))
    print(f"Added {len(snapshot['queries']['shownSpaceThrowers']['rows'])} original Shown Space player summaries.")
