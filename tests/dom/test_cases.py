"""Open DOM regressions; no reading of reserved QA case fixtures."""
import csv
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from tarvo.finance.cases import build_case_packet


def digest(folder):
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*.csv')}


def table(folder,name):
    with (folder/name).open(encoding='utf-8',newline='') as fh:
        return list(csv.DictReader(fh,delimiter=';'))


def change_table(folder,name,mutate):
    rows=table(folder,name)
    fields=list(rows[0])
    mutate(rows)
    with (folder/name).open('w',encoding='utf-8',newline='') as fh:
        writer=csv.DictWriter(fh,fieldnames=fields,delimiter=';'); writer.writeheader(); writer.writerows(rows)
    path=folder/'manifest.json'
    manifest=json.loads(path.read_text(encoding='utf-8'))
    for item in manifest['outputs']:
        if item['file']==name:
            item['sha256']=hashlib.sha256((folder/name).read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')


class RealOutputCasePackets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=ROOT/'saida'
        cls.before=digest(cls.folder)
        cls.packets={key:build_case_packet(str(cls.folder),key) for key in ('casa','rota','mundo','atlas')}

    def test_values_reproduce_existing_outputs_and_origins(self):
        for key in ('casa','rota','mundo'):
            packet=self.packets[key]
            total=sum((Decimal(row['amount']) for row in packet['rows']),Decimal(0))
            self.assertEqual(Decimal(packet['amount']),total)
            self.assertTrue(packet['amount_reconciliation']['matches'])
            for row in packet['rows']:
                self.assertEqual(Decimal(row['amount']),sum((Decimal(t['valor']) for t in row['trace_rows']),Decimal(0)))
                self.assertTrue(row['source_refs'])
        # Direct output-row reference, not another invocation of financial calculation.
        for key,kind in [('casa','DEVOLUCAO_CASA'),('rota','CONTESTACAO_ORBE'),('mundo','CONTESTACAO_PONTE')]:
            packet=self.packets[key]
            anchor=next(r for r in table(self.folder,'pendencias.csv') if r['tipo']==kind and r['id_saida'] in packet['output_ids'])
            self.assertEqual(Decimal(packet['amount']),Decimal(anchor['valor_brl']))

    def test_casa_merchant_refund_is_never_orbe_charge(self):
        p=self.packets['casa']
        self.assertEqual(p['action_type'],'prepare_merchant_refund')
        self.assertNotIn('Orbe',p['recipient'])
        self.assertIn('comercial',p['owner'])
        self.assertTrue(all(r['contestar_parceiro']=='NAO' for r in p['rows']))

    def test_rota_preserves_signed_components(self):
        p=self.packets['rota']
        self.assertEqual(p['recipient'],'Orbe Adquirência')
        self.assertTrue(any(Decimal(r['amount'])<0 for r in p['rows']))
        self.assertLess(Decimal(p['amount']),sum((Decimal(r['amount']) for r in p['rows'] if Decimal(r['amount'])>0),Decimal(0)))

    def test_mundo_full_excess_and_commission_remain_separate(self):
        p=self.packets['mundo']
        self.assertEqual(p['recipient'],'Ponte Câmbio')
        self.assertEqual(p['amount_nature'],'excesso_integral_de_spread_pago_pelo_lojista')
        self.assertEqual(p['amount'],p['amount_reconciliation']['component_sum'])
        self.assertEqual(len(p['related_outputs']['commissions']),1)
        self.assertEqual(len(p['related_outputs']['invoices']),1)
        original=next(r for r in table(self.folder,'comissoes_por_lojista.csv') if r['cnpj']==p['entity']['identifier'] and r['linha_negocio']=='REMESSA')
        self.assertEqual(Decimal(p['related_outputs']['commissions'][0]['amount']),Decimal(original['comissao_brl']))

    def test_atlas_amount_is_unknown_and_origins_are_conserved(self):
        p=self.packets['atlas']
        self.assertIsNone(p['amount'])
        self.assertEqual(p['entity']['identifier_type'],'EC_ORBE')
        self.assertTrue(all(r['amount'] is None for r in p['rows']))
        self.assertTrue(all(r['value_nature']=='volume_bruto_pendente_nao_comissao' for r in p['rows']))
        self.assertEqual(sum((Decimal(r['observed_amount']) for r in p['rows']),Decimal(0)),Decimal(p['supporting_metrics'][0]['amount']))
        self.assertFalse(p['related_outputs']['invoices'])
        self.assertFalse(p['related_outputs']['commissions'])

    def test_no_approval_send_model_or_mutation(self):
        for packet in self.packets.values():
            self.assertEqual(packet['status'],'prepared_for_review')
            self.assertFalse(packet['approved']); self.assertFalse(packet['sent']); self.assertFalse(packet['model_used'])
            self.assertEqual(packet['snapshot'],self.before)
            self.assertEqual(len(packet['snapshot']),6)
            self.assertTrue(packet['closure_evidence'])
        self.assertEqual(self.before,digest(self.folder))

    def test_stable_identity_and_no_shared_mutable_policy(self):
        first=build_case_packet(str(self.folder),'casa')
        first['closure_evidence'].append('MUTATION TEST')
        second=build_case_packet(str(self.folder),'casa')
        self.assertEqual(first['case_id'],second['case_id'])
        self.assertNotIn('MUTATION TEST',second['closure_evidence'])

    def test_unknown_case_rejected(self):
        with self.assertRaisesRegex(ValueError,'case_key'):
            build_case_packet(str(self.folder),'inventado')


class CaseFailureGates(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.folder=Path(self.tmp.name)/'run'
        shutil.copytree(ROOT/'saida',self.folder)

    def tearDown(self):
        self.tmp.cleanup()

    def test_stale_snapshot_rejected(self):
        path=self.folder/'divergencias_taxa.csv'
        path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            build_case_packet(str(self.folder),'casa')

    def test_missing_trace_rejected(self):
        def mutate(rows):
            rows[:]=[r for r in rows if r['id_saida']!='PEN-2026-09-368d9e37ed38d9']
        change_table(self.folder,'rastro.csv',mutate)
        with self.assertRaisesRegex(ValueError,'Unreconciled'):
            build_case_packet(str(self.folder),'casa')

    def test_approval_claim_fails_closed(self):
        def mutate(rows):
            for r in rows:
                if r['tipo']=='DEVOLUCAO_CASA': r['estado']='APROVADO'
        change_table(self.folder,'pendencias.csv',mutate)
        with self.assertRaisesRegex(ValueError,'not pending'):
            build_case_packet(str(self.folder),'casa')

    def test_wrong_casa_destination_fails_closed(self):
        def mutate(rows):
            for r in rows:
                if r['cnpj']=='00520815000100': r['contestar_parceiro']='REVISAO_HELENA'
        change_table(self.folder,'divergencias_taxa.csv',mutate)
        with self.assertRaisesRegex(ValueError,'must not route'):
            build_case_packet(str(self.folder),'casa')


if __name__=='__main__':
    unittest.main(verbosity=2)
