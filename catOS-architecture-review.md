# catOS 生產級架構評估

**已確認：單一 Supervisor 獨佔資金副作用，v1 單合約單 Bot；研究採 Jesse research 介面風格＋最小 Decimal 核心，不依賴 Jesse 完整套件。僅處理已收盤 K 線，支援只算指標的 warmup_bars；儲存失效緊急通道、虛擬分帳及內部對沖延後。**

本評估以分鐘至小時級、已收盤 K 線決策為 v1 範圍。Python 3.11+ 與 SQLite 是執行及儲存底座，FastAPI、Optuna 等本機套件可存在，不需要 Docker、PostgreSQL、Redis、Celery 或其他常駐服務。使用者已選擇先完成研究與本機模擬，Demo／Live 分階段再上。本文以專案根目錄 AGENTS.md 與使用者最新決策為準；第 15 節區分已確認原則、延後項目與剩餘政策細節，不把候選方案當核准要求。本文完成的是架構文件，不代表產品已實作、測試通過或獲准接觸真實憑證／發送 Live 請求。外部事實沿用 2026-09-10 已查核的官方文件及原始碼；本次僅同步使用者確認的 P7 選型、Closed Bar 與 warmup_bars 邊界。

**1. 從第一性原理定義安全，而非從框架開始**

catOS 最重要的資產是：交易所部位的可信認知、能改變部位的唯一權限，以及重啟後仍可解釋每筆動作的紀錄。策略只有提出交易意圖的權利。Supervisor 才能認可意圖、保留風險額度、產生委託、解釋成交與更新帳本。

這導出五個核心條件：

1. 任一增加風險的出站委託，都能追溯到已持久化的意圖、策略版本、風控決策與額度保留。
2. Worker 提供的身分、倉位、價格、風控標誌與交易所欄位都不是權威事實。
3. 未知結果必須是一等狀態；不能用預設成功、預設失敗或盲目重試消除它。
4. 新增風險需要肯定證據；降低風險有獨立的合法通道，不能因已超限而連平倉都遭拒。
5. 交易策略、交易所實體部位、研究模擬結果分別有明確語義；不能靠名稱相同假裝一致。

必須承認三個物理限制。一般 Python 子進程不構成 OS 安全沙箱；沒有交易所端持久冪等契約，無法無條件保證遠端下單 exactly-once；本機斷電或網路完全中斷時，Supervisor 無法執行新的市價清倉。可以嚴格設計內部安全性與恢復性，不能承諾永不損失、永不阻塞外部故障，或任何資料量都在幾秒完成研究。

「機構級」在此應指可審計的權限邊界、保守的不確定性處置與可演練的恢復流程。單機部署仍具有單機故障域，這不會因加入更多 Python 類別而消失。

設計以個人本機、單人維護為基準。新增機制須能指出目前階段的具體失敗情境、最小做法及驗證成本；不因「生產級」「業界標準」或未來擴充而預設跨平台封裝、多租戶或不受信任程式執行。必要的數值、交易與恢復正確性持續保留。P1 已確認 v1 不建置 AppContainer／原生沙箱；尚未核准的儲存失效緊急下單及 v2 分帳不構成研究交付前置。

**2. 不同架構哲學的選擇**

| 架構取向 | 最強優點 | 必須支付的成本 | 適用位置 |
|---|---|---|---|
| 研究優先：批次向量化＋很薄的下單器 | 批次訊號研究快，起步容易 | 路徑依賴、部分成交、風控及 live 語義容易分裂 | 可作研究比較，不宜作資金核心 |
| 可審計的小核心：事件序列＋唯一 Guardian | 故障狀態少，權限與恢復較容易驗證 | 必須自行驗證撮合模型與交易所適配 | **catOS v1** |
| 組合帳本：虛擬部位＋聚合執行 | 多策略共享資本，支援歸因及內部淨額抵銷 | 會計、分配公平性、退出規則較複雜 | **已延後，非既定 v2 路線** |
| 通用多市場交易平台 | 多資產、多交易所、高事件量的擴展較成熟 | 大量目前用不到的領域模型及整合面 | 需求超出本專案邊界時再考慮 |

以下複雜度是相對於 catOS 的改造與維護負擔；沒有共同資料、硬體與策略的實測，不能提供可信的倍數速度排名或虛構程式行數。

| 系統 | 已有優勢與研究／實盤方式 | 效率與擴展取向 | 與 catOS 底線的落差 |
|---|---|---|---|
| Freqtrade | 策略、回測、dry/live、研究工具完整；SQLite 可用 | pandas 批次訊號，適合 bar 策略；完整 bot 生態帶來較大的既有模型 | 現行官方表列 OKX futures 為 isolated；持倉模型使用 Float；安全邊界需改造 [1][2] |
| Jesse | 直觀策略介面；research 接受記憶體 candles，可回傳績效、權益曲線與交易 | 可直接封裝研究入口；每次呼叫前後重設全域研究狀態，並非所有使用方式都要 fork | 原生價格、數量與持倉計算含 Float；要保留 catOS 全交易 Decimal 才會涉及深層改造 [3][4][5][27] |
| NautilusTrader | Backtest／Sandbox／Live 共核心；明確的事件及交易領域模型 | Rust 核心提供高事件量擴展路線，支援多資產／場所 | 原生定點型別不是全鏈路 Python Decimal；理解及整合面積大；Redis／PG backing 是可選，不能說它必須使用外部 DB [6][7][8] |
| Hummingbot | Controller／Executor 分層，擅長做市及執行策略；可用 SQLite | 多 connector 與 executor 提供豐富組合能力 | 共用 Controller 不等於所有回測與 live 執行語義相同；Windows 官方安裝路徑涉及 WSL2；仍需自建安全邊界 [9][10] |
| catOS 自建 | 固定一個交易所、一種合約、一種持倉模式 | 預期足以處理本次 bar 級需求；Decimal 逐事件吞吐需實測 | 功能最少，資金安全驗證責任最大；小程式不會自動變安全 |

Jesse research 提供此次 API Style 的設計參考。它接受 config、routes、data_routes、candles 與 warmup_candles，呼叫框架的 simulator，並在執行前及 finally 重設 config、router、store。DB 程式有略過連線的條件；套件依賴列有資料庫 client，不等於每次記憶體回測都必須啟動 PostgreSQL／Redis。全域狀態可透過順序研究或既有獨立 Worker 管理，不能單憑這點否決封裝；目前主路徑使用 timestamp replay，也不能以舊的連續 1m 限制作全面結論。[3][4] 以下比較保留為已完成選型的依據，不構成 Jesse 整合工作。

真正的相容性差距在數值與策略語義。所查版本的 Strategy 把一般訂單價格／數量轉為 `np.array(..., dtype=float)`，Position 與交易所模型也使用浮點計算；在入口傳 Decimal、出口轉回 Decimal，無法改變中間已做 Float 交易運算的事實。[5][27] Jesse 策略亦會讀取其部位、可用保證金與訂單狀態；接上 catOS 純訊號 Worker 仍需定義對應語義。catOS 的 OKX 合約張數、歷史 funding、帳戶日損、在途額度與 UNKNOWN 需要逐項驗證，不因回測函式同名而自動一致。

| 選項 | 可省下的工作 | 保留的維護／驗證成本 | 與目前決策的關係 |
|---|---|---|---|
| A. 直接封裝原版 `jesse.research` | 重用既有撮合、策略生命週期、指標及研究輸出，研究起步最省 | 固定版本、安裝依賴、資料／合約單位映射與 catOS 策略接橋；實盤風控及對帳仍由 catOS 負責 | 未採用；原版交易回測含 Float，超出已批准的「僅 Optuna 評分」例外 |
| B. 借鑒 research 介面，保留最小 Decimal 核心 | 重用記憶體輸入、warm-up、一次呼叫回傳結果的使用方式；沿用合適的現成研究／圖表套件 | 仍須自行維護 bar 撮合、費用、funding 與 Decimal 帳務；借介面不等於借到回測引擎 | **P7 已確認採用**；不依賴 Jesse 完整套件，只做 Closed Bar，warmup_bars 期間僅算指標 |
| C. fork Jesse 並全面替換成 Decimal | 保留部分 Jesse 策略生態與引擎結構 | 改造 NumPy／原生數值依賴、策略 API 與帳務，持續合併上游並重驗；負擔最高 | 未採用 |
| D. 研究介面與引擎全部自建 | 完全掌握介面與事件模型 | 同時承擔交易核心、研究便利功能及工具維護，容易擴張成通用框架 | 未採用全面自建研究工具的路線 |

