"""Attach the full reviewed all-pass cohort, not only the article examples."""
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / 'analysis/thrower_article_comparison.json'
REFERENCE_FIELDS = [
    'forwardShare', 'lateralShare', 'backwardShare', 'shortShare', 'huckShare',
    'meanGain', 'nonHuckMeanGain', 'meanFlight', 'throwingY', 'sidelineShare',
    'completionRate', 'xcp', 'sourceCpoe', 'throwerAec', 'assists', 'hockeyAssists',
]


def add_thrower_profiles(snapshot):
    if not RESULT.exists():
        return
    result = json.loads(RESULT.read_text())
    current = json.loads((ROOT / 'data/database-exports/current.json').read_text())
    if current.get('manifest') != 'data/database-exports/2026-10-12/manifest.json' or current.get('season') != 2026:
        raise ValueError('Re-run the all-pass analysis for the new source snapshot before importing profiles.')
    manifest = json.loads((ROOT / current['manifest']).read_text())
    for table, digest in result['sourceHashes'].items():
        if manifest['tables'][table]['sha256'] != digest:
            raise ValueError(f'All-pass analysis source hash changed: {table}')
    teams = {r['name']: r['id'] for r in snapshot['queries']['teams']['rows']}
    rows = []
    for profile in result['allProfiles']:
        row = {k: v for k, v in profile.items() if k not in ('halves', 'percentiles')}
        row.update(team=teams[profile['team']], teamName=profile['team'])
        row.update({f'{k}Percentile': v for k, v in profile['percentiles'].items()})
        rows.append(row)
    if len(rows) != result['cohort']['players'] or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('All-pass cohort is incomplete or has duplicate player identities.')
    reference = [dict(feature=k, median=median(r[k] for r in rows if r[k] is not None),
                      players=sum(r[k] is not None for r in rows), season=2026)
                 for k in REFERENCE_FIELDS]
    source = dict(
        label='Shown Space exports · league-wide throwing profiles', url='https://shownspace.com',
        executedAt=result['analyzedAt'],
        tables=['prod.throws', 'prod.games', 'prod.players', 'prod.teams'],
        files=[f'data/database-exports/2026-10-12/{t}.csv' for t in result['sourceHashes']]
              + ['analysis/thrower_article_comparison.json'],
        filters=[
            '2026 regular season, all lines. Preserved October 12, 2026 CSV export; not a live refresh.',
            '100+ non-stall passes and 6+ observed games, one team. No minimum catches. All qualifying players are included.',
            'Source capture time refers to the derived analysis, not a new database query.',
        ],
        caveats=[c.replace('; all six article examples have complete modeled-pass coverage', '') for c in result['caveats'] if not c.startswith('The article was published')] + [
            'League median gives each qualifying player equal weight and stays fixed when searching or filtering teams. It is not a pooled completion rate.',
            'Volume, contribution totals and descriptive style differences are not a ranking of intrinsic player quality.',
            'The broader throwing cohort differs from Style matches, which also requires 100 catches and six catching games.',
        ],
        metricDefinitions=[
            dict(label=k, definition=v.replace(' All six examples have complete cp coverage.', '')) for k, v in result['definitions'].items()
        ] + [
            dict(label='Passing choices and distances', definition='Short passes have flight ≤10 yards. Forward gain is ReceiverY − ThrowerY; flight is Euclidean endpoint distance. All passing shares and means exclude stalls but retain incomplete passes. Non-huck mean gain excludes only passes meeting both strict huck thresholds.'),
            dict(label='Throwing locations', definition='Mean ThrowerY, from 0 at the back of the own end zone toward 120 at the back of the attacking end zone. Near-sideline share uses |ThrowerX| ≥15 yards.'),
            dict(label='League comparison', definition=f'Median of each metric across all {len(rows)} qualifying 2026 throwers, each weighted equally. The baseline does not change with team, search, sorting or selected player.'),
            dict(label='Observed profile descriptions', definition='Choose the two strongest absolute departures from the 50th style percentile among short-pass share, lateral share, mean forward gain, average throwing Y and near-sideline share. State actual values against the fixed league median. These are overlapping measured tendencies, not learned archetype assignments; outcomes are not inputs.'),
        ],
        evidenceFlow=[
            dict(title='Preserved exports', detail='DBeaver exports from October 12, 2026. Analysis records SHA-256 hashes for throws, games, players and teams; importer checks them against the preserved manifest.'),
            dict(title='All-pass analysis', detail='analysis/thrower_article_comparison.py aggregates every qualifying thrower. The website imports allProfiles rather than the six-row examples subset. Regular-season coverage is 131 of 132 games; Pittsburgh at Chicago on July 18 has no throws.'),
            dict(title='Reconciliation', detail='Assists, supplied xCP, drop-credit CPOE and total thrower aEC matched 991 cached player-game records across 26 games. Derived verified pre-assists differ from official HockeyAssists in 21 records and are labeled separately.'),
            dict(title='Full-cohort integration checks', detail='tools/thrower-profiles.test.mjs independently reconciles all 249 profiles to the existing reviewed event snapshot: passes, games, team, completions, drops, hucks, gain, flight, non-huck gain, short and directional shares, throwing Y, xCP, CPOE and total thrower aEC. It also verifies fixed medians, league-wide search and outcome-independent descriptions.'),
            dict(title='Website comparison', detail='tools/thrower_profiles.py preserves profile values and builds equal-player medians. Search and team filter select directory rows; the baseline remains league-wide. Style descriptions do not use completion or contribution outcomes.'),
        ],
    )
    methods = [dict(language='python', code='python3 analysis/thrower_article_comparison.py\npython3 tools/thrower_profiles.py'),
               dict(language='text', code='node --test tools/thrower-profiles.test.mjs')]
    for key, data in [('throwerProfiles', rows), ('throwerReference', reference)]:
        snapshot['queries'][key] = dict(rows=data, source=deepcopy(source), methods=deepcopy(methods))
    snapshot['queries']['throwerReference']['source']['label'] = 'Shown Space exports · fixed 2026 thrower medians'


if __name__ == '__main__':
    path = ROOT / 'src/data.json'
    snapshot = json.loads(path.read_text())
    add_thrower_profiles(snapshot)
    snapshot['buildStatus'] = 'updating'
    snapshot['generatedAt'] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(snapshot, separators=(',', ':'), allow_nan=False))
    print(f"Attached {len(snapshot['queries']['throwerProfiles']['rows'])} all-pass profiles and fixed league medians.")
