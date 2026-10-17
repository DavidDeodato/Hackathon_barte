import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { palette as C } from './abertura.mjs';

const directory = path.dirname(fileURLToPath(import.meta.url));
const slideIds = ['xjvl9k','nnexnc','r7ayvv','hwv1w4','93k4rm'];
const stations = [184,487,790,1093];
const captions = ['Apuração','Investigador','Crítico','Revisão humana'];
const descriptions = ['Valor e rastro','Consulta às fontes','Confronto das evidências','Helena, no caso Rota'];

async function illustration(file,width,height) {
  const bytes=await fs.readFile(path.join(directory,'assets',file));
  return `data:image/png;base64,${bytes.toString('base64')}`;
}

function text(s,name,value,x,y,w,h,size,options={}) {
  const q=s.shapes.add({geometry:'textbox',name,position:{left:x,top:y,width:w,height:h},
    fill:'none',line:{fill:'none',width:0}});
  q.text=value;
  q.text.style={typeface:options.mono?'Liberation Mono':'Arial',fontSize:size,color:options.color||C.ink,
    bold:options.bold||false,alignment:options.align||'left',verticalAlignment:'top',
    autoFit:'none',wrap:'none',insets:0};
  return q;
}
function line(s,name,x1,y1,x2,y2,options={}) {
  return s.shapes.add({geometry:'connector',kind:'straight',name,
    position:{left:Math.min(x1,x2),top:Math.min(y1,y2),width:Math.abs(x2-x1),height:Math.abs(y2-y1)},
    line:{fill:options.color||C.border,width:options.width||1.3,style:options.dash?'dashed':'solid'},
    ...(options.arrow?{tail:{type:'triangle',width:'sm',length:'sm'}}:{}),
    ...(options.both?{head:{type:'triangle',width:'sm',length:'sm'},tail:{type:'triangle',width:'sm',length:'sm'}}:{})});
}
function dot(s,name,x,y,r,color) {
  return s.shapes.add({geometry:'ellipse',name,position:{left:x-r,top:y-r,width:2*r,height:2*r},
    fill:color,line:{fill:'none',width:0}});
}
async function base(s,n,input) {
  s.background.fill=C.canvas;
  s.images.add({svg:await fs.readFile(input.logoPath,'utf8'),alt:'Lastro: marca original',fit:'contain',
    position:{left:88,top:51,width:105,height:22}});
  text(s,'architecture-section','ARQUITETURA AGÊNTICA',865,53,327,26,15,{mono:true,color:C.muted,align:'right'});
  text(s,'page',String(n),1160,667,32,26,16,{mono:true,color:C.muted,align:'right'});
}
function headline(s,first,second,w=760) {
  text(s,'headline-line-1',first,88,133,w,73,50);
  text(s,'headline-line-2',second,88,199,w,73,50,{color:C.accent});
}
async function foundation(s) {
  headline(s,'Arquitetura agêntica.','A apuração é a base.',570);
  text(s,'foundation-explanation','Fontes preservadas e regras vigentes\nformam a base de cada caso.',88,347,490,100,27,{color:C.muted});
  text(s,'foundation-scope','O cálculo determina os valores.\nOs agentes investigam as pendências.',88,509,490,104,26,{color:C.muted});
  s.images.add({contentType:'image/png',dataUrl:await illustration('fundacao-lastro-v3.png',1448,1086),
    alt:'Lastro: ilustração conceitual original de três camadas, fontes, regras e apuração. Não é infraestrutura de implantação.',
    fit:'contain',crop:{left:.13,top:.07,right:.10,bottom:.03},
    position:{left:752,top:169,width:456,height:460}});
  const labels=[['Apuração',302],['Regras',426],['Fontes',536]];
  for(const [label,y] of labels){
    text(s,`layer-label-${label}`,label,593,y-17,143,39,25,{align:'right',color:C.muted});
    line(s,`layer-link-${label}`,747,y+5,790,y+5,{color:C.border});
    dot(s,`layer-anchor-${label}`,790,y+5,2.8,C.accent);
  }
}
async function pathScene(s,stage) {
  s.images.add({contentType:'image/png',dataUrl:await illustration('percurso-caso-v3b.png',2172,724),
    alt:'Lastro: percurso conceitual de um caso por apuração, investigação, crítica e revisão humana. Ilustração autoral, sem representar execução.',
    fit:'contain',crop:{left:.035,top:.355,right:.035,bottom:.195},
    position:{left:74,top:369,width:1132,height:205}});
  for(let i=0;i<4;i++){
    const active=i===stage;
    const color=active?C.accent:'#8C9992';
    if(active){
      dot(s,`active-${i}`,stations[i],563,4,C.accent);
      line(s,`active-link-${i}`,stations[i],533,stations[i],552,{color:C.accent});
    }
    text(s,`station-${i}`,captions[i],stations[i]-134,586,268,40,25,{align:'center',color,bold:active});
    text(s,`station-detail-${i}`,descriptions[i],stations[i]-140,628,280,35,20,{align:'center',color:active?C.muted:'#8C9992'});
  }
}
function note(s,title,detail,x,y,w=300) {
  text(s,'focus-note-title',title,x,y,w,56,30,{color:C.accent});
  text(s,'focus-note-detail',detail,x,y+65,w,92,24,{color:C.muted});
}
async function scene(s,n) {
  if(n===21){await foundation(s);return;}
  const stage=n-22;
  const titles={
    22:['O resultado ganha','um caso com origem.'],
    23:['O investigador busca','contexto nas fontes.'],
    24:['Uma segunda leitura','confronta a interpretação.'],
    25:['A decisão continua','com o financeiro.']
  };
  headline(s,...titles[n],n===24?790:740);
  await pathScene(s,stage);
  if(n===22){
    text(s,'case-value','R$ 1.546,28',872,139,340,67,43,{color:C.accent});
    text(s,'case-qualifier','Rota Global\nDiferença líquida para revisão',874,214,340,81,23,{color:C.muted});
    text(s,'case-input','Valor, composição e referências',88,308,710,43,26,{color:C.muted});
  }
  if(n===23){
    note(s,'4 ferramentas de leitura','Regras, referências,\nfontes e pendências.',871,139,340);
    text(s,'source-node','Fontes cadastradas',350,305,277,38,24,{align:'center',color:C.accent});
    line(s,'source-tool-link',487,354,487,400,{both:true,color:C.accent,width:1.4});
    text(s,'source-query-label','consulta',364,365,108,27,18,{align:'right',color:C.muted});
    text(s,'source-evidence-label','evidências',503,365,130,27,18,{color:C.muted});
  }
  if(n===24){
    text(s,'critic-input','Mesmo caso, interpretação\ne evidências recuperadas',655,307,374,70,23,{align:'center',color:C.accent});
    line(s,'critic-input-link',790,382,790,402,{arrow:true,color:C.accent});
    text(s,'critic-boundary','O crítico examina o material recebido.',88,310,530,64,24,{color:C.muted});
  }
  if(n===25){
    note(s,'Helena','Responsável pelo caso Rota.\nParecer experimental.',896,139,314);
    text(s,'human-handoff','Caso e parecer',960,318,268,38,24,{align:'center',color:C.accent});
    line(s,'human-handoff-link',1093,366,1093,400,{arrow:true,color:C.accent});
    text(s,'human-boundary','Os valores permanecem vinculados à apuração.',88,310,750,44,25,{color:C.muted});
  }
}

