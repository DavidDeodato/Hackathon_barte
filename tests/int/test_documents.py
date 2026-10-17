"""Original bytes/persistence/batch boundaries. No cloud, credentials or LLM."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from tarvo.api.document_store import DocumentError, DocumentStore, ROLE_FILES, MAX_FILE_BYTES
from tarvo.api.documents import create_document_router


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.store = DocumentStore(self.folder / 'documents')
        self.batch = self.store.create_batch('Documentos de teste', '2026-09')
        self.batch_id = self.batch['id']
        app = FastAPI()
        def auth(request: Request):
            if request.headers.get('authorization') != 'Bearer test-only':
                raise HTTPException(401)
        app.include_router(create_document_router(self.store), dependencies=[Depends(auth)])
        self.client = TestClient(app)
        self.headers = {'Authorization': 'Bearer test-only'}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def endpoint(self):
        return f'/api/batches/{self.batch_id}/documents'

    def populate_roles(self, batch_id=None):
        return [self.store.add_document(batch_id or self.batch_id, name, ('fixture:' + role).encode(), role)
                for role, name in ROLE_FILES.items() if role != 'adjustments']

    def test_raw_upload_list_original_and_reopen_store_preserve_exact_bytes(self):
        raw = 'data;valor\n17/09/2026;12,35\n'.encode('utf-8')
        response = self.client.post(self.endpoint(), params={'name': 'operações.csv', 'role': 'orbe'},
                                    content=raw, headers={**self.headers, 'Content-Type': 'text/csv'})
        self.assertEqual(response.status_code, 201, response.text)
        document = response.json()
        self.assertEqual(document['name'], 'operações.csv')
        self.assertEqual(document['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(document['size_bytes'], len(raw))
        listed = self.client.get(self.endpoint(), headers=self.headers).json()['items']
        self.assertEqual(listed, [document])
        original = self.client.get('/api/documents/' + document['id'] + '/original', headers=self.headers)
        self.assertEqual(original.content, raw)
        self.assertEqual(original.headers['x-document-sha256'], document['sha256'])
        self.assertEqual(original.headers['x-content-type-options'], 'nosniff')
        reopened = DocumentStore(self.folder / 'documents')
        self.assertEqual(reopened.get_document(document['id']), document)
        self.assertEqual(reopened.original_path(document['id']).read_bytes(), raw)
        downloaded = self.client.get('/api/documents/' + document['id'] + '/original?download=true', headers=self.headers)
        self.assertIn('attachment;', downloaded.headers['content-disposition'])
        self.assertEqual(downloaded.content, raw)

    def test_multipart_works_without_python_multipart_dependency(self):
        response = self.client.post(self.endpoint(), files={'file': ('contrato.pdf', b'%PDF-1.7\nfixture', 'application/pdf')}, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        document = response.json()
        self.assertIsNone(document['role'])
        original = self.client.get(f'/api/documents/{document["id"]}/original', headers=self.headers)
        self.assertEqual(original.content, b'%PDF-1.7\nfixture')
        self.assertIn('sandbox', original.headers['content-security-policy'])

    def test_real_eml_message_rfc822_multipart_preserves_exact_original_bytes(self):
        path = ROOT / 'contexto/data_pack/03_email_ponte_cambio_relatorio_set2026.eml'
        raw = path.read_bytes()
        response = self.client.post(self.endpoint(), files={'file': (path.name, raw, 'message/rfc822')},
                                    data={'role': 'remessa'}, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        doc = response.json()
        self.assertEqual(doc['size_bytes'], len(raw))
        self.assertEqual(doc['sha256'], hashlib.sha256(raw).hexdigest())
        original = self.client.get(f'/api/documents/{doc["id"]}/original?download=true', headers=self.headers)
        self.assertEqual(original.content, raw)
        self.assertEqual(DocumentStore(self.folder / 'documents').original_path(doc['id']).read_bytes(), raw)

    def test_multipart_binary_and_boundary_like_payload_keeps_framing_distinct(self):
        for suffix in (b'', b'\r\n', b'\r\n\r\n'):
            raw = b'\x00\xff\n\r\n--test-boundary-not-a-delimiter\r\nHeader: keep\r\n\r\nbody' + suffix
            body = (b'--test-boundary\r\nContent-Disposition: form-data; name="file"; filename="bytes.eml"\r\n'
                    b'Content-Type: message/rfc822\r\n\r\n' + raw + b'\r\n--test-boundary--\r\n')
            response = self.client.post(self.endpoint(), content=body,
                                        headers={**self.headers, 'Content-Type': 'multipart/form-data; boundary=test-boundary'})
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(self.store.original_path(response.json()['id']).read_bytes(), raw)

    def test_multipart_rejects_missing_close_duplicate_file_and_duplicate_role(self):
        file = b'--b\r\nContent-Disposition: form-data; name="file"; filename="a.csv"\r\nContent-Type: text/csv\r\n\r\nx\r\n'
        role = b'--b\r\nContent-Disposition: form-data; name="role"\r\n\r\norbe\r\n'
        for body in (file, file + file + b'--b--\r\n', role + role + file + b'--b--\r\n'):
            response = self.client.post(self.endpoint(), content=body,
                                        headers={**self.headers, 'Content-Type': 'multipart/form-data; boundary=b'})
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.store.list_documents(self.batch_id)['items'], [])

    def test_auth_dependency_covers_list_upload_and_original(self):
        document = self.store.add_document(self.batch_id, 'a.csv', b'a;b\n1;2')
        for path in ('/api/batches', self.endpoint(), f'/api/documents/{document["id"]}/original'):
            self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.post(self.endpoint(), params={'name': 'x.csv'}, content=b'x').status_code, 401)

    def test_batch_create_period_and_pagination(self):
        response = self.client.post('/api/batches', json={'name': 'Outubro', 'period': '2026-10'}, headers=self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['period'], '2026-10')
        self.assertEqual(response.json()['status'], 'draft')
        first = self.client.get('/api/batches?limit=1', headers=self.headers).json()
        self.assertIsNotNone(first['next_cursor'])
        next_page = self.client.get('/api/batches', params={'limit': 1, 'cursor': first['next_cursor']}, headers=self.headers).json()
        self.assertNotEqual(first['items'][0]['id'], next_page['items'][0]['id'])
        for period in ('2026-13', '2026-00', '2026/09', '../2026'):
            self.assertEqual(self.client.post('/api/batches', json={'name': 'Bad', 'period': period}, headers=self.headers).status_code, 422)

    def test_unknown_batch_and_document_return_404(self):
        self.assertEqual(self.client.get('/api/batches/missing', headers=self.headers).status_code, 404)
        self.assertEqual(self.client.get('/api/documents/missing/original', headers=self.headers).status_code, 404)
        self.assertEqual(self.client.post('/api/batches/missing/documents?name=a.csv', content=b'a', headers=self.headers).status_code, 404)

    def test_unsafe_names_mime_empty_and_large_declared_body_rejected(self):
        for name in ('../a.csv', 'C:\\secret.csv', '.env', 'CON.csv', 'x.csv\r\nInjected:yes', 'a.exe', ' x.csv', 'x.csv.'):
            response = self.client.post(self.endpoint(), params={'name': name}, content=b'body', headers=self.headers)
            self.assertIn(response.status_code, (415, 422), (name, response.text))
        response = self.client.post(self.endpoint(), params={'name': 'a.csv'}, content=b'a', headers={**self.headers, 'Content-Type': 'text/html'})
        self.assertEqual(response.status_code, 415)
        response = self.client.post(self.endpoint(), params={'name': 'a.csv'}, content=b'', headers=self.headers)
        self.assertEqual(response.status_code, 422)
        response = self.client.post(self.endpoint(), params={'name': 'a.csv'}, content=b'x', headers={**self.headers, 'Content-Length': str(MAX_FILE_BYTES + 1)})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.store.list_documents(self.batch_id)['items'], [])

    def test_versions_keep_distinct_bytes_and_names(self):
        a = self.store.add_document(self.batch_id, 'a.csv', b'first')
        b = self.store.add_document(self.batch_id, 'a.csv', b'second')
        self.assertNotEqual(a['id'], b['id'])
        self.assertEqual(self.store.original_path(a['id']).read_bytes(), b'first')
        self.assertEqual(self.store.original_path(b['id']).read_bytes(), b'second')

    def test_role_assignment_changes_metadata_not_bytes(self):
        document = self.store.add_document(self.batch_id, 'custom.csv', b'data')
        response = self.client.patch('/api/documents/' + document['id'], json={'role': 'orbe'}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['role'], 'orbe')
        self.assertEqual(response.json()['sha256'], document['sha256'])
        self.assertEqual(self.store.original_path(document['id']).read_bytes(), b'data')
        with self.assertRaises(DocumentError):
            self.store.add_document(self.batch_id, 'fake.pdf', b'pdf', 'contracts')

    def test_selection_is_immutable_verified_and_reusable_after_role_update(self):
        documents = self.populate_roles()
        selection = self.store.resolve_inputs(self.batch_id)
        self.assertEqual(selection['period'], '2026-09')
        self.assertEqual(set(selection['input_files']), set(ROLE_FILES) - {'adjustments'})
        for document in documents:
            raw = (Path(selection['input_dir']) / selection['input_files'][document['role']]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), document['sha256'])
        self.assertEqual(self.store.resolve_inputs(self.batch_id)['selection_id'], selection['selection_id'])
        self.store.update_role(documents[0]['id'], None)
        self.assertTrue((Path(selection['input_dir']) / selection['input_files']['orbe']).exists())
        with self.assertRaises(DocumentError):
            self.store.resolve_inputs(self.batch_id)

    def test_cross_batch_duplicate_roles_missing_sources_and_support_document_fail(self):
        documents = self.populate_roles()
        other = self.store.create_batch('Outro', '2026-09')
        external = self.store.add_document(other['id'], 'other.csv', b'data', 'orbe')
        for ids in ([], [external['id']], [documents[0]['id'], documents[0]['id']], [documents[0]['id']]):
            with self.assertRaises(DocumentError):
                self.store.resolve_inputs(self.batch_id, ids)
        duplicate = self.store.add_document(self.batch_id, 'another.csv', b'next', 'orbe')
        with self.assertRaises(DocumentError) as duplicate_error:
            self.store.resolve_inputs(self.batch_id)
        self.assertEqual(duplicate_error.exception.code, 'DUPLICATE_DOCUMENT_ROLE')
        good = [doc['id'] for doc in documents]
        self.assertEqual(len(self.store.resolve_inputs(self.batch_id, good)['source_documents']), 6)
        support = self.store.add_document(self.batch_id, 'memo.pdf', b'%PDF-x')
        with self.assertRaises(DocumentError):
            self.store.resolve_inputs(self.batch_id, good + [support['id']])
        self.assertNotIn(duplicate['id'], good)

    def test_blob_and_selection_tampering_detected(self):
        documents = self.populate_roles()
        original = self.store.original_path(documents[0]['id'])
        before = original.read_bytes()
        original.write_bytes(b'tampered')
        with self.assertRaises(DocumentError):
            self.store.original_path(documents[0]['id'])
        original.write_bytes(before)
        selection = self.store.resolve_inputs(self.batch_id)
        (Path(selection['input_dir']) / selection['input_files']['orbe']).write_bytes(b'tampered')
        with self.assertRaises(DocumentError) as error:
            self.store.resolve_inputs(self.batch_id)
        self.assertEqual(error.exception.code, 'SELECTION_INTEGRITY_ERROR')

    def test_seed_registers_only_real_files_and_is_idempotent(self):
        source = self.folder / 'originals'
        source.mkdir()
        (source / '00_LEIA-ME.md').write_text('Real support document', encoding='utf-8')
        for name in list(ROLE_FILES.values())[:6]:
            (source / name).write_bytes(b'real fixture bytes')
        first = self.store.seed_directory(source)
        second = DocumentStore(self.folder / 'documents').seed_directory(source)
        self.assertEqual(first['id'], second['id'])
        documents = self.store.list_documents(first['id'])['items']
        self.assertEqual(len(documents), 7)
        self.assertFalse(any(doc['role'] == 'adjustments' for doc in documents))
        for doc in documents:
            self.assertEqual(self.store.original_path(doc['id']).read_bytes(), (source / doc['name']).read_bytes())

    def test_no_internal_paths_in_public_metadata(self):
        doc = self.store.add_document(self.batch_id, 'normal.csv', b'data')
        public = json.dumps({'batch': self.store.get_batch(self.batch_id), 'doc': doc})
        self.assertNotIn(str(self.folder), public)
        self.assertNotIn('blob', public)

    def test_real_original_selection_processes_via_dom_without_modifying_sources(self):
        from tarvo.finance import run_close
        source = ROOT / 'contexto/data_pack'
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file()}
        batch = self.store.seed_directory(source)
        selection = self.store.resolve_inputs(batch['id'])
        result = run_close(selection['input_dir'], str(self.folder / 'close-output'), selection['period'],
                           input_files=selection['input_files'])
        self.assertEqual(result['status'], 'pending_review')
        self.assertEqual(len(result['outputs']), 6)
        manifest = json.loads((self.folder / 'close-output' / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['additional_files'], [])
        self.assertFalse((Path(selection['input_dir']) / 'selection.json').exists())
        self.assertTrue(all(Path(path).is_file() for path in result['outputs']))
        self.assertEqual(hashes, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file()})
        self.assertEqual(any(doc['role'] == 'adjustments' for doc in selection['source_documents']),
                         any(name.startswith('06_') and name.endswith('.csv') for name in hashes))
        direct = run_close(str(source), str(self.folder / 'direct-output'), selection['period'])
        self.assertEqual({Path(path).name: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in result['outputs']},
                         {Path(path).name: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in direct['outputs']})
        for doc in selection['source_documents']:
            self.assertEqual(doc['name'], doc['input_name'])

    def test_colliding_original_names_and_fallback_alias_collision_keep_every_document(self):
        names = {'orbe': 'same.csv', 'accounts': 'same.csv', 'aurora': '01_orbe.csv',
                 'contracts': 'contract.xlsx', 'remessa': 'email.eml', 'meridiano': 'bank.ofx'}
        docs = [self.store.add_document(self.batch_id, name, role.encode(), role) for role, name in names.items()]
        selection = self.store.resolve_inputs(self.batch_id)
        self.assertEqual(len(set(name.casefold() for name in selection['input_files'].values())), 6)
        for doc in docs:
            path = Path(selection['input_dir']) / selection['input_files'][doc['role']]
            self.assertEqual(path.read_bytes(), doc['role'].encode())
        self.assertEqual(selection['input_files']['contracts'], 'contract.xlsx')

    def test_selection_period_is_not_silently_replaced_by_file_period(self):
        from tarvo.finance import run_close
        batch = self.store.seed_directory(ROOT / 'contexto/data_pack', period='2026-10', name='Competência de teste incompatível')
        selection = self.store.resolve_inputs(batch['id'])
        self.assertEqual(selection['period'], '2026-10')
        with self.assertRaises(ValueError):
            run_close(selection['input_dir'], str(self.folder / 'bad-period-output'), selection['period'],
                      input_files=selection['input_files'])


if __name__ == '__main__':
    unittest.main()
