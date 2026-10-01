# W5 限定唯讀獨立驗收

2026-10-01（台灣時間）。結果：**PASS**。使用者本輪明確授權「本次例外，請用 6.1 SOL 直接驗收」；僅適用本次 W5，不變更後續獨立驗收與 Git 的既有分工。

## 本輪核對

- 讀取 W5 提案、交接、原始 before／after、兩段 Network 事件、UI 文字及 metadata。執行 compare.py 的唯讀斷言部分，截斷於任何寫檔之前：41 項 PASS；未執行原腳本的輸出寫入段，既有證據未覆寫。
- 唯一新案例仍為 `c02f745093ae4aaba423cb5a51855219`，request_id=`947445dc87224c8681ae793235a0fd5d`；completed、2 warmup＋8 bars、4 fills、cleanup_confirmed=true、worker_closed=true、error=null，無 stop。原始 Network 唯一 UI start POST／202，刷新沒有額外 POST。
- equity=`999.91375990`、fees=`0.00404010`；四筆費用 Decimal 加總一致、固定 tag 正確、預熱無意圖、原定 1 秒節奏符合。
- 現行僅 GET：8770 workspace／research／simulation version、研究及模擬清單、R4 摘要；8771 workspace version 與 simulation version（404）。三正式版本 loaded=current、restart_required=false，控制槽 idle；研究 26/26 complete，W4／W5 清單與 R4 完整內容保持。
- 8770／8771 均為 127.0.0.1 唯一 listener，PID 分別 39200／5512；命令及程序建立時刻符合原始證據。preview loaded build 不變且 restart_required=true。
- 保存的來源 SHA 與合成 CSV SHA 全數符合現行檔案；依 R4 manifest 的 runtime_files 重算 SHA，符合 `ec21bab7a7f26436bc75f6f48ea843f82dfcf62e1dbf65b5c507a44616db9e65`。

原始保存 API 的部分時間字串為 +08:00，現行 GET 為 +00:00；首次逐字比較未通過，逐欄將 ISO 時間轉為 UTC 後，research version、完整研究／模擬清單及 R4 全部一致，只排除 observed_at。owner 建立時間另有末尾小數位 0 的表示差異，以原始 JSON 與 CIM 時刻解析核對一致。沒有忽略其他內容差異。

## 證據限制與邊界

命令先保存的判斷：現行 simulation.js 第 49 行同步 setItem，失敗 return，第 55 行才 POST，第 59 行成功後 removeItem；來源 SHA 保持且原始 POST 成功。未直接觀測即時 sessionStorage，不擴張為該項動態觀測 PASS。刷新證據採既有 Network／UI 文字，本輪未重新操作瀏覽器。

未另開 run、POST、stop、重啟、開 DB、重跑 R4 verifier 或 W2／W3 測試；未執行 Git、清理、交易、採集或修改應用程式。僅新增此驗收文件與同步入口。cleanup 不代表 ownership 釋放或逐列帳務重驗；本輪不取代 R4 八小時驗收。

下一步建議由原指定 5.6 Sol (Web) 限定核對 W2／W3／W4／W5 的 Git 分片與待提交內容；提交／push 仍需既有明確授權。本次角色例外不延伸至 Git，不自動新增功能或啟動案例。
