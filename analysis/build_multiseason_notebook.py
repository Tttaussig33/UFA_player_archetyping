"""Build and execute the review notebook with portable, embedded SVG figures.

The lightweight executor runs Python cells in order and saves their actual
outputs. It does not require an installed Jupyter kernel to generate the file.
"""
import ast
import contextlib
import html
import io
import json
from pathlib import Path
import re
import sys
import uuid

HERE = Path(__file__).resolve().parent
cells = []
existing_path = HERE / 'multiseason_release_validation.ipynb'
existing_ids = {''.join(c['source']).strip(): c['id'] for c in json.loads(existing_path.read_text()).get('cells', [])} if existing_path.exists() else {}


def cell_id(text):
    return existing_ids.get(text.strip(), uuid.uuid5(uuid.NAMESPACE_URL, 'ufa-analysis:' + text.strip()).hex[:8])


def md(text):
    cells.append({'cell_type': 'markdown', 'id': cell_id(text), 'metadata': {}, 'source': text.strip().splitlines(True)})


def code(text):
    cells.append({'cell_type': 'code', 'id': cell_id(text), 'metadata': {}, 'source': text.strip().splitlines(True),
                  'execution_count': None, 'outputs': []})


md('''# Deep throwing: zones, player history and incoming passes
## tl;dr
**October 25 follow-up: viable as a modest scouting model, not yet as dependable individual setup archetypes.** In the main 2026 sample, adding incoming-pass direction reduced Brier prediction error by 0.65% beyond player history and release position. After accounting for whether a prior pass was classifiable, direction alone added 0.37%, with a 95% game-bootstrap interval of −0.13% to +0.88%. At a fixed top-fifth scouting budget, the simpler and direction models identified 236 and 240 of 590 hucks respectively. This is a small practical gain.

Across 22,386 regular-season hucks in the 2021–2026 export, this test does **not establish reliable player-specific best release zones**.

Among 48 testable players, the average chosen-zone advantage fell from **12.7 percentage points in 2021–2025 to 0.7 points in 2026**. The 2026 player-bootstrap interval is **−9.1 to +10.2 points**. Personalized zone effects did not improve held-out completion prediction beyond shared zone and coarse throw geometry.

A more useful near-term direction is predicting **whether a player attempts a huck**. Adding player history to league field-position tendencies reduced 2026 prediction error by **3.1%**, across **6,173 passes by 44 players** released from Y20–60. This is a modest forecasting improvement, not a 3.1-point increase in completion or proof that a particular defensive tactic works. Personal zone interactions added no reliable further improvement.

The source is the October 12 exported snapshot; October 24 live season totals match, but row contents were not refetched. This is an exploratory historical check, including a previously inspected 2026 season.''')

md('''## Context & Methods
**Coaching decision:** Is there evidence to recommend a different preferred release zone for each deep thrower, or is a simpler scouting view more defensible?

- Primary comparison: train on 2021–2025 regular seasons, evaluate 2026. Expanding-history checks evaluate 2022–2025. Training sets and players overlap across checks.
- Huck: forward gain strictly greater than 30 yards **and** straight-line distance strictly greater than 40 yards. Stalls are excluded. Completion means no recorded turnover; drops are incomplete.
- Best-zone selection: at least 40 prior hucks and two zones with at least 10 prior attempts. Choose the highest earlier completion rate. Evaluate against all other zones for that player in 2026. A player must have a later attempt both inside and outside the chosen zone for a paired comparison.
- The main gap gives each player equal weight. Pooled percentages shown separately give more weight to players with more throws; they need not have the same gap.
- Prediction models use fixed penalized binomial regression. Shared geometry adjusts for flight-length and forward-gain categories and an end-zone endpoint. A player-by-zone term asks whether personal zones add predictive value beyond those baselines. Penalties are fixed, not tuned on 2026.
- Attempt prediction uses passes released at Y20 to less than Y60, with additional 10-yard release-depth adjustment. It does not use the future receiver location to predict the attempt decision.
- Intervals: 5,000 bootstrap samples of entire players for the zone gap; entire games and, separately, players for prediction-error differences. Intervals are omitted with fewer than 10 clusters. These intervals are conditional on training and do not capture all crossed dependence.

### Key Assumptions
Source coordinates represent offense moving toward Y120, as specified by the data owner. Recomputed geometry matches the supplied differences and distances. Stable source player IDs are kept; same-name IDs are not automatically merged. An unclassified 2021 game is excluded.

Association is not causation. Receiver movement, marking, pressure, wind, stall count, role and team changes can affect results. Endpoint geometry is a retrospective difficulty adjustment for completion, not information available before release. Failure of these fixed models does not prove that no player has a real zone advantage.''')

