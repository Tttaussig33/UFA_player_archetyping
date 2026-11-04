import React,{useMemo,useState} from 'react';
import {Button,DataComponent,DataTable,Dropdown,SegmentedControl,SortableItem,SortableRegion} from '../../data-app-public.jsx';
import {averageAngleLabel,directionLabel} from './distance-angle-model.js';
import {findPlayers,finderEvidence} from './player-finder-model.js';
import './player-finder.css';

const percentage=value=>Number.isFinite(value)?`${(100*value).toFixed(1)}%`:'—';
const directionChoices=['all',...Array.from({length:12},(_,index)=>String(index))];
const directionLabels={all:'Any direction',...Object.fromEntries(directionChoices.slice(1).map(id=>[id,directionLabel(Number(id))]))};
const sortLabels={closest:'Closest arrow',attempts:'Most throws',share:'Highest frequency',completion:'Highest completion %'};

function AverageArrow({angle,gap}) {
  const label=averageAngleLabel(angle);
  return <div className="ufa-finder-arrow-cell"><svg viewBox="0 0 42 42" aria-hidden="true"><circle cx="21" cy="21" r="18"/><line className="ufa-finder-axis" x1="21" y1="3" x2="21" y2="39"/><g transform={`rotate(${-angle} 21 21)`}><line x1="21" y1="31" x2="21" y2="10"/><path d="M17 14L21 8L25 14"/></g></svg><span>{label.replace(' of forward','')}<small>{gap.toFixed(1)}° apart</small></span></div>;
}

