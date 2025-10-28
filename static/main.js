const $ = (q) => document.querySelector(q);
const $$ = (q) => Array.from(document.querySelectorAll(q));
function h(tag, attrs={}, ...children){
  const el = document.createElement(tag);
  for(const [k,v] of Object.entries(attrs)){
    if(k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if(v!==undefined && v!==null) el.setAttribute(k, v);
  }
  for(const c of children){
    if(Array.isArray(c)) c.forEach(x => el.append(x));
    else if(c instanceof Node) el.append(c);
    else if(c!==undefined && c!==null) el.append(String(c));
  }
  return el;
}
async function api(path, opts={}){
  const res = await fetch(path, {headers: { 'Content-Type': 'application/json' }, ...opts});
  if(!res.ok) throw new Error(`API ${path} -> ${res.status}`);
  return res.json();
}
function show(view){
  $$('.nav-btn').forEach(btn=> btn.classList.toggle('active', btn.dataset.view===view));
  $$('.view').forEach(v=> v.classList.remove('visible'));
  document.querySelector(`#view-${view}`).classList.add('visible');
}
$$('.nav-btn').forEach(btn=> btn.addEventListener('click', ()=> show(btn.dataset.view)));
async function loadDashboard(){
  const data = await api('/api/dashboard');
  const tl = document.querySelector('#taskLoad'); tl.innerHTML = '';
  for(const [k,v] of Object.entries(data.task_load)){ tl.append(h('span', {class:'badge'}, `${k}: ${v}`), ' '); }
  const due = document.querySelector('#dueList'); due.innerHTML='';
  data.due_this_week.forEach(t=> due.append(h('li',{}, h('span',{}, t.title), h('span',{class:'badge'}, t.due_date))));
  const issues = document.querySelector('#issueList'); issues.innerHTML='';
  data.open_issues.forEach(t=> issues.append(h('li',{}, h('span',{}, t.title), h('span',{class:'badge'}, t.priority))));
  const risks = document.querySelector('#riskList'); risks.innerHTML='';
  data.risks_due.forEach(r=> risks.append(h('li',{}, h('span',{}, r.title), h('span',{class:'badge'}, r.review_date))));
  renderWeeklyGantt(data.due_this_week, data.week_start, data.week_end);
}
function renderWeeklyGantt(tasks, startISO, endISO){
  const wrap = document.querySelector('#weeklyGantt');
  wrap.innerHTML = '';
  const start = new Date(startISO); const end = new Date(endISO);
  const totalDays = (end - start) / 86400000 + 1;
  tasks.slice(0,8).forEach(t=>{
    const due = new Date(t.due_date);
    const offset = Math.max(0, Math.floor((due - start)/86400000));
    const bar = h('div',{class:'gantt-bar', style:`width: ${Math.max(10,100/totalDays)}%; margin-left:${(offset/totalDays)*100}%`}, h('span',{class:'label'}, t.title));
    wrap.append(h('div',{class:'gantt-row'}, bar));
  });
}
let backlogMode = 'list';
document.querySelector('#toggleBacklogMode').addEventListener('click', ()=>{
  backlogMode = backlogMode==='list' ? 'kanban' : 'list';
  document.querySelector('#backlogListMode').classList.toggle('hidden', backlogMode!=='list');
  document.querySelector('#kanbanMode').classList.toggle('hidden', backlogMode!=='kanban');
  loadBacklog();
});
document.querySelector('#addTaskBtn').addEventListener('click', async ()=>{
  const title = prompt('Title?'); if(!title) return;
  await api('/api/tasks', {method:'POST', body: JSON.stringify({title})});
  loadBacklog(); loadDashboard();
});
async function loadBacklog(){
  const tasks = await api('/api/tasks');
  if(backlogMode==='list'){
    const tbody = document.querySelector('#backlogTableBody'); tbody.innerHTML = '';
    tasks.forEach(t=>{
      const tr = h('tr',{}, h('td',{}, t.title), h('td',{}, t.type||''), h('td',{}, t.status||''), h('td',{}, t.priority||''), h('td',{}, t.due_date||''), h('td',{}, h('button',{class:'link', onclick: ()=>editTask(t)}, 'Edit'), ' · ', h('button',{class:'link', onclick: ()=>delTask(t.id)}, 'Delete')) );
      tbody.append(tr);
    });
  } else {
    const cols = ['backlog','to-do','in progress','blocked','done','cancelled'];
    cols.forEach(s=> document.querySelector(`#col-${s}`).innerHTML='');
    tasks.forEach(t=>{
      const card = h('div',{class:'card-item', draggable:'true'}, h('div',{class:'title'}, t.title), h('div',{class:'meta'}, h('span',{}, t.type||''), h('span',{}, t.priority||''), t.due_date ? h('span',{}, t.due_date) : '') );
      card.addEventListener('dragstart', e=>{ e.dataTransfer.setData('text/plain', String(t.id)); card.classList.add('dragging');});
      card.addEventListener('dragend', ()=> card.classList.remove('dragging'));
      document.querySelector(`#col-${t.status}`).append(card);
    });
  }
}
Array.from(document.querySelectorAll('.kanban-drop')).forEach(box=>{
  box.addEventListener('dragover', e=>{e.preventDefault()});
  box.addEventListener('drop', async e=>{
    e.preventDefault();
    const id = Number(e.dataTransfer.getData('text/plain'));
    const status = box.parentElement.dataset.status;
    await api('/api/tasks', {method:'PUT', body: JSON.stringify({id, status})});
    loadBacklog(); loadDashboard();
  });
});
async function editTask(t){
  const title = prompt('Title', t.title); if(!title) return;
  const due_date = prompt('Due (YYYY-MM-DD)', t.due_date||'');
  await api('/api/tasks', {method:'PUT', body: JSON.stringify({id:t.id, title, due_date})});
  loadBacklog(); loadDashboard();
}
async function delTask(id){
  if(!confirm('Delete item?')) return;
  await api('/api/tasks', {method:'DELETE', body: JSON.stringify({id})});
  loadBacklog(); loadDashboard();
}
document.querySelector('#addPIBtn').addEventListener('click', async ()=>{
  const name = prompt('PI name?'); if(!name) return;
  const start_date = prompt('Start YYYY-MM-DD?');
  const end_date = prompt('End YYYY-MM-DD?');
  await api('/api/pis', {method:'POST', body: JSON.stringify({name,start_date,end_date})});
  loadPI();
});
document.querySelector('#addSprintBtn').addEventListener('click', async ()=>{
  const pi_id = Number(prompt('PI id?')); if(!pi_id) return;
  const name = prompt('Sprint name?');
  const start_date = prompt('Start YYYY-MM-DD?');
  const end_date = prompt('End YYYY-MM-DD?');
  await api('/api/sprints', {method:'POST', body: JSON.stringify({pi_id,name,start_date,end_date})});
  loadPI();
});
document.querySelector('#addTimeOffBtn').addEventListener('click', async ()=>{
  const date = prompt('Date YYYY-MM-DD?'); if(!date) return;
  const category = prompt('Category (holiday/vacation/pto)?')||'holiday';
  const note = prompt('Note?')||'';
  await api('/api/timeoff', {method:'POST', body: JSON.stringify({date,category,note})});
  loadPI();
});
async function loadPI(){
  const [pis, sprints, offs] = await Promise.all([api('/api/pis'), api('/api/sprints'), api('/api/timeoff')]);
  const piTable = document.querySelector('#piTable'); piTable.innerHTML='';
  pis.forEach(p=>{
    const tr = h('tr',{}, h('td',{}, p.name), h('td',{}, p.start_date||''), h('td',{}, p.end_date||''), h('td',{}, h('button',{class:'link', onclick: async()=>{ const name = prompt('Name', p.name)||p.name; const start_date = prompt('Start YYYY-MM-DD', p.start_date||'')||p.start_date; const end_date = prompt('End YYYY-MM-DD', p.end_date||'')||p.end_date; await api('/api/pis',{method:'PUT', body: JSON.stringify({id:p.id, name, start_date, end_date})}); loadPI(); }}, 'Edit')) );
    piTable.append(tr);
  });
  const sprintTable = document.querySelector('#sprintTable'); sprintTable.innerHTML='';
  sprints.forEach(s=>{
    const tr = h('tr',{}, h('td',{}, s.pi_id), h('td',{}, s.name), h('td',{}, s.start_date||''), h('td',{}, s.end_date||''), h('td',{}, h('button',{class:'link', onclick: async()=>{ const name = prompt('Name', s.name)||s.name; const start_date = prompt('Start', s.start_date||'')||s.start_date; const end_date = prompt('End', s.end_date||'')||s.end_date; await api('/api/sprints',{method:'PUT', body: JSON.stringify({id:s.id, name, start_date, end_date})}); loadPI(); }}, 'Edit')) );
    sprintTable.append(tr);
  });
  const toTable = document.querySelector('#timeoffTable'); toTable.innerHTML='';
  offs.forEach(o=>{
    const tr = h('tr',{}, h('td',{}, o.date), h('td',{}, o.category||''), h('td',{}, o.note||''), h('td',{}, h('button',{class:'link', onclick: async()=>{ if(!confirm('Delete?')) return; await api('/api/timeoff',{method:'DELETE', body: JSON.stringify({id:o.id})}); loadPI(); }}, 'Delete')) );
    toTable.append(tr);
  });
}
document.querySelector('#refreshGantt').addEventListener('click', loadGantt);
document.querySelector('#ganttSearch').addEventListener('input', ()=> highlightGantt(document.querySelector('#ganttSearch').value));
document.querySelector('#ganttZoom').addEventListener('change', loadGantt);
async function loadGantt(){
  const tasks = await api('/api/tasks');
  const zoom = document.querySelector('#ganttZoom').value;
  renderGantt(tasks, zoom);
}
function renderGantt(tasks, zoom){
  const canvas = document.querySelector('#ganttCanvas'); canvas.innerHTML='';
  const dates = tasks.map(t=> t.start_date || t.due_date).filter(Boolean).map(d=> new Date(d));
  if(dates.length===0){ canvas.textContent='No dated tasks'; return; }
  const min = new Date(Math.min(...dates));
  const max = new Date(Math.max(...dates));
  const dayMs = 86400000;
  const spanDays = Math.max(1, Math.ceil((max - min)/dayMs) + 7);
  tasks.forEach(t=>{
    const s = new Date(t.start_date || t.due_date || min);
    const e = new Date(t.end_date || t.due_date || s);
    const left = ((s - min)/dayMs)/spanDays*100;
    const width = Math.max(1, ((e - s)/dayMs || 1))/spanDays*100;
    const bar = h('div',{class:'gantt-bar', style:`margin-left:${left}%; width:${width}%`}, h('span',{class:'label'}, t.title));
    const row = h('div',{class:'gantt-row'}, bar);
    row.dataset.title = (t.title||'').toLowerCase();
    canvas.append(row);
  });
}
function highlightGantt(q){
  const needle = q.toLowerCase();
  Array.from(document.querySelectorAll('#ganttCanvas .gantt-row')).forEach(r=>{
    r.style.outline = r.dataset.title.includes(needle) && needle ? '2px solid var(--accent)' : 'none';
  });
}
document.querySelector('#addRiskBtn').addEventListener('click', async ()=>{
  const title = prompt('Risk title?'); if(!title) return;
  const impact = prompt('Impact (low/medium/high/severe)','medium');
  const probability = prompt('Probability (low/medium/high)','low');
  const review_date = prompt('Review date YYYY-MM-DD?');
  await api('/api/risks',{method:'POST', body: JSON.stringify({title, impact, probability, review_date})});
  loadRisks(); loadDashboard();
});
async function loadRisks(){
  const risks = await api('/api/risks');
  const tbody = document.querySelector('#riskTable'); tbody.innerHTML='';
  risks.forEach(r=>{
    const tr = h('tr',{}, h('td',{}, r.title), h('td',{}, r.impact||''), h('td',{}, r.probability||''), h('td',{}, r.status||''), h('td',{}, r.review_date||''), h('td',{}, r.mitigation||''), h('td',{}, h('button',{class:'link', onclick: async()=>{ const status = prompt('Status', r.status||'open')||r.status; const mitigation = prompt('Mitigation', r.mitigation||'')||r.mitigation; await api('/api/risks',{method:'PUT', body: JSON.stringify({id:r.id, status, mitigation})}); loadRisks(); loadDashboard(); }}, 'Edit')) );
    tbody.append(tr);
  });
}
async function loadAutomations(){
  const items = await api('/api/automations');
  const box = document.querySelector('#automationList'); box.innerHTML='';
  if(items.length===0){ box.textContent = 'Drop .py files into automations/'; return; }
  items.forEach(it=>{ box.append(h('button',{class:'primary', onclick:()=>runAutomation(it.name)}, it.name)); box.append(' '); })
}
async function runAutomation(name){
  const out = document.querySelector('#automationOutput'); out.textContent='Running...';
  try{
    const res = await api('/api/automations/run', {method:'POST', body: JSON.stringify({name})});
    out.textContent = (res.stdout||'') + (res.stderr? '\nERR:\n'+res.stderr : '');
  }catch(e){ out.textContent = 'Error: '+e.message; }
}
document.querySelector('#seedBtn').addEventListener('click', async ()=>{
  if(!confirm('This will replace existing sample rows. Continue?')) return;
  await api('/api/seed', {method:'POST'});
  await Promise.all([loadDashboard(), loadBacklog(), loadPI(), loadRisks(), loadGantt(), loadAutomations()]);
  alert('Seeded!');
});
(async function init(){
  show('dashboard');
  await Promise.all([loadDashboard(), loadBacklog(), loadPI(), loadRisks(), loadGantt(), loadAutomations()]);
})();
