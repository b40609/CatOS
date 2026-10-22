import { create } from 'zustand';

export interface PreviewBot {
  id: string;
  name: string;
  symbol: string;
  timeframe: string;
  strategyId: string;
  status: 'running' | 'paused';
  side: 'long' | 'short' | 'idle';
  qtyText: string;
  notional: number;
  upnl: number;
  upnlPct: number;
  dailyRet: string;
  sevenDayRet: string;
  dd: number;
  p6StopPrice: string;
  p6DistPct: string;
  p6Status: 'ACTIVE' | 'UPDATING' | 'STANDBY';
  p6Rounding: string;
  warning?: boolean;
  intentSummary: string;
  dataTime: string;
  bar: string;
  currentPos: string;
  targetPos: string;
  condition: string;
  riskLimit: string;
  orderRecon: string;
  nextStep: string;
  stages: [string, string][];
  relatedEventId?: string;
  relatedOrderId?: string;
  relatedPositionId?: string;
}

export interface PreviewPosition {
  id: string;
  botId: string;
  botName: string;
  symbol: string;
  base: string;
  side: 'long' | 'short';
  qty: string;
  entry: string;
  mark: string;
  notional: string;
  upnl: number;
  upnlPct: number;
  leverage: string;
  opened: string;
  liqPrice: string;
  distLiqPct: string;
  p6Status: 'CONFIRMED' | 'UPDATING' | 'DISABLED';
  p6ActiveStopPrice: string; // 已確認生效價 (未知時顯示 "未知")
  p6TargetStopPrice: string; // 更新目標價
  p6CoveredQty: string;      // 覆蓋數量 (待確認時顯示 "待確認")
  p6ConfirmedAt: string;     // 確認時間
  p6Source: string;          // 來源
  p6OrderState: string;      // 保護委託狀態
  p6Detail: string;          // 說明
  p6NextStep: string;        // 下一步
  relatedEventId?: string;
  relatedOrderId?: string;
}

export interface PreviewOrder {
  id: string;
  clientOrderId: string;
  botId: string;
  botName: string;
  symbol: string;
  side: 'buy' | 'sell';
  type: string;
  price: string;
  qty: string;
  distPct: string;
  distTicks: string;
  frozenMargin: string;
  notionalUsd: string;
  placed: string;
  status: string;
  isUnknown?: boolean;
  detail?: string;
  relatedEventId?: string;
}

export interface PreviewEvent {
  id: string;
  time: string;
  category: 'ALERT' | 'FILL' | 'SYSTEM';
  severity: 'WARN' | 'INFO' | 'OK' | 'TRADE';
  source: string;
  botName?: string;
  botId?: string;
  title: string;
  detail: string;
  resolution: 'open' | 'resolved';
  impact?: string;
  nextStep?: string;
  relatedOrderId?: string;
  relatedPositionId?: string;
  symbol?: string;
  action?: string;
  side?: 'buy' | 'sell';
  qty?: string;
  price?: string;
  pnl?: number;
}

export interface InspectorState {
  type: 'bot' | 'event' | 'protection' | null;
  id: string | null;
}

export interface HighlightTarget {
  type: 'bot' | 'order' | 'position' | 'protection' | 'event' | null;
  id: string | null;
  token: number;
}

interface PreviewStoreState {
  bots: PreviewBot[];
  positions: PreviewPosition[];
  orders: PreviewOrder[];
  events: PreviewEvent[];
  activeInspector: InspectorState;
  highlightTarget: HighlightTarget;
  positionsTab: 'positions' | 'orders';
  eventCategory: 'OPEN' | 'ALL' | 'FILL' | 'ALERT' | 'SYSTEM';

  // Actions
  toggleBotPause: (botId: string) => void;
  openInspector: (type: 'bot' | 'event' | 'protection', id: string) => void;
  closeInspector: () => void;
  setPositionsTab: (tab: 'positions' | 'orders') => void;
  setEventCategory: (cat: 'OPEN' | 'ALL' | 'FILL' | 'ALERT' | 'SYSTEM') => void;
  triggerHighlight: (type: 'bot' | 'order' | 'position' | 'protection' | 'event', id: string) => void;

