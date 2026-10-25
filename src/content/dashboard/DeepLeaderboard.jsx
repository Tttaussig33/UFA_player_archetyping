import React,{useEffect,useMemo,useRef,useState} from 'react';
import {Button,ChartMark,ChartTooltip,DataComponent,Dropdown} from '../../data-app-public.jsx';
import {ZONES,fmt,int} from './model.js';
import {Face,playerName} from './Field.jsx';
import {completionInterval,rankDeepThrowers} from './deep-thrower-model.js';

const percent=value=>value==null?'—':`${fmt(value*100,1)}%`;
const orderedIds=['own-endzone','center-init','left-build','center-build','right-build','left-attack','center-attack','right-attack','center-red','ez-left','ez-right','ez-deep'];
const shortNames={'own-endzone':'Own end zone','center-init':'Initiation','left-build':'Left build-up','center-build':'Center build-up','right-build':'Right build-up','left-attack':'Left attack','center-attack':'Center attack','right-attack':'Right attack','center-red':'Red zone','ez-left':'Left end zone','ez-right':'Right end zone','ez-deep':'Deep end zone'};
const clean=value=>value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
const totalStats=stats=>{
  const attempts=stats.reduce((n,s)=>n+s.attempts,0),completed=stats.reduce((n,s)=>n+s.completed,0);
  const [lower,upper]=completionInterval(completed,attempts);
  return {attempts,completed,rate:attempts?completed/attempts:null,lower,upper};
};

function RateCell({stats,minimum,name,zone,onInspect,baseline=false,overallRate=null,scopeRate=null}) {
  if(!stats.attempts)return <span className="ufa-deep-no-attempts" aria-label={`${name} · ${zone}: no huck attempts`}>—</span>;
  const small=stats.attempts<minimum;
  if(baseline)return <span className="ufa-deep-baseline-value"><strong>{percent(stats.rate)}</strong><small>{int(stats.completed)}/{int(stats.attempts)}</small></span>;
  return <ChartMark className={`ufa-deep-matrix-cell${small?' is-small-sample':''}`}
    style={{'--cell-fill':small?'transparent':`color-mix(in srgb,var(--chart-1) ${8+stats.rate*34}%,var(--surface))`}}
    aria-label={`${name} · ${zone}: ${stats.completed}/${stats.attempts} complete, ${percent(stats.rate)}${small?`, below ${minimum}-attempt minimum`:''}`}
    context={{kind:'chart',chartType:'heatmap',label:`${name} · ${zone}`,value:stats.rate,row:{player:name,zone,...stats},actions:[{label:'View player and hucks',onSelect:onInspect}]}}
    tooltip={<ChartTooltip active label={`${name} · ${zone}`} headerValue={percent(stats.rate)} details={[
      {label:'Completed / attempts',value:`${stats.completed} / ${stats.attempts}`},
      {label:'95% Wilson interval',value:`${percent(stats.lower)}–${percent(stats.upper)}`},
      ...(Number.isFinite(overallRate)?[{label:'Player’s overall completion',value:percent(overallRate)},{label:'Difference from their overall rate',value:`${stats.rate>=overallRate?'+':''}${fmt((stats.rate-overallRate)*100,1)} percentage points`}]:[]),
      ...(Number.isFinite(scopeRate)?[{label:'All throwers in this location',value:percent(scopeRate)}]:[]),
      ...(small?[{label:'Small sample',value:`Fewer than ${minimum} attempts; not eligible for a zone ranking`}]:[]),
    ]}/>}>
    <strong>{percent(stats.rate)}</strong><small>{stats.completed}/{stats.attempts}{small?' · low n':''}</small>
  </ChartMark>;
}

