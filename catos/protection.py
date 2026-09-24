"""P6 local-only protection journal. All calls run on Supervisor's sole writer.

Synthetic confirmations are not an OKX protocol or proof of remote coverage.
"""
from dataclasses import dataclass
from decimal import Decimal, localcontext, ROUND_CEILING, ROUND_FLOOR
import json

from catos import ipc, research, risk
from catos.fake_exchange import TAG

D = Decimal


def same_coverage(active, desired):
    if active is None or desired is None:
        return active is desired
    return (D(active['price']) == D(desired['price']) and active['side'] == desired['side']
            and active['trigger'] == desired['trigger'])


@dataclass(frozen=True)
class Config:
    ratio: Decimal = D('0')
    trigger: str | None = 'mark'
    rounding: str | None = 'earlier'
    disable: str | None = 'cancel_confirm'

    def __post_init__(self):
        if not 0 <= risk.decimal(self.ratio, 'disaster ratio') < 1:
            raise ipc.ProtocolError('disaster ratio must be in [0,1)')
        if self.trigger not in (None, 'mark', 'last', 'index'):
            raise ipc.ProtocolError('invalid trigger source')
        if self.rounding not in (None, 'earlier', 'later') or self.disable not in (None, 'cancel_confirm', 'flat_only'):
            raise ipc.ProtocolError('invalid protection policy')
        if self.ratio and None in (self.trigger, self.rounding, self.disable):
            raise ipc.ProtocolError('enabled protection requires explicit policies')

    def wire(self):
        return dict(ratio=str(self.ratio), trigger=self.trigger, rounding=self.rounding, disable=self.disable)


def stop_price(average, position, tick, config):
    for name, value in (('average', average), ('position', position), ('tick', tick)):
        risk.decimal(value, name)
    if not config.ratio or not position:
        return None
    if average <= 0 or tick <= 0:
        raise ipc.ProtocolError('verified positive cost and tick required')
    with localcontext(research._CONTEXT):
        raw = average * (1 - config.ratio if position > 0 else 1 + config.ratio)
        up = (position > 0) == (config.rounding == 'earlier')
        price = (raw / tick).to_integral_value(rounding=ROUND_CEILING if up else ROUND_FLOOR) * tick
        if price <= 0 or (position > 0 and price >= average) or (position < 0 and price <= average):
            raise ipc.ProtocolError('tick cannot represent a protective distance')
        return price


@dataclass(frozen=True)
class Report:
    request_id: str
    revision: int
    status: str
    price: Decimal | None = None
    side: str | None = None
    trigger: str | None = None
    complete: bool = False
    algo_id: str | None = None

    def wire(self):
        ipc.token(self.request_id, 'protection request')
        ipc.integer(self.revision, 'protection revision', 1)
        if self.status not in ('LIVE', 'CANCELED', 'REJECTED', 'TRIGGERED', 'NOT_FOUND'):
            raise ipc.ProtocolError('invalid protection status')
        if type(self.complete) is not bool:
            raise ipc.ProtocolError('explicit protection completeness required')
        if self.algo_id is not None:
            ipc.token(self.algo_id, 'remote algo id')
        if self.status in ('LIVE', 'CANCELED', 'TRIGGERED') and self.algo_id is None:
            raise ipc.ProtocolError('remote algo identity required')
        if self.status == 'LIVE':
            if risk.decimal(self.price, 'confirmed price') <= 0 or self.side not in ('buy', 'sell') or self.trigger not in ('mark', 'last', 'index'):
                raise ipc.ProtocolError('invalid confirmed protection')
        return dict(request_id=self.request_id, revision=self.revision, status=self.status,
                    price=None if self.price is None else str(self.price), side=self.side,
                    trigger=self.trigger, complete=self.complete, algo_id=self.algo_id)


