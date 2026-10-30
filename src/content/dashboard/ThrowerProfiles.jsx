import React,{useMemo,useState} from 'react';
import {Button,DataComponent,DataTable,Dropdown,SortableItem,SortableRegion} from '../../data-app-public.jsx';
import {Face} from './Field.jsx';
import {DISTANCE_TRAITS,OUTCOME_TRAITS,PASSING_TRAITS,THROWER_SORTS,observedThrowingTraits,throwerComparison,throwerDirectory} from './thrower-profile-model.js';
import './thrower-profiles.css';

const format=(v,unit='number')=>!Number.isFinite(v)?'—':unit==='share'?`${(v*100).toFixed(1)}%`:unit==='pp'?`${v>=0?'+':''}${(v*100).toFixed(1)} pp`:unit==='yards'?`${v.toFixed(1)} yd`:unit==='count'?v.toLocaleString():v.toFixed(1);
const identity=(v,r)=><span className="ufa-profile-identity"><Face id={r.id} name={r.name}/><span>{v}<small>{r.teamName}</small></span></span>;
const directoryColumns=[
  {field:'name',label:'Player',renderCell:identity},
  {field:'throws',label:'Passes',renderCell:(v,r)=><span>{v.toLocaleString()}<small className="ufa-profile-subvalue">{r.games} games</small></span>},
  {field:'meanGain',label:'Gain / pass',renderCell:v=>format(v,'yards')},
  {field:'shortShare',label:'Short %',renderCell:v=>format(v,'share')},
  {field:'lateralShare',label:'Lateral %',renderCell:v=>format(v,'share')},
  {field:'completionRate',label:'Completion',renderCell:v=>format(v,'share')},
  {field:'throwerAec',label:'Thrower aEC',renderCell: v=>format(v)},
];
const comparisonColumns=(player,other)=>[
  {field:'label',label:'Measure'},
  {field:'playerValue',label:player,renderCell:(v,r)=>format(v,r.unit)},
  {field:'comparisonValue',label:other,renderCell:(v,r)=>format(v,r.unit)},
];

