"""Reconcile throw expectations to the captured read-only player-game source."""
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'data/database-metadata/2026-11-04'


def validate():
    snapshot = json.loads((ROOT / 'src/data.json').read_text())
    events = snapshot['queries']['events']['rows']
    reference = json.loads((EVIDENCE / 'player-stats-game-2026.json').read_text())
    by_player = defaultdict(list)
    orders = defaultdict(list)
    sequences = Counter()
    next_aec = defaultdict(float)

    def integer(value):
        return isinstance(value, (int, float)) and math.isfinite(value) and value == math.trunc(value)

    def context(e):
        keys = ('quarter', 'point', 'possession')
        if not e['game'] or not e['team'] or not all(integer(e[k]) and e[k] >= 0 for k in keys):
            return None
        return (e['game'], e['team'], *(e[k] for k in keys))

    for e in events:
        if not e['stall'] and e['thrower']:
            by_player[(e['game'], e['thrower'])].append(e)
        key = context(e)
        if key is not None and integer(e['possessionThrow']) and e['possessionThrow'] >= 1:
            orders[(key, e['possessionThrow'])].append(e)
            if e['eventSequence'] is not None:
                sequences[(key, e['eventSequence'])] += 1

    links = 0
    for e in events:
        key, order = context(e), e['possessionThrow']
        if key is None or not integer(order) or order < 2 or e['thrower'] in (None, 'unknown', ''):
            continue
        current, previous = orders[(key, order)], orders[(key, order-1)]
        if len(current) != 1 or len(previous) != 1:
            continue
        p = previous[0]
        if not p['complete'] or p['stall'] or p['receiver'] != e['thrower']:
            continue
        if p['eventSequence'] is None or e['eventSequence'] is None or p['eventSequence'] >= e['eventSequence']:
            continue
        if sequences[(key, p['eventSequence'])] != 1 or sequences[(key, e['eventSequence'])] != 1:
            continue
        next_aec[(p['game'], p['thrower'])] += e['aec'] or 0
        links += 1

    checked = cpoe_matches = xcp_matches = missing_cp_games = lc_checked = lc_matches = 0
    season_lc = defaultdict(float)
    for r in reference['rows']:
        key = (r['GameID'], r['PlayerID'])
        season_lc[r['PlayerID']] += r['lag_contribution'] or 0
        if r['ThrowAttempts']:
            lc_checked += 1
            lc_matches += abs(next_aec[key]-(r['lag_contribution'] or 0)) < 1e-7
        passes = by_player[key]
        scored = [e['cp'] for e in passes if e['cp'] is not None]
        if not passes or not scored:
            continue
        expected = math.fsum(scored)/len(scored)
        cpoe = sum(e['complete'] or e['drop'] for e in passes)/len(passes)-expected
        checked += 1
        missing_cp_games += len(scored) != len(passes)
        xcp_matches += abs(expected-r['xcp']) < 1e-7
        cpoe_matches += abs(cpoe-r['cpoe']) < 1e-7

    players = snapshot['queries']['shownSpaceThrowers']['rows']
    season_matches = sum(abs(p['lagContribution']-season_lc[p['id']]) < 1e-7 for p in players)
    result = dict(
        source=reference['source'], checkedAt=reference['checkedAt'],
        playerGameRows=len(reference['rows']), sourceGames=len({r['GameID'] for r in reference['rows']}),
        cpoe=dict(compared=checked, matched=cpoe_matches, xcpMatched=xcp_matches,
                  gamesWithMissingCp=missing_cp_games,
                  formula='(complete or dropped attempts)/all non-stall attempts - mean available cp',
                  individualFormula='(1 for complete or dropped, otherwise 0) - cp; missing cp stays null',
                  rawFieldWarning='Stored per-throw cpoe is 1 on recorded drops. Do not average it.'),
        lagContribution=dict(perThrowColumnAvailable=False, seasonPlayers=len(players),
                             seasonTotalsMatchingGameSource=season_matches,
                             candidate='Sum next raw aEC over uniquely verified possession-adjacent passes',
                             verifiedLinks=links, compared=lc_checked, candidateMatches=lc_matches,
                             decision='Rejected: does not reproduce all official LC totals. Keep original season LC; filtered and per-throw LC remain unavailable.'),
        sourceRowsChanged=False,
    )
    assert checked == cpoe_matches == xcp_matches == 5383
    assert links == 67168
    assert lc_matches == 2961 < lc_checked
    assert season_matches == len(players) == 747
    (EVIDENCE / 'throw-metric-validation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    validate()
