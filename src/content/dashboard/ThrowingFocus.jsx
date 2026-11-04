import React,{useEffect,useMemo,useRef,useState} from 'react';
import {Button,ChartMark,ChartTooltip,DataComponent,DataTable,Dropdown,SegmentedControl,SortableItem,SortableRegion} from '../../data-app-public.jsx';
import {Face} from './Field.jsx';
import {focusDirectory} from './throwing-focus-model.js';
import {LONG_FIELD,THROW_TYPES,fieldPoint,longThrowsModel,longThrowRecords,throwHitArea} from './long-throws-model.js';
import './throwing-focus.css';

const count=n=>n.toLocaleString(),percent=n=>Number.isFinite(n)?`${(n*100).toFixed(1).replace(/\.0$/,'')}%`:'—';
const value=n=>Number.isFinite(n)?n.toFixed(1):'Unavailable';
const points=n=>{if(!Number.isFinite(n))return '—';const rounded=Number((n*100).toFixed(1));return `${rounded>0?'+':''}${rounded.toFixed(1)} pp`;};
const outcome=e=>e.complete?'complete':'incomplete';

function ThrowVector({event,prefix}) {
  const [x1,y1]=fieldPoint(event.tx,event.ty),[x2,y2]=fieldPoint(event.rx,event.ry);
  return <g className={`ufa-long-vector ufa-long-${outcome(event)}`}>
    <line x1={x1} y1={y1} x2={x2} y2={y2} markerEnd={`url(#${prefix}-${outcome(event)})`}/>
    <circle cx={x1} cy={y1} r="2.1"/>
  </g>;
}

