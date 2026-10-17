import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {palette as C} from './abertura.mjs';
const dir=path.dirname(fileURLToPath(import.meta.url));
const repo='https://github.com/DavidDeodato/Hackathon_barte/blob/0cc8d320fb80828744a80f6d6d13e1b1f6ad18eb/';
const crops={'dossie-editorial.png':{left:.1878,top:.0258,right:.1153,bottom:.0295},'contrato-vigencia-editorial.png':{left:.241,top:.081,right:.1354,bottom:.0488}};
export const evidenceAdvances=[
 [26,'Comissão de checkout','RESULTADOS','O checkout de setembro soma R$ 203.735,34 de comissão contratada. Inclui os ajustes tardios e continua sujeito à revisão do financeiro.','saida/comissoes_por_lojista.csv'],
 [27,'Comissão de remessas','RESULTADOS','A participação da Tarvo nas remessas é R$ 39.543,45. É comissão a receber. O recebimento da Ponte ainda precisa ser conferido.','saida/comissoes_por_lojista.csv'],
 [28,'Notas propostas','RESULTADOS','As 21 notas propostas somam R$ 243.284,29. A comissão negativa de R$ 5,50 da Casa não gera nota. Atlas segue sem taxa confirmada. Estas notas não foram emitidas.','saida/notas_a_emitir.csv'],
 [29,'Diferenças Orbe','VALORES EM REVISÃO','Há R$ 1.576,23 de diferenças líquidas a revisar com a Orbe. Rota contribui com R$ 1.546,28 e outra pendência com R$ 29,95. Os rascunhos não foram enviados.','saida/pendencias.csv'],
 [30,'Diferenças Ponte','VALORES EM REVISÃO','O excesso de spread ao lojista soma R$ 1.418,85. A contestação usa o valor integral. A comissão realizada da Tarvo continua separada. Um ajuste é reconhecido na competência em que ocorrer.','saida/divergencias_taxa.csv'],
 [31,'Devolução Casa','VALORES EM REVISÃO','A Casa tem R$ 15.397,42 em diferenças líquidas durante a isenção. A destinação é devolução ao lojista após decisão de Helena e Comercial. Este caso não deve virar cobrança contra a Orbe. CAN-22 registra que Casa e Mundo não tinham sido avisadas aos parceiros; não havia responsável fixo por essa comunicação. Essa lacuna de processo ajuda a explicar o erro além da fragmentação dos arquivos.','saida/pendencias.csv'],
 [32,'Ajustes tardios','SETEMBRO ATUALIZADO','Os 14 ajustes recebidos reduzem a comissão de checkout e as notas propostas em R$ 3.304,39. Foram incorporados à mesma competência. As demais frentes mantêm seus totais.','README.md'],
 [33,'Conferência do rastro','PROVA DOS NÚMEROS','O relatório registra 490 comparações entre valor de saída e soma do rastro, sem diferença. São 35 comissões, 233 divergências, 21 notas, 184 movimentos e 17 pendências. Isso prova consistência interna e não equivale ao gabarito da banca.','saida/reconciliacao.json'],
 [34,'Demo: abrir fechamento','DEMONSTRAÇÃO','A analista abre setembro e confere o estado de revisão. As comissões, as pendências e os seis arquivos ficam disponíveis. Mostrar a execução escolhida antes de abrir um caso.','web/src/App.tsx'],
 [35,'Demo: origem do valor','DEMONSTRAÇÃO','Em Pendências, abrir a diferença de R$ 1.546,28 da Orbe e clicar em Conferir rastro desta saída. São 87 componentes. Localizar TX88423647: R$ 66,28, linha 749 da Orbe. O slide 20 mostra as taxas desse registro.','saida/rastro.csv'],
 [36,'Demo: revisão do caso','DEMONSTRAÇÃO','Abrir Investigação, escolher caso para revisão e selecionar Rota. Conferir pacote, fontes e responsável. A captura usa consulta sem IA. Se optar por revisão assistida, confirmar o modo real, acompanhar as evidências e explicar o estado recebido.','web/src/CaseWorkspace.tsx'],
 [37,'Falha: taxa desconhecida','LIMITES DA SOLUÇÃO','Na Atlas, a taxa comercial não está confirmada. R$ 262.138,61 é volume bruto das linhas retidas, não comissão perdida. O Comercial confirma a condição e Helena revisa. Até lá, as origens ficam preservadas e o faturamento da taxa permanece pendente.','saida/pendencias.csv'],
 [38,'Direção da IA','COMO CONSTRUÍMOS','A IA sugeriu uma pergunta genérica sobre revisão após ajustes. O participante rejeitou porque não mudava a implementação. A investigação passou a buscar uma ambiguidade concreta em uma operação identificada.','PROMPTS/SESSAO_001.md'],
 [39,'Pergunta enviada','PERGUNTAR ANTES DE ASSUMIR','David perguntou qual data determina a isenção da antecipação da Casa. Usou AN88445172 como exemplo: antecipação em 09/09 sem vínculo com as vendas originais. A dúvida era se essas vendas precisavam ser localizadas antes de calcular.','contexto/PERGUNTA_DAVID_CASA.md'],
 [40,'Resposta do financeiro','REGRA CONFIRMADA','Manuel, no papel de Helena, respondeu a David às 13h34: vale a data da antecipação. O serviço prestado em setembro está dentro da isenção e não exige buscar as vendas originadoras para essa tarifa.','contexto/PERGUNTA_DAVID_CASA.md'],
 [41,'Efeito no cálculo','REGRA APLICADA','AN88445172, em 09/09, aparece com taxa esperada zero e comissão R$ 0,00 no resultado publicado. A resposta confirma o tratamento que o motor já aplica. Estornos de vendas continuam respeitando a venda original.','saida/detalhes.json'],
 [42,'Premissa declarada','HIPÓTESES','A tolerância de remessas é uma escolha metodológica do time: reportar diferença absoluta superior a 0,01 ponto percentual. O cliente autorizou justificar o critério. Essa tolerância não muda a comissão realizada.','HIPOTESES.md'],
 [43,'Outubro: arquivos','PRÓXIMA COMPETÊNCIA','A analista começa por Documentos, escolhe ou cria a competência e envia os novos arquivos. Confere as fontes selecionadas antes de processar. Um conjunto vazio permanece sem apuração. Não há fechamento real de outubro demonstrado.','web/src/components/documents/DocumentsWorkspace.tsx'],
 [44,'Outubro: Atlas','CONTINUIDADE','Quando o Comercial confirmar a taxa válida desde 10/09, a orientação é faturar setembro junto com outubro. Preservar a origem das linhas pendentes faz parte do processo. O acompanhamento automático entre competências ainda precisa ser validado.','contexto/RESPOSTAS_FINANCEIRO.md'],
 [45,'Outubro: trânsito','CONTINUIDADE','A transferência de R$ 300 mil saiu do Aurora em 30/09 e exige conferência do crédito de 01/10 no Meridiano. O Lastro mantém a pendência identificada em setembro. O crédito de outubro não está nos arquivos de setembro.','saida/pendencias.csv'],
 [46,'Um mês: competência','PLANO DE DESENVOLVIMENTO','Nas primeiras duas semanas, validar um lote real de outubro e o acompanhamento de pendências de setembro. A prova esperada é comparar saldos, fontes e decisões nos dois períodos com a analista. Esse é um plano, não uma funcionalidade comprovada.','docs/apresentacao/roteiro.md'],
 [47,'Um mês: qualidade da IA','PLANO DE DESENVOLVIMENTO','Na terceira semana, comparar investigador sozinho e investigador com crítico sobre os mesmos casos. Medir interpretações erradas, fontes pertinentes e pedidos corretos de evidência com revisão humana. Não presumir que adicionar um crítico melhora a resposta.','src/tarvo/agents/case_review.py'],
 [48,'Um mês: esforço de revisão','PLANO DE DESENVOLVIMENTO','Na quarta semana, medir tempo por caso, retrabalho e correções com o financeiro. Os oito dias úteis da abertura são uma estimativa do processo atual. A economia atribuída ao Lastro ainda precisa ser medida.','contexto/RESPOSTAS_FINANCEIRO.md'],
 [49,'Fechamento com evidências','LASTRO','O Lastro prepara o fechamento com valores rastreáveis e decisões identificadas. A analista pode conferir a origem e encaminhar o que depende de confirmação. A aprovação financeira continua com Helena.','README.md'],
];
function text(s,name,value,x,y,w,h,size=27,opt={}){
 const a=s.shapes.add({geometry:'textbox',name,position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 a.text=value;a.text.style={typeface:opt.mono?'Liberation Mono':'Arial',fontSize:size,color:opt.color||C.ink,bold:false,alignment:opt.align||'left',verticalAlignment:'top',autoFit:'none',wrap:'none',insets:0};return a;
}
function line(s,name,x1,y1,x2,y2,opt={}){return s.shapes.add({geometry:'connector',kind:'straight',name,position:{left:x1,top:y1,width:x2-x1,height:y2-y1},line:{fill:opt.color||C.border,width:1.3},...(opt.arrow?{tail:{type:'triangle',width:'sm',length:'sm'}}:{})});}
async function art(s,file,x,y,w,h,opt={}){
 const b=await fs.readFile(path.join(dir,'assets',file));const jpeg=file.endsWith('.jpg');
 s.images.add({contentType:jpeg?'image/jpeg':'image/png',dataUrl:`data:image/${jpeg?'jpeg':'png'};base64,${b.toString('base64')}`,alt:`Lastro: arquivo original ${file}, ${jpeg?'captura real da consulta local às saídas publicadas, sem nova apuração':'ilustração conceitual original'}`,fit:'contain',crop:opt.crop||crops[file],position:{left:x,top:y,width:w,height:h}});
}
function headline(s,a,b='',w=1104){text(s,'evidence-heading',a,88,133,w,73,50);if(b)text(s,'evidence-heading-second',b,88,199,w,73,50,{color:C.accent});}
function foot(s,value){text(s,'evidence-qualifier',value,88,650,1050,39,20,{color:C.muted});}
const money=x=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(x));
async function metric(s,n,f){
 const data={
 26:['Comissão de checkout','apurada em setembro',f.checkout,'Condição contratada\npor operação','comissões por lojista'],
 27:['Comissão de remessas','apurada em setembro',f.remessa,'50% do spread\nrealizado elegível','comissão a receber'],
 28:['Notas propostas','para revisão do financeiro',f.invoices,'21 notas\npreparadas','documentos fiscais ainda não emitidos'],
 29:['Diferenças líquidas','a revisar com a Orbe',f.orbe_difference,'Rota: R$ 1.546,28\nOutro caso: R$ 29,95','rascunhos de contestação não enviados'],
 30:['Excesso de spread','a revisar com a Ponte',f.ponte_difference,'Valor integral\ncobrado ao lojista','contestação separada da comissão realizada'],
 31:['Devolução da Casa','aguarda decisão',f.casa_refund,'Helena e Comercial revisam\nIsenção não comunicada ao parceiro','devolução ao lojista; sem cobrança contra a Orbe'],
 }[n];
 headline(s,data[0],data[1]);text(s,'financial-value',money(data[2]),88,331,850,118,78,{color:C.accent});
 text(s,'financial-meaning',data[3],88,496,820,104,30,{color:C.muted});
 await art(s,n===27?'relatorios-editorial.png':n===31?'contrato-vigencia-editorial.png':'dossie-editorial.png',953,327,225,268);
 foot(s,'Setembro/2026 · '+data[4]);
}
async function demo(s,n){
 const spec={34:['A analista abre','o fechamento de setembro','fechamento.jpg','Competência escolhida\nRevisão pendente\nSeis arquivos'],35:['Confere o valor','até a linha de origem','rastro-rota.jpg','Rota Global\n87 componentes\nOrbe, linha 749'],36:['Abre o caso','com suas evidências','mesa-rota.jpg','Valor e natureza\nFontes do pacote\nResponsável'],37:['Atlas aguarda','a condição comercial','atlas.jpg','Taxa desconhecida\nComercial + Helena\nFaturamento pendente'],43:['Em outubro, começa','pelos novos arquivos','outubro.jpg','Competência\nConjunto de documentos\nSeleção de fontes']}[n];
 const compact={34:['A analista abre','o fechamento\nde setembro'],35:['Confere o valor','até a linha\nde origem'],36:['Abre o caso','com suas\nevidências'],37:['Atlas aguarda','a condição\ncomercial'],43:['Em outubro,','novos arquivos']}[n];
 text(s,'evidence-heading',compact[0],88,133,318,65,43);
 text(s,'evidence-heading-second',compact[1],88,195,318,126,43,{color:C.accent});
 text(s,'demo-guidance',spec[3],88,341,316,168,27,{color:C.muted});
 await art(s,'demo/'+spec[2],428,180,764,440,{crop:[34,35,37].includes(n)?{left:0,top:0,right:.23,bottom:.235}:undefined});
 foot(s,n===43?'Interface real · conjunto vazio, sem apuração de outubro':n===36?'Interface real · consulta documental sem IA e sem aprovação financeira':'Interface real · consulta às saídas publicadas, sem nova apuração');
 if(n===37)text(s,'atlas-amount-boundary','Volume conhecido.\nComissão desconhecida.',88,551,318,89,24,{color:C.accent});
}
function timeline(s,n){
 headline(s,n===44?'A taxa da Atlas':'A transferência de setembro',n===44?'depende de confirmação':'continua em trânsito');
 text(s,'period-september','SETEMBRO',88,343,440,35,18,{mono:true,color:C.muted});
 text(s,'period-october','OUTUBRO',795,343,400,35,18,{mono:true,color:C.accent});
 line(s,'period-link',408,451,746,451,{arrow:true,color:C.accent});
 text(s,'pending-source',n===44?'Linhas preservadas\nTaxa a confirmar':'R$ 300.000,00\nSaída em 30/09',88,405,380,107,34);
 text(s,'next-action',n===44?'Comercial confirma\nHelena revisa':'Conferir crédito\nem 01/10',795,405,400,107,34,{color:C.accent});
 foot(s,n===44?'Orientação do cliente · acompanhamento entre competências a validar':'Crédito de outubro ainda não comprovado nos arquivos de setembro');
}
async function plan(s,n){
 const info={46:['Validar a próxima','competência','Semanas 1 e 2','Lote real de outubro\nPendências de setembro\nSaldos e origens conferidos'],47:['Medir a qualidade','da investigação e da crítica','Semana 3','Mesmos casos para os dois modos\nRevisão humana das interpretações\nErros e evidências pertinentes'],48:['Medir o esforço','do financeiro','Semana 4','Tempo por caso\nRetrabalho e correções\nEsforço para concluir o mês']}[n];
 headline(s,info[0],info[1]);await art(s,'contrato-vigencia-editorial.png',94,334,300,278);
 text(s,'plan-week',info[2],516,334,680,58,34,{color:C.accent});
 text(s,'plan-validation',info[3],516,424,680,145,29,{color:C.muted});
 foot(s,'Plano para mais um mês · benefícios ainda sujeitos à medição');
}
async function content(s,n,f){
 if(n<=31)return metric(s,n,f);
 if([34,35,36,37,43].includes(n))return demo(s,n);
 if([44,45].includes(n))return timeline(s,n);
 if(n>=46&&n<=48)return plan(s,n);
 if(n===32){headline(s,'Os ajustes tardios','entram no mesmo fechamento');text(s,'adjustment-value','− R$ 3.304,39',88,331,925,115,78,{color:C.accent});text(s,'adjustment-count','14 registros adicionais',88,496,680,52,31);text(s,'adjustment-scope','Efeito nas comissões de checkout\ne nas notas propostas',88,558,860,80,27,{color:C.muted});await art(s,'relatorios-editorial.png',966,340,226,233);foot(s,'Setembro/2026 atualizado · demais frentes mantêm seus totais');}
 else if(n===33){headline(s,'O total confere','com os componentes de origem');text(s,'checks','490',88,322,414,145,106,{color:C.accent});text(s,'checks-meaning','comparações registradas\nsem diferença de soma',441,355,741,102,33);text(s,'scope','35 comissões · 233 divergências · 21 notas\n184 movimentos · 17 pendências',88,543,1104,80,28,{color:C.muted});foot(s,'Consistência interna do rastro · não equivale à aprovação pelo gabarito');}
 else if(n===38){headline(s,'A IA propôs uma pergunta','que não mudava a solução');text(s,'bad-question','Revisar tudo ou só o que mudou\napós um ajuste tardio?',88,338,880,112,38,{color:C.muted});line(s,'correction-link',115,478,115,519,{arrow:true,color:C.accent});text(s,'human-correction','O participante rejeitou a proposta\ne exigiu uma dúvida que afetasse o cálculo.',88,548,1100,87,31,{color:C.accent});foot(s,'Histórico real · PROMPTS/SESSAO_001.md e conversa pública');}
 else if(n===39){headline(s,'David levou uma operação','à pergunta para o financeiro');text(s,'question','A isenção vale pela data da antecipação\nou pelas vendas que geraram os recebíveis?',88,337,1104,113,36);text(s,'operation','AN88445172',88,505,655,70,43,{color:C.accent});text(s,'operation-context','09/09 · vendas de origem sem referência',88,583,1000,44,26,{color:C.muted});foot(s,'Pergunta enviada · resposta para David transcrita pela participante');}
 else if(n===40){headline(s,'Helena confirmou','a data da antecipação');text(s,'answer','“Vale pela data da antecipação.”',88,354,1104,86,45,{color:C.accent});text(s,'answer-detail','Serviço prestado em setembro\nestá dentro da isenção.',88,476,710,102,32);await art(s,'contrato-vigencia-editorial.png',920,342,256,250);foot(s,'manuel.freitas, como Helena · resposta para David às 13h34');}
 else if(n===41){headline(s,'A operação de 09/09','tem comissão zerada');text(s,'zero-commission','R$ 0,00',88,331,700,117,86,{color:C.accent});text(s,'reference','AN88445172 · Orbe, linha 509',88,496,1040,52,30);text(s,'meaning','A resposta confirma o tratamento\njá presente no resultado publicado.',88,558,1030,87,29,{color:C.muted});foot(s,'Isenção da antecipação · estornos continuam ligados à venda original');}
 else if(n===42){headline(s,'A tolerância de remessas','é uma premissa do time');text(s,'threshold','0,01 p.p.',88,331,630,119,78,{color:C.accent});text(s,'threshold-rule','Alerta quando a diferença absoluta\né superior à tolerância.',88,498,1030,95,30);foot(s,'Critério escrito e justificado · não altera a comissão realizada');}
 else if(n===49){headline(s,'Fechamento preparado','com decisões identificadas');await art(s,'dossie-editorial.png',855,328,334,316);text(s,'handoff','Valores rastreáveis\nPendências com responsável',88,366,749,122,38,{color:C.accent});text(s,'approval','A aprovação financeira\ncontinua com Helena.',88,541,730,91,32,{color:C.muted});}
}
export async function buildEvidenceContinuation({presentation,input}){
 if(presentation.slides.items.length<26||presentation.slides.getItem(25).id!=='93k4rm')throw new Error('Reinspecionar o deck antes de continuar.');
 const f=JSON.parse(await fs.readFile(path.join(dir,'assets/evidencias-setembro.json'),'utf8'));
 const authored=[];
 for(const n of input.indices){
  const e=evidenceAdvances.find(e=>e[0]===n);if(!e)throw new Error('Avanço desconhecido '+n);
  if(n<presentation.slides.items.length){
   const existing=presentation.slides.getItem(n);
   if(!existing.shapes.items.some(x=>x.name==='evidence-heading'))throw new Error('Avanço existente externo a esta continuação; preservar e reinspecionar '+n);
   if(!input.repair)continue;
   if(existing.id!==input.expectedIds[n])throw new Error('Preservar edição do avanço '+n);
  }
  else if(n!==presentation.slides.items.length)throw new Error('Há lacuna antes do avanço '+n);
  const s=n<presentation.slides.items.length?presentation.slides.getItem(n):presentation.slides.add({width:1280,height:720});
  if(input.repair){s.shapes.deleteAll();for(const i of [...s.images.items])i.delete();}
  s.background.fill=C.canvas;
  s.images.add({svg:await fs.readFile(input.logoPath,'utf8'),alt:'Lastro: marca original',fit:'contain',position:{left:88,top:51,width:105,height:22}});
  text(s,'section',e[2],822,53,370,26,15,{mono:true,color:C.muted,align:'right'});text(s,'page',String(n),1160,667,32,26,16,{mono:true,color:C.muted,align:'right'});
  s.speakerNotes.text=e[3]+'\n\nFonte: '+(e[4]==='contexto/PERGUNTA_DAVID_CASA.md'?'contexto/PERGUNTA_DAVID_CASA.md, transcrição fornecida pela participante nesta revisão.':repo+e[4]);
  if(n>=34&&n<=37||n===43)s.speakerNotes.text+='\n\nCaptura real da aplicação local em 17/10/2026. Consulta aos seis CSVs publicados em 0cc8d32, com hashes conferidos. Não houve nova apuração financeira nem inferência paga. O roteiro da demo distingue consulta, processamento real com os originais e revisão assistida; nunca usar essa captura como prova de execução nova.';
  if(n>=46&&n<=48)s.speakerNotes.text+='\n\nPlano proposto, ainda não executado. Não promete redução de tempo ou ganho de qualidade medido.';
  await content(s,n,f);authored.push({n,id:s.id});
 }
 return {authored,count:presentation.slides.items.length};
}
