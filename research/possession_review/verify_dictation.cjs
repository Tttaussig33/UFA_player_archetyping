const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('../vscode-preview/extension/vendor/typescript.js');

// Test the actual component with a simulated speech service; never open a microphone.
const file = path.resolve(__dirname,'../previews/UFA-possession-review.canvas.tsx');
const source = fs.readFileSync(file,'utf8').replace(/^import[^\n]+\n/,'').replace('export default function','function');
const compiled = ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.React,jsxFactory:'h'}}).outputText;
const states=[],saved=new Map(),timers=new Map(),instances=[]; let cursor=0,timerId=0,ownerPresent=true,observer;
class Recognition {
  start(){this.onstart?.();}
  stop(){this.stopRequested=true;}
  abort(){this.aborted=true;this.onend?.();}
  result(items){this.onresult?.({resultIndex:0,results:items.map(([text,isFinal])=>Object.assign([{transcript:text}],{isFinal}))});}
  constructor(){instances.push(this);}
}
const context={console,Date,Set,Map,String,Number,Math,JSON,encodeURIComponent,
  setTimeout:fn=>{timers.set(++timerId,fn);return timerId;},clearTimeout:id=>timers.delete(id),
  window:{SpeechRecognition:Recognition,addEventListener(){},removeEventListener(){}},
  document:{body:{},hidden:false,getElementById:()=>ownerPresent?{}:null,addEventListener(){},removeEventListener(){}},
  MutationObserver:class{constructor(fn){this.fn=fn;observer=this;}observe(){}disconnect(){this.disconnected=true;}},
  localStorage:{getItem:key=>saved.get(key)||null,setItem:(key,value)=>saved.set(key,value)},
  useState:initial=>{const i=cursor++;if(!(i in states))states[i]=typeof initial==='function'?initial():initial;return [states[i],next=>{states[i]=typeof next==='function'?next(states[i]):next;}];},
  useHostTheme:()=>({text:{primary:'text',secondary:'muted',link:'link'},stroke:{tertiary:'border'},accent:{primary:'accent'}}),
  h:(tag,props,...children)=>({tag,props:props||{},children:children.flat(Infinity)})};
