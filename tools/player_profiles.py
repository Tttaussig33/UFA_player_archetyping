"""Attach audited player-profile analysis without changing the event snapshot."""
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'analysis/archetype_candidate_validation.json'


def add_player_profiles(snapshot):
    if not RESULT.exists(): return
    result=json.loads(RESULT.read_text())
    current=json.loads((ROOT/'data/database-exports/current.json').read_text())
    # This analysis is explicitly frozen to these preserved exports, not live data.
    manifest=json.loads((ROOT/'data/database-exports/2026-10-12/manifest.json').read_text())
    for table,digest in result['sourceHashes'].items():
        if manifest['tables'][table]['sha256']!=digest:
            raise ValueError('Player-profile inputs changed. Re-run analysis/archetype_candidate_validation.py before attaching results.')
    if '2026-10-12' not in json.dumps(current) or str(current.get('season',2026))!='2026':
        raise ValueError('Player styles requires the reviewed 2026 season / October 12 export. Re-run its analysis for a new snapshot.')
    rows=[]
    for c,o in zip(result['clusterStudies'],result['outcomeStudies']):
        b=o['comparisons']; interval=b['gameBootstrap']['ci95']
        centers=sorted(c['groupCentroids'],key=lambda r:r['releaseY'])
        rows.append(dict(season=c['testSeason'],referenceSeason=c['referenceSeason'],groups=c['selectedK'],
            trainingPlayers=c['referencePlayers'],halfPlayers=c['evaluatedHalfSeasonPlayers'],
            sameGroupCount=sum(p['earlyGroup']==p['laterGroup'] for p in c['temporalMembership']),
            sameGroupRate=c['heldoutSameGroupRate'],temporalARI=c['heldoutARI'],temporalGate=.6,
            backfieldMeanThrowingY=centers[0]['releaseY'],upfieldMeanThrowingY=centers[-1]['releaseY'],
            silhouette=c['selectedSilhouette'],gaussianTail=c['gaussianReferenceTailFraction'],
            refitMedianARI=c['bootstrapARI']['median'],passedPilotGates=c['passedPilotGates'],
            relativeBrierImprovementPct=b['relativeBrierImprovementPct'],
            relativeBrierLowerPct=interval[0]/b['baselineBrier']*100,
            relativeBrierUpperPct=interval[1]/b['baselineBrier']*100,
            evaluatedThrows=o['evaluatedThrows'],evaluatedPlayers=o['evaluatedPlayers']))
    ref=result['clusterStudies'][-1]
    reference=[dict(feature=k,**meta,mean=ref['scalerMean'][k],sd=ref['scalerSD'][k],
        weight=ref['weights'][k],season=ref['referenceSeason'],players=ref['referencePlayers'])
        for k,meta in result['features'].items()]
    analyzed=result.get('analyzedAt') or datetime.fromtimestamp(RESULT.stat().st_mtime,timezone.utc).isoformat()
    source=dict(label='Shown Space exports · local player-style research',url='https://shownspace.com',
        executedAt=analyzed,
        files=[f'data/database-exports/2026-10-12/{t}.csv' for t in result['sourceHashes']]+['analysis/archetype_candidate_validation.json'],
        tables=['prod.throws','prod.games','prod.players','prod.teams'],
        filters=['Preserved source export: October 12, 2026. Source captured timestamp below refers to the local derived analysis, not a new database query.',
            'Profiles: 2026 regular season, all lines, 100+ located non-stall throws AND 100+ completed catches, 6+ games in each role, one team.',
            'Validation: 2024→2025 and 2025→2026. No test-year outcomes used to fit prediction models.'],
        caveats=result['caveats']+['This is the October 12 export, not a live database refresh.',
            'Missing regular-season coverage includes one Pittsburgh game; sample floors exclude low-involvement roles.',
            'Selected-player comparisons use 2026 observed profiles. The weighting scale comes from 227 eligible 2025 players.',
            'Retrospective completion above expectation is our coarse geometry model, not Shown Space CPOE or aEC. It is not used to rank style matches.'],
        metricDefinitions=[
            dict(label='Style distance',definition='Square root of the sum of weight × ((player trait − candidate trait) / 2025 standard deviation)². Four groups each receive 25% weight: passing choices, throwing locations, catching locations and disc involvement. Lower means more similar; zero means identical measured traits. No performance, team, name or absolute volume is a matching feature.'),
            dict(label='Huck',definition='Forward gain ReceiverY − ThrowerY > 30 yards AND Euclidean flight distance > 40 yards. Boundaries are strict. Offense always attacks toward Y=120.'),
            dict(label='Profile traits',definition='Short throws travel ≤10 yd. Forward throws gain more yards than absolute lateral displacement; backward throws lose more than absolute lateral displacement. Near-sideline means |X|≥15 yd. Catch traits use completed catches. Involvement is throws/(throws+completed catches), not on-field possession share.'),
            dict(label='Completion versus geometry expectation',definition='2026 actual completion minus expected completion from a penalized additive logistic model trained on 2021–2025 named, located, non-stall regular throws. Inputs: distance and forward-gain bands, throwing-Y band, near-sideline and end-zone target. Shown in percentage points. 95% intervals resample each player’s whole games 2,000 times, conditional on the fitted model; they do not establish intrinsic skill.'),
            dict(label='Archetype pilot',definition='K-means with 20 starts; K=2–6; every group ≥max(12, 5% of profiles). Choose smallest K within .02 of best silhouette. Compare 100 correlated Gaussian references; refit 60 whole-team bootstraps. Screening gates: reference tail<.05, median refit ARI≥.8, later half-season ARI≥.6. Gates are pilot choices, not universal standards. Neither year passes all three.'),
            dict(label='Performance repeatability',definition='Compare next-year Brier error for geometry + prior-year team offsets + prior-year player offsets against geometry + team alone. Offsets use ridge precision 5. Only players with 100 prior-year throws are evaluated. Positive relative improvement is better. 95% intervals resample games 5,000 times; neither year excludes zero. Player-bootstrap sensitivity is retained in the research result.')],
        evidenceFlow=[dict(title='Preserved source',detail='DBeaver CSV exports from October 12, 2026; SHA-256 hashes verified against manifest.json.'),
            dict(title='Analysis',detail='analysis/archetype_candidate_validation.py creates annual profiles, historical cluster tests and passing-outcome checks. Source endpoints are interpreted retrospectively.'),
            dict(title='Independent checks',detail='analysis/archetype_candidate_checks.py reconciles every one of the 230 displayed profiles directly from CSV and checks clustering, temporal ordering and outcome arithmetic.'),
            dict(title='Website',detail='tools/player_profiles.py attaches reviewed profile, scaling and study rows. The authored tab computes weighted style distances; selected rows and weights remain available in source inspection.')])
    methods=[dict(language='python',code='python3 analysis/archetype_candidate_validation.py\npython3 analysis/archetype_candidate_checks.py\npython3 tools/player_profiles.py')]
    for key,data in [('playerProfiles',result['profiles']),('profileReference',reference),('profileStudy',rows)]:
        snapshot['queries'][key]=dict(rows=data,source=deepcopy(source),methods=deepcopy(methods))
        snapshot['queries'][key]['source']['label']={'playerProfiles':'Shown Space exports · 2026 player profiles',
            'profileReference':'Shown Space exports · 2025 style reference scale',
            'profileStudy':'Shown Space exports · historical validation'}[key]


if __name__=='__main__':
    path=ROOT/'src/data.json'
    snapshot=json.loads(path.read_text())
    add_player_profiles(snapshot)
    snapshot['buildStatus']='updating'
    snapshot['generatedAt']=datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(snapshot,separators=(',',':'),allow_nan=False))
    print('Attached 230 reviewed profiles, nine scaling rows and two historical validation rows.')
