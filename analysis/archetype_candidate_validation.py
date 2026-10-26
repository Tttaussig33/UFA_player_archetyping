"""Explore style groups, repeatable passing outcomes and scouting comparisons.

Fixed pilot design: 2025 style profiles train, 2026 evaluates; repeat with
2024→2025. Nine existing style features, equal group weights; K=2..6. Pick the
smallest K within .02 of the best silhouette, with every group >=max(12, 5% N).
Compare separation with 100 correlated Gaussian reference samples, and refit
60 whole-team bootstraps. Pilot gates (.05 null-tail, .8 median bootstrap ARI,
.6 later half-season ARI) are screening rules, not universal statistical truths.

Passing-outcome check: geometry models trained before each evaluation season;
team and player log-odds offsets learned from the preceding season only, ridge
precision 5. Compare later Brier loss against the geometry+team baseline.
These are coarse retrospective comparisons, not intrinsic skill or causal value.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from passing_profile_validation import load_events, aggregate, qualify, FEATURES, GROUPS, serialize
from multiseason_release_validation import AdditiveLogistic, cluster_ci

HERE = Path(__file__).resolve().parent
SEED = 20261027
FEATURE_KEYS = list(FEATURES)
FEATURE_LABELS = {**{k:v[1] for k,v in FEATURES.items()},
    'releaseY':'Average throwing location (Y)', 'releaseSide':'Throws from near either sideline'}
GROUP_LABELS = [g.replace('Release locations','Throwing locations') for g in GROUPS]
WEIGHTS = np.array([1 / (len(GROUPS)*sum(FEATURES[f][0] == FEATURES[k][0] for f in FEATURES)) for k in FEATURE_KEYS])


def kmeans(x, k, seed, restarts=20):
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(restarts):
        centers = [x[rng.integers(len(x))]]
        for j in range(1,k):
            dist = ((x[:,None,:]-np.array(centers)[None,:,:])**2).sum(axis=2).min(axis=1)
            index = rng.choice(len(x),p=dist/dist.sum()) if dist.sum() else rng.integers(len(x))
            centers.append(x[index])
        centers = np.array(centers)
        for iteration in range(200):
            ds = ((x[:,None,:]-centers[None,:,:])**2).sum(axis=2)
            labels = ds.argmin(axis=1)
            if len(np.unique(labels)) != k: break
            new = np.array([x[labels==j].mean(axis=0) for j in range(k)])
            converged = np.max(np.abs(new-centers)) < 1e-8
            centers = new
            if converged: break
        labels = ((x[:,None,:]-centers[None,:,:])**2).sum(axis=2).argmin(axis=1)
        if len(np.unique(labels)) != k: continue
        inertia = float(((x-centers[labels])**2).sum())
        if best is None or inertia < best[0]: best = (inertia,centers.copy(),labels.copy())
    if best is None: raise ValueError('No nonempty clustering fit')
    return best[1],best[2],best[0]


def assign(x, centers):
    return ((x[:,None,:]-centers[None,:,:])**2).sum(axis=2).argmin(axis=1)


def silhouette(x, labels):
    ds = np.sqrt(np.maximum(0,((x[:,None,:]-x[None,:,:])**2).sum(axis=2)))
    ids = np.unique(labels)
    out = []
    for i in range(len(x)):
        same = labels == labels[i]
        if same.sum() == 1: out.append(0.0); continue
        a = ds[i,same].sum()/(same.sum()-1)
        b = min(ds[i,labels==j].mean() for j in ids if j!=labels[i])
        out.append((b-a)/max(a,b) if max(a,b)>0 else 0.0)
    return float(np.mean(out))


def adjusted_rand(a,b):
    _,ai = np.unique(a,return_inverse=True); _,bi = np.unique(b,return_inverse=True)
    table = np.zeros((ai.max()+1,bi.max()+1),dtype=int)
    np.add.at(table,(ai,bi),1)
    choose2 = lambda x: np.sum(x*(x-1)/2)
    pairs = len(a)*(len(a)-1)/2
    expected = choose2(table.sum(axis=1))*choose2(table.sum(axis=0))/pairs
    maximum = .5*(choose2(table.sum(axis=1))+choose2(table.sum(axis=0)))
    return float((choose2(table)-expected)/(maximum-expected)) if maximum != expected else 1.0


def fit_candidates(x,seed,restarts=20):
    fits = []
    for k in range(2,7):
        centers, labels, inertia = kmeans(x,k,seed+k,restarts)
        counts = np.bincount(labels,minlength=k)
        fits.append(dict(k=k, silhouette=silhouette(x,labels),counts=counts.tolist(),
            admissible=bool(counts.min() >= max(12,.05*len(x))), centers=centers,labels=labels))
    valid = [f for f in fits if f['admissible']]
    if not valid: raise ValueError('No candidate meets the declared size rule')
    maximum = max(f['silhouette'] for f in valid)
    chosen = next(f for f in valid if f['silhouette'] >= maximum-.02)
    return fits,chosen


def cluster_study(annual, halves, year):
    train = qualify(annual[annual.season.eq(year-1)],minimum=100,games=6).sort_values('player').reset_index(drop=True)
    test = qualify(halves[halves.season.eq(year)],minimum=50,games=3)
    early = test[test.half.eq('early')].set_index('player')
    late = test[test.half.eq('late')].set_index('player')
    both = sorted(set(early.index)&set(late.index))
    mean, sd = train[FEATURE_KEYS].mean(),train[FEATURE_KEYS].std(ddof=0)
    transform = lambda p: ((p[FEATURE_KEYS]-mean)/sd).to_numpy(float)*np.sqrt(WEIGHTS)
    x = transform(train)
    fits,chosen = fit_candidates(x,SEED+year)
    print(f'{year}: {len(train)} training profiles; chose K={chosen["k"]}, silhouette {chosen["silhouette"]:.3f}.',flush=True)
    rng = np.random.default_rng(SEED+year)
    teams = train.team.unique()
    boot = []
    for i in range(60):
        selected = rng.choice(teams,size=len(teams),replace=True)
        ix = np.concatenate([np.flatnonzero(train.team.to_numpy()==t) for t in selected])
        centers,_,_ = kmeans(x[ix],chosen['k'],SEED+year+i+10000,restarts=10)
        boot.append(adjusted_rand(chosen['labels'],assign(x,centers)))
    null = []
    covariance = np.cov(x,rowvar=False)
    for i in range(100):
        # This is an explicit unimodal reference assumption, not a distribution-free test.
        z = rng.multivariate_normal(x.mean(axis=0),covariance,size=len(x))
        nf,_ = fit_candidates(z,SEED+year+i+20000,restarts=5)
        null.append(max(f['silhouette'] for f in nf if f['admissible']))
    a,b = assign(transform(early.loc[both]),chosen['centers']),assign(transform(late.loc[both]),chosen['centers'])
    chance = sum(np.mean(a==j)*np.mean(b==j) for j in range(chosen['k']))
    null_tail = (1+sum(v>=chosen['silhouette'] for v in null))/(len(null)+1)
    ari = adjusted_rand(a,b)
    gates = dict(separation=null_tail<.05,refitStability=float(np.median(boot))>=.8,temporalStability=ari>=.6)
    full_test = qualify(annual[annual.season.eq(year)],minimum=100,games=6).sort_values('player').reset_index(drop=True)
    actual_centers = chosen['centers']/np.sqrt(WEIGHTS)*sd.to_numpy()+mean.to_numpy()
    summary = dict(testSeason=year,referenceSeason=year-1,referencePlayers=len(train),
        evaluatedHalfSeasonPlayers=len(both), selectedK=chosen['k'],
        candidates=[{k:v for k,v in f.items() if k not in ['centers','labels']} for f in fits],
        selectedSilhouette=chosen['silhouette'],gaussianReferenceTailFraction=null_tail,
        gaussianReference95=np.quantile(null,[.025,.975]).tolist(),gaussianReferenceScores=null,
        bootstrapARI=dict(median=float(np.median(boot)),range95=np.quantile(boot,[.025,.975]).tolist()),
        heldoutARI=ari,heldoutSameGroupRate=float(np.mean(a==b)),chanceSameGroupRate=float(chance),
        pilotGates=gates,passedPilotGates=all(gates.values()),
        scalerMean=mean.to_dict(),scalerSD=sd.to_dict(),weights=dict(zip(FEATURE_KEYS,WEIGHTS.tolist())),
        weightedCenters=chosen['centers'].tolist(),
        groupCentroids=[dict(group=j,trainingPlayers=chosen['counts'][j],
            **{f:float(actual_centers[j,k]) for k,f in enumerate(FEATURE_KEYS)}) for j in range(chosen['k'])],
        temporalMembership=[dict(player=p,earlyGroup=int(aa),laterGroup=int(bb)) for p,aa,bb in zip(both,a,b)])
    full_test['group'] = assign(transform(full_test),chosen['centers'])
    return summary,full_test


def geometry(events):
    d = events[events.namedThrower].copy()
    d['player'] = d.Thrower
    for field,bins,new in [('distance',[-1,10,20,30,40,50,60,80,np.inf],'distanceBand'),
        ('gain',[-np.inf,-10,0,10,20,30,40,60,np.inf],'gainBand'),
        ('ty',[-1,20,40,60,80,100,121],'throwingBand')]:
        d[new] = pd.cut(d[field],bins,right=False).astype(str)
    d['sideline'] = d.releaseSide.astype(str)
    d['endzoneTarget'] = d.ry.ge(100).astype(str)
    return d


def fit_offsets(frame,probability,key,penalty=5.0):
    p = np.clip(probability,1e-6,1-1e-6)
    baseline = np.log(p/(1-p))
    mapping = {}
    for label,ix in frame.groupby(key).indices.items():
        y = frame.iloc[ix].complete.to_numpy(float)
        offset = 0.0
        for _ in range(100):
            pred = AdditiveLogistic.sigmoid(baseline[ix]+offset)
            step = ((y-pred).sum()-penalty*offset)/((pred*(1-pred)).sum()+penalty)
            offset += step
            if abs(step)<1e-9: break
        mapping[label] = float(offset)
    return mapping


def apply_offsets(base,frame,mapping,key):
    p = np.clip(base,1e-6,1-1e-6)
    return AdditiveLogistic.sigmoid(np.log(p/(1-p))+frame[key].map(mapping).fillna(0).to_numpy(float))


def outcome_study(d,year):
    fields = ['distanceBand','gainBand','throwingBand','sideline','endzoneTarget']
    historic = d[d.season.lt(year-1)]
    prior = d[d.season.eq(year-1)].copy().reset_index(drop=True)
    test = d[d.season.eq(year)].copy().reset_index(drop=True)
    prior_base = AdditiveLogistic(fields).fit(historic,'complete').predict(prior)
    test_fit = AdditiveLogistic(fields).fit(d[d.season.lt(year)],'complete')
    test_base = test_fit.predict(test)
    teams = fit_offsets(prior,prior_base,'team')
    prior_team = apply_offsets(prior_base,prior,teams,'team')
    players = fit_offsets(prior,prior_team,'player')
    test_team = apply_offsets(test_base,test,teams,'team')
    test_player = apply_offsets(test_team,test,players,'player')
    past_counts = prior.groupby('player').size()
    mask = test.player.isin(past_counts[past_counts>=100].index).to_numpy()
    evaluated = test[mask]
    y = evaluated.complete.to_numpy(float)
    base_loss = (test_team[mask]-y)**2
    difference = base_loss-(test_player[mask]-y)**2
    comparisons = dict(relativeBrierImprovementPct=float(difference.mean()/base_loss.mean()*100),
        absoluteBrierImprovement=float(difference.mean()),baselineBrier=float(base_loss.mean()),
        playerBrier=float(((test_player[mask]-y)**2).mean()),
        gameBootstrap=cluster_ci(difference,evaluated.game.to_numpy()),
        playerBootstrap=cluster_ci(difference,evaluated.player.to_numpy()))
    test['expected'] = test_base
    test['residual'] = test.complete.astype(float)-test_base
    summary = dict(testSeason=year,offsetTrainingSeason=year-1,
        geometryTrainingSeasons=sorted(d.loc[d.season.lt(year),'season'].unique().tolist()),
        evaluatedThrows=len(evaluated),evaluatedPlayers=int(evaluated.player.nunique()),
        actualCompletionRate=float(y.mean()),predictedCompletionRate=float(test_player[mask].mean()),
        comparisons=comparisons,minimumPriorThrows=100,
        coefficients=dict(teamOffsets=teams,playerOffsets=players),
        convergence=dict(iterations=test_fit.iterations,maxParameterChange=test_fit.max_delta),
        calibration=[dict(bin=int(i),throws=len(g),actual=float(g.complete.mean()),expected=float(g.expected.mean()))
            for i,g in test.groupby(pd.cut(test.expected,[0,.5,.7,.8,.9,.95,1.0001],labels=False),observed=True)])
    print(f'{year}: passing-performance increment {comparisons["relativeBrierImprovementPct"]:+.3f}% Brier; {len(evaluated)} test throws.',flush=True)
    return summary,test


def game_interval(frame):
    a = frame.groupby('game').residual.agg(['sum','size'])
    if len(a)<6: return None,None
    rng = np.random.default_rng(SEED)
    ix = rng.integers(0,len(a),(2000,len(a)))
    values = a['sum'].to_numpy()[ix].sum(axis=1)/a['size'].to_numpy()[ix].sum(axis=1)
    return np.quantile(values,[.025,.975]).tolist()


def run():
    events,names,teams,hashes,quality,cutoffs = load_events()
    annual,halves = aggregate(events,half=False),aggregate(events)
    clusters=[]
    for year in [2025,2026]:
        summary,profiles = cluster_study(annual,halves,year)
        clusters.append(summary)
    d=geometry(events)
    outcomes=[]
    for year in [2025,2026]:
        summary,scored = outcome_study(d,year)
        outcomes.append(summary)
    rows=[]
    for _,p in profiles.iterrows():
        throws=scored[scored.player.eq(p.player)]
        hucks=throws[throws.huck]
        low,high=game_interval(throws)
        rows.append(dict(id=p.player,name=names[p.player],team=p.team,
            teamName=teams.get(('2026',p.team),p.team),season=2026,
            throws=int(p.throws),catches=int(p.catches),throwGames=int(p.throwGames),catchGames=int(p.catchGames),
            completions=int(p.completions),completionRate=float(p.completions/p.throws),
            turnovers=int(p.throws-p.completions),huckAttempts=len(hucks),huckCompletions=int(hucks.complete.sum()),
            huckCompletion=float(hucks.complete.mean()) if len(hucks) else None,
            meanForwardGain=float(throws.gain.mean()),
            expectedCompletion=float(throws.expected.mean()),
            completionAboveExpected=float(throws.residual.mean()),completionLower=low,completionUpper=high,
            exploratoryGroup=int(p.group),**{k:float(p[k]) for k in FEATURE_KEYS}))
    result=dict(study='Archetype and passing-performance pilot',analyzedAt=datetime.now(timezone.utc).isoformat(),sourceSnapshot='2026-10-12',
        sourceHashes=hashes,quality=quality,features={k:dict(label=FEATURE_LABELS[k],
            group=FEATURES[k][0].replace('Release locations','Throwing locations'),
            storedUnit='yards' if FEATURES[k][2]=='yd' else 'fraction') for k in FEATURE_KEYS},
        clusterStudies=clusters,outcomeStudies=outcomes,profiles=rows,
        methodReferences=['https://scikit-learn.org/stable/modules/clustering.html#clustering-performance-evaluation'],
        caveats=['Exploratory historical test; these seasons were examined in prior work.',
            'Profile cohort requires 100 throws and 100 completed catches, 6 games per role, one team per season.',
            'A forced partition is not evidence of discrete archetypes. The Gaussian reference is an explicit assumption.',
            'Completion comparisons adjust coarse geometry, not wind, marking, routes or receiver ability.',
            'Geometry uses recorded endpoints retrospectively; it is not a forecast available before the throw.',
            'No lineup replacement outcome was observed or tested. Similar players are scouting candidates.',
            'Intervals are conditional on fitted models; repeated opponents and profile uncertainty remain.'])
    path=HERE/'archetype_candidate_validation.json'
    path.write_text(json.dumps(result,default=serialize,indent=2,allow_nan=False)+'\n')
    print(f'Saved {len(rows)} current profiles to {path}',flush=True)
    return result


if __name__=='__main__': run()
