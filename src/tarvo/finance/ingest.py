"""Read source exports without changing them. Decimal values retain source precision."""
from __future__ import annotations

import csv
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from email import policy
from email.parser import BytesParser
from io import BytesIO
from pathlib import Path

import openpyxl

D = Decimal
ZERO = D('0')
ORBE_FIELDS = ('id_transacao','data_movimento','cod_estabelecimento','nome_estabelecimento',
               'tipo_lancamento','modalidade','qtd_parcelas','bandeira','valor_bruto',
               'taxa_aplicada_pct','valor_taxa','valor_liquido','id_referencia','data_venda_original')


def money(value):
    return D(str(value)).quantize(D('.01'), rounding=ROUND_HALF_UP)


def dec(value, brazilian=False):
    if value is None or value == '':
        return ZERO
    text = str(value).strip().replace('%', '')
    if brazilian or ',' in text:
        text = text.replace('.', '').replace(',', '.')
    return D(text)


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or ''))
                   if not unicodedata.combining(c)).upper().strip()


def cnpj(value):
    text = re.sub(r'\D', '', str(value or ''))
    if not text:
        return ''
    if len(text) > 14:
        raise ValueError('CNPJ exceeds 14 digits')
    return text.zfill(14)


def iso(value):
    if isinstance(value, (datetime, date)):
        return value.strftime('%Y-%m-%d')
    return datetime.strptime(str(value), '%d/%m/%Y').strftime('%Y-%m-%d')


def read_text(path):
    raw = Path(path).read_bytes()
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return raw.decode('cp1252')


def find_file(folder, prefix, suffix):
    found = sorted(p for p in Path(folder).iterdir()
                   if p.name.startswith(prefix) and p.suffix.lower() == suffix)
    if len(found) != 1:
        raise ValueError(f'Expected exactly one {prefix}*{suffix}; found {len(found)}')
    return found[0]


def read_orbe(path):
    rows = []
    reader = csv.DictReader(read_text(path).splitlines(), delimiter=';')
    if len(reader.fieldnames or []) != len(ORBE_FIELDS) or set(reader.fieldnames or []) != set(ORBE_FIELDS):
        raise ValueError(f'{path.name}: formato Orbe incompatível. São necessárias as 14 colunas originais; envie o arquivo integral, não uma transcrição truncada.')
    for line, r in enumerate(reader, 2):
        if None in r or any(v is None or '\t' in v for v in r.values()):
            raise ValueError(f'{path.name} L{line}: linha incompleta ou corrompida. Envie o CSV original integral.')
        if not r['id_transacao'] or not re.fullmatch(r'\d+',r['cod_estabelecimento']):
            raise ValueError(f'{path.name} L{line}: falta identificador da transação ou do estabelecimento.')
        for field in ('valor_bruto','taxa_aplicada_pct','valor_taxa','valor_liquido'):
            if not re.fullmatch(r'[+-]?(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d+)?',r[field]):
                raise ValueError(f'{path.name} L{line}: valor decimal inválido no campo {field}. Preserve o formato do arquivo original.')
        rows.append(dict(r, source=path.name, source_line=line,
                         date=iso(r['data_movimento']),
                         original_date=iso(r['data_venda_original']) if r['data_venda_original'] else '',
                         gross=dec(r['valor_bruto'], True),
                         applied=dec(r['taxa_aplicada_pct'], True) / 100,
                         charged=dec(r['valor_taxa'], True)))
    return rows


def merge_orbe(rows):
    """Retain one exact payload per ID, preserve identical duplicates as evidence."""
    seen,unique,duplicates = {},[],[]
    for row in rows:
        key=row['id_transacao']
        if key not in seen:
            seen[key]=row; unique.append(row); continue
        original=seen[key]
        if any(row[f] != original[f] for f in ORBE_FIELDS):
            raise ValueError(f'Identificador Orbe conflitante {key}: {original["source"]} L{original["source_line"]} e {row["source"]} L{row["source_line"]}. Valores diferentes exigem conferência; nenhuma linha foi substituída.')
        duplicates.append((original,row))
    return unique,duplicates


