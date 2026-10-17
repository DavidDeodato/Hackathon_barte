import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { ArrowLeft, ArrowUpRight, FileText, Layers3, ShieldCheck, Sparkles } from 'lucide-react';
import CaseReviewTrace, { type CaseReviewResult } from './components/mission-control/CaseReviewTrace';
import type { AgentEvent } from './components/mission-control/types';
import './case-workspace.css';

type PacketRow = { id_saida?: string; amount?: string | null; amount_nature?: string; output_file?: string; source_refs?: string[] };
type CasePacket = {
  schema_version?: string; case_id?: string; period?: string; status?: string;
  entity?: { name?: string; identifier?: string }; amount?: string | null; amount_nature?: string;
  action_type?: string; action_prepared?: string; recipient?: string; owner?: string;
  closure_evidence?: string[]; limitations?: string[]; source_refs?: string[]; rule_refs?: string[];
  rows?: PacketRow[]; snapshot_id?: string; snapshot?: Record<string, string>;
  supporting_metrics?: { amount?: string | null; amount_nature?: string; metric?: string; name?: string; nature?: string }[];
};
type ReviewEnvelope = { review_id: string; status: string; result?: CaseReviewResult | null; error?: string | { message?: string; code?: string } | null };
export type CaseWorkspaceProps = { base: string; token: string; runId: string; caseKey: string; onClose: () => void };

const ACTIONS: Record<string, string> = {
  prepare_merchant_refund: 'Devolução ao lojista', request_contract_confirmation: 'Confirmação de contrato',
  prepare_orbe_dispute: 'Contestação ao parceiro', prepare_ponte_dispute: 'Contestação de spread',
};
const NATURES: Record<string, string> = {
  devolucao_ao_lojista_por_isencao: 'Devolução ao lojista por isenção',
};
const ACTIVE = new Set(['queued', 'running', 'pending', 'processing']);
function label(value?: string) { return value?.replaceAll('_', ' ') || 'Não informado'; }
function money(value?: string | null) {
  if (value == null || !/^-?\d+(\.\d{1,2})?$/.test(value)) return 'Não determinado';
  const [whole, cents = ''] = value.split('.');
  return `R$ ${whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.')},${cents.padEnd(2, '0')}`;
}
function failure(error: unknown) { return error instanceof Error ? error.message : 'Não foi possível carregar este registro.'; }
function serviceError(error: ReviewEnvelope['error']) { return typeof error === 'string' ? error : error?.message || error?.code || 'A revisão falhou no servidor.'; }

