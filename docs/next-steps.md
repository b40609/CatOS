# 下一步

更新：2026-11-17。2026-11-17 前的完整沿革（研究線、工作包 A～F、v1 驗收、repo 重建、兩台機器分工）在 `docs/archive/next-steps-20261117.md`，本頁只寫現況。

## 現況

- v1 local-sim、研究線、工作包 B（Kill-Switch 與新風控預設）都已完成並合併進 `main`。
- **M1 接 OKX 模擬盤**：程式完成、在模擬盤實測、獨立驗收通過（有觀察）。只差使用者核准正式設定並啟動。

| 步驟 | 內容 | 狀態與證據 |
| --- | --- | --- |
| 1 | 模擬盤用戶端、`demo status` | 完成。桌面金鑰檔第 2 組可用（子帳戶、讀取＋交易、net_mode）。讀到 5,000 USDT |
| 2 | `demo first-order` 開倉再平倉 | 完成。ordId 4105011010260422656／4105011044586606592，權益變化等於成交損益加手續費 |
| 3 | 策略 Bot `demo bot`，逐根 K 線經 Supervisor 下單 | 完成。11-16 用隔離核准跑 5m：買 1 張，ordId 4105099728749056000，12 筆成交全部入帳。11-17 修正後又跑一次：買 1 張，ordId 4105945336137371648 |
| 4 | Kill／Hard 在模擬盤平倉 | 完成。11-16 Kill 後 4 秒平倉（ordId 4105108293048061952）；11-17 修正後同樣 4 秒平倉（ordId 4105971616673157120，14 筆成交），部位 0 |

## 使用者要做的

1. 在 `C:\dev\CatOS` 的終端機核准正式設定（15m、Donchian 192／48、1 張），代理不能代做：
   `.venv\Scripts\python.exe -m catos.cli strategy approve --strategy donchian-breakout --version donchian-parameters-v1 --sha256 1596e3ace639379086f6fd5ff2ba73948697c2b34884366c3b32b15ba9ba6817 --profile catos\deployment_profiles\donchian-breakout-15m-192-48.json`
2. 啟動：`.venv\Scripts\python.exe -m catos.cli demo bot --profile catos\deployment_profiles\donchian-breakout-15m-192-48.json`。視窗要開著，電腦不能睡眠。

## M1 獨立驗收（2026-11-17）

- 第一輪 FAIL：`reports/okx-demo-m1-acceptance-20261117/acceptance.md`。下單出口、UNKNOWN 不重送、成交入帳、憑證、Decimal 都通過。不通過的是四個缺陷：
  - D1：清倉途中讀取失敗一次就放棄，部位留著。
  - D2：Soft／Hard 鎖存與當日基準只存在單次 run，同日重啟就重設。
  - D3：沒看其他合約的部位。
  - D4：同一個帳戶可以同時跑兩個 Bot。
- 修正：
  - D1：讀 OKX 會退避重試，清倉中重試約 2 分鐘。
  - D2：帳戶紀錄放在 `~/.catos/okx-demo-accounts/`，存當日基準與 Soft 鎖存，重啟和換 output root 都沿用。紀錄遺失或損壞就拒絕啟動。Soft 只能由使用者用 `demo rearm` 解除。Hard 會寫入共用的 Kill-Switch 紀錄，來源是 `demo-bot`。
  - D3：讀整個帳戶，其他合約有部位或掛單就視為陌生部位。
  - D4：用 OKX uid 的檔案鎖，一個帳戶只能跑一個 Bot。
  - 另外依觀察補了幾項：有部位時每分鐘看一次帳戶；等 K 線期間也檢查 Kill；反手的第二腿被 Soft 擋下時以空倉繼續跑；只允許 BTC-USDT-SWAP；手續費不是 USDT 就不結清；清倉失敗時 CLI 回 2。
- 第二輪重驗 PASS（有觀察）：`reports/okx-demo-m1-acceptance-20261117/recheck.md`，D1～D4 都用驗收者自寫的情境重現過。這輪找到 N1（帳戶檔被刪除會當成首次建立）與 N2（帳戶檔跟著 output root 走），已依上面的方式修正。
- 第三輪重驗 PASS（有觀察）：`reports/okx-demo-m1-acceptance-20261117/recheck3.md`。N1、N2 修好，D1～D4 沒有回歸，沒有新缺陷。之後依觀察 O1～O4、O6 補了以下幾項，只有開發者自測：
  - 第一次寫帳戶紀錄失敗時不留下鎖檔。
  - 建 run 失敗會關掉 log。
  - 關閉 Supervisor 失敗時仍會釋放鎖。
  - Ctrl+C 後 `status.json` 寫成 stopped／interrupted。
  - 啟動被拒時附上處理提示。
- 還沒處理的觀察：
  - O5：任一帳戶檔損壞時，`demo rearm` 整個停下。
  - O7：少數啟動例外仍會印 traceback。這時鎖已釋放，也還沒下單。
- 驗證：後端整套與前端四項檢查見 commit 訊息。

## 代理決定（可推翻）

- 帳本沿用 local-sim 的資料庫結構與標籤，不改 schema；實際交易所記在 run 的 manifest。
- P1 核准涵蓋模擬盤 Bot，只認 2026-11-16 之後的核准。
- 錯過後補處理的 K 線只更新策略狀態，不下單。
- Hard 寫入 Kill-Switch 紀錄（INVARIANTS 原文就是「Hard 啟動市價清倉及 Kill-Switch」）；Soft 跨日也保持鎖住，要人工解除。
- 入金會掩蓋虧損：外部資金流在模擬盤階段不分類（使用者 11-16 第 3 題），模擬盤上不要入出金。

## 已知缺口

- 停下後不能接續同一個 run：重新啟動要先平倉。
- 交易所端的災難停損（P6）沒接，預設也是關閉。
- 介面沒有 Bot 畫面，等前端定案再接。
- 九月的模組（`okx_http`、`demo_collection` 等）仍被 Supervisor、帳本與風控期間引用，還沒拆。
- 驗收觀察，沒有處理：
  - 送單請求最壞的耗時會超過 Supervisor 的 5 秒等待。超過時記成不確定，再查詢結清，結果仍正確。
  - 只看 SWAP 部位和一般委託，看不到條件單。
  - OKX 回報空的 tag 時仍接受。
  - 清倉單送出時遇到 503，依規則停下，要手動平倉。
  - 8770 服務要重啟，才看得懂 `demo-bot` 來源的 Kill-Switch 紀錄。舊版會把整份紀錄當成無法讀取，結果是擋下所有 run。
- 其他小缺口沿用舊清單：`docs/archive/next-steps-20261117.md`「已知小缺口」。

## 等使用者決定

- 前端方向（另一個對話在出 X／Y／Z 草稿）。
- 第 6 步（同幣種多策略）的做法草案，見封存檔。
- 下一個工作包候選：Bot 的介面、接續 run、P6 災難停損、拆掉九月模組、Agent 提交策略的入口。
