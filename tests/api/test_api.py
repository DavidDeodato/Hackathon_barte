"""API boundary tests. Stub arithmetic does not validate the financial motor."""
from dataclasses import replace
from pathlib import Path
import time

from fastapi.testclient import TestClient
import pytest

from tarvo.api.config import Settings
from tarvo.api.main import create_app
from tarvo.api.worker import StateLock
from tarvo.storage import Store, QueueFull


def fake_close(payload):
    out = Path(payload["output_dir"])
    (out / "comissoes.csv").write_text("id_saida;comissao_brl\nTEST;1.25\n", encoding="utf-8")
    return {"status": "pending_review", "summary": {"test_only": "1.25"}, "issues": [], "outputs": [str(out / "comissoes.csv")]}


def fake_investigate(payload):
    return {"status": "completed", "answer": "Deterministic test adapter", "evidence": [],
            "proposed_changes": [], "events": [{"type": "tool.called", "status": "completed", "actor": "test", "task_id": "observed-child-task", "summary": "fixture read", "evidence_refs": []}], "limitations": ["Fixture, not an LLM"]}


def slow_close(payload):
    time.sleep(10)
    return {"status": "pending_review"}


def failing_close(payload):
    raise ValueError("SENSITIVE_ERROR_DETAIL_MUST_NOT_LEAK")


def fake_compare(payload):
    before = (Path(payload["before_dir"]) / "comissoes.csv").read_text(encoding="utf-8")
    after = (Path(payload["after_dir"]) / "comissoes.csv").read_text(encoding="utf-8")
    assert before == after
    return {"status": "completed", "before_run_id": "test-manifest-before", "after_run_id": "test-manifest-after",
            "input_changes": [], "outputs": [{"name": "comissoes.csv", "added": [], "removed": [], "changed": [], "unchanged_count": 1}],
            "limitations": ["Adapter fixture, not finance validation"]}


def needs_review_investigation(payload):
    return {"status": "needs_review", "answer": "Proposta requer revisão", "proposed_changes": [{"impact_brl": None, "applied_to_calculation": False}],
            "tool_errors": [{"tool": "search_rules", "code": "invalid_as_of"}],
            "events": [{"type": "tool.called", "status": "failed", "actor": "INT", "task_id": "test-recovery", "summary": "search_rules invalid_as_of"}]}


def unknown_status_close(payload):
    return {"status": "unexpected_status"}