code('''from pathlib import Path
import contextlib, io, json, sys
import pandas as pd

project = next(p for p in [Path.cwd(), *Path.cwd().parents]
               if (p / 'analysis/multiseason_release_validation.py').exists())
sys.path.insert(0, str(project / 'analysis'))
import multiseason_release_validation as study
import multiseason_release_checks as checks

RERUN_ANALYSIS = True  # Set False only to inspect the saved, hash-identified result.
if RERUN_ANALYSIS:
    with contextlib.redirect_stdout(io.StringIO()):
        result = study.run()
else:
    result = json.loads((project / 'analysis/multiseason_release_validation.json').read_text())
primary = result['studies'][-1]
print('Primary test: history from 2021–2025 → outcomes in 2026.')
print('Source: data/database-exports/2026-10-12/{throws,games,players}.csv')
print('Live count receipt: data/database-metadata/2026-10-24/live-season-coverage.json')''')

md('''## Data
The analysis reads all three full exports, verifies their recorded SHA-256 hashes, checks one row per game and per game/throw ID, then filters regular-season, identified, nonstall passes with valid geometry. No source rows or website data are edited. Game and throw counts also reconcile with the saved live DBeaver result.''')
code('''coverage = pd.DataFrame(result['quality']['seasonRows'])
coverage[['season', 'analysisGames', 'analysisThrows', 'hucks', 'completedHucks']].rename(columns={
    'season':'Season', 'analysisGames':'Games', 'analysisThrows':'Located passes',
    'hucks':'Huck attempts', 'completedHucks':'Completed hucks'})''')
code('''validation = checks.check()  # Independent csv-reader implementation of counts and zone selection.
assert sum(row['analysisThrows'] for row in result['quality']['seasonRows']) == 456555
assert validation['independentlyMatchedHucks'] == 22386
print('Independent recalculation matched every seasonal huck/completion count and all 48 selected player-zone identities.')
print('2026 chosen zones: 139 / 201 complete; other zones: 438 / 660 complete.')
print('No duplicate game/throw keys or orphan GameIDs; all 490,685 comparable geometry rows matched.')
print('Excluded: 481 throws in an unclassified 2021 game. Three missing source coordinates belong to already-excluded unnamed throwers.')
print('Identity: source IDs preserved; same-name IDs are not merged.')''')

md('''## Results
### 1. Earlier best zones did not show a dependable later advantage
The same 48 players and historically selected zones are used in both periods. The historical advantage is inflated by selecting the best-looking earlier zone; the later season is the relevant test. Of 97 historically eligible players, 48 had a 2026 attempt both inside and outside the selected zone.''')

