import type {Investigation} from './api';
const MODES={deterministic:'Consulta às fontes',llm:'Investigação com IA',replay:'Consulta a registro anterior'};
const metric=(value:unknown)=>value==null?'—':String(value);
export default function InvestigationMetrics({result}: {result:Investigation}){
  return <section className="investigation-metrics" aria-label="Método da investigação"><span className="small-label">{result.mode?MODES[result.mode]??'Análise registrada':'Análise registrada'}</span>{!!result.model_metrics?.length&&<details><summary>Registro de processamento</summary><div className="table-scroll"><table><thead><tr><th>Modelo</th><th>Estado</th><th>Tokens de entrada</th><th>Tokens de saída</th><th>Tempo (ms)</th><th>Custo registrado (R$)</th></tr></thead><tbody>{result.model_metrics.map((item,index)=><tr key={index}><td>{metric(item.model)}</td><td>{metric(item.status)}</td><td>{metric(item.input_tokens)}</td><td>{metric(item.output_tokens)}</td><td>{metric(item.latency_ms)}</td><td>{metric(item.cost_brl)}</td></tr>)}</tbody></table></div></details>}</section>;
}
