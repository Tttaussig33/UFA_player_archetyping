import React,{useEffect,useMemo,useRef,useState} from 'react';
import {Button,ChartMark,ChartTooltip,DataComponent,Dropdown,SegmentedControl,SortableItem,SortableRegion} from '../../data-app-public.jsx';
import {ZONES,fmt,int,zoneFor} from './model.js';
import {Face,playerName} from './Field.jsx';
import {connectionPlayerDirectory,connectionSearchTeam,passGeometry} from './connections-model.js';
import {bestReleaseZone,buildDeepThrower,deepThrowerComparison,HUCK_SETUPS,precedingPasses,priorPassDirection,selectHucks,sequenceSource} from './deep-thrower-model.js';
import {DeepLeaderboard} from './DeepLeaderboard.jsx';
import {DeepSetups} from './DeepSetups.jsx';
import './deep-throwers.css';

const percent=value=>value==null?'—':`${fmt(value*100,1)}%`;
const result=e=>e.complete?'Complete':e.drop?'Drop':'Turnover';
const endpointName=(players,id)=>!id||id==='unknown'?'Unrecorded player':playerName(players,id);
const zoneName=id=>ZONES.find(z=>z.id===id)?.label||'Outside mapped field';
const metricNames={rate:'Completion rate',attempts:'Huck attempts'};
const scopeFields={'Team':'team','Season phase':'phase','Line':'line'};

function exportHucks(rows) {
  const fields=['id','game','team','quarter','point','possession','possessionThrow','throwerName','receiverName','outcome',
    'flightYards','downfieldYards','throwAec','releaseZone','tx','ty','rx','ry','previousPassId','previousThrower',
    'previousTx','previousTy','catchX','catchY','catchZone','priorPassDirection'];
  const quote=value=>'"'+String(value??'').replaceAll('"','""')+'"';
  const csv=[fields,...rows.map(row=>fields.map(field=>row[field]))].map(row=>row.map(quote).join(',')).join('\n');
  const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
  const link=document.createElement('a');link.href=url;link.download='ufa-deep-thrower-hucks.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function ZoneField({zones,kind,receiving,metric,minimum,selection,onInspect,name}) {
  const isReceive=kind==='receive',countKey=receiving==='before'?'beforeHuck':'catches';
  const maxCount=Math.max(1,...zones.map(z=>isReceive?z[countKey]:z.attempts));
  return <div className="ufa-deep-field-wrap" data-chart-interaction-root data-reviewed-rows>
    <div className="ufa-deep-direction">Attacking end zone ↑</div>
    <div className="ufa-deep-field">
      {[0,20,40,60,80,100,120].map(y=><span key={y} className="ufa-deep-yard" style={{top:`${100-y/1.2}%`}}>{y}</span>)}
      {zones.map(zone=>{
        const count=isReceive?zone[countKey]:zone.attempts;
        const qualified=isReceive||metric==='attempts'||zone.attempts>=minimum;
        const value=isReceive?count:zone[metric];
        const intensity=isReceive||metric==='attempts'?count/maxCount:(zone.rate??0);
        const label=isReceive?int(count):count?metric==='rate'?`${fmt(zone.rate*100,0)}%`:int(count):'—';
        const selected=selection?.kind===kind&&selection.zoneId===zone.id;
        const details=isReceive?[
          {label:receiving==='before'?'Catches before hucks':'Completed catches',value:int(count)},
          {label:'Share of catches in this view',value:percent(receiving==='before'?zone.beforeShare:zone.catchShare)},
        ]:[{label:'Completed / attempts',value:`${zone.completed} / ${zone.attempts}`},
          {label:'Completion rate',value:percent(zone.rate)},
          {label:'95% Wilson interval',value:zone.attempts?`${percent(zone.lower)}–${percent(zone.upper)}`:'—'},
          ...(!qualified&&count?[{label:'Sample',value:`Below ${minimum}-attempt shading minimum`}]:[])];
        const actions=isReceive&&receiving==='all'?[]:[{label:isReceive?'Inspect following hucks':'Inspect hucks from here',onSelect:()=>onInspect({kind,zoneId:zone.id})}];
        return <ChartMark key={zone.id} className={`ufa-deep-cell${!qualified&&count?' is-small-sample':''}`}
          style={{left:`${(zone.x0+26.65)/53.3*100}%`,top:`${(120-zone.y1)/120*100}%`,width:`${(zone.x1-zone.x0)/53.3*100}%`,height:`${(zone.y1-zone.y0)/120*100}%`,
            '--zone-fill':count&&qualified?`color-mix(in srgb,var(--chart-1) ${12+intensity*38}%,var(--surface))`:'var(--surface)'}}
          aria-pressed={selected} aria-label={`${zone.label}: ${isReceive?`${count} catches`:`${zone.completed} completed of ${count} hucks, ${percent(zone.rate)}`}`}
          context={{kind:'chart',chartType:'field heatmap',label:`${name} · ${zone.label}`,value,row:zone,actions}}
          tooltip={<ChartTooltip active label={zone.label} headerValue={label} details={details}/>}>
          <strong>{label}</strong>
          <span>{isReceive?(count?percent(receiving==='before'?zone.beforeShare:zone.catchShare):'catches'):count?`${zone.completed}/${count}`:'no attempts'}</span>
          {!qualified&&count>0&&<small>small n</small>}
        </ChartMark>;
      })}
    </div>
    <div className="ufa-deep-direction">Own end zone · distances in yards</div>
  </div>;
}

