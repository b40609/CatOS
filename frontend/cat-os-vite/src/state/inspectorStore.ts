import { create } from 'zustand';

export type InspectorPresentationMode =
  | "bottom_dock"
  | "inline_row"
  | "master_detail"
  | "popover_peek"
  | "all_active";

export type InspectorTab = 'bot' | 'p6' | 'r1' | 'fill';

export interface InspectorStage {
  name: string;
  subtext: string;
  status: 'OK' | 'WARNING' | 'BLOCKED';
  detail: string;
}

export interface InspectorBotData {
  id: string;
  name: string;
  symbol: string;
  timeframe: string;
  strategyId: string;
  status: 'running' | 'paused';
  intentSummary: string;
  dataEvalTime: string;
  targetPosText: string;
  notional: number;
  upnl: number;
  upnlPct: number;
  p6StopPrice: string;
  p6DistPct: string;
  p6Status: 'ACTIVE' | 'UPDATING' | 'STANDBY';
  condition: string;
  riskLimit: string;
  stages: InspectorStage[];
  p6Source: string;
  p6Rounding: string;
  p6BudgetPct: string;
  riskLeverage: string;
  riskSingleAssetQuota: string;
  entryPrice: string;
  markPrice: string;
  algoOrderId?: string;
  nextEvalCountdown?: string;
  lowerExitPrice?: string;
  upperAddPrice?: string;
  costBasis?: string;
  stopLossPct?: string;
  remainingQuota?: string;
  leverageContrib?: string;
  traceLatency?: string;
}

