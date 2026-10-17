import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDownToLine, ArrowRight, Building2, ChartNoAxesCombined, Check, ChevronRight, CircleHelp, Clock3, CreditCard, Database, FileCheck2, FileSearch, FileText, Globe2, Layers3, LoaderCircle, Play, RefreshCw, Search, Settings2, ShieldCheck, Unplug, Users, X, AlertTriangle } from 'lucide-react';
import { ApiError, makeApi, type AgentEvent, type Investigation, type JsonRecord, type Output, type Run } from './api';
import MissionControl from './components/mission-control/MissionControl';
import Papa from 'papaparse';
import ComparisonPanel from './ComparisonPanel';
import {EvidenceCard,ProposalCard} from './EvidenceCard';
import InvestigationMetrics from './InvestigationMetrics';

type View = 'close' | 'issues' | 'sources' | 'investigate' | 'agents';
const NAV = [
  {id: 'close', label: 'Fechamento', icon: ChartNoAxesCombined},
  {id: 'issues', label: 'Pendências', icon: Clock3},
  {id: 'sources', label: 'Fontes', icon: Database},
  {id: 'investigate', label: 'Investigação', icon: Search},
  {id: 'agents', label: 'Central de agentes', icon: Users},
] as const;
const LABELS: Record<string, string> = {queued: 'Na fila', running: 'Em processamento', processing: 'Em processamento', completed: 'Processado', succeeded: 'Processado', success: 'Processado', failed: 'Falhou', blocked: 'Bloqueado', unavailable: 'Indisponível', pending: 'Aguardando execução', review_required: 'Revisão necessária', needs_review: 'Revisão necessária', pending_review: 'Revisão pendente', interrupted: 'Interrompido', timed_out: 'Tempo esgotado', cancelled: 'Cancelado', completed_with_issues: 'Processado com pendências'};
const SOURCES = [
  ['01_orbe_relatorio_comissoes_set2026.csv', 'Checkout', 'Transações, taxas aplicadas e antecipações da Orbe.'],
  ['02_tabela_taxas_contratadas.xlsx', 'Condições comerciais', 'Cadastro, identidade e taxas contratadas por lojista.'],
  ['03_email_ponte_cambio_relatorio_set2026.eml', 'Remessas internacionais', 'E-mail e relatório de operações da Ponte Câmbio.'],
  ['04_plano_de_contas_fenix_erp.csv', 'Plano de contas', 'Contas disponíveis para classificação bancária.'],
  ['05a_extrato_banco_aurora_cc4471_set2026.csv', 'Banco Aurora', 'Movimentações da conta corrente.'],
  ['05b_extrato_banco_meridiano_cc90233_set2026.ofx', 'Banco Meridiano', 'Movimentações e identificadores OFX.'],
];
const text = (value: unknown): string => value == null ? 'Não informado' : typeof value === 'object' ? JSON.stringify(value) : String(value);
const message = (error: unknown) => error instanceof Error ? error.message : 'Não foi possível concluir esta ação.';
const isBusy = (status?: string) => ['queued', 'running', 'processing'].includes(status ?? '');
const terminal = (status?: string) => !!status && !isBusy(status);
function money(value: unknown): string | null {
  if (typeof value !== 'string' || !/^-?\d+\.\d{2}$/.test(value)) return null;
  const [integer,decimal]=value.split('.');
  return `R$ ${integer.replace(/\B(?=(\d{3})+(?!\d))/g,'.')},${decimal}`;
}
function Status({status}: {status: string}) {return <span className={`status status-${status}`}><span />{LABELS[status] ?? status}</span>;}
function Empty({title, children}: {title: string; children?: React.ReactNode}) {return <div className="empty"><FileSearch size={30} strokeWidth={1.4} /><strong>{title}</strong>{children && <p>{children}</p>}</div>;}
function Fields({data}: {data: JsonRecord}) {return <dl className="fields">{Object.entries(data).map(([key,value]) => <div key={key}><dt>{key.replaceAll('_',' ')}</dt><dd>{text(value)}</dd></div>)}</dl>;}
function FinancialSummary({run,onOutput}: {run: Run;onOutput:(name:string)=>void}) {
  const summary=run.summary;
  const rows=[['checkout_commission_brl','Comissão de checkout','comissoes_por_lojista.csv'],['remessa_commission_brl','Comissão de remessas','comissoes_por_lojista.csv'],['invoices_brl','Notas a emitir','notas_a_emitir.csv'],['checkout_rate_difference_brl','Divergência checkout · exceto Casa','divergencias_taxa.csv'],['casa_refund_brl','Devolução Casa · sem cobrança Orbe','pendencias.csv'],['remessa_rate_difference_brl','Divergência remessas · valor integral','divergencias_taxa.csv']];
  const counts=summary.counts && typeof summary.counts==='object' ? summary.counts as JsonRecord : {};
  return <><div className="summary-heading"><Status status={run.status}/><span>Cálculo determinístico · não aprovado financeiramente</span></div><div className="financial-summary">{rows.filter(([key])=>key in summary).map(([key,label,file])=><button key={key} onClick={()=>onOutput(file)}><span>{label}</span><strong>{money(summary[key]) ?? 'Não informado'}</strong><ChevronRight size={15}/></button>)}</div><p className="inline-help">Comissões, notas, divergências e pendências representam naturezas distintas. Estes valores não devem ser somados.</p><div className="validation-row"><ShieldCheck size={17}/><span>{summary.trace_reconciled===true ? 'Conservação do rastro conferida pelo motor' : 'Conferência do rastro não informada'}</span><strong>{summary.trace_checks == null ? 'n/a' : `${text(summary.trace_checks)} checagens`}</strong></div><div className="output-counts">{Object.entries(counts).map(([name,count])=><button key={name} onClick={()=>onOutput(name)}><FileText size={14}/><span>{name}</span><strong>{text(count)}</strong></button>)}</div><details className="technical"><summary>Detalhes técnicos da execução</summary><Fields data={summary}/></details></>;
}

