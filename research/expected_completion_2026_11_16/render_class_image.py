"""Export the reviewed team comparison as a static presentation figure.

The interactive canvas and webpage are inputs to the preservation check only.
"""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUT = ROOT / 'figures'
OUT.mkdir(exist_ok=True)
WEB = REPO / 'research/previews/html/UFA-expected-completion-by-possession.ufa.html'
web_hash = hashlib.sha256(WEB.read_bytes()).hexdigest()
data = json.loads((ROOT / 'results.json').read_text())
inference = json.loads((ROOT / 'team_significance.json').read_text())
for name, digest in inference['inputs'].items():
    assert hashlib.sha256((REPO / name).read_bytes()).hexdigest() == digest, name
oline_source_path = ROOT / 'shownspace-oline-aec-source.json'
oline_source = json.loads(oline_source_path.read_text())
oline_rows = oline_source['rows']
oline_by_team = {r['team']: r for r in oline_rows}
assert len(oline_rows) == len(oline_by_team) == 22
assert oline_source['filters'] == {'season': 2026, 'division': 'ALL', 'unit': 'O-LINE', 'view': 'Total'}
assert set(oline_by_team) == {r['team'] for r in data['scopes']['long_field']['teams']}
rows = sorted(
    [dict(r, oline_aec=oline_by_team[r['team']]['oline_aec']) for r in data['scopes']['long_field']['teams']],
    key=lambda r: -r['oline_aec'],
)
assert [r['team'] for r in rows] == [r['team'] for r in sorted(oline_rows, key=lambda r: r['rank'])]
for row in rows:
    row['inference'] = inference['scopes']['long_field']['teams'][row['team']]
    assert abs(row['change_pp'] - row['inference']['difference_pp']) < 1e-10
assert len(rows) == 22
assert sum(r['inference']['nominal_excludes_zero'] for r in rows) == 5
assert all(not r['inference']['bonferroni_excludes_zero'] for r in rows)

INK, MUTED, BLUE, GRAY, GRID = '#172B3A', '#52616F', '#1267B1', '#7D8790', '#E5E9ED'
plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':16,
                     'svg.fonttype':'none', 'axes.unicode_minus':True})

