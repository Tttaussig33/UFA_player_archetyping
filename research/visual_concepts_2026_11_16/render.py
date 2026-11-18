"""Four standalone research figures from reviewed calculations. No webpages."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.transforms import Bbox

ROOT=Path(__file__).resolve().parent
D=json.loads((ROOT/'results.json').read_text())
OUT=ROOT/'images'
BLUE='#246b9b';INK='#20313d';GRAY='#8e9ba4';DARK='#344d60';MUTED='#566773';GRID='#e3e9ed'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'text.color':INK,'axes.labelcolor':INK,
 'xtick.color':MUTED,'ytick.color':MUTED,'svg.fonttype':'none','axes.unicode_minus':True})
SOURCE='Source: preserved ShownSpace + audited UFA events · April 24–July 19, 2026 regular season.'
LONG='Original receiving seven · starts ≥60 yards from goal · physical throws include centering passes.'
NAMES=['First','Second','Third or later']

def save(fig,name):
    fig.savefig(OUT/(name+'.png'),dpi=200,facecolor='white')
    fig.savefig(OUT/(name+'.svg'),facecolor='white')
    plt.close(fig)

def title(fig,num,topic,headline,subtitle):
    fig.text(.08,.956,f'OPTION {num}  /  UFA O-LINE POSSESSIONS  /  {topic}',fontsize=10,weight='bold',color=MUTED)
    fig.text(.08,.903,headline,fontsize=22,weight='bold')
    fig.text(.08,.858,subtitle,fontsize=11,color=MUTED)

def tidy(ax,axis='both'):
    ax.set_axisbelow(True)
    ax.grid(axis=axis,color=GRID,lw=.8)
    for spine in ax.spines.values():spine.set_visible(False)
    ax.tick_params(length=0,pad=8)

def team_map():
    fig,ax=plt.subplots(figsize=(12,8.6))
    fig.subplots_adjust(left=.105,right=.965,bottom=.24,top=.80)
    title(fig,1,'TEAM IDENTITIES','Who converts the second chance?',
          'First-possession scoring versus second-possession scoring · each dot is one team')
    data=D['team_map'];bx=data['benchmarks']['first'];by=data['benchmarks']['second']
    tidy(ax);ax.set(xlim=(20,80),ylim=(0,80),xticks=range(20,81,10),yticks=range(0,81,20))
    ax.axhspan(by,80,color=BLUE,alpha=.04)
    ax.axvline(bx,color=MUTED,ls=(0,(5,4)),lw=1.3)
    ax.axhline(by,color=MUTED,ls=(0,(5,4)),lw=1.3)
    labels={'union':'Chicago','bighorns':'Vegas','windchill':'Minnesota','flyers':'Carolina'}
    qtext={'upper_left':'Second-chance strength','upper_right':'Above average on both',
           'lower_left':'Below average on both','lower_right':'Opening-possession strength'}
    reserved=[]
    for q in qtext:
        left=q.endswith('left');upper=q.startswith('upper')
        s=f"{qtext[q]}\n{len(data['quadrants'][q])} {'team' if len(data['quadrants'][q])==1 else 'teams'}"
        reserved.append(ax.text(.025 if left else .975,.965 if upper else .035,s,transform=ax.transAxes,
          ha='left' if left else 'right',va='top' if upper else 'bottom',color=MUTED,fontsize=11,linespacing=1.6))
    for r in data['teams']:
        a,b=r['stages']
        ax.scatter(a['scoring'],b['scoring'],s=75,color=BLUE if r['team'] in labels else GRAY,
                   edgecolor='white',linewidth=.8,zorder=3)
    fig.canvas.draw();renderer=fig.canvas.get_renderer()
    used=[r.get_window_extent(renderer).expanded(1.02,1.05) for r in reserved]
    points=[ax.transData.transform((r['stages'][0]['scoring'],r['stages'][1]['scoring'])) for r in data['teams']]
    point_boxes=[Bbox.from_bounds(x-8,y-8,16,16) for x,y in points]
    for r in data['teams']:
        if r['team'] not in labels:continue
        a,b=r['stages'];x,y=a['scoring'],b['scoring'];text=f"{labels[r['team']]} · n={b['possessions']}";best=None
        for dx,dy in [(10,12),(10,-16),(-10,12),(-10,-16),(4,30),(4,-32),(26,30),(-26,30),(35,-30),(-35,-30)]:
            txt=ax.annotate(text,(x,y),xytext=(dx,dy),textcoords='offset points',ha='left' if dx>=0 else 'right',va='center',fontsize=10)
            bb=txt.get_window_extent(renderer).expanded(1.08,1.2)
            penalty=100*sum(bb.overlaps(v) for v in used)+20*sum(bb.overlaps(v) for v in point_boxes)+.1*(abs(dx)+abs(dy))
            if not ax.bbox.contains(bb.x0,bb.y0) or not ax.bbox.contains(bb.x1,bb.y1):penalty+=1000
            qx,qy=ax.transData.transform((bx,by))
            if (x<bx and bb.x1>qx) or (x>bx and bb.x0<qx) or (y<by and bb.y1>qy) or (y>by and bb.y0<qy):penalty+=1000
            txt.remove()
            if best is None or penalty<best[0]:best=(penalty,dx,dy,bb)
        _,dx,dy,bb=best;used.append(bb)
        ax.annotate(text,(x,y),xytext=(dx,dy),textcoords='offset points',ha='left' if dx>=0 else 'right',va='center',fontsize=10,
            arrowprops={'arrowstyle':'-','color':GRAY,'lw':.7,'shrinkA':3,'shrinkB':6} if abs(dy)>20 else None)
    ax.set_xlabel('First-possession scoring (%)',fontsize=12,labelpad=13)
    ax.set_ylabel('Second-possession scoring (%)',fontsize=12,labelpad=12)
    fig.text(.105,.144,f'Dashed lines = league rates: {bx:.1f}% first / {by:.1f}% second. n = second-possession sample.',fontsize=10,color=MUTED)
    fig.text(.105,.108,'Quadrants describe observed team rates; small samples make the placements uncertain.',fontsize=10,color=MUTED)
    fig.text(.105,.071,LONG,fontsize=9,color=MUTED)
    fig.text(.105,.039,SOURCE,fontsize=9,color=MUTED)
    save(fig,'01-team-second-chance-map')

def field_heatmap():
    fig,ax=plt.subplots(figsize=(12,9))
    fig.subplots_adjust(left=.23,right=.88,bottom=.23,top=.76)
    title(fig,2,'SCORING AND FIELD POSITION','Does the starting position change the story?',
          'Scoring percentage at each possession number, grouped by distance from the attacking goal')
    rows=D['field_position'];grid=np.array([[next(r['estimate'] for r in rows if r['band']==i and r['stage']==j) for j in [1,2,3]] for i in range(5)])
    cmap=LinearSegmentedColormap.from_list('scoring',['#f5f8fa','#c2d7e6','#246b9b'])
    im=ax.imshow(grid,cmap=cmap,vmin=0,vmax=100,aspect='auto')
    ax.set_xticks(range(3),['First','Second','Third or later'],fontsize=12)
    ax.xaxis.tick_top();ax.tick_params(axis='x',pad=14)
    ax.set_yticks(range(5),['80+ yards','60–80 yards','40–60 yards','20–40 yards','Under 20 yards'],fontsize=11)
    ax.set_ylabel('Distance to goal at the first throw',labelpad=18,fontsize=12)
    ax.set_xticks(np.arange(-.5,3,1),minor=True);ax.set_yticks(np.arange(-.5,5,1),minor=True)
    ax.grid(which='minor',color='white',lw=6);ax.tick_params(which='both',length=0)
    for spine in ax.spines.values():spine.set_visible(False)
    for r in rows:
        x=r['stage']-1;y=r['band'];color='white' if r['estimate']>=90 else INK
        ax.text(x,y-.20,f"{r['estimate']:.1f}%",ha='center',va='center',fontsize=19,weight='bold',color=color)
        ax.text(x,y+.08,f"{int(r['numerator']):,} / {int(r['denominator']):,} scored",ha='center',va='center',fontsize=10,color=color)
        ax.text(x,y+.30,f"95% range: {r['ci95'][0]:.0f}–{r['ci95'][1]:.0f}%",ha='center',va='center',fontsize=9.5,color=color)
    cax=fig.add_axes([.905,.23,.017,.53]);cb=fig.colorbar(im,cax=cax,ticks=[0,25,50,75,100]);cb.outline.set_visible(False)
    cb.set_label('Scoring (%)',fontsize=10,labelpad=10);cb.ax.tick_params(length=0,labelsize=9)
    fig.text(.08,.166,'Original seven · all known starts · 5,474 first / 838 second / 137 third-or-later possessions.',fontsize=10,color=MUTED)
    fig.text(.08,.127,'Cells show observed rates and 95% game-bootstrap ranges. Small groups have much wider ranges.',fontsize=10,color=MUTED)
    fig.text(.08,.089,'Starting areas are broad, and later possessions are selected. These differences do not establish fatigue.',fontsize=10,color=MUTED)
    fig.text(.08,.048,SOURCE,fontsize=9,color=MUTED)
    save(fig,'02-scoring-by-starting-position')

def throws_progression():
    fig,axes=plt.subplots(1,3,figsize=(12,7.6),sharey=True)
    fig.subplots_adjust(left=.08,right=.97,bottom=.28,top=.72,wspace=.20)
    title(fig,3,'THROWS PER POSSESSION','How does possession length change?',
          'The same comparison, separated into possessions that end in goals and turnovers')
    colors=[DARK,BLUE,GRAY]
    for ax,g,color,name in zip(axes,D['throws_by_outcome'],colors,['All possessions','Ending in a goal','Ending in a turnover']):
        v=g['stages'];xx=np.arange(3);yy=np.array([r['estimate'] for r in v]);lo=np.array([r['ci95'][0] for r in v]);hi=np.array([r['ci95'][1] for r in v])
        tidy(ax,axis='y');ax.set_title(name,fontsize=13,pad=20,weight='bold')
        ax.plot(xx,yy,color=color,lw=1.8,zorder=2)
        ax.errorbar(xx,yy,yerr=[yy-lo,hi-yy],fmt='o',color=color,capsize=5,ms=7,lw=1.3,zorder=3)
        for x,r in zip(xx,v):ax.text(x,r['ci95'][1]+.43,f"{r['estimate']:.2f}",ha='center',fontsize=12,weight='bold',color=INK)
        ax.set_xticks(xx,[f"{name}\nn={int(r['denominator']):,}" for name,r in zip(['First','Second','Third+'],v)],fontsize=10)
        ax.set(xlim=(-.35,2.35),ylim=(0,12.2),yticks=[0,3,6,9,12])
    axes[0].set_ylabel('Average physical throws per possession',fontsize=11,labelpad=10)
    fig.text(.08,.182,'Dots = averages. Whiskers = 95% game-bootstrap ranges. n = possessions in that outcome group.',fontsize=10,color=MUTED)
    fig.text(.08,.133,LONG,fontsize=9.5,color=MUTED)
    fig.text(.08,.091,'Shorter possessions appear in both outcomes; this does not show that taking fewer throws causes either result.',fontsize=9.5,color=MUTED)
    fig.text(.08,.045,SOURCE,fontsize=9,color=MUTED)
    save(fig,'03-throw-count-progression')

def huck_profile():
    fig,axes=plt.subplots(1,2,figsize=(12,7.8))
    fig.subplots_adjust(left=.08,right=.96,bottom=.30,top=.73,wspace=.26)
    title(fig,4,'HUCK CHOICES AND OUTCOMES','How does hucking change after a regain?',
          'Separate how often the O-line attempts a huck from how often those hucks are completed')
    colors=[GRAY,BLUE,DARK]
    for ax,g,name,unit,denom,top in zip(axes,D['huck_profile'],['Huck attempt percentage','Huck completion percentage'],['Share of all throws (%)','Share of hucks completed (%)'],['throws','hucks'],[14,100]):
        v=g['stages'];xx=np.arange(3);yy=np.array([r['estimate'] for r in v]);lo=np.array([r['ci95'][0] for r in v]);hi=np.array([r['ci95'][1] for r in v])
        tidy(ax,axis='y');ax.set_title(name,fontsize=13,pad=22,weight='bold')
        ax.bar(xx,yy,color=colors,width=.55,zorder=2)
        ax.errorbar(xx,yy,yerr=[yy-lo,hi-yy],fmt='none',ecolor=INK,capsize=5,lw=1.2,zorder=3)
        for x,r in zip(xx,v):ax.text(x,r['estimate']*.45,f"{r['estimate']:.1f}%",ha='center',va='center',fontsize=14,weight='bold',color=INK if x==0 else 'white')
        ax.set_xticks(xx,[f"{name}\n{int(r['denominator']):,} {denom}" for name,r in zip(['First','Second','Third+'],v)],fontsize=10)
        ax.set_ylabel(unit,fontsize=11,labelpad=10);ax.set_ylim(0,top)
        if top==14:ax.set_yticks([0,3,6,9,12])
        a,b=g['change_ci95']
        ax.text(.5,-.22,f"First → second: {g['change']:+.1f} percentage points\n95% range: {a:+.1f} to {b:+.1f}",transform=ax.transAxes,ha='center',va='top',fontsize=10,color=MUTED,linespacing=1.6)
    fig.text(.08,.104,'Whiskers = 95% game-bootstrap ranges. Third-or-later completion uses just 32 huck attempts.',fontsize=10,color=MUTED)
    fig.text(.08,.066,LONG,fontsize=9.5,color=MUTED)
    fig.text(.08,.028,SOURCE,fontsize=9,color=MUTED)
    save(fig,'04-huck-frequency-and-completion')

team_map();field_heatmap();throws_progression();huck_profile()
print(json.dumps({'images':[str(p) for p in sorted(OUT.glob('*.png'))]}))
