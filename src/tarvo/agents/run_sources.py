"""Bind trusted run selections to original documents; no parsing or rule promotion."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class RunSourceError(ValueError):
    """Safe code only: original contents and server paths stay private."""


def verify_run_sources(context, output_dir):
    fields = ('input_dir', 'input_files', 'source_documents', 'selection_id')
    if not any(key in context for key in fields):
        return {'mode': 'legacy_outputs_only', 'verified': False, 'documents': [],
                'limitation': 'Originais não vinculados; consulta limitada às saídas deste fechamento e ao catálogo normativo Tarvo.'}
    if any(not context.get(key) for key in fields):
        raise RunSourceError('incomplete_run_source_context')
    mapping, docs = context['input_files'], context['source_documents']
    if not isinstance(mapping, dict) or not isinstance(docs, list) or not docs:
        raise RunSourceError('invalid_run_source_context')
    root = Path(context['input_dir']).resolve(strict=True)
    descriptor_path = root.parent / (root.name + '.json')
    if not descriptor_path.exists():
        descriptor_path = root / 'selection.json'  # Historical immutable selection.
    if descriptor_path.is_symlink():
        raise RunSourceError('unsafe_run_selection')
    descriptor = json.loads(descriptor_path.read_text(encoding='utf-8'))
    identifier = 'selection-' + hashlib.sha256(json.dumps(descriptor, sort_keys=True).encode()).hexdigest()[:32]
    if identifier != context['selection_id'] or descriptor.get('period') != context.get('period'):
        raise RunSourceError('run_selection_identity_mismatch')
    if descriptor.get('input_files') != mapping:
        raise RunSourceError('run_selection_mapping_mismatch')
    reduced = [{key: doc[key] for key in ('id', 'name', 'sha256', 'role')}
               for doc in sorted(docs, key=lambda item: item['role'])]
    if reduced != descriptor.get('documents') or len(docs) != len(mapping):
        raise RunSourceError('run_selection_documents_mismatch')
    manifest = json.loads((Path(output_dir) / 'manifest.json').read_text(encoding='utf-8'))
    inputs = manifest.get('inputs', [])
    hashes = {item['file']: item['sha256'] for item in inputs}
    if descriptor_path.parent == root and 'selection.json' in hashes:
        if hashes.pop('selection.json') != hashlib.sha256(descriptor_path.read_bytes()).hexdigest():
            raise RunSourceError('run_selection_metadata_mismatch')
        inputs = [item for item in inputs if item['file'] != 'selection.json']
    if (len(inputs) != len(hashes) or set(hashes) != set(mapping.values()) or
            manifest.get('period') != context.get('period')):
        raise RunSourceError('run_manifest_selection_mismatch')
    seen, public = set(), []
    for doc in docs:
        name = mapping.get(doc['role'])
        if (not isinstance(name, str) or not name or Path(name).name != name or
                '/' in name or '\\' in name or name in seen or doc.get('input_name') != name or
                doc.get('batch_id') != descriptor.get('batch_id')):
            raise RunSourceError('unsafe_run_source_mapping')
        path = root / name
        if path.is_symlink() or path.resolve(strict=True).parent != root:
            raise RunSourceError('unsafe_run_source_path')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != doc['sha256'] or digest != hashes[name]:
            raise RunSourceError('run_source_integrity_mismatch')
        seen.add(name)
        public.append({key: doc[key] for key in ('id', 'batch_id', 'name', 'sha256', 'role', 'input_name')})
    return {'mode': 'selected_documents', 'verified': True, 'selection_id': identifier,
            'period': context['period'], 'documents': public,
            'limitation': 'Hashes vinculam os originais ao cálculo; não certificam autenticidade, regra comercial ou aprovação.'}
