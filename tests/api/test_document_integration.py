"""Authenticated real-document selection -> real finance; no provider calls."""
from pathlib import Path
import hashlib
import time

from fastapi.testclient import TestClient

from tarvo.api.config import Settings
from tarvo.api.main import create_app

ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "https://app.test"


def wait(client, run_id):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        response = client.get("/api/runs/" + run_id)
        assert response.status_code == 200
        result = response.json()
        if result["status"] not in {"queued", "running"}:
            return result
        time.sleep(.05)
    raise AssertionError("Financial run did not finish")


def test_cookie_originals_selection_to_real_007_and_context(tmp_path):
    settings = Settings(ROOT, ROOT / "contexto/data_pack", tmp_path, api_token="fixture-technical",
                        access_password="fixture-human", production=True, job_timeout=30)
    app = create_app(settings)
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get("/api/batches").status_code == 401
        assert client.post("/api/session", json={"password": settings.access_password}, headers={"Origin": ORIGIN}).status_code == 200
        batch = client.get("/api/batches").json()["items"][0]
        documents = client.get(f"/api/batches/{batch['id']}/documents").json()["items"]
        selected = [item for item in documents if item["role"]]
        assert len(selected) == 7
        additional = next(item for item in selected if item["role"] == "adjustments")
        original = client.get(f"/api/documents/{additional['id']}/original?download=true")
        assert original.status_code == 200
        assert hashlib.sha256(original.content).hexdigest() == additional["sha256"]
        assert "sandbox" in original.headers["content-security-policy"]
        response = client.post("/api/runs", json={"batch_id": batch["id"], "period": batch["period"],
                               "document_ids": [item["id"] for item in selected]}, headers={"Origin": ORIGIN})
        assert response.status_code == 202, response.text
        run_id = response.json()["run_id"]
        run = wait(client, run_id)
        assert run["status"] == "pending_review", run
        assert run["summary"]["late_adjustments"] == "INCORPORADO"
        assert run["summary"]["operational_input_issues"] == 0
        assert run["summary"]["checkout_commission_brl"] == "203735.34"
        assert run["summary"]["remessa_commission_brl"] == "39543.45"
        assert run["summary"]["invoices_brl"] == "243284.29"
        assert run["batch_id"] == batch["id"] and run["selection_id"]
        assert {item["name"] for item in run["source_documents"]} == {item["name"] for item in selected}
        outputs = client.get(f"/api/runs/{run_id}/outputs").json()["items"]
        for output in outputs:
            data = client.get(output["url"]).content
            expected = (ROOT / "saida" / output["name"]).read_bytes()
            assert hashlib.sha256(data).hexdigest() == hashlib.sha256(expected).hexdigest(), output["name"]
        # Both semantic entry points receive the same immutable selected set;
        # inspect queued payload without making a paid/model call.
        investigation = client.post(f"/api/runs/{run_id}/investigations", json={"question": "Atlas"}, headers={"Origin": ORIGIN}).json()
        context = app.state.store.get(investigation["investigation_id"])["payload"]["run_context"]
        assert context["selection_id"] == run["selection_id"]
        assert context["source_documents"] == run["source_documents"]


def test_batches_period_payload_boundaries_and_human_errors(tmp_path):
    settings = Settings(ROOT, ROOT / "contexto/data_pack", tmp_path, job_timeout=30)
    app = create_app(settings)
    with TestClient(app) as client:
        batch = client.get("/api/batches").json()["items"][0]
        documents = client.get(f"/api/batches/{batch['id']}/documents").json()["items"]
        assert client.post("/api/runs", json={"batch_id": batch["id"], "period": "2026-10"}).status_code == 409
        assert client.post("/api/runs", json={"document_ids": [documents[0]["id"]]}).status_code == 422
        assert client.post("/api/runs", json={"batch_id": batch["id"], "input_dir": "external"}).status_code == 422
        assert client.post("/api/runs", json={"batch_id": batch["id"], "document_ids": ["foreign"]}).status_code == 409
        selected = [item for item in documents if item["role"]]
        subset = client.post("/api/runs", json={"batch_id": batch["id"], "document_ids": [selected[0]["id"]]})
        assert subset.status_code == 409 and "Faltam fontes" in subset.json()["error"]["message"]
        october = client.post("/api/batches", json={"name": "Outubro com fonte setembro", "period": "2026-10"}).json()
        for doc in selected:
            # Use real uploaded originals; no synthetic financial rows.
            raw = (ROOT / "contexto/data_pack" / doc["name"]).read_bytes()
            response = client.post(f"/api/batches/{october['id']}/documents", params={"name": doc["name"], "role": doc["role"]},
                                   content=raw, headers={"Content-Type": doc["media_type"]})
            assert response.status_code == 201
        created = client.post("/api/runs", json={"batch_id": october["id"], "period": "2026-10"}).json()
        result = wait(client, created["run_id"])
        assert result["status"] == "failed"
        assert result["error"]["code"] == "FINANCIAL_INPUT_REJECTED"
        assert "competência" in result["error"]["message"]


def test_cookie_multipart_real_eml_original_bytes_preserved(tmp_path):
    settings = Settings(ROOT, ROOT / "contexto/data_pack", tmp_path, api_token="fixture-technical",
                        access_password="fixture-human", production=True)
    with TestClient(create_app(settings, start_worker=False), base_url=ORIGIN) as client:
        client.post("/api/session", json={"password": settings.access_password}, headers={"Origin": ORIGIN})
        batch = client.post("/api/batches", json={"name": "E-mail original real", "period": "2026-09"}, headers={"Origin": ORIGIN}).json()
        source = ROOT / "contexto/data_pack/03_email_ponte_cambio_relatorio_set2026.eml"
        data = source.read_bytes()
        response = client.post(f"/api/batches/{batch['id']}/documents", files={"file": (source.name, data, "message/rfc822")},
                               data={"role": "remessa"}, headers={"Origin": ORIGIN})
        assert response.status_code == 201, response.text
        document = response.json()
        original = client.get(f"/api/documents/{document['id']}/original?download=true")
        assert original.status_code == 200 and original.content == data
        assert document["sha256"] == hashlib.sha256(data).hexdigest()
