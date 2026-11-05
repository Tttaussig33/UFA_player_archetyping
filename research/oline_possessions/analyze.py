"""Exploratory subsequent O-line possession comparisons with game-level uncertainty."""
from pathlib import Path
import json
import math
import hashlib
import warnings
import numpy as np
import pandas as pd
import patsy
import scipy
from scipy import stats
import statsmodels
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parent
SEED = 20261105
DRAWS = 10000
RNG = np.random.default_rng(SEED)
STAGE_NAMES = {1:'First',2:'Second',3:'Third or later'}

def clean(value):
    if isinstance(value, dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value, (list,tuple,np.ndarray)): return [clean(v) for v in value]
    if isinstance(value, (np.integer,)): return int(value)
    if isinstance(value, (np.floating,float)): return float(value) if np.isfinite(value) else None
    if isinstance(value, np.bool_): return bool(value)
    return value

def dump(name, value):
    (ROOT/name).write_text(json.dumps(clean(value),indent=2,allow_nan=False)+'\n')

def quantile(a):
    good = np.asarray(a)[np.isfinite(a)]
    return [float(np.quantile(good,.025)),float(np.quantile(good,.975))] if len(good) else None

def observed(d, outcome, categories=(1,2,3), category='stage'):
    games = sorted(d.GameID.unique())
    n = np.zeros((len(games),len(categories))); y = np.zeros_like(n)
    gi = pd.Categorical(d.GameID,categories=games).codes
    ci = pd.Categorical(d[category],categories=categories).codes
    assert (ci>=0).all()
    np.add.at(n,(gi,ci),1); np.add.at(y,(gi,ci),d[outcome].to_numpy(float))
    weights = RNG.multinomial(len(games),np.full(len(games),1/len(games)),size=DRAWS)
    with np.errstate(divide='ignore',invalid='ignore'):
        b = (weights@y)/(weights@n)
        means = y.sum(0)/n.sum(0)
    result = {'groups':[],'games':len(games),'differences':[]}
    for i,k in enumerate(categories):
        q = d[d[category].eq(k)]
        display_name = ({0:'First',1:'All subsequent'} if category=='regained' else STAGE_NAMES).get(k,str(k))
        result['groups'].append({'stage':int(k),'name':display_name,
            'n':len(q),'sum':float(y[:,i].sum()),'estimate':means[i],
            'median':float(q[outcome].median()) if len(q) else None,
            'ci95':quantile(b[:,i]),'games':q.GameID.nunique()})
        if i:
            result['differences'].append({'from':int(categories[0]),'to':int(k),'difference':means[i]-means[0],
                                         'ci95':quantile(b[:,i]-b[:,0])})
    return clean(result)

def dataset_metrics(p,t,cutoff=60,vertical=False):
    resolved = p[p.outcome.isin(['goal','turnover'])].copy()
    hp = p[p.first_y.le(cutoff)].copy()
    ht = t[t.first_y.le(cutoff)].copy()
    hcol = 'vertical_huck' if vertical else 'huck'
    if vertical:
        counts = ht.groupby('possession_id').vertical_huck.sum()
        hp['has_huck'] = hp.possession_id.map(counts).fillna(0).gt(0).astype(int)
        early = ht[ht.ordinal.le(3)].groupby('possession_id').vertical_huck.sum()
        hp['early_huck'] = hp.possession_id.map(early).fillna(0).gt(0).astype(int)
    return {
        'throws_goal':(resolved[resolved.goal.eq(1)],'throws'),
        'throws_turnover':(resolved[resolved.goal.eq(0)],'throws'),
        'throws_all':(resolved,'throws'),
        'scoring':(resolved,'goal'),
        'huck_share':(ht,hcol),
        'early_huck':(hp,'early_huck'),
        'any_huck':(hp,'has_huck'),
        'huck_completion':(ht[ht[hcol].eq(1)],'complete')}

CONTEXT = 'bs(first_y, df=5, degree=3, include_intercept=False) + bs(abs_x, df=3, degree=2, include_intercept=False) + C(team) + C(opponent) + C(quarter) + point_remaining'

def prepare(d,point_lookup):
    d = d.copy()
    if 'point_start_time' not in d:
        d['point_start_time'] = d.point_id.map(point_lookup.point_start_time)
    d['point_remaining'] = (720 - d.point_start_time).clip(0,720)/720
    d['abs_x'] = d.first_x.abs()
    return d.dropna(subset=['first_y','abs_x','point_remaining']).reset_index(drop=True)

