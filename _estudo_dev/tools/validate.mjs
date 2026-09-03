import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const runtimeFiles=[
  "manifest.json","index.html","assets/styles.css","assets/progress.js","assets/app.js",
  "data/catalog.js","data/plan.js","data/questions.js",
  "data/commands.js","data/references.js","data/evidence.js"
];
const text=Object.fromEntries(runtimeFiles.map((p)=>[p,fs.readFileSync(path.join(root,p),"utf8")]));
const manifest=JSON.parse(text["manifest.json"]);
const context={window:{}};
for(const p of runtimeFiles.filter((x)=>x.startsWith("data/"))){
  vm.runInNewContext(text[p],context,{filename:p,timeout:2000});
}
vm.runInNewContext(text["assets/progress.js"],context,{filename:"assets/progress.js",timeout:2000});
const E=context.window.ESTUDO;
const errors=[];
const assert=(condition,message)=>{if(!condition)errors.push(message);};
const unique=(items,key,label)=>{
  const values=items.map(key);
  assert(values.length===new Set(values).size,label+" possui IDs duplicados");
};

const actualCounts={
  modules:E.modules.length,concepts:E.concepts.length,relations:E.relations.length,
  claims:E.claims.length,evidence:E.evidence.length,questions:E.questions.length,
  days:E.plan.length,labs:E.labs.length,commands:E.commands.length,references:E.references.length
};
for(const [name,expected] of Object.entries(manifest.counts||{})){
  assert(Object.hasOwn(actualCounts,name),"contagem desconhecida no manifest: "+name);
  assert(actualCounts[name]===expected,`manifest declara ${expected} ${name}; runtime contém ${actualCounts[name]}`);
}
for(const name of Object.keys(actualCounts))assert(Object.hasOwn(manifest.counts||{},name),"contagem ausente no manifest: "+name);
const declaredRuntime=(manifest.runtimeFiles||[]).map((p)=>p.replace(/^\.\//,""));
assert(JSON.stringify(declaredRuntime)===JSON.stringify(runtimeFiles),"runtimeFiles do manifest diverge do pacote validado");
unique(E.modules,(x)=>x.id,"módulos");
unique(E.concepts,(x)=>x.id,"conceitos");
unique(E.questions,(x)=>x.id,"questões");
unique(E.commands,(x)=>x.id,"comandos");
unique(E.references,(x)=>x.id,"fontes");
unique(E.claims,(x)=>x.id,"claims");
unique(E.evidence,(x)=>x.id,"evidências");

const blankProgress={format:"estudo-dev-progress",schemaVersion:"1.0.0",completedDays:[],dayScores:{},questionScores:{},checkpoints:[],reviews:[]};
const normalizeProgress=(candidate)=>vm.runInNewContext(
  "window.ESTUDO.normalizeProgressState("+JSON.stringify(candidate)+")",
  context,
  {filename:"progress-validation",timeout:2000}
);
assert(JSON.stringify(normalizeProgress(blankProgress))===JSON.stringify(blankProgress),"progresso vazio válido não normaliza de forma estável");
for(const [label,candidate] of [
  ["reviews nulo",{...blankProgress,reviews:null}],
  ["score fora da faixa",{...blankProgress,dayScores:{1:5}}],
  ["dia duplicado",{...blankProgress,completedDays:[1,1]}],
  ["prototype escapado",JSON.parse('{"format":"estudo-dev-progress","schemaVersion":"1.0.0","completedDays":[],"dayScores":{},"questionScores":{},"checkpoints":[],"reviews":[],"\\u005f\\u005fproto\\u005f\\u005f":{}}')]
]){
  let rejected=false;
  try{normalizeProgress(candidate);}catch(_){rejected=true;}
  assert(rejected,"importação aceitou "+label);
}

const moduleIds=new Set(E.modules.map((x)=>x.id));
const sourceIds=new Set(E.references.map((x)=>x.id));
for(const c of E.concepts){
  assert(moduleIds.has(c.moduleId),"módulo órfão em "+c.id);
  for(const sid of c.sourceIds)assert(sourceIds.has(sid),"fonte órfã "+sid+" em "+c.id);
}
for(const claim of E.claims){
  assert(moduleIds.has(claim.subjectId.replace(":module","")),"claim sem sujeito "+claim.id);
  for(const eid of claim.evidenceIds)assert(E.evidence.some((x)=>x.id===eid),"claim sem evidência "+claim.id);
}
for(const e of E.evidence)assert(sourceIds.has(e.sourceId),"evidência sem fonte "+e.id);
for(const r of E.relations){
  assert(moduleIds.has(r.from)&&moduleIds.has(r.to),"relação órfã "+r.id);
}
for(const d of E.plan){
  assert(d.duration>=45&&d.duration<=90,"duração inválida no dia "+d.day);
  assert(d.artifact&&d.criteria.length&&d.question,"contrato incompleto no dia "+d.day);
}
for(const c of E.commands){
  assert(E.commandLegend[c.risk],"risco inválido em "+c.id);
  assert(c.command&&c.intent&&c.version,"comando incompleto em "+c.id);
}
for(const r of E.references){
  assert(!/^(?:https?:|file:|\/|\\\\)|\.\./i.test(r.locator),"locator absoluto/proibido em "+r.id);
}

const visiting=new Set(),visited=new Set();
function visit(id){
  if(visiting.has(id)){errors.push("ciclo de pré-requisito em "+id);return;}
  if(visited.has(id))return;
  visiting.add(id);
  const m=E.modules.find((x)=>x.id===id);
  for(const p of m.prerequisites)visit(p);
  visiting.delete(id);visited.add(id);
}
for(const m of E.modules)visit(m.id);

const runtime=runtimeFiles.map((p)=>text[p]).join("\n");
assert(!/https?:\/\//i.test(runtime),"runtime contém endereço remoto completo");
assert(!/(?:href|src)=["']\/[^/]/i.test(text["index.html"]),"HTML contém caminho absoluto");
const links=[...text["index.html"].matchAll(/(?:href|src)=["']([^"'#]+)["']/g)].map((m)=>m[1]);
for(const ref of links){
  const target=path.resolve(root,ref.replace(/^\.\//,""));
  assert(target.startsWith(root+path.sep)&&fs.existsSync(target),"referência quebrada: "+ref);
}
vm.runInNewContext("new Function("+JSON.stringify(text["assets/app.js"])+")",{}, {timeout:2000});

if(errors.length){
  console.error(errors.map((x)=>"ERRO: "+x).join("\n"));
  process.exit(1);
}
console.log(JSON.stringify({
  status:"ok",...actualCounts,
  absoluteRemoteLinks:0
},null,2));