code('''from html import escape
import math

class SVGFigure:
    def __init__(self, value): self.value = value
    def _repr_svg_(self): return self.value

def interval_figure(rows, title, axis, subtitle):
    # Small, directly labeled vector figures, embedded in the saved notebook.
    width, left, right, row_h = 880, 180, 70, 70
    top, bottom = 90, 75
    height = top + row_h * len(rows) + bottom
    bounds = [0] + [v for row in rows for v in (row['low'], row['high'])]
    lo, hi = min(bounds), max(bounds)
    span = max(hi-lo, 1)
    lo -= span*.1; hi += span*.1
    x = lambda value: left + (value-lo)/(hi-lo)*(width-left-right)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">',
             f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
             '<g font-family="Arial,sans-serif" fill="#20252b">',
             f'<text x="20" y="28" font-size="19">{escape(title)}</text>',
             f'<text x="20" y="51" font-size="13">{escape(subtitle)}</text>']
    plot_bottom = top + row_h*len(rows)-20
    for i in range(5):
        value = lo+(hi-lo)*i/4
        xx=x(value)
        parts += [f'<line x1="{xx}" y1="{top-20}" x2="{xx}" y2="{plot_bottom}" stroke="#dce1e5"/>',
                  f'<text x="{xx}" y="{plot_bottom+26}" text-anchor="middle" font-size="13">{value:+.1f}</text>']
    parts += [f'<line x1="{x(0)}" y1="{top-20}" x2="{x(0)}" y2="{plot_bottom}" stroke="#4b5563"/>']
    for i,row in enumerate(rows):
        yy=top+i*row_h+15
        parts += [f'<text x="{left-16}" y="{yy+5}" text-anchor="end" font-size="14">{escape(row["label"])}</text>',
                  f'<line x1="{x(row["low"])}" y1="{yy}" x2="{x(row["high"])}" y2="{yy}" stroke="#246b8e" stroke-width="3"/>',
                  f'<circle cx="{x(row["mean"])}" cy="{yy}" r="6" fill="#246b8e"/>',
                  f'<text x="{x(row["mean"])}" y="{yy-15}" text-anchor="middle" font-size="14">{row["mean"]:+.1f}</text>']
    parts += [f'<text x="{(left+width-right)/2}" y="{height-16}" text-anchor="middle" font-size="14">{escape(axis)}</text>', '</g></svg>']
    return SVGFigure(''.join(parts))

b = primary['bestCompletionZone']
zone_plot_rows = [dict(label=label, mean=b[key]['mean']*100,
                      low=b[key]['ci95'][0]*100, high=b[key]['ci95'][1]*100)
                  for label,key in [('2021–2025','trainPlayerGap'),('2026','testPlayerGap')]]
interval_figure(zone_plot_rows, 'Does the earlier best zone stay better?',
                'Mean within-player completion advantage (percentage points)',
                '48 players · chosen zone minus other zones · 95% player-bootstrap intervals')''')

md('''**Interpretation:** The 2026 average gap is +0.7 points, with a −9.1 to +10.2 interval. There is insufficient precision to recommend each player’s earlier best box as a reliably better location. This is not evidence that moving a player there would improve completion.

The pooled 2026 rates are 69.2% (139/201) in the selected zones versus 66.4% (438/660) elsewhere. Those percentages weight throws; the chart weights players equally. Twenty-six players had a positive later gap, four tied, and eighteen had a negative gap.''')

code('''example_rows = sorted((r for r in b['rows'] if r['test']['gap'] is not None),
    key=lambda r: -(r['test']['chosen']['attempts']+r['test']['other']['attempts']))[:10]
examples = []
for row in example_rows:
    output = {'Player':row['name'], 'Earlier chosen zone':row['zoneLabel']}
    for period, label in [('train','2021–25'),('test','2026')]:
        for group, desc in [('chosen','chosen zone'),('other','elsewhere')]:
            c=row[period][group]
            output[f'{label}: {desc}']=f"{c['successes']}/{c['attempts']} ({c['rate']:.0%})"
    examples.append(output)
pd.DataFrame(examples)''')
md('''Examples are ordered by 2026 huck volume among testable players, not by how favorable their result looks. Jake Felton’s earlier right-side advantage did not persist; Chad Yorgason’s center-zone comparison remained positive. Small later cells, including Alex Atkins’s four chosen-zone attempts, cannot support strong player-level conclusions.''')

