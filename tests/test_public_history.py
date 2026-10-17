"""Privacy and provenance checks use synthetic sessions, never live credentials."""
import importlib.util
import json
from pathlib import Path
import tempfile

spec = importlib.util.spec_from_file_location('public_history', Path(__file__).resolve().parents[1]/'tools/export_prompt_history.py')
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


def message(text, role='user', phase=None):
    return dict(type='response_item', timestamp='2026-10-17T19:00:00Z',
                payload=dict(type='message', role=role, phase=phase,
                             content=[dict(type='input_text', text=text)]))


def test_visible_text_preserved_verbatim_without_secrets():
    text = 'Recalcule os 14 ajustes; não invente taxa da Atlas.'
    result = history.classify(message(text), 7)
    assert result['content'] == [text]
    assert result['source_record'] == 7
    assert result['role'] == 'user'
    assert not result['redacted']


def test_tool_bodies_and_hidden_roles_never_enter_output():
    records = [dict(type='response_item', payload=dict(type=kind, output='PRIVATE-FILE-SENTINEL'))
               for kind in ('function_call_output', 'custom_tool_call_output', 'reasoning')]
    records += [message('PRIVATE-FILE-SENTINEL', role=role) for role in ('system','developer')]
    records += [message('PRIVATE-FILE-SENTINEL', role='assistant', phase='analysis')]
    for position, record in enumerate(records, 1):
        result = history.classify(record, position)
        assert result['record_kind'] == 'omission'
        assert 'PRIVATE-FILE-SENTINEL' not in json.dumps(result)
        assert result['source_record'] == position


def test_runtime_and_attachment_omissions_are_explicit():
    result = history.classify(message('<codex_delegation>PRIVATE-FILE-SENTINEL</codex_delegation>'), 3)
    assert result['omitted_parts'] == ['runtime_instructions_or_internal_message']
    assert 'PRIVATE-FILE-SENTINEL' not in json.dumps(result)
    record = message('real text')
    record['payload']['content'].append(dict(type='input_image', image_url='PRIVATE-IMAGE'))
    result = history.classify(record, 4)
    assert result['content'][0] == 'real text'
    assert result['omitted_parts'] == ['non_text_attachment']


def test_known_credentials_and_personal_identifiers_are_redacted():
    text = 'secret-fixture-value; person@example.org; C:/Users/Someone/work; token=12345678-abcd-abcd-abcd-123456789abc'
    clean = history.clean_text(text, ['secret-fixture-value'])
    for private in ('secret-fixture-value', 'person@example.org', 'Someone', '12345678-abcd-abcd-abcd-123456789abc'):
        assert private not in clean


def test_project_selection_original_bytes_and_omission_index():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory); source=root/'sessions'; source.mkdir(); target=root/'public'
        rows=[dict(type='session_meta',payload=dict(cwd=str(root))), message('Prompt real'),
              dict(type='response_item',payload=dict(type='function_call_output',output='PRIVATE-FILE-SENTINEL'))]
        original=''.join(json.dumps(row)+'\n' for row in rows).encode()
        (source/'selected.jsonl').write_bytes(original)
        (source/'other.jsonl').write_text(json.dumps(dict(type='session_meta',payload=dict(cwd=str(root/'other'))))+'\n')
        manifest=history.export(source,target,root)
        assert len(manifest['sessions'])==1
        assert (source/'selected.jsonl').read_bytes()==original
        assert manifest['omissions_index']['records']==1
        assert json.loads((target/'omissions.jsonl').read_text())['source_record']==3
        assert 'PRIVATE-FILE-SENTINEL' not in (target/'selected.jsonl').read_text()
