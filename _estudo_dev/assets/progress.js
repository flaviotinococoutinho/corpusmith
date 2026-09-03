(function progressGuard(){
"use strict";
const E=window.ESTUDO=window.ESTUDO||{};
const format="estudo-dev-progress";
const schemaVersion="1.0.0";

function isRecord(value){
  if(!value||typeof value!=="object"||Array.isArray(value))return false;
  const proto=Object.getPrototypeOf(value);
  return proto===Object.prototype||proto===null;
}
function rejectForbiddenKeys(value){
  if(Array.isArray(value)){value.forEach(rejectForbiddenKeys);return;}
  if(!isRecord(value))return;
  Object.keys(value).forEach((key)=>{
    if(key==="__proto__"||key==="constructor"||key==="prototype")throw new Error("chave proibida");
    rejectForbiddenKeys(value[key]);
  });
}
function requireKeys(record,allowed,label){
  if(!isRecord(record))throw new Error(label+" inválido");
  const extra=Object.keys(record).find((key)=>!allowed.includes(key));
  if(extra)throw new Error(label+" contém campo desconhecido: "+extra);
}
function requireString(value,label){if(typeof value!=="string")throw new Error(label+" inválido");return value;}
function requireScore(value,label){if(!Number.isInteger(value)||value<0||value>4)throw new Error(label+" inválido");return value;}

function normalizeProgressState(value){
  if(!Array.isArray(E.plan)||!Array.isArray(E.questions))throw new Error("dados de progresso não carregados");
  rejectForbiddenKeys(value);
  requireKeys(value,["format","schemaVersion","completedDays","dayScores","questionScores","checkpoints","reviews","appVersion","exportedAt"],"progresso");
  if(value.format!==format||value.schemaVersion!==schemaVersion)throw new Error("schema incompatível");
  if(!Array.isArray(value.completedDays)||!isRecord(value.dayScores)||!isRecord(value.questionScores)||!Array.isArray(value.checkpoints)||!Array.isArray(value.reviews))throw new Error("schema incompatível");

  const completedDays=value.completedDays.map((day)=>{
    if(!Number.isInteger(day)||day<1||day>E.plan.length)throw new Error("dia concluído inválido");
    return day;
  });
  if(new Set(completedDays).size!==completedDays.length)throw new Error("dias concluídos duplicados");

  const dayScores={};
  Object.entries(value.dayScores).forEach(([day,score])=>{
    if(!/^\d+$/.test(day)||Number(day)<1||Number(day)>E.plan.length)throw new Error("nota de dia inválida");
    dayScores[day]=requireScore(score,"nota de dia");
  });
  const questionIds=new Set(E.questions.map((question)=>question.id));
  const questionScores={};
  Object.entries(value.questionScores).forEach(([id,score])=>{
    if(!questionIds.has(id))throw new Error("questão desconhecida: "+id);
    questionScores[id]=requireScore(score,"nota de questão");
  });

  const checkpoints=value.checkpoints.map((record,index)=>{
    requireKeys(record,["day","focus","practice","output","score","errors","next","evidence","createdAt"],"checkpoint "+index);
    if(!Number.isInteger(record.day)||record.day<1||record.day>E.plan.length)throw new Error("dia de checkpoint inválido");
    const createdAt=requireString(record.createdAt,"data do checkpoint");
    if(!Number.isFinite(Date.parse(createdAt)))throw new Error("data do checkpoint inválida");
    const evidence=requireString(record.evidence,"evidência");
    if(/^(?:https?:|file:|\/|\\\\)|\.\./i.test(evidence))throw new Error("evidência usa caminho proibido");
    return {day:record.day,focus:requireString(record.focus,"foco"),practice:requireString(record.practice,"prática"),output:requireString(record.output,"saída"),score:requireScore(record.score,"nota do checkpoint"),errors:requireString(record.errors,"erros"),next:requireString(record.next,"próximo passo"),evidence,createdAt};
  });
  const reviews=value.reviews.map((review,index)=>{
    requireKeys(review,["subject","score","stage","dueAt"],"revisão "+index);
    const dueAt=requireString(review.dueAt,"data da revisão");
    if(!Number.isFinite(Date.parse(dueAt)))throw new Error("data da revisão inválida");
    return {subject:requireString(review.subject,"assunto da revisão"),score:requireScore(review.score,"nota da revisão"),stage:requireString(review.stage,"estágio da revisão"),dueAt};
  });
  return {format,schemaVersion,completedDays,dayScores,questionScores,checkpoints,reviews};
}

E.normalizeProgressState=normalizeProgressState;
}());
