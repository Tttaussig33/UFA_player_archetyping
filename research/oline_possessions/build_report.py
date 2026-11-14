"""Refresh the existing self-contained report from reviewed aggregate results."""
from pathlib import Path
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parent
CANVAS = Path('/Users/teddytaussig/.cursor/projects/Users-teddytaussig-Desktop-Work-UFA-player-archetyping/canvases/UFA-oline-regain-hucking.canvas.tsx')

BODY = r'''
type Estimate = {stage:number; estimate:number|null; n?:number; sum?:number; ci95:[number,number]|null};
const names = ["First", "Second", "Third or later"];
const pct = (v:number) => (100*v).toFixed(1)+"%";
const number = (v:number) => v.toLocaleString();
const signed = (v:number) => (v>0?"+":"")+v.toFixed(1);
const range = (v:number[], scale=1) => v.map(x=>(scale*x).toFixed(1)).join(" to ");
const SOURCE = "Source: preserved ShownSpace export and UFA event sequences · 2026 regular season · November 5 analysis, November 6 follow-ups and November 9 exact-possession tables.";
const SCORING_SOURCE = "Source: preserved ShownSpace possession records and UFA event lineups · 2026 regular season · original-seven scoring audit, November 13, 2026.";
const HAP_SOURCE = "Source: saved ShownSpace Postgres export and audited UFA event lineups · 2026 regular season · 131 of 132 games · recalculated November 13, 2026.";
const metrics:Record<string,{label:string;unit:string;count:boolean;denominator:string;explain:string}> = {
  early_huck:{label:"Huck within the first 3 throws (parked)",unit:"% of eligible possessions",count:false,denominator:"possessions",explain:"This comparison is parked while we review starting locations and centering passes. The saved figures count possessions with at least one huck in their first three actual throws, including those ending before throw three. Starts must be at least 40 yards from the attacking goal line."},
  throws_goal:{label:"Throws before a goal",unit:"mean throws per goal possession",count:true,denominator:"goal possessions",explain:"The average number of physical throws in possessions that end in a goal. Every actual throw counts, including setup passes. All starting locations are included."},
  throws_turnover:{label:"Throws before a turnover",unit:"mean throws per turnover possession",count:true,denominator:"turnover possessions",explain:"The average number of physical throws in possessions that end in a turnover, including the final incomplete throw. A stall adds no physical throw. All starting locations are included."},
  scoring:{label:"Possession scoring rate",unit:"% of resolved possessions",count:false,denominator:"resolved original-line possessions",explain:"Goals divided by possessions ending in a goal or turnover while the original seven receiving-point players remain on. Stop at the first personnel change; keep completed possessions before it. Near-goal starts remain included. Possessions containing a timeout and period-ending possessions are excluded from the main rate."},
  huck_share:{label:"Huck attempt percentage",unit:"% of throw attempts",count:false,denominator:"throw attempts",explain:"Huck attempts divided by all physical throw attempts by the original seven, including centering passes. This team view uses starts at least 60 yards from goal. The dedicated huck-attempt comparison above also lets you include all starting locations. A shorter possession can have a higher huck share without being more likely to contain a huck."},
  any_huck:{label:"Possessions with a huck (%)",unit:"% of eligible possessions",count:false,denominator:"possessions",explain:"Possessions containing at least one huck divided by eligible possessions. Each possession counts once. This differs from huck attempt percentage, whose denominator is throw attempts. This earlier comparison uses starts at least 40 yards from goal and its earlier timeout filters."},
  huck_completion:{label:"Huck completion percentage",unit:"% of huck attempts",count:false,denominator:"huck attempts",explain:"Completed hucks divided by huck attempts, with drops counted as incomplete. The team comparison is descriptive and unadjusted; small later-possession samples limit conclusions about accuracy."},
  break_after_turnover:{label:"Eventually broken after a turnover",unit:"% of turnovers in points ending with a goal",count:false,denominator:"turnovers in resolved points",explain:"After this team turns the disc over, how often does its opponent eventually score in that same point? This is an observed point outcome, not one minus possession scoring rate. Points ending with the period are excluded from this rate."}
};
function chartValue(g:Estimate, count=false) { return Number(((g.estimate||0)*(count?1:100)).toFixed(1)); }
function groupText(g:Estimate, count=false) { return !g || !g.n || g.estimate==null ? "— (0)" : (count?g.estimate.toFixed(1):pct(g.estimate))+" ("+number(g.n)+")"; }
function observedInterval(g:Estimate,count=false) { return !count&&(g.sum===0||g.sum===g.n)?null:g.ci95; }
function Counts({groups,count=false,denominator="possessions"}:{groups:Estimate[];count?:boolean;denominator?:string}) {
  return <Table headers={["Team possession","Observed result","95% uncertainty range","Number of "+denominator]}
    rows={groups.map(g=>[names[g.stage-1],g.estimate==null?"—":(count?g.estimate.toFixed(2):pct(g.estimate)),g.ci95?range(g.ci95,count?1:100)+(count?" throws":"% "):"—",number(g.n||0)])}
    columnAlign={["left","right","right","right"]}/>;
}
function LabeledBarChart({xLabel="Team possession within the same point",yLabel,...props}:any) {
  const theme=useHostTheme();
  return <figure style={{margin:0}} aria-label={`${yLabel} by ${xLabel}`}>
    <div style={{display:"grid",gridTemplateColumns:"28px minmax(0,1fr)",gap:4,alignItems:"stretch"}}>
      <div data-axis-y={yLabel} style={{writingMode:"vertical-rl",transform:"rotate(180deg)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:13,color:theme.text.primary,paddingBottom:24}}>{yLabel}</div>
      <div style={{minWidth:0}}><BarChart {...props}/><div data-axis-x={xLabel} style={{textAlign:"center",fontSize:13,color:theme.text.primary,paddingTop:4}}>{xLabel}</div></div>
    </div>
  </figure>;
}
function SingleChart({groups,label,count=false,max,yLabel,xLabel}:{groups:Estimate[];label:string;count?:boolean;max?:number;yLabel:string;xLabel?:string}) {
  const visible=groups.filter(g=>g.estimate!=null && (g.n===undefined || g.n>0));
  const axisMax=max??(count?Math.ceil(Math.max(...visible.map(g=>g.estimate||0))*1.05/4)*4:undefined);
  return <LabeledBarChart yLabel={yLabel} xLabel={xLabel} categories={visible.map(g=>names[g.stage-1])}
    series={[{name:label,data:visible.map(g=>chartValue(g,count)),tone:"info"}]}
    height={245} showValues beginAtZero yMax={axisMax} valueSuffix={count?"":"%"}/>;
}

type TeamColumn = {key:string; label:string; value?:(team:any)=>number|string|null; display:(team:any)=>any; align?:"left"|"right"};
function SortableTeamTable({rows,columns,label}:{rows:any[];columns:TeamColumn[];label:string}) {
  const theme=useHostTheme();
  const [sort,setSort]=useState({key:"team",direction:"asc"});
  const selected=columns.find(c=>c.key===sort.key&&c.value);
  const active=selected||columns[0];
  const direction=selected?sort.direction:"asc";
  const ordered=[...rows].sort((a,b)=>{
    const av=active.value?.(a),bv=active.value?.(b);
    const missingA=av==null||(typeof av==="number"&&!Number.isFinite(av));
    const missingB=bv==null||(typeof bv==="number"&&!Number.isFinite(bv));
    if(missingA!==missingB)return missingA?1:-1;
    const comparison=missingA?0:typeof av==="number"&&typeof bv==="number"?av-bv:String(av).localeCompare(String(bv));
    return (direction==="desc"?-comparison:comparison)||a.team_name.localeCompare(b.team_name);
  });
  const cellStyle={padding:"9px 11px",borderBottom:`1px solid ${theme.stroke.tertiary}`,verticalAlign:"top" as const};
  return <div role="region" aria-label={label} tabIndex={0} data-sort-key={active.key} data-sort-direction={direction} style={{maxWidth:"100%",overflowX:"auto"}}>
    <table style={{borderCollapse:"collapse",width:"100%",fontSize:13,color:theme.text.primary}}>
      <thead><tr>{columns.map((column,i)=>{
        const current=column.key===active.key;
        const next=current?(direction==="asc"?"desc":"asc"):(column.key==="team"?"asc":"desc");
        const order=column.key==="team"?(next==="asc"?"A to Z":"Z to A"):(next==="asc"?"low to high":"high to low");
        return <th key={column.key} scope="col" aria-sort={column.value?(current?(direction==="asc"?"ascending":"descending"):"none"):undefined} style={{...cellStyle,minWidth:i===0?140:90,textAlign:column.align||"right",fontWeight:600}}>
          {column.value?<button type="button" title={`Sort ${order}`} aria-label={`Sort by ${column.label}, ${order}`} onClick={()=>setSort({key:column.key,direction:next})} style={{font:"inherit",fontWeight:"inherit",textAlign:"inherit",color:"inherit",background:"transparent",border:0,padding:0,cursor:"pointer"}}>{column.label}<span aria-hidden="true" style={{marginLeft:6,color:current?theme.text.link:theme.text.secondary}}>{current?(direction==="asc"?"↑":"↓"):"↕"}</span></button>:column.label}
        </th>;
      })}</tr></thead>
      <tbody>{ordered.map(team=><tr key={team.team}>{columns.map(column=><td key={column.key} style={{...cellStyle,textAlign:column.align||"right"}}>{column.display(team)}</td>)}</tr>)}</tbody>
    </table>
  </div>;
}

export default function OLineRegainHucking() {
  const theme=useHostTheme();
  const [metric,setMetric]=useState("throws_goal");
  const [teamId,setTeamId]=useState("spiders");
  const [teamPool,setTeamPool]=useState("playoffs");
  const [scoringView,setScoringView]=useState("observed");
  const [tablePossession,setTablePossession]=useState("1");
  const [hapScope,setHapScope]=useState("long_field");
  const [hapTeamId,setHapTeamId]=useState("league");
  const hap=DATA.huck_attempt_percentage.scopes[hapScope];
  const hapTeams=[...hap.teams].sort((a:any,b:any)=>a.team_name.localeCompare(b.team_name));
  const hapTeam=hapTeams.find((t:any)=>t.team===hapTeamId);
  const hapObserved=hapTeam?hapTeam.observed:hap.league;
  const hapGroups=hapObserved.groups.slice(0,2);
  const hapChange=hapObserved.differences[0];
  const hapName=hapTeam?hapTeam.team_name:"League total";
  const tableStage=Number(tablePossession);
  const tableStageLabel=tablePossession==="all"?"Comparison":({"1":"First possession","2":"Second possession","3":"Third possession"} as Record<string,string>)[tablePossession];
  const teams=DATA.teams.filter((t:any)=>teamPool==="all"||DATA.follow_up.playoff_team_ids.includes(t.team)).sort((a:any,b:any)=>a.team_name.localeCompare(b.team_name));
  const team=teams.find((t:any)=>t.team===teamId)||teams[0];
  const spec=metrics[metric];
  const modeled=Boolean(DATA.team_changes[metric]);
  const observedComparison=modeled?null:team.metrics[metric].first_vs_all_subsequent;
  const change=modeled?DATA.team_changes[metric].teams.find((t:any)=>t.team===team.team):{...observedComparison.differences[0],subsequent_n:observedComparison.groups[1].n,games:observedComparison.games};
  const teamNameColumn:TeamColumn={key:"team",label:"Team",align:"left",value:t=>t.team_name,display:t=>t.team_name+(t.games===11?" *":"")};
  const tableChange=(t:any)=>modeled?DATA.team_changes[metric].teams.find((v:any)=>v.team===t.team):t.metrics[metric].first_vs_all_subsequent.differences[0];
  const tableChangeRange=(t:any)=>!modeled&&!spec.count&&t.metrics[metric].first_vs_all_subsequent.groups.some((g:Estimate)=>g.sum===0||g.sum===g.n)?null:tableChange(t).ci95;
  const changeInterval=tableChangeRange(team);
  const tableColumns:TeamColumn[]=tablePossession==="all"?[teamNameColumn,
    ...["First","Second","Third+"].map((label,i)=>({key:`stage${i+1}`,label:`${label} (${spec.count?"mean":"%"}; n)`,value:(t:any)=>t.metrics[metric].groups[i].estimate,display:(t:any)=>groupText(t.metrics[metric].groups[i],spec.count)})),
    {key:"change",label:`${modeled?"Adjusted":"Observed"} change (${spec.count?"throws":"pp"}); 95% range`,value:t=>tableChange(t).difference,display:t=>{const c=tableChange(t);const ci=tableChangeRange(t);return `${signed(c.difference*(spec.count?1:100))} [${ci?range(ci,spec.count?1:100):"—"}]`;}}]
    :[teamNameColumn,{key:"value",label:`${tableStageLabel} (${spec.count?"mean throws":"%"}; n)`,value:t=>t.exact_metrics[metric][tableStage-1].estimate,display:t=>groupText(t.exact_metrics[metric][tableStage-1],spec.count)},
      {key:"uncertainty",label:"95% uncertainty range",display:t=>{const g=t.exact_metrics[metric][tableStage-1];const ci=observedInterval(g,spec.count);return ci?range(ci,spec.count?1:100)+(spec.count?" throws":"%"):"—";}}];
  const summaryColumns:TeamColumn[]=[teamNameColumn,...["throws_goal","throws_turnover","scoring","early_huck"].map(k=>({key:k,label:({throws_goal:"Throws before goal (mean; n)",throws_turnover:"Throws before turnover (mean; n)",scoring:"Possession scoring (%; n)",early_huck:"Early huck — parked (%; n)"} as Record<string,string>)[k],
    value:(t:any)=>{if(tablePossession!=="all")return t.exact_metrics[k][tableStage-1].estimate;const gs=t.metrics[k].groups;const n=gs[1].n+gs[2].n;return n?(gs[1].sum+gs[2].sum)/n:null;},
    display:(t:any)=>{if(tablePossession!=="all")return groupText(t.exact_metrics[k][tableStage-1],k.startsWith("throws"));const gs=t.metrics[k].groups;const n=gs[1].n+gs[2].n;const later={stage:2,n,estimate:n?(gs[1].sum+gs[2].sum)/n:null,ci95:null};return `${groupText(gs[0],k.startsWith("throws"))} → ${groupText(later,k.startsWith("throws"))}`;}}))];
  const early=DATA.league.early_huck.groups;
  const earlyModel=DATA.adjusted.early_huck;
  const startingReview=DATA.huck_starting_location_review.groups;
  const caught=DATA.league.huck_completion.groups;
  const rawScore=DATA.league.scoring.groups;
  const lineScore=DATA.original_line_scoring;
  const scoreGroups=scoringView==="observed"?rawScore:DATA.adjusted.scoring.groups;
  const sectionStyle={paddingTop:24,borderTop:`1px solid ${theme.stroke.tertiary}`};
  const linkStyle={color:theme.text.link};
  const centering=DATA.reviewed_centering_counts;
  const centeringStages=centering.groups.goal.map((g:any)=>g.stage);
  const centeringSampleText=centeringStages.map((stage:number)=>`${names[stage-1]} possession: ${centering.groups.goal.find((g:any)=>g.stage===stage).n} goals, ${centering.groups.turnover.find((g:any)=>g.stage===stage).n} turnovers`).join(" · ");
  const centeringAxisMax=Math.ceil(Math.max(...Object.values(centering.groups).flat().map((g:any)=>g.physicalMean))/4)*4;
  return <Stack gap={28} style={{padding:22,maxWidth:1100,margin:"0 auto",color:theme.text.primary}}>
    <Stack gap={10}>
      <H1>O-line offense after turnovers</H1>
      <Text>2026 UFA regular season · 22 teams · 131 of 132 games · exploratory research</Text>
      <Text>After turning the disc over and getting it back, does an O-line change how it attacks, and how do its chances of scoring compare with its opening opportunity?</Text>
      <Text><strong>Current focus: throw counts, huck attempt percentage, scoring and outcomes after turnovers.</strong> The reviewed comparison shows the same possessions before and after subtracting confirmed centering passes. League-wide huck timing remains parked until more opening passes are classified and comparable starting locations are established.</Text>
      <Text><strong>When a timeout changes the lineup.</strong> After the O-line turns the disc over, a timeout may allow its team to replace it with D-line players. We keep the original O-line’s throws and turnover, regardless of which team calls the timeout. We stop following that O-line when its lineup changes. Later throws, goals and turnovers by the replacement players do not count as the original O-line’s second or third possession.</Text>
      <Text size="small">The turnover means the point was not a clean hold. The receiving team can still finish with a hold or a break, but we record that team result separately from the original O-line’s performance.</Text>
      <div style={{display:"flex",gap:18,flexWrap:"wrap",fontSize:14}}>
        <a href="#centering-counts" style={linkStyle}>Centering-pass adjustment</a>
        <a href="#league" style={linkStyle}>League results</a><a href="#scoring" style={linkStyle}>Scoring with the original O-line</a><a href="#huck-attempts" style={linkStyle}>Huck attempt percentage</a><a href="#teams" style={linkStyle}>Playoff teams and all teams</a><a href="#breaks" style={linkStyle}>Breaks after turnovers</a><a href="#huck-outcomes" style={linkStyle}>Huck outcomes</a><a href="#paper" style={linkStyle}>Research direction</a><a href="#methods" style={linkStyle}>Definitions and checks</a>
      </div>
    </Stack>
    <section aria-label="How to read the comparisons">
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(min(100%,230px),1fr))",gap:20}}>
        <Text><strong>First</strong><br/>The receiving team's opening possession after the pull.</Text>
        <Text><strong>Second</strong><br/>Its first possession after losing the disc and getting it back.</Text>
        <Text><strong>Third or later</strong><br/>Its possessions after further losses and recoveries within that point.</Text>
      </div>
      <Text size="small" tone="secondary" style={{marginTop:16}}><strong>Scoring and huck attempt percentage follow the original seven players.</strong> The updated views stop at a recorded personnel change or uncertain lineup record. Other league measures retain their earlier filters and may include replacement players. The before-and-after throw-count charts below use only the film-reviewed sample.</Text>
    </section>

    <section id="centering-counts" style={sectionStyle} data-review-count-source="reviewed_centering_counts.json">
      <Stack gap={18}>
        <H2>Throw counts before and after the centering-pass adjustment</H2>
        <Text><strong>Both charts contain exactly the same possessions.</strong> The first counts every throw. For the second, subtract one from a possession only if it has a confirmed centering pass, leave every other possession unchanged, and recalculate the average. No possession is removed because it has a centering pass.</Text>
        <Text size="small"><strong>Starting location stays at the beginning of the possession.</strong> Removing a centering pass changes the throw count, not the location used to compare starts. The current records use the first throwing location, which may differ from the exact place the pull was caught or the disc was picked up.</Text>
        <Text><strong>Blue:</strong> possessions ending in a goal. <strong>Gray:</strong> possessions ending in a turnover. Each bar shows the average number of throws in that group, not a scoring percentage or a count of goals or turnovers.</Text>
        {(["physical","adjusted"] as const).map(view=>{
          const adjusted=view==="adjusted";
          return <Stack key={view} gap={10}>
            <H2>{adjusted?"2. Same possessions, centering passes subtracted":"1. All throws, centering passes included"}</H2>
            <LabeledBarChart categories={centeringStages.map((stage:number)=>`${names[stage-1]} possession`)}
              series={[{name:"Ends in a goal",tone:"info",data:centering.groups.goal.map((g:any)=>Number((adjusted?g.attackingMean:g.physicalMean).toFixed(1)))},{name:"Ends in a turnover",tone:"neutral",data:centering.groups.turnover.map((g:any)=>Number((adjusted?g.attackingMean:g.physicalMean).toFixed(1)))}]}
              height={255} showValues beginAtZero yMax={centeringAxisMax}
              yLabel="Mean throws per possession"
              xLabel="Possession within the point"/>
            <Text size="small" tone="secondary">Reviewed possessions — {centeringSampleText}.</Text>
          </Stack>;
        })}
        <Text size="small">Each color uses exactly the same possessions in both charts. Only confirmed centering-pass throws are subtracted in the bottom chart. Second-possession bars stay the same because those possessions have no opening centering pass.</Text>
        <Text size="small" tone="secondary">Source: saved human review labels and preserved UFA event records · 2026 games · counted November 12, 2026. Across goals and turnovers, the sample contains {centering.scope.first} opening and {centering.scope.second} second possessions. These examples were selected for film review and are not matched by starting location. The bars describe this reviewed sample, not a league estimate or a proven first-to-second change.</Text>
        <details><summary>Which reviews are included?</summary><Stack gap={10} style={{marginTop:12}}>
          <Text>Of {centering.scope.reviewed} saved reviews, {centering.scope.included} completed possessions qualify. Excluded examples remain in the review archive. {centering.scope.thirdOrLater===0?"No qualifying third possession is available in this small sample.":"Third and later possessions are grouped together."}</Text>
          <ul style={{margin:0,paddingLeft:22,lineHeight:1.6}}>{centering.primaryExclusions.map((e:any)=><li key={e.reason}>{e.reason}: {e.n}</li>)}</ul>
          <Text>A centering-pass turnover still counts as a turnover, even if it leaves zero attacking throws. Scoring outcomes are not changed by subtracting a centering pass. Unreviewed or unresolved openings are not automatically shortened.</Text>
        </Stack></details>
      </Stack>
    </section>

    <section id="league" style={sectionStyle}>
      <Stack gap={12}>
        <H2>1. Early-huck comparison — parked</H2>
        <Text>We are holding this comparison out of the main findings until we settle how to compare starting locations and opening sequences.</Text>
        <details data-early-huck-review="true"><summary>View the saved charts and where the +7.1 estimate comes from</summary><Stack gap={18} style={{marginTop:16}}>
        <H2>Recorded hucks within the first 3 throws</H2>
        <Text>Each bar shows the percentage of possessions containing at least one huck in throws 1–3. Only starts at least 40 yards from the attacking goal line are included. All actual throws count, including centering passes.</Text>
        <div data-recorded-early-chart="true"><SingleChart groups={early} label="Recorded huck within first 3 throws" yLabel="Share of possessions (%)" max={30}/></div>
        <ul style={{margin:0,paddingLeft:22,lineHeight:1.6}}>
          <li><strong>Starting locations still differ.</strong> The 40-yard cutoff leaves room for a deep throw, but it does not put every possession in the same field area.</li>
          <li><strong>Opening sequences differ too.</strong> A centering pass uses one of the first three throws. Opening possessions can therefore contain fewer attacking throws within this window.</li>
        </ul>
        <Text size="small" tone="secondary">{SOURCE} First: {number(early[0].sum)} / {number(early[0].n)}; second: {number(early[1].sum)} / {number(early[1].n)}; third or later: {number(early[2].sum)} / {number(early[2].n)}. Counts and 95% uncertainty ranges are retained below; third-or-later evidence is less precise.</Text>

        <H2>Where the +7.1 percentage points comes from</H2>
        <Text>We fitted a logistic regression for this study: a model estimating whether a possession contains a huck in its first three throws. It uses {number(earlyModel.model.n)} possessions from {earlyModel.model.games} games. ShownSpace's pass-completion predictions are not inputs to this model.</Text>
        <ol style={{margin:0,paddingLeft:22,lineHeight:1.6}}>
          <li><strong>Learn the relationship in the records.</strong> The model uses possession number, starting distance from goal and from the middle of the field, team, opponent, quarter, and the recorded time when the point began.</li>
          <li><strong>Make two predictions for each included situation.</strong> Keep its starting location and game information the same. Predict once with the possession number set to first, then again with it set to second.</li>
          <li><strong>Average each set of predictions.</strong> The resulting estimates are {pct(earlyModel.groups[0].estimate)} for first possessions and {pct(earlyModel.groups[1].estimate)} for second possessions.</li>
        </ol>
        <div data-modeled-early-chart="true"><LabeledBarChart categories={names.slice(0,2)} series={[{name:"Model estimate using the same recorded situations",tone:"info",data:earlyModel.groups.slice(0,2).map((g:Estimate)=>chartValue(g))}]} horizontal height={245} showValues beginAtZero yMax={30} valueSuffix="%" xLabel="Estimated share of possessions (%)" yLabel="Team possession in the same point"/></div>
        <Text><strong>{pct(earlyModel.groups[1].estimate)} − {pct(earlyModel.groups[0].estimate)} = {signed(100*earlyModel.differences[0].difference)} percentage points.</strong> This is the model-estimated first-to-second difference, with a 95% uncertainty range of {range(earlyModel.differences[0].ci95,100)} percentage points. The bars above are predictions averaged over the same mix of situations.</Text>
        <Text><strong>Why it remains parked:</strong> This calculation relies on the model; it does not pair actual possessions starting in the same place. Starting location is the first recorded throwing location, which may differ from where the disc was won. <strong>It does not adjust for which passes are centering passes.</strong> We still need to review starting-location overlap and decide how to treat opening setup throws before interpreting the difference as a change in attacking behavior.</Text>
        <Text size="small" tone="secondary">{SOURCE} Saved November 5 model; no refit. The model uses time at the start of the point, not elapsed time before a later possession. First and second model estimates are shown here to explain this particular comparison; the saved third-or-later estimate remains in the research results.</Text>

        <H2>Field position changes the whole-possession comparison</H2>
        <Text>This is a separate question: did a huck occur <strong>at any point</strong> in the possession?</Text>
        <ul style={{margin:0,paddingLeft:22,lineHeight:1.6}}>
          <li><strong>With the 40-yard starting restriction:</strong> {pct(DATA.league.any_huck.groups[0].estimate)} of first possessions and {pct(DATA.league.any_huck.groups[1].estimate)} of second possessions contain a huck.</li>
          <li><strong>Including all known starting locations:</strong> those rates are {pct(startingReview[0].any_huck_rate)} and {pct(startingReview[1].any_huck_rate)}. Starts within 40 yards of goal make up {pct(startingReview[0].near_goal_n/startingReview[0].known_location_n)} of first possessions versus {pct(startingReview[1].near_goal_n/startingReview[1].known_location_n)} of second possessions.</li>
        </ul>
        <Text>The near-equal rates apply only to the restricted sample. They do not show that teams huck equally often from all starting locations, and the early-throw comparison alone does not establish why teams change their choices.</Text>
        <Text size="small" tone="secondary">Same preserved possession records and timeout exclusions. All-known-start counts: first {number(startingReview[0].any_huck_n)} / {number(startingReview[0].known_location_n)}; second {number(startingReview[1].any_huck_n)} / {number(startingReview[1].known_location_n)}. Unknown locations are excluded from both location comparisons.</Text>
        <details><summary>Counts, uncertainty, and the opening centering pass</summary><Stack gap={12} style={{marginTop:14}}>
          <Counts groups={early}/>
          <Text>After a caught pull, the first pass should be a centering pass in the opening sequence we are examining. Brick starts and immediate attacking throws need separate treatment. We have not automatically labeled those sequences across the league.</Text>
          <Text>As a check beyond throw one, the huck share on throws 2–3 is {pct(DATA.throw_windows[1].groups[0].estimate)} on first possessions versus {pct(DATA.throw_windows[1].groups[1].estimate)} on second possessions. After context adjustment, that difference is {signed(100*DATA.follow_up_checks.adjusted_huck_choice_throws_2_3.differences[0].difference)} points, with a 95% range of {range(DATA.follow_up_checks.adjusted_huck_choice_throws_2_3.differences[0].ci95,100)}. These are still recorded throw numbers, not proven equivalents of the first two attacking throws. This check does not fully resolve centering-pass differences.</Text>
          <Text>Manual review: case A is setup; D is a centering pass; C and E are not centering passes. These examples have been recorded, but they are not enough to classify every opening pass automatically. No blanket first-pass removal is applied.</Text>
          <H2>Huck choices by throw number</H2>
          <LabeledBarChart xLabel="Throw number within the current possession" yLabel="Throws that are hucks (%)" categories={DATA.throw_windows.map((w:any)=>w.window)} series={[{name:"First possession",tone:"neutral",data:DATA.throw_windows.map((w:any)=>chartValue(w.groups[0]))},{name:"Second possession",tone:"info",data:DATA.throw_windows.map((w:any)=>chartValue(w.groups[1]))}]} height={260} showValues beginAtZero yMax={12} valueSuffix="%"/>
          <Text size="small" tone="secondary">{SOURCE} A possession must survive long enough to enter a later throw window. This is a per-throw comparison, unlike the per-possession chart above.</Text>
        </Stack></details>
        </Stack></details>
      </Stack>
    </section>

    <section style={sectionStyle}>
      <Stack gap={12}>
        <H2>2. Subsequent possessions use fewer throws</H2>
        <Text>On possessions ending in a goal, the mean falls from <strong>{DATA.league.throws_goal.groups[0].estimate.toFixed(1)} to {DATA.league.throws_goal.groups[1].estimate.toFixed(1)} throws</strong> between first and second possessions. On possessions ending in a turnover, it falls from <strong>{DATA.league.throws_turnover.groups[0].estimate.toFixed(1)} to {DATA.league.throws_turnover.groups[1].estimate.toFixed(1)}</strong>.</Text>
        <LabeledBarChart yLabel="Mean number of throws" categories={names} series={[{name:"Ends in a goal",tone:"info",data:DATA.league.throws_goal.groups.map((g:Estimate)=>chartValue(g,true))},{name:"Ends in a turnover",tone:"neutral",data:DATA.league.throws_turnover.groups.map((g:Estimate)=>chartValue(g,true))}]} height={275} showValues beginAtZero yMax={12}/>
        <Text>Regained possessions begin about 24 yards farther upfield on average, which explains part of the difference. After accounting for starting location and other recorded context, second possessions still average <strong>{Math.abs(DATA.adjusted.throws_goal.differences[0].difference).toFixed(1)} fewer throws before goals</strong> and <strong>{Math.abs(DATA.adjusted.throws_turnover.differences[0].difference).toFixed(1)} fewer before turnovers</strong>.</Text>
        <Text>These are fewer passing actions within a possession. That fits the change in approach you described. The analysis does not attribute the entire difference to hucks or establish what players were feeling.</Text>
        <Text size="small" tone="secondary">{SOURCE} All field locations; goals and turnovers shown separately. Completed hucks can shorten the passing sequence, but possession length and huck choice are not independent measures.</Text>
        <details><summary>Throw-count denominators and uncertainty</summary><Stack gap={12} style={{marginTop:14}}>
          <Text weight="semibold">Possessions ending in a goal</Text><Counts groups={DATA.league.throws_goal.groups} count denominator="goal possessions"/>
          <Text weight="semibold">Possessions ending in a turnover</Text><Counts groups={DATA.league.throws_turnover.groups} count denominator="turnover possessions"/>
          <Text size="small">The final incomplete throw counts. Stalls add no throw; Callahan catches can create a zero-throw goal possession. Those outcomes are retained in the raw totals. Period-ending possessions are not included in either mean.</Text>
        </Stack></details>
      </Stack>
    </section>

    <section id="scoring" style={sectionStyle}>
      <Stack gap={12}>
        <H2>3. Scoring does not clearly decrease on later opportunities</H2>
        <Text><strong>We follow the same seven players who received the pull.</strong> A second or later possession counts only if the original lineup has stayed together. Once any player is replaced, we stop counting that line's possessions for the rest of the point. Completed possessions before the change still count; an interrupted possession is not recorded as a scoring failure.</Text>
        <Text><strong>What the denominator means:</strong> {number(rawScore[0].sum)} of {number(rawScore[0].n)} first possessions score ({pct(rawScore[0].estimate)}). Among teams that reach a second possession, {number(rawScore[1].sum)} of {number(rawScore[1].n)} second possessions score ({pct(rawScore[1].estimate)}). Each denominator contains possessions ending in a goal or turnover. Teams that are broken before recovering the disc cannot contribute a second possession.</Text>
        <Text>Combining second and all later possessions gives {pct(DATA.league.scoring.first_vs_all_subsequent.groups[1].estimate)} ({number(DATA.league.scoring.first_vs_all_subsequent.groups[1].sum)}/{number(DATA.league.scoring.first_vs_all_subsequent.groups[1].n)}). These are conditional scoring chances after reaching that possession, not the share of all receiving points that score later. Individual teams can differ from the league average.</Text>
        <Text>Later possessions often start closer to the goal. Accounting for starting location and recorded game context gives scoring estimates of {pct(DATA.adjusted.scoring.groups[0].estimate)} on first possessions and {pct(DATA.adjusted.scoring.groups[1].estimate)} on second possessions.</Text>
        <label style={{display:"grid",gap:6,maxWidth:400}}><span>Scoring comparison</span><Select value={scoringView} onChange={setScoringView} options={[{value:"observed",label:"Observed rates — what happened"},{value:"adjusted",label:"Adjusted rates — comparable recorded context"}]}/></label>
        <SingleChart groups={scoreGroups} label={scoringView==="observed"?"Observed scoring rate":"Adjusted scoring estimate"} yLabel={scoringView==="observed"?"Possessions scoring (%)":"Adjusted scoring estimate (%)"} max={100}/>
        <Text>The adjusted first-to-second change is <strong>{signed(100*DATA.adjusted.scoring.differences[0].difference)} percentage points</strong>, with a 95% range from {range(DATA.adjusted.scoring.differences[0].ci95,100)}. That range includes both a decrease and an increase. The first-to-third-or-later change is {signed(100*DATA.adjusted.scoring.differences[1].difference)} points, with a wider range from {range(DATA.adjusted.scoring.differences[1].ci95,100)}. Neither comparison establishes a scoring decline. Individual team patterns are shown below.</Text>
        <Text size="small" tone="secondary">{SCORING_SOURCE} Near-goal starts retained. The denominator contains {number(lineScore.scope.resolved)} completed original-line possessions. Another {number(lineScore.scope.period_end)} end with the period and are reported separately. This check uses recorded lineups; it cannot confirm substitutions missing from the source.</Text>
        <details><summary>Lineup exclusions, scoring counts and starting field areas</summary><Stack gap={12} style={{marginTop:14}}>
          <Text>The earlier chart removed possessions containing a timeout, but could still include a replacement line on the next possession. We now check every recorded lineup update from the start of the point through each possession's end, including substitutions during injuries. Which team called the timeout does not determine eligibility.</Text>
          <Table headers={["Possession","Removed from the earlier scoring sample","Recorded personnel changes","Uncertain or contradictory lineup records"]} rows={lineScore.scope.removed_by_stage.map((g:any)=>[names[g.stage-1],number(g.n),number(g.line_change_n),number(g.n-g.line_change_n)])} columnAlign={["left","right","right","right"]}/>
          <Text size="small">Possessions containing a timeout remain excluded under the existing main filter. A prior timeout without a personnel change does not automatically remove the next possession. We retain original possession numbers and do not remove an opening possession because its players were replaced later.</Text>
          <Counts groups={rawScore} denominator="resolved possessions"/>
          <Text>Each row below compares starts within the same broad area. These are raw within-area rates, not model estimates. Near-goal regains are common and must stay in the scoring analysis.</Text>
          <Table headers={["Yards from starting location to goal line","First: goals / possessions","Second: goals / possessions","Third or later: goals / possessions"]}
            rows={DATA.start_band_rows.map((r:any)=>[r.label,...r.groups.map((g:any)=>g?`${pct(g.rate)} (${g.goals}/${g.n})`:"—")])} columnAlign={["left","right","right","right"]}/>
          <Text size="small">Location is the first recorded throwing or stall location, which may follow movement or a penalty after gaining the disc. The adjusted model uses {number(lineScore.scope.model_n)} possessions and omits {number(lineScore.scope.model_missing_context)} with missing context. The alternate calculation counting period endings as no-goal gives {DATA.sensitivity.period_end_as_no_goal.groups.map((g:Estimate)=>pct(g.estimate||0)).join(", ")} for first, second, and third or later.</Text>
        </Stack></details>
      </Stack>
    </section>

    <section id="huck-attempts" style={sectionStyle}>
      <Stack gap={14}>
        <H2>Huck attempt percentage: first versus second possession</H2>
        <Text><strong>Huck attempts ÷ all throw attempts × 100.</strong> For example, 6 hucks among 100 passes gives a 6% huck attempt percentage. Completed and incomplete passes both count. We add up the team's throws; we do not average its players' percentages.</Text>
        <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(min(100%,300px),1fr))",gap:18}}>
          <label style={{display:"grid",gap:6}}><span>Huck comparison starting locations</span><Select value={hapScope} onChange={setHapScope} options={[{value:"long_field",label:"At least 60 yards from goal"},{value:"all_starts",label:"All starting locations"}]}/></label>
          <label style={{display:"grid",gap:6}}><span>Huck comparison team</span><Select value={hapTeamId} onChange={setHapTeamId} options={[{value:"league",label:"League total"},...hapTeams.map((t:any)=>({value:t.team,label:t.team_name}))]}/></label>
        </div>
        <H2>{hapName}: huck attempt percentage</H2>
        <Text>{hapScope==="long_field"?"Only possessions starting at least 60 yards from the attacking goal line are included. Both groups have a long field to cover, although their exact starting locations still differ.":"All starting locations are included. Second possessions can begin much closer to the attacking goal, leaving less room to huck."} First is the opening opportunity after the pull; second is the same O-line's next opportunity after losing the disc and getting it back. Third and later possessions are not included in these two bars.</Text>
        <div data-hap-chart="true" data-hap-team={hapTeamId} data-hap-scope={hapScope}><SingleChart groups={hapGroups} label="Huck attempt percentage" yLabel="Huck attempt percentage (%)" xLabel="O-line possession within the same point" max={20}/></div>
        <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(min(100%,260px),1fr))",gap:18}}>
          {hapGroups.map((g:any)=><Text key={g.stage}><strong>{names[g.stage-1]}: {number(g.sum)} hucks / {number(g.n)} throws</strong><br/>{number(g.possessions)} possessions across {g.games} games</Text>)}
        </div>
        <Text><strong>Second minus first: {signed(100*hapChange.difference)} percentage points.</strong> The 95% uncertainty range is {range(hapChange.ci95,100)} points. {hapChange.ci95[0]<=0&&hapChange.ci95[1]>=0?"That range includes no difference.":"This is an observed difference, before accounting for the remaining differences in field position and play context."}</Text>
        <Text><strong>Centering passes are included.</strong> This follows the all-throw-attempt definition, so an opening setup pass adds to the denominator and can lower the first-possession percentage. Subtracting confirmed centering passes would answer a separate question about attacking throws; we have not applied that adjustment across the league.</Text>
        <Text size="small" tone="secondary">{HAP_SOURCE} Huck: over 40 yards in distance and over 30 yards forward, using Braden's ShownSpace equation. Percentages describe original O-line possessions in this research sample, not all of a team's offense.</Text>
        <details><summary>Compare all 22 teams</summary><Stack gap={12} style={{marginTop:14}}>
          <Text>{hapScope==="long_field"?"Starts at least 60 yards from goal":"All starting locations"} · first versus exactly second possession · counts are hucks / throw attempts.</Text>
          <div data-hap-team-table="true"><Table headers={["Team","First % (hucks / throws)","Second % (hucks / throws)","Change (pp)","95% range (pp)"]} rows={hapTeams.map((t:any)=>{const gs=t.observed.groups;const c=t.observed.differences[0];return [t.team_name,...gs.slice(0,2).map((g:any)=>`${pct(g.estimate)} (${number(g.sum)} / ${number(g.n)})`),signed(100*c.difference),range(c.ci95,100)];})} columnAlign={["left","right","right","right","right"]}/></div>
          <Text size="small">Teams are listed alphabetically. Small second-possession samples can produce large changes. These are individual uncertainty ranges, not proof of differences across all 22 teams. Chicago and Pittsburgh have 11 available games; the other teams have 12.</Text>
        </Stack></details>
        <details><summary>What counts, and how to read this measure</summary><Stack gap={12} style={{marginTop:14}}>
          <Text>We retain every physical pass by the original seven before their first recorded personnel change or uncertain lineup record. If a timeout changes the lineup during a possession, the original players' earlier throws still count; the replacement players' throws do not. A timeout with the same seven does not remove their attempts.</Text>
          <Text>Throws before a period ends also count. Pulls, stalls and other actions without a throw do not. This differs from possession scoring rate, which needs a resolved possession and retains the earlier within-possession timeout exclusion.</Text>
          <Text>Starting position is the original first recorded throwing location, before any centering pass. This is a proxy for where the possession begins. The opening baseline includes all eligible openings, including those that score immediately and never have a second possession.</Text>
          <Text>A higher huck attempt percentage means a larger share of passes are hucks. It does not tell us whether hucks occur earlier, whether more possessions contain a huck, or whether those hucks are completed. A possession with fewer short passes can have a larger huck percentage even if its number of hucks stays the same.</Text>
          <Text size="small">Uncertainty is calculated by resampling whole games 10,000 times, preserving the first-versus-second comparison within each sampled game. These observed rates need no completion-probability model. The calculation also preserves checks excluding timeout-containing and period-ending possessions. The saved database snapshot is dated October 12, 2026; no live refresh is claimed. <a href="https://shownspace.com/about" style={linkStyle}>ShownSpace's metric catalog</a> supplies the HAP% formula.</Text>
        </Stack></details>
      </Stack>
    </section>

    <section id="teams" style={sectionStyle}>
      <Stack gap={12}>
        <H2>4. How the playoff teams vary</H2>
        <Text>The default view shows the 12 teams that qualified for the 2026 playoffs. Their tendencies are measured during the regular season against all opponents. Scoring and huck attempt percentage use the original-seven check; other measures retain their earlier filters. The selector below also includes all 22 teams. Membership agrees with the <a href={DATA.follow_up.playoff_source.url} style={linkStyle}>official UFA playoff list</a> and the database's playoff games.</Text>
        <Text>All 12 playoff teams use fewer throws on goal-ending subsequent possessions in the earlier observed analysis, but the size varies. The scoring views below have been recalculated after checking personnel continuity. The first-to-subsequent comparison combines second and later possessions; observed rates still reflect differences in starting field position.</Text>
        <Text>The strongest evidence of differences across teams is in early hucking after a regain. The overall team-difference test remains detectable after checking six measures. Individual team estimates are less settled: qualifying regain samples can be small, and the table is a starting point for scouting, not a ranking of proven tendencies.</Text>
        <Text>Among playoff teams, DC's early-huck rate rises from 9.3% (23/247) to 30.3% (10/33) after regains, while Seattle's falls from 14.9% (36/241) to 6.9% (2/29). These are observed patterns with small regain samples, not established differences in long-term team ability.</Text>
        <label style={{display:"grid",gap:6,maxWidth:400}}><span>Teams shown</span><Select value={teamPool} onChange={value=>{setTeamPool(value);if(value==="playoffs"&&!DATA.follow_up.playoff_team_ids.includes(teamId))setTeamId("spiders");}} options={[{value:"playoffs",label:"2026 playoff teams (12)"},{value:"all",label:"All 2026 teams (22)"}]}/></label>
        <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(min(100%,300px),1fr))",gap:18}}>
          <label style={{display:"grid",gap:6}}><span>Measure</span><Select value={metric} onChange={setMetric} options={Object.entries(metrics).map(([value,s])=>({value,label:s.label}))}/></label>
          <label style={{display:"grid",gap:6}}><span>Team (chart only)</span><Select value={team.team} onChange={setTeamId} options={teams.map((t:any)=>({value:t.team,label:t.team_name}))}/></label>
        </div>
        <H2>{team.team_name}: {spec.label.toLowerCase()}</H2>
        <Text>{spec.explain}</Text>
        <div data-selected-team-chart={team.team} data-selected-metric={metric}><SingleChart groups={team.metrics[metric].groups} label={spec.label} yLabel={spec.count?"Mean number of throws":metric==="huck_share"?"Huck attempt percentage (%)":metric==="huck_completion"?"Huck completion percentage (%)":metric==="break_after_turnover"?"Turnovers followed by a break (%)":"Possessions (%)"} count={spec.count} max={spec.count?undefined:metric==="huck_share"?30:metric==="early_huck"?60:100}/></div>
        <Text>{modeled?"Adjusting for recorded context, this":"In the observed data, this"} team's change from first to <strong>all subsequent possessions combined</strong> is {signed(change.difference*(spec.count?1:100))} {spec.count?"throws":"percentage points"}{changeInterval?` (95% range ${range(changeInterval,spec.count?1:100)})`:"; no uncertainty range is shown because one group has only successes or only failures"}. That estimate uses {number(change.subsequent_n)} subsequent {spec.denominator} across {change.games} games.</Text>
        <Text size="small" tone="secondary">{metric==="scoring"?SCORING_SOURCE:metric==="huck_share"?HAP_SOURCE:SOURCE} Bars are observed values. The change combines second and later possessions to avoid splitting already-small team samples. {modeled?(metric==="scoring"?"The scoring model was refitted using eligible original-line possessions from all 22 teams.":"The original model includes all 22 teams; changing this view does not refit the model or remove centering passes."):"This comparison uses observed rates and whole-game bootstrap ranges; it is not adjusted for context."}</Text>
        <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(min(100%,300px),1fr))",gap:18}}>
          <label style={{display:"grid",gap:6}}><span>Table measure</span><Select value={metric} onChange={setMetric} options={Object.entries(metrics).map(([value,s])=>({value,label:s.label}))}/></label>
          <label style={{display:"grid",gap:6}}><span>Possession shown in tables</span><Select value={tablePossession} onChange={setTablePossession} options={[{value:"1",label:"First possession"},{value:"2",label:"Second possession"},{value:"3",label:"Third possession"},{value:"all",label:"Compare first, second and third or later"}]}/></label>
        </div>
        <Text size="small">Compare every team in the table below. Table measure also updates the chart above; the chart's team selector does not limit the table. Third possession means exactly the third opportunity. The comparison option uses third or later.</Text>
        <Text weight="semibold">{teamPool==="playoffs"?"12 playoff teams":"All 22 teams"} · {tableStageLabel} · {spec.label.toLowerCase()}</Text>
        <Text size="small">Each rate or mean is followed by its number of {spec.denominator} in parentheses. {tablePossession==="all"?`The last column compares first with all subsequent possessions ${modeled?"after context adjustment":"without adjustment"}; pp means percentage points. A range crossing zero includes no change.`:"Values are observed, without adjustment for field position. The uncertainty range is based on resampling games; an interval is not shown for an exact-third estimate from fewer than two games."} {!spec.count?"A dash also replaces a resampling range when a group contains only successes or only failures; a few identical results do not establish a certain 0% or 100% rate.":""}</Text>
        <Text size="small">Click a column heading's arrow to switch between high to low and low to high. The Team arrow sorts alphabetically. Values are sorted before rounding; missing results stay at the bottom. <strong>n</strong> is the sample size shown in parentheses.</Text>
        <div data-team-table="true" data-possession-filter={tablePossession} data-measure={metric}><SortableTeamTable rows={teams} columns={tableColumns} label={`Team comparison: ${tableStageLabel}, ${spec.label}`}/></div>
        <details><summary>What does the 95% uncertainty range mean?</summary><Stack gap={12} style={{marginTop:14}}>
          <Text>It shows how precisely we can estimate a team's average or percentage from the games available. For example, an estimated mean of 10 throws with a range of 8–12 is less precise than the same mean with a range of 9.5–10.5. These are illustrative numbers, not additional team results.</Text>
          <Text>For the observed team values, we repeatedly draw whole games from the available games, allowing a game to be drawn more than once, and recalculate the statistic 10,000 times. The middle 95% of those recalculated values forms this approximate confidence interval. Keeping each game together preserves the relationship among its possessions.</Text>
          <Text>The 95% refers to the method: across repeated comparable samples, intervals made this way are intended to contain the underlying average or rate about 95% of the time, when the assumptions hold. It does not mean 95% of a team's possessions fall inside the range, or that the next game will fall inside it. With only 11–12 games per team, these ranges remain approximate.</Text>
          <Text>For a change between possessions, a range that includes zero leaves both no change and changes in either direction plausible. The adjusted-change column uses the context model's uncertainty calculation, with observations grouped by game, rather than the resampling calculation. Neither method removes unmeasured differences such as receiver openness, and sorting teams does not prove that their underlying tendencies differ.</Text>
          <Text size="small"><a href="https://www.itl.nist.gov/div898/handbook/prc/section1/prc14.htm" style={linkStyle}>NIST: interpreting confidence intervals</a>.</Text>
        </Stack></details>
        <details><summary>Huck attempt percentage versus possessions with a huck</summary><Stack gap={12} style={{marginTop:14}}>
          <Text><strong>Huck attempt percentage:</strong> huck attempts ÷ throw attempts. <strong>Possessions with a huck:</strong> possessions containing at least one huck ÷ possessions. <strong>Huck completion percentage:</strong> completed hucks ÷ huck attempts.</Text>
          <Text>For example, suppose 10 possessions contain 100 throws, including 5 hucks in 4 different possessions. Huck attempt percentage is 5%; possessions with a huck is 40%. Both describe hucking, but they answer different questions. This example holds the sample fixed; our saved measures also have different eligibility rules, shown in their descriptions.</Text>
        </Stack></details>
        <Text size="small" tone="secondary">{metric==="scoring"?SCORING_SOURCE:metric==="huck_share"?HAP_SOURCE:SOURCE} * Chicago and Pittsburgh have 11 available games; other teams have 12. A dash with (0) means there are no qualifying observations. Third-possession samples can be very small. These 95% ranges are individual intervals, not simultaneous guarantees across all teams. Updated scoring and huck-attempt contrasts are exploratory; the earlier multi-measure tests do not apply to these revised samples.</Text>
        <details><summary>Team statistics across measures</summary><Stack gap={12} style={{marginTop:14}}>
          <Text weight="semibold">{teamPool==="playoffs"?"12 playoff teams":"All 22 teams"} · {tablePossession==="all"?"First versus all subsequent possessions":tableStageLabel}</Text>
          <Text>{tablePossession==="all"?"Each cell reads first → subsequent, with sample sizes in parentheses. Subsequent combines the second and all later possessions.":`Each cell shows ${tableStageLabel.toLowerCase()} statistics, with sample sizes in parentheses.`} These are observed means and rates. Scoring uses the updated original-seven filter; other measures retain their earlier samples. Goal and turnover throw counts keep all starting locations; early-huck rates use starts at least 40 yards from the attacking goal line.</Text>
          <Text size="small">Use the column arrows to sort each measure. {tablePossession==="all"?"In this first → subsequent view, sorting uses the subsequent value on the right of the arrow.":"Sorting uses the selected possession's value."}</Text>
          <div data-playoff-summary="true" data-possession-filter={tablePossession}><SortableTeamTable rows={teams} columns={summaryColumns} label={`Team statistics across measures: ${tableStageLabel}`}/></div>
          <Text size="small" tone="secondary">The team and possession filters above apply to this table. {tablePossession==="all"?"Select a single possession to see its observed uncertainty ranges in the table above.":"Use the measure selector for the matching uncertainty ranges in the table above."}</Text>
        </Stack></details>
      </Stack>
    </section>

    <section id="huck-outcomes" style={sectionStyle}>
      <Stack gap={12}>
        <H2>5. Huck completion differences remain uncertain</H2>
        <Text>Huck completion percentages are {pct(caught[0].estimate)}, {pct(caught[1].estimate)}, and {pct(caught[2].estimate)} across first, second, and third-or-later possessions. The second-possession rate is lower in this sample, but the difference is too uncertain to conclude that regain hucks are less accurate.</Text>
        <Text size="small">Drops count as incomplete in this chart.</Text>
        <SingleChart groups={caught} label="Huck completion percentage" yLabel="Huck completion %" max={100}/>
        <Text>A completed huck also does not have to be an assist to help the possession. Among resolved possessions containing at least one completed huck, {pct(DATA.scoring_after_completed_huck.groups[0].estimate)} of first and {pct(DATA.scoring_after_completed_huck.groups[1].estimate)} of second possessions eventually score. That is a descriptive result conditional on completing a huck; it is not an estimate of how choosing to huck changes scoring probability.</Text>
        <Text size="small" tone="secondary">{SOURCE} Huck attempts: {caught.map((g:Estimate)=>number(g.n||0)).join(" / ")} across the three stages. Third-or-later completion estimates are especially uncertain.</Text>
        <details><summary>Catch counts, drops, and ShownSpace difficulty measures</summary><Stack gap={12} style={{marginTop:14}}>
          <Counts groups={caught} denominator="huck attempts"/>
          <Table headers={["Team possession","Drops / attempts","Mean recorded CP","Drop-credited CPOE"]} rows={DATA.huck_outcomes.map((h:any)=>[names[h.stage-1],`${h.drops} / ${h.attempts}`,pct(h.mean_cp),signed(h.credited_cpoe_pp)+" pp"])} columnAlign={["left","right","right","right"]}/>
          <Text size="small">For this comparison, drop-credited CPOE is recomputed as mean(caught + recorded drop − CP), in percentage points. This follows Braden's explanation that drops are credited for CPOE; it does not reinterpret stored CPOE=1 values. Huck completion percentage remains separate. No aEC-per-attempt measure is used.</Text>
          <Text size="small">Recorded CP is used as a fitted difficulty-score covariate in the catch model, rather than assumed perfectly calibrated to actual catches. The adjusted second-minus-first catch difference is {signed(100*DATA.adjusted.huck_completion.differences[0].difference)} pp (95% range {range(DATA.adjusted.huck_completion.differences[0].ci95,100)}). Model identity and production training labels are not independently verified; exclusion of 2026 from CP training remains the agreed working assumption.</Text>
        </Stack></details>
      </Stack>
    </section>

    <section id="breaks" style={sectionStyle}>
      <Stack gap={12}>
        <H2>6. After a turnover, how often is the O-line eventually broken?</H2>
        <Text>A possession ending in a turnover does not necessarily mean a break: the receiving team can get the disc back and still hold. This chart follows each turnover through to the end of the same point and asks which team ultimately scores.</Text>
        <SingleChart groups={DATA.follow_up.break_league.groups} label="Eventually broken after this turnover" yLabel="Turnovers followed by a break (%)" xLabel="Team possession that ended in a turnover" max={100}/>
        <Text>After a first-possession turnover, {pct(DATA.follow_up.break_league.groups[0].estimate)} of resolved points end in a break ({number(DATA.follow_up.break_league.groups[0].sum)}/{number(DATA.follow_up.break_league.groups[0].n)}). The corresponding rate after a second-possession turnover is {pct(DATA.follow_up.break_league.groups[1].estimate)} ({number(DATA.follow_up.break_league.groups[1].sum)}/{number(DATA.follow_up.break_league.groups[1].n)}). Combining second and all later turnovers gives {pct(DATA.follow_up.break_league.first_vs_all_subsequent.groups[1].estimate)}. The first-to-second difference is uncertain; this is not evidence of a steady increase after every turnover.</Text>
        <Text>The third-or-later rate is {pct(DATA.follow_up.break_league.groups[2].estimate)}, based on only {number(DATA.follow_up.break_league.groups[2].n)} turnovers in resolved points. This is an exploratory association and is not adjusted for where the turnover occurred or other game context.</Text>
        <Text size="small" tone="secondary">{SOURCE} Each observation is a receiving-team turnover. The turnover possession must be free of recorded timeouts; the rest of that point is then followed to its outcome. Period-ending points are excluded from the displayed rates. A point with repeated turnovers can contribute more than once; intervals resample whole games.</Text>
        <details><summary>Immediate breaks, later breaks, and holds after a recovery</summary><Stack gap={12} style={{marginTop:14}}>
          <Counts groups={DATA.follow_up.break_league.groups} denominator="turnovers in resolved points"/>
          <Table headers={["Possession ending in turnover","Broken before another regain","Regain, then eventually broken","Recover and hold","Period-ended; excluded"]} rows={DATA.follow_up.break_outcome_counts.map((r:any)=>[names[r.stage-1],`${r.break_before_regain} / ${r.resolved_points}`,`${r.regain_then_break} / ${r.resolved_points}`,`${r.eventual_hold} / ${r.resolved_points}`,String(r.period_ending_points)])} columnAlign={["left","right","right","right","right"]}/>
          <Text size="small">The first three outcome columns add to the resolved-point denominator. An opponent goal immediately following the turnover and a break after several further exchanges are distinguished here. The team selector includes this break measure for all teams and playoff teams.</Text>
        </Stack></details>
      </Stack>
    </section>

    <section id="paper" style={sectionStyle}>
      <Stack gap={12}>
        <H2>A clearer research direction</H2>
        <Text><strong>Question:</strong> After turning the disc over and getting it back, does an O-line change how it attacks, and how do its chances of scoring compare with its opening opportunity?</Text>
        <Text><strong>Working finding:</strong> Second possessions involve fewer passing actions, even after accounting for recorded field and game context. The evidence does not show a corresponding decrease in possession scoring. The early-huck estimates are parked and are not part of the current working finding.</Text>
        <Text><strong>What remains unresolved:</strong> We need to review which starting locations offer a useful first-versus-later comparison and how to identify opening centering passes. The saved huck calculations remain available for that review. These observations do not establish fatigue or impatience as the cause of a change.</Text>
        <Text><strong>Use for coaches:</strong> Compare how many passes your team needs on its opening and later opportunities, separately for possessions ending in goals and turnovers. Use scoring, break outcomes and sample sizes to choose situations for film review. Revisit early deep looks after resolving the starting-location and setup-pass questions.</Text>
        <details><summary>Secondary check about earlier activity, separate from possession length</summary><Stack gap={12} style={{marginTop:14}}>
          <Text>This was an additional question: after a 15-throw failed possession, does a team huck early more often than after a five-throw failed possession? It is separate from the main comparison of how many throws first and subsequent possessions contain.</Text>
          <Text>Within subsequent eligible possessions, more prior own-team throws are not clearly associated with early hucking. The adjusted odds ratio for doubling (1 + the prior throw count) is {DATA.prior_activity.prior_own_throws.odds_ratio_for_doubling_one_plus_count.toFixed(2)} (95% range {range(DATA.prior_activity.prior_own_throws.or_ci95)}). A value of 1 means no estimated change in odds.</Text>
          <Table headers={["Earlier own-team throws in the point","Early-huck possessions / eligible regains","Early-huck rate"]} rows={DATA.prior_activity.observed_bands.map((b:any)=>[b.band,`${b.early_hucks} / ${b.n}`,pct(b.rate)])} columnAlign={["left","right","right"]}/>
          <Text size="small">The last band has only 20 possessions. Prior activity means throws before this possession began; it does not use the current possession's eventual length. A separate both-teams activity check is also uncertain and has verified coverage for only {DATA.prior_activity.prior_total_throws.n} of {DATA.prior_activity.prior_total_throws.n+DATA.prior_activity.prior_total_throws.missing} eligible regained possessions.</Text>
        </Stack></details>
      </Stack>
    </section>

    <section id="methods" style={sectionStyle}>
      <details><summary style={{fontSize:19,fontWeight:600}}>Definitions, sensitivity checks, and sources</summary><Stack gap={14} style={{marginTop:16}}>
        <Text><strong>Scope and denominators.</strong> The original analysis uses receiving-team role, which alone does not establish unchanged personnel. Of {number(DATA.audit.source_receiving_points)} raw receiving-point starts, {number(DATA.audit.included_points)} pass sequence checks. These contain {number(DATA.audit.possessions)} possessions before removing {DATA.scope.timeout_possessions_excluded} with timeout markers. After removal, {number(DATA.scope.possessions)} remain. The updated scoring comparison additionally follows the original seven and retains {number(lineScore.scope.resolved)} completed possessions; its exclusions are shown in section 3. Numbering is preserved. Third and later opportunities are grouped in the charts; the exact-third team table remains available.</Text>
        <Text><strong>Huck definition.</strong> More than 40 yards in straight-line distance and more than 30 yards of forward gain, matching Braden's equation as confirmed by Teddy. The new huck attempt percentage comparison offers starts at least 60 yards from goal or all starts. The earlier huck analyses use a first throwing location at least 40 yards from goal. Neither cutoff exactly matches field positions. The early-huck comparison is parked pending review of starting locations and setup throws. Scoring and throw-count comparisons retain starts near the end zone.</Text>
        <Text><strong>What adjustment means.</strong> Binomial models estimate scoring and huck probabilities; Poisson mean models estimate throw counts, with uncertainty clustered by game. Starting longitudinal and lateral location, team, opponent, quarter, and the recorded time at the start of the point are included. The latter is not the time at the start of each subsequent possession. Current throwing location is also included in the per-throw huck model. Estimated stages are compared using a common recorded context mix.</Text>
        <Text><strong>Uncertainty and multiple comparisons.</strong> Observed ranges use 10,000 whole-game bootstrap samples. Adjusted ranges use game-cluster covariance; within-team tests use the team's game count for a conservative t reference. The original analysis applied Holm corrections to 16 league comparisons, six team-difference tests, and 132 individual team-by-measure contrasts. Those original corrections do not cover the revised scoring contrasts, which remain exploratory. The updated scoring file includes a separate Holm correction across its 22 team contrasts; displayed 95% ranges remain individual intervals. Ranges and changes matter more than a cutoff: a p-value is not the probability that a hypothesis is true.</Text>
        <Text><strong>Earlier checks against alternative choices.</strong> The table preserves the earlier sample and reports first-to-all-subsequent differences. It has not been recalculated with the new original-seven huck-attempt filter. In that earlier analysis, the huck and throw-count direction persists when changing the huck definition, starting-location cutoff, or disrupted-point exclusions.</Text>
        <Table headers={["Alternative analysis","Early huck change (pp)","Huck share change (pp)","Goal-possession throw change"]} rows={DATA.sensitivity_rows.map((r:any)=>[r.label,signed(r.early_huck*100),signed(r.huck_share*100),signed(r.throws_goal)])} columnAlign={["left","right","right","right"]}/>
        <Text size="small">The earlier within-game and common-starting-region sensitivity models remain archived in results.json and have not been refitted for the revised lineup sample. Current scoring counts, context-adjusted estimates, period-ending checks and timeout sensitivity calculations are saved separately in original_line_scoring.json.</Text>
        <Text><strong>Source limits.</strong> Pittsburgh at Chicago on July 18, 2026 is missing. Twenty-nine receiving points fail sequence/source checks. Four games have at least one raw event stream that disagrees with the final score; valid points are retained, and excluding those games is a sensitivity check. Zero-throw outcomes are retained; unknown starting locations are omitted from location-adjusted models. Setup passes have not been automatically labeled across the league.</Text>
        <Text><strong>Interpretation limits.</strong> Subsequent possessions necessarily follow turnovers and recovery, while the opening baseline includes all eligible receiving points. Restricting openings to points that later regain would select opening failures and invalidate a scoring baseline. Scoring now excludes recorded personnel changes, but this cannot rule out unrecorded substitutions or incorrect lineup records. Field adjustment cannot account for receiver openness, defensive force, wind or intent. This is an exploratory observational study, not a causal test or a preregistered confirmation.</Text>
        <Text size="small">Sources: local ShownSpace export preserved October 12, 2026, with file hashes checked; archived UFA raw events with capture receipts and hashes; <a href="https://www.docs.ufastats.com/events" style={linkStyle}>UFA event definitions</a>. No live database refresh is claimed. Reproducible cohort, analysis specification, aggregate results, and validation are saved under research/oline_possessions. The earlier unrestricted huck snapshot remains in research/huck_timing_study/oline_regains; its denominators differ from this expanded comparison.</Text>
      </Stack></details>
    </section>
  </Stack>;
}
'''

