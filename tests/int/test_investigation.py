"""Executable contract and safety regressions, not a financial reference oracle."""
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from tarvo.agents.service import investigate
from tarvo.intelligence import InvestigationEngine
from tarvo.knowledge import KnowledgeBase


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'config').mkdir()
        (self.root / 'saida').mkdir()
        (self.root / 'source.txt').write_text('Fixture explicita; nao e outubro real.', encoding='utf-8')
        catalog = {'version': 'TEST-FIXTURE', 'sources': [{'path': 'source.txt',
                   'sha256': hashlib.sha256((self.root / 'source.txt').read_bytes()).hexdigest()}],
                   'rules': [{'id': 'RULE-1', 'title': 'Atlas', 'text': 'Atlas aguarda Comercial.',
                              'keywords': ['atlas'], 'source_refs': ['source.txt#RULE-1']}]}
        (self.root / 'config' / 'knowledge_rules.json').write_text(json.dumps(catalog), encoding='utf-8')
        self.context = dict(project_root=str(self.root), output_dir=str(self.root / 'saida'),
                            run_id='fixture-run', period='2026-09')

    def tearDown(self):
        self.temp.cleanup()

    def write_csv(self, name, rows):
        with (self.root / 'saida' / name).open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, delimiter=';', fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def request(self, **updates):
        return dict(text='Proposta sintetica', source_refs=['RULE-1'], category='commercial',
                    effective_from='2026-10-01', effective_to='2026-10-31',
                    scope={'merchant': 'FICTICIO', 'business_line': 'CHECKOUT'},
                    exceptions=['Estorno de periodo anterior'], **updates)

    def test_default_is_observed_deterministic_and_json_serializable(self):
        result = investigate('Atlas', self.context)
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(result['model_called'])
        self.assertEqual(result['mode'], 'deterministic')
        self.assertEqual(result['proposed_changes'], [])
        self.assertIn('RULE-1', result['answer'])
        for event in result['events']:
            self.assertTrue(set('id run_id task_id timestamp actor type status summary evidence_refs'.split()) <= event.keys())
            self.assertEqual(event['run_id'], 'fixture-run')
        self.assertTrue(any(e['type'] == 'tool.called' for e in result['events']))
        json.dumps(result)

    def test_llm_unavailable_does_not_silently_fallback(self):
        result = investigate('Atlas', dict(self.context, mode='llm'))
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['evidence'], [])
        self.assertFalse(result['model_called'])

    def test_unknown_is_gap(self):
        result = investigate('zzxyq', self.context)
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(result['evidence'], [])

    def test_changed_or_missing_source_blocks_before_adapter(self):
        for mutate in ('change', 'delete'):
            with self.subTest(mutate=mutate):
                path = self.root / 'source.txt'
                if mutate == 'change':
                    path.write_text('changed', encoding='utf-8')
                else:
                    path.unlink()
                result = investigate('Atlas', dict(self.context, mode='llm', model_adapter=lambda _: self.fail('must not call')))
                self.assertEqual(result['status'], 'blocked')
                self.assertFalse(result['model_called'])

    def test_exact_output_lookup_and_trace(self):
        self.write_csv('comissoes_por_lojista.csv', [{'id_saida': 'OUT-1', 'cnpj': '12345678901234', 'comissao_brl': '12.35'}])
        self.write_csv('rastro.csv', [{'id_saida': 'OUT-1', 'ref_origem': 'TX0001', 'arquivo_origem': 'fixture.csv', 'valor': '12.35'}])
        result = investigate('TX0001', self.context)
        item = next(e for e in result['evidence'] if e['kind'] == 'output_trace')
        self.assertEqual(item['data']['trace'][0]['valor'], '12.35')
        self.assertEqual(item['data']['reference'], 'TX0001')

    def test_pending_continuity_is_stable_and_never_auto_resolved(self):
        self.write_csv('pendencias.csv', [{'id_saida': 'P-1', 'ref_origem': 'TX001', 'motivo': 'Atlas sem contrato', 'valor_brl': '', 'quem_decide': 'Comercial'}])
        first = investigate('pendencias outubro Atlas', self.context)
        second = investigate('pendencias outubro Atlas', self.context)
        a = next(e['data'] for e in first['evidence'] if e['kind'] == 'pending')
        b = next(e['data'] for e in second['evidence'] if e['kind'] == 'pending')
        self.assertEqual(a['continuity_key'], b['continuity_key'])
        self.assertFalse(a['automatically_resolved'])
        self.assertEqual(a['pending']['valor_brl'], '')
        self.assertTrue(a['carry_to_next_period'])
        self.assertEqual(a['origin_period'], '2026-09')
        self.assertEqual(a['origin_refs'], ['TX001'])

    def test_proposal_has_authority_scope_dates_and_cannot_activate(self):
        before = (self.root / 'config/knowledge_rules.json').read_bytes()
        result = investigate('Atlas', dict(self.context, change_request=self.request()))
        self.assertEqual(result['status'], 'needs_review')
        proposal = result['proposed_changes'][0]
        self.assertEqual(proposal['required_authority'], 'Comercial')
        self.assertIsNone(proposal['approved_by'])
        self.assertFalse(proposal['applied_to_calculation'])
        self.assertEqual(proposal['scope']['merchant'], 'FICTICIO')
        self.assertEqual(proposal['base_run_id'], 'fixture-run')
        self.assertEqual(proposal['status'], 'needs_evidence')
        self.assertEqual(proposal['authority_evidence_refs'], [])
        self.assertEqual(proposal['impact_status'], 'not_calculated')
        self.assertIsNone(proposal['impact_brl'])
        self.assertEqual(proposal['valid_from'], '2026-10-01')
        self.assertEqual(before, (self.root / 'config/knowledge_rules.json').read_bytes())

    def test_unknown_citation_or_approval_field_rejects_proposal(self):
        for alteration in ({'source_refs': ['HALLUCINATED']}, {'approved_by': 'Helena'}):
            change = self.request()
            change.update(alteration)
            result = investigate('Atlas', dict(self.context, change_request=change))
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['proposed_changes'], [])

    def test_v11_validity_and_distinct_authority_evidence(self):
        change = self.request()
        change['valid_from'] = change.pop('effective_from')
        change['valid_to'] = change.pop('effective_to')
        change['authority_evidence_refs'] = ['RULE-1']
        result = investigate('Atlas', dict(self.context, change_request=change))
        item = result['proposed_changes'][0]
        self.assertEqual(item['status'], 'needs_evidence')
        self.assertIn('specific_authority_decision_not_verified', item['validation_gaps'])
        self.assertIsNone(item['approved_by'])
        self.assertFalse(item['applied_to_calculation'])
        change['authority_evidence_refs'] = ['NOT-RETRIEVED']
        self.assertEqual(investigate('Atlas', dict(self.context, change_request=change))['status'], 'failed')

    def test_conflicting_validity_aliases_rejected(self):
        change = self.request()
        change['valid_from'] = '2026-11-01'
        self.assertEqual(investigate('Atlas', dict(self.context, change_request=change))['status'], 'failed')

    def test_proposal_identity_includes_scope_and_end_date(self):
        kb = KnowledgeBase(self.root)
        a = kb.propose_rule(**self.request())
        change = self.request()
        change['scope'] = {'merchant': 'OUTRO-FICTICIO'}
        b = kb.propose_rule(**change)
        self.assertNotEqual(a['id'], b['id'])
        change = self.request()
        change['effective_to'] = '2026-11-30'
        self.assertNotEqual(a['id'], kb.propose_rule(**change)['id'])

    def test_invalid_dates_and_categories_fail_closed(self):
        for changes in ({'effective_from': '2026-13-01'}, {'effective_to': '2026-09-30'}, {'category': 'payment'}):
            change = self.request()
            change.update(changes)
            result = investigate('Atlas', dict(self.context, change_request=change))
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['proposed_changes'], [])

    def test_replay_loop_reacts_to_actual_tool_result_without_claiming_model(self):
        observed = []
        def adapter(request):
            observed.append(request)
            if len(observed) == 1:
                return {'tool_calls': [{'id': 'c1', 'name': 'search_rules', 'arguments': {'query': 'Atlas'}}]}
            self.assertIn('RULE-1', request['messages'][-1]['content'])
            return {'answer': 'Fixture: Atlas aguarda Comercial.', 'citations': ['RULE-1']}
        result = investigate('Atlas', dict(self.context, mode='replay', replay_adapter=adapter))
        self.assertEqual(result['status'], 'needs_review')
        self.assertFalse(result['model_called'])
        self.assertEqual(len(observed), 2)
        self.assertTrue(any('Replay' in x for x in result['limitations']))

    def test_unretrieved_model_citation_is_not_promoted(self):
        result = investigate('Atlas', dict(self.context, mode='replay', replay_adapter=lambda _: {'answer': 'invented', 'citations': ['RULE-1']}))
        self.assertEqual(result['status'], 'needs_review')
        self.assertNotIn('invented', result['answer'])

    def test_arbitrary_file_and_unknown_tools_are_rejected(self):
        for name, arguments in [('read_source', {'source_path': '../.env'}), ('write_rule', {})]:
            result = investigate('Atlas', dict(self.context, mode='replay', replay_adapter=lambda _, n=name, a=arguments: {'tool_calls': [{'name': n, 'arguments': a}]}))
            self.assertEqual(result['status'], 'failed')

    def test_registered_source_is_really_read(self):
        calls = []
        def adapter(request):
            calls.append(request)
            if len(calls) == 1:
                return {'tool_calls': [{'name': 'read_source', 'arguments': {'source_path': 'source.txt'}}]}
            return {'answer': 'Fixture, nao outubro real.', 'citations': ['source.txt']}
        result = investigate('source', dict(self.context, mode='replay', replay_adapter=adapter))
        self.assertEqual(result['evidence'][0]['kind'], 'source_text')
        self.assertIn('Fixture explicita', result['evidence'][0]['data']['text'])

    def test_budget_is_bounded(self):
        adapter = lambda _: {'tool_calls': [{'name': 'search_rules', 'arguments': {'query': 'Atlas'}}]}
        result = investigate('Atlas', dict(self.context, mode='replay', replay_adapter=adapter))
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(sum(e['summary'].startswith('Adaptador') for e in result['events']), 4)

    def test_provider_error_detail_is_not_exposed(self):
        def adapter(_):
            raise RuntimeError('FAKE_SECRET_MUST_NOT_APPEAR')
        result = investigate('Atlas', dict(self.context, mode='replay', replay_adapter=adapter))
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn('FAKE_SECRET', json.dumps(result))

    def test_empty_question_and_bad_mode_fail(self):
        self.assertEqual(investigate('', self.context)['status'], 'failed')
        self.assertEqual(investigate('Atlas', dict(self.context, mode='something'))['status'], 'failed')


