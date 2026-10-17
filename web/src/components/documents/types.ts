export interface DocumentBatch {
  id: string;
  name: string;
  period: string;
  created_at?: string;
  document_count?: number;
}

/** UI projection only. The client maps the real INT wire contract to these fields. */
export interface OriginalDocument {
  id: string;
  batch_id: string;
  name: string;
  media_type: string;
  size_bytes: number;
  created_at?: string;
  sha256?: string;
  role: DocumentRole | null;
}

export type DocumentRole = 'orbe' | 'contracts' | 'remessa' | 'accounts' | 'aurora' | 'meridiano' | 'adjustments';
export const DOCUMENT_ROLES: { value: DocumentRole; label: string; required: boolean }[] = [
  { value: 'orbe', label: 'Transações de checkout · Orbe', required: true },
  { value: 'contracts', label: 'Taxas e contratos', required: true },
  { value: 'remessa', label: 'Remessas · Ponte', required: true },
  { value: 'accounts', label: 'Plano de contas', required: true },
  { value: 'aurora', label: 'Extrato Aurora', required: true },
  { value: 'meridiano', label: 'Extrato Meridiano', required: true },
  { value: 'adjustments', label: 'Ajustes adicionais', required: false },
];

export interface OriginalFile {
  blob: Blob;
  filename: string;
  mediaType: string;
}

export interface DocumentsClient {
  listBatches(signal?: AbortSignal): Promise<DocumentBatch[]>;
  createBatch(name: string, period: string, signal?: AbortSignal): Promise<DocumentBatch>;
  listDocuments(batchId: string, signal?: AbortSignal): Promise<OriginalDocument[]>;
  upload(batchId: string, file: File, role?: DocumentRole | null, signal?: AbortSignal): Promise<OriginalDocument>;
  setRole(documentId: string, role: DocumentRole | null, signal?: AbortSignal): Promise<OriginalDocument>;
  original(batchId: string, document: OriginalDocument, signal?: AbortSignal, download?: boolean): Promise<OriginalFile>;
}

export interface DocumentsNavigationRequest {
  requestId: number;
  batchId?: string;
  create?: boolean;
  /** Prefill for creation only. An existing batch keeps its own period. */
  period?: string;
}

export interface DocumentsWorkspaceProps {
  base: string;
  token?: string;
  onProcess: (batchId: string, documentIds: string[], period: string) => Promise<void>;
  onBatchChange?: (batchId: string | null, period: string) => void;
  createRequest?: number;
  navigationRequest?: DocumentsNavigationRequest;
  /** Optional for embedding and QA; normal operation uses the real HTTP client. */
  client?: DocumentsClient;
}

export interface BatchSelectorProps {
  batches: DocumentBatch[];
  value: string;
  onChange: (id: string) => void;
  disabled?: boolean;
  loading?: boolean;
}
