import { taskKey } from './model';
import type { AgentEvent, MissionTask } from './types';

/** Display-only translations of canonical status messages. Never mutates the event. */
export function presentEventSummary(event:AgentEvent):string {
  const key=event.summary.normalize('NFD').replace(/\p{M}/gu,'').toLowerCase().trim();
  const review:Record<string,string>={review_required:'Revisão concluída; pendências para análise.',needs_evidence:'A revisão aguarda evidências adicionais.',failed:'A revisão foi interrompida.',unavailable:'A revisão não está disponível.'};
  const reviewStatus=/^revisao encerrada em (review_required|needs_evidence|failed|unavailable); nenhuma aprovacao ou alteracao financeira\.$/.exec(key)?.[1];
  if(reviewStatus)return review[reviewStatus];
  const ended:Record<string,string>={completed:'Análise concluída.',needs_review:'Análise concluída; revisão pendente.',pending_review:'Preparação concluída; revisão pendente.',needs_evidence:'A análise aguarda evidências adicionais.',unavailable:'A análise não está disponível.',failed:'A análise foi interrompida.',blocked:'A análise precisa de revisão.'};
  const investigation=/^investigacao encerrada: (completed|needs_review|pending_review|needs_evidence|unavailable|failed|blocked)$/.exec(key)?.[1];
  if(investigation)return ended[investigation];
  const execution:Record<string,string>={failed:'A execução foi interrompida.',completed:'Preparação concluída.',pending_review:'Preparação concluída; revisão pendente.',blocked:'A execução aguarda resolução de uma pendência.',unavailable:'A execução não está disponível.'};
  const state=/^execucao encerrada: (failed|completed|pending_review|blocked|unavailable)$/.exec(key)?.[1];
  return state?execution[state]:event.summary;
}
export type TeamRoleId = 'automation' | 'case' | 'investigation' | 'investigator' | 'critic' | 'human' | 'unknown';
export interface TeamRole {
  id: TeamRoleId; name: string; monogram: string; category: string; stage: string;
  mission: string; skills: string[]; receives: string; delivers: string; trigger: string; source: string;
}
export const TEAM_ROLES: TeamRole[] = [
  { id:'automation',name:'Motor de fechamento',monogram:'MF',category:'Automação',stage:'Preparar',mission:'Transformar os documentos selecionados em uma preparação financeira rastreável.',skills:['Aplicar taxas e contratos','Conciliar movimentos','Preparar saídas e pendências'],receives:'Documentos e competência do conjunto selecionado.',delivers:'Cálculos, arquivos de saída e pendências para revisão.',trigger:'Processar uma seleção no fluxo de documentos.',source:'api/worker.py · finance/engine.py' },
  { id:'case',name:'Preparação do caso',monogram:'PC',category:'Automação',stage:'Contextualizar',mission:'Conferir o pacote do caso e a versão de suas fontes antes da revisão.',skills:['Preservar o pacote original','Conferir a versão das fontes','Organizar referências do caso'],receives:'Pacote do caso e fontes vinculadas à execução.',delivers:'Contexto verificado e eventual solicitação de revisão.',trigger:'Abrir uma revisão de caso pelo fluxo existente.',source:'agents/case_review.py · review_case' },
  { id:'investigation',name:'Investigação financeira',monogram:'IF',category:'Consulta e análise',stage:'Entender',mission:'Explicar uma dúvida a partir das fontes da execução.',skills:['Localizar transações e regras','Recuperar evidências','Distinguir proposta de decisão'],receives:'Pergunta e fontes vinculadas à execução.',delivers:'Resposta, referências e propostas sujeitas à autoridade responsável.',trigger:'Enviar uma pergunta no fluxo de investigação.',source:'agents/service.py · investigate' },
  { id:'investigator',name:'Investigador',monogram:'IN',category:'Papel assistido',stage:'Investigar',mission:'Examinar o caso e sustentar observações com referências.',skills:['Consultar o pacote do caso','Verificar fontes','Propor uma interpretação'],receives:'Pacote imutável do caso e fontes disponíveis.',delivers:'Observações, evidências e limitações; nenhuma aprovação.',trigger:'Solicitar revisão assistida de um caso.',source:'agents/case_review.py · _run_role(investigator)' },
  { id:'critic',name:'Crítico',monogram:'CR',category:'Papel assistido',stage:'Contrapor',mission:'Questionar a interpretação e procurar evidências que a limitem.',skills:['Buscar contraprovas','Verificar alcance da regra','Identificar lacunas'],receives:'Pacote do caso e observações anteriores, conforme o serviço.',delivers:'Objeções e limites para revisão; nenhuma alteração financeira.',trigger:'Revisão assistida que alcance o papel crítico.',source:'agents/case_review.py · _run_role(critic)' },
  { id:'human',name:'Revisão financeira',monogram:'HF',category:'Autoridade humana',stage:'Decidir',mission:'Conferir a preparação e decidir exceções dentro de sua autoridade.',skills:['Helena: revisar o fechamento','Comercial: confirmar regras comerciais','Pedir evidência ou correção'],receives:'Preparação financeira, fontes e pendências.',delivers:'Decisão da pessoa responsável, fora da execução automática.',trigger:'Uma pendência ou revisão que exija autoridade humana.',source:'RESPOSTAS_FINANCEIRO.md · regras de autoridade' },
];
const UNKNOWN:TeamRole={id:'unknown',name:'Atividade registrada',monogram:'AT',category:'Papel não identificado',stage:'Registro',mission:'Consultar a atividade tal como foi registrada pela fonte.',skills:[],receives:'Entrada não detalhada neste contrato de eventos.',delivers:'Somente o resultado explicitado nos registros.',trigger:'Consultar os detalhes da tarefa.',source:'Contrato de eventos v1'};
export function roleForTask(task: MissionTask): TeamRole {
  let id:TeamRoleId='unknown';
  if(task.actors.includes('INT:investigator')) id='investigator';
  else if(task.actors.includes('INT:critic')) id='critic';
  else if(task.actors.includes('INT')) id=task.id.startsWith('INV-')||task.events.some(e=>e.summary.startsWith('Investigacao iniciada'))?'investigation':'case';
  else if(task.actors.some(a=>['api','worker'].includes(a))) {
    const registered=task.events.find(e=>e.type==='task.created')?.summary??'';
    id=/Revis[aã]o de caso enfileirada/i.test(registered)?'case':/Investiga[cç][aã]o enfileirada/i.test(registered)?'investigation':/Fechamento enfileirado/i.test(registered)?'automation':'unknown';
  }
  return TEAM_ROLES.find(r=>r.id===id)??UNKNOWN;
}
export function taskDisplayName(task:MissionTask):string {
  if(roleForTask(task).id==='case'&&task.actors.some(a=>['api','worker'].includes(a)))return 'Coordenação da revisão';
  if(task.actors.includes('INT')&&!task.actors.some(a=>a.startsWith('INT:'))&&!task.id.startsWith('INV-')&&!task.events.some(e=>e.summary.startsWith('Investigacao iniciada'))) return 'Preparação do caso';
  return roleForTask(task).name;
}
export function observedMode(task:MissionTask):string {
  const started=task.events.find(e=>e.type==='task.started'&&/modo (llm|deterministic|replay)/.test(e.summary));
  if(started?.summary.includes('modo llm'))return 'Modo LLM declarado pelo serviço';
  if(started?.summary.includes('modo deterministic'))return 'Consulta determinística';
  if(started?.summary.includes('modo replay'))return 'Replay declarado pelo serviço';
  return roleForTask(task).category==='Papel assistido'?'Papel registrado; modo e chamada a modelo não certificados por este evento.':'A presença desta tarefa não comprova chamada a modelo.';
}
export function taskState(task:MissionTask):string {
  if(task.reviewRequired&&task.status==='completed')return 'Preparado · revisão pendente';
  if(!task.lifecycleObserved)return 'Estado não informado';
  return {queued:'Aguardando',running:'Processando',completed:'Encerrado tecnicamente',failed:'Falhou',blocked:'Precisa de revisão'}[task.status];
}
export function layoutTeam(tasks:MissionTask[]) {
  const map=new Map(tasks.map(t=>[t.key,t]));
  function depth(task:MissionTask,visited=new Set<string>()):number {
    if(visited.has(task.key))return 0;visited.add(task.key);
    const parents=task.parentIds.map(id=>map.get(taskKey(task.runId,id))).filter((p):p is MissionTask=>Boolean(p)&&p?.key!==task.key);
    return parents.length?Math.min(6,1+Math.max(...parents.map(p=>depth(p,new Set(visited))))):0;
  }
  const rows=new Map<number,number>();
  const nodes=tasks.map(task=>{const col=depth(task);const row=rows.get(col)??0;rows.set(col,row+1);return{task,x:36+col*322,y:45+row*180};});
  const nodeMap=new Map(nodes.map(n=>[n.task.key,n]));
  const edges=nodes.flatMap(child=>child.task.parentIds.flatMap(id=>{const parent=nodeMap.get(taskKey(child.task.runId,id));return parent&&parent.task.key!==child.task.key?[{id:JSON.stringify([parent.task.key,child.task.key]),parent,child,events:child.task.events.filter(e=>e.parent_task_id===id)}]:[];}));
  return{nodes,edges,width:Math.max(800,...nodes.map(n=>n.x+310)),height:Math.max(290,...nodes.map(n=>n.y+170))};
}
