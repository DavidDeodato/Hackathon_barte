"""Narrow review of prior-month refunds against supplied dated contract rows."""
import csv
import json
from datetime import datetime
from decimal import Decimal

from reference import ROOT, build_reference, read_sources

reference = build_reference()
_, contracts, _, _ = read_sources()
contract_rows = {number: values for number, values in contracts}
official = ROOT / "saida"
with (official / "comissoes_por_lojista.csv").open(encoding="utf-8-sig", newline="") as stream:
    ids = {row["id_saida"] for row in csv.DictReader(stream, delimiter=";")}
with (official / "rastro.csv").open(encoding="utf-8-sig", newline="") as stream:
    traces = {row["ref_origem"]: row for row in csv.DictReader(stream, delimiter=";") if row["id_saida"] in ids}
rows = []
for ref in reference["historical_proxy_refs"]:
    expected = reference["checkout_lines"][ref]
    raw = contract_rows[expected["contract_row"]]
    start = datetime.strptime(raw[10], "%d/%m/%Y").date()
    original = datetime.strptime(expected["effective"], "%d/%m/%Y").date()
    actual = traces[ref]
    rows.append({"source_ref": ref, "contract_row": expected["contract_row"], "contract_valid_from": start.isoformat(),
                 "original_sale_date_from_refund": original.isoformat(), "contract_covers_original_date": start <= original,
                 "contract_rate_pct": expected["contract_rate_pct"], "independent_value_brl": expected["value"], "actual_trace_value_brl": actual["valor"],
                 "matches_independent_value": Decimal(actual["valor"]) == Decimal(expected["value"]),
                 "raw_original_transaction_present": expected["original_present"]})
report = {"scope": "Nine prior-month originals flagged by broad initial QA exclusion. Validity checks use supplied Taxas vigentes date, not old 2025 table or applied-fee assumption.",
          "rows": rows, "checks": {"nine_reviewed": len(rows) == 9, "all_dated_contracts_cover_original": all(r["contract_covers_original_date"] for r in rows), "all_values_match": all(r["matches_independent_value"] for r in rows)},
          "limits": ["Original August transaction documents remain absent. Date linkage is the provided September refund's data_venda_original.",
                     "This supports calculations under supplied dated schedule; no real contract authenticity, prior invoice, approval or complete August ledger certified.",
                     "An original before supplied contract validity would remain unresolved; this review does not relax that gate."]}
path = ROOT / "docs/agent/branches/QA/artifacts/historical_review_001.json"
path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report["checks"]))
raise SystemExit(0 if all(report["checks"].values()) else 1)