  // Jump navigations
  jumpToBot: (botId: string) => void;
  jumpToOrder: (orderId: string) => void;
  jumpToProtection: (positionId: string) => void;
  jumpToEvent: (eventId: string) => void;
}

const INITIAL_BOTS_DATA: PreviewBot[] = [
  {
    id: 'tabby',
    name: 'Tabby',
    symbol: 'BTC-USDT-SWAP',
    timeframe: '15m',
    strategyId: 'breakout_v22',
    status: 'running',
    side: 'long',
    qtyText: '0.85 BTC',
    notional: 52820,
    upnl: 561.43,
    upnlPct: 1.07,
    dailyRet: '+2.45%',
    sevenDayRet: '+8.12%',
    dd: -1.24,
    p6StopPrice: '$59,500.00',
    p6DistPct: '-4.25%',
    p6Status: 'ACTIVE',
    p6Rounding: 'CEIL 向上取整',
    intentSummary: '續抱 · 等待 11:15 收盤',
    dataTime: '11:15:00 (UTC+08:00)',
    bar: '11:00 已收盤 K 線',
    currentPos: '0.85 BTC',
    targetPos: '0.85 BTC (維持續抱)',
    condition: '已收盤價格仍在策略持有區間；策略停損條件未成立。',
    riskLimit: '無新增曝險，合約風控在預算內；有效槓桿 2.16x / 3.0x。',
    orderRecon: '無新委託 · 現有部位 0.85 BTC 與 OKX 交易所對帳一致。',
    nextStep: '下一次評估：11:15 K 線收盤後；交易所端災難停損已確認。',
    stages: [
      ['資料', '11:00 已收盤'],
      ['意圖', 'HOLD 續抱'],
      ['風控', '無新增曝險'],
      ['委託', '無新委託'],
      ['對帳', '部位已同步'],
    ],
    relatedPositionId: 'p1',
    relatedEventId: 'evt_resolved_tabby',
  },
  {
    id: 'calico',
    name: 'Calico',
    symbol: 'ETH-USDT-SWAP',
    timeframe: '1h',
    strategyId: 'trend_follow',
    status: 'running',
    side: 'long',
    qtyText: '9.50 ETH',
    notional: 32060,
    upnl: 524.40,
    upnlPct: 1.66,
    dailyRet: '+3.12%',
    sevenDayRet: '+12.45%',
    dd: -2.15,
    p6StopPrice: '$3,210.00',
    p6DistPct: '-4.89%',
    p6Status: 'ACTIVE',
    p6Rounding: 'CEIL 向上取整',
    warning: true,
    intentSummary: '目標 11 ETH · 委託待對帳',
    dataTime: '11:15:00 (UTC+08:00)',
    bar: '11:00 已收盤 K 線',
    currentPos: '9.50 ETH',
    targetPos: '11.00 ETH (尚未達成)',
    condition: '收盤趨勢條件成立；增倉委託已送出，但回覆逾時，不能確認是否成交。',
    riskLimit: '額度仍保留 (在途凍結 $4,050.00)；禁止增加曝險，合法減倉依既有路徑。',
    orderRecon: '增倉委託 UNKNOWN (ID: cat_calico_unknown_01) · 等待可信終態。',
    nextStep: '核對原委託與成交來源。未取得可信終態前，不盲目重送、不釋放額度；合法減倉依既有路徑。',
    stages: [
      ['資料', '11:00 已收盤'],
      ['意圖', '目標 11 ETH'],
      ['風控', '額度仍保留'],
      ['委託', 'UNKNOWN'],
      ['對帳', '等待可信終態'],
    ],
    relatedPositionId: 'p2',
    relatedOrderId: 'order_calico_unknown_01',
    relatedEventId: 'evt_unknown_calico',
  },
  {
    id: 'mochi',
    name: 'Mochi',
    symbol: 'SOL-USDT-SWAP',
    timeframe: '5m',
    strategyId: 'grid_mm',
    status: 'running',
    side: 'long',
    qtyText: '95.0 SOL',
    notional: 14516,
    upnl: 437.00,
    upnlPct: 3.10,
    dailyRet: '+1.88%',
    sevenDayRet: '+6.30%',
    dd: -0.85,
    p6StopPrice: '目標 $142.00 (未生效)',
    p6DistPct: '-7.07%',
    p6Status: 'UPDATING',
    p6Rounding: 'CEIL 向上取整',
    warning: true,
    intentSummary: '保護更新待確認 · 禁增倉',
    dataTime: '11:15:00 (UTC+08:00)',
    bar: '11:10 已收盤 K 線',
    currentPos: '95.0 SOL',
    targetPos: '110.0 SOL (待確認保護後)',
    condition: '收盤加倉條件成立；交易所端災難停損更新尚未確認，Supervisor 阻擋新增曝險。',
    riskLimit: '交易所端災難停損更新待確認；禁增倉，不自動減持，合法減倉依既有路徑。',
    orderRecon: '未送出增倉單 · 現有 95.0 SOL 部位已同步。',
    nextStep: '檢查保護委託終態。此限制不會自動減持；不能把更新目標價當成已生效保護。',
    stages: [
      ['資料', '11:10 已收盤'],
      ['意圖', '目標 110 SOL'],
      ['風控', '保護未確認'],
      ['委託', '未送增倉單'],
      ['對帳', '現有部位同步'],
    ],
    relatedPositionId: 'p3',
    relatedEventId: 'evt_protection_mochi',
  },
  {
    id: 'shiro',
    name: 'Shiro',
    symbol: 'ARB-USDT-SWAP',
    timeframe: '1h',
    strategyId: 'pairs',
    status: 'paused',
    side: 'idle',
    qtyText: '0.00',
    notional: 0,
    upnl: 0,
    upnlPct: 0,
    dailyRet: '0.00%',
    sevenDayRet: '0.00%',
    dd: -3.42,
    p6StopPrice: '—',
    p6DistPct: '無持倉',
    p6Status: 'STANDBY',
    p6Rounding: '待命',
    intentSummary: '已暫停 · 不產生新策略意圖',
    dataTime: '11:15:00 (UTC+08:00)',
    bar: '未評估',
    currentPos: '空倉 (0.00)',
    targetPos: '無新目標',
    condition: 'Bot 已手動暫停，尚未取得合約執行權。',
    riskLimit: '未啟用合約，無持倉曝險。',
    orderRecon: '無在途委託 · 空倉已同步。',
    nextStep: '目前沒有待處理的策略意圖。點擊重啟後可恢復策略評估。',
    stages: [
      ['資料', '未評估'],
      ['意圖', '無'],
      ['風控', '未啟用'],
      ['委託', '無'],
      ['對帳', '空倉'],
    ],
    relatedEventId: 'evt_sys_shiro_paused',
  },
];

