import React,{useEffect,useMemo,useState} from 'react';
import {Button,ChartMark,ChartTooltip,DataComponent,Dropdown,SegmentedControl,SortableItem,SortableRegion} from '../../data-app-public.jsx';
import {int,fmt} from './model.js';
import {Face,playerName} from './Field.jsx';
import {connectionPlayerDirectory,connectionPlayers,connectionSearchTeam,passGeometry} from './connections-model.js';
import {buildRadials,directionAngle,radialHitArea,radialPoint,radialRecords,radialWedge} from './radial-model.js';
import './radials.css';

const percent=value=>value===null?'—':`${fmt(value*100,1)}%`;
const range=bucket=>`${fmt(bucket.startAngle,0)}°–<${fmt(bucket.endAngle,0)}°`;
const outcomeLabel=event=>event.stall?'Stall':event.complete?'Complete':event.drop?'Drop':'Turnover';

function exportPasses(rows) {
  const fields=['game','team','throwerName','receiverName','outcome','directionDegrees','flightYards','downfieldYards','huck','tx','ty','rx','ry'];
  const quote=value=>'"'+String(value??'').replaceAll('"','""')+'"';
  const csv=[fields,...rows.map(row=>fields.map(field=>row[field]))].map(row=>row.map(quote).join(',')).join('\n');
  const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
  const link=document.createElement('a');link.href=url;link.download='ufa-radial-passes.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function DirectionDiagram({side,role,name,scaleMax,selection,onInspect}) {
  const maxRadius=144,innerRadius=9.6,width=360/side.buckets.length;
  return <div className="ufa-radial-diagram" data-chart-interaction-root data-reviewed-rows>
    <svg className="ufa-radial-grid" viewBox="0 0 400 400" aria-hidden="true">
      {[.33,.66,1].map(fraction=><circle key={fraction} cx="200" cy="200" r={maxRadius*fraction} fill="none" className="ufa-radial-ring"/>)}
      {side.buckets.map(bucket=>{const [x,y]=radialPoint(bucket.centerAngle,maxRadius);return <line key={bucket.index} x1="200" y1="200" x2={x} y2={y} className="ufa-radial-spoke"/>;})}
      {[0,90,180,270].map(angle=>{const [x,y]=radialPoint(angle,174);return <text key={angle} x={x} y={y} dominantBaseline="middle" textAnchor="middle">{angle}°</text>;})}
    </svg>
    {side.buckets.map(bucket=>{
      const radius=innerRadius+(maxRadius-innerRadius)*(scaleMax>0?(bucket.share??0)/scaleMax:0);
      const selected=selection?.role===role&&selection.index===bucket.index;
      return <ChartMark key={bucket.index} className="ufa-radial-mark" style={{clipPath:radialHitArea(bucket.centerAngle,width)}}
        aria-label={`${role==='throw'?'Throws':'Receiving'}, ${range(bucket)}, ${int(bucket.count)} events, ${percent(bucket.share)}`} aria-pressed={selected}
        context={{kind:'chart',chartType:'radial',label:`${name} · ${role==='throw'?'Throws':'Receiving'} · ${range(bucket)}`,value:bucket.count,
          row:{direction:range(bucket),events:bucket.count,share:bucket.share,completed:bucket.completed},
          actions:[{label:'Inspect passes',onSelect:()=>onInspect({role,index:bucket.index})}]}}
        tooltip={<ChartTooltip active label={range(bucket)} headerValue={percent(bucket.share)} details={[{label:'Recorded events',value:int(bucket.count)},{label:'Completed',value:int(bucket.completed)},{label:'Share of',value:`${int(side.total)} ${role==='throw'?'throws':'targets'}`}]} />}>
        <svg viewBox="0 0 400 400" aria-hidden="true">
          <path className="ufa-radial-focus" d={radialWedge(bucket.centerAngle,width,maxRadius)}/>
          {bucket.count>0&&<path className="ufa-radial-wedge" d={radialWedge(bucket.centerAngle,width,radius)} data-count={bucket.count}/>}
        </svg>
      </ChartMark>;
    })}
  </div>;
}

