"""Read-only semantic comparison of trusted close directories (contract v1.2).

Output identifiers are linkage, never business identity. Aggregates are keyed by
period/entity/line; their traced components are compared as content. Trace rows
are keyed by the semantic output plus source file/ref/physical line. Ambiguous
business keys, orphan traces and mismatched manifest hashes fail explicitly.
"""
from __future__ import annotations

import csv
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

SCHEMAS = {
    'comissoes_por_lojista.csv': ('comissao_brl', ('cnpj','linha_negocio')),
    'divergencias_taxa.csv': ('diferenca_brl', ('cnpj','linha_negocio','ref_origem','natureza','arquivo_origem','linha_origem')),
    'notas_a_emitir.csv': ('valor_brl', ('tomador_cnpj','linha_negocio')),
    'lancamentos_classificados.csv': ('valor', ('banco','ref_origem')),
    'pendencias.csv': ('valor_brl', ('tipo','ref_origem')),
}
TRACE = 'rastro.csv'
NUMERIC = {'comissao_brl','diferenca_brl','valor_brl','valor','taxa_contratada_pct','taxa_aplicada_pct','confianca'}


def _canonical_number(value):
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f'Invalid decimal: {value!r}') from exc
    if not number.is_finite():
        raise ValueError('Non-finite financial value')
    return format(number.normalize(),'f') if number else '0'


def _canonical_row(row):
    return {k:_canonical_number(v) if k in NUMERIC and v != '' else v
            for k,v in sorted(row.items()) if k != 'id_saida'}


def _token(key):
    return json.dumps(key,sort_keys=True,ensure_ascii=False,separators=(',',':'))


def _source_key(row):
    return {k:row.get(k,'') for k in ('arquivo_origem','ref_origem','linha_origem')}


def _source_ref(row):
    return f"{row.get('arquivo_origem','')}#{row.get('ref_origem','')}@L{row.get('linha_origem','')}"


def _load(folder):
    root = Path(folder).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Run location must be a directory')

    def path_for(name):
        path = (root/name).resolve(strict=True)
        if path.parent != root:
            raise ValueError('Run artifact resolves outside trusted directory')
        return path

    manifest = json.loads(path_for('manifest.json').read_text(encoding='utf-8'))
    period = manifest.get('period')
    run_id = manifest.get('run_id')
    if not isinstance(period,str) or not period or not isinstance(run_id,str) or not run_id:
        raise ValueError('Manifest requires period and run_id')
    hashes = {}
    for artifact in manifest.get('outputs',[]):
        name = artifact.get('file')
        if name in hashes:
            raise ValueError('Duplicate manifest output name')
        hashes[name] = artifact.get('sha256')
    tables = {}
    for name in [*SCHEMAS,TRACE]:
        path = path_for(name)
        if name not in hashes or hashlib.sha256(path.read_bytes()).hexdigest() != hashes[name]:
            raise ValueError(f'Manifest output hash mismatch/missing: {name}')
        with path.open(encoding='utf-8-sig',newline='') as fh:
            reader = csv.DictReader(fh,delimiter=';')
            required = {'id_saida'} | ({'arquivo_origem','ref_origem','valor'} if name == TRACE else
                                     {SCHEMAS[name][0],*SCHEMAS[name][1]})
            if not required.issubset(reader.fieldnames or []):
                raise ValueError(f'Unsupported semantic schema: {name}; missing {sorted(required-set(reader.fieldnames or []))}')
            rows = list(reader)
            if any(None in r or any(v is None for v in r.values()) for r in rows):
                raise ValueError(f'Malformed CSV row: {name}')
            tables[name] = rows

    records = {name:{} for name in [*SCHEMAS,TRACE]}
    ids = {}
    for name,(_,fields) in SCHEMAS.items():
        for raw in tables[name]:
            ident = raw['id_saida']
            key = dict(period=period,output=name,**{f:raw[f] for f in fields})
            if not ident or ident in ids:
                raise ValueError(f'Duplicate/empty output identifier: {ident!r}')
            if _token(key) in records[name]:
                raise ValueError(f'Ambiguous semantic output key in {name}: {_token(key)}')
            record = dict(key=key,row=_canonical_row(raw),traces=[],source_refs=[],id=ident)
            records[name][_token(key)] = record
            ids[ident] = record
    trace_keys = set()
    for raw in tables[TRACE]:
        if raw['id_saida'] not in ids:
            raise ValueError(f'Orphan trace identifier: {raw["id_saida"]}')
        parent = ids[raw['id_saida']]
        key = dict(output=TRACE,target=parent['key'],source=_source_key(raw))
        token = _token(key)
        if token in trace_keys:
            raise ValueError(f'Ambiguous source trace key: {token}')
        trace_keys.add(token)
        canonical = _canonical_row(raw)
        parent['traces'].append(canonical)
        parent['source_refs'].append(_source_ref(raw))
        records[TRACE][token] = dict(key=key,row=canonical,traces=[],source_refs=[_source_ref(raw)])
    for name in SCHEMAS:
        field = SCHEMAS[name][0]
        for record in records[name].values():
            record['traces'].sort(key=_token)
            record['source_refs'] = sorted(set(record['source_refs']))
            amount = record['row'][field]
            if amount != '' and (not record['traces'] or sum((Decimal(r['valor']) for r in record['traces']),Decimal(0)) != Decimal(amount)):
                raise ValueError(f'Unreconciled trace in {name}: {record["id"]}')
    inputs = {}
    for item in manifest.get('inputs',[]):
        name = item.get('file')
        if not name or name in inputs:
            raise ValueError('Ambiguous manifest input filename')
        inputs[name] = item.get('sha256')
    return dict(root=root,manifest=manifest,period=period,run_id=run_id,records=records,inputs=inputs)


