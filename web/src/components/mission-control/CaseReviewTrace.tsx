import { useId, useState } from 'react';
import MissionControl from './MissionControl';
import { CASE_ROLE_LABEL, CASE_ROLES, describeRole, inspectCaseReview, strings } from './case-review-model';
import type { CaseReviewRole, CaseReviewTraceProps } from './case-review-types';
import './case-review.css';

export type { CaseReviewRole, CaseReviewEvidence, CaseReviewResult, CaseReviewTraceProps } from './case-review-types';

const REVIEW_LABELS: Record<string, string> = { review_required: 'Preparado para revisão humana', needs_evidence: 'Faltam evidências', failed: 'Revisão interrompida' };
const NO_EVENTS: never[] = [];

function NoteList({ title, values }: { title: string; values: string[] }) {
  return values.length ? <section className="mcr-notes"><h4>{title}</h4><ul>{values.map((value, index) => <li key={`${index}-${value}`}>{value}</li>)}</ul></section> : null;
}

function RolePanel({ roleKey, role, mode, showContent, onReference }: {
  roleKey: 'investigator' | 'critic'; role?: CaseReviewRole; mode?: string; showContent: boolean; onReference: (value: string) => void;
}) {
  const description = describeRole(role, mode);
  const show = showContent && description.showContent;
  const objections = strings(role?.objections);
  return <article className={`mcr-role mcr-role-${roleKey}`}>
    <header><span className="mcr-role-number" aria-hidden="true">{roleKey === 'investigator' ? '01' : '02'}</span><div><p className="mcr-eyebrow">{roleKey === 'investigator' ? 'Leitura proposta' : 'Contraponto'}</p><h3>{CASE_ROLE_LABEL[roleKey]}</h3></div></header>
    <p className={`mcr-role-state mcr-tone-${description.tone}`}>{description.label === 'Estado do papel não reconhecido' ? 'Estado da análise indisponível' : description.label}</p>
    {show ? <>
      <h4>{roleKey === 'investigator' ? 'Conclusão em análise' : 'Parecer do crítico'}</h4>
      <p className="mcr-summary">{typeof role?.summary === 'string' && role.summary.trim() ? role.summary : 'Conclusão ainda indisponível. Consulte o histórico e as pendências.'}</p>
      <NoteList title="Observações registradas" values={strings(role?.observations)} />
      <NoteList title="Objeções registradas" values={objections} />
      {roleKey === 'critic' && objections.length === 0 ? <p className="mcr-caption">{role?.status === 'failed' ? 'Não há objeção conclusiva recebida.' : 'Nenhuma objeção adicional registrada.'}</p> : null}
      {strings(role?.citations).length ? <div className="mcr-citations" aria-label={`Citações do ${CASE_ROLE_LABEL[roleKey]}`}>{strings(role?.citations).map((reference, index) => <button type="button" key={`${index}-${reference}`} onClick={() => onReference(reference)}>{reference}<span aria-hidden="true"> ↗</span></button>)}</div> : <p className="mcr-caption">Nenhuma fonte citada neste parecer.</p>}
      <NoteList title="Pontos a conferir" values={strings(role?.limitations)} />
    </> : <p className="mcr-caption">{mode === 'deterministic' ? 'Documentos conferidos sem investigação com IA.' : 'Parecer ainda indisponível.'}</p>}
    <details className="mcr-role-calls"><summary>Detalhes da análise</summary><p>Chamadas registradas: {typeof role?.model_calls === 'number' && Number.isFinite(role.model_calls) && role.model_calls >= 0 ? role.model_calls : 'n/a'}</p></details>
  </article>;
}

