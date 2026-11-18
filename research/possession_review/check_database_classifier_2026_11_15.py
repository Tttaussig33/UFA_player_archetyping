"""Archive final-definition film labels and run a fixed small database diagnostic."""
from collections import Counter
from pathlib import Path
import json
import hashlib
import math
import re

import numpy as np
from opening_classifier_pilot import fit, predict, FEATURES, PENALTY

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, v):
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def score(rows, key):
    c = Counter((r['human_label'], r[key]) for r in rows)
    return {'n':len(rows), 'centering':sum(r['human_label']=='setup1' for r in rows),
        'noCentering':sum(r['human_label']=='attack1' for r in rows),
        'correctCentering':c['setup1','setup1'], 'correctNoCentering':c['attack1','attack1'],
        'falseCentering':c['attack1','setup1'], 'missedCentering':c['setup1','attack1'],
        'correct':c['setup1','setup1']+c['attack1','attack1']}


def main():
    paths = {'plan':HERE/'classifier_check_plan_2026-11-15.json',
        'export':HERE/'annotations/2026-11-15-completed-next12-browser-export.json',
        'batch':HERE/'next_review_batch_12_2026-11-14.json',
        'inventory':HERE/'opening_pass_feasibility.json',
        'frozen_model':HERE/'opening_classifier_pilot.json',
        'definition':HERE/'centering_definition.json',
        'possessions':HERE.parent/'oline_possessions/possessions.csv',
        'throws':HERE.parent/'oline_possessions/throws.csv',
        'model_implementation':HERE/'opening_classifier_pilot.py',
        'calculation':Path(__file__)}
    inputs = {k:{'path':str(v.relative_to(ROOT)), 'sha256':sha(v)} for k,v in paths.items()}
    plan=json.loads(paths['plan'].read_text())
    export=json.loads(paths['export'].read_text())
    batch=json.loads(paths['batch'].read_text())
    inventory=json.loads(paths['inventory'].read_text())
    old=json.loads(paths['frozen_model'].read_text())
    definition=json.loads(paths['definition'].read_text())
    assert FEATURES==plan['features'] and PENALTY==1.0
    assert plan['definitionVersion']==definition['version']
    for k in ['possessions','throws']:
        assert inputs[k]['sha256']==inventory['inputs'][k]['sha256']
    inv={r['possession_id']:r for r in inventory['rows']}
    reviews=export['reviews']; assert len(reviews)==len({r['possessionId'] for r in reviews})==177
    current={r['possessionId']:r for r in reviews}
    clips=batch['clips']; assert len(clips)==12
    rows=[]
    for clip in clips:
        r=current[clip['possessionId']]; f=inv[r['possessionId']]
        assert r['reviewRound']==plan['batchId'] and r['definitionVersion']==definition['version']
        assert r['decision'] in ['setup1','attack1']
        assert r.get('currentReviewExposesSuggestion') is False
        assert not f['coordinate_hold'] and not f['label_alignment_hold']
        assert f['first_attempt_original_line'] and f['first_attempt_event_type']==18
        assert not r.get('endOfQuarterAttempt',False)
        assert r['possessionId'] not in old['model']['full_fit']['training_ids']
        rows.append({**{k:f[k] for k in FEATURES},
            'possession_id':r['possessionId'], 'caseId':r['caseId'], 'game_id':f['game_id'],
            'team':f['team'], 'human_label':r['decision'], 'reviewContext':r['context'],
            'reviewedOn':r.get('reviewedOn'), 'definitionVersion':r['definitionVersion'],
            'frozenScore':clip['uncalibratedGeometryScore'], 'frozenPrediction':clip['frozenPrediction'],
            'alwaysCenteringPrediction':'setup1',
            'timing':{k:f[k] for k in ['pull_match','pull_event_type','pull_hangtime_ms','timestamp_gap_pull_to_throw1','timestamp_gap_throw1_to_throw2']}})
    assert len({r['game_id'] for r in rows})==12
    assert Counter(r['human_label'] for r in rows)=={'setup1':6,'attack1':6}
    frozen_scores=predict(old['model']['full_fit'],rows)
    for r,s in zip(rows,frozen_scores):
        assert math.isclose(r['frozenScore'],float(s),abs_tol=1e-12)
        assert r['frozenPrediction']==('setup1' if s>=.5 else 'attack1')
    # Only the twelve final-definition labels enter the exploratory refit.
    folds=[]
    for game in sorted({r['game_id'] for r in rows}):
        train=[r for r in rows if r['game_id']!=game]
        test=[r for r in rows if r['game_id']==game]
        model=fit(train)
        assert len(train)==11 and len(test)==1
        assert game not in {r['game_id'] for r in train}
        assert np.allclose(model['training_mean'],np.array([[r[k] for k in FEATURES] for r in train]).mean(0))
        s=float(predict(model,test)[0]);r=test[0]
        r['heldOutScore']=s; r['heldOutPrediction']='setup1' if s>=.5 else 'attack1'
        folds.append({'heldOutGame':game,'testId':r['possession_id'],'fit':model})
    scored={k:score(rows,key) for k,key in [('frozenEarlierModel','frozenPrediction'),
           ('currentDefinitionGameHoldout','heldOutPrediction'),('alwaysCentering','alwaysCenteringPrediction')]}
    archive_path=HERE/'annotations/current_reviewed_decisions.json'
    archive=json.loads(archive_path.read_text())
    backup=HERE/'annotations/reviewed_decisions_before_next12_20261115.json'
    if not backup.exists():
        backup.write_bytes(archive_path.read_bytes())
    prior=json.loads(backup.read_text());prior_by_id={r['possessionId']:r for r in prior['reviews']}
    assert len(prior_by_id)==165
    assert all(current[pid]==r for pid,r in prior_by_id.items())
    legacy_positive=[r for r in reviews if r['decision']=='setup1' and r.get('definitionVersion')!=definition['version']]
    legacy_opening_positive=[r for r in legacy_positive if int(r['possessionId'].split('|')[-1])==1]
    known_scope={'sideline','sideline_inbounds','roller_inbounds','back_endline','brick','offsides_midfield'}
    recheck=[r for r in legacy_opening_positive if r.get('context') not in known_scope]
    training_games={inv[pid]['game_id'] for pid in old['model']['full_fit']['training_ids']}
    gaps=[r['timing']['timestamp_gap_pull_to_throw1'] for r in rows if r['timing']['timestamp_gap_pull_to_throw1'] is not None]
    result={'id':plan['id'],'checkedOn':'2026-11-15','status':'Exploratory check complete; automatic labels not enabled',
        'definitionVersion':definition['version'],'reviewCount':len(reviews),
        'latestBatch':{'n':12,'games':12,'centering':6,'noCentering':6,'allPredictionsHiddenDuringReview':True},
        'labelAudit':{'earlierReviews':165,'currentDefinitionLabels':12,'earlierOpeningPositiveLabels':len(legacy_opening_positive),
            'earlierPositiveScopeExclusions':len(legacy_opening_positive)-len(recheck),
            'earlierPositiveLabelsNeedingDefinitionCheck':len(recheck),
            'recheckCaseIds':[r['caseId'] for r in recheck]},
        'models':scored,'rows':rows,'folds':folds,
        'featurePolicy':{'used':plan['features'],'excluded':plan['forbiddenInputs'],
            'pullTimingAvailable':len(gaps),'firstThrowLoggedBeforePull':sum(x<0 for x in gaps),
            'pullTypeCodesInMatchedRows':sorted({r['timing']['pull_event_type'] for r in rows if r['timing']['pull_event_type'] is not None}),
            'timingDecision':'Logging times do not reliably measure catch-to-release time. Excluded from the model.'},
        'limitations':[
            'Only twelve explicit final-definition labels, one per selected game. This is an exploratory development check, not proof of league accuracy.',
            'Selection emphasized old-model geometry and earlier quarters. The sample is not a random audit.',
            'Earlier-model predictions were frozen before review, but '+str(len(training_games & {r['game_id'] for r in rows}))+' of these games appeared in historical training. They test new possessions, not wholly unseen games.',
            'The current-definition refit holds each game out but uses only eleven labeled examples per fit. No threshold or feature tuning was performed.',
            'Scores are not calibrated probabilities. No high-confidence automation coverage is claimed.',
            'Human restart context is used only for descriptive subgroup checks, never as a database feature.',
            'Earlier labels are preserved; positive labels are not silently upgraded to the final definition.'
        ],
        'methodReferences':['https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data',
                            'https://scikit-learn.org/stable/modules/calibration.html'],
        'automaticResearchDeductions':False,'leagueMetricsChanged':False,'inputs':inputs,
        'validation':{'uniqueReviews':True,'prior165ReviewsUnchanged':True,'all12JoinedOneToOne':True,
            'frozenPredictionsReproduced':True,'heldOutGamesDisjoint':True,'trainingOnlyStandardization':True,
            'noHumanContextInFeatures':True,'noOutcomeFeatures':True,'noNewReviewBatch':True}}
    write(HERE/'database_classifier_check_2026-11-15.json',result)
    archive['updatedOn']='2026-11-15';archive['reviews']=reviews
    archive['inputs']['completedNext12BrowserExport']=inputs['export']
    archive['provenance'].update({r['possessionId']:inputs['export'] for r in reviews})
    archive['definitionReaudit'].update({'currentDefinitionLabels':12,'earlierPositiveLabelsNeedingDefinitionCheck':len(recheck)})
    write(archive_path,archive)
    for k,record in inputs.items():assert sha(paths[k])==record['sha256']
    print(json.dumps({'reviewsSaved':177,'models':scored,'labelAudit':result['labelAudit'],
        'timing':result['featurePolicy'],'errors':[{'caseId':r['caseId'],'actual':r['human_label'],
            'predicted':r['heldOutPrediction']} for r in rows if r['heldOutPrediction']!=r['human_label']]},indent=2))


if __name__=='__main__':
    main()