function LongThrowField({model,player,names,slot,filter}) {
  const [focused,setFocused]=useState(null);
  const selectionRef=useRef(null);
  useEffect(()=>{
    if(!focused)return;
    const frame=requestAnimationFrame(()=>{
      selectionRef.current?.scrollIntoView({block:'nearest',behavior:'auto'});
      selectionRef.current?.focus({preventScroll:true});
    });
    return()=>cancelAnimationFrame(frame);
  },[focused]);
  const prefix=`ufa-long-${slot}`,selected=model.rows.find(e=>e.id===focused);
  const records=useMemo(()=>longThrowRecords(model,player,names),[model,player,names]);
  const byId=useMemo(()=>new Map(records.map(r=>[r.id,r])),[records]);
  const selectedRecord=selected&&byId.get(selected.id);
  const {width,height,left,top,scale}=LONG_FIELD,fieldWidth=120*scale,fieldHeight=53.3*scale;
  const viewBox=`0 0 ${width} ${height}`;
  return <article className="ufa-long-player" aria-label={`${player.name} throws`} data-reviewed-rows>
    <div className="ufa-focus-identity"><Face id={player.id} name={player.name}/><div><h3>{player.name}</h3><p>{player.teamName} · {player.games} games</p></div></div>
    <dl className="ufa-long-stats">
      <div><dt>Attempts</dt><dd>{count(model.attempts)}</dd><p>{percent(model.share)} of all throws</p></div>
      <div><dt>Completion %</dt><dd>{percent(model.completion)}</dd><p>{count(model.completed)} completed</p></div>
      <div><dt>CPOE</dt><dd className="ufa-long-metric">{points(model.cpoe)}</dd><p>Selected throws</p></div>
      <div><dt>Lag contribution</dt><dd>{value(player.lagContribution)}</dd><p>Whole season</p></div>
    </dl>
    <div className={`ufa-long-field${selected?' has-selection':''}`} data-chart-interaction-root role="group" aria-label={`${player.name}: all ${model.attempts} attempts · ${filter.label}`}>
      <svg viewBox={viewBox} aria-hidden="true" className="ufa-long-field-base">
        <defs>{['complete','incomplete'].map(kind=><marker key={kind} id={`${prefix}-${kind}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="4" markerHeight="4" orient="auto"><path className={`ufa-long-${kind}`} d="M0 0L8 4L0 8Z"/></marker>)}</defs>
        <rect x={left} y={top} width={fieldWidth} height={fieldHeight} className="ufa-long-pitch"/>
        <rect x={left} y={top} width={20*scale} height={fieldHeight} className="ufa-long-endzone"/>
        <rect x={left+100*scale} y={top} width={20*scale} height={fieldHeight} className="ufa-long-endzone"/>
        <text x={left} y="22">Own end zone</text>
        <text x={left+fieldWidth} y="22" textAnchor="end" className="ufa-long-attack">Attacking end zone →</text>
        {[0,20,40,60,80,100,120].map(y=><g key={y}>
          <text x={fieldPoint(0,y)[0]} y={top+fieldHeight+16} textAnchor="middle">{y}</text>
          {y>0&&y<120&&<line x1={fieldPoint(0,y)[0]} x2={fieldPoint(0,y)[0]} y1={top} y2={top+fieldHeight} className={y===20||y===100?'ufa-long-goalline':'ufa-long-yardline'}/>}
        </g>)}
        <text x={left+fieldWidth/2} y={top+fieldHeight+34} textAnchor="middle">Field length in yards</text>
        <g className="ufa-long-base-vectors">{model.rows.map(e=><ThrowVector key={e.id} event={e} prefix={prefix}/>)}</g>
      </svg>
      {model.rows.map(e=>{
        const row=byId.get(e.id),label=`${player.name} → ${row.receiver}`;
        return <ChartMark key={e.id} className="ufa-long-mark" style={{clipPath:throwHitArea(e)}} aria-label={`${label}, ${row.outcome.toLowerCase()}, ${value(row.length)} yards, ${e.game}`}
          context={{kind:'chart',chartType:'scatter',label,value:row.length,row,
            actions:[{label:'Highlight this throw',onSelect:()=>setFocused(e.id)}]}}
          tooltip={<ChartTooltip active label={label} headerValue={`${row.outcome} · ${value(row.length)} yd`} details={[{label:'Expected completion',value:percent(row.expectedCompletion)},{label:'CPOE',value:points(row.cpoe)},{label:'Lag contribution',value:'Not provided per throw'},{label:'Game',value:e.game},{label:'Forward gain',value:`${value(row.forwardGain)} yd`}]} />}>
          <svg viewBox={viewBox} aria-hidden="true"><ThrowVector event={e} prefix={prefix}/></svg>
        </ChartMark>;
      })}
      {selected&&<svg className="ufa-long-selected" viewBox={viewBox} aria-hidden="true"><ThrowVector event={selected} prefix={prefix}/></svg>}
      {!model.attempts&&<p className="ufa-long-empty">No throws recorded for {filter.label.toLowerCase()}.</p>}
    </div>
    {selectedRecord&&<div ref={selectionRef} tabIndex={-1} className="ufa-long-selection" role="region" aria-label={`${player.name} selected throw`}>
      <div className="ufa-long-selection-header"><p>{selectedRecord.receiver} · {selectedRecord.outcome} · {value(selectedRecord.length)} yd<br/><span>{selectedRecord.game}</span></p><Button onClick={()=>setFocused(null)}>Clear highlight</Button></div>
      <dl className="ufa-long-throw-metrics">
        <div><dt>Expected completion</dt><dd>{percent(selectedRecord.expectedCompletion)}</dd></div>
        <div><dt>CPOE</dt><dd>{points(selectedRecord.cpoe)}</dd></div>
        <div><dt>Lag contribution</dt><dd className="ufa-long-unavailable">Not provided per throw</dd></div>
      </dl>
      {selected?.drop&&<p className="ufa-focus-note">This was dropped. CPOE gives the thrower completion credit; actual completion counts it as incomplete.</p>}
    </div>}
    {model.missingExpectation>0&&<p className="ufa-focus-note">Expected-completion data is available for {count(model.scoredAttempts)} of {count(model.attempts)} throws.</p>}
    {model.missingLocations>0&&<p className="ufa-focus-note">{count(model.missingLocations)} throws lack coordinates and cannot be classified or plotted.</p>}
    <details className="ufa-focus-records"><summary>Throw records ({count(model.attempts)})</summary>
      <DataTable rows={records} searchable={false} columns={[
        {field:'game',label:'Game'},{field:'receiver',label:'Thrown to'},
        {field:'length',label:'Length (yd)',renderCell:value},{field:'outcome',label:'Result'},
        {field:'expectedCompletion',label:'Expected completion',renderCell:percent},
        {field:'cpoe',label:'CPOE',renderCell:points},
      ]} caption={`${player.name} · ${filter.label}`}/>
    </details>
  </article>;
}

export function ThrowingFocus({queries}) {
  const summaries=queries.shownSpaceThrowers?.rows||[],events=queries.events?.rows||[],players=queries.players?.rows||[];
  const [firstId,setFirstId]=useState('aatkins'),[secondId,setSecondId]=useState('jnissen'),[type,setType]=useState('long');
  const filter=THROW_TYPES.find(option=>option.id===type);
  const directory=useMemo(()=>focusDirectory(summaries),[summaries]);
  const choices=useMemo(()=>directory.map(p=>p.id),[directory]);
  const labels=useMemo(()=>Object.fromEntries(directory.map(p=>[p.id,`${p.name} · ${p.teamName}`])),[directory]);
  const names=useMemo(()=>Object.fromEntries(players.map(p=>[p.id,p.name])),[players]);
  const first=summaries.find(p=>p.id===firstId)||directory[0],second=summaries.find(p=>p.id===secondId)||directory[1]||directory[0];
  const firstModel=useMemo(()=>longThrowsModel(events,first?.id,type),[events,first?.id,type]);
  const secondModel=useMemo(()=>longThrowsModel(events,second?.id,type),[events,second?.id,type]);
  const sourceRows=useMemo(()=>[...new Map([...firstModel.allPasses,...secondModel.allPasses].map(e=>[e.id,e])).values()],[firstModel,secondModel]);
  const displayRows=useMemo(()=>first&&second?[...new Map([...longThrowRecords(firstModel,first,names),...longThrowRecords(secondModel,second,names)].map(e=>[e.id,e])).values()]:[],[first,second,firstModel,secondModel,names]);
  if(!first||!second)return <p role="status">Player summaries are unavailable in this snapshot.</p>;
  const scope=[{label:'Players',value:[...new Set([first.name,second.name])].join(' / ')},{label:'Season',value:'2026 including playoffs · all lines'}];
  const selectedPlayers=[...new Map([first,second].map(p=>[p.id,p])).values()];
  return <section className="ufa-throwing-focus ufa-long-comparison" aria-label="Compare throws by distance">
    <h2 data-editable-id="ufa-long-throw-question">How often do they throw each distance—and complete it?</h2>
    <div className="ufa-long-pickers">
      <Dropdown label="Player 1" searchable placeholder="Search a player or team…" value={first.id} choices={choices} choiceLabels={labels} onChange={setFirstId}/>
      <Dropdown label="Player 2" searchable placeholder="Search a player or team…" value={second.id} choices={choices} choiceLabels={labels} onChange={setSecondId}/>
    </div>
    <SortableRegion id="ufa:throwing-focus" variant="stack" authoredRevision={1} authoredOrder={['ufa-throwing-explorer','ufa-throwing-season']} label="Throwing comparison">
      <SortableItem id="ufa-throwing-explorer" label="Throws by distance" kind="custom">
        <DataComponent id="ufa-throwing-explorer" queryId="events" queryIds={['events','shownSpaceThrowers']} kind="custom" title="Throws by distance"
          sourceRowsByQuery={{events:sourceRows,shownSpaceThrowers:selectedPlayers}} displayRows={displayRows}
          scopeFilters={[...scope,{label:'Throw type',value:type==='hucks'?'Hucks (>40 yards and >30 yards forward)':`${filter.label} (≥${filter.min}${Number.isFinite(filter.max)?` and <${filter.max}`:''} yards)`}]}
          description="Both fields show every qualifying attempt by the selected players on identical scales, attacking toward Y=120, shown to the right. Solid lines are complete and dashed lines incomplete, including drops and unnamed targets. Dots mark throwing locations; arrows end at recorded target locations. Lines connect endpoints, not tracked flight paths or player movement. Attempts, completion percentage and CPOE cover the selected throws. CPOE is (completed or dropped attempts) / attempts minus the mean available source cp, matching the source player-game calculation; drops receive thrower credit. Individual CPOE is credited outcome minus cp, not the raw cpoe field, which is 1 on drops. Lag contribution comes from shownSpaceThrowers and remains a whole-season total. The database has no per-throw LC field; a next-throw aEC reconstruction failed reconciliation with official totals, so no filtered or per-throw LC is inferred. Share of all throws divides qualifying attempts by all of that player’s non-stall attempts, so it describes frequency rather than just season volume. Source inspection includes all non-stall passes for both players to preserve these denominators; displayed rows contain only the plotted throws. Hover to highlight a throw; click for the shared action menu. Completion percentage is unadjusted; CPOE compares credited outcomes with the source model’s expected completion probabilities."
          headerControls={<SegmentedControl ariaLabel="Throw distance or hucks" className="ufa-throw-distance-options" value={type} onChange={setType} options={THROW_TYPES.map(option=>({value:option.id,label:option.label}))}/>}
        >
          <p className="ufa-focus-note ufa-long-definition">{type==='hucks'?'Hucks travel over 40 yards and gain over 30 yards forward.':type==='long'?'40+ yards is the straight-line distance from thrower to target, in any direction.':`${filter.label} includes ${filter.min} and excludes ${filter.max}. Distance is measured in a straight line from thrower to target, in any direction.`}</p>
          <div className="ufa-long-legend"><span><i className="ufa-long-key-complete"/>Complete</span><span><i className="ufa-long-key-incomplete"/>Incomplete</span><span className="ufa-focus-note">Dot = throwing location · Arrow = target · Hover to inspect</span></div>
          <p className="ufa-focus-note ufa-long-metric-note">CPOE is completion above expected, in percentage points (pp); it credits recorded drops to the thrower. Lag contribution is the whole-season total; per-throw LC is unavailable.</p>
          <div className="ufa-long-fields">
            <LongThrowField key={`first:${first.id}:${type}`} model={firstModel} player={first} names={names} slot="first" filter={filter}/>
            <LongThrowField key={`second:${second.id}:${type}`} model={secondModel} player={second} names={names} slot="second" filter={filter}/>
          </div>
        </DataComponent>
      </SortableItem>
      <SortableItem id="ufa-throwing-season" label="Shown Space season stats" kind="custom">
        <DataComponent id="ufa-throwing-season" queryId="shownSpaceThrowers" queryIds={['shownSpaceThrowers','events']} title="Shown Space season stats" kind="custom"
          sourceRowsByQuery={{shownSpaceThrowers:selectedPlayers,events:sourceRows}}
          displayRows={selectedPlayers.map(p=>({...p,completionRate:p.recordedAttempts?p.recordedCompletions/p.recordedAttempts:null}))} scopeFilters={scope}
          description="Whole-season totals, including playoffs. aEC and lag contribution are unchanged original Shown Space leaderboard values, including stalls. Season Completion % is completed / non-stall attempts in the export; drops count as incomplete. It is not the differently adjusted leaderboard CP% field. These values remain fixed when changing distance bands or the huck filter. LC is available only as a season total; no filtered LC is inferred.">
          <details className="ufa-long-season-details"><summary>Show whole-season aEC, lag contribution and completion %</summary>
            <div className="ufa-long-season-grid" data-reviewed-rows>{[first,second].map((p,i)=><div key={i}>
              <h3>{p.name}</h3><dl><div><dt>Thrower aEC</dt><dd>{value(p.throwerAec)}</dd></div><div><dt>Lag contribution</dt><dd>{value(p.lagContribution)}</dd></div><div><dt>Season completion %</dt><dd>{percent(p.recordedAttempts?p.recordedCompletions/p.recordedAttempts:null)}</dd></div></dl>
              {(p.recordedAttempts!==p.sourceAttempts||p.recordedCompletions!==p.sourceCompletions)&&<p className="ufa-focus-note">Export: {p.recordedCompletions} / {p.recordedAttempts}; source season summary: {p.sourceCompletions} / {p.sourceAttempts}. The fields and completion rates use the exported throws.</p>}
            </div>)}</div>
            <p className="ufa-focus-note">Whole season, including playoffs. <a href="https://shownspace.com/about" target="_blank" rel="noreferrer">Shown Space’s definitions ↗</a></p>
          </details>
        </DataComponent>
      </SortableItem>
    </SortableRegion>
    <p className="ufa-focus-note ufa-focus-coverage">Throw records: October 12 export · 2026 including playoffs. One regular-season game is missing: Pittsburgh at Chicago, July 18. Shown Space season totals checked November 3.</p>
  </section>;
}