P7 已確認採 B：「借鑒 Jesse research 介面風格（API Style）＋最小十進位核心（Decimal Core）」。Jesse 僅作研究入口設計的參考；catOS 不安裝或依賴完整 Jesse 套件，不 fork 其引擎，也不維護 Jesse 初篩與 Decimal 再驗兩套模擬路徑。策略遵循 catOS 的純訊號契約；資料、撮合及 Decimal 帳務保持窄範圍。上表保留作為選型依據，維護負擔屬架構判斷，尚無 catOS 相同工作負載的性能或工時實測。

**3. 最終拓樸：一個資金決策核心，幾個清楚的邊界**

本機 UI 與靈感匯入 → 策略製品 → 純訊號 Worker → 結構化意圖 → Supervisor → OKX。依已確認的 P1，Worker 採普通獨立 Python 程序，提供故障隔離，不承諾 OS 層的惡意程式隔離。

行情、帳戶、成交反向進入 Supervisor，形成標準事件與權威帳本，再把 Worker 所需的唯讀視圖送回。SQLite 與 Telegram 也只由 Supervisor 存取。UI 只是觀察與控制介面，關閉瀏覽器不影響交易。

Supervisor 是一個 Python 進程。內部包含序列化的狀態更新器、風控、唯一出站訂單排程器、交易所適配器及 SQLite 寫入通道。它們是模組，不是微服務。SQLite I/O 可交給同進程的單一專用執行緒，避免 fsync 阻塞 asyncio 行情讀取。v1 由唯一的資金狀態驅動器依序完成「評估、暫定額度保留、提交、確認」，一次只有一筆資金決策提交在途；前筆未確認前，不批准下一筆資金決策。行情接收與健康監控仍持續運行，其他執行緒不能自行決定訂單。

每個實盤 Bot 一個長駐 Worker。研究使用少量受限 Worker，不與 Guardian 爭滿 CPU／RAM；預設以低並行度執行 Optuna。Supervisor 不執行策略、策略初始化、動態 import 探測或策略提供的序列化 hook。連列出策略都只讀資料 manifest。

最低必要持久化資料只有幾組：策略製品及啟用版本、決策輸入與 checkpoint、意圖與風控保留量、委託及出站待辦、成交／帳務分錄、風控鎖存及清倉操作。這些在同一個交易 SQLite 中原子更新；不需要另外部署訊息佇列，也不需要把每個 UI 操作都升格為 event sourcing。

歷史 K 線可放另一個本機 SQLite 快取，仍由 Supervisor 寫入。研究啟動時將所需資料批次載入記憶體；回測熱路徑完全不碰磁碟。資金狀態不能跨兩個 WAL 資料庫分開提交，避免誤認跨檔交易具有同樣的斷電原子性。

**4. 同一策略、同一事件語義的回測內核**

2026-09-11 已完成第二個研究切片：`catos/optimization.py` 採 InMemoryStorage＋順序 ask/tell，整數格點及十進位字串候選，策略仍執行既有 Decimal backtest，僅衍生評分轉 Float。保留 trial 參數、原始績效與失敗紀錄；8 個專屬測試及 12-trial 合成示範通過。此為本地研究控制器，尚未接入正式 Supervisor／Worker 與 SQLite；分工交接見 WORK_PLAN.md 及 ANTIGRAVITY_HANDOFF.md。

2026-09-11 使用者已同意首個研究切片：單合約、單週期、合成 Closed Bar；只支援市價意圖，本根收盤決策、下一根開盤加明示滑價成交。已新增 `catos/research.py`、合成資料示範及專屬單元測試。這是純記憶體策略／撮合／Decimal 帳務切片；本節其餘完整研究與共用核心能力仍依階段實作，沒有接入帳戶風控、保證金／強平、Supervisor／Worker 執行程序或交易所連線。可執行入口、資料契約及假設見 README.md。

P7 已確認採 API Style＋Decimal Core。回測入口接受記憶體資料及設定，一次呼叫回傳交易、權益與績效；策略執行只讀取當時已收盤的指定週期 K 線，不載入 1m 細部資料或其他更細行情來還原盤中路徑。

最小研究入口的介面形狀為 `backtest(*, strategy, candles, config, warmup_bars=0)`；`warmup_bars` 是輸入 candles 前段用於預熱的非負整數根數。預熱與正式區間均只接受已收盤 K 線，依時間逐根推進，不把整段未來資料暴露給策略。

- 前 `warmup_bars` 根只更新指標及必要歷史窗口，不呼叫交易決策，不產生、排隊或保留交易意圖，不撮合、不記交易費用，也不納入績效期間。
- 預熱結束後保留指標狀態，從下一根正式 K 線收盤開始允許策略決策；不得在預熱結束時補送預熱訊號，亦不得在第一根正式 K 線開盤執行來自預熱的委託。
- `warmup_bars=0` 表示不使用預熱區段，第一根正式 K 線先更新指標再檢查就緒；正數預熱結束時即須就緒。負數、非整數、資料不足以涵蓋指定預熱及至少一根正式 K 線，或指標未就緒時，回傳明確的輸入／就緒錯誤，不默默縮短預熱或以未就緒指標交易。
- 正式區間的第一筆決策仍遵守下述成交時序，不能在讀完該根收盤資料後回填同根成交。結果記錄預熱根數及正式評估起點，以供重現。

標準策略物件應含：製品雜湊、策略邏輯、Decimal 參數、宣告的標的與週期、warm-up 需求、可序列化狀態及資源預算。它的行為可描述為：

\[
(s_{n+1}, I_n)=F(s_n,e_n,v_n;\theta)
\]

其中 s 是策略狀態、e 是標準輸入事件、v 是當時可見的帳戶／部位視圖、θ 是固定參數、I 是本事件產生的一整組意圖。回測、Demo、Live 載入相同製品，使用相同 F；時鐘、行情來源與成交來源由外部注入。

v1 意圖以「某標的的目標合約張數＋有效期限＋執行約束」為主，這是純資料訊號，不是可直接送往交易所的訂單 payload。Supervisor 用已成交部位及仍有效的委託決定差額並驗證合法數量，不能每收到一次目標就重新買入一次。策略不能填 API key、broker tag、帳戶模式或原始任意 API 參數；減倉也由 Supervisor 判定，不能相信 Worker 宣稱的 reduce-only。

核心採事件驅動，只有一套委託、成交、費用、資金費、持倉與風控狀態轉移。回測用記憶體撮合器產生成交；Demo／Live 用 OKX 回報產生成交。純計算部分可共用同一核心套件，研究 Worker 跑模擬副本；Supervisor 不向它提供實盤適配器或憑證。研究與交易 Worker 均遵循第 6 節已確認的受信策略邊界。

向量化只用於可證明逐點等價的特徵預計算，不另外維護向量化交易狀態機。嚴格維持價格、數量、金額及保證金 Decimal；不能先用 NumPy float 計算 PnL 再轉回 Decimal，宣稱滿足精度底線。v1 優先使用增量指標、快取與批次載入，避免每根 K 線重算全部歷史。

資料使用事件時間與可見時間，直接接收指定週期的已收盤 K 線，不以載入 1m 再聚合為前置。需要多週期時，各 stream 亦只能使用自己已收盤的資料，不要求不同合約擁有完全相同的資料起點。相同時刻收盤的相關資料先形成固定順序的決策 frame；缺資料要標為 missing/stale，不得填入未來值或悄悄假造可交易價格。OKX K 線的 confirm 欄位區分未完成及已完成，輸入層應依此正規化。[11]

v1 撮合假設需要明確寫在報告內：收盤決策後，最早在下一個可交易事件成交，不能知道收盤價後再假設以同一收盤價無滑價成交。應包含手續費、買賣價差、滑價、部分成交／拒單、合約張數限制，以及實際歷史資金費率和計費時間。沒有歷史資金費或合約規格版本時，資料品質不足必須可見。

首個切片將市價單假設為全量成交，以不利方向 bps 滑價及 tick 捨入模擬合計執行成本；沒有另加 spread 或模擬部分成交／交易所拒單。資金費由輸入明確提供時間、費率及結算 mark，同時事件先按原部位結算再撮合。以各根收盤估值，期末不強制平倉，保留未實現損益與未成交意圖；這些模型假設寫入結果，不宣稱可重現交易所盤中路徑。