export const INSPECTOR_BOTS: Record<string, InspectorBotData> = {
  tabby: {
    id: "tabby",
    name: "BOT-BTC-15M (Breakout v2.2)",
    symbol: "BTC-USDT-SWAP",
    timeframe: "15m",
    strategyId: "breakout_v22",
    status: "running",
    intentSummary: "續抱多單 · 突破唐奇安上軌 $64,200",
    dataEvalTime: "11:15:00 UTC+8",
    targetPosText: "+1.20 BTC",
    notional: 74535,
    upnl: 759.36,
    upnlPct: 1.03,
    p6StopPrice: "$59,500.00",
    p6DistPct: "-4.21%",
    p6Status: "ACTIVE",
    condition: "收盤價突破 Donchian Upper，MACD 柱狀體放大",
    riskLimit: "單幣預算上限 50% ($104,832) · 當前占比 35.6% (SAFE)",
    p6Source: "OKX Mark 撮合 (CEIL 向上取整)",
    p6Rounding: "向上取整 (CEIL)",
    p6BudgetPct: "35.6% / 50.0%",
    riskLeverage: "2.13x / 3.0x",
    riskSingleAssetQuota: "35.6% (上限 50%)",
    entryPrice: "$61,480.00",
    markPrice: "$62,112.80",
    algoOrderId: "algo_41cb_948201",
    nextEvalCountdown: "11:30:00 (倒數 03:22)",
    lowerExitPrice: "$61,200.00",
    upperAddPrice: "$66,000.00",
    costBasis: "$61,480.00",
    stopLossPct: "3.22%",
    remainingQuota: "$30,205 USDT (約 0.48 BTC)",
    leverageContrib: "+0.76x (總槓桿 2.13x / 3.0x)",
    traceLatency: "總延遲 48ms (OKX 28ms · 本地 20ms)",
    stages: [
      { name: "資料評估", subtext: "15m Bar #2880 · 4ms", status: "OK", detail: "已收盤 K 線基準 @ $62,112.80，杜絕盤中提前進場" },
      { name: "策略意圖", subtext: "續抱 +1.20 BTC · 11ms", status: "OK", detail: "突破唐奇安上軌，維持多頭目標 1.20 BTC" },
      { name: "風控審核", subtext: "E_risk 100% · 2ms", status: "OK", detail: "有效槓桿 2.12x < 3.0x，單幣預算占比 35.6% < 50%" },
      { name: "交易所委託", subtext: "OKX tag 驗證 · 28ms", status: "OK", detail: "Supervisor 強制注入 tag: 41cb53c54d6dABDE，已成交" },
      { name: "帳務對帳", subtext: "WAL Sync · 3ms", status: "OK", detail: "部位與 SQLite WAL 本地雙向一致，零漂移" },
    ],
  },
  calico: {
    id: "calico",
    name: "BOT-ETH-1H (Trend Follow v1.4)",
    symbol: "ETH-USDT-SWAP",
    timeframe: "1h",
    strategyId: "trend_follow",
    status: "running",
    intentSummary: "目標 14.30 ETH · 委託待對帳 (UNKNOWN 鎖存)",
    dataEvalTime: "11:00:00 UTC+8",
    targetPosText: "+14.30 ETH",
    notional: 45515,
    upnl: 695.25,
    upnlPct: 1.55,
    p6StopPrice: "$3,210.00",
    p6DistPct: "-4.79%",
    p6Status: "ACTIVE",
    condition: "1H 均線多頭排列，收盤確認站上 EMA20",
    riskLimit: "在途 UNKNOWN 委託額度鎖存，禁止盲目重送",
    p6Source: "OKX Mark 撮合 (CEIL 向上取整)",
    p6Rounding: "向上取整 (CEIL)",
    p6BudgetPct: "23.0% / 50.0%",
    riskLeverage: "2.13x / 3.0x",
    riskSingleAssetQuota: "23.0% (上限 50%)",
    entryPrice: "$3,320.00",
    markPrice: "$3,371.50",
    algoOrderId: "algo_41cb_837192",
    nextEvalCountdown: "12:00:00 (倒數 33:22)",
    lowerExitPrice: "$3,210.00",
    upperAddPrice: "$3,520.00",
    costBasis: "$3,320.00",
    stopLossPct: "3.31%",
    remainingQuota: "$59,317 USDT (約 17.6 ETH)",
    leverageContrib: "+0.46x (總槓桿 2.13x / 3.0x)",
    traceLatency: "總延遲 82ms (OKX UNKNOWN · 本地 18ms)",
    stages: [
      { name: "資料評估", subtext: "1h Closed Bar", status: "OK", detail: "11:00 收盤確認均線突破" },
      { name: "策略意圖", subtext: "增倉至 14.30 ETH", status: "OK", detail: "發出加倉 0.80 ETH 意圖" },
      { name: "風控審核", subtext: "額度保留鎖存", status: "WARNING", detail: "存在 UNKNOWN 在途單，凍結保證金 $674.25" },
      { name: "交易所委託", subtext: "cat_calico_unknown_01", status: "WARNING", detail: "發送委託後逾時，等待 Supervisor 對帳終態" },
      { name: "帳務對帳", subtext: "待對帳終態", status: "BLOCKED", detail: "未取得交易所確認前，嚴格禁止再次增倉" },
    ],
  },
  mochi: {
    id: "mochi",
    name: "BOT-SOL-5M (Volatility Grid v3.0)",
    symbol: "SOL-USDT-SWAP",
    timeframe: "5m",
    strategyId: "grid_mm",
    status: "running",
    intentSummary: "保護更新待確認 · 暫停新增曝險",
    dataEvalTime: "11:15:00 UTC+8",
    targetPosText: "+135.00 SOL",
    notional: 20574,
    upnl: 567.00,
    upnlPct: 2.83,
    p6StopPrice: "更新中 (待確認)",
    p6DistPct: "-6.82%",
    p6Status: "UPDATING",
    condition: "網格區間高拋低吸，ATR 波動度正常",
    riskLimit: "P6 災難停損更新中，未生效前禁止增倉",
    p6Source: "OKX Mark (待確認)",
    p6Rounding: "向上取整 (CEIL)",
    p6BudgetPct: "12.4% / 50.0%",
    riskLeverage: "2.13x / 3.0x",
    riskSingleAssetQuota: "12.4% (上限 50%)",
    entryPrice: "$148.20",
    markPrice: "$152.40",
    algoOrderId: "algo_41cb_625103 (更新中)",
    nextEvalCountdown: "11:20:00 (倒數 01:15)",
    lowerExitPrice: "$142.00",
    upperAddPrice: "$162.00",
    costBasis: "$148.20",
    stopLossPct: "4.18%",
    remainingQuota: "$84,258 USDT (約 552 SOL)",
    leverageContrib: "+0.21x (總槓桿 2.13x / 3.0x)",
    traceLatency: "總延遲 39ms (OKX 22ms · 本地 17ms)",
    stages: [
      { name: "資料評估", subtext: "5m 實時 Bar", status: "OK", detail: "價格波動觸及格線" },
      { name: "策略意圖", subtext: "推移防線至 $142.00", status: "OK", detail: "向上調整停損錨定價" },
      { name: "風控審核", subtext: "保護防線優先", status: "WARNING", detail: "必須先完成 P6 更新終態" },
      { name: "交易所委託", subtext: "更新請求在途", status: "WARNING", detail: "向 OKX 發送 algo_stop 更新，等待 ACK" },
      { name: "帳務對帳", subtext: "待更新終態", status: "WARNING", detail: "生效價暫標為未知，覆蓋數量待確認" },
    ],
  },
  shiro: {
    id: "shiro",
    name: "BOT-ARB-1H (Mean Reversion v1.1)",
    symbol: "ARB-USDT-SWAP",
    timeframe: "1h",
    strategyId: "pairs",
    status: "paused",
    intentSummary: "已手動暫停 · 空倉",
    dataEvalTime: "08:00:00 UTC+8",
    targetPosText: "0.00 (空倉)",
    notional: 0,
    upnl: 0,
    upnlPct: 0,
    p6StopPrice: "未啟用 (空倉)",
    p6DistPct: "--",
    p6Status: "STANDBY",
    condition: "統計套利價差偏離 > 2.0 倍標準差時介入",
    riskLimit: "手動暫停狀態，無持倉曝險",
    p6Source: "--",
    p6Rounding: "--",
    p6BudgetPct: "0.0% / 50.0%",
    riskLeverage: "2.13x / 3.0x",
    riskSingleAssetQuota: "0.0% (上限 50%)",
    entryPrice: "—",
    markPrice: "$0.5420",
    algoOrderId: "—",
    nextEvalCountdown: "手動暫停中",
    lowerExitPrice: "—",
    upperAddPrice: "—",
    costBasis: "—",
    stopLossPct: "0.00%",
    remainingQuota: "$104,832 USDT (100% 額度可用)",
    leverageContrib: "+0.00x (零持倉)",
    traceLatency: "零延遲 (離線)",
    stages: [
      { name: "資料評估", subtext: "1h 定期檢查", status: "OK", detail: "未達統計套利偏離門檻" },
      { name: "策略意圖", subtext: "手動暫停", status: "BLOCKED", detail: "交易員手動停用 Worker" },
      { name: "風控審核", subtext: "允許合法減倉", status: "OK", detail: "零部位狀態" },
      { name: "交易所委託", subtext: "無委託", status: "OK", detail: "當前無在途掛單" },
      { name: "帳務對帳", subtext: "空倉", status: "OK", detail: "零部位狀態對帳完成" },
    ],
  },
};