/** Pure read-only view of existing CASES HTTP result/events. Never starts or approves work. */
export function CaseReviewTrace({ result, events, loading = false, error }: CaseReviewTraceProps) {
  const id = useId();
  const [selection, setSelection] = useState<{ reviewId?: string; reference: string } | null>(null);
  const inspection = inspectCaseReview(result);
  const selectedRef = selection?.reviewId === result?.review_id ? selection?.reference : undefined;
  const evidence = Array.isArray(result?.evidence) ? result.evidence.filter((item) => item && typeof item.id === 'string') : [];
  const matching = selectedRef ? evidence.filter((item) => item.id === selectedRef || strings(item.source_refs).includes(selectedRef)) : evidence;
  const sourceEvents = Array.isArray(events) ? events : Array.isArray(result?.events) ? result.events : NO_EVENTS;
  const deterministic = result?.mode === 'deterministic';
  const modeLabel = deterministic ? 'Conferência dos documentos' : result?.mode === 'replay' ? 'Reprodução de uma análise' : result?.mode === 'llm' ? 'Parecer experimental' : 'Aguardando revisão';
  const knownPacketRef = selectedRef ? strings(result?.packet?.source_refs).includes(selectedRef) || selectedRef === `packet:${result?.case_id}` : false;

  return <section className="mcr" aria-labelledby={id}>
    <header className="mcr-header"><div><p className="mcr-eyebrow">Análise do caso</p><h2 id={id}>Parecer e evidências</h2><p className="mcr-caption">Conclusões, contrapontos e documentos para apoiar a decisão.</p></div><span className="mcr-mode">{modeLabel}</span></header>
    <div className="mcr-boundaries"><div><span>Andamento da revisão</span><strong>{loading ? 'Análise em andamento' : result ? REVIEW_LABELS[result.status ?? ''] ?? 'Estado indisponível' : 'Aguardando início'}</strong></div><div><span>Decisão de Helena</span><strong>Aprovação não registrada</strong></div></div>
    {error ? <p className="mcr-alert" role="alert">{error}</p> : null}
    {result?.mode === 'replay' ? <p className="mcr-alert">Reprodução de análise anterior; não é uma nova investigação.</p> : null}
    {inspection.reasons.length > 0 ? <div className="mcr-alert" role="alert">Este parecer apresenta inconsistências e não deve orientar o encerramento do caso.<details><summary>Ver inconsistências</summary>{inspection.reasons.map(reason => <p key={reason}>{reason}</p>)}</details></div> : null}
    {result?.integration_allowed === false ? <p className="mcr-alert">O parecer não está vinculado ao fechamento. Confira as pendências antes de utilizá-lo.</p> : null}
    {inspection.unknownRoles > 0 ? <p className="mcr-alert">{inspection.unknownRoles} análise(s) não reconhecida(s). A revisão pode estar incompleta.</p> : null}
    {result ? <>
      <details className="mcr-identity"><summary>Identificação da revisão</summary><code>{result.case_id ?? 'Caso não informado'}</code><code>{result.review_id ?? 'Revisão não informada'}</code><span>Modelo acionado: {result.model_called === true ? 'sim' : result.model_called === false ? 'não' : 'n/a'}</span></details>
      {!deterministic && <div className="mcr-roles">{CASE_ROLES.map((key) => <RolePanel key={key} roleKey={key} role={inspection.roles.find((role) => role.role === key)} mode={result.mode} showContent={inspection.safeToShowContent} onReference={(reference) => setSelection({ reviewId: result.review_id, reference })} />)}</div>}
      <section className="mcr-evidence" aria-label="Fontes do parecer"><div className="mcr-section-title"><h3>{selectedRef ? `Referência: ${selectedRef}` : 'Fontes do parecer'}</h3>{selectedRef ? <button type="button" onClick={() => setSelection(null)}>Ver todas as fontes</button> : null}</div>
        {matching.length ? <ul>{matching.map((item, index) => <li key={`${index}-${item.id}`}><details><summary><span>Fonte {index + 1}</span><span>{item.role === 'investigator' ? 'Investigador' : item.role === 'critic' ? 'Crítico' : 'Referência da revisão'}</span></summary><code>{item.id}</code><p>{item.kind ?? 'Tipo não informado'}</p><ul>{strings(item.source_refs).map((ref, refIndex) => <li key={`${refIndex}-${ref}`}><code>{ref}</code></li>)}</ul></details></li>)}</ul> : <p className="mcr-caption">{knownPacketRef ? 'Referência do fechamento; confira o documento na ficha do caso.' : selectedRef ? 'A referência selecionada não foi encontrada neste parecer.' : 'Consulte os documentos vinculados na ficha do caso.'}</p>}
      </section>
      {strings(result.limitations).length > 0 && <details className="mcr-limitations"><summary>Pontos a conferir</summary><NoteList title="Pendências da análise" values={strings(result.limitations)} /></details>}
    </> : <div className="mcr-empty">{loading ? 'Preparando o parecer e reunindo as evidências…' : 'Inicie a revisão para consultar o parecer e suas fontes.'}</div>}
    <details className="mcr-operational"><summary>Histórico da revisão · {sourceEvents.length} registros</summary><MissionControl events={sourceEvents} loading={loading} /></details>
  </section>;
}

export default CaseReviewTrace;
