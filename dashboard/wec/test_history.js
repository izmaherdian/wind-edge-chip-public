const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createSheetHistory } = require('./history_core');
const H = createSheetHistory(), now = Date.UTC(2026, 9, 22, 10, 0, 0);
const stamp = t => {
  const d = new Date(t + 7 * 3600000), p = v => String(v).padStart(2, '0');
  return `${d.getUTCDate()}/${d.getUTCMonth()+1}/${d.getUTCFullYear()}, ${p(d.getUTCHours())}.${p(d.getUTCMinutes())}.${p(d.getUTCSeconds())}`;
};
const row = (t, power = '20') => [stamp(t), '40', '0.5', power, '1500', '1.25', '4', '-114', '70', '24', '50', '0', 'Optimal'];
assert.equal(H.timestamp('1/10/2026, 00.00.00'), Date.UTC(2026, 8, 30, 17));
assert.equal(H.timestamp('31/11/2026, 12.00.00'), null);
assert.equal(H.timestamp('22/10/2026, 24.00.00'), null);
const data = H.normalize([row(now-120000,'10'), row(now-60000,'OFF'), row(now-120000,'30'), row(now-4*3600000), row(now+1000), []],now);
assert.equal(data.rows.length,2); assert.equal(data.duplicates,1);
assert.equal(data.rows[0].power,30); assert.equal(data.rows[1].power,null);
assert.equal(H.normalize([row(now-1000,'0')],now).rows[0].power,0);
assert.equal(data.rows[0].winddirdeg,-114);
assert.equal(H.normalize([row(now-1000,'')],now).rows[0].power,null);
assert.equal(H.range(326586),'Sheet1!A311587:M326586');
assert.equal(H.range(0),null);
assert.equal(H.minutes(data.rows).length,2);

const core = fs.readFileSync(path.join(__dirname,'engine_core.js'),'utf8').replace(/^if \(typeof module.*$/m,'');
const bundle = JSON.parse(fs.readFileSync(path.join(__dirname,'model_bundle.json')));
const engine = new Function('msg','context','flow','node',core+'\nconst BUNDLE='+JSON.stringify(bundle)+';\n'+fs.readFileSync(path.join(__dirname,'engine_node.js'),'utf8'));
const realNow=Date.now;Date.now=()=>now;
const state={};const context={get:k=>state[k],set:(k,v)=>state[k]=v};const flow={get:()=>undefined,set:()=>{}};const node={status:()=>{}};
const historyRows=[];
for(let m=1;m<=120;m++)if(m!==75) historyRows.push(...H.normalize([row(now-m*60000)],now).rows);
assert.equal(engine({topic:'wec/history',payload:{source:'google-sheet',rows:historyRows}},context,flow,node),null);
const st=state.st;assert.equal(st.hist.size,119);assert.equal(st.hist.has(now/60000-75),false);
assert.equal(st.lastData,undefined);assert.equal(st.soc,bundle.battery.soc_awal);assert.deepEqual(st.evals,[]);assert.equal(st.last,null);
const k=now/60000-10;st.hist.set(k,{p:99});st.sheetHistoryMinutes.delete(k);
engine({topic:'wec/history',payload:{source:'google-sheet',rows:historyRows}},context,flow,node);
assert.equal(st.hist.get(k).p,99); // existing live measurement wins
const historical=now/60000-20;
engine({topic:'WEC/state',payload:{v:1,hist:[[historical,1,77,1,40,0.5,4,4,0,1,70,24]]}},context,flow,node);
assert.equal(st.hist.get(historical).p,77); // retained snapshot wins over Sheet
assert.equal(st.sheetHistoryMinutes.has(historical),false);
Date.now=realNow;
console.log('History: WIB parsing, OFF/missing, sorting/dedup, bounded read and ML seed priority passed.');

const manager = new Function('msg','context','node',fs.readFileSync(path.join(__dirname,'history_core.js'),'utf8').replace(/^if \(typeof module.*$/m,'')+'\nconst HISTORY_SEED_ROW=326586;\n'+fs.readFileSync(path.join(__dirname,'history_node.js'),'utf8'));
const cache={};const ctx={get:k=>cache[k],set:(k,v)=>cache[k]=v};Date.now=()=>now;
const first=manager({topic:'wec/history/request'},ctx,node);assert.equal(first[0].cells,'Sheet1!A311587:M326586');
assert.equal(manager({topic:'wec/history/request'},ctx,node)[0],null); // coalesced while in flight
const response=manager({...first[0],payload:[row(now-60000)]},ctx,node);
assert.equal(response[1].topic,'wec/history/chart');assert.equal(response[2].topic,'wec/history');
assert.equal(manager({topic:'wec/history/request'},ctx,node)[0],null); // cache hit
const ack=manager({payload:{updatedRange:'Sheet1!A326600:M326600'}},ctx,node);
assert.equal(JSON.parse(ack[3].payload).row,326600);assert.equal(ack[3].retain,true);
assert.equal(cache.history3h.cursor,326600);
Date.now=realNow;
console.log('History manager: cache, bounded cursor and read-only append acknowledgement passed.');
