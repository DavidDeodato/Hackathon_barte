"""Protected-by-integration document router; no app/config mutation.

API owner must include this router with the application's session/bearer auth
dependencies. Multipart parsing uses stdlib and is bounded before parsing.
"""
from __future__ import annotations

from email import policy
from email.parser import BytesParser
from pathlib import Path
import re

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .document_store import DocumentError, DocumentStore, MAX_FILE_BYTES


class BatchInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=120)
    period: str = Field(pattern=r'^20\d{2}-(0[1-9]|1[0-2])$')


class RoleInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: str | None = None


def _error(exc):
    return JSONResponse({'error': {'code': exc.code, 'message': exc.message}}, status_code=exc.status)


def _call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except DocumentError as exc:
        return _error(exc)


def _multipart(body, content_type):
    if '\r' in content_type or '\n' in content_type:
        raise DocumentError('INVALID_MULTIPART', 'Envio de documento inválido.')
    message = BytesParser(policy=policy.default).parsebytes(('Content-Type: ' + content_type + '\r\n\r\n').encode('ascii'), headersonly=True)
    boundary = message.get_boundary()
    if message.get_content_type() != 'multipart/form-data' or message.defects or not boundary or not re.fullmatch(r"[0-9A-Za-z'()+_,./:=? -]{1,70}", boundary) or boundary.endswith(' '):
        raise DocumentError('INVALID_MULTIPART', 'O envio não contém um arquivo válido.')
    # Parse only form framing. An EML/message/rfc822 can itself be multipart;
    # treating its payload as an email tree rejects it or changes source bytes.
    delimiters = list(re.finditer(rb'(?:\A|\r\n)--' + re.escape(boundary.encode('ascii')) + rb'(--)?(?:\r\n|\Z)', body))
    if (len(delimiters) < 2 or len(delimiters) > 5 or delimiters[0].start() != 0 or
            delimiters[-1].end() != len(body) or not delimiters[-1].group(1) or
            any(item.group(1) for item in delimiters[:-1])):
        raise DocumentError('INVALID_MULTIPART', 'Envie apenas um arquivo por requisição.')
    files, role, role_seen = [], None, False
    for start, end in zip(delimiters, delimiters[1:]):
        headers, separator, raw = body[start.end():end.start()].partition(b'\r\n\r\n')
        if not separator or len(headers) > 16384:
            raise DocumentError('INVALID_MULTIPART', 'O envio não contém um arquivo válido.')
        part = BytesParser(policy=policy.default).parsebytes(headers + b'\r\n\r\n', headersonly=True)
        if (part.defects or part.get_content_disposition() != 'form-data' or
                len(part.get_all('Content-Disposition', [])) != 1 or len(part.get_all('Content-Type', [])) > 1 or
                part.get('Content-Transfer-Encoding') not in (None, 'binary', '8bit')):
            raise DocumentError('INVALID_MULTIPART', 'Envie apenas um arquivo por requisição.')
        key = part.get_param('name', header='content-disposition')
        if key == 'file' and part.get_filename():
            files.append((part.get_filename(), raw, part.get_content_type()))
        elif key == 'role' and not part.get_filename():
            if role_seen:
                raise DocumentError('AMBIGUOUS_UPLOAD', 'Informe apenas um tipo de fonte por arquivo.')
            role_seen = True
            if len(raw or b'') > 80:
                raise DocumentError('INVALID_DOCUMENT_ROLE', 'Tipo de fonte financeira inválido.')
            role = (raw or b'').decode('utf-8').strip() or None
        else:
            raise DocumentError('INVALID_MULTIPART_FIELD', 'Envie somente o arquivo e seu tipo de fonte opcional.')
    if len(files) != 1:
        raise DocumentError('INVALID_MULTIPART', 'Envie exatamente um arquivo no campo file.')
    return (*files[0], role)


def create_document_router(store: DocumentStore | None = None, *, root_dir: str | Path | None = None):
    if store is None:
        if root_dir is None:
            raise ValueError('Document router requires a server-owned root directory')
        store = DocumentStore(root_dir)
    router = APIRouter(prefix='/api', tags=['documents'])
    router.document_store = store  # Trusted integration only; no paths in HTTP JSON.

    @router.get('/batches')
    def list_batches(limit: int = Query(100, ge=1, le=200), cursor: str | None = None):
        return _call(store.list_batches, limit, cursor)

    @router.post('/batches', status_code=201)
    def create_batch(body: BatchInput):
        return _call(store.create_batch, body.name, body.period)

    @router.get('/batches/{batch_id}')
    def get_batch(batch_id: str):
        return _call(store.get_batch, batch_id)

    @router.get('/batches/{batch_id}/documents')
    def list_documents(batch_id: str, limit: int = Query(100, ge=1, le=200), cursor: str | None = None):
        return _call(store.list_documents, batch_id, limit, cursor)

    @router.post('/batches/{batch_id}/documents', status_code=201)
    async def upload(batch_id: str, request: Request, name: str | None = None, role: str | None = None):
        try:
            store.get_batch(batch_id)
            content_type = request.headers.get('content-type', 'application/octet-stream')
            is_multipart = content_type.lower().startswith('multipart/form-data')
            limit = MAX_FILE_BYTES + (64 * 1024 if is_multipart else 0)
            length = request.headers.get('content-length')
            if length and (not length.isdigit() or int(length) > limit):
                raise DocumentError('DOCUMENT_TOO_LARGE', 'O arquivo excede o limite de 30 MiB.', 413)
            chunks, total = [], 0
            async for chunk in request.stream():
                total += len(chunk)
                if total > limit:
                    raise DocumentError('DOCUMENT_TOO_LARGE', 'O arquivo excede o limite de 30 MiB.', 413)
                chunks.append(chunk)
            data = b''.join(chunks)
            if is_multipart:
                filename, data, media, multipart_role = _multipart(data, content_type)
                if name is not None or role is not None and multipart_role is not None and role != multipart_role:
                    raise DocumentError('AMBIGUOUS_UPLOAD', 'Informe nome e tipo em um único lugar no envio.')
                role = role if role is not None else multipart_role
            else:
                filename, media = name, content_type
            return store.add_document(batch_id, filename, data, role, media)
        except (UnicodeDecodeError, UnicodeEncodeError):
            return _error(DocumentError('INVALID_MULTIPART', 'Não foi possível ler os campos do envio.'))
        except DocumentError as exc:
            return _error(exc)

    @router.patch('/documents/{document_id}')
    def role_update(document_id: str, body: RoleInput):
        return _call(store.update_role, document_id, body.role)

    @router.get('/documents/{document_id}/original')
    def original(document_id: str, download: bool = False):
        try:
            document = store.get_document(document_id)
            path = store.original_path(document_id)
            inline = not download and document['media_type'] in ('application/pdf', 'text/plain', 'text/csv')
            return FileResponse(path, media_type=document['media_type'], filename=document['name'],
                                content_disposition_type='inline' if inline else 'attachment',
                                headers={'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': "default-src 'none'; sandbox",
                                         'Cache-Control': 'private, no-store', 'X-Document-SHA256': document['sha256']})
        except DocumentError as exc:
            return _error(exc)

    return router
