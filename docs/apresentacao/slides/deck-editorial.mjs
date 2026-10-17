import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {palette as C} from './abertura.mjs';

const root=path.dirname(fileURLToPath(import.meta.url));
const ids=['5ipjat','70lrmj','2kxhmy','1yg763','cljwrc','mv4tng','2atxvn','did0bz','fpwxbm','a0i70z','492lsz','9exctf','9vq4vn','j2ubu5','2mw1ob','qx9hob','6bq8c3','12aywb','34tg3n','qr1nwo','217tvs'];
const crops={
  'planilha-editorial.png':{left:.1416,top:.0626,right:.1374,bottom:.0313},
  'relatorios-editorial.png':{left:.1395,top:.0405,right:.1381,bottom:.0516},
  'contexto-editorial.png':{left:.087,top:.0764,right:.0622,bottom:.0691},
  'dossie-editorial.png':{left:.1878,top:.0258,right:.1153,bottom:.0295},
  'contrato-vigencia-editorial.png':{left:.241,top:.081,right:.1354,bottom:.0488},
  'apuracao-frentes-editorial-v2.png':{left:.0129,top:.1768,right:.0092,bottom:.1312},
};

function txt(s,name,value,x,y,w,h,size,options={}) {
  const q=s.shapes.add({geometry:'textbox',name,position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  q.text=value;
  q.text.style={typeface:options.mono?'Liberation Mono':'Arial',fontSize:size,color:options.color||C.ink,
    bold:options.bold||false,alignment:options.align||'left',verticalAlignment:'top',autoFit:'none',wrap:'none',insets:0};
  return q;
}
function line(s,name,x1,y1,x2,y2,options={}) {
  if((x2-x1)*(y2-y1)<0&&!options.arrow){
    const left=Math.min(x1,x2),top=Math.min(y1,y2),w=Math.abs(x2-x1),h=Math.abs(y2-y1);
    return s.shapes.add({geometry:'custom',name,position:{left,top,width:w,height:h},fill:'none',
      line:{fill:options.color||C.border,width:options.width||1.3,style:options.dash?'dashed':'solid'},
      customPaths:[{width:w,height:h,commands:[{moveTo:{x:x1-left,y:y1-top}},{lineTo:{x:x2-left,y:y2-top}}]}]});
  }
  return s.shapes.add({geometry:'connector',kind:'straight',name,
    position:{left:Math.min(x1,x2),top:Math.min(y1,y2),width:Math.abs(x2-x1),height:Math.abs(y2-y1)},
    line:{fill:options.color||C.border,width:options.width||1.3,style:options.dash?'dashed':'solid'},
    ...(options.arrow?{tail:{type:'triangle',width:'sm',length:'sm'}}:{})});
}
function curve(s,name,x1,y1,x2,y2,options={}) {
  const left=Math.min(x1,x2),top=Math.min(y1,y2),w=Math.max(1,Math.abs(x2-x1)),h=Math.max(1,Math.abs(y2-y1));
  const sx=x1-left,sy=y1-top,tx=x2-left,ty=y2-top;
  return s.shapes.add({geometry:'custom',name,position:{left,top,width:w,height:h},fill:'none',
    line:{fill:options.color||C.border,width:options.width||1.3},
    customPaths:[{width:w,height:h,commands:[{moveTo:{x:sx,y:sy}},
      {cubicBezTo:{x1:sx+(tx-sx)*.5,y1:sy,x2:sx+(tx-sx)*.5,y2:ty,x:tx,y:ty}}]}]});
}
function circle(s,name,x,y,r,fill='none',stroke=C.border) {
  return s.shapes.add({geometry:'ellipse',name,position:{left:x-r,top:y-r,width:r*2,height:r*2},fill,line:{fill:stroke,width:1.3}});
}
async function art(s,file,x,y,w,h,options={}) {
  const b=await fs.readFile(path.join(root,'assets',file));
  return s.images.add({dataUrl:`data:image/png;base64,${b.toString('base64')}`,contentType:'image/png',
    alt:`Lastro: ilustração original ${file}, sem dados financeiros reais`,fit:'contain',
    crop:options.crop||crops[file],position:{left:x,top:y,width:w,height:h}});
}
async function brand(s,input,x=88,y=51,w=105) {
  s.images.add({svg:await fs.readFile(input.logoPath,'utf8'),alt:'Lastro: marca original',fit:'contain',
    position:{left:x,top:y,width:w,height:w*123.2/598.4}});
}
async function frame(s,n,input) {
  s.background.fill=C.canvas;
  if(n!==0&&n!==11) await brand(s,input);
  const section=n<=10?'CONTEXTO TARVO':n<=14?'SOLUÇÃO LASTRO':n<=18?'APURAÇÃO':'EVIDÊNCIA E ORIGEM';
  if(n!==0&&n!==11) txt(s,'section',section,850,53,342,26,15,{mono:true,color:C.muted,align:'right'});
  if(n!==0) txt(s,'page',String(n).padStart(2,'0'),1160,667,32,26,16,{mono:true,color:C.muted,align:'right'});
}
function headline(s,first,second='',width=1050,options={}) {
  const size=options.size||50,y=options.y||133;
  txt(s,'headline-first',first,88,y,width,73,size);
  if(second) txt(s,'headline-second',second,88,y+66,width,73,size,{color:C.accent});
}

async function triangle(s,stage,compact=false) {
  const p=compact?[[178,365],[482,365],[330,602]]:[[790,350],[1100,350],[945,611]];
  const center=compact?[330,462]:[945,440];
  const labelSize=compact?20:21,r=16;
  if(stage>=3){
    line(s,'triangle-top',...p[0],...p[1]);
    line(s,'triangle-left',...p[0],...p[2]);
    line(s,'triangle-right',...p[1],...p[2]);
    line(s,'helena-context',center[0],center[1]+47,p[2][0],p[2][1]-17,{dash:true,color:'#A4B3A9'});
  }
  for(let i=0;i<3;i++){
    const visible=stage>=i+1,active=stage===i+1;
    const q=circle(s,`front-${i+1}`,p[i][0],p[i][1],r,active?C.accent:visible?C.soft:'none',visible?C.accent:'#A4B3A9');
    if(visible){q.text=String(i+1);q.text.style={typeface:'Arial',fontSize:19,color:active?C.white:C.accent,
      alignment:'center',verticalAlignment:'middle',insets:0,wrap:'none',autoFit:'none'};}
  }
  const files=['planilha-editorial.png','relatorios-editorial.png','contexto-editorial.png'];
  const labels=compact?['Taxas','Relatórios','Contexto']:['Planilha de taxas','Relatórios e extratos','Contexto e exceções'];
  for(let i=0;i<Math.min(stage,3);i++){
    const [x,y]=p[i];
    const w=i===2?(compact?135:190):(compact?140:200);
    const h=i===2?(compact?88:104):(compact?110:163);
    const ay=i===2?(compact?499:491):(compact?235:167);
    await art(s,files[i],x-w/2,ay,w,h);
    txt(s,`front-label-${i+1}`,labels[i],x-145,i===2?y+33:(compact?213:125),290,34,labelSize,{align:'center',color:C.muted});
  }
  if(stage>=3){
    txt(s,'helena','Helena',center[0]-104,center[1]-15,208,59,compact?36:40,{color:C.accent,align:'center'});
  }
  return {center};
}
async function opening(s,n,input) {
  if(n===0){
    await brand(s,input,88,236,466);
    txt(s,'cover-subtitle','Fechamento financeiro\nda Tarvo',88,372,570,125,43);
    txt(s,'cover-period','Setembro de 2026',88,604,530,39,24,{color:C.muted});
    await art(s,'dossie-editorial.png',760,181,411,418);
  } else if(n===1||n===2){
    txt(s,'client-introduction','Essa é a',88,181,510,48,29,{color:C.muted});
    txt(s,'tarvo-identification','Tarvo',88,240,550,120,88);
    if(n===1) await art(s,'dossie-editorial.png',780,245,355,357);
    else {
      txt(s,'opening-title','3 frentes que\nnão se conectam',88,406,565,150,47,{color:C.accent});
      await triangle(s,0);
    }
  } else if(n===3){
    const q=txt(s,'opening-title','Planilha com\ntaxas e condições\nde cada lojista',88,228,580,245,48);
    q.text.get('Planilha').fill=C.accent;q.text.get('cada lojista').fill=C.accent;
    await triangle(s,1);
  } else if(n===4){
    const q=txt(s,'opening-title','O que foi cobrado?',88,269,565,100,48);
    q.text.get('cobrado').fill=C.accent;
    await triangle(s,2);
  } else if(n===5){
    headline(s,'Entre pontas,','uma única pessoa',580,{y:230});
    await triangle(s,3);
  } else if(n>=6&&n<=8){
    headline(s,'No fim do mês');
    const {center}=await triangle(s,3,true);
    const labels=['Quanto pode faturar','O que precisa corrigir','Quais valores continuam\npendentes'];
    for(let i=0;i<n-5;i++) txt(s,`closing-question-${i+1}`,labels[i],710,323+i*113,492,i===2?95:60,35,
      {color:i===n-6?C.accent:C.muted});
    const target=348+(n-6)*113;
    curve(s,'join-to-question',center[0]+117,center[1]+13,684,target,{color:C.accent,width:1.5});
    circle(s,'question-anchor',684,target,3.2,C.accent,C.accent);
  } else if(n===9){
    txt(s,'days','8',88,160,205,220,174,{color:C.accent});
    txt(s,'duration','dias úteis',313,194,820,83,59);
    txt(s,'duration-meaning','para fechar o mês',315,290,820,67,40,{color:C.muted});
    txt(s,'incorrect-charges','Espaço para\ncobranças incorretas',88,477,510,110,32);
    txt(s,'tacit-dependency','Fechamento dependente\nde quem conhece as regras',683,477,525,110,32);
    txt(s,'baseline','Prazo relatado no case',88,649,730,30,18,{color:C.muted});
  } else if(n===10){
    headline(s,'Cada operação','precisa da regra certa',630);
    await art(s,'contrato-vigencia-editorial.png',785,289,352,326);
    txt(s,'what-question','O que tem?',704,169,218,46,28);
    txt(s,'what-context','Taxa e condição',704,222,218,37,21,{color:C.muted});
    txt(s,'origin-question','De onde veio?',997,169,224,46,28);
    txt(s,'origin-context','Fonte e vigência',997,222,224,37,21,{color:C.muted});
    curve(s,'condition-link',816,269,893,320);
    curve(s,'origin-link',1108,269,1080,492);
    circle(s,'origin-anchor',1080,492,2.5,C.accent,C.accent);
    txt(s,'operation-label','Operação',824,631,292,40,27,{color:C.accent,align:'center'});
  }
}

async function processing(s,n) {
  const stage=n-15;
  const first=['Apura o checkout','Apura as remessas','Classifica os movimentos'];
  const second=['pela condição contratada','pelo spread realizado','bancários'];
  headline(s,first[stage],second[stage],810);
  await art(s,'apuracao-frentes-editorial-v2.png',88,333,1104,248);
  if(stage<2){
    const x=stage===0?485:808;
    s.shapes.add({geometry:'rect',name:'future-streams',position:{left:x,top:313,width:1280-x,height:350},fill:C.canvas,line:{fill:'none',width:0}});
  }
  const xs=[260,662,1055];
  const names=['Checkout','Remessas','Bancos'];
  const details=['Comissão contratada\nComparação de taxas','50% do spread elegível\nDuplicidades e contestação','Conta proposta\nJustificativa e origem'];
  for(let i=0;i<=stage;i++){
    txt(s,`stream-${i}`,names[i],xs[i]-166,592,332,40,27,{color:i===stage?C.accent:C.muted});
    txt(s,`stream-detail-${i}`,details[i],xs[i]-166,632,332,64,21,{color:C.muted});
  }
}
async function continuation(s,n,input) {
  if(n===11){
    await brand(s,input,88,246,481);
    txt(s,'solution-entry','Fechamento financeiro da Tarvo',88,378,645,62,32,{color:C.muted});
    await art(s,'dossie-editorial.png',795,196,389,405);
  } else if(n===12){
    const q=txt(s,'definition','Um gerenciador inteligente\ndo fechamento financeiro\nda Tarvo',88,133,735,212,47);
    q.text.get('gerenciador inteligente').fill=C.accent;
    txt(s,'definition-detail','Reúne os arquivos e as regras da operação.\nApura comissões, confere cobranças e\norganiza as pendências para o financeiro.',88,415,727,157,28,{color:C.muted});
    await art(s,'dossie-editorial.png',840,265,347,354);
  } else if(n===13){
    headline(s,'Recebe os arquivos','como chegam');
    const values=[['Orbe e ajustes','CSV'],['E-mail da Ponte','XLSX no anexo'],['Taxas e plano de contas','XLSX / CSV'],['Dois bancos','CSV / OFX']];
    for(let i=0;i<values.length;i++){
      const y=318+i*81;
      txt(s,`source-${i}`,values[i][0],135,y,450,38,28);
      txt(s,`source-format-${i}`,values[i][1],135,y+39,450,29,18,{mono:true,color:C.muted});
      curve(s,`source-link-${i}`,570,y+27,790,470);
    }
    await art(s,'dossie-editorial.png',806,301,347,346);
    txt(s,'unified-files','Arquivos preservados',803,650,350,35,23,{align:'center',color:C.accent});
  } else if(n===14){
    headline(s,'Liga cada operação','à condição aplicável');
    const items=[['Lojista','Identidade confirmada'],['Contrato e vigência','Condição válida na data'],['Orientação do financeiro','Fonte e confirmação']];
    for(let i=0;i<items.length;i++){
      const y=316+i*99;
      txt(s,`condition-${i}`,items[i][0],104,y,500,43,29);
      txt(s,`condition-detail-${i}`,items[i][1],104,y+45,500,35,22,{color:C.muted});
      curve(s,`match-link-${i}`,605,y+28,795,457);
    }
    await art(s,'contrato-vigencia-editorial.png',820,290,350,328);
    txt(s,'unconfirmed','Informação sem confirmação permanece pendente.',88,650,1040,36,24,{color:C.muted});
  } else if(n>=15&&n<=17){
    await processing(s,n);
  } else if(n===18){
    headline(s,'Reúne os resultados','do fechamento');
    for(const [i,label] of ['Checkout','Remessas','Bancos'].entries()){
      txt(s,`input-${i}`,label,111,331+i*109,281,49,30,{color:C.muted});
      curve(s,`convergence-${i}`,332,355+i*109,515,468);
    }
    await art(s,'dossie-editorial.png',523,336,250,270);
    line(s,'dossier-to-output',781,468,828,468,{arrow:true,color:C.accent});
    txt(s,'deliverables','Comissões\nDivergências\nNotas a emitir\nLançamentos classificados\nPendências\nRastro',855,315,365,302,27);
    txt(s,'invoice-state','Notas propostas para revisão',88,650,1040,36,24,{color:C.muted});
  } else if(n===19){
    headline(s,'Cada valor aponta','para a origem');
    const xs=[208,501,794,1087];
    const files=['dossie-editorial.png','planilha-editorial.png','contrato-vigencia-editorial.png','relatorios-editorial.png'];
    const titles=['Resultado','Operações','Regra','Arquivo'];
    const details=['Total apresentado','Linhas que\ncompõem o valor','Condição e\nvigência aplicadas','Referência exata\nda fonte'];
    for(let i=0;i<4;i++){
      await art(s,files[i],xs[i]-94,351,188,176);
      txt(s,`trace-title-${i}`,titles[i],xs[i]-118,562,236,43,28,{color:i===0?C.accent:C.ink,align:'center'});
      txt(s,`trace-detail-${i}`,details[i],xs[i]-130,611,260,71,21,{color:C.muted,align:'center'});
      if(i<3)line(s,`trace-link-${i}`,xs[i]+112,443,xs[i+1]-112,443,{arrow:true});
    }
  } else if(n===20){
    headline(s,'Rota Global');
    txt(s,'case-status','Diferença líquida preparada para revisão',88,216,1070,45,28,{color:C.muted});
    txt(s,'case-total','R$ 1.546,28',88,320,650,109,78,{color:C.accent});
    txt(s,'positive-component','+ R$ 1.644,72',88,491,300,47,31,{color:C.accent});
    txt(s,'positive-meaning','diferenças positivas',377,496,350,42,25,{color:C.muted});
    txt(s,'negative-component','− R$ 98,44',88,549,300,47,31);
    txt(s,'negative-meaning','abatimentos por estornos',377,554,365,42,25,{color:C.muted});
    txt(s,'operation','Operação TX88423647',805,319,410,43,25);
    txt(s,'contract-rate','3,59%',805,386,160,55,39);
    txt(s,'contract-caption','contratados',984,402,232,37,24,{color:C.muted});
    txt(s,'applied-rate','4,09%',805,449,160,55,39);
    txt(s,'applied-caption','aplicados',984,465,232,37,24,{color:C.muted});
    txt(s,'line-difference','R$ 66,28',805,524,410,62,42,{color:C.accent});
    txt(s,'line-meaning','de diferença nesta linha',805,586,410,39,24,{color:C.muted});
    txt(s,'source','Orbe, linha 749. Taxas vigentes da Rota Global.',88,650,1055,35,20,{color:C.muted});
  }
}

export async function reviseFullEditorialDeck({presentation,input}) {
  const selected=input.indices;
  if(!Array.isArray(selected)||!selected.length)throw new Error('Escolha explicitamente os avanços a revisar.');
  for(const n of selected){
    if(n<0||n>20||presentation.slides.getItem(n).id!==ids[n])throw new Error(`Reinspecionar a ordem do avanço ${n}.`);
    const foreign=presentation.slides.getItem(n).images.items.filter(i=>!i.alt?.startsWith('Lastro:')&&!['Marca Lastro'].includes(i.alt));
    if(foreign.length)throw new Error(`Imagem adicionada ao avanço ${n}; preservar e revisar antes de substituir.`);
  }
  for(const n of selected){
    const s=presentation.slides.getItem(n);
    for(const image of [...s.images.items])image.delete();
    s.shapes.deleteAll();
    await frame(s,n,input);
    if(n<=10)await opening(s,n,input);else await continuation(s,n,input);
  }
  return {revised:selected,count:presentation.slides.items.length};
}
