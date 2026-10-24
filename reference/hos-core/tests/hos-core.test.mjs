import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {normalizeDataset,normalizeStudent,recommendEvents,answerEventQuestion,HOSSession,InMemoryDemoRegistrationGateway,HttpRegistrationGateway,eventRegistrationStatus} from '../src/hos-core.mjs';
const load=(name)=>JSON.parse(readFileSync(new URL('../data/'+name,import.meta.url)));
const users=load('users.json'),rawEvents=load('events.json'),tags=load('tags.json'),legacy=load('legacy-campus-dataset.json');
const events=normalizeDataset(rawEvents),legacyEvents=normalizeDataset(legacy);
const now='2026-10-24T15:00:00+02:00';

test('all 80 source IDs, references, and tags match original data',()=>{
  assert.equal(events.length,80);assert.equal(new Set(events.map(e=>e.id)).size,80);
  assert.equal(users.length,40);assert.equal(tags.length,25);
  for(const e of events){assert.equal(e.source_id,e.id);assert.ok(e.tags.every(tag=>tags.includes(tag)));assert.ok(Date.parse(e.end)>Date.parse(e.start));}
});
test('legacy 17-event adapter retains event IDs, clubs, occupancy, closures',()=>{
  assert.equal(legacyEvents.length,17);
  assert.equal(legacyEvents.find(e=>e.id==='E009').availability,0);
  assert.equal(legacyEvents.find(e=>e.id==='E014').status,'cancelled');
  assert.equal(legacyEvents.find(e=>e.id==='E001').document_ids[0],'D001');
});
test('preferences genuinely reorder recommendations',()=>{
  const student={id:'s',preferences:['AI']};
  const a=recommendEvents(student,events,{now,limit:10});
  assert.ok(a.length>0);assert.ok(a.every(r=>r.shared_tags.includes('AI')));
  const b=recommendEvents({...student,preferences:['musica']},events,{now,limit:10});
  assert.ok(b.length>0);assert.ok(b.every(r=>r.shared_tags.includes('musica')));
  assert.notDeepEqual(a.map(r=>r.event.id),b.map(r=>r.event.id));
});
test('empty preferences are clearly not personalized',()=>{
  const result=recommendEvents({id:'u',preferences:[]},events,{now,limit:3});
  assert.equal(result.length,3); assert.equal(result[0].score,null); assert.equal(result[0].personalized,false);
});
test('synthetic 80-event dataset does not invent vacancy counts',()=>{
  assert.equal(events[0].availability,null);
  assert.equal(events[0].registered_count,null);
  const status=eventRegistrationStatus(events[0],{now});
  assert.equal(status.allowed,true);assert.match(status.reason,/non verificabili/);
});
test('cancelled and full events cannot be proposed',()=>{
  assert.equal(eventRegistrationStatus(legacyEvents.find(e=>e.id==='E009'),{now}).allowed,false);
  assert.equal(eventRegistrationStatus(legacyEvents.find(e=>e.id==='E014'),{now}).allowed,false);
  assert.ok(!recommendEvents(normalizeStudent(legacy.profiles[0],legacy),legacyEvents,{now,limit:17}).some(r=>r.event.id==='E014'));
});
test('assistant never makes up an unrelated claim',()=>{
  const student=normalizeStudent(users[0]);
  const q=answerEventQuestion('Il campus offre una navetta gratuita?',student,events,{now});
  assert.equal(q.kind,'unknown'); assert.deepEqual(q.source_ids,[]);
  const a=answerEventQuestion('Consigliami un evento',student,events,{now});
  assert.ok(a.source_ids.every(id=>events.some(e=>e.source_id===id)));
  assert.match(a.text,/Fonte: evt-/);
});
test('proposal and reject do not register; approval updates agenda',async()=>{
  const gateway=new InMemoryDemoRegistrationGateway();
  const s=new HOSSession({student:normalizeStudent(users[0]),events,gateway,now:()=>now});
  const id=s.recommendations(1)[0].event.id;
  let proposal=s.propose(id);
  assert.equal(s.agenda.length,0);assert.equal(gateway.records.length,0);
  s.reject();assert.equal(gateway.records.length,0);
  proposal=s.propose(id);assert.equal(gateway.records.length,0);
  const record=await s.approve(proposal.approval_id);
  assert.equal(record.mode,'demo');assert.equal(record.status,'simulated');
  assert.equal(s.agenda[0].event_id,id);assert.equal(gateway.records.length,1);
  await assert.rejects(()=>s.approve(proposal.approval_id),/No matching/);
  assert.throws(()=>s.propose(id),/Already registered/);
});
test('preferences update scores in the same active session',()=>{
  const s=new HOSSession({student:{id:'u',name:'Test',preferences:['AI']},events,gateway:new InMemoryDemoRegistrationGateway(),now:()=>now});
  assert.ok(s.recommendations(5).every(r=>r.shared_tags.includes('AI')));
  s.setPreferences(['basket']);
  assert.ok(s.recommendations(5).every(r=>r.shared_tags.includes('basket')));
});
test('backend adapter sends explicit approved registration contract',async()=>{
  let called=0,received;
  const fetcher=async(url,opts)=>{called++;received={url,opts};return {ok:true,json:async()=>({registration_id:'reg-1',student_id:'usr-001',event_id:'evt-001',status:'confirmed'})};};
  const gateway=new HttpRegistrationGateway({baseUrl:'https://example.invalid/api',fetcher});
  const session=new HOSSession({student:normalizeStudent(users[0]),events,gateway,now:()=>now});
  const proposal=session.propose('evt-001');assert.equal(called,0);
  await session.approve(proposal.approval_id);assert.equal(called,1);
  assert.equal(received.url,'https://example.invalid/api/registrations');
  assert.equal(JSON.parse(received.opts.body).approval_id,proposal.approval_id);
  assert.equal(session.agenda[0].status,'confirmed');
});
test('failed backend does not create agenda entry, restores proposal',async()=>{
  const gateway={async register(){throw new Error('API unavailable')}};
  const s=new HOSSession({student:normalizeStudent(users[0]),events,gateway,now:()=>now});
  const p=s.propose('evt-001');await assert.rejects(()=>s.approve(p.approval_id),/API unavailable/);
  assert.equal(s.agenda.length,0);assert.equal(s.pending.approval_id,p.approval_id);
});
