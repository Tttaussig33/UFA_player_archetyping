import React,{useCallback,useEffect,useMemo,useState} from 'react';
import {Button,DataComponent,Dropdown,EvidenceChart,SegmentedControl,SortableItem,SortableRegion} from '../../data-app-public.jsx';
import {fmt,int} from './model.js';
import {Face,playerName} from './Field.jsx';
import {buildConnections,connectionPlayers,passGeometry,selectedConnectionEvents} from './connections-model.js';
import './connections.css';

const connectionSpec={type:'sankey',x:'passer',y:'passes',stages:['passer','player','receiver'],showLegend:false,showValues:true,
  valueDecimals:0,labelMaxLength:26,sankeyNodeWidth:16,sankeyLabelFontSize:12,sankeyValueFontSize:11,sankeySortNodes:false,
  colors:{passer:'color-mix(in srgb, var(--chart-1) 28%, var(--surface))',player:'var(--chart-1)',receiver:'color-mix(in srgb, var(--chart-1) 28%, var(--surface))'}};

function exportConnections(events,players) {
  const rows=[['game','team','thrower','receiver','outcome','distance_yards','downfield_yards','huck','start_x','start_y','end_x','end_y'],
    ...events.map(event=>{const geometry=passGeometry(event);return [event.game,event.team,playerName(players,event.thrower),event.receiver?playerName(players,event.receiver):'Unrecorded player',event.complete?'Complete':event.drop?'Drop':'Turnover',geometry.distance,geometry.gain,geometry.huck,event.tx,event.ty,event.rx,event.ry];})];
  const quote=value=>'"'+String(value??'').replaceAll('"','""')+'"';
  const url=URL.createObjectURL(new Blob([rows.map(row=>row.map(quote).join(',')).join('\n')],{type:'text/csv;charset=utf-8'}));
  const link=document.createElement('a');link.href=url;link.download='ufa-connection-passes.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

export function Connections({events,players,scopeFilters}) {
  const [chosenPlayer,setChosenPlayer]=useState('aatkins'),[passType,setPassType]=useState('all'),[outcome,setOutcome]=useState('complete'),[limit,setLimit]=useState('5');
  const [selection,setSelection]=useState([]),[page,setPage]=useState(0),[resetKey,setResetKey]=useState(0);
  const selectConnection=useCallback(criteria=>{setSelection(criteria);setPage(0);},[]);
  const roster=useMemo(()=>connectionPlayers(events),[events]);
  const playerId=roster.includes(chosenPlayer)?chosenPlayer:roster[0];
  const name=playerName(players,playerId);
  const choices=useMemo(()=>roster.slice().sort((a,b)=>playerName(players,a).localeCompare(playerName(players,b))),[roster,players]);
  const model=useMemo(()=>buildConnections(events,playerId,{passType,outcome,limit:limit==='all'?Infinity:Number(limit),name:id=>playerName(players,id)}),[events,playerId,passType,outcome,limit,players]);
  useEffect(()=>{setSelection([]);setPage(0);},[events,playerId,passType,outcome,limit]);
  const selectedEvents=useMemo(()=>selectedConnectionEvents(model,selection),[model,selection]);
  const selectedLabel=selection.filter(item=>item.field!=='player').map(item=>`${item.field==='passer'?'From':'To'} ${item.name}`).join(' · ');
  const baseScope=scopeFilters.map(filter=>({...filter,field:({'Team':'team','Season phase':'phase','Line':'line'})[filter.label]||filter.label}));
  // Scope descriptions reference the original fields used by each predicate.
  // Player involvement is an OR across the two endpoints, not a thrower-only cut.
  const filteredScope=[...baseScope,{field:'thrower',label:'Player (thrower or receiver)',value:name||'No recorded players'},{field:'rx',label:'Pass geometry',value:passType==='hucks'?'Hucks only: flight ≥40 yd and downfield ≥30 yd':'All passes'},{field:'complete',label:'Outcome',value:outcome==='complete'?'Completed passes':'All pass attempts'}];
  const detailScope=[...filteredScope,...(selectedLabel?[{field:'id',label:'Connection',value:selectedLabel}]:[])];
  const recordRows=selectedEvents.map(event=>{const geometry=passGeometry(event);return {...event,throwerName:playerName(players,event.thrower),receiverName:event.receiver?playerName(players,event.receiver):'Unrecorded player',distanceYards:geometry.distance,downfieldYards:geometry.gain,huck:geometry.huck};});
  const metricLabel=outcome==='complete'?(passType==='hucks'?'completed hucks':'completed passes'):(passType==='hucks'?'huck attempts':'pass attempts');
  const hasIncoming=model.incoming.total>0,hasOutgoing=model.outgoing.total>0;
  const height=Math.max(360,Math.max(model.incoming.displayed.length,model.outgoing.displayed.length)*56+36);
  if(!playerId)return <div className="ufa-empty">No players have recorded passes for this team, season phase and line.</div>;
  return <section className="ufa-connections" aria-label="Player connections">
    <div className="ufa-connection-controls">
      <Dropdown label="Player" showLabel searchable value={playerId} choices={choices} choiceLabels={Object.fromEntries(choices.map(id=>[id,playerName(players,id)]))} onChange={setChosenPlayer}/>
      <div className="ufa-pass-type"><span>Pass type</span><SegmentedControl value={passType} onChange={setPassType} options={[{value:'all',label:'All passes'},{value:'hucks',label:'Hucks only'}]}/></div>
      <Dropdown label="Outcome" showLabel value={outcome} choices={['complete','all']} allLabel="All pass attempts" choiceLabels={{complete:'Completed passes'}} onChange={setOutcome}/>
      <Dropdown label="Partners" showLabel value={limit} choices={['5','10','all']} allLabel="All partners" choiceLabels={{'5':'Top 5 + others','10':'Top 10 + others'}} onChange={setLimit}/>
    </div>
    <p className="ufa-connection-definition">Huck: at least 40 yards of flight and 30 yards downfield. {passType==='hucks'?'The huck filter applies to both incoming and outgoing passes.':'Switch to Hucks only to see the deep connections.'}</p>
    <SortableRegion id="ufa:connections" variant="freeform" authoredRevision={1} className="ufa-connection-layout">
      <SortableItem id="ufa-connections-chart" label="Passing connections" kind="chart">
        <EvidenceChart key={JSON.stringify([scopeFilters,playerId,passType,outcome,limit,resetKey])} id="ufa-connections-chart" queryId="events" title="Passing connections" spec={connectionSpec}
          rows={model.chartRows} sourceRows={model.sourceRows} scopeFilters={[...filteredScope,{field:'receiver',label:'Shown partners',value:limit==='all'?'All partners':`Top ${limit} plus all remaining players`}]}
          height={model.chartRows.length?height:180}
          description="Left: passes to the selected player. Right: passes from them. Each side counts separate events across the selected games, not a single possession. Stalls are excluded. All pass attempts includes incompletions; unnamed targets are grouped as Unrecorded player."
          chartOptions={{onSankeySelection:selectConnection}}
          renderPlot={(plot,chart)=><div className="ufa-connections-scroll"><div className="ufa-connections-plot">
            {chart.type==='sankey'&&model.chartRows.length>0&&<div className={`ufa-connection-stages ${!hasIncoming||!hasOutgoing?'ufa-two-stages':''}`} data-reviewed-rows>
              {hasIncoming&&<span>Received from<small>{int(model.incoming.total)} {metricLabel}</small></span>}
              <span className="ufa-connection-center"><Face id={playerId} name={name}/><span>{name}<small>{passType==='hucks'?'Hucks only':'All passes'}</small></span></span>
              {hasOutgoing&&<span>Thrown to<small>{int(model.outgoing.total)} {metricLabel}</small></span>}
            </div>}{plot}
          </div></div>}>
          {!model.chartRows.length?<p className="ufa-connection-note">No {outcome==='complete'?'completed ':''}{passType==='hucks'?'hucks':'passes'} recorded for {name} in this scope.</p>:<p className="ufa-connection-note">Widths show {metricLabel}. The two sides are separate totals. {!hasIncoming?'No incoming passes match this scope. ':!hasOutgoing?'No outgoing passes match this scope. ':''}{limit!=='all'?'“Other players” retains every pass outside the displayed leaders. ':''}{outcome==='all'?'Unrecorded player means the source did not name a target. ':''}Select a connection to inspect its passes below.</p>}
        </EvidenceChart>
      </SortableItem>
      <SortableItem id="ufa-connection-records" label="Connection passes" kind="table">
        <DataComponent id="ufa-connection-records" queryId="events" title="Connection passes" kind="table" sourceRows={selectedEvents} displayRows={recordRows} scopeFilters={detailScope}
          headerControls={<>{selectedLabel&&<Button onClick={()=>{setSelection([]);setPage(0);setResetKey(value=>value+1);}}>Show all connections</Button>}<Button disabled={!selectedEvents.length} onClick={()=>exportConnections(selectedEvents,players)}>Export {int(selectedEvents.length)} passes</Button></>}>
          {selectedLabel&&<p className="ufa-connection-selected" aria-live="polite" data-reviewed-rows>{selectedLabel} · {int(selectedEvents.length)} passes</p>}
          <details className="ufa-records" data-reviewed-rows key={`${playerId}-${passType}-${outcome}-${selectedLabel}`} open={Boolean(selectedLabel)}>
            <summary>Inspect {int(selectedEvents.length)} passes{selectedLabel?'':` · ${name}`}</summary>
            <div className="ufa-table-scroll"><table><thead><tr><th>Game</th><th>From → to</th><th>Outcome</th><th>Huck</th><th className="ufa-num">Flight (yd)</th><th className="ufa-num">Downfield (yd)</th></tr></thead>
              <tbody>{recordRows.slice(page*12,(page+1)*12).map(row=><tr key={row.id}><td>{row.game}</td><td>{row.throwerName} → {row.receiverName}</td><td>{row.complete?'Complete':row.drop?'Drop':'Turnover'}</td><td>{row.huck?'Yes':'No'}</td><td className="ufa-num">{fmt(row.distanceYards,1)}</td><td className="ufa-num">{fmt(row.downfieldYards,1)}</td></tr>)}</tbody></table></div>
            <div className="ufa-pagination"><Button disabled={page===0} onClick={()=>setPage(page-1)}>Previous</Button><span>{page+1} / {Math.max(1,Math.ceil(selectedEvents.length/12))}</span><Button disabled={(page+1)*12>=selectedEvents.length} onClick={()=>setPage(page+1)}>Next</Button></div>
          </details>
        </DataComponent>
      </SortableItem>
    </SortableRegion>
  </section>;
}
