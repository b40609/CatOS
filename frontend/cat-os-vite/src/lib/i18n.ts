import { useCatStore, type Language } from "@/state/catStore";

export const DICT = {
  "zh-TW": {
    // 頂部導航
    workspace: "量化工作區",
    workspace_trail: "工作區",
    system_overview: "系統總覽",
    engine_online: "引擎連線中",
    all_systems_operational: "所有系統運作正常",
    simulated_data: "模擬市場數據",

    // 4-KPI Strip
    total_equity: "帳戶總權益",
    vs_yesterday: "較昨日",
    today_pnl: "今日損益",
    active_bots: "運行機器人",
    running: "運行中",
    paused: "已停止",
    max_drawdown: "歷史最大回撤",
    ytd: "今年以來",

    // Chart Panel
    equity_and_drawdown: "權益與回撤",
    this_period: "本週期",
    equity: "權益",
    drawdown: "回撤",
    portfolio_performance: "投資組合表現",
    updated_just_now: "剛剛更新",

    // Asset Allocation
    asset_allocation: "資產配置",
    assets_count: "種資產",
    total_assets: "總資產",
    btc_spot: "BTC 現貨",
    eth_spot: "ETH 現貨",
    sol_perp: "SOL 永續",
    arb_margin: "套利保證金",
    usdt_reserve: "USDT 儲備",

    // Open Positions Table
    open_positions: "當前持倉",
    filter_all: "全部",
    filter_long: "做多",
    filter_short: "做空",
    th_symbol: "交易標的",
    th_side: "方向",
    th_size: "倉位數量",
    th_entry: "開倉均價",
    th_mark: "標記價格",
    th_pnl: "未實現損益",
    perpetual: "永續合約",
    side_long: "▲ 做多",
    side_short: "▼ 做空",
    positions_summary: "筆當前持倉 · USDT 結算",
    manage_bots: "管理機器人",

    // Recent Fills
    recent_fills: "即時成交流水",
    live: "即時",
    buy: "買入",
    sell: "賣出",

    // Language Selector
    lang_name: "繁體中文",
    lang_zh: "繁體中文 (Traditional Chinese)",
    lang_en: "English (英文)",
  },
  "en": {
    // Top Nav
    workspace: "Quant Workspace",
    workspace_trail: "Workspace",
    system_overview: "Dashboard",
    engine_online: "Engine online",
    all_systems_operational: "All systems operational",
    simulated_data: "Simulated market data",

    // 4-KPI Strip
    total_equity: "Total equity",
    vs_yesterday: "vs. yesterday",
    today_pnl: "Today's PnL",
    active_bots: "Active bots",
    running: "running",
    paused: "paused",
    max_drawdown: "Max drawdown",
    ytd: "year to date",

    // Chart Panel
    equity_and_drawdown: "Equity & Drawdown",
    this_period: "this period",
    equity: "Equity",
    drawdown: "Drawdown",
    portfolio_performance: "Portfolio performance",
    updated_just_now: "Updated just now",

    // Asset Allocation
    asset_allocation: "Asset Allocation",
    assets_count: "assets",
    total_assets: "Total assets",
    btc_spot: "BTC Spot",
    eth_spot: "ETH Spot",
    sol_perp: "SOL Perp",
    arb_margin: "Arbitrage Margin",
    usdt_reserve: "USDT Reserve",

    // Open Positions Table
    open_positions: "Open Positions",
    filter_all: "All",
    filter_long: "Long",
    filter_short: "Short",
    th_symbol: "Symbol",
    th_side: "Side",
    th_size: "Size",
    th_entry: "Entry Price",
    th_mark: "Mark Price",
    th_pnl: "Unrealized PnL",
    perpetual: "Perpetual",
    side_long: "▲ LONG",
    side_short: "▼ SHORT",
    positions_summary: "open positions · USDT settled",
    manage_bots: "Manage bots",

    // Recent Fills
    recent_fills: "Recent Fills",
    live: "LIVE",
    buy: "BUY",
    sell: "SELL",

    // Language Selector
    lang_name: "English",
    lang_zh: "繁體中文 (Traditional Chinese)",
    lang_en: "English (US)",
  },
} as const;

export type TranslationKey = keyof typeof DICT["zh-TW"];

export function useI18n() {
  const language = useCatStore((s) => s.language);
  const setLanguage = useCatStore((s) => s.setLanguage);

  const t = (key: TranslationKey): string => {
    return DICT[language]?.[key] ?? DICT["zh-TW"][key] ?? key;
  };

  return { language, setLanguage, t };
}
export type { Language };
