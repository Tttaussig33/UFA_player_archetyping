import React,{useMemo} from 'react';
import {Button,DataComponent,Dropdown} from '../../data-app-public.jsx';
import {ZONES,fmt,int} from './model.js';
import {buildHuckSetups,sequenceSource} from './deep-thrower-model.js';

const percent=value=>value==null?'—':`${fmt(value*100,1)}%`;

export function DeepSetups({model,links,name,scopeFilters,minimum,zoneId,onZoneChange,onInspect}) {
  const setups=useMemo(()=>buildHuckSetups(model,links,zoneId),[model,links,zoneId]);
  const sourceRows=useMemo(()=>sequenceSource(setups.throws,links),[setups,links]);
  const zoneLabel=zoneId==='all'?'All locations':ZONES.find(z=>z.id===zoneId)?.label;
  const rows=[{...setups,id:'all',label:'All setups',detail:'Includes unclassified setups'},...setups.groups];
  const displayRows=rows.map(row=>({player:name,releaseZone:zoneLabel,setup:row.label,nextThrows:row.nextThrows,
    huckAttempts:row.attempts,completedHucks:row.completed,huckChoiceRate:row.huckShare,huckCompletionRate:row.rate,
    completion95Low:row.lower,completion95High:row.upper,belowSampleMinimum:row.attempts<minimum}));
  return <section className="ufa-deep-setups" aria-label="Incoming pass tendencies">
    <div className="ufa-deep-record-controls"><Dropdown label="Setup release location" showLabel value={zoneId} choices={['all',...ZONES.map(z=>z.id)]} allLabel="All locations" choiceLabels={Object.fromEntries(ZONES.map(z=>[z.id,z.label]))} onChange={onZoneChange}/></div>
    <DataComponent id="ufa-deep-setups" queryId="events" kind="custom" title="What happens after the incoming pass?" sourceRows={sourceRows} displayRows={displayRows}
      scopeFilters={[...scopeFilters,{field:'thrower',label:'Thrower',value:name},{field:'tx',label:'Release location',value:zoneLabel},{field:'possessionThrow',label:'Setup grouping',value:'Direction of the verified preceding pass; unknown and zero-distance setups stay unclassified'}]}
      description="Group recorded throws by the disc-flight direction of their unique verified prior completed pass. Forward means prior dy > abs(dx); backward means -dy > abs(dx); lateral means abs(dx) >= abs(dy) with nonzero distance. Missing links, incomplete geometry and zero-distance prior passes stay unclassified. Huck choice divides huck attempts by all non-stall throws with usable current endpoints in each group. Catches with no recorded next throw are not in that denominator. Huck completion divides completed hucks by attempted hucks. Release-location filtering uses the current throw origin, after the page team, phase and line filters. The original next throws and verified prior passes are retained once in source rows. Intervals use the same two-sided 95% Wilson calculation as the release maps; they do not adjust for game dependence or throw difficulty.">
      <p className="ufa-deep-setup-intro">Does {name} choose to huck more often after a forward, lateral, or backward pass—and do those hucks succeed? Compare within a release location to narrow the situation.</p>
      <div className="ufa-table-scroll" data-reviewed-rows>
        <table className="ufa-deep-setup-table">
          <caption className="ufa-deep-sr">{name}: huck choice and completion by incoming pass direction, {zoneLabel}</caption>
          <thead><tr><th scope="col">Incoming pass</th><th scope="col" className="ufa-num">Huck choice</th><th scope="col" className="ufa-num">Huck completion</th><th scope="col"><span className="ufa-deep-sr">Inspect source hucks</span></th></tr></thead>
          <tbody>{rows.map(row=><tr key={row.id} className={row.id==='all'?'ufa-deep-setup-baseline':''}>
            <th scope="row"><strong>{row.label}</strong><small>{row.detail}</small></th>
            <td className="ufa-num"><strong>{percent(row.huckShare)}</strong><small>{int(row.attempts)} / {int(row.nextThrows)} throws</small></td>
            <td className="ufa-num"><strong>{percent(row.rate)}</strong><small>{int(row.completed)} / {int(row.attempts)} hucks completed</small>
              {row.attempts>0&&<span className="ufa-deep-setup-interval">95% interval: {percent(row.lower)}–{percent(row.upper)}{row.attempts<minimum?' · small sample':''}</span>}</td>
            <td>{row.id!=='all'&&<Button disabled={!row.attempts} aria-label={`Inspect ${row.label.toLowerCase()} hucks`} onClick={()=>onInspect({kind:'setup',setupId:row.id,zoneId})}>Inspect {int(row.attempts)} hucks</Button>}</td>
          </tr>)}</tbody>
        </table>
      </div>
      {!setups.nextThrows&&<p className="ufa-empty" role="status">No throws with usable endpoints in this release location. Choose All locations to broaden the comparison.</p>}
      <p className="ufa-deep-note">Huck choice uses recorded throws with known endpoints, including short throws. Huck completion uses only huck attempts. These directions describe disc flight, not a confirmed swing, upline cut, or dead-disc start.{setups.missingGeometry>0?` ${setups.missingGeometry} throws with missing endpoint coordinates are excluded from both rates.`:''}</p>
      <p className="ufa-deep-note">The percentages describe observed tendencies. Differences can reflect receiver, defense, distance and game situation; a small group is a starting point for film review.</p>
    </DataComponent>
  </section>;
}
