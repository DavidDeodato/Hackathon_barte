"""Independent acceptance checks against delivered CSVs. No production imports.

Run: python -m unittest discover -s tests -p 'test_*.py' -v
TARVO_OUTPUT_DIR may point to another generated output directory.
"""
import csv
import os
import re
import unittest
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('TARVO_OUTPUT_DIR', ROOT / 'saida'))
DATA = ROOT / 'contexto/data_pack'
SCHEMAS = {
    'comissoes_por_lojista': 'id_saida cnpj lojista linha_negocio comissao_brl',
    'divergencias_taxa': 'id_saida cnpj linha_negocio ref_origem taxa_contratada_pct taxa_aplicada_pct diferenca_brl',
    'notas_a_emitir': 'id_saida tomador_cnpj tomador linha_negocio valor_brl discriminacao',
    'lancamentos_classificados': 'id_saida banco ref_origem data descricao valor conta_codigo metodo confianca',
    'pendencias': 'id_saida tipo ref_origem valor_brl motivo quem_decide',
    'rastro': 'id_saida arquivo_origem ref_origem valor',
}

def read_output(name):
    path = OUT / (name + '.csv')
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, delimiter=';')
        fields = reader.fieldnames
        rows = list(reader)
    return fields, rows

def money(value):
    if not re.fullmatch(r'-?\d+(?:\.\d+)?', value or ''):
        raise AssertionError('Expected decimal point number: ' + repr(value))
    return Decimal(value)

def raw_banks():
    expected = {}
    path = DATA / '05a_extrato_banco_aurora_cc4471_set2026.csv'
    for number, row in enumerate(csv.reader(path.read_text(encoding='utf-8-sig').splitlines(), delimiter=';'), 1):
        if len(row) >= 4 and re.fullmatch(r'\d{2}/09/2026', row[0]) and row[3]:
            expected[('AURORA', f'L{number}')] = Decimal(row[3].replace('.', '').replace(',', '.'))
    text = (DATA / '05b_extrato_banco_meridiano_cc90233_set2026.ofx').read_text(encoding='cp1252')
    for block in re.findall(r'<STMTTRN>(.*?)</STMTTRN>', text, flags=re.S):
        ref = re.search(r'<FITID>([^<\r\n]+)', block)[1].strip()
        value = Decimal(re.search(r'<TRNAMT>([^<\r\n]+)', block)[1].strip())
        expected[('MERIDIANO', ref)] = value
    return expected

class ContractTests(unittest.TestCase):
    def test_required_files_and_columns(self):
        for name, required in SCHEMAS.items():
            with self.subTest(file=name):
                fields, rows = read_output(name)
                self.assertTrue(set(required.split()).issubset(fields), (name, fields))
                self.assertTrue(all(None not in row for row in rows), 'Malformed column count')

    def test_unique_output_ids_and_trace_sum(self):
        seen = set()
        _, trace = read_output('rastro')
        sums = defaultdict(Decimal)
        for line in trace:
            self.assertTrue(line['arquivo_origem'].strip())
            self.assertTrue(line['ref_origem'].strip())
            sums[line['id_saida']] += money(line['valor'])
        value_fields = {'comissoes_por_lojista': 'comissao_brl', 'divergencias_taxa': 'diferenca_brl',
                        'notas_a_emitir': 'valor_brl', 'lancamentos_classificados': 'valor', 'pendencias': 'valor_brl'}
        for name, field in value_fields.items():
            for line in read_output(name)[1]:
                key = line['id_saida']
                self.assertTrue(key and key not in seen, 'Duplicate/blank id_saida ' + key)
                seen.add(key)
                # A genuinely unknown pending amount may be empty; never assume zero.
                if name == 'pendencias' and not line[field]:
                    continue
                self.assertIn(key, sums, 'Missing trace ' + key)
                self.assertEqual(money(line[field]), sums[key], 'Trace mismatch ' + key)
        self.assertFalse(set(sums) - seen, 'Orphan trace IDs')

    def test_bank_coverage_and_values(self):
        expected = raw_banks()
        self.assertEqual(len(expected), 184)
        actual = {}
        accounts = {r['COD_CONTA'] for r in csv.DictReader((DATA / '04_plano_de_contas_fenix_erp.csv').open(encoding='cp1252'), delimiter=';') if r['ACEITA_LANCTO'] == 'S'}
        for line in read_output('lancamentos_classificados')[1]:
            key = (line['banco'], line['ref_origem'])
            self.assertNotIn(key, actual)
            actual[key] = money(line['valor'])
            self.assertIn(line['conta_codigo'], accounts)
            self.assertIn(line['metodo'], ['REGRA', 'IA', 'HUMANO'])
            self.assertTrue(Decimal(0) <= money(line['confianca']) <= Decimal(1))
            self.assertRegex(line['data'], r'^2026-09-\d{2}$')
        self.assertEqual(actual, expected)

    def test_cnpj_lines_and_invoice_semantics(self):
        for name, field in [('comissoes_por_lojista', 'cnpj'), ('divergencias_taxa', 'cnpj'), ('notas_a_emitir', 'tomador_cnpj')]:
            for row in read_output(name)[1]:
                self.assertRegex(row[field], r'^\d{14}$')
                self.assertIn(row['linha_negocio'], ['CHECKOUT', 'REMESSA'])
        notes = read_output('notas_a_emitir')[1]
        self.assertTrue(all(money(r['valor_brl']) > 0 for r in notes))
        self.assertEqual(sum(r['linha_negocio'] == 'REMESSA' for r in notes), 1)
        keys = [(r['tomador_cnpj'], r['linha_negocio']) for r in notes]
        self.assertEqual(len(keys), len(set(keys)))

if __name__ == '__main__':
    unittest.main()
