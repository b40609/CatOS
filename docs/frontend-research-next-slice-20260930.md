# 正式研究前端下一片規劃

日期：2026-09-30。使用者已指示開始 R1；R1 實作與驗收狀態見 [R1 交接](frontend-research-r1-handoff-20260930.md)，本文件保留切片順序與規劃依據。Astra 編寫、Sol 獨立驗收與 Git；不授予提交、採集、DB 遷移或交易權限。

## 基線與缺口

外部來源 `C:/Users/user/Desktop/catOS-Frontend-Final` 為 mock 原型，Workspace 收尾見來源 HANDOFF。Astra 已有 `catos.research.backtest`、CSV 載入、報告與 `catos.optimization`。已讀研究 CLI、核心結果契約及 Optuna 示例，未重驗核心。`optuna_study.run_study` 帶固定設定且輸出 stdout，正式 UI 應用共用 `optimization` 核心，不把示範預設默認為使用者設定。未發現已接好的研究 HTTP／MCP 任務入口，實作前再核對 API。

目前具體缺口：畫面展示成功，卻沒有真實研究任務。下一片先完成單一回測流程，避免同時混合 UI、策略執行與交易責任。

## R1：同源策略回測流程

交付操作：策略中心 → 選受信策略版本與合成資料 → 設定參數／成本／預熱 → 建立回測 → 看真實績效、權益與成交 → reload 仍能讀取完成結果。

1. 逐檔 manifest 與來源 SHA256 帶入必要靜態資源至 Astra 新 frontend 目錄；先提供同源研究入口，驗收後再切根入口。保留既有 shell／Yaozi 路由，不整包覆蓋、不執行期跨桌面目錄 import、不刪舊原型。
2. 建共用研究 service，直接重用 `backtest`／CSV 契約；接受註冊策略／資料 ID，拒絕任意 Python、URL 與路徑執行。第一筆採既有 SMA 示例、單合約單週期合成 Closed Bar。任意 Agent 製品的受信檢查另於 R3 確認。
3. 最小 API：列策略／資料、建回測、讀任務、讀固定結果。一次一個任務，queued／running／complete／failed 與錯誤原因由後端提供；瀏覽器關閉不終止後端任務。資源與逾時上限於實作規格明列，不新增常駐服務。
4. 請求／結果存隔離研究輸出目錄 JSON／HTML，每筆綁 run_id、策略版本／hash、資料來源／hash、完整設定與模型假設；不改既有 DB/schema。完成結果跨重啟可讀，未完成任務標為中斷，不宣稱自動恢復。
5. Decimal 用 JSON 字串傳輸，前端轉換只供繪圖；不重算為帳務或風控依據。執行時固定請求快照，後續表單修改不改已完成結果。其他頁仍標原型，研究績效不當帳戶權益；不新增 AI 聊天室。

驗收：新 service／API／serializer 專屬測試，加一條瀏覽器成功流程與非法設定失敗流程、reload 保存。合成 fixture 結果須與直接核心呼叫一致；拒絕路徑穿越、未知策略、錯誤 Decimal 型態；不得覆蓋既有結果。不跑全市場回測。獨立驗收與 Git 維持 Sol 分工。

## 後續與整晚運行

- R2：`catos.optimization.optimize` 接同一 service，明示搜尋空間／trial budget／seed，呈現真實候選績效，套用候選並新建回測。Float 僅評分，原始績效 Decimal；未做樣本外檢驗明示。
- R3：MCP 共用同一 service，Agent 建經檢查的固定策略版本 → 回測／優化 → 網頁同步結果。先驗證一個常用客戶端，再驗證 Antigravity／DSH，不先宣稱相容；製品來源、hash、核可版本與受信執行先有具體契約。
- R4：人工選定固定版本，以既有 Worker／Supervisor 接 local-sim，連續一晚提供起訖時間、訊號、模擬成交與異常證據。回測成功不等於整晚模擬已驗收；Demo／Live 另依授權。

原規劃已進入 R1 實作；R2–R4 依序接續，不能將規劃改寫成已實作或已驗收。