class ProtectionJournal:
    def __init__(self, journal):
        self.j, self.db = journal, journal.connection

    def register(self, bot_id):
        from catos.journal import canonical
        initial = dict(config=Config().wire(), quantity='0', average='0', active=None,
                       pending=None, serial=0, uncertain=False, failed=False, alert=None,
                       revision=0, report=None, triggered=False)
        self.db.execute('INSERT OR IGNORE INTO protection VALUES (?,?)', (bot_id, canonical(initial)))

    def state(self, bot_id):
        row = self.db.execute('SELECT state_json FROM protection WHERE bot_id=?', (bot_id,)).fetchone()
        if row is None:
            raise ipc.ProtocolError('unknown protection bot')
        return json.loads(row[0])

    def save(self, bot_id, state):
        from catos.journal import canonical
        self.db.execute('UPDATE protection SET state_json=? WHERE bot_id=?', (canonical(state), bot_id))
        if self.blocked(bot_id):
            self.db.execute('UPDATE risk_orders SET eligible=0 WHERE reduce_only=0 AND intent_key IN (SELECT intent_key FROM intents WHERE bot_id=?)', (bot_id,))

    def desired(self, bot_id, state):
        config = Config(**(state['config'] | dict(ratio=D(state['config']['ratio']))))
        contract = self.j._checkpoint(self.j._bot(bot_id)).config.contract
        price = stop_price(D(state['average']), D(state['quantity']), contract.tick_size, config)
        return None if price is None else dict(price=str(price), side='sell' if D(state['quantity']) > 0 else 'buy', trigger=config.trigger)

    def blocked(self, bot_id):
        s = self.state(bot_id)
        if D(s['config']['ratio']):
            owner = self.db.execute('SELECT position FROM ownership WHERE bot_id=?', (bot_id,)).fetchone()
            if owner is None or owner[0] is None or D(owner[0]) != D(s['quantity']):
                return True
        if s['pending'] or s['uncertain'] or s['failed'] or s['triggered']:
            return True
        try:
            desired = self.desired(bot_id, s)
        except ipc.ProtocolError:
            return True
        return not same_coverage(s['active'], desired)

    def obligations(self, bot_id):
        s = self.state(bot_id)
        return bool(s['active'] or s['pending'] or s['uncertain'] or s['triggered'])

    def configure(self, bot_id, config):
        if not isinstance(config, Config):
            raise ipc.ProtocolError('Supervisor protection config required')
        with self.j._transaction():
            _, owner = self.j._require_owner(bot_id)
            s = self.state(bot_id)
            if config.ratio and (owner['position'] is None or D(owner['position']) != D(s['quantity'])):
                raise ipc.ProtocolError('verified cost baseline required before enabling protection')
            old = s['config']
            if s['pending'] or s['uncertain'] or s['triggered']:
                raise ipc.ProtocolError('resolve protection uncertainty before configuration')
            if not config.ratio and (s['active'] or D(s['quantity']) != 0) and D(old['ratio']):
                if old['disable'] == 'flat_only' and D(s['quantity']) != 0:
                    raise ipc.ProtocolError('disable requires flat position')
                config = Config(D(0), old['trigger'], old['rounding'], old['disable'])
            s['config'] = config.wire()
            s['failed'] = False
            s['alert'] = 'protection_change_pending' if self.desired(bot_id, s) or s['active'] else None
            self.save(bot_id, s)
        return s

    def fill(self, bot_id, previous, quantity, price):
        """Called in the SAME transaction as deduplicated execution fills."""
        s = self.state(bot_id)
        with localcontext(research._CONTEXT):
            if D(s['quantity']) != previous:
                # Legacy non-flat cost is not guessed or taken from Worker.
                s['average'] = '0'
            average = D(s['average'])
            current = previous + quantity
            if previous == 0:
                average = price
            elif previous * quantity > 0 and average > 0:
                average = (abs(previous) * average + abs(quantity) * price) / abs(current)
            elif current == 0:
                average = D(0)
            elif current * previous < 0:
                average = price
            s['quantity'], s['average'] = str(current), str(average)
        if D(s['config']['ratio']):
            s['alert'] = 'protection_recheck_required'
        # ownership is advanced by the surrounding execution transaction.
        self.save(bot_id, s)

    def prepare(self, bot_id, now_ms):
        from catos.journal import digest
        ipc.integer(now_ms, 'protection time')
        with self.j._transaction():
            bot, owner = self.j._require_owner(bot_id)
            s = self.state(bot_id)
            if s['pending']:
                return dict(operation='algo_query', payload=s['pending']['payload'])
            if s['triggered']:
                return None  # Triggered is NOT proof of fills or flat position.
            if s['uncertain'] and s['active']:
                s['pending'] = dict(operation='algo_query', payload=s['active']['payload'])
            else:
                snap = self.j.risk_state().snapshot
                if (snap is None or not snap.time_ms <= now_ms < snap.valid_until_ms
                        or not snap.position_verified or owner['position'] is None
                        or D(owner['position']) != D(s['quantity']) or snap.position != D(s['quantity'])
                        or owner['reconciled_revision'] != bot['revision'] or not owner['fills_reconciled']):
                    raise ipc.ProtocolError('fresh attributed position required for protection mutation')
                desired = self.desired(bot_id, s)
                active = s['active']
                if desired is None and active is None:
                    s['failed'], s['alert'] = False, None
                    self.save(bot_id, s)
                    return None
                if desired is not None and same_coverage(active, desired) and not s['failed']:
                    s['alert'] = None
                    self.save(bot_id, s)
                    return None
                s['serial'] += 1
                request_id = digest(f'{self.j.account_id}:{bot_id}:protection:{s["serial"]}')[:32]
                payload = dict(instId=bot['inst_id'], tdMode='cross', posSide='net',
                    ordType='conditional', closeFraction='1', reduceOnly=True, tag=TAG,
                    requestId=request_id, algoClOrdId=request_id if active is None else active['payload']['algoClOrdId'])
                if desired is not None:
                    payload.update(side=desired['side'], slTriggerPx=desired['price'],
                                   slTriggerPxType=desired['trigger'], slOrdPx='-1')
                operation = 'algo_cancel' if desired is None else 'algo_create' if active is None else 'algo_amend'
                s['pending'] = dict(operation=operation, payload=payload)
            if s['report'] is None or s['pending']['payload']['requestId'] != s['report']['request_id']:
                s['revision'], s['report'] = 0, None
            s['uncertain'], s['failed'] = True, False
            s['alert'] = 'protection_unconfirmed'
            self.save(bot_id, s)
            return s['pending']

    def apply(self, bot_id, report):
        data = report.wire()
        with self.j._transaction():
            s = self.state(bot_id)
            had_active = s['active'] is not None
            pending = s['pending']
            if pending is None or data['request_id'] != pending['payload']['requestId']:
                raise ipc.ProtocolError('protection response identity mismatch')
            if report.revision <= s['revision']:
                if data == s['report'] and not s['uncertain']:
                    return s
                raise ipc.ProtocolError('conflicting protection evidence')
            active_algo_id = None if s['active'] is None else s['active'].get('algo_id')
            if active_algo_id is not None and data['algo_id'] is not None and data['algo_id'] != active_algo_id:
                raise ipc.ProtocolError('protection remote identity mismatch')
            s['revision'], s['report'] = report.revision, data
            if report.complete and report.status == 'LIVE' and pending['operation'] != 'algo_cancel':
                s['active'] = dict(price=data['price'], side=data['side'], trigger=data['trigger'],
                                   algo_id=data['algo_id'], payload=pending['payload'])
                s['pending'], s['uncertain'], s['failed'], s['alert'] = None, False, False, None
            elif report.complete and report.status == 'CANCELED':
                s['active'], s['pending'], s['uncertain'], s['failed'] = None, None, False, False
                s['alert'] = None
            elif report.complete and report.status == 'REJECTED':
                s['pending'], s['uncertain'], s['failed'] = None, False, True
                s['alert'] = 'protection_request_failed'
            elif report.status == 'TRIGGERED':
                if s['active'] is not None:
                    s['active']['algo_id'] = data['algo_id']
                s['triggered'], s['alert'] = True, 'protection_triggered_requires_fill_reconciliation'
            # NOT_FOUND/incomplete/cancel ACK remains UNKNOWN. No blind resend.
            self.save(bot_id, s)
            if had_active != (s['active'] is not None):
                self.j.execution._dirty(bot_id)
            if self.blocked(bot_id) and not s['alert']:
                s['alert'] = 'protection_mismatch'
                self.save(bot_id, s)
            return s
