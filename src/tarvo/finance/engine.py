"""Cited, deterministic month-close preparation from original client exports.

Money uses ROUND_HALF_UP per event. No commercial rule is inferred by a model,
no invoice is issued and no pending decision is silently approved.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .ingest import (D, ZERO, cnpj, find_file, money, norm, read_banks,
                     read_contracts, read_orbe, read_remittances, read_text, merge_orbe)

RULES = 'contexto/RESPOSTAS_FINANCEIRO.md'
VERSION = 'dom-v1.2'
FIELDS = {
    'comissoes_por_lojista.csv': ['id_saida', 'cnpj', 'lojista', 'linha_negocio', 'comissao_brl'],
    'divergencias_taxa.csv': ['id_saida', 'cnpj', 'linha_negocio', 'ref_origem', 'taxa_contratada_pct', 'taxa_aplicada_pct', 'diferenca_brl', 'natureza', 'quem_decide', 'contestar_parceiro', 'regra_fonte', 'arquivo_origem', 'linha_origem'],
    'notas_a_emitir.csv': ['id_saida', 'tomador_cnpj', 'tomador', 'linha_negocio', 'valor_brl', 'discriminacao', 'estado'],
    'lancamentos_classificados.csv': ['id_saida', 'banco', 'ref_origem', 'data', 'descricao', 'valor', 'conta_codigo', 'metodo', 'confianca', 'regra_fonte', 'natureza_contrapartida'],
    'pendencias.csv': ['id_saida', 'tipo', 'ref_origem', 'valor_brl', 'motivo', 'quem_decide', 'estado', 'regra_fonte', 'metrica_valor'],
    'rastro.csv': ['id_saida', 'arquivo_origem', 'ref_origem', 'valor', 'linha_origem', 'campo_origem', 'formula', 'regra_fonte'],
}


def serialize(obj):
    if isinstance(obj, D):
        return format(obj, 'f')
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(type(obj).__name__)


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=serialize), encoding='utf-8')


def contract_for(contracts, key, value, date):
    matches = [r for r in contracts if r[key] == value and r['start'] <= date <= r['end'] and not r['inactive']]
    if len(matches) > 1:
        raise ValueError(f'Ambiguous contract {key}={value} at {date}')
    return matches[0] if matches else None


def expected_checkout(row, contracts, by_ref):
    kind = row['tipo_lancamento']
    if kind not in {'VENDA', 'ESTORNO', 'ANTECIPACAO', 'REVERSAO ANTECIPACAO'}:
        return None, None, 'tipo desconhecido'
    date = row['original_date'] or row['date']
    if kind in {'ESTORNO', 'REVERSAO ANTECIPACAO'} and not row['original_date']:
        return None, None, 'evento de reversão sem data original'
    original = by_ref.get(row['id_referencia'])
    if kind == 'REVERSAO ANTECIPACAO':
        if not original or original['tipo_lancamento'] != 'ANTECIPACAO' or original['cod_estabelecimento'] != row['cod_estabelecimento']:
            return None, None, 'reversão sem antecipação original válida'
        if row['gross'] != -original['gross']:
            return None, None, 'reversão parcial/diferente requer regra humana'
        date = original['date']
    if kind == 'ESTORNO' and original:
        if original['tipo_lancamento'] != 'VENDA' or original['cod_estabelecimento'] != row['cod_estabelecimento']:
            return None, None, 'vínculo de estorno incompatível'
        if original['date'] != date:
            return None, None, 'data original contradiz venda referenciada'
    contract = contract_for(contracts, 'ec', row['cod_estabelecimento'], date)
    if not contract:
        return None, None, 'contrato vigente não confirmado'
    ref = f"{contract['rule_ref']};{RULES}#REG-C01/REG-C02/REG-C04"
    if contract['cnpj'] == '00520815000100' and '2026-09-01' <= date <= '2026-12-31':
        return ZERO, contract, f'{RULES}#CAN-07/CAN-17/REG-C02'
    if 'ANTECIPACAO' in kind:
        field = 'anticipation'
        ref += f';{RULES}#REG-C03'
    elif row['modalidade'] == 'DEBITO':
        field = 'debit'
    elif row['modalidade'] == 'PIX':
        field = 'pix'
    elif row['modalidade'] == 'CREDITO A VISTA':
        field = 'credit'
    elif row['modalidade'] == 'CREDITO PARCELADO':
        count = int(row['qtd_parcelas'] or 0)
        if not 2 <= count <= 12:
            return None, contract, 'parcelamento sem regra'
        field = 'installment_2_6' if count <= 6 else 'installment_7_12'
    else:
        return None, contract, 'modalidade sem regra'
    return contract[field], contract, ref


def classify_bank(row):
    """Ordered exact semantic rules, never probabilistic identity matching."""
    desc = norm(row['description'])
    base = f'{RULES}#REG-B01'
    rules = [
        ('SEM IDENTIFICACAO', '1.1.09.002', 'REG-B05'),
        ('DEVOLUCAO PIX', '2.1.01.002', 'REG-B06'),
        ('ORBE ADQUIRENCIA', '1.1.03.001', 'REG-B09'),
        ('TRANSF ENTRE CONTAS', '1.1.09.001', 'REG-B07'),
        ('MESMA TITULARIDADE', '1.1.09.001', 'REG-B07'),
        ('REPASSE COMISSAO', '1.1.03.002', 'REG-B04'),
        ('LIQ OPERACOES', '2.1.02.001', 'REG-B01'),
        ('PAGTO SALARIOS', '2.1.04.001', 'REG-B02'),
        ('INSS', '2.1.04.002', 'REG-B02'),
        ('FGTS', '2.1.04.003', 'REG-B02'),
        ('IRRF', '2.1.03.004', 'REG-B02'),
        ('COFINS', '2.1.03.002', 'REG-B02'),
        ('PIS', '2.1.03.001', 'REG-B02'),
        ('ISS SAO PAULO', '2.1.03.003', 'REG-B02'),
        ('CONDOMINIO', '4.2.02', 'REG-B03'),
        ('AMAZON WEB', '4.2.03', 'REG-B03'),
        ('GOOGLE WORKSPACE', '4.2.04', 'REG-B03'),
        ('CONTABILIDADE', '4.2.06', 'REG-B03'),
        ('SEGURO EMPRESARIAL', '4.2.05', 'REG-B03'),
        ('APLICACAO AUTOMATICA', '1.1.02.001', 'REG-B03'),
        ('RESGATE AUTOMATICO', '1.1.02.001', 'REG-B03'),
        ('RENDIMENTO APLIC', '3.2.01', 'REG-B03'),
        ('IOF S/', '4.3.01', 'REG-B03'),
    ]
    for fragment, code, rule in rules:
        if fragment in desc:
            return code, '1.00', f'{base};{RULES}#{rule}'
    if desc.startswith(('TAR ', 'TARIFA ')):
        return '4.2.01', '1.00', f'{base};{RULES}#REG-B03'
    if row['bank'] == 'AURORA' and desc.startswith('PIX ENVIADO '):
        return '2.1.01.001', '0.95', f'{base};{RULES}#CAN-23'
    if row['bank'] == 'MERIDIANO' and desc.startswith('PIX RECEB '):
        return '2.1.02.001', '0.95', f'{base};{RULES}#REG-B08'
    return '', '0.00', f'{base};classificação pendente'


class Close:
    def __init__(self, period):
        self.period = period
        self.tables = {name: [] for name in FIELDS}
        self.details = {'checkout': [], 'remessa': [], 'bancos': []}
        self.issues = []

    def identifier(self, prefix, key):
        return f"{prefix}-{self.period}-{hashlib.sha256(str(key).encode()).hexdigest()[:14]}"

    def trace(self, output_id, row, value, field, formula, rule):
        self.tables['rastro.csv'].append(dict(id_saida=output_id, arquivo_origem=row['source'],
            ref_origem=row.get('ref', row.get('id_transacao', '')), valor=money(value),
            linha_origem=row.get('source_line', ''), campo_origem=field,
            formula=formula, regra_fonte=rule))

    def pending(self, kind, key, reason, owner, components=None, rule='', metric='não quantificado'):
        ident = self.identifier('PEN', (kind, key))
        components = components or []
        value = sum((value for _, value in components), ZERO) if components else ''
        rec = dict(id_saida=ident, tipo=kind, ref_origem=key, valor_brl=value,
                   motivo=reason, quem_decide=owner, estado='PENDENTE', regra_fonte=rule,
                   metrica_valor=metric)
        self.tables['pendencias.csv'].append(rec)
        self.issues.append(rec)
        for row, amount in components:
            self.trace(ident, row, amount, metric, 'soma dos componentes; não implica aprovação', rule)

    def checkout(self, rows, contracts):
        by_ref = {r['id_transacao']: r for r in rows}
        if len(by_ref) != len(rows):
            raise ValueError('Duplicate Orbe transaction ID; no silent deduplication')
        groups = defaultdict(list)
        blocked = defaultdict(list)
        casa = []
        ordinary = defaultdict(list)
        for row in rows:
            if not row['date'].startswith(self.period):
                continue
            expected, contract, rule = expected_checkout(row, contracts, by_ref)
            detail = dict(row, expected_rate=expected, contract=contract, rule_ref=rule,
                          state='calculado' if expected is not None else 'pendente')
            if expected is None:
                blocked[row['cod_estabelecimento']].append(row)
                detail['commission'] = None
                self.details['checkout'].append(detail)
                continue
            amount = money(row['gross'] * expected)
            if row['tipo_lancamento'] == 'REVERSAO ANTECIPACAO':
                original = by_ref[row['id_referencia']]
                amount = -money(original['gross'] * expected)
            detail['commission'] = amount
            groups[contract['cnpj']].append((row, amount, contract, rule))
            delta = money(row['gross'] * (row['applied'] - expected))
            detail['difference'] = delta
            if row['applied'] != expected and delta:
                nature = 'DEVOLUCAO_CASA_SEM_COBRANCA_ORBE' if contract['cnpj'] == '00520815000100' and expected == 0 else 'TAXA_ORBE'
                ident = self.identifier('DIV', ('CHECKOUT', row['id_transacao']))
                self.tables['divergencias_taxa.csv'].append(dict(id_saida=ident, cnpj=contract['cnpj'],
                    linha_negocio='CHECKOUT', ref_origem=row['id_transacao'], taxa_contratada_pct=expected*100,
                    taxa_aplicada_pct=row['applied']*100, diferenca_brl=delta, natureza=nature,
                    quem_decide='Helena + comercial' if nature.startswith('DEVOLUCAO') else 'Helena',
                    contestar_parceiro='NAO' if nature.startswith('DEVOLUCAO') else 'REVISAO_HELENA',
                    regra_fonte=rule, arquivo_origem=row['source'], linha_origem=row['source_line']))
                self.trace(ident, row, delta, 'valor_bruto;taxa_aplicada_pct', 'bruto * (aplicada - contratada) / 100; ROUND_HALF_UP', rule)
                if nature.startswith('DEVOLUCAO'):
                    casa.append((row, delta))
                else:
                    ordinary[contract['cnpj']].append((row, delta))
            self.details['checkout'].append(detail)
        for taxid, lines in groups.items():
            amount = sum((x[1] for x in lines), ZERO)
            contract = lines[0][2]
            ident = self.identifier('COM', ('CHECKOUT', taxid))
            self.tables['comissoes_por_lojista.csv'].append(dict(id_saida=ident, cnpj=taxid,
                lojista=contract['name'], linha_negocio='CHECKOUT', comissao_brl=amount))
            for row, value, _, rule in lines:
                self.trace(ident, row, value, 'valor_bruto', 'bruto * taxa contratada; arredondamento por evento', rule)
            if amount > 0:
                nf = self.identifier('NF', ('CHECKOUT', taxid))
                self.tables['notas_a_emitir.csv'].append(dict(id_saida=nf, tomador_cnpj=taxid,
                    tomador=contract['name'], linha_negocio='CHECKOUT', valor_brl=amount,
                    discriminacao=f'Serviços de checkout e antecipação - competência {self.period}', estado='PREPARADA_NAO_EMITIDA'))
                for row, value, _, rule in lines:
                    self.trace(nf, row, value, 'valor_bruto', 'comissão contratada por evento', rule)
            elif amount < 0:
                self.pending('COMISSAO_NEGATIVA', taxid, 'Saldo negativo sem NF e sem carregamento automático.', 'Helena',
                    [(r,v) for r,v,_,_ in lines], f'{RULES}#REG-C06', 'comissão contratada')
        for ec, lines in blocked.items():
            self.pending('CONTRATO_NAO_CONFIRMADO', ec,
                'Linhas retidas sem faturar nem inventar taxa/CNPJ. Atlas: confirmar contrato desde 10/09 e faturar setembro junto com outubro.',
                'Comercial + Helena', [(r,r['gross']) for r in lines], f'{RULES}#CAN-04/CAN-19', 'volume bruto pendente; não é comissão')
            anticipations = [(r,r['gross']) for r in lines if r['tipo_lancamento'] == 'ANTECIPACAO']
            if anticipations:
                self.pending('ANTECIPACAO_SEM_LASTRO_CONFIRMADO', ec,
                    'Antecipações sem taxa/contrato confirmado; conferir vendido e lastro sem inventar limite de crédito.',
                    'Helena + comercial', anticipations, f'{RULES}#CAN-17', 'volume bruto antecipado; não é comissão')
        if casa:
            self.pending('DEVOLUCAO_CASA', '1018325654',
                'Cobrança durante isenção set-dez; devolver ao lojista após decisão Helena/comercial. Não cobrar Orbe. Estorno agosto não isento.',
                'Helena + comercial', casa, f'{RULES}#CAN-17/CAN-24', 'diferença de taxa líquida')
        for taxid, lines in ordinary.items():
            net = sum((v for _,v in lines), ZERO)
            if net:
                self.pending('CONTESTACAO_ORBE', taxid, 'Conferir diferenças líquidas por taxa; venda e estorno compensam. Rascunho não enviado.',
                    'Helena', lines, f'{RULES}#REG-C05', 'diferença de taxa líquida')

    def remittances(self, rows, contracts, partner_cnpj):
        grouped = defaultdict(list)
        seen = {}
        divergences = defaultdict(list)
        for row in rows:
            if not row['date'].startswith(self.period):
                continue
            if row['ref'] in seen:
                previous = seen[row['ref']]
                ignored = {'source_line','note'}
                same = {k:v for k,v in row.items() if k not in ignored} == {k:v for k,v in previous.items() if k not in ignored}
                if not same:
                    raise ValueError(f"Conflicting Ponte duplicate {row['ref']}; financial selection requires human rule")
                self.pending('DUPLICATA_PONTE', row['ref'],
                    f"Mesma operação/valores nas linhas {previous['source_line']} e {row['source_line']}; primeira contada uma vez. Corrigir relatório.",
                    'Helena / Ponte Câmbio', [(row,ZERO)], f'{RULES}#REG-R07', 'impacto adicional após deduplicação')
                self.details['remessa'].append(dict(row, state='duplicata_excluida', commission=ZERO))
                continue
            seen[row['ref']] = row
            contract = contract_for(contracts, 'cnpj', row['cnpj'], row['date'])
            if row['spread_brl'] < 0:
                self.pending('SPREAD_NEGATIVO_CONTESTAR', row['ref'],
                    'Spread negativo rejeitado; fora da comissão/NF, aguarda contestação. Valor é perda potencial da participação Tarvo, não excesso cobrado ao lojista.',
                    'Helena / Ponte Câmbio', [(row,money(row['spread_brl']/2))], f'{RULES}#REG-R06', 'metade do spread negativo excluído')
                self.details['remessa'].append(dict(row,state='negativo_excluido',commission=ZERO))
                continue
            amount = money(row['spread_brl'] / 2)
            rule = f'{RULES}#REG-R01/REG-R02/REG-R05'
            grouped[row['cnpj']].append((row,amount,rule))
            expected = contract['spread'] if contract else None
            self.details['remessa'].append(dict(row,state='calculado',commission=amount,
                                                expected_rate=expected, rule_ref=rule, contract=contract))
            if contract is None:
                self.pending('CADASTRO_REMESSA', row['ref'], 'Participação calculada sobre realizado; confirmar cadastro/contrato para aferir divergência.',
                    'Comercial', [(row,amount)], f'{RULES}#REG-R11', 'comissão calculada')
            # Method choice: ignore <= .01 percentage point to absorb rounded FX rate noise.
            # This is a documented team tolerance, not client approval.
            if expected is not None and abs(row['applied'] - expected) > D('.0001'):
                delta = money((row['applied'] - expected) * row['ptax'] * row['foreign'])
                ident = self.identifier('DIV', ('REMESSA', row['ref']))
                self.tables['divergencias_taxa.csv'].append(dict(id_saida=ident, cnpj=row['cnpj'],
                    linha_negocio='REMESSA', ref_origem=row['ref'], taxa_contratada_pct=expected*100,
                    taxa_aplicada_pct=row['applied']*100,diferenca_brl=delta,natureza='SPREAD_LOJISTA_VALOR_INTEGRAL',
                    quem_decide='Helena',contestar_parceiro='REVISAO_HELENA',regra_fonte=f'{RULES}#REG-R03/REG-R04',
                    arquivo_origem=row['source'],linha_origem=row['source_line']))
                self.trace(ident,row,delta,'Spread %;PTAX Ref.;Valor ME','(aplicado - contratado) * PTAX * Valor ME; integral; tolerância >0.01 p.p.',f'{RULES}#REG-R04')
                divergences[row['cnpj']].append((row,delta))
        all_lines = []
        for taxid, lines in grouped.items():
            all_lines += lines
            contract = contract_for(contracts,'cnpj',taxid,lines[0][0]['date'])
            ident = self.identifier('COM',('REMESSA',taxid))
            self.tables['comissoes_por_lojista.csv'].append(dict(id_saida=ident,cnpj=taxid,
                lojista=contract['name'] if contract else lines[0][0]['name'],linha_negocio='REMESSA',
                comissao_brl=sum((v for _,v,_ in lines),ZERO)))
            for row,value,rule in lines:
                self.trace(ident,row,value,'Spread R$','Spread R$ * 50%; ROUND_HALF_UP por operação',rule)
        total = sum((v for _,v,_ in all_lines),ZERO)
        if total > 0 and partner_cnpj:
            ident = self.identifier('NF',('REMESSA','PONTE'))
            self.tables['notas_a_emitir.csv'].append(dict(id_saida=ident,tomador_cnpj=partner_cnpj,
                tomador='Ponte Câmbio S.A.',linha_negocio='REMESSA',valor_brl=total,
                discriminacao=f'Intermediação de câmbio - competência {self.period}',estado='PREPARADA_NAO_EMITIDA'))
            for row,value,rule in all_lines:
                self.trace(ident,row,value,'Spread R$','participação Tarvo; não estimado D-1',rule)
        elif total > 0:
            self.pending('CNPJ_PONTE_AUSENTE','PONTE','NF bloqueada até identificação documental do tomador.','Helena')
        for taxid,lines in divergences.items():
            self.pending('CONTESTACAO_PONTE',taxid,'Contestar excesso integral ao lojista, mantendo participação realizada setembro. Ajuste só na competência futura em que ocorrer.',
                         'Helena / Ponte Câmbio',lines,f'{RULES}#REG-R04/REG-R05','excesso integral de spread')
        if all_lines:
            self.pending('CONFERIR_RECEBIMENTO_PONTE',f'{self.period}/PONTE',
                'Conferir TED no mês seguinte; pagamento ou desconto não conhecido. Comissão a receber não equivale a caixa.',
                'Helena',[(r,v) for r,v,_ in all_lines],f'{RULES}#REG-R10','comissão a receber')

    def banks(self, rows, accounts):
        analytic = {r['COD_CONTA']:r for r in accounts if r['ACEITA_LANCTO']=='S'}
        incoming_transfers = defaultdict(list)
        for row in rows:
            if row['date'].startswith(self.period) and 'MESMA TITULARIDADE' in norm(row['description']):
                incoming_transfers[row['value']].append(row)
        for row in rows:
            if not row['date'].startswith(self.period):
                continue
            code,confidence,rule = classify_bank(row)
            if code and code not in analytic:
                raise ValueError(f'Classification account not analytic/allowed: {code}')
            ident = self.identifier('BAN',(row['bank'],row['ref']))
            nature = ('C' if row['value'] > 0 else 'D') if code else ''
            self.tables['lancamentos_classificados.csv'].append(dict(id_saida=ident,banco=row['bank'],ref_origem=row['ref'],
                data=row['date'],descricao=row['description'],valor=row['value'],conta_codigo=code,metodo='REGRA',
                confianca=confidence,regra_fonte=rule,natureza_contrapartida=nature))
            self.trace(ident,row,row['value'],'valor','valor assinado do extrato; contrapartida bancária',rule)
            self.details['bancos'].append(dict(row,conta_codigo=code,rule_ref=rule))
            if not code:
                self.pending('CLASSIFICACAO_BANCARIA',row['ref'],'Sem regra suficiente; não inventar contrapartida.',
                    'Caio + Helena',[(row,row['value'])],rule,'valor do movimento')
            elif code == '1.1.09.002':
                self.pending('CREDITO_NAO_IDENTIFICADO',row['ref'],
                    'Origem desconhecida; não é receita. Crédito da conta transitória de ativo é provisório, pode gerar saldo credor e exige reclassificação após identificar obrigação/origem.',
                    'Helena',[(row,row['value'])],rule,'crédito bancário a identificar')
            elif code == '2.1.01.002':
                self.pending('DEVOLUCAO_REPASSE',row['ref'],'Repasse devolvido; obrigação ao lojista restabelecida. Investigar motivo e novo destino.',
                    'Helena',[(row,row['value'])],rule,'obrigação ao lojista restabelecida')
            elif code == '1.1.09.001' and row['value'] < 0:
                matches = incoming_transfers[-row['value']]
                match = next((r for r in matches if r['date'] >= row['date']),None)
                if match:
                    matches.remove(match)
                else:
                    self.pending('TRANSFERENCIA_EM_TRANSITO',row['ref'],
                        'Saída sem entrada no mês; manter trânsito e conferir crédito no próximo período, sem inventar movimento bancário.',
                        'Caio + Helena',[(row,-row['value'])],rule,'saldo de trânsito a conferir')
            if row['ref'] == 'MRD2026090425' and self.period == '2026-09':
                self.pending('ADIANTAMENTO_REMESSA_OUTUBRO',row['ref'],
                    'Ponte Aérea Estudantil é lojista, não Ponte Câmbio. Recurso destinado a operação de outubro; manter passivo, sem comissão setembro.',
                    'Caio + Helena',[(row,row['value'])],f'{RULES}#REG-B08','recurso de lojista para remessa futura')

    def reconcile(self):
        totals = defaultdict(lambda: ZERO)
        for row in self.tables['rastro.csv']:
            totals[row['id_saida']] += row['valor']
        checks = []
        for filename,field in [('comissoes_por_lojista.csv','comissao_brl'),('divergencias_taxa.csv','diferenca_brl'),
                               ('notas_a_emitir.csv','valor_brl'),('lancamentos_classificados.csv','valor'),('pendencias.csv','valor_brl')]:
            for row in self.tables[filename]:
                if row[field] == '':
                    continue
                ok = row['id_saida'] in totals and totals[row['id_saida']] == row[field]
                checks.append(dict(id_saida=row['id_saida'],expected=row[field],trace=totals[row['id_saida']],ok=ok))
        if not all(x['ok'] for x in checks):
            raise ValueError('Trace conservation failed')
        return checks


def run_close(input_dir: str, output_dir: str, period: str = '2026-09', *, input_files: dict | None = None) -> dict:
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',period):
        raise ValueError('Competência inválida: informe ano e mês no formato AAAA-MM.')
    src,out = Path(input_dir).resolve(),Path(output_dir).resolve()
    if src == out or src in out.parents:
        raise ValueError('Output directory must be outside original input directory')
    role_specs = [
        ('orbe','01_','.csv'),('contracts','02_','.xlsx'),('remessa','03_','.eml'),
        ('accounts','04_','.csv'),('aurora','05a_','.csv'),('meridiano','05b_','.ofx')]
    if input_files is not None:
        required={r for r,_,_ in role_specs}
        if not isinstance(input_files,dict) or not required.issubset(input_files) or set(input_files)-required-{'adjustments'}:
            raise ValueError('Conjunto incompleto ou inválido: selecione os seis tipos de documento e, quando disponível, o arquivo de ajustes.')
        paths={}
        for role,name in input_files.items():
            if not isinstance(name,str) or not name or Path(name).name != name or '/' in name or '\\' in name:
                raise ValueError('Nome de documento inválido: selecione somente arquivos do conjunto, sem caminhos externos.')
            try:
                p=(src/name).resolve(strict=True)
            except OSError:
                raise ValueError('Documento selecionado não está disponível no conjunto. Selecione ou envie novamente.') from None
            if p.parent != src or not p.is_file():
                raise ValueError('Documento selecionado precisa ser um arquivo disponível dentro do conjunto.')
            expected=next((s for r,_,s in role_specs if r==role),'.csv')
            if p.suffix.lower()!=expected:
                raise ValueError(f'Tipo de documento incompatível: {role} precisa de arquivo {expected}.')
            paths[role]=p
        if len(set(paths.values())) != len(paths):
            raise ValueError('Um mesmo documento não pode preencher dois tipos de entrada do conjunto.')
        paths={role:paths[role] for role in [*[r for r,_,_ in role_specs],'adjustments'] if role in paths}
    else:
        paths={key:find_file(src,prefix,suffix) for key,prefix,suffix in role_specs}
        adjustments=sorted(p for p in src.iterdir() if p.is_file() and p.name.startswith('06_') and p.suffix.lower()=='.csv')
        if len(adjustments)>1:
            raise ValueError('Multiple adjustment files: choose one explicitly through input_files')
        if adjustments:
            paths['adjustments']=adjustments[0]
    announcement_path=Path(__file__).parent/'data/announced_inputs.json'
    announcement_digest=hashlib.sha256(announcement_path.read_bytes()).hexdigest()
    announcements=[a for a in json.loads(announcement_path.read_text(encoding='utf-8'))['announcements'] if a['period']==period]
    inputs = [{'path':str(p),'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths.values()]
    base_rows=read_orbe(paths['orbe'])
    adjustment_rows=read_orbe(paths['adjustments']) if 'adjustments' in paths else []
    if any(not r['date'].startswith(period) for r in adjustment_rows):
        raise ValueError('O arquivo de ajustes contém movimento fora da competência selecionada.')
    for announcement in announcements:
        if 'adjustments' in paths and len(adjustment_rows)!=announcement['expected_rows']:
            raise ValueError(f'O ajuste anunciado de setembro exige {announcement["expected_rows"]} linhas. Envie o CSV original integral; arquivo parcial não foi processado.')
    rows,orbe_duplicates=merge_orbe(base_rows+adjustment_rows)
    contracts = read_contracts(paths['contracts'])
    remits,partner = read_remittances(paths['remessa'])
    banks = read_banks(paths['aurora'],paths['meridiano'])
    if not any(r['date'].startswith(period) for r in rows + remits + banks):
        raise ValueError(f'Sem registros para a competência {period}. Selecione os documentos desse mês; alterar o mês na tela não altera as datas dos arquivos.')
    missing_period=[role for role,events in [('checkout',rows),('remessa',remits),
        ('aurora',[r for r in banks if r['bank']=='AURORA']),('meridiano',[r for r in banks if r['bank']=='MERIDIANO'])]
        if not any(r['date'].startswith(period) for r in events)]
    if missing_period:
        labels={'checkout':'checkout','remessa':'remessas','aurora':'Banco Aurora','meridiano':'Banco Meridiano'}
        raise ValueError(f'Conjunto incompatível com a competência {period}: sem movimentos de '+', '.join(labels[r] for r in missing_period)+'. Selecione os arquivos correspondentes ao mês.')
    accounts = list(csv.DictReader(read_text(paths['accounts']).splitlines(),delimiter=';'))
    close = Close(period)
    close.checkout(rows,contracts)
    close.remittances(remits,contracts,partner)
    close.banks(banks,accounts)
    for original,duplicate in orbe_duplicates:
        close.pending('DUPLICATA_CHECKOUT',duplicate['id_transacao'],
            f'Payload idêntico já contado em {original["source"]} L{original["source_line"]}; preservar cópias sem duplicar comissão.',
            'Responsável pelos dados / Helena',[(duplicate,ZERO)],'identidade exata por id_transacao e 14 campos Orbe','impacto adicional após deduplicação')
        close.details['checkout'].append(dict(duplicate,state='duplicata_excluida',commission=ZERO,duplicate_of=dict(file=original['source'],line=original['source_line'])))
    missing_announcements=[]
    for announcement in announcements:
        if announcement['role'] not in paths:
            missing_announcements.append(announcement)
            close.pending('ENTRADA_ANUNCIADA_AUSENTE',announcement['expected_file'],
                f'Comunicado da organização anuncia {announcement["expected_rows"]} linhas no schema01 para esta competência e exige incorporação. Fornecer CSV original integral; não reconstruir transcrição parcial. As partes independentes do lote original foram calculadas.',
                'Responsável pelos documentos / Helena',rule=announcement['source_ref'],metric='entrada operacional anunciada; efeito financeiro não quantificado')
    # A possible external update is not a financial obligation. Only observed
    # extra input files are reported, without assuming their content/authority.
    extra_paths = sorted(p for p in src.iterdir() if p.is_file() and p not in paths.values()
                         and p.name != '00_LEIA-ME.md' and not p.name.startswith('.'))
    extras = [p.name for p in extra_paths]
    for extra in extra_paths:
        digest = hashlib.sha256(extra.read_bytes()).hexdigest()
        inputs.append(dict(path=str(extra),file=extra.name,sha256=digest))
        close.pending('INPUT_ADICIONAL_NAO_HOMOLOGADO',extra.name,
            'Arquivo adicional observado, ainda não processado. Conferir origem, competência, schema e natureza antes de incorporar; conteúdo e efeito financeiro não inferidos.',
            'Responsável pelos dados / Helena',rule=f'arquivo observado: {extra.name}; sha256={digest}')
    checks = close.reconcile()
    identity = json.dumps([VERSION,period,inputs,announcement_digest],sort_keys=True).encode()
    run_id = 'close-'+hashlib.sha256(identity).hexdigest()[:16]
    out.mkdir(parents=True,exist_ok=True)
    outputs = []
    for filename,fields in FIELDS.items():
        path = out/filename
        with path.open('w',encoding='utf-8',newline='') as fh:
            writer = csv.DictWriter(fh,fieldnames=fields,delimiter=';',extrasaction='ignore')
            writer.writeheader()
            for row in close.tables[filename]:
                writer.writerow({k:format(v,'f') if isinstance(v,D) else v for k,v in row.items()})
        outputs.append(str(path))
    commissions = close.tables['comissoes_por_lojista.csv']
    divergences = close.tables['divergencias_taxa.csv']
    summary = dict(checkout_commission_brl=sum((r['comissao_brl'] for r in commissions if r['linha_negocio']=='CHECKOUT'),ZERO),
        remessa_commission_brl=sum((r['comissao_brl'] for r in commissions if r['linha_negocio']=='REMESSA'),ZERO),
        invoices_brl=sum((r['valor_brl'] for r in close.tables['notas_a_emitir.csv']),ZERO),
        checkout_rate_difference_brl=sum((r['diferenca_brl'] for r in divergences if r['linha_negocio']=='CHECKOUT' and r['natureza']=='TAXA_ORBE'),ZERO),
        casa_refund_brl=sum((r['diferenca_brl'] for r in divergences if r['natureza']=='DEVOLUCAO_CASA_SEM_COBRANCA_ORBE'),ZERO),
        remessa_rate_difference_brl=sum((r['diferenca_brl'] for r in divergences if r['linha_negocio']=='REMESSA'),ZERO),
        counts={name:len(lines) for name,lines in close.tables.items()},
        input_counts=dict(orbe=len(rows),contracts=len(contracts),remessa_rows=len(remits),bank_movements=len(banks),
                          orbe_raw=len(base_rows)+len(adjustment_rows),adjustment_rows=len(adjustment_rows),orbe_duplicates=len(orbe_duplicates)),
        trace_checks=len(checks),trace_reconciled=True,financial_approval='PENDENTE_HELENA',
        late_adjustments='ENTRADA_ANUNCIADA_AUSENTE' if missing_announcements else 'INPUT_ADICIONAL_NAO_HOMOLOGADO' if extras else 'INCORPORADO' if adjustment_rows else 'NAO_ANUNCIADO_PARA_COMPETENCIA',
        operational_input_issues=len(missing_announcements)+len(extras),
        selected_input_files={role:p.name for role,p in paths.items()},
        mode='DETERMINISTICO',completeness='LOTE_ORIGINAL_PROCESSADO_ATUALIZACAO_PENDENTE' if missing_announcements else 'ENTRADAS_ADICIONAIS_NAO_PROCESSADAS' if extras else 'CONJUNTO_FORNECIDO_PROCESSADO')
    result = dict(run_id=run_id,period=period,status='pending_review',outputs=outputs,summary=summary,issues=close.issues)
    # All additional files are explicit, auditable source-level evidence; not a second calculation engine.
    dump(out/'detalhes.json',dict(run_id=run_id,period=period,contracts=contracts,**close.details))
    dump(out/'reconciliacao.json',checks)
    dump(out/'manifest.json',dict(version=VERSION,run_id=run_id,period=period,created_at=datetime.now(timezone.utc).isoformat(),
        inputs=inputs,additional_files=extras,processed_adjustment_files=[paths['adjustments'].name] if 'adjustments' in paths else [],
        announced_inputs=announcements,announcement_source_sha256=announcement_digest,
        outputs=[dict(file=Path(p).name,sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest()) for p in outputs],
        policies=dict(rounding='Decimal ROUND_HALF_UP por evento antes da soma',
                      remessa_tolerance='diferença absoluta de spread > 0.01 p.p.; escolha metodológica do time, não regra aprovada pelo cliente',
                      pending_values='valores de pendências têm métricas distintas e não devem ser somados',
                      bank_confidence='prioridade de regra declarada, não probabilidade estatisticamente calibrada',
                      unknown_amount='campo vazio significa não quantificado; nunca zero inventado'),
        result=result))
    # JSON-compatible return is a hard integration contract.
    return json.loads(json.dumps(result,default=serialize,ensure_ascii=False))
