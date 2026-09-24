# Reconciliation classification closure assessment — 2026-09-22

本片只使用既有 185 組 `/api/v5/account/subtypes` 非敏感 catalog 與 OKX 公開文件；未呼叫 private endpoint、未讀 credential、未開既有 DB、未交易或修改帳戶。

## 結果

依已核准 C1-B／C2-A／C3-B／C4-B，新增 21 組可由公開官方語意直接支撐的分類：

- `internal` 12 組：`4/114,115`、`5/16,17`、`13/131,132`、`16/306,307,308,309`、`29/224,225`。
- `forbidden` 9 組：`1/420`、`6/160,161,162`、`15/210,211,212,213,216`。
- coverage 由 120/185 提升為 141/185：7 external、83 internal、51 forbidden；44 unknown，`complete=false`。

### Residual closure pass

後續依相同 C1-B／C2-A／C4-B 邊界，僅使用已保存的官方 catalog 語意再收斂 12 組：

- `internal` 6 組：`4/312`、`5/313,314,315,316,317`。這些都是 liability offset／forced-repayment／liquidation repayment lifecycle，不把 borrow/repay principal 當作資本注入或抽離。
- `forbidden` 3 組：`6/332,333,334`。官方 catalog 明示為 Margin in/out/offset；catOS v1 專用 USDT-M SWAP 帳戶不支援 MARGIN allocation activity。
- `external` 3 組：`33/357,358,359`。官方 catalog 分別明示 forced-converted asset 移往 Funding account、OTC system account transfer in/out，屬 verified trading-account equity scope 的明確跨界；沿用 signed `balChg`，不取絕對值。
- 最新 coverage：153/185：10 external、89 internal、54 forbidden；32 unknown，`complete=false`。

### Forced-repayment public-evidence pass

後續補查 OKX 官方 Forced Repayment／Auto Crypto Conversion 說明，文件明示 Trading Account 內會出售或轉換資產以償還該帳戶 liability；只有文件或 catalog 明示移往 Funding／OTC system account 時才形成 verified Trading Account scope crossing。因此再收斂 3 組：

- `internal` 3 組：`33/348,349` Forced repayment、`33/356` Forced conversion (pending deduction)。依 C2-A／C4-B，這三列沒有跨帳戶語意，視為 verified account equity scope 內的 liability settlement／conversion；不把 principal repayment 當資本流。
- `33/357,358,359` 維持 `external`，因 catalog 明示 Funding／OTC system account crossing。
- 當時 coverage：156/185：10 external、92 internal、54 forbidden；29 unknown，`complete=false`。

公開證據：

- OKX API guide：forced repayment buy/sell 被列為 trade filled price；`16/17` 被列在 liquidation price 語意；Quick Margin 欄位標示為 MARGIN-only，並說明 isolated manual transfer／position margin adjustment。
  - https://www.okx.com/docs-v5/en/
- OKX API changelog：`ddh` 定義為 `Delta dynamic hedge`，並明示 `type=13`、`131=ddh buy`、`132=ddh sell`。
  - https://www.okx.com/docs-v5/log_en/
- OKX borrowing/repayment 文件：borrow 形成 trading-account liability；One-click repay 在 Trading account 內出售 BTC／ETH／USDT 餘額後自動償還 liability。
  - https://www.okx.com/en-us/help/borrowing-and-repaying-in-multi-currency-and-portfolio-margin-account-modes
- OKX Forced Repayment／Auto Crypto Conversion 文件：Trading Account 內可出售／轉換資產以購回 overborrowed crypto、降低 negative balance／liability；另明示 forced repayment 可在 Trading Account 發生，即使其他帳戶持有同幣資產。
  - https://www.okx.com/help/introduction-to-the-forced-repayment-and-auto-crypto-conversion-mechanisms
- OKX VIP Loan 文件：VIP Loan 使用獨立 risk unit／Funding account loan lifecycle，不屬 catOS v1 專用 USDT-M SWAP 帳戶活動。
  - https://www.okx.com/help/updates-to-vip-loan-and-credit-line-risk-unit-terms-and-conditions
  - https://www.okx.com/en-us/help/vip-loan

## 2026-09-22 歷史狀態：仍未解 29 組

- type 1：290、292。
- type 4：376、377、393、394。
- type 12：276、277。
- type 22：259、260。
- type 24：274、275。
- type 26：441、442、443、444、445、446。
- type 37：421、422、423、424、425、426、427、432、433、434、435。

