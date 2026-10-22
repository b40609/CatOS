# Vue 前端 Codex 修復交驗

2026-10-05。使用者授權直接修復，再交 Antigravity 接續視覺細節。這是開發自測，未做 WorkBuddy 獨驗；保留目前版面，不接真核心、不操作 Git。

## 實際差異

- `frontend/redesign-v2-return/src/adapters/mock-adapter.ts`：Demo／Live 不讀本機事件、研究、情報及帳務值；歷史與停止回應只取當次 Run 快照，不借目前 Bot 的 hash／參數，不捏造缺失帳務。停止後未知部位也保留阻擋；已執行案例回應沿用歷史。已儲存的空策略／Bot／Run 陣列刷新後保持空，不重新植入示意案例。
- `src/state/useDashboard.ts`：模式切換清除舊資料，圖表非同步回應核對模式、範圍與請求 token，防止舊資料回灌。
- `src/pages/RiskPage.vue`：風控載入防競態，未開放模式不顯示本機部署／帳務；P6 明示未接線；Kill-Switch 禁用，移除未接線卻宣稱清倉成功的提示。
- 新增 `scripts/verify-local-repair.js`：隔離瀏覽器、僅 loopback 網路、動態空閒埠、實際監聽 owner、啟動前及退出後來源 hashes、正常關閉及唯一證據目錄。沒有執行舊版強制終止腳本。

相對路徑 `src/`、`scripts/` 均位於上述前端目錄。沒有改 CSS／版面結構，舊 dist、交付 ZIP、來源清單及原證據保留。

## 本輪命令與結果

在 `frontend/redesign-v2-return` 執行：

```text
npm run typecheck
npx vite build --outDir dist-codex-repair-20261005-final
node scripts/verify-local-repair.js dist-codex-repair-20261005-final
```

三者 exit 0。最後建置 109 modules；受影響自測 7/7，browser_errors 為空。真實瀏覽器互動包含三頁 Local→Demo→Live→Local、`.py` file input 上傳、勾選信任後關閉重開／人工分配／刷新、按鈕啟停／持倉歷史刷新。四路由 503、改 payload 409、快照錯配／缺資料案例包含直接 Adapter 故障注入，不能全部稱 UI 操作。延遲本機風控回應未覆蓋 Demo。已查看上傳、停止歷史及 Demo 風控截圖。

## 最終證據與基線

證據根：`frontend/redesign-v2-return/evidence/codex-repair-62b985a4-b1c9-4be0-9502-f479b5cb5759/`。

- `report.json`：7 項結果；`interactions.json`：互動紀錄；`retry-checks.json`：命令重送結果；PNG：畫面。
- `hashes.json`：完整 src、設定、lockfile、測試腳本及建置 SHA-256；`input-hashes.json`：輸入 hash。
- 輸入 `upload-fixture.py` SHA-256：`f26a8fcaf0531e9c8f825d091ea9e7a5636c1657771c0eb5895f21c9321ab455`。
- fixture：`127.0.0.1:62446`，實際 OS 監聽 owner `55012`，前端 instance `62b985a4-b1c9-4be0-9502-f479b5cb5759`。這是前端 fixture 身分，無後端 instance。
- `lifecycle.json`：exclusive loopback bind 確認空閒、OS owner 相符、source_drift `[]`、server_closed `true`、退出後監聽數 `0`、process_exit_code `0`。
- 最終 index SHA-256：`1e5d0327329822b06d0a94c063b42297b22b0bd7fa7d5667e4834bd38ad6c2da`。
- JS `index-VfJePCv9.js`：`560dbcdb7b15be82c7f84c32088f3e4bd24be96878ecc1d0c7406dc77ec2abd3`。
- CSS `index-DIZdAtel.css`：`7555651e9397c88fbb3151145019ae6afcb138eb00e48b280ccbb10981d53d7c`。

較早 `codex-repair-19a722b6-13c7-42da-a307-a3d3a368bba9` 的 5/5 只屬修復中間版本。`codex-repair-6d782e00-27d6-400f-ad86-7d51e2b6d03b` 補測失敗：空歷史刷新被重新播種導致 UI 啟動阻擋；退出後才修正，再另存 final build 完成上述 7/7。兩份原證據保留，不作最終基線。

## 限制與重驗入口

本輪仍為 Vue＋Mock Adapter／瀏覽器 storage。`.py` 上傳只證明前端匯入與不可變示意；測試策略為 `class Strategy: pass`，不證明 AST、hook 或策略真正執行。未測真 Python Worker、SQLite、MCP、外部 AI 客戶端、持續市场、provider、Demo／Live。未變更金融／資安政策，未執行 Git；其他工作樹內容未核對。

固定 Sidebar SAFE、連線延遲等既有展示文案仍屬 Mock；應由下一輪呈現調整清楚標示，不能當成真實服務健康證據。未宣稱整站所有內容與按鈕都已完成。

WorkBuddy 必要獨驗：重算上述來源／輸入／build hashes；核對原始互動、畫面與正常退出；依風險重驗模式隔離、空集合刷新、Run 不借 Bot 快照、未知持倉阻擋及四路由重送。使用全新隔離 fixture，不跑 `run-test-suite-r2.js`；不機械重跑歷史核心測試。後續 UI 變更須建立新基線。Git 核對由 WorkBuddy，commit／push 另需明確授權。

下一步由 Antigravity 依 [細節調整提示詞](antigravity-frontend-details-20261005.md) 接續；真核心接線留 Codex 後續工作，不以此交驗宣稱已接線。
