"""Two isolated synthetic variants of the received pack; no provider calls."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from tarvo.api.document_store import DocumentStore
from tarvo.agents.service import investigate
from tarvo.agents.case_review import review_case
from tarvo.agents.run_sources import RunSourceError
from tarvo.finance import run_close
from tarvo.finance.cases import build_case_packet
from tarvo.intelligence import InvestigationEngine


class RunSourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.temp.name)
        cls.store = DocumentStore(cls.folder / 'store')
        cls.contexts, cls.references = [], ['TX99123451', 'TX99123452']
        for number, reference in enumerate(cls.references):
            batch = cls.store.create_batch('Fixture isolamento ' + str(number), '2026-09')
            for path in sorted((ROOT / 'contexto/data_pack').iterdir()):
                if not path.is_file():
                    continue
                raw = path.read_bytes()
                if path.suffix == '.csv':
                    raw = raw.replace(b'TX88410932', reference.encode())
                cls.store.add_document(batch['id'], path.name, raw)
            selection = cls.store.resolve_inputs(batch['id'])
            output = cls.folder / ('run-' + str(number))
            run_close(selection['input_dir'], str(output), selection['period'], input_files=selection['input_files'])
            cls.contexts.append(dict(selection, output_dir=str(output), project_root=str(ROOT), run_id='fixture-' + str(number)))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_two_batches_lookup_only_their_exclusive_reference_and_original(self):
        for number, context in enumerate(self.contexts):
            engine = InvestigationEngine(ROOT, context['output_dir'], run_context=context)
            hit = engine.lookup(self.references[number])
            self.assertEqual(hit['status'], 'ENCONTRADO')
            docs = hit['source_documents']
            self.assertTrue(docs)
            self.assertTrue(all(doc['batch_id'] == context['source_documents'][0]['batch_id'] for doc in docs))
            self.assertEqual(engine.lookup(self.references[1-number])['status'], 'NAO_ENCONTRADO')
            result = investigate(self.references[number], context)
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['run_sources']['selection_id'], context['selection_id'])
            self.assertNotIn(context['input_dir'], json.dumps(result))

    def test_case_review_uses_bound_selection_and_preserves_packet_policy(self):
        for context in self.contexts:
            packet = build_case_packet(context['output_dir'], 'casa')
            result = review_case(packet, context)
            self.assertEqual(result['status'], 'review_required')
            self.assertTrue(result['run_sources']['verified'])
            self.assertTrue(result['packet_unchanged'])
            self.assertFalse(result['approved'])
            self.assertFalse(result['model_called'])

    def test_crossed_run_selection_fails_before_provider_and_review(self):
        crossed = dict(self.contexts[0], output_dir=self.contexts[1]['output_dir'])
        def forbidden(_):
            self.fail('Provider must not be called')
        result = investigate('TX99123451', dict(crossed, mode='llm', model_adapter=forbidden))
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['model_called'])
        packet = build_case_packet(crossed['output_dir'], 'casa')
        review = review_case(packet, crossed)
        self.assertEqual(review['status'], 'failed')
        self.assertFalse(review['integration_allowed'])

    def test_partial_context_cannot_fallback_to_default_pack(self):
        for key in ('input_dir', 'input_files', 'source_documents', 'selection_id'):
            context = dict(self.contexts[0])
            del context[key]
            with self.subTest(key=key), self.assertRaises(RunSourceError):
                InvestigationEngine(ROOT, context['output_dir'], run_context=context)

    def test_selected_bytes_rechecked_after_initialization(self):
        context = self.contexts[0]
        engine = InvestigationEngine(ROOT, context['output_dir'], run_context=context)
        path = Path(context['input_dir']) / context['input_files']['orbe']
        original = path.read_bytes()
        try:
            path.write_bytes(original + b'alterado')
            with self.assertRaises(RunSourceError):
                engine.lookup(self.references[0])
        finally:
            path.write_bytes(original)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         next(doc['sha256'] for doc in context['source_documents'] if doc['role'] == 'orbe'))

    def test_legacy_scope_explicit_and_normative_catalog_kept_separate(self):
        context = self.contexts[0]
        legacy = {'project_root': str(ROOT), 'output_dir': context['output_dir'], 'period': context['period']}
        result = investigate(self.references[0], legacy)
        self.assertEqual(result['run_sources']['mode'], 'legacy_outputs_only')
        self.assertFalse(result['run_sources']['verified'])
        engine = InvestigationEngine(ROOT, context['output_dir'], run_context=context)
        self.assertEqual([s['path'] for s in engine.kb.catalog['sources']], ['contexto/RESPOSTAS_FINANCEIRO.md'])

    def test_historical_in_directory_descriptor_is_validated_explicitly(self):
        context = self.contexts[0]
        root = Path(context['input_dir'])
        external, internal = root.parent / (root.name + '.json'), root / 'selection.json'
        manifest_path = Path(context['output_dir']) / 'manifest.json'
        original = manifest_path.read_bytes()
        try:
            external.replace(internal)
            manifest = json.loads(original)
            manifest['inputs'].append({'file': 'selection.json', 'sha256': hashlib.sha256(internal.read_bytes()).hexdigest()})
            manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
            engine = InvestigationEngine(ROOT, context['output_dir'], run_context=context)
            self.assertTrue(engine.run_sources['verified'])
            internal.write_bytes(internal.read_bytes() + b' ')
            with self.assertRaises(RunSourceError):
                engine.verify_run_sources()
        finally:
            # Restore the exact descriptor and manifest, including after failure.
            descriptor = json.loads(internal.read_bytes())
            internal.write_text(json.dumps(descriptor, ensure_ascii=False, indent=2), encoding='utf-8')
            internal.replace(external)
            manifest_path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
