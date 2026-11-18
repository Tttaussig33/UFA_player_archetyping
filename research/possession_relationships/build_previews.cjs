const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {makeReport} = require('../vscode-preview/extension/portable.cjs');
const managed='/Users/teddytaussig/.cursor/projects/Users-teddytaussig-Desktop-Work-UFA-player-archetyping/canvases';
const preview=path.resolve(__dirname,'../previews');
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const receipt=[];
for(const name of ['UFA-hucking-and-scoring','UFA-throw-count-and-scoring']){
  const sourcePath=path.join(managed,name+'.canvas.tsx');
  const source=fs.readFileSync(sourcePath,'utf8');
  const html=makeReport(source,sourcePath);
  const copy=path.join(preview,name+'.canvas.tsx');
  const output=path.join(preview,'html',name+'.ufa.html');
  fs.writeFileSync(copy,source);
  fs.writeFileSync(output,html);
  receipt.push({sourcePath,sourceSha256:sha(source),copy,output,htmlSha256:sha(html)});
}
fs.writeFileSync(path.join(__dirname,'preview-receipt.json'),JSON.stringify({reports:receipt},null,2)+'\n');
console.log(JSON.stringify(receipt.map(({copy,output})=>({copy,output}))));
