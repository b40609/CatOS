# S6 開發交接：合成情境轉接

## 正式驗收結果（2026-09-19 使用者回報）

S6 已由 Sol 驗收並提交：`ecc897e3afc19ab03527a4e1529f060b83f21df7`，`feat(lots): add S6 synthetic scenario adapter`。

- S6 34/34、S4 42/42、S5 39/39，合計 115/115，0 failure／error／skip。
- Python 3.14.6、SQLite 3.50.4；`py_compile`、`git diff --check`、staged check 通過，未執行全量測試。
- Schema、Risk、P6、execution／protection／交易路徑未變。
- 回報時 `main` 相對 `origin/main` ahead 6。`docs/lot-snapshot-handoff.md` 的 S5 驗收紀錄及 market／yaozi 工作仍未提交，全部未納入 S6 commit。yaoI／yaozi 為使用者同步開發的獨立功能，不併入量化平台工作。

本節依使用者回報補記，Astra 未重跑測試、編譯或查 Git；此文件更新發生於上述 commit 之後。下方保留原開發內容與驗收設計，歷史待驗收敘述不覆蓋本節結果。下一片範圍評估見 [S7 本機合成情境報告](../outputs/catos-s7-scenario-report-assessment.md)，尚未開始 S7 程式實作。

原開發狀態：依 [正式規格](../outputs/catos-s6-scenario-spec.md)完成程式與測試編寫，交由 Sol 獨立驗收。Astra 開發階段只做補丁與靜態閱讀，未執行測試、編譯、Git或資料庫操作。

## 變更與語義

- `catos/lot_scenario.py`：frozen evidence／result、ScenarioInputError、capture結構／排序／hash／Lot責任校驗、明示scenario attestation，以及純S4轉接；不讀DB、時鐘、網路或環境變數。
- `catos/lot_exposure.py`：request／report預設OBSERVED；新增synthetic buckets與分類，SYNTHETIC_SCENARIO只接受SYNTHETIC_LEDGER／UNTERMINATED，OBSERVED拒絕synthetic來源。未修改既有Gross／Net／CLOSE不預扣算術。
- `tests/test_lot_scenario.py`：34個測試方法；`tests/test_lot_exposure.py`新增6個方法，原36個保留。數量為靜態編寫清單，非執行結果。
- 更新README與WORK_PLAN。未修改S5 hash／capture實作、Schema7、Risk、execution、protection或交易路徑。其他草稿與market-intel檔案不在交付範圍。

capture驗證重用S5 streaming hash及S4 Lot驗證，另檢查Bot水位、pending身份／精度／數量一致、Lot方向及unresolved覆蓋；hash不構成外部來源真實性證明。不替輸入重新排序、不補造pending、不覆寫remaining quantity。數量一致性只做驗證，不重新產生餘量。OPEN resolved沿用原始輸入限制；CLOSE可有派生精度。

scenario必須精確綁定capture identity、scope與完整contract；cut不得等於capture_id。physical必須明示，mark可全缺席；時間原樣送入S4。unmanaged使pending incomplete；synthetic模式不可用時synthetic buckets為None，OBSERVED沒有synthetic來源時保持精確0。has_unknown仍只計EXCHANGE／UNKNOWN。

S4運算拋出的ExposureInputError不被S6吞掉或降級；若合法轉接觸發，需作實作問題處理。S6沒有accepted／ready／authorized等裁決。

## 驗收對照

| 規格群 | 測試覆蓋 |
|---|---|
| A01–A06 | 空情境、錯capture綁定、非法cut、逐欄scope／contract、原始時間與metadata轉接 |
| B01–B07 | 首次成交前OPEN、真實Journal部分／全成交未terminal、terminal移除、多Bot多方向；CLOSE含long／short |
| B08–B09 | S4新增回歸：OBSERVED拒synthetic、synthetic拒HELD／EXCHANGE override及非法配對 |
| C01–C07 | unmanaged降級不造假責任、重疊／不存在／resolved／重複拒絕、完整managed、舊hash、集合排序／重複 |
| D01–D07 | physical不推導、不完整／非法physical、精確MATCH／MISMATCH、mark缺席／過期／future及metadata |
| E01–E06 | buckets／總量／physical upper／OPEN-only Gross upper、UNKNOWN舊語義、不完整與各來源stale |
| F01–F04 | Decimal等價、低精度context、小步長／大mark／派生CLOSE、frozen不變、I/O阻斷案例 |
| 額外 | 64／4096合法上限與65／4097拒絕、偽造數量／水位／方向、S4錯誤傳遞 |
| F05–F06 | 由Sol執行S4／S5必要回歸與Git範圍／格式檢查，不算成新單元測試 |

## Sol 驗證順序

```text
<python> -B -m unittest discover -s tests -p "test_lot_scenario.py" -v
<python> -B -m unittest discover -s tests -p "test_lot_exposure.py" -v
<python> -B -m unittest discover -s tests -p "test_lot_snapshot.py" -v
```

預計34＋42＋39共115個測試方法，實際數量以runner為準。依失敗與受影響範圍再擴充，不自行宣稱全量通過。確認Windows臨時DB生命週期、Decimal邊界、S4原36個observed案例與S5原39個案例均維持，記錄Python／SQLite版本、failure／error／skip及diff/staged結果。不得把其他未提交工作納入S6。

S6驗收後再評估下一片；仍不延伸為真實帳戶physical／mark的可信截點、交易所訂單狀態或Gross限制。上下文交接可用本文件配合WORK_PLAN與正式規格。