class RealCaseRetrievalTests(unittest.TestCase):
    def test_atlas_full_context_preserves_unconfirmed_contract(self):
        kb = KnowledgeBase(ROOT)
        case = kb.get('CASE-ATLAS')
        self.assertIsNotNone(case)
        self.assertIn('Não faturar até comercial confirmar', case['text'])
        self.assertIn('10/09', case['text'])
        self.assertIn('2025', case['text'])
        self.assertIn('CASE-ATLAS', [row['id'] for row in kb.search('Atlas contrato outubro', limit=10)])

    def test_atlas_prompt_distinguishes_current_state_from_future_condition(self):
        requests = []
        def adapter(request):
            requests.append(request)
            if len(requests) == 1:
                return {'tool_calls': [{'id': 's1', 'name': 'search_rules', 'arguments': {'query': 'Atlas CAN-04 CAN-19', 'limit': 10}}]}
            return {'answer': 'Fixture de teste, revisao necessaria.', 'citations': ['CAN-04', 'CAN-19']}
        result = investigate('Atlas', dict(project_root=str(ROOT), mode='replay', replay_adapter=adapter))
        prompt = requests[0]['messages'][0]['content']
        self.assertIn('AINDA NAO esta confirmado', prompt)
        self.assertIn('SOMENTE QUANDO o Comercial confirmar', prompt)
        self.assertEqual(result['status'], 'needs_review')
        self.assertFalse(result['model_called'])

    def test_catalog_snapshot_and_legacy_entrypoint(self):
        kb = KnowledgeBase(ROOT)
        self.assertGreater(len(kb.rules), 40)
        self.assertTrue(all(x['matches_snapshot'] for x in kb.verify_sources()))
        rules = kb.search('Casa do Estudante')
        self.assertTrue(any('Orbe' in r['text'] for r in rules))
        result = InvestigationEngine(ROOT).investigate('CAN-21')
        self.assertFalse(result['model_called'])
        self.assertIn('Comercial', result['answer'])

    def test_real_case_authority_does_not_become_approval(self):
        result = investigate('CAN-21', dict(project_root=str(ROOT), run_id='real-case-read'))
        self.assertEqual(result['status'], 'completed')
        self.assertIn('Helena', result['answer'])
        self.assertEqual(result['proposed_changes'], [])


if __name__ == '__main__':
    unittest.main()