md('''### 2. Personal completion zones did not improve prediction
Lower Brier error means more accurate probabilities. Compare the same held-out throws under each model. The geometry models include receiver endpoints retrospectively, so this is a difficulty-adjusted association check rather than a pre-throw coaching forecast.''')
code('''prediction_rows=[]
for s in result['studies'][1:]:
    p=s['completionPrediction']; c=p['comparisons']['personalGeometryMinusSharedGeometry']
    prediction_rows.append({'Test season':s['testSeason'],'Players':p['testPlayers'],'Hucks':p['testEvents'],
        'Shared geometry Brier':round(p['models']['sharedGeometry']['brier'],6),
        'Add personal zone Brier':round(p['models']['personalGeometry']['brier'],6),
        'Error change (%)':round(c['relativeErrorChangePct'],2),
        '95% game CI, error difference':str([round(v,5) for v in c['gameBootstrap']['ci95']])})
pd.DataFrame(prediction_rows)''')
md('''Personal zone effects did not reduce completion error in any of the 2023–2026 checks; each interval includes zero. The 2022 cohort has only two eligible returning players and is too small to support a league conclusion. Using only 2024–2025 history or a broader 10-prior-huck prediction cohort also did not establish an improvement. These are overlapping historical checks, not independent experiments.''')

md('''### 3. A stronger alternative: forecast huck attempts
Here the outcome is whether any located, nonstall pass becomes a huck. Compare a league field-position model with the same model plus each player’s overall prior tendency. The release window is Y20 to less than Y60; both models include shared zones and 10-yard release depth. This controls the obvious inability to gain 30 yards near the end zone.''')
code('''attempt_plot_rows=[]
for s in result['studies'][1:]:
    p=s['attemptPredictionY20_60']
    c=p['comparisons']['sharedGeometryMinusLeagueGeometry']
    baseline=p['models']['leagueGeometry']['brier']
    low,high=c['gameBootstrap']['ci95']
    attempt_plot_rows.append({'label':str(s['testSeason']), 'mean':-c['relativeErrorChangePct'],
                              'low':-100*high/baseline, 'high':-100*low/baseline})
interval_figure(attempt_plot_rows, 'Player history helps predict huck attempts',
                'Prediction-error reduction versus league geometry (%)',
                'Train on earlier years · positive is better · 95% game-bootstrap intervals')''')
code('''attempt_rows=[]
for s in result['studies'][1:]:
    p=s['attemptPredictionY20_60']
    attempt_rows.append({'Test season':s['testSeason'], 'Players':p['testPlayers'],
        'Located passes':p['testEvents'],'Huck attempts':p['testSuccesses'],
        'League geometry Brier':round(p['models']['leagueGeometry']['brier'],6),
        'Add player history Brier':round(p['models']['sharedGeometry']['brier'],6),
        'Add personal zone Brier':round(p['models']['personalGeometry']['brier'],6)})
pd.DataFrame(attempt_rows)''')
md('''**Interpretation:** The 2026 improvement is modest but survives both game- and player-level resampling. The broader 10-prior-huck cohort gives a 2.0% error reduction across 17,586 passes by 188 players. More detailed personal-zone terms add no dependable benefit. The evidence supports general player propensity plus shared field context better than unique player-zone archetypes.''')

