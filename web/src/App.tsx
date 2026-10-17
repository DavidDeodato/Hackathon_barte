import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { ArrowDownToLine, ArrowRight, Building2, ChartNoAxesCombined, ChevronRight, Clock3, Database, FileSearch, FileText, FolderOpen, Layers3, LoaderCircle, Plus, RefreshCw, Search, LogOut, ShieldCheck, Users, X, AlertTriangle } from 'lucide-react';

import { ApiError, makeApi, type AgentEvent, type Investigation, type JsonRecord, type Output, type Run } from './api';

import MissionControl from './components/mission-control/MissionControl';

import Papa from 'papaparse';

import ComparisonPanel from './ComparisonPanel';

import {EvidenceCard,ProposalCard} from './EvidenceCard';
import AccessGate from './AccessGate';
import DocumentsWorkspace from './components/documents/DocumentsWorkspace';
import type {DocumentsNavigationRequest} from './components/documents/types';
import LastroAssistant from './components/assistant/LastroAssistant';
import type {NavigationTarget} from './components/assistant/types';

import InvestigationMetrics from './InvestigationMetrics';

import CaseWorkspace from './CaseWorkspace';

import CarbonOverview,{IssueCards,FileTile,outputRows,formatMoney,issueTitle,caseKeyFor,outputLabel} from './CarbonOverview';



type View = 'close' | 'issues' | 'documents' | 'sources' | 'investigate' | 'agents';

const NAV = [

  {id: 'close', label: 'Fechamento', icon: ChartNoAxesCombined},

  {id: 'issues', label: 'Pendências', icon: Clock3},

  {id: 'documents', label: 'Documentos', icon: FolderOpen},

  {id: 'sources', label: 'Resultados', icon: Database},

  {id: 'investigate', label: 'Investigação', icon: Search},

  {id: 'agents', label: 'Central de agentes', icon: Users},

] as const;

const LABELS: Record<string, string> = {queued: 'Na fila', running: 'Em processamento', processing: 'Em processamento', completed: 'Processado', succeeded: 'Processado', success: 'Processado', failed: 'Falhou', blocked: 'Bloqueado', unavailable: 'Indisponível', pending: 'Aguardando execução', review_required: 'Revisão necessária', needs_review: 'Revisão necessária', pending_review: 'Revisão pendente', interrupted: 'Interrompido', timed_out: 'Tempo esgotado', cancelled: 'Cancelado', completed_with_issues: 'Processado com pendências'};

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

  return <><div className="summary-heading"><Status status={run.status}/><span>Valores apurados · revisão pendente</span></div><div className="financial-summary">{rows.filter(([key])=>key in summary).map(([key,label,file])=><button key={key} onClick={()=>onOutput(file)}><span>{label}</span><strong>{money(summary[key]) ?? 'Não informado'}</strong><ChevronRight size={15}/></button>)}</div><p className="inline-help">Comissões, notas, divergências e pendências representam naturezas distintas. Estes valores não devem ser somados.</p><div className="validation-row"><ShieldCheck size={17}/><span>{summary.trace_reconciled===true ? 'Valores vinculados às fontes' : 'Vínculos às fontes ainda não conferidos'}</span><strong>{summary.trace_checks == null ? '—' : `${text(summary.trace_checks)} checagens`}</strong></div><div className="output-counts">{Object.entries(counts).map(([name,count])=><button key={name} onClick={()=>onOutput(name)}><FileText size={14}/><span>{name}</span><strong>{text(count)}</strong></button>)}</div><details className="technical"><summary>Detalhes da apuração</summary><Fields data={summary}/></details></>;

}



const SERVICE_BASE='';
export default function App(){return <AccessGate base={SERVICE_BASE}>{onSignOut=><Workspace onSignOut={onSignOut}/>}</AccessGate>;}