def render(subset, stem, title, *, backup=False):
    fig = plt.figure(figsize=(20, 16.5 if backup else 11.25), facecolor='white', dpi=200)
    texts=[]
    def text(x,y,s,**kw):
        kw.setdefault('color',INK)
        artist=fig.text(x,y,s,**kw)
        texts.append(artist)
        return artist
    text(.055,.949,title,fontsize=28,weight='bold',va='top')
    bottom, height = (.125,.710) if backup else (.155,.650)
    header_y = .872 if backup else .857
    body_size=18 if backup else 21
    left,right=.355,.865
    ax=fig.add_axes([left,bottom,right-left,height])
    n=len(subset)
    ax.set_xlim(-20,5)
    ax.set_ylim(-.6,n-.4)
    ax.set_yticks([])
    ax.set_xticks([-20,-15,-10,-5,0,5], ['−20','−15','−10','−5','0','+5'])
    ax.tick_params(axis='x',labelsize=16,length=0,pad=12,colors=MUTED)
    for spine in ax.spines.values():spine.set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis='x',color=GRID,lw=.8)
    ax.axvline(0,color=INK,lw=1.4,ls=(0,(4,4)),zorder=2)
    ax.text(0,1.020,'No change',transform=ax.get_xaxis_transform(),ha='center',va='bottom',fontsize=16,color=INK)
    text(.055,header_y,'TEAM',fontsize=16,weight='bold',color=MUTED)
    text(.310,header_y,'O-LINE aEC ↓',fontsize=16,weight='bold',ha='right',color=MUTED)
    text(.945,header_y,'CHANGE',fontsize=16,weight='bold',ha='right',color=MUTED)
    name_value_pairs=[]
    for j,row in enumerate(subset):
        y=n-1-j
        fy=bottom+height*((y+.6)/(n+.2))
        info=row['inference']; low,high=info['ci95_pp']
        blue=info['nominal_excludes_zero']
        assert (high<0) if blue else (low<=0<=high)
        color=BLUE if blue else GRAY
        name=text(.055,fy,row['team_name'],fontsize=body_size,va='center',weight='bold' if blue else 'normal')
        aec=text(.310,fy,f"{row['oline_aec']:.2f}",fontsize=body_size,ha='right',va='center',color=MUTED)
        name_value_pairs.append((name,aec))
        ax.hlines(y,low,high,color=color,lw=2.6,zorder=3)
        ax.vlines([low,high],y-.095,y+.095,color=color,lw=1.4,zorder=3)
        ax.plot(row['change_pp'],y,marker='D' if blue else 'o',ms=7,color=color,zorder=4)
        value=f"{row['change_pp']:+.1f}".replace('-','−')
        text(.945,fy,value,fontsize=body_size,ha='right',va='center',weight='bold' if blue else 'normal',color=INK)
    # Only the title, column headings, and measurement axis remain on the slide.
    # Explanations, provenance, and the unchanged 22-team testing family are in the speaker notes.
    text(.5,.070 if not backup else .065,
         'Change in average expected completion (percentage points)',fontsize=19,ha='center')
    text(.5,.033 if not backup else .038,
         'Second possession − first possession',fontsize=17,ha='center',color=MUTED)
    fig.canvas.draw()
    renderer=fig.canvas.get_renderer()
    W,H=fig.canvas.get_width_height()
    for artist in texts:
        box=artist.get_window_extent(renderer)
        assert box.x0>=0 and box.y0>=0 and box.x1<=W and box.y1<=H, artist.get_text()
    for name,value in name_value_pairs:
        assert name.get_window_extent(renderer).x1+8<value.get_window_extent(renderer).x0,name.get_text()
    paths=[OUT/(stem+'.png'),OUT/(stem+'.svg')]
    fig.savefig(paths[0],dpi=200,facecolor='white')
    fig.savefig(paths[1],facecolor='white')
    plt.close(fig)
    return {'title':title,
            'files':{str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            'dimensions_px':[W,H],'team_order':[r['team'] for r in subset],
            'blue_teams':[r['team'] for r in subset if r['inference']['nominal_excludes_zero']]}

main=render(rows[:10],'UFA-xcp-first-vs-second','Do O-lines attempt harder throws on their second possession?')
backup=render(rows,'UFA-xcp-all-teams','Expected completion: all 22 teams',backup=True)
assert hashlib.sha256(WEB.read_bytes()).hexdigest()==web_hash
receipt={
    'purpose':'Single-column presentation image, with full-league backup; original webpage preserved',
    'scope':'Starts at least 60 yards from goal; exactly first versus second receiving-team possession; original seven; all physical throws',
    'main_selection':'First 10 teams ranked by ShownSpace Pro total O-line aEC, descending; not selected by statistical significance',
    'main':main,'backup':backup,
    'shared_x_axis':[-20,5], 'layout_columns':1,
    'x_axis_title_alignment':'Centered beneath the full figure',
    'individual_status_text_removed':True,'legend_and_selected_explanatory_copy_removed':True,
    'difference_column_label':'Change',
    'difference_values_match_interval_colors':False,
    'testing_family_unchanged':22,'source_data_unchanged':True,
    'source_data_unchanged_scope':'xCP calculations, intervals, and original overall team aEC source are preserved; ranking uses the separate verified O-line source.',
    'ranking_source':str(oline_source_path.relative_to(REPO)),
    'ranking_source_sha256':hashlib.sha256(oline_source_path.read_bytes()).hexdigest(),
    'webpage_unchanged_sha256':web_hash,
    'numeric_and_text_bounds_checks_passed':True,
    'speaker_notes':'research/expected_completion_2026_11_16/figures/presentation-notes.txt',
}
(OUT/'image-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'main':main,'backup':backup},indent=2))
