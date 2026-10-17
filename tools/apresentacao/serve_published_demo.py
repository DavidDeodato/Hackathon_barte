"""Serve real published outputs for an explicitly declared archival consultation.

No financial recomputation or mock model adapter. Separate local state preserves
the production application and official output files. Original inputs are not
bundled and a clone does not reproduce the financial execution without them.
"""
from pathlib import Path
import argparse
import csv
from decimal import Decimal
import hashlib
import json
import os
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def prepare_snapshot(state):
    from tarvo.storage.sqlite import Store
    source = ROOT / "saida"
    manifest = json.loads((source / "manifest.json").read_text())
    for item in manifest["outputs"]:
        actual = hashlib.sha256((source / item["file"]).read_bytes()).hexdigest()
        if actual != item["sha256"]:
            raise ValueError("Published output hash mismatch: " + item["file"])
    tables = {}
    for item in manifest["outputs"]:
        with (source / item["file"]).open(encoding="utf-8-sig") as file:
            tables[item["file"]] = list(csv.DictReader(file, delimiter=";"))
    checks = json.loads((source / "reconciliacao.json").read_text())
    if not checks or any(not row["ok"] for row in checks):
        raise ValueError("Published trace report contains a mismatch")
    com = tables["comissoes_por_lojista.csv"]
    div = tables["divergencias_taxa.csv"]
    def total(rows, field):
        return str(sum((Decimal(row[field]) for row in rows), Decimal(0)))
    summary = {
        "checkout_commission_brl": total([r for r in com if r["linha_negocio"] == "CHECKOUT"], "comissao_brl"),
        "remessa_commission_brl": total([r for r in com if r["linha_negocio"] == "REMESSA"], "comissao_brl"),
        "invoices_brl": total(tables["notas_a_emitir.csv"], "valor_brl"),
        "checkout_rate_difference_brl": total([r for r in div if r["natureza"] == "TAXA_ORBE"], "diferenca_brl"),
        "casa_refund_brl": total([r for r in div if r["natureza"] == "DEVOLUCAO_CASA_SEM_COBRANCA_ORBE"], "diferenca_brl"),
        "remessa_rate_difference_brl": total([r for r in div if r["linha_negocio"] == "REMESSA"], "diferenca_brl"),
        "counts": {k: len(v) for k, v in tables.items()},
        "trace_checks": len(checks), "trace_reconciled": True,
        "financial_approval": "PENDENTE_HELENA", "mode": "CONSULTA_SAIDAS_PUBLICADAS",
        "late_adjustments": "INCORPORADO", "completeness": "CONJUNTO_FORNECIDO_PROCESSADO",
    }
    run_id = manifest["run_id"]
    archive = state / "runs" / run_id
    archive.mkdir(parents=True, exist_ok=True)
    for file in source.iterdir():
        if file.is_file():
            shutil.copyfile(file, archive / file.name)
    payload = {"output_dir": str(archive), "period": manifest["period"],
               "archived_from": "saida/manifest.json", "demo_kind": "published_outputs_consultation"}
    result = {"run_id": run_id, "period": manifest["period"], "status": "pending_review",
              "outputs": [str(archive / k) for k in tables], "summary": summary, "issues": []}
    store = Store(state / "tarvo.sqlite3")
    with store.connect() as db:
        existing = db.execute("SELECT id FROM jobs LIMIT 1").fetchone()
        if existing:
            raise ValueError("Use a new isolated state directory; this helper never overwrites an existing ledger")
        stamp = manifest["created_at"]
        db.execute("INSERT INTO jobs(id,kind,run_id,status,period,created_at,updated_at,payload,result) VALUES (?,?,?,'pending_review',?,?,?,?,?)",
                   (run_id, "close", run_id, manifest["period"], stamp, stamp, json.dumps(payload), json.dumps(result)))
    return run_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--frontend-origin", default="http://127.0.0.1:5173")
    args = parser.parse_args()
    if not args.frontend_origin.startswith(("http://127.0.0.1:", "http://localhost:")):
        parser.error("This archival consultation accepts only a local frontend origin")
    state = args.state_dir.resolve()
    if state == ROOT or state == ROOT / "saida":
        parser.error("Use a separate state directory")
    if (state / "tarvo.sqlite3").exists():
        parser.error("Use a new state directory for this consultation")
    run_id = prepare_snapshot(state)
    from tarvo.api.config import Settings
    from tarvo.api.main import create_app
    import uvicorn
    settings = Settings(project_root=ROOT, input_dir=state / "no-originals-bundled", state_dir=state,
                        access_password=os.environ.get("TARVO_ACCESS_PASSWORD", ""),
                        api_token=os.environ.get("TARVO_API_TOKEN", ""), cors_origins=(args.frontend_origin,))
    app = create_app(settings=settings)
    print("CONSULTA ARQUIVADA: " + run_id + ". Nenhuma nova apuração financeira ou inferência de modelo.", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, proxy_headers=False)


if __name__ == "__main__":
    main()
