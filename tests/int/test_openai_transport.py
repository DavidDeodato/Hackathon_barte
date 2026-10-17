"""HTTP mocks only. These tests never contact OpenAI or read actual credentials."""
import io
import json
import os
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from tarvo.agents.openai_transport import (ENDPOINT, OpenAITransport, OpenAITransportError,
                                          _NoRedirect, create_openai_adapter)
from tarvo.agents.service import TOOL_SCHEMA, investigate


def final(text=None, **extra):
    return dict(status='completed', model='configured-fixture-model',
                usage={'input_tokens': 12, 'output_tokens': 5, 'total_tokens': 17},
                output=[{'type': 'message', 'role': 'assistant', 'content': [
                    {'type': 'output_text', 'text': text or json.dumps({'answer': 'Fixture', 'citations': ['CAN-21'], 'proposed_changes': []})}]}], **extra)


def function_call():
    return {'status': 'completed', 'model': 'configured-fixture-model',
            'usage': {'input_tokens': 20, 'output_tokens': 8, 'total_tokens': 28},
            'output': [{'type': 'reasoning', 'id': 'rs-fixture', 'summary': [],
                        'encrypted_content': 'ENCRYPTED_FIXTURE_NOT_FOR_PUBLIC_OUTPUT'},
                       {'type': 'function_call', 'id': 'fc-fixture', 'call_id': 'call-fixture',
                        'name': 'search_rules', 'arguments': json.dumps({'query': 'CAN-21', 'as_of': None, 'limit': None})}]}