OHLC 不能辨認同一根 K 線內先觸停損還是停利。Closed Bar 回測須明列其保守順序或結果上下界，不以補載 1m／更細行情解決歧義，也不宣稱可還原逐筆成交。未來實盤 Guardian 仍會在 K 線內監控 mark price；其盤中熔斷以獨立 mock／插針壓力情境驗證，不把細部行情重播加入目前研究核心。**相同程式可以保證相同輸入下的行為一致，不能保證模擬市場與真實市場的成交一致。**

本機幾秒研究是有資料量與硬體範圍的性能目標。驗收須指定標的數、K 線數、指標、trial 數、冷啟動或暖快取及記憶體上限，再分別量測載入、單次回測與優化耗時。不要把一次回測的耗時宣傳成數百個 trial 的總耗時。

Optuna 由可信研究控制器以 ask/tell 管理；v1 可置於 Supervisor 的受控工作通道，計算則送研究 Worker。使用 InMemoryStorage，trial 結果由 Supervisor 寫 SQLite，不讓每個 Worker 直接用 Optuna RDBStorage 競爭寫庫，也不保存 pickle/joblib study。[12][13] 交易相關參數使用整數格點或十進位字串候選，進入策略前還原為 Decimal。P7 已確認：交易計算及原始績效維持 Decimal，衍生搜尋評分可轉為 Float 交給 Optuna；檢查評分為有限值，保存原始值、評分公式及實際 trial 參數，Float 評分不回流為資金帳本或風控依據。此例外不涵蓋回測引擎的價格、數量、PnL 或保證金浮點運算，亦不自行擴大交易參數的精度例外。

研究至少區分訓練、驗證、保留測試資料，並提供走勢／交易明細、費用後績效、drawdown、曝險、週轉及參數穩定區。固定種子不保證非同步 TPE 的搜尋路徑一致；需要精確重現時採順序搜尋，或固定 ask 批次及 tell 順序。保存實際 trial 序列比保存一個 seed 更可靠。

**5. 數值與交易模式：在出站前強制收斂**

所有金額、價格、部位從 API 字串直接解析為 Decimal，以字串跨 IPC，以 SQLite TEXT 儲存。固定 Decimal context、有效位數及每種運算的捨入規則；拒絕 NaN、Infinity、無界精度、除零與錯誤單位。FloatOperation 可用來發現意外混入，但不是完整型別驗證的替代。[14]

SQLite TEXT 只是儲存格式，不會使 SQL SUM、CAST 或排序自動具備 Decimal 語義。資金加總在可信 Python Decimal 層進行；不要讓 SQLite 隱式轉成 REAL。也不能用 quantize 的小數位數取代步長檢查：非十的冪次的 lotSz 必須按整數倍計算。數量通常向較小曝險捨入，價格依訂單方向與限價語義規範。

只接受 metadata 驗證通過的 linear USDT-settled SWAP，不能只靠字串以 USDT-SWAP 結尾。讀取並版本化 ctVal、ctValCcy、ctType、lotSz、minSz、tickSz 等；對允許的線性合約建立「每張對應標的數量」u，再以 |q|×u×mark 計算名目曝險。不要把張數當幣數，也不要在未確認定義下重複乘 ctMult。[15]

帳戶層驗證 net_mode；訂單層固定 tdMode=cross、posSide=net。cross 不等於一個能替所有訂單自動套用的帳戶總開關。交易所設定槓桿也不等於 catOS 的全域有效槓桿。[16]

所有建立 SWAP 訂單的出站路徑，由同一個可信 builder 從白名單欄位重建 payload，在簽名前強制填入 **tag = 41cb53c54d6dABDE**。包括開倉、一般平倉、硬熔斷、Kill-Switch，以及未來允許的 algo／保護單路徑。不能把 Worker 字典 merge 進請求；標籤不可被策略省略或覆寫。不支援所需歸因欄位的端點不列入可用路徑。

OKX 目前的直接 OpenAPI 整合文件使用 tag；CLI／MCP 使用各自的 Builder 欄位，不宜混淆。catOS 直接接 REST／WS API，可避開額外 CLI 依賴。[17] 此報告沒有驗證給定標籤的帳戶歸屬、核准狀態或返佣資格；這些需在 Builder dashboard 另行驗證。請求帶標籤、訂單成交與返佣入帳是不同的驗收事項。

Demo 與 Live 必須有獨立憑證、帳本命名空間與啟動 session。用戶一鍵切換是啟動相同策略製品的新環境；不能把 Demo 持倉、委託 ID 或未完成意圖搬入 Live。OKX Demo 需要對應的 Demo key 及 x-simulated-trading 設定。[18]

**6. Worker 職責與已確認的受信策略邊界**

