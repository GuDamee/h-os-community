import {normalizeDataset,normalizeStudent,HOSSession,InMemoryDemoRegistrationGateway,eventRegistrationStatus} from '../src/hos-core.mjs';
const el=id=>document.getElementById(id);
const escape=(s)=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const load=async(name)=>{const r=await fetch(`../data/${name}`);if(!r.ok)throw Error(`Could not load ${name}`);return r.json()};
const all=await Promise.all([load('users.json'),load('events.json'),load('tags.json'),load('legacy-campus-dataset.json')]);
const [users,events80,tags,legacy]=all;
const store={source:'80',events:normalizeDataset(events80),tags,students:users,session:null,selectedTags:new Set()};
function makeSession(user){store.session=new HOSSession({student:normalizeStudent(user,store.source==='17'?legacy:null),events:store.events,gateway:new InMemoryDemoRegistrationGateway()});store.selectedTags=new Set(store.session.student.preferences);el('mail').value=`${store.session.student.id}@students.example`;renderTags();renderAll();}
function selectDataset(source){store.source=source;store.events=normalizeDataset(source==='17'?legacy:events80);store.tags=source==='17'?legacy.interests.map(i=>i.label):tags;store.students=source==='17'?legacy.profiles:users;el('student').innerHTML=store.students.map((s,i)=>`<option value="${i}">${escape(s.name)} — ${escape(s.id)}</option>`).join('');makeSession(store.students[0]);}
function renderTags(){el('tag-list').innerHTML=store.tags.map(t=>`<button type="button" class="tag ${store.selectedTags.has(t)?'active':''}" data-tag="${escape(t)}" aria-pressed="${store.selectedTags.has(t)}">${escape(t)}</button>`).join('');}
function eventCard(event,rec=null){
 const status=eventRegistrationStatus(event);const score=rec&&rec.score!==null?`<span class="score">Compatibility: ${rec.score}% · ${escape(rec.reason)}</span><br>`:'';
 const availability=event.availability===null?'Places remaining: unknown':`Places remaining (synthetic): ${event.availability}`;
 return `<div class="event"><h3>${escape(event.title)}</h3>${score}<div class="evmeta">${escape(event.start.replace('T',' ').slice(0,16))} · ${escape(event.location)} · ${escape(event.source_id)}</div><p class="muted">${escape(event.description)}</p><p class="muted">${escape(availability)} · ${escape(status.reason)}</p><button type="button" class="outline" data-propose="${escape(event.id)}" ${status.allowed?'':'disabled'}>Propose registration</button></div>`;
}
function renderAll(){const s=store.session;const rec=s.recommendations(4);el('recommended-list').innerHTML=rec.length?rec.map(x=>eventCard(x.event,x)).join(''):'<p>No matching future events. Change your interests.</p>';renderEvents();renderAgenda();}
function renderEvents(){const query=el('filter').value.trim().toLocaleLowerCase('it-IT');const selected=store.events.filter(e=>`${e.title} ${e.description} ${e.tags.join(' ')} ${e.location}`.toLocaleLowerCase('it-IT').includes(query)).slice(0,16);el('event-counter').textContent=`Showing ${selected.length} of ${store.events.length} synthetic records (first 16 matches)`;el('event-list').innerHTML=selected.map(e=>eventCard(e)).join('');}
function renderAgenda(){el('agenda-list').innerHTML=store.session.agenda.length?store.session.agenda.map(x=>`<div class="event"><strong>${escape(x.event_title)}</strong><p class="muted">${escape(x.start)} · ${escape(x.location)} · Source: ${escape(x.source_id)}</p><span class="pill" style="color:#80562e">${x.mode==='demo'?'SIMULATED REGISTRATION':'BACKEND REGISTRATION'}</span></div>`).join(''):'<p class="muted">No registrations yet.</p>';}
function propose(id){try{const p=store.session.propose(id);el('approval-detail').innerHTML=`<p><strong>${escape(p.event_title)}</strong></p><p class="muted">Student: ${escape(p.student_id)} · Event: ${escape(p.event_id)} · Source: ${escape(p.source_id)}</p><div class="notice">${escape(p.warning)}</div>`;el('approval-status').textContent='';el('approval').showModal();}catch(e){alert(e.message);}}
function closeApproval(){store.session.reject();el('approval').close();}
el('tag-list').addEventListener('click',e=>{const b=e.target.closest('[data-tag]');if(!b)return;const tag=b.dataset.tag;store.selectedTags.has(tag)?store.selectedTags.delete(tag):store.selectedTags.add(tag);renderTags();});
el('save-preferences').addEventListener('click',()=>{store.session.setPreferences([...store.selectedTags]);el('onboarding-status').textContent=`Saved ${store.selectedTags.size} selected preferences. Recomputed recommendations.`;renderAll();});
el('student').addEventListener('change',()=>makeSession(store.students[Number(el('student').value)]));
el('dataset').addEventListener('change',()=>{el('filter').value='';selectDataset(el('dataset').value);});
el('filter').addEventListener('input',renderEvents);
document.addEventListener('click',e=>{const b=e.target.closest('[data-propose]');if(b)propose(b.dataset.propose);});
el('ask-sample').addEventListener('click',()=>{el('question').value='Consigliami un evento';el('ask').click();});
el('ask').addEventListener('click',()=>{const a=store.session.ask(el('question').value);el('answer').textContent=a.text;el('assistant-action').innerHTML=a.event_id?`<p><button data-propose="${escape(a.event_id)}">Propose registration for ${escape(a.event_id)}</button></p>`:'';});
el('cancel').addEventListener('click',closeApproval);
el('approval').addEventListener('cancel',e=>{e.preventDefault();closeApproval();});
el('confirm').addEventListener('click',async()=>{const pending=store.session.pending;if(!pending)return;el('confirm').disabled=true;try{const result=await store.session.approve(pending.approval_id);el('approval').close();renderAll();el('agenda').scrollIntoView({behavior:'smooth'});el('answer').textContent=`Simulated registration ${result.registration_id} was added to My Agenda. No actual campus booking was performed.`;}catch(e){el('approval-status').textContent=e.message;}finally{el('confirm').disabled=false;}});
selectDataset('80');
