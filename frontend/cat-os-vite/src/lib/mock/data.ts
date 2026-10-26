export type Strategy = {
  id: string;
  name: string;
  code: string;
  kind: "趨勢跟蹤" | "均值回歸" | "套利" | "做市" | "情緒模型";
  market: string;
  annual: number;
  sharpe: number;
  drawdown: number;
  winRate: number;
  trades: number;
  enabled: boolean;
  params: { key: string; value: string }[];
  curve: number[];
};

export type Bot = {
  id: string;
  name: string;
  strategy: string;
  market: string;
  status: "running" | "paused" | "error";
  position: string;
  pnlToday: number;
  uptimeHours: number;
  latencyMs: number;
};

export type Signal = {
  id: string;
  time: string;
  symbol: string;
  side: "LONG" | "SHORT" | "FLAT";
  confidence: number;
  model: string;
};

export type Fill = {
  id: string;
  time: string;
  symbol: string;
  side: "BUY" | "SELL";
  qty: number;
  price: number;
  pnl: number;
};

export type RiskRule = {
  id: string;
  name: string;
  desc: string;
  value: number;
  min: number;
  max: number;
  unit: string;
  enabled: boolean;
};

export type RiskAlert = {
  id: string;
  time: string;
  level: "warn" | "error" | "info";
  text: string;
};

export type LogLevel = "INFO" | "WARN" | "ERROR" | "TRADE";

export type LogLine = {
  id: string;
  time: string;
  level: LogLevel;
  source: string;
  message: string;
};

function walk(seed: number, n: number, drift = 0.4, vol = 3) {
  let v = 100;
  let s = seed;
  const out: number[] = [];
  for (let i = 0; i < n; i++) {
    s = (s * 9301 + 49297) % 233280;
    const r = s / 233280 - 0.5;
    v = Math.max(20, v + drift + r * vol);
    out.push(Number(v.toFixed(2)));
  }
  return out;
}

export const strategies: Strategy[] = [
  {
    id: "s1",
    name: "獵貓動能",
    code: "CAT-MOM-01",
    kind: "趨勢跟蹤",
    market: "BTC / ETH 永續",
    annual: 68.4,
    sharpe: 2.31,
    drawdown: -11.2,
    winRate: 57.8,
    trades: 1284,
    enabled: true,
    params: [
      { key: "lookback", value: "48h" },
      { key: "entry_z", value: "1.85" },
      { key: "exit_z", value: "0.35" },
      { key: "max_leverage", value: "3.0x" },
      { key: "model", value: "catnet-v4" },
    ],
    curve: walk(11, 60, 0.9, 4),
  },
  {
    id: "s2",
    name: "夜視回歸",
    code: "CAT-MR-07",
    kind: "均值回歸",
    market: "ETH / BTC 現貨",
    annual: 34.1,
    sharpe: 1.87,
    drawdown: -6.4,
    winRate: 64.2,
    trades: 3921,
    enabled: true,
    params: [
      { key: "window", value: "20m" },
      { key: "band", value: "2.2σ" },
      { key: "hold_max", value: "90m" },
      { key: "max_leverage", value: "1.5x" },
      { key: "model", value: "meanpaw-v2" },
    ],
    curve: walk(29, 60, 0.5, 2.2),
  },
  {
    id: "s3",
    name: "跨所套利",
    code: "CAT-ARB-03",
    kind: "套利",
    market: "Binance / OKX",
    annual: 22.7,
    sharpe: 3.42,
    drawdown: -2.1,
    winRate: 88.9,
    trades: 15422,
    enabled: true,
    params: [
      { key: "min_spread", value: "8 bps" },
      { key: "size", value: "0.35 BTC" },
      { key: "timeout", value: "1200ms" },
      { key: "max_leverage", value: "1.0x" },
      { key: "model", value: "rule-based" },
    ],
    curve: walk(41, 60, 0.35, 0.9),
  },
  {
    id: "s4",
    name: "做市貓爪",
    code: "CAT-MM-02",
    kind: "做市",
    market: "SOL 永續",
    annual: 45.9,
    sharpe: 2.05,
    drawdown: -9.8,
    winRate: 71.3,
    trades: 88211,
    enabled: false,
    params: [
      { key: "quote_bps", value: "6" },
      { key: "inventory_cap", value: "1200 SOL" },
      { key: "skew", value: "adaptive" },
      { key: "max_leverage", value: "2.0x" },
      { key: "model", value: "quotecat-v1" },
    ],
    curve: walk(53, 60, 0.7, 5),
  },
  {
    id: "s5",
    name: "輿情嗅探",
    code: "CAT-NLP-05",
    kind: "情緒模型",
    market: "BTC / SOL 社群訊號",
    annual: 51.2,
    sharpe: 1.42,
    drawdown: -18.6,
    winRate: 49.1,
    trades: 642,
    enabled: false,
    params: [
      { key: "sources", value: "交易所 / 鏈上 / 社群" },
      { key: "sentiment_th", value: "0.62" },
      { key: "hold", value: "3d" },
      { key: "max_leverage", value: "1.2x" },
      { key: "model", value: "whisker-llm" },
    ],
    curve: walk(67, 60, 0.75, 7),
  },
  {
    id: "s6",
    name: "波動獵手",
    code: "CAT-VOL-09",
    kind: "趨勢跟蹤",
    market: "BTC / ETH 永續波動",
    annual: 39.6,
    sharpe: 1.66,
    drawdown: -14.3,
    winRate: 52.4,
    trades: 418,
    enabled: true,
    params: [
      { key: "iv_rank", value: "> 65" },
      { key: "delta", value: "0.25" },
      { key: "roll", value: "7d" },
      { key: "max_leverage", value: "2.5x" },
      { key: "model", value: "vegacat-v3" },
    ],
    curve: walk(83, 60, 0.6, 5.5),
  },
];

