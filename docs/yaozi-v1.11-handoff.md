> 歷史來源：2026-09-23 從 CatOS_Yaozi 工作樹帶回，供 SMF 註解追溯；下文為來源原紀錄，不代表 Astra 本輪查證。

# v1.11 SMF 邊界與單幣口徑查證

2026-09-22 本輪直接讀取第一方登入後 rendered Guide 與 BTC 單幣頁；沒有讀取 cookies、憑證或私有 API。這是語義查證，不是新增 synchronized capture。

## 查證結果

來源：https://yaozi.yalgo.io/guide#s-grade

Guide 的 B 區間包含 -20 到 +19，C 區間包含 -49 到 -20。原站文字本身重疊，並非既有摘要單純抄錯。小數分數如何取整、顯示分數與分級使用分數是否相同也未明示。本輪沒有取得精確 score=-20 與 grade 的可信同源樣本，因此不能證明 -20 屬 B 或 C。

來源：https://yaozi.yalgo.io/picks/BTC

本輪可見頁面同時顯示 SMF B 中性、K 線方向看跌 -45.6、Dealer +4 中性且 1/3 軸有據。這些是同一頁不同欄位的觀察，非相同來源時間的保證；Dealer 還標有歷史快照。SMF 原始精確數值在本次讀取內容中未提供。不能用 K 線或 Dealer 數值代替 SMF score。

Guide 的 s-views 另明示 Opportunity 的 SMF 副指標來自該視角自身資料，不能直接代用異動板數值。後續比較必須保存視角、欄位類型、來源時間與分數版本；同幣同名徽章不足以證明同一輸入。

## 最小修改

catos/market_lifecycle.py 的 smf_grade 說明修正為本地既有分級慣例。保留 -20→B 與小數連續區間行為，避免在無證據下變更既有 reducer；不再宣稱該邊界已由原站規格唯一決定。

本輪不新增 mapping、比較分母或分數。既有 5 captures／51 rows 及 parity 73.5/88 基線不因本次文字查證加分。v1.10 禁止 caller 自我宣告等價的 gate 保持有效。

## 下一步與完成邊界

本次查證完成；結論是邊界仍不確定，而非映射已完成。下一片應以有明確數值及視角的 SMF 樣本作欄位證據，或先選取公開且無歧義的 L2 動能規則進行同口徑驗證。不要反覆採集只有 SMF 字母與 Today 排名的樣本來推算私有公式。

未 commit/push，保留 v1.5–v1.10 工作樹。沒有交易、DB schema 或 UI 行為修改。
