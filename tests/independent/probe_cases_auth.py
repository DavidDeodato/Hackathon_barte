"""Only new CASES auth routes, in isolated TestClient; never starts worker/provider."""
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fastapi.testclient import TestClient
from tarvo.api.main import create_app
from tarvo.api.config import Settings

OUT = ROOT / "docs/agent/branches/QA/artifacts/cases_http_r010"
state = OUT / ("auth_fixture_" + uuid4().hex[:8])
settings = Settings(project_root=ROOT, input_dir=ROOT / "contexto/data_pack", state_dir=state,
                    api_token="QA-PUBLIC-FIXTURE-NOT-A-CREDENTIAL", production=True)
app = create_app(settings=settings, start_worker=False)
checks = {}
routes = [
    ("packet", "GET", "/api/runs/QA-UNKNOWN/cases/casa", None),
    ("review_create", "POST", "/api/runs/QA-UNKNOWN/case-reviews", {"case_key": "casa", "mode": "deterministic"}),
    ("review_read", "GET", "/api/case-reviews/QA-UNKNOWN", None),
    ("review_events", "GET", "/api/case-reviews/QA-UNKNOWN/events", None),
    ("review_cancel", "POST", "/api/case-reviews/QA-UNKNOWN/cancel", None),
]
with TestClient(app) as client:
    checks["health_public_liveness_only"] = client.get("/api/health").status_code == 200
    for key, method, path, payload in routes:
        no_auth = client.request(method, path, json=payload)
        wrong_auth = client.request(method, path, json=payload, headers={"Authorization": "Bearer QA-WRONG-PUBLIC-FIXTURE"})
        valid = client.request(method, path, json=payload, headers={"Authorization": "Bearer " + settings.api_token})
        checks[key + "_unsigned401"] = no_auth.status_code == 401 and no_auth.json().get("error", {}).get("code") == "UNAUTHORIZED"
        checks[key + "_wrong401"] = wrong_auth.status_code == 401
        checks[key + "_authenticated_unknown404"] = valid.status_code == 404
result = {"kind": "isolated TestClient auth boundary; public fixture token, no worker/provider/network", "checks": checks,
          "limits": ["Not a hosted-service or actual credential test.", "No real packet returned in this auth fixture; canonical packets/HTTP processing were tested independently against localhost8000."]}
(OUT / "auth_002.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
raise SystemExit(0 if all(checks.values()) else 1)
