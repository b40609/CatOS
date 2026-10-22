# 遠端前端返還版審查

日期：2026-10-04。結論：型別／建置成功，功能審查未通過，未接入核心。這是 Codex 開發審查，不是 WorkBuddy 獨驗。保留目前設計，不要求重做視覺。

## 來源與完整性

輸入 ZIP：`catos-frontend-return-20261004-2348.zip`，SHA-256 `42B14B5A779038E258906F3DEBE9DE285D2E5676A9B58563FA9CB81022DF9B89`，與對方回報一致。

獨立副本：`outputs/frontend-review-return-20261004-42b14b5a/source/`。路徑穿越檢查通過；標準解壓因 ZIP 重複兩筆 `source-manifest-sha256.json` 而中斷，已保留原 ZIP 與當時副本，未覆寫重複項。來源清單 221 項逐檔核對，只有清單自己 hash 不一致，其餘 220 項一致。應修正打包脚本，排除清單自我引用並保證 entry 唯一；未改寫原證據或 hashes。

## 必修缺陷

1. **模式隔離失效（真實 UI 重現）**：切 Demo，顯示控制已鎖定，仍能按 ETH Bot 的啟動並成功。`BotsPage.vue` 未依模式限制命令，分配固定 `mode: 'local'`，工作區模式未控制 adapter 資料範圍。Demo／Live 應標示尚未開放並禁止命令；切換本身不得控制 Bot。
2. **啟動其他 Bot 改寫既有執行（真實 UI 重現）**：`mock-adapter.ts:startBot` 將所有 running run 直接改 completed。Demo 下啟動 ETH 後，既有 BTC 顯示 completed 但仍持倉 1 張。應拒絕合約已占用，不能用修改歷史狀態釋放執行槽。
3. **錯 hash 靜默綁第一版（來源確認）**：allocateBot 的 find 失敗後 `|| this.strategies[0]`，錯版拒絕無效。移除 fallback，明確拒絕。
4. **不可變版本與 hash 尚未成立（來源確認）**：createStrategy 用隨機 64 字元而非 canonical 製品 SHA-256，沒有同策略／版本內容衝突拒絕。fetchRuns 與 stop 回應也製造隨機 artifact_hash，造成歷史與 Bot 綁定不一致。Mock 也應維持契約語意，真實 hash 以核心回應為準。
5. **匯入與參數不符合契約（來源確認）**：`.py` 固定 version `1.0`，核心 TOKEN 禁止句點；固定 defaults 與 warmup 不能代表原製品 metadata。JSON 匯入用 `Number(...) || 2` 吞掉非法／零值。分配僅 JSON.parse，未驗證 object、float、depth、大小與整数範圍；不得宣稱排除 float 或匯入不可變版本庫成功。以 `catos/python_strategy.py` 與既有匯入入口為準，不執行策略驗證。
6. **重送無冪等契約（來源確認）**：pending 雖保存 ID/body/build/instance，retry 呼叫 startBot 仍建立新 run 並更改既有 run，未依相同命令還原結果／拒絕不同 body。明確失敗的 503／409 也遺留 pending。需區分確定拒絕與結果未知，核對持久化重送語意。
7. **狀態與說明誤導（UI／來源）**：目前純前端 Mock，但 Bot 頁 Worker HEALTHY、PID、即時事件等固定區塊未隨 Bot 更新。ETH 已 running，Worker 區仍 STOPPED；BTC completed 仍 HEALTHY。應標示示意並由同一狀態產生。歷史還原未完成，不能稱完整流程通過。
8. **對方匯入驗證不足（測試碼確認）**：verify-return-inspection.js 只查 input accept 與徽章，沒有檔案上傳；啟停只查狀態文字，沒有保留部位／獨佔拒絕斷言。文字回報中的「.py 匯入通過」及完整持倉停止語意缺證。
9. 外部 Google Fonts 仍存在；離線／跨電腦一致性未完成。各頁直接 import mock-adapter；真實 raw DTO、adapter 接線與核心整合仍需完成。

## 本輪實際驗證

在副本執行：

```text
npm.cmd ci --ignore-scripts --no-audit --no-fund
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit
node node_modules/vite/bin/vite.js build --outDir ../rebuilt-dist --emptyOutDir false
node node_modules/vite/bin/vite.js preview --outDir ../rebuilt-dist --host 127.0.0.1 --port 61944 --strictPort
```

安裝 exit 0（79 packages），型別檢查無診斷，連續命令最終 exit 0，Vite 6.4.3 建置 101 modules 成功。產物 CSS `index-DeL7oXxi.css` 109332 bytes，JS `index-Dm6oMexO.js` 316622 bytes，與交付名稱／大小一致；未作全產物逐位元比對宣稱。

啟動前 61944 無 listener。本輪 owner PID 39540，parent 26056，creation `2026-10-04T23:55:50.460447+08:00`，命令為上述 Vite preview。只有静態 fixture，無 backend build/instance／DB／Worker；畫面內 PID/build/instance 是 Mock，不是實際基線。

CUA：全新埠開 Bot 頁 → 點 Demo → 點 ETH 啟動 → 檢查成功提示、ETH running、BTC completed 且部位 1 → 刷新 → 模式回本機，Bot 變更仍保留。證據：`../outputs/frontend-review-return-20261004-42b14b5a/demo-start-state.txt`、`demo-start.png`、`refresh-state.txt`。不是完整九頁重驗，不宣稱匯入／信任／停止／503 本輪互動通過。

收尾：關閉本輪 tab；自己啟動的 preview Ctrl+C，exit 1，61944 listener 已不存在。不能宣稱正常 exit 0。未控制正式 8770/8771，未讀產品 DB／憑證，未接外部 provider、Git 或另一工作目錄，未改 incoming source／核心。

## 接續

保留既有視覺，先修上述 Mock 狀態、模式、匯入與命令契約，再以全新隔離 fixture 重驗受影響流程。修復後由 WorkBuddy 核對來源與必要行為；核心接入之前不能以 Mock 驗證代替 Worker、SQLite、MCP 成果鏈路。交付 ZIP 原件可保留，重新打包須另取檔名與 hash。