其中空白描述仍不得猜分類；`1/292` 雖已補到 OKX 明示未使用 Trading Bonus 會被 reclaim，但仍缺原始 credit／reclamation 跨日如何處理的政策；corporate action 公開文件可證明部分 Stock Perpetual rebase 保持 account equity，但同一 catalog type 亦包含 cash dividend、fund/share adjustment，仍不足以逐項判定 dedicated account scope。上述 29 組維持 `unknown_external_flow` 阻斷。

此片不把 `FlowClassification.complete` 改為 true，也不改 formal gate 行為。

### 29 Residual Unknowns Public-Evidence Assessment Pass

針對剩餘 29 組未解 subtype，依本次指令僅使用 OKX 官方公開文件、API 文件、API Changelog (log_en) 及 Help Center 條款進行逐項調查：

1. **查過的 subtype 清單（共 29 組）**：
   - 空白描述群（17 組）：
     - `1/290`（Transfer / [空白]）
     - `4/376, 377, 393, 394`（Auto token conversion / [空白]）
     - `12/276, 277`（Strategy transfer / [空白]）
     - `22/259, 260`（[空白] / [空白]）
     - `24/274, 275`（[空白] / [空白]）
     - `26/441, 442, 443, 444, 445, 446`（[空白] / [空白]）
   - Trading Bonus Reclamation（1 組）：
     - `1/292`（Transfer / Trading bonus reclamation transfer out）
   - Corporate Action 群（11 組）：
     - `37/421`（Corporate action: cash dividend）
     - `37/422`（Corporate action: open long）
     - `37/423`（Corporate action: open short）
     - `37/424`（Corporate action: close long）
     - `37/425`（Corporate action: close short）
     - `37/426`（Corporate action: buy）
     - `37/427`（Corporate action: sell）
     - `37/432`（Corporate Action Dividend）
     - `37/433`（Corporate Action Fund Transfer）
     - `37/434`（Corporate Action User Fund Adjustment）
     - `37/435`（Corporate Action Share Adjustment）

2. **找到的官方來源與具體證據**：
   - OKX API v5 Upcoming Changes (Log_en)（https://www.okx.com/docs-v5/log_en/）：
     - 查到 `376` 為 "Collateralized borrowing auto conversion buy"，`377` 為 "Collateralized borrowing auto conversion sell"，觸發條件為「特定幣種質押借幣負債達到平台風控限額時，系統自動賣出質押幣買入負債幣以降低風險」。
     - 未查到 `4/393, 394`、`12/276, 277`、`22/259, 260`、`24/274, 275`、`26/441-446` 的任何定義。
   - OKX Help Center「Trading Bonus Terms and Conditions / Introduction to Trading Bonus」：
     - 明示 Trading bonus 為平台發放之交易手續費／虧損折抵保證金額度，不可提現至資金帳戶或子帳戶；未在效期內使用或切換帳戶模式時，系統將執行 "Trading bonus reclamation" 自動回收剩餘未消耗 bonus。
   - OKX Help Center「Stock Perpetuals and Tokenized Stocks Corporate Actions」：
     - 明示在標的股票發生除息、分割、反分割、代碼變更等公司行動時，平台會對持倉進行現金股息支付（cash dividend）、關閉舊合約並開立新合約（open/close long/short/buy/sell）或份額調整（share/fund adjustment）。