export const bots: Bot[] = [
  {
    id: "b1",
    name: "CAT-01 / TOKYO",
    strategy: "獵貓動能",
    market: "BTC-USDT-SWAP",
    status: "running",
    position: "LONG 1.2400 BTC",
    pnlToday: 4821.4,
    uptimeHours: 412,
    latencyMs: 18,
  },
  {
    id: "b2",
    name: "CAT-02 / TAIPEI",
    strategy: "夜視回歸",
    market: "ETH-USDT-SWAP",
    status: "running",
    position: "SHORT 2.8000 ETH",
    pnlToday: -932.6,
    uptimeHours: 189,
    latencyMs: 31,
  },
  {
    id: "b3",
    name: "CAT-03 / SINGAPORE",
    strategy: "跨所套利",
    market: "BTC-USDT-SWAP",
    status: "running",
    position: "HEDGED 0.3500 BTC",
    pnlToday: 1180.2,
    uptimeHours: 902,
    latencyMs: 9,
  },
  {
    id: "b4",
    name: "CAT-04 / FRANKFURT",
    strategy: "做市貓爪",
    market: "SOL-USDT-SWAP",
    status: "paused",
    position: "FLAT",
    pnlToday: 0,
    uptimeHours: 0,
    latencyMs: 0,
  },
  {
    id: "b5",
    name: "CAT-05 / SEOUL",
    strategy: "輿情嗅探",
    market: "DOGE-USDT-SWAP",
    status: "error",
    position: "LONG 18500 DOGE",
    pnlToday: -2450.8,
    uptimeHours: 27,
    latencyMs: 214,
  },
  {
    id: "b6",
    name: "CAT-06 / LONDON",
    strategy: "波動獵手",
    market: "ETH-USDT-SWAP",
    status: "running",
    position: "SHORT 4.2000 ETH",
    pnlToday: 3140.9,
    uptimeHours: 331,
    latencyMs: 22,
  },
];

export const allocation = [
  { name: "BTC-USDT-SWAP", value: 42 },
  { name: "ETH-USDT-SWAP", value: 24 },
  { name: "SOL-USDT-SWAP", value: 18 },
  { name: "跨期套利儲備", value: 9 },
  { name: "USDT 保證金儲備", value: 7 },
];

export const equityCurve = walk(7, 90, 0.85, 3.4).map((v, i) => ({
  t: `D${i + 1}`,
  equity: Number((v * 12480).toFixed(0)),
  benchmark: Number((100 + i * 0.42) * 12480 * 0.94),
}));

export const symbols = [
  "BTC-USDT-SWAP",
  "ETH-USDT-SWAP",
  "SOL-USDT-SWAP",
  "DOGE-USDT-SWAP",
  "OKB-USDT-SWAP",
];

export const cryptoMarkets = [
  { symbol: "BTC-USDT-SWAP", code: "BTC", price: 64182.5, change: 2.84, funding: 0.0102, openInterest: "12.8B" },
  { symbol: "ETH-USDT-SWAP", code: "ETH", price: 3182.6, change: 1.46, funding: 0.0084, openInterest: "5.4B" },
  { symbol: "SOL-USDT-SWAP", code: "SOL", price: 142.38, change: -0.92, funding: -0.0031, openInterest: "1.9B" },
  { symbol: "DOGE-USDT-SWAP", code: "DOGE", price: 0.1742, change: 4.21, funding: 0.0148, openInterest: "812M" },
] as const;

// Simulated derivatives-market aggregate across the four markets above.
export const derivativesSnapshot = {
  fundingPct: 0.0087,
  openInterestB: 20.912,
  liquidationsM: 148.6,
  longLiquidationsM: 96.4,
  shortLiquidationsM: 52.2,
} as const;

export const models = ["catnet-v4", "meanpaw-v2", "whisker-llm", "vegacat-v3", "quotecat-v1"];

