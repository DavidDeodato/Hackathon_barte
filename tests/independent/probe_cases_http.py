"""Independent R010 cases HTTP probe; deterministic only against local API.

No paths/packet/adapters are accepted from the client. No paid provider call.
"""
import hashlib
import json
import time
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/agent/branches/QA/artifacts/cases_http_r010"
BASE = "http://127.0.0.1:8000"
RUN = "3c0bd187-5f20-4223-9399-d1ab32aa55a1"


def request(path, data=None):
    raw = json.dumps(data).encode() if data is not None else None
    try:
        response = urlopen(Request(BASE + path, data=raw, headers={"Content-Type": "application/json"} if raw else {}), timeout=15)
    except HTTPError as error:
        response = error
    return response.status, json.loads(response.read())


def code_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ["src/tarvo/api/main.py", "src/tarvo/api/worker.py", "src/tarvo/agents/case_review.py", "src/tarvo/finance/cases.py"]}


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads((ROOT / "docs/agent/branches/QA/artifacts/cases_001/proof.json").read_text(encoding="utf-8"))
    starts = code_hashes()
    checks, observed, packets = {}, {}, {}
    status, health = request("/api/health")
    checks["health_identity"] = status == 200 and health.get("service") == "tarvo-api"
    for key in ["casa", "mundo", "atlas", "rota"]:
        status, data = request(f"/api/runs/{RUN}/cases/{key}")
        packets[key] = data["packet"]
        packet = data["packet"]
        checks[key + "_get_envelope"] = status == 200 and data["run_id"] == RUN and data["case_key"] == key
        checks[key + "_origin_set"] = {row["ref_origem"] for row in packet["rows"]} == set(reference["expected"]["refs"][key])
        expected = None if key == "atlas" else reference["expected"]["amounts_brl"][key]
        # Decimal formatting only; values remain API strings/null, never float.
        checks[key + "_amount"] = packet["amount"] == expected if key == "atlas" else str(packet["amount"]) == f'{Decimal(expected):.2f}'
        checks[key + "_no_financial_approval"] = packet["status"] == "prepared_for_review" and packet["sent"] is False and packet["approved"] is False
        checks[key + "_snapshot"] = packet["snapshot"] == reference["before_hashes"]
        observed[key] = {"packet": packet}
    # Reject financial/config input before it can enqueue or reach INT.
    for field, value in {"packet": {"amount": "0"}, "amount": "0", "recipient": "Orbe", "output_dir": "QA-forbidden", "prompt": "QA untrusted", "investigator_adapter": "QA-untrusted"}.items():
        status, data = request(f"/api/runs/{RUN}/case-reviews", {"case_key": "casa", "mode": "deterministic", field: value})
        checks["reject_client_" + field] = status == 422 and "error" in data
    for key, path, expected in [
        ("unknown_run", "/api/runs/QA-NO-SUCH-RUN/cases/casa", 404),
        ("unknown_case", f"/api/runs/{RUN}/cases/QA-NO-SUCH-CASE", 422),
        ("unknown_review", "/api/case-reviews/QA-NO-SUCH-REVIEW", 404),
        ("unknown_review_events", "/api/case-reviews/QA-NO-SUCH-REVIEW/events", 404),
    ]:
        status, data = request(path)
        checks[key] = status == expected and {"code", "message"} <= set(data.get("error", {}))
    # Server is confirmed locally accessible without bearer, so LLM auth gate must refuse before enqueue/provider.
    status, denied = request(f"/api/runs/{RUN}/case-reviews", {"case_key": "casa", "mode": "llm"})
    checks["llm_unsigned_rejected_before_job"] = status == 403 and denied.get("error", {}).get("code") == "LLM_AUTH_REQUIRED" and "review_id" not in denied
    for key in ["casa", "atlas", "mundo"]:
        before_packet = packets[key]
        status, created = request(f"/api/runs/{RUN}/case-reviews", {"case_key": key, "mode": "deterministic"})
        iid = created["review_id"]
        checks[key + "_async202"] = status == 202 and created["status"] in {"queued", "running"} and created["run_id"] == RUN and created["case_key"] == key
        deadline = time.monotonic() + 50
        states = []
        while time.monotonic() < deadline:
            status, result = request("/api/case-reviews/" + iid)
            states.append(result["status"])
            if result["status"] not in {"queued", "running"}:
                break
            time.sleep(0.25)
        observed[key].update(review_id=iid, states=states, result=result)
        checks[key + "_terminal_pending_review"] = status == 200 and result["status"] == "pending_review" and result["result"]["status"] == "review_required"
        checks[key + "_canonical_result_packet"] = result["result"]["packet"] == before_packet
        checks[key + "_roles_not_executed"] = not result["result"]["model_called"] and len(result["result"]["roles"]) == 2 and all(not role["executed"] and role["status"] == "not_executed" for role in result["result"]["roles"])
        checks[key + "_still_not_approved"] = not result["result"]["approved"] and not result["result"]["applied_to_calculation"]
        status, events = request("/api/case-reviews/" + iid + "/events")
        observed[key]["events"] = events
        rows = events.get("events", [])
        required = {"id", "run_id", "task_id", "timestamp", "actor", "type", "status", "summary", "evidence_refs"}
        checks[key + "_events_contract"] = status == 200 and bool(rows) and all(required <= set(event) and event["run_id"] == RUN for event in rows)
        task_ids = {row["task_id"] for row in rows} | {iid, RUN}
        checks[key + "_parent_links"] = all(row.get("parent_task_id") in task_ids for row in rows if row.get("parent_task_id"))
        if rows:
            last = max(row["cursor"] for row in rows)
            status, next_events = request(f"/api/case-reviews/{iid}/events?after={last}")
            checks[key + "_events_incremental"] = status == 200 and next_events.get("events") == []
        status, bad = request(f"/api/case-reviews/{iid}/events?after=-1")
        checks[key + "_cursor_validation"] = status == 422 and "error" in bad
        _, repeated = request("/api/case-reviews/" + iid)
        checks[key + "_result_repeatable"] = repeated == result
        _, current_packet = request(f"/api/runs/{RUN}/cases/{key}")
        checks[key + "_packet_still_immutable"] = current_packet["packet"] == before_packet
    ends = code_hashes()
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "scope": "real local HTTP, no new close, deterministic case reviews; unsigned LLM refused", "base_url": BASE, "run_id": RUN,
              "checks": checks, "observed": observed, "start_code_sha256": starts, "end_code_sha256": ends, "code_changed_during_probe": starts != ends,
              "limits": ["No protected-token auth/restart/cloud claim from this localhost probe; producer's isolated auth smoke is separate.", "No mutation of API-owned outputs to simulate stale source; module-level stale/missing guards were independently tested.", "No real assisted model call or semantic-quality acceptance; live001 was rejected separately."]}
    (OUT / "probe_001.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checks": checks, "code_changed_during_probe": starts != ends, "reviews": {key: value.get("review_id") for key, value in observed.items()}}, ensure_ascii=False))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(run())