interface InspectorState {
  // 原有呈現模式
  presentationMode: InspectorPresentationMode;
  setPresentationMode: (mode: InspectorPresentationMode) => void;
  selectedBotId: string;
  selectBot: (id: string) => void;
  expandedInlineBotIds: string[];
  toggleInlineExpand: (id: string) => void;

  // 原有 Console 底部 Dock
  isBottomDockOpen: boolean;
  toggleBottomDock: (open?: boolean) => void;
  isBottomDockMaximized: boolean;
  setBottomDockMaximized: (max: boolean) => void;
  bottomDockTab: "intent" | "stages" | "p6" | "logs" | "risk";
  setBottomDockTab: (tab: "intent" | "stages" | "p6" | "logs" | "risk") => void;

  // 新增：右側折疊式檢驗抽屜 (Inspector Drawer)
  isOpen: boolean;
  activeTab: InspectorTab;
  selectedPositionId: string | null;
  selectedEventId: string | null;
  width: number;
  isPinned: boolean;

  toggleOpen: () => void;
  setOpen: (open: boolean) => void;
  setActiveTab: (tab: InspectorTab) => void;
  openWithBot: (botId: string) => void;
  openWithP6: (positionId?: string) => void;
  openWithR1: () => void;
  openWithFill: () => void;
  openWithEvent: (eventId: string) => void;
  setWidth: (width: number) => void;
  togglePin: () => void;
}

export const useInspectorStore = create<InspectorState>((set) => ({
  presentationMode: "bottom_dock",
  setPresentationMode: (mode) => set({ presentationMode: mode }),
  selectedBotId: "calico",
  selectBot: (id) => set({ selectedBotId: id }),
  expandedInlineBotIds: [],
  toggleInlineExpand: (id) =>
    set((state) => ({
      expandedInlineBotIds: state.expandedInlineBotIds.includes(id)
        ? state.expandedInlineBotIds.filter((x) => x !== id)
        : [...state.expandedInlineBotIds, id],
    })),

  isBottomDockOpen: false,
  toggleBottomDock: (open) =>
    set((state) => ({ isBottomDockOpen: open !== undefined ? open : !state.isBottomDockOpen })),
  isBottomDockMaximized: false,
  setBottomDockMaximized: (max) => set({ isBottomDockMaximized: max }),
  bottomDockTab: "stages",
  setBottomDockTab: (tab) => set({ bottomDockTab: tab }),

  isOpen: false,
  activeTab: 'bot',
  selectedPositionId: 'pos-1',
  selectedEventId: null,
  width: 380,
  isPinned: false,

  toggleOpen: () => set((s) => ({ isOpen: !s.isOpen })),
  setOpen: (isOpen) => set({ isOpen }),
  setActiveTab: (activeTab) => set({ activeTab, isOpen: true }),

  openWithBot: (botId) => set({ activeTab: 'bot', selectedBotId: botId, isOpen: true }),
  openWithP6: (positionId) => set({
    activeTab: 'p6',
    selectedPositionId: positionId || 'pos-1',
    isOpen: true,
  }),
  openWithR1: () => set({ activeTab: 'r1', isOpen: true }),
  openWithFill: () => set({ activeTab: 'fill', isOpen: true }),
  openWithEvent: (eventId) => set({ selectedEventId: eventId, isOpen: true }),
  setWidth: (width) => set({ width }),
  togglePin: () => set((s) => ({ isPinned: !s.isPinned })),
}));
