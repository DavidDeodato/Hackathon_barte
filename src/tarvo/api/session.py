"""Same-origin, revocable HttpOnly sessions; technical bearer remains optional.

Only hashes/expiry persist in SQLite. Neither the bearer nor opaque cookie is
returned in JSON. Shared access is not individual financial approval/audit.
"""
from datetime import datetime, timezone
import hashlib
import hmac
import re
import secrets
import time


class SessionError(Exception):
    def __init__(self, code, message, status):
        self.code, self.message, self.status = code, message, status


class SessionManager:
    def __init__(self, store, settings):
        self.store, self.settings = store, settings
        self.cookie_name = "__Host-lastro_session" if settings.production else "lastro_session"
        self.required = bool(settings.api_token or settings.access_password or settings.production)
        self.auth_version = hmac.new((settings.api_token or "local-session").encode(),
                                     ("access-v1:" + settings.access_password).encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def token_hash(value):
        return hashlib.sha256(value.encode()).hexdigest()

    def bearer_valid(self, request):
        given = request.headers.get("authorization", "")
        return bool(self.settings.api_token) and hmac.compare_digest(given.encode(), ("Bearer " + self.settings.api_token).encode())

    def cookie_session(self, request):
        if not self.settings.access_password:
            return None
        value = request.cookies.get(self.cookie_name, "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", value):
            return None
        return self.store.session(self.token_hash(value), self.auth_version, int(time.time()))

    def check_origin(self, request):
        origin = request.headers.get("origin", "")
        scheme = "https" if self.settings.production else request.url.scheme
        allowed = {scheme + "://" + request.headers.get("host", "")}
        if not self.settings.production:
            allowed.update(self.settings.cors_origins)
        # Browsers include Origin on unsafe fetches. Local command-line use may
        # omit it; production cookie writes always require a matching origin.
        if origin not in allowed and (origin or self.settings.production):
            raise SessionError("ORIGIN_NOT_ALLOWED", "Origem da solicitação não autorizada.", 403)

    def authorize(self, request):
        if self.bearer_valid(request):
            return "bearer"
        if self.cookie_session(request):
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                self.check_origin(request)
            return "session"
        if self.required:
            raise SessionError("UNAUTHORIZED", "Entre com sua credencial de acesso para continuar.", 401)
        host = request.client.host if request.client else ""
        if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
            raise SessionError("LOCAL_ONLY", "Acesso remoto exige autenticação configurada.", 403)
        return "local"

    def info(self, request):
        session = self.cookie_session(request)
        bearer = self.bearer_valid(request)
        return {"authenticated": bool(session or bearer or not self.required), "required": self.required,
                "auth_method": "session" if session else "bearer" if bearer else "local" if not self.required else None,
                "expires_at": datetime.fromtimestamp(session["expires_at"], timezone.utc).isoformat() if session else None}

    def login(self, request, password):
        self.check_origin(request)
        if not self.settings.access_password:
            raise SessionError("ACCESS_NOT_CONFIGURED", "O acesso ainda não foi configurado. Consulte o responsável pelo ambiente.", 503)
        host = request.client.host if request.client else "unknown"
        key = hmac.new(self.auth_version.encode(), host.encode(), hashlib.sha256).hexdigest()
        now = int(time.time())
        if self.store.login_failures(key, now) >= 10:
            raise SessionError("LOGIN_RATE_LIMIT", "Muitas tentativas de acesso. Aguarde alguns minutos antes de tentar novamente.", 429)
        supplied = hashlib.sha256(password.encode()).digest()
        expected = hashlib.sha256(self.settings.access_password.encode()).digest()
        if not hmac.compare_digest(supplied, expected):
            self.store.record_login_failure(key, now)
            raise SessionError("INVALID_ACCESS", "Credencial de acesso inválida.", 401)
        self.store.clear_login_failures(key)
        cookie = secrets.token_urlsafe(32)
        self.store.create_session(self.token_hash(cookie), self.auth_version, now, self.settings.session_ttl)
        return cookie, {"authenticated": True, "required": True,
                        "expires_at": datetime.fromtimestamp(now + self.settings.session_ttl, timezone.utc).isoformat()}

    def logout(self, request):
        self.check_origin(request)
        value = request.cookies.get(self.cookie_name, "")
        if value:
            self.store.revoke_session(self.token_hash(value))
