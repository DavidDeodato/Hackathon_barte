import type { AgentEvent } from './types';

/** Invented UI fixture. Not a financial run, live agent work, or October evidence. */
export const DEMO_EVENTS: AgentEvent[] = [
  { id: 'demo-01', run_id: 'DEMO-REPLAY', task_id: 'preparar-fontes', timestamp: '2026-10-17T16:00:00Z', actor: 'Preparação', type: 'task.started', status: 'running', summary: 'Demonstração: leitura dos arquivos de entrada.', evidence_refs: [] },
  { id: 'demo-02', run_id: 'DEMO-REPLAY', task_id: 'preparar-fontes', timestamp: '2026-10-17T16:00:02Z', actor: 'Preparação', type: 'evidence.found', status: 'completed', summary: 'Demonstração: referência de origem associada.', evidence_refs: ['DEMO/fonte.csv:L2'] },
  { id: 'demo-03', run_id: 'DEMO-REPLAY', task_id: 'preparar-fontes', timestamp: '2026-10-17T16:00:03Z', actor: 'Preparação', type: 'task.completed', status: 'completed', summary: 'Demonstração: preparação técnica concluída.', evidence_refs: ['DEMO/fonte.csv:L2'] },
  { id: 'demo-04', run_id: 'DEMO-REPLAY', task_id: 'conferir-taxas', parent_task_id: 'preparar-fontes', timestamp: '2026-10-17T16:00:04Z', actor: 'Conferência', type: 'task.started', status: 'running', summary: 'Demonstração: comparar condição contratada e aplicada.', evidence_refs: [] },
  { id: 'demo-05', run_id: 'DEMO-REPLAY', task_id: 'conferir-taxas', timestamp: '2026-10-17T16:00:05Z', actor: 'Conferência', type: 'tool.called', status: 'completed', summary: 'Demonstração: consulta de regra finalizada; tarefa permanece em execução.', evidence_refs: ['DEMO/regra:V1'] },
  { id: 'demo-06', run_id: 'DEMO-REPLAY', task_id: 'revisar-excecao', parent_task_id: 'conferir-taxas', timestamp: '2026-10-17T16:00:06Z', actor: 'Investigação', type: 'task.created', status: 'blocked', summary: 'Demonstração: uma regra ausente depende de confirmação humana.', evidence_refs: ['DEMO/pendencia:P1'] },
  { id: 'demo-07', run_id: 'DEMO-REPLAY', task_id: 'revisar-excecao', timestamp: '2026-10-17T16:00:07Z', actor: 'Investigação', type: 'decision.proposed', status: 'blocked', summary: 'Demonstração: proposta preservada sem ativar regra nem aprovar fechamento.', evidence_refs: ['DEMO/pendencia:P1'] },
  { id: 'demo-08', run_id: 'DEMO-REPLAY', task_id: 'revisar-excecao', timestamp: '2026-10-17T16:00:08Z', actor: 'Investigação', type: 'review.required', status: 'blocked', summary: 'Demonstração: revisão de Helena solicitada, sem decisão atribuída a ela.', evidence_refs: ['DEMO/pendencia:P1'] },
  { id: 'demo-09', run_id: 'DEMO-REPLAY', task_id: 'consulta-indisponivel', parent_task_id: 'preparar-fontes', timestamp: '2026-10-17T16:00:09Z', actor: 'Consulta', type: 'task.failed', status: 'failed', summary: 'Demonstração: fonte indisponível. Nenhuma resposta ou conclusão foi inventada.', evidence_refs: [] },
];
