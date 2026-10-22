"""Single-writer research jobs; isolated JSON/HTML, never the trading database."""

from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import uuid

from catos.research_catalog import (
    MAX_OUTPUT_BYTES, MAX_RUNS, ROOT, TIMEOUT_SECONDS,
    json_text, provenance, validate_optimization_request, validate_request,
)


class ResearchError(Exception):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.status = status


def now():
    return datetime.now(timezone.utc).isoformat()


class ResearchService:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir).resolve()
        self._guard = threading.RLock()
        self._owner_file = None
        self._thread = None
        self._active = None
        self._closing = False

    def start(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        owner = open(self.output_dir / "writer.lock", "a+b")
        try:
            owner.seek(0, 2)
            if owner.tell() == 0:
                owner.write(b"0")
                owner.flush()
            owner.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(owner.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            owner.close()
            raise ResearchError("research_output_in_use", 409) from None
        self._owner_file = owner
        try:
            for status_file in self.output_dir.glob("*/status.json"):
                status = json.loads(status_file.read_text(encoding="utf-8"))
                if status["status"] in ("queued", "running"):
                    status.update(status="failed", error="interrupted_by_service_restart", finished_at=now())
                    self._write_status(status)
        except Exception:
            self.close()
            raise

    def close(self):
        with self._guard:
            self._closing = True
            thread = self._thread
        if thread:
            thread.join(TIMEOUT_SECONDS + 5)
        # Never hand the writer lock to another instance while a job still writes.
        if thread and thread.is_alive():
            raise ResearchError("research_shutdown_pending", 503)
        if self._owner_file:
            self._owner_file.close()
            self._owner_file = None

    @property
    def active_run(self):
        with self._guard:
            return self._active

    def _run_dir(self, run_id):
        if type(run_id) is not str or re.fullmatch(r"[0-9a-f]{32}", run_id) is None:
            raise ResearchError("invalid_run_id")
        directory = self.output_dir / run_id
        if not directory.is_dir():
            raise ResearchError("run_not_found", 404)
        return directory

    def _write_new(self, path, value):
        with open(path, "x", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())

    def _write_status(self, status):
        directory = self._run_dir(status["run_id"])
        pending = directory / f"status-{uuid.uuid4().hex}.tmp"
        self._write_new(pending, json_text(status))
        pending.replace(directory / "status.json")

    def list_runs(self):
        with self._guard:
            statuses = [json.loads(path.read_text(encoding="utf-8"))
                        for path in self.output_dir.glob("*/status.json")]
        return sorted(statuses, key=lambda item: item["created_at"], reverse=True)

    def task(self, run_id):
        with self._guard:
            return json.loads((self._run_dir(run_id) / "status.json").read_text(encoding="utf-8"))

    def result(self, run_id):
        if self.task(run_id)["status"] != "complete":
            raise ResearchError("result_not_complete", 409)
        return json.loads((self._run_dir(run_id) / "result.json").read_text(encoding="utf-8"))

    def report(self, run_id):
        if self.task(run_id)["status"] != "complete":
            raise ResearchError("result_not_complete", 409)
        return (self._run_dir(run_id) / "report.html").read_text(encoding="utf-8")

    def submit(self, request, build_id):
        snapshot, _, _, _ = validate_request(request)
        return self._submit(snapshot, build_id, "backtest")

    def submit_optimization(self, request, build_id):
        snapshot, _, _ = validate_optimization_request(request)
        return self._submit(snapshot, build_id, "optimization")

    def submit_validation(self, request, build_id):
        from catos.research_validation_job import validate_validation_request

        snapshot, *_ = validate_validation_request(request)
        return self._submit(snapshot, build_id, "validation")

    def _submit(self, snapshot, build_id, kind):
        with self._guard:
            if self._closing or self._owner_file is None:
                raise ResearchError("research_service_not_ready", 503)
            if self._active is not None:
                raise ResearchError("research_busy", 409)
            if len(list(self.output_dir.iterdir())) >= MAX_RUNS + 1:
                raise ResearchError("research_run_limit_reached", 409)
            run_id = uuid.uuid4().hex
            directory = self.output_dir / run_id
            directory.mkdir(exist_ok=False)
            source = provenance()
            envelope = {"run_id": run_id, "created_at": now(), "build_id": build_id,
                        "kind": kind, "request": snapshot, "provenance": source}
            self._write_new(directory / "request.json", json_text(envelope))
            status = {"run_id": run_id, "kind": kind, "status": "queued", "error": None,
                      "created_at": envelope["created_at"], "started_at": None,
                      "finished_at": None, "request": snapshot, "provenance": source,
                      "build_id": build_id}
            self._write_status(status)
            self._active = run_id
            self._thread = threading.Thread(target=self._execute, args=(envelope, status), daemon=False)
            self._thread.start()
            # A caller must not mutate the live task's request/provenance through
            # nested objects in the submission reply.
            return json.loads(json_text(status))

    def _compute(self, envelope):
        # Only benign OS bootstrap variables. No inherited API credentials, user
        # profile, proxy, Python hooks, clients, signer, or database write handle.
        environment = {key: os.environ[key] for key in ("SystemRoot", "WINDIR") if key in os.environ}
        if envelope.get("kind") in ("optimization", "validation"):
            import importlib.util

            packaging_spec = importlib.util.find_spec("packaging")
            if packaging_spec is None or packaging_spec.origin is None:
                raise ResearchError("optuna_dependency_packaging_missing")
            environment["CATOS_OPTUNA_PACKAGING"] = str(Path(packaging_spec.origin).resolve())
        process = subprocess.Popen(
            [sys.executable, "-B", "-s", "-m", "catos.research_worker"], cwd=ROOT,
            env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        chunks = {"stdout": bytearray(), "stderr": bytearray()}
        overflow = threading.Event()

        def drain(stream, name, limit):
            while True:
                block = stream.read(8192)
                if not block:
                    return
                room = limit - len(chunks[name])
                chunks[name].extend(block[:max(0, room)])
                if len(block) > room:
                    overflow.set()
                    try:
                        process.kill()
                    except OSError:
                        pass
                    return

        readers = [threading.Thread(target=drain, args=(process.stdout, "stdout", MAX_OUTPUT_BYTES)),
                   threading.Thread(target=drain, args=(process.stderr, "stderr", 65536))]
        for reader in readers:
            reader.start()
        try:
            process.stdin.write(json_text(envelope).encode("utf-8"))
            process.stdin.close()
            try:
                process.wait(timeout=TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise ResearchError("research_timeout") from None
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            for reader in readers:
                reader.join()
            process.stdout.close()
            process.stderr.close()
            if not process.stdin.closed:
                process.stdin.close()
        if overflow.is_set():
            raise ResearchError("research_output_limit")
        if process.returncode:
            raise ResearchError("research_worker_failed")
        reply = json.loads(chunks["stdout"].decode("utf-8"))
        if "error" in reply:
            raise ResearchError(reply["error"])
        if reply["payload"]["provenance"] != envelope["provenance"] or provenance() != envelope["provenance"]:
            raise ResearchError("source_changed_during_run")
        return reply

    def _execute(self, envelope, status):
        try:
            with self._guard:
                status.update(status="running", started_at=now())
                self._write_status(status)
            reply = self._compute(envelope)
            directory = self._run_dir(status["run_id"])
            payload = {**reply["payload"], "run_id": envelope["run_id"],
                       "created_at": envelope["created_at"], "build_id": envelope["build_id"]}
            self._write_new(directory / "result.json", json_text(payload))
            binding = html.escape(json_text(envelope))
            footer = ('<section style="margin:24px;overflow-wrap:anywhere">'
                      '<h2>固定研究來源 · 合成資料</h2>'
                      '<p>不代表歷史市場績效。此報告綁定以下任務、版本、資料與設定。</p>'
                      f'<pre style="white-space:pre-wrap">{binding}</pre></section>')
            report = reply["report"].replace("</body>", footer + "</body>")
            self._write_new(directory / "report.html", report)
            with self._guard:
                status.update(status="complete", finished_at=now())
                self._write_status(status)
        except Exception as error:
            with self._guard:
                status.update(status="failed", error=f"{type(error).__name__}: {error}", finished_at=now())
                self._write_status(status)
        finally:
            with self._guard:
                self._active = None
