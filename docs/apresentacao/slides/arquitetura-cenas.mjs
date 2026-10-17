import { palette as C } from './abertura.mjs';

// Historical study from baa2d59, rejected in visual review.
// Current composition: arquitetura-editorial.mjs. Do not restore this study.

// Native editable conceptual diagrams. No application screen or model execution
// is simulated. Only the five explicitly selected architecture slides are edited.
const indices = [21, 22, 23, 24, 25];
const expectedIds = ['xjvl9k', 'nnexnc', 'r7ayvv', 'hwv1w4', '93k4rm'];

function shape(s, name, geometry, x, y, w, h, fill = 'none', stroke = 'none', weight = 0) {
  return s.shapes.add({ name, geometry, position: { left: x, top: y, width: w, height: h },
    fill, line: { style: 'solid', fill: stroke, width: weight } });
}
function text(s, name, value, x, y, w, h, size, options = {}) {
  const q = shape(s, name, 'textbox', x, y, w, h);
  q.text = value;
  q.text.style = { typeface: 'Arial', fontSize: size, color: options.color || C.ink,
    bold: options.bold || false, alignment: options.align || 'left', verticalAlignment: 'top',
    autoFit: 'none', wrap: 'none', insets: 0 };
  return q;
}
function line(s, name, x1, y1, x2, y2, options = {}) {
  return s.shapes.add({ geometry: 'connector', kind: 'straight', name,
    position: { left: Math.min(x1, x2), top: Math.min(y1, y2), width: Math.abs(x2-x1), height: Math.abs(y2-y1) },
    line: { style: options.dash ? 'dashed' : 'solid', fill: options.color || C.accent, width: options.width || 2.5 },
    ...(options.arrow ? { tail: { type: 'triangle', width: 'sm', length: 'sm' } } : {}),
    ...(options.both ? { head: { type: 'triangle', width: 'sm', length: 'sm' }, tail: { type: 'triangle', width: 'sm', length: 'sm' } } : {}) });
}
function plane(s, name, x, y, w, h, fill) {
  return s.shapes.add({geometry:'custom', name,
    position:{left:x,top:y,width:w,height:h},fill,line:{fill:C.accent,width:1.5},
    customPaths:[{width:w,height:h,commands:[
      {moveTo:{x:0,y:h*.43}},{lineTo:{x:w*.68,y:0}},
      {lineTo:{x:w,y:h*.57}},{lineTo:{x:w*.32,y:h}},{close:{}}
    ]}]});
}
function panel(s, n, title, question, support) {
  s.background.fill = C.canvas;
  shape(s, 'spoken-focus', 'rect', 0, 0, 414, 720, C.accent);
  text(s,'section','Arquitetura\nagêntica',44,52,330,90,31,{color:C.white});
  text(s,'spoken-stage',title,44,226,350,100,60,{color:C.white,bold:true});
  text(s,'spoken-question',question,44,351,332,150,31,{color:C.white});
  text(s,'spoken-support',support,44,578,332,78,23,{color:'#D4E8DF'});
  text(s,'page',String(n),1194,665,40,26,18,{align:'right',color:C.muted});
}
function packet(s) {
  const doc = shape(s,'rota-case','flowChartDocument',470,218,296,362,C.white,C.accent,2);
  text(s,'case-name','ROTA GLOBAL',492,240,250,34,22,{bold:true,color:C.accent});
  text(s,'case-amount','R$ 1.546,28',492,282,252,62,40,{bold:true});
  text(s,'case-state','Diferença líquida\npara revisão',492,345,252,72,25);
  line(s,'case-divider',492,432,742,432,{color:C.border,width:1});
  text(s,'example-id','Exemplo: TX88423647',492,445,252,29,20,{color:C.muted});
  text(s,'example-contract','3,59% contratados',492,482,252,32,24,{bold:true});
  text(s,'example-source','Orbe, linha 749',492,520,252,28,21,{color:C.muted});
  // The lower planes describe provenance/dependency, not execution order.
  plane(s,'trace-base',470,637,296,34,C.soft);
  plane(s,'calculation-base',470,612,296,34,'#C8DED1');
  text(s,'foundation-label','Apuração e rastro',470,679,296,29,23,{bold:true,align:'center'});
  line(s,'packet-from-calculation',618,577,618,609,{color:C.accent});
  return doc;
}
function actor(s, key, symbol, title, x, active) {
  const q = shape(s,key,'ellipse',x,250,96,96,active?C.accent:C.soft,active?C.accent:C.border,2);
  q.text=symbol;
  q.text.style={typeface:'Arial',fontSize:48,bold:true,color:active?C.white:C.accent,
    alignment:'center',verticalAlignment:'middle',insets:0,autoFit:'none',wrap:'none'};
  text(s,`${key}-label`,title,x-47,365,190,42,25,{bold:true,align:'center'});
  return q;
}
function investigation(s, stage) {
  actor(s,'investigator','I','Investigador',846,stage===23);
  line(s,'packet-to-investigator',766,298,846,298,{arrow:true});
  text(s,'packet-link-label','caso',781,261,64,28,19,{color:C.muted});
  shape(s,'registered-sources','flowChartDocument',812,505,163,98,C.soft,C.border,1.5);
  text(s,'sources-label','Fontes\ncadastradas',826,519,135,65,24,{align:'center'});
  line(s,'read-tools',894,411,894,501,{both:true});
  text(s,'read-label','consulta',800,446,88,27,19,{color:C.muted});
  text(s,'evidence-label','evidências',906,446,105,27,19,{color:C.muted});
}
function critic(s, stage) {
  actor(s,'critic','C','Crítico',1102,stage===24);
  line(s,'investigator-to-critic',942,298,1102,298,{arrow:true});
  text(s,'review-material','interpretação\n+ evidências',960,327,138,56,20,{align:'center',color:C.muted});
  line(s,'same-packet-up',618,158,618,216,{dash:true,color:C.muted,width:1.5});
  line(s,'same-packet-across',618,158,1150,158,{dash:true,color:C.muted,width:1.5});
  line(s,'same-packet-down',1150,158,1150,248,{dash:true,arrow:true,color:C.muted,width:1.5});
  text(s,'same-packet-label','mesmo pacote do caso',814,113,290,34,23,{color:C.muted,align:'center'});
}
function foundation(s) {
  s.background.fill=C.canvas;
  shape(s,'architecture-chapter','rect',0,0,556,720,C.accent);
  text(s,'architecture-title','Arquitetura\nagêntica.',44,165,490,200,72,{bold:true,color:C.white});
  text(s,'architecture-premise','A investigação parte\nde um valor apurado.',44,437,470,115,35,{color:C.white});
  const rows=[['Fontes',496,C.soft],['Regras',363,'#C8DED1'],['Apuração',230,C.accent]];
  for(const [label,y,fill] of rows){
    plane(s,`foundation-${label}`,665,y,474,130,fill);
    text(s,`label-${label}`,label,785,y+43,240,43,31,{bold:true,align:'center',color:label==='Apuração'?C.white:C.ink});
  }
  text(s,'foundation-meaning','Dependências da apuração',665,655,480,34,23,{color:C.muted,align:'center'});
  text(s,'page','21',1194,665,40,26,18,{color:C.muted,align:'right'});
}
function scene(s, n) {
  if(n===21){foundation(s);return;}
  const labels={
    22:['O caso.','O que chega\naos agentes?','Valor, contexto\ne referência de origem.'],
    23:['Investigar.','Como o agente\nbusca contexto?','Ferramentas de leitura\nsobre fontes cadastradas.'],
    24:['Criticar.','O que sustenta\na interpretação?','O crítico examina\no material recebido.'],
    25:['Decidir.','Helena recebe\no caso e o parecer.','Cálculo preservado.\nParecer experimental.']
  };
  panel(s,n,...labels[n]);
  packet(s);
  if(n===22){
    line(s,'amount-callout',766,310,836,310,{width:2});
    text(s,'amount-annotation','Valor apurado',858,278,350,49,34,{bold:true});
    text(s,'amount-annotation-detail','Composição conferível',858,330,350,50,26,{color:C.muted});
    line(s,'source-callout',766,497,836,497,{width:2});
    text(s,'origin-annotation','Regra e origem',858,446,350,50,34,{bold:true});
    text(s,'origin-annotation-detail','Condição contratada\ne linha do arquivo',858,503,350,85,26,{color:C.muted});
  }
  if(n>=23) investigation(s,n);
  if(n>=24) critic(s,n);
  if(n===25){
    line(s,'critic-to-human',1150,407,1150,501,{arrow:true});
    text(s,'human-input','parecer',1166,450,95,28,20,{color:C.muted});
    shape(s,'human-decision','rect',1035,505,198,98,C.accent);
    text(s,'human-name','Helena',1048,528,172,49,37,{color:C.white,bold:true,align:'center'});
    text(s,'human-role','Decisão financeira',1015,620,237,38,24,{align:'center'});
  }
}