function Workspace({onSignOut}:{onSignOut?:()=>void}) {

  const [view, setView] = useState<View>('close');

  const [tab, setTab] = useState<'summary'|'outputs'>('summary');
  const [createBatchRequest,setCreateBatchRequest]=useState(0);
  const [selectedBatchId,setSelectedBatchId]=useState<string|null>(null);
  const [documentsNavigation,setDocumentsNavigation]=useState<DocumentsNavigationRequest>();
  const [assistantOutput,setAssistantOutput]=useState<{runId:string;name:string}|null>(null);
  const documentNavigationId=useRef(0);

  const [period,setPeriod] = useState('2026-09');

  const connected=true;
  const base=SERVICE_BASE;
  const token='';

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

  const [globalQuery,setGlobalQuery]=useState('');

  const [issueScope,setIssueScope]=useState<'all'|'commercial'|'helena'>('all');

  const [caseKey,setCaseKey]=useState<string|null>(null);

  const [openedCases,setOpenedCases]=useState<string[]>([]);

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

    setAsking(false);setCaseKey(null);

  },[connected,runId,api]);



  useEffect(() => {

    if (!connected || !runId) return;

    const abort = new AbortController(); let timer: ReturnType<typeof setTimeout>; let cursor: string | null = null;

    const poll = async () => {

      try {

        const [next,eventPage] = await Promise.all([api.run(runId,abort.signal),api.events(runId,cursor,abort.signal)]);

        if (abort.signal.aborted) return;

        setRun(next);setError('');setFresh(new Date().toISOString());
        setRuns(current=>current.map(item=>item.run_id===next.run_id?{...item,status:next.status,updated_at:next.updated_at}:item));

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



  useEffect(()=>{

    if(!detail)return;

    const origin=document.activeElement as HTMLElement|null;

    const focusTimer=requestAnimationFrame(()=>document.querySelector<HTMLButtonElement>('[aria-label="Fechar detalhe"]')?.focus());

    const escape=(event:KeyboardEvent)=>{
      if(event.key==='Escape'){event.preventDefault();setDetail(null);return;}
      if(event.key==='Tab'){
        const elements=[...document.querySelectorAll<HTMLElement>('.detail-panel button,.detail-panel a,.detail-panel input,.detail-panel select,.detail-panel textarea,.detail-panel summary,.detail-panel [tabindex]')].filter(el=>!el.hasAttribute('disabled')&&el.getClientRects().length>0);
        const first=elements[0],last=elements[elements.length-1];
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
      }
    };

    document.addEventListener('keydown',escape);

    return()=>{cancelAnimationFrame(focusTimer);document.removeEventListener('keydown',escape);if(origin?.isConnected)origin.focus();};

  },[detail]);



  const processDocuments=useCallback(async(batchId:string,documentIds:string[],competence:string)=>{
    setCreating(true);setError('');
    try{const next=await api.create(competence,{batch_id:batchId,document_ids:documentIds});setPeriod(competence);setRunId(next.run_id);setCaseKey(null);setRefresh(n=>n+1);navigate('close');}
    finally{setCreating(false);}
  },[api,navigate]);
  const selectedBatchChanged=useCallback((batchId:string|null,competence:string)=>{setSelectedBatchId(batchId);if(competence)setPeriod(competence);},[]);
  function newClosing(){navigate('documents');setCreateBatchRequest(value=>value+1);}
  function assistantNavigate(target:NavigationTarget){
    if(target.view==='documents'){
      navigate('documents');
      setDocumentsNavigation({requestId:++documentNavigationId.current,batchId:target.batchId,create:target.newClosing===true,period:target.period});
      return;
    }
    const nextRun=target.runId||runId;
    if(target.runId){setRunId(target.runId);setCaseKey(null);setRefresh(value=>value+1);}
    if(target.view==='results'){
      if(target.output&&nextRun)setAssistantOutput({runId:nextRun,name:target.output});
      navigate('sources');
    }else navigate('close');
  }
  function assistantRunCreated(id:string){setRunId(id);setCaseKey(null);setRefresh(value=>value+1);navigate('close');}
  useEffect(()=>{
    if(!assistantOutput||run?.run_id!==assistantOutput.runId||runId!==assistantOutput.runId||!outputs.length)return;
    if(outputs.some(output=>output.name===assistantOutput.name))setSelectedOutput(assistantOutput.name);
    else setError('O arquivo indicado não está disponível neste fechamento.');
    setAssistantOutput(null);
  },[assistantOutput,run,runId,outputs]);


  async function ask() {

    if (!connected || !runId || !question.trim()) return;


    const epoch=contextEpoch.current;

    setAsking(true);setQuestionError('');setInvestigation(null);

    try {

      const result = await api.investigate(runId,question.trim(),investigationMode);if(epoch!==contextEpoch.current)return;setInvestigation(result.result ?? result);

      const id = result.investigation_id ?? result.id;

      if (isBusy(result.status) && id) setInvestigationId(id);else setAsking(false);

    } catch(e) {if(epoch===contextEpoch.current){setQuestionError(investigationMode==='llm'&&e instanceof ApiError&&[401,403].includes(e.status??0)?'A investigação com IA não está disponível para este acesso.':message(e));setAsking(false);}}

  }

  const displayed = NAV.find(item => item.id === view)!;

  const output = outputs.find(item => item.name === selectedOutput);

  const pendingOutput = outputs.find(item => item.name === 'pendencias.csv');

  const previewRows = outputRows(pendingOutput);

  const visibleIssues=previewRows.filter(row=>text(row).toLocaleLowerCase('pt-BR').includes(filter.toLocaleLowerCase('pt-BR'))).filter(row=>issueScope==='all'||String(row.quem_decide).toLowerCase().includes(issueScope==='commercial'?'comercial':'helena'));

  const startCase=(key:string)=>{setCaseKey(key);setOpenedCases(current=>current.includes(key)?current:[...current,key]);setDetail(null);setView('investigate');};

  const busy = creating || isBusy(run?.status);

  const prettyDate = fresh ? new Intl.DateTimeFormat('pt-BR',{hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date(fresh)) : null;



  return <div className="app-shell">

    <a href="#main" className="skip-link">Ir para o conteúdo</a>

    <aside className="sidebar">

      <div className="wordmark"><img className="brand-logo" src="/brand/lastro-logo.svg" width="136" height="28" alt="Lastro"/><img className="brand-symbol" src="/brand/lastro-symbol.svg" width="28" height="28" alt="Lastro"/><span className="brand-caption">Tarvo · Financeiro</span></div>

      <div className="workspace"><Building2 size={18}/><span>Financeiro</span><ChevronRight size={14}/></div>

      <nav aria-label="Navegação principal">{NAV.map(item => <button key={item.id} aria-label={item.label} className={view === item.id ? 'nav-item active' : 'nav-item'} aria-current={view === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}><item.icon size={19}/><span>{item.label}</span>{item.id === 'issues' && (run?.issues?.length ?? 0) > 0 && <span className="nav-count">{run!.issues.length}</span>}</button>)}</nav>

      <div className="sidebar-bottom">{onSignOut&&<button className="nav-item" aria-label="Sair" onClick={onSignOut}><LogOut size={18}/><span>Sair</span></button>}</div>

    </aside>

    <div className="workspace-shell">

      <header className="topbar"><div className="topbar-brand"><Layers3 size={26}/><span>LASTRO</span></div><form className="global-search" onSubmit={e=>{e.preventDefault();navigate('issues');setFilter(globalQuery);}}><Search size={17}/><input aria-label="Buscar pendências" placeholder="Buscar pendências, valores, referências…" value={globalQuery} onChange={e=>setGlobalQuery(e.target.value)}/><button aria-label="Buscar" type="submit"><ArrowRight size={15}/></button></form><span className="topbar-competence">{view==='documents'?period:run?.period??period}</span></header>

      <main id="main" tabIndex={-1}>

        <div className="page-heading"><div><h1 ref={headingRef}>{view === 'close' ? 'Fechamento' : displayed.label}</h1><p>{view === 'close' ? 'Apure o mês. Revise as exceções. Decida com evidências.' : view === 'issues' ? 'O que ainda exige uma decisão, com motivo e responsável.' : view === 'documents' ? 'Originais, conjuntos e competência para cada apuração.' : view === 'sources' ? 'Os resultados da apuração e seus registros de origem.' : view === 'investigate' ? 'Da pergunta à evidência. Toda mudança começa como proposta.' : 'Acompanhe ações observadas, ferramentas e evidências da execução.'}</p></div><div className="heading-actions"><button className="button primary" onClick={newClosing} disabled={creating}><Plus size={17}/><span>Novo fechamento</span></button></div></div>





        {error && <div className="notice error" role="alert"><AlertTriangle size={18}/><span>{error}</span><button onClick={() => setRefresh(n => n+1)}>Tentar novamente</button></div>}

        {connected && view!=='documents' && <div className="runbar"><label>Fechamento <select aria-label="Fechamento" value={runId} onChange={e=>setRunId(e.target.value)}><option value="">{loading ? 'Carregando…' : 'Selecione um fechamento'}</option>{runs.map(item => <option key={item.run_id} value={item.run_id}>{item.period} · {LABELS[item.status]??item.status}{item.created_at ? ` · ${new Date(item.created_at).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}` : ''}</option>)}{runId && !runs.some(item=>item.run_id === runId) && <option value={runId}>Fechamento selecionado</option>}</select></label>{run && <Status status={run.status}/>}<span className="sync">{prettyDate ? `Sincronizado às ${prettyDate}` : 'Aguardando sincronização'}</span><button className="icon-button" aria-label="Atualizar fechamento" onClick={() => setRefresh(n=>n+1)}><RefreshCw size={16} className={loading ? 'spin' : ''}/></button></div>}





        <div hidden={view!=='documents'}><DocumentsWorkspace base={base} createRequest={createBatchRequest} navigationRequest={documentsNavigation} onProcess={processDocuments} onBatchChange={selectedBatchChanged}/></div>

        {view === 'close' && <>

          {run?.error&&<div className="notice error" role="alert"><AlertTriangle size={18}/><span>{run.error.message || 'Não foi possível concluir esta apuração.'}</span><button onClick={()=>navigate('documents')}>Revisar documentos<ArrowRight size={14}/></button></div>}
          <CarbonOverview run={run} outputs={outputs} onOutput={openOutput} onAllIssues={()=>navigate('issues')} onRecord={openDetail} onCase={startCase} onInvestigate={q=>{setCaseKey(null);navigate('investigate');if(q)setQuestion(q);}}/>

          <details className="closing-details"><summary><Layers3 size={17}/>Resumo financeiro e saídas</summary><section className="surface"><div role="tablist" aria-label="Visão do fechamento" className="tabs"><button role="tab" aria-selected={tab==='summary'} onClick={()=>setTab('summary')}>Resumo</button><button role="tab" aria-selected={tab==='outputs'} onClick={()=>setTab('outputs')}>Saídas</button></div>{tab==='summary'?<div role="tabpanel" aria-label="Resumo">{run?<FinancialSummary run={run} onOutput={openOutput}/>:<Empty title="Selecione um fechamento"/>}</div>:<div className="output-list" role="tabpanel" aria-label="Saídas">{outputs.map(item=><button key={item.name} onClick={()=>openOutput(item.name)}><FileText size={20}/><span><strong>{outputLabel(item.name)}</strong><small>{item.preview?.total_rows??'—'} registros · CSV</small></span><ChevronRight size={17}/></button>)}</div>}</section></details>

          <details className="closing-details"><summary><Clock3 size={17}/>Histórico do fechamento <span className="count-badge">{events.length}</span></summary><section className="surface activity"><div className="section-heading"><h2>Atividade registrada</h2><button className="text-button" onClick={()=>navigate('agents')}>Ver central <ArrowRight size={14}/></button></div>{events.length?<div className="activity-list">{events.slice(-4).reverse().map(event=><div key={event.id}><span className={`activity-dot activity-${event.status}`}/><div><strong>{event.summary}</strong><small>{event.actor} · {event.type}</small></div><time>{new Date(event.timestamp).toLocaleTimeString('pt-BR')}</time></div>)}</div>:<Empty title="Nenhum evento disponível">As atividades deste fechamento aparecerão aqui.</Empty>}</section></details>

        </>}



        {view === 'issues' && <div className="issues-page"><section className="surface"><div className="section-heading"><h2>Revisões pendentes <span className="count-badge">{previewRows.length}</span></h2><label className="search-box"><Search size={16}/><input aria-label="Filtrar pendências" placeholder="Buscar motivo, valor ou referência" value={filter} onChange={e=>setFilter(e.target.value)}/></label></div><div className="filter-chips" aria-label="Responsável pela decisão">{[['all','Todas'],['commercial','Comercial'],['helena','Helena']].map(([id,label])=><button className={issueScope===id?'selected':''} key={id} onClick={()=>setIssueScope(id as typeof issueScope)}>{label}</button>)}</div><p className="issue-result-count">{visibleIssues.length} pendências nesta seleção · valores de naturezas distintas</p>{visibleIssues.length?<IssueCards rows={visibleIssues} onSelect={openDetail}/>:<Empty title={run?.status==='failed'?'Fechamento não concluído':run&&['queued','running'].includes(run.status)?'Apuração em andamento':filter?'Nenhuma pendência corresponde à busca':run?'Nenhuma pendência nesta seleção':'Selecione um fechamento'}/>}</section><aside className="surface issues-guidance"><ShieldCheck size={26}/><h2>Da exceção à decisão.</h2><p>Abra um caso para conferir o motivo, a natureza do valor e quem pode decidir.</p><p>O rastro mantém cada saída ligada aos registros e à regra que a sustentam.</p><button className="text-button" onClick={()=>{setCaseKey(null);navigate('investigate');}}>Investigar uma diferença<ArrowRight size={15}/></button></aside></div>}



        {view === 'sources' && <><div className="source-file-grid">{outputs.map(item=><FileTile key={item.name} output={item} onOpen={()=>{setSelectedOutput(item.name);setFilter('');}}/>)}</div><div className="source-layout"><section className="surface"><div className="section-heading"><h2>{outputs.length ? 'Arquivos da apuração' : 'Arquivos da apuração'}</h2><span className="muted">{outputs.length ? `${outputs.length} arquivos` : 'Selecione um fechamento'}</span></div>{outputs.length ? <div className="file-selector">{outputs.map(item=><button className={selectedOutput === item.name ? 'selected' : ''} key={item.name} onClick={()=>{setSelectedOutput(item.name);setFilter('');}}><FileText size={16}/>{item.name}</button>)}</div> : <Empty title="Nenhum arquivo de apuração">Selecione um fechamento para consultar seus resultados.</Empty>}{output && <><div className="output-toolbar"><div><h3>{output.name}</h3><small>{output.preview?.total_rows ?? '—'} registros · {output.preview?.truncated ? 'Prévia parcial' : 'Prévia do arquivo'}</small></div><button className="button secondary" onClick={()=>api.download(runId,output.name).catch(e=>setError(message(e)))}><ArrowDownToLine size={16}/>Baixar CSV</button></div><label className="search-box table-search"><Search size={16}/><input aria-label="Filtrar registros" value={filter} onChange={e=>setFilter(e.target.value)} placeholder="Buscar nesta prévia"/></label><DataTable output={output} filter={filter} onSelect={openDetail}/></> }</section><aside className="surface provenance"><Layers3 size={25}/><h2>O caminho do número</h2><p>Saída → rastro → registro de origem.</p><ol><li>Selecione um arquivo e um registro.</li><li>Confira o <code>id_saida</code> e a referência original.</li><li>Consulte <code>rastro.csv</code> para verificar os componentes do valor.</li></ol><p className="muted">Baixe o arquivo para consultar todos os registros.</p></aside></div></>}



        {view === 'investigate' && <><div className="case-entry-tabs filter-chips"><button className={!caseKey?'selected':''} onClick={()=>setCaseKey(null)}>Pergunta livre</button>{(run?.period==='2026-09'?['casa','atlas','mundo','rota']:[]).map(key=><button key={key} className={caseKey===key?'selected':''} onClick={()=>startCase(key)}>{key.charAt(0).toUpperCase()+key.slice(1)}</button>)}</div><div className="investigation-layout" hidden={!!caseKey}><section className="surface question-panel"><div className="section-heading"><h2>Investigar com evidências</h2><span className="small-label">{runId ? 'Fechamento selecionado' : 'Selecione um fechamento'}</span></div><label className="investigation-mode" htmlFor="investigation-mode">Método da investigação<select id="investigation-mode" value={investigationMode} disabled={asking} onChange={e=>{setInvestigationMode(e.target.value as 'deterministic'|'llm');setInvestigation(null);setQuestionError('');}}><option value="deterministic">Consulta às fontes</option><option value="llm">Investigação com IA</option></select></label><p className="investigation-method">{investigationMode==='deterministic'?'Localize registros e regras nos documentos do fechamento.':'Compare evidências e receba um parecer para revisão.'}</p><p className="muted">A investigação pode explicar e propor. Regras e valores não são alterados por esta tela.</p><label htmlFor="question">O que você precisa conferir?</label><textarea id="question" value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Ex.: Qual a origem desta divergência e quem pode decidir?" rows={5} maxLength={6000}/><div className="question-footer"><span>{question.length}/6000</span><button className="button primary" onClick={ask} disabled={!connected || !runId || !question.trim() || asking || busy}>{asking ? <LoaderCircle className="spin" size={17}/> : <Search size={17}/>}Investigar</button></div><div className="suggestions"><span>Pontos de partida</span>{['Quais divergências precisam de revisão?','Quais pendências exigem decisão de Helena?','Como rastrear uma comissão até sua origem?'].map(q=><button key={q} onClick={()=>setQuestion(q)}>{q}<ArrowRight size={14}/></button>)}</div></section><section className="surface answer-panel"><h2>Evidência e proposta</h2>{questionError && <div className="notice error" role="alert">{questionError}</div>}{investigation ? <><Status status={investigation.status}/><InvestigationMetrics result={investigation}/>{investigation.answer && <p className="answer-text">{investigation.answer}</p>}{investigation.error && <div className="notice error">{typeof investigation.error === 'string' ? investigation.error : investigation.error.message}</div>}{investigation.evidence?.length ? <><h3>Evidências localizadas</h3>{investigation.evidence.map((item,i)=><EvidenceCard key={i} item={item} index={i}/>)}</> : <p className="muted">Nenhuma evidência retornada até o momento.</p>}{investigation.proposed_changes?.length ? <><h3>Propostas · revisão necessária</h3>{investigation.proposed_changes.map((item,i)=><ProposalCard key={i} item={item} index={i}/>)}<p className="inline-help">O impacto depende da validação da regra proposta.</p></> : null}{investigation.limitations?.length ? <><h3>Limites da resposta</h3><ul className="limitations">{investigation.limitations.map((item,i)=><li key={i}>{item}</li>)}</ul></> : null}</> : <Empty title={asking ? 'Investigação em andamento' : 'A resposta precisa de lastro'}>{asking ? 'Consultando as evidências do fechamento.' : 'Faça uma pergunta para consultar os documentos e suas referências.'}</Empty>}</section></div></>}



        {connected&&runId&&run?.period==='2026-09'&&openedCases.map(key=><div key={key} className="case-layer" hidden={view!=='investigate'||caseKey!==key}><CaseWorkspace base={base} token={token} runId={runId} caseKey={key} onClose={()=>{setCaseKey(null);navigate('close');}}/></div>)}

        {view === 'investigate'&&caseKey&&(!connected||!runId)&&<Empty title="Selecione um fechamento">Selecione um fechamento para abrir os casos vinculados.</Empty>}

        {view === 'agents' && <section className="agents-surface"><div className="notice subtle"><ShieldCheck size={17}/><span>Histórico das verificações e análises deste fechamento.</span></div><MissionControl events={events} loading={loading || busy}/></section>}

        {view==='close'&&<details className="closing-details comparison-toggle"><summary><Layers3 size={17}/>Comparar fechamentos</summary><ComparisonPanel api={api} runs={runs} connected={connected}/></details>}

        <footer className="page-footer"><span>Competência {view==='documents'?period:run?.period ?? period}</span><span>Lastro · Financeiro</span></footer>

      </main>

    </div>



    <div hidden={Boolean(detail)}><LastroAssistant base={base} period={view==='documents'?period:run?.run_id===runId?run.period:undefined} batchId={view==='documents'?selectedBatchId:run?.run_id===runId?run.batch_id??null:null} runId={view==='documents'?null:run?.run_id===runId?runId:null} onNavigate={assistantNavigate} onRunCreated={assistantRunCreated}/></div>

    {detail && <><div className="detail-backdrop" onClick={()=>setDetail(null)}/><aside className="detail-panel" role="dialog" aria-modal="true" aria-label="Detalhe do registro"><div className="section-heading"><h2>Registro e evidência</h2><button className="icon-button" aria-label="Fechar detalhe" onClick={()=>setDetail(null)}><X size={20}/></button></div>{Boolean(detail.tipo)&&<><span className="review-pill">Revisão pendente</span><h2 style={{marginTop:18}}>{issueTitle(detail)}</h2><div className="detail-summary-value">{formatMoney(detail.valor_brl)??'Não quantificado'}</div><p className="detail-summary-nature">{String(detail.metrica_valor??'')}</p><div className="detail-context">{String(detail.motivo??'')}<p style={{marginTop:10}}><strong>Quem decide:</strong> {String(detail.quem_decide??'Não informado')}</p></div>{run?.period==='2026-09'&&caseKeyFor(detail)&&<button className="button primary" onClick={()=>startCase(caseKeyFor(detail)!)}>Abrir mesa de revisão<ArrowRight size={16}/></button>}</>}<details className="technical" open={!detail.tipo}><summary>Todos os campos do registro</summary><Fields data={detail}/></details>{detail.id_saida != null && <div className="trace-section"><button className="button primary" onClick={loadTrace} disabled={traceLoading}>{traceLoading ? <LoaderCircle className="spin" size={16}/> : <Layers3 size={16}/>}Conferir rastro desta saída</button>{traceError && <p role="alert" className="trace-error">{traceError}</p>}{trace && <><h3>{trace.length} componentes de origem</h3>{trace.length===0 && <p className="inline-help">Nenhuma origem vinculada a este registro.</p>}{trace.map((record,index)=><div className="trace-record" key={index}><Fields data={record}/></div>)}</>}</div>}<p className="inline-help">Confira as referências e os documentos de origem antes de decidir.</p></aside></>}

  </div>;

}



function DataTable({output,filter,onSelect}: {output: Output; filter: string; onSelect: (record: JsonRecord)=>void}) {

  const preview=output.preview;

  if (!preview || !preview.columns?.length) return <Empty title="Prévia não disponível">Baixe o arquivo para conferir o conteúdo integral.</Empty>;

  const rows=(preview.rows ?? []).map(row=>Array.isArray(row) ? Object.fromEntries(preview.columns.map((key,index)=>[key,row[index]])) : row);

  const visible=rows.filter(row=>text(row).toLocaleLowerCase('pt-BR').includes(filter.toLocaleLowerCase('pt-BR')));

  return <><div className="table-scroll" tabIndex={0} role="region" aria-label={`Prévia de ${output.name}`}><table><thead><tr>{preview.columns.map(col=><th key={col}>{col}</th>)}<th>Rastro</th></tr></thead><tbody>{visible.slice(0,100).map((row,index)=><tr key={index}>{preview.columns.map(col=><td key={col}>{text(row[col])}</td>)}<td><button className="text-button" onClick={()=>onSelect(row)}>Ver registro <ChevronRight size={14}/></button></td></tr>)}</tbody></table></div>{!visible.length && <Empty title="Nenhum registro corresponde à busca"/>}<p className="table-caption">{Math.min(visible.length,100)} registros exibidos da prévia{preview.truncated ? ' parcial' : ''}. Consulte o CSV para a base integral.</p></>;

}

