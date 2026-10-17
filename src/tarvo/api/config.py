from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    input_dir: Path
    state_dir: Path
    api_token: str = ""
    production: bool = False
    cors_origins: tuple = ("http://localhost:5173", "http://127.0.0.1:5173")
    job_timeout: float = 180
    max_pending: int = 20
    access_password: str = ""
    session_ttl: int = 28800

    @classmethod
    def from_env(cls):
        root = Path(os.environ.get("TARVO_PROJECT_ROOT", Path(__file__).resolve().parents[3])).resolve()
        state = Path(os.environ.get("TARVO_STATE_DIR", root / "docs/agent/branches/API/artifacts/runtime")).resolve()
        return cls(project_root=root,
                   input_dir=Path(os.environ.get("TARVO_INPUT_DIR", root / "contexto/data_pack")).resolve(),
                   state_dir=state,
                   api_token=os.environ.get("TARVO_API_TOKEN", ""),
                   production=os.environ.get("TARVO_ENV", "local").lower() == "production",
                   cors_origins=tuple(x.strip() for x in os.environ.get("TARVO_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()),
                   job_timeout=float(os.environ.get("TARVO_JOB_TIMEOUT_SECONDS", "180")),
                   max_pending=int(os.environ.get("TARVO_MAX_PENDING", "20")),
                   access_password=os.environ.get("TARVO_ACCESS_PASSWORD", ""),
                   session_ttl=int(os.environ.get("TARVO_SESSION_TTL_SECONDS", "28800")))

    def validate(self):
        if self.production and not self.api_token:
            raise ValueError("TARVO_API_TOKEN is required in production")
        if self.job_timeout <= 0 or self.max_pending < 1:
            raise ValueError("Job timeout and queue capacity must be positive")
        if "*" in self.cors_origins:
            raise ValueError("Use explicit CORS origins")
        if not 300 <= self.session_ttl <= 86400:
            raise ValueError("Session TTL must be between five minutes and one day")