使用者已明確要求 Supervisor 獨佔 API 金鑰與風控，策略端純訊號計算。策略只接收行情、參數及必要的唯讀視圖，輸出訊號／目標意圖；不取得交易 client、簽名器、寫庫介面或任意 URL 代理。Supervisor 自行驗證意圖、決定合法數量並構建出站請求。Freqtrade 官方同樣區分收盤訊號與後續交易執行，這可作職責分工的參考，不能據此推論所有框架都採用相同安全沙箱。[Freqtrade 策略文件](https://www.freqtrade.io/en/stable/strategy-customization/)

P1 已由使用者確認：v1 只執行使用者選定並經檢查的策略及依賴，防範程式錯誤、失控訊號與 Worker 故障。採普通獨立 Python Worker、既有 JSON IPC、啟動時不傳遞憑證／多餘 handles、有界輸出及逾時處理；不使用 AppContainer，不建置 macOS 原生沙箱封裝。Worker 按契約只計算並傳遞純資料訊號，不主動連網；外部資料由 Supervisor 提供，這是應用職責約束，不是 OS 禁網保證。策略版本與依賴經檢查後才執行，AI 生成程式不因來源是 AI 就自動可信。利用模組分工與測試降低誤用，不自製 Python 安全直譯器或通用策略語言。

使用者已接受此保證範圍：普通子程序提供的是故障隔離，**不提供 OS 層防止惡意策略讀檔、連網或越權的保證**。不傳 API key 不等於 OS 已禁止它取得秘密；程式檢查與測試也不構成惡意程式隔離證明。此已確認邊界取代先前對任意半受信 Python 的強制隔離要求；後續實作與驗收以應用職責約束及受信策略前提為準。

只有日後明確需要直接執行未審查的第三方／AI 插件，或要求 OS 強制防止程式惡意越權時，才提出成本與影響，交由使用者重新決定安全邊界。Microsoft AppContainer 與 macOS App Sandbox 的來源僅保留作未來評估參考，不是 v1 的實作或驗收要求。[19][20]

Worker 故障、逾時或協議違約時停用該 Worker，Supervisor 繼續管理其持倉。基本驗收聚焦不傳遞憑證、策略介面不暴露交易能力、壞訊號不繞過風控、Worker 異常不阻塞 Supervisor；這些驗收不能被標為已通過 OS 對抗性隔離測試。

FastAPI 僅綁定 127.0.0.1，且只啟動單一交易服務 instance，不使用多 Uvicorn workers 或 live auto-reload。另需 session 認證、Host／Origin 檢查、CSRF 防護與嚴格 CORS；localhost 並不等於瀏覽器來源可信。前端不取得 API key，Worker 不取得控制面 session，按應用契約不得透過 loopback 操作控制介面；不宣稱普通子程序在 OS 層無法建立 loopback 連線。

Supervisor 對 OKX／Telegram 使用固定功能與目的地，不提供 Worker 任意 URL 代理。Telegram 通知排程與交易排程分開，通知失敗不阻擋落帳或清倉。v1 僅做成交與告警推播；若未來加入遠端下單／解鎖指令，應重新評估控制面權限。

產品內負責策略合成的 AI 只產生策略製品與研究資料，不可直接改寫已安裝的 Guardian、憑證區或已上線製品。自然語言、影片摘要、Pine Script、截圖先形成明確規格，記錄訊號時點、是否 repaint、缺資料行為及交易單位；來源內容只能作資料，不能成為執行 shell 或取得秘密的指令。策略合成 agent 的授權範圍限制在研究工作區，生成程式經檢查後才執行；這些授權與檢查不構成 OS 沙箱。這與受使用者授權、在開發工作區修改 catOS 核心的 coding agent 不同；後者可依 AGENTS.md 自主完成本地開發，仍不得存取真實憑證或發送 Live 交易請求。

Live 啟用綁定製品雜湊、參數、風控設定及帳戶。回測通過不等於可自動替換 Live 策略；新版本走相同研究→Demo→啟用流程。任意 Python 也不天然確定，策略契約與測試用來驗證符合規範的製品可重播。所有經正式訊號介面送達的意圖均須通過 Guardian 檢查，但 Guardian 不提供對繞過應用介面的惡意程式之 OS 防護。

上述邊界假設 OS、Supervisor、已選定的策略與依賴可信；不提供惡意策略或管理員攻擊者的隔離保證。Read／Trade key 不開 Withdrawal，憑證放 OS 保護儲存；Python 不能承諾所有秘密位元組都可可靠清零，重點是避免散落至 log、DB、命令列、環境繼承與研究目錄。[17]

**7. IPC：byte pipes、明確訊框、確定性提交**

v1 使用兩個方向的 OS byte pipes，以長度前綴分框，再傳 UTF-8 JSON。每個方向只有一個 writer；協議含版本、事件序號、Worker 世代及有限型別的 payload。金額全部為十進位字串。bot 身分取自 Supervisor 授予的 pipe，不信訊息自報身分。

輸入驗證包含大小、巢狀深度、數字長度、型別、有限值及重複鍵；未知欄位不能下傳交易所。禁止 pickle、dill、cloudpickle、帶任意 class hook 的反序列化，也不使用自動 pickle 的 multiprocessing.Queue／Connection.recv 或研究 ProcessPool 傳物件。[21] Worker 以乾淨的獨立直譯器啟動，而非 fork 已持有秘密的 Supervisor。

async reader／writer 持續排空資料，stderr 有獨立且限量的排空通道。全部佇列及 pending 數有界。行情展示快照可合併；已收盤的策略事件、已接受意圖與成交不可靜默丟棄。慢 Worker 由持久化序號恢復；過期意圖留下 EXPIRED 結果，不能追補幾小时前本來應成交的開倉。

Guardian 不等待 Worker join、ACK 或 Telegram。同步讀 pipe、等待子程序卻不讀其輸出，可能使事件迴圈或父子程序互相等候；這些不能出現在資金控制熱路徑。[22] 分鐘策略沒有先引入共享記憶體 ring buffer、ZeroMQ 或二進位自訂協議的必要；先量測持久化往返及事件迴圈延迟，再決定是否優化。

至少一次傳遞的完整邊界如下：

1. Supervisor 將會交給策略的決策事件及可见輸入持久化，再傳給 Worker。
2. Worker 對單一事件回傳一整筆 EventResult：全部意圖與新的 JSON 狀態。單 Bot 同時只有一個尚未確認的決策事件。
3. Supervisor 用同一 SQLite 交易提交「事件消費位置、策略 checkpoint、意圖、風控判定、額度保留、出站待辦」。風控拒絕也提交明確結果，避免反覆重播。
4. COMMIT 成功後才 ACK。未 ACK 可以重送；Worker 死亡就由已提交 checkpoint 重播尚未完成事件。
5. 已接受意圖都有可查的執行、拒絕、取消、過期或未知狀態，不能只從記憶體 queue 消失。

意圖主鍵使用 account／environment、bot、strategy version、event sequence、output index 的穩定組合。SQLite UNIQUE 加 canonical payload hash：同鍵同內容回傳舊結果；同鍵異內容屬確定性違約，隔離 Worker。Worker generation 只負責阻擋舊進程訊息，**不能放進重播的意圖主鍵**，否則每次重啟都會變成新交易。

WAL 搭配 synchronous=FULL，用最少的金融提交換取 ACK 的耐久性。NORMAL 在斷電時可能回滾已提交交易；FULL 仍依賴 OS 與儲存裝置履行同步契約。[23] 備份用 SQLite backup API；執行中的 DB 不能只複製主檔而遺漏 WAL。[24]

至少一次不是「Worker 腦中產生的任意意圖永不遺失」。提交前的復原依賴已記錄輸入與確定性重播；提交後則由 SQLite outbox 負責。這個區分讓保證可以測試。

**8. 交易所結果未知：用可觀測的停等換取安全**

出站單的狀態至少有 READY、SUBMITTING、ACKNOWLEDGED、REJECTED、UNKNOWN；成交生命週期另有 live／partially filled／filled／canceled。ACKNOWLEDGED 不等於已成交，撤單 ACK 也不等於再無成交。

先將 SUBMITTING 與固定 clOrdId、payload、request deadline 提交，再碰網路。任何傳送後無法確定結果的 timeout／斷線，以及重啟時留下的 SUBMITTING，都按 UNKNOWN 處理。每次送出前重新檢查風控世代與資料新鮮度，撤銷尚未送出的舊開倉待辦；一旦已出站就按可能受理管理。

clOrdId 可由穩定 order key 編碼或雜湊而來，符合 32 位英數限制，並在本機永久不重用。雜湊只是編碼；仍需保存完整原鍵、映射與碰撞檢查。一次意圖若拆多張子單，每張子單也有固定的子序號，不能把每次重試當新子單。

**OKX 只對當下未結束委託檢查 clOrdId 唯一性。** 首張市價單已成交、ACK 遺失後，以同一 clOrdId 重送仍可能產生第二張單。官方也說明 50004 無法代表成功或失敗。[16][18] 因此 catOS 不能宣稱以重送同 ID 達成交易所 exactly-once。

UNKNOWN 的處置是查詢訂單、pending、歷史委託、成交與帳戶部位，以重疊區間和穩定的 exchange IDs 去重。一次查無訂單不構成從未受理的證明；部位剛好一樣也不能證明不存在成交。未釐清前保留風險額度，阻擋同標的衝突或新增風險的下單。只有確證未受理或明確的拒絕後，才依政策重新建立或推進交易；仍須檢查意圖是否過期。

expTime 可限制延遲請求在伺服器端的受理窗口，但不會撤銷已受理訂單，也不提供 exactly-once 證明。[15] 長期無法查證時保留 UNKNOWN／待處理，提供人工查核入口，不會偷偷釋放 reservation 或換 ID 重送。

本機保證是：意圖不重複接受、成交不重複入帳、未知結果不盲目重送。外部條件不足時，「一定下到單」與「絕不重複下單」不能同時無條件保證；以資金安全優先時，必須允許受控阻擋。

每個 account／environment 由一把 OS mutex 或 file lock 保護，同一身份即使使用不同 DB 路徑也競爭同一把鎖。新 Supervisor 不能因舊實例 heartbeat 過期就搶權；舊實例可能只是暫停，仍持有可用 key。Worker epoch 只能隔離舊 Worker，不能在 OKX 端 fence 掉舊 Supervisor。

**9. v1 單合約獨佔：所有權跟隨債務，不跟隨程序**

v1 對 account／environment／instId 實行單 Bot 所有權。Worker 掛掉時，ETH-USDT-SWAP 仍屬於原 Bot，Supervisor 繼續管理現有訂單與部位；不能把 Worker 死亡當成釋放標的的訊號。

只有部位為零、普通及條件委託已終結、沒有 UNKNOWN 提交、相關成交已對帳，才可釋放所有權。v1 不支援帶倉策略交接；新版本或新 Bot 在乾淨邊界接管，降低維護成本。

使用者已確認採用 OKX 專用子帳戶，禁止與手動交易混用。內部可以多個 catOS Bot 各自獨佔不同合約；其他交易程式不得與 catOS 共用這個帳戶下單。同標的獨佔只解決分倉踩踏，不會隔離跨標的保證金與虧損。

啟動或運行中發現陌生訂單／不明部位，要標記並停止新增風險，不能擅自歸給最像的策略。對既有外部部位是接管還是由交易者處理，需有明確政策；本方案不預設可清掉個人主帳戶內的其他資產。

OKX 在 2026 年 8 月公開的 Split Position 說明已支援 USDT 永續、cross／isolated、單向／雙向，但仍按聚合部位計算保證金與強平。[25] 本次沒有確認足以支援完整策略分倉生命週期的公開 API，不將其當成 v1 依賴；也不斷言 OKX 完全沒有 Split Position 功能。未來 API 可用時，仍須驗證歸因、費用與恢復語義，不能直接移除本機帳本。

**10. 全域風控的量綱與事前預留**

先定義：E 是 USDT 風控權益，包含未實現損益並與交易所資料對帳；q_j 是有號合約張數；u_j 是每張標的數量；m_j 是有效 mark；B_j、S_j 是可能成交的買／賣剩餘量，包括結果未知的委託。

對單一標的，採保守的可達部位區間：

\[
q_j'\in[q_j-S_j,\ q_j+B_j],\quad
\bar q_j=\max(|q_j-S_j|,|q_j+B_j|)
\]

兩張相反方向掛單不能先互相抵銷；尚未成交的減倉單也不能先釋放額度。v1 可把所有剩餘訂單量保守納入區間，之後才對經證明無法反向的 reduce-only 進行更精確處理。

P3 已確認採帳戶有效槓桿（Effective Leverage）與單幣曝險預算占比上限，兩項上限全面參數化。先區分已成交部位的有效槓桿與包含掛單的事前風控：

\[
n_j=|q_j|u_jm_j,\qquad
L_{effective}=\frac{\sum_j n_j}{E},\qquad
N_j=\bar q_j u_jm_j
\]

L_max 為帳戶有效槓桿上限，c_j 為單幣占總曝險預算的上限。B_total 是允許的名目曝險總預算，不是已使用保證金或當前持倉總值：

\[
B_{total}=L_{max}E_{risk},\qquad
\sum_jN_j\le B_{total},\qquad
C_j^{budget}=\frac{N_j}{B_{total}}\le c_j
\]

參數集中於使用者管理的風控設定：`max_effective_leverage` 沿用數值預設 `"3.0"`，`max_symbol_budget_share` 沿用數值預設 `"0.50"`，作為各 c_j 的共同上限。所有交易相關參數以 Decimal／十進位字串處理，公式不寫死 3 或 0.5；驗證 L_max 為有限正值、c_j 為 0～1 的有限值。交易所槓桿設定與帳戶有效槓桿上限分開，不因改此參數自動視為交易所設定已更新。Worker 與策略優化不得覆寫帳戶風控設定，使用的設定需隨研究／交易紀錄保存；Live 運行中修改參數的生效流程未定案。

E_risk 使用保守權益與必要的費用／滑價緩衝。實際接受訂單還要檢查可用保證金、當前交易所限制、合約狀態、價格／數量及資料年齡。新意圖評估通過後立即占用暫定 reservation，再將判定與 reservation 同筆提交。可用額度扣除已提交及待提交保留量；COMMIT 後將同一 reservation 從待提交轉為已提交，不重複扣除。配合第 3 節的單一提交序列，前筆提交確認前不批准後筆，不能只靠「各自原子交易」避免超額。未持久化確認不 ACK、不出站；提交失敗或結果不明時停止新增風險，先查明儲存狀態，不把暫定額度當成已釋放。尚未受理而過期的意圖可釋放；UNKNOWN 不可自動釋放。

反例驗收：可用額度為 100，A 申請 80 且提交仍在途時，B 不能再以 100 為可用額度批准另一筆 80；前筆成功後餘額為 20，失敗或未明時則保持新增風險關閉，直到狀態修復。

使用者已選定按總曝險預算計算單幣上限：當 E_risk=10,000 USDT、L_max=3、c_j=0.50 時，總預算為 30,000，單幣上限為 15,000 USDT，即 1.5x 風控權益。可以逐筆建倉，不要求先同時持有兩個幣。本規則取代舊候選的 N_j／E_risk≤0.50；它也不是 N_j／當前總曝險≤50%，後者在第一筆單幣部位會得到 100%。文件與介面使用「單幣曝險預算占比」，不以「業界標準」省略分母。一般框架的部位權重也可能以未加槓桿的投資組合價值為基準，不能直接混用。[26]

E 或 E_risk≤0、預算無效或無法可靠估值時，不進行除法放行；禁止新增風險，依已知部位與硬熔斷流程處理。因價格或權益變動而被動超過已設定的帳戶／單幣預算時，至少停止增加風險並允許合法減倉。是否自動去槓桿、降到哪個目標仍是待決政策；不能把事前上限宣稱為任何瞬間都不會超過的物理保證。

P4 已確認採固定日初權益 E_0 為分母，排除非策略外部資金流。C_t 為當日非策略外部淨流入，流出為負：

\[
r_d(t)=\frac{E_t-E_0-C_t}{E_0}
\]

交易手續費、funding、已實現與未實現損益都進入 E_t；外部注資不算獲利，提款不算策略虧損，已辨認的非策略分潤或獎勵也從交易損益中排除。E_0 是當日固定風險預算基礎，日中注資與人工恢復均不重設分母或放大當日虧損預算。各種返佣／分潤帳單如何辨認，仍須明確分類；未知帳務不能猜作策略獲利。v1 不引入資金流即重設預算或 unitized NAV。

帳戶 totalEq 的報價單位與 USDT 權益不能直接混為同一數字；v1 建議專用帳戶只持有 USDT 抵押資產，其他幣別或負債需明確估值或拒絕新增風險。交易費用回饋與外部分潤入帳也須分類，避免用新的資金流入掩蓋交易虧損。

交易日已確認使用 Asia/Taipei（UTC+08:00），每日 00:00 切日，依此重建 E_0。底層事件時間仍可保存 UTC，日界計算明確轉換時區，不跟隨電腦臨時變更的系統時區。日界線重建需要完整帳務與估值；停機跨日若無法可靠重建，就保持停止開倉，具體資料不足的人工復原流程仍待定案。反彈、重啟、補入資金或切換日期都不自動解除 Soft／Hard／Kill 鎖存。

**11. 閉合的風控狀態機：將目標、健康與執行進度分開**

不要用一個 RUNNING／STOPPED 布林值承擔所有意義，也不要讓多個 callback 各自呼叫 close_all。有限控制狀態用三個欄位即可：

| 維度 | 值 | 意義 |
|---|---|---|
| 風險要求 R | RUN、NO_INCREASE、FLAT | 可增加風險、只能降低風險、必須收斂至空倉 |
| 健康 H | RECONCILING、HEALTHY、DEGRADED | 尚未確立事實、可依賴目前事實、存在資料／連線／儲存故障 |
| 清倉操作 P | IDLE、WORKING、VERIFY、WAIT、DONE | 無操作、執行撤單及減倉、驗證完成、等待重試／外部修復、已確認空倉 |

另記錄原因集合、風控 epoch、清倉 operation ID、每個標的的在途动作及下次重試時間。UI 可以顯示「硬熔斷，斷線，等待重試」，不用為每個組合新增一個狀態名稱。

普通事件只能提高 R 的嚴重度：RUN < NO_INCREASE < FLAT。P5 已確認 Soft／Hard 日損與手動 Kill Switch 一律鎖存，保存於 SQLite；當日不重設預算，僅限人工恢復。人工 re-arm 仍須對帳完成、無未知單、有效日初權益，以及欲解除的風險原因已依核准政策解除。當前仍有效的 hard／Kill 原因具有否決權，不能被同一批次的 re-arm 覆蓋。空倉本身不代表日損門檻已解除；不能藉 re-arm、入金、修改參數或重啟偷改當日分母。

Soft／Hard／Kill 都不因反彈、跨日、重啟、清倉完成或入金自動解除。台北新日可建立有證據的新日初基準，但建立基準不等於恢復交易。「人工恢復」不等於可無條件解除：是否允許 Soft 在同日損益回升且原預算不變時恢復、Hard 的最早解除時點，以及單純手動 Kill 的解除資格仍待使用者定案；不自行加上「一律次日」或當日可恢復的例外。

新增風險的放行條件是 R=RUN、H=HEALTHY，且製品、所有權、資料、保證金及事前風控均有效。平倉不走這個開倉 gate；由獨立、窄範圍的減倉規則允許，只能作用於核實的實體部位，使用 reduceOnly，且不能穿越零建立反向倉。這避免帳戶已虧到超限時反而無法平倉。

閉合轉移規則如下：每次先吸收最新可驗證事實及執行進度，再重算 soft／hard、Kill 與健康條件，最後才判斷 re-arm 是否合格。優先序是衝突裁決，不是讓後處理的 re-arm 覆寫 hard；只要本次仍有有效 hard／Kill 原因，結果就必須保留 FLAT。所有其他輸入保持狀態並記錄必要原因。

反例驗收：同一批輸入包含「日損達 −5%」與「重新啟用」時，結果仍是 FLAT；網路恢復、清倉完成或再次按啟動，也不能解除仍有效的硬熔斷。

| 輸入／條件 | 風險及健康更新 | 動作／進度 |
|---|---|---|
| 程序啟動 | 保留已持久化 R；H=RECONCILING | 重建事實，不送新開倉 |
| r_d≤−3%，尚未 hard | R 至少 NO_INCREASE | 取消尚未成交的增加風險委託；保留合法減倉能力 |
| r_d≤−5% 或 Kill-Switch | R=FLAT | 以當前 risk epoch 建立或取得唯一清倉操作；失效所有新開倉待辦 |
| 新行情／帳戶／成交 | 更新可信估值與部位 | 重新評估門檻，即使當下沒有任何開倉意圖 |
| 行情過期、斷線、儲存錯誤、對帳差異 | H=DEGRADED，R 不下降 | 關閉新增風險通道；已有 hard 操作保持存在 |
| 部分成交／撤單終態 | R 不下降 | 去重入帳、更新剩餘量、續行同一操作 |
| 429／可重試失敗 | 不回到 RUN | P=WAIT，排定有界退避；到時重新取得事實再決定下一步 |
| 網路 timeout／50004 | 對應委託 UNKNOWN | 不盲重送；查單及對帳，必要時維持 WAIT |
| 連線恢復 | H 先回 RECONCILING | 對帳成功才 HEALTHY，R 與 hard latch 保留 |
| 清倉候選完成 | R=FLAT | P=VERIFY；檢查所有普通／條件／未知委託及部位 |
| 驗證完成 | R=FLAT | P=DONE；仍監看是否有晚到成交使部位重現 |
| 晚到成交使部位重現 | R=FLAT | 喚醒同一風控 episode 的清倉控制器 |
| 明確人工 re-arm | 僅依已核准資格降低 R；有效 hard／Kill 否決解除；當日不重設預算 | 須健康、完成對帳、無 UNKNOWN；hard 後還須空倉且無可重建曝險的委託。合格才開啟新 epoch，否則記錄拒絕原因 |
| 重複或不相干事件 | 冪等更新或不變 | 不建立第二個清倉控制器 |

風控由 mark-price 更新、帳戶事件、成交事件及獨立計時器驅動，不綁在策略 on_bar 或 place_order 前。策略每小時交易一次，Guardian 仍持續重估；行情失效不能當成價格不變。已知部位的即時 mark 損益可補上帳戶推送延遲，但必須用成交序號與快照水位避免重複加總未實現損益。

硬熔斷在同一操作中撤銷所有會增加風險的普通／條件單，並對有可靠實倉、無衝突未知減倉單的標的序列化發送 reduce-only 市價減倉。**不把「所有撤單都確認完成」設為所有標的開始減倉的全域屏障。** 否則一張卡住的撤單就可能拖住全帳戶止血。每個標的最多一個未釐清的減倉动作，部分成交後按最新剩餘量續行。

市場單仍可能部分成交、拒單、遇到價格限制或流動性不足；超額 reduce-only 也不應假設交易所自動裁切。以最新資料求剩餘張數，失敗後重新對帳，不對同一舊數量無限重試。REST 與 WS 不應被當成兩套互不相干的交易限流資源；使用同一可信排程器保留撤單、查單及減倉的配額。[15][16]

429 或斷線時，計時器喚醒原操作，不能重新入場建立第二條清倉 coroutine。重複 −5%、使用者再次按 Kill、重複 WS 回報，都只提高要求或更新進度。Kill-Switch 的語義建議為鎖存 FLAT、撤單及收斂空倉，而非直接殺掉 Supervisor；直接關掉守護程序反而留下未管理的倉位。

完成條件是所有受管實體部位為零、所有可能形成部位的普通／條件委託都已終結、沒有 UNKNOWN、成交及帳務已對帳。單看本機 q=0、某次 REST 無倉位或收到撤單 ACK 都不充分。

數學上，純狀態更新器對所有合法控制狀態與事件都有定義；違規輸入也有明確拒絕／隔離結果。更新器只做有界計算並輸出待辦，不做 I/O。外層唯一資金狀態驅動器可以非阻塞地等待專用 SQLite 執行緒的 COMMIT；等待期間不批准下一筆資金決策，不持有行情接收或健康監控所需的鎖。SQLite 執行緒也不反向等待該驅動器，避免形成循環等待。

COMMIT 是接受意圖與額度保留的持久化確認點。待提交 reservation 已占用額度；未確認前不 ACK、不出站，失敗則進入 DEGRADED。等待期間的行情／Kill／健康事件仍可關閉新增風險授權，不能因舊交易稍後成功提交就重新放行。提交完成後，出站前必須吸收這些事件並重查風控與資料新鮮度；已提交但不再合法的開倉待辦標記取消。已交付網路的請求則保留可能受理的責任，納入撤單與對帳。儲存永久失效時的緊急減倉仍按第 12、15 節待決政策處理。

這能排除設計中的循環等待，但 self-loop 和 timeout 本身不能證明沒有 livelock。完成性須另列前提：程序及排程持續前進、儲存可用、交易所最終恢復、未知結果可查明、沒有外部新下單，而且交易所最終允許正數量減倉。在所有增倉來源終結後，每次正數量的成功減倉降低有限 lot 數，才可推得最終至零。小於可平最小量、停牌、永久斷線或不可查證的 UNKNOWN 必須明示阻塞原因，不能假裝已完成。

**12. 復原與單機故障：不從「看起來沒事」開始**

啟動先取得帳戶鎖，驗證資料庫與製品，再讀取已保存的 risk latch／清倉操作。訂閱私有事件並暫存更新，查帳戶模式、餘額、全部受管倉位、普通及條件委託、重疊區間的歷史成交與帳務，去重合併後再次檢查一致性。訂單 WS 不提供訂閱前所有訂單的初始快照，因此不能只等 WS。[16]

REST 與 WS 並非單一全域原子快照，不能把一次 REST 時間戳冒充全世界一致的序號。每種資料依其穩定 ID、累計成交量、時間與可用序號處理，在禁止新開倉期間重查直到能建立一致邊界；衝突未消除時維持 RECONCILING／DEGRADED。

之後把殘留 SUBMITTING 視為 UNKNOWN，補上遺漏成交，檢查 q、現金流、費用與帳戶權益，恢復原有所有權。曾進入 hard 的 session 繼續其原清倉操作；曾在普通運行的 session 也要通過健康 gate 才可恢復。不可只讀最後一列 RUNNING 就立即開倉，亦不可每次重啟把當前權益設成新的日初資本。

DB 或歷史備份太舊、交易所資料保留區間不涵蓋停機期間時，數學上沒有足夠證據重建完整事實。此時顯示需要人工對帳；不能猜測 missing fills、成本或資金流。資料庫損壞也不應自動刪庫重建並恢復 Live。

P6 已延後儲存失效時繞過持久化的 emergency 下單通道。離線保護依使用者提出的方向，優先評估事先建立於 OKX 的參數化條件停損；Supervisor／Guardian 在線時仍執行帳戶級風控。交易所保護單延續唯一 Supervisor 出口、固定 tag、委託追蹤與重啟對帳，無須另建第二個持有金鑰的本機救援程序。

具體候選為每個受管合約一張整倉市價停損：官方 algo 端點提供 `closeFraction="1"`，在 net 模式須搭配 `reduceOnly=true`，適用條件／OCO 市價平倉且不支援 Portfolio Margin。`slTriggerPx` 為停損價格、`slTriggerPxType` 可選 last／index／mark，`slOrdPx="-1"` 表示市價；可評估 `cxlOnClosePos=true`，讓保護單在空倉後取消，須符合官方帳戶模式限制。官方也說明整倉 TP/SL 的數量隨部位變化，可減少部分減倉後反覆改數量的工作。[28][29] 實際觸發價格、調整規則、帳戶模式及首次建倉的保護生效時點尚未定案。

Demo 階段只需針對選定路徑驗證幾個直接失敗情境：部分成交期間何時有保護；新增／縮減部位後覆蓋是否正確；建立或修改 ACK 遺失能否查回；與正常平倉競爭是否只減倉；停損後殘留進場單會否再次開出無保護部位；重啟能否辨識保護單及實際成交。不能只因提交成功就宣稱離線完整受保護。若評估 Cancel All After，它僅撤單、不平持倉，對 algo／保護單的涵蓋需另查；目前不把 CAA 設為必要依賴。[15]

交易所保護單也不等於帳戶級 −5% 的絕對止損。價格跳空、滑價、交易所服務暫停仍可能讓虧損越過門檻。24/7 的部署驗收至少包含避免自動睡眠、啟動後自動對帳、網路恢復、電源中斷與通知失效。系統可雙擊啟動，但電腦關機後無法靠本機 Python 持續運作。

磁碟不可寫時禁止新增風險，在可行時告警；既有交易所停損繼續依交易所條件處理。延後的 emergency 通道不提供繞過持久化的新下單權限；新增 hard 狀態也不能假稱已成功寫入故障磁碟。恢復後先對帳，保留已持久化的鎖存，不以重啟清除未知狀態。這接受了離線期間只能依既有交易所保護執行、無法精確按帳戶日損門檻主動清倉的能力限制；不更動在線 −3%／−5% 及人工恢復政策。

**13. 同帳戶同幣種多策略：已延後**

P8 已確認 v1 維持「單合約單 Bot（One Bot, One Contract）」，沿用第 9 節的所有權與釋放條件。虛擬分帳、內部對沖、分配計畫、physical／virtual 雙重 gross 及策略退出連動均延後；不預建分配器、house 分帳或內部轉倉帳本。

v1 保存自身可追溯與對帳所需的 bot_id、策略版本、意圖、委託、原始成交與費用關聯即可；這是當前歸因需求，不授權未來多策略的資本分配政策。

待 OKX 官方分倉 API 能完整支援子部位識別、建立／增減／平倉、保護單、成交費用歸因與重啟查詢時，再評估同帳戶同幣種多策略，不預先承諾採交易所分倉或自建虛擬帳本。現有官方 Split Position 說明仍按聚合部位計算保證金與強平，不能把 UI 分倉視為資本隔離或完整 API 保證。[25]

**14. 漸進演進與可驗證的上線界線**

| 階段 | 交付切片 | 必須達到的出口條件 |
|---|---|---|
| v1 研究核心（目前交付） | Jesse research 介面風格＋最小 Decimal 核心；Closed Bar 記憶體回測、warmup_bars、同一策略 F、基本圖表；Optuna 搜尋評分允許 Float | 不依賴 Jesse 完整套件、不載入 1m 細部資料；預熱只算指標、無交易意圖及績效；無未來資料；固定輸入重播一致；費用、funding、lot/tick 單位正確；依已確認 P1 執行經檢查的策略 |
| v1 交易底座 | 單 Supervisor、單帳戶鎖、單合約所有權、JSON IPC、金融 journal／outbox；普通獨立 Worker | 不傳遞憑證／交易介面；重播不重複接受；舊 Worker 不可冒名；Worker 異常不阻塞 Supervisor |
| v1 Demo 前哨 | OKX 適配、固定 tag、私有 WS＋REST 對帳、UNKNOWN 管線、風控 FSM、Telegram；評估交易所條件停損 | 重啟及斷線故障演練通過；歸因與所選保護單生命週期驗證；不要求延後的儲存失效 emergency 通道 |
| v1 Live | 相同製品與風控核心、環境隔離、已確認的損失／退出政策 | 長時間運行與各種故障驗收；Live 啟用需綁定明確版本及預算 |
| 未來同帳戶同幣種多策略（延後） | 等待 OKX 官方分倉 API 成熟後重新評估範圍 | 另行確認歸因、保證金、保護單與恢復語義及維護成本；不是目前交付承諾 |

v1 先支援最少的市場／限價交易能力與必要的減倉保護，不先做插件市場、多交易所路由、分散式調度、雙 Supervisor 高可用、任意策略原地熱更新或逐筆高頻共享記憶體。這些不會改善目前 K 線策略最重要的安全論證。

以下是未來產品實作的驗收情境，按受影響模組選取最小必要單元測試，以假資料、mock 與受控故障模擬執行；不是要求每次修改重跑全部情境，也不授權全市場歷史回測、接觸真實憑證或發出 Live 請求。本次文件修訂僅檢查內容、格式、引用與合約一致性。

v1 生產驗收情境應包括：提交前後斷電；HTTP 已受理但 ACK 遺失；同一 fill 由 WS／REST 重複回報；撤單途中成交；舊 Worker 復活；連續 429；行情過期；無新訂單時插針越過兩層日損；清倉途中再次 Kill；跨日重啟；手動交易造成差異；磁碟不可寫；研究任務耗盡預算；tag 在每種建立訂單路徑均存在。

驗收不是只比最後 PnL。應檢查：沒有重複接收意圖、沒有重複記帳、沒有未經授權的增加風險、hard 不會因重啟解除、未知結果沒有被抹掉、可減倉時不會因開倉 gate 被拒，以及無法完成時有確切阻塞原因。以屬性測試和故障注入驗證上述不變量，才比寫大量鏡像實作的單元測試更有價值。

目前只保留重現研究與解釋受管交易所需的證據；反事實分支、通用版本譜系及多策略分帳不構成此次交付內容。

**15. 使用者決策與剩餘待決政策**

使用者已選擇先研究與本機模擬，再分階段進入實盤。P1～P5 的已確認原則維持；P6 複雜故障退出延後、P7 已確認 API Style＋Decimal Core、Closed Bar、warmup_bars 及 Float 搜尋評分邊界，P8 虛擬分帳及內部對沖延後。其餘待決政策不阻止不依賴它們的文件與已授權工作。

| 政策 | 已確認決策／目前方向 | 仍待討論的細節 |
|---|---|---|
| P1 Worker 與部署 | 已確認：只執行選定並經檢查的策略／依賴；Supervisor 獨佔金鑰、交易、風控及寫庫；普通獨立 Worker 僅計算並傳遞純訊號，不使用 AppContainer | 此項邊界已定案：採程序故障隔離與應用職責約束，不提供 OS 層防止惡意策略讀檔、連網或越權的保證 |
| P2 帳戶治理與接管範圍 | 已確認：OKX 專用子帳戶，禁止與手動交易混用 | 不明既有部位不自動接管；其處置與 hard／Kill 是否涵蓋全部已核實支援部位仍待定案 |
| P3 曝險與被動超限 | 已確認：帳戶有效槓桿與單幣曝險預算占比全面參數化；單幣上限 = L_max × E_risk × c_j，含在途與 UNKNOWN | 沿用數值預設 3.0x／50%，新定義下單幣上限為 1.5x 風控權益；緩衝、被動超限自動減倉及 Live 參數變更流程仍待決 |
| P4 日損與資金流 | 已確認：固定日初權益分母、Asia/Taipei 每日 00:00 切日、排除非策略外部資金流 | 具體返佣／分潤帳單分類與跨日停機資料不足的基準重建流程仍待定案 |
| P5 重新啟用與 Kill | 已確認：Soft／Hard 日損與手動 Kill 一律鎖存，當日不重設預算，僅限人工恢復 | 不自動解除、不覆蓋有效 hard／Kill；同日恢復資格、Hard 最早解除時點與 Kill 解除條件仍待定案；Kill 收斂空倉的具體操作語義維持候選 |
| P6 儲存／主機故障退出 | 已延後繞過持久化的 emergency 下單通道；使用者提出以 OKX 參數化條件停損作離線保護 | 第 12 節提出整倉市價停損候選；觸發參數、首次建倉／殘留進場單等生命週期於 Demo 階段定案，不承諾離線精確帳戶日損清倉 |
| P7 研究精度與引擎選型 | 已確認採 Jesse research API Style＋最小 Decimal Core，不依賴 Jesse 完整套件；僅 Closed Bar，不載入 1m 細部資料；warmup_bars 期間只算指標；Optuna 搜尋評分可轉 Float | 選型及上述邊界已定案；第 4 節明列預熱與正式決策分界。具體 bar 撮合假設需在實作契約與結果中明示，不擴大為盤中重播或 Float 交易計算 |
| P8 同帳戶同幣種多策略 | 已確認 v1 單合約單 Bot；延後虛擬分帳與內部對沖 | 待 OKX 官方分倉 API 成熟再評估，取消預定 v2.1／v2.2 分帳時程；現階段不預建分配機制 |

研究選型已確認，採指定週期 Closed Bar 與僅指標預熱；自有撮合與 Decimal 帳務的維護責任仍需以最小範圍承擔。固定 tag、單一交易出口、額度原子保留、UNKNOWN 與鎖存規則持續適用。

**來源**

下列為官方文件及專案自身原始碼，查核日為 2026-09-10。文件所載產品能力與本文建議的 catOS 設計分別陳述；框架效率比較屬架構判斷，不是共同基準測試結果。

1. Freqtrade， [Exchange-specific Notes](https://www.freqtrade.io/en/stable/exchanges/)，OKX 模式支援表。
2. Freqtrade， [Trade model 原始碼](https://raw.githubusercontent.com/freqtrade/freqtrade/stable/freqtrade/persistence/trade_model.py)；[Leverage](https://www.freqtrade.io/en/stable/leverage/)；[Advanced setup](https://www.freqtrade.io/en/stable/advanced-setup/)；[Strategy customization](https://www.freqtrade.io/en/stable/strategy-customization/)。
3. Jesse， [Research backtest 文件](https://docs.jesse.trade/docs/research/backtest)；[research/backtest.py](https://raw.githubusercontent.com/jesse-ai/jesse/2993e6b480dcca40cd95f6f99278deebc07bc507/jesse/research/backtest.py)。本次原始碼固定於 commit `2993e6b480dcca40cd95f6f99278deebc07bc507`，不等同已驗證的發行版。
4. Jesse， [主回測原始碼](https://raw.githubusercontent.com/jesse-ai/jesse/2993e6b480dcca40cd95f6f99278deebc07bc507/jesse/modes/backtest_mode.py)；[DB 連線條件](https://raw.githubusercontent.com/jesse-ai/jesse/2993e6b480dcca40cd95f6f99278deebc07bc507/jesse/services/db.py)。
5. Jesse， [Position 原始碼](https://raw.githubusercontent.com/jesse-ai/jesse/2993e6b480dcca40cd95f6f99278deebc07bc507/jesse/models/Position.py)；[requirements](https://raw.githubusercontent.com/jesse-ai/jesse/2993e6b480dcca40cd95f6f99278deebc07bc507/requirements.txt)。
6. NautilusTrader， [Architecture](https://nautilustrader.io/docs/latest/concepts/architecture/)。
7. NautilusTrader， [Value types](https://nautilustrader.io/docs/latest/concepts/value_types/)。
8. NautilusTrader， [Cache](https://nautilustrader.io/docs/latest/concepts/cache/)。
9. Hummingbot， [V2 architecture](https://hummingbot.org/strategies/v2-strategies/)；[Backtesting engine 原始碼](https://raw.githubusercontent.com/hummingbot/hummingbot/master/hummingbot/strategy_v2/backtesting/backtesting_engine_base.py)。
10. Hummingbot， [Client installation](https://hummingbot.org/client/installation/)。
11. OKX， [Market data／Candlesticks API](https://app.okx.com/docs-v5/en/#order-book-trading-market-data-get-candlesticks)，confirm 與行情單位。
12. Optuna， [FAQ](https://optuna.readthedocs.io/en/stable/faq.html)，記憶體儲存、並行與重現性。
13. Optuna， [Study API](https://optuna.readthedocs.io/en/stable/reference/generated/optuna.study.Study.html)，ask／tell 與搜尋介面。
14. Python， [Decimal](https://docs.python.org/3.11/library/decimal.html)，精度、捨入及 FloatOperation。
15. OKX， [API V5](https://www.okx.com/docs-v5)，委託欄位、合約單位、reduceOnly、expTime、Cancel All After；[Close positions](https://my.okx.com/docs-v5/#order-book-trading-trade-post-close-positions)，平倉及 tag 欄位。各區站點實作前需再次確認適用 schema。
16. OKX， [API best practices](https://www.okx.com/docs-v5/trick_en/)，模式、clOrdId、訂單通知與對帳。
17. OKX， [AI Builder Program Integration Guide](https://www.okx.com/help/ai-builder-program-integration-guide)，2026-08-21 發布、2026-09-02 更新；[官方整合示例](https://github.com/okx/builder-integration-demo)。
18. OKX， [API FAQ](https://www.okx.com/help/api-faq)，Demo 環境與 50004 未知結果。
19. Microsoft， [AppContainer for legacy apps](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-for-legacy-applications-)，2023-07-25 更新。
20. Apple， [Configuring the macOS App Sandbox](https://developer.apple.com/documentation/xcode/configuring-the-macos-app-sandbox)；[Protecting user data with App Sandbox](https://developer.apple.com/documentation/security/protecting-user-data-with-app-sandbox)。
21. Python， [multiprocessing](https://docs.python.org/3.11/library/multiprocessing.html)，物件交換與 pickle。
22. Python， [asyncio subprocess](https://docs.python.org/3.11/library/asyncio-subprocess.html)，管線與等待互鎖風險。
23. SQLite， [PRAGMA synchronous](https://sqlite.org/pragma.html#pragma_synchronous)；[Write-ahead logging](https://www.sqlite.org/wal.html)，耐久性與 WAL 行為。
24. SQLite， [Online Backup API](https://www.sqlite.org/backup.html)。
25. OKX， [Split Position — Introduction & FAQ](https://www.okx.com/help/split-position-introduction-and-faq)，2026-08-03 發布、2026-08-06 更新，聚合保證金與強平語義。
26. QuantConnect， [Position Sizing](https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/position-sizing)，投資組合權重與未加槓桿權重的含義；僅作分母需明確定義的對照，不替 catOS 設定政策。
27. Jesse， [Strategy 原始碼](https://github.com/jesse-ai/jesse/blob/2993e6b480dcca40cd95f6f99278deebc07bc507/jesse/strategies/Strategy.py#L1458-L1473)，一般委託價格／數量的 `dtype=float` 轉換。
28. OKX， [Place algo order](https://my.okx.com/docs-v5/en/#order-book-trading-algo-trading-post-place-algo-order)，`closeFraction`、`slTriggerPxType`、`slOrdPx`、`cxlOnClosePos`、`reduceOnly` 及 tag；實作前依適用地區及帳戶模式驗證。
29. OKX， [Strategy order types](https://www.okx.com/help/xi-strategy-order-types)，整倉 TP/SL 數量隨部位變化及觸發市價單；UI 說明不取代所選 API 路徑的 Demo 驗證。

[1]: https://www.freqtrade.io/en/stable/exchanges/
[2]: https://raw.githubusercontent.com/freqtrade/freqtrade/stable/freqtrade/persistence/trade_model.py
[3]: https://docs.jesse.trade/docs/research/backtest
[4]: https://raw.githubusercontent.com/jesse-ai/jesse/2993e6b480dcca40cd95f6f99278deebc07bc507/jesse/research/backtest.py
[5]: https://raw.githubusercontent.com/jesse-ai/jesse/2993e6b480dcca40cd95f6f99278deebc07bc507/jesse/models/Position.py
[6]: https://nautilustrader.io/docs/latest/concepts/architecture/
[7]: https://nautilustrader.io/docs/latest/concepts/value_types/
[8]: https://nautilustrader.io/docs/latest/concepts/cache/
[9]: https://hummingbot.org/strategies/v2-strategies/
[10]: https://hummingbot.org/client/installation/
[11]: https://app.okx.com/docs-v5/en/#order-book-trading-market-data-get-candlesticks
[12]: https://optuna.readthedocs.io/en/stable/faq.html
[13]: https://optuna.readthedocs.io/en/stable/reference/generated/optuna.study.Study.html
[14]: https://docs.python.org/3.11/library/decimal.html
[15]: https://www.okx.com/docs-v5
[16]: https://www.okx.com/docs-v5/trick_en/
[17]: https://www.okx.com/help/ai-builder-program-integration-guide
[18]: https://www.okx.com/help/api-faq
[19]: https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-for-legacy-applications-
[20]: https://developer.apple.com/documentation/xcode/configuring-the-macos-app-sandbox
[21]: https://docs.python.org/3.11/library/multiprocessing.html
[22]: https://docs.python.org/3.11/library/asyncio-subprocess.html
[23]: https://sqlite.org/pragma.html#pragma_synchronous
[24]: https://www.sqlite.org/backup.html
[25]: https://www.okx.com/help/split-position-introduction-and-faq
[26]: https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/position-sizing
[27]: https://github.com/jesse-ai/jesse/blob/2993e6b480dcca40cd95f6f99278deebc07bc507/jesse/strategies/Strategy.py#L1458-L1473
[28]: https://my.okx.com/docs-v5/en/#order-book-trading-algo-trading-post-place-algo-order
[29]: https://www.okx.com/help/xi-strategy-order-types
