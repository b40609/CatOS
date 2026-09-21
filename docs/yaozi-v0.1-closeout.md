# Yaozi 情報模組 v0.1 封版契約

2026-09-21。使用者已同意 catOS 自動策略為主線；Yaozi 完成限定收尾後封版。本文件不宣稱模組已封版或已整合至交易。

## 固定範圍

保留既有 public market providers、分析、唯讀 API 與 Dashboard。v0.1 不新增 provider／幣種涵蓋目標、不破解 SMF／排名私有公式、不做會員／聊天／授權系統。社群 identity 未證明、鏈上 15 日不完整、Deribit 未進既有 snapshots 等均明示 unavailable／partial，不作封版必補項。

模組不取得交易憑證、不直接下單、不修改交易帳本或風控。Supervisor 職責規則不變；collector／writer 的正式產品入口仍需盤點，不因現有獨立 CLI 已可跑而宣稱完成核心整合。第一個策略閉環不依賴情報模組。

## 第一個實際阻斷

catos.market_intel.SCHEMA_VERSION 為 14；market_api reader 初始化要求 DB user_version 相等。前輪記錄主 DB 為 v12，本輪未讀 DB。依此靜態推論，若主 DB 仍 v12，直接使用新版 reader 將得到 unsupported_schema；不能把此狀態稱作可啟動成品。

最小收尾先盤點啟動入口與版本相容方案：保留既有主 DB，不自動 migration。離線 QA 可沿用既有新建 v14 合成 DB fixture；明示 synthetic，不把它當 live 主庫。實際主庫升級若需要，先交具體備份／遷移／驗證方案，依既有 schema 變更規則另確認。不得以空白新 DB 替代原資料並宣稱完成。

## 驗收清單

| 編號 | 可觀察的通過條件 | 狀態 |
|---|---|---|
| Y01 | 文件給出與實碼一致的啟動／停止方式、127.0.0.1 與可指定 DB／埠，錯版本清楚回報 | 待核對 |
| Y02 | 選定 v0.1 可讀 DB 路徑與版本方案，保留舊資料；驗收分清 synthetic 與 live | 待方案／驗收 |
| Y03 | Dashboard 核心頁、單幣頁、來源涵蓋可讀；缺漏／過期／不支援不顯示假零或假評分 | 待固定版本驗收 |
| Y04 | 不啟動情報 collector/API 時，既有核心模擬不依賴 market 模組；無交易 client／帳務寫入連結 | 待依賴審查／必要驗證 |
| Y05 | 記錄資料時間、source、coverage、版本與已知限制；既有缺口照實交付 | 待文件核對 |
| Y06 | 專屬測試與最小啟動／視覺驗收由 Sol 執行，固定版本並記錄證據 | 待驗收 |

全部達標才宣布 v0.1 封版；83.5% parity 不用作 release gate。未完成項保留理由及下一步，不增加第二套通用插件框架、不先大搬檔。

## 檔案所有權與交付

Yaozi 對話負責 market 專屬實碼／測試及本文件的專屬進度；不得改交易核心、Lot、README、WORK_PLAN、current-handoff。共享 market_api／market_intel 也只容許一位實作者在同一時間修改。主線整合者彙整入口；Sol 驗收與 Git。未切至隔離 worktree 前，各線使用獨立暫存輸出，不共用 writer／DB／埠。

先完成靜態收尾 assessment，再依既有授權修正啟動或缺漏顯示問題；不擅自遷移 DB、不重新跑被 review 擋住的 live 路徑、不讀憑證、不 push。詳細來源歷史見 [切換前入口](market-intel-baseline-20260921.md)。