const INITIAL_POSITIONS_DATA: PreviewPosition[] = [
  {
    id: 'p1',
    botId: 'tabby',
    botName: 'Tabby',
    symbol: 'BTC-USDT-SWAP',
    base: 'BTC',
    side: 'long',
    qty: '0.85',
    entry: '61,480.00',
    mark: '62,140.50',
    notional: '52,820',
    upnl: 561.43,
    upnlPct: 1.07,
    leverage: '3x 全倉 (cross)',
    opened: '04:30',
    liqPrice: '54,210.00',
    distLiqPct: '+12.7%',
    p6Status: 'CONFIRMED',
    p6ActiveStopPrice: '$59,500.00',
    p6TargetStopPrice: '$59,500.00',
    p6CoveredQty: '0.85 BTC',
    p6ConfirmedAt: '11:14:58 (UTC+08:00)',
    p6Source: 'OKX 交易所保護快照 (合成)',
    p6OrderState: '有效錨定 · Mark 觸發 · 向上取整',
    p6Detail: '保護覆蓋量 0.85 BTC 與現有持倉 100% 吻合。交易所端整倉災難停損已確認生效。',
    p6NextStep: '目前保護與部位數量一致；均價變更時仍須重新確認覆蓋。',
    relatedEventId: 'evt_resolved_tabby',
  },
  {
    id: 'p2',
    botId: 'calico',
    botName: 'Calico',
    symbol: 'ETH-USDT-SWAP',
    base: 'ETH',
    side: 'long',
    qty: '9.50',
    entry: '3,320.00',
    mark: '3,375.20',
    notional: '32,060',
    upnl: 524.40,
    upnlPct: 1.66,
    leverage: '3x 全倉 (cross)',
    opened: '10/5 06:00',
    liqPrice: '2,980.00',
    distLiqPct: '+11.7%',
    p6Status: 'CONFIRMED',
    p6ActiveStopPrice: '$3,210.00',
    p6TargetStopPrice: '$3,210.00',
    p6CoveredQty: '9.50 ETH',
    p6ConfirmedAt: '11:14:58 (UTC+08:00)',
    p6Source: 'OKX 交易所保護快照 (合成)',
    p6OrderState: '有效錨定 (僅涵蓋核對部位)',
    p6Detail: '有效保護數量 9.50 ETH。注意：增倉委託 UNKNOWN，保護確認僅涵蓋目前已核對的 9.50 ETH 部位，尚未涵蓋在途 1.50 ETH。',
    p6NextStep: '先完成增倉委託對帳；若部位改變，必須重新確認保護覆蓋並重新錨定。',
    relatedEventId: 'evt_unknown_calico',
    relatedOrderId: 'order_calico_unknown_01',
  },
  {
    id: 'p3',
    botId: 'mochi',
    botName: 'Mochi',
    symbol: 'SOL-USDT-SWAP',
    base: 'SOL',
    side: 'long',
    qty: '95.00',
    entry: '148.20',
    mark: '152.80',
    notional: '14,516',
    upnl: 437.00,
    upnlPct: 3.10,
    leverage: '3x 全倉 (cross)',
    opened: '08:15',
    liqPrice: '131.50',
    distLiqPct: '+13.9%',
    p6Status: 'UPDATING',
    p6ActiveStopPrice: '未知 (未取得終態)',
    p6TargetStopPrice: '$142.00',
    p6CoveredQty: '待確認',
    p6ConfirmedAt: '11:09:18 請求中無終態',
    p6Source: 'OKX 保護回報 (合成)',
    p6OrderState: '更新請求尚無可信終態 · 禁增倉',
    p6Detail: '11:09:18 更新請求尚無可信終態；目前有效保護價與覆蓋量未確認。$142.00 僅為更新目標，不能視為已生效。',
    p6NextStep: '核對交易所保護委託終態，完成核對前禁止增加曝險，不自動減持，合法減倉依既有路徑。',
    relatedEventId: 'evt_protection_mochi',
  },
];

