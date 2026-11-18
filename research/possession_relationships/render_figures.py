"""Project figures: huck-share/scoring and throw-count/scoring quadrant maps."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.transforms import Bbox

ROOT=Path(__file__).resolve().parent
d=json.loads((ROOT/'results.json').read_text())
data=d['scopes']['long_field']['all']
OUT=ROOT/'figures'
OUT.mkdir(exist_ok=True)
ABBR=dict(alleycats='IND',apex='COL',bighorns='LV',breeze='DC',cascades='SEA',empire='NY',flyers='CAR',glory='BOS',growlers='SD',havoc='HOU',hustle='ATL',phoenix='PHI',radicals='MAD',royal='MTL',rush='TOR',shred='SLC',sol='ATX',spiders='OAK',steel='ORE',thunderbirds='PIT',union='CHI',windchill='MIN')
EXAMPLES=dict(union='Chicago',flyers='Carolina',windchill='Minnesota',cascades='Seattle')
BLUE='#24679b';INK='#20272d';MUTED='#56616c';GRID='#e0e5e9';GRAY='#8d99a3'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.labelcolor':INK,'text.color':INK,
                     'xtick.color':MUTED,'ytick.color':MUTED,'svg.fonttype':'none','axes.unicode_minus':True})

def labels(fig,ax,rows,xkey,focus,reserved):
    fig.canvas.draw();renderer=fig.canvas.get_renderer()
    points=[ax.transData.transform((r['change'][xkey],r['change']['scoring'])) for r in rows]
    point_boxes=[Bbox.from_bounds(x-7,y-7,14,14) for x,y in points]
    used=[a.get_window_extent(renderer).expanded(1.03,1.05) for a in reserved]
    for r in sorted(rows,key=lambda r:-r['change']['scoring']):
        if r['team'] not in EXAMPLES:
            continue
        x,y=r['change'][xkey],r['change']['scoring'];best=None
        candidates=[(9,9),(9,-12),(-9,10),(-9,-14),(3,22),(2,-25),(22,0),(-22,0),(27,15),(-27,-17),(20,28),(-20,-30),(38,-5),(-38,7),(0,38),(0,-40),(38,30),(-38,-30),(55,45),(-55,-45),(20,60),(-20,-60)]
        for order,(dx,dy) in enumerate(candidates):
            a=ax.annotate(EXAMPLES[r['team']],(x,y),xytext=(dx,dy),textcoords='offset points',
                          ha='left' if dx>3 else 'right' if dx<-3 else 'center',va='center',fontsize=10,
                          fontweight='bold' if r['team']==focus else 'normal',color=BLUE if r['team']==focus else INK)
            bb=a.get_window_extent(renderer).expanded(1.12,1.30)
            penalty=100*sum(bb.overlaps(b) for b in used)+15*sum(bb.overlaps(b) for b in point_boxes)+order*.2
            if not ax.bbox.contains(bb.x0,bb.y0) or not ax.bbox.contains(bb.x1,bb.y1):penalty+=300
            zero_x,zero_y=ax.transData.transform((0,0))
            if (x<0 and bb.x1>zero_x) or (x>0 and bb.x0<zero_x) or (y<0 and bb.y1>zero_y) or (y>0 and bb.y0<zero_y):penalty+=1000
            a.remove()
            if best is None or penalty<best[0]:best=(penalty,dx,dy,bb)
        _,dx,dy,bb=best;used.append(bb)
        ax.annotate(EXAMPLES[r['team']],(x,y),xytext=(dx,dy),textcoords='offset points',
                    ha='left' if dx>3 else 'right' if dx<-3 else 'center',va='center',fontsize=10,
                    fontweight='bold' if r['team']==focus else 'normal',color=BLUE if r['team']==focus else INK,
                    arrowprops={'arrowstyle':'-','color':GRAY,'lw':.6,'shrinkA':2,'shrinkB':8} if abs(dx)>17 or abs(dy)>21 else None)

for xkey,name,topic,focus in [
    ('hap','hucking-and-scoring','HUCK SHARE AND SCORING','flyers'),
    ('mean_throws','throw-count-and-scoring','THROW COUNT AND SCORING','union')]:
    rows=data['teams'];rel=data['correlations']['hucking_vs_scoring_change' if xkey=='hap' else 'throws_vs_scoring_change']
    xmax=10 if xkey=='hap' else 6
    fig,ax=plt.subplots(figsize=(12,9))
    fig.subplots_adjust(left=.105,right=.965,bottom=.255,top=.815)
    fig.text(.105,.965,'UFA 2026  /  '+topic,fontsize=10,color=MUTED,weight='bold')
    fig.text(.105,.922,'How teams change on their second possession',fontsize=21,weight='bold')
    fig.text(.105,.875,'Each dot is a team. Changes are measured against its first possessions. Zero means no change.',fontsize=11,color=MUTED)
    lo,hi=rel['ci95']
    ax.set_axisbelow(True)
    ax.axhspan(0,60,color=BLUE,alpha=.035,zorder=0)
    ax.axhspan(-60,0,color=GRAY,alpha=.035,zorder=0)
    ax.grid(color=GRID,lw=.8)
    for spine in ax.spines.values():spine.set_visible(False)
    ax.tick_params(length=0,pad=8)
    ax.set_xlim(-xmax,xmax);ax.set_ylim(-60,60)
    ax.set_xticks(np.arange(-10,11,5) if xkey=='hap' else np.arange(-6,7,2))
    ax.set_yticks(np.arange(-60,61,20))
    ax.axvline(0,color=MUTED,lw=1.4);ax.axhline(0,color=MUTED,lw=1.4)
    reserved=[]
    for q in ['upper_left','upper_right','lower_left','lower_right']:
        left=q.endswith('left');upper=q.startswith('upper')
        a=('Lower huck share' if left else 'Higher huck share') if xkey=='hap' else ('Fewer throws' if left else 'More throws')
        b='Higher scoring' if upper else 'Lower scoring'
        n=len(data['quadrants'][xkey][q])
        text=f"{a}\n{b} · {n} {'team' if n==1 else 'teams'}"
        artist=ax.text(.022 if left else .978,.975 if upper else .025,text,transform=ax.transAxes,
                       ha='left' if left else 'right',va='top' if upper else 'bottom',fontsize=11,
                       color=MUTED,linespacing=1.55,weight='medium')
        reserved.append(artist)
    actualx=[r['change'][xkey] for r in rows]
    xx=np.linspace(min(actualx),max(actualx),100)
    ax.plot(xx,rel['intercept']+rel['slope']*xx,color=MUTED,lw=1.1,ls=(0,(4,4)),zorder=1)
    for r in rows:
        ax.scatter(r['change'][xkey],r['change']['scoring'],s=95,
                   color=BLUE if r['team']==focus else GRAY,alpha=.9,edgecolor='white',linewidth=.8,zorder=3)
    labels(fig,ax,rows,xkey,focus,reserved)
    ax.set_xlabel('Change in huck share (percentage points)' if xkey=='hap' else 'Change in average throws',labelpad=15,fontsize=12)
    ax.set_ylabel('Change in scoring rate\n(percentage points)',labelpad=14,fontsize=12)
    example='−2 means a two-percentage-point decrease in huck share.' if xkey=='hap' else '−2 means two fewer throws per possession.'
    fig.text(.105,.153,'Second minus first. '+example+' Dashed line = overall trend.',fontsize=9.5,color=MUTED)
    uncertainty=' The range includes zero.' if lo<=0<=hi else ''
    fig.text(.105,.120,f"Correlation: r = {rel['pearson']:+.2f}  ·  95% uncertainty range: {lo:+.2f} to {hi:+.2f}."+uncertainty,fontsize=10.5)
    fig.text(.105,.090,'Source: ShownSpace + audited UFA events · April 24–July 19, 2026 regular season.',fontsize=9,color=MUTED)
    fig.text(.105,.063,'22 teams · 4,802 first / 457 second possessions · original seven · starts ≥60 yards from goal.',fontsize=9,color=MUTED)
    fig.text(.105,.036,'Team uncertainty can cross quadrant boundaries. Correlation does not establish causation.',fontsize=9,color=MUTED)
    fig.savefig(OUT/(name+'.png'),dpi=200,facecolor='white')
    fig.savefig(OUT/(name+'.svg'),facecolor='white')
    plt.close(fig)
print(json.dumps({'figures':[str(OUT/(n+'.png')) for n in ['hucking-and-scoring','throw-count-and-scoring']]}))
