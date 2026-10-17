"""Read-only HTTP probe against API-owned server. Writes only QA artifacts."""
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from audit_outputs import audit_directory

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/agent/branches/QA/artifacts"
BASE = "http://127.0.0.1:8000"
RUN = "5d9cd7ef-9f3c-47e7-8dcc-81045bfab964"


def get(path, headers=None):
    try:
        response = urlopen(Request(BASE + path, headers=headers or {}), timeout=10)
    except HTTPError as error:
        response = error
    body = response.read()
    return response.status, dict(response.headers), body


def run():
    checks, records = {}, {}
    for key, path, expected in [("health", "/api/health", 200), ("runs", "/api/runs", 200),
                                ("run", f"/api/runs/{RUN}", 200), ("events", f"/api/runs/{RUN}/events?after=0", 200),
                                ("outputs", f"/api/runs/{RUN}/outputs", 200), ("unknown", "/api/runs/unknown-qa", 404),
                                ("bad_cursor", f"/api/runs/{RUN}/events?after=-1", 422),
                                ("unknown_output", f"/api/runs/{RUN}/outputs/not-an-output.csv", 404)]:
        status, headers, body = get(path)
        data = json.loads(body)
        records[key] = {"status": status, "body": data}
        checks[key] = status == expected
        if expected >= 400:
            checks[key + "_error_contract"] = set(data) == {"error"} and {"code", "message"} <= set(data["error"])
    events = records["events"]["body"]["items"]
    checks["event_contract"] = all({"id", "run_id", "task_id", "timestamp", "actor", "type", "status", "summary", "evidence_refs"} <= set(e) for e in events)
    checks["event_run_identity"] = all(e["run_id"] == RUN for e in events)
    if events:
        cursor = max(e["cursor"] for e in events)
        status, _, body = get(f"/api/runs/{RUN}/events?after={cursor}")
        empty_events = json.loads(body)
        checks["event_incremental_no_repeat"] = status == 200 and not empty_events["items"]
        records["event_after_last"] = empty_events
    folder = OUT / "http_downloads"
    folder.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for item in records["outputs"]["body"]["items"]:
        name = item["name"]
        if not name.endswith(".csv") or Path(name).name != name:
            continue
        status, headers, body = get(f"/api/runs/{RUN}/outputs/{name}")
        checks["download_" + name] = status == 200 and "attachment" in headers.get("Content-Disposition", headers.get("content-disposition", ""))
        (folder / name).write_bytes(body)
        hashes[name] = hashlib.sha256(body).hexdigest()
    audit = audit_directory(folder)
    checks["downloaded_financial_audit"] = audit["status"] == "pass_with_limits"
    for label, origin in [("allowed", "http://127.0.0.1:5173"), ("unlisted", "https://qa-unlisted.invalid")]:
        status, headers, _ = get("/api/health", {"Origin": origin})
        allowed = headers.get("Access-Control-Allow-Origin", headers.get("access-control-allow-origin"))
        checks["cors_" + label] = allowed == origin if label == "allowed" else allowed is None
    report = {"base_url": BASE, "run_id": RUN, "scope": "GET only; no auth/remote access/restart/persistence/cloud or LLM execution certified", "checks": checks, "records": records, "download_hashes": hashes, "financial_audit": audit}
    (OUT / "http_probe_001.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checks": checks, "financial_audit": {"status": audit["status"], "checks": audit["checks"]}}, ensure_ascii=False))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(run())
