import {FileText,GitPullRequest} from 'lucide-react';
import type {JsonRecord} from './api';
const printable=(value:unknown)=>value==null?'Não informado':typeof value==='object'?JSON.stringify(value):String(value);
export function EvidenceCard({item,index}: {item:unknown;index:number}){
  if(!item || typeof item!=='object')return <p className="evidence-block">{printable(item)}</p>;
  const record=item as JsonRecord;const data=record.data&&typeof record.data==='object'?record.data as JsonRecord:record;
  const refs=Array.isArray(record.source_refs)?record.source_refs:Array.isArray(data.source_refs)?data.source_refs:[];
  const excerpt=printable(data.text??data.excerpt??data.summary??'Consulte o registro completo abaixo.');
  return <article className="source-evidence"><div className="source-evidence-heading"><FileText size={17}/><strong>{printable(data.title??data.id??record.id??`Evidência ${index+1}`)}</strong></div><p>{excerpt.length>420?excerpt.slice(0,420)+'…':excerpt}</p><div className="source-reference">{refs.map((ref,i)=><code key={i}>{printable(ref)}</code>)}</div>{data.authority!=null&&<p className="evidence-authority"><strong>Autoridade citada na fonte:</strong> {printable(data.authority)}</p>}<details><summary>Ler registro completo</summary><pre>{JSON.stringify(record,null,2)}</pre></details></article>;
}
export function ProposalCard({item,index}: {item:unknown;index:number}){
  if(!item||typeof item!=='object')return <p className="evidence-block proposal">{printable(item)}</p>;
  const record=item as JsonRecord;
  const labels:Record<string,string>={source_refs:'Fontes da proposta',scope:'Alcance',valid_from:'Válida a partir de',valid_to:'Válida até',exceptions:'Exceções',required_authority:'Autoridade necessária',authority_evidence_refs:'Evidências de aprovação específica'};
  return <article className="proposal-card"><div className="source-evidence-heading"><GitPullRequest size={17}/><strong>{printable(record.id??`Proposta ${index+1}`)}</strong></div><p>Proposta em revisão · nenhuma alteração aplicada ao cálculo</p><dl>{Object.entries(labels).map(([key,label])=><div key={key}><dt>{label}</dt><dd>{record[key]==null||(Array.isArray(record[key])&&record[key].length===0)?'Não informado':printable(record[key])}</dd></div>)}</dl><div className="proposal-impact"><span>Impacto financeiro</span><strong>Não calculado</strong></div><details><summary>Ver proposta integral</summary><pre>{JSON.stringify(record,null,2)}</pre></details></article>;
}