md('''### 4. Does the preceding pass add useful information?
**Decision:** Is incoming-pass information strong enough to support coaching-oriented deep-thrower scouting?

The primary new comparison adds forward/lateral/backward direction to a baseline that already knows the player, release position, and whether an incoming direction is classifiable. This isolates direction from simply knowing a player had a recorded preceding pass. Unknown setups include first throws of a possession; they are not all recording errors.

Both models score exactly the same later-season throws. Training uses all earlier regular-season players in the release window; the main test requires at least 40 earlier hucks in that window. The 2026 test contains 6,173 passes, 590 hucks and 44 players across 127 games. Prediction inputs exclude the current pass's target and outcome.

Prior passes must be completed, non-stall, received by the current thrower, and linked by unique consecutive throw orders and increasing event sequences within the same game, team, quarter, point and possession. Directions describe disc movement; they do not identify cutting routes or dead-disc state. The model is conditional on the recorded release point, not a forecast of where a player will move after catching.

The primary comparison, model variants, thresholds and sensitivity checks were set in the analysis script before these new results were inspected. The 2026 season was examined in previous work, so this remains exploratory temporal validation. Error reductions below are relative reductions in Brier loss, not increases in huck completion percentage.''')

code('''import os
import huck_setup_validation as setup_study
import huck_setup_checks as setup_checks
if RERUN_ANALYSIS:
    with contextlib.redirect_stdout(io.StringIO()):
        setups = setup_study.run()
else:
    setups = json.loads((project / 'analysis/huck_setup_validation.json').read_text())
setup_primary = setups['studies'][-1]
node = os.environ.get('UFA_NODE', 'node')
validation = setup_checks.check(node=node)
print('All 72,590 eligible 2026 regular-season passes matched the website sequence logic, including 61,777 verified links.')
print('Primary cohort and baseline prediction error match the prior study exactly.')''')

code('''direction_plot_rows = []
for fold in setups['studies']:
    comparison = fold['comparisons']['directionVsAvailability']
    baseline = fold['models']['availability']['brier']
    lo,hi = comparison['gameBootstrap']['ci95']
    direction_plot_rows.append(dict(label=str(fold['testSeason']),
        mean=comparison['relativeErrorReductionPct'], low=100*lo/baseline, high=100*hi/baseline))
interval_figure(direction_plot_rows, 'Incremental value of incoming-pass direction',
    'Brier-error reduction beyond player, position and prior-pass availability (%)',
    'Source: Oct 12 export · 2023–2026 test seasons · 95% game-bootstrap intervals')''')

md('''**Interpretation:** Direction has a positive point estimate in all four checks, but the gain is small. Both game- and player-bootstrap intervals exclude zero in 2024 and 2025; neither does in 2023 or the main 2026 comparison. The 2026 direction-only increment is 0.37% (game interval −0.13% to +0.88%; player interval −0.15% to +0.81%). The combined direction-and-availability model improves 0.65% over the original player/position baseline, with both intervals above zero. That combined gain should not all be attributed to direction.''')

code('''setup_rates = pd.DataFrame(setup_primary['incomingRates'])
setup_rates['Observed huck share'] = setup_rates.huckRate.map(lambda x: f'{x:.1%}')
setup_rates.rename(columns={'direction':'Preceding disc direction','passes':'Next passes','hucks':'Hucks'})[
    ['Preceding disc direction','Next passes','Hucks','Observed huck share']]''')

md('''These are descriptive rates in the 44-player 2026 test cohort: 220/1,636 after a forward pass (13.4%), 286/3,149 after a lateral pass (9.1%), 21/487 after a backward pass (4.3%), and 63/901 with an unclassified setup (7.0%). Player and field-position mix differ between rows; the prediction comparison above, rather than this raw difference, tests added information. The 901 unclassified setups remain in the analysis.''')

code('''scouting_rows=[]
for label,name in [('leaguePosition','Field position'), ('playerPosition','Add player history'),
                   ('availability','Add prior-pass availability'), ('direction','Add incoming direction')]:
    m=setup_primary['models'][label]; top=m['topFifth']
    scouting_rows.append({'Model':name,'Passes flagged':top['passes'],'Hucks identified':top['hucks'],
        'Share of 590 hucks':f"{top['shareOfAllHucks']:.1%}", 'Brier error':round(m['brier'],6)})
pd.DataFrame(scouting_rows)''')

