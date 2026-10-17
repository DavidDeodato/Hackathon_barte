"""One durable queue consumer; subprocesses allow actual timeout/cancellation.

Only one uvicorn worker may own a state directory. OS lock fails closed if a
second server attempts to process the same ledger. SQLite keeps queued work;
interrupted work is surfaced, never silently retried.
"""
import json
import logging
import multiprocessing
import os
from pathlib import Path
import threading
import time

logger = logging.getLogger("tarvo.api")


class FinancialInputError(Exception):
    def __init__(self, message):
        self.public_message = message


def finance_adapter(payload):
    from tarvo.finance import run_close
    try:
        kwargs = {"input_files": payload["input_files"]} if payload.get("input_files") is not None else {}
        result = run_close(payload["input_dir"], payload["output_dir"], payload["period"], **kwargs)
    except ValueError as exc:
        value = str(exc)
        allowed = ("Competência inválida", "Conjunto incompleto", "Conjunto incompatível", "Sem registros para a competência",
                   "Nome de documento inválido", "Documento selecionado", "Tipo de documento incompatível",
                   "Um mesmo documento", "O arquivo de ajustes", "O ajuste anunciado", "Identificador Orbe conflitante")
        message = value[:700] if value.startswith(allowed) else "Não foi possível processar este conjunto. Confira a competência, os tipos e a integridade dos arquivos enviados."
        raise FinancialInputError(message) from None
    if payload.get("batch_id"):
        result.update(batch_id=payload["batch_id"], selection_id=payload.get("selection_id"), source_documents=payload.get("source_documents", []))
    return result


def intelligence_adapter(payload):
    from tarvo.agents.service import investigate
    run_context = dict(payload["run_context"])
    if run_context.get("mode") == "llm":
        from tarvo.agents.openai_transport import create_openai_adapter
        run_context["model_adapter"] = create_openai_adapter()
    return investigate(payload["question"], run_context)


def comparison_adapter(payload):
    from tarvo.finance.compare import compare_runs
    return compare_runs(payload["before_dir"], payload["after_dir"])


def case_review_adapter(payload):
    from tarvo.agents.case_review import review_case
    run_context = dict(payload["run_context"])
    if run_context.get("mode") == "llm":
        from tarvo.agents.openai_transport import create_openai_adapter

        def role_factory(role):
            # A fresh transport/history per role; never serialize callables or
            # accept a provider factory/configuration from public HTTP input.
            return create_openai_adapter()

        run_context["case_adapter_factory"] = role_factory
    return review_case(payload["packet"], run_context)


def child_main(send, adapter, payload):
    try:
        result = adapter(payload)
        if not isinstance(result, dict):
            raise TypeError("Adapter must return an object")
        # Serialize before crossing the process boundary; no opaque objects.
        send.send((True, json.loads(json.dumps(result, ensure_ascii=False, allow_nan=False))))
    except FinancialInputError as exc:
        send.send((False, {"code": "FINANCIAL_INPUT_REJECTED", "message": exc.public_message}))
    except BaseException as exc:
        # Exception text and traceback can contain credentials or source data.
        send.send((False, {"code": "ADAPTER_FAILED", "message": "Módulo não concluiu a execução.", "exception_type": type(exc).__name__}))
    finally:
        send.close()


class StateLock:
    def __init__(self, path):
        self.path = path
        self.file = None

    def acquire(self):
        self.file = open(self.path, "a+b")
        self.file.seek(0)
        self.file.write(b"0")
        self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            self.file = None
            raise RuntimeError("State directory already has an API worker") from None

    def release(self):
        if self.file is not None:
            self.file.close()
            self.file = None


class Worker:
    def __init__(self, store, settings, close_adapter=finance_adapter, investigate_adapter=intelligence_adapter, compare_adapter=comparison_adapter, review_adapter=case_review_adapter):
        self.store = store
        self.settings = settings
        self.close_adapter = close_adapter
        self.investigate_adapter = investigate_adapter
        self.compare_adapter = compare_adapter
        self.review_adapter = review_adapter
        self.stop_event = threading.Event()
        self.thread = None
        self.lock = StateLock(settings.state_dir / "worker.lock")

    def start(self):
        self.lock.acquire()
        self.store.recover_interrupted()
        self.thread = threading.Thread(target=self.loop, name="tarvo-queue", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)
        self.lock.release()

    def loop(self):
        while not self.stop_event.is_set():
            try:
                job = self.store.claim()
                if job is None:
                    self.stop_event.wait(.1)
                else:
                    self.execute(job)
            except Exception as exc:
                logger.error("queue_error type=%s", type(exc).__name__)
                self.stop_event.wait(.2)

    def execute(self, job):
        adapter = {"close": self.close_adapter, "investigation": self.investigate_adapter, "comparison": self.compare_adapter, "case_review": self.review_adapter}[job["kind"]]
        payload = dict(job["payload"])
        if job["kind"] == "case_review":
            payload["run_context"] = {**payload["run_context"], "parent_task_id": job["id"]}
        if job["kind"] == "close":
            Path(payload["output_dir"]).mkdir(parents=True, exist_ok=True)
        context = multiprocessing.get_context("spawn")
        receive, send = context.Pipe(duplex=False)
        process = context.Process(target=child_main, args=(send, adapter, payload), daemon=True)
        try:
            process.start()
            send.close()
            deadline = time.monotonic() + self.settings.job_timeout
            while True:
                current = self.store.get(job["id"])
                if self.stop_event.is_set():
                    self.store.finish(job["id"], "interrupted", error={"code": "WORKER_INTERRUPTED", "message": "Servidor parado durante a execução."})
                    break
                if current["cancel_requested"]:
                    self.store.finish(job["id"], "cancelled", error={"code": "CANCELLED", "message": "Execução cancelada pelo operador."})
                    break
                if time.monotonic() >= deadline:
                    self.store.finish(job["id"], "timed_out", error={"code": "TIMEOUT", "message": "Tempo máximo de execução excedido."})
                    break
                if receive.poll(.05):
                    try:
                        ok, result = receive.recv()
                    except EOFError:
                        ok, result = False, {"code": "WORKER_EXITED", "message": "Processo terminou sem resultado."}
                    if ok:
                        if job["kind"] in {"investigation", "case_review"}:
                            self.store.append_events(job, result.get("events", []))
                        status = result.get("status", "pending_review" if job["kind"] == "close" else "completed")
                        if status in {"needs_review", "review_required", "needs_evidence"}:
                            status = "pending_review"
                        allowed = {"completed", "pending_review", "blocked", "unavailable", "failed", "replay"}
                        if status not in allowed:
                            self.store.finish(job["id"], "failed", error={"code": "INVALID_ADAPTER_STATUS", "message": "Módulo retornou estado fora do contrato."})
                            break
                        self.store.finish(job["id"], status, result=result)
                    else:
                        logger.warning("adapter_failed task=%s code=%s", job["id"], result["code"])
                        self.store.finish(job["id"], "failed", error=result)
                    break
                if not process.is_alive():
                    self.store.finish(job["id"], "failed", error={"code": "WORKER_EXITED", "message": "Processo terminou sem resultado."})
                    break
        except Exception as exc:
            logger.error("worker_failed task=%s type=%s", job["id"], type(exc).__name__)
            self.store.finish(job["id"], "failed", error={"code": "WORKER_FAILED", "message": "Falha na inicialização ou execução do worker."})
        finally:
            if process.is_alive():
                process.terminate()
            if process.pid is not None:
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=2)
            receive.close()
            send.close()
