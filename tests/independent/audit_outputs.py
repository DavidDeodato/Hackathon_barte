"""Read-only independent audit of official CSVs. No production imports.

python tests/independent/audit_outputs.py --output-dir saida --report <json>
Exit 1 means critical failure; 2 means output not yet available.
"""
import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from reference import DATA, ROOT, build_reference, table

SCHEMAS = {
    "comissoes_por_lojista": "id_saida cnpj lojista linha_negocio comissao_brl",
    "divergencias_taxa": "id_saida cnpj linha_negocio ref_origem taxa_contratada_pct taxa_aplicada_pct diferenca_brl",
    "notas_a_emitir": "id_saida tomador_cnpj tomador linha_negocio valor_brl discriminacao",
    "lancamentos_classificados": "id_saida banco ref_origem data descricao valor conta_codigo metodo confianca",
    "pendencias": "id_saida tipo ref_origem valor_brl motivo quem_decide",
    "rastro": "id_saida arquivo_origem ref_origem valor",
}
VALUES = {"comissoes_por_lojista": "comissao_brl", "divergencias_taxa": "diferenca_brl",
          "notas_a_emitir": "valor_brl", "lancamentos_classificados": "valor", "pendencias": "valor_brl"}


def decimal(value):
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", value or ""):
        raise ValueError(f"Invalid decimal: {value!r}")
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError("Non-finite decimal")
    return result


def base_ref(ref):
    match = re.match(r"(PC-\d+-\d+|(?:TX|AN)\d+|MRD\d+|L\d+)", ref)
    return match[1] if match else ref


