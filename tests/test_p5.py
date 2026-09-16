"""P5 configuration/recovery, durable evidence and concurrent control vetoes."""
import asyncio
from contextlib import closing
from dataclasses import replace
from decimal import Decimal as D, localcontext
from pathlib import Path
import json
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from catos import account_lock, ipc, risk
from catos.journal import Journal
from catos.supervisor import LocalSupervisor, SupervisorUnavailable
from test_ipc import config
from test_journal import proof
from test_risk import snapshot
from lot_journal_helpers import drop_empty_lot_schema


class PolicyTests(unittest.TestCase):
    def test_custom_boundaries_and_decimal_validation(self):
        limits = risk.Limits(soft_loss=D('.1234'), hard_loss=D('.2345'))
        with localcontext() as context:
            context.prec = 2
            for equity, expected in (('876.6001', 'RUN'), ('876.6', 'NO_INCREASE'), ('765.5', 'FLAT')):
                self.assertEqual(risk.observe(risk.State(), snapshot(equity=D(equity)), limits).mode, expected)
        for soft, hard in ((D(0), D('.2')), (D('.2'), D('.2')), (D('.3'), D('.2')),
                           (D('.1'), D('1.1')), (.1, D('.2')), (D('NaN'), D('.2'))):
            with self.assertRaises(ValueError):
                risk.Limits(soft_loss=soft, hard_loss=hard)

    def test_soft_same_day_recovery_preserves_basis_and_rejects_active_loss(self):
        state = risk.observe(risk.State(), snapshot(equity=D(900)))
        with self.assertRaises(ipc.ProtocolError):
            risk.rearm(state, risk.Limits(), 0, reconciled=True)
        bounced = risk.observe(state, snapshot(2, 1, equity=D(950)))
        self.assertEqual(bounced.mode, 'NO_INCREASE')
        recovered = risk.rearm(bounced, risk.Limits(), 1, reconciled=True)
        self.assertEqual((recovered.mode, recovered.basis, recovered.snapshot.external_net),
                         ('RUN', state.basis, D(0)))
        self.assertGreater(recovered.epoch, bounced.epoch)

    def test_expiry_missing_day_and_bad_position_veto_recovery(self):
        state = risk.halt(risk.observe(risk.State(), snapshot()), {'soft_loss'})
        for state_, now in ((state, 60000), (replace(state, health='DEGRADED'), 0),
                           (replace(state, snapshot=replace(state.snapshot, position_verified=False)), 0)):
            with self.assertRaises(ipc.ProtocolError):
                risk.rearm(state_, risk.Limits(), now, reconciled=True)
        midnight = risk.DAY_MS - risk.TAIPEI_OFFSET_MS
        state = risk.observe(state, snapshot(2, midnight, basis=None))
        with self.assertRaises(ipc.ProtocolError):
            risk.rearm(state, risk.Limits(), midnight, reconciled=True)


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'state.sqlite3'
        locks = patch.object(account_lock, 'LOCK_DIRECTORY', Path(self.directory.name) / 'locks')
        locks.start()
        self.addCleanup(locks.stop)
        self.s = self.make()
        self.addAsyncCleanup(self.cleanup)
        await self.s.start()
        await self.s.reconcile(proof(0))
        self.observe()
        await self.s.persist_controls()

    def make(self, limits=None):
        return LocalSupervisor(self.path, account_id='fake-account', bot_id='bot', config=config(),
                               fixture_budget=D(100), risk_limits=limits or risk.Limits())

    async def cleanup(self):
        await self.s.close()

    def observe(self, **changes):
        seq = self.s.risk_state.seq + 1
        return self.s.observe_risk(snapshot(seq, seq, **changes))

    async def recover(self, **extra):
        return await self.s.rearm(now_ms=self.s.risk_state.time_ms, actor='operator',
                                  evidence_id='manual-review', **extra)

    async def soften_and_bounce(self):
        self.observe(equity=D(900))
        self.observe()
        await self.s.persist_controls()

    async def test_configuration_does_not_clear_latch_then_explicit_rearm_survives_restart(self):
        self.observe(equity=D(900))
        await self.s.set_loss_limits(soft_loss=D('.15'), hard_loss=D('.25'), actor='operator', evidence_id='config')
        self.assertEqual(self.s.risk_state.mode, 'NO_INCREASE')
        before = self.s.risk_state.basis
        await self.recover()
        self.assertEqual(self.s.risk_state.mode, 'RUN')
        self.assertFalse(self.s.halt_reasons)
        audit = await self.s._io(lambda: [tuple(r) for r in self.s._journal.connection.execute(
            'SELECT kind,actor,evidence_id FROM risk_actions')])
        self.assertEqual(audit, [('loss_limits', 'operator', 'config'), ('rearm', 'operator', 'manual-review')])
        limits = self.s.risk_limits
        await self.s.close()
        self.s = self.make(limits)
        await self.s.start()
        self.assertEqual((self.s.risk_state.mode, self.s.risk_state.basis), ('RUN', before))
        self.assertEqual(self.s.risk_state.health, 'RECONCILING')
        self.assertIsNone(self.s.risk_state.snapshot)

    async def test_tightening_limits_immediately_latches_existing_loss(self):
        self.observe(equity=D(950))
        await self.s.set_loss_limits(soft_loss=D('.03'), hard_loss=D('.05'), actor='operator', evidence_id='tighten')
        self.assertEqual(self.s.risk_state.mode, 'FLAT')
        self.assertEqual(self.s.risk_state.reasons, {'soft_loss', 'hard_loss'})
        with self.assertRaises(SupervisorUnavailable):
            await self.recover()
        self.assertIsNone(self.s.failure)

    async def test_unknown_and_unfinished_orders_veto_without_poisoning_supervisor(self):
        await self.soften_and_bounce()
        for changes in (dict(unknown_count=1), dict(ordinary_open=1), dict(conditional_open=1),
                        dict(fills_reconciled=False)):
            await self.s.reconcile(proof(0, **changes))
            with self.assertRaises(SupervisorUnavailable):
                await self.recover()
            self.assertEqual(self.s.risk_state.mode, 'NO_INCREASE')
            self.assertIsNone(self.s.failure)
        await self.s.reconcile(proof(0))
        await self.recover()

    async def test_local_protection_obligations_veto_rearm_without_mutation(self):
        await self.soften_and_bounce()
        journal = self.s._journal
        protection = await self.s._io(journal.protection.state, 'bot')

        def save_protection(state):
            with journal._transaction():
                journal.protection.save('bot', state)

        def durable_state():
            return (journal.risk_state(), tuple(journal.connection.execute(
                'SELECT epoch,halt_reasons,health FROM control WHERE id=1').fetchone()),
                [tuple(row) for row in journal.connection.execute('SELECT * FROM risk_actions')])

        for changes in (dict(pending=dict(operation='algo_create', payload=dict(requestId='synthetic'))),
                        dict(uncertain=True), dict(triggered=True)):
            with self.subTest(changes=changes):
                await self.s._io(save_protection, protection | changes)
                before = await self.s._io(durable_state)
                memory = (self.s.risk_state, self.s.epoch, frozenset(self.s.halt_reasons))
                self.assertEqual((self.s.risk_state.mode, self.s.risk_state.health), ('NO_INCREASE', 'HEALTHY'))
                with self.assertRaises(SupervisorUnavailable):
                    await self.recover()
                self.assertEqual(await self.s._io(durable_state), before)
                self.assertEqual((self.s.risk_state, self.s.epoch, frozenset(self.s.halt_reasons)), memory)
                self.assertEqual(await self.s._io(journal.protection.state, 'bot'), protection | changes)
                self.assertIsNone(self.s.failure)
        await self.s._io(save_protection, protection)
        await self.recover()
        self.assertEqual(self.s.risk_state.mode, 'RUN')
        audit = await self.s._io(lambda: [row[0] for row in journal.connection.execute('SELECT kind FROM risk_actions')])
        self.assertEqual(audit, ['rearm'])

    async def test_hard_requires_completed_flatten_and_cause_gone_same_day(self):
        self.observe(equity=D(800))
        self.observe()
        with self.assertRaises(SupervisorUnavailable):
            await self.recover()
        await self.s.flatten_progress('VERIFY', now_ms=self.s.risk_state.time_ms)
        await self.s.flatten_progress('DONE', now_ms=self.s.risk_state.time_ms)
        self.s.latch('manual_kill')
        with self.assertRaises(SupervisorUnavailable):
            await self.recover()
        await self.recover(manual_cause_cleared=True)
        self.assertEqual((self.s.risk_state.mode, self.s.risk_state.phase), ('RUN', 'IDLE'))
        self.assertIsNone(self.s.risk_state.flatten_id)

    async def test_rearm_commit_failure_rolls_back_latch_and_audit(self):
        await self.soften_and_bounce()
        with patch.object(self.s._journal, '_commit', side_effect=sqlite3.OperationalError('mock disk failure')):
            with self.assertRaises(sqlite3.OperationalError):
                await self.recover()
        stored = await self.s._io(self.s._journal.risk_state)
        count = await self.s._io(lambda: self.s._journal.connection.execute('SELECT count(*) FROM risk_actions').fetchone()[0])
        self.assertEqual((stored.mode, self.s.risk_state.mode, count), ('NO_INCREASE', 'NO_INCREASE', 0))

    async def test_configuration_failure_rolls_back_persistent_limits(self):
        with patch.object(self.s._journal, '_commit', side_effect=sqlite3.OperationalError('mock disk failure')):
            with self.assertRaises(sqlite3.OperationalError):
                await self.s.set_loss_limits(soft_loss=D('.15'), hard_loss=D('.25'), actor='operator', evidence_id='change')
        saved = await self.s._io(lambda: self.s._journal.connection.execute('SELECT limits_json FROM risk_control').fetchone()[0])
        self.assertEqual(json.loads(saved)['soft_loss'], '0.10')
        self.assertEqual(self.s.risk_state.health, 'DEGRADED')

    async def test_control_event_during_rearm_commit_vetoes_gate(self):
        await self.soften_and_bounce()
        entered, release = threading.Event(), threading.Event()
        original = self.s._journal._commit

        def delayed():
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test timeout')
            original()

        with patch.object(self.s._journal, '_commit', delayed):
            task = asyncio.create_task(self.recover())
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 3))
                self.s.latch('manual_kill')
            finally:
                release.set()
            with self.assertRaisesRegex(SupervisorUnavailable, 'superseded'):
                await task
        self.assertEqual(self.s.risk_state.mode, 'FLAT')
        stored = await self.s._io(self.s._journal.risk_state)
        self.assertIn('manual_kill', stored.reasons)

    async def test_legacy_limits_migrate_without_clearing_latch_or_basis(self):
        await self.soften_and_bounce()
        basis = self.s.risk_state.basis
        await self.s.close()
        with closing(sqlite3.connect(self.path)) as db, db:
            drop_empty_lot_schema(db)
            db.execute('UPDATE risk_control SET limits_json=?', (json.dumps({'leverage': '3.0', 'symbol_share': '0.50'}),))
            db.execute('DROP TABLE risk_actions')
            db.execute('PRAGMA user_version=3')
        self.s = self.make()
        await self.s.start()
        self.assertEqual((self.s.risk_state.mode, self.s.risk_state.basis), ('NO_INCREASE', basis))
        self.assertEqual(self.s.risk_limits.soft_loss, D('.10'))
        self.assertIsNone(self.s.risk_state.snapshot)

    async def test_repeated_kill_during_commit_cannot_be_lost_as_equal_state(self):
        self.s.latch('manual_kill')
        await self.s.flatten_progress('VERIFY', now_ms=self.s.risk_state.time_ms)
        await self.s.flatten_progress('DONE', now_ms=self.s.risk_state.time_ms)
        entered, release = threading.Event(), threading.Event()
        original = self.s._journal._commit

        def delayed():
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test timeout')
            original()

        with patch.object(self.s._journal, '_commit', delayed):
            task = asyncio.create_task(self.recover(manual_cause_cleared=True))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 3))
                before = self.s.risk_state
                self.s.latch('manual_kill')
                self.assertEqual(self.s.risk_state, before)
            finally:
                release.set()
            with self.assertRaisesRegex(SupervisorUnavailable, 'superseded'):
                await task
        self.assertEqual(self.s.risk_state.mode, 'FLAT')


if __name__ == '__main__':
    unittest.main()