export function PlayerFinder({league,reference,secondId,rangeLabel,validRange,onCompare,onClearComparisonFocus,onDirectionChange}) {
  const [mode,setMode]=useState('arrows'),[tolerance,setTolerance]=useState(15),[direction,setDirection]=useState('all');
  const [minimum,setMinimum]=useState('20'),[team,setTeam]=useState('all'),[sort,setSort]=useState('closest');
  const teams=useMemo(()=>[...new Map(league.map(({player})=>[player.team,player.teamName])).entries()].sort((a,b)=>a[1].localeCompare(b[1])),[league]);
  const result=useMemo(()=>findPlayers(league,{mode,referenceId:reference.id,tolerance,direction,minimum,team,sort}),[league,mode,reference.id,tolerance,direction,minimum,team,sort]);
  const rows=validRange?result.rows:[];
  const sourceRows=useMemo(()=>finderEvidence(league,rows,mode==='arrows'?reference.id:null),[league,rows,mode,reference.id]);
  const summaries=useMemo(()=>league.filter(({player})=>rows.some(row=>row.id===player.id)||(mode==='arrows'&&player.id===reference.id)).map(({player})=>player),[league,rows,mode,reference.id]);
  const searchKey=[mode,tolerance,direction,minimum,team,sort,reference.id,rangeLabel].join(':');
  const missingReference=mode==='arrows'&&!Number.isFinite(result.referenceAngle);
  const changeMode=value=>{setMode(value);setSort(value==='arrows'?'closest':'attempts');onDirectionChange(value==='throws'?direction:'all');onClearComparisonFocus();};
  const changeDirection=value=>{setDirection(value);onDirectionChange(value);onClearComparisonFocus();};
  const columns=mode==='arrows'?[
    {field:'name',label:'Player',renderCell:(value,row)=><span className="ufa-finder-name">{value}<small>{row.teamName}</small></span>},
    {field:'averageArrow',label:'Average arrow',renderCell:(_value,row)=><AverageArrow angle={row.averageAngle} gap={row.angleDifference}/>},
    {field:'averageDistance',label:'Avg. distance',renderCell:value=>`${value.toFixed(1)} yd`},
    {field:'attempts',label:'Throws in range',renderCell:(value,row)=><span>{value.toLocaleString()}{row.missingDirections>0&&<small className="ufa-finder-angle-count">{row.directionalAttempts} with angles</small>}</span>},
  ]:[
    {field:'name',label:'Player',renderCell:(value,row)=><span className="ufa-finder-name">{value}<small>{row.teamName}</small></span>},
    {field:'attempts',label:'Matching throws',renderCell:value=>value.toLocaleString()},
    {field:'share',label:'% of all throws',renderCell:percentage},
    {field:'completion',label:'Completion %',renderCell:percentage},
  ];
  columns.push({field:'id',label:'Compare',renderCell:(id,row)=><Button disabled={id===reference.id} aria-label={`Compare ${row.name} with ${reference.name}`} onClick={()=>onCompare(id,mode==='throws'?direction:'all')}>{id===reference.id?'Player 1':id===secondId?'View comparison':'Compare'}</Button>});
  return <SortableRegion id="ufa:player-finder" variant="stack" authoredOrder={['ufa-distance-angle-finder']} label="Player finder">
    <SortableItem id="ufa-distance-angle-finder" label="Find players" kind="table">
      <DataComponent id="ufa-distance-angle-finder" queryId="events" queryIds={['events','shownSpaceThrowers']} title="Find players" kind="table"
        sourceRowsByQuery={{events:sourceRows,shownSpaceThrowers:summaries}} displayRows={rows}
        scopeFilters={[{label:'Season',value:'2026 including playoffs · all lines'},{label:'Distance',value:validRange?rangeLabel:'Invalid range'},
          {label:'Find by',value:mode==='arrows'?`Average arrow within ${tolerance}° of ${reference.name}`:`Individual throws: ${directionLabels[direction]}`},
          {label:'Minimum throws',value:minimum},{label:'Team',value:team==='all'?'All teams':Object.fromEntries(teams)[team]},{label:'Order',value:sortLabels[sort]}]}
        description="Combine the distance range with the finder’s angle, team and minimum-throw filters. Similar arrows compares circular mean directions for the whole distance range, using the shortest angular gap to Player 1; it excludes Player 1 and undefined means. Throws by direction counts individual attempts in the chosen 30-degree direction bin and distance range together, including incomplete throws. Frequency divides matching attempts by all non-stall attempts for that player; completion divides matching completions by matching attempts. The minimum is an adjustable browsing filter, not evidence of statistical reliability. Selecting Compare keeps Player 1 and loads the chosen player into Player 2 below; those diagrams retain all directions in the distance range. Similar averages do not establish a common archetype or equal skill."
        headerControls={<><SegmentedControl value={mode} onChange={changeMode} options={[{value:'arrows',label:'Similar arrows'},{value:'throws',label:'Throws by direction'}]}/><div className="ufa-finder-controls">
          {mode==='arrows'?<Dropdown label="Arrow difference" showLabel value={tolerance} choices={[5,10,15,30,45,90,180]} formatChoice={value=>`Within ${value}°`} onChange={value=>setTolerance(Number(value))}/>:<Dropdown label="Direction" showLabel value={direction} choices={directionChoices} choiceLabels={directionLabels} allLabel="Any direction" onChange={changeDirection}/>}
          <label className="ufa-finder-minimum">{mode==='arrows'?'Minimum throws in range':'Minimum matching throws'}<input type="number" min="1" step="1" aria-label={mode==='arrows'?'Minimum throws in range':'Minimum matching throws'} value={minimum} onChange={e=>setMinimum(e.target.value)}/></label>
          <Dropdown label="Team" showLabel value={team} choices={['all',...teams.map(([id])=>id)]} choiceLabels={{all:'All teams',...Object.fromEntries(teams)}} allLabel="All teams" onChange={setTeam}/>
          <Dropdown label="Order" showLabel value={sort} choices={mode==='arrows'?['closest','attempts']:['attempts','share','completion']} choiceLabels={sortLabels} onChange={setSort}/>
        </div></>}
      >
        {!validRange?<p className="ufa-focus-note">Enter a valid distance range to find players.</p>:!result.valid?<p role="alert" className="ufa-focus-note">Minimum throws must be a whole number of at least 1.</p>:missingReference?<p role="status" className="ufa-focus-note">{reference.name} has no single average arrow in {rangeLabel}. Choose another Player 1 or use Throws by direction.</p>:<>
          <p className="ufa-finder-summary" data-reviewed-rows>{mode==='arrows'?<><strong>{rows.length} players</strong> within {tolerance}° of {reference.name}’s arrow ({averageAngleLabel(result.referenceAngle)}) · {rangeLabel}.</>:<><strong>{rows.length} players</strong> with at least {minimum} throws {direction==='all'?'in any direction':directionLabels[direction]} · {rangeLabel}.</>}</p>
          {mode==='arrows'?<p className="ufa-focus-note">Similar averages can hide different patterns. Compare their full diagrams below.</p>:<p className="ufa-focus-note">Counts and completion use both filters together. “% of all throws” shows how often each player makes this throw.</p>}
          <DataTable key={searchKey} rows={rows} columns={columns} caption={`${mode==='arrows'?'Players with similar average arrows':'Players throwing in the selected direction'} · ${rangeLabel}`} selectedRowKey={secondId} rowKey="id"
            onRowSelect={row=>onCompare(row.id===reference.id?secondId:row.id,mode==='throws'?direction:'all')}
            rowActionLabel={row=>row.id===reference.id?'View current player comparison':`Open ${row.name} in the comparison`}/>
          {!rows.length&&<p role="status" className="ufa-focus-note">No players match these filters. Widen the range, lower the minimum, or choose All teams.</p>}
        </>}
      </DataComponent>
    </SortableItem>
  </SortableRegion>;
}
