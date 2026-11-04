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
        caveats=['Season aEC and LC remain fixed when changing distance bands or the huck filter. They depend on playing time.',
                 'The throw explorer uses the October 12 export. Source summary counts differ for eight players; five also differ in completions. Show the discrepancy for the affected selected player. All 747 imported thrower-aEC totals match the export within 1e-7.',
                 'The export covers 131 of 132 regular-season games plus recorded playoffs. Pittsburgh at Chicago on July 18 is missing.'],
        evidenceFlow=[dict(title='Source values', detail='GET the public leaderboard on November 3, 2026. Preserve the complete response and its SHA-256; copy thrower_aec and lag_contribution without recalculation.'),
                      dict(title='Endpoint', detail='https://shownspace.com/api/leaderboard?season=2026; the preserved response file is the evidence for this snapshot.'),
                      dict(title='Meaning', detail='https://shownspace.com/about, metric catalog inspected November 3, 2026.'),
                      dict(title='Reconciliation', detail='For every imported named thrower, sum the already-reviewed event throwAec, including stalls, and assert agreement with the source season value. Never silently replace source attempt or completion totals.')]),
        methods=[dict(language='text', code='python3 tools/throwing_focus.py')])
    query = snapshot['queries']['events']
    query['source']['filters']=[
        '2026 season. Throwing profiles and Distance & angle use the full available season including playoffs and all lines. Field views and Connections use their own season-phase, team and line controls; regular season is their default.'
        if f=='2026 season; regular season is the default. Playoffs can be selected separately.' or f.startswith('2026 season. Throwing profiles') else f
        for f in query['source'].get('filters',[])
    ]
    definitions = [
        dict(label='Distance and angle population', componentIds=['ufa-distance-angle-chart','ufa-distance-angle-finder'], definition='The independently selected players and player finder use all available 2026 non-stall attempts, including playoffs, incompletions, drops and unrecorded targets. The selected distance range applies to both sections. Source rows retain all non-stall player attempts for the frequency denominator; displayed rows hold the derived distributions or matching player summaries.'),
        dict(label='Similar arrows', componentIds=['ufa-distance-angle-finder'], definition='For each named player, calculate the circular mean angle from positive-distance attempts with recorded angles in the shared distance range. Match Player 1 using the shortest angular separation abs(((angle-reference+180) mod 360)-180), at or below the selected tolerance. Exclude Player 1 and undefined mean directions. Default tolerance is 15 degrees; default minimum is 20 throws in the distance range. Both are visible, adjustable browsing filters, not fitted archetypes or reliability thresholds. Team filtering restricts candidates, not the reference. Sort by angular separation, then count descending, then name and ID. Similar mean angles do not establish similar full distributions, playing ability, or repeatability.'),
        dict(label='Throws by direction finder', componentIds=['ufa-distance-angle-finder'], definition='Intersect the shared distance range with one source 30-degree angle bin and the candidate team filter. Distance lower edge is included and upper excluded; angle bins normalize source throwAngle into [0,360) and include lower edges. Any direction keeps all located attempts, including zero-distance or missing-angle throws. A selected angle bin requires positive distance and a recorded angle. Minimum matching throws applies after both filters. Matching throws counts all attempts, including incomplete throws and drops. % of all throws = matching attempts / every non-stall attempt by that player, including missing coordinates in the denominator. Completion % = matching completions / matching attempts. Highest-frequency ordering uses this share; highest-completion ordering uses this rate, without difficulty adjustment.'),
        dict(label='Finder evidence and comparison', componentIds=['ufa-distance-angle-finder'], definition='Primary events evidence includes all non-stall attempts for the candidate rows, preserving their denominators, plus Player 1 when its mean defines the search. shownSpaceThrowers evidence supplies the unchanged player directory and team identity. Display rows contain the sorted eligible players before the table text search and pagination. Arrow and distance averages describe the shared distance range; they are shown only in Similar arrows mode. The direction-search table shows matching counts, frequency and completion instead. Compare loads a candidate into Player 2 while retaining Player 1 and the shared distance range. The comparison diagrams retain all directions; the finder direction is outlined without changing the diagrams’ counts or averages. Filters and selections are local to this view and reset on reload.'),
        dict(label='Distance range', componentIds=['ufa-distance-angle-chart'], definition='Straight-line Euclidean endpoint distance sqrt((rx-tx)^2+(ry-ty)^2), not forward gain. Include distances at or above the lower input and strictly below the upper input. Default 15–20 means 15 <= distance <20. Use 15–16 for a one-yard band, or 14.5–15.5 for throws rounding to 15 yards. All distances sets a range that includes the largest recorded distance. Invalid inputs show an error, not stale results. Missing coordinates cannot be assigned to a range and are disclosed.'),
        dict(label='Distance range frequency', componentIds=['ufa-distance-angle-chart'], definition='Number of matching attempts divided by every non-stall attempt by the same player, in the same season scope. Missing-location attempts stay in the denominator. This is different from a direction slice’s share, which uses only the selected-range throws with a usable direction.'),
        dict(label='Average throw distance', componentIds=['ufa-distance-angle-chart'], definition='Arithmetic mean of the unrounded Euclidean distances of the selected throws. Zero-distance throws are included. Empty selection is unavailable, not zero. This is the mean attempted distance, including incomplete throws, rather than yards gained or distance on completions only.'),
        dict(label='Average throw angle', componentIds=['ufa-distance-angle-chart'], definition='Circular mean atan2(mean(sin(theta)), mean(cos(theta))) in degrees using source throwAngle, with equal weight per positive-distance throw. 0 degrees is forward, positive angles rotate left, negative right, and 180 is backward. Source angles agree with atan2(tx-rx, ry-ty) for all 77,822 positive-distance non-stall throws in the snapshot. Zero distance and missing angles are excluded from this mean and the direction distribution, while remaining in the distance summary when coordinates exist. An empty angle sample or mean-resultant magnitude below 1e-12 is unavailable; this threshold only handles numerical cancellation. The mean is not the most frequent angle and can hide opposing directions. Method reference: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.circmean.html .'),
        dict(label='Most common direction', componentIds=['ufa-distance-angle-chart'], definition='Use the source’s twelve 30-degree direction bins: normalize throwAngle into [0,360), then floor(angle/30). Lower edge included, upper excluded. 0–180 is shown on the left of forward, 180–360 on the right, with explicit left/right labels. Show every bin tied for the maximum positive count. No observations means no leading direction. These are display bins, not learned archetypes or an exact most frequent continuous angle.'),
        dict(label='Direction comparison diagram', componentIds=['ufa-distance-angle-chart'], definition='All positive-distance throws with a recorded angle in the selected range are counted once. Each wedge’s radial bar length is proportional to its share of those throws. Both players share the same outer-ring scale, rounded up to the next five percentage points; the outer-ring value is printed below. Purple arrows use a fixed length to indicate the circular mean direction, not mean distance. Each mean and mode remains based on the entire selected range when drilling into a direction’s records.'),
        dict(label='Throwing comparison', componentIds=['ufa-throwing-explorer'], definition='Two independently selected players, full available 2026 season including playoffs and all lines. Each field shows every matching non-stall attempt, including drops, incompletions and unnamed targets. Source rows preserve all non-stall attempts for the selected players; displayed rows are the matching throws in the selected distance band or huck filter. Shared source rows are deduplicated when the same player is selected twice. No sample-size threshold or custom quality score.'),
        dict(label='Distance bands', componentIds=['ufa-throwing-explorer'], definition='Straight-line Euclidean endpoint distance, in any direction. The 0–10, 10–20, 20–30 and 30–40 yard bands include the lower edge and exclude the upper edge. Exactly 10 yards belongs to 10–20; exactly 20 to 20–30; exactly 30 to 30–40; exactly 40 to 40+. Zero-distance records appear as dots in 0–10. These five distance bands partition every non-stall attempt with complete endpoint coordinates. Hucks are a separate overlapping filter, not an extra distance band.'),
        dict(label='40+ yard throws', componentIds=['ufa-throwing-explorer'], definition='Euclidean endpoint distance sqrt((rx-tx)^2+(ry-ty)^2) >=40 yards, in any direction. Do not substitute the rounded source throwDistance field. Hucks use the separate strict rule: distance >40 AND ry-ty >30. Stalls are excluded from every distance band and the huck filter.'),
        dict(label='Filtered completion %', componentIds=['ufa-throwing-explorer'], definition='Completed matching throws divided by all matching attempts, including drops as incomplete. Zero attempts means unavailable, not zero percent. Alex Atkins: 49/58 for 40+ yards; 45/53 for hucks. Jacques Nissen: 16/22 for 40+ yards; 15/20 for hucks. Descriptive rates, not adjusted for throw difficulty.'),
        dict(label='Share of all throws', componentIds=['ufa-throwing-explorer'], definition='Matching attempts divided by all non-stall attempts by that player in the same snapshot, including playoffs. The denominators are 551 for Alex Atkins and 446 for Jacques Nissen. Missing-coordinate throws stay in the denominator and are disclosed; they cannot be assigned to a distance band or identified as hucks.'),
        dict(label='Throw field', componentIds=['ufa-throwing-explorer'], definition='Both fields use the same 53.3 by 120 yard coordinate scale and attack toward increasing Y, shown to the right (source positive X points down). End zones are Y=0–20 and 100–120. A dot marks the throwing location and an arrow points to the recorded target. Complete throws are solid teal; incomplete throws and drops are dashed orange. Connectors are straight endpoint vectors, not tracked flight paths, running routes or receiver locations before the pass. Hover or the named highlight action can emphasize a single throw without changing the counts or plotted population.'),
        dict(label='Season completion %', componentIds=['ufa-throwing-season'], definition='Completed non-stall passes / all non-stall attempts in the 2026 event export, including playoffs and drops. Drops are incomplete; zero attempts means unavailable. This retains the original explorer completion calculation (for Alex Atkins, 534 / 551 = 96.9% to one decimal). It is not the differently adjusted completion_percentage field in the Shown Space leaderboard. This season rate never changes when changing distance bands or the huck filter.'),
        dict(label='Simple throwing view', componentIds=['ufa-throwing-explorer'], definition='All 2026 recorded non-stall passes by the selected thrower, including playoffs, drops and incomplete throws. No arbitrary sample-size minimum. Completion = completed / attempted throws, with drops incomplete. Zero attempts means unavailable, not zero percent.'),
        dict(label='Throw length', componentIds=['ufa-throwing-explorer'], definition='Straight-line endpoint distance sqrt((rx-tx)^2+(ry-ty)^2). Display groups: 0 ≤ distance <10, 10 ≤ distance <20, 20 ≤ distance <40, and distance ≥40 yards. These are explicit display ranges, not learned player types. A 40+ yard throw is not necessarily a huck.'),
        dict(label='Throw direction', componentIds=['ufa-throwing-explorer'], definition='Use the supplied throwAngle, normalized modulo 360, in twelve lower-inclusive 30-degree bins from prod.get_player_throw_directions. 0° is forward, 90° points toward decreasing source X (drawn to the left), 180° backward, 270° right. Draw each slice over its true angular range, centered at the midpoint. This new display uses the source bins with a field-oriented orientation, not the mirrored appearance of the old Shown Space reproduction. Zero-distance passes have no spatial direction and are excluded from the directional chart. Missing angles remain unavailable.'),
        dict(label='aEC for selected throws', componentIds=['ufa-throwing-explorer'], definition='Sum the existing reviewed throwAec for exactly the displayed non-stall passes. It uses the supplied aec with drops credited zero to the thrower, following the source convention. Season aEC above additionally includes stalls. Never compute or imply a filtered LC from these records.'),
    ]
    # Keep the old grouped-chart methods as historical evidence, not as the active field's definitions.
    historical={'Simple throwing view','Throw length','Throw direction','aEC for selected throws'}
    for definition in definitions:
        if definition['label'] in historical:
            definition['componentIds']=['ufa-throwing-patterns-archived']
    labels={d['label'] for d in definitions}|{'Long-throw comparison','Long-throw completion %','Long-throw field'}
    query['source']['metricDefinitions']=[d for d in query['source'].get('metricDefinitions',[]) if d.get('label') not in labels]+definitions


if __name__ == '__main__':
    path=ROOT/'src/data.json'
    snapshot=json.loads(path.read_text())
    add_throwing_focus(snapshot)
    snapshot['buildStatus']='updating'
    snapshot['generatedAt']=datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(snapshot,separators=(',',':'),allow_nan=False))
    print(f"Added {len(snapshot['queries']['shownSpaceThrowers']['rows'])} original Shown Space player summaries.")