def fit_model(d,outcome,family='binomial',context=CONTEXT,interaction=False,extra='',offset=None):
    formula = ('regained * C(team)' if interaction else 'C(stage, levels=[1,2,3])') + ' + ' + context
    if extra: formula += ' + ' + extra
    X = patsy.dmatrix(formula,d,return_type='dataframe')
    assert len(X)==len(d)
    rank = np.linalg.matrix_rank(X.to_numpy())
    assert rank==X.shape[1],(formula,rank,X.shape[1])
    fam = sm.families.Binomial() if family=='binomial' else sm.families.Poisson()
    with warnings.catch_warnings(record=True) as ws:
        fit = sm.GLM(d[outcome].to_numpy(float),X,family=fam,offset=offset).fit(
            maxiter=100,tol=1e-10,cov_type='cluster',
            cov_kwds={'groups':d.GameID.to_numpy(),'use_correction':True})
    assert fit.converged
    assert np.isfinite(fit.params).all() and np.isfinite(fit.cov_params()).all().all()
    fit_info = {'formula':formula,'family':family,'n':len(d),'games':d.GameID.nunique(),
                'design_rank':rank,'columns':X.shape[1],'converged':fit.converged,
                'warnings':[str(w.message) for w in ws], 'offset':'logit(recorded CP)' if offset is not None else None}
    return fit,X,fit_info

def marginal(fit,X,indices,changes,offset=None,df=None):
    xx = X.to_numpy()[indices].copy()
    cols = list(X.columns)
    for col,val in changes.items(): xx[:,cols.index(col)] = val
    off = 0 if offset is None else np.asarray(offset)[indices]
    eta = xx @ fit.params.to_numpy() + off
    mu = fit.family.link.inverse(eta)
    deriv = fit.family.link.inverse_deriv(eta)
    gradient = (xx*deriv[:,None]).mean(0)
    estimate = float(mu.mean())
    se = math.sqrt(max(0,float(gradient @ fit.cov_params().to_numpy() @ gradient)))
    critical = stats.t.ppf(.975,df) if df else 1.96
    return {'estimate':estimate,'ci95':[estimate-critical*se,estimate+critical*se]},gradient

def adjusted(d,outcome,family='binomial',context=CONTEXT,extra='',offset=None):
    fit,X,info = fit_model(d,outcome,family,context,extra=extra,offset=offset)
    ids = np.arange(len(d)); groups=[];grads=[]
    df = d.GameID.nunique()-1
    for stage in [1,2,3]:
        changes={f'C(stage, levels=[1, 2, 3])[T.{s}]':int(stage==s) for s in [2,3]}
        result,grad = marginal(fit,X,ids,changes,offset,df)
        groups.append({'stage':stage,**result});grads.append(grad)
    diffs=[]
    for i in [1,2]:
        delta=groups[i]['estimate']-groups[0]['estimate']; g=grads[i]-grads[0]
        se=math.sqrt(max(0,float(g @ fit.cov_params().to_numpy() @ g)))
        crit=stats.t.ppf(.975,df)
        diffs.append({'from':1,'to':i+1,'difference':delta,'se':se,
                      'ci95':[delta-crit*se,delta+crit*se],
                      'p_value':float(2*stats.t.sf(abs(delta/se),df)) if se else None})
    delta=groups[2]['estimate']-groups[1]['estimate'];g=grads[2]-grads[1]
    se=math.sqrt(max(0,float(g @ fit.cov_params().to_numpy() @ g)))
    crit=stats.t.ppf(.975,df)
    later={'from':2,'to':3,'difference':delta,'ci95':[delta-crit*se,delta+crit*se],
           'p_value':float(2*stats.t.sf(abs(delta/se),df)) if se else None,
           'role':'Exploratory follow-up; not a primary first-versus-subsequent contrast.'}
    return {'groups':groups,'differences':diffs,'second_to_third_or_later':later,'model':info}

