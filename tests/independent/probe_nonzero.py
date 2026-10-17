"""Synthetic one-line applied-fee delta through a separate real local API.

--prepare copies case files only into QA-owned paths. A QA-owned API must use
live_input and runtime below. Never reads credentials or modifies official data.
"""
import argparse
import csv
import hashlib
import json
import shutil
import time
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from urllib.request import Request, urlopen

from reference import DATA, ROOT, br, build_reference, rounded
from audit_outputs import SCHEMAS

WORK = ROOT / "docs/agent/branches/QA/artifacts/nonzero_001"
BASE = "http://127.0.0.1:8002"
ORBE = "01_orbe_relatorio_comissoes_set2026.csv"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes(folder):
    return {p.name: digest(p) for p in folder.iterdir() if p.is_file()}


def prepare():
    if (WORK / "prepared.json").exists():
        raise ValueError("Prepared scenario already exists; preserve its evidence")
    original = hashes(DATA)
    live = WORK / "live_input"
    live.mkdir(parents=True, exist_ok=True)
    for source in DATA.iterdir():
        if source.is_file():
            shutil.copyfile(source, live / source.name)
    with (live / ORBE).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=";")
        fields, rows = reader.fieldnames, list(reader)
    refs = {row["id_referencia"] for row in rows if row["id_referencia"]}
    reference = build_reference()
    target = next(row for row in rows if row["cod_estabelecimento"] == "1074504011" and row["tipo_lancamento"] == "VENDA"
                  and row["id_transacao"] not in refs and row["id_transacao"] in reference["checkout_lines"]
                  and br(row["taxa_aplicada_pct"]) != Decimal(reference["checkout_lines"][row["id_transacao"]]["contract_rate_pct"]))
    expected = reference["checkout_lines"][target["id_transacao"]]
    old_rate = br(target["taxa_aplicada_pct"])
    new_rate = old_rate + Decimal("1.00")  # synthetic +1 percentage point on exactly one existing applied fee
    gross = br(target["valor_bruto"])
    contracted = Decimal(expected["contract_rate_pct"])
    old_difference = rounded(gross * (old_rate - contracted) / 100)
    new_difference = rounded(gross * (new_rate - contracted) / 100)
    fixture = {"dataset_kind": "synthetic_test", "description": "One existing Rota applied fee increased by 1.00 percentage point; not a received late adjustment or client-approved rule.",
               "source_file": ORBE, "source_ref": target["id_transacao"], "gross_brl": str(gross), "contract_rate_pct": str(contracted),
               "before_applied_pct": str(old_rate), "after_applied_pct": str(new_rate), "expected_before_difference_brl": str(old_difference),
               "expected_after_difference_brl": str(new_difference), "expected_delta_brl": str(new_difference - old_difference),
               "expected_perimeter": {"divergencias_taxa.csv": "one changed existing CHECKOUT/Rota/source-ref row",
                                      "pendencias.csv": "one changed CONTESTACAO_ORBE Rota aggregate",
                                      "rastro.csv": "two changed traces for that transaction (divergence and pending)",
                                      "comissoes_por_lojista.csv": "unchanged", "notas_a_emitir.csv": "unchanged", "lancamentos_classificados.csv": "unchanged"},
               "original_input_hashes": original, "official_csv_hashes": {name + ".csv": digest(ROOT / "saida" / (name + ".csv")) for name in SCHEMAS}}
    (WORK / "prepared.json").write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"work": str(WORK), "live_input": str(live), "runtime": str(WORK / "runtime"), "fixture": fixture}, ensure_ascii=False))


