"""Explicit state adapter for the inspected, unchanged SMATrend artifact."""

from examples.closed_bar_demo import SMATrend


def restore_sma(checkpoint):
    strategy = SMATrend()
    strategy.closes.extend(checkpoint.closes)
    return strategy


def snapshot_closes(strategy):
    return tuple(strategy.closes)
