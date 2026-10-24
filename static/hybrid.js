(function(){
  const left=document.querySelector('#screen-desk .topbar-left');
  const bar=document.querySelector('#screen-desk .topbar');
  if(!left||!bar)return;
  const m=document.createElement('button');m.type='button';m.className='hy-menu';m.innerHTML='Menu <span class="caret">&#9662;</span>';
  m.onclick=e=>{e.stopPropagation();document.body.classList.toggle('hy-rail-open')};
  left.insertBefore(m,left.children[1]||null);
  // Center cluster: Chiedi ad H-ELP + Sondaggio (prefer markup in index.html)
  let center=document.getElementById('topbar-center');
  if(!center){
    center=document.createElement('div');
    center.id='topbar-center';
    center.className='topbar-center';
    center.setAttribute('aria-label','Azioni rapide');
    const a=document.createElement('button');a.type='button';a.className='hy-ask';a.textContent='Chiedi ad H-ELP';a.dataset.action='open-ai';a.setAttribute('aria-label','Chiedi ad H-ELP');a.title='Chiedi ad H-ELP';
    const s=document.createElement('button');s.type='button';s.id='survey-top-btn';s.className='survey-top-btn';s.textContent='Sondaggio';s.dataset.action='open-survey';s.setAttribute('aria-label','Sondaggio interessi');s.title='Sondaggio veloce · interessi';
    center.appendChild(a);center.appendChild(s);
    const right=bar.querySelector('.topbar-right');
    if(right) bar.insertBefore(center,right); else bar.appendChild(center);
  } else {
    const ask=center.querySelector('.hy-ask');
    if(ask){ask.textContent='Chiedi ad H-ELP';ask.setAttribute('aria-label','Chiedi ad H-ELP');ask.title='Chiedi ad H-ELP';}
  }
  // Drop any legacy absolute hy-ask siblings outside the center cluster
  bar.querySelectorAll(':scope > .hy-ask').forEach(el=>el.remove());
  document.addEventListener('click',e=>{const r=document.querySelector('.workspace .rail');
    if(document.body.classList.contains('hy-rail-open')&&r&&(!r.contains(e.target)||e.target.closest('[data-action="section"]')))document.body.classList.remove('hy-rail-open')});
  const ov=document.getElementById('ai-overlay');
  if(ov)new MutationObserver(()=>{if(ov.hidden){ov.classList.remove('hy-open')}else{requestAnimationFrame(()=>ov.classList.add('hy-open'))}}).observe(ov,{attributes:true,attributeFilter:['hidden']});
  if(ov)ov.addEventListener('click',e=>{if(e.target===ov&&typeof openAiOverlay==='function')openAiOverlay(false)});
})();