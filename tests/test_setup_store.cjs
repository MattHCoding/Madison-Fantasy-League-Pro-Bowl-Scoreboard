const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const root = path.join(__dirname,'..');
const config = JSON.parse(fs.readFileSync(path.join(root,'data/matchup.json')));
const snapshot = JSON.parse(fs.readFileSync(path.join(root,'data/rosters-2026.json')));
function store(fetch) {
  const ctx = vm.createContext({fetch,TextEncoder,TextDecoder,Uint8Array,btoa,atob});
  vm.runInContext(fs.readFileSync(path.join(root,'setup-store.js'),'utf8')+';globalThis.store=setupStore;',ctx);
  return ctx.store;
}
const file = value => ({ok:true,json:async()=>({sha:'current-version',content:Buffer.from(JSON.stringify(value)).toString('base64')})});
test('submitted selections persist as UTF-8 config with version protection; no token in config',async()=>{
  const draft=structuredClone(config);draft.week=4;draft.sides.west.name='Nick’s team 🏈';
  const calls=[];
  const api=store(async(url,options)=>{calls.push({url,options});return options.method==='PUT'?{ok:true,json:async()=>({commit:{sha:'saved'}})}:file(config);});
  api.validate(draft,snapshot);
  await api.save(draft,config,'test-token');
  assert.equal(calls.length,2);
  const body=JSON.parse(calls[1].options.body);
  assert.equal(body.sha,'current-version');assert.equal(body.branch,'main');
  assert.deepEqual(JSON.parse(Buffer.from(body.content,'base64').toString('utf8')),draft);
  assert.equal(calls[1].options.headers.Authorization,'Bearer test-token');
  assert.ok(!Buffer.from(body.content,'base64').toString('utf8').includes('test-token'));
});
test('a newer shared configuration blocks write',async()=>{
  let writes=0;const changed=structuredClone(config);changed.week=5;
  const api=store(async(url,options)=>{if(options.method)writes++;return file(changed);});
  await assert.rejects(api.save(config,config,'token'),/changed since/);assert.equal(writes,0);
});
test('missing authentication performs no requests',async()=>{
  const api=store(()=>{throw Error('unexpected request');});
  await assert.rejects(api.save(config,config,''),/Connect GitHub/);
});
test('permission, racing write, and network failures do not report success',async()=>{
  for(const code of [401,403,404,409,422]) {
    const api=store(async(url,options)=>options.method?{ok:false,status:code}:file(config));
    await assert.rejects(api.save(config,config,'token'),/token|access|changed|could not save/);
  }
  const api=store(async(url,options)=>{if(options.method)throw Error('network');return file(config);});
  await assert.rejects(api.save(config,config,'token'),/Could not confirm/);
});
test('invalid week, duplicate players, wrong position, rejected; manual ownership is unnecessary',()=>{
  const api=store(()=>{});api.validate(config,snapshot);
  let draft=structuredClone(config);draft.week=19;assert.throws(()=>api.validate(draft,snapshot),/week/);
  draft=structuredClone(config);draft.sides.west.players[2].id=draft.sides.west.players[1].id;assert.throws(()=>api.validate(draft,snapshot),/once/);
  draft=structuredClone(config);draft.sides.west.players[0].id=draft.sides.west.players[1].id;assert.throws(()=>api.validate(draft,snapshot),/eligible/);
  draft=structuredClone(config);draft.week=4;draft.enabled=true;api.validate(draft,snapshot);
  draft.sides.west.players[0].id=null;assert.throws(()=>api.validate(draft,snapshot),/every player/);
});
