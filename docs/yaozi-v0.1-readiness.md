# Yaozi v0.1 封版 readiness

更新：2026-09-21。範圍僅限 Yaozi / `market-intel` 可選唯讀情報模組；本文件是靜態 assessment，不宣稱 runtime 驗收已完成，也不把 synthetic DB 當 live 產品。

## 結論狀態

目前狀態是 **runtime / DB 封版條件已驗收，待 Git 固定版本**。2026-09-21 已依使用者授權保留原 v12 主庫，透過 SQLite backup 產生獨立備份與 `outputs/catos-market-intel-v14.sqlite`，只對新檔執行 v12→v14 migration。主要 release gate 不使用歷史 parity 分數。

## 1. 啟動 / 停止入口

靜態核對前，`catos.market_api` 只有 `serve(db_path, host="127.0.0.1", port=8765)`，沒有 `python -m` CLI，因此封版契約 Y01 尚未成立。本輪補上最小入口：

```text
python -m catos.market_api --db outputs/catos-market-intel-v14.sqlite --port 8765
python -m catos.market_api --db outputs/catos-market-intel-v14.sqlite --check
```

- host 不開放 CLI 覆寫；`serve()` 仍只接受 `127.0.0.1`。
- `--db` 與 `--port` 可指定，避免不同工作線共用 DB / port。
- `--check` 只以 SQLite `mode=ro` + `query_only=ON` 讀 metadata / `PRAGMA user_version`，不啟動 server、不建立或 migration DB。
- schema / metadata 不符時啟動回報包含 `status`、`expected_schema`、`actual_schema`、`format`、`path`，並以非零 exit code 停止。
- 正常停止方式是前景執行時 `Ctrl+C`；`KeyboardInterrupt` 視為乾淨停止。沒有新增 background service / PID manager。

Sol 已完成 focused tests、synthetic 啟停與產品候選 DB read-surface 驗收；Y01 通過。

## 2. schema v14 reader 與前輪主 DB v12

現行 `MarketIntelReader` 採 exact schema contract：`user_version` 必須等於 `SCHEMA_VERSION=14`。這是正確的 fail-closed 行為，因 v13 / v14 增加 liquidity / social tables；若讓 v12 直接進新版 reader，部分頁面會在查詢時才因缺 table 失敗，反而更不清楚。

v0.1 相容方案已執行：

1. 原 `outputs/catos-market-intel.sqlite` 保持 schema v12；migration 前後主檔 SHA-256 均為 `862b732e302fb3f8b1444584bf566dd811371bf3aa8ca0144f28a05841d9d4a8`。
2. 備份為 `outputs/catos-market-intel-v12-backup-20260921.sqlite`，schema v12、`integrity_check=ok`。
3. 產品候選為 `outputs/catos-market-intel-v14.sqlite`，schema v14、`integrity_check=ok`、foreign-key violations=0；v12 既有表逐表 row count 無差異。
4. v13/v14 新表 `liquidity_source_run`、`liquidity_snapshot`、`social_source_run`、`social_metric_snapshot` 初始均為 0 rows；不把 synthetic/live facts 虛構搬入。
5. market API 與 market 專屬 CLI 預設 DB 已切至 `outputs/catos-market-intel-v14.sqlite`；舊 v12 路徑只保留歷史資料，不作預設 writer target。

不採用的捷徑：API 啟動時自動 migration、用空白 v14 DB 取代 v12、或在 reader 內對缺少的 v13/v14 tables 靜默 fallback。

## 3. 缺漏、過期與不支援顯示

既有 read model 的靜態語義大致符合 v0.1：missing 以 `None` / `missing` / `MISSING_DATA` / `not_materialized` 表示；social heat、YAOZI ranking、signed GEX、private formula 等保持 null / unknown；`/intel/source-coverage` 明示 `freshness_status=not_evaluated_no_wall_clock` 與 `live_equivalence_status=not_inferred_from_persisted_run`。

本輪找到一個顯示缺陷：Dashboard 頂列原本固定綠色狀態點，會讓使用者誤解為目前 live / fresh。已改成中性狀態並顯示 `READ ONLY`；footer 明示 `FRESHNESS NOT INFERRED`。來源覆蓋頁原本就標示 persisted runs only / no wall-clock freshness inference。

