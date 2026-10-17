"""Prepare immutable, cited financial actions from the six existing close CSVs.

No raw data recalc, model, outbound action or financial approval. The amounts
come exclusively from reconciled output rows and their trace components.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from .compare import _load, _token

CASE_SCHEMA = 'case-packet-v1'
SPECS = {
    'casa': dict(entity='00520815000100',name='Casa do Estudante',line='CHECKOUT',
        pending_type='DEVOLUCAO_CASA',pending_ref='1018325654',nature='DEVOLUCAO_CASA_SEM_COBRANCA_ORBE',
        amount_nature='devolucao_ao_lojista_por_isencao',action_type='prepare_merchant_refund',
        recipient='Casa do Estudante, por intermédio do comercial',owner='Helena + comercial',
        action='Preparar devolução ao lojista das diferenças líquidas durante a isenção de checkout; separar a devolução de qualquer cobrança ao parceiro.',
        closure=['Decisão documentada de Helena e comercial sobre a devolução e seu alcance.',
                 'Comprovante da devolução ao lojista, vinculado às operações e ao valor revisado.',
                 'Registro do ajuste na competência em que efetivamente ocorrer.']),
    'rota': dict(entity='95927868000148',name='Rota Global',line='CHECKOUT',
        pending_type='CONTESTACAO_ORBE',pending_ref='95927868000148',nature='TAXA_ORBE',
        amount_nature='diferenca_de_taxa_liquida_venda_estorno',action_type='prepare_orbe_dispute',
        recipient='Orbe Adquirência',owner='Helena',
        action='Preparar contestação da diferença líquida por taxa, incluindo as vendas e os abatimentos de estorno do mesmo caso. O cálculo é pelo contratado.',
        closure=['Revisão documentada de Helena com operações, taxas e valor líquido da contestação.',
                 'Registro do envio por Helena e resposta documentada da Orbe.',
                 'Comprovante e reconhecimento de eventual ajuste recebido; rascunho não encerra a pendência.']),
    'mundo': dict(entity='17217888000111',name='Mundo Aberto',line='REMESSA',
        pending_type='CONTESTACAO_PONTE',pending_ref='17217888000111',nature='SPREAD_LOJISTA_VALOR_INTEGRAL',
        amount_nature='excesso_integral_de_spread_pago_pelo_lojista',action_type='prepare_ponte_dispute',
        recipient='Ponte Câmbio',owner='Helena',
        action='Preparar contestação do excesso integral pago pelo lojista. Manter comissão e NF de setembro pelo realizado elegível; eventual ajuste só na competência em que ocorrer.',
        closure=['Revisão documentada de Helena sobre operações e excesso integral a contestar.',
                 'Registro do envio por Helena e resposta documentada da Ponte Câmbio.',
                 'Crédito/débito no relatório seguinte e conferência de Helena antes de reconhecer eventual ajuste.']),
    'atlas': dict(entity='1076801732',name='Atlas Idiomas',line='CHECKOUT',
        pending_type='CONTRATO_NAO_CONFIRMADO',pending_ref='1076801732',nature=None,
        amount_nature='comissao_nao_quantificada_sem_contrato',action_type='request_contract_confirmation',
        recipient='Comercial da Tarvo, com revisão de Helena',owner='Comercial + Helena',
        action='Manter faturamento destas linhas bloqueado e solicitar contrato/taxas confirmados desde 10/09. Preservar as origens para reprocessamento; não inferir taxa aplicada nem usar tabela antiga.',
        closure=['Contrato ou confirmação comercial documentada com taxas, modalidades e vigência desde 10/09.',
                 'Registro da regra por Helena, com fonte, autoridade e data.',
                 'Novo cálculo rastreável e revisão do faturamento de setembro junto com outubro; não emitir automaticamente.']),
}


def _one(records,label):
    if len(records) != 1:
        raise ValueError(f'{label}: expected one supported output, found {len(records)}')
    return records[0]


def _amount(value):
    return format(Decimal(value),'.2f')


def _row(record,filename,amount,nature):
    return dict(record['row'],id_saida=record['id'],output_file=filename,amount=amount,
                amount_nature=nature,trace_rows=record['traces'],source_refs=record['source_refs'])


def build_case_packet(output_dir,case_key):
    """Build Casa/Rota/Mundo/Atlas action packet from a trusted run directory.

    Raises ValueError if identity, destination, period, source hash, lineage or
    reconciliation cannot support the proposed action. Never modifies a run.
    """
    if case_key not in SPECS:
        raise ValueError('case_key must be casa|rota|mundo|atlas')
    run = _load(output_dir)
    spec = SPECS[case_key]
    if run['period'] != '2026-09':
        raise ValueError('These case actions are supported only for received September 2026 outputs; no automatic October rule')
    records = run['records']
    pending = _one([r for r in records['pendencias.csv'].values()
                    if r['row']['tipo']==spec['pending_type'] and r['row']['ref_origem']==spec['pending_ref']],
                   f'{case_key} pending anchor')
    if pending['row'].get('estado') != 'PENDENTE':
        raise ValueError('Case anchor is not pending; cannot claim an existing approval or resolution')
    if not pending['traces'] or not pending['row'].get('regra_fonte'):
        raise ValueError('Case needs existing traced source and rule reference')
    if any(not t.get('arquivo_origem') or not t.get('ref_origem') or not t.get('regra_fonte') for t in pending['traces']):
        raise ValueError('Case source locator or rule reference missing')
    related = dict(pending=[_row(pending,'pendencias.csv',_amount(pending['row']['valor_brl']),pending['row'].get('metrica_valor',''))],
                   commissions=[],invoices=[],other_pending=[])
    limitations = [
        'Ação documental preparada para revisão, sem envio, aprovação, emissão ou movimentação financeira.',
        'Valores extraídos das saídas e do rastro deste snapshot; não houve recálculo por modelo.',
        'Rascunho não resolve pendência nem comprova recuperação/devolução ou ganho econômico.',
        'Comissão, NF, divergência e pendência podem representar o mesmo dinheiro; não somar naturezas sobrepostas.',
        'Hashes identificam os seis CSVs; não certificam autenticidade externa de contrato ou aprovação.',
    ]
    evidence_refs = set(pending['source_refs'])
    rules = {pending['row']['regra_fonte']}
    for r in pending['traces']:
        if r.get('regra_fonte'):
            rules.add(r['regra_fonte'])
    if case_key == 'atlas':
        # No contract/CNPJ is invented. The pending output contains gross volume,
        # not a fee: keep that known metric separate from the unknown commission.
        forbidden = [r for r in records['rastro.csv'].values()
                     if r['row'].get('ref_origem') in {t['ref_origem'] for t in pending['traces']}
                     and r['key']['target']['output'] in {'comissoes_por_lojista.csv','notas_a_emitir.csv'}]
        if forbidden:
            raise ValueError('Atlas origin already appears in commission/invoice; current blocked-contract packet would be contradictory')
        amount = None
        rows = [dict(t,id_saida=pending['id'],output_file='pendencias.csv',amount=None,
                     observed_amount=_amount(t['valor']),value_nature='volume_bruto_pendente_nao_comissao',
                     source_refs=[f"{t['arquivo_origem']}#{t['ref_origem']}@L{t.get('linha_origem','')}"])
                for t in pending['traces']]
        volume = sum((Decimal(t['valor']) for t in pending['traces']),Decimal(0))
        reconciliation = dict(metric='volume_bruto_pendente_nao_comissao',component_sum=_amount(volume),
                              reported_amount=_amount(pending['row']['valor_brl']),matches=volume==Decimal(pending['row']['valor_brl']),
                              commission_amount=None,method='Soma do volume bruto assinado retido no rastro da pendência; não converte volume em comissão.')
        supporting_metrics = [dict(name='volume_bruto_retido',amount=_amount(volume),nature='volume_bruto_pendente_nao_comissao',
                                   output_ids=[pending['id']])]
        related['other_pending'] = [_row(r,'pendencias.csv',_amount(r['row']['valor_brl']),r['row'].get('metrica_valor',''))
            for r in records['pendencias.csv'].values() if r['row']['ref_origem']==spec['entity'] and r['id'] != pending['id']]
        limitations += ['Comissão Atlas desconhecida: amount=null. Volume bruto inclui eventos de naturezas distintas e não é receita nem taxa.',
                        'Linhas preservadas não demonstram resolução intercompetência; confirmação e faturamento futuro ainda exigem documentos/reexecução.']
    else:
        found = [r for r in records['divergencias_taxa.csv'].values()
                 if r['row']['cnpj']==spec['entity'] and r['row']['linha_negocio']==spec['line']]
        if not found or any(r['row']['natureza'] != spec['nature'] for r in found):
            raise ValueError('Case financial nature absent or contradictory')
        if any(not r['row'].get('regra_fonte') or any(not t.get('arquivo_origem') or not t.get('ref_origem') or not t.get('regra_fonte') for t in r['traces']) for r in found):
            raise ValueError('Case source locator or rule reference missing')
        if case_key == 'casa' and any(r['row'].get('contestar_parceiro') != 'NAO' for r in found):
            raise ValueError('Casa must not route a charge to Orbe')
        if case_key in {'rota','mundo'} and any(r['row'].get('contestar_parceiro') != 'REVISAO_HELENA' for r in found):
            raise ValueError('Partner dispute must remain under Helena review')
        components = sum((Decimal(r['row']['diferenca_brl']) for r in found),Decimal(0))
        if components != Decimal(pending['row']['valor_brl']):
            raise ValueError('Case detail sum does not match pending anchor')
        # Compare the source-level allocation, not just the total: same sum with
        # a source added/removed is insufficient evidence for this action.
        def allocation(traces):
            result={}
            for trace in traces:
                key=_token({k:trace.get(k,'') for k in ('arquivo_origem','ref_origem','linha_origem')})
                result[key]=result.get(key,Decimal(0))+Decimal(trace['valor'])
            return result
        if allocation([t for r in found for t in r['traces']]) != allocation(pending['traces']):
            raise ValueError('Case origin allocation differs from pending anchor')
        amount = _amount(components)
        rows = [_row(r,'divergencias_taxa.csv',_amount(r['row']['diferenca_brl']),spec['amount_nature']) for r in found]
        rows.sort(key=lambda r:(r['arquivo_origem'],r['ref_origem'],r.get('linha_origem','')))
        for r in found:
            evidence_refs.update(r['source_refs']); rules.add(r['row']['regra_fonte'])
        reconciliation = dict(metric=spec['amount_nature'],component_sum=amount,reported_amount=_amount(pending['row']['valor_brl']),
                              matches=True,method='Soma assinada das divergências por origem, reconciliada com pendência e rastro; sem somar duas representações.')
        supporting_metrics = []
        related['commissions'] = [_row(r,'comissoes_por_lojista.csv',_amount(r['row']['comissao_brl']),'comissao_contratada' if spec['line']=='CHECKOUT' else 'participacao_sobre_realizado_elegivel')
            for r in records['comissoes_por_lojista.csv'].values() if r['row']['cnpj']==spec['entity'] and r['row']['linha_negocio']==spec['line']]
        if case_key == 'mundo':
            _one(related['commissions'],'Mundo realized commission')
            related['invoices'] = [_row(r,'notas_a_emitir.csv',_amount(r['row']['valor_brl']),'NF_total_Ponte_nao_somente_Mundo')
                for r in records['notas_a_emitir.csv'].values() if r['row']['linha_negocio']=='REMESSA']
            _one(related['invoices'],'Ponte remittance invoice')
            limitations.append('Contestação Mundo usa excesso integral, não 50%. Comissão realizada e NF única Ponte são contexto separado e permanecem intactas.')
        if case_key == 'casa':
            limitations.append('Isenção vale para eventos dentro do alcance temporal; estorno de venda de agosto não é automaticamente isento. Este pacote não cobra Orbe.')
        if case_key == 'rota':
            limitations.append('Valor da ação é líquido de componentes positivos e negativos; a lista preserva estornos em vez de somar apenas cobranças positivas.')
    snapshot = {x['file']:x['sha256'] for x in run['manifest']['outputs'] if x['file'] in records}
    if len(snapshot) != 6:
        raise ValueError('A case snapshot requires the six canonical CSVs')
    # Recheck bytes after the read to detect concurrent replacement, not just
    # yesterday's manifest. This remains a check, not a filesystem transaction.
    for filename,digest in snapshot.items():
        if hashlib.sha256((run['root']/filename).read_bytes()).hexdigest() != digest:
            raise ValueError('Case source changed during preparation; retry on a stable snapshot')
    snapshot_id = 'snapshot-'+hashlib.sha256(_token(snapshot).encode()).hexdigest()[:20]
    identity = _token(dict(schema=CASE_SCHEMA,case_key=case_key,period=run['period'],snapshot=snapshot))
    if any(r['row'].get('tipo')=='AJUSTES_TARDIOS_NAO_INCORPORADOS' for r in records['pendencias.csv'].values()):
        limitations.append('Baseline contém ajustes tardios não incorporados; pacote não completa a entrada ausente.')
    return dict(schema_version=CASE_SCHEMA,case_id='case-'+hashlib.sha256(identity.encode()).hexdigest()[:20],
                case_key=case_key,run_id=run['run_id'],period=run['period'],snapshot=snapshot,snapshot_id=snapshot_id,
                entity=dict(identifier=spec['entity'],identifier_type='EC_ORBE' if case_key=='atlas' else 'CNPJ',name=spec['name']),
                line_of_business=spec['line'],source_refs=sorted(evidence_refs),rule_refs=sorted(rules),rows=rows,
                output_ids=sorted({pending['id'],*[r['id_saida'] for r in rows]}),amount=amount,amount_nature=spec['amount_nature'],
                amount_reconciliation=reconciliation,supporting_metrics=supporting_metrics,related_outputs=related,
                action_type=spec['action_type'],recipient=spec['recipient'],owner=spec['owner'],
                action_prepared=spec['action'],closure_evidence=list(spec['closure']),status='prepared_for_review',
                sent=False,approved=False,model_used=False,limitations=limitations)
