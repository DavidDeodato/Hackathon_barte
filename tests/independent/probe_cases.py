"""Independent case-packet acceptance from primary-source QA reference.

Production is called only for observed packets, never to generate expected values.
"""
import csv
import hashlib
import json
import shutil
import sys
from decimal import Decimal
from pathlib import Path

from reference import ROOT, br, build_reference, read_sources

sys.path.insert(0, str(ROOT / "src"))
from tarvo.finance.cases import build_case_packet

OUT = ROOT / "docs/agent/branches/QA/artifacts/cases_001"
OFFICIAL = ROOT / "saida"
NAMES = ["comissoes_por_lojista.csv", "divergencias_taxa.csv", "notas_a_emitir.csv", "lancamentos_classificados.csv", "pendencias.csv", "rastro.csv"]


def hashes(folder):
    return {name: hashlib.sha256((folder / name).read_bytes()).hexdigest() for name in NAMES}


def run():
    OUT.mkdir(exist_ok=True)
    reference = build_reference()
    checkout, _, _, _ = read_sources()
    expected_refs = {
        "casa": {ref for ref, value in reference["checkout_lines"].items() if value["cnpj"] == "00520815000100" and Decimal(value["difference"]) != 0},
        "rota": {ref for ref, value in reference["checkout_lines"].items() if value["cnpj"] == "95927868000148" and Decimal(value["difference"]) != 0},
        "mundo": {ref for ref, value in reference["remittance_lines"].items() if value["cnpj"] == "17217888000111" and value["eligible"] and abs(Decimal(value["applied_rate_pct"]) - Decimal(value["contract_rate_pct"])) > Decimal("0.01")},
        "atlas": set(reference["atlas_refs"]),
    }
    expected_amounts = {key: sum((Decimal(reference["checkout_lines" if key in {"casa", "rota"} else "remittance_lines"][ref]["difference"]) for ref in refs), Decimal(0)) for key, refs in expected_refs.items() if key != "atlas"}
    atlas_volume = sum((br(row["valor_bruto"]) for row in checkout if row["id_transacao"] in expected_refs["atlas"]), Decimal(0))
    initial = hashes(OFFICIAL)
    packets = {key: build_case_packet(str(OFFICIAL), key) for key in expected_refs}
    checks = {}
    summaries = {}
    for key, packet in packets.items():
        observed_refs = {row.get("ref_origem") for row in packet["rows"]}
        checks[key + "_exact_origin_set"] = observed_refs == expected_refs[key]
        checks[key + "_pending_not_resolved"] = packet["status"] == "prepared_for_review" and not packet["approved"] and not packet["sent"]
        checks[key + "_deterministic_honest"] = packet["model_used"] is False
        checks[key + "_snapshot_six_files"] = packet["snapshot"] == initial
        checks[key + "_closure_evidence_present"] = len(packet["closure_evidence"]) >= 2 and bool(packet["owner"]) and bool(packet["recipient"])
        if key != "atlas":
            checks[key + "_independent_amount"] = Decimal(packet["amount"]) == expected_amounts[key]
            checks[key + "_each_component"] = all(Decimal(row["amount"]) == Decimal(reference["checkout_lines" if key in {"casa", "rota"} else "remittance_lines"][row["ref_origem"]]["difference"]) for row in packet["rows"])
        summaries[key] = {field: packet[field] for field in ["case_id", "snapshot_id", "amount", "amount_nature", "recipient", "owner", "status", "action_type", "closure_evidence", "limitations"]}
        summaries[key]["source_refs"] = packet["source_refs"]
    checks["casa_destination_not_orbe"] = packets["casa"]["action_type"] == "prepare_merchant_refund" and "comercial" in packets["casa"]["recipient"].lower()
    checks["casa_august_refund_excluded_from_refund_case"] = "TX88445133" not in expected_refs["casa"]
    checks["rota_includes_signed_refunds"] = any(Decimal(row["amount"]) < 0 for row in packets["rota"]["rows"])
    checks["mundo_destination_ponte"] = packets["mundo"]["recipient"] == "Ponte Câmbio" and packets["mundo"]["action_type"] == "prepare_ponte_dispute"
    realized = packets["mundo"]["related_outputs"]["commissions"]
    invoices = packets["mundo"]["related_outputs"]["invoices"]
    checks["mundo_realized_commission_preserved"] = len(realized) == 1 and Decimal(realized[0]["amount"]) == Decimal(reference["remittance_totals"]["17217888000111"])
    checks["mundo_full_ponte_invoice_preserved"] = len(invoices) == 1 and Decimal(invoices[0]["amount"]) == Decimal(reference["remittance_total"])
    checks["atlas_unknown_commission_not_volume"] = packets["atlas"]["amount"] is None and Decimal(packets["atlas"]["supporting_metrics"][0]["amount"]) == atlas_volume
    checks["repeated_preparation_stable_ids"] = all(build_case_packet(str(OFFICIAL), key)["case_id"] == packets[key]["case_id"] for key in packets)
    checks["official_run_immutable"] = hashes(OFFICIAL) == initial

    fixture = OUT / "negative_fixture"
    fixture.mkdir(exist_ok=True)
    def reset():
        for name in [*NAMES, "manifest.json"]:
            shutil.copyfile(OFFICIAL / name, fixture / name)
    def mutate(name, change):
        with (fixture / name).open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, delimiter=";")
            fields, rows = reader.fieldnames, list(reader)
        change(rows)
        with (fixture / name).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, delimiter=";")
            writer.writeheader(); writer.writerows(rows)
        manifest = json.loads((fixture / "manifest.json").read_text(encoding="utf-8"))
        manifest["dataset_kind"] = "synthetic_test"
        for item in manifest["outputs"]:
            if item["file"] == name:
                item["sha256"] = hashlib.sha256((fixture / name).read_bytes()).hexdigest()
        (fixture / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    def rejects(key):
        try:
            build_case_packet(str(fixture), key)
        except ValueError:
            return True
        return False
    reset()
    mutate("divergencias_taxa.csv", lambda rows: [row.update(contestar_parceiro="REVISAO_HELENA") for row in rows if row["cnpj"] == "00520815000100"])
    checks["casa_wrong_partner_route_rejected"] = rejects("casa")
    reset()
    mutate("pendencias.csv", lambda rows: [row.update(estado="APROVADO") for row in rows if row["tipo"] == "CONTESTACAO_PONTE"])
    checks["invented_approved_anchor_rejected"] = rejects("mundo")
    reset()
    with (fixture / "rastro.csv").open("a", encoding="utf-8") as stream:
        stream.write("QA corrupted source\n")
    checks["changed_snapshot_rejected"] = rejects("casa")
    try:
        build_case_packet(str(OFFICIAL), "unknown")
        checks["unknown_case_rejected"] = False
    except ValueError:
        checks["unknown_case_rejected"] = True
    checks["original_still_immutable_after_adversarial"] = hashes(OFFICIAL) == initial
    report = {"kind": "known-case deterministic regression; expected values from independent primary-source calculations", "checks": checks,
              "expected": {"amounts_brl": {k: str(v) for k, v in expected_amounts.items()}, "atlas_volume_not_commission": str(atlas_volume), "refs": {k: sorted(v) for k, v in expected_refs.items()}},
              "observed": summaries, "before_hashes": initial, "after_hashes": hashes(OFFICIAL),
              "limits": ["Four curated deterministic case types only; not generalized/adaptive case investigation.", "This validates preparation, not approval, sending, recovery or resolution.", "Authority/rule prose is a curated specification; CSV snapshot hashes are not primary-contract authenticity verification.", "No LLM called, case-packet UI/HTTP integration not covered by this module probe."]}
    (OUT / "proof.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checks": checks, "expected_amounts": report["expected"]["amounts_brl"]}, ensure_ascii=False))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(run())