def _snapshot(record):
    if record is None:
        return None
    return dict(record['row'],source_refs=record['source_refs'],rastro=record['traces'])


def _delta(before,after,field):
    if before is not None and after is not None:
        if before['row'].get('metrica_valor') != after['row'].get('metrica_valor'):
            return None
    b = before['row'].get(field) if before is not None else '0'
    a = after['row'].get(field) if after is not None else '0'
    if b in ('',None) or a in ('',None):
        return None
    return format((Decimal(a)-Decimal(b)).quantize(Decimal('.01')),'f')


def _nature(name,record):
    row = record['row']
    if name == 'lancamentos_classificados.csv':
        return {k:row.get(k,'') for k in ('banco','conta_codigo')}
    if name == 'pendencias.csv':
        return {k:row.get(k,'') for k in ('tipo','metrica_valor')}
    return {k:row.get(k,'') for k in ('linha_negocio','natureza') if k in row}


def _totals(name,before,after):
    if name == TRACE:
        return []  # rastro repeats the other outputs: it is never an extra financial total.
    field = SCHEMAS[name][0]
    groups = {}
    for side,records in [('before',before),('after',after)]:
        for record in records.values():
            nature = dict(period=record['key']['period'],**_nature(name,record))
            group = groups.setdefault(_token(nature),dict(nature=nature,before=Decimal(0),after=Decimal(0),unknown_before=0,unknown_after=0))
            value = record['row'][field]
            if value == '':
                group['unknown_'+side] += 1
            else:
                group[side] += Decimal(value)
    result = []
    for _,g in sorted(groups.items()):
        result.append(dict(nature=g['nature'],before=format(g['before'],'.2f') if not g['unknown_before'] else None,
                           after=format(g['after'],'.2f') if not g['unknown_after'] else None,
                           monetary_delta=format(g['after']-g['before'],'.2f') if not g['unknown_before'] and not g['unknown_after'] else None,
                           unknown_before=g['unknown_before'],unknown_after=g['unknown_after']))
    return result


