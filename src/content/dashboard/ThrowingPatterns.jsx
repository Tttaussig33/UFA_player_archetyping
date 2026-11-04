import React,{useEffect,useMemo,useRef,useState} from 'react';
import {Button,ChartMark,ChartTooltip,DataComponent,DataTable,Dropdown,SegmentedControl,SortableItem,SortableRegion} from '../../data-app-public.jsx';
import {Face} from './Field.jsx';
import {focusDirectory,focusModel,directionSlice,directionHit,throwLength} from './throwing-focus-model.js';
import './throwing-focus.css';

const count=n=>n.toLocaleString(),percent=n=>Number.isFinite(n)?`${(n*100).toFixed(1).replace(/\.0$/,'')}%`:'—';
const value=n=>Number.isFinite(n)?n.toFixed(1):'Unavailable';

// Archived single-player length/direction explorer; not mounted by current navigation.
export function ThrowingPatterns({queries}) {
  const summaries=queries.shownSpaceThrowers?.rows||[],events=queries.events?.rows||[];
  const players=queries.players?.rows||[];
  const [playerId,setPlayerId]=useState('aatkins'),[view,setView]=useState('length'),[selection,setSelection]=useState(null);
  const [recordsOpen,setRecordsOpen]=useState(false),[recordsRequest,setRecordsRequest]=useState(0);
  const recordsRef=useRef(null),recordsFilterRef=useRef(null);
  const directory=useMemo(()=>focusDirectory(summaries),[summaries]);
  const player=summaries.find(r=>r.id===playerId)||directory[0];
  const model=useMemo(()=>focusModel(events,player?.id,view,selection),[events,player,view,selection]);
  const names=useMemo(()=>Object.fromEntries(players.map(p=>[p.id,p.name])),[players]);
  const records=useMemo(()=>model.rows.map(e=>({id:e.id,game:e.game,receiver:names[e.receiver]||'Unrecorded target',
    length:throwLength(e),outcome:e.complete?'Complete':e.drop?'Drop':'Incomplete',throwerAec:e.throwAec})),[model.rows,names]);
  const changePlayer=id=>{setPlayerId(id);setSelection(null);setRecordsOpen(false);};
  const changeView=v=>{setView(v);setSelection(null);setRecordsOpen(false);};
  const inspectThrows=id=>{setSelection(id);setRecordsOpen(true);setRecordsRequest(n=>n+1);};
  useEffect(()=>{
    if(!recordsOpen||!recordsRequest)return;
    const frame=requestAnimationFrame(()=>{
      const details=recordsRef.current;
      if(!details?.open)return;
      (recordsFilterRef.current||details).scrollIntoView({block:'start',behavior:'auto'});
      details.querySelector('summary')?.focus({preventScroll:true});
    });
    return()=>cancelAnimationFrame(frame);
  },[recordsOpen,recordsRequest]);
  const selectedLabel=model.selected?.label||(view==='length'?'All throw lengths':'All recorded directions');
  const max=Math.max(1,...model.groups.map(g=>g.attempts));
  const scope=[{label:'Player',value:player?.name||'None'},{label:'Season',value:'2026 including playoffs · all lines'}];
  const seasonCompletion=player?.recordedAttempts?player.recordedCompletions/player.recordedAttempts:null;
  if(!player)return <p role="status">Shown Space player summaries are unavailable in this snapshot.</p>;
  return <section className="ufa-throwing-focus" aria-label="Simple throwing profiles">
    <h2 data-editable-id="ufa-throwing-question">What does this player throw—and how successful is it?</h2>
    <div className="ufa-focus-player-picker">
      <Dropdown label="Find a player" searchable placeholder="Search any player or team…" value={player.id}
        choices={directory.map(p=>p.id)} choiceLabels={Object.fromEntries(directory.map(p=>[p.id,`${p.name} · ${p.teamName}`]))} onChange={changePlayer}/>
    </div>
    <SortableRegion id="ufa:throwing-focus" variant="stack" authoredOrder={['ufa-throwing-season','ufa-throwing-explorer']} label="Throwing profile">
      <SortableItem id="ufa-throwing-season" label="Shown Space season stats" kind="custom">
        <DataComponent id="ufa-throwing-season" queryId="shownSpaceThrowers" queryIds={['shownSpaceThrowers','events']} title="Shown Space season stats" kind="custom"
          sourceRowsByQuery={{shownSpaceThrowers:[player],events:model.allPasses}} displayRows={[{...player,completionRate:seasonCompletion}]} scopeFilters={scope}
          description="Season statistics including playoffs. aEC and lag contribution are original Shown Space leaderboard totals, including stalls. Completion % is completed passes divided by non-stall attempts in the export; drops count as incomplete. It preserves the completion calculation previously shown beside the chart, rather than using the differently adjusted leaderboard CP% field. All three stay fixed when inspecting a throw length or direction. aEC and lag contribution depend on playing time.">
          <div className="ufa-focus-season" data-reviewed-rows>
            <div className="ufa-focus-identity"><Face id={player.id} name={player.name}/><div><h3>{player.name}</h3><p>{player.teamName} · {player.games} games</p></div></div>
            <div className="ufa-focus-source-stat"><span>Thrower aEC</span><strong>{value(player.throwerAec)}</strong><p>Scoring contribution credited to their throws.</p></div>
            <div className="ufa-focus-source-stat"><span>Lag contribution</span><strong>{value(player.lagContribution)}</strong><p>Setup value from the following throw.</p></div>
            <div className="ufa-focus-source-stat" title={`${player.recordedCompletions} completions / ${player.recordedAttempts} attempts`}><span>Completion %</span><strong>{percent(seasonCompletion)}</strong></div>
          </div>
          <p className="ufa-focus-note">Season stats, including playoffs. These stay fixed while you explore throws below. <a href="https://shownspace.com/about" target="_blank" rel="noreferrer">Shown Space’s definitions ↗</a></p>
        </DataComponent>
      </SortableItem>
      <SortableItem id="ufa-throwing-explorer" label="Throwing tendencies" kind="custom">
        <DataComponent id="ufa-throwing-explorer" queryId="events" kind="custom" title="Throwing tendencies"
          sourceRows={model.eligible} displayRows={model.displayRows}
          scopeFilters={[...scope,{label:'View',value:view==='length'?'Throw length':'Throw direction'},{label:'Throw records',value:selectedLabel}]}
          description="The chart counts physical throws in the preserved October 12 export, including incompletions and drops, excluding stalls. Select a bar directly, or a direction slice followed by Inspect throws, to open the matching records below. Completion % in the season stats stays fixed. Group completion is available on hover; drops count as incomplete. Individual aEC values remain in the throw records. Lag contribution is available only as a season total. Length ranges include their lower edge and exclude their upper edge. Direction uses the source’s twelve 30-degree bins, drawn with attack forward and 90° left. Longer bars/slices mean more attempts, not better results. The outer radius represents the busiest direction. Source inspection includes all plotted groups; selected throws are in the expandable records below."
          headerControls={<SegmentedControl value={view} onChange={changeView} options={[{value:'length',label:'Throw length'},{value:'direction',label:'Throw direction'}]}/>}
        >
          <div className="ufa-focus-explore" data-reviewed-rows>
            <div className="ufa-focus-pattern">
              <h3>What do they tend to throw?</h3>
              <p className="ufa-focus-note">{count(model.eligible.length)} throws · {view==='length'?'Select a length to see its throws.':'Longer slices mean more throws. Select a slice, then Inspect throws.'}</p>
              {view==='length'?<div className="ufa-focus-lengths">
                {model.groups.map(g=><button type="button" key={g.id} className="ufa-focus-length" aria-pressed={selection===g.id} disabled={!g.attempts}
                  onClick={()=>inspectThrows(g.id)} aria-controls="ufa-focus-throw-records" aria-expanded={selection===g.id&&recordsOpen} aria-label={`${g.label}, ${g.attempts} throws. Inspect throws.`} title={`${g.label} · ${percent(g.completion)} complete`}>
                  <span>{g.label}</span><span className="ufa-focus-length-track"><i style={{width:`${g.attempts/max*100}%`}}/></span><strong>{count(g.attempts)}</strong>
                </button>)}
                <p className="ufa-focus-note">Length is the straight-line distance from throw to target. Ranges are in yards.</p>
              </div>:<div className="ufa-focus-wheel-wrap">
                <div className="ufa-focus-wheel" data-chart-interaction-root>
                  <svg viewBox="0 0 360 360" aria-hidden="true">
                    {[48,96,144].map(r=><circle key={r} cx="180" cy="180" r={r} fill="none" className="ufa-focus-ring"/>)}
                    <text x="180" y="16" textAnchor="middle">Forward · attacking end zone ↑</text><text x="16" y="184">Left</text><text x="344" y="184" textAnchor="end">Right</text><text x="180" y="354" textAnchor="middle">Back</text>
                  </svg>
                  {model.groups.map(g=><ChartMark key={g.id} className="ufa-focus-direction" style={{clipPath:directionHit(g.startAngle,g.endAngle)}}
                    disabled={!g.attempts} aria-label={`${g.label}, ${g.startAngle} to ${g.endAngle} degrees, ${g.attempts} throws`} aria-pressed={selection===g.id}
                    context={{kind:'chart',chartType:'radial',label:g.label,value:g.attempts,row:model.displayRows.find(r=>r.id===g.id),
                      actions:[{label:'Inspect throws',onSelect:()=>inspectThrows(g.id)}]}}
                    tooltip={<ChartTooltip active label={g.label} headerValue={`${g.attempts} throws`} details={[{label:'Completion %',value:percent(g.completion)},{label:'Direction',value:`${g.startAngle}° to <${g.endAngle}°`}]} />}>
                    <svg viewBox="0 0 360 360" aria-hidden="true"><path className="ufa-focus-direction-outline" d={directionSlice(g.startAngle,g.endAngle,144)}/>{g.attempts>0&&<path className="ufa-focus-direction-fill" d={directionSlice(g.startAngle,g.endAngle,12+132*g.attempts/max)}/>}</svg>
                  </ChartMark>)}
                </div>
                {model.excluded>0&&<p className="ufa-focus-note">{model.excluded} throws have no usable direction or no distance and are left out of this direction view.</p>}
              </div>}
            </div>
          </div>
          {(player.recordedAttempts!==player.sourceAttempts||player.recordedCompletions!==player.sourceCompletions)&&<p className="ufa-focus-note" data-reviewed-rows>Our export has {player.recordedCompletions} completions / {player.recordedAttempts} attempts; Shown Space’s season summary has {player.sourceCompletions} / {player.sourceAttempts}. The explorer uses the individual exported throws.</p>}
          {model.selected&&<div ref={recordsFilterRef} className="ufa-focus-record-filter" data-reviewed-rows><span>{selectedLabel} · {count(model.rows.length)} throws</span><Button onClick={()=>inspectThrows(null)} aria-controls="ufa-focus-throw-records">Show all throws</Button></div>}
          <details id="ufa-focus-throw-records" ref={recordsRef} className="ufa-focus-records" open={recordsOpen} onToggle={event=>setRecordsOpen(event.currentTarget.open)}><summary>{recordsOpen?`${player.name} · ${selectedLabel}`:'Inspect these throws'}</summary>
            <div data-reviewed-rows><DataTable key={`${player.id}:${view}:${selection}`} rows={records} searchable={false} columns={[
              {field:'game',label:'Game'},{field:'receiver',label:'Thrown to'},{field:'length',label:'Length (yards)',renderCell:v=>value(v)},
              {field:'outcome',label:'Result'},{field:'throwerAec',label:'Thrower aEC',renderCell:v=>Number.isFinite(v)?v.toFixed(3):'—'},
            ]} caption={`${player.name} · ${selectedLabel}`}/></div>
          </details>
        </DataComponent>
      </SortableItem>
    </SortableRegion>
    <p className="ufa-focus-note ufa-focus-coverage">Throw records: October 12 export · 2026 including playoffs. One regular-season game is missing: Pittsburgh at Chicago, July 18. Shown Space season totals checked November 3.</p>
  </section>;
}
