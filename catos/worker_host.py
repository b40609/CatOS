"""Async owner of one data-only worker pipe, not a trading Supervisor yet."""

import asyncio
import math
import os
from pathlib import Path
import subprocess
import sys
import uuid

from catos import ipc

STDERR_LIMIT = 8192
STOP_TIMEOUT = 2


class WorkerError(RuntimeError):
    pass


def worker_environment():
    # Deliberately do not enumerate or copy the parent environment.
    return {name: os.environ[name] for name in ("SystemRoot", "WINDIR") if name in os.environ}


class WorkerHost:
    def __init__(self, bot_id, config, *, checkpoint=None, timeout=5):
        self.bot_id = ipc.token(bot_id, "bot_id")  # Bound to this pipe, never sent by the child.
        self.config = ipc.WorkerConfig.from_wire(config.to_wire())
        self.checkpoint = ipc.Checkpoint.from_wire(
            (checkpoint or ipc.Checkpoint(self.config)).to_wire(), self.config)
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise ValueError("timeout must be in (0, 60] seconds")
        self.timeout = timeout  # Scheduling duration only; never a financial Float.
        self.generation = uuid.uuid4().hex
        self.process = None
        self.failure = None
        self.stderr_tail = bytearray()
        self._tasks = []
        self._pending = None
        self._busy = False
        self._started = False
        self._closing = False

    async def _spawn(self):
        root = str(Path(__file__).resolve().parent.parent)
        bootstrap = f"import sys; sys.path.insert(0, {root!r}); from catos.worker import main; raise SystemExit(main())"
        return await asyncio.create_subprocess_exec(
            sys.executable, "-I", "-S", "-B", "-u", "-c", bootstrap,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, env=worker_environment(),
            close_fds=True, limit=ipc.MAX_FRAME,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)

    def _fail(self, reason):
        if self.failure is None:
            self.failure = str(reason)
        if self._pending is not None and not self._pending.done():
            self._pending.set_exception(WorkerError(self.failure))
        if self.process is not None and self.process.returncode is None:
            try:
                self.process.kill()
            except ProcessLookupError:
                pass

    async def _stdout(self):
        try:
            while True:
                message = await ipc.read_frame(self.process.stdout)
                if self._pending is None or self._pending.done():
                    raise ipc.ProtocolError("unsolicited or duplicate worker output")
                self._pending.set_result(message)
        except Exception as exc:
            if not self._closing:
                self._fail(exc)

    async def _stderr(self):
        try:
            while chunk := await self.process.stderr.read(4096):
                self.stderr_tail.extend(chunk)
                del self.stderr_tail[:-STDERR_LIMIT]
        except Exception as exc:
            if not self._closing:
                self._fail(exc)

    async def _exchange(self, message, response_kind):
        if self.failure is not None or self._closing:
            raise WorkerError(self.failure or "worker closed")
        self._pending = asyncio.get_running_loop().create_future()

        async def communicate():
            self.process.stdin.write(ipc.encode_frame(message))
            await self.process.stdin.drain()
            return await self._pending

        try:
            response = await asyncio.wait_for(communicate(), self.timeout)
            if self.failure is not None:
                raise WorkerError(self.failure)
            return ipc.check_envelope(response, response_kind, self.generation, message["seq"])
        finally:
            if not self._pending.done():
                self._pending.cancel()
            elif not self._pending.cancelled():
                self._pending.exception()  # Retrieve failures if drain failed first.
            self._pending = None

    async def start(self):
        if self._started or self._closing:
            raise WorkerError("host is single-use")
        self._started = True
        self._busy = True
        try:
            self.process = await self._spawn()
            self._tasks = [asyncio.create_task(self._stdout()), asyncio.create_task(self._stderr())]
            payload = await self._exchange(ipc.envelope("init", self.generation,
                self.checkpoint.event_seq, dict(config=self.config.to_wire(),
                checkpoint=self.checkpoint.to_wire())), "initialized")
            ipc.exact(payload, ("checkpoint",))
            if ipc.Checkpoint.from_wire(payload["checkpoint"], self.config) != self.checkpoint:
                raise ipc.ProtocolError("worker restored a different checkpoint")
            return self
        except BaseException as exc:
            self._fail(f"worker startup failed: {type(exc).__name__}: {exc}")
            await self.close()
            if isinstance(exc, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                raise
            raise WorkerError(self.failure) from exc
        finally:
            self._busy = False

    async def process_bar(self, bar, account=None):
        if not self._started or self.process is None or self._closing or self.failure:
            raise WorkerError(self.failure or "worker not running")
        if self._busy:
            raise WorkerError("one outstanding event per bot; concurrent request rejected")
        self._busy = True
        try:
            payload = dict(bar=ipc.bar_to_wire(bar), account=ipc.account_to_wire(account))
            bar, account, warmup = ipc.parse_event(payload, self.checkpoint)
            response = await self._exchange(ipc.envelope("bar", self.generation,
                self.checkpoint.event_seq + 1, payload), "result")
            result = ipc.parse_result(response, self.checkpoint, bar, account, warmup)
            self.checkpoint = result.checkpoint
            return result
        except BaseException as exc:
            self._fail(f"worker event failed: {type(exc).__name__}: {exc}")
            await self.close()
            if isinstance(exc, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                raise
            raise WorkerError(self.failure) from exc
        finally:
            self._busy = False

    async def close(self):
        self._closing = True
        if self._pending is not None and not self._pending.done():
            self._pending.set_exception(WorkerError("worker closed"))
        try:
            if self.process is not None:
                if self.process.returncode is None:
                    try:
                        self.process.kill()
                    except ProcessLookupError:
                        pass
                await asyncio.wait_for(self.process.wait(), STOP_TIMEOUT)
        finally:
            for task in self._tasks:
                task.cancel()
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
            if self.process is not None and self.process.stdin is not None:
                self.process.stdin.close()

    async def __aenter__(self):
        return await self.start()

    async def __aexit__(self, *exc):
        await self.close()
