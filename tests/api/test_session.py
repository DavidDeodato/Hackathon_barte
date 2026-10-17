from dataclasses import replace
from pathlib import Path
import time

from fastapi.testclient import TestClient

from tarvo.api.config import Settings
from tarvo.api.main import create_app

ORIGIN = "https://app.test"


def settings(tmp_path):
    return Settings(tmp_path, tmp_path, tmp_path / "state", api_token="fixture-technical-key",
                    access_password="fixture-human-password", production=True)


def test_session_cookie_protected_access_restart_and_logout(tmp_path):
    config = settings(tmp_path)
    with TestClient(create_app(config, start_worker=False), base_url=ORIGIN) as client:
        assert client.get("/api/session").json()["authenticated"] is False
        assert client.get("/api/runs").status_code == 401
        assert client.post("/api/session", json={"password": "wrong"}, headers={"Origin": ORIGIN}).status_code == 401
        login = client.post("/api/session", json={"password": config.access_password}, headers={"Origin": ORIGIN})
        assert login.status_code == 200
        body = login.json()
        assert body["authenticated"] is True and body["required"] is True
        assert all(key not in body for key in ("token", "password", "api_token", "cookie"))
        header = login.headers["set-cookie"]
        assert "HttpOnly" in header and "Secure" in header and "SameSite=strict" in header
        assert "Domain=" not in header and "Path=/" in header
        assert client.get("/api/runs").status_code == 200
        assert client.get("/api/session").json()["auth_method"] == "session"
        cookie = client.cookies.get("__Host-lastro_session")
        raw_database = (config.state_dir / "tarvo.sqlite3").read_bytes()
        assert cookie.encode() not in raw_database
    with TestClient(create_app(config, start_worker=False), base_url=ORIGIN) as restored:
        restored.cookies.set("__Host-lastro_session", cookie, domain="app.test", path="/")
        assert restored.get("/api/runs").status_code == 200
        assert restored.delete("/api/session", headers={"Origin": ORIGIN}).status_code == 200
        restored.cookies.set("__Host-lastro_session", cookie, domain="app.test", path="/")
        assert restored.get("/api/runs").status_code == 401


def test_cookie_csrf_origin_and_bearer_compatibility(tmp_path):
    config = settings(tmp_path)
    with TestClient(create_app(config, start_worker=False), base_url=ORIGIN) as client:
        assert client.post("/api/session", json={"password": config.access_password}, headers={"Origin": "https://other.test"}).status_code == 403
        assert client.post("/api/session", json={"password": config.access_password}).status_code == 403
        client.post("/api/session", json={"password": config.access_password}, headers={"Origin": ORIGIN})
        assert client.post("/api/runs", json={}, headers={"Origin": "https://other.test"}).status_code == 403
        assert client.delete("/api/session", headers={"Origin": "null"}).status_code == 403
        assert client.get("/api/runs", headers={"Authorization": "Bearer " + config.api_token}).status_code == 200
        client.cookies.clear()
        assert client.post("/api/runs", json={}, headers={"Authorization": "Bearer " + config.api_token}).status_code == 202


def test_expiry_rotation_missing_configuration_and_rate_limit(tmp_path):
    config = settings(tmp_path)
    app = create_app(config, start_worker=False)
    with TestClient(app, base_url=ORIGIN) as client:
        client.post("/api/session", json={"password": config.access_password}, headers={"Origin": ORIGIN})
        cookie = client.cookies.get("__Host-lastro_session")
        with app.state.store.connect() as db:
            db.execute("UPDATE access_sessions SET expires_at=?", (int(time.time()) - 1,))
        assert client.get("/api/runs").status_code == 401
        for _ in range(10):
            assert client.post("/api/session", json={"password": "wrong"}, headers={"Origin": ORIGIN}).status_code == 401
        assert client.post("/api/session", json={"password": config.access_password}, headers={"Origin": ORIGIN}).status_code == 429
    with TestClient(create_app(replace(config, access_password="rotated-password"), start_worker=False), base_url=ORIGIN) as rotated:
        rotated.cookies.set("__Host-lastro_session", cookie, domain="app.test", path="/")
        assert rotated.get("/api/runs").status_code == 401
    with TestClient(create_app(replace(config, access_password=""), start_worker=False), base_url=ORIGIN) as missing:
        assert missing.post("/api/session", json={"password": "anything"}, headers={"Origin": ORIGIN}).status_code == 503


def test_local_open_and_vite_cookie_login(tmp_path):
    local = replace(settings(tmp_path), production=False, api_token="", access_password="")
    with TestClient(create_app(local, start_worker=False)) as client:
        assert client.get("/api/session").json()["required"] is False
        assert client.get("/api/session").json()["authenticated"] is True
    secured = replace(local, access_password="fixture-local-password")
    with TestClient(create_app(secured, start_worker=False), base_url="http://127.0.0.1:8000") as client:
        login = client.post("/api/session", json={"password": secured.access_password}, headers={"Origin": "http://127.0.0.1:5173"})
        assert login.status_code == 200 and "Secure" not in login.headers["set-cookie"]
        assert client.get("/api/runs").status_code == 200


def test_assistant_router_shares_session_and_origin_protection(tmp_path):
    config = settings(tmp_path)
    with TestClient(create_app(config, start_worker=False), base_url=ORIGIN) as client:
        assert client.get('/api/assistant/context').status_code == 401
        assert client.get('/api/assistant/conversations').status_code == 401
        assert client.post('/api/assistant/conversations', json={'period': '2099-01'}).status_code == 401
        client.post('/api/session', json={'password': config.access_password}, headers={'Origin': ORIGIN})
        assert client.get('/api/assistant/context').status_code == 200
        assert client.post('/api/assistant/conversations', json={'period': '2099-01'}, headers={'Origin': 'https://other.test'}).status_code == 403
        created = client.post('/api/assistant/conversations', json={'period': '2099-01'}, headers={'Origin': ORIGIN})
        assert created.status_code == 201
        assert client.get('/api/assistant/conversations/' + created.json()['id']).status_code == 200
