import {useEffect,useMemo,useRef,useState} from 'react';
import {ArrowUpRight,Check,ChevronLeft,FileText,History,LoaderCircle,Plus,Send,X} from 'lucide-react';
import {assistantClient} from './client';
import type {AssistantAction,AssistantContext,AssistantSource,Conversation,ContextCatalog,NavigationTarget} from './types';
import './assistant.css';

export interface LastroAssistantProps {base:string;token?:string;period?:string;batchId?:string|null;runId?:string|null;onNavigate?:(target:NavigationTarget)=>void;onRunCreated?:(runId:string)=>void}
const toolNames:Record<string,string>={available_contexts:'Competências e conjuntos',run_summary:'Resumo do fechamento',query_output:'Registros de resultado',trace_reference:'Rastro de origem',list_documents:'Documentos originais',compare_runs:'Comparação de execuções',prepare_close:'Preparação do processamento',open_documents:'Documentos'};
const month=(value:string)=>/^20\d{2}-\d{2}$/.test(value)?new Intl.DateTimeFormat('pt-BR',{month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(`${value}-01T00:00:00Z`)):value;
const initialCatalog:ContextCatalog={periods:[],batches:[],runs:[]};
const defaultPeriod=()=>new Date().toISOString().slice(0,7);

export function LastroAssistant({base,token='',period,batchId,runId,onNavigate,onRunCreated}:LastroAssistantProps) {
  const api=useMemo(()=>assistantClient(base,token),[base,token]);
  const [open,setOpen]=useState(false),[history,setHistory]=useState(false),[catalog,setCatalog]=useState(initialCatalog);
  const [conversations,setConversations]=useState<Conversation[]>([]),[conversation,setConversation]=useState<Conversation|null>(null);
  const [draft,setDraft]=useState<AssistantContext>({period:period||defaultPeriod(),batch_id:batchId||null,run_id:runId||null});
  const [text,setText]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[loading,setLoading]=useState(false);
  const [confirmation,setConfirmation]=useState<AssistantAction|null>(null),[actionBusy,setActionBusy]=useState(false);
  const trigger=useRef<HTMLButtonElement>(null),panel=useRef<HTMLElement>(null),input=useRef<HTMLTextAreaElement>(null),bottom=useRef<HTMLDivElement>(null);
  const storageKey=`lastro-assistant-v1:${base||'same-origin'}`;
  const current=conversation?.context||draft;
  const batches=catalog.batches.filter(b=>b.period===draft.period);
  const runs=catalog.runs.filter(r=>r.period===draft.period&&(!draft.batch_id||r.batch_id===draft.batch_id));
  const appChanged=!!conversation&&!!period&&(conversation.context.period!==period||conversation.context.run_id!==(runId||null)||conversation.context.batch_id!==(batchId||null));

  useEffect(()=>{if(!conversation)setDraft({period:period||defaultPeriod(),batch_id:batchId||null,run_id:runId||null});},[period,batchId,runId,conversation]);
  useEffect(()=>{
    if(!open)return;
    let alive=true;setLoading(true);setError('');
    const saved=localStorage.getItem(storageKey);
    void Promise.all([api.request<ContextCatalog>('/context'),api.request<{items:Conversation[]}>('/conversations'),!conversation&&saved?api.request<Conversation>(`/conversations/${encodeURIComponent(saved)}`).catch(()=>null):Promise.resolve(null)])
      .then(([context,list,savedConversation])=>{if(alive){setCatalog(context);setConversations(list.items);if(savedConversation)setConversation(savedConversation);}})
      .catch(e=>{if(alive)setError(e.message);}).finally(()=>{if(alive)setLoading(false);});
    input.current?.focus();return()=>{alive=false;};
  // Opening is the fetch trigger; a message updates history separately.
  },[open,api,storageKey]);
  useEffect(()=>{if(open)bottom.current?.scrollIntoView({behavior:'smooth',block:'nearest'});},[conversation?.messages.length,busy,open]);
  useEffect(()=>{
    if(!open)return;
    function key(e:KeyboardEvent) {
      if(e.key==='Escape'){setOpen(false);trigger.current?.focus();}
      if(e.key==='Tab'&&panel.current){
        const all=Array.from(panel.current.querySelectorAll<HTMLElement>('button:not(:disabled),input,select,textarea,a[href]')).filter(el=>el.offsetParent!==null);
        const first=all[0],last=all[all.length-1];
        if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}
        else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}
      }
    }
    document.addEventListener('keydown',key);return()=>document.removeEventListener('keydown',key);
  },[open]);

  function remember(next:Conversation){setConversation(next);localStorage.setItem(storageKey,next.id);}
  function fresh(){setConversation(null);setHistory(false);setConfirmation(null);setError('');localStorage.removeItem(storageKey);setDraft({period:period||defaultPeriod(),batch_id:batchId||null,run_id:runId||null});input.current?.focus();}
  async function resume(id:string){setLoading(true);setError('');try{remember(await api.request<Conversation>(`/conversations/${id}`));setHistory(false);}catch(e){setError((e as Error).message);}finally{setLoading(false);}}
  async function send(value=text){
    if(!value.trim()||busy||loading)return;setBusy(true);setError('');setText('');
    try{
      const active=conversation||await api.request<Conversation>('/conversations',draft);remember(active);
      const result=await api.request<Conversation>(`/conversations/${active.id}/messages`,{content:value.trim(),request_id:crypto.randomUUID()});remember(result);
      const list=await api.request<{items:Conversation[]}>('/conversations');setConversations(list.items);
    }catch(e){setError((e as Error).message);setText(value);}finally{setBusy(false);input.current?.focus();}
  }
  async function execute(action:AssistantAction){
    if(!conversation||actionBusy)return;setActionBusy(true);setError('');
    try{
      const result=await api.request<{run_id:string;status:string}>(`/conversations/${conversation.id}/actions/${action.id}`,{confirm:true});
      remember(await api.request<Conversation>(`/conversations/${conversation.id}`));setConfirmation(null);onRunCreated?.(result.run_id);setOpen(false);
    }catch(e){setError((e as Error).message);}finally{setActionBusy(false);}
  }
  function actionClick(action:AssistantAction){
    if(action.kind==='navigate'){onNavigate?.(action.target as unknown as NavigationTarget);setOpen(false);}
    else setConfirmation(action);
  }
  function sourceClick(source:AssistantSource){
    if(source.run_id&&onNavigate){
      const output=source.url.match(/\/outputs\/([^/]+)$/)?.[1];
      onNavigate({view:output?'results':'close',period:source.period,runId:source.run_id,output:output?decodeURIComponent(output):undefined});setOpen(false);
    }else void api.source(source.url,source.label).catch(e=>setError(e.message));
  }
  const close=()=>{setOpen(false);trigger.current?.focus();};

  return <div className="lastro-assistant-root">
    {open&&<div className="la-backdrop" onClick={close}/>}
    {open&&<section ref={panel} className="la-panel" role="dialog" aria-modal="true" aria-labelledby="la-title">
      <header className="la-header"><img src="/brand/lastro-symbol.svg" width="27" height="27" alt=""/><div><h2 id="la-title">Assistente Lastro</h2><span>Seu fechamento, com evidências.</span></div><button className="la-icon" aria-label="Fechar assistente" onClick={close}><X size={20}/></button></header>
      <div className="la-toolbar"><button onClick={()=>{setHistory(!history);setError('');}} disabled={busy}><History size={15}/>{history?'Voltar à conversa':'Conversas'}</button><button onClick={fresh} disabled={busy||actionBusy}><Plus size={15}/>Nova conversa</button></div>
      {history?<div className="la-history"><h3>Conversas deste espaço</h3><p>Histórico compartilhado do financeiro Tarvo.</p>{conversations.length===0?<p>Nenhuma conversa salva ainda.</p>:conversations.map(c=><button key={c.id} className={c.id===conversation?.id?'la-active':''} onClick={()=>void resume(c.id)}><span>{c.title}</span><small>{month(c.context.period)} · {new Date(c.updated_at).toLocaleDateString('pt-BR')}</small></button>)}</div>:<>
      <div className="la-context"><span className="la-eyebrow">Contexto da conversa</span>{conversation?<><strong>{month(current.period)}</strong><span>{catalog.batches.find(b=>b.id===current.batch_id)?.name||(current.batch_id?'Conjunto selecionado':'Sem conjunto selecionado')}</span><span>{current.run_id?`Execução ${current.run_id.slice(0,8)}`:'Sem execução selecionada'}</span>{appChanged&&<div className="la-context-alert">O painel mudou. Esta conversa mantém suas fontes originais.<button onClick={fresh} disabled={busy}>Conversar sobre o painel atual<ArrowUpRight size={13}/></button></div>}</>:<><div className="la-context-grid"><label>Competência<input aria-label="Competência do assistente" type="month" min="2000-01" max="2099-12" value={draft.period} onChange={e=>setDraft({period:e.target.value,batch_id:null,run_id:null})}/></label><label>Conjunto<select aria-label="Conjunto do assistente" value={draft.batch_id||''} onChange={e=>setDraft({...draft,batch_id:e.target.value||null,run_id:null})}><option value="">Selecionar conjunto</option>{batches.map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</select></label></div><label>Execução<select aria-label="Execução do assistente" value={draft.run_id||''} onChange={e=>{const r=catalog.runs.find(x=>x.run_id===e.target.value);setDraft({...draft,run_id:r?.run_id||null,batch_id:r?.batch_id||draft.batch_id});}}><option value="">Sem execução selecionada</option>{runs.map(r=><option key={r.run_id} value={r.run_id}>{r.run_id.slice(0,8)} · {r.status}</option>)}</select></label>{!batches.length&&!runs.length&&<p className="la-no-data">Nenhum dado disponível neste mês. Abra Documentos para carregar um conjunto.<button onClick={()=>{onNavigate?.({view:'documents',period:draft.period,newClosing:true});setOpen(false);}}>Carregar documentos<ArrowUpRight size={13}/></button></p>}</>}</div>
      <div className="la-messages" role="log" aria-live="polite" aria-relevant="additions text">
        {!conversation?.messages.length&&!busy&&<div className="la-welcome"><span className="la-eyebrow">Da pergunta à origem</span><h3>O que vamos conferir?</h3><p>Consulte resultados, encontre pendências ou prepare o próximo fechamento.</p>{['Quanto temos a faturar neste mês?','O que falta para concluir este fechamento?','Quais documentos estão neste conjunto?'].map(q=><button key={q} onClick={()=>void send(q)} disabled={loading}>{q}<ArrowUpRight size={15}/></button>)}</div>}
        {conversation?.messages.map(m=><article key={m.id} className={`la-message la-${m.role}`}><span className="la-speaker">{m.role==='user'?'Você':'Lastro'}</span><div className="la-message-text">{m.content}</div>{m.tool_events?.length? <details className="la-consulted"><summary>{m.tool_events.filter(t=>t.status==='completed').length} consultas realizadas</summary>{m.tool_events.map((t,i)=><div key={i}>{t.status==='completed'?<Check size={12}/>:<FileText size={12}/>} {toolNames[t.tool]||t.tool} · {t.status==='completed'?'consultado':'indisponível'}</div>)}</details>:null}{m.sources.length>0&&<div className="la-sources"><span>Fontes consultadas</span>{m.sources.map((s,i)=><button key={`${s.id}-${i}`} onClick={()=>sourceClick(s)}><FileText size={13}/><span>{s.label}{s.row_numbers?.length?` · linhas ${s.row_numbers.slice(0,4).join(', ')}${s.row_numbers.length>4?'…':''}`:''}</span><ArrowUpRight size={12}/></button>)}</div>}{m.actions.map(a=><div className="la-action" key={a.id}>{a.target_label&&<small>{a.target_label}</small>}<button disabled={a.status==='executing'||a.status==='failed'||actionBusy} onClick={()=>a.status==='completed'&&a.result?.run_id?(onRunCreated?.(a.result.run_id),close()):actionClick(a)}>{a.status==='completed'?'Abrir execução criada':a.label}<ArrowUpRight size={14}/></button>{a.status==='failed'&&<small>A ação não foi concluída. Consulte as execuções antes de tentar outra vez.</small>}</div>)}</article>)}
        {busy&&<div className="la-working" role="status"><LoaderCircle size={16} className="la-spin"/>Consultando as fontes selecionadas…</div>}
        <div ref={bottom}/>
      </div>
      {confirmation&&<div className="la-confirm"><strong>Processar este fechamento?</strong><p>{confirmation.target_label}</p>{confirmation.documents?.length?<details><summary>Conferir documentos selecionados</summary><ul>{confirmation.documents.map(d=><li key={d.id}>{d.name}</li>)}</ul></details>:null}<p>Será criada uma execução com os documentos selecionados. A aprovação financeira continua pendente.</p><div><button onClick={()=>setConfirmation(null)} disabled={actionBusy}><ChevronLeft size={14}/>Voltar</button><button className="la-primary" onClick={()=>void execute(confirmation)} disabled={actionBusy}>{actionBusy?<LoaderCircle size={14} className="la-spin"/>:<Check size={14}/>}Confirmar processamento</button></div></div>}
      <form className="la-composer" onSubmit={e=>{e.preventDefault();void send();}}><label className="la-sr" htmlFor="la-question">Pergunta ao assistente Lastro</label><textarea ref={input} id="la-question" value={text} onChange={e=>setText(e.target.value)} maxLength={6000} rows={2} disabled={busy} placeholder="Pergunte sobre este fechamento…" onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();void send();}}}/><button type="submit" aria-label="Enviar pergunta" className="la-primary" disabled={busy||loading||!text.trim()||!draft.period}><Send size={18}/></button></form>
      </>}
      {loading&&<div className="la-loading" role="status"><LoaderCircle size={14} className="la-spin"/>Carregando conversas…</div>}
      {error&&<div className="la-error" role="alert">{error}<button aria-label="Fechar aviso" onClick={()=>setError('')}><X size={14}/></button></div>}
      <footer className="la-footer">Valores preparados dependem da revisão do financeiro.</footer>
    </section>}
    <button ref={trigger} className="la-trigger" aria-label={open?'Fechar assistente Lastro':'Abrir assistente Lastro'} aria-expanded={open} aria-haspopup="dialog" onClick={()=>open?close():setOpen(true)}>{open?<X size={23}/>:<img src="/brand/lastro-symbol.svg" alt="" width="26" height="26"/>}<span>{open?'Fechar':'Lastro'}</span></button>
  </div>;
}
export default LastroAssistant;