export function DeepLeaderboard({comparison,events,players,teams,scopeFilters,minimum,onMinimumChange,onInspect,selectedPlayer}) {
  const [zoneId,setZoneId]=useState('all'),[playerMinimum,setPlayerMinimum]=useState('20');
  const [sort,setSort]=useState('rate'),[search,setSearch]=useState(''),[page,setPage]=useState(0);
  const [quality,setQuality]=useState('scope');
  const matrixRef=useRef(null);
  const zones=useMemo(()=>orderedIds.map(id=>ZONES.find(z=>z.id===id)).filter(z=>z.y0<100||
    comparison.some(p=>p.zones.find(s=>s.id===z.id)?.attempts>0)||z.id===zoneId),[comparison,zoneId]);
  const directory=useMemo(()=>comparison.map(p=>({...p,name:playerName(players,p.id),
    teamLabel:p.teamIds.map(id=>teams.find(t=>t.id===id)?.abbrev||id).join(' / '),
    teamNames:p.teamIds.map(id=>teams.find(t=>t.id===id)?.name||id).join(' ')})),[comparison,players,teams]);
  const baseline=useMemo(()=>({...totalStats(comparison),zones:Object.fromEntries(ZONES.map(z=>[z.id,totalStats(comparison.map(p=>p.zones.find(s=>s.id===z.id)))]))}),[comparison]);
  const scopeRate=(zoneId==='all'?baseline:baseline.zones[zoneId]).rate;
  const minimumRate=quality==='scope'?scopeRate:quality==='all'?null:Number(quality)/100;
  const qualityLabel=quality==='scope'?`At least scope average (${percent(scopeRate)})`:quality==='all'?'Any completion rate':`At least ${quality}%`;
  const eligible=useMemo(()=>rankDeepThrowers(directory,{zoneId,minimumPlayer:Number(playerMinimum),minimumZone:Number(minimum),minimumRate,sort}),[directory,zoneId,playerMinimum,minimum,minimumRate,sort]);
  const matching=useMemo(()=>eligible.filter(p=>clean(`${p.name} ${p.teamLabel} ${p.teamNames}`).includes(clean(search))),[eligible,search]);
  useEffect(()=>setPage(0),[comparison,zoneId,playerMinimum,minimum,quality,sort,search]);
  useEffect(()=>{
    const container=matrixRef.current,selected=container?.querySelector('thead th.is-ranked'),playerColumn=container?.querySelector('.ufa-deep-player-column');
    if(container&&selected&&container.scrollWidth>container.clientWidth) {
      const left=selected.getBoundingClientRect().left-container.getBoundingClientRect().left+container.scrollLeft-(playerColumn?.getBoundingClientRect().width||0);
      container.scrollTo({left:Math.max(0,left),behavior:'auto'});
    }
  },[zoneId]);
  const pageSize=15,pageCount=Math.max(1,Math.ceil(matching.length/pageSize)),currentPage=Math.min(page,pageCount-1);
  const shown=matching.slice(currentPage*pageSize,(currentPage+1)*pageSize);
  const sourceRows=useMemo(()=>events.filter(e=>!e.stall&&e.thrower&&e.thrower!=='unknown'),[events]);
  const displayRows=useMemo(()=>[
    ...[{id:'all',label:'All locations'},...zones].map(z=>{const stats=z.id==='all'?baseline:baseline.zones[z.id];return {rowType:'Scope baseline',player:'All throwers in scope',zone:z.label,attempts:stats.attempts,completed:stats.completed,completionRate:stats.rate,wilson95Low:stats.lower,wilson95High:stats.upper};}),
    ...matching.flatMap((p,index)=>[{...p,id:'all',label:'All locations'},...zones.map(z=>p.zones.find(s=>s.id===z.id))].map(z=>({rowType:'Player',rank:index+1,player:p.name,team:p.teamLabel,zone:z.label,attempts:z.attempts,completed:z.completed,completionRate:z.rate,overallCompletionRate:p.rate,differenceFromOverall:z.rate===null?null:z.rate-p.rate,scopeLocationRate:(z.id==='all'?baseline:baseline.zones[z.id]).rate,wilson95Low:z.lower,wilson95High:z.upper,huckShareOfThrows:p.huckShare,meetsZoneMinimum:z.attempts>=Number(minimum)}))),
  ],[matching,zones,baseline,minimum]);
  const zoneLabel=zoneId==='all'?'All locations':ZONES.find(z=>z.id===zoneId)?.label;
  const unmapped=comparison.reduce((sum,p)=>sum+p.unmappedReleases,0);
  const rankLocation=id=>{setZoneId(id);setPage(0);};
  return <div className="ufa-deep-leaderboard">
    <div className="ufa-deep-board-controls">
      <label className="ufa-deep-find"><span>Find players</span><input type="search" aria-label="Filter deep thrower leaderboard" value={search} placeholder="Player or team…" onChange={event=>setSearch(event.target.value)}/></label>
      <Dropdown label="Rank location" showLabel value={zoneId} choices={['all',...zones.map(z=>z.id)]} allLabel="All locations" choiceLabels={Object.fromEntries(zones.map(z=>[z.id,z.label]))} onChange={rankLocation}/>
      <Dropdown label="Rank by" showLabel value={sort} choices={['rate','attempts']} choiceLabels={{rate:'Completion rate',attempts:'Huck attempts (volume)'}} onChange={setSort}/>
      <Dropdown label="Completion filter" showLabel value={quality} choices={['scope','70','80','all']} allLabel="Any completion rate" choiceLabels={{scope:'At least scope average',70:'70% or higher',80:'80% or higher'}} onChange={setQuality}/>
      <Dropdown label="Player minimum" showLabel value={playerMinimum} choices={['1','10','20','30']} choiceLabels={{1:'1+ hucks',10:'10+ hucks',20:'20+ hucks',30:'30+ hucks'}} onChange={setPlayerMinimum}/>
      <Dropdown label="Zone minimum" showLabel value={minimum} choices={['3','5','10']} choiceLabels={{3:'3 attempts',5:'5 attempts',10:'10 attempts'}} onChange={onMinimumChange}/>
    </div>
    <DataComponent id="ufa-deep-comparison" queryId="events" kind="custom" title="Huck completion by release zone" sourceRows={sourceRows} displayRows={displayRows}
      scopeFilters={[...scopeFilters,{field:'thrower',label:'Player minimum',value:`${playerMinimum} huck attempts across all locations`},{field:'tx',label:'Rank location',value:zoneLabel},{field:'id',label:'Zone minimum',value:`${minimum} attempts in the ranked zone`},{field:'complete',label:'Completion filter',value:qualityLabel},{field:sort==='rate'?'complete':'id',label:'Rank by',value:sort==='rate'?'Completion rate':'Huck attempts (volume)'},{field:'thrower',label:'Search',value:search||'All players'}]}
      description="Players must meet the total huck minimum and the completion-rate filter in the ranked location. Choosing a release zone also requires the zone minimum there; other cells retain all counts. Rank by completion rate or attempts in the chosen location; tied completion rates use more attempts, then player ID. The baseline pools every named thrower in the team, phase and line scope, before minimums, completion filtering and search. It changes with the ranked zone, team, season phase and line. Huck share divides a player’s hucks by non-stall throws with usable endpoints. Colors use the same 0–100% completion scale. These are observed results, not difficulty-adjusted player ratings.">
      <div className="ufa-deep-board-caption"><p>Select a zone heading to rank it. Inspect a cell to compare with the player’s overall rate; select a player for field maps.</p><span data-reviewed-rows>{zoneLabel} · {matching.length} player{matching.length===1?'':'s'}</span></div>
      <p className="ufa-deep-filter-explainer" data-reviewed-rows><strong>{qualityLabel}</strong> in {zoneLabel.toLowerCase()}. The attempt minimum sets the sample size; completion measures success.{sort==='attempts'?' Volume sorting orders only the players who pass these filters.':''}</p>
      <div className="ufa-deep-board-key"><span><i className="ufa-deep-key-gradient"/>0 → 100% completion</span><span><i className="ufa-deep-key-small"/>Below {minimum} attempts</span><span>Each cell: completion % · completed/attempted</span></div>
      <div ref={matrixRef} className="ufa-deep-matrix-scroll" tabIndex={0} aria-label="Deep thrower leaderboard; scroll horizontally to compare all field zones" data-chart-interaction-root data-reviewed-rows>
        <table className="ufa-deep-matrix">
          <caption className="ufa-deep-sr">Players ranked by {sort==='rate'?'completion rate':'huck attempts'} in {zoneLabel}. Field distances are yards from the back of the own end zone; offense attacks toward 120.</caption>
          <thead><tr><th scope="col" className="ufa-deep-player-column">Player<small>Team · share of throws that are hucks</small></th>
            {[{id:'all',label:'All locations'},...zones].map(z=><th key={z.id} scope="col" className={zoneId===z.id?'is-ranked':''} aria-sort={zoneId===z.id?'descending':'none'}><button aria-label={`Rank by ${z.label}`} aria-pressed={zoneId===z.id} onClick={()=>rankLocation(z.id)}>{z.id==='all'?'All locations':shortNames[z.id]}<small>{z.id==='all'?'Whole field':`${z.y0}–${z.y1} yd`}</small></button></th>)}
          </tr></thead>
          <tbody><tr className="ufa-deep-baseline"><th scope="row" className="ufa-deep-player-column">All throwers in scope<small>Before eligibility filters and search</small></th>
            {[{id:'all',stats:baseline},...zones.map(z=>({id:z.id,stats:baseline.zones[z.id]}))].map(({id,stats})=><td key={id} className={zoneId===id?'is-ranked':''}><RateCell baseline stats={stats} name="All throwers" zone={id==='all'?'All locations':shortNames[id]}/></td>)}
          </tr>
          {shown.map((p,index)=><tr key={p.id} data-selected={p.id===selectedPlayer}>
            <th scope="row" className="ufa-deep-player-column"><button className="ufa-deep-player-link" onClick={()=>onInspect(p.id,zoneId==='all'?null:zoneId)} aria-label={`View ${p.name} profile`}><span className="ufa-deep-place">{currentPage*pageSize+index+1}</span><Face id={p.id} name={p.name}/><span>{p.name}<small>{p.teamLabel} · {percent(p.huckShare)} hucks</small></span></button></th>
            {[{...p,id:'all',label:'All locations'},...zones.map(z=>p.zones.find(s=>s.id===z.id))].map(z=><td key={z.id} className={zoneId===z.id?'is-ranked':''}><RateCell stats={z} minimum={z.id==='all'?Number(playerMinimum):Number(minimum)} name={p.name} zone={z.label} overallRate={z.id==='all'?null:p.rate} scopeRate={(z.id==='all'?baseline:baseline.zones[z.id]).rate} onInspect={()=>onInspect(p.id,z.id==='all'?null:z.id)}/></td>)}
          </tr>)}
          </tbody>
        </table>
      </div>
      {!matching.length&&<div className="ufa-empty" role="status">No players meet these filters. Try All locations, lower the minimums, choose Any completion rate, or clear the player search.</div>}
      <div className="ufa-pagination" data-reviewed-rows><span>{matching.length?`${currentPage*pageSize+1}–${Math.min((currentPage+1)*pageSize,matching.length)} of ${matching.length} player${matching.length===1?'':'s'}`:'0 players'}{search?` · ${eligible.length} before search`:''}</span><Button disabled={!currentPage} onClick={()=>setPage(currentPage-1)}>Previous players</Button><Button disabled={currentPage+1>=pageCount} onClick={()=>setPage(currentPage+1)}>More players</Button></div>
      <p className="ufa-deep-note">Hucks travel more than 40 yards and gain more than 30 yards forward. A 100% cell on five throws is still a small sample. Hover for the completion interval; rates do not adjust for throw difficulty or opponents. Distances run from your own end zone (0) toward the attacking end zone (120).{unmapped>0?` ${unmapped} hucks have releases outside the mapped field; included in All locations.`:''}</p>
    </DataComponent>
  </div>;
}
