import React,{useEffect,useMemo,useRef,useState} from 'react';
import {Button,ChartMark,ChartTooltip,DataComponent,DataTable,Dropdown,SortableItem,SortableRegion} from '../../data-app-public.jsx';
import {Face} from './Field.jsx';
import {focusDirectory,throwLength,directionPoint,directionSlice,directionHit} from './throwing-focus-model.js';
import {averageAngleLabel,distanceAngleModel,directionDisplayRows,directionScale,validDistanceRange} from './distance-angle-model.js';
import {distanceAngleLeague,indexPlayerThrows} from './player-finder-model.js';
import {PlayerFinder} from './PlayerFinder.jsx';
import {AverageDirectionArrow} from './AverageDirectionArrow.jsx';
import './distance-angle.css';

const percent=n=>Number.isFinite(n)?`${(n*100).toFixed(1).replace(/\.0$/,'')}%`:'—';
const decimal=n=>Number.isFinite(n)?n.toFixed(1):'—';
const count=n=>n.toLocaleString();

function DirectionProfile({player,model,scale,names,rangeLabel,highlightDirection}) {
  const [selected,setSelected]=useState(null),[inspectRequest,setInspectRequest]=useState(0),[open,setOpen]=useState(false);
  const recordsRef=useRef(null);
  const group=model.groups.find(g=>g.id===selected),recordEvents=group?.rows||model.rows;
  const displayRows=useMemo(()=>directionDisplayRows(model,player),[model,player]);
  const records=useMemo(()=>recordEvents.map(e=>({id:e.id,game:e.game,receiver:names[e.receiver]||'Unrecorded target',
    distance:throwLength(e),angle:throwLength(e)>0?averageAngleLabel(e.throwAngle):'No direction',
    result:e.complete?'Complete':e.drop?'Drop':'Incomplete'})),[recordEvents,names]);
  const inspect=id=>{setSelected(id);setOpen(true);setInspectRequest(n=>n+1);};
  useEffect(()=>{
    if(!open||!inspectRequest)return;
    const frame=requestAnimationFrame(()=>{
      recordsRef.current?.scrollIntoView({block:'start',behavior:'auto'});
      recordsRef.current?.querySelector('summary')?.focus({preventScroll:true});
    });
    return()=>cancelAnimationFrame(frame);
  },[inspectRequest,open]);
  return <article className="ufa-angle-player" aria-label={`${player.name} distance and angle`} data-reviewed-rows>
    <div className="ufa-focus-identity"><Face id={player.id} name={player.name}/><div><h3>{player.name}</h3><p>{player.teamName}</p></div></div>
    <dl className="ufa-angle-stats">
      <div><dt>Throws in range</dt><dd>{count(model.count)}</dd><dd className="ufa-angle-stat-note">{percent(model.share)} of all throws</dd></div>
      <div><dt>Average distance</dt><dd>{decimal(model.averageDistance)}<small> yd</small></dd></div>
      <div><dt>Average angle</dt><dd>{Number.isFinite(model.averageAngle)?`${decimal(Math.abs(model.averageAngle))}°`:'—'}</dd><dd className="ufa-angle-stat-note">{!model.directional.length?'No recorded directions':model.averageAngle===null?'Directions cancel out':Math.abs(model.averageAngle)<.05?'straight forward':Math.abs(model.averageAngle)>179.95?'backward':`${model.averageAngle>0?'left':'right'} of forward`}</dd></div>
    </dl>
    <div className="ufa-angle-wheel" data-chart-interaction-root role="group" aria-label={`${player.name} directions for ${rangeLabel}`}>
      <svg className="ufa-angle-background" viewBox="0 0 360 360" aria-hidden="true">
        <text x="180" y="16" textAnchor="middle" className="ufa-angle-forward">Forward · 0° ↑</text>
        <text x="180" y="354" textAnchor="middle">Backward · 180°</text>
        <text x="9" y="172">Left</text><text x="9" y="187">90°</text>
        <text x="351" y="172" textAnchor="end">Right</text><text x="351" y="187" textAnchor="end">90°</text>
        {[48,96,144].map(r=><circle key={r} cx="180" cy="180" r={r}/>)}
        {model.groups.map(g=>{const p=directionPoint(g.startAngle,144);return <line key={g.id} x1="180" y1="180" x2={p[0]} y2={p[1]}/>;})}
      </svg>
      {model.groups.map(g=><ChartMark key={g.id} disabled={!g.count} className={`ufa-angle-slice${highlightDirection===g.id?' is-finder-direction':''}`} style={{clipPath:directionHit(g.startAngle,g.endAngle)}}
        aria-label={`${player.name}, ${g.label}, ${g.count} throws`} aria-pressed={selected===g.id}
        context={{kind:'chart',chartType:'radial',label:g.label,value:g.count,row:displayRows[g.index],actions:[{label:'Inspect throws',onSelect:()=>inspect(g.id)}]}}
        tooltip={<ChartTooltip active label={g.label} headerValue={`${g.count} throws`} details={[{label:'Share of directions',value:percent(g.share)},{label:'Completion %',value:percent(g.count?g.completed/g.count:null)}]}/>}
      ><svg viewBox="0 0 360 360" aria-hidden="true"><path className="ufa-angle-slice-boundary" d={directionSlice(g.startAngle,g.endAngle,144)}/>{g.count>0&&<path className={`ufa-angle-slice-fill${model.leaders.some(l=>l.id===g.id)?' is-leading':''}`} d={directionSlice(g.startAngle,g.endAngle,12+132*g.share/scale)}/>}</svg></ChartMark>)}
      <div className="ufa-angle-mean"><AverageDirectionArrow angle={model.averageAngle}/></div>
      {!model.directional.length&&<p className="ufa-angle-empty">{model.count?'These throws have no usable angle.':'No throws in this range.'}</p>}
    </div>
    <div className="ufa-angle-common"><span>Most common {model.leaders.length>1?'directions':'direction'}</span><strong>{model.leaders.length?model.leaders.map(g=>g.label).join(' / '):'—'}</strong>{model.leaders.length>0&&<small>{model.leaders[0].count} throws{model.leaders.length>1?' each · tied':''} · {percent(model.leaders[0].share)}{model.leaders.length>1?' each':''}</small>}</div>
    {model.missingDirections>0&&<p className="ufa-focus-note">{model.missingDirections} attempts have zero distance or no recorded angle. They count toward distance and frequency, but not directions.</p>}
    {model.missingLocations>0&&<p className="ufa-focus-note">{model.missingLocations} attempts lack coordinates and cannot be placed in a distance range.</p>}
    <details ref={recordsRef} className="ufa-angle-records" open={open} onToggle={e=>setOpen(e.currentTarget.open)}><summary>{group?`${group.label} · ${group.count} throws`:`Inspect throws (${model.count})`}</summary>
      {group&&<Button onClick={()=>inspect(null)}>Show all directions in range</Button>}
      <DataTable key={selected??'all'} rows={records} searchable={false} columns={[
        {field:'game',label:'Game'},{field:'receiver',label:'Thrown to'},{field:'distance',label:'Distance (yd)',renderCell:decimal},{field:'angle',label:'Angle'},{field:'result',label:'Result'},
      ]} caption={`${player.name} · ${rangeLabel}${group?` · ${group.label}`:''}`}/>
    </details>
  </article>;
}

