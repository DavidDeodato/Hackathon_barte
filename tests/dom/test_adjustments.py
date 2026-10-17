"""Synthetic 14-row adjustment scenarios, never reconstructed client transcript."""
import csv
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
import base64
from io import BytesIO
from email import policy
from email.parser import BytesParser
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from tarvo.finance import run_close
from tarvo.finance.ingest import ORBE_FIELDS


class AdjustmentInputs(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.inputs=self.root/'inputs'
        # Explicit six-source baseline for controlled scenarios, even after
        # the real07 delivery pack includes the received06 in its own folder.
        shutil.copytree(ROOT/'contexto/data_pack',self.inputs,ignore=lambda _,names:[n for n in names if n.startswith('06_')])
        self.orbe=self.inputs/'01_orbe_relatorio_comissoes_set2026.csv'
        self.base=list(csv.DictReader(self.orbe.read_text(encoding='utf-8-sig').splitlines(),delimiter=';'))
        self.reference=next(r for r in self.base if r['cod_estabelecimento']=='1074504011' and r['tipo_lancamento']=='VENDA'
                            and r['modalidade']=='CREDITO A VISTA' and int(r['data_movimento'][:2])<12)
        self.source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.inputs.iterdir() if p.is_file()}

    def tearDown(self):
        self.tmp.cleanup()

    def write_adjustments(self,count=14,conflict=False,corrupt=False):
        # One exact duplicate, one late refund of a linked sale, twelve new
        # known synthetic sales. None are copied from the client's partial06.
        duplicate=dict(self.base[0])
        if conflict: duplicate['valor_bruto']='999999,00'
        refund=dict(self.reference,id_transacao='SYN-LATE-REFUND',tipo_lancamento='ESTORNO',
                    data_movimento='30/09/2026',id_referencia=self.reference['id_transacao'],
                    data_venda_original=self.reference['data_movimento'])
        for f in ('valor_bruto','valor_taxa','valor_liquido'):
            refund[f]='-'+self.reference[f].lstrip('-')
        sales=[dict(self.reference,id_transacao=f'SYN-LATE-SALE-{i}',data_movimento='30/09/2026',
                    valor_bruto='100,00',taxa_aplicada_pct='2,49',valor_taxa='2,49',valor_liquido='97,51',
                    id_referencia='',data_venda_original='') for i in range(12)]
        rows=([duplicate,refund]+sales)[:count]
        if corrupt: rows[-1]['valor_bruto']='100\t00'
        path=self.inputs/'06_orbe_ajustes_tardios_set2026.csv'
        with path.open('w',encoding='utf-8',newline='') as fh:
            w=csv.DictWriter(fh,fieldnames=ORBE_FIELDS,delimiter=';');w.writeheader();w.writerows(rows)
        return path

    def test_fourteen_rows_linked_refund_exact_dedup_trace_and_replay(self):
        baseline=run_close(str(self.inputs),str(self.root/'before'))
        extra=self.write_adjustments()
        result=run_close(str(self.inputs),str(self.root/'after'))
        self.assertEqual(result['summary']['input_counts']['adjustment_rows'],14)
        self.assertEqual(result['summary']['input_counts']['orbe_duplicates'],1)
        self.assertFalse(any(r['tipo']=='ENTRADA_ANUNCIADA_AUSENTE' for r in result['issues']))
        self.assertEqual(result['summary']['late_adjustments'],'INCORPORADO')
        original_gross=Decimal(self.reference['valor_bruto'].replace(',','.'))
        expected=-((original_gross*Decimal('.0249')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))+Decimal('29.88')
        observed=Decimal(result['summary']['checkout_commission_brl'])-Decimal(baseline['summary']['checkout_commission_brl'])
        self.assertEqual(observed,expected)
        trace=list(csv.DictReader((self.root/'after/rastro.csv').read_text(encoding='utf-8').splitlines(),delimiter=';'))
        self.assertTrue(any(r['arquivo_origem']==extra.name and r['ref_origem']=='SYN-LATE-REFUND' and r['linha_origem']=='3' for r in trace))
        manifest=json.loads((self.root/'after/manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['processed_adjustment_files'],[extra.name])
        self.assertTrue(any(i['file']==extra.name and i['sha256']==hashlib.sha256(extra.read_bytes()).hexdigest() for i in manifest['inputs']))
        before_hash={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.root/'after').glob('*.csv')}
        second=run_close(str(self.inputs),str(self.root/'after'))
        self.assertEqual(result['run_id'],second['run_id'])
        self.assertEqual(before_hash,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.root/'after').glob('*.csv')})
        self.assertTrue(all(hashlib.sha256((self.inputs/name).read_bytes()).hexdigest()==v for name,v in self.source_hashes.items()))

    def test_partial_announced_file_rejected(self):
        self.write_adjustments(count=9)
        with self.assertRaisesRegex(ValueError,'exige 14 linhas'):
            run_close(str(self.inputs),str(self.root/'after'))

    def test_corrupt_transcript_rejected_without_reconstruction(self):
        self.write_adjustments(corrupt=True)
        with self.assertRaisesRegex(ValueError,'incompleta ou corrompida'):
            run_close(str(self.inputs),str(self.root/'after'))

    def test_conflicting_id_rejected_no_silent_replacement(self):
        self.write_adjustments(conflict=True)
        with self.assertRaisesRegex(ValueError,'Orbe conflitante'):
            run_close(str(self.inputs),str(self.root/'after'))

    def test_selected_safe_filenames_and_roles(self):
        roles={'orbe':'01_orbe_relatorio_comissoes_set2026.csv','contracts':'02_tabela_taxas_contratadas.xlsx',
               'remessa':'03_email_ponte_cambio_relatorio_set2026.eml','accounts':'04_plano_de_contas_fenix_erp.csv',
               'aurora':'05a_extrato_banco_aurora_cc4471_set2026.csv','meridiano':'05b_extrato_banco_meridiano_cc90233_set2026.ofx'}
        chosen={}
        for n,(role,name) in enumerate(roles.items()):
            new=f'selected-{n}'+Path(name).suffix; (self.inputs/name).rename(self.inputs/new);chosen[role]=new
        result=run_close(str(self.inputs),str(self.root/'selected'),input_files=chosen)
        self.assertEqual(result['summary']['selected_input_files'],chosen)
        changed=dict(chosen,orbe='../escape.csv')
        with self.assertRaisesRegex(ValueError,'sem caminhos externos'):
            run_close(str(self.inputs),str(self.root/'invalid'),input_files=changed)
        with self.assertRaisesRegex(ValueError,'seis tipos de documento'):
            run_close(str(self.inputs),str(self.root/'invalid'),input_files={'orbe':chosen['orbe']})

    def test_period_is_not_hardcoded_and_mixed_inputs_rejected(self):
        # Shift the isolated synthetic set's event dates only; no claim of
        # real October data or invoice resolution is made by this test.
        for path in [self.orbe,self.inputs/'05a_extrato_banco_aurora_cc4471_set2026.csv']:
            path.write_text(path.read_text(encoding='utf-8-sig').replace('/09/2026','/10/2026'),encoding='utf-8')
        ofx=self.inputs/'05b_extrato_banco_meridiano_cc90233_set2026.ofx'
        raw=ofx.read_bytes();ofx.write_bytes(raw.replace(b'202609',b'202610'))
        # Remittance file remains September, so a mixed selected set must fail.
        with self.assertRaisesRegex(ValueError,'Conjunto incompatível'):
            run_close(str(self.inputs),str(self.root/'mixed'),'2026-10')
        # Shift only XLSX date cells B/C inside a synthetic EML copy. No
        # authored customer workbook, no reconstruction of missing06 rows.
        eml=self.inputs/'03_email_ponte_cambio_relatorio_set2026.eml'
        msg=BytesParser(policy=policy.default).parsebytes(eml.read_bytes())
        part=next(msg.iter_attachments()); zipped=BytesIO()
        with ZipFile(BytesIO(part.get_payload(decode=True))) as src,ZipFile(zipped,'w') as dst:
            for name in src.namelist():
                data=src.read(name)
                if name=='xl/worksheets/sheet1.xml':
                    root=ET.fromstring(data); ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    for cell in root.findall('.//s:c',ns):
                        ref=cell.attrib.get('r','')
                        if ref.startswith(('B','C')) and ref[1:].isdigit() and int(ref[1:])>5:
                            value=cell.find('s:v',ns)
                            if value is not None and value.text and value.text.isdigit():
                                value.text=str(int(value.text)+30)
                    data=ET.tostring(root,encoding='utf-8',xml_declaration=True)
                dst.writestr(name,data)
        part.set_payload(base64.encodebytes(zipped.getvalue()).decode('ascii'))
        eml.write_bytes(msg.as_bytes())
        october=run_close(str(self.inputs),str(self.root/'synthetic-october'),'2026-10')
        self.assertEqual(october['period'],'2026-10')
        self.assertEqual(october['summary']['late_adjustments'],'NAO_ANUNCIADO_PARA_COMPETENCIA')
        self.assertFalse(any(x['tipo']=='ENTRADA_ANUNCIADA_AUSENTE' for x in october['issues']))


if __name__=='__main__':
    unittest.main(verbosity=2)