export default function App() {
  const [view, setView] = useState<View>('close');
  const [tab, setTab] = useState<'summary'|'outputs'>('summary');
  const [period,setPeriod] = useState('2026-09');
  const [connected,setConnected] = useState(!!import.meta.env.VITE_API_BASE_URL);
  const [base,setBase] = useState(import.meta.env.VITE_API_BASE_URL ?? '');
  const [token,setToken] = useState('');
  const [config,setConfig] = useState(false);
  const [draftBase,setDraftBase] = useState(base);
  const [draftToken,setDraftToken] = useState('');
  const [runs,setRuns] = useState<Run[]>([]);
  const [runId,setRunId] = useState('');
  const [run,setRun] = useState<Run | null>(null);
  const [events,setEvents] = useState<AgentEvent[]>([]);
  const [outputs,setOutputs] = useState<Output[]>([]);
  const [selectedOutput,setSelectedOutput] = useState('');
  const [loading,setLoading] = useState(false);
  const [creating,setCreating] = useState(false);
  const [error,setError] = useState('');
  const [fresh,setFresh] = useState('');
  const [filter,setFilter] = useState('');
  const [detail,setDetail] = useState<JsonRecord | null>(null);
  const [trace,setTrace] = useState<JsonRecord[] | null>(null);
  const [traceLoading,setTraceLoading] = useState(false);
  const [traceError,setTraceError] = useState('');
  const [question,setQuestion] = useState('');
  const [investigationMode,setInvestigationMode]=useState<'deterministic'|'llm'>('deterministic');
  const [investigation,setInvestigation] = useState<Investigation | null>(null);
  const [asking,setAsking] = useState(false);
  const [questionError,setQuestionError] = useState('');
  const [investigationId,setInvestigationId] = useState('');
  const [refresh,setRefresh] = useState(0);
  const api = useMemo(() => makeApi(base,token),[base,token]);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const contextEpoch=useRef(0);
  const traceEpoch=useRef(0);
  const navigate = useCallback((target: View) => {setView(target);setDetail(null);setFilter('');},[]);
  const openDetail=useCallback((record:JsonRecord)=>{traceEpoch.current++;setDetail(record);setTrace(null);setTraceError('');setTraceLoading(false);},[]);
  function openOutput(name:string){setSelectedOutput(name);navigate('sources');}
  async function loadTrace(){
    if(!detail?.id_saida || !runId) return;
    const epoch=++traceEpoch.current;
    setTraceLoading(true);setTraceError('');
    try{const csv=await api.outputText(runId,'rastro.csv');if(epoch!==traceEpoch.current)return;const parsed=Papa.parse<JsonRecord>(csv,{header:true,delimiter:';',skipEmptyLines:true});if(parsed.errors.length) throw new Error('Não foi possível interpretar o rastro recebido.');setTrace(parsed.data.filter(row=>row.id_saida===detail.id_saida));}
    catch(e){if(epoch===traceEpoch.current)setTraceError(message(e));}finally{if(epoch===traceEpoch.current)setTraceLoading(false);}
  }

  useEffect(() => {
    if (!connected) return;
    const abort = new AbortController(); setLoading(true); setError('');
    Promise.all([api.health(abort.signal),api.runs(abort.signal)]).then(([,result]) => {
      if (abort.signal.aborted) return;
      setRuns(result.items ?? []);
      setRunId(current => current || result.items?.[0]?.run_id || '');
      setFresh(new Date().toISOString());
    }).catch(e => {if (!abort.signal.aborted) setError(message(e));}).finally(() => {if (!abort.signal.aborted) setLoading(false);});
    return () => abort.abort();
  },[api,connected,refresh]);

  useEffect(() => {
    contextEpoch.current++;traceEpoch.current++;setDetail(null);setTrace(null);setTraceError('');setTraceLoading(false);
    setRun(null);setEvents([]);setOutputs([]);setSelectedOutput('');setInvestigation(null);setInvestigationId('');setQuestionError('');
    setAsking(false);
  },[connected,runId,api]);

  useEffect(() => {
    if (!connected || !runId) return;
    const abort = new AbortController(); let timer: ReturnType<typeof setTimeout>; let cursor: string | null = null;
    const poll = async () => {
      try {
        const [next,eventPage] = await Promise.all([api.run(runId,abort.signal),api.events(runId,cursor,abort.signal)]);
        if (abort.signal.aborted) return;
        setRun(next);setError('');setFresh(new Date().toISOString());
        setEvents(current => {const all = new Map(current.map(e => [e.id,e]));for(const event of eventPage.items ?? []) all.set(event.id,event);return [...all.values()];});
        cursor = eventPage.next_cursor ?? cursor;
        if (terminal(next.status)) {
          const page = await api.outputs(runId,abort.signal);
          if (abort.signal.aborted) return;
          setOutputs(page.items ?? []);setSelectedOutput(current => current || page.items?.[0]?.name || '');
        } else timer = setTimeout(poll,1500);
      } catch(e) {if (!abort.signal.aborted) setError(message(e));}
    };
    void poll();return () => {abort.abort();clearTimeout(timer);};
  },[api,connected,runId,refresh]);

  useEffect(() => {
    if (!config) return;
    function keyboard(event: KeyboardEvent) {
      if(event.key === 'Escape') {setConfig(false);return;}
      if(event.key !== 'Tab') return;
      const controls=[...document.querySelectorAll<HTMLElement>('.connection-dialog button,.connection-dialog input')].filter(el=>!el.hasAttribute('disabled'));
      const first=controls[0],last=controls[controls.length-1];
      if(event.shiftKey && document.activeElement===first){event.preventDefault();last?.focus();}
      else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first?.focus();}
    }
    document.addEventListener('keydown',keyboard);return ()=>document.removeEventListener('keydown',keyboard);
  },[config]);

  useEffect(() => {
    if (!investigationId || !runId || !connected) return;
    const abort = new AbortController();let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const result = await api.investigation(runId,investigationId,abort.signal);
        if (abort.signal.aborted) return;
        setInvestigation(result.result ?? result);
        if (isBusy(result.status)) timer = setTimeout(poll,1500);else {setAsking(false);setInvestigationId('');setRefresh(n => n+1);}
      } catch(e) {if (!abort.signal.aborted) {setQuestionError(message(e));setAsking(false);setInvestigationId('');}}
    };
    void poll();return () => {abort.abort();clearTimeout(timer);};
  },[api,connected,runId,investigationId]);

  async function createRun() {
    if (!connected) {setConfig(true);return;}
    setCreating(true);setError('');
    try {const next = await api.create(period);setRunId(next.run_id);setRefresh(n => n+1);navigate('close');}
    catch(e) {setError(message(e));}finally {setCreating(false);}
  }
  async function ask() {
    if (!connected || !runId || !question.trim()) return;
    if(investigationMode==='llm'&&!token.trim()){setQuestionError('Investigação com IA exige um token de sessão. Abra Conexão da API e informe o bearer autorizado.');return;}
    const epoch=contextEpoch.current;
    setAsking(true);setQuestionError('');setInvestigation(null);
    try {
      const result = await api.investigate(runId,question.trim(),investigationMode);if(epoch!==contextEpoch.current)return;setInvestigation(result.result ?? result);
      const id = result.investigation_id ?? result.id;
      if (isBusy(result.status) && id) setInvestigationId(id);else setAsking(false);
    } catch(e) {if(epoch===contextEpoch.current){setQuestionError(investigationMode==='llm'&&e instanceof ApiError&&[401,403].includes(e.status??0)?'Investigação com IA não autorizada. Confira o token de sessão e a habilitação do backend. Nenhuma consulta determinística foi usada como substituta.':message(e));setAsking(false);}}
  }
  const displayed = NAV.find(item => item.id === view)!;
  const output = outputs.find(item => item.name === selectedOutput);
  const issues = (run?.issues ?? []).filter(item => text(item).toLocaleLowerCase('pt-BR').includes(filter.toLocaleLowerCase('pt-BR')));
  const pendingOutput = outputs.find(item => item.name === 'pendencias.csv');
  const previewRows = pendingOutput?.preview?.rows ?? [];
  const busy = creating || isBusy(run?.status);
  const prettyDate = fresh ? new Intl.DateTimeFormat('pt-BR',{hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date(fresh)) : null;

  return <div className="app-shell">
    <a href="#main" className="skip-link">Ir para o conteúdo</a>
    <aside className="sidebar">
      <div className="wordmark"><img className="brand-logo" src="/brand/lastro-logo.svg" width="136" height="28" alt="Lastro"/><img className="brand-symbol" src="/brand/lastro-symbol.svg" width="28" height="28" alt="Lastro"/><span className="brand-caption">Tarvo · Financeiro</span></div>
      <div className="workspace"><Building2 size={18}/><span>Financeiro</span><ChevronRight size={14}/></div>
      <nav aria-label="Navegação principal">{NAV.map(item => <button key={item.id} aria-label={item.label} className={view === item.id ? 'nav-item active' : 'nav-item'} aria-current={view === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}><item.icon size={19}/><span>{item.label}</span>{item.id === 'issues' && (run?.issues?.length ?? 0) > 0 && <span className="nav-count">{run!.issues.length}</span>}</button>)}</nav>
      <div className="sidebar-bottom"><div><ShieldCheck size={17}/><span>Rastro antes de resultado</span></div><button className="nav-item" aria-label="Conexão da API" onClick={() => {setDraftBase(base);setConfig(true);}}><Settings2 size={18}/><span>Conexão da API</span></button></div>
    </aside>
    <div className="workspace-shell">
      <header className="topbar"><div>Financeiro <span>/</span> <strong>{displayed.label}</strong></div><button className={`connection ${connected ? 'live' : 'demo'}`} onClick={() => setConfig(true)}><span className="connection-dot"/>{connected ? error ? 'Conexão com falha' : 'API configurada' : 'Modo demonstração'}</button></header>
      <main id="main" tabIndex={-1}>
        <div className="page-heading"><div><h1 ref={headingRef}>{view === 'close' ? 'Fechamento mensal' : displayed.label}</h1><p>{view === 'close' ? 'Apure, investigue e confira com a origem de cada número.' : view === 'issues' ? 'O que ainda exige uma decisão, com motivo e responsável.' : view === 'sources' ? 'Os arquivos de origem e os registros que sustentam a apuração.' : view === 'investigate' ? 'Da pergunta à evidência. Toda mudança começa como proposta.' : 'Acompanhe ações observadas, ferramentas e evidências da execução.'}</p></div><div className="heading-actions"><label className="period"><span className="sr-only">Competência</span><input aria-label="Competência" type="month" value={period} onChange={e=>setPeriod(e.target.value)} /></label><button className="button primary" onClick={createRun} disabled={busy || !period}>{busy ? <LoaderCircle className="spin" size={17}/> : <Play size={16}/>}<span>{busy ? 'Processando' : 'Processar fechamento'}</span></button></div></div>

        {!connected && <div className="notice demo-notice" role="status"><AlertTriangle size={18}/><span>Demonstração de interface. Nenhum valor financeiro foi calculado.</span><button onClick={() => setConfig(true)}>Conectar API <ArrowRight size={14}/></button></div>}
        {error && <div className="notice error" role="alert"><AlertTriangle size={18}/><span>{error}</span><button onClick={() => setRefresh(n => n+1)}>Tentar novamente</button></div>}
        {connected && <div className="runbar"><label>Execução <select aria-label="Execução" value={runId} onChange={e=>setRunId(e.target.value)}><option value="">{loading ? 'Carregando…' : 'Selecione uma execução'}</option>{runs.map(item => <option key={item.run_id} value={item.run_id}>{item.period} · {item.run_id}</option>)}{runId && !runs.some(item=>item.run_id === runId) && <option value={runId}>{runId}</option>}</select></label>{run && <Status status={run.status}/>}<span className="sync">{prettyDate ? `Sincronizado às ${prettyDate}` : 'Aguardando sincronização'}</span><button className="icon-button" aria-label="Atualizar execução" onClick={() => setRefresh(n=>n+1)}><RefreshCw size={16} className={loading ? 'spin' : ''}/></button></div>}

        {run?.summary?.late_adjustments === 'PENDENTE' && <div className="notice demo-notice" role="status"><AlertTriangle size={18}/><span>Baseline sem ajustes tardios. Resultado parcial, pendente de incorporação e revisão de Helena.</span></div>}
        {view === 'close' && <>
          <section className="metrics" aria-label="Indicadores da execução">{[
            {icon: CreditCard,label:'Comissão checkout',value:money(run?.summary?.checkout_commission_brl)},
            {icon: Globe2,label:'Comissão remessas',value:money(run?.summary?.remessa_commission_brl)},
            {icon: FileText,label:'Pendências',value:run ? pendingOutput?.preview?.total_rows ?? run.issues?.length : null},
            {icon: ArrowDownToLine,label:'Arquivos de saída',value:run ? run.outputs?.length ?? null : null},
          ].map(({icon:Icon,label,value}) => <div className="metric" key={label}><Icon size={21}/><div><span>{label}</span><strong>{value == null ? '—' : String(value)}</strong><small>{value == null ? run ? 'Ver resumo da apuração abaixo' : 'Aguardando processamento' : 'Nesta execução'}</small></div></div>)}</section>
          <div className="overview-grid"><section className="surface"><h2>Visão do fechamento</h2><div role="tablist" aria-label="Visão do fechamento" className="tabs"><button role="tab" aria-selected={tab==='summary'} onClick={()=>setTab('summary')}>Resumo</button><button role="tab" aria-selected={tab==='outputs'} onClick={()=>setTab('outputs')}>Saídas {outputs.length > 0 && <small>{outputs.length}</small>}</button></div>
            {tab === 'summary' ? <div role="tabpanel" aria-label="Resumo">{run && Object.keys(run.summary ?? {}).length > 0 ? <><FinancialSummary run={run} onOutput={openOutput}/></> : <div className="stages">{[{icon:CreditCard,label:'Checkout',target:'sources'},{icon:Globe2,label:'Remessas internacionais',target:'sources'},{icon:Building2,label:'Classificação bancária',target:'sources'}].map(({icon:Icon,label,target}) => <button key={label} className="stage-row" onClick={()=>navigate(target as View)}><Icon size={24}/><span><strong>{label}</strong><small>Fonte → regra → cálculo</small></span><Status status={run?.status ?? 'pending'}/><ChevronRight size={18}/></button>)}</div>}
            <ol className="flow"><li><span>1</span>Fontes</li><li><span>2</span>Apuração</li><li><span>3</span>Investigação</li><li><span>4</span>Revisão de Helena</li></ol></div> : <div role="tabpanel" aria-label="Saídas">{outputs.length ? <div className="output-list">{outputs.map(item=><button key={item.name} onClick={()=>{setSelectedOutput(item.name);navigate('sources');}}><FileText size={20}/><span><strong>{item.name}</strong><small>{item.preview?.total_rows == null ? 'Contagem não informada' : `${item.preview.total_rows} registros`}</small></span><ChevronRight size={17}/></button>)}</div> : <Empty title="Nenhum arquivo disponível">Os arquivos aparecerão após o processamento da API.</Empty>}</div>}
          </section><aside className="surface review-panel"><h2>Antes de concluir</h2><div className="review-item"><FileCheck2 size={25}/><div><h3>Aprovação financeira</h3><p>O fechamento depende da conferência de Helena.</p></div></div><div className="review-item"><ShieldCheck size={25}/><div><h3>Rastreabilidade</h3><p>Cada resultado deve manter fonte, registro e regra.</p></div></div><button className="investigate-card" onClick={()=>navigate('investigate')}><strong>Investigue uma diferença</strong><span>Pergunte sobre um lançamento ou uma regra.</span><b>Abrir investigação <ArrowRight size={17}/></b></button></aside></div>
          <section className="surface activity"><div className="section-heading"><h2>Atividade da execução</h2>{events.length > 0 && <button className="text-button" onClick={()=>navigate('agents')}>Ver central <ArrowRight size={14}/></button>}</div>{events.length ? <div className="activity-list">{events.slice(-4).reverse().map(event=><div key={event.id}><span className={`activity-dot activity-${event.status}`}/><div><strong>{event.summary}</strong><small>{event.actor} · {event.type}</small></div><time>{new Date(event.timestamp).toLocaleTimeString('pt-BR')}</time></div>)}</div> : <Empty title={loading || busy ? 'Aguardando eventos da execução' : 'Nenhuma execução selecionada'}>As ações e evidências aparecem aqui quando forem registradas pela API.</Empty>}</section>
        </>}

        {view === 'issues' && <section className="surface"><div className="section-heading"><h2>Pendências para revisão</h2><label className="search-box"><Search size={16}/><input aria-label="Filtrar pendências" placeholder="Buscar motivo ou referência" value={filter} onChange={e=>setFilter(e.target.value)}/></label></div><div className="notice subtle"><CircleHelp size={17}/><span>Registrar uma pendência não resolve a regra nem aprova o fechamento.</span></div>{previewRows.length ? <DataTable output={pendingOutput!} filter={filter} onSelect={openDetail}/> : issues.length ? <div className="issue-list">{issues.map((issue,index) => {const item=typeof issue === 'object' && issue ? issue as JsonRecord : {motivo:issue};return <button key={index} onClick={()=>openDetail(item)}><AlertTriangle size={19}/><span><strong>{text(item.motivo ?? item.message ?? item.title ?? item.tipo ?? 'Pendência da execução')}</strong><small>{text(item.quem_decide ?? item.owner ?? 'Responsável não informado')} · {text(item.ref_origem ?? item.code ?? '')}</small></span><ChevronRight size={17}/></button>;})}</div> : <Empty title={filter ? 'Nenhuma pendência corresponde à busca' : run ? 'Nenhuma pendência disponível nesta resposta' : 'As pendências dependem de uma execução'}>A ausência nesta tela não constitui aprovação financeira.</Empty>}</section>}

        {view === 'sources' && <div className="source-layout"><section className="surface"><div className="section-heading"><h2>{outputs.length ? 'Arquivos da apuração' : 'Fontes do case'}</h2><span className="muted">{outputs.length ? `${outputs.length} arquivos` : 'Catálogo local · conteúdo não carregado'}</span></div>{outputs.length ? <div className="file-selector">{outputs.map(item=><button className={selectedOutput === item.name ? 'selected' : ''} key={item.name} onClick={()=>{setSelectedOutput(item.name);setFilter('');}}><FileText size={16}/>{item.name}</button>)}</div> : <div className="source-catalog">{SOURCES.map(([file,label,description])=><div key={file}><FileText size={22}/><div><h3>{label}</h3><code>{file}</code><p>{description}</p></div><span className="source-state">Não inspecionada pela interface</span></div>)}</div>}{output && <><div className="output-toolbar"><div><h3>{output.name}</h3><small>{output.preview?.total_rows ?? 'n/a'} registros · {output.preview?.truncated ? 'Prévia parcial' : 'Prévia da API'}</small></div><button className="button secondary" onClick={()=>api.download(runId,output.name).catch(e=>setError(message(e)))}><ArrowDownToLine size={16}/>Baixar CSV</button></div><label className="search-box table-search"><Search size={16}/><input aria-label="Filtrar registros" value={filter} onChange={e=>setFilter(e.target.value)} placeholder="Buscar nesta prévia"/></label><DataTable output={output} filter={filter} onSelect={openDetail}/></> }</section><aside className="surface provenance"><Layers3 size={25}/><h2>O caminho do número</h2><p>Saída → rastro → registro de origem.</p><ol><li>Selecione um arquivo e um registro.</li><li>Confira o <code>id_saida</code> e a referência original.</li><li>Consulte <code>rastro.csv</code> para verificar os componentes do valor.</li></ol><p className="muted">A prévia preserva as colunas retornadas pela API. O catálogo de fontes não comprova ingestão.</p></aside></div>}

        {view === 'investigate' && <div className="investigation-layout"><section className="surface question-panel"><div className="section-heading"><h2>Investigar com evidências</h2><span className="small-label">{runId ? 'Contexto da execução selecionada' : 'Selecione uma execução'}</span></div><label className="investigation-mode" htmlFor="investigation-mode">Método da investigação<select id="investigation-mode" value={investigationMode} disabled={asking} onChange={e=>{setInvestigationMode(e.target.value as 'deterministic'|'llm');setInvestigation(null);setQuestionError('');}}><option value="deterministic">Consulta às fontes</option><option value="llm">Investigação com IA</option></select></label><p className="investigation-method">{investigationMode==='deterministic'?'Busca determinística nas fontes locais · sem chamada de modelo':'IA via backend · requer sessão autorizada; execução e métricas serão confirmadas pela API'}</p>{investigationMode==='llm'&&!token.trim()&&<div className="notice demo-notice"><span>Para usar IA, conecte uma sessão com bearer autorizado. Nenhuma chamada será enviada sem token.</span><button onClick={()=>setConfig(true)}>Configurar sessão</button></div>}<p className="muted">A investigação pode explicar e propor. Regras e valores não são alterados por esta tela.</p><label htmlFor="question">O que você precisa conferir?</label><textarea id="question" value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Ex.: Qual a origem desta divergência e quem pode decidir?" rows={5} maxLength={6000}/><div className="question-footer"><span>{question.length}/6000</span><button className="button primary" onClick={ask} disabled={!connected || !runId || !question.trim() || asking || busy || (investigationMode==='llm'&&!token.trim())}>{asking ? <LoaderCircle className="spin" size={17}/> : <Search size={17}/>}Investigar</button></div>{!connected && <p className="inline-help">Conecte a API para executar uma investigação. Nenhuma resposta é gerada na demonstração.</p>}<div className="suggestions"><span>Pontos de partida</span>{['Por que a devolução da Casa não é cobrada da Orbe?','Quais pendências exigem decisão de Helena?','Como rastrear uma comissão até sua origem?'].map(q=><button key={q} onClick={()=>setQuestion(q)}>{q}<ArrowRight size={14}/></button>)}</div></section><section className="surface answer-panel"><h2>Evidência e proposta</h2>{questionError && <div className="notice error" role="alert">{questionError}</div>}{investigation ? <><Status status={investigation.status}/><InvestigationMetrics result={investigation}/>{investigation.answer && <p className="answer-text">{investigation.answer}</p>}{investigation.error && <div className="notice error">{typeof investigation.error === 'string' ? investigation.error : investigation.error.message}</div>}{investigation.evidence?.length ? <><h3>Evidências localizadas</h3>{investigation.evidence.map((item,i)=><EvidenceCard key={i} item={item} index={i}/>)}</> : <p className="muted">Nenhuma evidência retornada até o momento.</p>}{investigation.proposed_changes?.length ? <><h3>Propostas · revisão necessária</h3>{investigation.proposed_changes.map((item,i)=><ProposalCard key={i} item={item} index={i}/>)}<p className="inline-help">Impacto financeiro não calculado por esta tela. Proposta não é regra ativa.</p></> : null}{investigation.limitations?.length ? <><h3>Limites da resposta</h3><ul className="limitations">{investigation.limitations.map((item,i)=><li key={i}>{item}</li>)}</ul></> : null}</> : <Empty title={asking ? 'Investigação em andamento' : 'A resposta precisa de lastro'}>{asking ? 'Aguardando retorno da API, sem inferir conclusão.' : 'A resposta, suas fontes e os limites aparecerão aqui após uma investigação real.'}</Empty>}</section></div>}

        {view === 'agents' && <section className="agents-surface"><div className="notice subtle"><ShieldCheck size={17}/><span>Eventos registram ações observadas. Uma tarefa concluída não equivale a fechamento aprovado.</span></div><MissionControl events={events} loading={loading || busy}/></section>}
        {view==='close'&&<ComparisonPanel api={api} runs={runs} connected={connected}/>}
        <footer className="page-footer"><span>Competência {run?.period ?? period} · Valores e regras dependem da execução</span><span>Preparação ≠ aprovação financeira</span></footer>
      </main>
    </div>
    {config && <div className="dialog-backdrop" onClick={e=>{if(e.target===e.currentTarget)setConfig(false);}}><section className="connection-dialog" role="dialog" aria-modal="true" aria-labelledby="connection-title"><button className="icon-button close-dialog" aria-label="Fechar conexão" onClick={()=>setConfig(false)}><X size={20}/></button><Settings2 size={27}/><h2 id="connection-title">Conectar o ambiente</h2><p>Use a API do projeto. O token fica somente na memória desta aba e é descartado ao recarregar.</p><label htmlFor="api-base">Endereço da API</label><input id="api-base" autoFocus value={draftBase} onChange={e=>setDraftBase(e.target.value)} placeholder="Vazio = proxy local /api"/><small>Desenvolvimento: deixe vazio para o proxy localhost:8000.</small><button className="text-button published-api" onClick={()=>setDraftBase('https://api-production-6bfe.up.railway.app')}>Usar API publicada</button><label htmlFor="api-token">Token da sessão, se exigido</label><input id="api-token" type="password" value={draftToken} onChange={e=>setDraftToken(e.target.value)} autoComplete="off" placeholder="Token de acesso"/><div className="dialog-actions"><button className="button secondary" onClick={()=>{setConnected(false);setToken('');setDraftToken('');setRunId('');setRuns([]);setRun(null);setEvents([]);setOutputs([]);setError('');setConfig(false);}}><Unplug size={16}/>Demonstração</button><button className="button primary" onClick={()=>{const value=draftBase.trim();if(value && !/^https?:\/\//i.test(value)){setError('Use endereço HTTP(S) válido para a API.');setConfig(false);return;}setBase(value);setToken(draftToken);setDraftToken('');setConnected(true);setRefresh(n=>n+1);setConfig(false);}}><Check size={16}/>Conectar</button></div></section></div>}
    {detail && <aside className="detail-panel" aria-label="Detalhe do registro"><div className="section-heading"><h2>Registro e evidência</h2><button className="icon-button" aria-label="Fechar detalhe" onClick={()=>setDetail(null)}><X size={20}/></button></div><Fields data={detail}/>{detail.id_saida != null && <div className="trace-section"><button className="button primary" onClick={loadTrace} disabled={traceLoading}>{traceLoading ? <LoaderCircle className="spin" size={16}/> : <Layers3 size={16}/>}Conferir rastro desta saída</button>{traceError && <p role="alert" className="trace-error">{traceError}</p>}{trace && <><h3>{trace.length} componentes de origem</h3>{trace.length===0 && <p className="inline-help">Nenhum vínculo encontrado neste rastro. Não inferir origem.</p>}{trace.map((record,index)=><div className="trace-record" key={index}><Fields data={record}/></div>)}</>}</div>}<p className="inline-help">Verifique a referência no arquivo de origem e em rastro.csv. Este detalhe não representa aprovação.</p></aside>}
  </div>;
}

function DataTable({output,filter,onSelect}: {output: Output; filter: string; onSelect: (record: JsonRecord)=>void}) {
  const preview=output.preview;
  if (!preview || !preview.columns?.length) return <Empty title="Prévia não disponível">Baixe o arquivo para conferir o conteúdo integral.</Empty>;
  const rows=(preview.rows ?? []).map(row=>Array.isArray(row) ? Object.fromEntries(preview.columns.map((key,index)=>[key,row[index]])) : row);
  const visible=rows.filter(row=>text(row).toLocaleLowerCase('pt-BR').includes(filter.toLocaleLowerCase('pt-BR')));
  return <><div className="table-scroll" tabIndex={0} role="region" aria-label={`Prévia de ${output.name}`}><table><thead><tr>{preview.columns.map(col=><th key={col}>{col}</th>)}<th>Rastro</th></tr></thead><tbody>{visible.slice(0,100).map((row,index)=><tr key={index}>{preview.columns.map(col=><td key={col}>{text(row[col])}</td>)}<td><button className="text-button" onClick={()=>onSelect(row)}>Ver registro <ChevronRight size={14}/></button></td></tr>)}</tbody></table></div>{!visible.length && <Empty title="Nenhum registro corresponde à busca"/>}<p className="table-caption">{Math.min(visible.length,100)} registros exibidos da prévia{preview.truncated ? ' parcial' : ''}. Consulte o CSV para a base integral.</p></>;
}