class Response:
    def __init__(self, data, status=200):
        self.data = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.status = status

    def read(self, size):
        return self.data[:size]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class TransportTests(unittest.TestCase):
    def request(self):
        return {'messages': [{'role': 'system', 'content': 'Return JSON with evidence.'},
                             {'role': 'user', 'content': 'Fixture question'}],
                'tools': deepcopy(TOOL_SCHEMA), 'max_output_tokens': 1800}

    def test_wire_schema_limits_metrics_and_auth_without_key_exposure(self):
        seen = []
        def opener(request, timeout):
            seen.append((request, timeout))
            return Response(final())
        adapter = OpenAITransport('SYNTHETIC_KEY', 'configured-fixture-model', opener=opener)
        result = adapter(self.request())
        request, timeout = seen[0]
        wire = json.loads(request.data)
        self.assertEqual(request.full_url, ENDPOINT)
        self.assertEqual(timeout, 30)
        self.assertEqual(request.get_header('Authorization'), 'Bearer SYNTHETIC_KEY')
        self.assertFalse(wire['store'])
        self.assertEqual(wire['max_output_tokens'], 1800)
        self.assertEqual(wire['tool_choice'], 'required')
        self.assertNotIn('SYNTHETIC_KEY', repr(adapter))
        self.assertNotIn('SYNTHETIC_KEY', json.dumps(result))
        self.assertEqual(adapter.metrics[0]['input_tokens'], 12)
        self.assertEqual(adapter.metrics[0]['output_tokens'], 5)
        self.assertEqual(adapter.metrics[0]['total_tokens'], 17)
        self.assertGreaterEqual(adapter.metrics[0]['latency_ms'], 0)
        self.assertIsNone(adapter.metrics[0]['cost_brl'])
        for tool in wire['tools']:
            schema = tool['parameters']
            self.assertTrue(tool['strict'])
            self.assertFalse(schema['additionalProperties'])
            self.assertEqual(set(schema['required']), set(schema['properties']))

    def test_json_mode_requirement_is_in_wire_input_and_continuation_preserved(self):
        seen = []
        def opener(request, timeout):
            seen.append(json.loads(request.data))
            return Response(function_call() if len(seen) == 1 else final())
        adapter = OpenAITransport('SYNTHETIC_KEY', 'configured-fixture-model', opener=opener)
        request = self.request()
        request['messages'][0]['content'] = 'Use evidence and return a structured object.'
        original = deepcopy(request['messages'])
        first = adapter(request)
        self.assertTrue(any('json' in item.get('content', '').lower() for item in seen[0]['input']))
        self.assertEqual(request['messages'], original)
        request['messages'] += [{'role': 'assistant', 'content': json.dumps(first)},
                                {'role': 'tool', 'tool_call_id': 'call-fixture', 'content': '{"evidence":"CAN-21"}'}]
        adapter(request)
        self.assertEqual(seen[0]['input'][:3], seen[1]['input'][:3])
        self.assertEqual(sum(item.get('type') == 'function_call_output' for item in seen[1]['input']), 1)

    def test_native_tools_and_encrypted_history_are_kept_private(self):
        seen = []
        def opener(request, timeout):
            seen.append(json.loads(request.data))
            return Response(function_call() if len(seen) == 1 else final())
        adapter = OpenAITransport('SYNTHETIC_KEY', 'configured-fixture-model', opener=opener)
        request = self.request()
        first = adapter(request)
        self.assertEqual(first['tool_calls'][0]['id'], 'call-fixture')
        self.assertEqual(first['tool_calls'][0]['arguments'], {'query': 'CAN-21'})
        self.assertNotIn('ENCRYPTED_FIXTURE', json.dumps(first))
        request['messages'] += [{'role': 'assistant', 'content': json.dumps(first)},
                                {'role': 'tool', 'tool_call_id': 'call-fixture', 'content': '{"evidence":"CAN-21"}'}]
        adapter(request)
        history = seen[1]['input']
        self.assertTrue(any(item.get('type') == 'reasoning' for item in history))
        observation = next(item for item in history if item.get('type') == 'function_call_output')
        self.assertEqual(observation['call_id'], 'call-fixture')
        self.assertEqual(seen[1]['tool_choice'], 'auto')

    def test_service_end_to_end_mock_metrics_and_tools(self):
        seen = []
        def opener(request, timeout):
            seen.append(request)
            return Response(function_call() if len(seen) == 1 else final())
        adapter = OpenAITransport('SYNTHETIC_KEY', 'configured-fixture-model', opener=opener)
        result = investigate('CAN-21', {'project_root': str(ROOT), 'period': '2026-09',
                                      'mode': 'llm', 'model_adapter': adapter})
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(len(result['model_metrics']), 2)
        self.assertEqual(result['model_metrics'][0]['total_tokens'], 28)
        self.assertTrue(any(e['kind'] == 'rule' for e in result['evidence']))
        self.assertNotIn('ENCRYPTED_FIXTURE', json.dumps(result))
        self.assertNotIn('SYNTHETIC_KEY', json.dumps(result))

    def test_invalid_month_as_of_recovers_with_real_tool_observation(self):
        seen = []
        def opener(request, timeout):
            seen.append(json.loads(request.data))
            if len(seen) == 1:
                data = function_call()
                data['output'][1]['arguments'] = json.dumps({'query': 'CAN-21', 'as_of': '2026-09', 'limit': 6})
                return Response(data)
            if len(seen) == 2:
                observation = next(item for item in seen[1]['input'] if item.get('type') == 'function_call_output')
                self.assertEqual(json.loads(observation['output'])['error']['code'], 'invalid_as_of')
                data = function_call()
                data['output'][1].update(id='fc-fixture-2', call_id='call-fixture-2')
                return Response(data)
            return Response(final())
        adapter = OpenAITransport('SYNTHETIC_KEY', 'configured-fixture-model', opener=opener)
        result = investigate('CAN-21', {'project_root': str(ROOT), 'period': '2026-09',
                                      'mode': 'llm', 'model_adapter': adapter})
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(result['tool_errors'], [{'tool': 'search_rules', 'code': 'invalid_as_of'}])
        self.assertTrue(result['evidence'])
        self.assertEqual(len(result['model_metrics']), 3)
        self.assertEqual(len(seen), 3)

    def test_repeated_invalid_tool_arguments_still_exhaust_budget(self):
        def opener(request, timeout):
            data = function_call()
            data['output'][1]['arguments'] = json.dumps({'query': 'CAN-21', 'as_of': None, 'limit': 0})
            return Response(data)
        adapter = OpenAITransport('SYNTHETIC_KEY', 'configured-fixture-model', opener=opener)
        result = investigate('CAN-21', {'project_root': str(ROOT), 'mode': 'llm', 'model_adapter': adapter})
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(len(result['model_metrics']), 4)
        self.assertEqual(len(result['tool_errors']), 4)
        self.assertEqual(result['evidence'], [])

    def test_missing_usage_stays_null(self):
        data = final()
        data['usage'] = None
        adapter = OpenAITransport('SYNTHETIC_KEY', 'configured-fixture-model', opener=lambda *a, **k: Response(data))
        adapter(self.request())
        self.assertIsNone(adapter.metrics[0]['total_tokens'])

    def test_http_error_no_retry_no_body_or_key_exposed(self):
        calls = []
        def opener(*args, **kwargs):
            calls.append(1)
            raise HTTPError(ENDPOINT, 429, 'SYNTHETIC_SECRET_BODY', {}, io.BytesIO(b'SYNTHETIC_SECRET_BODY'))
        adapter = OpenAITransport('SYNTHETIC_KEY', 'configured-fixture-model', opener=opener)
        with self.assertRaises(OpenAITransportError) as error:
            adapter(self.request())
        self.assertEqual(len(calls), 1)
        self.assertEqual(str(error.exception), 'http_429')
        self.assertNotIn('SYNTHETIC_SECRET', json.dumps(adapter.metrics))
        self.assertEqual(adapter.metrics[0]['http_status'], 429)

    def test_timeout_sanitized_and_retained_in_service_metrics(self):
        def opener(*args, **kwargs):
            raise URLError(TimeoutError('SYNTHETIC_SECRET'))
        adapter = OpenAITransport('SYNTHETIC_KEY', 'configured-fixture-model', opener=opener)
        result = investigate('CAN-21', {'project_root': str(ROOT), 'mode': 'llm', 'model_adapter': adapter})
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['model_metrics'][0]['error_code'], 'timeout')
        self.assertNotIn('SYNTHETIC_SECRET', json.dumps(result))

    def test_malformed_incomplete_refusal_and_fake_tool_text_fail(self):
        malformed = [b'not json', final('not JSON'), final('{"tool_calls":[]}')]
        incomplete = final()
        incomplete['status'] = 'incomplete'
        malformed.append(incomplete)
        refusal = final()
        refusal['output'][0]['content'] = [{'type': 'refusal', 'refusal': 'fixture'}]
        malformed.append(refusal)
        for data in malformed:
            with self.subTest(data=str(data)[:40]):
                adapter = OpenAITransport('SYNTHETIC_KEY', 'configured-fixture-model', opener=lambda *a, d=data, **k: Response(d))
                with self.assertRaises(OpenAITransportError):
                    adapter(self.request())

    def test_factory_only_uses_inherited_named_env_and_does_not_call(self):
        for env in ({}, {'OPENAI_API_KEY': 'SYNTHETIC_KEY'}, {'OPENAI_MODEL': 'configured-fixture-model'}):
            with patch.dict(os.environ, env, clear=True):
                self.assertIsNone(create_openai_adapter())
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'SYNTHETIC_KEY', 'OPENAI_MODEL': 'configured-fixture-model'}, clear=True):
            adapter = create_openai_adapter()
            self.assertTrue(callable(adapter))
            self.assertEqual(adapter.metrics, [])

    def test_timeout_budget_config_and_redirect_bounds(self):
        for kwargs in ({'timeout': 31}, {'timeout': 0}, {'max_calls': 5}, {'max_calls': 0}):
            with self.assertRaises(OpenAITransportError):
                OpenAITransport('SYNTHETIC_KEY', 'configured-fixture-model', **kwargs)
        with self.assertRaises(OpenAITransportError):
            _NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid')

    def test_call_budget_and_unrelated_reuse_fail_before_second_http(self):
        count = []
        def opener(*args, **kwargs):
            count.append(1)
            return Response(function_call())
        adapter = OpenAITransport('SYNTHETIC_KEY', 'configured-fixture-model', max_calls=1, opener=opener)
        adapter(self.request())
        with self.assertRaises(OpenAITransportError):
            adapter(self.request())
        self.assertEqual(len(count), 1)
        adapter = OpenAITransport('SYNTHETIC_KEY', 'configured-fixture-model', opener=opener)
        request = self.request()
        adapter(request)
        request['messages'][1]['content'] = 'other investigation'
        request['messages'].append({'role': 'tool', 'tool_call_id': 'call-fixture', 'content': '{}'})
        with self.assertRaises(OpenAITransportError):
            adapter(request)


if __name__ == '__main__':
    unittest.main()
