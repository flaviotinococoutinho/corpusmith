(function app(){
"use strict";
const E=window.ESTUDO;
if(!E||!E.concepts||!E.plan||!E.questions) throw new Error("Dados canônicos não carregados");

const $=(q,root=document)=>root.querySelector(q);
const $$=(q,root=document)=>Array.from(root.querySelectorAll(q));
const esc=(v)=>String(v??"").replace(/[&<>"']/g,(ch)=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
const strip=(v)=>String(v??"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
const storageKey="estudoDev.progress.v1";
const prefKey="estudoDev.preferences.v1";
const blankState={format:"estudo-dev-progress",schemaVersion:"1.0.0",completedDays:[],dayScores:{},questionScores:{},checkpoints:[],reviews:[]};
let state=loadState();
let prefs=loadPrefs();
let selectedCheckpointScore=null;
let questionIndex=0;
let seconds=120;
let timerHandle=null;
let conceptPage=1;
const pageSize=18;
let lastDialogTrigger=null;

function clone(obj){return JSON.parse(JSON.stringify(obj));}
function loadState(){
  try{
    const parsed=JSON.parse(localStorage.getItem(storageKey)||"null");
    return parsed&&parsed.format===blankState.format?Object.assign(clone(blankState),parsed):clone(blankState);
  }catch(_){return clone(blankState);}
}
function loadPrefs(){
  try{return Object.assign({theme:"light",dense:false},JSON.parse(localStorage.getItem(prefKey)||"{}"));}
  catch(_){return {theme:"light",dense:false};}
}
function saveState(){
  localStorage.setItem(storageKey,JSON.stringify(state));
  renderDashboard(); renderPlan(); renderCheckpointHistory();
}
function savePrefs(){
  localStorage.setItem(prefKey,JSON.stringify(prefs));
}
function announce(message){
  $("#live-region").textContent="";
  requestAnimationFrame(()=>{$("#live-region").textContent=message;});
}
function moduleOf(id){return E.modules.find((m)=>m.id===id);}
function routeName(){
  const part=(location.hash||"#/inicio").replace(/^#\//,"").split("/")[0];
  return ["inicio","mapa","conceitos","trilhas","entrevistas","laboratorios","comandos","fontes","checkpoint"].includes(part)?part:"inicio";
}
function showRoute(){
  const route=routeName();
  $$(".screen").forEach((s)=>s.hidden=s.dataset.screen!==route);
  $$("#primary-nav a").forEach((a)=>a.classList.toggle("active",a.dataset.route===route));
  document.title=(route==="inicio"?"Estudo Dev":route[0].toUpperCase()+route.slice(1)+" · Estudo Dev");
  const main=$("#main");
  main.focus({preventScroll:true});
  window.scrollTo({top:0,behavior:"auto"});
  if(route==="mapa") renderGraph();
  if(route==="conceitos") renderConcepts();
  if(route==="entrevistas") renderQuestion();
  closeMobileMenu();
}

function renderMetrics(){
  const values=[
    [E.meta.conceptCount,"conceitos canônicos"],
    [E.modules.length,"módulos conectados"],
    [E.questions.length,"questões de entrevista"],
    [E.commands.length,"cartões operacionais"]
  ];
  $("#metric-grid").innerHTML=values.map(([n,label])=>`<div class="metric"><strong>${esc(n)}</strong><span>${esc(label)}</span></div>`).join("");
}

function lowestScores(limit=3){
  return Object.entries(state.dayScores).sort((a,b)=>a[1]-b[1]).slice(0,limit);
}
function nextDay(){
  return E.plan.find((d)=>!state.completedDays.includes(d.day))||E.plan[E.plan.length-1];
}
function renderDashboard(){
  const next=nextDay();
  $("#next-day-title").textContent=`Dia ${next.day} · ${next.title}`;
  $("#next-day-duration").textContent=`${next.duration} min`;
  $("#next-day-objective").textContent=next.objective;
  $("#next-day-evidence").textContent=`Evidência exigida: ${next.artifact}`;
  $("#continue-link").textContent=state.completedDays.length===21?"Revisar plano completo":"Continuar próxima sessão";
  const reviews=state.reviews.filter((r)=>new Date(r.dueAt)<=new Date()).slice(0,4);
  $("#review-queue").innerHTML=(reviews.length?reviews:[{subject:"Nenhuma revisão vencida",stage:"—"}]).map((r)=>`<div class="mini-item"><b>${esc(r.stage)}</b><span>${esc(r.subject)}</span></div>`).join("");
  const lows=lowestScores();
  $("#gap-list").innerHTML=(lows.length?lows:[["—","Registre a primeira nota"]]).map(([day,score])=>`<div class="mini-item"><b>${esc(score)}</b><span>${day==="—"?"Registre a primeira nota":`Dia ${esc(day)} · ${esc(E.plan[Number(day)-1]?.title||"")}`}</span></div>`).join("");
}

const positions={
  method:[500,55],java:[245,145],coding:[755,145],jvm:[135,255],kotlin:[315,255],spring:[500,255],data:[685,255],
  kafka:[350,375],messaging:[540,375],storage:[730,375],distributed:[540,485],platform:[260,595],sre:[470,595],architecture:[685,595],staff:[880,595]
};
function renderGraph(){
  const svg=$("#knowledge-graph");
  while(svg.firstChild) svg.removeChild(svg.firstChild);
  const ns=svg.namespaceURI;
  const defs=document.createElementNS(ns,"defs");
  const marker=document.createElementNS(ns,"marker");
  marker.setAttribute("id","arrow");marker.setAttribute("viewBox","0 0 10 10");marker.setAttribute("refX","9");marker.setAttribute("refY","5");marker.setAttribute("markerWidth","6");marker.setAttribute("markerHeight","6");marker.setAttribute("orient","auto-start-reverse");
  const path=document.createElementNS(ns,"path");path.setAttribute("d","M 0 0 L 10 5 L 0 10 z");path.setAttribute("fill","currentColor");
  marker.appendChild(path);defs.appendChild(marker);svg.appendChild(defs);
  E.relations.forEach((rel)=>{
    const a=positions[rel.from],b=positions[rel.to]; if(!a||!b)return;
    const line=document.createElementNS(ns,"line");
    line.setAttribute("x1",a[0]);line.setAttribute("y1",a[1]);line.setAttribute("x2",b[0]);line.setAttribute("y2",b[1]);
    line.setAttribute("class","graph-edge");line.setAttribute("marker-end","url(#arrow)");
    svg.appendChild(line);
  });
  E.modules.forEach((m)=>{
    const [x,y]=positions[m.id];
    const g=document.createElementNS(ns,"g");
    g.setAttribute("class","graph-node");g.setAttribute("data-priority",m.priority);g.setAttribute("tabindex","0");g.setAttribute("role","button");g.setAttribute("aria-label",`${m.title}, ${m.conceptCount} conceitos`);
    const circle=document.createElementNS(ns,"circle");circle.setAttribute("cx",x);circle.setAttribute("cy",y);circle.setAttribute("r","52");
    const text=document.createElementNS(ns,"text");text.setAttribute("x",x);text.setAttribute("y",y-3);text.setAttribute("text-anchor","middle");
    const lines=m.short.split(/\/| e /).slice(0,2);
    lines.forEach((value,i)=>{const t=document.createElementNS(ns,"tspan");t.setAttribute("x",x);t.setAttribute("dy",i?"16":"0");t.textContent=value; text.appendChild(t);});
    g.append(circle,text);g.addEventListener("click",()=>selectGraphModule(m.id));g.addEventListener("keydown",(ev)=>{if(ev.key==="Enter"||ev.key===" "){ev.preventDefault();selectGraphModule(m.id);}});
    svg.appendChild(g);
  });
  $("#graph-text-list").innerHTML=E.modules.map((m)=>`<button type="button" data-module="${esc(m.id)}"><strong>${esc(m.order)}. ${esc(m.short)}</strong><br><small>${esc(m.conceptCount)} conceitos · ${esc(m.priority)}</small></button>`).join("");
  $$("#graph-text-list button").forEach((b)=>b.addEventListener("click",()=>selectGraphModule(b.dataset.module)));
}
function selectGraphModule(id){
  const m=moduleOf(id); if(!m)return;
  const concepts=E.concepts.filter((c)=>c.moduleId===id);
  $("#graph-detail").innerHTML=`<p class="eyebrow">NÓ ${esc(m.order)} · ${esc(m.priority)}</p><h2>${esc(m.title)}</h2><p>${esc(m.description)}</p><div class="detail-block"><h3>Pré-requisitos</h3><p>${m.prerequisites.length?m.prerequisites.map((p)=>esc(moduleOf(p)?.short||p)).join(" → "):"raiz da trilha"}</p></div><h3>${concepts.length} conceitos</h3><div class="graph-text-list">${concepts.map((c)=>`<button type="button" data-concept="${esc(c.id)}">${esc(c.title)}</button>`).join("")}</div>`;
  $$("#graph-detail [data-concept]").forEach((b)=>b.addEventListener("click",()=>openConcept(b.dataset.concept,b)));
}

function populateFilters(){
  $("#module-filter").insertAdjacentHTML("beforeend",E.modules.map((m)=>`<option value="${esc(m.id)}">${esc(m.order)} · ${esc(m.short)}</option>`).join(""));
  const kinds=Array.from(new Set(E.concepts.map((c)=>c.kind))).sort();
  $("#kind-filter").insertAdjacentHTML("beforeend",kinds.map((k)=>`<option value="${esc(k)}">${esc(k)}</option>`).join(""));
  const tools=Array.from(new Set(E.commands.map((c)=>c.tool))).sort();
  $("#command-tool-filter").insertAdjacentHTML("beforeend",tools.map((t)=>`<option>${esc(t)}</option>`).join(""));
}
function filteredConcepts(){
  const query=strip($("#concept-search").value);
  const moduleId=$("#module-filter").value,priority=$("#priority-filter").value,kind=$("#kind-filter").value;
  return E.concepts.filter((c)=>{
    const hay=strip([c.title,c.summary,c.tags.join(" "),moduleOf(c.moduleId)?.title].join(" "));
    return (!query||hay.includes(query))&&(!moduleId||c.moduleId===moduleId)&&(!priority||c.priority===priority)&&(!kind||c.kind===kind);
  });
}
function renderConcepts(){
  const list=filteredConcepts(); const pages=Math.max(1,Math.ceil(list.length/pageSize)); conceptPage=Math.min(conceptPage,pages);
  const page=list.slice((conceptPage-1)*pageSize,conceptPage*pageSize);
  $("#concept-count-label").textContent=`${list.length} de ${E.concepts.length} conceitos`;
  $("#concept-grid").innerHTML=page.map((c)=>{
    const m=moduleOf(c.moduleId);
    return `<article class="concept-card"><header><span class="badge">${esc(m.short)}</span><strong class="priority-${esc(c.priority)}">${esc(c.priority)}</strong></header><h2>${esc(c.title)}</h2><p>${esc(c.summary)}</p><div class="card-tags">${c.tags.slice(0,4).map((t)=>`<span>#${esc(t)}</span>`).join("")}</div><button type="button" data-concept="${esc(c.id)}">Abrir mecanismo →</button></article>`;
  }).join("")||`<div class="panel"><h2>Nenhum resultado</h2><p>Remova um filtro ou tente um termo mais amplo.</p></div>`;
  $$("#concept-grid [data-concept]").forEach((b)=>b.addEventListener("click",()=>openConcept(b.dataset.concept,b)));
  $("#concept-page").textContent=`Página ${conceptPage} de ${pages}`;
  $("#concept-prev").disabled=conceptPage<=1; $("#concept-next").disabled=conceptPage>=pages;
}
function openConcept(id,trigger){
  const c=E.concepts.find((x)=>x.id===id); if(!c)return;
  const m=moduleOf(c.moduleId); const refs=c.sourceIds.map((sid)=>E.references?.find((r)=>r.id===sid)).filter(Boolean);
  lastDialogTrigger=trigger||document.activeElement;
  $("#concept-dialog-content").innerHTML=`<p class="eyebrow">${esc(m.title)} · ${esc(c.priority)}</p><h2 id="concept-dialog-title">${esc(c.title)}</h2><p class="lede">${esc(c.summary)}</p><div class="detail-grid"><div class="detail-block"><h3>Mecanismo</h3><p>${esc(c.mechanism)}</p></div><div class="detail-block"><h3>Regra</h3><p>${esc(c.rule)}</p></div><div class="detail-block"><h3>Armadilha</h3><p>${esc(c.trap)}</p></div><div class="detail-block"><h3>Validade</h3><p>${esc(c.versionScope)}</p></div></div><h3>Contrato epistemológico</h3><p><span class="badge">${esc(c.epistemic)}</span> confiança ${esc(c.confidence)} · estado ${esc(c.status)}</p><h3>Fontes relacionadas</h3><ul>${refs.map((r)=>`<li>${esc(r.title)} · grau ${esc(r.grade)}</li>`).join("")||"<li>Evidência pendente no catálogo local.</li>"}</ul>`;
  $("#concept-dialog").showModal();
  $(".dialog-close",$("#concept-dialog")).focus();
}
function closeDialog(dialog){
  if(dialog.open)dialog.close();
  if(lastDialogTrigger&&document.contains(lastDialogTrigger))lastDialogTrigger.focus();
}

function reviewForScore(score){
  const offsets={0:0,1:1,2:3,3:7,4:14}; const stages={0:"R0",1:"R1",2:"R3",3:"R7",4:"R14"};
  return {days:offsets[score],stage:stages[score]};
}
function scheduleReview(subject,score){
  const rule=reviewForScore(score); const due=new Date(); due.setDate(due.getDate()+rule.days);
  state.reviews=state.reviews.filter((r)=>r.subject!==subject);
  state.reviews.push({subject,score,stage:rule.stage,dueAt:due.toISOString()});
}
function renderPlan(){
  $("#plan-list").innerHTML=E.plan.map((d)=>{
    const done=state.completedDays.includes(d.day); const score=state.dayScores[d.day];
    return `<article class="plan-day ${done?"completed":""}"><div class="day-number">${d.day}</div><div><h2>${esc(d.title)}</h2><p>${esc(d.objective)}</p><span class="pill">${d.duration} min${score!==undefined?` · nota ${score}`:""}</span></div><button class="plan-check" type="button" data-day="${d.day}" aria-pressed="${done}" aria-label="${done?"Reabrir":"Marcar como concluído"} o dia ${d.day}">${done?"✓":"○"}</button><details><summary>Prática, artefato e conclusão</summary><p><strong>Prática:</strong> ${esc(d.practice)}</p><p><strong>Artefato:</strong> <code>${esc(d.artifact)}</code></p><ul>${d.criteria.map((x)=>`<li>${esc(x)}</li>`).join("")}</ul><p><strong>Pergunta:</strong> ${esc(d.question)}</p></details></article>`;
  }).join("");
  $$("#plan-list .plan-check").forEach((b)=>b.addEventListener("click",()=>{
    const day=Number(b.dataset.day);
    if(state.completedDays.includes(day)){
      state.completedDays=state.completedDays.filter((x)=>x!==day);
      saveState();announce(`Dia ${day} reaberto`);
    }else{
      const proof=state.checkpoints.some((r)=>r.day===day&&r.score>=3&&r.output&&r.evidence);
      if(!proof){
        location.hash="#/checkpoint";
        setTimeout(()=>{$("#checkpoint-day").value=String(day);$("#checkpoint-focus").focus();},0);
        announce("Conclusão bloqueada: registre nota mínima 3, artefato e evidência relativa");
        return;
      }
      state.completedDays.push(day);saveState();announce(`Dia ${day} concluído com evidência`);
    }
  }));
  const pct=Math.round(state.completedDays.length/21*100);
  $("#plan-progress").innerHTML=`<span>${state.completedDays.length}/21</span>`;
  $("#plan-progress").setAttribute("aria-label",`${pct}% do plano concluído`);
  $("#checkpoint-day").innerHTML=E.plan.map((d)=>`<option value="${d.day}">${d.day} · ${esc(d.title)}</option>`).join("");
  $("#checkpoint-day").value=String(nextDay().day);
}
function renderLabs(){
  $("#lab-grid").innerHTML=E.labs.map((l)=>`<article class="lab-card"><div class="card-meta"><span class="badge">Dia ${l.day}</span><span>${l.duration} min</span></div><h2>${esc(l.title)}</h2><p>${esc(l.practice)}</p><h3>Critério executável</h3><ul>${l.checks.map((x)=>`<li>${esc(x)}</li>`).join("")}</ul><footer>Artefato: <code>${esc(l.artifact)}</code></footer></article>`).join("");
}
function renderCommands(){
  const tool=$("#command-tool-filter").value,risk=$("#command-risk-filter").value;
  const list=E.commands.filter((c)=>(!tool||c.tool===tool)&&(!risk||c.markers.includes(risk)));
  $("#command-grid").innerHTML=list.map((c)=>`<article class="command-card"><div><span class="risk risk-${esc(c.risk)}" aria-label="Risco ${esc(E.commandLegend[c.risk])}">${esc(c.risk)}</span><p>${esc(c.tool)}<br>${esc(c.version)}</p></div><div><strong>${esc(c.intent)}</strong><code>${esc(c.command)}</code>${c.rollback?`<p><b>Guardrail:</b> ${esc(c.rollback)}</p>`:""}</div><button class="copy-command" type="button" data-command-id="${esc(c.id)}" aria-label="Copiar comando">⧉</button></article>`).join("");
  $$("#command-grid .copy-command").forEach((b)=>b.addEventListener("click",()=>copyCommand(b.dataset.commandId,b)));
  announce(`${list.length} comandos exibidos`);
}
async function copyCommand(id,button){
  const value=E.commands.find((c)=>c.id===id)?.command||"";
  try{
    if(navigator.clipboard&&isSecureContext)await navigator.clipboard.writeText(value);
    else{
      const ta=document.createElement("textarea");ta.value=value;ta.setAttribute("readonly","");ta.className="clipboard-fallback";document.body.appendChild(ta);ta.select();document.execCommand("copy");ta.remove();
    }
    button.textContent="✓";setTimeout(()=>button.textContent="⧉",1000);announce("Comando copiado");
  }catch(_){announce("Não foi possível copiar; selecione o comando manualmente");}
}
function renderReferences(){
  $("#reference-grid").innerHTML=E.references.map((r)=>`<article class="reference-card"><div class="card-meta"><span class="badge">${esc(r.epistemic)}</span><span>grau ${esc(r.grade)}</span></div><h2>${esc(r.title)}</h2><p>${esc((r.note||r.scope))}</p><div class="card-tags"><span>${esc(r.type)}</span><span>${esc(r.organization)}</span><span>${esc(r.visibility)}</span></div>${r.locator.startsWith("./")?`<a class="locator" href="${esc(r.locator)}">Abrir artefato local →</a>`:`<div class="locator">${esc(r.locator)}</div>`}</article>`).join("");
}
function renderQuestion(){
  const q=E.questions[questionIndex%E.questions.length]; const m=moduleOf(q.moduleId);
  $("#question-id").textContent=q.id;$("#question-module").textContent=m.title;$("#question-prompt").textContent=q.prompt;
  $("#answer-30").textContent=q.answer30;$("#answer-120").textContent=q.answer120;
  $("#must-mention").innerHTML=q.mustMention.map((x)=>`<li>${esc(x)}</li>`).join("");
  $("#answer-details").open=false;$("#answer-notes").value="";
  renderScoreButtons("#question-score-buttons",(score)=>{
    state.questionScores[q.id]=score;scheduleReview(q.prompt,score);saveState();renderQuestionScore();announce(`Nota ${score} registrada para ${q.id}`);
  });
  resetTimer();renderQuestionScore();
}
function renderQuestionScore(){
  const q=E.questions[questionIndex%E.questions.length],score=state.questionScores[q.id];
  $$("#question-score-buttons button").forEach((b)=>b.classList.toggle("selected",Number(b.dataset.score)===score));
}
function renderScoreButtons(selector,onPick){
  $(selector).innerHTML=[0,1,2,3,4].map((n)=>`<button type="button" data-score="${n}" aria-label="Nota ${n}">${n}</button>`).join("");
  $$(selector+" button").forEach((b)=>b.addEventListener("click",()=>onPick(Number(b.dataset.score))));
}
function resetTimer(){
  clearInterval(timerHandle);timerHandle=null;seconds=120;updateTimer();
}
function updateTimer(){
  const timer=$("#timer"); const min=String(Math.floor(seconds/60)).padStart(2,"0"),sec=String(seconds%60).padStart(2,"0");
  $("strong",timer).textContent=`${min}:${sec}`;$("span",timer).textContent=timerHandle?"respondendo":seconds===0?"tempo encerrado":"pronto";
  timer.classList.toggle("running",Boolean(timerHandle));timer.classList.toggle("expired",seconds===0);
}
function startTimer(){
  if(timerHandle)return;
  timerHandle=setInterval(()=>{seconds=Math.max(0,seconds-1);updateTimer();if(seconds===0){clearInterval(timerHandle);timerHandle=null;updateTimer();announce("Tempo de 120 segundos encerrado");}},1000);
  updateTimer();
}
function nextQuestion(){
  questionIndex=(questionIndex+17)%E.questions.length;renderQuestion();
}

function renderCheckpointHistory(){
  const rows=state.checkpoints.slice().reverse();
  $("#checkpoint-history").innerHTML=rows.length?rows.map((r)=>`<div class="history-row"><strong>Dia ${esc(r.day)}</strong><div><b>${esc(r.focus)}</b><p>${esc(r.errors)}</p><small>${esc(new Date(r.createdAt).toLocaleDateString("pt-BR"))}</small></div><strong>${esc(r.score)}/4</strong></div>`).join(""):"<p>Nenhum checkpoint salvo neste navegador.</p>";
}
function submitCheckpoint(ev){
  ev.preventDefault();
  if(selectedCheckpointScore===null){announce("Selecione uma nota de 0 a 4");return;}
  const record={
    day:Number($("#checkpoint-day").value),focus:$("#checkpoint-focus").value.trim(),practice:$("#checkpoint-practice").value.trim(),
    output:$("#checkpoint-output").value.trim(),score:selectedCheckpointScore,errors:$("#checkpoint-errors").value.trim(),
    next:$("#checkpoint-next").value.trim(),evidence:$("#checkpoint-evidence").value.trim(),createdAt:new Date().toISOString()
  };
  if(!record.focus||!record.practice||!record.output||!record.errors||!record.next||!record.evidence){announce("Preencha os campos obrigatórios");return;}
  if(/^(?:https?:|file:|\/|\\\\)|\.\./i.test(record.evidence)){announce("A evidência deve usar caminho relativo, sem URL ou caminho absoluto");return;}
  state.checkpoints.push(record);state.dayScores[record.day]=record.score;scheduleReview(`Dia ${record.day} · ${E.plan[record.day-1].title}`,record.score);
  if(record.score>=3&&!state.completedDays.includes(record.day))state.completedDays.push(record.day);
  saveState();ev.target.reset();selectedCheckpointScore=null;renderCheckpointScore();announce("Checkpoint salvo localmente");
}
function renderCheckpointScore(){
  $$("#checkpoint-score-buttons button").forEach((b)=>b.classList.toggle("selected",Number(b.dataset.score)===selectedCheckpointScore));
}
function exportProgress(){
  const payload=Object.assign({},state,{appVersion:"1.0.0",exportedAt:new Date().toISOString()});
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:"application/json"});
  const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="estudo-dev-progresso.json";document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),0);announce("Progresso exportado");
}
function importProgress(file){
  if(!file||file.size>1024*1024){announce("Arquivo ausente ou maior que 1 MB");return;}
  const reader=new FileReader();
  reader.onload=()=>{
    try{
      const text=String(reader.result);
      if(/"(__proto__|constructor|prototype)"\s*:/.test(text))throw new Error("chave proibida");
      const parsed=JSON.parse(text);
      if(parsed.format!==blankState.format||parsed.schemaVersion!=="1.0.0"||!Array.isArray(parsed.checkpoints)||!Array.isArray(parsed.completedDays))throw new Error("schema incompatível");
      state=Object.assign(clone(blankState),parsed);saveState();announce("Progresso importado com sucesso");
    }catch(err){announce("Importação recusada: "+err.message);}
  };
  reader.readAsText(file);
}

function openSearch(){
  const d=$("#global-search-dialog");lastDialogTrigger=document.activeElement;d.showModal();$("#global-search-input").focus();
}
function renderGlobalSearch(){
  const q=strip($("#global-search-input").value);
  if(q.length<2){$("#global-search-results").innerHTML="<p>Digite pelo menos dois caracteres.</p>";return;}
  const results=[];
  E.concepts.forEach((c)=>{if(strip(c.title+" "+c.summary+" "+c.tags.join(" ")).includes(q))results.push({kind:"conceito",title:c.title,subtitle:moduleOf(c.moduleId).title,id:c.id,action:"concept"});});
  E.questions.forEach((x)=>{if(strip(x.prompt).includes(q))results.push({kind:"pergunta",title:x.prompt,subtitle:x.id,id:x.id,action:"question"});});
  E.labs.forEach((x)=>{if(strip(x.title+" "+x.practice).includes(q))results.push({kind:"laboratório",title:x.title,subtitle:"Dia "+x.day,id:String(x.day),action:"lab"});});
  E.references.forEach((x)=>{if(strip(x.title+" "+(x.note||x.scope)).includes(q))results.push({kind:"fonte",title:x.title,subtitle:x.epistemic+" · grau "+x.grade,id:x.id,action:"reference"});});
  $("#global-search-results").innerHTML=results.slice(0,30).map((r)=>`<button type="button" class="search-result" data-action="${r.action}" data-id="${esc(r.id)}"><strong>${esc(r.title)}</strong><span>${esc(r.kind)} · ${esc(r.subtitle)}</span></button>`).join("")||"<p>Nenhum resultado.</p>";
  $$("#global-search-results button").forEach((b)=>b.addEventListener("click",()=>activateSearchResult(b.dataset.action,b.dataset.id,b)));
  announce(`${results.length} resultados encontrados`);
}
function activateSearchResult(action,id,trigger){
  if(action==="concept"){closeDialog($("#global-search-dialog"));openConcept(id,trigger);return;}
  if(action==="question"){questionIndex=E.questions.findIndex((q)=>q.id===id);location.hash="#/entrevistas";}
  if(action==="lab")location.hash="#/laboratorios";
  if(action==="reference")location.hash="#/fontes";
  closeDialog($("#global-search-dialog"));
}

function applyPrefs(){
  document.documentElement.dataset.theme=prefs.theme;
  document.body.classList.toggle("dense",prefs.dense);
}
function cycleTheme(){
  const themes=["light","dark","contrast"];prefs.theme=themes[(themes.indexOf(prefs.theme)+1)%themes.length];applyPrefs();savePrefs();announce("Tema "+prefs.theme);
}
function toggleDensity(){prefs.dense=!prefs.dense;applyPrefs();savePrefs();announce(prefs.dense?"Densidade compacta":"Densidade confortável");}
function closeMobileMenu(){$(".sidebar").classList.remove("open");$("#menu-button").setAttribute("aria-expanded","false");}
function toggleMobileMenu(){const open=$(".sidebar").classList.toggle("open");$("#menu-button").setAttribute("aria-expanded",String(open));}

function bind(){
  window.addEventListener("hashchange",showRoute);
  $("#menu-button").addEventListener("click",toggleMobileMenu);
  $("#search-button").addEventListener("click",openSearch);
  $("#theme-button").addEventListener("click",cycleTheme);
  $("#density-button").addEventListener("click",toggleDensity);
  $("#export-button").addEventListener("click",exportProgress);
  $("#concept-search").addEventListener("input",()=>{conceptPage=1;renderConcepts();});
  ["module-filter","priority-filter","kind-filter"].forEach((id)=>$("#"+id).addEventListener("change",()=>{conceptPage=1;renderConcepts();}));
  $("#clear-filters").addEventListener("click",()=>{$("#concept-search").value="";$("#module-filter").value="";$("#priority-filter").value="";$("#kind-filter").value="";conceptPage=1;renderConcepts();});
  $("#concept-prev").addEventListener("click",()=>{conceptPage--;renderConcepts();});
  $("#concept-next").addEventListener("click",()=>{conceptPage++;renderConcepts();});
  $("#command-tool-filter").addEventListener("change",renderCommands);$("#command-risk-filter").addEventListener("change",renderCommands);
  $("#timer-start").addEventListener("click",startTimer);$("#timer-reset").addEventListener("click",resetTimer);$("#next-question").addEventListener("click",nextQuestion);
  $("#checkpoint-form").addEventListener("submit",submitCheckpoint);
  $("#import-button").addEventListener("click",()=>$("#import-file").click());
  $("#import-file").addEventListener("change",(ev)=>{importProgress(ev.target.files[0]);ev.target.value="";});
  $("#global-search-input").addEventListener("input",renderGlobalSearch);
  $$("dialog .dialog-close").forEach((b)=>b.addEventListener("click",()=>closeDialog(b.closest("dialog"))));
  $$("dialog").forEach((d)=>d.addEventListener("click",(ev)=>{if(ev.target===d)closeDialog(d);}));
  document.addEventListener("keydown",(ev)=>{
    const typing=/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName);
    if(ev.key==="/"&&!typing){ev.preventDefault();openSearch();}
    if(ev.key==="Escape")$$("dialog[open]").forEach(closeDialog);
    if(!typing&&!ev.ctrlKey&&!ev.metaKey&&!ev.altKey){
      const routes={g:"mapa",c:"conceitos",t:"trilhas",i:"entrevistas"};
      if(routes[ev.key])location.hash="#/"+routes[ev.key];
    }
  });
}

function init(){
  applyPrefs();populateFilters();renderMetrics();renderDashboard();renderGraph();renderConcepts();renderPlan();renderLabs();renderCommands();renderReferences();renderQuestion();renderCheckpointHistory();
  renderScoreButtons("#checkpoint-score-buttons",(score)=>{selectedCheckpointScore=score;renderCheckpointScore();announce(`Nota ${score} selecionada`);});
  bind();if(!location.hash)location.hash="#/inicio";else showRoute();
}
init();
})();
