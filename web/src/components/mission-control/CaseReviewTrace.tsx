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
    <header><span className="mcr-role-number" aria-hidden="true">{roleKey === 'investigator' ? '01' : '02'}</span><div><p className="mcr-eyebrow">{roleKey === 'investigator' ? 'Leitura proposta' : 'Tentativa de refutação'}</p><h3>{CASE_ROLE_LABEL[roleKey]}</h3></div></header>
    <p className={`mcr-role-state mcr-tone-${description.tone}`}>{description.label}</p>
    {show ? <>
      <h4>{roleKey === 'investigator' ? 'Conclusão em análise' : 'Parecer do crítico'}</h4>
      <p className="mcr-summary">{typeof role?.summary === 'string' && role.summary.trim() ? role.summary : 'Conclusão não recebida. Consulte os eventos e as lacunas.'}</p>
      <NoteList title="Observações registradas" values={strings(role?.observations)} />
      <NoteList title="Objeções registradas" values={objections} />
      {roleKey === 'critic' && objections.length === 0 ? <p className="mcr-caption">{role?.status === 'failed' ? 'Não há objeção conclusiva recebida.' : 'Nenhuma objeção adicional registrada. Isso não equivale a aprovação.'}</p> : null}
      {strings(role?.citations).length ? <div className="mcr-citations" aria-label={`Citações do ${CASE_ROLE_LABEL[roleKey]}`}>{strings(role?.citations).map((reference, index) => <button type="button" key={`${index}-${reference}`} onClick={() => onReference(reference)}>{reference}<span aria-hidden="true"> ↗</span></button>)}</div> : <p className="mcr-caption">Nenhuma citação recebida para este papel.</p>}
      <NoteList title="Lacunas e limites deste papel" values={strings(role?.limitations)} />
    </> : <p className="mcr-caption">{mode === 'deterministic' ? 'O pacote foi preparado por regras. Não há hipótese ou objeção de modelo para exibir.' : 'Nenhuma conclusão é atribuída a este papel sem registro de execução válido.'}</p>}
    <p className="mcr-role-calls">Chamadas registradas: {typeof role?.model_calls === 'number' && Number.isFinite(role.model_calls) && role.model_calls >= 0 ? role.model_calls : 'n/a'}</p>
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
  const modeLabel = deterministic ? 'Pacote determinístico · papéis não executados' : result?.mode === 'replay' ? 'Replay declarado · não comprova inferência real' : result?.mode === 'llm' ? 'Revisão assistida · registro do servidor' : 'Modo não informado';
  const knownPacketRef = selectedRef ? strings(result?.packet?.source_refs).includes(selectedRef) || selectedRef === `packet:${result?.case_id}` : false;

  return <section className="mcr" aria-labelledby={id}>
    <header className="mcr-header"><div><p className="mcr-eyebrow">Investigação e crítica do caso</p><h2 id={id}>Da conclusão à contraprova</h2><p className="mcr-caption">Pareceres e fontes recebidos. Valores, destino e ação continuam no pacote financeiro.</p></div><span className="mcr-mode">{modeLabel}</span></header>
    <div className="mcr-boundaries"><div><span>Execução técnica</span><strong>{loading ? 'Processando · resultado ainda não final' : result ? REVIEW_LABELS[result.status ?? ''] ?? 'Estado não reconhecido' : 'Aguardando registro'}</strong></div><div><span>Revisão financeira</span><strong>Aprovação não demonstrada</strong></div></div>
    {error ? <p className="mcr-alert" role="alert">{error}</p> : null}
    {result?.mode === 'replay' ? <p className="mcr-alert">Replay informado pela fonte. Conteúdo de teste não é investigação observada em operação.</p> : null}
    {inspection.reasons.map((reason) => <p className="mcr-alert" role="alert" key={reason}>{reason}</p>)}
    {result?.integration_allowed === false ? <p className="mcr-alert">Integração do parecer com o pacote não liberada pelo servidor. A tentativa permanece visível para conferência.</p> : null}
    {inspection.unknownRoles > 0 ? <p className="mcr-alert">{inspection.unknownRoles} papel(is) fora do contrato não apresentado(s).</p> : null}
    {result ? <>
      <div className="mcr-identity"><code>{result.case_id ?? 'Caso não informado'}</code><code>{result.review_id ?? 'Revisão não informada'}</code><span>Modelo acionado: {result.model_called === true ? 'registrado pelo servidor' : result.model_called === false ? 'não' : 'n/a'}</span></div>
      <div className="mcr-roles">{CASE_ROLES.map((key) => <RolePanel key={key} roleKey={key} role={inspection.roles.find((role) => role.role === key)} mode={result.mode} showContent={inspection.safeToShowContent} onReference={(reference) => setSelection({ reviewId: result.review_id, reference })} />)}</div>
      <section className="mcr-evidence" aria-label="Fontes do parecer"><div className="mcr-section-title"><h3>{selectedRef ? `Referência: ${selectedRef}` : 'Fontes registradas no parecer'}</h3>{selectedRef ? <button type="button" onClick={() => setSelection(null)}>Ver todas as fontes</button> : null}</div>
        {matching.length ? <ul>{matching.map((item, index) => <li key={`${index}-${item.id}`}><details><summary><code>{item.id}</code><span>{item.role ?? 'Papel não informado'} · {item.kind ?? 'Tipo não informado'}</span></summary><ul>{strings(item.source_refs).map((ref, refIndex) => <li key={`${refIndex}-${ref}`}><code>{ref}</code></li>)}</ul></details></li>)}</ul> : <p className="mcr-caption">{knownPacketRef ? 'Referência recebida do pacote financeiro; confira seu conteúdo na vista do caso.' : selectedRef ? 'Nenhum registro de evidência correspondente foi recebido neste parecer.' : 'Nenhuma evidência de revisão recebida. O pacote e suas fontes continuam na vista do caso.'}</p>}
        <p className="mcr-caption">Citação e preservação de versão não comprovam interpretação correta nem autorização financeira.</p>
      </section>
      <div className="mcr-limitations"><NoteList title="Lacunas e limites da revisão" values={strings(result.limitations)} /></div>
    </> : <div className="mcr-empty">{loading ? 'Aguardando resultado do servidor. Nenhum parecer é preenchido durante a espera.' : 'Inicie a revisão na vista do caso. Hipóteses e objeções só aparecerão após retorno real.'}</div>}
    <details className="mcr-operational"><summary>Abrir trilha de ações observadas · {sourceEvents.length} eventos recebidos</summary><MissionControl events={sourceEvents} loading={loading} /></details>
  </section>;
}

export default CaseReviewTrace;
