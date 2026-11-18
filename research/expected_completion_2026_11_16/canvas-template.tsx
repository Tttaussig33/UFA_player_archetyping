import { H1, H2, Text, Stack, Select, Table, useState, useHostTheme } from "cursor/canvas";

const DATA: any = __REVIEWED_DATA__;
const fmt = (v: any, places = 1) => v == null ? "—" : Number(v).toFixed(places);
const sign = (v: any) => v == null ? "—" : (v > 0 ? "+" : "") + fmt(v);
const count = (v: number) => v.toLocaleString();
const range = (v: any, places = 1) => v ? fmt(v[0],places) + " to " + fmt(v[1],places) : "Too few games for a range";
const markedName = (row: any) => row.team_name + (row.inference.nominal_excludes_zero ? " *" : "");
const significanceStatus = (row: any) => !row.inference.estimable ? "Insufficient data" : row.inference.bonferroni_excludes_zero ? "Significant after correction" : row.inference.nominal_excludes_zero ? "Significant, unadjusted only" : "Not significant";
const orderedTeams = (rows: any[], sort: string) => [...rows].sort((a:any,b:any) => {
  const difference = sort === "aec_desc" ? b.total_aec-a.total_aec : sort === "aec_asc" ? a.total_aec-b.total_aec : sort === "change" ? a.change_pp-b.change_pp : 0;
  return difference || a.team_name.localeCompare(b.team_name);
});

function Legend() {
  const t = useHostTheme();
  return <div style={{display:"flex",gap:24,flexWrap:"wrap",fontSize:14}}>
    <span style={{color:t.text.secondary}}>● First possession · after the pull</span>
    <span style={{color:t.accent.primary}}>■ Second possession · after both teams turn it over</span>
  </div>;
}

function Progression({row, limit, uncertainty}: any) {
  const t = useHostTheme();
  const series = row.stages.map((s: any) => s.series.slice(0, limit));
  const values = series.flatMap((s: any) => s.flatMap((p: any) => p.xcp == null ? [] : (uncertainty && p.ci95 ? p.ci95 : [p.xcp])));
  const lo = Math.max(0, Math.min(90, 5 * Math.floor((Math.min(...values) - 2) / 5)));
  const ticks = Array.from({length: Math.round((100-lo)/5)+1}, (_, i) => lo + 5*i);
  const left=80, right=1000, top=30, bottom=340;
  const X = (n: number) => left+(n-1)/(limit-1)*(right-left);
  const Y = (v: number) => bottom-(v-lo)/(100-lo)*(bottom-top);
  return <div style={{overflowX:"auto"}}>
    <svg role="img" aria-label={row.team_name+": mean expected completion probability by recorded throw number in first and second possessions"} viewBox="0 0 1050 420" style={{width:"100%",minWidth:680,display:"block"}}>
      <title>{row.team_name}: expected completion by throw number</title>
      {ticks.map(v => <g key={v}><line x1={left} x2={right} y1={Y(v)} y2={Y(v)} stroke={t.stroke.tertiary}/><text x={left-12} y={Y(v)+4} textAnchor="end" fill={t.text.secondary} fontSize={13}>{v}%</text></g>)}
      {Array.from({length:limit},(_,i)=>i+1).map(n=><g key={n}><line x1={X(n)} x2={X(n)} y1={bottom} y2={bottom+5} stroke={t.text.secondary}/><text x={X(n)} y={bottom+24} textAnchor="middle" fill={t.text.secondary} fontSize={13}>{n}</text></g>)}
      {series.map((s: any, index: number) => {
        const color = index ? t.accent.primary : t.text.secondary;
        return <g key={index}>
          {s.slice(1).map((p: any,i:number)=>p.xcp!=null&&s[i].xcp!=null?<line key={p.ordinal} x1={X(s[i].ordinal)} y1={Y(s[i].xcp)} x2={X(p.ordinal)} y2={Y(p.xcp)} stroke={color} strokeWidth={2.5} strokeDasharray={index?undefined:"6 4"}/>:null)}
          {s.map((p:any)=>p.xcp==null?null:<g key={p.ordinal} data-series={index+1} data-ordinal={p.ordinal} data-value={p.xcp}>
            {uncertainty&&p.ci95?<g opacity={.42}><line x1={X(p.ordinal)} x2={X(p.ordinal)} y1={Y(p.ci95[0])} y2={Y(p.ci95[1])} stroke={color} strokeWidth={2}/><line x1={X(p.ordinal)-5} x2={X(p.ordinal)+5} y1={Y(p.ci95[0])} y2={Y(p.ci95[0])} stroke={color}/><line x1={X(p.ordinal)-5} x2={X(p.ordinal)+5} y1={Y(p.ci95[1])} y2={Y(p.ci95[1])} stroke={color}/></g>:null}
            {index?<rect x={X(p.ordinal)-4.5} y={Y(p.xcp)-4.5} width={9} height={9} fill={color}/>:<circle cx={X(p.ordinal)} cy={Y(p.xcp)} r={4.5} fill={color}/>}
            <title>{(index?"Second":"First")+" possession, throw "+p.ordinal+": "+fmt(p.xcp,2)+"% xCP; "+p.cp_attempts+" throws in "+p.games+" games. 95% range: "+range(p.ci95)}</title>
          </g>)}
        </g>;
      })}
      <text x={(left+right)/2} y={bottom+64} textAnchor="middle" fill={t.text.primary} fontSize={14}>Recorded throw number within the possession</text>
      <text transform="translate(20 185) rotate(-90)" textAnchor="middle" fill={t.text.primary} fontSize={14}>Mean expected completion probability (%)</text>
    </svg>
  </div>;
}

