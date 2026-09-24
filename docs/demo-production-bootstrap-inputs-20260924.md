# catOSv1 Demo production bootstrap inputs

使用者於 2026-09-24 核准依 Sol 建議先鎖定 production bootstrap inputs。以下設定只決定新 ledger 的 Bot/config 與固定風控參數；不等於 Q1、reconciliation 或交易授權。

## 已定案

- `bot_id = sma-trend-btc-usdt-swap-v1`
- strategy artifact：既有 `sma-trend` v1；`timeframe_ms=900000`（15m）、`warmup_bars=2`
- contract：`BTC-USDT-SWAP`
  - `base_per_contract=0.01 BTC`
  - `tick_size=0.1 USDT`
  - `lot_size=0.01 contracts`
  - `min_size=0.01 contracts`
- `fixture_budget=Decimal("100")`：risk mode 不用此值做交易裁決；僅保留為既有 Journal metadata／resume identity，不代表真實餘額、E₀ 或可交易預算。
- risk limits：`leverage=3.0`、`symbol_share=0.50`、`soft_loss=0.10`、`hard_loss=0.20`，沿用既有已確認 v1 policy。

機器可讀單一來源為 `catos/demo_production_inputs.py::catosv1_demo_inputs()`。

## OKX public instrument 驗證

2026-09-24T10:37:53+08:00 以無 credential 的 public `GET /api/v5/public/instruments?instType=SWAP&instId=BTC-USDT-SWAP` 核對：`state=live`、`ctType=linear`、`ctVal=0.01`、`ctMult=1`、`ctValCcy=BTC`、`settleCcy=USDT`、`tickSz=0.1`、`lotSz=0.01`、`minSz=0.01`。`base_per_contract` 因此固定為 `ctVal × ctMult = 0.01 BTC`。

bootstrap 前必須對當時最新 public instrument row 再呼叫 `verify_okx_public_instrument()`；任一規格或 `state` 漂移即 fail closed，不以這份 2026-09-24 snapshot 取代當時 metadata。

## sizing 邊界

目前 inspected SMA v1 的 signal artifact 在 long 條件成立時固定輸出 target position `2` contracts。依上述真實合約規格即 0.02 BTC 名目；實際 entry 是否可送仍由當時 verified equity、3.0x／50% exposure gate 與獨立一次性 `DemoTradeGrant.max_entry_mark_notional_usdt` 同時限制。bootstrap 本身不授權或送出該 entry。

## 尚未成立

production ledger／binding 仍不存在。現有 production Q1 evidence 仍有 bills，不能建立 E₀；下一個可行 collection 時點仍是 2026-09-25 07:07:33+08:00 之後，且需要當次明確 production read-only 採集授權。只有新 evidence 同時滿足 Q1、accounting、identity、responsibility 與 freshness/window contract，才可進入 bootstrap operation；成功 bootstrap 後 `reconciled=false`、`trade_authorized=false` 仍保持。
