"""Attach the reviewed contribution study to the existing dashboard snapshot."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT/'analysis/offensive_contributions.json'


def add_offensive_contributions(snapshot):
    if not RESULT.exists():
        return
    result = json.loads(RESULT.read_text())
    checks_path = ROOT/'analysis/offensive_contribution_checks.json'
    checks = json.loads(checks_path.read_text())
    if not checks.get('passed') or checks.get('resultSha256') != hashlib.sha256(RESULT.read_bytes()).hexdigest():
        raise ValueError('Run the independent contribution checks for this exact analysis before importing it.')
    current = json.loads((ROOT/'data/database-exports/current.json').read_text())
    if current != {'manifest':'data/database-exports/2026-10-12/manifest.json','season':2026}:
        raise ValueError('Re-run the contribution study for the selected export before importing it.')
    manifest = json.loads((ROOT/current['manifest']).read_text())
    for table, digest in result['sourceHashes'].items():
        if manifest['tables'][table]['sha256'] != digest:
            raise ValueError(f'Contribution source changed: {table}')
    team_ids = {r['id'] for r in snapshot['queries']['teams']['rows']}
    if any(r['teamId'] not in team_ids for r in result['profiles']):
        raise ValueError('Contribution profiles contain an unknown team.')
    source = dict(
        label='Shown Space exports · offensive contributions', url='https://shownspace.com',
        executedAt=result['analyzedAt'],
        tables=['prod.throws','prod.games','prod.players','prod.teams'],
        files=[f'data/database-exports/2026-10-12/{t}.csv' for t in result['sourceHashes']]
              + ['analysis/offensive_contributions.json', 'analysis/offensive_contribution_checks.json'],
        filters=[
            '2026 regular season, all lines, preserved October 12, 2026 export. Not a live refresh.',
            '249 throwers: 100+ physical passes, 6+ observed games, one team; no catching minimum.',
            'Scoring delivery overlaps the directional categories. Never add the three role totals.',
            'Source captured timestamp refers to this local analysis, not the age of the database export.',
        ],
        metricDefinitions=[dict(label=k,definition=v) for k,v in result['definitions'].items()],
        caveats=result['caveats']+[
            'Minimum-attempt and team/search controls filter the displayed players. The pooled league benchmark remains the fixed qualifying cohort.',
            f"{result['coverage']['scoringCompletionsNotGoals']} completed goal-line targets in the cohort are not recorded as goals; actual source assists stay separate.",
        ],
        evidenceFlow=[
            dict(title='Source',detail='analysis/thrower_article_comparison.py loads the preserved CSVs, verifies file hashes, enforces unique throws and a many-to-one games join, and keeps source drop and goal indicators.'),
            dict(title='Contributions',detail='analysis/offensive_contributions.py assigns outcome-independent pass masks, aggregates all 249 players, pools fixed cohort baselines, and computes 2,000 within-player whole-game bootstrap intervals with random seed 20261030.'),
            dict(title='Across games',detail='Chronological first half of each player’s observed games versus the rest. Frequency requires 50 total passes in each half; performance additionally requires 20 role attempts in each half. These are same-season associations, not a forecast or fitted archetype classifier.'),
            dict(title='Independent checks',detail='analysis/offensive_contribution_checks.py uses csv.DictReader and independent scalar geometry/outcome arithmetic to reconcile every player-role row and cohort membership with the preserved exports. Website model tests check category selection, minimum samples, missing outcomes, and fixed baseline scope.'),
        ])
    methods=[dict(language='text',code='python3 analysis/offensive_contributions.py\npython3 analysis/offensive_contribution_checks.py\npython3 tools/offensive_contributions.py\nnode --test tools/offensive-contributions.test.mjs')]
    study=[{k:v for k,v in row.items() if k!='passingPairs'} for row in result['repeatability']]
    for key,rows in [('offensiveContributions',result['profiles']),('contributionBaselines',result['baselines']),('contributionStudy',study)]:
        snapshot['queries'][key]=dict(rows=deepcopy(rows),source=deepcopy(source),methods=deepcopy(methods))
    snapshot['queries']['contributionBaselines']['source']['label']='Shown Space exports · fixed contribution benchmarks'
    snapshot['queries']['contributionStudy']['source']['label']='Shown Space exports · within-season contribution checks'


if __name__=='__main__':
    path=ROOT/'src/data.json'
    snapshot=json.loads(path.read_text())
    add_offensive_contributions(snapshot)
    snapshot['buildStatus']='updating'
    snapshot['generatedAt']=datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(snapshot,separators=(',',':'),allow_nan=False))
    print(f"Attached {len(snapshot['queries']['offensiveContributions']['rows'])} reviewed player-contribution rows.")