def compare_runs(before_dir: str, after_dir: str) -> dict:
    """Return semantic differences without changing either run or approving a rule.

    Raises ValueError on ambiguous identity, broken lineage or corrupt manifests.
    Read only the six CSVs and manifest.json, never paths embedded in a manifest.
    """
    before,after = _load(before_dir),_load(after_dir)
    changes = []
    for name in sorted(before['inputs'].keys()|after['inputs'].keys()):
        b,a = before['inputs'].get(name),after['inputs'].get(name)
        if b != a:
            changes.append(dict(name=name,kind='source',change='added' if name not in before['inputs'] else 'removed' if name not in after['inputs'] else 'changed',before=b,after=a))
    for field in ('version','policies','additional_files','dataset_kind'):
        b,a = before['manifest'].get(field),after['manifest'].get(field)
        if b != a:
            changes.append(dict(name=field,kind='manifest_metadata',change='changed',before=b,after=a))
    outputs = []
    for name in [*SCHEMAS,TRACE]:
        b,a = before['records'][name],after['records'][name]
        item = dict(name=name,added=[],removed=[],changed=[],unchanged_count=0)
        field = 'valor' if name == TRACE else SCHEMAS[name][0]
        for key in sorted(b.keys()|a.keys()):
            old,new = b.get(key),a.get(key)
            old_content,new_content = _snapshot(old),_snapshot(new)
            if old_content == new_content:
                item['unchanged_count'] += 1
                continue
            entry = dict(key=(old or new)['key'],before=old_content,after=new_content,
                         monetary_delta=_delta(old,new,field),
                         source_refs=sorted(set((old or {}).get('source_refs',[])+(new or {}).get('source_refs',[]))))
            item['added' if old is None else 'removed' if new is None else 'changed'].append(entry)
        item['totals_by_nature'] = _totals(name,b,a)
        outputs.append(item)
    limits = [
        'Comparação determinística de artefatos recebidos; não aprova regra, nota, pagamento ou fechamento.',
        'Valores separados por saída, competência e natureza. Comissão, nota e rastro se sobrepõem; não somar entre saídas.',
        'Hashes do manifest validam versão dos CSVs; não certificam correção semântica nem autenticidade de documento externo.',
        'Manifest v1 não contém hash de todo código/fonte de regras; alterações não registradas nesses metadados não são atestadas como mudanças de entrada.',
        'Campos desconhecidos continuam vazios/null; delta de valor não quantificado é null. Rastro não recebe total financeiro adicional.',
    ]
    if before['period'] != after['period']:
        limits.append('Competências distintas: registros são inclusões/remoções por período; isto não é resolução de obrigação intercompetência.')
    if any(side['manifest'].get('dataset_kind') == 'synthetic_test' for side in (before,after)):
        limits.append('Cenário sintético de teste: não representa ajuste tardio recebido, outubro real ou decisão aprovada do cliente.')
    if any(r.get('tipo')=='AJUSTES_TARDIOS_NAO_INCORPORADOS' for side in (before,after) for r in (x['row'] for x in side['records']['pendencias.csv'].values())):
        limits.append('Ao menos um snapshot histórico contém aviso de ajustes tardios sem fonte primária confirmada; isso não comprova requisito externo nem invalida o lote original.')
    if any(r.get('tipo')=='INPUT_ADICIONAL_NAO_HOMOLOGADO' for side in (before,after) for r in (x['row'] for x in side['records']['pendencias.csv'].values())):
        limits.append('Ao menos um run registra arquivo adicional observado não homologado; a comparação não interpreta seu conteúdo nem presume impacto financeiro.')
    if any(r.get('tipo')=='ENTRADA_ANUNCIADA_AUSENTE' for side in (before,after) for r in (x['row'] for x in side['records']['pendencias.csv'].values())):
        limits.append('Ao menos um run tem entrada anunciada ausente com fonte registrada; comparação do lote disponível não incorpora nem estima o conteúdo faltante.')
    return dict(status='completed',before_run_id=before['run_id'],after_run_id=after['run_id'],
                input_changes=changes,outputs=outputs,limitations=limits)
