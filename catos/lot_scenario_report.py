"""Pure offline presentation of validated synthetic scenario observations."""

from decimal import Decimal
from html import escape

from catos import lot_scenario
from catos.lot_scenario import SyntheticScenarioEvidence
from catos.lot_snapshot import LocalLotCapture


_REASONS = {
    "lot_stale": "Lot 來源不在有效期內",
    "physical_stale": "合成實體來源不在有效期內",
    "mark_stale": "合成 mark 不在有效期內",
    "pending_stale": "未決責任來源不在有效期內",
    "future_observation": "存在晚於評估時間的取樣",
    "physical_unknown": "合成實體數量未提供",
    "physical_unverified": "合成實體完整性聲明未成立",
    "lot_inventory_incomplete": "Lot 集合不完整",
    "position_cut_mismatch": "Lot 與合成實體截點不一致",
    "mark_missing": "合成 mark 未提供",
    "pending_missing": "未決責任集合未提供",
    "pending_lot_link_incomplete": "未決責任與 Lot 關聯不足",
    "pending_incomplete": "未決責任集合不完整",
    "pending_cut_mismatch": "未決責任與部位截點不一致",
    "pending_quantity_unknown": "存在數量未知的未決責任",
    "pending_effect_unknown": "存在效果未分類的未決責任",
}
_STATUS = {"MATCH": "合成情境數量相符", "MISMATCH": "合成情境數量不符",
           "UNAVAILABLE": "無法比較"}
_QUANTITIES = (
    ("observed_long_qty", "已觀測多倉數量", "張"),
    ("observed_short_qty", "已觀測空倉數量", "張"),
    ("observed_gross_qty", "已觀測 Gross 數量", "張"),
    ("observed_net_qty", "已觀測淨數量（含正負號）", "張"),
    ("physical_qty", "合成實體淨數量（含正負號）", "張"),
    ("delta_qty", "數量差額（Lot Net−合成實體）", "張"),
    ("observed_gross_notional", "已觀測 Gross 名目價值", "USDT"),
    ("observed_signed_net_notional", "已觀測淨名目價值（含正負號）", "USDT"),
    ("physical_notional", "合成實體名目價值（絕對值）", "USDT"),
)
_PENDING = (
    ("pending_buy_qty", "未決責任買入總量", "張"),
    ("pending_sell_qty", "未決責任賣出總量", "張"),
    ("synthetic_buy_qty", "合成帳本未決買入量", "張"),
    ("synthetic_sell_qty", "合成帳本未決賣出量", "張"),
    ("held_buy_qty", "HELD 分類買入量", "張"),
    ("held_sell_qty", "HELD 分類賣出量", "張"),
    ("exchange_buy_qty", "EXCHANGE 分類買入量", "張"),
    ("exchange_sell_qty", "EXCHANGE 分類賣出量", "張"),
    ("physical_scenario_upper_qty", "合成實體情境數量上界", "張"),
    ("virtual_gross_scenario_upper_qty", "虛擬 Gross 情境數量上界", "張"),
    ("unresolved_lot_count", "未決 Lot 數", "個"),
    ("pending_unique_count", "去重後責任數", "筆"),
    ("pending_duplicate_count", "重複責任數", "筆"),
)
_FLAGS = (
    ("lot_complete", "Lot 集合完整", "—"),
    ("lot_fresh", "Lot 來源在有效期內", "—"),
    ("physical_fresh", "合成實體來源在有效期內", "—"),
    ("physical_verified", "合成實體完整性聲明成立", "—"),
    ("mark_fresh", "合成 mark 在有效期內", "—"),
    ("pending_complete", "未決責任集合完整", "—"),
    ("pending_fresh", "未決責任來源在有效期內", "—"),
    ("has_unknown", "所見 EXCHANGE／UNKNOWN 責任", "—"),
)
_STYLE = """
:root { color-scheme: light; font-family: system-ui, sans-serif; color: #172b3a; background: #edf2f5; }
* { box-sizing: border-box; }
body { margin: 0; padding: 24px; }
main { max-width: 1080px; margin: auto; }
h1 { font-size: 1.7rem; } h2 { font-size: 1.2rem; }
p, li { line-height: 1.65; overflow-wrap: anywhere; }
.source { border-left: 5px solid #966100; background: #fff4d8; padding: 16px; }
section { background: white; border: 1px solid #cbd7df; border-radius: 8px; padding: 18px; margin-top: 18px; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; }
th, td { padding: 10px 8px; border-bottom: 1px solid #dce4ea; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
thead th { background: #f1f5f8; } th:first-child { width: 44%; } th:last-child { width: 18%; }
tbody th { font-weight: 500; } code { display: block; font-size: .78rem; color: #465c6b; overflow-wrap: anywhere; }
td { font-variant-numeric: tabular-nums; } .note { color: #425766; }
@media (max-width: 600px) { body { padding: 10px; } section { padding: 10px; } th, td { padding: 8px 5px; } }
"""


