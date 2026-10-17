"""Case review regressions. Synthetic public fixtures; no provider calls/env."""
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from tarvo.agents.case_review import CSV_NAMES, review_case


def verdict(*, objections=None, needs_evidence=False, **extra):
    answer = {'summary': 'Revisao preparada, requer decisao humana.',
              'observations': ['Fonte e alcance precisam ser conferidos pelo responsavel.'],
              'objections': objections or [], 'limitations': ['Fixture; nao mede semantica LLM.'],
              'needs_evidence': needs_evidence, 'packet_unchanged': True}
    answer.update(extra)
    return {'answer': answer, 'citations': ['R1'], 'proposed_changes': []}


class ScriptedAdapter:
    def __init__(self, responses):
        self.responses = responses
        self.requests = []
        self.metrics = []

    def __call__(self, request):
        self.requests.append(deepcopy(request))
        item = self.responses[len(self.requests) - 1]
        return item(request) if callable(item) else deepcopy(item)


class CaseReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.output = self.root / 'saida'
        self.output.mkdir()
        (self.root / 'config').mkdir()
        self.source = self.root / 'rules.txt'
        self.source.write_text('Casa: nao cobrar Orbe; revisao Helena/Comercial.', encoding='utf-8')
        catalog = {'version': 'CASE-FIXTURE', 'sources': [{'path': 'rules.txt',
                   'sha256': hashlib.sha256(self.source.read_bytes()).hexdigest()}],
                   'rules': [{'id': 'R1', 'title': 'Casa', 'text': self.source.read_text(encoding='utf-8'),
                              'keywords': ['Casa'], 'source_refs': ['rules.txt#R1']}]}
        (self.root / 'config/knowledge_rules.json').write_text(json.dumps(catalog), encoding='utf-8')
        for name in CSV_NAMES:
            (self.output / name).write_text('id_saida;valor\nFIX-1;12.35\n', encoding='utf-8')
        self.packet = {'case_id': 'FIX-CASE-1', 'case_key': 'casa', 'period': '2026-09',
                       'snapshot': {name: hashlib.sha256((self.output / name).read_bytes()).hexdigest() for name in CSV_NAMES},
                       'source_refs': ['FIX-TX1'], 'rows': [{'ref_origem': 'FIX-TX1', 'amount': '12.35'}],
                       'amount': '12.35', 'amount_nature': 'devolucao_interna',
                       'action_type': 'preparar_devolucao', 'recipient': 'Helena/Comercial',
                       'owner': 'Helena', 'closure_evidence': ['Decisao especifica e comprovante vinculado.'],
                       'status': 'prepared_for_review', 'approved': False, 'sent': False}
        self.context = {'project_root': str(self.root), 'output_dir': str(self.output), 'run_id': 'FIX-RUN'}
        # Synthetic fixture packet is authenticated by a stubbed DOM builder.
        # Production binding is exercised separately against real DOM packets.
        self.canonical_packet = deepcopy(self.packet)
        self.builder_patch = patch('tarvo.finance.cases.build_case_packet', side_effect=lambda *_: deepcopy(self.canonical_packet))
        self.builder_patch.start()

    def tearDown(self):
        self.builder_patch.stop()
        self.temp.cleanup()

    def adapters(self, investigator_final=None, critic_final=None):
        investigator = ScriptedAdapter([
            {'tool_calls': [{'id': 'read1', 'name': 'search_rules', 'arguments': {'query': 'Casa'}}]},
            investigator_final or verdict()])
        critic = ScriptedAdapter([critic_final or verdict()])
        return investigator, critic

    def run_assisted(self, investigator=None, critic=None, **context):
        if investigator is None:
            investigator, default_critic = self.adapters()
            critic = critic or default_critic
        return review_case(self.packet, dict(self.context, mode='replay', investigator_adapter=investigator,
                                             critic_adapter=critic, **context))

    def test_deterministic_packet_is_usable_without_fake_roles(self):
        before = deepcopy(self.packet)
        result = review_case(self.packet, dict(self.context, case_adapter_factory=lambda _: self.fail('no factory in deterministic')))
        self.assertEqual(result['status'], 'review_required')
        self.assertFalse(result['model_called'])
        self.assertEqual(result['packet'], before)
        self.assertEqual(self.packet, before)
        self.assertTrue(result['packet_unchanged'])
        self.assertFalse(any(r['executed'] for r in result['roles']))
        self.assertFalse(result['approved'])
        self.assertFalse(result['applied_to_calculation'])
        json.dumps(result)

    def test_roles_have_distinct_instances_and_critic_gets_observed_sources(self):
        inv, critic = self.adapters()
        result = self.run_assisted(inv, critic)
        self.assertEqual(result['status'], 'needs_evidence')
        self.assertEqual(len(inv.requests), 2)
        self.assertEqual(len(critic.requests), 1)
        critic_input = json.loads(critic.requests[0]['messages'][1]['content'])
        self.assertEqual(critic_input['investigator_conclusion']['role'], 'investigator')
        self.assertEqual(critic_input['evidence'][0]['data']['id'], 'R1')
        self.assertEqual(critic_input['decision_under_review'], self.packet['action_type'])
        semantics = critic_input['packet']['field_semantics']
        self.assertFalse(semantics['closure_evidence']['proves_existing_documents'])
        self.assertFalse(semantics['amount']['proves_payment_or_refund'])
        self.assertFalse(semantics['rows']['omission_proves_missing_corpus_or_rate'])
        self.assertEqual(result['analysis_kind'], 'experimental_assisted_review')
        self.assertEqual(result['semantic_quality'], 'not_validated')
        self.assertIn('estorno', critic_input['case_challenge'].lower())
        self.assertEqual(critic.requests[0]['tools'], [])
        self.assertEqual(result['packet']['amount'], '12.35')
        self.assertFalse(result['model_called'])  # explicit replay
        self.assertEqual([r['role'] for r in result['roles']], ['investigator', 'critic'])
        role_events = [e for e in result['events'] if e['actor'] != 'INT']
        self.assertTrue(all(e['parent_task_id'] == result['review_id'] for e in role_events))
        self.assertEqual(len({e['task_id'] for e in role_events}), 2)

    def test_same_adapter_instance_rejected_without_calls(self):
        inv, _ = self.adapters()
        result = self.run_assisted(inv, inv)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error_code'], 'roles_share_adapter_instance')
        self.assertEqual(inv.requests, [])

    def test_two_bound_methods_of_same_instance_are_not_independent(self):
        inv, _ = self.adapters()
        result = self.run_assisted(inv.__call__, inv.__call__)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error_code'], 'roles_share_adapter_instance')
        self.assertEqual(inv.requests, [])

    def test_factory_is_called_once_per_role_and_not_serialized(self):
        inv, critic = self.adapters()
        roles = []
        def factory(role):
            roles.append(role)
            return inv if role == 'investigator' else critic
        result = review_case(self.packet, dict(self.context, mode='replay', case_adapter_factory=factory))
        self.assertEqual(roles, ['investigator', 'critic'])
        self.assertEqual(result['status'], 'needs_evidence')
        json.dumps(result)

    def test_unknown_amount_stays_null_and_not_zero(self):
        self.packet.update(case_key='atlas', amount=None, amount_nature='comissao_desconhecida')
        self.canonical_packet = deepcopy(self.packet)
        result = self.run_assisted()
        self.assertIsNone(result['packet']['amount'])
        self.assertEqual(result['status'], 'needs_evidence')

    def test_critic_objection_preserves_packet_and_requires_evidence(self):
        inv, critic = self.adapters(critic_final=verdict(objections=['Decisao: preparar devolucao | Fonte: R1 e packet.recipient | Efeito: manter o item sem envio ate conferir a origem.']))
        before = deepcopy(self.packet)
        result = self.run_assisted(inv, critic)
        self.assertEqual(result['status'], 'needs_evidence')
        self.assertEqual(result['packet'], before)
        self.assertEqual(result['objections'][0]['role'], 'critic')
        self.assertEqual(len(result['roles']), 2)

    def test_missing_or_changed_snapshot_fails_before_any_model(self):
        for action in ('change', 'delete'):
            path = self.output / CSV_NAMES[0]
            if action == 'change':
                path.write_text('changed', encoding='utf-8')
            else:
                path.unlink()
            inv, critic = self.adapters()
            result = self.run_assisted(inv, critic)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['error_code'], 'snapshot_missing_or_stale')
            self.assertFalse(result['integration_allowed'])
            self.assertEqual(inv.requests, [])

    def test_missing_knowledge_source_fails_before_model(self):
        self.source.unlink()
        inv, critic = self.adapters()
        result = self.run_assisted(inv, critic)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error_code'], 'knowledge_source_missing_or_stale')
        self.assertEqual(inv.requests, [])

    def test_source_or_output_changed_during_role_rejects_integration(self):
        for target in (self.source, self.output / CSV_NAMES[0]):
            original = target.read_bytes()
            def mutate(request):
                target.write_text('changed during role', encoding='utf-8')
                return verdict()
            inv, critic = self.adapters()
            inv.responses[0] = mutate
            result = self.run_assisted(inv, critic)
            self.assertEqual(result['status'], 'failed')
            self.assertFalse(result['integration_allowed'])
            self.assertEqual(critic.requests, [])
            target.write_bytes(original)

    def test_packet_mutation_from_injected_adapter_fails_closed(self):
        def mutate(request):
            self.packet['amount'] = '999.00'
            return verdict()
        inv, critic = self.adapters()
        inv.responses[0] = mutate
        result = self.run_assisted(inv, critic)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error_code'], 'packet_mutated')
        self.assertFalse(result['packet_unchanged'])
        self.assertEqual(result['packet']['amount'], '12.35')
        self.assertEqual(critic.requests, [])

    def test_model_cannot_return_changes_or_approval_fields(self):
        variants = []
        changed = verdict()
        changed['proposed_changes'] = [{'amount': '0'}]
        variants.append(changed)
        variants.append(verdict(amount='999'))
        variants.append(verdict(status='approved'))
        variants.append(verdict(packet_unchanged=False))
        variants.append(verdict(summary='Helena já aprovou este caso.'))
        for candidate in variants:
            inv, critic = self.adapters(investigator_final=candidate)
            result = self.run_assisted(inv, critic)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['packet']['amount'], '12.35')
            self.assertFalse(result['approved'])
            self.assertFalse(result['integration_allowed'])
            self.assertEqual(critic.requests, [])

    def test_explicit_absence_of_approval_is_not_positive_approval(self):
        inv, critic = self.adapters(critic_final=verdict(summary='O caso não está aprovado e não foi enviado.', needs_evidence=True))
        result = self.run_assisted(inv, critic)
        self.assertEqual(result['status'], 'needs_evidence')
        self.assertFalse(result['approved'])

    def test_qa_explicit_absence_and_positive_certainty_are_distinct(self):
        inv, critic = self.adapters(critic_final=verdict(summary='Não há evidência de que Helena aprovou esta condição.', needs_evidence=True))
        self.assertEqual(self.run_assisted(inv, critic)['status'], 'needs_evidence')
        inv, critic = self.adapters(critic_final=verdict(summary='Não há dúvida de que Helena aprovou esta condição.'))
        self.assertEqual(self.run_assisted(inv, critic)['status'], 'failed')
        inv, critic = self.adapters(critic_final=verdict(summary='Helena aprovou esta devolução.'))
        self.assertEqual(self.run_assisted(inv, critic)['status'], 'failed')

    def test_same_csv_snapshot_does_not_authenticate_forged_packet_content(self):
        for key, value in [('amount', '0.00'), ('recipient', 'Orbe'), ('rows', []), ('case_id', 'forged')]:
            forged = dict(self.packet, **{key: value})
            result = review_case(forged, self.context)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['error_code'], 'packet_not_canonical')
            self.assertFalse(result['integration_allowed'])

    def test_unqualified_objection_is_preserved_without_accepted_counterevidence(self):
        text = 'Falta toda a tabela historica e provas de outras partes.'
        inv, critic = self.adapters(critic_final=verdict(objections=[text]))
        result = self.run_assisted(inv, critic)
        role = result['roles'][1]
        self.assertEqual(result['status'], 'needs_evidence')
        self.assertEqual(role['objections'], [])
        self.assertEqual(role['model_objections'], [text])
        self.assertEqual(role['rejected_objections'][0]['text'], text)
        self.assertEqual(role['rejected_objections'][0]['reason'], 'missing_concrete_decision_source_effect')

    def test_not_found_is_observed_abstention_not_global_absence(self):
        inv, critic = self.adapters()
        inv.responses[0] = {'tool_calls': [{'id': 'nf', 'name': 'lookup_reference', 'arguments': {'reference': 'DOES-NOT-EXIST'}}]}
        inv.responses[1] = verdict(needs_evidence=True)
        inv.responses[1]['citations'] = ['packet:' + self.packet['case_id']]
        critic.responses[0]['citations'] = ['packet:' + self.packet['case_id']]
        result = self.run_assisted(inv, critic)
        self.assertEqual(result['status'], 'needs_evidence')
        record = result['evidence'][0]
        self.assertEqual(record['kind'], 'lookup_not_found')
        self.assertEqual(record['data']['reference'], 'DOES-NOT-EXIST')
        self.assertTrue(record['data']['files_checked'])
        self.assertTrue(any('ausência global' in item for item in result['roles'][0]['limitations']))

    def test_investigator_must_actually_retrieve_and_cite_evidence(self):
        inv, critic = self.adapters()
        inv.responses = [verdict()]
        result = self.run_assisted(inv, critic)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error_code'], 'investigator_without_retrieved_evidence')
        inv, critic = self.adapters()
        inv.responses[1]['citations'] = ['MADE-UP']
        self.assertEqual(self.run_assisted(inv, critic)['status'], 'failed')

    def test_budget_ends_without_circular_debate(self):
        call = {'tool_calls': [{'id': 's', 'name': 'search_rules', 'arguments': {'query': 'Casa'}}]}
        inv = ScriptedAdapter([call, call])
        critic = ScriptedAdapter([verdict(needs_evidence=True)])
        result = self.run_assisted(inv, critic)
        self.assertEqual(result['status'], 'needs_evidence')
        self.assertEqual(len(inv.requests), 2)
        self.assertEqual(len(critic.requests), 1)
        self.assertEqual(len(result['roles']), 2)

    def test_no_adapter_does_not_simulate_two_roles(self):
        result = review_case(self.packet, dict(self.context, mode='llm'))
        self.assertEqual(result['status'], 'needs_evidence')
        self.assertFalse(result['model_called'])
        self.assertEqual(result['roles'], [])

    def test_unknown_tool_and_arbitrary_source_fail(self):
        for name, args in [('write_rule', {}), ('read_source', {'source_path': '../.env'})]:
            inv, critic = self.adapters()
            inv.responses[0] = {'tool_calls': [{'id': 'bad', 'name': name, 'arguments': args}]}
            result = self.run_assisted(inv, critic)
            self.assertEqual(result['status'], 'failed')
            self.assertFalse(result['integration_allowed'])

    def test_provider_exception_text_not_disclosed(self):
        def fail(request):
            raise RuntimeError('SYNTHETIC_SECRET_DO_NOT_EXPOSE')
        inv, critic = self.adapters()
        inv.responses[0] = fail
        result = self.run_assisted(inv, critic)
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn('SYNTHETIC_SECRET', json.dumps(result))

    def test_invalid_or_unserializable_packet_returns_safe_failure(self):
        for packet in ({}, [], dict(self.packet, amount=object())):
            result = review_case(packet, self.context)
            self.assertEqual(result['status'], 'failed')

    def test_packet_cannot_arrive_approved_sent_or_model_calculated(self):
        for field in ('approved', 'sent', 'model_used'):
            packet = dict(self.packet, **{field: True})
            result = review_case(packet, self.context)
            self.assertEqual(result['status'], 'failed')
            self.assertFalse(result['integration_allowed'])

    def test_native_openai_transport_preserves_structured_role_answer(self):
        from tarvo.agents.openai_transport import OpenAITransport
        requests = {'investigator': [], 'critic': []}
        class Response:
            status = 200
            def __init__(self, data):
                self.data = json.dumps(data).encode('utf-8')
            def read(self, size):
                return self.data[:size]
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
        def opener(role):
            def send(request, timeout):
                wire = json.loads(request.data)
                requests[role].append(wire)
                self.assertEqual(timeout, 30)
                if role == 'investigator' and len(requests[role]) == 1:
                    output = [{'type': 'function_call', 'id': 'fc1', 'call_id': 'call1',
                               'name': 'search_rules', 'arguments': '{"query":"Casa","as_of":null,"limit":6}'}]
                else:
                    output = [{'type': 'message', 'role': 'assistant', 'content': [
                        {'type': 'output_text', 'text': json.dumps(verdict())}]}]
                return Response({'status': 'completed', 'model': 'fixture-model', 'output': output,
                                 'usage': {'input_tokens': 10, 'output_tokens': 3, 'total_tokens': 13}})
            return send
        inv = OpenAITransport('SYNTHETIC-KEY', 'fixture-model', max_calls=2, opener=opener('investigator'))
        critic = OpenAITransport('SYNTHETIC-KEY', 'fixture-model', max_calls=2, opener=opener('critic'))
        result = self.run_assisted(inv, critic)
        self.assertEqual(result['status'], 'needs_evidence')
        self.assertEqual(len(requests['investigator']), 2)
        self.assertEqual(len(requests['critic']), 1)
        self.assertEqual(requests['critic'][0]['tools'], [])
        self.assertEqual([metric['role'] for metric in result['model_metrics']], ['investigator', 'investigator', 'critic'])
        self.assertEqual(sum(metric['total_tokens'] for metric in result['model_metrics']), 39)
        self.assertNotIn('SYNTHETIC-KEY', json.dumps(result))
        self.assertFalse(result['model_called'])