export default function CaseWorkspace({ base, token, runId, caseKey, onClose }: CaseWorkspaceProps) {
  const modeId = useId();
  const [packet, setPacket] = useState<CasePacket | null>(null);
  const [loading, setLoading] = useState(true);
  const [packetError, setPacketError] = useState('');
  const [mode, setMode] = useState<'deterministic' | 'llm'>('deterministic');
  const [busy, setBusy] = useState(false);
  const [reviewError, setReviewError] = useState('');
  const [review, setReview] = useState<ReviewEnvelope | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [jobId, setJobId] = useState('');
  const [pollRevision, setPollRevision] = useState(0);
  const [reload, setReload] = useState(0);
  const submitting = useRef(false);
  const context = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const reviewByCase = useRef(new Map<string, string>());
  const session = useRef({ base, token });
  const request = useCallback(async <T,>(path: string, signal: AbortSignal, body?: unknown): Promise<T> => {
    const response = await fetch(`${base.replace(/\/$/, '')}${path}`, {
      method: body ? 'POST' : 'GET', signal: AbortSignal.any([signal, AbortSignal.timeout(25000)]),
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(body ? { 'Content-Type': 'application/json' } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(response.status === 401 || response.status === 403
      ? `Acesso não autorizado (HTTP ${response.status}). Confira a sessão; nenhum modo alternativo foi executado.`
      : data?.error?.message || `O serviço retornou HTTP ${response.status}.`);
    if (!data) throw new Error('O serviço retornou uma resposta vazia.');
    return data as T;
  }, [base, token]);

  useEffect(() => {
    const controller = new AbortController(); context.current = controller; generation.current += 1;
    if (session.current.base !== base || session.current.token !== token) { reviewByCase.current.clear(); session.current = { base, token }; }
    submitting.current = false; setPacket(null); setLoading(true); setPacketError(''); setMode('deterministic');
    setReview(null); setReviewError(''); setEvents([]); setJobId(reviewByCase.current.get(`${runId}/${caseKey}`) || ''); setBusy(false);
    request<{ packet: CasePacket }>(`/api/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseKey)}`, controller.signal)
      .then(data => { if (!controller.signal.aborted) { if (!data.packet || data.packet.schema_version !== 'case-packet-v1') throw new Error('Versão do pacote não reconhecida.'); setPacket(data.packet); } })
      .catch(error => { if (!controller.signal.aborted) setPacketError(failure(error)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [runId, caseKey, request, reload, base, token]);

  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController(); const started = Date.now(); let timer: ReturnType<typeof setTimeout>;
    setBusy(true); setReviewError('');
    const poll = async () => {
      try {
        const current = await request<ReviewEnvelope>(`/api/case-reviews/${encodeURIComponent(jobId)}`, controller.signal);
        if (controller.signal.aborted) return;
        setReview(current);
        const stream = await request<{ events: AgentEvent[] }>(`/api/case-reviews/${encodeURIComponent(jobId)}/events`, controller.signal);
        if (controller.signal.aborted) return;
        setEvents(Array.isArray(stream.events) ? stream.events : []);
        if (ACTIVE.has(current.status)) {
          if (Date.now() - started > 180000) throw new Error('A revisão continua no servidor. A consulta automática foi pausada; retome para acompanhar o mesmo registro.');
          timer = setTimeout(poll, 1800);
        } else {
          setBusy(false);
          if (current.status === 'failed' || current.error) setReviewError(serviceError(current.error));
          else if (!current.result) setReviewError('A execução terminou sem resultado disponível.');
        }
      } catch (error) { if (!controller.signal.aborted) { setReviewError(failure(error)); setBusy(false); } }
    };
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [jobId, pollRevision, request]);

  async function startReview() {
    if (!packet || submitting.current || busy || (jobId && ACTIVE.has(review?.status || '')) || !context.current) return;
    if (mode === 'llm' && !token.trim()) { setReviewError('Conecte uma sessão autorizada para usar a investigação com IA.'); return; }
    const controller = context.current; const version = generation.current;
    submitting.current = true; setBusy(true); setReviewError(''); setReview(null); setEvents([]); setJobId('');
    try {
      const created = await request<ReviewEnvelope>(`/api/runs/${encodeURIComponent(runId)}/case-reviews`, controller.signal, { case_key: caseKey, mode });
      if (controller.signal.aborted || version !== generation.current) return;
      if (!created.review_id) throw new Error('O serviço não retornou o identificador da revisão.');
      reviewByCase.current.set(`${runId}/${caseKey}`, created.review_id);
      setReview(created); setJobId(created.review_id);
    } catch (error) { if (!controller.signal.aborted && version === generation.current) { setReviewError(failure(error)); setBusy(false); } }
    finally { if (version === generation.current) submitting.current = false; }
  }

  return <section className="case-workspace" aria-label="Mesa de decisão do caso">
    <header className="cw-top"><button type="button" onClick={onClose}><ArrowLeft size={16} /> Voltar ao fechamento</button><span>Mesa de decisão</span></header>
    {loading ? <div className="cw-loading" role="status">Abrindo pacote e evidências…</div> : packetError ? <div className="cw-error" role="alert">{packetError}<button type="button" onClick={() => setReload(value => value + 1)}>Tentar novamente</button></div> : packet ? <>
      <div className="cw-layout">
        <article className="cw-dossier">
          <header className="cw-identity"><div className="cw-icon"><Layers3 size={22} /></div><div><p>{packet.period || 'Período não informado'}</p><h2>{packet.entity?.name || label(caseKey)}</h2></div><span className="cw-pending">Revisão humana</span></header>
          <div className="cw-amount"><p>{ACTIONS[packet.action_type || ''] || label(packet.action_type)}</p><strong>{money(packet.amount)}</strong><span>{NATURES[packet.amount_nature || ''] || label(packet.amount_nature)}</span></div>
          <dl className="cw-parties"><div><dt>Destino da ação</dt><dd>{packet.recipient || 'Não informado'}</dd></div><div><dt>Responsável pela decisão</dt><dd>{packet.owner || 'Não informado'}</dd></div></dl>
          <section className="cw-next"><h3>Ação preparada</h3><p>{packet.action_prepared || 'Ação ainda não recebida.'}</p><span><ShieldCheck size={14} /> Preparação não equivale a aprovação ou envio.</span></section>
          <details className="cw-detail" open><summary>O que falta para encerrar <ArrowUpRight size={15} /></summary><ol>{(packet.closure_evidence || []).map((item, index) => <li key={index}>{item}</li>)}</ol>{!packet.closure_evidence?.length && <p>Evidência de encerramento não informada.</p>}</details>
          {!!packet.supporting_metrics?.length && <details className="cw-detail"><summary>Valores de contexto</summary>{packet.supporting_metrics.map((metric, index) => <p key={index}><strong>{money(metric.amount)}</strong><br />{label(metric.nature || metric.amount_nature || metric.metric || metric.name)}</p>)}</details>}
          <details className="cw-detail"><summary>Regras e limites</summary>{packet.rule_refs?.map(ref => <code key={ref}>{ref}</code>)}<ul>{packet.limitations?.map((item, index) => <li key={index}>{item}</li>)}</ul></details>
          <details className="cw-detail"><summary><span><FileText size={15} /> Fontes vinculadas</span><span>{packet.source_refs?.length ?? '—'}</span></summary><div className="cw-source-list">{packet.source_refs?.map(ref => <code key={ref}>{ref}</code>)}</div></details>
          <details className="cw-detail"><summary>Composição do valor <span>{packet.rows?.length ?? '—'} registros</span></summary><p>Linhas do pacote recebido. Naturezas diferentes não são somadas nesta vista.</p><div className="cw-row-list">{packet.rows?.map((row, index) => <article key={`${row.id_saida}-${index}`}><div><strong>{money(row.amount)}</strong><span>{label(row.amount_nature)}</span></div><code>{row.id_saida}</code><small>{row.output_file}</small>{row.source_refs?.map((ref, ri) => <code key={ri}>{ref}</code>)}</article>)}</div></details>
          <details className="cw-detail cw-version"><summary>Versão e rastreabilidade</summary><code>{packet.case_id}</code><code>{packet.snapshot_id}</code>{Object.entries(packet.snapshot || {}).map(([file, hash]) => <p key={file}>{file}<code>{hash}</code></p>)}</details>
        </article>
        <div className="cw-review-area">
          <header className="cw-review-heading"><span className="cw-eyebrow">Revisão do caso</span><h2>Uma decisão com lastro.</h2><p>Confira o pacote. Quando necessário, confronte a análise com um parecer crítico e suas fontes.</p></header>
          <div className="cw-review-controls"><label htmlFor={modeId}>Modo de revisão<select id={modeId} value={mode} disabled={busy} onChange={event => { setMode(event.target.value as 'deterministic' | 'llm'); setReviewError(''); }}><option value="deterministic">Conferir pacote · sem IA</option><option value="llm">Investigar e criticar · com IA</option></select></label><button type="button" className="cw-start" disabled={busy || Boolean(jobId && ACTIVE.has(review?.status || '')) || (mode === 'llm' && !token.trim())} onClick={() => void startReview()}><Sparkles size={16} />{busy ? 'Revisão em andamento…' : mode === 'llm' ? 'Iniciar investigação' : 'Conferir pacote'}</button></div>
          {mode === 'llm' && !token.trim() && <p className="cw-access">A investigação com IA precisa de uma sessão autorizada. Configure o acesso na conexão.</p>}
          {(mode === 'llm' || review?.result?.mode === 'llm') && <p className="cw-access">Análise assistida experimental · exige conferência das evidências. Montantes, destino e ação vêm exclusivamente do pacote determinístico. Pareceres não aprovam o fechamento.</p>}
          {reviewError && <div className="cw-error" role="alert">{reviewError}{jobId && !busy && <button type="button" onClick={() => setPollRevision(value => value + 1)}>Consultar esta revisão novamente</button>}</div>}
          <CaseReviewTrace result={review?.result ?? null} events={events} loading={busy} />
          {review?.review_id && <details className="cw-job"><summary>Registro da execução</summary><code>{review.review_id}</code><p>Estado técnico recebido: {label(review.status)}</p></details>}
        </div>
      </div>
    </> : null}
  </section>;
}