def _format(value, missing="不可用"):
    if value is None:
        return missing
    if isinstance(value, bool):
        return "是（true）" if value else "否（false）"
    if isinstance(value, Decimal):
        return format(value, "f") if value else "0"
    return str(value)


def _row(key, label, value, unit="—", missing="不可用"):
    # Keys and labels are code constants; all text is escaped at this boundary.
    return (f'<tr data-field="{escape(key, quote=True)}"><th scope="row">'
            f'{escape(label, quote=True)}<code>{escape(key, quote=True)}</code></th>'
            f'<td>{escape(_format(value, missing), quote=True)}</td>'
            f'<td>{escape(unit, quote=True)}</td></tr>')


def _section(title, rows, note=""):
    return (f'<section><h2>{escape(title, quote=True)}</h2>'
            f'<p class="note">{escape(note, quote=True)}</p>'
            '<div class="table-wrap"><table><thead><tr><th scope="col">欄位</th>'
            '<th scope="col">內容</th><th scope="col">單位</th></tr></thead><tbody>'
            + "".join(rows) + '</tbody></table></div></section>')


def _reason_section(reasons):
    items = "".join(
        '<li><code>' + escape(code, quote=True) + '</code>'
        + escape(_REASONS.get(code, "未收錄原因"), quote=True) + '</li>' for code in reasons)
    return ('<section id="reasons"><h2>降級原因</h2>'
            + ('<ul>' + items + '</ul>' if reasons else '<p>無降級原因</p>')
            + '</section>')


def render_synthetic_scenario_report(*, capture: LocalLotCapture,
                                     scenario: SyntheticScenarioEvidence,
                                     now_ms: int) -> str:
    """Validate once through S6, then return HTML without I/O or new arithmetic."""
    observation = lot_scenario.observe_synthetic_scenario(
        capture=capture, scenario=scenario, now_ms=now_ms)
    return _render(capture, scenario, observation)


def render_synthetic_scenario_report_v2(*, capture, scenario, now_ms):
    observation = lot_scenario.observe_synthetic_scenario_v2(capture=capture, scenario=scenario, now_ms=now_ms)
    return _render(capture, scenario, observation)


def render_synthetic_scenario_report_v3(*, capture, scenario, now_ms):
    observation = lot_scenario.observe_synthetic_scenario_v3(capture=capture, scenario=scenario, now_ms=now_ms)
    return _render(capture, scenario, observation)


def _fee_section(quality):
    rows = []
    for item in quality:
        status = ("費用涵蓋範圍未驗證／fee_coverage_unverified" if item.coverage == "UNVERIFIED" else
                  "費用已完整" if item.fee_complete else "費用不完整／fee_incomplete")
        for name, label, value in (
            ("lot_id", "Lot", item.lot_id), ("bot_id", "Bot", item.bot_id),
            ("revision", "版本", item.revision), ("coverage", "費用涵蓋範圍", item.coverage),
            ("known_fee_subtotal", "已知費用小計，非全部費用", item.known_fee_subtotal),
            ("fee_unknown_fill_count", "缺費成交筆數", item.fee_unknown_fill_count),
            ("fee_complete", "費用完整性", item.fee_complete), ("status", "費用品質", status)):
            rows.append(_row("fee_quality." + name, label, value, "USDT" if name == "known_fee_subtotal" else "—"))
    return _section("費用品質", rows,
        "funding 未知；費用已完整仍不代表完整淨損益。" if quality else "無 Lot 費用資料")


