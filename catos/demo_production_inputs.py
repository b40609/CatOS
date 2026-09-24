"""Pinned non-secret inputs for the first catOSv1 OKX Demo ledger bootstrap.

The values in this module are operator-approved configuration, not remote
account evidence.  Callers must still provide the independently verified Demo
UID digest and a fresh production read-only responsibility/Q1 evidence set.
"""

from dataclasses import dataclass
from decimal import Decimal

from catos import ipc, risk
from catos.research import ContractSpec


D = Decimal

VERSION = "catosv1-demo-production-inputs.v1"
BOT_ID = "sma-trend-btc-usdt-swap-v1"
OKX_PUBLIC_INSTRUMENT_SOURCE = "GET /api/v5/public/instruments?instType=SWAP&instId=BTC-USDT-SWAP"
OKX_PUBLIC_INSTRUMENT_OBSERVED_AT = "2026-09-24T10:37:53+08:00"


@dataclass(frozen=True)
class DemoProductionInputs:
    version: str
    bot_id: str
    config: ipc.WorkerConfig
    fixture_budget: Decimal
    risk_limits: risk.Limits


class DemoProductionInputsError(ValueError):
    """Stable validation failure for the pinned public instrument contract."""


def catosv1_demo_inputs() -> DemoProductionInputs:
    return DemoProductionInputs(
        version=VERSION,
        bot_id=BOT_ID,
        config=ipc.WorkerConfig(
            ContractSpec(
                "BTC-USDT-SWAP",
                base_per_contract=D("0.01"),
                tick_size=D("0.1"),
                lot_size=D("0.01"),
                min_size=D("0.01"),
            ),
            timeframe_ms=900_000,
            warmup_bars=2,
        ),
        # Risk mode does not use this value for trading decisions.  It remains
        # a positive legacy Journal identity field and is pinned for resume.
        fixture_budget=D("100"),
        risk_limits=risk.Limits(
            leverage=D("3.0"),
            symbol_share=D("0.50"),
            soft_loss=D("0.10"),
            hard_loss=D("0.20"),
        ),
    )


def verify_okx_public_instrument(row: dict) -> None:
    """Fail closed if current public OKX metadata no longer matches the pin."""
    if type(row) is not dict:
        raise DemoProductionInputsError("instrument_metadata_invalid")
    expected_text = {
        "instId": "BTC-USDT-SWAP",
        "state": "live",
        "ctType": "linear",
        "ctValCcy": "BTC",
        "settleCcy": "USDT",
    }
    for key, expected in expected_text.items():
        if row.get(key) != expected:
            raise DemoProductionInputsError("instrument_metadata_mismatch")
    try:
        ct_val = ipc.decimal_text(row.get("ctVal"), "ctVal", positive=True)
        ct_mult = ipc.decimal_text(row.get("ctMult"), "ctMult", positive=True)
        tick_size = ipc.decimal_text(row.get("tickSz"), "tickSz", positive=True)
        lot_size = ipc.decimal_text(row.get("lotSz"), "lotSz", positive=True)
        min_size = ipc.decimal_text(row.get("minSz"), "minSz", positive=True)
    except ipc.ProtocolError as exc:
        raise DemoProductionInputsError("instrument_metadata_invalid") from exc

    config = catosv1_demo_inputs().config.contract
    if (ct_val * ct_mult != config.base_per_contract
            or tick_size != config.tick_size
            or lot_size != config.lot_size
            or min_size != config.min_size):
        raise DemoProductionInputsError("instrument_metadata_mismatch")