export function Radials({events,allEvents,players,teams,team,onTeamChange,scopeFilters}) {
  const roster=useMemo(()=>connectionPlayers(events),[events]);
  const directory=useMemo(()=>connectionPlayerDirectory(allEvents,players,teams).filter(player=>player.id!=='unknown'),[allEvents,players,teams]);
  const [chosenPlayer,setChosenPlayer]=useState(()=>({id:roster.includes('aatkins')?'aatkins':roster[0],team}));
  const [passType,setPassType]=useState('all'),[outcome,setOutcome]=useState('all'),[scale,setScale]=useState('original');
  const [selection,setSelection]=useState(null),[page,setPage]=useState(0);
  const chosenMatchesTeam=team==='all'||chosenPlayer.team===team||directory.find(player=>player.id===chosenPlayer.id)?.teamIds.includes(team);
  const playerId=chosenPlayer.id&&chosenMatchesTeam?chosenPlayer.id:roster[0],name=playerName(players,playerId);
  const choices=useMemo(()=>directory.map(player=>player.id),[directory]);
  const choiceLabels=useMemo(()=>Object.fromEntries(directory.map(player=>[player.id,player.label])),[directory]);
  const choosePlayer=id=>{
    const nextTeam=connectionSearchTeam(directory.find(player=>player.id===id),team);
    setChosenPlayer({id,team:nextTeam});if(nextTeam!==team)onTeamChange(nextTeam);
  };
  const model=useMemo(()=>buildRadials(events,playerId,{passType,outcome}),[events,playerId,passType,outcome]);
  useEffect(()=>{setSelection(null);setPage(0);},[model]);
  const selectedEvents=useMemo(()=>radialRecords(model,selection),[model,selection]);
  const recordRows=useMemo(()=>selectedEvents.map(event=>{const geometry=passGeometry(event);return {...event,
    throwerName:playerName(players,event.thrower),receiverName:event.receiver?playerName(players,event.receiver):'Unrecorded player',
    outcome:outcomeLabel(event),directionDegrees:directionAngle(event.throwAngle),flightYards:geometry.distance,downfieldYards:geometry.gain,huck:geometry.huck};}),[selectedEvents,players]);
  const filteredScope=[...scopeFilters.map(filter=>({...filter,field:({'Team':'team','Season phase':'phase','Line':'line'})[filter.label]})),
    {field:'thrower',label:'Player (thrower or receiver)',value:name},
    {field:'rx',label:'Pass type',value:passType==='hucks'?'Hucks only: flight ≥40 yd and downfield ≥30 yd':'All passes'},
    {field:'complete',label:'Outcome',value:outcome==='all'?'All recorded events (original)':'Completed passes'},
    {field:'throwAngle',label:'Direction',value:'Recorded angles only; twelve 30° buckets'}];
  const selectedBucket=selection?model[selection.role].buckets[selection.index]:null;
  const selectedLabel=selection?`${selection.role==='throw'?'Throws':'Receiving'} · ${range(selectedBucket)}`:'';
  return <section className="ufa-radials" aria-label="Player throw radials">
    <div className="ufa-connection-controls">
      <div className="ufa-player-search" onFocusCapture={event=>{if(event.target.getAttribute('role')==='combobox')event.target.select();}}>
        <span>Search players <small>All teams</small></span>
        <Dropdown label="Search players" searchable placeholder="Type a player or team name…" value={playerId||'all'} allLabel="Choose a player" choices={choices} choiceLabels={choiceLabels} onChange={choosePlayer}/>
      </div>
      <div className="ufa-pass-type"><span>Pass type</span><SegmentedControl value={passType} onChange={setPassType} options={[{value:'all',label:'All passes'},{value:'hucks',label:'Hucks only'}]}/></div>
      <Dropdown label="Outcome" showLabel value={outcome} choices={['all','complete']} allLabel="All recorded (original)" choiceLabels={{complete:'Completed passes'}} onChange={setOutcome}/>
      <Dropdown label="Scale" showLabel value={scale} choices={['original','shared']} choiceLabels={{original:'Original: each diagram',shared:'Shared percentage'}} onChange={setScale}/>
    </div>
    <p className="ufa-radial-note">Twelve directions, matching Shown Space’s radial diagrams. {passType==='hucks'?'Hucks travel at least 40 yards and gain at least 30 yards downfield.':'Percentages show how often a player uses each direction.'}</p>
    {!playerId?<div className="ufa-empty" role="status">No recorded players in this scope. Search for a player above to explore another team.</div>:<>
      <div className="ufa-radial-player"><Face id={playerId} name={name}/><h3>{name}</h3></div>
      <SortableRegion id="ufa:radials" variant="freeform" authoredRevision={1} className="ufa-radial-layout">
        {['throw','receive'].map(role=>{
          const side=model[role],scaleMax=scale==='shared'?Math.max(model.throw.maxShare,model.receive.maxShare):side.maxShare;
          const title=role==='throw'?'Throwing directions':'Receiving directions';
          const displayRows=side.buckets.map(bucket=>({direction:range(bucket),displayAngle:bucket.centerAngle,events:bucket.count,share:bucket.share,completed:bucket.completed}));
          return <SortableItem key={role} id={`ufa-radial-${role}`} label={title} kind="custom">
            <DataComponent id={`ufa-radial-${role}`} queryId="events" title={title} kind="custom" sourceRows={side.sourceRows} displayRows={displayRows}
              scopeFilters={[...filteredScope,{field:role==='throw'?'thrower':'receiver',label:'Role',value:role==='throw'?'Thrower':'Receiver / recorded target'},{field:'throwAngle',label:'Display scale',value:scale==='shared'?'Shared percentage':'Each role’s own largest bucket'}]}
              description="Buckets use the recorded throw angle, normalized to 0–360°. As on Shown Space, each wedge is drawn at its bucket’s lower-edge angle, with 0° at the top and increasing clockwise. Receiving uses the pass’s original flight angle, without a 180° rotation.">
              <p className="ufa-radial-total" data-reviewed-rows><strong>{int(side.total)}</strong> {outcome==='complete'?(role==='throw'?'completed passes':'catches'):(role==='throw'?'recorded throws':'recorded targets')}</p>
              {side.total>0?<><DirectionDiagram key={`${playerId}-${passType}-${outcome}-${JSON.stringify(scopeFilters)}`} side={side} role={role} name={name} scaleMax={scaleMax} selection={selection} onInspect={value=>{setSelection(value);setPage(0);}}/>
                <p className="ufa-radial-scale" data-reviewed-rows>Outer ring: {percent(scaleMax)} of {role==='throw'?'throws':'targets'}</p></>:<div className="ufa-empty" role="status">No {outcome==='complete'?'completed ':''}{passType==='hucks'?'hucks':'passes'} {role==='throw'?'thrown by':'to'} {name} with recorded angles in this scope.</div>}
              {side.missingAngle>0&&<p className="ufa-coverage">{int(side.missingAngle)} event(s) have no recorded angle and are excluded.</p>}
            </DataComponent>
          </SortableItem>;
        })}
      </SortableRegion>
      <p className="ufa-radial-note">{scale==='original'?'Each diagram scales to its own busiest direction; compare the percentages to compare roles.':'Both diagrams use the same percentage scale.'} Angles follow the original chart: 0° at the top, increasing clockwise. Receiving shows the disc’s flight direction. {outcome==='all'?'All recorded includes incompletions, named targets and, for All passes, stalls. ':''}{model.sourceRows.length>0?'Select a wedge, then Inspect passes.':''}</p>
      <DataComponent id="ufa-radial-records" queryId="events" title="Direction passes" kind="table" sourceRows={selectedEvents} displayRows={recordRows}
        scopeFilters={[...filteredScope,...(selectedLabel?[{field:'throwAngle',label:'Selected direction',value:selectedLabel}]:[])]}
        headerControls={<>{selection&&<Button onClick={()=>{setSelection(null);setPage(0);}}>Show all directions</Button>}<Button disabled={!recordRows.length} onClick={()=>exportPasses(recordRows)}>Export {int(recordRows.length)} passes</Button></>}>
        {selection&&<p className="ufa-radial-selected" aria-live="polite" data-reviewed-rows>{selectedLabel} · {int(selectedEvents.length)} passes</p>}
        <details className="ufa-records" key={`${playerId}-${passType}-${outcome}-${selectedLabel}`} open={Boolean(selection)} data-reviewed-rows>
          <summary>Inspect {int(recordRows.length)} passes · {name}</summary>
          <div className="ufa-table-scroll"><table><thead><tr><th>Game</th><th>From → to</th><th>Outcome</th><th className="ufa-num">Angle</th><th>Huck</th><th className="ufa-num">Flight (yd)</th></tr></thead>
            <tbody>{recordRows.slice(page*12,(page+1)*12).map(row=><tr key={row.id}><td>{row.game}</td><td>{row.throwerName} → {row.receiverName}</td><td>{row.outcome}</td><td className="ufa-num">{fmt(row.directionDegrees,1)}°</td><td>{row.huck?'Yes':'No'}</td><td className="ufa-num">{fmt(row.flightYards,1)}</td></tr>)}</tbody>
          </table></div>
          <div className="ufa-pagination"><Button disabled={page===0} onClick={()=>setPage(page-1)}>Previous</Button><span>{page+1} / {Math.max(1,Math.ceil(recordRows.length/12))}</span><Button disabled={(page+1)*12>=recordRows.length} onClick={()=>setPage(page+1)}>Next</Button></div>
        </details>
      </DataComponent>
    </>}
  </section>;
}