class CanonicalDOMRegressionTests(unittest.TestCase):
    @unittest.skipUnless((ROOT / 'saida/manifest.json').is_file(), 'Requires generated baseline outputs')
    def test_real_dom_packet_binding_rejects_same_snapshot_forgery(self):
        from tarvo.finance.cases import build_case_packet
        context = {'project_root': str(ROOT), 'output_dir': str(ROOT / 'saida')}
        mundo = build_case_packet(str(ROOT / 'saida'), 'mundo')
        original = deepcopy(mundo)
        self.assertEqual(review_case(mundo, context)['status'], 'review_required')
        forged = dict(mundo, amount='0.00')
        self.assertEqual(review_case(forged, context)['error_code'], 'packet_not_canonical')
        casa = build_case_packet(str(ROOT / 'saida'), 'casa')
        self.assertEqual(review_case(dict(casa, recipient='Orbe'), context)['error_code'], 'packet_not_canonical')
        self.assertEqual(mundo, original)

    @unittest.skipUnless((ROOT / 'saida/manifest.json').is_file(), 'Requires generated baseline outputs')
    def test_compound_source_references_retrieve_real_case_rules(self):
        from tarvo.finance.cases import build_case_packet
        cases = [
            ('casa', 'contexto/RESPOSTAS_FINANCEIRO.md#CAN-07/CAN-17/REG-C02', ['CAN-07', 'CAN-17', 'REG-C02']),
            ('mundo', 'contexto/RESPOSTAS_FINANCEIRO.md#REG-R03/REG-R04/REG-R05', ['REG-R03', 'REG-R04', 'REG-R05']),
            ('atlas', 'contexto/RESPOSTAS_FINANCEIRO.md#CAN-04/CAN-19', ['CAN-04', 'CAN-19']),
        ]
        for key, reference, ids in cases:
            with self.subTest(case=key):
                packet = build_case_packet(str(ROOT / 'saida'), key)
                answer = verdict()
                answer['citations'] = ids
                inv = ScriptedAdapter([{'tool_calls': [{'id': 'composite', 'name': 'lookup_reference',
                                                       'arguments': {'reference': reference}}]}, answer])
                critic = ScriptedAdapter([answer])
                result = review_case(packet, {'project_root': str(ROOT), 'output_dir': str(ROOT / 'saida'),
                                              'mode': 'replay', 'investigator_adapter': inv, 'critic_adapter': critic})
                self.assertEqual(result['status'], 'needs_evidence')
                self.assertEqual([row['data']['id'] for row in result['evidence']], ids)
                self.assertTrue(all(row['kind'] == 'rule' for row in result['evidence']))
                self.assertTrue(all(row['data']['reference_resolution']['requested_reference'] == reference for row in result['evidence']))
                self.assertEqual(result['packet'], packet)
                self.assertFalse(result['model_called'])

    def test_registered_line_locators_and_bare_rule_ids(self):
        from tarvo.agents.case_review import _resolve_knowledge_reference
        from tarvo.intelligence import InvestigationEngine
        engine = InvestigationEngine(ROOT)
        bare = _resolve_knowledge_reference(engine, 'CAN-07/CAN-17')
        self.assertEqual([item[1]['id'] for item in bare], ['CAN-07', 'CAN-17'])
        line = _resolve_knowledge_reference(engine, 'contexto/RESPOSTAS_FINANCEIRO.md#L62')
        self.assertEqual(line[0][1]['reference_resolution']['resolved_locator'], 'L62')
        excerpt = _resolve_knowledge_reference(engine, 'contexto/RESPOSTAS_FINANCEIRO.md#L1-L2')
        self.assertEqual(excerpt[0][0], 'source_excerpt')
        self.assertEqual(excerpt[0][1]['locator'], 'L1-L2')
        self.assertIn('Regras e esclarecimentos', excerpt[0][1]['text'])

    def test_unknown_or_unsafe_compound_sources_do_not_trigger_arbitrary_read(self):
        from tarvo.agents.case_review import _resolve_knowledge_reference, CaseReviewError
        from tarvo.intelligence import InvestigationEngine
        engine = InvestigationEngine(ROOT)
        for reference in ('../.env#L1', 'unknown.txt#CAN-07',
                          'contexto/RESPOSTAS_FINANCEIRO.md#../.env',
                          'contexto/RESPOSTAS_FINANCEIRO.md#L1-L99999'):
            with self.subTest(reference=reference), self.assertRaises(CaseReviewError):
                _resolve_knowledge_reference(engine, reference)
        missing = _resolve_knowledge_reference(engine, 'contexto/RESPOSTAS_FINANCEIRO.md#CAN-99999')
        self.assertEqual(missing[0][0], 'catalog_reference_not_found')
        self.assertEqual(missing[0][1]['locator'], 'CAN-99999')


if __name__ == '__main__':
    unittest.main()
