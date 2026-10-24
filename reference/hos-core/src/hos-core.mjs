/** H-OS frontend integration core. No LLM, authentication, backend or real registration is implied. */
export const HOS_NAME = 'H-OS';
const unique = (values) => [...new Set((values ?? []).filter(x => typeof x === 'string'))];
const dateMs = (value) => Date.parse(value);

/** Adapt the two EXISTING dataset formats; do not change their event IDs. */
export function normalizeDataset(raw) {
  if (Array.isArray(raw)) {
    return raw.map(e => {
      if (!e.id || !e.source_id || !Array.isArray(e.tags) || !e.start || !e.end) throw new Error(`Invalid new event record: ${e.id ?? 'unknown'}`);
      return {
        id:e.id, source_id:e.source_id, title:e.title, description:e.description,
        tags:unique(e.tags), location:typeof e.location === 'object' ? e.location.building : e.location,
        start:e.start,end:e.end,capacity:e.capacity,
        registered_count:null, availability:null, status:'scheduled',
        registration_mode:'unknown', registration_deadline:null,
        club_id:null, document_ids:[], synthetic:true, raw:e
      };
    });
  }
  if (raw && Array.isArray(raw.events) && Array.isArray(raw.interests)) {
    const names = new Map(raw.interests.map(i => [i.id,i.label]));
    return raw.events.map(e => {
      const remaining = Number.isInteger(e.registered_count) ? Math.max(0,e.capacity-e.registered_count) : null;
      return {
        id:e.id,source_id:e.id,title:e.title,description:e.description,
        tags:e.interest_ids.map(id => names.get(id) ?? id),tagIds:unique(e.interest_ids),
        location:e.location,start:e.start,end:e.end,capacity:e.capacity,
        registered_count:e.registered_count, availability:remaining, status:e.status,
        registration_mode:e.registration_mode,registration_deadline:e.registration_deadline,
        club_id:e.club_id,document_ids:e.document_ids ?? [],synthetic:true,raw:e
      };
    });
  }
  throw new Error('Unsupported H-OS dataset format');
}

export function normalizeStudent(raw, legacyData=null) {
  if (Array.isArray(raw.preferences)) {
    return {id:raw.id,name:raw.name,preferences:unique(raw.preferences),disliked:[],email:null};
  }
  if (Array.isArray(raw.liked_interest_ids) && legacyData) {
    const labels=new Map(legacyData.interests.map(i=>[i.id,i.label]));
    return {id:raw.id,name:raw.name,preferences:unique(raw.liked_interest_ids.map(id=>labels.get(id)??id)),disliked:unique((raw.disliked_interest_ids??[]).map(id=>labels.get(id)??id)),email:null};
  }
  throw new Error('Unsupported H-OS student schema');
}

/** Score is a coverage percentage, NOT a probability. For no preferences we rank by chronological start without personalization. */
export function recommendEvents(student,events,{now=new Date().toISOString(),limit=5,excludeRegistered=[]}={}) {
  const liked=unique(student.preferences);
  const disliked=new Set(student.disliked??[]);
  const excluded=new Set(excludeRegistered);
  const time=dateMs(now);
  return events.filter(e=>e.status!=='cancelled' && e.status!=='completed' && dateMs(e.start)>time && !excluded.has(e.id))
    .map(e=>{
      const shared=liked.filter(t=>e.tags.includes(t));
      const avoided=e.tags.filter(t=>disliked.has(t));
      // A disfavored event is not promoted even when one tag overlaps.
      const score=liked.length ? Math.max(0,Math.round(100*(shared.length/liked.length)-25*avoided.length)) : null;
      return {event:e,score,shared_tags:shared,excluded_tags:avoided,source_id:e.source_id,
        reason:liked.length ? (shared.length ? `Interessi condivisi: ${shared.join(', ')}.` : 'Nessun interesse condiviso.') : 'Prossimo evento in calendario: preferenze non impostate.',
        personalized:liked.length>0};
    })
    .filter(r=> !liked.length || (r.score>0 && r.shared_tags.length>0))
    .sort((a,b)=> (b.score??0)-(a.score??0) || dateMs(a.event.start)-dateMs(b.event.start) || a.event.id.localeCompare(b.event.id))
    .slice(0,limit);
}

export function eventRegistrationStatus(event,{now=new Date().toISOString()}={}) {
  if (event.status==='cancelled') return {allowed:false,reason:'Evento annullato'};
  if (event.status==='completed' || dateMs(event.start)<=dateMs(now)) return {allowed:false,reason:'Evento concluso o iniziato'};
  if (event.registration_deadline && dateMs(event.registration_deadline)<dateMs(now)) return {allowed:false,reason:'Iscrizioni chiuse'};
  if (event.registration_mode==='closed') return {allowed:false,reason:'Iscrizioni chiuse'};
  if (event.registration_mode==='waitlist' || event.availability===0) return {allowed:false,reason:'Solo lista d’attesa: non supportata da questo modulo'};
  return {allowed:true,reason:event.availability===null ? 'Posti disponibili non verificabili: capienza totale soltanto' : `${event.availability} posti dichiarati nel dataset sintetico`};
}

