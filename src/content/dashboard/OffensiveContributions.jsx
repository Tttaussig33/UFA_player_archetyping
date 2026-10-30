import React,{useMemo,useState} from 'react';
import {Button,DataComponent,DataTable,Dropdown,EvidenceChart,SegmentedControl,SortableItem,SortableRegion} from '../../data-app-public.jsx';
import {Face} from './Field.jsx';
import {CONTRIBUTIONS,CONTRIBUTION_SORTS,contributionDirectory,contributionPlot,playerContributions,percent,signedPp,intervalText} from './contribution-model.js';
import './offensive-contributions.css';

const nameCell=(v,r)=><span className="ufa-profile-identity"><Face id={r.playerId} name={r.name}/><span>{v}<small>{r.teamName}</small></span></span>;
const intervalCell=(v,r)=><span>{signedPp(v)}<small className="ufa-profile-subvalue">{intervalText(r)}</small></span>;
const chartSpec={type:'scatter',x:'contributionShare',y:'cpoePp',xLabel:'Share of this player’s passes',yLabel:'Above expected (pp)',showXAxisLabel:true,showYAxisLabel:true,
  startAtZero:true,showLegend:false,stackable:false,valueDecimals:1,colors:{cpoePp:'var(--chart-1)'}};

export function OffensiveContributions({queries,team,teamName}) {
  const rows=queries.offensiveContributions?.rows||[],baselines=queries.contributionBaselines?.rows||[],study=queries.contributionStudy?.rows||[];
  const [role,setRole]=useState('advance'),[search,setSearch]=useState(''),[minimum,setMinimum]=useState('20'),[sort,setSort]=useState('share'),[selectedId,setSelectedId]=useState(null);
  const directory=useMemo(()=>contributionDirectory(rows,{role,team,search,minimum,sort}),[rows,role,team,search,minimum,sort]);
  const plotted=useMemo(()=>contributionPlot(directory),[directory]);
  const selected=directory.find(r=>r.playerId===selectedId)||directory[0];
  const baseline=baselines.find(r=>r.role===role);
  const playerRows=useMemo(()=>playerContributions(rows,selected?.playerId,baselines),[rows,selected,baselines]);
  const selectedSource=selected?rows.filter(r=>r.playerId===selected.playerId):[];
  const pick=row=>setSelectedId(row.playerId);
  const commonScope=[{label:'Season',value:'2026 regular season · all lines'},{label:'Export',value:'October 12, 2026'},
    {label:'Cohort',value:'249 throwers; 100+ passes and 6+ games, single team'}];
  const filteredScope=[...commonScope,{label:'Contribution',value:CONTRIBUTIONS[role].label},{label:'Team',value:teamName},
    {label:'Minimum role attempts',value:minimum},{label:'Search',value:search||'All players'}];
  const columns=[
    {field:'name',label:'Player',renderCell:nameCell},
    {field:'share',label:'Share of passes',renderCell:percent},
    {field:'attempts',label:'Complete / attempts',renderCell:(v,r)=>`${r.completions} / ${v}`},
    {field:'completionRate',label:'Completion',renderCell:percent},
    {field:'cpoePp',label:'Above expected · 95% interval',renderCell:intervalCell},
    role==='score'?{field:'assists',label:'Actual assists'}:{field:'meanCompletedGain',label:'Gain / completion',renderCell:v=>Number.isFinite(v)?`${v.toFixed(1)} yd`:'—'},
  ];
  if(!rows.length||!baseline||!study.length)return <p className="ufa-empty" role="status">The contribution study is unavailable for this snapshot.</p>;
  const scoringStudy=study.find(r=>r.role==='score');
  return <section className="ufa-contributions" aria-label="Offensive contributions">
    <div className="ufa-profile-intro"><h2 data-editable-id="ufa-contributions-heading">Offensive contributions</h2><p data-editable-id="ufa-contributions-intro">How do throwers advance the disc, redistribute it, and deliver scoring passes—and how effective are they at each?</p></div>
    <p className="ufa-profile-scope" data-reviewed-rows>{baseline.players} qualifying players · 2026 regular season · Scoring delivery overlaps the two direction groups.</p>
    <div className="ufa-contribution-role"><SegmentedControl value={role} onChange={setRole} options={Object.entries(CONTRIBUTIONS).map(([value,r])=>({value,label:r.label}))}/></div>
    <p className="ufa-contribution-definition" data-reviewed-rows>{CONTRIBUTIONS[role].description}</p>
    <div className="ufa-contribution-controls">
      <label className="ufa-thrower-search">Search players<input aria-label="Search offensive contributions" type="search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Player or team…"/></label>
      <Dropdown label="Minimum attempts" showLabel value={minimum} choices={['0','20','50','100']} choiceLabels={{0:'All samples',20:'20 in this contribution',50:'50 in this contribution',100:'100 in this contribution'}} onChange={setMinimum}/>
      <Dropdown label="Sort players" showLabel value={sort} choices={Object.keys(CONTRIBUTION_SORTS)} choiceLabels={CONTRIBUTION_SORTS} onChange={setSort}/>
      {search&&<Button onClick={()=>setSearch('')}>Clear search</Button>}
    </div>
    <p className="ufa-contribution-explanation" data-editable-id="ufa-contribution-cpoe-explanation"><strong>Above expected</strong> compares completed or recorded-dropped passes with the source model’s expected completion. It gives the thrower credit for drops. Positive values mean more credited completions than expected; they are observed results, not a proven skill rating.</p>
    <SortableRegion id="ufa:contributions:blocks" variant="canvas" columns={12} spacing="standard" label="Contribution analysis blocks"
      rows={[{id:'contributions:overview',items:['ufa-contribution-map','ufa-contribution-player']},{id:'contributions:players',items:['ufa-contribution-directory']},{id:'contributions:study',items:['ufa-contribution-study']}]}>
      <SortableItem id="ufa-contribution-map" label="Frequency and results" kind="chart" span={7} minSpan={6}>
        <EvidenceChart id="ufa-contribution-map" queryId="offensiveContributions" queryIds={['offensiveContributions','contributionBaselines']} title="Frequency & recorded results"
          spec={chartSpec} rows={plotted} sourceRowsByQuery={{offensiveContributions:directory,contributionBaselines:[baseline]}}
          height={320} scopeFilters={filteredScope}
          description="Each point is one qualifying player in the selected contribution. X is role attempts / all of that player’s physical passes. Y is drop-credit completion above supplied expectation in percentage points. Missing outcomes are omitted from the plot, never set to zero. The table and selected-player panel show pointwise 95% whole-game intervals where there are at least 20 attempts across six role games; chart positions alone do not show rank certainty. Axes follow the displayed range. Select a point, then View contribution profile."
          chartOptions={{getMarkActions:({row})=>row?.playerId?[{label:'View contribution profile',onSelect:()=>pick(row)}]:[]}}>
          <p className="ufa-profile-note" data-reviewed-rows>{plotted.length} players plotted · League benchmark: {percent(baseline.completionRate)} actual completion on {baseline.attempts.toLocaleString()} attempts.</p>
        </EvidenceChart>
      </SortableItem>
      <SortableItem id="ufa-contribution-player" label="Player contributions" kind="custom" span={5} minSpan={4}>
        <DataComponent id="ufa-contribution-player" queryId="offensiveContributions" queryIds={['offensiveContributions','contributionBaselines']} title="Player contributions" kind="custom"
          sourceRowsByQuery={{offensiveContributions:selectedSource,contributionBaselines:baselines}} displayRows={playerRows}
          scopeFilters={[...commonScope,{label:'Player',value:selected?.name||'None'},{label:'Comparison',value:'Fixed league median share; all three contributions'}]}
          description="All three contributions for the selected player, even when the directory is filtered to one contribution. The solid bar is the player’s share; the vertical line is the fixed median share across all 249 qualifying players. All bars run from 0 to 100%. Advancement and redistribution sum to 100%; scoring delivery overlaps. CPOE intervals resample whole games 2,000 times; they are exploratory, conditional on the source model, and not simultaneous ranking tests.">
          {selected?<div data-reviewed-rows>
            <div className="ufa-thrower-selected"><Face id={selected.playerId} name={selected.name}/><div><h3>{selected.name}</h3><p>{selected.teamName} · {selected.totalPasses} passes / {selected.games} games</p></div></div>
            <p className="ufa-profile-note">Share of their passes · line = league median</p>
            {playerRows.map(r=><div key={r.role} className="ufa-contribution-player-row">
              <div className="ufa-contribution-player-label"><strong>{r.roleName}</strong><span>{percent(r.share)}</span></div>
              <div className="ufa-contribution-share-track" role="img" aria-label={`${r.roleName}: ${percent(r.share)} of passes; league median ${percent(r.medianShare)}`}>
                <i style={{width:`${r.share*100}%`}}/><b style={{left:`${r.medianShare*100}%`}}/>
              </div>
              <div className="ufa-contribution-player-result"><span>{r.completions}/{r.attempts} complete · {percent(r.completionRate)}</span><b>{signedPp(r.cpoePp)}</b></div>
              <small>95% interval: {intervalText(r)}{r.role==='score'?` · ${r.assists} actual assists`:''}</small>
            </div>)}
          </div>:<p className="ufa-profile-note" role="status">No player matches these filters. Clear the search or lower the attempt minimum.</p>}
        </DataComponent>
      </SortableItem>
      <SortableItem id="ufa-contribution-directory" label="Compare players" kind="table" span={12} minSpan={12}>
        <DataComponent id="ufa-contribution-directory" queryId="offensiveContributions" title="Compare players" kind="table" sourceRows={directory} displayRows={directory}
          scopeFilters={[...filteredScope,{label:'Sort',value:CONTRIBUTION_SORTS[sort]}]}
          description="Share measures use of this contribution, not overall playing time. Completion includes drops as failures; above expected credits them to the thrower. Expected completion uses only non-missing supplied cp. Intervals are pointwise 95% game-bootstrap ranges, available with ≥20 role attempts and ≥6 role games. A narrow interval does not remove source-model error, team context or selection bias. Gain per completion describes completed passes only, not net possession value. Scoring delivery counts source assists separately from completed targets.">
          <div data-reviewed-rows><DataTable key={`${role}:${team}:${search}:${minimum}:${sort}`} rows={directory} columns={columns} searchable={false} compactNumbers={false}
            rowKey="playerId" selectedRowKey={selected?.playerId} onRowSelect={pick} rowActionLabel={r=>`View contributions for ${r.name}`} caption={`${CONTRIBUTIONS[role].label}: frequency, outcomes and game-bootstrap intervals`}/></div>
          <p className="ufa-profile-note" data-reviewed-rows>{directory.length} matching players · {minimum==='0'?'All sample sizes':`At least ${minimum} attempts in this contribution`}. Select a row to compare all three contributions above.</p>
          <p className="ufa-profile-note">Intervals need at least 20 attempts in six games. Sorting shows recorded values; nearby players may not be meaningfully different.</p>
        </DataComponent>
      </SortableItem>
      <SortableItem id="ufa-contribution-study" label="Across games" kind="custom" span={12} minSpan={12}>
        <DataComponent id="ufa-contribution-study" queryId="contributionStudy" title="Across games" kind="custom" sourceRows={study} displayRows={study}
          scopeFilters={[...commonScope,{label:'Population',value:'Fixed league cohort, unaffected by the player filters'}]}
          description="Compare the first half of each player’s chronological observed games with the remaining games. Frequency checks require ≥50 total passes in each half. Outcome checks also require ≥20 role attempts per half. Spearman correlation uses ranks with average handling of ties. Advancement and redistribution share correlations are identical by construction; do not count them as independent evidence. This is descriptive same-season continuity, not a prospective prediction test or natural-cluster validation.">
          <p className="ufa-contribution-finding" data-reviewed-rows>Passing tendencies repeat more consistently than adjusted outcomes in these checks. Only {scoringStudy?.outcomePlayers} players have enough scoring-delivery attempts in both halves to assess performance consistency.</p>
          <details className="ufa-contribution-study"><summary>See the first-half / later-half comparisons</summary>
            <div data-reviewed-rows><DataTable rows={study} searchable={false} columns={[
              {field:'roleName',label:'Contribution'},
              {field:'shareSpearman',label:'Frequency rank consistency',renderCell:(v,r)=><span>{v.toFixed(2)}<small className="ufa-profile-subvalue">{r.sharePlayers} players</small></span>},
              {field:'cpoeSpearman',label:'Above-expected rank consistency',renderCell:(v,r)=><span>{Number.isFinite(v)?v.toFixed(2):'—'}<small className="ufa-profile-subvalue">{r.outcomePlayers} players{r.outcomePlayers<30?' · limited sample':''}</small></span>},
            ]} caption="Same-season rank consistency across game halves; fixed cohort"/></div>
            <p className="ufa-profile-note">1 means identical ordering; 0 means no rank association. Forward and redistribution shares are complements, so their frequency results are the same check. These results support scouting descriptions, not fixed archetypes or guaranteed replacements.</p>
          </details>
        </DataComponent>
      </SortableItem>
    </SortableRegion>
    <p className="ufa-profile-scope">October 12, 2026 export · 131/132 regular-season games available. Pittsburgh at Chicago on July 18 is missing.</p>
  </section>;
}
