"""Real child processes using synthetic input and test-only fault peers."""

import asyncio
from decimal import Decimal, localcontext
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from catos import ipc, research, worker_host
from catos.worker_host import WorkerError, WorkerHost
from examples.closed_bar_demo import SMATrend
from test_ipc import account, bar, config

ROOT = Path(__file__).resolve().parents[1]


class PeerHost(WorkerHost):
    def __init__(self, mode, **kwargs):
        super().__init__("test-bot", config(), **kwargs)
        self.mode = mode

    async def _spawn(self):
        fixture = str(ROOT / "tests" / "fixtures" / "worker_peer.py")
        script = (f"import sys, runpy; sys.path.insert(0, {str(ROOT)!r}); "
                  f"sys.argv = [{fixture!r}, {self.mode!r}]; runpy.run_path({fixture!r}, run_name='__main__')")
        return await asyncio.create_subprocess_exec(
            sys.executable, "-I", "-S", "-B", "-u", "-c", script,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, env=worker_host.worker_environment(),
            close_fds=True, limit=ipc.MAX_FRAME)


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def started(self, host):
        self.addAsyncCleanup(host.close)
        await host.start()
        return host

    async def assert_stopped(self, host):
        await host.close()
        self.assertIsNotNone(host.process.returncode)
        self.assertTrue(all(task.done() for task in host._tasks))

    async def test_sma_matches_inspected_artifact_with_exact_decimal_and_warmup(self):
        strategy = SMATrend()
        host = await self.started(WorkerHost("sma-bot", config()))
        prices = ("100.01", "101.02", "103.03", "102.04", "99.05")
        results = []
        for index, price in enumerate(prices):
            candle = bar(index, price)
            research._call(strategy.update_indicators, candle)
            expected = None if index < 2 else research._call(strategy.on_bar, candle, account(index))
            with localcontext() as context:
                context.prec = 2
                result = await host.process_bar(candle, None if index < 2 else account(index))
                self.assertEqual(context.prec, 2)
            self.assertEqual(result.target_position, expected)
            self.assertEqual(result.checkpoint.closes, tuple(strategy.closes))
            results.append(result.target_position)
        self.assertEqual(results, [None, None, Decimal("2"), Decimal("0"), Decimal("0")])
        await self.assert_stopped(host)

    async def test_explicit_checkpoint_restore_preserves_next_decision(self):
        first = await self.started(WorkerHost("sma-bot", config()))
        for index, price in enumerate(("100", "101", "103")):
            await first.process_bar(bar(index, price), None if index < 2 else account(index))
        saved = ipc.Checkpoint.from_wire(first.checkpoint.to_wire(), config())
        expected = await first.process_bar(bar(3, "102"), account(3))
        await self.assert_stopped(first)
        second = await self.started(WorkerHost("sma-bot", config(), checkpoint=saved))
        self.assertNotEqual(first.generation, second.generation)
        actual = await second.process_bar(bar(3, "102"), account(3))
        self.assertEqual(actual, expected)
        await self.assert_stopped(second)

    async def test_restore_during_warmup_does_not_leak_an_intent(self):
        first = await self.started(WorkerHost("sma-bot", config()))
        await first.process_bar(bar(0))
        saved = first.checkpoint
        await self.assert_stopped(first)
        second = await self.started(WorkerHost("sma-bot", config(), checkpoint=saved))
        result = await second.process_bar(bar(1, "101"))
        self.assertIsNone(result.target_position)
        self.assertTrue(result.ready)
        self.assertEqual((await second.process_bar(bar(2, "102"), account(2))).target_position, Decimal("2"))

    async def test_none_is_not_a_flatten_intent(self):
        host = await self.started(PeerHost("none"))
        await host.process_bar(bar(0))
        await host.process_bar(bar(1))
        self.assertIsNone((await host.process_bar(bar(2), account(2))).target_position)

    async def test_faults_disable_worker_without_advancing_checkpoint(self):
        for mode in ("crash", "corrupt", "truncated", "wrong_generation", "wrong_seq",
                     "impersonate", "warmup_intent"):
            with self.subTest(mode=mode):
                host = await self.started(PeerHost(mode))
                with self.assertRaises(WorkerError):
                    await host.process_bar(bar(0))
                self.assertEqual(host.checkpoint.event_seq, 0)
                self.assertIsNotNone(host.failure)
                await self.assert_stopped(host)
                with self.assertRaises(WorkerError):
                    await host.process_bar(bar(0))

    async def test_timeout_keeps_event_loop_responsive_and_rejects_concurrency(self):
        host = await self.started(PeerHost("hang"))
        host.timeout = 0.2
        pending = asyncio.create_task(host.process_bar(bar(0)))
        await asyncio.sleep(0)
        with self.assertRaisesRegex(WorkerError, "outstanding"):
            await host.process_bar(bar(0))
        beats = 0
        while not pending.done():
            beats += 1
            await asyncio.sleep(0.01)
        with self.assertRaisesRegex(WorkerError, "TimeoutError"):
            await pending
        self.assertGreater(beats, 2)
        self.assertEqual(host.checkpoint.event_seq, 0)
        await self.assert_stopped(host)

    async def test_startup_timeout_and_cancellation_reap_children(self):
        host = PeerHost("startup_hang", timeout=0.2)
        self.addAsyncCleanup(host.close)
        with self.assertRaisesRegex(WorkerError, "startup failed"):
            await host.start()
        await self.assert_stopped(host)
        host = await self.started(PeerHost("hang"))
        pending = asyncio.create_task(host.process_bar(bar(0)))
        await asyncio.sleep(0.03)
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        await self.assert_stopped(host)

    async def test_stderr_is_drained_and_tail_bounded(self):
        host = await self.started(PeerHost("stderr"))
        result = await host.process_bar(bar(0))
        self.assertEqual(result.event_seq, 1)
        self.assertEqual(bytes(host.stderr_tail), b"x" * worker_host.STDERR_LIMIT)
        await self.assert_stopped(host)

    async def test_control_side_close_interrupts_wait_and_host_cannot_restart(self):
        host = await self.started(PeerHost("hang"))
        pending = asyncio.create_task(host.process_bar(bar(0)))
        await asyncio.sleep(0.03)
        await host.close()
        with self.assertRaises(WorkerError):
            await pending
        await self.assert_stopped(host)
        self.assertEqual(host.checkpoint.event_seq, 0)
        with self.assertRaisesRegex(WorkerError, "single-use"):
            await host.start()

    async def test_duplicate_output_is_a_protocol_failure(self):
        host = await self.started(PeerHost("duplicate"))
        try:
            await host.process_bar(bar(0))
        except WorkerError:
            pass
        for _ in range(100):
            if host.failure:
                break
            await asyncio.sleep(0.01)
        self.assertIsNotNone(host.failure)
        await self.assert_stopped(host)

    async def test_fake_credential_and_pythonpath_are_not_inherited(self):
        # Replace the environment mapping with fake data, never copy real secrets.
        minimal = worker_host.worker_environment()
        fake = dict(minimal, CATOS_FAKE_CREDENTIAL="not-a-real-key", PYTHONPATH="fake-path")
        with patch.object(worker_host.os, "environ", fake):
            self.assertEqual(worker_host.worker_environment(), minimal)
            host = await self.started(PeerHost("normal"))
            self.assertNotIn("not-a-real-key", str(host.checkpoint.to_wire()))
            await host.process_bar(bar(0))
            await self.assert_stopped(host)

    async def test_host_import_and_running_child_do_not_load_strategy_in_parent(self):
        script = f"""
import sys, asyncio
sys.path.insert(0, {str(ROOT)!r})
from decimal import Decimal as D
from catos.ipc import WorkerConfig
from catos.research import ContractSpec
from catos.worker_host import WorkerHost
async def check():
    cfg = WorkerConfig(ContractSpec('SYNTHETIC-USDT-SWAP', D('.01'), D('.01'), D('1'), D('1')), 900000, 2)
    async with WorkerHost('bot', cfg):
        assert 'examples.closed_bar_demo' not in sys.modules
        assert 'examples.sma_state' not in sys.modules
        assert 'catos.worker' not in sys.modules
asyncio.run(check())
"""
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-I", "-S", "-B", "-c", script,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=worker_host.worker_environment())
        try:
            out, err = await asyncio.wait_for(process.communicate(), 10)
            self.assertEqual(process.returncode, 0, (out, err))
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()

    async def test_invalid_input_stops_session_and_readiness_matches_research(self):
        host = await self.started(WorkerHost("sma-bot", config()))
        with self.assertRaisesRegex(WorkerError, "warm-up"):
            await host.process_bar(bar(0), account(0))
        await self.assert_stopped(host)
        for warmup in (0, 1):
            host = await self.started(WorkerHost("sma-bot", config(warmup)))
            with self.assertRaises(WorkerError):
                await host.process_bar(bar(0), account(0) if warmup == 0 else None)
            await self.assert_stopped(host)


if __name__ == "__main__":
    unittest.main()