3. **為什麼仍不足以判定 equity boundary（嚴格遵守不推論原則）**：
   - **空白描述項（17 組）**：
     - 契約與安全紅線明文規定「blank typeDesc/subTypeDesc 不得猜」、「不得因 subtype 編號相鄰而猜分類」、「不得因 type 名稱相同而整組套分類」。
     - `4/376, 377` 雖在 log_en 出現名稱，但在當前 catalog JSON 中仍為空白描述，且質押借幣自動換幣屬於跨幣種或槓桿保證金機制的強制處置，是否涉及專用子帳戶無抵押權益、抑或屬 forbidden 借貸活動，仍缺帳戶邊界定義。其餘 15 組（`1/290`、`4/393, 394`、`12/276, 277`、`22/259, 260`、`24/274, 275`、`26/441-446`）官方文件完全無公開語意，不可猜測。
   - **Trading Bonus Reclamation `1/292`（1 組）**：
     - 契約與指令明定「必須考慮原始 bonus credit 與 reclaim 的資本流／跨日語意；沒有足夠政策依據就保持 unknown」。
     - 若視為 external outflow，跨日回收會錯誤扣減當日 external flow，扭曲當日日損分母；若視為 internal，未交易之額度失效會被算成策略虧損；若標為 forbidden，平台自動收回過期贈金將癱瘓對帳。在欠缺跨日權益與贈金會計政策下，保持 unknown 是唯一安全選擇。
   - **Corporate Action `37/421-427, 432-435`（11 組）**：
     - 契約與指令明定「不得因『這個產品看起來不會用到』就直接標 forbidden」、「不可只因 Stock Perpetual 某些 rebase 保持 equity 就把整個 type 37 標 internal」、「Corporate Action 必須逐項確認產品／帳戶 scope」。
     - 現金股息（`421, 432`）究竟派發至 Trading Account 還是 Funding Account、是否應依 C3-B 視為外部資本調整，公開文件未記載帳務入帳路徑；轉帳（`433`）與資金／份額調整（`434, 435`）是否跨越受管帳戶邊界缺乏具體流水規格；持倉開閉（`422-427`）雖為名義調整，但無法證明是否伴隨現金結算跨界。

4. **下一步需求**：
   - 空白描述項（17 組）：需要 OKX 官方更新 `/api/v5/account/subtypes` 或官方 changelog 補齊 subtype definition。
   - `1/292`：需要使用者與 Astra 明確定案 Trading Bonus Reclamation 之會計政策（Policy Decision，例如是否在專用子帳戶禁用贈金活動以標為 forbidden，或定義跨日折抵扣減公式）。
   - Type 37（11 組）：需要 OKX 官方發布具體 Corporate Action 帳單流水欄位規範（官方 subtype definition）或真實帳單 evidence，或使用者定案「專用 USDT-M SWAP 帳戶如出現非 SWAP 股票公司行動一律標為 forbidden」的業務政策。

## 驗證

- `python -m unittest tests.test_okx_readonly`：21/21 OK。
- `git diff --check`（本片 7 個 code/doc 檔）：exit 0；僅既有 LF/CRLF working-tree warning。
- residual closure 後：`python -m unittest tests.test_okx_readonly tests.test_account_report` 63/63 OK；`python -m unittest discover -s tests -p test_reconciliation_gate.py` 16/16 OK，合計 79/79。直接 package 啟動 gate 測試會因既有 `from test_ipc import config` 頂層測試匯入方式失敗；discover 啟動可正確載入，未修改產品碼或測試 import contract。
- forced-repayment public-evidence pass 後再次執行 `python -m unittest tests.test_okx_readonly tests.test_account_report -v` 63/63 OK；`python -m unittest discover -s tests -p test_reconciliation_gate.py -v` 16/16 OK，合計 79/79；scoped `git diff --check` exit 0。
- 本輪 29 個 residual unknown public-evidence assessment 完成後：測試與 coverage 維持 156/185（10 external、92 internal、54 forbidden、29 unknown，`complete=false`）。`python -m unittest tests.test_okx_readonly tests.test_account_report -v` 63/63 OK；`python -m unittest discover -s tests -p test_reconciliation_gate.py -v` 16/16 OK，合計 79/79 OK；scoped `git diff --check` exit 0。未為產生 code diff 進行不安全硬分類。
- 針對 `4/376,377,393,394`、`22/259,260`、`26/441-446`、`1/290`、`1/292`、`37/421-427,432-435` 均維持 unknown，不由 type 名稱、序號鄰近或產品概念外推。

### Corporate-action rebase public-evidence pass — 2026-09-23

OKX 2026 年 Stock Perpetual 官方文件補足了先前缺口：stock split／reverse split rebase 明示為 value-neutral，position value 與 account equity 在調整前後維持不變；官方條款亦明示 corporate-action billing records 會反映對 position 與 account balance 的調整。搭配已保存官方 subtype catalog 的逐項名稱，可在既有 C2-A verified Trading Account equity scope 下，將純持倉重整的 6 組 subtype 收斂為 `internal`：

- `37/422` Corporate action: open long
- `37/423` Corporate action: open short
- `37/424` Corporate action: close long
- `37/425` Corporate action: close short
- `37/426` Corporate action: buy
- `37/427` Corporate action: sell

