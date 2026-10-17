export type JsonRecord = Record<string, unknown>;
export interface Run {
  run_id: string; period: string; status: string; created_at?: string; updated_at?: string;
  summary: JsonRecord; issues: unknown[]; outputs: unknown[];
  error?: {code: string; message: string} | null;
}
export type { AgentEvent } from './components/mission-control/types';
import type { AgentEvent } from './components/mission-control/types';
export interface Output {
  name: string; size_bytes?: number; url?: string;
  preview?: {columns: string[]; rows: (JsonRecord | unknown[])[]; total_rows?: number; truncated?: boolean};
}
export interface Investigation {
  investigation_id?: string; id?: string; status: string; answer?: string;
  evidence?: unknown[]; proposed_changes?: unknown[]; limitations?: string[]; result?: Investigation;
  error?: {code?: string; message?: string} | string;
  mode?: 'deterministic'|'llm'|'replay'; model_called?: boolean;
  model_metrics?: {provider?:string;model?:string;call_index?:number;latency_ms?:number|null;input_tokens?:number|null;output_tokens?:number|null;total_tokens?:number|null;http_status?:number|null;status?:string;cost_brl?:number|string|null}[];
}
export interface ComparisonJob {
  comparison_id: string; before_run_id?: string; after_run_id?: string; status: string;
  result?: {status:string;before_run_id:string;after_run_id:string;input_changes:unknown[];outputs:{name:string;added:JsonRecord[];removed:JsonRecord[];changed:JsonRecord[];unchanged_count:number;totals_by_nature?:unknown}[];limitations:string[]};
  error?: {code?:string;message?:string} | null;
}
export class ApiError extends Error { constructor(message: string, public status?: number) {super(message);} }

export function makeApi(base: string, token: string) {
  const prefix = base.replace(/\/$/, '');
  async function request<T>(path: string, init?: RequestInit, signal?: AbortSignal): Promise<T> {
    let response: Response;
    try {
      response = await fetch(`${prefix}${path}`, {...init, signal: signal ? AbortSignal.any([signal,AbortSignal.timeout(25000)]) : AbortSignal.timeout(25000), headers: {
        ...(init?.body ? {'Content-Type': 'application/json'} : {}),
        ...(token ? {Authorization: `Bearer ${token}`} : {}), ...init?.headers,
      }});
    } catch (error) {
      if (signal?.aborted) throw error;
      throw new ApiError('Não foi possível acessar a API. Verifique a conexão e tente novamente.');
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new ApiError(body?.error?.message || (response.status === 401 ? 'Sessão não autorizada. Confira o token de acesso.' : `API retornou HTTP ${response.status}.`), response.status);
    }
    return response.json();
  }
  return {
    health: (signal?: AbortSignal) => request<JsonRecord>('/api/health', undefined, signal),
    runs: (signal?: AbortSignal) => request<{items: Run[]}>('/api/runs', undefined, signal),
    run: (id: string, signal?: AbortSignal) => request<Run>(`/api/runs/${encodeURIComponent(id)}`, undefined, signal),
    create: (period: string) => request<{run_id: string; status: string}>('/api/runs', {method: 'POST', body: JSON.stringify({period})}),
    events: (id: string, cursor?: string | null, signal?: AbortSignal) => request<{items: AgentEvent[]; next_cursor: string | null}>(`/api/runs/${encodeURIComponent(id)}/events${cursor ? `?after=${encodeURIComponent(cursor)}` : ''}`, undefined, signal),
    outputs: (id: string, signal?: AbortSignal) => request<{items: Output[]}>(`/api/runs/${encodeURIComponent(id)}/outputs`, undefined, signal),
    outputText: async (id: string,name: string) => {
      const response=await fetch(`${prefix}/api/runs/${encodeURIComponent(id)}/outputs/${encodeURIComponent(name)}`,{headers:token ? {Authorization:`Bearer ${token}`} : {},signal:AbortSignal.timeout(25000)});
      if(!response.ok) throw new ApiError(`Arquivo indisponível (HTTP ${response.status}).`,response.status);
      return response.text();
    },
    investigate: (id: string, question: string, mode: 'deterministic'|'llm' = 'deterministic') => request<Investigation>(`/api/runs/${encodeURIComponent(id)}/investigations`, {method: 'POST', body: JSON.stringify({question,mode})}),
    investigation: (id: string, iid: string, signal?: AbortSignal) => request<Investigation>(`/api/runs/${encodeURIComponent(id)}/investigations/${encodeURIComponent(iid)}`, undefined, signal),
    compare: (before: string,after: string) => request<ComparisonJob>('/api/comparisons',{method:'POST',body:JSON.stringify({before_run_id:before,after_run_id:after})}),
    comparison: (id: string,signal?:AbortSignal) => request<ComparisonJob>(`/api/comparisons/${encodeURIComponent(id)}`,undefined,signal),
    download: async (id: string, name: string) => {
      const response = await fetch(`${prefix}/api/runs/${encodeURIComponent(id)}/outputs/${encodeURIComponent(name)}`, {headers: token ? {Authorization: `Bearer ${token}`} : {}, signal: AbortSignal.timeout(25000)});
      if (!response.ok) throw new ApiError(`Não foi possível baixar o arquivo (HTTP ${response.status}).`, response.status);
      const url = URL.createObjectURL(await response.blob());
      const a = document.createElement('a'); a.href = url; a.download = name; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
  };
}
