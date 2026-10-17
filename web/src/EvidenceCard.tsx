import type { ReactNode } from 'react';
import { FileText, GitPullRequest } from 'lucide-react';
import type { JsonRecord } from './api';

const object = (value: unknown): JsonRecord | null => value && typeof value === 'object' && !Array.isArray(value) ? value as JsonRecord : null;
const scalar = (value: unknown) => value == null ? 'Não informado' : typeof value === 'boolean' ? value ? 'Sim' : 'Não' : typeof value === 'object' ? 'Consulte os campos abaixo.' : String(value);
const labels: Record<string, string> = {
  entity: 'Entidade', merchant: 'Lojista', modality: 'Modalidade', business_line: 'Linha de negócio',
  line_of_business: 'Linha de negócio', recipient: 'Destinatário', owner: 'Responsável', period: 'Competência',
  id_saida: 'Registro de saída', ref_origem: 'Referência de origem', arquivo_origem: 'Arquivo de origem',
  linha_origem: 'Linha física', valor: 'Valor registrado', valor_brl: 'Valor registrado em reais',
  comissao_brl: 'Comissão em reais', diferenca_brl: 'Diferença em reais', motivo: 'Motivo',
  quem_decide: 'Quem decide', tipo: 'Tipo', natureza: 'Natureza', status: 'Estado informado',
};
const label = (key: string) => labels[key] || key.replaceAll('_', ' ');
function Value({ value, depth = 0 }: { value: unknown; depth?: number }): ReactNode {
  if (Array.isArray(value)) return value.length ? <ul>{value.map((item, index) => <li key={index}><Value value={item} depth={depth + 1} /></li>)}</ul> : 'Não informado';
  const fields = object(value);
  if (fields && depth < 3) return <dl>{Object.entries(fields).map(([key, item]) => <div key={key}><dt>{label(key)}</dt><dd><Value value={item} depth={depth + 1} /></dd></div>)}</dl>;
  return fields ? 'Detalhes agrupados; consulte o registro técnico completo.' : scalar(value);
}
function Reference({ value }: { value: unknown }) {
  if (typeof value !== 'string') return <div><Value value={value} /></div>;
  const [file, locator] = value.split('#', 2);
  const sourceName = file.includes('RESPOSTAS_FINANCEIRO') ? 'Esclarecimentos do financeiro' : /^CAN-\d+$/.test(file) ? `Esclarecimento ${file}` : /^REG-/.test(file) ? `Regra ${file}` : file.split(/[\\/]/).at(-1) || file;
  return <span><strong>{sourceName}</strong>{locator ? <span> · {locator}</span> : null}<br /><code>{value}</code></span>;
}
function References({ values }: { values: unknown[] }) {
  return values.length ? <div className="source-reference" aria-label="Referências da fonte">{values.map((value, index) => <Reference key={index} value={value} />)}</div> : <p>Referência de origem não informada.</p>;
}

