"""CASES HTTP integration. Real DOM/INT deterministic; no provider call."""
from dataclasses import replace
import hashlib
from pathlib import Path
import sqlite3
import time
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from tarvo.api.config import Settings
from tarvo.api.main import create_app
from tarvo.api.worker import Worker, case_review_adapter
from tarvo.finance import run_close
from tarvo.storage import Store

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "fixture-only-not-a-real-credential"


def wait(client, path, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(path)
        assert response.status_code == 200, response.text
        item = response.json()
        if item["status"] not in {"queued", "running"}:
            return item
        time.sleep(.05)
    pytest.fail("Job did not finish")


@pytest.fixture(scope="module")
def running(tmp_path_factory):
    state = tmp_path_factory.mktemp("cases-api")
    settings = Settings(ROOT, ROOT / "contexto/data_pack", state, api_token=TOKEN, job_timeout=30)
    app = create_app(settings)
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + TOKEN
        response = client.post("/api/runs", json={"period": "2026-09"})
        assert response.status_code == 202
        run_id = response.json()["run_id"]
        assert wait(client, "/api/runs/" + run_id)["status"] == "pending_review"
        yield client, app, settings, run_id


def test_real_case_packets_reviews_events_and_durable_result(running):
    client, app, settings, run_id = running
    output = Path(app.state.store.get(run_id)["payload"]["output_dir"])
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob("*.csv")}
    reviews = []
    for key in ("casa", "atlas"):
        response = client.get(f"/api/runs/{run_id}/cases/{key}")
        assert response.status_code == 200
        packet = response.json()["packet"]
        assert packet["case_key"] == key
        assert packet["status"] == "prepared_for_review"
        assert packet["snapshot"] == before
        assert packet["approved"] is False and packet["sent"] is False
        assert packet["amount"] is None if key == "atlas" else isinstance(packet["amount"], str)
        response = client.post(f"/api/runs/{run_id}/case-reviews", json={"case_key": key})
        assert response.status_code == 202 and response.json()["status"] == "queued"
        review_id = response.json()["review_id"]
        detail = wait(client, "/api/case-reviews/" + review_id)
        assert detail["status"] == "pending_review"
        assert detail["result"]["status"] == "review_required"
        assert detail["result"]["packet"] == packet
        assert detail["result"]["packet_unchanged"] is True
        assert detail["result"]["approved"] is False
        assert detail["result"]["applied_to_calculation"] is False
        assert all(not role["executed"] and role["status"] == "not_executed" for role in detail["result"]["roles"])
        events = client.get(f"/api/case-reviews/{review_id}/events").json()
        assert events["events"][0]["task_id"] == review_id
        assert events["events"][0]["type"] == "task.created"
        assert any(e.get("parent_task_id") == review_id for e in events["events"])
        assert client.get(f"/api/case-reviews/{review_id}/events?after={events['next_cursor']}").json()["events"] == []
        first_page = client.get(f"/api/case-reviews/{review_id}/events?limit=1").json()
        assert len(first_page["events"]) == 1
        assert Store(settings.state_dir / "tarvo.sqlite3").get(review_id)["result"] == detail["result"]
        reviews.append(review_id)
    # A review-specific feed must not include the other case's API task.
    for review_id, other in (reviews, reversed(reviews)):
        events = client.get(f"/api/case-reviews/{review_id}/events").json()["events"]
        assert not any(e["task_id"] == other or e.get("parent_task_id") == other for e in events)
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob("*.csv")} == before
    # A fresh app/store instance retrieves the persisted object without another
    # worker or import of the first app's in-memory response.
    with TestClient(create_app(settings, start_worker=False)) as restored:
        restored.headers["Authorization"] = "Bearer " + TOKEN
        assert restored.get("/api/case-reviews/" + reviews[0]).json()["result"]["packet"]["case_key"] == "casa"


def test_cases_auth_validation_unknown_ids_and_payload_paths(running):
    client, _, _, run_id = running
    for method, path, body in [
        ("get", f"/api/runs/{run_id}/cases/casa", None),
        ("post", f"/api/runs/{run_id}/case-reviews", {"case_key": "casa"}),
        ("get", "/api/case-reviews/unknown", None),
        ("get", "/api/case-reviews/unknown/events", None),
    ]:
        response = client.request(method, path, headers={"Authorization": ""}, json=body)
        assert response.status_code == 401
    assert client.get("/api/runs/unknown/cases/casa").status_code == 404
    assert client.get("/api/case-reviews/unknown").status_code == 404
    assert client.get(f"/api/runs/{run_id}/cases/arbitrary").status_code == 422
    assert client.post(f"/api/runs/{run_id}/case-reviews", json={"case_key": "casa", "output_dir": "arbitrary"}).status_code == 422
    tampered = {"case_key": "casa", "mode": "deterministic", "packet": {"amount": "0.01", "recipient": "Orbe"}}
    assert client.post(f"/api/runs/{run_id}/case-reviews", json=tampered).status_code == 422
    assert client.post(f"/api/runs/{run_id}/case-reviews", json={"case_key": "casa", "amount": "0.01", "recipient": "Orbe"}).status_code == 422
    assert client.post(f"/api/runs/{run_id}/case-reviews", json={"case_key": "casa", "mode": "replay"}).status_code == 422


