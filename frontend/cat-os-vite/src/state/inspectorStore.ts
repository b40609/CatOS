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
}

export const INSPECTOR_BOTS: Record<string, InspectorBotData> = {
  tabby: {
    id: "tabby",
    name: "Tabby 獵貓動能",
    symbol: "BTC-USDT-SWAP",
    timeframe: "15m",
    strategyId: "dcm_trend_v1",
    status: "running",
    intentSummary: "續抱多單 · 突破唐奇安上軌 $64,200",
    dataEvalTime: "11:15:00 UTC+8",
    targetPosText: "+0.20 BTC",
    notional: 12840,
    upnl: 342.5,
    upnlPct: 2.74,
    p6StopPrice: "$59,500.00",
    p6DistPct: "-4.24%",
    p6Status: "ACTIVE",
    condition: "收盤價突破 Donchian Upper，MACD 柱狀體放大",
    riskLimit: "單幣預算上限 50% · 當前占比 28.2% (SAFE)",
    p6Source: "OKX Mark 撮合 (CEIL 向上取整)",
    p6Rounding: "向上取整 (CEIL)",
    p6BudgetPct: "28.2% / 50.0%",
    riskLeverage: "1.46x / 3.0x",
    riskSingleAssetQuota: "28.2% (上限 50%)",
    entryPrice: "$62,150.00",
    markPrice: "$64,210.00",
    stages: [
      { name: "資料評估", subtext: "15m Closed Bar", status: "OK", detail: "已收盤 K 線撮合，杜絕盤中提前進場" },
      { name: "策略意圖", subtext: "多頭強度 +0.78", status: "OK", detail: "訊號維持做多，目標持倉 0.20 BTC" },
      { name: "風控審核", subtext: "E_risk 100% 通過", status: "OK", detail: "有效槓桿 1.46x < 3.0x，無超限" },
      { name: "交易所委託", subtext: "OKX SWAP net_mode", status: "OK", detail: "已成交，Supervisor 強制注入專屬返佣 tag" },
      { name: "帳務對帳", subtext: "完全吻合", status: "OK", detail: "持倉與本機 SQLite WAL 雙向一致" },
    ],
  },
  calico: {
    id: "calico",
    name: "Calico 三花夜視",
    symbol: "ETH-USDT-SWAP",
    timeframe: "1H",
    strategyId: "night_mean_revert_v2",
    status: "running",
    intentSummary: "目標 3 ETH · 委託待對帳 (UNKNOWN 鎖存)",
    dataEvalTime: "11:00:00 UTC+8",
    targetPosText: "+3.00 ETH",
    notional: 10350,
    upnl: -48.2,
    upnlPct: -0.46,
    p6StopPrice: "$3,210.00",
    p6DistPct: "-4.89%",
    p6Status: "ACTIVE",
    condition: "RSI 超賣 28.4，夜間流動性回踩 EMA20",
    riskLimit: "在途 UNKNOWN 委託額度保留，禁止盲目重送",
    p6Source: "OKX Mark 撮合 (CEIL 向上取整)",
    p6Rounding: "向上取整 (CEIL)",
    p6BudgetPct: "27.6% / 50.0%",
    riskLeverage: "1.46x / 3.0x",
    riskSingleAssetQuota: "27.6% (上限 50%)",
    entryPrice: "$3,450.20",
    markPrice: "$3,434.10",
    stages: [
      { name: "資料評估", subtext: "1H Closed Bar", status: "OK", detail: "11:00 收盤確認站上均線" },
      { name: "策略意圖", subtext: "增倉至 3.0 ETH", status: "OK", detail: "發出加倉 1.2 ETH 意圖" },
      { name: "風控審核", subtext: "額度保留鎖存", status: "WARNING", detail: "存在 UNKNOWN 在途單，凍結預算 $474.75" },
      { name: "交易所委託", subtext: "cat_calico_unknown_01", status: "WARNING", detail: "發送委託後逾時，等待 Supervisor 對帳終態" },
      { name: "帳務對帳", subtext: "待對帳終態", status: "BLOCKED", detail: "未取得交易所確認前，嚴格禁止再次增倉" },
    ],
  },
  mochi: {
    id: "mochi",
    name: "Mochi 橘貓突破",
    symbol: "SOL-USDT-SWAP",
    timeframe: "15m",
    strategyId: "vol_breakout_v1",
    status: "running",
    intentSummary: "保護更新待確認 · 暫停新增曝險",
    dataEvalTime: "11:15:00 UTC+8",
    targetPosText: "+15.0 SOL",
    notional: 2130,
    upnl: 18.5,
    upnlPct: 0.88,
    p6StopPrice: "更新中 (待確認)",
    p6DistPct: "-7.06%",
    p6Status: "UPDATING",
    condition: "ATR 波動率突破 2.4 倍標準差",
    riskLimit: "P6 災難停損更新中，未生效前禁止增倉",
    p6Source: "OKX Mark (待確認)",
    p6Rounding: "向上取整 (CEIL)",
    p6BudgetPct: "5.7% / 50.0%",
    riskLeverage: "1.46x / 3.0x",
    riskSingleAssetQuota: "5.7% (上限 50%)",
    entryPrice: "$140.50",
    markPrice: "$142.00",
    stages: [
      { name: "資料評估", subtext: "15m 實時 Bar", status: "OK", detail: "價格波動突破上軌" },
      { name: "策略意圖", subtext: "推移防線至 $142.00", status: "OK", detail: "向上調整停損錨定價" },
      { name: "風控審核", subtext: "保護防線優先", status: "WARNING", detail: "必須先完成 P6 更新終態" },
      { name: "交易所委託", subtext: "更新請求在途", status: "WARNING", detail: "向 OKX 發送 algo_stop 更新，等待 ACK" },
      { name: "帳務對帳", subtext: "待更新終態", status: "WARNING", detail: "生效價暫標為未知，覆蓋數量待確認" },
    ],
  },
  shiro: {
    id: "shiro",
    name: "Shiro 白貓避險",
    symbol: "BTC-USDT-SWAP",
    timeframe: "4H",
    strategyId: "macro_hedge_v1",
    status: "paused",
    intentSummary: "已手動暫停 · 不產生新策略意圖",
    dataEvalTime: "08:00:00 UTC+8",
    targetPosText: "0.00 (空倉)",
    notional: 0,
    upnl: 0,
    upnlPct: 0,
    p6StopPrice: "未啟用 (空倉)",
    p6DistPct: "--",
    p6Status: "STANDBY",
    condition: "資金費率偏離 > 0.05% 時反向對沖",
    riskLimit: "手動暫停狀態，保留既有部位安全平倉通道",
    p6Source: "--",
    p6Rounding: "--",
    p6BudgetPct: "0.0% / 50.0%",
    riskLeverage: "1.46x / 3.0x",
    riskSingleAssetQuota: "0.0% (上限 50%)",
    entryPrice: "--",
    markPrice: "--",
    stages: [
      { name: "資料評估", subtext: "4H 定期檢查", status: "OK", detail: "未達宏觀對沖門檻" },
      { name: "策略意圖", subtext: "手動暫停", status: "BLOCKED", detail: "交易員手動停用 Worker" },
      { name: "風控審核", subtext: "允許合法減倉", status: "OK", detail: "若有舊部位仍可平倉" },
      { name: "交易所委託", subtext: "無委託", status: "OK", detail: "當前無在途掛單" },
      { name: "帳務對帳", subtext: "無持倉", status: "OK", detail: "零部位狀態對帳完成" },
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
  expandedInlineBotIds: ["calico"],
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
