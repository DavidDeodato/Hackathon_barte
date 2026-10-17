from contextlib import asynccontextmanager
import csv
import hmac
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException

from tarvo.storage import Store, QueueFull
from .config import Settings
from .worker import Worker, finance_adapter, intelligence_adapter, comparison_adapter, case_review_adapter


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: str = Field(default="2026-09", pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")


class InvestigationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=8000)
    mode: Literal["deterministic", "llm"] = "deterministic"


class ComparisonInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    before_run_id: str = Field(min_length=1, max_length=100)
    after_run_id: str = Field(min_length=1, max_length=100)


CaseKey = Literal["casa", "rota", "mundo", "atlas"]


class CaseReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_key: CaseKey
    mode: Literal["deterministic", "llm"] = "deterministic"


class APIError(Exception):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status


def public_run(job):
    result = job["result"] or {}
    return {"run_id": job["id"], "period": job["period"], "status": job["status"],
            "created_at": job["created_at"], "updated_at": job["updated_at"],
            "summary": result.get("summary", {}), "issues": result.get("issues", []),
            "outputs": [Path(p).name for p in result.get("outputs", [])], "error": job["error"]}


def create_app(settings=None, close_adapter=finance_adapter, investigate_adapter=intelligence_adapter, start_worker=True, compare_adapter=comparison_adapter, review_adapter=case_review_adapter):
    settings = settings or Settings.from_env()
    settings.validate()
    store = Store(settings.state_dir / "tarvo.sqlite3")
    worker = Worker(store, settings, close_adapter, investigate_adapter, compare_adapter, review_adapter)

    @asynccontextmanager
    async def lifespan(app):
        if start_worker:
            worker.start()
        try:
            yield
        finally:
            if start_worker:
                worker.stop()

    app = FastAPI(title="Tarvo fechamento", version="1.0.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store
    app.state.settings = settings
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                       allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])

    @app.exception_handler(APIError)
    async def error_handler(request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, exc):
        return JSONResponse({"error": {"code": "INVALID_REQUEST", "message": "Parâmetros inválidos; confira período, pergunta e campos permitidos."}}, status_code=422)

    @app.exception_handler(HTTPException)
    async def http_handler(request, exc):
        return JSONResponse({"error": {"code": "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR", "message": "Recurso não encontrado." if exc.status_code == 404 else "Requisição não permitida."}}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unexpected_handler(request, exc):
        return JSONResponse({"error": {"code": "INTERNAL_ERROR", "message": "Falha interna; consulte o operador."}}, status_code=500)

    def authenticated(request: Request):
        if settings.api_token:
            given = request.headers.get("authorization", "")
            expected = "Bearer " + settings.api_token
            if not hmac.compare_digest(given.encode(), expected.encode()):
                raise APIError("UNAUTHORIZED", "Autenticação necessária.", 401)
        else:
            host = request.client.host if request.client else ""
            if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
                raise APIError("LOCAL_ONLY", "Acesso remoto exige autenticação configurada.", 403)

    auth = [Depends(authenticated)]

    def get_run(run_id):
        job = store.get(run_id)
        if job is None or job["kind"] != "close":
            raise APIError("RUN_NOT_FOUND", "Fechamento não encontrado.", 404)
        return job

    def enqueue(*args, **kwargs):
        try:
            return store.enqueue(*args, max_pending=settings.max_pending, **kwargs)
        except QueueFull:
            raise APIError("QUEUE_FULL", "Fila cheia; aguarde uma execução terminar.", 429) from None

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "tarvo-api", "version": "1.0.0"}

    @app.get("/api/runs", dependencies=auth)
    def runs():
        return {"items": [public_run(j) for j in store.list_runs()], "next_cursor": None}

    @app.post("/api/runs", status_code=202, dependencies=auth)
    def create_run(body: RunInput):
        if not settings.input_dir.is_dir():
            raise APIError("INPUT_UNAVAILABLE", "Diretório de entradas confiáveis indisponível.", 503)
        from uuid import uuid4
        run_id = str(uuid4())
        job = enqueue("close", body.period,
                      {"input_dir": str(settings.input_dir), "output_dir": str(settings.state_dir / "runs" / run_id), "period": body.period}, run_id=run_id)
        # Store ID is authoritative; its internal run_id must match the output folder.
        return {"run_id": job["id"], "status": job["status"]}

    @app.get("/api/runs/{run_id}", dependencies=auth)
    def run(run_id: str):
        return public_run(get_run(run_id))

    @app.post("/api/runs/{run_id}/cancel", status_code=202, dependencies=auth)
    def cancel_run(run_id: str):
        get_run(run_id)
        job = store.cancel(run_id)
        return {"run_id": run_id, "status": job["status"], "cancel_requested": bool(job["cancel_requested"])}

    @app.get("/api/runs/{run_id}/events", dependencies=auth)
    def events(run_id: str, after: int = 0, limit: int = 100):
        get_run(run_id)
        if after < 0 or not 1 <= limit <= 500:
            raise APIError("INVALID_CURSOR", "Cursor ou limite inválido.", 422)
        return store.events(run_id, after, limit)

    def output_path(job, name):
        if not name or Path(name).name != name or "/" in name or "\\" in name:
            raise APIError("OUTPUT_NOT_FOUND", "Arquivo não encontrado.", 404)
        root = Path(job["payload"]["output_dir"]).resolve()
        allowed = (job["result"] or {}).get("outputs", [])
        for value in allowed:
            path = Path(value)
            path = path.resolve() if path.is_absolute() else (root / path).resolve()
            if path.name == name and path.is_relative_to(root) and path.is_file():
                return path
        raise APIError("OUTPUT_NOT_FOUND", "Arquivo não encontrado.", 404)

    @app.get("/api/runs/{run_id}/outputs", dependencies=auth)
    def outputs(run_id: str):
        job = get_run(run_id)
        items = []
        for name in public_run(job)["outputs"]:
            try:
                path = output_path(job, name)
            except APIError:
                continue
            item = {"name": name, "size_bytes": path.stat().st_size,
                    "url": f"/api/runs/{run_id}/outputs/{name}"}
            if path.suffix.lower() == ".csv":
                with path.open(encoding="utf-8-sig", newline="") as file:
                    reader = csv.DictReader(file, delimiter=";")
                    rows, total = [], 0
                    for row in reader:
                        if total < 100:
                            rows.append(row)
                        total += 1
                    item["preview"] = {"columns": reader.fieldnames or [], "rows": rows, "total_rows": total, "truncated": total > len(rows)}
            items.append(item)
        return {"items": items, "next_cursor": None}

    @app.get("/api/runs/{run_id}/outputs/{name}", dependencies=auth)
    def download(run_id: str, name: str):
        path = output_path(get_run(run_id), name)
        return FileResponse(path, filename=path.name, media_type="text/csv" if path.suffix.lower() == ".csv" else "application/octet-stream")

    @app.post("/api/runs/{run_id}/investigations", status_code=202, dependencies=auth)
    def investigation(run_id: str, body: InvestigationInput):
        job = get_run(run_id)
        if body.mode == "llm" and not settings.api_token:
            raise APIError("LLM_AUTH_REQUIRED", "Investigações com provedor exigem autenticação configurada no servidor.", 403)
        if job["status"] in {"queued", "running", "failed", "interrupted", "timed_out", "cancelled"}:
            raise APIError("RUN_NOT_READY", "Fechamento precisa de resultado antes da investigação.", 409)
        if not body.question.strip():
            raise APIError("INVALID_QUESTION", "Informe uma pergunta.", 422)
        result = job["result"] or {}
        context = {"project_root": str(settings.project_root), "output_dir": job["payload"]["output_dir"],
                   "run_id": run_id, "period": job["period"], "summary": result.get("summary", {}),
                   "issues": result.get("issues", []), "mode": body.mode}
        inv = enqueue("investigation", job["period"], {"question": body.question, "run_context": context}, run_id=run_id)
        return {"investigation_id": inv["id"], "run_id": run_id, "status": inv["status"]}

    @app.get("/api/runs/{run_id}/investigations/{investigation_id}", dependencies=auth)
    def investigation_result(run_id: str, investigation_id: str):
        get_run(run_id)
        inv = store.get(investigation_id)
        if inv is None or inv["kind"] != "investigation" or inv["run_id"] != run_id:
            raise APIError("INVESTIGATION_NOT_FOUND", "Investigação não encontrada.", 404)
        return {"investigation_id": inv["id"], "run_id": run_id, "status": inv["status"],
                "result": inv["result"], "error": inv["error"], "updated_at": inv["updated_at"]}

    def comparison_view(job):
        return {"comparison_id": job["id"], "before_run_id": job["payload"]["before_run_id"],
                "after_run_id": job["payload"]["after_run_id"], "status": job["status"],
                "result": job["result"], "error": job["error"], "updated_at": job["updated_at"]}

    def get_comparison(comparison_id):
        job = store.get(comparison_id)
        if job is None or job["kind"] != "comparison":
            raise APIError("COMPARISON_NOT_FOUND", "Comparação não encontrada.", 404)
        return job

    def comparable_run(run_id):
        job = get_run(run_id)
        if job["status"] not in {"pending_review", "completed"} or not (job["result"] or {}).get("outputs"):
            raise APIError("RUN_NOT_COMPARABLE", "Comparação exige execuções concluídas com arquivos de saída.", 409)
        # Resolve and contain all paths from trusted job state, never from HTTP.
        root = Path(job["payload"]["output_dir"]).resolve()
        if not root.is_relative_to((settings.state_dir / "runs").resolve()):
            raise APIError("RUN_NOT_COMPARABLE", "Diretório de saída inválido.", 409)
        for name in public_run(job)["outputs"]:
            output_path(job, name)
        return job

    @app.post("/api/comparisons", status_code=202, dependencies=auth)
    def create_comparison(body: ComparisonInput):
        before, after = comparable_run(body.before_run_id), comparable_run(body.after_run_id)
        job = enqueue("comparison", after["period"],
                      {"before_run_id": before["id"], "after_run_id": after["id"],
                       "before_dir": before["payload"]["output_dir"], "after_dir": after["payload"]["output_dir"]},
                      run_id=after["id"])
        return {"comparison_id": job["id"], "status": job["status"]}

    @app.get("/api/comparisons/{comparison_id}", dependencies=auth)
    def comparison_result(comparison_id: str):
        return comparison_view(get_comparison(comparison_id))

    @app.post("/api/comparisons/{comparison_id}/cancel", status_code=202, dependencies=auth)
    def cancel_comparison(comparison_id: str):
        get_comparison(comparison_id)
        return comparison_view(store.cancel(comparison_id))

    def case_packet(run_id, case_key):
        from tarvo.finance.cases import build_case_packet
        job = get_run(run_id)
        if job["status"] not in {"pending_review", "completed"} or not (job["result"] or {}).get("outputs"):
            raise APIError("RUN_NOT_READY", "Caso exige fechamento processado com arquivos de saída.", 409)
        root = Path(job["payload"]["output_dir"]).resolve()
        if not root.is_relative_to((settings.state_dir / "runs").resolve()):
            raise APIError("CASE_PACKET_INVALID", "Diretório de saída fora do escopo da execução.", 409)
        try:
            for name in public_run(job)["outputs"]:
                output_path(job, name)
            packet = build_case_packet(str(root), case_key)
        except (ValueError, FileNotFoundError, OSError, KeyError, APIError):
            raise APIError("CASE_PACKET_INVALID", "Pacote indisponível ou versão de saída inconsistente; revisar o fechamento.", 409) from None
        return job, packet

    @app.get("/api/runs/{run_id}/cases/{case_key}", dependencies=auth)
    def get_case_packet(run_id: str, case_key: CaseKey):
        _, packet = case_packet(run_id, case_key)
        return {"run_id": run_id, "case_key": case_key, "packet": packet}

    @app.post("/api/runs/{run_id}/case-reviews", status_code=202, dependencies=auth)
    def create_case_review(run_id: str, body: CaseReviewInput):
        if body.mode == "llm" and not settings.api_token:
            raise APIError("LLM_AUTH_REQUIRED", "Revisão assistida exige autenticação configurada no servidor.", 403)
        job, packet = case_packet(run_id, body.case_key)
        context = {"project_root": str(settings.project_root), "output_dir": job["payload"]["output_dir"],
                   "run_id": run_id, "period": job["period"], "mode": body.mode}
        review = enqueue("case_review", job["period"], {"case_key": body.case_key, "packet": packet, "run_context": context}, run_id=run_id)
        return {"review_id": review["id"], "run_id": run_id, "case_key": body.case_key, "status": review["status"]}

    def get_case_review(review_id):
        job = store.get(review_id)
        if job is None or job["kind"] != "case_review":
            raise APIError("CASE_REVIEW_NOT_FOUND", "Revisão de caso não encontrada.", 404)
        return job

    def review_view(job):
        return {"review_id": job["id"], "run_id": job["run_id"], "case_key": job["payload"]["case_key"],
                "status": job["status"], "result": job["result"], "error": job["error"]}

    @app.get("/api/case-reviews/{review_id}", dependencies=auth)
    def get_case_review_result(review_id: str):
        return review_view(get_case_review(review_id))

    @app.get("/api/case-reviews/{review_id}/events", dependencies=auth)
    def case_review_events(review_id: str, after: int = 0, limit: int = 100):
        get_case_review(review_id)
        if after < 0 or not 1 <= limit <= 500:
            raise APIError("INVALID_CURSOR", "Cursor ou limite inválido.", 422)
        return store.job_events(review_id, after, limit)

    @app.post("/api/case-reviews/{review_id}/cancel", status_code=202, dependencies=auth)
    def cancel_case_review(review_id: str):
        get_case_review(review_id)
        return review_view(store.cancel(review_id))

    # Optional compiled UI; API routes and their authentication stay first.
    # Only the build directory is served, never project sources or state.
    static_dir = settings.project_root / "web" / "dist"
    if (static_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")
    return app
