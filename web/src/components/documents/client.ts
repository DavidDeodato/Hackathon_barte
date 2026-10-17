import type { DocumentBatch, DocumentRole, DocumentsClient, OriginalDocument } from './types';
import { DOCUMENT_ROLES } from './types';

const ROLES = new Set(DOCUMENT_ROLES.map((role) => role.value));
const record = (value: unknown): Record<string, unknown> => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('A lista de documentos chegou em um formato inesperado. Atualize e tente novamente.');
  return value as Record<string, unknown>;
};
const text = (value: unknown) => typeof value === 'string' ? value : '';
function batch(value: unknown): DocumentBatch {
  const row = record(value);
  if (!text(row.id) || !text(row.name) || !/^\d{4}-(0[1-9]|1[0-2])$/.test(text(row.period))) throw new Error('Um conjunto recebido está sem identificação ou competência válida.');
  return { id: text(row.id), name: text(row.name), period: text(row.period), created_at: text(row.created_at) || undefined, document_count: typeof row.documents_count === 'number' ? row.documents_count : undefined };
}
function document(value: unknown): OriginalDocument {
  const row = record(value);
  if (!text(row.id) || !text(row.batch_id) || !text(row.name) || typeof row.size_bytes !== 'number' || !Number.isFinite(row.size_bytes) || row.size_bytes < 0) throw new Error('Um documento recebido está sem identificação ou tamanho válido.');
  return { id: text(row.id), batch_id: text(row.batch_id), name: text(row.name), media_type: text(row.media_type), size_bytes: row.size_bytes, created_at: text(row.uploaded_at) || undefined, sha256: text(row.sha256) || undefined, role: ROLES.has(row.role as DocumentRole) ? row.role as DocumentRole : null };
}

/** INT DOCUMENTS_CONTRACT R013 v1. Session cookies; bearer only for existing integrations. */
export function createDocumentsClient(base: string, token = ''): DocumentsClient {
  const prefix = base.replace(/\/$/, '');
  async function request(path: string, init: RequestInit = {}, signal?: AbortSignal): Promise<Response> {
    let response: Response;
    try {
      response = await fetch(`${prefix}${path}`, { ...init, credentials: 'include', headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers }, signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(init.body instanceof FormData ? 90000 : 25000)]) : AbortSignal.timeout(25000) });
    } catch (error) {
      if (signal?.aborted) throw error;
      throw new Error('Não foi possível acessar os documentos. Confira sua conexão e tente novamente.');
    }
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      if (response.status === 401) window.dispatchEvent(new Event('lastro:session-expired'));
      const message = response.status === 401 ? 'Sua sessão terminou. Entre novamente para continuar.' : response.status === 403 ? 'Você não tem acesso a este conjunto de documentos.' : payload?.error?.message;
      throw new Error(typeof message === 'string' ? message : `Não foi possível concluir a operação com o arquivo (HTTP ${response.status}).`);
    }
    return response;
  }
  async function list<T>(path: string, map: (value: unknown) => T, signal?: AbortSignal): Promise<T[]> {
    const items: T[] = []; let cursor: string | null = null; const seen = new Set<string>();
    for (let page = 0; page < 100; page += 1) {
      const response = await request(`${path}?limit=200${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`, {}, signal);
      const payload = record(await response.json());
      if (!Array.isArray(payload.items)) throw new Error('Não foi possível conferir a lista recebida. Atualize os documentos.');
      items.push(...payload.items.map(map));
      if (payload.next_cursor == null) return items;
      if (typeof payload.next_cursor !== 'string' || !payload.next_cursor || seen.has(payload.next_cursor)) throw new Error('A consulta de documentos ficou incompleta. Atualize e tente novamente.');
      cursor = payload.next_cursor; seen.add(cursor);
    }
    throw new Error('Há muitos conjuntos para esta consulta. A lista não foi apresentada como completa.');
  }
  return {
    listBatches: (signal) => list('/api/batches', batch, signal),
    createBatch: async (name, period, signal) => batch(await (await request('/api/batches', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, period }) }, signal)).json()),
    listDocuments: (id, signal) => list(`/api/batches/${encodeURIComponent(id)}/documents`, document, signal),
    upload: async (id, file, role, signal) => {
      const data = new FormData(); data.append('file', file, file.name); if (role) data.append('role', role);
      return document(await (await request(`/api/batches/${encodeURIComponent(id)}/documents`, { method: 'POST', body: data }, signal)).json());
    },
    setRole: async (id, role, signal) => document(await (await request(`/api/documents/${encodeURIComponent(id)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role }) }, signal)).json()),
    original: async (_batchId, doc, signal, download = false) => {
      const response = await request(`/api/documents/${encodeURIComponent(doc.id)}/original?download=${download ? 'true' : 'false'}`, {}, signal);
      return { blob: await response.blob(), filename: doc.name, mediaType: response.headers.get('Content-Type')?.split(';')[0] || doc.media_type };
    },
  };
}
