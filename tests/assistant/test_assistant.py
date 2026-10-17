"""Synthetic fixtures, not September actuals or measured model performance."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from tarvo.storage import Store
from tarvo.api.document_store import DocumentStore
from tarvo.assistant.router import create_assistant_router
from tarvo.assistant.service import AssistantService
from tarvo.assistant.store import AssistantError
from tarvo.assistant.tools import WorkspaceTools
from tarvo.assistant.transport import AssistantTransport


@pytest.fixture
def workspace(tmp_path):
    settings = SimpleNamespace(state_dir=tmp_path)
    jobs = Store(tmp_path / 'jobs.sqlite3')
    documents = DocumentStore(tmp_path / 'documents')
    batch = documents.create_batch('Sintético · teste', '2026-09')
    doc = documents.add_document(batch['id'], 'source.txt', b'Synthetic source')
    root = tmp_path / 'runs' / 'run-a'
    root.mkdir(parents=True)
    (root / 'notas.csv').write_text('id;lojista;valor_nota\nN1;Teste;1,10\nN2;Teste;2,20\nN3;Outro;9,00\n', encoding='utf-8')
    (root / 'rastro.csv').write_text('id_saida;origem;valor\nN1;source.txt:2;1,10\n', encoding='utf-8')
    jobs.enqueue('close', '2026-09', {'output_dir': str(root), 'batch_id': batch['id'], 'source_documents': [doc]}, run_id='run-a')
    jobs.claim()
    jobs.finish('run-a', 'pending_review', {'summary': {'notas': '12.30'}, 'outputs': ['notas.csv', 'rastro.csv']})
    service = AssistantService(jobs, documents, settings, transport_factory=lambda: None)
    context = dict(period='2026-09', batch_id=batch['id'], run_id='run-a')
    return service, context, doc


def tools_for(service, context):
    conversation = service.create(context)
    return WorkspaceTools(service.store, service.documents, service.settings, service.conversations, conversation)


def test_exact_sum_and_physical_lines(workspace):
    service, context, _ = workspace
    tools = tools_for(service, context)
    result = tools.call('query_output', dict(output='notas.csv', contains='Teste', sum_column='valor_nota'))
    assert result['exact_sum'] == '3.30'
    assert result['matched_rows'] == 2
    assert result['source']['row_numbers'] == [2, 3]
    assert result['source']['run_id'] == 'run-a'


def test_context_mismatch(workspace):
    service, context, _ = workspace
    with pytest.raises(AssistantError, match='CONTEXT_MISMATCH'):
        service.create({**context, 'period': '2026-10'})


def test_other_batch_rejected(workspace):
    service, context, _ = workspace
    other = service.documents.create_batch('Outro', '2026-09')
    with pytest.raises(AssistantError, match='BATCH_MISMATCH'):
        service.create({**context, 'batch_id': other['id']})


def test_no_data_month_does_not_fallback(workspace):
    service, _, _ = workspace
    tools = tools_for(service, dict(period='2026-10', batch_id=None, run_id=None))
    assert tools.call('run_summary', {})['error']['code'] == 'RUN_REQUIRED'
    assert tools.sources == []


def test_summary_does_not_infer_payment_from_pending_approval(workspace):
    service, context, _ = workspace
    with service.store.connect() as db:
        job = service.store.get('run-a')
        result = job['result']
        result['summary'].update(invoices_brl='12.30', financial_approval='PENDENTE_HELENA')
        db.execute('UPDATE jobs SET result=? WHERE id=?', (json.dumps(result), 'run-a'))
    summary = tools_for(service, context).call('run_summary', {})
    facts = summary['financial_facts']
    assert facts['valor_notas_a_emitir_brl'] == '12.30'
    assert facts['aprovacao_registrada'] == 'Pendente de revisão de Helena nos registros'
    assert facts['estado_de_recebimento'] == 'não verificado por estas fontes'
    assert facts['valor_recebido_brl'] is None
    assert summary['summary']['financial_approval'] == 'PENDENTE_HELENA'


def test_available_contexts_are_metadata_not_financial_zero(workspace):
    service, _, _ = workspace
    result = tools_for(service, dict(period='2099-01', run_id=None, batch_id=None)).call('available_contexts', {})
    evidence = result['selected_context_evidence']
    assert evidence['status'] == 'metadata_only'
    assert evidence['financial_amount'] is None
    assert evidence['approval'] == 'unknown'
    assert evidence['cash_movements'] == 'unknown'


@pytest.mark.parametrize('path', ['../notas.csv', 'C:\\notas.csv', 'unknown.csv', '/notas.csv'])
def test_arbitrary_files_blocked(workspace, path):
    service, context, _ = workspace
    result = tools_for(service, context).call('query_output', dict(output=path, contains=None, sum_column=None))
    assert result['error']['code'] == 'OUTPUT_NOT_ALLOWED'


def test_unknown_tool_and_injected_fields(workspace):
    service, context, _ = workspace
    tools = tools_for(service, context)
    with pytest.raises(AssistantError):
        tools.call('shell', {'command': 'anything'})
    with pytest.raises(AssistantError):
        tools.call('run_summary', {'run_id': 'other'})


def test_trace_exact(workspace):
    service, context, _ = workspace
    result = tools_for(service, context).call('trace_reference', {'reference': 'N1'})
    assert result['matched_rows'] == 1
    assert result['rows'][0]['data']['origem'] == 'source.txt:2'


def test_mixed_nature_trace_cannot_be_summed(workspace):
    service, context, _ = workspace
    result = tools_for(service, context).call('query_output', dict(output='rastro.csv', contains=None, sum_column='valor'))
    assert result['error']['code'] == 'MIXED_NATURES'


def test_comparison_requires_explicit_distinct_runs(workspace):
    service, context, _ = workspace
    result = tools_for(service, context).call('compare_runs', dict(before_run_id='run-a', after_run_id='run-a'))
    assert result['error']['code'] == 'TWO_RUNS_REQUIRED'


def test_changed_selected_sources_block_output(workspace):
    service, context, _ = workspace
    with service.store.connect() as db:
        job = service.store.get('run-a')
        payload = {**job['payload'], 'selection_id': 'selection-invalid'}
        db.execute('UPDATE jobs SET payload=? WHERE id=?', (json.dumps(payload), 'run-a'))
    result = tools_for(service, context).call('query_output', dict(output='notas.csv', contains=None, sum_column=None))
    assert result['error']['code'] == 'SOURCE_CHANGED'


def test_amount_column_must_be_numeric(workspace):
    service, context, _ = workspace
    result = tools_for(service, context).call('query_output', dict(output='notas.csv', contains=None, sum_column='id'))
    assert result['error']['code'] == 'SUM_COLUMN_INVALID'


def test_original_document_links(workspace):
    service, context, doc = workspace
    result = tools_for(service, context).call('list_documents', {})
    assert result['documents'][0]['source']['url'] == f"/api/documents/{doc['id']}/original"


def test_history_persists_and_new_chat_is_empty(workspace):
    service, context, _ = workspace
    first = service.create(context)
    response = service.message(first['id'], 'Minha pergunta', 'request_0001')
    assert response['messages'][1]['status'] == 'unavailable'
    again = AssistantService(service.store, service.documents, service.settings, transport_factory=lambda: None)
    assert again.conversations.get(first['id'])['messages'] == response['messages']
    assert again.create(context)['messages'] == []
    assert len(service.message(first['id'], 'Minha pergunta', 'request_0001')['messages']) == 2


def test_processing_preview_and_idempotency(workspace):
    service, context, _ = workspace
    dispatched = []
    service.create_run = lambda payload: dispatched.append(payload) or {'run_id': 'created-once', 'status': 'queued'}
    from tarvo.api.document_store import ROLE_FILES, REQUIRED_ROLES
    for role in REQUIRED_ROLES:
        service.documents.add_document(context['batch_id'], ROLE_FILES[role], b'Synthetic processing source', role=role)
    tools = tools_for(service, {**context, 'run_id': None})
    result = tools.call('prepare_close', {})
    assert dispatched == []
    action = result['action']
    assert action['target']['period'] == '2026-09'
    assert action['target']['batch_id'] == context['batch_id']
    assert len(action['target']['document_ids']) == len(REQUIRED_ROLES)
    assert all(d['name'] != 'source.txt' for d in action['documents'])
    first = service.execute(tools.conversation['id'], action['id'])
    assert service.execute(tools.conversation['id'], action['id']) == first
    assert len(dispatched) == 1


def test_prepare_cannot_dispatch_incomplete_or_support_only_batch(workspace):
    service, context, _ = workspace
    result = tools_for(service, {**context, 'run_id': None}).call('prepare_close', {})
    assert result['error']['code'] == 'NO_DOCUMENTS'


@pytest.mark.parametrize('add_adjustment', [False, True])
def test_reprocess_preserves_run_ids_with_new_versions_or_adjustments(workspace, add_adjustment):
    service, context, _ = workspace
    from tarvo.api.document_store import ROLE_FILES, REQUIRED_ROLES
    selected_roles = list(REQUIRED_ROLES) + ([] if add_adjustment else ['adjustments'])
    selected = [service.documents.add_document(context['batch_id'], ROLE_FILES[role], b'Synthetic original', role=role) for role in selected_roles]
    with service.store.connect() as db:
        job = service.store.get('run-a')
        payload = {**job['payload'], 'source_documents': selected}
        db.execute('UPDATE jobs SET payload=? WHERE id=?', (json.dumps(payload), 'run-a'))
    if add_adjustment:
        extra = service.documents.add_document(context['batch_id'], ROLE_FILES['adjustments'], b'Synthetic new adjustment', role='adjustments')
    else:
        extra = service.documents.add_document(context['batch_id'], '02_new_version.xlsx', b'Synthetic new version', role='contracts')
    result = tools_for(service, context).call('prepare_close', {})
    assert set(result['action']['target']['document_ids']) == {d['id'] for d in selected}
    assert extra['id'] not in result['action']['target']['document_ids']


def test_legacy_run_does_not_guess_selection(workspace):
    service, context, _ = workspace
    result = tools_for(service, context).call('prepare_close', {})
    assert result['error']['code'] == 'RUN_SELECTION_UNAVAILABLE'


def test_batch_with_multiple_versions_requires_selection(workspace):
    service, context, _ = workspace
    from tarvo.api.document_store import ROLE_FILES, REQUIRED_ROLES
    for role in REQUIRED_ROLES:
        service.documents.add_document(context['batch_id'], ROLE_FILES[role], b'Synthetic source', role=role)
    service.documents.add_document(context['batch_id'], '02_version2.xlsx', b'Alternate synthetic', role='contracts')
    result = tools_for(service, {**context, 'run_id': None}).call('prepare_close', {})
    assert result['error']['code'] == 'AMBIGUOUS_DOCUMENTS'


class FakeModel:
    metrics = [{'provider': 'synthetic-test', 'cost_brl': None}]
    def __init__(self):
        self.calls = 0
    def __call__(self, messages):
        self.calls += 1
        if self.calls == 1:
            return {'tool_calls': [{'id': 'call-1', 'name': 'query_output', 'arguments': dict(output='notas.csv', contains='Teste', sum_column='valor_nota')}]}
        observation = json.loads(messages[-1]['content'])
        return {'answer': 'Total preparado: ' + observation['exact_sum'], 'citations': [observation['source']['id']]}


def test_model_tool_loop_real_storage_synthetic_model(workspace):
    service, context, _ = workspace
    service.transport_factory = FakeModel
    chat = service.create(context)
    result = service.message(chat['id'], 'Qual total de Teste?', 'request_model1')
    message = result['messages'][-1]
    assert message['content'] == 'Total preparado: 3.30'
    assert message['sources'][0]['row_numbers'] == [2, 3]
    assert message['tool_events'] == [dict(tool='query_output', status='completed')]


def test_final_without_tool_is_not_accepted(workspace):
    service, context, _ = workspace
    class NoTool:
        def __call__(self, messages):
            return dict(answer='Invented unsupported answer', citations=[])
    service.transport_factory = NoTool
    chat = service.create(context)
    result = service.message(chat['id'], 'Quanto?', 'request_no_tool')
    assert result['messages'][-1]['status'] == 'unavailable'
    assert 'Invented' not in result['messages'][-1]['content']


def test_final_with_sources_requires_citation(workspace):
    service, context, _ = workspace
    class NoCitation(FakeModel):
        def __call__(self, messages):
            result = super().__call__(messages)
            if 'answer' in result:
                result['citations'] = []
            return result
    service.transport_factory = NoCitation
    chat = service.create(context)
    result = service.message(chat['id'], 'Quanto?', 'request_no_citation')
    assert result['messages'][-1]['status'] == 'unavailable'


def test_router_auth_validation_and_action_confirmation(workspace):
    service, context, _ = workspace
    app = FastAPI()
    router = create_assistant_router(store=service.store, documents=service.documents, settings=service.settings, transport_factory=FakeModel)
    allowed = [False]
    def auth():
        if not allowed[0]:
            raise HTTPException(401)
    app.include_router(router, dependencies=[Depends(auth)])
    client = TestClient(app)
    assert client.get('/api/assistant/conversations').status_code == 401
    allowed[0] = True
    chat = client.post('/api/assistant/conversations', json=context).json()
    assert client.post(f"/api/assistant/conversations/{chat['id']}/messages", json={'content': '  ', 'request_id': 'test_12345'}).status_code == 422
    assert client.post(f"/api/assistant/conversations/{chat['id']}/actions/unknown", json={'confirm': False}).status_code == 422
    reply = client.post(f"/api/assistant/conversations/{chat['id']}/messages", json={'content': 'Quanto?', 'request_id': 'test_123456'}).json()
    assert reply['messages'][-1]['content'] == 'Total preparado: 3.30'
    assert client.get(f"/api/assistant/conversations/{chat['id']}").json()['messages'] == reply['messages']


def test_transport_wire_uses_native_tools_and_private_state():
    observed = []
    responses = [dict(status='completed', output=[dict(type='function_call', call_id='c1', name='available_contexts', arguments='{}')]), dict(status='completed', output=[dict(type='message', content=[dict(type='output_text', text='{"answer":"Consulta concluída","citations":[]}')])], usage=dict(input_tokens=10, output_tokens=5,total_tokens=15))]
    class Response:
        status = 200
        def __init__(self, data): self.data = data
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return json.dumps(self.data).encode()
    def opener(request, timeout):
        observed.append(json.loads(request.data))
        return Response(responses.pop(0))
    adapter = AssistantTransport('synthetic-key', 'test-model', opener=opener)
    messages = [dict(role='system', content='JSON answer'), dict(role='user', content='Olá')]
    assert adapter(messages)['tool_calls'][0]['name'] == 'available_contexts'
    messages += [dict(role='assistant', content=''), dict(role='tool', tool_call_id='c1', content='{}')]
    assert adapter(messages)['answer'] == 'Consulta concluída'
    assert observed[0]['store'] is False
    assert observed[1]['input'][-1]['type'] == 'function_call_output'
    assert adapter.metrics[-1]['total_tokens'] == 15
    assert 'synthetic-key' not in json.dumps(adapter.metrics)


@pytest.mark.parametrize('final_mode', ['answer', 'tool', 'unknown_citation', 'blocked_only'])
def test_last_request_reserved_for_synthesis_with_same_four_call_budget(workspace, final_mode):
    """Synthetic HTTP provider; tests wire mechanics, never live model quality.

    CAPTURE03 recorded two blocked queries then a valid CSV query, followed by
    another tool call instead of synthesis. The actual invalid arguments were
    not recorded; these deliberately invalid fixture columns are not a replay.
    """
    service, context, _ = workspace
    wire, adapters = [], []
    class Response:
        status = 200
        def __init__(self, value): self.value = value
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return json.dumps(self.value).encode()
    def opener(request, timeout):
        payload = json.loads(request.data)
        wire.append(payload)
        number = len(wire)
        if payload['tool_choice'] == 'none':
            if final_mode == 'tool':
                output = [dict(type='function_call', call_id='forbidden-final', name='prepare_close', arguments='{}')]
            else:
                citation = 'invented-source' if final_mode == 'unknown_citation' else 'src-1'
                answer = dict(answer='Fixture synthesis from observed CSV: 3.30', citations=[] if final_mode == 'blocked_only' else [citation])
                output = [dict(type='message', content=[dict(type='output_text', text=json.dumps(answer))])]
        else:
            invalid_column = number <= 2 or final_mode == 'blocked_only'
            args = dict(output='notas.csv', contains='Teste', sum_column='fixture_invalid_column' if invalid_column else 'valor_nota')
            output = [dict(type='function_call', call_id=f'query-{number}', name='query_output', arguments=json.dumps(args))]
        return Response(dict(status='completed', output=output, usage=dict(input_tokens=5,output_tokens=5,total_tokens=10)))
    def factory():
        adapter = AssistantTransport('synthetic-key', 'test-model', opener=opener)
        adapters.append(adapter)
        return adapter
    service.transport_factory = factory
    chat = service.create(context)
    response = service.message(chat['id'], 'Fixture total with evidence?', 'request_synthesis_1')
    last = response['messages'][-1]
    assert len(wire) == 4
    assert [p['tool_choice'] for p in wire] == ['required','auto','auto','none']
    assert wire[-1]['input'][-1]['type'] == 'function_call_output'
    assert len(last['tool_events']) == 3  # No fourth tool is executed.
    assert [t['status'] for t in last['tool_events']][:2] == ['blocked','blocked']
    assert last['model_metrics'][-1]['call_index'] == 4
    from tarvo.agents.openai_transport import OpenAITransportError
    with pytest.raises(OpenAITransportError, match='call_budget_exceeded'):
        adapters[0]([])
    assert len(wire) == 4  # A fifth HTTP request is impossible.
    if final_mode == 'answer':
        assert last['status'] == 'completed'
        assert last['content'] == 'Fixture synthesis from observed CSV: 3.30'
        assert last['failure_code'] is None
        assert last['sources'][0]['row_numbers'] == [2,3]
        observation = json.loads(wire[-1]['input'][-1]['output'])
        assert observation['exact_sum'] == '3.30'
    else:
        assert last['status'] == 'unavailable'
        assert last['failure_code'] == {'tool':'unexpected_final_tool_call','unknown_citation':'unverified_citation','blocked_only':'no_completed_tool'}[final_mode]
        assert last['actions'] == []
        assert 'Fixture synthesis' not in last['content']


def test_exhausted_adapter_failure_stays_unavailable_and_history_is_not_rewritten(workspace):
    service, context, _ = workspace
    class NeverFinal:
        def __init__(self): self.calls = 0
        def __call__(self, messages):
            self.calls += 1
            return dict(tool_calls=[dict(id=f'call-{self.calls}',name='run_summary',arguments={})])
    service.transport_factory = NeverFinal
    chat = service.create(context)
    failed = service.message(chat['id'], 'Fixture no final', 'request_exhaustion_1')
    original_failed = failed['messages'][-1].copy()
    assert original_failed['status'] == 'unavailable'
    assert original_failed['failure_code'] == 'turn_limit'
    service.transport_factory = FakeModel
    later = service.message(chat['id'], 'Separate fixture turn', 'request_exhaustion_2')
    assert later['messages'][-1]['status'] == 'completed'
    assert later['messages'][1] == original_failed
