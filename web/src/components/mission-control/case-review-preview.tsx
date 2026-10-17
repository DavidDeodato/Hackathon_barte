// QA only. Not imported by production. All content below is an invented interface fixture.
import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import CaseReviewTrace from './CaseReviewTrace';
import type { CaseReviewResult } from './case-review-types';
import type { AgentEvent } from './types';

const events: AgentEvent[] = [
  { id: 'qa-1', run_id: 'DEMO-CASE-REPLAY', task_id: 'DEMO-REVIEW', timestamp: '2026-10-17T18:00:00Z', actor: 'INT', type: 'task.started', status: 'running', summary: 'Fixture: revisão registrada.', evidence_refs: [] },
  { id: 'qa-2', run_id: 'DEMO-CASE-REPLAY', task_id: 'DEMO-INVESTIGATOR', parent_task_id: 'DEMO-REVIEW', timestamp: '2026-10-17T18:00:01Z', actor: 'INT:investigator', type: 'task.started', status: 'running', summary: 'Fixture: papel iniciado.', evidence_refs: [] },
  { id: 'qa-3', run_id: 'DEMO-CASE-REPLAY', task_id: 'DEMO-INVESTIGATOR', parent_task_id: 'DEMO-REVIEW', timestamp: '2026-10-17T18:00:02Z', actor: 'INT:investigator', type: 'task.completed', status: 'completed', summary: 'Fixture: leitura preparada.', evidence_refs: ['DEMO-EVD-1'] },
  { id: 'qa-4', run_id: 'DEMO-CASE-REPLAY', task_id: 'DEMO-CRITIC', parent_task_id: 'DEMO-REVIEW', timestamp: '2026-10-17T18:00:03Z', actor: 'INT:critic', type: 'task.completed', status: 'completed', summary: 'Fixture: objeção registrada.', evidence_refs: ['DEMO-EVD-1'] },
  { id: 'qa-5', run_id: 'DEMO-CASE-REPLAY', task_id: 'DEMO-REVIEW', timestamp: '2026-10-17T18:00:04Z', actor: 'INT', type: 'review.required', status: 'blocked', summary: 'Fixture: nenhuma aprovação.', evidence_refs: [] },
];
const fixture: CaseReviewResult = {
  review_id: 'DEMO-REVIEW', case_id: 'DEMO-CASE', status: 'needs_evidence', mode: 'replay', model_called: false,
  packet_unchanged: true, integration_allowed: true, approved: false, applied_to_calculation: false,
  packet: { case_id: 'DEMO-CASE', source_refs: ['DEMO-SOURCE:L1'] },
  roles: [
    { role: 'investigator', executed: true, model_calls: 2, status: 'review_required', summary: 'Leitura fictícia: o pacote permite preparar uma ação para revisão.', observations: ['Fixture: linha de origem identificada.'], objections: [], limitations: ['Fixture não representa execução real.'], citations: ['DEMO-EVD-1'] },
    { role: 'critic', executed: true, model_calls: 1, status: 'needs_evidence', summary: 'Contraponto fictício: a fonte não comprova decisão financeira.', observations: [], objections: ['Fixture: política de autoridade não comprova aprovação deste caso.'], limitations: ['Fixture: aguardar evidência da decisão específica.'], citations: ['DEMO-EVD-1'] },
  ],
  evidence: [{ id: 'DEMO-EVD-1', role: 'investigator', kind: 'rule', source_refs: ['DEMO-SOURCE:L1'] }],
  limitations: ['Fixture para testar leitura e interação; nenhum valor financeiro apresentado.'], events,
};
function Preview() {
  const [mode, setMode] = useState('replay');
  const result = mode === 'pending' ? null : mode === 'deterministic' ? { ...fixture, mode: 'deterministic', status: 'review_required', roles: [{ role: 'investigator', executed: false, model_calls: 0, status: 'not_executed' }, { role: 'critic', executed: false, model_calls: 0, status: 'not_executed' }], evidence: [], events: [] } : mode === 'invalid' ? { ...fixture, approved: true } : fixture;
  return <main style={{ maxWidth: 1180, margin: '0 auto', padding: 24 }}><h1 style={{ fontSize: 21 }}>TESTE DE INTERFACE · fixture inventada</h1><p>Não é feed real, revisão assistida real nem evidência financeira.</p><nav aria-label="Cenários QA" style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBlock: 20 }}>{[['replay', 'Replay de teste'], ['deterministic', 'Determinístico'], ['pending', 'Em espera'], ['invalid', 'Contrato inválido']].map(([key, label]) => <button type="button" key={key} onClick={() => setMode(key)}>{label}</button>)}</nav><CaseReviewTrace result={result} loading={mode === 'pending'} /></main>;
}
document.body.style.cssText = 'margin:0;font-family:Segoe UI,Arial,sans-serif;background:#f6f7f4;color:#132b2a';
createRoot(document.getElementById('root')!).render(<Preview />);
