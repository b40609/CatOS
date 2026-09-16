"""P6 synthetic policy alternatives; no account/network/production defaults."""
import asyncio
from contextlib import closing
from dataclasses import replace
from decimal import Decimal as D, localcontext
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from catos import account_lock, ipc, protection as p, risk
from catos.fake_exchange import FakeExchange, Fill, TAG
from catos.journal import digest, OwnershipError, FixtureDecision
from catos.supervisor import LocalSupervisor, SupervisorUnavailable
from test_execution import report
from test_ipc import STEP, config
from test_journal import proof, prepare_and_commit, input_for, result_for
from test_risk import snapshot


def policy(ratio='.10', **changes):
    return p.Config(D(ratio), **changes)


class PriceTests(unittest.TestCase):
    def test_disabled_and_confirmed_policy_defaults(self):
        self.assertIsNone(p.stop_price(D(100), D(2), D('.01'), p.Config()))
        cfg = p.Config(D('.1'))
        self.assertEqual((cfg.trigger, cfg.rounding, cfg.disable),
                         ('mark', 'earlier', 'cancel_confirm'))
        for value in (D('-1'), D(1), .1, D('NaN')):
            with self.assertRaises(ValueError):
                p.Config(value)

    def test_tick_directions_and_decimal_context(self):
        with localcontext() as ctx:
            ctx.prec = 2
            for rounding, position, expected in (('earlier', '2', '90.10'), ('earlier', '-2', '110.11'),
                                                 ('later', '2', '90.09'), ('later', '-2', '110.12')):
                cfg = p.Config(D('.1'), 'last', rounding, 'flat_only')
                self.assertEqual(p.stop_price(D('100.101'), D(position), D('.01'), cfg), D(expected))

    def test_cost_changes_and_distinct_bot_values(self):
        self.assertEqual(p.stop_price(D(100), D(2), D('.01'), policy('.1')), D(90))
        self.assertEqual(p.stop_price(D(100), D(2), D('.01'), policy('.2')), D(80))
        self.assertEqual(p.stop_price(D(120), D(2), D('.01'), policy('.1')), D(108))
        with self.assertRaises(ValueError):
            p.stop_price(D('.01'), D(2), D('.01'), policy('.1'))


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'p6.sqlite3'
        locks = patch.object(account_lock, 'LOCK_DIRECTORY', Path(self.directory.name) / 'locks')
        locks.start()
        self.addCleanup(locks.stop)
        self.exchange = FakeExchange('fake-account')
        self.s = self.make()
        self.addAsyncCleanup(self.cleanup)
        await self.s.start()
        await self.s.reconcile(proof(0))
        self.observe(D(0))
        await self.s.persist_controls()
        for index in (0, 1):
            await self.s._io(prepare_and_commit, self.s._journal, index)
        first = await self.s._io(lambda: prepare_and_commit(self.s._journal, 2, target=D(2)))
        self.first_key = first.intent_key
        self.exchange.enqueue('submit', report(self.first_key, status='FILLED',
            fills=(Fill('first', D(2), D(100)),), complete=True))
        await self.s.dispatch(self.first_key, now_ms=3 * STEP)
        await self.reconcile(D(2))

    def make(self):
        return LocalSupervisor(self.path, account_id='fake-account', bot_id='bot', config=config(),
                               fixture_budget=D(100), risk_limits=risk.Limits(), exchange=self.exchange)

    async def cleanup(self):
        await self.s.close()

    def observe(self, position, **changes):
        self.s.observe_risk(snapshot(self.s.risk_state.seq + 1, 3 * STEP,
                                    valid_until_ms=20 * STEP, position=position, **changes))

    async def reconcile(self, position, conditional=0):
        await self.s.reconcile(proof(self.s.revision, position=position,
            attributed_bot_id='bot' if position else None, conditional_open=conditional))
        self.observe(position)
        await self.s.persist_controls()

    async def state(self):
        return await self.s.protection_state()

    async def blocked(self):
        return await self.s._io(self.s._journal.protection.blocked, 'bot')

    async def respond(self, operation, status='LIVE', price='90', complete=True, revision=1):
        s = await self.state()
        request = (s['pending']['payload']['requestId'] if s['pending'] else
                   s['active']['payload']['requestId'] if s['uncertain'] and s['active'] else
                   digest(f'fake-account:bot:protection:{s["serial"] + 1}')[:32])
        self.exchange.enqueue(operation, p.Report(request, revision, status,
            D(price) if status == 'LIVE' else None, 'sell' if status == 'LIVE' else None,
            'mark' if status == 'LIVE' else None, complete))
        return await self.s.protection_step(now_ms=3 * STEP)

    async def enable(self):
        await self.s.configure_protection(policy())
        await self.respond('algo_create')
        await self.reconcile(D(2), 1)

    async def intent(self, index, position, target):
        def commit():
            j = self.s._journal
            cp = j.snapshot('bot')['checkpoint']
            payload = input_for(index)
            payload['account']['position'] = str(position)
            payload['account']['average_entry'] = '110' if position else '0'
            j.prepare('bot', index + 1, payload, (index + 2) * STEP)
            return j.commit_result('bot', result_for(cp, index, target=target), FixtureDecision(), (index + 1) * STEP)
        return await self.s._io(commit)

    async def test_default_disabled_sends_nothing_and_keeps_account_hard(self):
        self.assertFalse(await self.blocked())
        await self.s.protection_step(now_ms=3 * STEP)
        self.assertFalse(any(op.startswith('algo_') for op, _ in self.exchange.calls))
        self.observe(D(2), equity=D(800))
        self.assertEqual(self.s.risk_state.mode, 'FLAT')

    async def test_create_whole_position_tag_and_confirmed_coverage(self):
        await self.enable()
        state = await self.state()
        self.assertEqual(D(state['average']), D(100))
        self.assertFalse(await self.blocked())
        payload = self.exchange.calls[-1][1]
        self.assertEqual((payload['tag'], payload['closeFraction'], payload['reduceOnly'], payload['slOrdPx']),
                         (TAG, '1', True, '-1'))
        self.assertEqual(payload['slTriggerPxType'], 'mark')

    async def test_create_timeout_queries_only_and_not_found_does_not_release(self):
        await self.s.configure_protection(policy())
        await self.s.protection_step(now_ms=3 * STEP)
        await self.respond('algo_query', 'NOT_FOUND', complete=True)
        self.assertTrue(await self.blocked())
        await self.respond('algo_query', revision=2)
        self.assertFalse(await self.blocked())
        self.assertEqual([op for op, _ in self.exchange.calls if op.startswith('algo_')],
                         ['algo_create', 'algo_query', 'algo_query'])

    async def test_first_create_timeout_vetoes_rearm_after_healthy_rebound(self):
        await self.s.configure_protection(policy())
        await self.s.protection_step(now_ms=3 * STEP)
        protection = await self.state()
        self.assertIsNone(protection['active'])
        self.assertIsNotNone(protection['pending'])
        self.assertTrue(protection['uncertain'])
        self.observe(D(2), equity=D(900))
        await self.reconcile(D(2))
        before = self.s.risk_state
        epoch = self.s.epoch
        self.assertEqual((before.mode, before.health), ('NO_INCREASE', 'HEALTHY'))
        audit_before = await self.s._io(lambda: [tuple(row) for row in self.s._journal.connection.execute(
            'SELECT * FROM risk_actions')])
        with self.assertRaises(SupervisorUnavailable):
            await self.s.rearm(now_ms=3 * STEP, actor='operator', evidence_id='protection-review')
        self.assertEqual(self.s.risk_state, before)
        self.assertEqual(await self.s._io(self.s._journal.risk_state), before)
        self.assertEqual(self.s.epoch, epoch)
        self.assertEqual(await self.state(), protection)
        self.assertEqual(await self.s._io(lambda: [tuple(row) for row in self.s._journal.connection.execute(
            'SELECT * FROM risk_actions')]), audit_before)
        self.assertIsNone(self.s.failure)
        with self.assertLogs('catos.protection', level='WARNING'):
            await self.respond('algo_query', 'REJECTED')
        await self.reconcile(D(2))
        resolved = await self.state()
        self.assertTrue(resolved['failed'])
        self.assertTrue(await self.blocked())
        self.assertFalse(await self.s._io(self.s._journal.protection.obligations, 'bot'))
        await self.s.rearm(now_ms=3 * STEP, actor='operator', evidence_id='protection-resolved')
        self.assertEqual(self.s.risk_state.mode, 'RUN')
        self.assertTrue(await self.blocked())
        self.assertEqual(await self.s._io(lambda: self.s._journal.connection.execute(
            'SELECT count(*) FROM risk_actions').fetchone()[0]), len(audit_before) + 1)

    async def test_update_failure_keeps_old_protection_blocks_increase_and_alerts(self):
        await self.enable()
        await self.s.configure_protection(policy('.2'))
        before = len(self.exchange.calls)
        with self.assertLogs('catos.protection', level='WARNING') as logs:
            await self.respond('algo_amend', 'REJECTED')
        self.assertIn('protection_request_failed', logs.output[0])
        self.assertEqual(D((await self.state())['active']['price']), D(90))
        self.assertTrue(await self.blocked())
        self.assertIsNone(self.s.failure)
        self.assertEqual([op for op, _ in self.exchange.calls[before:]], ['algo_amend'])
        # No synthetic liquidation or market reduce is issued by failure handling.
        increase = await self.intent(3, D(2), D(4))
        self.assertEqual(increase.reason, 'protection_gate_closed')
        reduction = await self.intent(4, D(2), D(1))
        self.assertEqual(reduction.reason, 'legal_reduction')

    async def test_disable_waits_for_cancel_terminal_and_unknown_does_not_disable_gate(self):
        await self.enable()
        await self.s.configure_protection(p.Config())
        await self.respond('algo_cancel', 'CANCELED', complete=False)
        self.assertTrue(await self.blocked())
        self.assertIsNotNone((await self.state())['active'])
        await self.respond('algo_query', 'CANCELED', revision=2)
        self.assertFalse(await self.blocked())
        self.assertIsNone((await self.state())['active'])

    async def test_flat_only_policy_rejects_disable_in_position(self):
        await self.s.configure_protection(p.Config(D('.1'), 'mark', 'earlier', 'flat_only'))
        await self.respond('algo_create')
        with self.assertRaises(SupervisorUnavailable):
            await self.s.configure_protection(p.Config())
        self.assertEqual(D((await self.state())['config']['ratio']), D('.1'))

    async def test_restart_retains_responsibility_and_queries_before_increasing(self):
        await self.enable()
        await self.s.close()
        self.s = self.make()
        await self.s.start()
        self.assertTrue(await self.blocked())
        await self.respond('algo_query', revision=2)
        self.assertEqual(self.exchange.calls[-1][0], 'algo_query')
        await self.reconcile(D(2), 1)
        self.assertFalse(await self.blocked())

    async def test_commit_failure_never_reaches_fake_exchange(self):
        await self.s.configure_protection(policy())
        count = len(self.exchange.calls)
        with patch.object(self.s._journal, '_commit', side_effect=sqlite3.OperationalError('mock full disk')):
            with self.assertRaises(sqlite3.OperationalError):
                await self.s.protection_step(now_ms=3 * STEP)
        self.assertEqual(len(self.exchange.calls), count)
        self.assertIsNone((await self.s._io(self.s._journal.protection.state, 'bot'))['pending'])

    async def test_new_cost_from_fills_requires_amend_and_reduction_keeps_cost(self):
        await self.enable()
        receipt = await self.intent(3, D(2), D(4))
        self.exchange.enqueue('submit', report(receipt.intent_key, status='FILLED',
            fills=(Fill('second', D(2), D(120)),), complete=True))
        await self.s.dispatch(receipt.intent_key, now_ms=3 * STEP)
        self.assertEqual(D((await self.state())['average']), D(110))
        self.assertTrue(await self.blocked())
        await self.reconcile(D(4), 1)
        await self.respond('algo_amend', price='99')
        self.assertFalse(await self.blocked())
        reduced = await self.intent(4, D(4), D(2))
        self.exchange.enqueue('submit', report(reduced.intent_key, status='FILLED',
            fills=(Fill('reduction', D(2), D(130)),), complete=True))
        await self.s.dispatch(reduced.intent_key, now_ms=3 * STEP)
        self.assertEqual(D((await self.state())['average']), D(110))

    async def test_trigger_is_not_flat_or_done_and_foreign_conditionals_rejected(self):
        await self.s.configure_protection(policy())
        await self.respond('algo_create', 'TRIGGERED')
        self.assertTrue(await self.blocked())
        self.assertEqual((await self.state())['quantity'], '2')
        with self.assertRaises(OwnershipError):
            await self.reconcile(D(2), 2)

    async def test_normal_close_leaves_protection_obligation_until_canceled(self):
        await self.enable()
        receipt = await self.intent(3, D(2), D(0))
        self.exchange.enqueue('submit', report(receipt.intent_key, status='FILLED',
            fills=(Fill('normal-close', D(2), D(100)),), complete=True))
        await self.s.dispatch(receipt.intent_key, now_ms=4 * STEP)
        await self.reconcile(D(0), 1)
        self.assertTrue(await self.blocked())
        with self.assertRaises(OwnershipError):
            await self.s.release_contract()
        await self.respond('algo_cancel', 'CANCELED')
        await self.reconcile(D(0))
        await self.s.release_contract()

    async def test_partial_fill_cost_dedup_before_order_terminal(self):
        await self.enable()
        receipt = await self.intent(3, D(2), D(4))
        partial = report(receipt.intent_key, status='PARTIAL', fills=(Fill('partial', D(1), D(130)),))
        self.exchange.enqueue('submit', partial)
        await self.s.dispatch(receipt.intent_key, now_ms=4 * STEP)
        self.assertEqual(D((await self.state())['average']), D(110))
        self.assertTrue(await self.blocked())
        self.exchange.enqueue('query', replace(partial, revision=2))
        await self.s.query_order(receipt.intent_key)
        self.assertEqual(D((await self.state())['average']), D(110))
        self.assertEqual(D((await self.state())['quantity']), D(3))

    async def test_malformed_or_stale_confirmation_never_opens_gate(self):
        await self.enable()
        await self.s.close()
        self.s = self.make()
        await self.s.start()
        with self.assertRaises(ipc.ProtocolError):
            await self.respond('algo_query', revision=1)
        self.assertTrue(await self.s._io(self.s._journal.protection.blocked, 'bot'))

    async def test_uncertain_amend_retains_old_price_and_queries_without_resend(self):
        await self.enable()
        await self.s.configure_protection(policy('.2'))
        await self.s.protection_step(now_ms=3 * STEP)
        self.assertEqual(D((await self.state())['active']['price']), D(90))
        self.assertTrue(await self.blocked())
        await self.respond('algo_query', price='80')
        self.assertFalse(await self.blocked())
        self.assertEqual([op for op, _ in self.exchange.calls[-2:]], ['algo_amend', 'algo_query'])

    async def test_schema_four_nonflat_migration_does_not_invent_cost(self):
        await self.s.close()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DROP TABLE protection')
            db.execute('PRAGMA user_version=4')
        self.s = self.make()
        await self.s.start()
        self.assertEqual((await self.state())['config']['ratio'], '0')
        with self.assertRaisesRegex(SupervisorUnavailable, 'cost baseline'):
            await self.s.configure_protection(policy())
        self.assertEqual(self.exchange.calls[-1][0], 'submit')


if __name__ == '__main__':
    unittest.main()