v0.1 **不自行新增 freshness 門檻**。因此「過期」只能顯示 persisted timestamp 與「freshness 未評估」，不能自行標 green / fresh / stale。若未來要做 stale badge，需要先由主線定義 freshness policy。

Sol 視覺驗收需特別核對：空資料不顯示 `0` 當實值、未知 private score 顯示 `—` / unknown、lower-bound liquidity 保留 `≥`、source coverage 不顯示 live/fresh 綠燈。

## 4. 核心依賴隔離

靜態 import 掃描未找到非 `market_*.py` 的 catOS 核心模組反向 import `catos.market_*`。`market_api` 只建立 read-only SQLite connection；Dashboard 只讀 localhost API。market collectors 的公開來源程式也明示不持有帳戶憑證或交易 authority。

因此 v0.1 可維持：

- 不啟動 `catos.market_api` / collectors 時，交易核心與 local-sim 不需要 market 模組才能 import / 啟動。
- 第一個策略閉環不依賴情報資料，也沒有由 Dashboard / reader 呼叫交易 client、Journal writer、下單或帳戶 API 的路徑。
- collector / writer 仍是獨立 market 資料製作路徑；本輪不把它們掛入 Supervisor 自動啟動。

這是靜態結論，Y04 最終仍需 Sol 用固定版本做「核心最小 import / local-sim 不啟動 market」驗收。

## 5. 必要最小程式修改

本輪已編寫並完成 Sol 驗收：

| 檔案 | 最小修改 | 目的 |
|---|---|---|
| `catos/market_api.py` | `inspect_database()`、`--check`、`--db`、`--port`、`python -m` 入口、Ctrl+C clean stop | Y01 / Y02 的唯讀啟動 preflight；不 migration DB |
| `catos/market_dashboard.py` | 綠色 status dot 改中性 `READ ONLY`，footer 加 `FRESHNESS NOT INFERRED` | 避免 persisted data 被誤看成 live / fresh |
| `tests/test_market_api.py` | 加 schema preflight、CLI 不啟動 writer、固定 loopback startup、Dashboard 語義測試 | 交給 Sol 執行 deterministic 驗收 |

目前不需要改 `market_intel` schema，也不需要新增 persistence table、provider、background service 或交易整合。

## 6. Sol 驗收清單

Sol 驗收結果：

1. `tests.test_market_api` 24/24、`tests.test_market_intel` 26/26、Supervisor smoke 14/14 通過；本次預設路徑切換後另重跑受影響 focused tests。
2. `py_compile` 目標 market API / Dashboard / tests 已通過；預設路徑切換後另重跑變更模組 compile。
3. synthetic v14 `--check=ready`；synthetic v12 fail closed 且 bytes 不變。
4. synthetic localhost server 只綁 `127.0.0.1`；Dashboard / Today / BTC single-coin / source-coverage 實際可讀。Ctrl+C 後 Uvicorn 完整 shutdown；Windows shell 當輪回傳 1，未視為產品資料錯誤。
5. 視覺 QA 已確認 `READ ONLY` / `FRESHNESS NOT INFERRED`，missing / unknown / partial / lower-bound 未變成假零或假分數。
6. 產品候選 DB `--check=ready`；Dashboard、Today、BTC single-coin、source-coverage、social、liquidity 使用 TestClient 均回 HTTP 200。
7. 核心 smoke 未載入 `catos.market_*`，情報模組維持可選依賴。

## 7. 封版判定

| 契約 | 靜態 assessment / 程式狀態 | 封版判定 |
|---|---|---|
| Y01 啟停 / localhost / 錯版本 | CLI + read-only preflight + runtime smoke | **通過** |
| Y02 v14 可讀 DB / 保留 v12 | 原 v12 不動；獨立 backup；產品候選 v14 已驗證 | **通過** |
| Y03 Dashboard / missing / freshness | API + visual QA 通過 | **通過** |
| Y04 核心隔離 | 最小 smoke 未載入 market 模組 | **通過** |
| Y05 時間 / source / coverage / 限制 | source、timestamp、coverage、unknown 邊界保持 | **通過** |
| Y06 固定版本驗收證據 | runtime/hash 證據已固定；market 檔仍未納入 Git commit | **待 Git 固定版本** |

目前唯一剩餘 release 動作是由 Git 負責線將本輪 market 檔與文件固定到可重現 commit；在 commit 前不宣稱 Git-level 封版。