for(const name of ['BarChart','H1','H2','Select','Stack','Table','Text'])context[name]=name;
vm.createContext(context);vm.runInContext(compiled,context);
const render=()=>{cursor=0;return context.PossessionReview();};
const all=node=>node&&typeof node==='object'?[node,...(node.children||[]).flatMap(all)]:[];
const words=node=>typeof node==='string'?node:(node?.children||[]).map(words).join('');
const button=(tree,name)=>all(tree).find(n=>n.tag==='button'&&words(n)===name);
const note=tree=>all(tree).find(n=>n.props.id==='ufa-review-note');
const heading=tree=>all(tree).filter(n=>n.tag==='H2').map(words);
const reviews=()=>JSON.parse(saved.get('ufa-opening-film-review-v1')||'{}');
const activeCase=tree=>all(tree).find(n=>n.props['data-review-id'])?.props['data-review-id'];
const select=(tree,option)=>all(tree).find(n=>n.tag==='Select'&&n.props.options?.some(x=>x.value===option));
const nav=(tree,name)=>all(tree).find(n=>n.tag==='button'&&n.props['aria-label']===name);
const exportReviews=tree=>JSON.parse(decodeURIComponent(all(tree).find(n=>n.props.download==='ufa-film-review-decisions.json').props.href.split(',')[1])).reviews;
let tree=render();
const baseline=exportReviews(tree),baselineById=new Map(baseline.map(r=>[r.caseId,r]));
assert.equal(baseline.length,52);assert.equal(activeCase(tree),'R100');
assert.equal(select(tree,'R100').props.options.length,12);
assert.equal(baselineById.get('R035').decision,'setup1');
assert.equal(baselineById.get('R077').decision,'attack1');
assert.equal(baselineById.get('R100').decision,'attack1');
assert(!button(tree,'Save & next').props.disabled);
// Clear the two answers in this memory-only test to exercise incomplete reviews.
// The archived review and real browser answers are never changed.
select(tree,'caught_pull').props.onChange('');tree=render();
select(tree,'setup1').props.onChange('');tree=render();
assert(button(tree,'Save & next').props.disabled);
// Both answers are required; a new edit preserves batch/provenance and the note.
select(tree,'caught_pull').props.onChange('caught_pull');tree=render();
assert(button(tree,'Save & next').props.disabled);
select(tree,'setup1').props.onChange('setup1');tree=render();
button(tree,'Save & next').props.onClick();tree=render();assert.equal(activeCase(tree),'R101');
const newReview=exportReviews(tree).find(r=>r.caseId==='R100');
assert.equal(newReview.reviewBatch,'new-games-review-20261112');
assert.equal(newReview.reviewRound,'new-games-review-20261112');
assert.equal(newReview.reviewMode,'manual');assert(!newReview.suggestion);
assert.equal(newReview.clip.start,645);assert.equal(newReview.clip.end,670);
for(const r of exportReviews(tree).filter(r=>r.caseId!=='R100'))assert.equal(JSON.stringify(r),JSON.stringify(baselineById.get(r.caseId)));
saved.clear();states.length=0;tree=render();
select(tree,'focus').props.onChange('focus');tree=render();assert.equal(activeCase(tree),'R039');
assert(!words(tree).includes('R039'));assert(!words(tree).includes('Agreed rule'));assert(!words(tree).includes('My suggestion:'));
assert(words(tree).includes('33:35'));assert(words(tree).includes('34:05'));
// Reclassifying start context keeps the existing note and attacking label.
select(tree,'turnover').props.onChange('turnover');tree=render();
assert.equal(note(tree).props.value,baselineById.get('R039').note);
assert.equal(exportReviews(tree).find(r=>r.caseId==='R039').decision,'attack1');
assert.equal(exportReviews(tree).find(r=>r.caseId==='R039').reviewRound,baselineById.get('R039').reviewRound);
note(tree).props.onChange({target:{value:'Existing note. Start at 33:35.'}});tree=render();
button(tree,'Dictate notes').props.onClick();tree=render();
assert(note(tree).props.readOnly);assert(button(tree,'Stop dictation'));
const mic=instances.at(-1);
mic.result([['First pass',false]]);tree=render();assert.equal(note(tree).props.value,'Existing note. Start at 33:35.');
mic.result([['First pass begins the attack.',true],['The next',false]]);tree=render();
mic.result([['First pass begins the attack.',true],['The next',false]]);tree=render();
assert.equal(note(tree).props.value,'Existing note. Start at 33:35. First pass begins the attack.');
nav(tree,'Next sequence').props.onClick();tree=render();
assert(mic.stopRequested);assert.equal(activeCase(tree),'R039');
mic.result([['First pass begins the attack.',true],['The next pass is a reset.',true]]);mic.onend();tree=render();
assert(!note(tree).props.readOnly);
assert.equal(note(tree).props.value,'Existing note. Start at 33:35. First pass begins the attack. The next pass is a reset.');
button(tree,'Save & next').props.onClick();tree=render();assert.equal(activeCase(tree),'R082');
const savedFirst=exportReviews(tree).find(r=>r.caseId==='R039');
assert.equal(savedFirst.context,'turnover');assert.equal(savedFirst.reviewRound,'opening-starts-followup-20261112');
assert.equal(savedFirst.clip.start,2015);assert.equal(savedFirst.clip.end,2045);
assert.equal(savedFirst.currentReviewExposesSuggestion,false);assert.equal(savedFirst.suggestion.decision,baselineById.get('R039').suggestion.decision);
const nextCaseNote=note(tree).props.value;
mic.result([['Late words must not reach another possession.',true]]);tree=render();assert.equal(note(tree).props.value,nextCaseNote);
assert.equal(Object.keys(reviews()).length,1);
button(tree,'Dictate notes').props.onClick();tree=render();const denied=instances.at(-1);
denied.onerror({error:'not-allowed'});tree=render();assert(button(tree,'Dictate notes'));assert(words(tree).includes('Microphone access was blocked'));
button(tree,'Dictate notes').props.onClick();tree=render();const detached=instances.at(-1);
ownerPresent=false;observer.fn();tree=render();assert(detached.aborted);assert(observer.disconnected);ownerPresent=true;
select(tree,'R035').props.onChange('R035');tree=render();
select(tree,'turnover').props.onChange('');tree=render();assert(button(tree,'Save & next').props.disabled);
select(tree,'turnover').props.onChange('unclear');tree=render();assert(!button(tree,'Save & next').props.disabled);
button(tree,'Save & next').props.onClick();tree=render();assert.equal(activeCase(tree),'R077');
// Test labels live only in the memory store. Untouched archived reviews remain exact.
for(const r of exportReviews(tree)) if(!['R039','R035'].includes(r.caseId))assert.equal(JSON.stringify(r),JSON.stringify(baselineById.get(r.caseId)));
context.window.SpeechRecognition=null;states.length=0;tree=render();assert(button(tree,'Dictate notes').props.disabled);assert(words(tree).includes('Dictation is unavailable'));
assert.equal(activeCase(tree),'R100');select(tree,'focus').props.onChange('focus');tree=render();
assert.equal(timers.size,0);
// Reload restores text and progress, and export retains the entire archive.
assert.equal(activeCase(tree),'R039');assert.equal(note(tree).props.value,savedFirst.note);
assert.equal(exportReviews(tree).length,52);assert.equal(exportReviews(tree).find(r=>r.caseId==='R039').reviewRound,savedFirst.reviewRound);
button(tree,'Restore archived answers').props.onClick();tree=render();
assert.equal(note(tree).props.value,baselineById.get('R039').note);assert.equal(exportReviews(tree).find(r=>r.caseId==='R039').context,baselineById.get('R039').context);
console.log('PASS: 52 archived reviews, required answers, separate batch provenance, archived user confirmations, saved-label preservation, two-question flow, corrected clip provenance, append-only dictation, no duplicate or cross-case speech, microphone failure, cleanup, reload/export and restoring archived answers. No real microphone or browser research labels were modified.');
