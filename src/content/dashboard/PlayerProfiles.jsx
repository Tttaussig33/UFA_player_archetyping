import React,{useMemo,useState} from 'react';
import {Button,DataComponent,DataTable,Dropdown,SortableItem,SortableRegion} from '../../data-app-public.jsx';
import {Face} from './Field.jsx';
import {cleanProfileSearch,rankStyleCandidates,comparisonRows} from './profile-model.js';
import './player-profiles.css';

const pct=v=>Number.isFinite(v)?`${(100*v).toFixed(1)}%`:'—';
const dec=v=>Number.isFinite(v)?v.toFixed(1):'—';
const signed=v=>Number.isFinite(v)?`${v>=0?'+':''}${v.toFixed(2)}`:'—';
const pp=v=>Number.isFinite(v)?`${signed(v*100)} pp`:'—';
const traitValue=(v,unit)=>unit==='yards'?`${dec(v)} yd`:pct(v);
const nameCell=(value,row)=><span className="ufa-profile-identity"><Face id={row.id} name={row.name}/><span>{value}<small>{row.teamName}</small></span></span>;
const profileColumns=[
  {field:'name',label:'Player',renderCell:nameCell},
  {field:'throws',label:'Throws'}, {field:'catches',label:'Catches'},
  {field:'huckShare',label:'Huck share',renderCell:pct},
  {field:'shortShare',label:'Short-pass share',renderCell:pct},
  {field:'releaseY',label:'Avg. throwing location',renderCell:v=>`${dec(v)} yd`},
  {field:'catchY',label:'Avg. catching location',renderCell:v=>`${dec(v)} yd`},
];