function TeamAverages({rows, selected, onSelect, sort}: any) {
  const t = useHostTheme();
  const ordered = orderedTeams(rows, sort);
  const vals = rows.flatMap((r:any)=>r.stages.map((s:any)=>s.summary.xcp));
  const lo = Math.max(0, Math.floor((Math.min(...vals)-1)/2)*2), hi=Math.min(100,Math.ceil((Math.max(...vals)+1)/2)*2);
  const left=285,right=750,top=42,bottom=top+(ordered.length-1)*33;
  const X=(v:number)=>left+(v-lo)/(hi-lo)*(right-left);
  return <div style={{overflowX:"auto"}}>
    <svg role="img" aria-label="Team average expected completion probability: first versus second possessions" viewBox={"0 0 1050 "+(bottom+100)} style={{width:"100%",minWidth:800,display:"block"}}>
      <text x={0} y={18} fill={t.text.secondary} fontSize={12}>TEAM</text>
      <text x={242} y={18} textAnchor="end" fill={t.text.secondary} fontSize={12}>TOTAL aEC</text>
      <text x={830} y={18} textAnchor="end" fill={t.text.secondary} fontSize={12}>CHANGE (pp)</text>
      <text x={1030} y={18} textAnchor="end" fill={t.text.secondary} fontSize={12}>THROWS (1st / 2nd)</text>
      {Array.from({length:Math.round((hi-lo)/2)+1},(_,i)=>lo+2*i).map(v=><g key={v}><line x1={X(v)} x2={X(v)} y1={top-12} y2={bottom+14} stroke={t.stroke.tertiary}/><text x={X(v)} y={bottom+39} textAnchor="middle" fill={t.text.secondary} fontSize={13}>{v}%</text></g>)}
      {ordered.map((r:any,i:number)=>{const a=r.stages[0].summary,b=r.stages[1].summary,y=top+33*i;return <g key={r.team} role="button" tabIndex={0} data-team={r.team} data-unadjusted-significant={String(r.inference.nominal_excludes_zero)} data-corrected-significant={String(r.inference.bonferroni_excludes_zero)} aria-label={"Show "+r.team_name+" throw-by-throw graph"} onClick={()=>onSelect(r.team)} onKeyDown={(e:any)=>{if(e.key==="Enter"||e.key===" ")onSelect(r.team);}} style={{cursor:"pointer"}}>
        <rect x={0} y={y-14} width={1040} height={30} fill="transparent"/>
        <text x={0} y={y+4} fill={selected===r.team?t.accent.primary:t.text.primary} fontSize={13} fontWeight={selected===r.team?650:450}>{markedName(r)}</text>
        <text x={242} y={y+4} textAnchor="end" fill={t.text.secondary} fontSize={13}>{fmt(r.total_aec,2)}</text>
        <line x1={X(a.xcp)} x2={X(b.xcp)} y1={y} y2={y} stroke={t.stroke.tertiary} strokeWidth={3}/>
        <circle cx={X(a.xcp)} cy={y} r={4.5} fill={t.text.secondary}/>
        <rect x={X(b.xcp)-4.5} y={y-4.5} width={9} height={9} fill={t.accent.primary}/>
        <text x={830} y={y+4} textAnchor="end" fill={t.text.primary} fontSize={13}>{sign(r.change_pp)}</text>
        <text x={1030} y={y+4} textAnchor="end" fill={t.text.secondary} fontSize={13}>{count(a.cp_attempts)+" / "+count(b.cp_attempts)}</text>
        <title>{r.team_name+": "+fmt(a.xcp,2)+"% first, "+fmt(b.xcp,2)+"% second. Difference: "+sign(r.change_pp)+" percentage points; individual 95% range "+range(r.inference.ci95_pp,2)+" pp. "+significanceStatus(r)+". Range after 22-team correction: "+range(r.inference.bonferroni_interval_pp,2)+" pp. ShownSpace 2026 total aEC: "+fmt(r.total_aec,2)+" across "+r.aec_games+" games. Select to inspect above."}</title>
      </g>;})}
      <text x={(left+right)/2} y={bottom+78} textAnchor="middle" fill={t.text.primary} fontSize={14}>Mean expected completion probability (%) · all throws in each possession</text>
    </svg>
  </div>;
}