export function DistanceAngle({queries}) {
  const events=queries.events?.rows||[],summaries=queries.shownSpaceThrowers?.rows||[],players=queries.players?.rows||[];
  const [firstId,setFirstId]=useState('aatkins'),[secondId,setSecondId]=useState('jnissen');
  const [lower,setLower]=useState('15'),[upper,setUpper]=useState('20');
  const [highlightDirection,setHighlightDirection]=useState('all'),[comparisonRequest,setComparisonRequest]=useState(0);
  const finderRef=useRef(null),comparisonRef=useRef(null);
  const directory=useMemo(()=>focusDirectory(summaries),[summaries]);
  const choices=useMemo(()=>directory.map(p=>p.id),[directory]);
  const labels=useMemo(()=>Object.fromEntries(directory.map(p=>[p.id,`${p.name} · ${p.teamName}`])),[directory]);
  const names=useMemo(()=>Object.fromEntries(players.map(p=>[p.id,p.name])),[players]);
  const allUpper=useMemo(()=>Math.ceil((events.reduce((max,e)=>Math.max(max,throwLength(e)??0),0)+1)/10)*10,[events]);
  const valid=validDistanceRange(lower,upper),min=valid?Number(lower):0,max=valid?Number(upper):0;
  const allDistances=valid&&min===0&&max>=allUpper;
  const rangeLabel=allDistances?'All distances':`${lower}–${upper} yd`;
  const first=directory.find(p=>p.id===firstId)||directory[0],second=directory.find(p=>p.id===secondId)||directory[1]||directory[0];
  const indexed=useMemo(()=>indexPlayerThrows(events),[events]);
  const league=useMemo(()=>distanceAngleLeague(indexed,directory,min,max),[indexed,directory,min,max]);
  const firstModel=league.find(({player})=>player.id===first?.id)?.model||distanceAngleModel([],first?.id,min,max);
  const secondModel=league.find(({player})=>player.id===second?.id)?.model||distanceAngleModel([],second?.id,min,max);
  const scale=directionScale([firstModel,secondModel]);
  const sourceRows=useMemo(()=>[...new Map([...firstModel.allPasses,...secondModel.allPasses].map(e=>[e.id,e])).values()],[firstModel,secondModel]);
  const displayRows=useMemo(()=>first&&second?[...new Map([...directionDisplayRows(firstModel,first),...directionDisplayRows(secondModel,second)].map(r=>[`${r.playerId}:${r.id}`,r])).values()]:[],[first,second,firstModel,secondModel]);
  const jumpTo=ref=>{ref.current?.scrollIntoView({block:'start',behavior:'auto'});ref.current?.focus({preventScroll:true});};
  useEffect(()=>{
    if(!comparisonRequest)return;
    const frame=requestAnimationFrame(()=>jumpTo(comparisonRef));
    return()=>cancelAnimationFrame(frame);
  },[comparisonRequest]);
  const compare=(id,direction)=>{setSecondId(id);setHighlightDirection(direction);setComparisonRequest(value=>value+1);};
  if(!first||!second)return <p role="status">Player records are unavailable in this snapshot.</p>;
  return <section className="ufa-throwing-focus ufa-distance-angle" aria-label="Throw distance and angle">
    <h2 data-editable-id="ufa-distance-angle-question">Which directions do they throw at each distance?</h2>
    <div ref={finderRef} tabIndex={-1} className="ufa-angle-finder-section">
    <div className="ufa-angle-range-controls ufa-angle-global-controls" role="group" aria-label="Distance range for finder and comparison"><span>Distance in yards</span><label>From <input type="number" min="0" step="0.5" inputMode="decimal" aria-label="Minimum throw distance" value={lower} onChange={e=>setLower(e.target.value)}/></label><label>to under <input type="number" min="0" step="0.5" inputMode="decimal" aria-label="Maximum throw distance exclusive" value={upper} onChange={e=>setUpper(e.target.value)}/></label><Button onClick={()=>{setLower('0');setUpper(String(allUpper));}}>All distances</Button><Button onClick={()=>jumpTo(comparisonRef)}>View comparison</Button></div>
    <div className="ufa-angle-pickers">
      <Dropdown label="Player 1 · reference arrow" showLabel searchable value={first.id} choices={choices} choiceLabels={labels} onChange={setFirstId}/>
      <Dropdown label="Player 2" showLabel searchable value={second.id} choices={choices} choiceLabels={labels} onChange={setSecondId}/>
    </div>
      <PlayerFinder league={league} reference={first} secondId={second.id} rangeLabel={rangeLabel} validRange={valid} onCompare={compare} onClearComparisonFocus={()=>setComparisonRequest(0)} onDirectionChange={setHighlightDirection}/>
    </div>
    <div ref={comparisonRef} tabIndex={-1} className="ufa-angle-comparison" aria-label="Selected player comparison">
    <SortableRegion id="ufa:distance-angle" variant="stack" authoredOrder={['ufa-distance-angle-chart']} label="Distance and angle comparison">
      <SortableItem id="ufa-distance-angle-chart" label="Directions by distance" kind="custom">
        <DataComponent id="ufa-distance-angle-chart" title="Directions by distance" queryId="events" kind="custom" sourceRows={sourceRows} displayRows={valid?displayRows:[]}
          scopeFilters={[{label:'Players',value:[...new Set([first.name,second.name])].join(' / ')},{label:'Season',value:'2026 including playoffs · all lines'},{label:'Distance',value:valid?rangeLabel:'Invalid range'}]}
          description="All non-stall attempts, including drops and unnamed targets, from the selected players in the available 2026 season. Distance is Euclidean endpoint distance. Lower range boundary included; upper excluded. Average distance is the arithmetic mean of all located selected attempts. Average angle is the circular mean of source throwAngle values, one equal vote per positive-distance throw; zero distance or missing angle is excluded. Positive angles rotate left from forward. A numerical-zero mean resultant has no unique angle and is unavailable. Wedges use the source’s twelve lower-inclusive 30-degree bins. Most common is the bin with the most throws, preserving ties. Both diagrams use a shared frequency scale; arrow length is fixed and indicates only the mean direction. Direction selection opens matching records without changing the summaries. Source rows retain all player attempts for frequency denominators; displayed rows hold the selected-range distributions and averages."
          headerControls={<Button onClick={()=>jumpTo(finderRef)}>Back to player finder</Button>}
        >
          {!valid?<p className="ufa-angle-error" role="alert">Enter a range starting at 0 yards or more, with an upper limit greater than the lower limit.</p>:<>
            <p className="ufa-angle-range-note" data-reviewed-rows><strong>{rangeLabel} · All directions</strong> · Counts and averages use this range. Includes completed and incomplete throws.{highlightDirection!=='all'&&<> The finder’s {firstModel.groups[Number(highlightDirection)].label} direction is outlined.</>}</p>
            <div className="ufa-angle-legend"><span><i/>Throw frequency</span><span><i className="ufa-angle-mean-key"/>Average direction</span><span className="ufa-focus-note">Angles start at straight downfield (0°).</span></div>
            <div className="ufa-angle-profiles">
              <DirectionProfile key={`first:${first.id}:${min}:${max}`} player={first} model={firstModel} scale={scale} names={names} rangeLabel={rangeLabel} highlightDirection={highlightDirection}/>
              <DirectionProfile key={`second:${second.id}:${min}:${max}`} player={second} model={secondModel} scale={scale} names={names} rangeLabel={rangeLabel} highlightDirection={highlightDirection}/>
            </div>
            <p className="ufa-focus-note ufa-angle-reading">Each slice covers 30°. Longer slices mean a larger share of throws in this range; the outer ring is {percent(scale)} on both charts. The average can fall between frequently used directions.</p>
          </>}
        </DataComponent>
      </SortableItem>
    </SortableRegion>
    </div>
    <p className="ufa-focus-note ufa-focus-coverage">2026 including playoffs · October 12 export. Pittsburgh at Chicago, July 18, is missing. Choose All distances for whole-season averages.</p>
  </section>;
}
