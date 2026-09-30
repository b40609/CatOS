# CatOS 目前接續入口

更新：2026-09-30。工作目錄 `C:/Users/user/Desktop/CatOS_Astra`。

## 當前切片：正式 8770 工作台入口

使用者已授權切換正式入口，限定最小驗證、不大量點擊。已將 `scripts/start-research.ps1` 改啟動 `catos.workspace_api`；根入口及 /quant、/workspace 顯示 Gemini 首頁，六頁工作台與研究 API 共用既有單一 ResearchService／writer。舊研究頁 /research/、舊 F1 /workspace/legacy 保留。沒有新增 DB schema、交易功能或第二 writer。

本輪受影響測試 **22/22 PASS**，含正式根入口、同服務暫存合成回測及 Decimal 結果；未做瀏覽器操作，未重驗 R4。占用中的 8770 啟動測試非零退出，未停 owner 或改 port。詳見 [正式入口交接與人工清單](workspace-formal-entry-handoff-20260930.md)。

**正式服務已於 2026-09-30 23:20（台灣時間）接續啟動。** 對話遺失後核對 8770 已無 listener，未停止任何舊程序；執行 `python -B -m catos.workspace_api`，新 PID `41344`、instance `e126513443884f26810bf437290c66b1`。版本端點確認 preview=false、research_owner=same_app、兩端 restart_required=false、active_run_id=null。首頁含戰情總覽，策略中心／設定頁 HTTP 200；保存研究紀錄 26 筆、queued／running=0。R4 專用快照 `status.state=complete`、32 根／13 fills／0 anomalies、issues=[]。8771 preview PID `5512` 保留。這取代先前「實際服務尚未切換」狀態；先前停止命令遭自動安全政策拒絕仍為歷史紀錄。

指定 **5.6 Sol (Web)** 已完成限定範圍獨立驗收：唯一 8770 listener 與 API PID 均為 `41344`，程序命令為 `python -B -m catos.workspace_api`；workspace／research 版本一致且無需重啟，研究紀錄 26 筆且 queued／running=0。真實瀏覽器首頁顯示 R4 已完成、32/32 根訊號、13 成交；側欄實際進入策略中心與系統設定均正常，沒有建立研究任務或修改設定。本輪未重跑單元測試、回測或 R4 verifier。R4 仍讀 `/api/workspace/local-sim/runs/347282b9d0d9433db6a0276209936f60`，不是研究 runs 端點。後續功能切片尚未定案。

## 完成基線與證據

- **F1：提交 `7957447`。** Gemini 六頁工作台保留整體畫面、密度、導航與布局操作；來源／版本／驗收收進詳情，缺資料短標示。指定 5.6 Sol (Web) 已回報 **6/6 PASS**，本輪僅引用。策略中心沿用研究服務；其餘頁讀 R4 證據／缺口／偏好，沒有 Bot 啟停或交易 mutation。[F1 交接](catos-workspace-f1-handoff-20260930.md)／[規格](catos-workspace-f1-spec-20260930.md)／[設計決策](catos-frontend-design-feedback-20260930.md)。
- **R4：正式 PASS 並提交 `33a4518`。** 唯一 run=`347282b9d0d9433db6a0276209936f60`；eight-hour、28800.073241599952 秒、32 根正式＋2 根預熱、13 fills、0 anomalies、final_equity=`999.67939950`、fees=`0.01320050`。既有 verifier 證據為 read-only、runtime_digest_unchanged=true。本輪未重跑。固定 runtime SHA=`ec21bab7a7f26436bc75f6f48ea843f82dfcf62e1dbf65b5c507a44616db9e65`，manifest 程式保持凍結。[R4 交接](frontend-research-r4-handoff-20260930.md)／[規格](frontend-research-r4-spec-20260930.md)。
- **R3：既有 36/36 與 MCP E2E 證據。** 固定核可 SMA／合成資料、七 MCP 工具 exact binding；本輪未重驗。[R3 交接](frontend-research-r3-handoff-20260930.md)。

## 分工、授權與其他工作

本輪指定 **5.6 Sol (Web)** 驗收已通過；Git 收尾僅納入 workspace_api、start-research、README、workspace tests、正式 8770 交接與本入口，不 push。`AGENTS.md`、`.codex/`、outputs 與 F1 歷史補記等其他未提交內容繼續留在工作樹，不混入本片。

不碰 R4 DB、凍結 runtime、其他研究 runs、Gemini 原目錄或 CatOS_Yaozi；不讀真實憑證，不採集、不下單、不解除 latch。outputs 與其他未提交工作不混入。既有 R4 heartbeat 後端已回報不存在，不另建監控。

模型設定修正保留：專案 [.codex/config.toml](../.codex/config.toml) 已取消 model／model_reasoning_effort 固定值，6.1／medium 僅為 [AGENTS.md](../AGENTS.md) 建議；全域既有 6.1／low 未修改。新對話選單尚待使用者確認；AGENTS／.codex 設定不納入本片 Git。
