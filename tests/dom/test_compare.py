"""Known synthetic comparator cases, separate from independent QA fixtures."""
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from tarvo.finance.compare import compare_runs
from tarvo.finance.engine import FIELDS


def write_snapshot(folder,amount='10.00',run_id='synthetic-before',ref='SYN-TX-1',output_id='COM-SYN-1',
                   extra_commission=False,unknown=False,omit_commission=False,input_hash='a'*64):
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    tables={name:[] for name in FIELDS}
    if not omit_commission:
        tables['comissoes_por_lojista.csv'].append(dict(id_saida=output_id,cnpj='12345678000199',lojista='Empresa fictícia de teste',linha_negocio='CHECKOUT',comissao_brl=amount))
        tables['rastro.csv'].append(dict(id_saida=output_id,arquivo_origem='synthetic_01.csv',ref_origem=ref,
            valor=amount,linha_origem='2',campo_origem='base_sintetica',formula='valor conhecido de teste',regra_fonte='SYNTHETIC_TEST_ONLY'))
    if extra_commission:
        tables['comissoes_por_lojista.csv'].append(dict(id_saida='COM-SYN-2',cnpj='12345678000270',lojista='Outra empresa fictícia',linha_negocio='CHECKOUT',comissao_brl='3.00'))
        tables['rastro.csv'].append(dict(id_saida='COM-SYN-2',arquivo_origem='synthetic_01.csv',ref_origem='SYN-TX-2',
            valor='3.00',linha_origem='3',campo_origem='base_sintetica',formula='valor conhecido de teste',regra_fonte='SYNTHETIC_TEST_ONLY'))
    if unknown:
        tables['pendencias.csv'].append(dict(id_saida='PEN-SYN-1',tipo='TESTE_NAO_QUANTIFICADO',ref_origem='SYN-DOC-1',valor_brl='',
            motivo='Documento fictício sem quantificação',quem_decide='Responsável fictício',estado='PENDENTE',regra_fonte='SYNTHETIC_TEST_ONLY',metrica_valor='não quantificado'))
    for name,fields in FIELDS.items():
        with (folder/name).open('w',encoding='utf-8',newline='') as fh:
            writer=csv.DictWriter(fh,fieldnames=fields,delimiter=';')
            writer.writeheader(); writer.writerows(tables[name])
    manifest=dict(run_id=run_id,period='2026-09',version='synthetic-test-v1',dataset_kind='synthetic_test',
                  inputs=[dict(file='synthetic_01.csv',sha256=input_hash,path='ignored-local-source-location')],
                  outputs=[dict(file=name,sha256=hashlib.sha256((folder/name).read_bytes()).hexdigest()) for name in FIELDS])
    (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')


def rehash(folder):
    path=folder/'manifest.json'
    manifest=json.loads(path.read_text(encoding='utf-8'))
    manifest['outputs']=[dict(file=name,sha256=hashlib.sha256((folder/name).read_bytes()).hexdigest()) for name in FIELDS]
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')


def hashes(folder):
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}


class SemanticComparison(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.a=Path(self.tmp.name)/'before'; self.b=Path(self.tmp.name)/'after'

    def tearDown(self):
        self.tmp.cleanup()

    def compare(self):
        return compare_runs(str(self.a),str(self.b))

    def test_identical_replay_no_delta_and_read_only(self):
        write_snapshot(self.a); write_snapshot(self.b)
        before=(hashes(self.a),hashes(self.b))
        result=self.compare()
        self.assertTrue(all(not x['changed'] and not x['added'] and not x['removed'] for x in result['outputs']))
        self.assertFalse(result['input_changes'])
        self.assertEqual(before,(hashes(self.a),hashes(self.b)))

    def test_ids_are_not_business_identity(self):
        write_snapshot(self.a,output_id='sequence-1'); write_snapshot(self.b,output_id='sequence-999')
        result=self.compare()
        self.assertTrue(all(not x['changed'] and not x['added'] and not x['removed'] for x in result['outputs']))

    def test_known_money_delta_and_input_change(self):
        write_snapshot(self.a); write_snapshot(self.b,amount='12.25',run_id='synthetic-after',input_hash='b'*64)
        result=self.compare()
        commission=result['outputs'][0]
        self.assertEqual(len(commission['changed']),1)
        self.assertEqual(commission['changed'][0]['monetary_delta'],'2.25')
        self.assertEqual(commission['totals_by_nature'][0]['monetary_delta'],'2.25')
        self.assertEqual(result['input_changes'][0]['kind'],'source')
        self.assertTrue(any('sintético' in x for x in result['limitations']))

    def test_equal_total_different_origin_is_change(self):
        write_snapshot(self.a); write_snapshot(self.b,ref='SYN-TX-REPLACED')
        result=self.compare()
        commission=result['outputs'][0]
        self.assertEqual(len(commission['changed']),1)
        self.assertEqual(commission['changed'][0]['monetary_delta'],'0.00')
        trace=next(r for r in result['outputs'] if r['name']=='rastro.csv')
        self.assertEqual(len(trace['added']),1); self.assertEqual(len(trace['removed']),1)
        self.assertEqual(trace['totals_by_nature'],[])

    def test_addition_and_removal_have_signed_delta(self):
        write_snapshot(self.a); write_snapshot(self.b,omit_commission=True,extra_commission=True)
        item=self.compare()['outputs'][0]
        self.assertEqual(item['added'][0]['monetary_delta'],'3.00')
        self.assertEqual(item['removed'][0]['monetary_delta'],'-10.00')

    def test_unknown_amount_does_not_become_zero(self):
        write_snapshot(self.a); write_snapshot(self.b,unknown=True)
        item=next(x for x in self.compare()['outputs'] if x['name']=='pendencias.csv')
        self.assertIsNone(item['added'][0]['monetary_delta'])
        self.assertIsNone(item['totals_by_nature'][0]['after'])

    def test_semantic_duplicate_rejected_even_new_id(self):
        write_snapshot(self.a); write_snapshot(self.b)
        path=self.b/'comissoes_por_lojista.csv'
        text=path.read_text(encoding='utf-8')
        path.write_text(text+text.splitlines()[1].replace('COM-SYN-1','COM-SYN-DUP')+'\n',encoding='utf-8')
        rehash(self.b)
        with self.assertRaisesRegex(ValueError,'Ambiguous semantic'):
            self.compare()

    def test_hash_mismatch_rejected(self):
        write_snapshot(self.a); write_snapshot(self.b)
        path=self.b/'rastro.csv'; path.write_text(path.read_text(encoding='utf-8')+'\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            self.compare()

    def test_orphan_trace_and_inconsistent_amount_rejected(self):
        write_snapshot(self.a); write_snapshot(self.b)
        path=self.b/'rastro.csv'
        text=path.read_text(encoding='utf-8')
        path.write_text(text.replace('COM-SYN-1','ORPHAN'),encoding='utf-8'); rehash(self.b)
        with self.assertRaisesRegex(ValueError,'Orphan trace'):
            self.compare()
        path.write_text(text.replace(';10.00;',';11.00;'),encoding='utf-8'); rehash(self.b)
        with self.assertRaisesRegex(ValueError,'Unreconciled trace'):
            self.compare()

    def test_actual_baseline_replay_is_zero(self):
        result=compare_runs(str(ROOT/'saida'),str(ROOT/'saida'))
        self.assertTrue(all(not x['changed'] and not x['added'] and not x['removed'] for x in result['outputs']))
        self.assertEqual(sum(x['unchanged_count'] for x in result['outputs']),5668)


if __name__=='__main__':
    unittest.main(verbosity=2)