def request(path, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = Request(BASE + path, data=body, headers={"Content-Type": "application/json"} if body else {})
    with urlopen(req, timeout=15) as response:
        return response.status, json.load(response)


def wait_job(path, seconds=70):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        _, body = request(path)
        if body["status"] not in {"queued", "running", "processing"}:
            return body
        time.sleep(0.4)
    raise TimeoutError(path)


def probe():
    fixture = json.loads((WORK / "prepared.json").read_text(encoding="utf-8"))
    live = WORK / "live_input"
    status, before = request("/api/runs", {"period": "2026-09"})
    before_job = wait_job("/api/runs/" + before["run_id"])
    if before_job["status"] != "pending_review":
        raise AssertionError(before_job)
    before_folder = WORK / "runtime/runs" / before["run_id"]
    before_hashes = hashes(before_folder)
    with (live / ORBE).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=";")
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        if row["id_transacao"] == fixture["source_ref"]:
            row["taxa_aplicada_pct"] = fixture["after_applied_pct"].replace(".", ",")
            fee = (br(row["valor_bruto"]) * Decimal(fixture["after_applied_pct"]) / 100).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            row["valor_taxa"] = str(fee).replace(".", ",")
            row["valor_liquido"] = str(br(row["valor_bruto"]) - fee).replace(".", ",")
    with (live / ORBE).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    (live / "QA_SYNTHETIC_SCENARIO.json").write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
    _, after = request("/api/runs", {"period": "2026-09"})
    after_job = wait_job("/api/runs/" + after["run_id"])
    _, replay = request("/api/runs", {"period": "2026-09"})
    replay_job = wait_job("/api/runs/" + replay["run_id"])
    _, compare = request("/api/comparisons", {"before_run_id": before["run_id"], "after_run_id": after["run_id"]})
    comparison = wait_job("/api/comparisons/" + compare["comparison_id"])
    outputs = comparison["result"]["outputs"]
    changes = {o["name"]: {"added": len(o["added"]), "removed": len(o["removed"]), "changed": len(o["changed"])} for o in outputs}
    checks = {"before_202": status == 202, "all_runs_pending_review": all(x["status"] == "pending_review" for x in [before_job, after_job, replay_job]),
              "comparison_completed": comparison["status"] == "completed", "before_immutable": before_hashes == hashes(before_folder),
              "original_pack_immutable": fixture["original_input_hashes"] == hashes(DATA),
              "official_csvs_immutable": fixture["official_csv_hashes"] == {name + ".csv": digest(ROOT / "saida" / (name + ".csv")) for name in SCHEMAS}}
    for name in ["comissoes_por_lojista.csv", "notas_a_emitir.csv", "lancamentos_classificados.csv"]:
        checks["unchanged_" + name] = changes[name] == {"added": 0, "removed": 0, "changed": 0}
    for name in ["divergencias_taxa.csv", "pendencias.csv"]:
        output = next(o for o in outputs if o["name"] == name)
        checks["one_changed_" + name] = changes[name] == {"added": 0, "removed": 0, "changed": 1}
        checks["expected_delta_" + name] = len(output["changed"]) == 1 and Decimal(output["changed"][0]["monetary_delta"]) == Decimal(fixture["expected_delta_brl"])
        checks["target_source_" + name] = bool(output["changed"]) and any(fixture["source_ref"] in ref for ref in output["changed"][0]["source_refs"])
    checks["trace_perimeter"] = changes["rastro.csv"] == {"added": 0, "removed": 0, "changed": 2}
    after_folder = WORK / "runtime/runs" / after["run_id"]
    replay_folder = WORK / "runtime/runs" / replay["run_id"]
    checks["replay_csvs_identical"] = all(digest(after_folder / (name + ".csv")) == digest(replay_folder / (name + ".csv")) for name in SCHEMAS)
    report = {"type": "synthetic_test; no actual late adjustment/client rule approval", "base_url": BASE, "fixture": fixture, "checks": checks,
              "before_run_id": before["run_id"], "after_run_id": after["run_id"], "replay_run_id": replay["run_id"], "comparison_id": compare["comparison_id"],
              "changes": changes, "before_hashes": before_hashes, "before_final_hashes": hashes(before_folder), "comparison": comparison,
              "limits": ["Same monetary delta in divergence and pending describes one underlying effect; do not add them.",
                         "Synthetic source copy only; no received adjustment, commercial authority, original October data, approval or recovery is proven.",
                         "Mode is deterministic; no LLM request was made."]}
    (WORK / "proof.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checks": checks, "delta": fixture["expected_delta_brl"], "source_ref": fixture["source_ref"], "before": before["run_id"], "after": after["run_id"], "comparison_id": compare["comparison_id"]}, ensure_ascii=False))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        prepare()
    else:
        raise SystemExit(probe())
