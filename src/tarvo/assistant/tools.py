"""Exact, scoped tools. No SQL, shell, network or arbitrary file paths."""
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote
from tarvo.agents.run_sources import verify_run_sources, RunSourceError
from tarvo.api.document_store import REQUIRED_ROLES, ROLE_LABELS
from .store import AssistantError


def definition(name, description, properties):
    return dict(type='function', name=name, description=description, strict=True,
                parameters=dict(type='object', properties=properties, required=list(properties), additionalProperties=False))


TEXT = {'type': ['string', 'null']}
TOOLS = [
    definition('available_contexts', 'List actual months, batches and runs. Does not switch this conversation.', {}),
    definition('run_summary', 'Read selected run status, exact summary and output names. Money is prepared, never approved/paid.', {}),
    definition('query_output', 'Filter an allowed CSV of selected run; exact totals via Decimal. Returns rows with physical row numbers and source links. Null filter returns first rows. sum_column null omits totals. Never sum unlike money natures.', {'output': {'type': 'string'}, 'contains': TEXT, 'sum_column': TEXT}),
    definition('trace_reference', 'Find an exact identifier in selected run rastro.csv; up to 25 matching source rows.', {'reference': {'type': 'string'}}),
    definition('list_documents', 'List original documents for selected batch or immutable selected run. Never claims arbitrary uploads were parsed.', {}),
    definition('compare_runs', 'Compare two explicit actual runs of SAME month; return exact summary deltas. Does not compare unlike money natures.', {'before_run_id': {'type': 'string'}, 'after_run_id': {'type': 'string'}}),
    definition('prepare_close', 'Prepare action to process selected batch and month. Does NOT execute. Requires user click after target preview. Never approves finances.', {}),
    definition('open_documents', 'Offer navigation to documents/upload for this month. Does not upload or create files.', {}),
]