function TeamDifferenceChart({rows, allRows, sort, onInspect}: any) {
  const t=useHostTheme();
  const ordered=orderedTeams(rows,sort);
  const values=allRows.flatMap((r:any)=>[r.change_pp,...(r.inference.ci95_pp||[])]);
  const lo=5*Math.floor(Math.min(-5,...values)/5),hi=5*Math.ceil(Math.max(5,...values)/5);
  const left=360,right=920,top=64,bottom=top+(ordered.length-1)*36;
  const X=(v:number)=>left+(v-lo)/(hi-lo)*(right-left);
  return <div style={{overflowX:"auto"}}>
    <svg role="img" aria-label="Change in each team’s mean expected completion probability: second minus first possession, with individual 95% uncertainty ranges" viewBox={"0 0 1280 "+(bottom+100)} style={{width:"100%",minWidth:930,display:"block"}}>
      <title>Change in mean expected completion probability, first to second possession</title>
      <text x={0} y={24} fill={t.text.secondary} fontSize={15}>TEAM</text>
      <text x={320} y={24} textAnchor="end" fill={t.text.secondary} fontSize={15}>TOTAL aEC{sort==="aec_desc"?" ↓":sort==="aec_asc"?" ↑":""}</text>
      <text x={left} y={24} fill={t.text.secondary} fontSize={15}>Lower expected completion</text>
      <text x={1005} y={24} textAnchor="end" fill={t.text.secondary} fontSize={15}>CHANGE</text>
      <text x={1040} y={24} fill={t.text.secondary} fontSize={15}>INDIVIDUAL TEST</text>
      {Array.from({length:Math.round((hi-lo)/5)+1},(_,i)=>lo+5*i).map(v=><g key={v}>
        <line x1={X(v)} x2={X(v)} y1={top-16} y2={bottom+18} stroke={v===0?t.text.secondary:t.stroke.tertiary} strokeWidth={v===0?1.8:1} strokeDasharray={v===0?"5 4":undefined}/>
        <text x={X(v)} y={bottom+43} textAnchor="middle" fill={t.text.secondary} fontSize={16}>{v===0?"0":v>0?"+"+v:"−"+Math.abs(v)}</text>
      </g>)}
      <text x={X(0)} y={44} textAnchor="middle" fill={t.text.primary} fontSize={15}>No change</text>
      {ordered.map((r:any,i:number)=>{
        const y=top+36*i,significant=r.inference.nominal_excludes_zero,color=significant?t.accent.primary:t.text.secondary,ci=r.inference.ci95_pp;
        return <g key={r.team} role="button" tabIndex={0} data-team={r.team} data-total-aec={r.total_aec} data-unadjusted-significant={String(significant)} data-corrected-significant={String(r.inference.bonferroni_excludes_zero)} data-change-pp={r.change_pp} data-ci-low={ci?.[0]} data-ci-high={ci?.[1]} aria-label={"Inspect "+r.team_name+": "+sign(r.change_pp)+" percentage points; "+(significant?"significant before correction":"not statistically significant")} onClick={()=>onInspect(r.team)} onKeyDown={(e:any)=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();onInspect(r.team);}}} style={{cursor:"pointer"}}>
          <rect x={0} y={y-16} width={1270} height={34} fill="transparent"/>
          <text x={0} y={y+5} fill={t.text.primary} fontSize={17} fontWeight={significant?600:400}>{r.team_name}</text>
          <text x={320} y={y+5} textAnchor="end" fill={t.text.secondary} fontSize={17}>{fmt(r.total_aec,2)}</text>
          {ci?<g><line x1={X(ci[0])} x2={X(ci[1])} y1={y} y2={y} stroke={color} strokeWidth={2.5}/><line x1={X(ci[0])} x2={X(ci[0])} y1={y-5} y2={y+5} stroke={color}/><line x1={X(ci[1])} x2={X(ci[1])} y1={y-5} y2={y+5} stroke={color}/></g>:null}
          {significant?<path d={"M "+X(r.change_pp)+" "+(y-6)+" L "+(X(r.change_pp)+6)+" "+y+" L "+X(r.change_pp)+" "+(y+6)+" L "+(X(r.change_pp)-6)+" "+y+" Z"} fill={color}/>:<circle cx={X(r.change_pp)} cy={y} r={5} fill={color}/>}
          <text x={1005} y={y+5} textAnchor="end" fill={t.text.primary} fontSize={17}>{sign(r.change_pp)}</text>
          <text x={1040} y={y+5} fill={color} fontSize={16} fontWeight={significant?600:400}>{significant?"Significant":"Uncertain"}</text>
          <title>{r.team_name+": first "+fmt(r.stages[0].summary.xcp,2)+"%, second "+fmt(r.stages[1].summary.xcp,2)+"%. Change "+fmt(r.change_pp,2)+" percentage points. Individual 95% range: "+range(ci,2)+". "+significanceStatus(r)+". ShownSpace total aEC: "+fmt(r.total_aec,2)+" across "+r.aec_games+" games. First/second possessions: "+r.stages[0].summary.possessions+" / "+r.stages[1].summary.possessions+". Select for the original detailed view."}</title>
        </g>;
      })}
      <text x={(left+right)/2} y={bottom+83} textAnchor="middle" fill={t.text.primary} fontSize={17}>Change in mean expected completion probability (percentage points)</text>
    </svg>
  </div>;
}