export function ThrowerProfiles({queries,team,teamName,onOpenFieldGuide}) {
  const profiles=queries.throwerProfiles?.rows||[],reference=queries.throwerReference?.rows||[];
  const [search,setSearch]=useState(''),[sort,setSort]=useState('throws');
  const [selectedId,setSelectedId]=useState(null),[compareId,setCompareId]=useState('median');
  const directory=useMemo(()=>throwerDirectory(profiles,{team,search,sort}),[profiles,team,search,sort]);
  const visibleColumns=sort==='throwingY'?directoryColumns.map(c=>c.field==='shortShare'?{field:'throwingY',label:'Throwing location',renderCell:v=>format(v,'yards')}:c):directoryColumns;
  const selected=directory.find(p=>p.id===selectedId)||directory[0];
  const comparisonOptions=useMemo(()=>[...profiles].sort((a,b)=>a.name.localeCompare(b.name)),[profiles]);
  const candidate=profiles.find(p=>p.id===compareId&&p.id!==selected?.id);
  const comparisonName=candidate?.name||'League median';
  const passing=throwerComparison(selected,candidate,reference,PASSING_TRAITS);
  const distances=throwerComparison(selected,candidate,reference,DISTANCE_TRAITS);
  const outcomes=throwerComparison(selected,candidate,reference,OUTCOME_TRAITS);
  const traits=observedThrowingTraits(selected,reference);
  const pair=selected?[selected,...(candidate?[candidate]:[])]:[];
  const sourceRowsByQuery={throwerProfiles:pair,throwerReference:reference};
  const scope=[{label:'Season',value:'2026 regular season · all lines'},{label:'Snapshot',value:'October 12, 2026'},
    {label:'Eligibility',value:'100+ non-stall passes, 6+ observed games, one team; no catching minimum'}];
  const selectionScope=[...scope,{label:'Player',value:selected?.name||'None'},{label:'Compare with',value:comparisonName},
    {label:'League baseline',value:`Fixed median of all ${profiles.length} qualifying players`}];
  if(!profiles.length||!reference.length)return <p className="ufa-empty" role="status">The reviewed all-pass profiles are unavailable for this snapshot.</p>;
  return <section className="ufa-throwers" aria-label="League-wide throwing profiles">
    <div className="ufa-profile-intro"><h2 data-editable-id="ufa-throwers-heading">Throwing profiles across the league</h2><p data-editable-id="ufa-throwers-intro">Find players by how they move the disc. Select anyone to compare their passing choices and recorded results.</p></div>
    <p className="ufa-profile-scope" data-reviewed-rows>{profiles.length} qualifying throwers · 100+ passes across 6+ games · 2026 regular season, all lines</p>
    <div className="ufa-thrower-controls">
      <label className="ufa-thrower-search">Search players<input type="search" aria-label="Search throwing profiles" placeholder="Player or team…" value={search} onChange={e=>setSearch(e.target.value)}/></label>
      <Dropdown label="Sort by" showLabel value={sort} choices={Object.keys(THROWER_SORTS)} choiceLabels={THROWER_SORTS} onChange={setSort}/>
      {search&&<Button onClick={()=>setSearch('')}>Clear search</Button>}
    </div>
    <SortableRegion id="ufa:throwers:blocks" variant="canvas" columns={12} spacing="standard" label="Throwing profile blocks"
      rows={[{id:'throwers:directory',items:['ufa-thrower-directory']},{id:'throwers:profile',items:['ufa-thrower-passing','ufa-thrower-results']}]}>
      <SortableItem id="ufa-thrower-directory" label="Explore throwers" kind="table" span={12} minSpan={12}>
        <DataComponent id="ufa-thrower-directory" queryId="throwerProfiles" kind="table" title="Explore throwers" sourceRows={directory} displayRows={directory}
          scopeFilters={[...scope,{label:'Team',value:teamName},{label:'Search',value:search||'All players'},{label:'Sort',value:THROWER_SORTS[sort]}]}
          description="Every qualifying thrower is available, including players outside the article. Passes exclude stalls and include incompletions. Gain is forward yards, not total flight. Short passes travel at most 10 yards. Lateral means sideways displacement is at least as large as forward/backward displacement. Completion treats drops as incomplete. Total thrower aEC uses the supplied model and includes stalls. Sorts show observed values, not a universal player-quality ranking.">
          <div data-reviewed-rows><DataTable key={`${team}:${search}:${sort}`} rows={directory} columns={visibleColumns} searchable={false} compactNumbers={false}
            rowKey="id" selectedRowKey={selected?.id} onRowSelect={r=>setSelectedId(r.id)} rowActionLabel={r=>`View throwing profile for ${r.name}`} caption="All qualifying 2026 throwers; select a row to compare the player below"/></div>
          <p className="ufa-profile-note" data-reviewed-rows aria-live="polite">{selected?`${directory.length} matching player${directory.length===1?'':'s'} · Showing ${selected.name} below`:'No qualifying players match. Clear the search or choose All teams.'}</p>
        </DataComponent>
      </SortableItem>
      <SortableItem id="ufa-thrower-passing" label="Passing profile" kind="custom" span={6} minSpan={6}>
        <DataComponent id="ufa-thrower-passing" queryId="throwerProfiles" queryIds={['throwerProfiles','throwerReference']} kind="custom" title="Passing profile"
          sourceRowsByQuery={sourceRowsByQuery} displayRows={[...passing,...distances]} scopeFilters={selectionScope}
          headerControls={<Dropdown label="Compare with" showLabel value={candidate?.id||'median'} choices={['median',...comparisonOptions.filter(p=>p.id!==selected?.id).map(p=>p.id)]}
            choiceLabels={{median:'League median',...Object.fromEntries(comparisonOptions.map(p=>[p.id,`${p.name} · ${p.teamName}`]))}} onChange={setCompareId}/>}
          description="Compare any two qualifying throwers, or use the fixed median of all qualifying players. Profile descriptions select the two largest style-percentile departures among short share, lateral share, forward gain, throwing location and sideline share. They do not use outcomes or assign a player to a fixed archetype. Bars use a shared 0–100% scale. Forward, lateral and backward partition direction; short passes and hucks overlap those direction groups.">
          {selected?<div data-reviewed-rows>
            <div className="ufa-thrower-selected"><Face id={selected.id} name={selected.name}/><div><h3>{selected.name}</h3><p>{selected.teamName} · {selected.throws} passes / {selected.games} games</p></div></div>
            <div className="ufa-thrower-observations">{traits.map(t=><p key={t.field}><strong>{format(t.value,t.unit)}</strong> {t.label} <span>· league median {format(t.median,t.unit)}</span></p>)}</div>
            <div className="ufa-thrower-legend"><span><i/>{selected.name}</span><span><i/>{comparisonName}</span></div>
            {passing.map(r=><div className="ufa-thrower-bar-row" key={r.field}>
              <span>{r.label}</span><span className="ufa-thrower-bar-values"><b>{format(r.playerValue,r.unit)}</b><span>{format(r.comparisonValue,r.unit)}</span></span>
              <div className="ufa-thrower-bars" role="img" aria-label={`${r.label}: ${selected.name} ${format(r.playerValue,r.unit)}; ${comparisonName} ${format(r.comparisonValue,r.unit)}`}>
                <i style={{width:`${r.playerValue*100}%`}}/><i style={{width:`${r.comparisonValue*100}%`}}/>
              </div>
            </div>)}
            <details className="ufa-thrower-details"><summary>Distances & throwing locations</summary>
              <DataTable rows={distances} columns={comparisonColumns(selected.name,comparisonName)} searchable={false} compactNumbers={false} caption="All-pass distances and throwing locations"/>
              <p className="ufa-profile-note">Locations run from 0 at the back of your own end zone toward 120. Gain excludes sideways distance; flight includes it.</p>
            </details>
            <Button onClick={onOpenFieldGuide}>See directions on a field</Button>
            <p className="ufa-profile-note">Observed tendencies, not fixed archetypes. Longer bars do not mean better.</p>
          </div>:<p className="ufa-profile-note">Choose a player from the directory.</p>}
        </DataComponent>
      </SortableItem>
      <SortableItem id="ufa-thrower-results" label="Recorded results" kind="table" span={6} minSpan={6}>
        <DataComponent id="ufa-thrower-results" queryId="throwerProfiles" queryIds={['throwerProfiles','throwerReference']} kind="table" title="Recorded results"
          sourceRowsByQuery={sourceRowsByQuery} displayRows={outcomes} scopeFilters={selectionScope}
          description="Actual completion counts drops as failures. Supplied-model CPOE instead credits recorded drops to the thrower: (completions + drops) / passes minus mean available cp. Do not subtract xCP from actual completion to reproduce it. Totals depend on playing time and role. Verified pre-assists use only unambiguous linked passes before a goal and are not exact official hockey-assist totals. No future-season quality or replacement claim is made.">
          {selected?<div data-reviewed-rows>
            <p className="ufa-profile-note"><strong>{selected.name}</strong>: {selected.completions} completed / {selected.throws} passes{candidate?` · ${candidate.name}: ${candidate.completions} / ${candidate.throws}`:` · Median of ${profiles.length} qualifying players`}</p>
            <DataTable rows={outcomes} columns={comparisonColumns(selected.name,comparisonName)} searchable={false} compactNumbers={false} caption="Observed passing outcomes; comparison does not account for playing time or role"/>
            <p className="ufa-profile-note">CPOE gives the thrower credit for recorded drops; actual completion does not. pp = percentage points.</p>
            <p className="ufa-profile-note">aEC, assists and verified pre-assists are season totals. Different pass counts and playing time matter.</p>
            {(selected.scoredPasses<selected.throws||candidate&&candidate.scoredPasses<candidate.throws)&&<p className="ufa-profile-note">Some passes lack expected-completion values. xCP uses only scored passes; CPOE uses all pass outcomes. See source rows for coverage.</p>}
            {(selected.missingAec>0||candidate?.missingAec>0)&&<p className="ufa-profile-note">Some source aEC values are missing; the displayed total sums available values.</p>}
          </div>:<p className="ufa-profile-note">Choose a player to see recorded outcomes.</p>}
        </DataComponent>
      </SortableItem>
    </SortableRegion>
    <p className="ufa-profile-scope" data-reviewed-rows>October 12, 2026 export · 131/132 regular-season games available; Pittsburgh at Chicago on July 18 is missing. League medians stay fixed when you filter.</p>
  </section>;
}
