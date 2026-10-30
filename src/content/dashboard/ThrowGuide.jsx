import React,{useId,useRef,useState} from 'react';
import {Button,Dialog} from '../../data-app-public.jsx';
import {clampGuidePoint,guideMetrics,THROW_EXAMPLES} from './throw-guide-model.js';
import './throw-guide.css';

const X=x=>170+x*4,Y=y=>516-y*4;
const points=rows=>rows.map(([x,y])=>`${X(x)},${Y(y)}`).join(' ');
const num=n=>Number.isFinite(n)?n.toFixed(1):'—';
const signed=n=>`${n>0?'+':''}${num(n)}`;

export function ThrowGuide({open,onClose}) {
  const [pass,setPass]=useState(THROW_EXAMPLES[1]);
  const dragging=useRef(null),svgRef=useRef(null),uid=useId().replaceAll(':','');
  const m=guideMetrics(pass),start={x:pass.tx,y:pass.ty},end={x:pass.rx,y:pass.ry};
  const bearing=m.angle??0,axis=m.gain<0?-1:1;
  const changePoint=(which,point)=>{
    const p=clampGuidePoint(point);
    setPass(previous=>({...previous,id:'custom',...(which==='start'?{tx:p.x,ty:p.y}:{rx:p.x,ry:p.y})}));
  };
  const fromPointer=event=>{
    const svg=svgRef.current,matrix=svg?.getScreenCTM();
    if(!matrix)return null;
    const point=svg.createSVGPoint();point.x=event.clientX;point.y=event.clientY;
    const local=point.matrixTransform(matrix.inverse());
    return {x:(local.x-170)/4,y:(516-local.y)/4};
  };
  const beginDrag=(event,which)=>{
    if(event.button!==0)return;
    const p=fromPointer(event);if(!p)return;
    event.preventDefault();event.stopPropagation();
    dragging.current=which;svgRef.current.setPointerCapture(event.pointerId);
    changePoint(which,p);
  };
  const endDrag=event=>{dragging.current=null;if(svgRef.current?.hasPointerCapture(event.pointerId))svgRef.current.releasePointerCapture(event.pointerId);};
  const moveWithKeys=(event,which)=>{
    const step=event.shiftKey?5:1,delta={ArrowUp:[0,step],ArrowDown:[0,-step],ArrowLeft:[-step,0],ArrowRight:[step,0]}[event.key];
    if(!delta)return;
    event.preventDefault();const p=which==='start'?start:end;changePoint(which,{x:p.x+delta[0],y:p.y+delta[1]});
  };
  const arcAngle=m.gain<0?(m.angle>=0?180:-180):0;
  const arcPoint=a=>[X(pass.tx)+Math.sin(a*Math.PI/180)*32,Y(pass.ty)-Math.cos(a*Math.PI/180)*32];
  const arcStart=arcPoint(arcAngle),arcEnd=arcPoint(bearing);
  const labelAngle=(arcAngle+bearing)/2*Math.PI/180;
  return <Dialog open={open} onClose={onClose} title="Field guide">
    <div className="ufa-throw-guide">
      <p className="ufa-guide-intro">Drag T (thrower) or D (destination).</p>
      <div className="ufa-guide-examples" aria-label="Example throws">
        {[THROW_EXAMPLES[1],THROW_EXAMPLES[3]].map(example=><Button key={example.id} aria-pressed={pass.id===example.id} onClick={()=>setPass(example)}>{example.label}</Button>)}
      </div>
      <svg ref={svgRef} viewBox="0 0 340 560" className="ufa-guide-field" role="group" aria-label="Interactive ultimate field; attack is toward the top"
        onPointerMove={event=>{if(dragging.current){const p=fromPointer(event);if(p)changePoint(dragging.current,p);}}}
        onPointerUp={endDrag} onPointerCancel={endDrag} onLostPointerCapture={()=>{dragging.current=null;}}>
        <defs>
          <clipPath id={`${uid}-field`}><rect x={X(-26.65)} y={Y(120)} width="213.2" height="480"/></clipPath>
          <marker id={`${uid}-arrow`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="4" markerHeight="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="currentColor"/></marker>
        </defs>
        <g aria-hidden="true" pointerEvents="none">
          <text x="170" y="18" textAnchor="middle" className="ufa-guide-end-label">Attack ↑</text>
          <rect x={X(-26.65)} y={Y(120)} width="213.2" height="480" className="ufa-guide-grass"/>
          <g clipPath={`url(#${uid}-field)`}>
            <polygon points={points([[pass.tx,pass.ty],[pass.tx-150,pass.ty+axis*150],[pass.tx+150,pass.ty+axis*150]])} className="ufa-guide-cone"/>
            {[20,100].map(y=><line key={y} x1={X(-26.65)} y1={Y(y)} x2={X(26.65)} y2={Y(y)} className="ufa-guide-goal"/>)}
            <line x1={X(pass.tx)} y1={Y(pass.ty)} x2={X(pass.tx)} y2={Y(axis>0?120:0)} className="ufa-guide-axis"/>
            {[-1,1].map(dx=><line key={dx} x1={X(pass.tx)} y1={Y(pass.ty)} x2={X(pass.tx+dx*150)} y2={Y(pass.ty+axis*150)} className="ufa-guide-boundary"/>)}
            {m.offset>0&&<path d={`M${arcStart.join(',')} A32,32 0 0 ${bearing>arcAngle?1:0} ${arcEnd.join(',')}`} className="ufa-guide-angle-arc"/>}
            {m.distance>0&&<line x1={X(pass.tx)} y1={Y(pass.ty)} x2={X(pass.rx)} y2={Y(pass.ry)} className="ufa-guide-flight-line" markerEnd={`url(#${uid}-arrow)`}/>}
          </g>
          {m.offset>0&&<text x={Math.max(30,Math.min(310,X(pass.tx)+Math.sin(labelAngle)*53))} y={Math.max(50,Math.min(506,Y(pass.ty)-Math.cos(labelAngle)*53+4))} textAnchor="middle" className="ufa-guide-angle-label">{num(m.offset)}°</text>}
          <rect x={X(-26.65)} y={Y(120)} width="213.2" height="480" className="ufa-guide-outline"/>
          <text x="170" y={Y(110)+4} textAnchor="middle" className="ufa-guide-zone-label">Attacking end zone</text>
          <text x="170" y={Y(10)+4} textAnchor="middle" className="ufa-guide-zone-label">Own end zone</text>
        </g>
        <rect x={X(-26.65)} y={Y(120)} width="213.2" height="480" fill="transparent" onPointerDown={event=>beginDrag(event,'end')}/>
        {[['start',start,'T','Thrower'],['end',end,'D','Disc destination']].map(([key,p,letter,label])=><g key={key} role="button" tabIndex={0} className="ufa-guide-handle" aria-label={`${label} marker; use arrow keys to move, Shift for five yards`}
          onKeyDown={event=>moveWithKeys(event,key)} onPointerDown={event=>beginDrag(event,key)}>
          <circle cx={X(p.x)} cy={Y(p.y)} r="18" className="ufa-guide-hit"/>
          <circle cx={X(p.x)} cy={Y(p.y)} r="11" className={key==='start'?'ufa-guide-start':'ufa-guide-end'}/>
          <text x={X(p.x)} y={Y(p.y)+4} textAnchor="middle" className="ufa-guide-handle-label">{letter}</text>
        </g>)}
      </svg>
      <dl className="ufa-guide-readout" aria-live="polite" aria-atomic="true">
        <div><dt>Angle</dt><dd>{m.angle===null?'—':`${num(m.offset)}°`}</dd><small>{m.angle===null?'Move the dots apart':`from ${axis>0?'forward':'backward'}`}</small></div>
        <div><dt>Gain (yd)</dt><dd>{signed(m.gain)}</dd><small>Forward progress</small></div>
        <div><dt>Flight (yd)</dt><dd>{num(m.distance)}</dd><small>Straight-line distance</small></div>
      </dl>
      <details className="ufa-guide-details"><summary>How to read it</summary>
        <p>This is an example pass. The shaded area extends 45° either side of straight forward or backward. The arc shows the throw’s angle from that direction.</p>
        <p>Forward means toward the attacking end zone; backward means toward your own. Gain is negative for a backward throw. Flight measures the straight line between the dots.</p>
        <p>In Player styles, exactly 45° is grouped with sideways throws. Hucks require both gain over 30 yd and flight over 40 yd. This guide uses coordinates; Throw radials keeps Shown Space’s recorded-angle convention.</p>
        <p>Click anywhere on the field to move D, or focus either marker and use arrow keys. Hold Shift to move five yards.</p>
      </details>
    </div>
  </Dialog>;
}