export const riskRules: RiskRule[] = [
  {
    id: "r1",
    name: "單幣曝險預算上限",
    desc: "單幣上限 = 總曝險預算 (槓桿上限 × E_risk) × 50%",
    value: 50,
    min: 10,
    max: 100,
    unit: "%",
    enabled: true,
  },
  {
    id: "r2",
    name: "帳戶有效槓桿上限",
    desc: "總名目價值 / 風控權益 (E_risk = E_verified)",
    value: 3,
    min: 1,
    max: 5,
    unit: "x",
    enabled: true,
  },
  {
    id: "r3",
    name: "Soft 日損停止增倉",
    desc: "Asia/Taipei 00:00 每日初權益損失 10% 停止增倉並鎖存",
    value: 10,
    min: 2,
    max: 15,
    unit: "%",
    enabled: true,
  },
  {
    id: "r4",
    name: "Hard 日損清倉與熔斷",
    desc: "日初權益損失達 20% 啟動市價清倉及 Kill-Switch 鎖存",
    value: 20,
    min: 10,
    max: 30,
    unit: "%",
    enabled: true,
  },
  {
    id: "r5",
    name: "OKX 整倉災難停損",
    desc: "交易所端整倉停損單 (Mark 價格向提早觸發方向取整)",
    value: 15,
    min: 0,
    max: 30,
    unit: "%",
    enabled: true,
  },
];

export const riskAlerts: RiskAlert[] = [
  { id: "a1", time: "09:41:22", level: "error", text: "CAT-05 OKX WebSocket 心跳超時，觸發自動重連" },
  { id: "a2", time: "09:12:07", level: "warn", text: "SOL-USDT-SWAP 單幣曝險達 42.8%，接近 50% 預算上限" },
  { id: "a3", time: "08:55:44", level: "warn", text: "帳戶有效槓桿 2.81x，接近 3.0x 預設上限" },
  { id: "a4", time: "08:30:00", level: "info", text: "日損基準權益重置完成 (Asia/Taipei 00:00 E_initial: $128,450)" },
  { id: "a5", time: "07:58:13", level: "info", text: "OKX 子帳戶對帳通過：E_verified 權益一致，無陌生部位" },
];

export const logSources = ["engine", "router", "risk", "feed", "catnet", "exec"];

export const logSeeds: LogLine[] = [
  {
    id: "l1",
    time: "09:41:22.184",
    level: "ERROR",
    source: "feed",
    message: "websocket okx: heartbeat timeout after 5000ms, reconnecting (attempt 1)",
  },
  {
    id: "l2",
    time: "09:41:20.902",
    level: "TRADE",
    source: "exec",
    message: "FILL BTC-USDT-SWAP BUY 0.35 @ 64,182.5 slippage=1.2bps bot=CAT-01",
  },
  {
    id: "l3",
    time: "09:41:18.331",
    level: "INFO",
    source: "catnet",
    message: "inference batch=64 latency=42ms conf_mean=0.71",
  },
  {
    id: "l4",
    time: "09:41:12.775",
    level: "WARN",
    source: "risk",
    message: "exposure SOL-USDT-SWAP 42.8% approaching single-asset budget limit 50.0%",
  },
  {
    id: "l5",
    time: "09:41:05.120",
    level: "INFO",
    source: "router",
    message: "order routed venue=okx latency=18ms queue_depth=1",
  },
];

const LOG_POOL: { level: LogLevel; source: string; message: string }[] = [
  { level: "INFO", source: "engine", message: "tick loop ok latency=6ms open_orders=12" },
  { level: "INFO", source: "router", message: "order routed venue=okx latency=14ms" },
  { level: "INFO", source: "feed", message: "websocket okx subscribed channel=books5 symbol=ETH-USDT-SWAP" },
  { level: "INFO", source: "catnet", message: "inference batch=128 latency=39ms conf_mean=0.74" },
  { level: "INFO", source: "engine", message: "rebalance check complete drift=0.8% within band" },
  { level: "WARN", source: "risk", message: "exposure SOL-USDT-SWAP 42.8% approaching budget limit 50.0%" },
  { level: "WARN", source: "feed", message: "market data gap detected symbol=SOL-USDT-SWAP recovered=2 ticks" },
  { level: "WARN", source: "exec", message: "partial fill BTC-USDT-SWAP 0.45/0.85 — retrying" },
  { level: "ERROR", source: "feed", message: "websocket okx: heartbeat timeout after 5000ms, reconnecting (attempt 2)" },
  { level: "ERROR", source: "exec", message: "order rejected reason=insufficient_margin bot=CAT-04" },
  { level: "TRADE", source: "exec", message: "FILL ETH-USDT-SWAP SELL 2.5000 @ 3,412.80 bot=CAT-02" },
  { level: "TRADE", source: "exec", message: "FILL SOL-USDT-SWAP BUY 14.0000 @ 142.38 bot=CAT-05" },
  { level: "TRADE", source: "exec", message: "FILL BTC-USDT-SWAP BUY 0.2000 @ 64,540.00 bot=CAT-01" },
];

export function nextLog(): LogLine {
  const pick = LOG_POOL[Math.floor(Math.random() * LOG_POOL.length)]!;
  const now = new Date(Date.now() + 8 * 3600_000);
  const time = now.toISOString().slice(11, 23);
  return {
    id: `lg-${now.getTime()}-${Math.random().toString(36).slice(2, 6)}`,
    time,
    level: pick.level,
    source: pick.source,
    message: pick.message,
  };
}
