# 依實際流水判定分類完整性

2026-09-23 使用者明確同意縮減方案，取代先前「整份 OKX catalog 必須 complete=true 才放行」政策。166/185、19 unknown、catalog complete=false 仍保留為 coverage 資訊，未使用的 subtype 不再獨立構成 production blocker。

`catos/reconciliation_gate.py` 移除全目錄 completeness 阻擋；保留實際 report discrepancy 的 unknown／forbidden 阻擋、day-ledger unknown count、classification ID 一致性、完整採集、verified E₀ 與責任檢查。沒有把 unknown 分類成 internal 或把金額當零；沒有新增交易授權、告警通道或更動合法減倉路径，沿用既有 blocker／Supervisor 行為。此縮減只保證完整採集範圍內的實際流水可分類，不保證預先支援所有 OKX 業務。

## 本輪驗證

- `python -B -m unittest discover -s tests -p test_reconciliation_gate.py -q`：17/17 OK，新增 partial catalog 下已知流水通過、unknown／forbidden／採集不完整仍阻擋案例。
- `python -B -m unittest discover -s tests -p test_demo_reconciliation.py -q`：30/30 OK，production mapping + synthetic empty bills 可完成 reconciliation，trade_authorized 仍 false。
- `python -B -m unittest tests.test_account_report -q`：42/42 OK，保留實際 bills 分類行為。
- 首次 integration 執行 29/30，原測試 day ledger 使用 synthetic classification ID，與 production mapping 不一致；修正測試資料使 ID 一致後 30/30。未放寬 ID 檢查。

合計 89/89；只用 temporary DB／synthetic evidence，未修改既有 DB/schema、Yaozi/Lot/market 或 Git 狀態。

## 同輪 UID 診斷

沿用指定 `Desktop/OKX_API.txt` 與既有 bounded GET 授權，額外只查一次 Demo account/config。received_ms=1790150949728，identity_fields_valid=true、expected_uid_pass=false、subaccount_pass=false、main_account_confirmed=true（uid == mainUid）。已確認目前檔案選用的 credential 屬於 Demo 主帳戶，並非指定 catOSv1；不輸出 UID／credential，不讀其他檔案、不修改 profile 或帳戶。若來源含 profiles，loader 僅依 default_profile 選取，不會搜尋匹配 UID 的其他金鑰。需使用 catOSv1 對應的 Demo credential，不能只改 account alias 或 UID 常數。

remaining blockers：指定子帳戶 credential／identity、遠端 responsibility 與 local UNKNOWN 尚未完成、D1-A verified E₀；Demo write 未授權。19 個未遇到的 subtype 不再列獨立 blocker。