function SequenceField({huck,previous}) {
  const id=React.useId().replaceAll(':',''),point=(x,y)=>[30+y*5,20+(x+26.65)*5];
  const valid=e=>e&&[e.tx,e.ty,e.rx,e.ry].every(Number.isFinite);
  const color=huck.complete?'var(--ufa-deep-complete)':'var(--ufa-deep-negative)';
  return <svg className="ufa-deep-sequence-field" viewBox="0 0 660 326" role="img" aria-label={`Disc-flight sequence: ${previous?'previous completed pass, then ':''}huck ${result(huck).toLowerCase()}. Offense attacks to the right.`}>
    <defs>{[['prior','var(--chart-1)'],['huck',color]].map(([kind,fill])=><marker key={kind} id={`${id}-${kind}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L8 4L0 8Z" fill={fill}/></marker>)}</defs>
    <rect x="30" y="20" width="600" height="266.5" className="ufa-deep-pitch"/>
    {[0,20,40,60,80,100,120].map(y=><g key={y}><line x1={30+y*5} x2={30+y*5} y1="20" y2="286.5" className={y===20||y===100?'ufa-deep-goal-line':'ufa-deep-grid-line'}/><text x={30+y*5} y="307" textAnchor="middle">{y}</text></g>)}
    {[['prior',previous,'var(--chart-1)'],['huck',huck,color]].filter(([,e])=>valid(e)).map(([kind,e,stroke])=>{
      const [x1,y1]=point(e.tx,e.ty),[x2,y2]=point(e.rx,e.ry);
      return <g key={kind}><line x1={x1} y1={y1} x2={x2} y2={y2} stroke={stroke} strokeWidth="3" strokeDasharray={kind==='prior'?'7 5':undefined} markerEnd={`url(#${id}-${kind})`}/><circle cx={x1} cy={y1} r="4" fill={stroke}/><circle cx={x2} cy={y2} r="5" fill="var(--surface)" stroke={stroke} strokeWidth="2"/></g>;
    })}
    <text x="330" y="13" textAnchor="middle">Attack →</text>
  </svg>;
}

export function DeepThrowers({events,allEvents,players,teams,team,onTeamChange,scopeFilters}) {
  const directory=useMemo(()=>connectionPlayerDirectory(allEvents,players,teams).filter(p=>p.id!=='unknown'),[allEvents,players,teams]);
  const comparison=useMemo(()=>deepThrowerComparison(events),[events]);
  const links=useMemo(()=>precedingPasses(events),[events]);
  const [chosen,setChosen]=useState(()=>({id:comparison.some(p=>p.id==='aatkins')?'aatkins':comparison[0]?.id,team}));
  const [receiving,setReceiving]=useState('before'),[metric,setMetric]=useState('rate'),[minimum,setMinimum]=useState('5');
  const [profileOpen,setProfileOpen]=useState(false),[scrollToProfile,setScrollToProfile]=useState(false);
  const [selection,setSelection]=useState(null),[sequenceIndex,setSequenceIndex]=useState(0),[recordPage,setRecordPage]=useState(0);
  const [setupZone,setSetupZone]=useState('all');
  const profileRef=useRef(null),recordsRef=useRef(null),leaderboardRef=useRef(null),setupsRef=useRef(null);
  const chosenMatches=team==='all'||chosen.team===team||directory.find(p=>p.id===chosen.id)?.teamIds.includes(team);
  const playerId=chosen.id&&chosenMatches?chosen.id:comparison[0]?.id,name=playerName(players,playerId);
  const choosePlayer=(id,scroll=false,releaseZoneId=null)=>{
    const person=directory.find(p=>p.id===id);if(!person)return;
    const nextTeam=connectionSearchTeam(person,team);setChosen({id,team:nextTeam});
    if(nextTeam!==team)onTeamChange(nextTeam);
    setProfileOpen(true);setSelection(releaseZoneId?{kind:'release',zoneId:releaseZoneId}:null);
    setSetupZone(releaseZoneId||'all');
    setSequenceIndex(0);setRecordPage(0);setScrollToProfile(scroll);
  };
  const model=useMemo(()=>buildDeepThrower(events,playerId,links),[events,playerId,links]);
  const best=bestReleaseZone(model,Number(minimum));
  useEffect(()=>{setSequenceIndex(0);setRecordPage(0);},[model]);
  useEffect(()=>{if(profileOpen&&scrollToProfile){profileRef.current?.scrollIntoView({block:'start',behavior:'auto'});setScrollToProfile(false);}},[profileOpen,scrollToProfile,playerId]);
  const selectedHucks=useMemo(()=>selectHucks(model,selection),[model,selection]);
  const inspectedSources=useMemo(()=>sequenceSource(selectedHucks,links),[selectedHucks,links]);
  const recordRows=useMemo(()=>selectedHucks.map(e=>{
    const previous=links.get(e.id),geometry=passGeometry(e);
    return {...e,throwerName:playerName(players,e.thrower),receiverName:endpointName(players,e.receiver),outcome:result(e),
      flightYards:geometry.distance,downfieldYards:geometry.gain,releaseZone:zoneName(zoneFor(e.tx,e.ty)),
      previousPassId:previous?.id??null,previousThrower:previous?playerName(players,previous.thrower):null,
      previousTx:previous?.tx??null,previousTy:previous?.ty??null,catchX:previous?.rx??null,catchY:previous?.ry??null,
      catchZone:previous?zoneName(zoneFor(previous.rx,previous.ry)):null,
      priorPassDirection:HUCK_SETUPS.find(s=>s.id===priorPassDirection(previous)).label};
  }),[selectedHucks,links,players]);
  const baseScope=scopeFilters.map(f=>({...f,field:scopeFields[f.label]}));
  const playerScope=[...baseScope,{field:'thrower',label:'Selected player',value:name},{field:'rx',label:'Huck',value:'Flight >40 yd and downfield >30 yd; stalls excluded'}];
  const selectZone=value=>{setSelection(value);setSequenceIndex(0);setRecordPage(0);recordsRef.current?.scrollIntoView({block:'start',behavior:'auto'});};
  const selectedLabel=selection?.kind==='setup'?`${HUCK_SETUPS.find(s=>s.id===selection.setupId)?.label} · ${selection.zoneId==='all'?'all release locations':zoneName(selection.zoneId)}`:selection?`${selection.kind==='receive'?'Caught before huck in':'Released from'} ${zoneName(selection.zoneId)}`:'All huck release locations';
  const inspectionValue=selection?.kind==='setup'?`setup:${selection.setupId}:${selection.zoneId}`:selection?`${selection.kind}:${selection.zoneId}`:'all';
  const inspectionOptions=[...ZONES.flatMap(z=>[[`release:${z.id}`,`Release: ${z.label}`],[`receive:${z.id}`,`Prior catch: ${z.label}`]]),
    ...HUCK_SETUPS.map(s=>[`setup:${s.id}:all`,`${s.label} · all release locations`]),
    ...(selection?.kind==='setup'&&selection.zoneId!=='all'?[[inspectionValue,selectedLabel]]:[])];
  const sequence=selectedHucks[Math.min(sequenceIndex,Math.max(0,selectedHucks.length-1))],previous=sequence?links.get(sequence.id):null;
  const receiptRows=receiving==='before'?model.linkedCatches:model.catches;
  const maxReceipts=Math.max(0,...model.zones.map(z=>receiving==='before'?z.beforeHuck:z.catches));
  const maxAttempts=Math.max(0,...model.zones.map(z=>z.attempts));
  const choices=directory.map(p=>p.id),choiceLabels=Object.fromEntries(directory.map(p=>[p.id,p.label]));

  return <section className="ufa-deep" aria-label="Deep thrower profiles">
    <div ref={leaderboardRef} className="ufa-deep-board-anchor"><DeepLeaderboard comparison={comparison} events={events} players={players} teams={teams} scopeFilters={baseScope} minimum={minimum} onMinimumChange={setMinimum} onInspect={(id,releaseZoneId)=>choosePlayer(id,true,releaseZoneId)} selectedPlayer={profileOpen?playerId:null}/></div>
    {profileOpen&&<div ref={profileRef} className="ufa-deep-detail">
    <div className="ufa-deep-detail-heading"><h3>{name} · player profile</h3><div className="ufa-deep-profile-nav"><Button onClick={()=>setupsRef.current?.scrollIntoView({block:'start',behavior:'auto'})}>Incoming pass tendencies</Button><Button onClick={()=>{setProfileOpen(false);leaderboardRef.current?.scrollIntoView({block:'start',behavior:'auto'});}}>Back to leaderboard</Button></div></div>
    <div className="ufa-deep-controls">
      <div className="ufa-player-search" onFocusCapture={e=>{if(e.target.getAttribute('role')==='combobox')e.target.select();}}><span>Search players <small>All teams</small></span><Dropdown label="Search deep throwers" searchable placeholder="Type a player or team name…" value={playerId||'all'} allLabel="Choose a player" choices={choices} choiceLabels={choiceLabels} onChange={id=>choosePlayer(id)}/></div>
      <Dropdown label="Release map" showLabel value={metric} choices={['rate','attempts']} choiceLabels={metricNames} onChange={setMetric}/>
    </div>
    <p className="ufa-deep-note">Hucks travel more than 40 yards in a straight line and gain more than 30 yards forward. Team, season phase and line filters apply throughout this tab.</p>
    {!playerId?<div className="ufa-empty" role="status">No recorded throwers in this scope. Search for a player above or change the team and season filters.</div>:<>
      <div className="ufa-deep-profile">
        <DataComponent id="ufa-deep-profile" queryId="events" kind="custom" title={`${name} · deep throwing`} sourceRows={model.throws}
          displayRows={[{player:name,attempts:model.attempts,completed:model.completed,completionRate:model.rate,huckShare:model.huckShare,locatedThrows:model.locatedThrows.length}]}
          scopeFilters={playerScope} description="Huck share divides hucks by non-stall throws with usable endpoint coordinates. Completion includes all identified huck attempts, including drops and unnamed targets.">
          <div className="ufa-deep-summary" data-reviewed-rows><Face id={playerId} name={name}/><div><strong>{int(model.attempts)}</strong><span>huck attempts</span></div><div><strong>{percent(model.rate)}</strong><span>{model.completed} complete · {model.failed} unsuccessful</span></div><div><strong>{percent(model.huckShare)}</strong><span>of {int(model.locatedThrows.length)} located throws</span></div></div>
          {!model.attempts&&<p className="ufa-deep-note" role="status">No huck attempts are recorded for {name} with these team, season and line filters. Change the filters to broaden the scope.</p>}
          {model.throws.length>model.locatedThrows.length&&<p className="ufa-deep-note">{model.throws.length-model.locatedThrows.length} throws lack endpoint coordinates and cannot be classified as hucks.</p>}
          <p className="ufa-deep-finding" data-reviewed-rows>{best?<><span>Highest observed completion rate</span><strong>{best.label}</strong> · {best.completed}/{best.attempts} completed ({percent(best.rate)}). At least {minimum} attempts per eligible zone.</>:`No release zone has ${minimum} huck attempts in this scope. Counts remain visible below.`}</p>
        </DataComponent>
      </div>
      <div className="ufa-deep-map-controls"><span>Receiving map</span><SegmentedControl value={receiving} onChange={v=>{setReceiving(v);if(selection?.kind==='receive'){setSelection(null);setSequenceIndex(0);setRecordPage(0);}}} options={[{value:'before',label:'Before a huck'},{value:'all',label:'All catches'}]}/></div>
      <SortableRegion id="ufa:deep-fields" variant="freeform" authoredRevision={1} className="ufa-deep-maps">
        <SortableItem id="ufa-deep-receive" label="Receiving locations" kind="custom">
          <DataComponent id="ufa-deep-receive" queryId="events" title="Where they receive" kind="custom" sourceRows={receiptRows}
            displayRows={model.zones.map(z=>({zone:z.label,catches:receiving==='before'?z.beforeHuck:z.catches,share:receiving==='before'?z.beforeShare:z.catchShare}))}
            scopeFilters={[...baseScope,{field:'receiver',label:'Receiver',value:name},{field:'complete',label:'Receptions',value:receiving==='before'?'Verified completed pass immediately before a huck':'All completed catches'}]}
            description="The receiving location is the recorded destination of a completed pass. Before a huck uses a unique completed prior pass in the same game, team, quarter, point and possession, with consecutive throw order and increasing event sequence. Missing or ambiguous links are left unmatched.">
            <p className="ufa-deep-map-caption" data-reviewed-rows>{receiving==='before'?<><strong>{model.pairs.length}/{model.attempts}</strong> hucks have a verified preceding catch</>:<><strong>{int(model.catches.length)}</strong> completed catches in this scope</>}</p>
            <ZoneField zones={model.zones} kind="receive" receiving={receiving} metric={metric} minimum={Number(minimum)} selection={selection} onInspect={selectZone} name={name}/>
            <p className="ufa-deep-scale" data-reviewed-rows><i/> 0 → {maxReceipts} catches · count and share of this view</p>
            {receiving==='before'?<p className="ufa-deep-note">{model.attempts-model.pairs.length} hucks have no verified prior pass in this scope. They remain in the release map. Select a zone, then <strong>Inspect following hucks</strong>.</p>:<p className="ufa-deep-note">All completed catches, including catches that were not followed by a huck. Drops and unsuccessful targets are excluded.</p>}
            {(receiving==='before'?model.unmappedLinked:model.unmappedCatches)>0&&<p className="ufa-coverage">{receiving==='before'?model.unmappedLinked:model.unmappedCatches} catches fall outside the mapped field; retained in source rows and share denominators.</p>}
          </DataComponent>
        </SortableItem>
        <SortableItem id="ufa-deep-release" label="Huck release locations" kind="custom">
          <DataComponent id="ufa-deep-release" queryId="events" title="Where their hucks succeed" kind="custom" sourceRows={model.hucks}
            displayRows={model.zones.map(z=>({zone:z.label,attempts:z.attempts,completed:z.completed,completionRate:z.rate,wilson95Low:z.lower,wilson95High:z.upper}))}
            scopeFilters={[...playerScope,{field:metric==='rate'?'complete':'id',label:'Map measure',value:metricNames[metric]},{field:'tx',label:'Shading threshold',value:`${minimum} attempts per zone; all counts retained`}]}
            description="Each huck belongs to the zone containing its recorded release, using the same field boundaries as Field views. Completion rate divides completed hucks by every huck attempt in the zone. Tooltips show 95% Wilson intervals, which summarize sampling uncertainty without adjusting for repeated players, games or opponents.">
            <p className="ufa-deep-map-caption" data-reviewed-rows><strong>{metricNames[metric]}</strong> · completed / attempts below each value</p>
            <ZoneField zones={model.zones} kind="release" receiving={receiving} metric={metric} minimum={Number(minimum)} selection={selection} onInspect={selectZone} name={name}/>
            <p className="ufa-deep-scale" data-reviewed-rows><i/>{metric==='rate'?'0% → 100% completion':`0 → ${maxAttempts} attempts`}</p>
            <p className="ufa-deep-note">{metric!=='attempts'?`Hatched zones have fewer than ${minimum} attempts. `:''}Hover for exact values and uncertainty. Select a zone, then <strong>Inspect hucks from here</strong>.</p>
            {model.unmappedReleases>0&&<p className="ufa-coverage">{model.unmappedReleases} huck releases fall outside the mapped field; included in totals and records.</p>}
          </DataComponent>
        </SortableItem>
      </SortableRegion>
      <p className="ufa-deep-caution">These are observed patterns, not proof that a location causes success. The data does not show the receiver’s position when the huck is released, defensive pressure, or cutting routes.</p>
      <div ref={setupsRef} className="ufa-deep-setup-anchor"><DeepSetups model={model} links={links} name={name} scopeFilters={baseScope} minimum={Number(minimum)} zoneId={setupZone} onZoneChange={setSetupZone} onInspect={selectZone}/></div>
    </>}

    {playerId&&<div ref={recordsRef} className="ufa-deep-sequences">
      <div className="ufa-deep-record-controls"><Dropdown label="Inspect hucks" showLabel value={inspectionValue} choices={['all',...inspectionOptions.map(([value])=>value)]} allLabel="All hucks" choiceLabels={Object.fromEntries(inspectionOptions)} onChange={value=>{const [kind,first,second]=value.split(':');setSelection(value==='all'?null:kind==='setup'?{kind,setupId:first,zoneId:second}:{kind,zoneId:first});setSequenceIndex(0);setRecordPage(0);}}/></div>
      <DataComponent id="ufa-deep-sequences" queryId="events" kind="custom" title="The pass before the huck" sourceRows={inspectedSources} displayRows={recordRows}
        scopeFilters={[...playerScope,{field:selection?.kind==='receive'?'rx':'tx',label:'Selected hucks',value:selectedLabel},{field:'possessionThrow',label:'Record grain',value:'One row per huck; original source also includes linked preceding passes'}]}
        headerControls={<Button disabled={!recordRows.length} onClick={()=>exportHucks(recordRows)}>Export {int(recordRows.length)} hucks</Button>}
        description="The dashed line is a verified completed pass into the selected thrower; the solid line is their next recorded throw in that possession. These are disc-flight endpoints, not tracked player motion. No upline, swing, dead-disc or receiver-route label is inferred. Export contains one row per selected huck, with prior-pass ID and endpoint coordinates when available; source inspection retains both original events once.">
        <p className="ufa-deep-note" data-reviewed-rows>{selectedLabel} · {selectedHucks.length} hucks</p>
        {sequence?<div data-reviewed-rows>
          <div className="ufa-deep-sequence-heading"><div><strong>{previous?`${endpointName(players,previous.thrower)} → `:''}{name} → {endpointName(players,sequence.receiver)}</strong><span>{sequence.game} · Q{sequence.quarter} · Point {sequence.point} · {result(sequence)}</span></div><span>{fmt(passGeometry(sequence).distance,1)} yd flight · {fmt(sequence.throwAec,3)} thrower aEC</span></div>
          <SequenceField huck={sequence} previous={previous}/>
          <div className="ufa-deep-sequence-legend">{previous&&<span><i className="is-prior"/>Pass into {name}</span>}<span><i className={sequence.complete?'is-complete':'is-failed'}/>Huck · {result(sequence)}</span><span>Filled dot: release · open circle: destination</span></div>
          <p className="ufa-deep-note">{previous?`Caught in ${zoneName(zoneFor(previous.rx,previous.ry))}; huck released from ${zoneName(zoneFor(sequence.tx,sequence.ty))}.`:'No unique completed prior pass could be verified in this scope. This does not establish a dead-disc start.'} The lines show disc flight, not player movement.</p>
          <div className="ufa-pagination"><Button disabled={!sequenceIndex} onClick={()=>setSequenceIndex(sequenceIndex-1)}>Previous huck</Button><span>{sequenceIndex+1} / {selectedHucks.length}</span><Button disabled={sequenceIndex+1>=selectedHucks.length} onClick={()=>setSequenceIndex(sequenceIndex+1)}>Next huck</Button></div>
        </div>:<div className="ufa-empty" role="status">No hucks match this zone and scope. Choose All hucks or change the filters.</div>}
        <details className="ufa-records" data-reviewed-rows><summary>Inspect {recordRows.length} huck records</summary><div className="ufa-table-scroll"><table><thead><tr><th>Game</th><th>Receiver</th><th>Outcome</th><th>Prior catch</th><th>Release zone</th><th className="ufa-num">Flight (yd)</th><th className="ufa-num">Thrower aEC</th><th>Sequence</th></tr></thead><tbody>{recordRows.slice(recordPage*12,(recordPage+1)*12).map((row,i)=><tr key={row.id}><td>{row.game}</td><td>{row.receiverName}</td><td>{row.outcome}</td><td>{row.catchZone??'No verified prior pass'}</td><td>{row.releaseZone}</td><td className="ufa-num">{fmt(row.flightYards,1)}</td><td className="ufa-num">{fmt(row.throwAec,3)}</td><td><Button onClick={()=>setSequenceIndex(recordPage*12+i)}>View pass {recordPage*12+i+1}</Button></td></tr>)}</tbody></table></div><div className="ufa-pagination"><Button disabled={!recordPage} onClick={()=>setRecordPage(recordPage-1)}>Previous records</Button><span>{recordPage+1} / {Math.max(1,Math.ceil(recordRows.length/12))}</span><Button disabled={(recordPage+1)*12>=recordRows.length} onClick={()=>setRecordPage(recordPage+1)}>More records</Button></div></details>
      </DataComponent>
    </div>}
    </div>}
  </section>;
}