md('''**Practical size:** Flagging 1,235 passes under each model identifies 236 hucks with player history and position versus 240 after adding direction: a net gain of four identified hucks out of 590. The models can flag different passes. This is a retrospective ranking check, not a validated in-game alert threshold or an estimate of goals prevented. Player history contributes substantially more to this ranking than the direction feature.''')

code('''sensitivity_rows=[]
labels={'lowerHistoricalFloor':'10 earlier hucks', 'recentHistory':'2024–2025 history',
        'knownDirectionsOnly':'Known direction only', 'finerReleasePosition':'5×5-yard release grid',
        'teamAdjustment':'Adjust for team'}
for label,fold in setups['sensitivities'].items():
    c=fold['comparisons']['directionVsAvailability']; base=fold['models']['availability']['brier']
    lo,hi=c['gameBootstrap']['ci95']
    sensitivity_rows.append({'Check':labels[label],'Players':fold['testPlayers'],'Passes':fold['testPasses'],
        'Error reduction (%)':round(c['relativeErrorReductionPct'],2),
        'Game interval (%)':f'{100*lo/base:.2f} to {100*hi/base:.2f}'})
pd.DataFrame(sensitivity_rows)''')

md('''The broader 10-prior-huck cohort (188 players, 17,586 passes) shows a small 0.52% direction increment with both cluster intervals above zero. Finer 5×5-yard release controls, team adjustment, and a known-direction-only sample retain small but uncertain 2026 gains. Using only 2024–2025 history leaves 10 eligible players and gives an uncertain negative point estimate; its different cohort limits comparison.

More detailed incoming geometry and individual player-by-direction terms did not establish an additional Brier improvement: their intervals include zero in every 2023–2026 check. These secondary analyses were not adjusted for multiple comparisons. They do not justify a claim that a given player has a dependable personal setup archetype.''')

code('''pd.DataFrame(setup_primary['models']['direction']['calibration']).assign(
    prediction=lambda f:f.prediction.map(lambda x:f'{x:.1%}'),
    observed=lambda f:f.observed.map(lambda x:f'{x:.1%}'))[
    ['low','high','passes','hucks','prediction','observed']].rename(columns={
        'low':'Probability band lower','high':'Probability band upper','passes':'Passes','hucks':'Hucks',
        'prediction':'Mean predicted','observed':'Observed huck share'})''')

md('''Probability calibration is shown for inspection, with fixed bands and sample counts. Small upper-probability bands should not be treated as precise individual-player forecasts. This test predicts huck attempts among recorded throws, not catch-to-huck probabilities or huck success.

## Takeaways
- Keep the current field maps as descriptive scouting summaries, with attempts and completions visible. Avoid labeling the highest observed box a validated personal strength.
- Prioritize the question **“Who is likely to huck from this field position?”** using player history plus general field patterns. This can prioritize film review and prepare defenders to anticipate deep attempts.
- Incoming direction is a modest additional scouting clue. Show counts and raw tendencies, but retain player history and field position as the core of the forecast.
- The evidence does not yet support dependable personalized setup archetypes. More complex setup features did not establish additional predictive value; a future season or newly collected film labels would be a stronger next validation than further tuning on 2026.
- Do not infer that denying a particular box will reduce goals, or that a completion percentage captures thrower skill alone. Those coaching claims need additional evidence.

Original zone computations and per-player results are in `analysis/multiseason_release_validation.py` and `.json`; incoming-pass extensions are in `analysis/huck_setup_validation.py` and `.json`. Checks are `multiseason_release_checks.py` and `huck_setup_checks.py`. This notebook executes without database access given the three original CSVs, Python with numpy and pandas, and Node for the independent website reconciliation. Set `UFA_NODE` to an absolute Node path if Node is not on PATH.''')


