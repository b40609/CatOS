# Market-intel social provider 接續

更新：2026-09-21；social raw metric slice 已驗收，後續 universe mapping coverage 已完成實作與 focused 驗證。

## 接手現況

現行 social slice 包含 `market_social.py`、schema 14 的 `social_source_run` / `social_metric_snapshot`、writer、reader、`/intel/social`、`/intel/picks/{symbol}/social` 與 source-coverage diagnostics。Astra 後續補上 transport failure evidence、writer fail-closed validation 與防禦測試；Sol 已用暫存 DB 驗收整條鏈路。

Git provenance 只能確認歷史 snapshot `80747fe` 的 `market_intel.py` 尚為 schema 10，沒有 social schema；目前 `market_social.py`、schema 14 版本 `market_intel.py`、相關 tests 與 handoff 都是未追蹤工作樹內容，因此無法從現有 Git 歷史把 schema 14 歸屬到特定提交。本輪只驗收現況，不把 provenance 不明改寫成已提交或已核准 migration。

既有 adapter 使用 caller 指定 CoinPaprika ID，驗證 response ID / base symbol 後讀取 `links_extended.stats`。只保存 provider-reported followers/subscribers/members；link metadata 不算 metric，缺值不轉 0，不推導 social heat、ranking 或 YAOZI heat。

`observed_at_ms` 是本地觀測時間，不是 provider counter timestamp。CoinPaprika 官方 `GET /v1/coins/{id}` 文件標示 Free plan 可用、endpoint update interval 為 every 1 minute，且 `links_extended.stats` 可提供 Twitter followers / Reddit subscribers / Telegram members；但個別 social count 沒有 source timestamp，因此不能從單次 count 證明 counter 的實際更新時刻。

Universe mapping 新增 `catos-coinpaprika-identity-list-v1`，使用 CoinPaprika 官方公開 `GET /v1/coins` identity list。官方文件標示此 endpoint Free、`security: []`、每分鐘更新，欄位包含 `id` / `name` / `symbol` / `rank` / `is_active` / `type`。這份 list **只用來驗證候選 identity，不自行由 ticker 推導 mapping**：

- caller 必須明示 `SocialAssetRef(symbol, coinpaprika_id)`；current list 必須存在該 active ID 且 provider symbol 等於 CatOS base symbol才 resolved。
- 同 symbol 多個 active CoinPaprika identity → `ambiguous_mapping`。
- 沒有 active identity → `missing_asset`。
- 只有一個 active ticker candidate、但沒有 caller / cross-provider identity evidence → `unverified_identity`，仍不得 materialize social metric。
- detail endpoint 仍再做 response exact `id` + base symbol 驗證，任何 mismatch fail closed。

這個收緊是必要的：current live list 中可觀察到 `APP-USDT-SWAP` 的唯一 CoinPaprika ticker candidate 為 `app-dappsy`、`ARM-USDT-SWAP` 為 `arm-aramis`；只看 ticker 唯一性仍可能把不同資產誤配。CoinPaprika list 另含少數非典型 ID（前後連字號、非 ASCII 等），list parser 不把這些 provider rows 誤判成整份 malformed；但不符合 CatOS 安全 coin-id contract 的 ID 也不能成為 caller-supplied resolved asset。

## 本輪修改

- `market_social.py`：OSError / HTTPException 轉為不含原始例外細節的 `source_transport_error` batch；拒絕非法 link type、URL parser failure、超出 SQLite signed INTEGER 範圍的數值。
- `market_intel.py`：writer 重驗資產映射格式，拒絕 issues 與 metrics 並存、重複／未知 metric、非法 URL／數值，保留 exact replay 與 transaction rollback。
- `test_market_social.py`：新增 4 個測試方法，涵蓋失敗 run 遮蔽舊值、metadata-only empty、合法零值、畸形資料、重複 metric、writer 防禦與 rollback。
- universe mapping slice：`CoinPaprikaSocialTransport` 新增 bounded `/v1/coins` list fetch；resolver 新增 explicit mapping verification、ambiguous / missing / unverified 狀態與 deterministic replay；8 MiB list body cap 已由 current live payload 驗證，原 4 MiB cap 會正確 fail closed 為 `source_body_too_large`。
- mapping 不新增 persistence table。現有 v14 source run / metric row 已保存實際使用的 `asset_id`；unresolved coverage 是 collection-time evidence，不需要為方便升 schema。

