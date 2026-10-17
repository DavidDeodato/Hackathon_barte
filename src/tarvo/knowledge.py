"""Versioned, cited case knowledge. Retrieval never creates commercial authority."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path


def normalize(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value))
                   if not unicodedata.combining(c)).lower()


class KnowledgeBase:
    def __init__(self, project_root: str | Path):
        self.root = Path(project_root)
        self.path = self.root / 'config' / 'knowledge_rules.json'
        if not self.path.exists():
            self.path = Path(__file__).parent / 'agents' / 'data' / 'knowledge_rules.json'
        self.catalog = json.loads(self.path.read_text(encoding='utf-8'))
        self.version = self.catalog['version']
        self.rules = self.catalog['rules']
        self.digest = hashlib.sha256(self.path.read_bytes()).hexdigest()

    def search(self, query: str, as_of: str | None = None, limit: int = 6) -> list[dict]:
        """Lexical retrieval with explicit dates, not an LLM or confidence estimate."""
        if as_of:
            date.fromisoformat(as_of)
        if not isinstance(limit, int) or not 1 <= limit <= 20:
            raise ValueError('limit deve estar entre 1 e 20.')
        stop = {'como', 'qual', 'para', 'pela', 'pelo', 'devo', 'isso', 'sobre', 'quais', 'porque'}
        terms = {t for t in re.findall(r'[a-z0-9]+', normalize(query)) if len(t) > 2 and t not in stop}
        ranked = []
        for rule in self.rules:
            if as_of and (as_of < rule.get('effective_from', '') or
                          as_of > rule.get('effective_to', '9999-12-31')):
                continue
            keywords = normalize(' '.join(rule.get('keywords', [])))
            body = normalize(rule['title'] + ' ' + rule['text'])
            keyword_terms = set(re.findall(r'[a-z0-9]+', keywords))
            body_terms = set(re.findall(r'[a-z0-9]+', body))
            score = sum(4 if t in keyword_terms else 1 for t in terms if t in keyword_terms or t in body_terms)
            if normalize(rule['id']) in normalize(query):
                score += 100
            if score:
                ranked.append((score, rule['id'], dict(rule, retrieval_score=score)))
        return [r for _, _, r in sorted(ranked, key=lambda x: (-x[0], x[1]))[:limit]]

    def get(self, rule_id: str) -> dict | None:
        return next((dict(r) for r in self.rules if r['id'] == rule_id), None)

    def verify_sources(self) -> list[dict]:
        results = []
        for source in self.catalog['sources']:
            path = self.root / source['path']
            digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
            results.append({'source': source['path'], 'exists': path.exists(),
                            'matches_snapshot': digest == source['sha256'], 'sha256': digest})
        return results

    def propose_rule(self, text: str, source_refs: list[str], category: str,
                     effective_from: str | None = None, *, effective_to: str | None = None,
                     scope: dict | None = None, exceptions: list[str] | None = None,
                     authority_evidence_refs: list[str] | None = None,
                     base_run_id: str | None = None) -> dict:
        if not text.strip() or not source_refs:
            raise ValueError('Uma proposta exige texto e pelo menos uma fonte.')
        if category not in ('commercial', 'closing'):
            raise ValueError('Categoria deve ser commercial ou closing.')
        if any(not isinstance(ref, str) or not ref.strip() for ref in source_refs):
            raise ValueError('Referencias devem ser identificadores nao vazios.')
        if effective_from:
            date.fromisoformat(effective_from)
        if effective_to:
            date.fromisoformat(effective_to)
        if effective_from and effective_to and effective_to < effective_from:
            raise ValueError('Vigencia final anterior a inicial.')
        if scope is not None and not isinstance(scope, dict):
            raise ValueError('scope deve ser objeto.')
        exceptions = exceptions or []
        authority_evidence_refs = authority_evidence_refs or []
        if not isinstance(authority_evidence_refs, list) or not all(isinstance(x, str) and x.strip() for x in authority_evidence_refs):
            raise ValueError('authority_evidence_refs deve ser lista de referencias.')
        if not isinstance(exceptions, list) or not all(isinstance(x, str) for x in exceptions):
            raise ValueError('exceptions deve ser lista de textos.')
        payload = [text, sorted(source_refs), category, effective_from, effective_to, scope, exceptions, base_run_id]
        identifier = hashlib.sha256(json.dumps(payload, sort_keys=True,
                                               ensure_ascii=False).encode()).hexdigest()[:12]
        return {'id': 'PROP-' + identifier, 'text': text, 'source_refs': source_refs,
                'category': category, 'effective_from': effective_from, 'effective_to': effective_to,
                'scope': scope or {}, 'exceptions': exceptions,
                'base_run_id': base_run_id,
                'valid_from': effective_from, 'valid_to': effective_to,
                'authority_evidence_refs': authority_evidence_refs,
                # A retrieved policy naming an approver is not authorization for
                # this condition. No semantic approval verifier exists in v1.
                'status': 'needs_evidence',
                'impact_status': 'not_calculated', 'impact_brl': None,
                'state': 'PROPOSTA', 'approved_by': None, 'approved_at': None,
                'required_authority': 'Comercial' if category == 'commercial' else 'Helena',
                'applied_to_calculation': False, 'base_version': self.version,
                'review_required': True,
                'validation_gaps': (["scope" ] if not scope else []) +
                                   (["valid_from"] if not effective_from else []) +
                                   (["authority_evidence_refs"] if not authority_evidence_refs else []) +
                                   ["specific_authority_decision_not_verified"]}
