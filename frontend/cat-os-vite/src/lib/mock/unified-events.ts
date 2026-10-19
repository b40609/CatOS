export type EventCategory = "ALL" | "FILL" | "ALERT" | "SYSTEM";
export type EventSeverity = "CRIT" | "WARN" | "INFO" | "OK" | "TRADE";

export interface UnifiedEvent {
  id: string;
  time: string;
  category: "FILL" | "ALERT" | "SYSTEM";
  severity: EventSeverity;
  title: string;
  detail: string;
  source: string;
  // 成交專用欄位 (選填)
  symbol?: string;
  action?: "開多" | "平多" | "開空" | "平空";
  side?: "buy" | "sell";
  qty?: string;
  price?: string;
  pnl?: number;
  botName?: string;
}

export const UNIFIED_EVENTS: UnifiedEvent[] = [
  {
    id: "evt_01",
    time: "11:10:02",
    category: "ALERT",
    severity: "WARN",
    title: "ETH 震盪網格 Alpha 03 撮合滑價偏離",
    detail: "最近一筆買單成交價滑價達 0.08%，高於預設容忍值 0.05%。已記錄並維持運行，未觸發硬終止。",
    source: "RiskEngine",
    botName: "Calico",
  },
  {
    id: "evt_02",
    time: "10:24:15",
    category: "SYSTEM",
    severity: "INFO",
    title: "外部 Agent 生成新研究草稿 v1.2-draft",
    detail: "Antigravity IDE 透過 MCP 提交候選草稿，已隔離儲存於策略中心，未影響在線運行之生產版本。",
    source: "MCP-Server",
  },
  {
    id: "evt_03",
    time: "09:30:10",
    category: "SYSTEM",
    severity: "INFO",
    title: "SOL 試驗波段 04 切換為手動維護停機",
    detail: "操作者於 15m 週期回測校準前手動發出暫停指令，現有持倉保持 FLAT 零部位。",
    source: "Supervisor",
    botName: "Mochi",
  },
  {
    id: "evt_04",
    time: "09:00:22",
    category: "FILL",
    severity: "TRADE",
    title: "DOGE-USDT-SWAP 委託市價成交",
    detail: "市價開多 8,000 口，成交均價 $0.1680，無滑價滑移。",
    source: "OKX-SWAP",
    symbol: "DOGE-USDT-SWAP",
    action: "開多",
    side: "buy",
    qty: "8,000",
    price: "0.1680",
    pnl: 0,
    botName: "Tabby",
  },
  {
    id: "evt_05",
    time: "08:14:55",
    category: "FILL",
    severity: "TRADE",
    title: "SOL-USDT-SWAP 策略停利平倉成交",
    detail: "唐奇安上軌突破停利，平多 12.00 SOL，成交均價 $152.40，實現損益 +$68.20。",
    source: "OKX-SWAP",
    symbol: "SOL-USDT-SWAP",
    action: "平多",
    side: "sell",
    qty: "12.00",
    price: "152.40",
    pnl: 68.2,
    botName: "Mochi",
  },
  {
    id: "evt_06",
    time: "08:00:00",
    category: "SYSTEM",
    severity: "OK",
    title: "OKX P6 交易所端整倉災難停損更新完成",
    detail: "部位平均成本微幅改變，交易所端整倉停損單已重新錨定 (BTC @ 59,500, ETH @ 3,210)。保護狀態 ACTIVE。",
    source: "OKX-P6-Guard",
  },
  {
    id: "evt_07",
    time: "06:00:00",
    category: "FILL",
    severity: "TRADE",
    title: "ETH-USDT-SWAP 1H 收盤訊號開倉成交",
    detail: "均線回踩確認，開多 2.40 ETH，成交均價 $3,320.00，佔用保證金 15%。",
    source: "OKX-SWAP",
    symbol: "ETH-USDT-SWAP",
    action: "開多",
    side: "buy",
    qty: "2.40",
    price: "3,320.00",
    pnl: 0,
    botName: "Calico",
  },
  {
    id: "evt_08",
    time: "04:30:12",
    category: "FILL",
    severity: "TRADE",
    title: "BTC-USDT-SWAP 獵貓動能平空成交",
    detail: "次根開盤市價平空 0.12 BTC，成交均價 $61,480.00，實現損益 +$142.50。",
    source: "OKX-SWAP",
    symbol: "BTC-USDT-SWAP",
    action: "平空",
    side: "buy",
    qty: "0.12",
    price: "61,480.00",
    pnl: 142.5,
    botName: "Tabby",
  },
  {
    id: "evt_09",
    time: "00:00:01",
    category: "SYSTEM",
    severity: "INFO",
    title: "每日日損防線分母切日歸位 (Asia/Taipei)",
    detail: "依 Asia/Taipei 00:00 基準，日初權益分母更新為 $40,272.50。Soft 10% / Hard 20% 防線重設就位。",
    source: "RiskGuardian",
  },
];