具體失敗情境為 upstream timeout 沒有 evidence，以及 caller constructed batch 將部分失敗數值寫成可讀 facts。修補沿用現有 schema 與 transaction，不新增 table 或另一條持久化路徑。

## Sol 驗收

2026-09-21 已完成：

- `python -m unittest tests.test_market_social tests.test_market_intel tests.test_market_api`：**54/54 OK**；其中 social 專屬測試共 7 個。
- `python -m unittest tests.test_market_social`：**7/7 OK**。
- `python -m py_compile catos/market_social.py catos/market_intel.py catos/market_api.py tests/test_market_social.py tests/test_market_intel.py tests/test_market_api.py`：OK。
- social scope trailing-whitespace scan：無命中。`git diff --check` 本身 exit 0，但相關檔案目前未追蹤，不能把它當成內容 provenance 證據。
- bounded direct live：`BTC-USDT-SWAP -> btc-bitcoin` 與 `ETH-USDT-SWAP -> eth-ethereum` identity 驗證成功；新建暫存 schema v14 DB 共 2 個 source runs、4 個 metric rows、0 issues。reader / source-coverage 的 `materialized_public_count_source` 語義由 social 專屬測試覆蓋。
- live counts 只保存 provider-reported raw counts；`social_heat`、`yaozi_heat`、ranking 仍固定 null / unknown。
- 驗收證據：`outputs/yaozi-social-verification-20260921.json`。

未執行主 `outputs/catos-market-intel.sqlite` 的 v12→v14 migration，也未把 social live facts 寫入主 DB；沒有 push、沒有清理其他未提交內容，也沒有重跑 S10 或 Blockscout 15-day blocked 路徑。

## Universe mapping 驗證

2026-09-21 bounded live：

- CatOS current public universe 直接走既有 `collect_universe()`，取得 1,124 instrument refs / **734 active symbols**；沒有寫入主 DB。
- CoinPaprika `/v1/coins` 同輪取得 61,607 rows / 13,096 active rows。
- 只帶入先前已驗證的 explicit mapping：`BTC-USDT-SWAP -> btc-bitcoin`、`ETH-USDT-SWAP -> eth-ethereum`。
- universe-wide 結果：**2 resolved / 242 ambiguous / 324 unverified_identity / 166 missing_asset**。
- coverage rows deterministic SHA-256：`f6e0a0f42d4e6d9f28afe524537e1b64881af1e95867c381e797b8834e86689f`；universe symbol SHA-256：`7452d1d06b8032122769eb142db14bc319d5300ead8769148a001a7f42d6a9fd`。
- 暫存 schema v14 DB 只寫入 BTC/ETH：2 source runs / 4 metric rows / 0 issues；reader `social_heat` / `yaozi_heat` / ranking 全為 null。
- 主 `outputs/catos-market-intel.sqlite` 驗證前後 `PRAGMA user_version=12`，未 migration。
- evidence：`outputs/yaozi-social-mapping-verification-20260921.json`。

## 下一步

Universe-wide mapping coverage 已完成盤點與 fail-closed contract。公開 CoinPaprika identity list 本身不足以把 732 個未 resolved CatOS symbols安全對應到實際資產；後續要提高 coverage，需要可驗證的 explicit cross-provider identity evidence，再逐筆送入同一 contract。不得把 unique ticker candidate、raw follower/subscriber/member count 自行升格為 asset identity、YAOZI social heat、rotation rank 或 private score。
