"""Regression and financial invariants. Independent full-case audit belongs to QA."""
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from tarvo.finance import run_close
from tarvo.finance.engine import Close, classify_bank, expected_checkout
from tarvo.finance.ingest import D, cnpj, money


def fixture(kind='VENDA',dt='2026-09-20',gross='100.00',ec='1',**extra):
    return dict(tipo_lancamento=kind,original_date='',date=dt,cod_estabelecimento=ec,
                id_referencia='',id_transacao='TX1',gross=D(gross),applied=D('.03'),
                modalidade='CREDITO A VISTA',qtd_parcelas='1',source='synthetic.csv',source_line=2,**extra)


def contract(**extra):
    base = dict(ec='1',cnpj='12345678000199',name='Fictício',start='2026-01-01',end='9999-12-31',
                inactive=False,rule_ref='synthetic.xlsx!A6',credit=D('.03'),anticipation=D('.02'),
                debit=D('.01'),pix=D('.005'),installment_2_6=D('.04'),installment_7_12=D('.05'))
    base.update(extra)
    return base


class FinancialRules(unittest.TestCase):
    def test_signed_half_cent(self):
        self.assertEqual(money('.005'),D('.01'))
        self.assertEqual(money('-.005'),D('-.01'))

    def test_cnpj_keeps_leading_zeros(self):
        self.assertEqual(cnpj(3229837000103),'03229837000103')
        self.assertEqual(cnpj('00.520.815/0001-00'),'00520815000100')

    def test_bridge_boundary_and_refund_original_date(self):
        old = contract(end='2026-09-14',credit=D('.0259'))
        new = contract(start='2026-09-15',credit=D('.0219'))
        row = fixture(dt='2026-09-14')
        self.assertEqual(expected_checkout(row,[old,new],{})[0],D('.0259'))
        row['date']='2026-09-15'
        self.assertEqual(expected_checkout(row,[old,new],{})[0],D('.0219'))
        row.update(tipo_lancamento='ESTORNO',original_date='2026-09-14',gross=D('-100'))
        self.assertEqual(expected_checkout(row,[old,new],{})[0],D('.0259'))

    def test_casa_august_refund_not_exempt(self):
        cas = contract(cnpj='00520815000100')
        row = fixture()
        self.assertEqual(expected_checkout(row,[cas],{})[0],D('0'))
        row.update(tipo_lancamento='ESTORNO',original_date='2026-08-20',gross=D('-100'))
        self.assertEqual(expected_checkout(row,[cas],{})[0],D('.03'))

    def test_reversal_requires_original_and_same_base(self):
        row = fixture(kind='REVERSAO ANTECIPACAO',gross='-100')
        row.update(original_date='2026-09-10',id_referencia='AN1')
        self.assertIsNone(expected_checkout(row,[contract()],{})[0])
        original = fixture(kind='ANTECIPACAO',dt='2026-09-10')
        self.assertEqual(expected_checkout(row,[contract()],{'AN1':original})[0],D('.02'))
        row['gross']=D('-99')
        self.assertIsNone(expected_checkout(row,[contract()],{'AN1':original})[0])

    def test_unknown_contract_never_uses_applied_rate(self):
        row=fixture(ec='unknown')
        self.assertIsNone(expected_checkout(row,[contract()],{})[0])

    def test_ponte_aerea_not_partner_commission(self):
        row=dict(bank='MERIDIANO',description='PIX RECEB PONTE AEREA ESTUDANTIL L',value=D('18240'))
        self.assertEqual(classify_bank(row)[0],'2.1.02.001')
        row['description']='TED RECEB PONTE CAMBIO SA REPASSE COMISSAO 08/2026'
        self.assertEqual(classify_bank(row)[0],'1.1.03.002')


class FullPackInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.out=Path(cls.tmp.name)
        cls.before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'contexto/data_pack').iterdir() if p.is_file()}
        cls.result=run_close(str(ROOT/'contexto/data_pack'),str(cls.out))
        cls.tables={p.name:list(csv.DictReader(p.read_text(encoding='utf-8').splitlines(),delimiter=';')) for p in cls.out.glob('*.csv')}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_amount_has_reconciling_trace(self):
        totals={}
        for row in self.tables['rastro.csv']:
            totals[row['id_saida']]=totals.get(row['id_saida'],D(0))+D(row['valor'])
            self.assertTrue(row['ref_origem'])
        for filename,field in [('comissoes_por_lojista.csv','comissao_brl'),('divergencias_taxa.csv','diferenca_brl'),
                               ('notas_a_emitir.csv','valor_brl'),('lancamentos_classificados.csv','valor'),('pendencias.csv','valor_brl')]:
            for row in self.tables[filename]:
                if row[field]:
                    self.assertEqual(D(row[field]),totals[row['id_saida']],row['id_saida'])

    def test_all_bank_movements_unique_and_classified(self):
        rows=self.tables['lancamentos_classificados.csv']
        self.assertEqual(len(rows),184)
        self.assertEqual(len({(r['banco'],r['ref_origem']) for r in rows}),184)
        self.assertTrue(all(r['conta_codigo'] for r in rows))
        self.assertEqual(sum(r['banco']=='AURORA' for r in rows),84)

    def test_no_casa_invoice_and_unknown_atlas_no_invoice(self):
        notes=self.tables['notas_a_emitir.csv']
        self.assertFalse(any(r['linha_negocio']=='CHECKOUT' and r['tomador_cnpj']=='00520815000100' for r in notes))
        self.assertTrue(all(D(r['valor_brl'])>0 for r in notes))
        self.assertEqual(sum(r['linha_negocio']=='REMESSA' for r in notes),1)
        self.assertTrue(any(r['tipo']=='CONTRATO_NAO_CONFIRMADO' and r['ref_origem']=='1076801732' for r in self.tables['pendencias.csv']))

    def test_casa_never_contested_with_orbe(self):
        casa=[r for r in self.tables['divergencias_taxa.csv'] if r['cnpj']=='00520815000100']
        self.assertTrue(casa)
        self.assertTrue(all(r['contestar_parceiro']=='NAO' for r in casa))

    def test_remessa_dedup_negative_exclusion_and_source_integrity(self):
        details=json.loads((self.out/'detalhes.json').read_text(encoding='utf-8'))
        self.assertEqual(sum(r['state']=='duplicata_excluida' for r in details['remessa']),1)
        self.assertEqual(sum(r['state']=='negativo_excluido' for r in details['remessa']),4)
        self.assertEqual(self.before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'contexto/data_pack').iterdir() if p.is_file()})

    def test_rerun_does_not_duplicate_rows_or_change_ids(self):
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.out.glob('*.csv')}
        second=run_close(str(ROOT/'contexto/data_pack'),str(self.out))
        self.assertEqual(self.result['run_id'],second['run_id'])
        self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.out.glob('*.csv')})

    def test_missing_period_is_not_fabricated(self):
        with self.assertRaisesRegex(ValueError,'No source records'):
            run_close(str(ROOT/'contexto/data_pack'),str(self.out),'2026-10')


if __name__=='__main__':
    unittest.main(verbosity=2)