def team_changes(d,outcome,family='binomial',context=CONTEXT):
    fit,X,info=fit_model(d,outcome,family,context,interaction=True)
    cols=list(X.columns);rows=[]
    interactions=[c for c in cols if 'regained:C(team)' in c or 'C(team)' in c and ':regained' in c]
    R=np.zeros((len(interactions),len(cols)))
    for i,col in enumerate(interactions):R[i,cols.index(col)]=1
    test=fit.wald_test(R,use_f=True,scalar=True)
    for team,q in d.groupby('team',sort=True):
        ids=q.index.to_numpy();df=q.GameID.nunique()-1
        gg=[];mm=[]
        for state in [0,1]:
            changes={'regained':state}
            for c in interactions:changes[c]=state*int('[T.'+team+']' in c)
            m,g=marginal(fit,X,ids,changes,df=df);mm.append(m);gg.append(g)
        delta=mm[1]['estimate']-mm[0]['estimate'];g=gg[1]-gg[0]
        se=math.sqrt(max(0,float(g@fit.cov_params().to_numpy()@g)))
        crit=stats.t.ppf(.975,df)
        rows.append({'team':team,'games':q.GameID.nunique(),
                     'opening_n':int(q.regained.eq(0).sum()),'subsequent_n':int(q.regained.eq(1).sum()),
                     'opening':mm[0]['estimate'],'subsequent':mm[1]['estimate'],
                     'difference':delta,'ci95':[delta-crit*se,delta+crit*se],
                     'p_value':float(2*stats.t.sf(abs(delta/se),df)) if se else 1})
    adjusted_p=multipletests([r['p_value'] for r in rows],method='holm')[1]
    for r,p in zip(rows,adjusted_p):r['p_holm']=float(p)
    return {'teams':rows,'heterogeneity_p':float(test.pvalue),'model':info,
            'note':'Field/context-adjusted first vs all subsequent possessions. Within-team t reference uses team game count minus one; Holm correction across 22 teams within this metric. Few games per team remain a limitation.'}

