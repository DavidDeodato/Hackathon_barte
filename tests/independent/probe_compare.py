"""Independent synthetic mutations after baseline freeze. No engine-derived gold."""
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from tarvo.finance.compare import compare_runs

OUT = ROOT / "docs/agent/branches/QA/artifacts"
FILES = ["comissoes_por_lojista.csv", "divergencias_taxa.csv", "notas_a_emitir.csv", "lancamentos_classificados.csv", "pendencias.csv", "rastro.csv"]


def read(folder, name):
    with (folder / name).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=";")
        return reader.fieldnames, list(reader)


def write(folder, name, fields, rows):
    with (folder / name).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["dataset_kind"] = "synthetic_test"
    for output in manifest["outputs"]:
        if output["file"] == name:
            output["sha256"] = hashlib.sha256((folder / name).read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def run():
    source = OUT / "replay_a"
    before_hashes = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in FILES}
    work = OUT / ("compare_independent_" + uuid4().hex[:8])
    baseline = work / "before"
    renamed = work / "renamed"
    traces_changed = work / "traces_changed"
    ambiguous = work / "ambiguous"
    for folder in [baseline, renamed, traces_changed, ambiguous]:
        folder.mkdir(parents=True)
        for name in [*FILES, "manifest.json"]:
            shutil.copyfile(source / name, folder / name)
    zero = compare_runs(str(baseline), str(baseline))
    checks = {"identical_has_zero_delta": all(not r["added"] and not r["removed"] and not r["changed"] for r in zero["outputs"])}
    for name in FILES:
        fields, rows = read(renamed, name)
        for row in rows:
            row["id_saida"] = "QA-RENUMBERED-" + row["id_saida"]
        write(renamed, name, fields, rows)
    renumbered = compare_runs(str(baseline), str(renamed))
    checks["renumbering_no_financial_delta"] = all(not r["added"] and not r["removed"] and not r["changed"] for r in renumbered["outputs"])
    fields, trace = read(traces_changed, "rastro.csv")
    _, commission = read(traces_changed, "comissoes_por_lojista.csv")
    target = next(r["id_saida"] for r in commission if sum(t["id_saida"] == r["id_saida"] for t in trace) > 2)
    selected = [r for r in trace if r["id_saida"] == target]
    first, second = next((a, b) for a in selected for b in selected if a["valor"] != b["valor"])
    first["valor"], second["valor"] = second["valor"], first["valor"]
    write(traces_changed, "rastro.csv", fields, trace)
    shifted = compare_runs(str(baseline), str(traces_changed))
    changed_commissions = next(r for r in shifted["outputs"] if r["name"] == "comissoes_por_lojista.csv")["changed"]
    checks["same_total_changed_composition_detected"] = len(changed_commissions) == 1 and changed_commissions[0]["monetary_delta"] == "0.00"
    checks["changed_composition_has_sources"] = bool(changed_commissions[0]["source_refs"])
    checks["trace_not_added_to_financial_total"] = next(r for r in shifted["outputs"] if r["name"] == "rastro.csv")["totals_by_nature"] == []
    fields, pending = read(ambiguous, "pendencias.csv")
    duplicate = dict(pending[0], id_saida="QA-DUPLICATE-BUSINESS-KEY")
    pending.append(duplicate)
    write(ambiguous, "pendencias.csv", fields, pending)
    try:
        compare_runs(str(baseline), str(ambiguous))
        checks["ambiguous_semantic_identity_rejected"] = False
    except ValueError:
        checks["ambiguous_semantic_identity_rejected"] = True
    after_hashes = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in FILES}
    checks["original_run_immutable"] = before_hashes == after_hashes
    report = {"type": "synthetic regression; not real rule approval or October", "checks": checks, "baseline_hashes": before_hashes, "final_baseline_hashes": after_hashes, "zero": zero, "renumbered": renumbered, "composition_shift": shifted}
    (OUT / "compare_probe_001.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checks": checks, "work_dir": str(work)}, ensure_ascii=False))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(run())
