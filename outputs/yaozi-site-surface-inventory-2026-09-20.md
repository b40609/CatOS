# YAOZI 全站 Surface Inventory（2026-09-20）

此清單按「先 Guide，再首頁，再主導航與已知入口」逐頁核對。它代表目前登入帳號可見、Guide／首頁／導航／頁內連結可發現的第一方 surface；不聲稱已枚舉未公開 private endpoint。`sitemap.xml` 實際為 404，頁面 meta 為 noindex/nofollow，因此完整性不能依 sitemap 證明。

## 1. 掃描方法與邊界

- 先讀 `/guide` 的完整目錄、公式、訊號辭典、K 線與指標說明。
- 回到 `/`，從首頁公開入口逐一核對主導航。
- 主導航後再核對頁內 tab、alias、單幣頁、帳號、legal、chat、whistle、登入流程。
- 所有研究動作只讀；未發聊天室訊息、未改 watchlist／通知／帳號、未標記已讀、未下單、未撤單。
- 動態名單／價格／hit rate／線上人數只記為 snapshot evidence，不列為規格常數。

## 2. Route / Surface inventory

| Route / Surface | 狀態 | 核心功能／欄位 | Scoring vs Observation | Parity 註記 |
|---|---|---|---|---|
| `/guide` | 已完整核對 | 產品定位、五視角、SMF、14 lights、patterns、Capital Flow、exit reasons、K 線、指標、Direction badge | 混合；章節明確標層級 | 已固化到 Guide spec |
| `/` | 已完整核對 | 市場 brief、公開 calibration、昨日 truth-vs-ours、funnel、五視角、module map、playbook | brief/reference + proof | catOS 有 dashboard，但不是完整首頁 parity |
| `/today` | 已核對 | market phase、focus、retreat、holdings、decision flow | 混合 | catOS 有 partial materialized aggregate；YAOZI private today ranking 未驗證 |
| `/narrative?tab=rotation` | 已核對 | stablecoin/market pulse、sector quadrant rotation | observation | catOS endpoint placeholder |
| `/narrative?tab=narrative` | 已核對 | narrative map、risk map、peer percentile、duration | observation / risk local score | catOS endpoint placeholder |
| `/narrative?tab=sectors` | 已核對 | sector flow、leaders、sector relation | observation | catOS endpoint placeholder |
| `/narrative?tab=news` | 已核對 | market news stream | observation | catOS endpoint placeholder |
| `/narrative` 的 Options/Gamma tab | 已核對 | options/gamma market context；Live 多於 Guide | observation | catOS endpoint placeholder |
| `/picks?view=flow` | 已核對 | FLOW score、components、蓄勢／點火 lifecycle | scoring | lifecycle 核心公式已實作；來源完整度仍不足 |
| `/picks?view=momentum` | 已核對 | SMF、14 lights、funnel、cycle | scoring | partial；private funnel/ranking 未還原 |
| `/picks?view=opportunity` | 已核對 | quality、structure、behavior、SMF、risk override | scoring | threshold reducer 已實作；quality source/formula 仍外部提供 |
| `/picks?view=risk` | 已核對 | bearish risk、evidence、cooling/hysteresis | scoring | threshold reducer 有；Live cooling 時間語意未完整實作 |
| `/picks?view=history` | 已核對 | cycle history、MFE capture、hold-to-exit result | validation/history | cycle/history 已物化；YAOZI 全視覺/統計仍 partial |
| `/picks/{base}` | 已核對代表幣頁 | hero、SMF、lights、patterns、journey、K 線、right sidebar | 混合 | catOS single-coin JSON + basic detail；完整 chart/workbench 未做 |
| `/operator/{base}` | 已核對代表幣頁 | Dealer profile、evidence axes、direction reading | observation-only | Dealer snapshot/materialization 已有；direction formula intentionally null |
| `/operator/onchain` | 已完整核對 | FLAGGED/ELEVATED/Plateau/research、chain scope、ratio/baseline | observation-only | reducer 已做；live address provider 尚未接通 |
| `/signals` | 已完整核對 | event stream、view/time filters、custom filters、event taxonomy | detection/event log | catOS signals API/dashboard partial；非完整 YAOZI event taxonomy parity |
| `/proof` | 已完整核對 | frozen snapshot、24h outcome、MFE/MAE、market & vol-matched baseline、failure cases | validation layer | catOS proof core 已有；完整公開 calibration surface partial |
| `/reflection` | 已檢查 | admin-only self-review | admin validation | 權限不可存取；未繞過，內容保持 unknown |
| `/account` | 已完整唯讀核對 | membership、notifications、watchlist、history alerts、profile、support、legal/social | member shell | catOS YAOZI 分支未實作 |
| Chat panel | 已唯讀核對 | online users、500-char composer、`$TOKEN` link behavior | communication | 未實作；研究時未送訊息 |
| Whistle drawer | 已唯讀核對 | live/watchlist/history、分類 filters、unread、mark-all-read | alert shell | 未實作；研究時未改已讀狀態 |
| `/legal/terms` | 已核對 | service positioning、usage restrictions、IP terms | legal | 規格證據，不屬分析核心 |
| `/legal/privacy` | 已核對 | account/preferences/push/device/log data、第三方 market data behavior | legal/privacy | 規格證據，不屬分析核心 |
| `/login` | 已核對 | login | auth shell | catOS YAOZI 分支未實作 |
| `/register` | 已核對 | email/nickname/password application | auth shell | catOS YAOZI 分支未實作 |
| `/forgot` | 已核對 | password reset link flow | auth shell | catOS YAOZI 分支未實作 |
| `/guide/signals` | 已核對 | 實際導向 Guide signal chapter | alias | 無獨立第二套 taxonomy |
| `/sectors` | 已核對 | redirect 到 narrative rotation | alias | 可用 redirect 規格處理 |
| `/focus/BTC` | 已核對 | redirect 到 `/picks/BTC` | alias | 可用 redirect 規格處理 |
| `sitemap.xml` | 已核對 | 404 / Next not-found | discovery | 不可作完整枚舉來源 |