def main():
    p_all=pd.read_csv(ROOT/'possessions.csv');t_all=pd.read_csv(ROOT/'throws.csv')
    points=pd.read_csv(ROOT/'points.csv')
    p=p_all[~p_all.has_timeout].copy();t=t_all[~t_all.has_timeout].copy()
    lookup=p_all.drop_duplicates('point_id').set_index('point_id')
    metrics=dataset_metrics(p,t)
    result={'scope':{'year':2026,'games':p.GameID.nunique(),'teams':p.team.nunique(),
                     'possessions':len(p),'resolved_possessions':int(p.outcome.ne('period_end').sum()),
                     'period_end_possessions':int(p.outcome.eq('period_end').sum()),
                     'physical_throws':len(t),'timeout_possessions_excluded':int(p_all.has_timeout.sum()),
                     'huck_maximum_start_y':60,'bootstrap_draws':DRAWS,'seed':SEED},
            'league':{},'teams':[], 'adjusted':{},'team_changes':{}}
    for key,(d,outcome) in metrics.items():
        result['league'][key]=observed(d,outcome)
        result['league'][key]['first_vs_all_subsequent']=observed(d,outcome,(0,1),'regained')
    for team,pp in p.groupby('team',sort=True):
        tt=t[t.team.eq(team)]
        row={'team':team,'team_name':pp.team_name.iloc[0],'games':pp.GameID.nunique(),'metrics':{}}
        for key,(d,outcome) in dataset_metrics(pp,tt).items():
            row['metrics'][key]=observed(d,outcome)
            if key=='huck_completion':
                row['metrics'][key]['first_vs_all_subsequent']=observed(d,outcome,(0,1),'regained')
        result['teams'].append(row)
    print('Observed league and team estimates complete.',flush=True)

    for key in ['throws_goal','throws_turnover','throws_all','scoring','early_huck','any_huck']:
        d,outcome=metrics[key];dd=prepare(d,lookup)
        family='poisson' if key.startswith('throws') else 'binomial'
        result['adjusted'][key]=adjusted(dd,outcome,family)
        if key!='throws_all':result['team_changes'][key]=team_changes(dd,outcome,family)
        print('Adjusted',key,flush=True)
    # For huck choice, field position at that throw is a pre-choice control.
    ht=prepare(metrics['huck_share'][0],lookup)
    ht=ht[ht.ty.lt(90)].reset_index(drop=True)
    hcontext=CONTEXT+' + bs(ty, df=5, degree=3, include_intercept=False) + I(abs(tx)/26.67)'
    result['adjusted']['huck_share']=adjusted(ht,'huck',context=hcontext)
    result['team_changes']['huck_share']=team_changes(ht,'huck',context=hcontext)
    hc=prepare(metrics['huck_completion'][0],lookup)
    hc=hc[hc.cp.between(0.001,.999)].reset_index(drop=True)
    hc['logit_cp']=np.log(hc.cp.to_numpy()/(1-hc.cp.to_numpy()))
    # Braden confirmed that drops are credited for CPOE, but the saved CP
    # training target is not independently established. Fit the score's slope
    # instead of assuming it is already calibrated to actual catches.
    result['adjusted']['huck_completion']=adjusted(hc,'complete',context='logit_cp + C(team) + C(opponent) + C(quarter)')
    result['adjusted']['huck_completion']['model']['interpretation']='Actual catches, with recorded CP used as a fitted difficulty covariate; not assumed calibrated to the catch target.'
    result['cp_offset_sensitivity']=adjusted(hc,'complete',context='C(team) + C(opponent) + C(quarter)',offset=hc.logit_cp.to_numpy())
    result['huck_outcomes']=[]
    for stage,q in hc.groupby('stage'):
        result['huck_outcomes'].append({'stage':stage,'attempts':len(q),'caught':int(q.complete.sum()),
          'catch_rate':q.complete.mean(),'drops':int(q['drop'].sum()),'mean_cp':q.cp.mean(),
          'actual_minus_recorded_cp_pp':100*(q.complete-q.cp).mean(),
          'credited_cpoe_pp':100*(q.complete+q['drop']-q.cp).mean(),'huck_assists':int(q.assist.sum())})
    completed_ids=set(t[t.first_y.le(60)&t.huck.eq(1)&t.complete.eq(1)].possession_id)
    continuation=p[p.possession_id.isin(completed_ids)&p.outcome.ne('period_end')]
    result['scoring_after_completed_huck']=observed(continuation,'goal')
    print('Huck models complete.',flush=True)
    hp=prepare(metrics['early_huck'][0],lookup)
    regains=hp[hp.regained.eq(1)].reset_index(drop=True)
    # Correlate preceding activity with early hucking within subsequent possessions,
    # rather than using the mechanically related current possession length.
    activity={}
    for col in ['prior_own_throws','prior_total_throws']:
        dd=regains.dropna(subset=[col]).reset_index(drop=True)
        formula='C(stage) + '+CONTEXT+' + np.log1p('+col+')'
        X=patsy.dmatrix(formula,dd,return_type='dataframe')
        fit=sm.GLM(dd.early_huck,X,family=sm.families.Binomial()).fit(cov_type='cluster',cov_kwds={'groups':dd.GameID,'use_correction':True})
        term='np.log1p('+col+')';coef=float(fit.params[term]);se=float(fit.bse[term]);df=dd.GameID.nunique()-1
        crit=stats.t.ppf(.975,df)
        activity[col]={'n':len(dd),'missing':len(regains)-len(dd),'coefficient_log1p':coef,'se':se,
           'odds_ratio_for_doubling_one_plus_count':math.exp(coef*math.log(2)),
           'or_ci95':[math.exp((coef-crit*se)*math.log(2)),math.exp((coef+crit*se)*math.log(2))],
           'p_value':float(2*stats.t.sf(abs(coef/se),df)),'formula':formula}
    regains['activity_band']=pd.cut(regains.prior_own_throws,[-1,5,10,20,10000],labels=['0–5','6–10','11–20','21+'])
    activity['observed_bands']=[{'band':str(b),'n':len(q),'early_hucks':int(q.early_huck.sum()),'rate':q.early_huck.mean()}
                                for b,q in regains.groupby('activity_band',observed=True)]
    result['prior_activity']=activity
    result['starting_positions']=[{'stage':int(s),'n':len(q),'known_location_n':int(q.first_y.notna().sum()),
              'mean_y':q.first_y.mean(),'median_y':q.first_y.median(),'mean_yards_to_goal_line':100-q.first_y.mean(),
              'huck_eligible_n':int(q.first_y.le(60).sum())} for s,q in p.groupby('stage')]
    # Show scoring within the same coarse starting spaces, retaining near-goal starts.
    pp=p[p.outcome.ne('period_end')&p.first_y.notna()].copy()
    pp['start_band']=pd.cut(pp.first_y,[-.01,20,40,60,80,120],right=True,
                          labels=['Own end zone: 0–20','Deep own half: 20–40','To midfield: 40–60','Attacking half: 60–80','Near goal: 80–120'])
    result['scoring_by_start']=[{'band':str(b),'stage':int(s),'n':len(q),'goals':int(q.goal.sum()),'rate':q.goal.mean()}
                 for (b,s),q in pp.groupby(['start_band','stage'],observed=True)]
    recovery=[]
    for team,q in points[~points.has_timeout].groupby('team'):
        failed=q[q.opening_outcome.eq('turnover')]
        recovery.append({'team':team,'points':len(q),'opening_goal_points':int(q.opening_outcome.eq('goal').sum()),
                         'opening_turnover_points':len(failed),'regained_points':int(failed.own_possessions.ge(2).sum()),
                         'eventual_holds_after_opening_turnover':int(failed.hold.sum())})
    result['recovery_supporting']=recovery
    print('Prior-activity and field comparisons complete.',flush=True)

    # Sensitivities were specified before inspecting the expanded results.
    audit=json.loads((ROOT/'cohort_audit.json').read_text())
    mismatch_games={x['game'] for x in audit['score_reconciliation']['mismatches']}
    variants={
      'all_possessions_including_timeouts':(p_all,t_all,60,False),
      'exclude_whole_timeout_or_injury_points':(p[~p.point_has_timeout&~p.point_has_injury],t[~t.point_has_timeout&~t.point_has_injury],60,False),
      'exclude_four_score_discrepancy_games':(p[~p.GameID.isin(mismatch_games)],t[~t.GameID.isin(mismatch_games)],60,False),
      'huck_start_y_at_most_50':(p,t,50,False),
      'huck_start_y_at_most_70':(p,t,70,False),
      'hucks_all_start_locations':(p,t,120,False),
      'huck_over_40_forward_yards':(p,t,60,True)}
    result['sensitivity']={}
    for name,(pp,tt,cutoff,vertical) in variants.items():
        mm=dataset_metrics(pp,tt,cutoff,vertical)
        result['sensitivity'][name]={key:observed(d,out,(0,1),'regained') for key,(d,out) in mm.items()}
    result['sensitivity']['period_end_as_no_goal']=observed(p,'goal')
    # Field adjustment restricted to common deep/midfield starts, without redefining
    # the all-field scoring result. Also compare within the same game.
    result['model_sensitivity']={}
    for key in ['scoring','throws_goal','throws_turnover','early_huck']:
        d,outcome=metrics[key];dd=prepare(d,lookup);family='poisson' if key.startswith('throws') else 'binomial'
        common=dd[dd.first_y.le(60)].reset_index(drop=True)
        result['model_sensitivity'][key]={'common_start_region':adjusted(common,outcome,family),
            'within_game':adjusted(dd,outcome,family,context=CONTEXT.replace('C(opponent)','C(GameID)'))}
        print('Sensitivity',key,flush=True)
    # Follow-up checks motivated by the first expanded results, rather than new
    # outcomes selected because they produce a small p-value.
    result['follow_up_checks']={
        'reason':'The initial analysis showed an early-huck change and fewer throws. Check the opening-pass concern and whether possession length predicts the same pattern.',
        'exact_possession_counts':p.own_possession.value_counts().sort_index().to_dict(),
        'throws_by_huck_and_end':[{'stage':int(s),'outcome':end,'has_huck':int(h),'n':len(q),
                                 'mean_throws':q.throws.mean(),'mean_start_y':q.first_y.mean()}
               for (s,end,h),q in p[p.outcome.ne('period_end')].groupby(['stage','outcome','has_huck'])]}
    result['throw_windows']=[]
    full_ht=metrics['huck_share'][0]
    for label,lo,hi in [('1',1,1),('2–3',2,3),('4–6',4,6),('7+',7,1000)]:
        q=full_ht[full_ht.ordinal.between(lo,hi)]
        result['throw_windows'].append({'window':label,**observed(q,'huck')})
    window23=ht[ht.ordinal.between(2,3)].reset_index(drop=True)
    result['follow_up_checks']['adjusted_huck_choice_throws_2_3']=adjusted(window23,'huck',context=hcontext)
    exact3p=p[p.own_possession.le(3)];exact3t=t[t.own_possession.le(3)]
    result['follow_up_checks']['third_possession_only']={key:observed(d,out)
        for key,(d,out) in dataset_metrics(exact3p,exact3t).items()}
    league_tests=[row for value in result['adjusted'].values() for row in value['differences']]
    for row,pv in zip(league_tests,multipletests([r['p_value'] for r in league_tests],method='holm')[1]):
        row['p_holm_across_16_league_comparisons']=float(pv)
    names=list(result['team_changes'])
    hp=multipletests([result['team_changes'][k]['heterogeneity_p'] for k in names],method='holm')[1]
    for k,pv in zip(names,hp):result['team_changes'][k]['heterogeneity_p_holm']=float(pv)
    all_team_tests=[row for value in result['team_changes'].values() for row in value['teams']]
    for row,pv in zip(all_team_tests,multipletests([r['p_value'] for r in all_team_tests],method='holm')[1]):
        row['p_holm_across_132_team_comparisons']=float(pv)
    result['environment']={'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'statsmodels':statsmodels.__version__,'patsy':patsy.__version__}
    result['inputs']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['possessions.csv','throws.csv','points.csv','analysis_design.json']}
    dump('results.json',result)
    print(json.dumps(clean({'adjusted':{k:v['differences'] for k,v in result['adjusted'].items()},
        'team_heterogeneity':{k:(v['heterogeneity_p'],v['heterogeneity_p_holm']) for k,v in result['team_changes'].items()},
        'prior_activity':activity}),indent=2))

if __name__=='__main__':main()