export function PlayerProfiles({queries,team,teamName}) {
  const profiles=queries.playerProfiles?.rows||[],reference=queries.profileReference?.rows||[],study=queries.profileStudy?.rows||[];
  const [selectedId,setSelectedId]=useState('aatkins'),[candidateId,setCandidateId]=useState(null);
  const [search,setSearch]=useState(''),[pool,setPool]=useState('other');
  const scoped=useMemo(()=>profiles.filter(p=>team==='all'||p.team===team),[profiles,team]);
  const selected=scoped.find(p=>p.id===selectedId)||scoped.find(p=>p.id==='aatkins')||scoped[0];
  const directory=useMemo(()=>scoped.filter(p=>cleanProfileSearch(`${p.name} ${p.teamName}`).includes(cleanProfileSearch(search))).sort((a,b)=>a.name.localeCompare(b.name)),[scoped,search]);
  const candidates=useMemo(()=>rankStyleCandidates(selected,profiles,reference,pool==='other'),[selected,profiles,reference,pool]);
  const closest=candidates.slice(0,5).map((p,i)=>({...p,rank:i+1}));
  const candidate=closest.find(p=>p.id===candidateId)||closest[0];
  const traits=comparisonRows(selected,candidate,reference);
  const pair=selected?[selected,...(candidate?[profiles.find(p=>p.id===candidate.id)]:[])]:[];
  const candidateSource=selected?profiles.filter(p=>p.id===selected.id||candidates.some(c=>c.id===p.id)):[];
  const latest=study.find(s=>s.season===2026);
  const fixedScope=[{label:'Season',value:'2026 regular season · all lines'},{label:'Source snapshot',value:'October 12, 2026'},{label:'Eligibility',value:'100+ throws and 100+ completed catches; 6+ games per role; single team'}];
  const matchingScope=[...fixedScope,{label:'Selected player',value:selected?.name||'None'},{label:'Candidate pool',value:pool==='other'?'All other teams':'All teams, including teammates'}];
  const pick=row=>{setSelectedId(row.id);setCandidateId(null);};
  if(!profiles.length||!reference.length||!study.length)return <div className="ufa-empty" role="status">The reviewed player-style analysis is unavailable for this snapshot. Rebuild the player-profile study to enable comparisons.</div>;
  return <div className="ufa-profiles">
    <div className="ufa-profile-intro"><h2 data-editable-id="ufa-profiles-heading">Player styles & comparisons</h2><p data-editable-id="ufa-profiles-intro">Find players who make similar passing choices and operate in similar areas. Use the results to choose who to scout and what to check on film.</p></div>
    <p className="ufa-profile-scope" data-reviewed-rows>{profiles.length} qualified players · Regular season only · 100+ throws and 100+ completed catches, across 6+ games in each role.</p>
    <SortableRegion id="ufa:profiles:blocks" variant="canvas" columns={12} spacing="standard" label="Player comparison blocks"
      rows={[{id:'profiles:directory',items:['ufa-profile-directory']},{id:'profiles:matches',items:['ufa-profile-matches','ufa-profile-traits']},{id:'profiles:outcomes',items:['ufa-profile-outcomes']},{id:'profiles:evidence',items:['ufa-profile-evidence']}]}>
      <SortableItem id="ufa-profile-directory" label="Find a player" kind="table" span={12} minSpan={12}>
        <DataComponent id="ufa-profile-directory" queryId="playerProfiles" kind="table" title="Find a player" sourceRows={directory} displayRows={directory}
          scopeFilters={[...fixedScope,{label:'Team',value:teamName},{label:'Search',value:search||'All qualified players'}]}
          description="Select a player to update the comparisons below. The sample floor includes both passing and completed catching; low-involvement players and multi-team seasons are excluded. Coordinates run from 0 at the back of the own end zone toward 120 at the back of the attacking end zone. Short passes travel at most 10 yards; hucks gain more than 30 yards and travel more than 40 yards.">
          <div className="ufa-profile-directory-controls"><label>Search players<input type="search" aria-label="Search player styles" placeholder="Player or team…" value={search} onChange={e=>setSearch(e.target.value)}/></label><span data-reviewed-rows>{selected?`Comparing ${selected.name} below`:'No eligible players for this team'}</span>{search&&<Button onClick={()=>setSearch('')}>Clear search</Button>}</div>
          <div data-reviewed-rows><DataTable rows={directory} columns={profileColumns} searchable={false} compactNumbers={false} rowKey="id" selectedRowKey={selected?.id} onRowSelect={pick} rowActionLabel={r=>`Compare ${r.name}`} caption="Qualified 2026 player styles; select a player for comparisons"/></div>
          {!directory.length&&<p role="status" className="ufa-profile-note">No qualified players match this search and team. Clear the search or choose All teams.</p>}
          <p className="ufa-profile-note">Locations are yards from the back of the own end zone (0), attacking toward 120. Search filters this directory; select a row to change the comparison.</p>
        </DataComponent>
      </SortableItem>
      <SortableItem id="ufa-profile-matches" label="Closest style matches" kind="table" span={6} minSpan={6}>
        <DataComponent id="ufa-profile-matches" queryId="playerProfiles" queryIds={['playerProfiles','profileReference']} kind="table" title="Five closest style matches"
          sourceRowsByQuery={{playerProfiles:candidateSource,profileReference:reference}} displayRows={closest}
          scopeFilters={matchingScope} headerControls={<Dropdown label="Compare with" showLabel value={pool} choices={['other','all']} allLabel="All teams" choiceLabels={{other:'Other teams',all:'All teams'}} onChange={v=>{setPool(v);setCandidateId(null);}}/>}
          description="Matches use nine traits with four equally weighted groups: passing choices, throwing locations, catching locations and disc involvement. Distances use the fixed spread of 2025 profiles; lower means more similar. Outcomes do not affect matching. Select a candidate to compare traits and recorded results. This ranking is descriptive, not a probability of replacing the selected player successfully.">
          <p className="ufa-profile-note" data-reviewed-rows>Closest to <strong>{selected?.name||'no selected player'}</strong> among {candidates.length} eligible candidates. Select a match to compare.</p>
          <div data-reviewed-rows><DataTable rows={closest} columns={[
            {field:'rank',label:'#'},{field:'name',label:'Player',renderCell:nameCell},
            {field:'distance',label:'Style distance ↓',renderCell:v=>v.toFixed(3)},
            {field:'huckShare',label:'Huck share',renderCell:pct},
          ]} searchable={false} rowKey="id" selectedRowKey={candidate?.id} onRowSelect={r=>setCandidateId(r.id)} rowActionLabel={r=>`Inspect style match ${r.name}`} caption={`Five closest style matches to ${selected?.name||'selected player'}`}/></div>
          <p className="ufa-profile-note" data-editable-id="ufa-profile-matching-note">A starting point for scouting. Team tactics, defensive assignments, off-disc movement and replacement outcomes are not captured here.</p>
        </DataComponent>
      </SortableItem>
      <SortableItem id="ufa-profile-traits" label="Compare playing styles" kind="custom" span={6} minSpan={6}>
        <DataComponent id="ufa-profile-traits" queryId="playerProfiles" queryIds={['playerProfiles','profileReference']} kind="custom" title="Compare playing styles"
          sourceRowsByQuery={{playerProfiles:pair,profileReference:reference}} displayRows={traits} scopeFilters={[...matchingScope,{label:'Comparison player',value:candidate?.name||'None'}]}
          description="Bars show actual values: 0–120 yards for average field positions, 0–100% for shares. Bar lengths show tendencies, not better/worse performance. Every numeric value remains available in source inspection. A throw is forward or backward when its longitudinal displacement exceeds its absolute lateral displacement; these categories need not total 100%.">
          {selected?<div className="ufa-profile-traits" data-reviewed-rows>
            <div className="ufa-profile-pair"><span><i className="ufa-profile-dot primary"/>{selected.name}</span>{candidate&&<span><i className="ufa-profile-dot secondary"/>{candidate.name}</span>}</div>
            {traits.map((r,i)=><React.Fragment key={r.feature}>
              {(i===0||traits[i-1].group!==r.group)&&<h3>{r.group}</h3>}
              <div className="ufa-profile-trait"><span>{r.trait}</span><div className="ufa-profile-trait-values"><b>{traitValue(r.playerValue,r.unit)}</b><span>{candidate?traitValue(r.candidateValue,r.unit):'—'}</span></div>
                <div className="ufa-profile-track" aria-hidden="true"><i className="primary" style={{width:`${r.playerValue/(r.unit==='yards'?120:1)*100}%`}}/>{candidate&&<i className="secondary" style={{width:`${r.candidateValue/(r.unit==='yards'?120:1)*100}%`}}/>}</div>
              </div>
            </React.Fragment>)}
            <p className="ufa-profile-note">Location scale: 0–120 yd, attacking toward 120. Share scale: 0–100%. Longer bars do not mean better.</p>
          </div>:<p className="ufa-profile-note">Select an eligible player to compare.</p>}
        </DataComponent>
      </SortableItem>
      <SortableItem id="ufa-profile-outcomes" label="Recorded passing outcomes" kind="table" span={12} minSpan={12}>
        <DataComponent id="ufa-profile-outcomes" queryId="playerProfiles" kind="table" title="Recorded passing outcomes" sourceRows={pair} displayRows={pair}
          scopeFilters={[...fixedScope,{label:'Players',value:pair.map(p=>p.name).join(' / ')}]}
          description="Completion versus expectation is actual completion minus a coarse throw-geometry model trained on 2021–2025. It uses the recorded destination, so it is a retrospective comparison. Intervals resample each player’s games 2,000 times and hold the model fixed. This is not Shown Space CPOE or aEC and does not adjust for defense, weather, receiver ability or off-disc work.">
          <p className="ufa-profile-note" data-editable-id="ufa-profile-outcomes-note">These describe recorded results. Our historical test did not validate the prior-year passing rating as a useful addition to next-year completion predictions.</p>
          <div data-reviewed-rows><DataTable rows={pair} searchable={false} compactNumbers={false} columns={[
            {field:'name',label:'Player',renderCell:nameCell},
            {field:'throwGames',label:'Games'},
            {field:'completionRate',label:'Complete / throws',renderCell:(v,r)=><span>{pct(v)}<small className="ufa-profile-subvalue">{r.completions} / {r.throws}</small></span>},
            {field:'huckCompletion',label:'Complete / hucks',renderCell:(v,r)=><span>{pct(v)}<small className="ufa-profile-subvalue">{r.huckCompletions} / {r.huckAttempts}{r.huckAttempts<20?' · small sample':''}</small></span>},
            {field:'completionAboveExpected',label:'vs. geometry expectation',renderCell:pp},
            {field:'completionLower',label:'95% game interval',renderCell:(v,r)=><span>{pp(v)} to {pp(r.completionUpper)}</span>},
          ]} caption="Observed results for the selected player and comparison candidate; not a player-quality ranking"/></div>
          <p className="ufa-profile-note">pp = percentage points. Style matches do not use these results. The model adjusts only coarse throw geometry.</p>
        </DataComponent>
      </SortableItem>
      <SortableItem id="ufa-profile-evidence" label="What the research supports" kind="custom" span={12} minSpan={12}>
        <DataComponent id="ufa-profile-evidence" queryId="profileStudy" kind="custom" title="What the research supports" sourceRows={study} displayRows={study}
          scopeFilters={[{label:'Validation seasons',value:'2024→2025 and 2025→2026'}]}
          description="All results are exploratory historical tests on previously examined seasons. Broad groups are stable under team resampling but do not meet our chosen .60 adjusted-Rand threshold for later half-season stability. This threshold is a pilot decision, not a universal definition of archetypes. Game and player bootstraps for the outcome test both include zero improvement. No replacement intervention or replacement outcome was measured.">
          {latest&&<div className="ufa-profile-verdicts" data-reviewed-rows>
            <div><span className="ufa-profile-status">Exploratory</span><h3>Two broad style families</h3><p>Mostly backfield versus upfield activity. {latest.sameGroupCount}/{latest.halfPlayers} players stayed in the same group across 2026 halves. Grouping has not met our stability threshold in either test year.</p></div>
            <div><span className="ufa-profile-status">Not validated</span><h3>A transferable passing rating</h3><p>Adding last year’s player rating made 2026 prediction error {Math.abs(latest.relativeBrierImprovementPct).toFixed(2)}% {latest.relativeBrierImprovementPct<0?'higher':'lower'} than the baseline. The uncertainty interval includes no improvement.</p></div>
            <div><span className="ufa-profile-status">Not tested</span><h3>Successful replacements</h3><p>These are similar-player shortlists. We have not measured how a candidate performs in the same lineup and assigned role as the player being replaced.</p></div>
          </div>}
          <details className="ufa-profile-study"><summary>See the historical checks</summary><div data-reviewed-rows><DataTable rows={study} searchable={false} columns={[
            {field:'season',label:'Test season',renderCell:v=>String(v)}, {field:'halfPlayers',label:'Players in both halves'},
            {field:'sameGroupRate',label:'Stayed in group',renderCell:pct},
            {field:'temporalARI',label:'Chance-adjusted stability',renderCell:v=>v.toFixed(3)},
            {field:'relativeBrierImprovementPct',label:'Prediction improvement',renderCell:v=>`${signed(v)}%`},
            {field:'relativeBrierLowerPct',label:'95% game interval',renderCell:(v,r)=>`${signed(v)}% to ${signed(r.relativeBrierUpperPct)}%`},
          ]} caption="Historical clustering and passing-outcome validation"/></div><p className="ufa-profile-note">Stability score: 1 = identical groups; about 0 = chance agreement. Our pilot threshold is 0.60. Prediction improvement compares geometry + prior team + prior player performance with geometry + prior team performance; positive is better. The outcome cohorts differ from the style cohorts.</p></details>
        </DataComponent>
      </SortableItem>
    </SortableRegion>
  </div>;
}