export async function reviseEditorialArchitecture({presentation,input}) {
  const selected=input.indices||[21,22,23,24,25];
  for(const n of selected){
    if(n<21||n>25||presentation.slides.getItem(n).id!==slideIds[n-21]) throw new Error('Reinspecionar a ordem dos slides antes de editar.');
    if(presentation.slides.getItem(n).images.items.some(img=>!img.alt?.startsWith('Lastro:'))) throw new Error(`Slide ${n} contém imagem externa a esta revisão; preservar a edição.`);
  }
  for(const n of selected){
    const s=presentation.slides.getItem(n);
    for(const image of [...s.images.items]) image.delete();
    s.shapes.deleteAll();
    await base(s,n,input);
    await scene(s,n);
    s.speakerNotes.text=s.speakerNotes.text.split('\n\nDireção visual revisada:')[0].split('\n\nRevisão editorial Barte:')[0];
    s.speakerNotes.text+='\n\nRevisão editorial Barte: fundo claro, títulos regulares, destaque seletivo e ilustração com foco progressivo. A pilha representa dependências conceituais. O percurso acompanha o caso, sem representar execução ou aprovação. Ilustrações originais geradas com imagegen; textos e vínculos técnicos são nativos editáveis. O crítico recebe o mesmo caso, interpretação e evidências recuperadas, sem uma nova busca. A decisão do caso Rota cabe a Helena. Parecer experimental. Não há nova execução do motor ou do modelo nesta revisão.';
  }
  return {revised:selected,count:presentation.slides.items.length};
}