def test_case_packet_version_mismatch_fails_before_enqueue(running):
    client, app, _, _ = running
    run_id = client.post("/api/runs", json={}).json()["run_id"]
    wait(client, "/api/runs/" + run_id)
    output = Path(app.state.store.get(run_id)["payload"]["output_dir"])
    target = output / "pendencias.csv"
    target.write_bytes(target.read_bytes() + b"\n")
    response = client.get(f"/api/runs/{run_id}/cases/casa")
    assert response.status_code == 409 and response.json()["error"]["code"] == "CASE_PACKET_INVALID"
    assert client.post(f"/api/runs/{run_id}/case-reviews", json={"case_key": "casa"}).status_code == 409


def prepare_without_worker(tmp_path):
    settings = Settings(ROOT, ROOT / "contexto/data_pack", tmp_path, api_token=TOKEN, job_timeout=30)
    app = create_app(settings, start_worker=False)
    run_id = str(uuid4())
    output = settings.state_dir / "runs" / run_id
    result = run_close(str(settings.input_dir), str(output))
    store = app.state.store
    store.enqueue("close", "2026-09", {"output_dir": str(output)}, run_id=run_id)
    store.claim()
    store.finish(run_id, "pending_review", result=result)
    return settings, app, run_id, output


def test_snapshot_change_while_queued_fails_closed(tmp_path):
    settings, app, run_id, output = prepare_without_worker(tmp_path)
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + TOKEN
        review_id = client.post(f"/api/runs/{run_id}/case-reviews", json={"case_key": "casa"}).json()["review_id"]
        queued = client.get("/api/case-reviews/" + review_id).json()
        assert queued["status"] == "queued" and queued["result"] is None
        target = output / "divergencias_taxa.csv"
        target.write_bytes(target.read_bytes() + b"\n")
        worker = Worker(app.state.store, settings)
        worker.start()
        try:
            result = wait(client, "/api/case-reviews/" + review_id)
            assert result["status"] == "failed"
            assert result["result"]["status"] == "failed"
            assert result["result"]["integration_allowed"] is False
            assert result["result"]["approved"] is False
        finally:
            worker.stop()


def test_case_cancel_and_run_not_ready(tmp_path):
    settings, app, run_id, _ = prepare_without_worker(tmp_path)
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + TOKEN
        created = client.post(f"/api/runs/{run_id}/case-reviews", json={"case_key": "atlas"}).json()
        review_id = created["review_id"]
        cancelled = client.post(f"/api/case-reviews/{review_id}/cancel").json()
        assert cancelled["status"] == "cancelled" and cancelled["result"] is None
        incomplete = client.post("/api/runs", json={}).json()["run_id"]
        assert client.get(f"/api/runs/{incomplete}/cases/casa").status_code == 409


def test_cases_llm_without_configuration_keeps_packet_and_no_fake_roles(running, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    client, _, _, run_id = running
    review_id = client.post(f"/api/runs/{run_id}/case-reviews", json={"case_key": "atlas", "mode": "llm"}).json()["review_id"]
    result = wait(client, "/api/case-reviews/" + review_id)
    assert result["status"] == "pending_review"
    assert result["result"]["status"] == "needs_evidence"
    assert result["result"]["model_called"] is False
    assert result["result"]["roles"] == []
    assert result["result"]["packet"]["amount"] is None


def test_llm_case_factory_creates_distinct_role_adapters(monkeypatch):
    from tarvo.agents import case_review, openai_transport
    created = []

    def factory():
        def adapter(request):
            raise AssertionError("No model should be called in this unit test")
        created.append(adapter)
        return adapter

    def check_review(packet, context):
        first = context["case_adapter_factory"]("investigator")
        second = context["case_adapter_factory"]("critic")
        assert first is not second
        assert context["output_dir"] == "trusted-server-path"
        return {"status": "needs_evidence", "approved": False}

    monkeypatch.setattr(openai_transport, "create_openai_adapter", factory)
    monkeypatch.setattr(case_review, "review_case", check_review)
    result = case_review_adapter({"packet": {}, "run_context": {"mode": "llm", "output_dir": "trusted-server-path"}})
    assert result["status"] == "needs_evidence" and len(created) == 2


def test_event_migration_and_nested_role_parent_chain(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT NOT NULL,event TEXT NOT NULL)")
        db.execute("INSERT INTO events(run_id,event) VALUES ('old','{}')")
    store = Store(path)
    job = store.enqueue("case_review", "2026-09", {}, run_id="api-run")
    store.append_events(job, [
        {"type": "task.started", "status": "running", "task_id": "internal-review", "parent_task_id": job["id"]},
        {"type": "task.started", "status": "running", "task_id": "investigator-task", "parent_task_id": "internal-review"},
        {"type": "task.completed", "status": "completed", "task_id": "critic-task", "parent_task_id": "internal-review"},
    ])
    events = store.job_events(job["id"])["events"]
    assert [e.get("parent_task_id") for e in events[1:]] == [job["id"], "internal-review", "internal-review"]
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT event FROM events WHERE run_id='old'").fetchone()[0] == "{}"