def read_contracts(path):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    if 'Taxas vigentes' not in wb.sheetnames:
        raise ValueError('Missing current-rate sheet; historical sheet is forbidden')
    rows = []
    for line, values in enumerate(wb['Taxas vigentes'].values, 1):
        if line <= 5 or not values[1]:
            continue
        name, taxid, ec, *rest = values
        rates = []
        for val in values[3:10]:
            rates.append(None if val is None else
                         D('.015') if norm(val) == 'PADRAO' else
                         dec(val) / 100 if '%' in str(val) else dec(val))
        validity = str(values[10] or '')
        dates = re.findall(r'\d{2}/\d{2}/\d{4}', validity)
        start, end = '0001-01-01', '9999-12-31'
        if dates:
            if norm(validity).startswith('ATE'):
                end = iso(dates[0])
            else:
                start = iso(dates[0])
        rows.append(dict(name=name, cnpj=cnpj(taxid), ec=str(ec or ''),
                         debit=rates[0], credit=rates[1], installment_2_6=rates[2],
                         installment_7_12=rates[3], pix=rates[4], anticipation=rates[5],
                         spread=rates[6] if rates[6] is not None else D('.015'),
                         start=start, end=end, inactive='INATIVO' in norm(values[11]),
                         source=path.name, source_line=line,
                         rule_ref=f'{path.name}#Taxas vigentes!A{line}:L{line}'))
    wb.close()
    # Explicit client identity corrections CAN-04; never fuzzy match source names.
    for ec, taxid in {'1043300981': '66564512000199',
                      '1043396662': '78576234000179',
                      '1038867654': '07752116000126'}.items():
        for row in rows:
            if row['cnpj'] == taxid:
                row['ec'] = ec
                row['identity_ref'] = 'contexto/RESPOSTAS_FINANCEIRO.md#CAN-04'
    return rows


def read_remittances(path):
    msg = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    attachments = [p for p in msg.iter_attachments() if str(p.get_filename()).endswith('.xlsx')]
    if len(attachments) != 1:
        raise ValueError('Expected one XLSX attachment in Ponte EML')
    part = attachments[0]
    wb = openpyxl.load_workbook(BytesIO(part.get_payload(decode=True)), data_only=True, read_only=True)
    ws = wb['Operações']
    rows = []
    for line, vals in enumerate(ws.values, 1):
        if line <= 5 or not str(vals[0] or '').startswith('PC-'):
            continue
        rows.append(dict(ref=vals[0], date=iso(vals[1]), settlement_date=iso(vals[2]),
                         cnpj=cnpj(vals[3]), name=vals[4], currency=vals[5],
                         foreign=dec(vals[6]), client_rate=dec(vals[7]), ptax=dec(vals[8]),
                         brl=dec(vals[9]), spread_brl=dec(vals[10]), applied=dec(vals[11]),
                         estimated_spread=dec(vals[12]), iof=dec(vals[13]), compliance=vals[14],
                         note=vals[15], source=path.name, source_line=line,
                         attachment=part.get_filename(), sheet=ws.title))
    wb.close()
    text = '\n'.join(p.get_content() for p in msg.walk() if p.get_content_type() == 'text/plain')
    match = re.search(r'CNPJ\s+([\d./-]+)', text)
    return rows, cnpj(match[1]) if match else ''


def read_banks(aurora, meridiano):
    rows = []
    for line, vals in enumerate(csv.reader(read_text(aurora).splitlines(), delimiter=';'), 1):
        if line <= 8 or len(vals) < 5 or not re.fullmatch(r'\d{2}/\d{2}/\d{4}', vals[0]):
            continue
        if not vals[3]:
            continue
        rows.append(dict(bank='AURORA', ref=f'L{line}', source=aurora.name, source_line=line,
                         date=iso(vals[0]), description=vals[1], value=dec(vals[3], True),
                         balance=dec(vals[4], True)))
    for part in re.findall(r'<STMTTRN>(.*?)</STMTTRN>', read_text(meridiano), re.S | re.I):
        def tag(name):
            found = re.search(fr'<{name}>([^<\r\n]*)', part, re.I)
            if not found:
                raise ValueError(f'Missing OFX {name}')
            return found[1].strip()
        dt = tag('DTPOSTED')[:8]
        rows.append(dict(bank='MERIDIANO', ref=tag('FITID'), source=meridiano.name,
                         source_line='', date=f'{dt[:4]}-{dt[4:6]}-{dt[6:8]}',
                         description=tag('MEMO'), value=dec(tag('TRNAMT'))))
    return rows