function ClassPresentation({data,scope,setScope,teamVisibility,setTeamVisibility,sort,setSort,setView,onInspect}:any) {
  const t=useHostTheme();
  const rows=teamVisibility==="significant"?data.teams.filter((r:any)=>r.inference.nominal_excludes_zero):data.teams;
  return <article style={{maxWidth:1240,margin:"0 auto",padding:"24px 24px",color:t.text.primary}}><Stack gap={18}>
    <div style={{display:"flex",justifyContent:"space-between",gap:20,alignItems:"center",flexWrap:"wrap"}}>
      <H1>Do teams attempt harder throws on their second possession?</H1>
      <label>View <Select value="class" onChange={setView} options={[{value:"class",label:"Class presentation"},{value:"detailed",label:"Original detailed view"}]}/></label>
    </div>
    <div style={{display:"flex",gap:28,flexWrap:"wrap",borderTop:"1px solid "+t.stroke.tertiary,borderBottom:"1px solid "+t.stroke.tertiary,padding:"14px 0"}}>
      <div style={{flex:"1 1 320px"}}><Text weight="semibold">First possession</Text><Text>The offense receives the pull—the throw that starts the point.</Text></div>
      <div style={{flex:"1 1 320px"}}><Text weight="semibold">Second possession · same point</Text><Text>The offense loses the disc, the opponent loses it, and the offense has another chance before either team scores.</Text></div>
    </div>
    <Text><strong>We measure the average model-estimated chance that an attempted pass is completed.</strong> For each team, subtract the first-possession average from the second. A negative change means harder throws on the second possession, according to the model.</Text>
    <div style={{display:"flex",gap:18,flexWrap:"wrap",alignItems:"end"}}>
      <label>Starting location <Select value={scope} onChange={setScope} options={[{value:"long_field",label:"At least 60 yards from goal"},{value:"all_starts",label:"All known starts"}]}/></label>
      <label>Show teams <Select value={teamVisibility} onChange={setTeamVisibility} options={[{value:"all",label:"All teams"},{value:"significant",label:"Significant teams only"}]}/></label>
      <label>Order teams <Select value={sort} onChange={setSort} options={[{value:"aec_desc",label:"Total aEC · high to low"},{value:"aec_asc",label:"Total aEC · low to high"},{value:"name",label:"Alphabetical"},{value:"change",label:"Largest decrease first"}]}/></label>
    </div>
    <section aria-label="Team comparison for class"><Stack gap={10}>
      <H2>Change in expected completion: second minus first possession</H2>
      <Text size="small">Each dot or diamond is a team’s change; the horizontal line is its 95% uncertainty range. A range that crosses zero leaves the direction of the difference uncertain.</Text>
      <div style={{display:"flex",gap:24,flexWrap:"wrap",fontSize:15}}>
        <span style={{color:t.accent.primary}}>◆ Significant · before the 22-team correction</span>
        <span style={{color:t.text.secondary}}>● Uncertain · range includes zero</span>
      </div>
      <TeamDifferenceChart rows={rows} allRows={data.teams} sort={sort} onInspect={onInspect}/>
      <Text size="small"><strong>Exploratory results: none of the teams passes the correction for testing 22 teams.</strong> “Significant” here means the individual, unadjusted comparison. {teamVisibility==="significant"?"Showing only the "+rows.length+" teams that meet that individual threshold; all 22 remain part of the correction.":"All 22 teams are shown."}</Text>
    </Stack></section>
    <details><summary>Explain the measure with an example</summary><Stack gap={10} style={{paddingTop:12}}>
      <Text>For Carolina, the average predicted completion probability is {fmt(data.teams.find((r:any)=>r.team==="flyers").stages[0].summary.xcp)}% on the first possession and {fmt(data.teams.find((r:any)=>r.team==="flyers").stages[1].summary.xcp)}% on the second. That is a change of {sign(data.teams.find((r:any)=>r.team==="flyers").change_pp)} percentage points.</Text>
      <Text>These are model predictions averaged over attempted throws, not the percentage of passes actually caught. Longer lines mean more uncertainty about the difference. The plot uses the same scale when switching between all teams and significant teams.</Text>
      <Text size="small">Select a team’s row to open its original detailed view, including first and second averages, throw counts, and the throw-by-throw chart. Total aEC only sets the order; it is not the quantity on the horizontal axis.</Text>
    </Stack></details>
    <Text size="small" tone="secondary">Source: ShownSpace probabilities + audited UFA events · April 24–July 19, 2026 · original seven players · centering passes included. This measures differences between observed possessions, not the causal effect of a turnover.</Text>
    <Text size="small" tone="secondary">Order by total aEC uses ShownSpace’s full-season team totals, including playoffs. The completion-probability comparison uses our 131-game regular-season sample.</Text>
  </Stack></article>;
}

