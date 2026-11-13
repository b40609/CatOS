"""Fixed v1 simulation registry and read-only Decimal projections (no ledger access)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext

from catos import research, risk
from catos.research_catalog import (APPROVED_STRATEGY_SHA256, DEFAULT_REQUEST, STRATEGY_ENTRY,
                                    STRATEGY_FILES, STRATEGY_ID, STRATEGY_VERSION)

BOT_ID = "sim-control-sma"
STRATEGY_NAME = "SMA 趨勢（Long / Flat）"
STRATEGY_DESCRIPTION = ("登錄的固定 SMA 策略：本根收盤決策、下一根開盤加明示滑價成交；"
                        "v1 只允許本機合成模擬（local），不接 Demo／Live。")
INVARIANTS = {"fixed_tag": "41cb53c54d6dABDE", "settlement": "cross_net_mode",
              "arithmetic": "decimal_text"}
ACCOUNT_FIELDS = ("position", "average_entry", "balance", "realized_pnl", "unrealized_pnl",
                  "equity", "fees", "funding_paid")
ACCOUNT_EVENTS = {"signal", "fill", "final_account", "day_basis"}
MAX_EVENT_LIMIT = 200
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
ZERO = Decimal("0")


def iso_to_ms(value):
    if value is None:
        return None
    return (datetime.fromisoformat(value) - EPOCH) // timedelta(milliseconds=1)


def strategy_entry():
    return {"strategy_id": STRATEGY_ID, "version": STRATEGY_VERSION, "name": STRATEGY_NAME,
            "description": STRATEGY_DESCRIPTION, "artifact_hash": APPROVED_STRATEGY_SHA256,
            "entry": STRATEGY_ENTRY, "approval_state": "approved", "allowed_modes": ["local"],
            "defaults": {"parameters": dict(DEFAULT_REQUEST["parameters"]),
                         "warmup_bars": DEFAULT_REQUEST["warmup_bars"]},
            "source_files": list(STRATEGY_FILES), "kind": "registered_python_module"}


def bot_static(contract, timeframe_ms, created_at_ms):
    inst_id = None if contract is None else contract.inst_id
    return {"bot_id": BOT_ID, "mode": "local", "strategy_id": STRATEGY_ID,
            "strategy_version": STRATEGY_VERSION, "strategy_name": STRATEGY_NAME,
            "artifact_hash": APPROVED_STRATEGY_SHA256,
            "parameters": dict(DEFAULT_REQUEST["parameters"]),
            "inst_id": inst_id, "symbol": inst_id, "contract": contract_wire(contract),
            "timeframe_ms": timeframe_ms, "trusted": True, "created_at_ms": created_at_ms}


def contract_wire(contract):
    if contract is None:
        return None
    return {"inst_id": contract.inst_id, "base_per_contract": str(contract.base_per_contract),
            "tick_size": str(contract.tick_size), "lot_size": str(contract.lot_size),
            "min_size": str(contract.min_size)}


def latest_account(run):
    """Latest Decimal-string account view and the events it came from.

    final_account is exact. Otherwise the last signal's pre-decision view is used;
    when a fill followed that signal in the same bar, the fill's durable
    position/fees/equity override it (other fields lag one bar).
    """
    if run is None:
        return None, None, None
    final = next((e for e in reversed(run["events"]) if e["kind"] == "final_account"), None)
    if final is not None:
        return dict(final["account"]), final.get("risk_state"), "final_account"
    signal, fill = run.get("last_signal"), run.get("last_fill")
    if signal is None:
        return None, None, None
    account = dict(signal["account"])
    source = "signal"
    if fill is not None and fill.get("seq", -1) >= signal.get("seq", 0):
        account.update(position=fill["position"], fees=fill["fees"], equity=fill["equity"])
        source = "signal_fill"
    return account, signal.get("risk_state"), source


def latest_mark(run, risk_state):
    if risk_state and risk_state.get("snapshot"):
        return risk_state["snapshot"]["mark"]
    signal = None if run is None else run.get("last_signal")
    return None if signal is None else signal.get("mark")


def notional(contract, position, mark, pending_buy=ZERO, pending_sell=ZERO):
    if contract is None or position is None or mark is None:
        return None
    with localcontext(research._CONTEXT):
        return risk.worst_notional(Decimal(position), Decimal(pending_buy), Decimal(pending_sell),
                                   contract.base_per_contract, Decimal(mark))


def risk_status(state):
    reasons = set(state.get("reasons") or ())
    if reasons & {"hard_loss", "manual_kill"}:
        return "hard_latch"
    if "soft_loss" in reasons:
        return "soft_latch"
    if state.get("basis") is None or state.get("health") != "HEALTHY":
        return "missing"
    return "normal"


def risk_projection(run, risk_state, contract, limits):
    """RiskSnapshotDTO body (without version); None when no risk observation exists."""
    if run is None or risk_state is None:
        return None
    state = dict(risk_state)
    basis = None if state.get("basis") is None else dict(state["basis"])
    if basis is not None:
        basis["period_start_ms"] = basis["day"] * risk.DAY_MS - risk.TAIPEI_OFFSET_MS
    snapshot = None if state.get("snapshot") is None else dict(state["snapshot"])
    if snapshot is not None:
        snapshot.pop("basis", None)
    derived = {"period_pnl": None, "period_pnl_ratio": None, "notional": None,
               "effective_leverage": None, "exposure_budget": None, "symbol_budget": None,
               "can_increase": (state.get("mode") == "RUN" and state.get("health") == "HEALTHY"
                                and basis is not None),
               "status": risk_status(state)}
    if snapshot is not None:
        with localcontext(research._CONTEXT):
            equity, risk_equity = Decimal(snapshot["equity"]), Decimal(snapshot["risk_equity"])
            if basis is not None:
                pnl = equity - Decimal(basis["equity"]) - Decimal(snapshot["external_net"])
                derived["period_pnl"] = str(pnl)
                derived["period_pnl_ratio"] = str(pnl / Decimal(basis["equity"]))
            worst = notional(contract, snapshot["position"], snapshot["mark"],
                             snapshot["pending_buy"], snapshot["pending_sell"])
            if worst is not None:
                derived["notional"] = str(worst)
                leverage = risk.effective_leverage((worst,), equity)
                derived["effective_leverage"] = None if leverage is None else str(leverage)
            budget = limits.leverage * risk_equity
            derived["exposure_budget"] = str(budget)
            derived["symbol_budget"] = str(budget * limits.symbol_share)
    return {"run_id": run["run_id"], "bot_id": BOT_ID, "run_state": run["control_state"],
            "seq": state.get("seq"), "time_ms": state.get("time_ms"), "mode": state.get("mode"),
            "health": state.get("health"), "phase": state.get("phase"),
            "reasons": list(state.get("reasons") or ()), "epoch": state.get("epoch"),
            "limits": limits.to_wire(), "basis": basis, "snapshot": snapshot, "derived": derived}


def position_projection(run, account, risk_state, contract):
    if run is None or account is None or Decimal(account["position"]) == ZERO:
        return []
    mark = latest_mark(run, risk_state)
    snapshot = (risk_state or {}).get("snapshot") or {}
    worst = notional(contract, account["position"], mark)
    return [{"bot_id": BOT_ID, "run_id": run["run_id"], "run_state": run["control_state"],
             "inst_id": None if contract is None else contract.inst_id,
             "symbol": None if contract is None else contract.inst_id,
             "position": account["position"], "average_entry": account["average_entry"],
             "mark": mark, "unrealized_pnl": account["unrealized_pnl"],
             "notional": None if worst is None else str(worst),
             "verified": snapshot.get("position_verified"),
             "protection": None, "funding_interval_ms": None, "funding_rate": None,
             "liquidation_price": None, "margin": None}]


def summary_projection(run, account, risk_dto, active, limits):
    if run is None or account is None:
        return None
    derived = None if risk_dto is None else risk_dto["derived"]
    basis = None if risk_dto is None else risk_dto["basis"]
    return {"equity": account["equity"], "realized_pnl": account["realized_pnl"],
            "unrealized_pnl": account["unrealized_pnl"], "fees": account["fees"],
            "period_pnl": None if derived is None else derived["period_pnl"],
            "period_pnl_ratio": None if derived is None else derived["period_pnl_ratio"],
            "period_start_ms": None if basis is None else basis["period_start_ms"],
            "basis_equity": None if basis is None else basis["equity"],
            "running_bots": 0 if active is None else 1, "total_bots": 1,
            "risk_status": None if derived is None else derived["status"],
            "effective_leverage": None if derived is None else derived["effective_leverage"],
            "leverage_limit": str(limits.leverage), "invariants": dict(INVARIANTS)}


def event_level_category(event):
    kind = event["kind"]
    if kind == "run_state":
        state = event.get("state")
        level = ("ERROR" if state in ("failed", "recovery_required")
                 else "WARN" if state == "stopping" else "INFO")
        return level, "SYSTEM"
    if kind == "stop_requested":
        return "WARN", "SYSTEM"
    if kind in ("warmup", "signal"):
        state = event.get("risk_state") or {}
        return ("WARN" if state.get("mode") not in (None, "RUN") else "INFO"), "WORKER"
    if kind == "fill":
        return "INFO", "ORDER"
    if kind in ("final_account", "day_basis"):
        state = event.get("risk_state") or {}
        return ("WARN" if state.get("reasons") or state.get("mode") not in (None, "RUN")
                else "INFO"), "RISK"
    if kind == "kill_switch":
        return "ERROR", "RISK"
    if kind in ("stop", "anomaly"):
        return "ERROR" if kind == "anomaly" else "WARN", "SYSTEM"
    return "INFO", "SYSTEM"


def event_dto(run_id, event):
    level, category = event_level_category(event)
    payload = {key: value for key, value in event.items()
               if key not in ("kind", "wall_time", "wall_time_ms", "event_seq")}
    return {"seq": event["event_seq"], "run_id": run_id, "bot_id": BOT_ID, "kind": event["kind"],
            "wall_time_ms": event.get("wall_time_ms"),
            "synthetic_time_ms": event.get("synthetic_time_ms"),
            "level": level, "category": category, "payload": payload}