const INITIAL_ORDERS_DATA: PreviewOrder[] = [
  {
    id: 'order_calico_unknown_01',
    clientOrderId: 'cat_calico_unknown_01',
    botId: 'calico',
    botName: 'Calico',
    symbol: 'ETH-USDT-SWAP',
    side: 'buy',
    type: '限價/市價增倉',
    price: '3,375.00',
    qty: '0.60',
    distPct: '0.00%',
    distTicks: '0 ticks',
    frozenMargin: '$474.75',
    notionalUsd: '$2,025',
    placed: '11:10:02',
    status: 'UNKNOWN · 待對帳',
    isUnknown: true,
    detail: '11:10:02 回覆逾時；是否成交尚未確認。額度仍保留，禁止盲目重送。',
    relatedEventId: 'evt_unknown_calico',
  },
  {
    id: 'o3',
    clientOrderId: 'cat_mochi_0733',
    botId: 'mochi',
    botName: 'Mochi',
    symbol: 'SOL-USDT-SWAP',
    side: 'sell',
    type: '限價',
    price: '155.80',
    qty: '10.0',
    distPct: '+1.96%',
    distTicks: '+30 ticks',
    frozenMargin: '$145.80',
    notionalUsd: '$1,558',
    placed: '09:30',
    status: '掛單中',
  },
  {
    id: 'o4',
    clientOrderId: 'cat_mochi_0734',
    botId: 'mochi',
    botName: 'Mochi',
    symbol: 'SOL-USDT-SWAP',
    side: 'buy',
    type: '限價',
    price: '146.90',
    qty: '6.0',
    distPct: '-3.86%',
    distTicks: '-54 ticks',
    frozenMargin: '$298.10',
    notionalUsd: '$881',
    placed: '09:30',
    status: '掛單中',
  },
];