export default function ExpectedCompletionByPossession() {
  const t=useHostTheme();
  const [scope,setScope]=useState("long_field"),[team,setTeam]=useState("league"),[limit,setLimit]=useState("12"),[uncertainty,setUncertainty]=useState("show"),[sort,setSort]=useState("aec_desc"),[teamVisibility,setTeamVisibility]=useState("all"),[view,setView]=useState("class");
  const data=DATA.scopes[scope],row=team==="league"?data.league:data.teams.find((r:any)=>r.team===team);
  const comparisonTeams=teamVisibility==="significant"?data.teams.filter((r:any)=>r.inference.nominal_excludes_zero):data.teams;
  const a=row.stages[0].summary,b=row.stages[1].summary;
  const n=Number(limit),first=row.stages[0].series,second=row.stages[1].series;
  if(view==="class")return <ClassPresentation data={data} scope={scope} setScope={setScope} teamVisibility={teamVisibility} setTeamVisibility={setTeamVisibility} sort={sort} setSort={setSort} setView={setView} onInspect={(selected:string)=>{setTeam(selected);setView("detailed");}}/>;
  return <article style={{maxWidth:1160,margin:"0 auto",padding:"28px 24px",color:t.text.primary}}><Stack gap={18}>
    <Text size="small" tone="secondary">O-LINE THROWING TENDENCIES · 2026 REGULAR SEASON</Text>
    <H1>Expected completion, first possession to second</H1>
    <label>View <Select value={view} onChange={setView} options={[{value:"class",label:"Class presentation"},{value:"detailed",label:"Original detailed view"}]}/></label>
    <Text>Do teams attempt harder throws after getting the disc back? Compare ShownSpace’s expected completion probability (xCP) through the receiving team’s first and second possessions in the same point.</Text>
    <div style={{display:"flex",gap:18,flexWrap:"wrap"}}>
      <label>Team <Select value={team} onChange={setTeam} options={[{value:"league",label:"League pooled"},...data.teams.map((r:any)=>({value:r.team,label:r.team_name}))]}/></label>
      <label>Starting location <Select value={scope} onChange={setScope} options={[{value:"long_field",label:"At least 60 yards from goal"},{value:"all_starts",label:"All known starts"}]}/></label>
      <label>Throw numbers shown <Select value={limit} onChange={setLimit} options={[{value:"12",label:"1–12"},{value:"20",label:"1–20"}]}/></label>
      <label>95% ranges <Select value={uncertainty} onChange={setUncertainty} options={[{value:"show",label:"Show"},{value:"hide",label:"Hide"}]}/></label>
    </div>
    <section style={{borderTop:"1px solid "+t.stroke.tertiary,borderBottom:"1px solid "+t.stroke.tertiary,padding:"16px 0"}}><Stack gap={8}>
      <Text weight="semibold">{row.team_name} · all throws in eligible possessions</Text>
      <div style={{display:"flex",gap:36,flexWrap:"wrap"}}>
        <div><Text size="small" tone="secondary">FIRST POSSESSION</Text><H2>{fmt(a.xcp)}%</H2><Text size="small">{count(a.cp_attempts)} throws · {count(a.possessions)} possessions</Text></div>
        <div><Text size="small" tone="secondary">SECOND POSSESSION</Text><H2>{fmt(b.xcp)}%</H2><Text size="small">{count(b.cp_attempts)} throws · {count(b.possessions)} possessions</Text></div>
        <div><Text size="small" tone="secondary">SECOND MINUS FIRST</Text><H2>{sign(row.change_pp)} percentage points</H2><Text size="small">Individual 95% range: {range(row.inference.ci95_pp,2)} pp</Text></div>
      </div>
    </Stack></section>
    <H2>{row.team_name} · throw by throw</H2>
    <Legend/>
    <Progression row={row} limit={n} uncertainty={uncertainty==="show"}/>
    <Text><strong>Lower on the graph means a harder attempted throw according to the model.</strong> Each mark averages the throws recorded at that position in the sequence. It does not show actual completion percentage or the chance of scoring the possession.</Text>
    <Text size="small" tone="secondary">All physical throws are counted, including opening centering passes. At throw {n}, the first-possession estimate uses {count(first[n-1].cp_attempts)} attempts and the second uses {count(second[n-1].cp_attempts)}. Only possessions that reach that throw contribute, so the lines do not follow a fixed set of possessions. The vertical scale adjusts to the selected data.</Text>
    <details><summary>Counts and values for each throw number</summary><Stack gap={10} style={{paddingTop:12}}>
      <Table headers={["Throw number","First xCP (%)","First throws","Second xCP (%)","Second throws","First games","Second games"]} columnAlign={["left","right","right","right","right","right","right"]} rows={first.slice(0,n).map((r:any,i:number)=>[r.ordinal,fmt(r.xcp,2),count(r.cp_attempts),fmt(second[i].xcp,2),count(second[i].cp_attempts),r.games,second[i].games])}/>
      <Text size="small">First/second throws after the displayed range: {count(a.attempts-first.slice(0,n).reduce((sum:number,r:any)=>sum+r.attempts,0))} / {count(b.attempts-second.slice(0,n).reduce((sum:number,r:any)=>sum+r.attempts,0))}. These still count in the whole-possession averages above.</Text>
    </Stack></details>
    <section style={{borderTop:"1px solid "+t.stroke.tertiary,paddingTop:24}}><Stack gap={14}>
      <H2>Compare team averages</H2>
      <Text size="small">Each row compares every eligible attempted throw in a team’s first and second possessions. Select a team’s row to update the throw-by-throw chart above. Total aEC can set the team order; the dots show expected completion probability.</Text>
      <div style={{display:"flex",gap:18,flexWrap:"wrap",alignItems:"end"}}>
        <label>Show teams <Select value={teamVisibility} onChange={setTeamVisibility} options={[{value:"all",label:"All teams"},{value:"significant",label:"Significant teams only"}]}/></label>
        <label>Order teams <Select value={sort} onChange={setSort} options={[{value:"aec_desc",label:"Total aEC · high to low"},{value:"aec_asc",label:"Total aEC · low to high"},{value:"name",label:"Alphabetical"},{value:"change",label:"Largest xCP decrease first"}]}/></label>
      </div>
      <Text size="small" tone="secondary">Total aEC: <a href="https://shownspace.com/teams" target="_blank" rel="noreferrer">ShownSpace’s 2026 team totals</a>, recorded November 16, across 12–15 games per team including playoffs. xCP still uses our regular-season sample. Changing the starting-location filter does not change a team’s total aEC.</Text>
      <Text size="small"><strong>* Statistically significant in the individual 95% comparison (unadjusted).</strong> {data.significanceSummary.nominal_teams.length} of 22 teams are marked. {data.significanceSummary.corrected_teams.length===0?"None remains significant after correcting for the 22 team comparisons.":"Significant after the 22-team correction: "+data.significanceSummary.corrected_teams.join(", ")+"."} Stars refer to the first-to-second xCP difference for the selected starting-location filter.</Text>
      <Text size="small" tone="secondary">Showing {comparisonTeams.length} of 22 teams{teamVisibility==="significant"?" · individual significance, before the 22-team correction":""}. This filter changes only which teams are displayed.</Text>
      <Legend/>
      <TeamAverages rows={comparisonTeams} selected={team} onSelect={setTeam} sort={sort}/>
      <Text size="small" tone="secondary">The table below provides the exact averages and uncertainty ranges. Small second-possession samples can produce large changes; a large change alone does not establish a reliable team tendency.</Text>
      <details><summary>Team averages, possession counts and uncertainty</summary><Stack gap={10} style={{paddingTop:12}}>
        <Table headers={["Team","Total aEC","aEC games","First xCP (%)","Second xCP (%)","Change (pp)","Individual 95% range (pp)","Significance","First possessions","Second possessions"]} columnAlign={["left","right","right","right","right","right","right","left","right","right"]} rows={orderedTeams(comparisonTeams,sort).map((r:any)=>[markedName(r),fmt(r.total_aec,2),r.aec_games,fmt(r.stages[0].summary.xcp,2),fmt(r.stages[1].summary.xcp,2),fmt(r.change_pp,2),range(r.inference.ci95_pp,2),significanceStatus(r),r.stages[0].summary.possessions,r.stages[1].summary.possessions])}/>
      </Stack></details>
    </Stack></section>
    <details><summary>What this comparison includes</summary><Stack gap={10} style={{paddingTop:12}}>
      <Text size="small">The receiving team’s first possession begins after the pull. Its second possession begins after it turns the disc over and the opponent turns it back. These occur in the same point. Openings that never lead to a second possession are included; the two samples are not paired and are not restricted to eventual holds.</Text>
      <Text size="small">The recorded original seven must remain throughout each included possession. Exclude possessions with a timeout, uncertain or changed lineups, unresolved period endings, and previously reviewed end-of-quarter scoring attempts. Completed possessions before a later substitution remain included. Original possession numbers are preserved.</Text>
      <Text size="small">The default field-position filter keeps starts at least 60 yards from the attacking goal. It uses the first recorded throwing location, not a film-verified pickup spot. A broad long-field filter does not exactly match the two groups’ starting locations or other context.</Text>
      <Text size="small">xCP = 100 × sum of stored completion probabilities ÷ attempted throws with a probability. Completions, drops, interceptions and throwaways all remain attempts. All {count(DATA.coverage.eligible_attempts)} eligible attempts have a stored probability. No new completion model or centering-pass classifier is fitted.</Text>
      <Text size="small">The throw-by-throw ranges use 10,000 whole-game resamples. Whole-possession difference ranges and team significance use the more extensive 200,000-resample check, keeping both teams and both stages together. A star means the unrounded individual 95% difference range excludes zero; it does not mean the team passes the correction for 22 comparisons. The correction is applied separately within each starting-location filter. These exploratory ranges describe sampling uncertainty and exclude uncertainty in the underlying completion model. Ranges are omitted with fewer than two contributing games or too many empty resamples.</Text>
      <Text size="small">Later possessions occur only when the receiving team gets another opportunity. The opponent, field position, personnel context and receiver separation can differ. These observations do not establish fatigue, impatience or a causal effect of turnovers. Centering labels remain incomplete; the opening-pass difference is still part of this unadjusted comparison.</Text>
      <Text size="small">Archived 2026 regular season, April 24–July 19: 131 games, 22 teams. Pittsburgh at Chicago on July 18 is missing. Five otherwise eligible first/second possessions have no recorded starting location. Reviewed clock exclusions cover identified cases rather than a full league screen. This is not a live refresh of the website.</Text>
      <Text size="small">Definition: <a href="https://shownspace.com/about" target="_blank" rel="noreferrer">ShownSpace metric catalog</a>. Calculations, source hashes and row-level membership: research/expected_completion_2026_11_16. Source probabilities and film labels are unchanged.</Text>
    </Stack></details>
    <Text size="small" tone="secondary">Source: preserved ShownSpace data + audited UFA events · 2026 regular season · first vs. exactly second possession · original seven · centering included.</Text>
  </Stack></article>;
}