def _render(capture, scenario, observation):
    report = observation.report
    identity = [
        _row("observation.evidence_kind", "外層合成證據種類", observation.evidence_kind),
        _row("evidence_kind", "報告合成證據種類", report.evidence_kind),
        _row("capture.source", "快照來源", capture.source),
        _row("scenario.source", "情境來源", scenario.source),
        _row("scope.account_ref", "本機帳戶代稱", report.scope.account_ref),
        _row("scope.environment", "環境", report.scope.environment),
        _row("contract.inst_id", "合約", report.contract.inst_id),
        _row("contract.base_per_contract", "每張標的資產數量", report.contract.base_per_contract, "標的資產／張"),
        _row("contract.tick_size", "價格跳動單位", report.contract.tick_size, "USDT／標的資產"),
        _row("contract.lot_size", "張數步長", report.contract.lot_size, "張"),
        _row("contract.min_size", "最小張數", report.contract.min_size, "張"),
        _row("source_capture_id", "來源 capture 身份", observation.source_capture_id),
        _row("scenario_cut_id", "明示合成情境截點", observation.scenario_cut_id),
    ]
    if type(observation) is lot_scenario.SyntheticScenarioObservationV3:
        identity.append(_row("capture.version", "資料版本",
                             "capture v3／schema9；費用為此截點的有效小計"))
    for key, label in (("lot_cut_id", "Lot 截點"), ("physical_cut_id", "合成實體截點"),
                       ("pending_cut_id", "未決責任截點"), ("quote_id", "合成 mark 報價身份")):
        identity.append(_row(key, label, getattr(report, key), missing="未提供"))
    times = [_row("now_ms", "評估時間", report.now_ms, "Unix epoch 毫秒")]
    for key, label, value in (
        ("capture.observed_at_ms", "Lot／未決責任取樣時間", capture.observed_at_ms),
        ("capture.valid_until_ms", "Lot／未決責任有效截止時間", capture.valid_until_ms),
        ("scenario.physical_observed_at_ms", "合成實體取樣時間", scenario.physical_observed_at_ms),
        ("scenario.physical_valid_until_ms", "合成實體有效截止時間", scenario.physical_valid_until_ms),
        ("scenario.mark_observed_at_ms", "合成 mark 取樣時間", scenario.mark_observed_at_ms),
        ("scenario.mark_valid_until_ms", "合成 mark 有效截止時間", scenario.mark_valid_until_ms),
    ):
        times.append(_row(key, label, value, "Unix epoch 毫秒", "未提供"))
    times.append(_row("scenario.mark", "合成 mark 原始輸入", scenario.mark, "USDT／標的資產", "未提供"))
    status = _STATUS.get(report.comparison_status, "未識別比較狀態") + "（" + report.comparison_status + "）"
    quantities = [_row("comparison_status", "數量比較", status)]
    quantities.extend(_row(key, label, getattr(report, key), unit) for key, label, unit in _QUANTITIES)
    pending = [_row(key, label, getattr(report, key), unit) for key, label, unit in _PENDING]
    flags = [_row(key, label, getattr(report, key), unit) for key, label, unit in _FLAGS]
    sections = [
        _section("來源與身份", identity, "capture hash 只代表內容身份，不證明外部來源真實性。"),
        _section("時間與合成 mark", times, "有效期為取樣時間 <= 評估時間 < 有效截止時間；旗標沿用 S4 結果。"),
        _section("數量與估值", quantities, "數字有值不代表來源新鮮，請同時閱讀品質旗標與降級原因。"),
        _section("未決責任與情境上界", pending,
                 "責任來源為 SYNTHETIC_LEDGER／UNTERMINATED。HELD／EXCHANGE 分項為零只代表本合成輸入沒有該分類，"
                 "不能證明交易所沒有委託。上界是合成情境量，並非額度或限額；未成交 CLOSE 不預扣目前 Gross。"
                 "零剩餘但未 terminal 的責任仍可能計入筆數；未決 Lot 數只計現有 Lot，不包含尚未形成 Lot 的全部 OPEN 責任。"),
        _section("品質旗標", flags,
                 "physical_verified 沿用 scenario.physical_complete 映射，非交易所查證。"
                 "mark 缺席時 mark_fresh 亦為 false。has_unknown=false 不表示無未決責任或完整對帳。"),
        _reason_section(report.reasons),
    ]
    if isinstance(observation, lot_scenario.SyntheticScenarioObservationV2):
        sections.append(_fee_section(observation.fee_quality))
    return ('<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>catOS 本機合成情境報告</title><style>' + _STYLE + '</style></head><body><main>'
            '<h1>catOS 本機合成情境報告</h1><p class="source">本機合成情境／SYNTHETIC_SCENARIO。'
            '本機合成情境；不是交易所證據或交易許可。MATCH 僅表示本次合成情境數量相符。</p>'
            + "".join(sections) + '</main></body></html>')
