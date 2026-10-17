import {useMemo,useState} from 'react';

import {ArrowDownToLine,ArrowRight,ChevronRight,Clock3,CreditCard,FileText,Globe2,Layers3,Search,ShieldCheck} from 'lucide-react';

import type {JsonRecord,Output,Run} from './api';



export const outputLabel=(name:string)=>({ 'comissoes_por_lojista.csv':'Comissões por lojista','divergencias_taxa.csv':'Diferenças de taxa','notas_a_emitir.csv':'Notas a emitir','lancamentos_classificados.csv':'Classificação bancária','pendencias.csv':'Pendências','rastro.csv':'Rastro de evidências'}[name]??name.replace(/\.csv$/,'').replaceAll('_',' '));

export function formatMoney(value:unknown){if(typeof value!=='string'||!/^[-]?\d+(\.\d{1,2})?$/.test(value))return null;const [whole,decimal='00']=value.split('.');return `R$ ${whole.replace(/\B(?=(\d{3})+(?!\d))/g,'.')},${decimal.padEnd(2,'0')}`;}

export function outputRows(output?:Output):JsonRecord[]{return(output?.preview?.rows??[]).map(row=>Array.isArray(row)?Object.fromEntries((output?.preview?.columns??[]).map((key,i)=>[key,row[i]])):row);}

const TITLES:Record<string,string>={DEVOLUCAO_CASA:'Devolução · Casa',CONTRATO_NAO_CONFIRMADO:'Contrato · Atlas',ANTECIPACAO_SEM_LASTRO_CONFIRMADO:'Antecipação sem lastro',CONTESTACAO_ORBE:'Contestar diferença · Orbe',DUPLICATA_PONTE:'Duplicidade · Ponte',SPREAD_NEGATIVO_CONTESTAR:'Spread negativo',CONTESTACAO_PONTE:'Contestar spread · Ponte',CONFERIR_RECEBIMENTO_PONTE:'Recebimento · Ponte',CREDITO_NAO_IDENTIFICADO:'Crédito a identificar',DEVOLUCAO_REPASSE:'Repasse devolvido',TRANSFERENCIA_EM_TRANSITO:'Transferência em trânsito',ADIANTAMENTO_REMESSA_OUTUBRO:'Adiantamento · outubro',AJUSTES_TARDIOS_NAO_INCORPORADOS:'Ajustes tardios',COMISSAO_NEGATIVA:'Comissão negativa'};

export const issueTitle=(row:JsonRecord)=>TITLES[String(row.tipo)]??String(row.tipo??row.title??'Revisão necessária').replaceAll('_',' ');

export const caseKeyFor=(row:JsonRecord)=>String(row.tipo)==='DEVOLUCAO_CASA'?'casa':String(row.ref_origem)==='1076801732'?'atlas':null;

export function FileTile({output,onOpen}:{output:Output;onOpen:()=>void}){return <button className="file-tile" onClick={onOpen}><div className="file-identity" aria-hidden="true"><FileText size={28}/><span>CSV</span></div><span className="file-title">{outputLabel(output.name)}</span><span className="file-meta">{output.preview?.total_rows??'—'} registros <ArrowRight size={13}/></span></button>}

export function IssueCards({rows,selected,onSelect}:{rows:JsonRecord[];selected?:JsonRecord|null;onSelect:(row:JsonRecord)=>void}){return <div className="carbon-issue-list">{rows.map((row,i)=><button key={String(row.id_saida??i)} className={`carbon-issue ${selected?.id_saida===row.id_saida?'is-selected':''}`} onClick={()=>onSelect(row)}><span className="issue-icon"><Clock3 size={19}/></span><span className="issue-content"><span className="issue-title">{issueTitle(row)}</span><strong>{formatMoney(row.valor_brl)??'Valor não quantificado'}</strong><small>{String(row.metrica_valor??'Natureza não informada')}</small><span className="issue-owner">{String(row.quem_decide??'Responsável não informado')}</span></span><span className="issue-side"><span className="review-pill"><i/>Revisão pendente</span><ChevronRight size={18}/></span></button>)}</div>}



