// Read-only preparation: reuse the exact huck, zone and sequence rules in the app.
import fs from 'node:fs';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {zoneFor, ZONES} from '../src/content/dashboard/model.js';
import {passGeometry} from '../src/content/dashboard/connections-model.js';
import {precedingPasses, priorPassDirection} from '../src/content/dashboard/deep-thrower-model.js';

const source=fileURLToPath(new URL('../src/data.json',import.meta.url));
const bytes=fs.readFileSync(source), data=JSON.parse(bytes);
const events=data.queries.events.rows.filter(e=>e.phase==='Regular season');
const links=precedingPasses(events);
const rows=events.filter(e=>!e.stall&&e.thrower&&e.thrower!=='unknown').map(e=>{
  const geometry=passGeometry(e);
  return {id:e.id,game:e.game,date:e.date,player:e.thrower,team:e.team,
    complete:Number(e.complete),zone:zoneFor(e.tx,e.ty),huck:geometry.huck,
    distance:geometry.distance,gain:geometry.gain,cp:e.cp,cpoe:e.cpoe,
    drop:e.drop,setup:priorPassDirection(links.get(e.id)),tx:e.tx,ty:e.ty,rx:e.rx,ry:e.ry};
});
process.stdout.write(JSON.stringify({rows,players:data.queries.players.rows,zones:ZONES,
  source:{path:'src/data.json',sha256:crypto.createHash('sha256').update(bytes).digest('hex'),
    eventRowsSha256:crypto.createHash('sha256').update(JSON.stringify(data.queries.events.rows)).digest('hex'),
    exportedAt:data.queries.events.source.executedAt,
    rawEvents:data.queries.events.rows.length,regularEvents:events.length,
    tables:data.queries.events.source.tables,caveats:data.queries.events.source.caveats}}));
