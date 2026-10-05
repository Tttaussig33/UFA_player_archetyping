import React from 'react';
import portraits from '../assets/portraits.json';
import {fmt,clampX,roleLabel,eventRole,eventAec} from './model.js';
export const playerName=(players,id)=>players[id]?.name||id||'';
const initials=name=>name.split(' ').map(x=>x[0]).slice(0,2).join('');
const shortName=name=>{const words=name.split(' ');return words.length>1?words.slice(1).join(' '):name;};
export function Face({id,name,className=''}){return portraits[id]?<img className={`ufa-face ${className}`} src={portraits[id]} alt={name}/>:<span className={`ufa-face ufa-initials ${className}`} aria-label={name}>{initials(name)}</span>;}
const X=x=>48+(clampX(x)+26.65)*6,Y=y=>34+(120-y)*6;
const COLORS={throw:'#dfe9e6',receive:'#e6e3f2',combined:'#e0e8ed',callahan:'#e8e3dc'};
export function Field({zones,ranks,selectedZone,selectedPlayer,players,vectors,shownEvents,onZone,onEvent,svgRef,animate,enlarged}){
 const current=zones.find(z=>z.id===selectedZone),role=current.role,bottom=zones.find(z=>z.id==='own-endzone');
 return <svg ref={svgRef} className="ufa-field" data-reviewed-rows style={enlarged?{height:'auto'}:undefined} viewBox="0 0 416 818" role="group" aria-label="UFA field with player boxes: select a zone to inspect disc-flight vectors">
  <title>2026 UFA zone leaders and disc-flight vectors</title>
  <defs>{[['complete','#238268'],['turnover','#c15b49'],['callahan','#756096']].map(([id,color])=><marker key={id} id={`ufa-${id}-arrow`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="4" markerHeight="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill={color}/></marker>)}<clipPath id="ufa-field-clip"><rect x="48" y="34" width="319.8" height="720"/></clipPath></defs>
  <rect width="416" height="818" fill="#fafbf9"/>
  <text x="208" y="16" textAnchor="middle" fill="#6a667e" fontSize="10" letterSpacing="1.2">{roleLabel(zones[0].role)}</text>
  <text x="390" y="310" transform="rotate(90 390 310)" textAnchor="middle" fill="#48655d" fontSize="10" letterSpacing="1.2">{roleLabel(zones.find(z=>z.id==='center-init').role)} · ATTACK ↑</text>
  {zones.map(z=>{
   const leader=ranks[z.id]?.[0],name=leader?playerName(players,leader.id):null;
   const left=X(z.x0),top=Y(z.y1),w=(z.x1-z.x0)*6,h=(z.y1-z.y0)*6,active=z.id===selectedZone;
   const short=h<=60.1,slim=w<90,faceH=short?31:52,center=left+w/2,faceY=short?top+3:top+h/2-45,faceX=short?(w<250?left+9:center-60):center-faceH/2,textX=short?(w<250?left+48:center+8):center;
   const lines=name?(slim?shortName(name).split(/[- ]/).reduce((arr,part)=>{if(arr.length&&arr.at(-1).length+part.length<12)arr[arr.length-1]+=' '+part;else arr.push(part);return arr;},[]):[shortName(name)]):[];
   return <g key={z.id} className="ufa-zone" role="button" tabIndex={0} aria-label={`${z.label}, ${roleLabel(z.role)}: ${name||'No recorded events'}`} aria-pressed={active} onClick={()=>onZone(z.id)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onZone(z.id);}}}>
    <title>{z.label}: {name?`${name}, ${fmt(leader.aec)} ${roleLabel(z.role)}`:'No recorded events'}</title>
    <rect x={left} y={top} width={w} height={h} fill={COLORS[z.role]} stroke={active?'#173f34':'#abb8b2'} strokeWidth={active?2.1:.7}/>
    <g opacity={vectors ? .13 : 1} pointerEvents="none">{leader?<>
     {portraits[leader.id]?<image href={portraits[leader.id]} x={faceX} y={faceY} width={faceH} height={faceH} preserveAspectRatio="xMidYMid meet"/>:<text x={short?faceX+15:center} y={faceY+29} fontSize="18" textAnchor="middle" fill="#456359">{initials(name)}</text>}
     {lines.slice(0,3).map((line,i)=><text key={i} x={textX} y={short?top+19+i*14:faceY+faceH+15+i*14} fontSize={short?13:slim?12:14} fontWeight="650" textAnchor={short?'start':'middle'} fill="#213e35">{line}</text>)}
     <text x={textX} y={short?top+36:faceY+faceH+15+lines.slice(0,3).length*14} fontSize="11" textAnchor={short?'start':'middle'} fill="#597168">{fmt(leader.aec)} aEC</text>
    </>:<text x={center} y={top+h/2} fontSize="10" textAnchor="middle" fill="#77857f">No recorded {z.role==='callahan'?'Callahans':z.role==='combined'?'contributions':z.role==='throw'?'throws':'catches / drops'}</text>}</g>
   </g>;
  })}
  {[0,20,40,60,80,100,120].map(y=><text key={y} x="37" y={Y(y)+3} textAnchor="end" fontSize="9" fill="#75817b">{y}</text>)}
  <text x="13" y="398" transform="rotate(-90 13 398)" textAnchor="middle" fill="#75817b" fontSize="10">FIELD LENGTH (YARDS)</text>
  {[20,100].map(y=><line key={y} x1={X(-26.65)} x2={X(26.65)} y1={Y(y)} y2={Y(y)} stroke="#536a60" strokeWidth="1.5"/>)}
  {vectors&&<g clipPath="url(#ufa-field-clip)" key={`${selectedZone}-${selectedPlayer}-${animate}`}>
   {shownEvents.map((e,i)=>{const contribution=eventRole(e,role),receiving=role==='combined'&&contribution==='receive',outcome=role==='callahan'?'callahan':e.complete?'complete':'turnover',color=outcome==='complete'?'#238268':outcome==='turnover'?'#c15b49':'#756096',anchor=contribution==='throw'?[e.tx,e.ty]:[e.rx,e.ry];
    return <g key={`${e.id}-${contribution}`} className="ufa-trajectory" data-credit-role={contribution} style={{animationDelay:`${Math.min(i*7,650)}ms`}} onMouseEnter={()=>onEvent(e)} onMouseLeave={()=>onEvent(null)}><title>{e.game}: {role==='callahan'?`${playerName(players,e.player)} interception`:`${playerName(players,e.thrower)} → ${e.receiver?playerName(players,e.receiver):'turnover'}`} · {fmt(role==='combined'?eventAec(e,role):e.aec,3)} {role==='combined'?roleLabel(contribution):'event aEC'}</title><line x1={X(e.tx)} y1={Y(e.ty)} x2={X(e.rx)} y2={Y(e.ry)} stroke={color} strokeWidth=".95" opacity=".55" strokeDasharray={receiving?'3 2':undefined} markerEnd={`url(#ufa-${outcome}-arrow)`}/>{receiving?<rect x={X(anchor[0])-2} y={Y(anchor[1])-2} width="4" height="4" fill={outcome==='turnover'?color:'#fafbf9'} stroke="#27473b" strokeWidth=".8"/>:<circle cx={X(anchor[0])} cy={Y(anchor[1])} r="2" fill={outcome==='turnover'?color:'#fafbf9'} stroke={outcome==='callahan'?color:'#27473b'} strokeWidth=".8"/>}</g>;
   })}
   <rect x={X(current.x0)+3} y={Y(current.y0)-18} width={(current.x1-current.x0)*6-6} height="15" rx="2" fill="#fafbf9" fillOpacity=".88"/>
   <text x={(X(current.x0)+X(current.x1))/2} y={Y(current.y0)-7} fontSize={current.x1-current.x0<15?8:10} fontWeight="600" textAnchor="middle" fill="#234136">{shortName(playerName(players,selectedPlayer))}</text>
  </g>}
  <rect x="48" y="34" width="319.8" height="720" fill="none" stroke="#536a60" strokeWidth="1.2" pointerEvents="none"/>
  <text x="208" y="773" textAnchor="middle" fill="#716759" fontSize="10" letterSpacing="1.1">{bottom.role==='callahan'?'CALLAHAN aEC':`OWN END ZONE · ${roleLabel(bottom.role)}`}</text><text x="208" y="796" textAnchor="middle" fill="#75817b" fontSize="10">← 53.3 yards wide →</text>
 </svg>;
}
