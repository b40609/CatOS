# W6 本機版本保存

2026-10-01（台灣時間）。W6 A／B 已由指定 5.6 Sol (Web) 唯讀獨立驗收 PASS；使用者於後續 scoped Git 收尾建議後明確回覆「同意 請執行」。本次由目前執行者完成限定本機提交，不改一般獨立驗收／Git 角色分工、不授權 push。

## 提交範圍

起點為 `main`／`d03e4d6`，暫存區空。單一提交訊息為 `test(local-sim): save W6 fixture and independent acceptance`，提交號由 git log 辨識。精確保存七檔：

- `tests/simulation_ui_w6_fixture.py`
- `tests/test_simulation_ui_w6_fixture.py`
- `docs/local-sim-bot-control-w6-assessment-20261001.md`
- `docs/local-sim-bot-control-w6-handoff-20261001.md`
- `docs/local-sim-bot-control-w6-acceptance-20261001.md`
- `docs/current-handoff.md`
- 本文件。

AGENTS、.codex、F1 補記與所有 outputs 排除，保留原始證據及未提交工作；不修改 ignore、不清理、不碰 CatOS_Yaozi。fixture 為既有隔離回覆不可確認案例，不修改正式程式；本次只新增收尾文件並同步入口。

## 核對與歷史證據

- [指定角色獨驗](local-sim-bot-control-w6-acceptance-20261001.md)記錄直接由原始檔離線重算 40 項核心斷言全數 PASS。本次只核對該文件列出的八個原始檔 SHA256，8/8 相符，不宣稱重新執行獨驗。
- 專屬單元 1/1、A 開發核對 36/36、B 開發核對 18/18 均為歷史證據；本次未跑測試或重算案例，未以開發核對替代獨驗。
- 本次檢查精確暫存集合與 `git diff --cached --check`；提交後核對七檔集合、空暫存區及排除檔未改動。
- 保留 A 較早閒置 GET 已截斷、B 僅隔離 stub 的限制，不宣稱實際 Worker／帳務／斷網驗證。

本輪未新增 run、未 POST 控制命令、未重跑 W6／研究／R4、未操作服務或 DB、未解除 recovery／latch、未讀憑證、未 push。提交採單次 `maintenance.auto=false`／`gc.auto=0`，未改 Git 設定、未清理，也不宣稱先前自動維護警訊已修復。

W6 執行／獨驗文件中的「本輪未 Git」仍描述各自歷史輪次；本文件記錄其後另行授權的版本保存。後續可先評估正式 stop 原命令重送的最小缺口，僅提出 assessment，不新增案例或放寬交易／恢復邊界。