@pytest.fixture
def settings(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    return Settings(tmp_path, inputs, tmp_path / "state", job_timeout=15)


def wait_result(client, url, terminal=None, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(url)
        assert response.status_code == 200, response.text
        result = response.json()
        if result["status"] not in {"queued", "running"}:
            if terminal:
                assert result["status"] == terminal, result
            return result
        time.sleep(.05)
    pytest.fail("Worker did not finish within test deadline")


def test_end_to_end_persistence_events_outputs_and_investigation(settings):
    app = create_app(settings, close_adapter=fake_close, investigate_adapter=fake_investigate)
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        response = client.post("/api/runs", json={"period": "2026-09"})
        assert response.status_code == 202
        run_id = response.json()["run_id"]
        url = "/api/runs/" + run_id
        detail = wait_result(client, url, "pending_review")
        assert detail["summary"] == {"test_only": "1.25"}
        assert detail["outputs"] == ["comissoes.csv"]
        events = client.get(url + "/events").json()
        types = [e["type"] for e in events["items"]]
        assert types == ["task.created", "task.started", "task.completed", "review.required"]
        assert all(e["run_id"] == run_id for e in events["items"])
        assert client.get(url + f"/events?after={events['next_cursor']}").json()["items"] == []
        output = client.get(url + "/outputs").json()["items"][0]
        assert output["preview"]["rows"] == [{"id_saida": "TEST", "comissao_brl": "1.25"}]
        assert client.get(output["url"]).status_code == 200
        inv = client.post(url + "/investigations", json={"question": "Confira a fonte"})
        assert inv.status_code == 202
        inv_id = inv.json()["investigation_id"]
        result = wait_result(client, url + "/investigations/" + inv_id, "completed")
        assert result["result"]["limitations"] == ["Fixture, not an LLM"]
        tool_event = next(e for e in client.get(url + "/events").json()["items"] if e["type"] == "tool.called")
        assert tool_event["task_id"] == "observed-child-task"
        assert tool_event["parent_task_id"] == inv_id
    # Re-open the actual ledger; no process memory is used to recover this run.
    with TestClient(create_app(settings)) as client:
        restored = client.get(url).json()
        assert restored == detail
        assert client.get("/api/runs").json()["items"][0]["run_id"] == run_id


def test_auth_validation_and_cors(settings):
    app = create_app(replace(settings, production=True, api_token="test-only-token"), start_worker=False)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/runs").status_code == 401
        assert client.get("/api/runs", headers={"Authorization": "Bearer wrong"}).status_code == 401
        client.headers["Authorization"] = "Bearer test-only-token"
        assert client.get("/api/runs").status_code == 200
        bad = client.post("/api/runs", json={"period": "2026-99", "input_dir": "arbitrary"})
        assert bad.status_code == 422
        assert set(bad.json()) == {"error"}
        cors = client.options("/api/runs", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "Authorization"})
        assert cors.headers["access-control-allow-origin"] == "http://localhost:5173"
        denied = client.options("/api/runs", headers={"Origin": "https://untrusted.invalid", "Access-Control-Request-Method": "GET"})
        assert "access-control-allow-origin" not in denied.headers
    with pytest.raises(ValueError, match="TOKEN"):
        create_app(replace(settings, production=True))


def test_queue_bound_cancel_and_not_ready(settings):
    with TestClient(create_app(replace(settings, max_pending=1), start_worker=False)) as client:
        job = client.post("/api/runs", json={}).json()
        url = "/api/runs/" + job["run_id"]
        assert client.post("/api/runs", json={}).status_code == 429
        assert client.post(url + "/investigations", json={"question": "test"}).status_code == 409
        assert client.post(url + "/cancel").json()["status"] == "cancelled"
        assert client.post("/api/runs", json={}).status_code == 202
        assert client.get("/api/runs/missing").json()["error"]["code"] == "RUN_NOT_FOUND"


def test_timeout_kills_child_and_preserves_event(settings):
    with TestClient(create_app(replace(settings, job_timeout=.5), close_adapter=slow_close)) as client:
        run_id = client.post("/api/runs", json={}).json()["run_id"]
        result = wait_result(client, "/api/runs/" + run_id, "timed_out")
        assert result["error"]["code"] == "TIMEOUT"
        assert client.get(f"/api/runs/{run_id}/outputs").json()["items"] == []


def test_running_cancel(settings):
    with TestClient(create_app(settings, close_adapter=slow_close)) as client:
        run_id = client.post("/api/runs", json={}).json()["run_id"]
        url = "/api/runs/" + run_id
        deadline = time.monotonic() + 5
        while client.get(url).json()["status"] != "running":
            assert time.monotonic() < deadline
            time.sleep(.05)
        assert client.post(url + "/cancel").json()["cancel_requested"] is True
        wait_result(client, url, "cancelled")


def test_adapter_failure_hides_exception_text(settings):
    with TestClient(create_app(settings, close_adapter=failing_close)) as client:
        run_id = client.post("/api/runs", json={}).json()["run_id"]
        result = wait_result(client, "/api/runs/" + run_id, "failed")
        assert result["error"]["code"] == "ADAPTER_FAILED"
        assert "SENSITIVE_ERROR_DETAIL" not in str(result)


def test_restart_and_single_worker_lock(settings):
    store = Store(settings.state_dir / "tarvo.sqlite3")
    queued = store.enqueue("close", "2026-09", {})
    store.claim()
    assert store.recover_interrupted() == 1
    assert store.get(queued["id"])["status"] == "interrupted"
    assert store.events(queued["id"])["items"][-1]["type"] == "task.failed"
    a, b = StateLock(settings.state_dir / "worker.lock"), StateLock(settings.state_dir / "worker.lock")
    a.acquire()
    try:
        with pytest.raises(RuntimeError, match="already"):
            b.acquire()
    finally:
        a.release()
    b.acquire()
    b.release()


def test_outputs_cannot_exfiltrate_outside_run_directory(settings):
    with TestClient(create_app(settings, start_worker=False)) as client:
        run_id = client.post("/api/runs", json={}).json()["run_id"]
        outside = settings.project_root / "outside.csv"
        outside.write_text("private", encoding="utf-8")
        app_store = client.app.state.store
        app_store.claim()
        app_store.finish(run_id, "pending_review", result={"outputs": [str(outside)]})
        assert client.get(f"/api/runs/{run_id}/outputs").json()["items"] == []
        assert client.get(f"/api/runs/{run_id}/outputs/outside.csv").status_code == 404


def test_remote_access_requires_token(settings):
    with TestClient(create_app(settings, start_worker=False), client=("192.0.2.1", 12345)) as client:
        assert client.get("/api/runs").status_code == 403


def test_unavailable_task_does_not_emit_completed_event(settings):
    store = Store(settings.state_dir / "tarvo.sqlite3")
    job = store.enqueue("close", "2026-09", {})
    store.claim()
    store.finish(job["id"], "unavailable", result={"status": "unavailable"})
    event = store.events(job["id"])["items"][-1]
    assert event["type"] == "review.required"
    assert event["status"] == "blocked"


def test_llm_mode_requires_server_auth_even_on_loopback(settings):
    with TestClient(create_app(settings, start_worker=False)) as client:
        run_id = client.post("/api/runs", json={}).json()["run_id"]
        store = client.app.state.store
        store.claim()
        store.finish(run_id, "pending_review", result={})
        result = client.post(f"/api/runs/{run_id}/investigations", json={"question": "test", "mode": "llm"})
        assert result.status_code == 403
        assert result.json()["error"]["code"] == "LLM_AUTH_REQUIRED"


def test_comparison_uses_known_run_dirs_and_persists(settings):
    app = create_app(settings, close_adapter=fake_close, compare_adapter=fake_compare)
    with TestClient(app) as client:
        ids = []
        for _ in range(2):
            run_id = client.post("/api/runs", json={}).json()["run_id"]
            wait_result(client, "/api/runs/" + run_id, "pending_review")
            ids.append(run_id)
        request = {"before_run_id": ids[0], "after_run_id": ids[1]}
        response = client.post("/api/comparisons", json=request)
        assert response.status_code == 202
        comparison_id = response.json()["comparison_id"]
        url = "/api/comparisons/" + comparison_id
        result = wait_result(client, url, "completed")
        assert result["before_run_id"] == ids[0] and result["after_run_id"] == ids[1]
        assert result["result"]["outputs"][0]["changed"] == []
        assert client.post("/api/comparisons", json={**request, "before_dir": "C:/private"}).status_code == 422
        assert client.post("/api/comparisons", json={**request, "after_run_id": "unknown"}).status_code == 404
        assert client.get("/api/comparisons/" + ids[0]).status_code == 404
    with TestClient(create_app(settings, start_worker=False)) as client:
        assert client.get(url).json() == result


def test_comparison_rejects_queued_runs(settings):
    with TestClient(create_app(settings, start_worker=False)) as client:
        run_id = client.post("/api/runs", json={}).json()["run_id"]
        response = client.post("/api/comparisons", json={"before_run_id": run_id, "after_run_id": run_id})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "RUN_NOT_COMPARABLE"


def test_real_int_transport_without_env_is_unavailable_no_fallback(settings, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    app = create_app(replace(settings, api_token="test-only-token"), close_adapter=fake_close)
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer test-only-token"
        run_id = client.post("/api/runs", json={}).json()["run_id"]
        url = "/api/runs/" + run_id
        wait_result(client, url, "pending_review")
        inv = client.post(url + "/investigations", json={"question": "Confira a fonte", "mode": "llm"}).json()
        result = wait_result(client, url + "/investigations/" + inv["investigation_id"], "unavailable")
        assert result["result"]["mode"] == "llm"
        assert result["result"]["model_called"] is False
        assert result["result"]["proposed_changes"] == []


def test_needs_review_remains_pending_not_completed(settings):
    with TestClient(create_app(settings, close_adapter=fake_close, investigate_adapter=needs_review_investigation)) as client:
        run_id = client.post("/api/runs", json={}).json()["run_id"]
        url = "/api/runs/" + run_id
        wait_result(client, url, "pending_review")
        inv = client.post(url + "/investigations", json={"question": "Regra proposta"}).json()
        result = wait_result(client, url + "/investigations/" + inv["investigation_id"], "pending_review")
        assert result["result"]["status"] == "needs_review"
        assert result["result"]["proposed_changes"][0]["applied_to_calculation"] is False
        assert result["result"]["tool_errors"] == [{"tool": "search_rules", "code": "invalid_as_of"}]
        events = client.get(url + "/events").json()["items"]
        assert events[-1]["type"] == "review.required"
        failed_tool = next(e for e in events if e["type"] == "tool.called" and e["status"] == "failed")
        assert failed_tool["parent_task_id"] == inv["investigation_id"]


def test_unknown_adapter_status_fails_without_inventing_completion(settings):
    with TestClient(create_app(settings, close_adapter=unknown_status_close)) as client:
        run_id = client.post("/api/runs", json={}).json()["run_id"]
        result = wait_result(client, "/api/runs/" + run_id, "failed")
        assert result["error"]["code"] == "INVALID_ADAPTER_STATUS"