export default function CarbonOverview({run,outputs,onOutput,onAllIssues,onRecord,onInvestigate,onCase}:{run:Run|null;outputs:Output[];onOutput:(name:string)=>void;onAllIssues:()=>void;onRecord:(row:JsonRecord)=>void;onInvestigate:(question?:string)=>void;onCase:(key:string)=>void}){

 const rows=useMemo(()=>{const all=outputRows(outputs.find(x=>x.name==='pendencias.csv'));return [...all].sort((a,b)=>Number(b.tipo==='DEVOLUCAO_CASA')-Number(a.tipo==='DEVOLUCAO_CASA'));},[outputs]);

 const [inspectorOpen,setInspectorOpen]=useState(false);

 const [selection,setSelection]=useState<string|null>(null);

 const selected=rows.find(x=>x.id_saida===selection)??rows[0];

 const [scope,setScope]=useState<'all'|'commercial'>('all');

 const filtered=scope==='commercial'?rows.filter(x=>String(x.quem_decide).toLowerCase().includes('comercial')):rows;

 const key=run?.period==='2026-09'&&selected?caseKeyFor(selected):null;

 return <div className={`carbon-workspace ${inspectorOpen?'is-inspecting':''}`}>

  <div className="carbon-main">

   <section className="money-strip" aria-label="Comissões da execução">{[{label:'Comissão checkout',value:run?.summary?.checkout_commission_brl,icon:CreditCard},{label:'Comissão remessas',value:run?.summary?.remessa_commission_brl,icon:Globe2}].map(({label,value,icon:Icon},i)=><button className="money-cell" key={label} onClick={()=>onOutput('comissoes_por_lojista.csv')} disabled={!outputs.length}><span className={`money-icon tone-${i}`}><Icon size={23}/></span><span><small>{label}</small><strong>{formatMoney(value)??'—'}</strong><span className="money-caption">{!run?'Aguardando apuração':['queued','running','processing'].includes(run.status)?'Apurando documentos':run.status==='failed'?'Apuração não concluída':run.status==='pending_review'?'Apurado · revisão pendente':'Apurado'}</span></span><ChevronRight size={17}/></button>)}</section>

   <div className="carbon-workgrid">

    <section className="surface review-queue"><div className="section-heading"><h2>Revisões pendentes <span className="count-badge">{rows.length||'—'}</span></h2><div className="pill-tabs" aria-label="Filtrar revisões"><button className={scope==='all'?'selected':''} onClick={()=>setScope('all')}>Todas</button><button className={scope==='commercial'?'selected':''} onClick={()=>setScope('commercial')}>Comercial</button></div></div>{filtered.length?<IssueCards rows={filtered.slice(0,4)} selected={selected} onSelect={row=>{setSelection(String(row.id_saida));setInspectorOpen(true);if(window.matchMedia('(max-width:680px)').matches)window.scrollTo({top:0,behavior:'smooth'});}}/>:<div className="carbon-empty"><Clock3 size={25}/><h3>{run?.status==='failed'?'Fechamento não concluído':run&&['queued','running'].includes(run.status)?'Apuração em andamento':run?'Nenhuma pendência nesta seleção':'Selecione um fechamento'}</h3><p>{run?.status==='failed'?'Revise os documentos e o motivo informado para retomar a apuração.':'Os casos aparecem com os dados da apuração.'}</p></div>}<button className="queue-more" onClick={onAllIssues}><Layers3 size={17}/>Ver todas as pendências<ArrowRight size={17}/></button></section>

    <section className="surface document-library"><div className="section-heading"><h2>Arquivos <span className="count-badge">{outputs.length}</span></h2><FileText size={17}/></div><div className="document-grid">{outputs.slice(0,4).map(output=><FileTile key={output.name} output={output} onOpen={()=>onOutput(output.name)}/>)}</div>{!outputs.length&&<div className="carbon-empty"><FileText size={27}/><p>Arquivos disponíveis após a apuração.</p></div>}{outputs.length>0&&<button className="queue-more" onClick={()=>onOutput(outputs[0].name)}><ArrowDownToLine size={15}/>Explorar {outputs.length} arquivos<ArrowRight size={15}/></button>}</section>

   </div>

  </div>

  <aside className="carbon-inspector" aria-label="Caso selecionado"><button className="inspector-back" onClick={()=>setInspectorOpen(false)}><ArrowRight size={16} style={{transform:'rotate(180deg)'}}/>Voltar às revisões</button><div className="inspector-top"><span className="inspector-kicker">EM REVISÃO</span><ShieldCheck size={18}/></div>{selected?<><div className="inspector-case"><span className="review-pill"><i/>Decisão pendente</span><h2>{issueTitle(selected)}</h2><strong className="inspector-amount">{formatMoney(selected.valor_brl)??'Não quantificado'}</strong><p>{String(selected.metrica_valor??'')}</p></div><div className="inspector-owner"><UsersIcon/><span><small>Quem decide</small><strong>{String(selected.quem_decide??'Não informado')}</strong></span></div><button className="button inspector-action" onClick={()=>key?onCase(key):onRecord(selected)}><FileText size={17}/>{key?'Abrir mesa de revisão':'Ver evidências'}<ArrowRight size={17}/></button><section className="inspector-section"><h3>O que precisa de decisão</h3><p>{String(selected.motivo??'Motivo não informado.')}</p></section><details className="inspector-section"><summary>Fonte da regra<ChevronRight size={15}/></summary><p className="reference-text">{String(selected.regra_fonte??'Não informada')}</p></details><details className="inspector-section"><summary>Registro de origem<ChevronRight size={15}/></summary><p className="reference-text">{String(selected.ref_origem??'Não informado')}</p><button className="text-button" onClick={()=>onRecord(selected)}>Conferir rastro<ArrowRight size={14}/></button></details><button className="inspector-investigate" onClick={()=>onInvestigate(`Investigue a pendência ${selected.id_saida}: ${selected.motivo}`)}><Search size={18}/>Investigar este caso<ArrowRight size={15}/></button></>:<div className="carbon-empty"><ShieldCheck size={30}/><h3>Uma decisão com lastro.</h3><p>Selecione uma pendência para conferir valor, fonte e responsável.</p></div>}<p className="inspector-foot">A análise prepara a decisão. A aprovação financeira permanece com Helena.</p></aside>

 </div>

}

function UsersIcon(){return <span className="owner-avatar">H</span>}