const INITIAL_EVENTS_DATA: PreviewEvent[] = [
  {
    id: 'evt_unknown_calico',
    time: '11:10:02',
    category: 'ALERT',
    severity: 'WARN',
    source: 'Supervisor',
    botName: 'Calico',
    botId: 'calico',
    title: 'ETH 增倉委託 UNKNOWN',
    resolution: 'open',
    detail: '策略目標 3.00 ETH；目前核對部位 2.40 ETH。送單回覆逾時，尚未確認最終結果。',
    impact: '增倉受限，對應額度 ($474.75) 保持占用；不能直接認定失敗，禁止盲目重送。',
    nextStep: '核對原委託與成交來源，取得可信終態；合法減倉依既有路徑。',
    relatedOrderId: 'order_calico_unknown_01',
    relatedPositionId: 'p2',
  },
  {
    id: 'evt_protection_mochi',
    time: '11:09:18',
    category: 'ALERT',
    severity: 'WARN',
    source: 'P6 Guard',
    botName: 'Mochi',
    botId: 'mochi',
    title: 'SOL 災難停損更新未確認',
    resolution: 'open',
    detail: '現有部位 18 SOL；保護更新目標 $142.00 尚未確認生效。20 SOL 策略目標之增倉委託未送出。',
    impact: '禁止增加曝險；不自動減持，合法減倉依既有路徑。',
    nextStep: '核對交易所保護委託終態與覆蓋數量；確認前不顯示「保護中」。',
    relatedPositionId: 'p3',
  },
  {
    id: 'evt_sys_heartbeat',
    time: '11:14:58',
    category: 'SYSTEM',
    severity: 'OK',
    source: 'Supervisor',
    title: '部位核對完成 · 保護仍有 1 筆待確認',
    resolution: 'resolved',
    detail: 'BTC、ETH、SOL 已核對目前部位；P6 確認 2/3，Mochi 未確認狀態持續保留。',
  },
  {
    id: 'evt_resolved_tabby',
    time: '10:45:16',
    category: 'ALERT',
    severity: 'WARN',
    source: 'Market Feed',
    botName: 'Tabby',
    botId: 'tabby',
    title: 'BTC 收盤 K 線延遲 · 已恢復',
    resolution: 'resolved',
    detail: '10:45:16 已補齊並核對收盤資料，恢復後重新評估；目前沒有此項資料限制。歷史告警仍保留於日誌。',
    impact: '無待處理事項，不影響其他未解除原因。',
    nextStep: '此事件已解除，無待處理事項；歷史事件保留於戰情日誌。',
    relatedPositionId: 'p1',
  },
  {
    id: 'evt_fill_mochi',
    time: '10:30:00',
    category: 'FILL',
    severity: 'TRADE',
    source: 'OKX-SWAP',
    botName: 'Mochi',
    botId: 'mochi',
    title: 'SOL 開多成交',
    symbol: 'SOL-USDT-SWAP',
    action: '開多',
    side: 'buy',
    qty: '18.0',
    price: '148.20',
    pnl: 0,
    resolution: 'resolved',
    detail: '合成成交紀錄：部位 18.0 SOL。後續保護更新狀態請見未解除事件。',
    relatedPositionId: 'p3',
  },
  {
    id: 'evt_sys_shiro_paused',
    time: '09:30:10',
    category: 'SYSTEM',
    severity: 'INFO',
    source: 'Supervisor',
    botName: 'Shiro',
    botId: 'shiro',
    title: 'Shiro 已暫停 · 空倉',
    resolution: 'resolved',
    detail: '沒有在途委託，未取得合約執行權；不產生新策略意圖。',
  },
];