export async function reviseArchitectureScenes({presentation,input}) {
  const selected = input.indices || indices;
  for(const n of selected){
    if(!indices.includes(n)) throw new Error(`Slide ${n} fora do trecho de revisão.`);
    const s=presentation.slides.getItem(n);
    if(s.id!==expectedIds[n-21]) throw new Error(`A ordem do slide ${n} mudou; reinspecionar antes de editar.`);
    if(s.images.items.length) throw new Error(`Slide ${n} ganhou imagens; preservar e revisar a edição manual.`);
  }
  for(const n of selected){
    const s=presentation.slides.getItem(n);
    s.shapes.deleteAll();
    scene(s,n);
    const marker='\n\nDireção visual revisada: cenas progressivas do Canva Sprint 5 (DAHXPa49m0k) e abstrações estudadas na Barte. Composição própria do Lastro. Diagrama conceitual editável, sem simular interface ou execução de modelo. O caso Rota mantém os dados do pacote publicado em b43e80e. Camadas representam dependências, não ordem de chamadas. O crítico recebe as evidências, sem nova consulta de ferramentas. Para Rota, a responsável é Helena; outros casos podem exigir o Comercial.';
    if(!s.speakerNotes.text.includes('Direção visual revisada:')) s.speakerNotes.text += marker;
  }
  return {revised:selected,total:presentation.slides.items.length};
}