class WorkspaceTools:
    def __init__(self, store, documents, settings, conversations, conversation):
        self.store, self.documents, self.settings = store, documents, settings
        self.conversations, self.conversation = conversations, conversation
        self.context = conversation['context']
        self.sources, self.actions, self.events = [], [], []

    def contexts(self):
        batches = self.documents.list_batches(200)['items']
        runs = [dict(run_id=r['id'], period=r['period'], status=r['status'], batch_id=r['payload'].get('batch_id'), created_at=r['created_at']) for r in self.store.list_runs(100)]
        return dict(batches=batches, runs=runs, periods=sorted({x['period'] for x in batches + runs}, reverse=True), truncated=len(batches) == 200 or len(runs) == 100,
                    selected_context_evidence=dict(period=self.context.get('period'), run_id=self.context.get('run_id'), status='metadata_only', financial_amount=None, approval='unknown', cash_movements='unknown'),
                    coverage='Metadados dos registros disponíveis neste workspace; ausência nesta lista NÃO prova que não existe valor, aprovação ou movimentação financeira. Sem execução vinculada, não é possível confirmar esses fatos.')

    def job(self, identifier=None):
        identifier = identifier or self.context.get('run_id')
        if not identifier:
            raise AssistantError('RUN_REQUIRED', 'Este mês ainda não tem execução selecionada. Selecione um fechamento ou prepare o conjunto.')
        job = self.store.get(identifier)
        if not job or job['kind'] != 'close':
            raise AssistantError('RUN_NOT_FOUND', 'Execução não encontrada.', 404)
        if job['period'] != self.context['period']:
            raise AssistantError('CONTEXT_MISMATCH', 'A execução pertence a outra competência. Inicie uma conversa no mês correto.')
        if identifier == self.context.get('run_id') and self.context.get('batch_id') and job['payload'].get('batch_id') != self.context['batch_id']:
            raise AssistantError('BATCH_MISMATCH', 'A execução não corresponde ao conjunto selecionado.')
        return job

    def source(self, label, url, **metadata):
        source = dict(id='src-' + str(len(self.sources) + 1), label=label, url=url, period=self.context['period'], **metadata)
        self.sources.append(source)
        return source

    def rows(self, name, job=None):
        job = job or self.job()
        if job['status'] not in ('pending_review', 'completed'):
            raise AssistantError('RUN_NOT_READY', 'O fechamento ainda não terminou. Consulte seu andamento antes de usar valores.')
        if not isinstance(name, str) or Path(name).name != name or '/' in name or '\\' in name or not name.endswith('.csv'):
            raise AssistantError('OUTPUT_NOT_ALLOWED', 'Escolha um arquivo de resultado desta execução.')
        root = Path(job['payload']['output_dir']).resolve()
        if not root.is_relative_to((self.settings.state_dir / 'runs').resolve()):
            raise AssistantError('OUTPUT_NOT_ALLOWED', 'O resultado não pertence ao armazenamento de execuções.')
        listed = [Path(p).name for p in (job.get('result') or {}).get('outputs', [])]
        path = (root / name).resolve()
        if name not in listed or not path.is_relative_to(root) or not path.is_file() or path.stat().st_size > 20_000_000:
            raise AssistantError('OUTPUT_NOT_ALLOWED', 'Arquivo indisponível nesta execução.')
        if job['payload'].get('selection_id'):
            try:
                verify_run_sources({**job['payload'], 'period': job['period']}, root)
            except (RunSourceError, OSError, ValueError, KeyError):
                raise AssistantError('SOURCE_CHANGED', 'As fontes desta execução mudaram ou estão incompletas. Reprocesse o conjunto antes de consultar.') from None
        with path.open(encoding='utf-8-sig', newline='') as file:
            return list(csv.DictReader(file, delimiter=';'))

    @staticmethod
    def decimal(value):
        text = str(value).strip()
        if ',' in text:
            text = text.replace('.', '').replace(',', '.')
        try:
            result = Decimal(text)
            if not result.is_finite():
                raise InvalidOperation()
            return result
        except InvalidOperation:
            raise AssistantError('NOT_NUMERIC', 'A coluna contém valores não numéricos; nenhum total foi inferido.') from None

    def query(self, name, contains=None, sum_column=None, exact=None):
        rows = self.rows(name)
        indexed = [(i + 2, row) for i, row in enumerate(rows)]
        if contains:
            indexed = [(i, row) for i, row in indexed if contains.casefold() in ' '.join(str(v) for v in row.values()).casefold()]
        if exact:
            indexed = [(i, row) for i, row in indexed if exact in row.values()]
        result = dict(output=name, total_rows=len(rows), matched_rows=len(indexed), rows=[dict(row_number=i, data=row) for i, row in indexed[:25]], truncated=len(indexed) > 25)
        if sum_column:
            if name == 'rastro.csv':
                raise AssistantError('MIXED_NATURES', 'O rastro reúne componentes de naturezas diferentes. Consulte o arquivo de saída específico para somar.')
            if not rows or sum_column not in rows[0] or not any(term in sum_column.lower() for term in ('valor', 'comiss', 'total', 'saldo', 'montante')):
                raise AssistantError('SUM_COLUMN_INVALID', 'Escolha uma coluna monetária existente; identificadores e taxas não são somáveis.')
            result['exact_sum'] = str(sum((self.decimal(r[sum_column]) for _, r in indexed), Decimal('0')))
            result['sum_column'] = sum_column
        result['source'] = self.source(name, f"/api/runs/{quote(self.context['run_id'])}/outputs/{quote(name)}", run_id=self.context['run_id'], row_numbers=[i for i, _ in indexed[:25]])
        return result

    def call(self, name, args):
        allowed = next((t for t in TOOLS if t['name'] == name), None)
        if not allowed or not isinstance(args, dict) or set(args) != set(allowed['parameters']['properties']):
            raise AssistantError('INVALID_TOOL', 'Ferramenta ou parâmetros não permitidos.')
        for key, value in args.items():
            schema = allowed['parameters']['properties'][key]
            if value is None and schema.get('type') == ['string', 'null']:
                continue
            if not isinstance(value, str) or len(value) > 200 or not value.strip():
                raise AssistantError('INVALID_TOOL_ARGUMENT', 'Informe um identificador ou filtro válido com até 200 caracteres.')
        self.events.append(dict(tool=name, status='started'))
        try:
            result = self.dispatch(name, args)
            self.events[-1]['status'] = 'completed'
            return result
        except AssistantError as exc:
            self.events[-1]['status'] = 'blocked'
            return dict(error=dict(code=exc.code, message=exc.message))

    def dispatch(self, name, args):
        if name == 'available_contexts':
            return self.contexts()
        if name == 'run_summary':
            job = self.job()
            source = self.source('Resumo do fechamento', f"/api/runs/{quote(job['id'])}", run_id=job['id'])
            result = job.get('result') or {}
            summary = result.get('summary', {})
            approval = summary.get('financial_approval')
            financial_facts = dict(natureza='apuração preparada para revisão', valor_notas_a_emitir_brl=summary.get('invoices_brl'),
                                   aprovacao_registrada='Pendente de revisão de Helena nos registros' if approval == 'PENDENTE_HELENA' else approval or 'Não registrada neste resumo',
                                   estado_de_recebimento='não verificado por estas fontes', valor_recebido_brl=None,
                                   limite='Preparação, emissão de nota e aprovação não determinam recebimento ou movimentação de caixa. Uma nota pode documentar taxa já descontada. Não afirmar pago nem não pago a partir deste resumo.')
            return dict(run_id=job['id'], period=job['period'], batch_id=job['payload'].get('batch_id'), status=job['status'], summary=summary, financial_facts=financial_facts, outputs=[Path(p).name for p in result.get('outputs', [])], source=source, original_sources='vinculadas' if job['payload'].get('selection_id') else 'execução histórica: apenas saídas vinculadas')
        if name == 'query_output':
            return self.query(args['output'], args['contains'], args['sum_column'])
        if name == 'trace_reference':
            return self.query('rastro.csv', exact=args['reference'])
        if name == 'list_documents':
            if self.context.get('run_id'):
                docs = self.job()['payload'].get('source_documents', [])
            elif self.context.get('batch_id'):
                docs = self.documents.list_documents(self.context['batch_id'])['items']
            else:
                docs = []
            return dict(documents=[dict(id=d['id'], name=d['name'], role=d.get('role'), sha256=d['sha256'], source=self.source(d['name'], f"/api/documents/{quote(d['id'])}/original", document_id=d['id'])) for d in docs], limitation='Documentos listados não equivalem a conteúdo interpretado nem aprovação.')
        if name == 'compare_runs':
            before, after = self.job(args['before_run_id']), self.job(args['after_run_id'])
            if before['id'] == after['id']:
                raise AssistantError('TWO_RUNS_REQUIRED', 'Selecione duas execuções distintas para comparar.')
            a, b = (before.get('result') or {}).get('summary', {}), (after.get('result') or {}).get('summary', {})
            changes = {key: dict(before=a.get(key), after=b.get(key)) for key in sorted(set(a) | set(b)) if a.get(key) != b.get(key)}
            for key, change in changes.items():
                if key.endswith('_brl') and change['before'] is not None and change['after'] is not None:
                    change['delta_brl'] = str(self.decimal(change['after']) - self.decimal(change['before']))
            for job in (before, after):
                self.source('Resumo ' + job['id'][:8], f"/api/runs/{quote(job['id'])}", run_id=job['id'])
            return dict(before_run_id=before['id'], after_run_id=after['id'], period=before['period'], summary_changes=changes, limitation='Comparação dos resumos registrados; não prova causalidade ou aprovação financeira.')
        if name == 'prepare_close':
            batch_id = self.context.get('batch_id')
            if not batch_id:
                raise AssistantError('BATCH_REQUIRED', 'Selecione um conjunto de documentos para preparar o fechamento.')
            batch = self.documents.get_batch(batch_id)
            if batch['period'] != self.context['period']:
                raise AssistantError('BATCH_MISMATCH', 'O conjunto pertence a outro mês.')
            available = self.documents.list_documents(batch_id)['items']
            if self.context.get('run_id'):
                selected = self.job()['payload'].get('source_documents') or []
                if not selected or any(not d.get('role') for d in selected):
                    raise AssistantError('RUN_SELECTION_UNAVAILABLE', 'Esta execução não tem uma seleção original completa vinculada. Abra Documentos e selecione as fontes antes de preparar outro fechamento.')
                by_id = {d['id']: d for d in available}
                if any(d['id'] not in by_id or any(by_id[d['id']].get(key) != d.get(key) for key in ('role', 'sha256', 'batch_id')) for d in selected):
                    raise AssistantError('RUN_SELECTION_CHANGED', 'A seleção original não está disponível com a mesma versão e classificação. Abra Documentos para conferir antes de preparar outra execução.')
                documents = [by_id[d['id']] for d in selected]
            else:
                documents = [d for d in available if d.get('role')]
            if not documents:
                raise AssistantError('NO_DOCUMENTS', 'O conjunto não tem fontes financeiras classificadas. Abra Documentos para carregar e selecionar os arquivos.')
            roles = [d['role'] for d in documents]
            if len(roles) != len(set(roles)):
                raise AssistantError('AMBIGUOUS_DOCUMENTS', 'O conjunto tem mais de uma versão da mesma fonte. Abra Documentos e selecione a versão que deseja processar.')
            missing = [role for role in REQUIRED_ROLES if role not in roles]
            if missing:
                raise AssistantError('MISSING_SOURCES', 'Faltam fontes financeiras: ' + ', '.join(ROLE_LABELS[role] for role in missing) + '. Abra Documentos para completar o conjunto.')
            action = self.conversations.action(self.conversation['id'], dict(kind='process_close', label='Processar fechamento', target=dict(period=batch['period'], batch_id=batch_id, document_ids=[d['id'] for d in documents]), target_label=batch['name'] + ' · ' + batch['period'] + f' · {len(documents)} fontes', documents=[dict(id=d['id'],name=d['name'],role=d['role']) for d in documents], requires_confirmation=True))
            self.actions.append(action)
            return dict(action=action, status='awaiting_user_confirmation', explanation='A ação criará uma execução pelo processamento existente. Não emite nota, paga ou aprova valores.')
        if name == 'open_documents':
            action = dict(id='nav-documents', kind='navigate', label='Abrir documentos', target=dict(view='documents', period=self.context['period'], batchId=self.context.get('batch_id')), requires_confirmation=False)
            self.actions.append(action)
            return dict(action=action)
        raise AssistantError('INVALID_TOOL', 'Ferramenta não permitida.')
