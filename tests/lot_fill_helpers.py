from decimal import Decimal as D

from catos import lots
from catos.lot_accounting import SyntheticFill
from lot_journal_helpers import contract, scope


def opening(journal, *, order="open", seq=1, side="long", quantity=D("3"), bot="lot-bot"):
    return journal.lot_fills.bind_order(
        source_id="synthetic", order_id=order,
        context=lots.IntentContext(scope(), bot, contract(), seq, False),
        intent=lots.OpenLot(side, quantity, lots.LotProtection("mark", None, None)))


def fill(*, order="open", seq=1, trade=None, quantity=D("1"), price=D("100"), fee=D("0.01")):
    return SyntheticFill(scope(), "synthetic", contract().inst_id, order, trade or f"trade-{seq}",
                         seq, quantity, price, fee)


def terminal(journal, *, order="open", seq=1, quantity=D("3"), status="FILLED", terminal_id="terminal"):
    return journal.lot_fills.finish_order(scope=scope(), source_id="synthetic", inst_id=contract().inst_id,
                                         order_id=order, terminal_id=terminal_id, status=status,
                                         final_fill_seq=seq, final_filled_qty=quantity)


def current(journal):
    return journal.lots.list_current(scope=scope(), bot_id="lot-bot")[0]


def close_order(journal, *, order="close", seq=2, quantity=None):
    lot = current(journal).lot
    return journal.lot_fills.bind_order(
        source_id="synthetic", order_id=order,
        context=lots.IntentContext(scope(), "lot-bot", contract(), seq, False),
        intent=lots.CloseLot(lot.lot_id, quantity, lot.revision))
