# 切換前入口歷史存檔

本檔保存切換至自動策略主線前的入口原文；「本輪」「目前 HEAD」等均屬原交接時點，不是本輪重驗或新授權。最新優先序見 current-handoff.md。

# CatOS 目前接續入口

更新：2026-09-21。當前接續範圍：YAOZI 功能複製 / `market-intel`。Lot S10 為獨立工作，保留既有未提交內容，不混入本切片。

## 當前階段

2026-09-21 CoinPaprika universe mapping slice 已完成：新增 `catos-coinpaprika-identity-list-v1`，固定讀公開 `GET /v1/coins`，只把 CoinPaprika identity list 當候選集合；**不因 ticker 唯一就自動建立 mapping**。只有 caller 明示 `SocialAssetRef(symbol, coin_id)`，且 current list 證明該 ID 為 active、同 base symbol，才成為 resolved asset；多候選為 `ambiguous_mapping`、零候選為 `missing_asset`、單一候選但缺跨來源 identity 證據為 `unverified_identity`。2026-09-21 current public universe live scan 為 1,124 instrument refs / 734 active symbols；同輪 CoinPaprika list 61,607 rows / 13,096 active，結果 **2 resolved（BTC/ETH）/ 242 ambiguous / 324 unverified / 166 missing**。暫存 v14 DB 只 materialize resolved BTC/ETH，共 2 source runs / 4 raw metrics / 0 issues；`social_heat` / `yaozi_heat` / ranking 仍 null。主 DB 前後皆 schema v12，未 migration、未寫 social facts。無需 schema v15：v14 `social_source_run.asset_id` / `social_metric_snapshot.asset_id` 已保存實際使用 mapping。parity 維持 **73.5 / 88 = 83.5%**。詳細見 `docs/market-social-handoff.md`、`outputs/yaozi-social-verification-20260921.json` 與 `outputs/yaozi-social-mapping-verification-20260921.json`。S10 不重跑，使用者指定不 push。

最新完成切片是 Deribit second public Options provider。完整 15-day Blockscout live probe 本輪再次被 runtime safety review 阻擋後，依既定 fallback 新增 `catos.market_options` 的 Deribit inverse option book source：固定 `www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={base}&kind=option`，保留 expiry/strike/C-P、underlying-base OI、mark IV、mark/underlying price 與 premium currency。

現行 option snapshot tables 沒有 source 欄，所以 Deribit 只 persist `option_context_run` source evidence，不混寫 OKX snapshots、不升 schema。2026-09-21 `BTC-USD` bounded direct live：918 items、0 issues、source-run `ok`，暫存 DB 的 `option_summary_snapshot` / `option_open_interest_snapshot` 都是 0；focused `tests.test_market_options` 8/8、`py_compile`、scoped `diff --check` 通過。驗收證據：`outputs/yaozi-deribit-options-verification-20260921.json`。

前一個 Blockscout Ethereum on-chain provider implementation 仍有效：`catos.market_onchain` / `catos-blockscout-token-outgoing-address-v1` 使用固定 `eth.blockscout.com/api/v2/tokens/{contract}/transfers` public GET、validated `block_number/index` cursor、caller-supplied 24h 日界、目標日 + 前 14 個完整日 coverage gate、bounded page budget 與 fail-closed persistence。

只有 15 個 24h window 全部證明 complete 時，才把 distinct ERC-20 `from` address 計數送入既有 3× / 2× / 1.5× reducer。mint sender、self-transfer、token scope mismatch、non-monotonic source order、duplicate transfer、repeated cursor、transport/parser issue、page truncation 全部 fail closed；partial run 只保存 `onchain_source_run` evidence，不生成 `onchain_activity`。

目前 functional parity：**73.5 / 88 = 83.5%**。On-chain I/S/V/U：**1 / 0.5 / 1 / 1**。

## Live / 資料邊界

- WBTC Blockscout token-transfer endpoint 已取得 keyless HTTP 200、50 items、timestamp/token payload 與 `block_number/index` cursor，證明 endpoint 與目前 payload contract 可用。
- 完整「目標日 + 前 14 日」live pagination 尚未驗證；高活動 WBTC 單頁只覆蓋約數分鐘。
- adapter end-to-end 15-day live collection 本輪再次被 runtime safety review 阻擋，因此**不得宣稱** 15-day complete、主 DB live materialization 或 full Source coverage。
- 日界固定由 caller 明示；YAOZI calendar/timezone contract 未公開，不自行推測。
- direct ERC-20 transfer-from address activity 不等於 beneficial owner、smart wallet、whale identity、SMF 或方向訊號。
- beneficial-owner aggregation、YAOZI main-cost、Dealer direction、SMF exact formula、private funnel / threshold、Capital Flow private trigger gate 持續維持 `unknown_unpublished / not_inferred`。

## 驗證基線