def main():
    result = json.loads((ROOT/'results.json').read_text())
    possession_path = ROOT/'possessions.csv'
    possession_hash = hashlib.sha256(possession_path.read_bytes()).hexdigest()
    assert possession_hash == result['inputs']['possessions.csv'], 'Possession rows no longer match the reviewed results.'
    with possession_path.open(newline='') as handle:
        rows = [r for r in csv.DictReader(handle) if r['has_timeout']=='False' and r['first_y']]
    start_groups = []
    for stage in (1,2,3):
        group = [r for r in rows if int(r['stage'])==stage]
        eligible = [r for r in group if float(r['first_y'])<=60]
        original = result['league']['early_huck']['groups'][stage-1]
        assert len(eligible)==original['n'] and sum(int(r['early_huck']) for r in eligible)==original['sum']
        hucks = sum(int(r['has_huck']) for r in group)
        start_groups.append({'stage':stage, 'known_location_n':len(group),
            'near_goal_n':len(group)-len(eligible), 'any_huck_n':hucks, 'any_huck_rate':hucks/len(group)})
    result['huck_starting_location_review'] = {'groups':start_groups,
        'source':'possessions.csv', 'source_sha256':possession_hash, 'reviewed_on':'2026-11-10',
        'definition':'No recorded timeout; known first throwing location. Any huck counts at most once per possession, with no throw-number restriction. Near goal means first_y >60, less than 40 yards from the attacking goal line.'}
    result['follow_up'] = json.loads((ROOT/'follow_up_20261106.json').read_text())
    result['possession_filters'] = json.loads((ROOT/'possession_filters.json').read_text())
    for name,digest in result['possession_filters']['inputs'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest, 'Re-run possession_filters.py after changing its inputs.'
    assert result['follow_up']['inputs']['results.json']==hashlib.sha256((ROOT/'results.json').read_bytes()).hexdigest(), 'Re-run follow_up.py after changing the main results.'
    for team in result['teams']:
        team['metrics']['break_after_turnover']=next(x for x in result['follow_up']['break_teams'] if x['team']==team['team'])
        team['exact_metrics']=next(x for x in result['possession_filters']['teams'] if x['team']==team['team'])['metrics']
    scoring = json.loads((ROOT/'original_line_scoring.json').read_text())
    for source in scoring['inputs'].values():
        assert hashlib.sha256((ROOT.parents[1]/source['path']).read_bytes()).hexdigest() == source['sha256'], 'Re-run original_line_scoring.py after changing its inputs.'
    assert scoring['validation']['passed']
    result['original_line_scoring'] = {k:v for k,v in scoring.items() if k not in {'rows','teams','rawGameHashes','observed','adjusted','team_changes','scoring_by_start','sensitivity'}}
    result['league']['scoring'] = scoring['observed']
    result['adjusted']['scoring'] = scoring['adjusted']
    result['team_changes']['scoring'] = scoring['team_changes']
    result['scoring_by_start'] = scoring['scoring_by_start']
    result['sensitivity']['period_end_as_no_goal'] = scoring['sensitivity']['period_end_as_no_goal']
    for team in result['teams']:
        revised = next(t for t in scoring['teams'] if t['team']==team['team'])
        team['metrics']['scoring'] = revised['observed']
        team['exact_metrics']['scoring'] = revised['exact']
    hap = json.loads((ROOT/'huck_attempt_percentage.json').read_text())
    for source in hap['inputs'].values():
        assert hashlib.sha256((ROOT.parents[1]/source['path']).read_bytes()).hexdigest() == source['sha256'], 'Re-run huck_attempt_percentage.py after changing its inputs.'
    assert hap['validation']['passed']
    result['huck_attempt_percentage'] = {k:v for k,v in hap.items() if k != 'game_counts'}
    result['league']['huck_share'] = hap['scopes']['long_field']['league']
    result['team_changes'].pop('huck_share', None)
    for team in result['teams']:
        revised = next(t for t in hap['scopes']['long_field']['teams'] if t['team']==team['team'])
        team['metrics']['huck_share'] = revised['observed']
        team['exact_metrics']['huck_share'] = revised['exact']
    result['audit'] = json.loads((ROOT/'cohort_audit.json').read_text())
    centering_path = ROOT / 'reviewed_centering_counts.json'
    result['reviewed_centering_counts'] = json.loads(centering_path.read_text())
    assert [g['stage'] for g in result['reviewed_centering_counts']['groups']['goal']] == [g['stage'] for g in result['reviewed_centering_counts']['groups']['turnover']], 'Align outcome groups before drawing the paired bars; missing outcomes are not zero.'
    for source in result['reviewed_centering_counts']['inputs'].values():
        assert hashlib.sha256((ROOT.parents[1] / source['path']).read_bytes()).hexdigest() == source['sha256'], 'Re-run reviewed_centering_counts.py after changing its inputs.'
    labels = {'all_possessions_including_timeouts':'Keep timeout possessions',
      'exclude_whole_timeout_or_injury_points':'Remove whole points with timeouts/injuries',
      'exclude_four_score_discrepancy_games':'Remove four score-discrepancy games',
      'huck_start_y_at_most_50':'Require at least 50 yards to goal',
      'huck_start_y_at_most_70':'Require at least 30 yards to goal',
      'hucks_all_start_locations':'Allow all starting locations',
      'huck_over_40_forward_yards':'Define huck as over 40 forward yards'}
    result['sensitivity_rows']=[{'label':label,**{metric:result['sensitivity'][key][metric]['differences'][0]['difference']
        for metric in ['early_huck','huck_share','throws_goal']}} for key,label in labels.items()]
    bands=[('Own end zone: 0–20','80–100 yd'),('Deep own half: 20–40','60–<80 yd'),
           ('To midfield: 40–60','40–<60 yd'),('Attacking half: 60–80','20–<40 yd'),
           ('Near goal: 80–120','Under 20 yd or in end zone')]
    result['start_band_rows']=[{'label':label,'groups':[next((g for g in result['scoring_by_start']
       if g['band']==band and g['stage']==s),None) for s in [1,2,3]]} for band,label in bands]
    data=json.dumps(result,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    source='import { BarChart, H1, H2, Select, Stack, Table, Text, useHostTheme, useState } from "cursor/canvas";\n\nconst DATA: any = '+data+';\n'+BODY
    CANVAS.write_text(source)
    print(str(CANVAS))

if __name__=='__main__':main()
