import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Check, Download, ExternalLink, FileText, FolderOpen, LoaderCircle, Plus, RefreshCw, UploadCloud, X } from 'lucide-react';
import BatchSelector from './BatchSelector';
import { createDocumentsClient } from './client';
import { previewOriginal, releasePreview } from './preview';
import type { DocumentPreview } from './preview';
import { formatBytes, selectionIssues } from './selection';
import { DOCUMENT_ROLES } from './types';
import type { DocumentBatch, DocumentRole, DocumentsNavigationRequest, DocumentsWorkspaceProps, OriginalDocument, OriginalFile } from './types';
import './documents.css';

export type { DocumentsWorkspaceProps, DocumentsNavigationRequest, DocumentBatch, DocumentRole, OriginalDocument, DocumentsClient } from './types';
type UploadItem = { id: string; name: string; state: 'waiting' | 'sending' | 'received' | 'error' | 'cancelled'; message?: string };
const ACCEPT = '.csv,.xlsx,.xls,.ofx,.eml,.pdf,.docx,.txt,.json';
const MAX_SIZE = 30 * 1024 * 1024;
const message = (reason: unknown) => reason instanceof Error ? reason.message : 'Não foi possível concluir esta ação.';
function download(file: OriginalFile) {
  const url = URL.createObjectURL(file.blob); const link = document.createElement('a');
  link.href = url; link.download = file.filename; link.rel = 'noopener'; document.body.append(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function DocumentsWorkspace({ base, token = '', onProcess, onBatchChange, createRequest, navigationRequest, client: suppliedClient }: DocumentsWorkspaceProps) {
  const client = useMemo(() => suppliedClient ?? createDocumentsClient(base, token), [base, token, suppliedClient]);
  const [batches, setBatches] = useState<DocumentBatch[]>([]);
  const [batchId, setBatchId] = useState('');
  const [batchLoading, setBatchLoading] = useState(true);
  const [batchError, setBatchError] = useState('');
  const [documents, setDocuments] = useState<OriginalDocument[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [docsError, setDocsError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [creating, setCreating] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState('');
  const [period, setPeriod] = useState('');
  const [createError, setCreateError] = useState('');
  const [uploadRole, setUploadRole] = useState<DocumentRole | ''>('');
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [uploading, setUploading] = useState(false);
  const [roleSaving, setRoleSaving] = useState('');
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [processing, setProcessing] = useState(false);
  const [processMessage, setProcessMessage] = useState('');
  const [processError, setProcessError] = useState('');
  const [opened, setOpened] = useState<OriginalDocument | null>(null);
  const [original, setOriginal] = useState<OriginalFile | null>(null);
  const [preview, setPreview] = useState<DocumentPreview | null>(null);
  const [opening, setOpening] = useState(false);
  const [openError, setOpenError] = useState('');
  const [downloading, setDownloading] = useState('');
  const [pendingNavigation, setPendingNavigation] = useState<DocumentsNavigationRequest | null>(null);
  const [navigationLoading, setNavigationLoading] = useState(false);
  const [navigationError, setNavigationError] = useState('');
  const navigationSeen = useRef(new Set<number>());
  const allCheckbox = useRef<HTMLInputElement>(null);
  const previewFocus = useRef<HTMLDivElement>(null);
  const originalOpener = useRef<HTMLElement | null>(null);
  const uploadAbort = useRef<AbortController | null>(null);
  const operations = useRef(new AbortController());
  const generation = useRef(0);
  const firstSelection = useRef<string | null>(null);
  const batchCallback = useRef(onBatchChange);
  const uploadInput = useId(); const createId = useId(); const titleId = useId();
  const activeBatch = batches.find((batch) => batch.id === batchId);
  const picked = documents.filter((doc) => selected.has(doc.id));
  const financialDocuments = documents.filter((doc) => doc.role && doc.media_type !== 'application/pdf');
  const problems = selectionIssues(picked);
  const operationBusy = creating || uploading || processing || Boolean(roleSaving);
  const busy = operationBusy || navigationLoading;
  const canProcess = Boolean(activeBatch && picked.length && !problems.length && !busy && !docsLoading && !docsError);

  useEffect(() => { batchCallback.current = onBatchChange; }, [onBatchChange]);
  useEffect(() => { if (createRequest && createRequest > 0) setCreateOpen(true); }, [createRequest]);
  useEffect(() => {
    if (!navigationRequest || navigationSeen.current.has(navigationRequest.requestId)) return;
    if (!Number.isSafeInteger(navigationRequest.requestId) || navigationRequest.requestId < 0) { setNavigationError('Não foi possível identificar a solicitação de documentos. Tente abrir o conjunto novamente.'); return; }
    navigationSeen.current.add(navigationRequest.requestId);
    setPendingNavigation({ ...navigationRequest }); setNavigationError('');
  }, [navigationRequest]);
  useEffect(() => {
    if (!pendingNavigation || operationBusy || batchLoading) return;
    const request = pendingNavigation; const target = request.batchId?.trim();
    setNavigationLoading(false);
    if (target) {
      const known = batches.find((item) => item.id === target);
      if (known) { setBatchId(known.id); setCreateOpen(false); setPendingNavigation(null); return; }
      const controller = new AbortController(); setNavigationLoading(true);
      void client.listBatches(controller.signal).then((items) => {
        if (controller.signal.aborted) return;
        setNavigationLoading(false); setBatches(items); const found = items.find((item) => item.id === target);
        if (found) { setBatchId(found.id); setCreateOpen(false); }
        else setNavigationError('O conjunto solicitado não foi encontrado. Escolha um conjunto disponível ou crie um novo.');
        setPendingNavigation(null);
      }).catch((reason) => { if (!controller.signal.aborted) { setNavigationLoading(false); setNavigationError(message(reason)); setPendingNavigation(null); } });
      return () => controller.abort();
    }
    if (!request.create) setNavigationError('Escolha um conjunto ou solicite a criação de um novo fechamento.');
    else if (request.period !== undefined && !/^\d{4}-(0[1-9]|1[0-2])$/.test(request.period)) setNavigationError('A competência solicitada é inválida. Abra um novo conjunto e escolha o mês.');
    else { setName(''); setPeriod(request.period ?? ''); setCreateError(''); setCreateOpen(true); }
    setPendingNavigation(null);
  }, [pendingNavigation, operationBusy, batchLoading, batches, client]);
  useEffect(() => {
    const controller = new AbortController(); operations.current = controller; generation.current += 1;
    setBatches([]); setBatchId(''); setBatchLoading(true); setBatchError('');
    void client.listBatches(controller.signal).then((items) => {
      if (!controller.signal.aborted) { setBatches(items); setBatchId(items[0]?.id ?? ''); }
    }).catch((reason) => { if (!controller.signal.aborted) setBatchError(message(reason)); }).finally(() => { if (!controller.signal.aborted) setBatchLoading(false); });
    return () => { controller.abort(); uploadAbort.current?.abort(); };
  }, [client]);
  useEffect(() => {
    generation.current += 1; setSelected(new Set()); setOpened(null); setUploads([]); setRowErrors({}); setProcessError(''); setProcessMessage('');
    firstSelection.current = activeBatch?.id ?? null;
    batchCallback.current?.(activeBatch?.id ?? null, activeBatch?.period ?? '');
  }, [activeBatch?.id, activeBatch?.period]);
  useEffect(() => {
    const controller = new AbortController(); setDocuments([]); setDocsError('');
    if (!batchId) { setDocsLoading(false); return () => controller.abort(); }
    setDocsLoading(true);
    void client.listDocuments(batchId, controller.signal).then((items) => { if (!controller.signal.aborted) { setDocuments(items); if (firstSelection.current === batchId) { setSelected(new Set(items.filter((doc) => doc.role && doc.media_type !== 'application/pdf').map((doc) => doc.id))); firstSelection.current = null; } else setSelected((ids) => new Set([...ids].filter((id) => items.some((doc) => doc.id === id)))); } })
      .catch((reason) => { if (!controller.signal.aborted) setDocsError(message(reason)); }).finally(() => { if (!controller.signal.aborted) setDocsLoading(false); });
    return () => controller.abort();
  }, [client, batchId, refresh]);
  useEffect(() => { const count = financialDocuments.filter((doc) => selected.has(doc.id)).length; if (allCheckbox.current) allCheckbox.current.indeterminate = count > 0 && count < financialDocuments.length; }, [selected, financialDocuments]);
  useEffect(() => {
    const controller = new AbortController(); let loaded: DocumentPreview | null = null;
    setOriginal(null); setPreview(null); setOpenError('');
    if (!opened) { setOpening(false); return () => controller.abort(); }
    setOpening(true);
    const heading = previewFocus.current;
    if (heading && heading.getClientRects().length) { const bounds = heading.getBoundingClientRect(); heading.focus({ preventScroll: true }); if (bounds.top < 100 || bounds.bottom > window.innerHeight) heading.scrollIntoView({ block: 'start', inline: 'nearest', behavior: 'auto' }); }
    void client.original(opened.batch_id, opened, controller.signal).then(async (file) => {
      loaded = await previewOriginal(file.blob, file.filename, file.mediaType);
      if (!controller.signal.aborted) { setOriginal(file); setPreview(loaded); } else releasePreview(loaded);
    }).catch((reason) => { if (!controller.signal.aborted) setOpenError(message(reason)); }).finally(() => { if (!controller.signal.aborted) setOpening(false); });
    return () => { controller.abort(); releasePreview(loaded); };
  }, [client, opened]);

  function openDocument(doc: OriginalDocument, source: HTMLElement) { originalOpener.current = source; setOpened(doc); }
  function closeOriginal() {
    setOpened(null); const source = originalOpener.current;
    if (source?.isConnected && source.getClientRects().length) { source.focus({ preventScroll: true }); source.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'auto' }); }
  }
  async function create() {
    if (busy || !name.trim() || !/^\d{4}-(0[1-9]|1[0-2])$/.test(period)) return;
    setCreating(true); setCreateError(''); const signal = operations.current.signal;
    try { const batch = await client.createBatch(name.trim(), period, signal); if (signal.aborted) return; setBatches((current) => [batch, ...current.filter((item) => item.id !== batch.id)]); setBatchId(batch.id); setName(''); setCreateOpen(false); }
    catch (reason) { if (!signal.aborted) setCreateError(message(reason)); }
    finally { if (!signal.aborted) setCreating(false); }
  }
  async function upload(files: File[]) {
    if (!activeBatch || busy || !files.length) return;
    const version = generation.current; const controller = new AbortController(); uploadAbort.current = controller;
    const queue = files.map((file, index) => ({ id: `${index}-${file.lastModified}-${file.name}`, name: file.name, state: 'waiting' as const }));
    setUploads(queue); setUploading(true);
    const update = (id: string, state: UploadItem['state'], detail?: string) => { if (generation.current === version) setUploads((items) => items.map((item) => item.id === id ? { ...item, state, message: detail } : item)); };
    let receivedCount = documents.length;
    for (const [index, file] of files.entries()) {
      if (controller.signal.aborted) { update(queue[index].id, 'cancelled', 'Envio não iniciado.'); continue; }
      if (file.size > MAX_SIZE) { update(queue[index].id, 'error', 'O limite é 30 MB por arquivo.'); continue; }
      if (receivedCount >= 100) { update(queue[index].id, 'error', 'O conjunto comporta até 100 documentos. Crie outro conjunto.'); continue; }
      update(queue[index].id, 'sending');
      try { const received = await client.upload(activeBatch.id, file, uploadRole || null, controller.signal); if (generation.current !== version) return; receivedCount += 1; setDocuments((items) => [...items.filter((item) => item.id !== received.id), received]); update(queue[index].id, 'received', 'Original recebido. Ainda não processado.'); }
      catch (reason) { update(queue[index].id, controller.signal.aborted ? 'cancelled' : 'error', controller.signal.aborted ? 'Envio interrompido. Atualize a lista para conferir se o original foi recebido.' : message(reason)); }
    }
    if (generation.current === version) { setUploading(false); setRefresh((value) => value + 1); }
  }
  async function changeRole(doc: OriginalDocument, role: DocumentRole | null) {
    if (busy) return; setRoleSaving(doc.id); setRowErrors((current) => ({ ...current, [doc.id]: '' })); const version = generation.current;
    try { const changed = await client.setRole(doc.id, role, operations.current.signal); if (generation.current === version) setDocuments((items) => items.map((item) => item.id === changed.id ? changed : item)); }
    catch (reason) { if (generation.current === version) setRowErrors((current) => ({ ...current, [doc.id]: message(reason) })); }
    finally { if (generation.current === version) setRoleSaving(''); }
  }
  async function downloadDocument(doc: OriginalDocument) {
    setDownloading(doc.id); setRowErrors((current) => ({ ...current, [doc.id]: '' })); const signal = operations.current.signal;
    try { const file = original && opened?.id === doc.id ? original : await client.original(doc.batch_id, doc, signal, true); if (!signal.aborted) download(file); }
    catch (reason) { if (!signal.aborted) setRowErrors((current) => ({ ...current, [doc.id]: message(reason) })); }
    finally { if (!signal.aborted) setDownloading(''); }
  }
  async function process() {
    if (!canProcess || !activeBatch) return; const version = generation.current;
    setProcessing(true); setProcessError(''); setProcessMessage('');
    try { await onProcess(activeBatch.id, picked.map((doc) => doc.id), activeBatch.period); if (generation.current === version) setProcessMessage('Seleção encaminhada. Acompanhe o resultado no fechamento.'); }
    catch (reason) { if (generation.current === version) setProcessError(message(reason)); }
    finally { if (generation.current === version) setProcessing(false); }
  }

  return <section className="dw" aria-labelledby={titleId}>
    {navigationLoading ? <p className="dw-preview-caption" role="status">Localizando o conjunto solicitado…</p> : pendingNavigation && operationBusy ? <p className="dw-preview-caption" role="status">A solicitação será aberta quando a operação em curso terminar.</p> : null}
    {navigationError ? <div className="dw-error" role="alert">{navigationError}<button type="button" onClick={() => setNavigationError('')}>Fechar aviso</button></div> : null}
    <header className="dw-header"><div><p className="dw-eyebrow">Originais e competência</p><h2 id={titleId}>Documentos do fechamento</h2><p>Reúna os arquivos, confira os originais e escolha o que entra na apuração.</p></div><button type="button" className="dw-button dw-secondary" aria-expanded={createOpen} aria-controls={createId} onClick={() => setCreateOpen((value) => !value)} disabled={busy}><Plus size={16} />Novo conjunto</button></header>
    {createOpen ? <form id={createId} className="dw-create" onSubmit={(event) => { event.preventDefault(); void create(); }}><label className="dw-field"><span>Nome do conjunto</span><input value={name} onChange={(event) => setName(event.target.value)} required autoFocus maxLength={200} placeholder="Identifique os arquivos deste fechamento" disabled={busy} /></label><label className="dw-field"><span>Competência do conjunto</span><input type="month" value={period} onChange={(event) => setPeriod(event.target.value)} required disabled={busy} /></label><button className="dw-button dw-primary" type="submit" disabled={busy || !name.trim() || !period}>{creating ? <LoaderCircle className="dw-spin" size={16} /> : <Plus size={16} />}Criar conjunto</button>{createError ? <p className="dw-error" role="alert">{createError}</p> : null}</form> : null}
    <div className="dw-batchbar"><BatchSelector batches={batches} value={batchId} onChange={setBatchId} disabled={busy} loading={batchLoading} /><label className="dw-field dw-period"><span>Competência</span><input type="month" value={activeBatch?.period ?? ''} readOnly aria-readonly="true" aria-label="Competência selecionada" /></label><button className="dw-button dw-secondary" type="button" aria-label="Atualizar documentos" disabled={busy || batchLoading} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={16} />Atualizar</button></div>
    {batchError ? <div className="dw-error" role="alert">{batchError}<button type="button" onClick={() => { setBatchError(''); setBatchLoading(true); void client.listBatches(operations.current.signal).then((items) => { setBatches(items); setBatchId(items[0]?.id ?? ''); }).catch((reason) => setBatchError(message(reason))).finally(() => setBatchLoading(false)); }}>Tentar novamente</button></div> : null}
    {!batchLoading && !batches.length && !batchError ? <div className="dw-empty"><FolderOpen size={28} /><h3>Nenhum conjunto recebido</h3><p>Crie um conjunto com a competência e envie os arquivos originais.</p></div> : null}
    {activeBatch ? <>
      <div className="dw-upload"><div><h3>Adicionar originais</h3><p>CSV, planilhas, extratos, e-mails, PDF e documentos de apoio · até 30 MB por arquivo.</p></div><label className="dw-field"><span>Papel dos arquivos enviados</span><select aria-label="Papel para upload" value={uploadRole} onChange={(event) => setUploadRole(event.target.value as DocumentRole | '')} disabled={busy}><option value="">Identificar pelo nome quando reconhecido</option>{DOCUMENT_ROLES.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}</select></label><label className={`dw-button dw-primary dw-upload-label${busy ? ' dw-disabled' : ''}`} htmlFor={uploadInput}><UploadCloud size={17} />{uploading ? 'Enviando…' : 'Escolher arquivos'}<input id={uploadInput} className="dw-file-input" type="file" multiple accept={ACCEPT} disabled={busy} onChange={(event) => { const files = Array.from(event.currentTarget.files ?? []); event.currentTarget.value = ''; void upload(files); }} /></label>{uploading ? <button className="dw-button dw-secondary" type="button" onClick={() => uploadAbort.current?.abort()}>Interromper envio</button> : null}</div>
      {uploads.length ? <ul className="dw-upload-results" aria-label="Resultado dos envios" aria-live="polite">{uploads.map((item) => <li key={item.id} className={`dw-upload-${item.state}`}><span>{item.state === 'sending' ? <LoaderCircle className="dw-spin" size={15} /> : item.state === 'received' ? <Check size={15} /> : null}<strong>{item.name}</strong></span><span>{item.message ?? (item.state === 'sending' ? 'Enviando original…' : 'Aguardando envio')}</span></li>)}</ul> : null}
      <div className={`dw-content${opened ? ' dw-has-preview' : ''}`}>
        <div className="dw-library"><div className="dw-list-header"><label><input type="checkbox" ref={allCheckbox} checked={financialDocuments.length > 0 && financialDocuments.every((doc) => selected.has(doc.id))} disabled={busy || !financialDocuments.length || docsLoading} onChange={(event) => setSelected(event.target.checked ? new Set(financialDocuments.map((doc) => doc.id)) : new Set())} />Selecionar financeiros</label><span>{docsLoading ? 'Consultando originais…' : docsError ? 'Lista indisponível' : `${documents.length} arquivos recebidos`}</span></div>
          {docsError ? <p className="dw-error" role="alert">{docsError} A seleção não será enviada enquanto a lista não puder ser conferida.</p> : null}
          {docsLoading ? <p className="dw-empty" role="status">Carregando os originais deste conjunto…</p> : documents.length ? <ul className="dw-documents">{documents.map((doc) => <li key={doc.id} data-document-id={doc.id} className={selected.has(doc.id) ? 'dw-document-selected' : ''}><div className="dw-document-main"><label className="dw-checkbox"><input type="checkbox" aria-label={`Selecionar ${doc.name}`} checked={selected.has(doc.id)} disabled={busy} onChange={(event) => setSelected((current) => { const next = new Set(current); if (event.target.checked) next.add(doc.id); else next.delete(doc.id); return next; })} /></label><FileText size={21} /><div className="dw-document-name"><button type="button" className="dw-name-button" onClick={(event) => openDocument(doc, event.currentTarget)}>{doc.name}</button><span>{formatBytes(doc.size_bytes)} · {doc.name.includes('.') ? doc.name.split('.').at(-1)?.toUpperCase() : 'Arquivo'}</span>{doc.created_at ? <time dateTime={doc.created_at}>Recebido em {Number.isFinite(Date.parse(doc.created_at)) ? new Date(doc.created_at).toLocaleString('pt-BR') : doc.created_at}</time> : null}</div><div className="dw-document-actions"><button type="button" className="dw-icon-button" aria-label={`Abrir ${doc.name}`} onClick={(event) => openDocument(doc, event.currentTarget)}><ExternalLink size={17} /></button><button type="button" className="dw-icon-button" aria-label={`Baixar ${doc.name}`} disabled={Boolean(downloading)} onClick={() => void downloadDocument(doc)}>{downloading === doc.id ? <LoaderCircle className="dw-spin" size={17} /> : <Download size={17} />}</button></div></div><label className="dw-role"><span>Papel no fechamento</span><select aria-label={`Papel de ${doc.name}`} value={doc.role ?? ''} disabled={busy} onChange={(event) => void changeRole(doc, event.target.value ? event.target.value as DocumentRole : null)}><option value="">Não definido / documento de apoio</option>{DOCUMENT_ROLES.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}</select></label>{rowErrors[doc.id] ? <p className="dw-error" role="alert">{rowErrors[doc.id]}</p> : null}</li>)}</ul> : !docsError ? <div className="dw-empty"><FileText size={28} /><h3>Este conjunto ainda não tem arquivos</h3><p>Envie os arquivos para começar.</p></div> : null}
        </div>
        {opened ? <aside className="dw-original" aria-label="Original do documento"><div className="dw-preview-heading" ref={previewFocus} tabIndex={-1}><div><span>Original recebido</span><h3>{opened.name}</h3></div><button className="dw-icon-button" type="button" aria-label="Fechar original" onClick={closeOriginal}><X size={18} /></button></div>{opening ? <p className="dw-empty" role="status">Abrindo documento…</p> : openError ? <p className="dw-error" role="alert">{openError}</p> : preview?.kind === 'pdf' ? <div className="dw-empty dw-pdf-card"><FileText size={34} /><h3>PDF original disponível</h3><p>Abra em outra aba para usar o leitor de PDF do navegador ou baixe o arquivo original.</p></div> : preview?.kind === 'csv' ? <><p className="dw-preview-caption">Prévia de até 50 linhas · {preview.encoding} · separador {preview.delimiter === ';' ? 'ponto e vírgula' : preview.delimiter === ',' ? 'vírgula' : preview.delimiter || 'não identificado'}. O original permanece inalterado.</p>{preview.warningCount ? <p className="dw-warning">A leitura da prévia encontrou {preview.warningCount} aviso(s). Confira o original antes de processar.</p> : null}<div className="dw-csv-scroll" role="region" tabIndex={0} aria-label={`Prévia CSV de ${opened.name}`}><table><thead><tr>{preview.columns.map((column, index) => <th key={index}>{column || `Coluna ${index + 1}`}</th>)}</tr></thead><tbody>{preview.rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((value, index) => <td key={index}>{value}</td>)}</tr>)}</tbody></table></div>{preview.limited ? <p className="dw-preview-caption">Prévia parcial. Baixe o original para conferir todas as linhas.</p> : null}</> : preview?.kind === 'unsupported' ? <div className="dw-empty"><FileText size={27} /><h3>Prévia não disponível para este formato</h3><p>Baixe o original para abrir no aplicativo correspondente. O recebimento não confirma compatibilidade com o fechamento.</p></div> : null}<div className="dw-original-actions"><button className="dw-button dw-secondary" type="button" disabled={!original || opening} onClick={() => original && download(original)}><Download size={16} />Baixar original</button>{preview?.kind === 'pdf' ? <button className="dw-button dw-secondary" type="button" onClick={() => window.open(preview.url, '_blank', 'noopener,noreferrer')}><ExternalLink size={16} />Abrir PDF em outra aba</button> : null}</div>{opened.sha256 ? <details className="dw-integrity"><summary>Identificação do original</summary><code>{opened.sha256}</code><p>Referência para conferir o original. Não representa validação financeira.</p></details> : null}</aside> : null}
      </div>
      <footer className="dw-processing"><div><h3>{picked.length} arquivo(s) selecionado(s)</h3><p>Competência {activeBatch.period}. Para outro mês, crie um novo conjunto.</p>{problems.length ? <ul aria-label="O que falta para processar">{problems.map((problem) => <li key={problem}>{problem}</li>)}</ul> : <p>A seleção tem os papéis necessários. A compatibilidade dos dados será conferida no processamento.</p>}</div><button type="button" className="dw-button dw-primary" disabled={!canProcess} onClick={() => void process()}>{processing ? <LoaderCircle className="dw-spin" size={17} /> : <FolderOpen size={17} />}{processing ? 'Encaminhando seleção…' : 'Processar seleção'}</button>{processError ? <p className="dw-error" role="alert">{processError}</p> : null}{processMessage ? <p className="dw-success" role="status">{processMessage}</p> : null}</footer>
    </> : null}
  </section>;
}

export default DocumentsWorkspace;