## 3. 首頁公開 Funnel 與來源族群

首頁目前明示的 funnel：

1. 全市場 source layer。
2. L1 candidate pool，約 <= 200。
3. L2 multi-signal cross，約 <= 50。
4. 決策層 focus 約 20。

首頁列出的 source families 包含 24h heat、15m pump detection、OI surge、short squeeze、accumulation／ambush、market gainers、news、BBWP compression、whale holdings、funding reversal 等。這是來源／scanner 家族 inventory，不代表所有 private threshold 都已公開。

## 4. `/signals` Live event taxonomy observations

目前可見 event family 至少涵蓋：

- SMF grade／強流入／強流出／弱流出等資金狀態。
- God-tier。
- Flow 蓄勢／相關資金流事件。
- Risk imminent／large-trader turns short。
- On-chain large-trade burst、whale buy、exchange inflow/outflow、distribution alert 等。
- Market direction／market phase。
- First in pool、confirmed exit、neutral transition、still-active 等 lifecycle event。

這些是 rendered event stream 的 taxonomy evidence；不能因名稱相似就把本地 public candidate 自動宣稱為 YAOZI event hit。

## 5. Account / Membership observations

目前 Live 顯示一般會員可看核心決策／部分榜單／history／K 線；更深的 single-coin analysis、Dealer、on-chain forensics、watchlist push 等有會員層級差異。這類 entitlement 是產品 shell 規格，與 scoring formula 分開。

## 6. Chat / Alert interactions

### Chat

- 顯示線上人數／成員。
- 輸入上限 500 字。
- `$BTC` 類 token syntax 可轉成單幣 link 並自動大寫。
- 一般 URL 不會自動變成相同形式的 token link。

### Whistle

- Tabs：即時、我的觀察、歷史。
- Filters：Today、Narrative、Picks 各 view、Risk、On-chain、News 等。
- 有 unread state、只看未讀、全部已讀。
- 已見事件樣本包括結構撤離、首次入池、敘事上榜／風險地圖、A/D grade、God-tier、鏈上放量／派發、市場階段／方向、data source health。

## 7. Legal / Privacy 對複製工作的影響

- 原站定位為 market data organization / filtering，非投資建議與代操。
- Terms 明示限制未授權的大量自動抓取、轉售／再散布、規避驗證，以及把原站內容包裝為自有產品。
- 因此本分支只重建功能、資料來源、公式語義與本地分析流程，不拷貝原站 proprietary 文案、介面素材或品牌視覺。
- Privacy 表示站方不需要交易所 API key／私鑰；第三方行情請求主要由 server side 發出。

## 8. 完整性結論

目前已逐一檢查可由 Guide、首頁、主導航、頁內連結與已知 alias 發現的登入後第一方 surface。唯一明確不可讀的是 admin-only `/reflection`，已記錄 access state 而未繞過。

這個結論只表示可發現且有權限的網站 surface inventory 已掃完，不表示 private backend endpoint、server code、隱藏 admin API 或 unpublished scoring formula 已被取得。
