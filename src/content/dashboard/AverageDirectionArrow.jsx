import React from 'react';
import {directionPoint} from './throwing-focus-model.js';
import {averageAngleLabel} from './distance-angle-model.js';
import './average-direction-arrow.css';

export function AverageDirectionArrow({angle,compact=false}) {
  if(!Number.isFinite(angle))return null;
  const tip=directionPoint(angle,144);
  const base=directionPoint(angle,compact?106:132);
  const tail=directionPoint(angle,compact?-72:0);
  const left=directionPoint(angle+90,compact?22:5,...base);
  const right=directionPoint(angle-90,compact?22:5,...base);
  const label=averageAngleLabel(angle).replace(' of forward','');
  // Keep the label beside the actual endpoint, including left/right/backward means.
  const labelAfter=tip[0]<110||(tip[0]>180&&tip[0]<250);
  const labelY=tip[1]+(Math.abs(tip[0]-180)>100?-12:4);
  return <svg className={`ufa-average-arrow${compact?' is-compact':''}`} viewBox="0 0 360 360" aria-hidden="true">
    {compact&&<circle className="ufa-average-arrow-ring" cx="180" cy="180" r="153"/>}
    <line className="ufa-average-arrow-forward" x1="180" y1="180" x2="180" y2="36"/>
    <line className="ufa-average-arrow-shaft" x1={tail[0]} y1={tail[1]} x2={base[0]} y2={base[1]}/>
    <polygon className="ufa-average-arrow-head" points={[tip,left,right].map(p=>p.join(',')).join(' ')}/>
    {!compact&&<>
      <circle className="ufa-average-arrow-origin" cx="180" cy="180" r="4"/>
      <text className="ufa-average-arrow-label" x={tip[0]+(labelAfter?12:-12)} y={labelY} textAnchor={labelAfter?'start':'end'}>{label}</text>
    </>}
  </svg>;
}