export function EvidenceCard({ item, index }: { item: unknown; index: number }) {
  const record = object(item);
  if (!record) return <p className="evidence-block">{scalar(item)}</p>;
  const data = object(record.data) || record;
  const refs = Array.isArray(record.source_refs) ? record.source_refs : Array.isArray(data.source_refs) ? data.source_refs : [];
  const rawText = data.text ?? data.excerpt ?? data.summary;
  const excerpt = typeof rawText === 'string' ? rawText : null;
  const outputs = Array.isArray(data.outputs) ? data.outputs : [];
  const traces = Array.isArray(data.trace) ? data.trace : [];
  const fields = ['title', 'reference', 'source_path', 'locator', 'ref_origem', 'arquivo_origem', 'linha_origem']
    .filter(key => data[key] != null);
  const missing = record.kind === 'lookup_not_found' || record.kind === 'search_not_found' || record.kind === 'catalog_reference_not_found';
  const title = typeof data.id === 'string' && /^CAN-\d+$/.test(data.id) ? `Esclarecimento do financeiro · ${data.id}`
    : typeof data.id === 'string' && /^REG-/.test(data.id) ? `Regra documentada · ${data.id}`
      : scalar(data.title ?? data.id ?? record.id ?? `Evidência ${index + 1}`);
  return <article className="source-evidence">
    <div className="source-evidence-heading"><FileText size={17} /><strong>{title}</strong></div>
    {excerpt ? <p>{excerpt.length > 420 ? `${excerpt.slice(0, 420)}…` : excerpt}</p> : <p>{missing ? 'Busca realizada sem localizar esta referência no conjunto consultado. Isso não comprova ausência fora deste conjunto.' : outputs.length || traces.length ? `${outputs.length} registros de saída e ${traces.length} componentes de origem localizados.` : 'Fonte registrada para conferência. Consulte sua referência e localização.'}</p>}
    <References values={refs} />
    {data.authority != null ? <p className="evidence-authority"><strong>Papel citado na fonte:</strong> {scalar(data.authority)}. Esta referência não comprova uma aprovação específica.</p> : null}
    {excerpt && excerpt.length > 420 ? <details><summary>Ler trecho completo</summary><p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{excerpt}</p></details> : null}
    {fields.length ? <details><summary>Conferir localização</summary><dl>{fields.map(key => <div key={key}><dt>{key === 'title' ? 'Assunto na fonte' : key === 'reference' ? 'Referência consultada' : key === 'source_path' ? 'Arquivo de origem' : key === 'locator' ? 'Localizador' : label(key)}</dt><dd>{scalar(data[key])}</dd></div>)}</dl></details> : null}
    {outputs.length ? <details><summary>Ver registros localizados ({outputs.length})</summary>{outputs.map((output, i) => {
      const result = object(output); const row = object(result?.row);
      return <section key={i}><h4>{scalar(result?.file ?? `Registro ${i + 1}`)}</h4>{row ? <Value value={row} /> : <p>Detalhes do registro não informados.</p>}</section>;
    })}</details> : null}
    {traces.length ? <details><summary>Conferir componentes de origem ({traces.length})</summary>{traces.map((trace, i) => <Value key={i} value={trace} />)}</details> : null}
    <details><summary>Registro técnico completo</summary><pre>{JSON.stringify(record, null, 2)}</pre></details>
  </article>;
}

export function ProposalCard({ item, index }: { item: unknown; index: number }) {
  const record = object(item);
  if (!record) return <p className="evidence-block proposal">{scalar(item)}</p>;
  const sourceRefs = Array.isArray(record.source_refs) ? record.source_refs : [];
  const authorityRefs = Array.isArray(record.authority_evidence_refs) ? record.authority_evidence_refs : [];
  const fields = [['scope', 'Alcance proposto'], ['valid_from', 'Vigência proposta a partir de'], ['valid_to', 'Vigência proposta até'], ['exceptions', 'Exceções a conferir'], ['required_authority', 'Quem precisa decidir']] as const;
  return <article className="proposal-card">
    <div className="source-evidence-heading"><GitPullRequest size={17} /><strong>Proposta {index + 1} · revisão necessária</strong></div>
    <p><strong>{typeof record.text === 'string' && record.text.trim() ? record.text : 'Descrição da mudança não informada.'}</strong></p>
    <p>Registro de proposta não comprova aprovação, envio ou alteração no fechamento.</p>
    <dl>{fields.map(([key, title]) => <div key={key}><dt>{title}</dt><dd><Value value={record[key]} /></dd></div>)}</dl>
    <details><summary>Fontes que sustentam a proposta ({sourceRefs.length})</summary><References values={sourceRefs} /></details>
    <details><summary>Referências sobre autoridade ({authorityRefs.length})</summary><p>Identificar quem decide não comprova que a condição foi aprovada. A aprovação específica continua sujeita a conferência.</p><References values={authorityRefs} /></details>
    <div className="proposal-impact"><span>Impacto financeiro</span><strong>Não calculado</strong></div>
    {record.id != null ? <details><summary>Identificador da proposta</summary><code>{scalar(record.id)}</code></details> : null}
    <details><summary>Registro técnico completo</summary><pre>{JSON.stringify(record, null, 2)}</pre></details>
  </article>;
}