export const usePreviewStore = create<PreviewStoreState>((set, get) => ({
  bots: INITIAL_BOTS_DATA,
  positions: INITIAL_POSITIONS_DATA,
  orders: INITIAL_ORDERS_DATA,
  events: INITIAL_EVENTS_DATA,
  activeInspector: { type: null, id: null },
  highlightTarget: { type: null, id: null, token: 0 },
  positionsTab: 'positions',
  eventCategory: 'ALL',

  toggleBotPause: (botId: string) => {
    const currentBots = get().bots;
    const targetBot = currentBots.find((b) => b.id === botId);
    if (!targetBot) return;

    const nextStatus: 'running' | 'paused' = targetBot.status === 'running' ? 'paused' : 'running';
    const isPausedNow = nextStatus === 'paused';

    // 1. 更新 Bot 狀態
    const updatedBots: PreviewBot[] = currentBots.map((b) => {
      if (b.id !== botId) return b;
      return {
        ...b,
        status: nextStatus,
        intentSummary: isPausedNow ? '已暫停 · 不產生新策略意圖' : b.intentSummary,
      };
    });

    // 2. 產生模擬日誌
    const now = new Date();
    const timeStr = now.toTimeString().slice(0, 8);
    const newLogId = `evt_toggle_${botId}_${Date.now()}`;

    const newEvent: PreviewEvent = {
      id: newLogId,
      time: timeStr,
      category: 'SYSTEM',
      severity: 'INFO',
      source: 'Supervisor',
      botName: targetBot.name,
      botId: targetBot.id,
      title: `${targetBot.name} 已${isPausedNow ? '暫停' : '啟用'} · 本地模擬`,
      resolution: 'resolved',
      detail: isPausedNow
        ? `${targetBot.name} 策略已手動暫停。注意：暫停不代表平倉；合約執行權暫時保留，空倉或既有持倉依舊安全。此操作為本機前端模擬，不向後端發送控制請求。`
        : `${targetBot.name} 策略已恢復運作。注意：啟用不得解除風控限制或 UNKNOWN（如 Calico UNKNOWN 或 Mochi 保護未確認之禁增倉限制依然有效）。此操作為本機前端模擬。`,
      impact: isPausedNow ? '不再產生次根開盤意圖，現有部位或保護不受影響。' : '恢復 Closed Bar 收盤決策；若有既有風控限制依然強制保留。',
      nextStep: isPausedNow ? '若需平倉請至部位卡操作；恢復時點擊重啟。' : '等待次根 K 線收盤重新評估策略。',
    };

    set({
      bots: updatedBots,
      events: [newEvent, ...get().events],
    });
  },

  openInspector: (type, id) => {
    set({ activeInspector: { type, id } });
  },

  closeInspector: () => {
    set({ activeInspector: { type: null, id: null } });
  },

  setPositionsTab: (tab) => {
    set({ positionsTab: tab });
  },

  setEventCategory: (cat) => {
    set({ eventCategory: cat });
  },

  triggerHighlight: (type, id) => {
    set({ highlightTarget: { type, id, token: Date.now() } });
  },

  jumpToBot: (botId) => {
    get().triggerHighlight('bot', botId);
    get().openInspector('bot', botId);
  },

  jumpToOrder: (orderId) => {
    set({ positionsTab: 'orders' });
    get().triggerHighlight('order', orderId);
  },

  jumpToProtection: (positionId) => {
    set({ positionsTab: 'positions' });
    get().triggerHighlight('protection', positionId);
    get().openInspector('protection', positionId);
  },

  jumpToEvent: (eventId) => {
    get().openInspector('event', eventId);
  },
}));