/** Deterministic assistant: answers only using matching dataset entries; no model is connected. */
export function answerEventQuestion(query,student,events,{now=new Date().toISOString()}={}) {
  const q=String(query??'').toLocaleLowerCase('it-IT').trim();
  if (!q) return {kind:'unknown',text:'Scrivi una domanda sugli eventi del dataset.',source_ids:[],recommendations:[]};
  const candidates=recommendEvents(student,events,{now,limit:5});
  const match=events.find(e => q.includes(e.title.toLocaleLowerCase('it-IT')) || q.includes(e.id.toLowerCase()));
  if (match) {
    return {kind:'detail',text:`${match.title}: ${match.description} Luogo: ${match.location}. Inizio: ${match.start}. Fonte: ${match.source_id}.`,source_ids:[match.source_id],recommendations:[],event_id:match.id};
  }
  if (/consigli|suggeri|raccomand|interess|evento|attivit|partecip|iscriv|registr|recommend|suggest|event|activit|join|sign\s*up|interest|upcoming|what(?:'s| is) on/.test(q)) {
    if(!candidates.length) return {kind:'recommendations',text:'Non trovo eventi futuri compatibili nel dataset. Prova a modificare le preferenze.',source_ids:[],recommendations:[]};
    const r=candidates[0];
    return {kind:'recommendations',text:`Ti consiglio «${r.event.title}». ${r.reason} Luogo: ${r.event.location}; inizio: ${r.event.start}. Fonte: ${r.source_id}. Per iscriverti devi approvare una proposta: nessuna azione è stata eseguita.`,source_ids:[r.source_id],recommendations:candidates.map(x=>({event_id:x.event.id,source_id:x.source_id,score:x.score,shared_tags:x.shared_tags,reason:x.reason})),event_id:r.event.id};
  }
  return {kind:'unknown',text:'Non posso verificarlo con i dati sugli eventi disponibili. Nessuna informazione inventata.',source_ids:[],recommendations:[]};
}

/** Explicit-only DEMO adapter: local browser interaction, never described as a real booking. */
export class InMemoryDemoRegistrationGateway {
  constructor(){this.records=[];}
  async register({student_id,event_id,approval_id,idempotency_key}) {
    const existing=this.records.find(r=>r.idempotency_key===idempotency_key);
    if(existing) return existing;
    const record={registration_id:`demo-${this.records.length+1}`,student_id,event_id,approval_id,idempotency_key,status:'simulated',mode:'demo',created_at:new Date().toISOString()};
    this.records.push(record);
    return record;
  }
}

/** Backend HTTP adapter, disabled until teammate supplies a verified API. */
export class HttpRegistrationGateway {
  constructor({baseUrl,fetcher=globalThis.fetch}={}) {
    if(!baseUrl || typeof fetcher!=='function') throw new Error('Backend URL and fetch required');
    this.baseUrl=baseUrl.replace(/\/$/,'');this.fetcher=fetcher;
  }
  async register(payload){
    const response=await this.fetcher(`${this.baseUrl}/registrations`,{
      method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':payload.idempotency_key},credentials:'include',body:JSON.stringify(payload)
    });
    if(!response.ok) throw new Error(`Registration API rejected request: ${response.status}`);
    const data=await response.json();
    if(!data.registration_id || !['confirmed','waitlisted'].includes(data.status) || data.event_id!==payload.event_id || data.student_id!==payload.student_id) throw new Error('Invalid registration API response');
    return {...data,mode:'backend'};
  }
}

/** Approval is a required step before gateway invocation. The backend must independently enforce authorization/capacity. */
export class HOSSession {
  constructor({student,events,gateway,now=()=>new Date().toISOString()}) {
    if(!student?.id || !gateway?.register) throw new Error('Student and registration gateway required');
    this.student={...student,preferences:unique(student.preferences)};
    this.events=events;this.gateway=gateway;this.now=now;
    this.pending=null;this.agenda=[];this.sequence=0;
  }
  setPreferences(preferences,{disliked=this.student.disliked??[]}={}){this.student.preferences=unique(preferences);this.student.disliked=unique(disliked).filter(t=>!this.student.preferences.includes(t));this.pending=null;}
  recommendations(limit=5){return recommendEvents(this.student,this.events,{now:this.now(),limit,excludeRegistered:this.agenda.map(x=>x.event_id)});}
  ask(text){return answerEventQuestion(text,this.student,this.events,{now:this.now()});}
  propose(eventId){
    const event=this.events.find(e=>e.id===eventId);
    if(!event) throw new Error('Unknown event ID');
    if(this.agenda.some(r=>r.event_id===eventId)) throw new Error('Already registered in agenda');
    const state=eventRegistrationStatus(event,{now:this.now()});
    if(!state.allowed) throw new Error(state.reason);
    const id=`client-proposal-${++this.sequence}`;
    this.pending={approval_id:id,student_id:this.student.id,event_id:event.id,event_title:event.title,source_id:event.source_id,warning:state.reason};
    return this.pending;
  }
  reject(){this.pending=null;}
  async approve(approvalId){
    const p=this.pending;
    if(!p || p.approval_id!==approvalId) throw new Error('No matching pending approval');
    if(this.agenda.some(r=>r.event_id===p.event_id)) throw new Error('Already in agenda');
    const event=this.events.find(e=>e.id===p.event_id);
    if(!event || !eventRegistrationStatus(event,{now:this.now()}).allowed) throw new Error('Event no longer eligible');
    // Prevent double-clicks and concurrent calls. Backend MUST enforce idempotency.
    this.pending=null;
    const key=`${this.student.id}:${p.event_id}:${p.approval_id}`;
    try {
      const record=await this.gateway.register({student_id:this.student.id,event_id:p.event_id,approval_id:p.approval_id,idempotency_key:key});
      if(!record?.registration_id || record.event_id!==p.event_id || record.student_id!==this.student.id || !['confirmed','waitlisted','simulated'].includes(record.status)) throw new Error('Gateway returned an invalid registration');
      this.agenda.push({...record,event_title:event.title,source_id:event.source_id,start:event.start,location:event.location});
      return this.agenda[this.agenda.length-1];
    } catch(error){this.pending=p;throw error;}
  }
}