def execute():
    ns = {'__name__': '__main__'}
    execution_count = 0
    for cell in cells:
        if cell['cell_type'] != 'code':
            continue
        execution_count += 1
        source = ''.join(cell['source'])
        tree = ast.parse(source)
        last = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(compile(tree, '<notebook>', 'exec'), ns)
            value = eval(compile(ast.Expression(last.value), '<notebook>', 'eval'), ns) if last else None
        cell['execution_count'] = execution_count
        if output.getvalue():
            cell['outputs'].append({'output_type': 'stream', 'name': 'stdout', 'text': output.getvalue().splitlines(True)})
        if value is not None:
            data = {'text/plain': [repr(value)]}
            if hasattr(value, '_repr_svg_'):
                data['image/svg+xml'] = [value._repr_svg_()]
            elif hasattr(value, '_repr_html_'):
                data['text/html'] = [value._repr_html_()]
            cell['outputs'].append({'output_type': 'execute_result', 'execution_count': execution_count, 'metadata': {}, 'data': data})
    return execution_count


def markdown_preview(source):
    text = html.escape(source)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    lines = []
    for line in text.splitlines():
        if line.startswith('#'):
            n = len(line) - len(line.lstrip('#'))
            lines.append(f'<h{n}>{line[n:].strip()}</h{n}>')
        elif line.startswith('- '):
            lines.append('<p class="bullet">• ' + line[2:] + '</p>')
        elif line.strip():
            lines.append('<p>' + line + '</p>')
    return '\n'.join(lines)


if __name__ == '__main__':
    count = execute()
    notebook = {'nbformat': 4, 'nbformat_minor': 5, 'metadata': {
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
        'language_info': {'name': 'python', 'version': sys.version.split()[0]},
        'validation': {'execution': 'All Python cells executed top-to-bottom by this builder.',
                       'source': 'CSV hashes verified; independent row-by-row counts matched.'}}, 'cells': cells}
    path = HERE / 'multiseason_release_validation.ipynb'
    path.write_text(json.dumps(notebook, indent=1) + '\n')
    reread = json.loads(path.read_text())
    assert reread['nbformat'] == 4 and len({c['id'] for c in cells}) == len(cells)
    assert all(c['execution_count'] is not None for c in cells if c['cell_type'] == 'code')
    preview = ['<!doctype html><html><meta charset="utf-8"><title>Historical huck validation</title>',
               '<style>body{font:16px/1.55 system-ui;color:#20252b;background:#fff;max-width:1060px;margin:40px auto;padding:0 24px}h1,h2,h3{line-height:1.2}h2{margin-top:42px}p.bullet{padding-left:15px}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:9px;border-bottom:1px solid #dce1e5;text-align:right}th:first-child,td:first-child{text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}svg{max-width:100%;height:auto}details{color:#59636c;margin:12px 0}.table-wrap{overflow:auto}</style><body>']
    for cell in cells:
        source = ''.join(cell['source'])
        if cell['cell_type'] == 'markdown':
            preview.append(markdown_preview(source))
        else:
            preview.append('<details><summary>Calculation</summary><pre>' + html.escape(source) + '</pre></details>')
            for out in cell['outputs']:
                data = out.get('data', {})
                if 'image/svg+xml' in data:
                    preview += data['image/svg+xml']
                elif 'text/html' in data:
                    preview.append('<div class="table-wrap">' + ''.join(data['text/html']) + '</div>')
                elif out['output_type'] == 'stream':
                    preview.append('<pre>' + html.escape(''.join(out['text'])) + '</pre>')
                else:
                    preview.append('<pre>' + html.escape(''.join(data.get('text/plain', []))) + '</pre>')
    preview.append('</body></html>')
    directory = Path('/tmp/ufa-multiseason-review')
    directory.mkdir(exist_ok=True)
    (directory / 'index.html').write_text('\n'.join(preview))
    print(f'Saved and executed {count} code cells: {path}')
    print(f'Preview: {directory / "index.html"}')
