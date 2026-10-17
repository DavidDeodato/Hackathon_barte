"""Persistent original documents and immutable close-input selections.

Own database/blobs under the supplied server directory; no global settings,
credentials, financial calculations or extraction of arbitrary documents.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

MAX_FILE_BYTES = 30 * 1024 * 1024
MAX_BATCH_DOCUMENTS = 100
MIME_TYPES = {'.csv': 'text/csv', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
              '.xls': 'application/vnd.ms-excel', '.ofx': 'application/x-ofx', '.eml': 'message/rfc822',
              '.pdf': 'application/pdf', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
              '.txt': 'text/plain', '.md': 'text/plain', '.json': 'application/json'}
ROLE_FILES = {'orbe': '01_orbe.csv', 'contracts': '02_contracts.xlsx', 'remessa': '03_remessa.eml',
              'accounts': '04_accounts.csv', 'aurora': '05a_aurora.csv', 'meridiano': '05b_meridiano.ofx',
              'adjustments': '06_adjustments.csv'}
REQUIRED_ROLES = tuple(role for role in ROLE_FILES if role != 'adjustments')
ROLE_LABELS = {'orbe': 'transações de checkout da Orbe', 'contracts': 'tabela de taxas contratadas',
               'remessa': 'relatório de remessas da Ponte', 'accounts': 'plano de contas',
               'aurora': 'extrato Aurora', 'meridiano': 'extrato Meridiano', 'adjustments': 'ajustes adicionais'}
ROLE_PREFIXES = {'01_': 'orbe', '02_': 'contracts', '03_': 'remessa', '04_': 'accounts',
                 '05a_': 'aurora', '05b_': 'meridiano', '06_': 'adjustments'}
EXTRA_MIME_TYPES = {'application/octet-stream', 'text/plain', 'application/csv',
                    'text/ofx', 'application/ofx', 'application/x-ofx', 'application/vnd.ms-excel'}


class DocumentError(Exception):
    def __init__(self, code, message, status=422):
        self.code, self.message, self.status = code, message, status
        super().__init__(code)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def valid_period(period):
    if not isinstance(period, str) or not re.fullmatch(r'20\d{2}-(?:0[1-9]|1[0-2])', period):
        raise DocumentError('INVALID_PERIOD', 'Informe a competência no formato AAAA-MM, com mês válido.')
    return period


def valid_name(name):
    if (not isinstance(name, str) or not name or len(name) > 180 or name != name.strip()
            or name.endswith('.') or name in ('.', '..') or re.search(r'[\x00-\x1f\x7f<>:"/\\|?*]', name)
            or re.fullmatch(r'(?i)(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', name)):
        raise DocumentError('INVALID_DOCUMENT_NAME', 'Use apenas o nome do arquivo, sem caminho ou caracteres reservados.')
    if Path(name).suffix.lower() not in MIME_TYPES:
        raise DocumentError('UNSUPPORTED_DOCUMENT_TYPE', 'Formato não suportado. Envie CSV, planilha, OFX, e-mail, PDF ou documento de texto.', 415)
    return name


def infer_role(name):
    lowered = name.lower()
    for prefix, role in ROLE_PREFIXES.items():
        if lowered.startswith(prefix) and Path(name).suffix.lower() == Path(ROLE_FILES[role]).suffix:
            return role
    return None


def valid_role(role, name):
    if role is None or role == '':
        return None
    if not isinstance(role, str) or role not in ROLE_FILES:
        raise DocumentError('INVALID_DOCUMENT_ROLE', 'Escolha um tipo de fonte financeira conhecido ou mantenha o documento sem tipo.')
    if Path(name).suffix.lower() != Path(ROLE_FILES[role]).suffix:
        raise DocumentError('DOCUMENT_ROLE_TYPE_MISMATCH', 'O formato deste arquivo não corresponde ao tipo de fonte financeira escolhido.')
    return role


class DocumentStore:
    def __init__(self, root_dir):
        self.root = Path(root_dir).resolve()
        self.blobs = self.root / 'blobs'
        self.staging = self.root / 'staging'
        self.selections = self.root / 'selections'
        for folder in (self.root, self.blobs, self.staging, self.selections):
            folder.mkdir(parents=True, exist_ok=True)
        self.database = self.root / 'documents.sqlite3'
        with self._db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS batches (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, period TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(id), name TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL, media_type TEXT NOT NULL, role TEXT,
                    uploaded_at TEXT NOT NULL, sha256 TEXT NOT NULL, blob TEXT NOT NULL, seed_key TEXT UNIQUE);
                CREATE INDEX IF NOT EXISTS documents_batch ON documents(batch_id,uploaded_at,id);
                CREATE TABLE IF NOT EXISTS seeds (
                    source_key TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(id));
            ''')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA journal_mode=WAL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def _batch(self, db, batch_id):
        row = db.execute('SELECT b.*,COUNT(d.id) documents_count FROM batches b LEFT JOIN documents d ON d.batch_id=b.id WHERE b.id=? GROUP BY b.id', (batch_id,)).fetchone()
        if row is None:
            raise DocumentError('BATCH_NOT_FOUND', 'Conjunto de documentos não encontrado.', 404)
        result = dict(row)
        result['status'] = 'documents_added' if result['documents_count'] else 'draft'
        return result

    @staticmethod
    def _document(row):
        return {key: row[key] for key in ('id', 'batch_id', 'name', 'size_bytes', 'media_type', 'role', 'uploaded_at', 'sha256')}

    def create_batch(self, name, period):
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120 or re.search(r'[\x00-\x1f\x7f]', name):
            raise DocumentError('INVALID_BATCH_NAME', 'Informe um nome para o conjunto, com até 120 caracteres.')
        valid_period(period)
        identifier = 'batch-' + uuid4().hex
        with self._db() as db:
            db.execute('INSERT INTO batches VALUES (?,?,?,?)', (identifier, name.strip(), period, utcnow()))
            return self._batch(db, identifier)

    def get_batch(self, batch_id):
        with self._db() as db:
            return self._batch(db, batch_id)

    def list_batches(self, limit=100, cursor=None):
        offset = self._pagination(limit, cursor)
        with self._db() as db:
            rows = db.execute('SELECT id FROM batches ORDER BY created_at DESC,id LIMIT ? OFFSET ?', (limit + 1, offset)).fetchall()
            return {'items': [self._batch(db, row['id']) for row in rows[:limit]],
                    'next_cursor': str(offset + limit) if len(rows) > limit else None}

    @staticmethod
    def _pagination(limit, cursor):
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200 or cursor is not None and not re.fullmatch(r'\d{1,8}', str(cursor)):
            raise DocumentError('INVALID_DOCUMENT_CURSOR', 'Página de documentos inválida.')
        return int(cursor or 0)

    def list_documents(self, batch_id, limit=100, cursor=None):
        offset = self._pagination(limit, cursor)
        with self._db() as db:
            self._batch(db, batch_id)
            rows = db.execute('SELECT * FROM documents WHERE batch_id=? ORDER BY uploaded_at,id LIMIT ? OFFSET ?', (batch_id, limit + 1, offset)).fetchall()
            return {'items': [self._document(row) for row in rows[:limit]],
                    'next_cursor': str(offset + limit) if len(rows) > limit else None}

    def add_document(self, batch_id, name, data, role=None, media_type=None, *, seed_key=None):
        name = valid_name(name)
        if not isinstance(data, bytes) or not data:
            raise DocumentError('EMPTY_DOCUMENT', 'O documento está vazio; envie o arquivo original com conteúdo.')
        if len(data) > MAX_FILE_BYTES:
            raise DocumentError('DOCUMENT_TOO_LARGE', 'O arquivo excede o limite de 30 MiB.', 413)
        canonical_mime = MIME_TYPES[Path(name).suffix.lower()]
        declared = media_type.split(';', 1)[0].strip().lower() if isinstance(media_type, str) else ''
        if declared and declared not in {canonical_mime, *EXTRA_MIME_TYPES}:
            raise DocumentError('UNSUPPORTED_DOCUMENT_MIME', 'O tipo informado não é compatível com o documento enviado.', 415)
        chosen_role = valid_role(role, name) if role is not None else infer_role(name)
        identifier = 'doc-' + uuid4().hex
        blob = identifier + '.bin'
        target = self.blobs / blob
        digest = hashlib.sha256(data).hexdigest()
        committed = False
        try:
            with self._db() as db:
                db.execute('BEGIN IMMEDIATE')
                batch = self._batch(db, batch_id)
                if seed_key:
                    existing = db.execute('SELECT * FROM documents WHERE seed_key=?', (seed_key,)).fetchone()
                    if existing:
                        return self._document(existing)
                if batch['documents_count'] >= MAX_BATCH_DOCUMENTS:
                    raise DocumentError('BATCH_DOCUMENT_LIMIT', 'Este conjunto já atingiu o limite de 100 documentos.', 409)
                with tempfile.NamedTemporaryFile(dir=self.staging, delete=False) as staged:
                    temporary = Path(staged.name)
                    staged.write(data)
                    staged.flush()
                    os.fsync(staged.fileno())
                os.replace(temporary, target)
                db.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)',
                           (identifier, batch_id, name, len(data), canonical_mime, chosen_role, utcnow(), digest, blob, seed_key))
                row = db.execute('SELECT * FROM documents WHERE id=?', (identifier,)).fetchone()
            committed = True
            return self._document(row)
        finally:
            if not committed:
                target.unlink(missing_ok=True)
            if 'temporary' in locals():
                temporary.unlink(missing_ok=True)

    def get_document(self, document_id):
        with self._db() as db:
            row = db.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
            if row is None:
                raise DocumentError('DOCUMENT_NOT_FOUND', 'Documento não encontrado.', 404)
            return self._document(row)

    def original_path(self, document_id):
        with self._db() as db:
            row = db.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
            if row is None:
                raise DocumentError('DOCUMENT_NOT_FOUND', 'Documento não encontrado.', 404)
            path = (self.blobs / row['blob']).resolve()
            if not path.is_relative_to(self.blobs) or not path.is_file():
                raise DocumentError('DOCUMENT_BYTES_UNAVAILABLE', 'Os bytes originais não estão disponíveis; revise o armazenamento.', 409)
            if path.stat().st_size != row['size_bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
                raise DocumentError('DOCUMENT_INTEGRITY_ERROR', 'O documento armazenado não corresponde à versão registrada.', 409)
            return path

    def update_role(self, document_id, role):
        document = self.get_document(document_id)
        role = valid_role(role, document['name'])
        with self._db() as db:
            db.execute('UPDATE documents SET role=? WHERE id=?', (role, document_id))
        return self.get_document(document_id)

    def seed_directory(self, input_dir, period='2026-09', name='Arquivos originais · setembro/2026'):
        valid_period(period)
        source = Path(input_dir).resolve()
        if not source.is_dir():
            raise DocumentError('ORIGINAL_DIRECTORY_UNAVAILABLE', 'O conjunto original não está disponível neste servidor.', 409)
        source_key = hashlib.sha256((str(source) + '|' + period).encode()).hexdigest()
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT batch_id FROM seeds WHERE source_key=?', (source_key,)).fetchone()
            if prior:
                batch_id = prior['batch_id']
            else:
                batch_id = 'batch-' + uuid4().hex
                db.execute('INSERT INTO batches VALUES (?,?,?,?)', (batch_id, name, period, utcnow()))
                db.execute('INSERT INTO seeds VALUES (?,?)', (source_key, batch_id))
        for file in sorted(source.iterdir()):
            if not file.is_file() or not file.resolve().is_relative_to(source) or file.suffix.lower() not in MIME_TYPES:
                continue
            if file.stat().st_size > MAX_FILE_BYTES:
                raise DocumentError('DOCUMENT_TOO_LARGE', 'Uma fonte original excede o limite de armazenamento.', 413)
            data = file.read_bytes()
            key = hashlib.sha256((source_key + '|' + file.name + '|' + hashlib.sha256(data).hexdigest()).encode()).hexdigest()
            self.add_document(batch_id, file.name, data, seed_key=key)
        return self.get_batch(batch_id)

    def resolve_inputs(self, batch_id, document_ids=None):
        batch = self.get_batch(batch_id)
        available = self.list_documents(batch_id, 200)['items']
        if document_ids is None:
            documents = [doc for doc in available if doc['role'] is not None]
        else:
            if not isinstance(document_ids, list) or not document_ids or len(document_ids) > MAX_BATCH_DOCUMENTS or not all(isinstance(value, str) for value in document_ids) or len(set(document_ids)) != len(document_ids):
                raise DocumentError('INVALID_DOCUMENT_SELECTION', 'Selecione uma lista de documentos sem repetições.')
            by_id = {doc['id']: doc for doc in available}
            if any(identifier not in by_id for identifier in document_ids):
                raise DocumentError('DOCUMENT_OUTSIDE_BATCH', 'A seleção contém documento que não pertence a este conjunto.', 409)
            documents = [by_id[identifier] for identifier in document_ids]
        roles = {}
        for doc in documents:
            role = doc['role']
            if role is None:
                raise DocumentError('DOCUMENT_NOT_PROCESSABLE', f'O documento {doc["name"]} não tem tipo de fonte financeira definido. Guarde-o como apoio ou escolha o tipo correto.', 409)
            if role in roles:
                raise DocumentError('DUPLICATE_DOCUMENT_ROLE', f'Há mais de uma versão de {ROLE_LABELS[role]}; selecione apenas a versão que deseja processar.', 409)
            valid_role(role, doc['name'])
            roles[role] = doc
        missing = [role for role in REQUIRED_ROLES if role not in roles]
        if missing:
            raise DocumentError('MISSING_FINANCIAL_SOURCES', 'Faltam fontes para este fechamento: ' + ', '.join(ROLE_LABELS[role] for role in missing) + '.', 409)
        # Preserve original source names in trace/IDs. Alias only collisions,
        # including a collision introduced by another role's fallback alias.
        input_names = {role: doc['name'] for role, doc in roles.items()}
        while True:
            counts = Counter(name.casefold() for name in input_names.values())
            collisions = [role for role, name in input_names.items() if counts[name.casefold()] > 1]
            if not collisions:
                break
            for role in collisions:
                input_names[role] = ROLE_FILES[role]
        descriptor = {'batch_id': batch_id, 'period': batch['period'],
                      'input_files': {role: input_names[role] for role in sorted(roles)},
                      'documents': [{key: doc[key] for key in ('id', 'name', 'sha256', 'role')} for doc in sorted(documents, key=lambda item: item['role'])]}
        selection_id = 'selection-' + hashlib.sha256(json.dumps(descriptor, sort_keys=True).encode()).hexdigest()[:32]
        target = self.selections / selection_id
        result = {'selection_id': selection_id, 'input_dir': str(target), 'period': batch['period'],
                  'input_files': dict(input_names),
                  'source_documents': [dict(doc, input_name=input_names[doc['role']]) for doc in documents]}
        if target.exists():
            for role, doc in roles.items():
                file = target / input_names[role]
                if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != doc['sha256']:
                    raise DocumentError('SELECTION_INTEGRITY_ERROR', 'A cópia de processamento foi alterada; não será reutilizada.', 409)
            return result
        with tempfile.TemporaryDirectory(dir=self.staging) as folder:
            staged = Path(folder).resolve()
            if not staged.is_relative_to(self.staging):
                raise DocumentError('UNSAFE_SELECTION_PATH', 'Não foi possível preparar a seleção.', 409)
            for role, doc in roles.items():
                shutil.copyfile(self.original_path(doc['id']), staged / input_names[role])
                if hashlib.sha256((staged / input_names[role]).read_bytes()).hexdigest() != doc['sha256']:
                    raise DocumentError('DOCUMENT_INTEGRITY_ERROR', 'A fonte mudou durante a preparação do fechamento.', 409)
            # Administrative descriptor stays outside the financial input set.
            descriptor_temp = self.staging / ('descriptor-' + uuid4().hex + '.json')
            try:
                descriptor_temp.write_text(json.dumps(descriptor, ensure_ascii=False, indent=2), encoding='utf-8')
                os.replace(descriptor_temp, self.selections / (selection_id + '.json'))
            finally:
                descriptor_temp.unlink(missing_ok=True)
            try:
                os.replace(staged, target)
            except OSError:
                if not target.exists():
                    raise
                for role, doc in roles.items():
                    if hashlib.sha256((target / input_names[role]).read_bytes()).hexdigest() != doc['sha256']:
                        raise DocumentError('SELECTION_INTEGRITY_ERROR', 'Seleção simultânea incompatível; tente novamente.', 409) from None
        return result
