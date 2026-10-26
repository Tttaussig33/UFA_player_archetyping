"""Independent reconciliation with the website's existing sequence implementation.

Run: python analysis/huck_setup_checks.py --node /absolute/path/to/node
The original exports and the reviewed src/data.json must be present locally.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import numpy as np
import pandas as pd

import huck_setup_validation as study


def fixture_checks():
    base = dict(GameID='game', throw_sig_id='prior', Thrower='a', Receiver='b',
                ThrowerX='0', ThrowerY='25', ReceiverX='5', ReceiverY='30',
                turnover='0', stall='0', is_home_team='true', game_quarter='1',
                quarter_point='1', possession_num='1', possession_throw='1', global_event_seq='10')
    current = dict(base, throw_sig_id='current', Thrower='b', Receiver='c',
                   possession_throw='2', global_event_seq='12', ThrowerX='5', ThrowerY='30',
                   ReceiverX='5', ReceiverY='90')
    def output(rows):
        return study.link_incoming(pd.DataFrame(rows)).set_index('throw_sig_id').loc['current']
    checks = 0
    assert output([current, base]).incoming == 'lateral'; checks += 1  # Exact 45° boundary.
    assert output([dict(base, ReceiverY='31'), current]).incoming == 'forward'; checks += 1
    assert output([dict(base, ReceiverY='19'), current]).incoming == 'backward'; checks += 1
    for field, value in [('GameID','other'), ('is_home_team','false'), ('game_quarter','2'),
                         ('quarter_point','2'), ('possession_num','2'), ('possession_throw','3'),
                         ('possession_throw',''), ('global_event_seq','10'), ('global_event_seq','')]:
        assert not output([base, dict(current, **{field: value})]).linkVerified, field
        checks += 1
    for changed in [dict(base, turnover='1'), dict(base, stall='1'), dict(base, Receiver='other'),
                    dict(base, Receiver=''), dict(base, global_event_seq='13')]:
        assert not output([changed, current]).linkVerified; checks += 1
    assert not output([base, dict(base, throw_sig_id='duplicate'), current]).linkVerified; checks += 1
    assert not output([base, current, dict(current, throw_sig_id='dup-current')]).linkVerified; checks += 1
    assert not output([base, current, dict(current, throw_sig_id='dup-seq', possession_throw='3')]).linkVerified; checks += 1
    for changed in [dict(base, ReceiverX='0', ReceiverY='25'), dict(base, ReceiverX='')]:
        answer = output([changed, current]); assert answer.linkVerified and answer.incoming == 'unclassified'; checks += 1
    # The target outcome and its endpoint cannot leak into this pass's predictors.
    one = output([base, current])
    two = output([base, dict(current, Receiver='', ReceiverX='-20', ReceiverY='31', turnover='1')])
    assert one[['incoming','incomingDistance','catchZone']].equals(two[['incoming','incomingDistance','catchZone']]); checks += 1
    # A prior pass from outside the modeled release window must remain available.
    assert output([dict(base, ThrowerY='10'), current]).incoming == 'forward'; checks += 1
    return checks


def check(node='node', loaded=None):
    fixtures = fixture_checks()
    d, names, quality, hashes, linked = loaded if loaded is not None else study.load_data()
    regular_2026 = d[d.season.eq(2026)]
    expected = [{'id': r.game + ':' + r.throwID,
                 'prior': (r.game + ':' + r.prior_throw_sig_id) if r.linkVerified else None,
                 'direction': r.incoming} for r in regular_2026.itertuples()]
    module_uri = (study.ROOT / 'src/content/dashboard/deep-thrower-model.js').as_uri()
    script = '''import fs from 'node:fs';
import {precedingPasses, priorPassDirection} from MODULE_URI;
const app=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
const expected=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const events=app.queries.events.rows.filter(e=>e.phase==='Regular season');
const byID=new Map(events.map(e=>[e.id,e]));
const links=precedingPasses(events);
let matched=0, verified=0;
for(const row of expected){
 if(!byID.has(row.id))throw new Error('Missing app event: '+row.id);
 const prior=links.get(row.id);
 if((prior?.id??null)!==row.prior)throw new Error('Prior identity mismatch: '+row.id);
 if(priorPassDirection(prior)!==row.direction)throw new Error('Direction mismatch: '+row.id);
 matched++;if(prior)verified++;
}
console.log(JSON.stringify({matchedEvents:matched,verifiedLinks:verified}));
'''.replace('MODULE_URI', json.dumps(module_uri))
    executable = shutil.which(node)
    if executable is None:
        raise RuntimeError('Node is required for the independent website comparison; supply --node.')
    with tempfile.TemporaryDirectory(prefix='ufa-setup-check-') as directory:
        path = Path(directory) / 'expected.json'; path.write_text(json.dumps(expected))
        response = subprocess.run([executable, '--input-type=module', '-e', script,
                                   str(study.ROOT / 'src/data.json'), str(path)],
                                  check=True, capture_output=True, text=True)
        independent = json.loads(response.stdout)
    result_path = study.HERE / 'huck_setup_validation.json'
    result = json.loads(result_path.read_text())
    assert hashes == result['source']['sha256']
    for fold in result['studies']:
        y = fold['testSeason']; f = d[d.ty.between(20, 60, inclusive='left')]
        train, test = f[f.season.lt(y)], f[f.season.eq(y)]
        counts = train.groupby('player').huck.sum()
        test = test[test.player.isin(counts[counts.ge(40)].index)]
        assert (len(test), int(test.huck.sum()), test.player.nunique()) == (fold['testPasses'], fold['testHucks'], fold['testPlayers'])
        assert sum(r['passes'] for r in fold['incomingRates']) == len(test)
        assert sum(r['hucks'] for r in fold['incomingRates']) == int(test.huck.sum())
        for name, comparison in fold['comparisons'].items():
            a,b = fold['models'][comparison['base']],fold['models'][comparison['extended']]
            assert abs(a['brier']-b['brier']-comparison['brierReduction']) < 1e-12
            assert abs(100*(a['brier']-b['brier'])/a['brier']-comparison['relativeErrorReductionPct']) < 1e-9
        for m in fold['models'].values():
            assert np.isfinite(m['brier']) and 0 <= m['brier'] <= 1
            assert sum(r['passes'] for r in m['calibration']) == len(test)
            assert sum(r['hucks'] for r in m['calibration']) == int(test.huck.sum())
    assert result['baselineReconciliation']['brierDifferenceFromPriorStudy'] == 0
    checked = {'boundaryAndLeakageFixtures': fixtures, 'website2026Reconciliation': independent,
               'temporalFoldsReconciled': len(result['studies']), 'csvHashesMatched': True,
               'priorBaselineMatchedExactly': True}
    print(json.dumps(checked, indent=2))
    return checked


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--node', default='node')
    check(parser.parse_args().node)