- focused `tests.test_market_onchain + tests.test_market_p1 + tests.test_market_intel + tests.test_market_api`：**72/72 OK**。
- 全部 `test_market*.py`：**192/192 OK**。
- `py_compile`：OK。
- scoped `git diff --check`：OK。
- 驗收證據：`outputs/yaozi-onchain-provider-verification-20260921.json`。
- Deribit fallback slice：`tests.test_market_options` **8/8 OK**、targeted `py_compile` / scoped `diff --check` OK；direct live 918 items / 0 issues。未重跑全部 market suite。
- Social slice：`tests.test_market_social` **7/7 OK**；`tests.test_market_social + tests.test_market_intel + tests.test_market_api` **54/54 OK**；targeted `py_compile` 與 trailing-whitespace scan OK。BTC/ETH direct live 2 runs / 4 raw metrics / 0 issues，使用暫存 v14 DB。相關檔案目前未追蹤，所以 `git diff --check` exit 0 不作為 provenance 證據。驗收證據：`outputs/yaozi-social-verification-20260921.json`。
- 詳細狀態：`outputs/yaozi-handoff-2026-09-20.md`、`outputs/yaozi-parity-matrix-2026-09-20.md`、`docs/market-intel.md`。

以上是本輪已實際取得的驗證結果；新對話不要無目的重跑完整 market suite，除非後續程式變更需要。

### Lot S10 獨立驗收（與 market-intel 切片分離）

- Sol 已於 2026-09-21 完成 S10 獨立驗收：專屬測試 **34/34 OK**、必要 Lot／Journal 回歸 **344/344 OK**、目標檔 `py_compile` 與 scoped `git diff --check` OK。
- 首輪專屬測試為 33/34；唯一失敗來自 C03 測試 stub 誤攔截 Lot 防禦性重驗。Sol 只修正 `tests/test_lot_fee_correction.py` 的測試注入條件，生產 reducer 未修改，重跑後 34/34。
- F05 已產生 `outputs/s10-qa-20260921-sol/` 六張 1280／390 px 實際 Chrome 渲染截圖與 viewport metrics；無頁面級水平溢位，V3 版本、capture_id、revision、長 Decimal、缺費／完整狀態及 funding 未知文案均可讀。
- 共用 renderer 的 S9 回歸以目前 schema8 HTML 與先前實圖驗收版本 SHA256 逐 byte 相同證明，並重新讀取既有 1280／390 實圖；未見 V3 文案污染。
- 詳細結果見 `docs/lot-fee-correction-handoff.md`。本輪只用新建 local-sim QA DB；未動既有 DB migration、未連網／交易、未 stage／commit／push，其他未提交工作保留。

## 下一步

優先順序：

1. On-chain 15-day live pagination 目前仍被 runtime safety review 阻擋；不要以 partial evidence 冒充 full live，也不要反覆重試相同路徑。
2. Social universe-wide CoinPaprika candidate coverage 已完成；current 734 active symbols 只有 BTC/ETH 具既有明示 identity 可安全 resolved，其餘 732 保持 ambiguous / unverified / missing。若要提高 social coverage，需要新的 explicit cross-provider identity evidence；不得把 unique ticker candidate 自動當 mapping。raw follower/subscriber/member count 不當 social heat，counter 無 source timestamp。
3. Deribit 第二 provider 已完成 source-run evidence。若後續要把 Deribit OI/IV facts 放進 `/intel/options`，先設計 source 維度，現階段不升 schema。
4. 不擴張 liquidity venue breadth 當高優先；六個 configured venues 已有 direct live evidence。主 `outputs/catos-market-intel.sqlite` 仍未自行升至目前 schema v14；沒有明確需求前不要動使用者既有 DB。

## Git / 工作樹

目前 HEAD：`cc216f7910fc786afe39776daacf1d10737cc66d`。工作樹有大量 YAOZI / market 與已完成獨立驗收的 Lot S10 未提交內容；不要清理、reset、`git add .` 或混合提交。Astra 負責編寫；Sol 已完成 S10 獨立驗收，本輪未 stage／commit／push。若後續需要提交，先逐 hunk 核對來源。

本輪 on-chain 直接相關未提交內容至少包含：`catos/market_onchain.py`、`tests/test_market_onchain.py`、`tests/test_market_api.py`、`docs/market-intel.md`、`outputs/yaozi-onchain-provider-schema-proposal-20260921.md`、`outputs/yaozi-onchain-provider-verification-20260921.json`、`outputs/yaozi-parity-matrix-2026-09-20.md`、`outputs/yaozi-handoff-2026-09-20.md`。Lot S10 已驗收但仍是另一組未提交工作；不要混入 market 提交，也不要清理。

## 新對話短指令

> 接續 CatOS_Astra 的 YAOZI / market-intel 開發，工作目錄 `C:\Users\user\Desktop\CatOS_Astra`。先讀 `AGENTS.md`、`docs/current-handoff.md`、`docs/market-social-handoff.md`、`outputs/yaozi-social-verification-20260921.json`、`outputs/yaozi-social-mapping-verification-20260921.json`、`outputs/yaozi-onchain-provider-verification-20260921.json`、`outputs/yaozi-parity-matrix-2026-09-20.md`。CoinPaprika social raw metric schema v14 / writer / API 已完成；universe mapping contract 只接受 caller 明示 ID，再用 current `/v1/coins` 驗證 active + same-symbol identity。2026-09-21 current live coverage：734 active symbols，2 resolved（BTC/ETH）/ 242 ambiguous / 324 unique-but-unverified / 166 missing；不得把 unique ticker candidate 自動升格 mapping。暫存 v14 DB 仍只有 BTC/ETH 2 runs / 4 metrics，`social_heat` / `yaozi_heat` / ranking 維持 null；主 DB 保持 v12。Blockscout 15-day live pagination 仍被 runtime safety review 阻擋，不重試同路徑。不碰 Lot S10、不 push。