def audit_tables(tables, headers, reference):
    findings = []
    checks = 0

    def check(condition, code, detail, severity="error"):
        nonlocal checks
        checks += 1
        if not condition:
            findings.append({"severity": severity, "code": code, "detail": detail})

    for name, schema in SCHEMAS.items():
        check(name in tables, "missing_file", name)
        if name in tables:
            check(set(schema.split()) <= set(headers[name]), "schema", name)
            check(all(None not in row for row in tables[name]), "column_count", name)
    if any(x["code"] in {"missing_file", "schema", "column_count"} for x in findings):
        return {"checks": checks, "findings": findings}
    ids, trace_sums = {}, defaultdict(Decimal)
    traces = defaultdict(list)
    known_sources = set(reference["source_hashes"])
    valid_refs = set(reference["checkout_lines"]) | set(reference["atlas_refs"]) | set(reference["remittance_lines"]) | {b["ref"] for b in reference["banks"]}
    for row in tables["rastro"]:
        key, ref = row["id_saida"], base_ref(row["ref_origem"])
        traces[key].append(row)
        trace_sums[key] += decimal(row["valor"])
        filename = Path(row["arquivo_origem"].replace("\\", "/")).name
        # A reference to an xlsx attachment is legitimate; require an explicit parent EML or a filename present in it.
        valid_file = filename in known_sources or "03_email_ponte_cambio_relatorio_set2026.eml" in row["arquivo_origem"]
        check(valid_file, "unknown_trace_file", row)
        check(ref in valid_refs, "unknown_trace_ref", row)
        if filename.startswith("01_orbe"):
            check(ref in reference["checkout_lines"] or ref in reference["atlas_refs"], "trace_wrong_source", row)
        if filename.startswith("05a_"):
            check(("AURORA", ref) in {(b["bank"], b["ref"]) for b in reference["banks"]}, "trace_wrong_source", row)
        if filename.startswith("05b_"):
            check(("MERIDIANO", ref) in {(b["bank"], b["ref"]) for b in reference["banks"]}, "trace_wrong_source", row)
    for name, field in VALUES.items():
        for row in tables[name]:
            key = row["id_saida"]
            check(bool(key) and key not in ids, "output_id_not_unique", {"table": name, "id": key})
            ids[key] = name
            if name == "pendencias" and not row[field]:
                check(bool(row["motivo"]) and bool(row["quem_decide"]), "unowned_pending", key)
                continue
            value = decimal(row[field])
            check(key in trace_sums, "missing_trace", key)
            check(value == trace_sums[key], "trace_sum", {"id": key, "reported": str(value), "trace": str(trace_sums[key])})
    check(not (set(trace_sums) - set(ids)), "orphan_trace", sorted(set(trace_sums) - set(ids)))
    for name, field in [("comissoes_por_lojista", "cnpj"), ("divergencias_taxa", "cnpj"), ("notas_a_emitir", "tomador_cnpj")]:
        for row in tables[name]:
            check(bool(re.fullmatch(r"\d{14}", row[field])), "cnpj_format", row["id_saida"])
            check(row["linha_negocio"] in {"CHECKOUT", "REMESSA"}, "business_line", row["id_saida"])
    commissions = tables["comissoes_por_lojista"]
    invoice_keys = set()
    for row in tables["notas_a_emitir"]:
        check(decimal(row["valor_brl"]) > 0, "nonpositive_invoice", row["id_saida"])
        key = row["tomador_cnpj"], row["linha_negocio"]
        check(key not in invoice_keys, "duplicate_invoice", key)
        invoice_keys.add(key)
        if row["linha_negocio"] == "CHECKOUT":
            check(row["tomador_cnpj"] != "39566044000119", "atlas_in_invoice", row["id_saida"])
            matching = [r for r in tables["comissoes_por_lojista"] if r["linha_negocio"] == "CHECKOUT" and r["cnpj"] == row["tomador_cnpj"]]
            check(len(matching) == 1 and decimal(row["valor_brl"]) == sum((decimal(r["comissao_brl"]) for r in matching), Decimal(0)), "checkout_invoice_value", row["id_saida"])
    remit_invoices = [r for r in tables["notas_a_emitir"] if r["linha_negocio"] == "REMESSA"]
    check(len(remit_invoices) == 1, "remittance_invoice_count", len(remit_invoices))
    if len(remit_invoices) == 1:
        check(decimal(remit_invoices[0]["valor_brl"]) == Decimal(reference["remittance_total"]), "remittance_invoice_value", remit_invoices[0])
        check("ponte" in remit_invoices[0]["tomador"].lower(), "remittance_invoice_party", remit_invoices[0]["tomador"])
    actual_remit = defaultdict(Decimal)
    for row in commissions:
        if row["linha_negocio"] == "REMESSA":
            actual_remit[row["cnpj"]] += decimal(row["comissao_brl"])
    check(dict(actual_remit) == {k: Decimal(v) for k, v in reference["remittance_totals"].items()}, "remittance_by_merchant", {"actual": {k: str(v) for k, v in actual_remit.items()}})
    divergence_refs = set()
    for row in tables["divergencias_taxa"]:
        ref = base_ref(row["ref_origem"])
        key = row["linha_negocio"], ref
        check(key not in divergence_refs, "duplicate_divergence", key)
        divergence_refs.add(key)
        expected = reference["checkout_lines" if key[0] == "CHECKOUT" else "remittance_lines"].get(ref)
        check(expected is not None, "unknown_divergence", key)
        if expected is None or expected.get("confidence") == "historical_proxy_requires_review":
            continue
        check(decimal(row["taxa_contratada_pct"]) == Decimal(expected["contract_rate_pct"]), "divergence_contract_rate", ref)
        check(decimal(row["taxa_aplicada_pct"]) == Decimal(expected["applied_rate_pct"]), "divergence_applied_rate", ref)
        check(decimal(row["diferenca_brl"]) == Decimal(expected["difference"]), "divergence_line_value", ref)
        if row["cnpj"] == "00520815000100" and key[0] == "CHECKOUT":
            check(row.get("contestar_parceiro", "NAO") == "NAO", "casa_charged_to_orbe", ref)
    for ref, expected in reference["checkout_lines"].items():
        if expected["confidence"] == "source_supported" and Decimal(expected["applied_rate_pct"]) != Decimal(expected["contract_rate_pct"]):
            check(("CHECKOUT", ref) in divergence_refs, "missing_checkout_divergence", ref)
    for row in commissions:
        if row["linha_negocio"] == "CHECKOUT":
            check(row["cnpj"] != "39566044000119", "atlas_in_commission", row["id_saida"])
        commission_refs = set()
        for trace in traces[row["id_saida"]]:
            ref = base_ref(trace["ref_origem"])
            check(ref not in commission_refs, "duplicate_commission_source", {"id": row["id_saida"], "ref": ref})
            commission_refs.add(ref)
            if row["linha_negocio"] == "CHECKOUT" and ref in reference["checkout_lines"]:
                expected = reference["checkout_lines"][ref]
                if expected["confidence"] == "source_supported":
                    check(decimal(trace["valor"]) == Decimal(expected["value"]), "checkout_line_value", {"ref": ref, "actual": trace["valor"], "expected": expected["value"]})
                check(row["cnpj"] == expected["cnpj"], "checkout_identity", ref)
            elif row["linha_negocio"] == "REMESSA" and ref in reference["remittance_lines"]:
                expected = reference["remittance_lines"][ref]
                check(expected["eligible"], "excluded_remittance_in_commission", ref)
                check(decimal(trace["valor"]) == Decimal(expected["value"]), "remittance_line_value", ref)
                check(row["cnpj"] == expected["cnpj"], "remittance_identity", ref)
    # Source conservation must not depend on equal grand totals.
    represented_checkout = {base_ref(t["ref_origem"]) for t in tables["rastro"] if ids.get(t["id_saida"]) in {"comissoes_por_lojista", "pendencias"}}
    check(not ((set(reference["checkout_lines"]) | set(reference["atlas_refs"])) - represented_checkout), "unrepresented_checkout", sorted((set(reference["checkout_lines"]) | set(reference["atlas_refs"])) - represented_checkout))
    expected_banks = {(b["bank"], b["ref"]): b for b in reference["banks"]}
    actual_banks = {}
    accounts = {r["COD_CONTA"] for r in table(DATA / "04_plano_de_contas_fenix_erp.csv", "cp1252") if r["ACEITA_LANCTO"] == "S"}
    for row in tables["lancamentos_classificados"]:
        key = row["banco"], row["ref_origem"]
        check(key not in actual_banks, "duplicate_bank", key)
        actual_banks[key] = row
        check(key in expected_banks, "unknown_bank_ref", key)
        if key in expected_banks:
            check(decimal(row["valor"]) == Decimal(expected_banks[key]["value"]), "bank_amount", key)
        check(row["conta_codigo"] in accounts, "invalid_account", row["id_saida"])
        check(row["metodo"] in {"REGRA", "IA", "HUMANO"}, "classification_method", row["id_saida"])
        check(0 <= decimal(row["confianca"]) <= 1, "confidence", row["id_saida"])
        try:
            date = datetime.strptime(row["data"], "%Y-%m-%d")
            check(date.strftime("%Y-%m") == "2026-09", "bank_period", key)
        except ValueError:
            check(False, "bank_date", key)
    check(set(actual_banks) == set(expected_banks), "bank_conservation", {"missing": sorted(set(expected_banks) - set(actual_banks)), "extra": sorted(set(actual_banks) - set(expected_banks))})
    for key, expected in expected_banks.items():
        if key not in actual_banks:
            continue
        row = actual_banks[key]
        desc = expected["description"].upper()
        if key == ("MERIDIANO", "MRD2026090132"):
            check(row["conta_codigo"] == "1.1.03.002", "ponte_august_receivable", row)
        if key == ("MERIDIANO", "MRD2026090425"):
            check(row["conta_codigo"] == "2.1.02.001", "future_remittance_liability", row)
        if "ORBE" in desc and Decimal(expected["value"]) > 0:
            check(row["conta_codigo"] == "1.1.03.001", "orbe_receivable", key)
        if expected["value"] in {"-300000.00", "-300000,00", "-300000"} and key[0] == "AURORA":
            check(row["conta_codigo"] == "1.1.09.001", "in_transit_transfer", row)
        if "FOLHA" in desc:
            check(row["conta_codigo"] == "2.1.04.001", "payroll_provision", row)
        for token, account in {"ISS": "2.1.03.003", "INSS": "2.1.04.002", "FGTS": "2.1.04.003", "IRRF": "2.1.03.004", "PIS": "2.1.03.001", "COFINS": "2.1.03.002"}.items():
            if re.search(r"\b" + token + r"\b", desc):
                check(row["conta_codigo"] == account, "tax_provision", row)
        if Decimal(expected["value"]) == Decimal("7350") and key[0] == "AURORA":
            check(not row["conta_codigo"].startswith("3."), "unknown_pix_as_revenue", row)
        if Decimal(expected["value"]) == Decimal("12400") and "DEVOL" in desc:
            check(row["conta_codigo"] in {"2.1.01.001", "2.1.01.002"}, "returned_transfer_liability", row)
    if not reference["late_adjustments_present"]:
        findings.append({"severity": "limitation", "code": "late_adjustment_missing", "detail": "06 integral absent: only received pack audited, not complete updated close."})
    findings.append({"severity": "limitation", "code": "historical_contract_review", "detail": f'{len(reference["historical_proxy_refs"])} pre-September checkout references require historical-source review; proxy values not used for exact assertions.'})
    return {"checks": checks, "findings": findings}


def audit_directory(output_dir):
    tables, headers, missing = {}, {}, []
    for name in SCHEMAS:
        path = output_dir / (name + ".csv")
        if not path.exists():
            missing.append(str(path))
            continue
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, delimiter=";")
            headers[name], tables[name] = reader.fieldnames or [], list(reader)
    result = audit_tables(tables, headers, build_reference())
    result.update({"timestamp": datetime.now(timezone.utc).isoformat(), "output_dir": str(output_dir.resolve()), "missing": missing,
                   "status": "not_available" if missing else "fail" if any(x["severity"] == "error" for x in result["findings"]) else "pass_with_limits"})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit_directory(args.output_dir)
    except (ValueError, InvalidOperation, KeyError) as error:
        result = {"status": "fail", "findings": [{"severity": "error", "code": "malformed_data", "detail": str(error)}]}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    errors = [x for x in result["findings"] if x["severity"] == "error"]
    print(json.dumps({"status": result["status"], "checks": result.get("checks"), "errors": len(errors), "first_errors": errors[:8]}, ensure_ascii=False))
    raise SystemExit(2 if result["status"] == "not_available" else 1 if errors else 0)