本輪沒有把整個 type 37 套用同一分類。`37/421` cash dividend、`37/432` Dividend、`37/433` Fund Transfer、`37/434` User Fund Adjustment、`37/435` Share Adjustment 仍維持 unknown；後四者不能只由名稱推定帳戶邊界，股息也仍涉及 C3-B 非策略正向 credit 的會計語意。

官方公開證據：

- OKX Stock Split Adjustments for Stock Perpetuals：rebase 明示 value-neutral，position value 與 account equity preserved。
  - https://www.okx.com/en-au/help/stock-split-adjustments-for-stock-perpetuals
- OKX Terms and Conditions for Stock Perpetuals：corporate-action adjustments 用於維持 position notional value，且 post-CA billing records 會反映 position/account-balance adjustments。
  - https://www.okx.com/fr/help/terms-and-conditions-for-stock-perpetuals

後續再由現行 OKX API guide 直接取得 `274 = Spread trading close long`、`275 = Spread trading close short` 的官方定義，因此 `24/274,275` 可沿 C2-A 收斂為 `internal`；這不是依 subtype 鄰近編號推論。

最新 coverage：164/185：10 external、100 internal、54 forbidden；21 unknown，`complete=false`。仍未解清單為：`1/290,292`、`4/376,377,393,394`、`12/276,277`、`22/259,260`、`26/441-446`、`37/421,432-435`。formal gate 對未分類 bill 的 fail-closed 行為不變。

本輪實跑驗證：`python -B -m unittest tests.test_okx_readonly tests.test_account_report -v` 63/63 OK；`python -B -m unittest discover -s tests -p test_reconciliation_gate.py -v` 16/16 OK。tracked touched files 的 `git diff --check` exit 0，僅既有 LF/CRLF warning；本輪碰到的三個 untracked 文件另查 trailing whitespace 為 0。

### Collateralized-borrowing auto-conversion public-evidence pass — 2026-09-23

現行 OKX API guide 與 API changelog 已直接定義 `376 = Collateralized borrowing auto conversion buy`、`377 = Collateralized borrowing auto conversion sell`。OKX 官方 Forced Repayment／Auto Crypto Conversion 文件進一步明示，該機制會在使用者帳戶內出售資產、買入負債幣以降低 borrowing；文件沒有為這兩個 subtype 指出 Funding／OTC system account 等跨 verified Trading Account equity scope 的移轉。依既有 C2-A／C4-B，這類帳內 liability principal／conversion 不視為 external capital flow，因此收斂為 `internal`：

- `4/376` Collateralized borrowing auto conversion buy
- `4/377` Collateralized borrowing auto conversion sell

官方公開證據：

- OKX API guide：Transaction details 的 `subType` enum 直接列出 376／377。
  - https://www.okx.com/docs-v5/en/
- OKX API changelog：2025-05-06 新增 376／377 定義。
  - https://www.okx.com/docs-v5/log_en/
- OKX Introduction to the Forced Repayment and Auto Crypto Conversion Mechanisms：說明 collateral-limit auto conversion 會出售帳戶內 collateral asset，並以轉換結果降低 borrowing liability。
  - https://www.okx.com/help/introduction-to-the-forced-repayment-and-auto-crypto-conversion-mechanisms

本輪重新檢查其餘 residual subtype；官方 API guide／changelog 仍未提供 `1/290`、`4/393,394`、`12/276,277`、`22/259,260`、`26/441-446` 的直接定義。`1/292` 仍缺 Trading Bonus credit/reclamation 跨日會計政策；`37/421,432-435` 仍缺足以逐項判斷 verified account equity scope 的 billing 規格。因此不依 type 名稱、相鄰編號或產品猜測分類。

最新 coverage：166/185：10 external、102 internal、54 forbidden；19 unknown，`complete=false`。仍未解清單為：`1/290,292`、`4/393,394`、`12/276,277`、`22/259,260`、`26/441-446`、`37/421,432-435`。formal gate 對未分類 bill 的 fail-closed 行為不變。

本輪驗證：`python -B -m unittest tests.test_okx_readonly tests.test_account_report -v` 63/63 OK；`python -B -m unittest discover -s tests -p test_reconciliation_gate.py -v` 16/16 OK；`git diff --check` exit 0，僅既有 LF/CRLF warning；本輪碰到的三個 untracked 文件 trailing whitespace 為 0。
