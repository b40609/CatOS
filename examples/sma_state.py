"""Explicit state adapter for the inspected, unchanged SMATrend artifact."""

from decimal import Decimal


def restore_sma(checkpoint):
    if checkpoint.config.strategy_artifact is not None:
        from catos.research_catalog import load_registered_strategy, provenance

        strategy = load_registered_strategy(provenance())(2, Decimal("2"))
    else:
        from examples.closed_bar_demo import SMATrend

        strategy = SMATrend()
    strategy.closes.extend(checkpoint.closes)
    return strategy


def snapshot_closes(strategy):
    return tuple(strategy.closes)
