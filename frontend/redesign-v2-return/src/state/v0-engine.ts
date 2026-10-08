/**
 * 1:1 Mathematical Simulation Engine ported from cat-os
 * Preserves all deterministic pseudo-random seeds, high-frequency tick generator,
 * equity calculations, positions, orders, trades, and events.
 */
import { ref, computed } from 'vue';

export type Period = '24H' | '7D' | '30D';
export const PERIODS: Period[] = ['24H', '7D', '30D'];
export const PERIOD_LABEL: Record<Period, string> = {
  '24H': '過去 24 小時',
  '7D': '過去 7 天',
  '30D': '過去 30 天'
};
export const PERIOD_LEN: Record<Period, number> = { '24H': 96, '7D': 672, '30D': 2880 };
export const TOTAL = 2880;
const STEP_MS = 15 * 60 * 1000;
const NOW_MS = Date.UTC(2026, 9, 6, 1, 42);
export const NOW_TEXT = '10 月 6 日 週二 09:42';

const pad = (n: number) => String(n).padStart(2, '0');

export function timeAt(index: number) {
  return NOW_MS - (TOTAL - 1 - index) * STEP_MS;
}

export function formatTime(ms: number, withDate: boolean) {
  const d = new Date(ms + 8 * 3600 * 1000);
  const hm = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
  return withDate ? `${d.getUTCMonth() + 1}/${d.getUTCDate()} ${hm}` : hm;
}

export function formatPct(v: number, digits = 2) {
  if (Number.isNaN(v)) return '—';
  const sign = v > 0 ? '+' : v < 0 ? '−' : '';
  return `${sign}${Math.abs(v).toFixed(digits)}%`;
}

export function formatMoney(v: number) {
  const sign = v > 0 ? '+' : v < 0 ? '−' : '';
  return `${sign}${Math.round(Math.abs(v)).toLocaleString('en-US')}`;
}

function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function gauss(r: () => number) {
  let u = 0;
  let v = 0;
  while (u === 0) u = r();
  while (v === 0) v = r();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

export type BotStatus = 'running' | 'paused';

export interface Bot {
  id: string;
  name: string;
  strategyId: string;
  symbol: string;
  timeframe: string;
  status: BotStatus;
  seed: number;
  drift: number;
  vol: number;
  guard: number;
  startIndex: number;
  pauseIndex?: number;
  decline?: boolean;
  capital: number;
}

const seriesCache = new Map<string, number[]>();

export function equitySeries(bot: Bot): number[] {
  const key = `${bot.id}-${bot.seed}-${bot.drift}-${bot.vol}-${bot.startIndex}-${bot.pauseIndex ?? ''}`;
  const cached = seriesCache.get(key);
  if (cached) return cached;
  const r = mulberry32(bot.seed);
  const out = new Array<number>(TOTAL).fill(Number.NaN);
  let v = 1;
  let peak = 1;
  for (let i = bot.startIndex; i < TOTAL; i++) {
    if (bot.pauseIndex !== undefined && i > bot.pauseIndex) {
      out[i] = v;
      continue;
    }
    // 穩健量化策略收益累積，疊加自然市場波動
    v *= 1 + bot.drift + bot.vol * gauss(r);
    peak = Math.max(peak, v);
    out[i] = v;
  }
  seriesCache.set(key, out);
  return out;
}

export interface Trade {
  index: number;
  side: '多' | '空';
  pnl: number;
  price: number;
}

const BASE_PRICE: Record<string, number> = { BTCUSDT: 62140, ETHUSDT: 2452, SOLUSDT: 148.6, 'BTC/ETH': 25.34 };
const tradeCache = new Map<string, Trade[]>();

export function tradesFor(bot: Bot): Trade[] {
  const key = `${bot.id}-${bot.seed}-${bot.startIndex}-${bot.pauseIndex ?? ''}`;
  const cached = tradeCache.get(key);
  if (cached) return cached;
  const r = mulberry32(bot.seed * 977 + 3);
  const base = BASE_PRICE[bot.symbol] ?? 100;
  const end = bot.pauseIndex ?? TOTAL - 1;
  const out: Trade[] = [];
  let i = bot.startIndex + 4 + Math.floor(r() * 30);
  while (i < end) {
    out.push({
      index: i,
      side: r() > 0.45 ? '多' : '空',
      pnl: gauss(r) * 0.55 + bot.drift * 3000,
      price: base * (1 + gauss(r) * 0.03),
    });
    i += 12 + Math.floor(r() * 36);
  }
  tradeCache.set(key, out);
  return out;
}

export interface RunView {
  points: number[];
  indices: number[];
  ret: number;
  pnl: number;
  maxDD: number;
  ddNow: number;
  markers: { frac: number; pnl: number }[];
  trades: Trade[];
  winRate: number;
  windowStart: number;
}

export function viewFor(bot: Bot, period: Period, samples = 180): RunView {
  const eq = equitySeries(bot);
  const len = PERIOD_LEN[period];
  const start = TOTAL - len;
  const step = Math.max(1, Math.floor(len / samples));
  let base = Number.NaN;
  for (let i = start; i < TOTAL; i++) {
    if (!Number.isNaN(eq[i])) {
      base = eq[i];
      break;
    }
  }
  const indices: number[] = [];
  for (let i = start; i < TOTAL; i += step) indices.push(i);
  if (indices[indices.length - 1] !== TOTAL - 1) indices.push(TOTAL - 1);
  const points = indices.map((i) => (Number.isNaN(eq[i]) ? Number.NaN : (eq[i] / base - 1) * 100));
  let peak = Number.NEGATIVE_INFINITY;
  let maxDD = 0;
  for (let i = start; i < TOTAL; i++) {
    if (Number.isNaN(eq[i])) continue;
    peak = Math.max(peak, eq[i]);
    maxDD = Math.min(maxDD, (eq[i] / peak - 1) * 100);
  }
  let overallPeak = Number.NEGATIVE_INFINITY;
  for (let i = bot.startIndex; i < TOTAL; i++) overallPeak = Math.max(overallPeak, eq[i]);
  const ddNow = (eq[TOTAL - 1] / overallPeak - 1) * 100;
  const ret = points[points.length - 1];
  const trades = tradesFor(bot).filter((t) => t.index >= start);
  const wins = trades.filter((t) => t.pnl > 0).length;
  return {
    points,
    indices,
    ret,
    pnl: (ret / 100) * bot.capital,
    maxDD,
    ddNow,
    markers: trades.map((t) => ({ frac: (t.index - start) / (len - 1), pnl: t.pnl })),
    trades,
    winRate: trades.length ? wins / trades.length : 0,
    windowStart: start,
  };
}

export const INITIAL_BOTS: Bot[] = [
  {
    id: 'tabby',
    name: 'Tabby',
    strategyId: 'breakout_v22',
    symbol: 'BTCUSDT',
    timeframe: '15m',
    status: 'running',
    seed: 22,
    drift: 0.000075,
    vol: 0.0009,
    guard: -8,
    startIndex: 0,
    capital: 10000,
  },
  {
    id: 'calico',
    name: 'Calico',
    strategyId: 'trend_follow',
    symbol: 'ETHUSDT',
    timeframe: '1h',
    status: 'running',
    seed: 27,
    drift: 0.000085,
    vol: 0.0010,
    guard: -8,
    startIndex: 0,
    decline: false,
    capital: 10000,
  },
  {
    id: 'mochi',
    name: 'Mochi',
    strategyId: 'grid_mm',
    symbol: 'SOLUSDT',
    timeframe: '5m',
    status: 'running',
    seed: 4,
    drift: 0.000045,
    vol: 0.0005,
    guard: -5,
    startIndex: 0,
    capital: 10000,
  },
  {
    id: 'shiro',
    name: 'Shiro',
    strategyId: 'pairs',
    symbol: 'BTC/ETH',
    timeframe: '1h',
    status: 'paused',
    seed: 5,
    drift: 0.000020,
    vol: 0.0007,
    guard: -6,
    startIndex: 0,
    pauseIndex: TOTAL - 190,
    capital: 10000,
  },
];

export const MARKETS = [
  { symbol: 'BTCUSDT', base: 'BTC', mark: 62140.5, chg: 1.84, digits: 1 },
  { symbol: 'ETHUSDT', base: 'ETH', mark: 2452.18, chg: 1.15, digits: 2 },
  { symbol: 'SOLUSDT', base: 'SOL', mark: 148.62, chg: 2.42, digits: 2 },
];
export const MARK: Record<string, number> = Object.fromEntries(MARKETS.map((m) => [m.symbol, m.mark]));

export function baseOf(symbol: string) {
  return MARKETS.find((m) => m.symbol === symbol)?.base ?? symbol;
}

export function formatPrice(v: number, symbol: string) {
  const d = MARKETS.find((m) => m.symbol === symbol)?.digits ?? 2;
  return v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
}

export function formatUsd(v: number, signed = false, digits = 2) {
  const abs = Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  const sign = v < 0 ? '−' : signed && v > 0 ? '+' : '';
  return `${sign}${abs}`;
}

export function toneOf(v: number) {
  return v > 0 ? 'text-gain' : v < 0 ? 'text-risk' : 'text-muted-foreground';
}

export interface Position {
  id: string;
  botId: string;
  symbol: string;
  side: 'long' | 'short';
  qty: number;
  entry: number;
  opened: string;
}

export const POSITIONS: Position[] = [
  { id: 'p1', botId: 'tabby', symbol: 'BTCUSDT', side: 'long', qty: 0.12, entry: 61480, opened: '04:30' },
  { id: 'p2', botId: 'calico', symbol: 'ETHUSDT', side: 'long', qty: 2.4, entry: 2390.0, opened: '10/5 06:00' },
  { id: 'p3', botId: 'mochi', symbol: 'SOLUSDT', side: 'long', qty: 18, entry: 143.20, opened: '09:04' },
  { id: 'p4', botId: 'shiro', symbol: 'BTCUSDT', side: 'long', qty: 0.05, entry: 61850, opened: '10/4 03:00' },
  { id: 'p5', botId: 'shiro', symbol: 'ETHUSDT', side: 'short', qty: 1.3, entry: 2515.0, opened: '10/4 03:00' },
];

export function positionMetrics(p: Position) {
  const mark = MARK[p.symbol] ?? (p.symbol === 'BTC/ETH' ? 25.34 : 100);
  const dir = p.side === 'long' ? 1 : -1;
  const notional = p.qty * mark;
  return {
    mark,
    notional,
    signed: notional * dir,
    upnl: (mark - p.entry) * p.qty * dir,
    upnlPct: (mark / p.entry - 1) * 100 * dir,
  };
}

export type PositionRow = Position & ReturnType<typeof positionMetrics>;

export interface OpenOrder {
  id: string;
  botId: string;
  symbol: string;
  side: 'buy' | 'sell';
  type: '限價' | '停損';
  price: number;
  qty: number;
  placed: string;
}

export const OPEN_ORDERS: OpenOrder[] = [
  { id: 'o1', botId: 'mochi', symbol: 'SOLUSDT', side: 'buy', type: '限價', price: 147.8, qty: 6, placed: '09:30' },
  { id: 'o2', botId: 'mochi', symbol: 'SOLUSDT', side: 'buy', type: '限價', price: 146.9, qty: 6, placed: '09:30' },
  { id: 'o3', botId: 'mochi', symbol: 'SOLUSDT', side: 'sell', type: '限價', price: 150.8, qty: 6, placed: '09:30' },
  { id: 'o4', botId: 'mochi', symbol: 'SOLUSDT', side: 'sell', type: '限價', price: 151.7, qty: 6, placed: '09:30' },
  { id: 'o5', botId: 'tabby', symbol: 'BTCUSDT', side: 'sell', type: '停損', price: 60560, qty: 0.12, placed: '09:15' },
  {
    id: 'o6',
    botId: 'calico',
    symbol: 'ETHUSDT',
    side: 'sell',
    type: '停損',
    price: 2350,
    qty: 2.4,
    placed: '10/5 06:00',
  },
];

export const LIMITS = { dailyLossPct: -2, accountDDPct: -10, grossLeverage: 1.5, concentrationPct: 40 };
export const TODAY_BARS = 39;

const accountCache = new Map<string, number[]>();

export function accountSeries(bots: Bot[]): number[] {
  const key = bots.map((b) => `${b.id}:${b.startIndex}:${b.pauseIndex ?? ''}`).join('|');
  const cached = accountCache.get(key);
  if (cached) return cached;
  const out = new Array<number>(TOTAL).fill(0);
  for (const b of bots) {
    const eq = equitySeries(b);
    for (let i = 0; i < TOTAL; i++) out[i] += Number.isNaN(eq[i]) ? b.capital : eq[i] * b.capital;
  }
  accountCache.set(key, out);
  return out;
}

export function botUsdSeries(bot: Bot): number[] {
  return equitySeries(bot).map((v) => v * bot.capital);
}

export interface SeriesView {
  indices: number[];
  points: number[];
  dd: number[];
  ret: number;
  pnl: number;
  maxDD: number;
  ddNow: number;
  baseIndex: number;
}

export function summarize(series: number[], period: Period, samples = 280): SeriesView {
  const len = PERIOD_LEN[period];
  const start = TOTAL - len;
  const step = Math.max(1, Math.floor(len / samples));
  let baseIndex = start;
  while (baseIndex < TOTAL && Number.isNaN(series[baseIndex])) baseIndex++;
  const base = series[baseIndex];
  const peakAt = new Array<number>(TOTAL);
  let peak = Number.NEGATIVE_INFINITY;
  for (let i = 0; i < TOTAL; i++) {
    if (!Number.isNaN(series[i])) peak = Math.max(peak, series[i]);
    peakAt[i] = peak;
  }
  const indices: number[] = [];
  for (let i = start; i < TOTAL; i += step) indices.push(i);
  if (indices[indices.length - 1] !== TOTAL - 1) indices.push(TOTAL - 1);
  const points = indices.map((i) => (Number.isNaN(series[i]) ? Number.NaN : (series[i] / base - 1) * 100));
  const dd = indices.map((i) => (Number.isNaN(series[i]) ? Number.NaN : (series[i] / peakAt[i] - 1) * 100));
  let maxDD = 0;
  let windowPeak = Number.NEGATIVE_INFINITY;
  for (let i = start; i < TOTAL; i++) {
    if (Number.isNaN(series[i])) continue;
    windowPeak = Math.max(windowPeak, series[i]);
    maxDD = Math.min(maxDD, (series[i] / windowPeak - 1) * 100);
  }
  const last = series[TOTAL - 1];
  return {
    indices,
    points,
    dd,
    ret: (last / base - 1) * 100,
    pnl: last - base,
    maxDD,
    ddNow: (last / peakAt[TOTAL - 1] - 1) * 100,
    baseIndex,
  };
}

export function positionsFor(bots: Bot[]): PositionRow[] {
  const ids = new Set(bots.map((b) => b.id));
  return POSITIONS.filter((p) => ids.has(p.botId)).map((p) => ({ ...p, ...positionMetrics(p) }));
}

export function accountSnapshot(bots: Bot[]) {
  const series = accountSeries(bots);
  const equity = series[TOTAL - 1];
  const dayStart = series[TOTAL - 1 - TODAY_BARS];
  const capital = bots.reduce((sum, b) => sum + b.capital, 0);
  const positions = positionsFor(bots);
  const upnl = positions.reduce((s, p) => s + p.upnl, 0);
  const gross = positions.reduce((s, p) => s + p.notional, 0);
  const longNotional = positions.filter((p) => p.side === 'long').reduce((s, p) => s + p.notional, 0);
  const shortNotional = gross - longNotional;
  const net = longNotional - shortNotional;
  const bySymbol = MARKETS.map((m) => {
    const legs = positions.filter((p) => p.symbol === m.symbol);
    const long = legs.filter((p) => p.side === 'long').reduce((s, p) => s + p.notional, 0);
    const short = legs.filter((p) => p.side === 'short').reduce((s, p) => s + p.notional, 0);
    return { ...m, legs, long, short, net: long - short };
  });
  let peak = 0;
  for (const v of series) peak = Math.max(peak, v);
  return {
    equity,
    capital,
    totalPnl: equity - capital,
    todayPnl: equity - dayStart,
    todayPct: (equity / dayStart - 1) * 100,
    upnl,
    realized: equity - capital - upnl,
    cash: equity - net,
    gross,
    net,
    longNotional,
    shortNotional,
    leverage: gross / equity,
    ddNow: (equity / peak - 1) * 100,
    bySymbol,
    maxConcentration: Math.max(...bySymbol.map((s) => (Math.abs(s.net) / equity) * 100)),
    positions,
  };
}

export interface Fill {
  id: string;
  botId: string;
  symbol: string;
  action: '平多' | '平空';
  qty: number;
  price: number;
  pnl: number;
  time: string;
  index: number;
}
const DEFAULT_QTY: Record<string, number> = { BTCUSDT: 0.12, ETHUSDT: 2.4, SOLUSDT: 6, 'BTC/ETH': 0.05 };

export function recentFills(bots: Bot[], count = 16): Fill[] {
  const out: Fill[] = [];
  for (const bot of bots) {
    const symbol = bot.symbol === 'BTC/ETH' ? 'BTCUSDT' : bot.symbol;
    const mark = MARK[symbol] ?? 100;
    for (const t of tradesFor(bot).slice(-8)) {
      out.push({
        id: `${bot.id}-${t.index}`,
        botId: bot.id,
        symbol,
        action: t.side === '多' ? '平多' : '平空',
        qty: DEFAULT_QTY[bot.symbol] ?? 1,
        price: mark * (1 + (t.price / mark - 1) * 0.6),
        pnl: t.pnl * 64,
        time: formatTime(timeAt(t.index), TOTAL - 1 - t.index > 38),
        index: t.index,
      });
    }
  }
  return out.sort((a, b) => b.index - a.index).slice(0, count);
}

export function todayChange(series: number[]) {
  const end = series[TOTAL - 1];
  const startRaw = series[TOTAL - 1 - TODAY_BARS];
  if (Number.isNaN(end)) return { pnl: 0, pct: 0 };
  const start = Number.isNaN(startRaw) ? (series.find((v) => !Number.isNaN(v)) ?? end) : startRaw;
  return { pnl: end - start, pct: (end / start - 1) * 100 };
}

export function todayTradeCount(bot: Bot) {
  return tradesFor(bot).filter((t) => t.index > TOTAL - 1 - TODAY_BARS).length;
}

export function lastSignal(bot: Bot) {
  const trades = tradesFor(bot);
  const last = trades[trades.length - 1];
  if (!last) return '—';
  return formatTime(timeAt(last.index), TOTAL - 1 - last.index > 38);
}

export interface DeskEvent {
  id: string;
  category: string;
  severity: 'high' | 'medium' | 'info';
  time: string;
  title: string;
  detail?: string;
  botId?: string;
  strategyId?: string;
  actionable: boolean;
}

export function deriveEvents(bots: Bot[]): DeskEvent[] {
  const out: DeskEvent[] = [];
  for (const bot of bots) {
    if (bot.status !== 'running') continue;
    const { ddNow } = viewFor(bot, '30D');
    if (ddNow <= bot.guard * 0.75) {
      out.push({
        id: `guard-${bot.id}`,
        category: '風控',
        severity: 'high',
        time: '即時',
        title: `${bot.name} 回撤 ${formatPct(ddNow, 1)}，距自動暫停線 ${bot.guard}% 剩 ${(ddNow - bot.guard).toFixed(1)}%`,
        detail: `${bot.symbol} ${bot.timeframe} · 觸線時自動暫停，持倉不會被平倉。`,
        botId: bot.id,
        actionable: true,
      });
    }
  }
  for (const bot of bots) {
    if (bot.status !== 'paused') continue;
    const legs = positionsFor([bot]);
    if (!legs.length) continue;
    const upnl = legs.reduce((s, p) => s + p.upnl, 0);
    out.push({
      id: `paused-${bot.id}`,
      category: '風控',
      severity: 'medium',
      time: bot.pauseIndex !== undefined ? `${Math.round(((TOTAL - 1 - bot.pauseIndex) * 15) / 60)}h 前` : '剛剛',
      title: `${bot.name} 已暫停，但仍持有 ${legs.length} 筆部位`,
      detail: `未實現 ${formatUsd(upnl, true)} USDT。暫停的機器人不會管理停損，部位仍計入帳戶曝險。`,
      botId: bot.id,
      actionable: true,
    });
  }
  out.push({
    id: 'mcp-sync',
    category: '策略',
    severity: 'info',
    time: '08:51',
    title: '外部 AI 經 MCP 寫入 breakout_v2.py v2.3',
    detail: 'Tabby 仍在執行你信任的 v2.2，不受影響。',
    strategyId: 'breakout_v23',
    actionable: false,
  });
  return out;
}

// Strategy & Pipeline Data
export type Stage = 'import' | 'review' | 'trusted' | 'assigned' | 'simulating' | 'results' | 'rejected';

export interface ReviewInfo {
  checks: { label: string; status: 'ok' | 'warn'; note?: string }[];
  diff: {
    type: ' ' | '+' | '-';
    text: string;
  }[];
  diffLabel: string;
  requiresAck?: boolean;
}

export interface Strategy {
  id: string;
  file: string;
  version: string;
  stage: Stage;
  origin: 'import' | 'mcp';
  summary: string;
  time?: string;
  attnDetail?: string;
  trustedSummary?: string;
  botId?: string;
  botName?: string;
  symbol?: string;
  timeframe?: string;
  result?: { ret: number; span: string; trades: number };
  review?: ReviewInfo;
}

export const STAGES: { key: Exclude<Stage, 'rejected'>; label: string; hint: string }[] = [
  { key: 'import', label: '匯入', hint: '解析 Python 檔' },
  { key: 'review', label: '檢查', hint: '靜態檢查與差異' },
  { key: 'trusted', label: '信任', hint: '核准可執行版本' },
  { key: 'assigned', label: '分配', hint: '綁定機器人' },
  { key: 'simulating', label: '模擬', hint: '本機模擬中' },
  { key: 'results', label: '成果', hint: '已完成的執行' }
];

export const GENERIC_CHECKS: ReviewInfo['checks'] = [
  { label: '只引用允許的模組（math, numpy, pandas 等）', status: 'ok' },
  { label: '沒有網路連線或檔案寫入', status: 'ok' },
  { label: '下單只經由 catos.api.order()', status: 'ok' }
];

export const INITIAL_STRATEGIES: Strategy[] = [
  {
    id: 'breakout_v23',
    file: 'breakout_v2.py',
    version: 'v2.3',
    stage: 'review',
    origin: 'mcp',
    time: '08:51',
    summary: '外部 AI 經 MCP 調整了 2 項參數',
    attnDetail: 'MCP 用戶端在 08:51 寫入 v2.3。Tabby 仍在執行你信任的 v2.2，不受影響。',
    trustedSummary: '已信任 · Tabby 仍執行 v2.2',
    symbol: 'BTCUSDT',
    timeframe: '15m',
    review: {
      checks: [
        ...GENERIC_CHECKS,
        {
          label: '30 天合成資料回測',
          status: 'ok',
          note: 'v2.3：+5.1%、最大回撤 −3.2% ｜ v2.2：+3.4%、最大回撤 −4.0%'
        }
      ],
      diffLabel: 'v2.2 → v2.3',
      diff: [
        { type: ' ', text: 'class Breakout(Strategy):' },
        { type: '-', text: '    lookback = 20' },
        { type: '+', text: '    lookback = 14' },
        { type: '-', text: '    stop_pct = 0.020' },
        { type: '+', text: '    stop_pct = 0.015' },
        { type: ' ', text: '    take_profit = 0.04' },
        { type: ' ', text: '' },
        { type: ' ', text: '    def on_bar(self, bar):' },
        { type: ' ', text: '        hi = self.history.high[-self.lookback:].max()' }
      ]
    }
  },
  {
    id: 'mean_revert',
    file: 'mean_revert_ob.py',
    version: 'v1.0',
    stage: 'review',
    origin: 'import',
    time: '昨天',
    summary: '靜態檢查有 1 項警告',
    attnDetail: '靜態檢查發現 1 項警告：第 3 行 import requests（網路模組）。',
    symbol: 'ETHUSDT',
    timeframe: '5m',
    review: {
      checks: [
        { label: '只引用允許的模組', status: 'warn', note: '第 3 行 import requests；目前未被呼叫，但具備網路能力。' },
        { label: '沒有檔案寫入', status: 'ok' },
        { label: '下單只經由 catos.api.order()', status: 'ok' }
      ],
      diffLabel: '新檔案 · 前 8 行',
      requiresAck: true,
      diff: [
        { type: '+', text: 'import numpy as np' },
        { type: '+', text: 'from catos.api import Strategy, order' },
        { type: '+', text: 'import requests' },
        { type: '+', text: '' },
        { type: '+', text: 'class MeanRevertOB(Strategy):' },
        { type: '+', text: '    window = 48' },
        { type: '+', text: '    z_entry = 2.2' },
        { type: '+', text: '    z_exit = 0.4' }
      ]
    }
  },
  {
    id: 'vol_squeeze',
    file: 'vol_squeeze.py',
    version: 'v0.4',
    stage: 'import',
    origin: 'import',
    summary: '解析完成，尚未檢查',
    symbol: 'SOLUSDT',
    timeframe: '15m',
    review: {
      checks: GENERIC_CHECKS,
      diffLabel: '新檔案 · 前 6 行',
      diff: [
        { type: '+', text: 'from catos.api import Strategy, order' },
        { type: '+', text: '' },
        { type: '+', text: 'class VolSqueeze(Strategy):' },
        { type: '+', text: '    bb_len = 20' },
        { type: '+', text: '    kc_mult = 1.5' },
        { type: '+', text: '    hold_bars = 12' }
      ]
    }
  },
  {
    id: 'rsi_div',
    file: 'rsi_divergence.py',
    version: 'v1.2',
    stage: 'trusted',
    origin: 'import',
    summary: '已信任，尚未分配機器人',
    symbol: 'BTCUSDT',
    timeframe: '1h'
  },
  {
    id: 'breakout_v22',
    file: 'breakout_v2.py',
    version: 'v2.2',
    stage: 'simulating',
    origin: 'import',
    summary: 'Tabby 模擬中',
    botId: 'tabby'
  },
  {
    id: 'trend_follow',
    file: 'trend_follow.py',
    version: 'v3.0',
    stage: 'simulating',
    origin: 'import',
    summary: 'Calico 模擬中',
    botId: 'calico'
  },
  {
    id: 'grid_mm',
    file: 'grid_mm.py',
    version: 'v1.4',
    stage: 'simulating',
    origin: 'import',
    summary: 'Mochi 模擬中',
    botId: 'mochi'
  },
  {
    id: 'pairs',
    file: 'pairs_btc_eth.py',
    version: 'v0.9',
    stage: 'simulating',
    origin: 'import',
    summary: 'Shiro 已暫停',
    botId: 'shiro'
  },
  {
    id: 'macd_cross',
    file: 'macd_cross.py',
    version: 'v1.1',
    stage: 'results',
    origin: 'import',
    summary: '30 天模擬已完成',
    result: { ret: -1.8, span: '30 天', trades: 41 }
  },
  {
    id: 'breakout_v21',
    file: 'breakout_v2.py',
    version: 'v2.1',
    stage: 'results',
    origin: 'import',
    summary: '14 天模擬已完成',
    result: { ret: 4.2, span: '14 天', trades: 63 }
  }
];

const STAGE_PRIORITY: Partial<Record<Stage, number>> = { review: 0, import: 1, trusted: 2 };

export function recommendedStrategy(strategies: Strategy[]): Strategy | undefined {
  return [...strategies]
    .filter((s) => s.stage in STAGE_PRIORITY)
    .sort((a, b) => {
      const d = (STAGE_PRIORITY[a.stage] ?? 99) - (STAGE_PRIORITY[b.stage] ?? 99);
      if (d !== 0) return d;
      return (a.origin === 'mcp' ? 0 : 1) - (b.origin === 'mcp' ? 0 : 1);
    })[0];
}

// Global Singleton State
const botsState = ref<Bot[]>([...INITIAL_BOTS]);
const strategiesState = ref<Strategy[]>([...INITIAL_STRATEGIES]);
const currentPeriod = ref<Period>('7D');
const focusBotId = ref<string | null>(null);
const selectedBotId = ref<string | null>(null);
const ackedEvents = ref<string[]>([]);
const activityTab = ref<'positions' | 'orders' | 'fills'>('positions');
const eventFilter = ref<'all' | 'action'>('all');

export function useV0Engine() {
  const snapshot = computed(() => accountSnapshot(botsState.value));
  const series = computed(() => accountSeries(botsState.value));
  const periodView = computed(() => summarize(series.value, currentPeriod.value));
  const events = computed(() => deriveEvents(botsState.value));
  const positions = computed(() => positionsFor(botsState.value));
  const fills = computed(() => recentFills(botsState.value));

  function setPeriod(p: Period) {
    currentPeriod.value = p;
  }

  function setFocusBot(id: string | null) {
    focusBotId.value = id;
  }

  function selectBot(id: string | null) {
    selectedBotId.value = id;
  }

  function togglePause(id: string) {
    const b = botsState.value.find((x) => x.id === id);
    if (!b) return;
    if (b.status === 'running') {
      b.status = 'paused';
      b.pauseIndex = TOTAL - 1;
    } else {
      b.status = 'running';
      delete b.pauseIndex;
    }
  }

  function pauseAll() {
    for (const b of botsState.value) {
      if (b.status === 'running') {
        b.status = 'paused';
        b.pauseIndex = TOTAL - 1;
      }
    }
  }

  function ackEvent(id: string) {
    if (!ackedEvents.value.includes(id)) {
      ackedEvents.value.push(id);
    }
  }

  function importStrategy(fileName: string) {
    const newStrat: Strategy = {
      id: 'import_' + Date.now(),
      file: fileName,
      version: 'v0.1',
      stage: 'import',
      origin: 'import',
      summary: '剛匯入的 Python 策略檔',
      time: '剛剛',
      review: {
        checks: GENERIC_CHECKS,
        diffLabel: '新檔案',
        diff: [
          { type: '+', text: 'from catos.api import Strategy, order' },
          { type: '+', text: `class UserStrategy_${Date.now().toString().slice(-4)}(Strategy):` },
          { type: '+', text: '    pass' }
        ]
      }
    };
    strategiesState.value.unshift(newStrat);
  }

  function updateStrategyStage(id: string, stage: Stage) {
    const st = strategiesState.value.find(s => s.id === id);
    if (st) {
      st.stage = stage;
    }
  }

  return {
    bots: botsState,
    strategies: strategiesState,
    period: currentPeriod,
    focusBotId,
    selectedBotId,
    ackedEvents,
    activityTab,
    eventFilter,
    snapshot,
    series,
    periodView,
    events,
    positions,
    fills,
    openOrders: OPEN_ORDERS,
    setPeriod,
    setFocusBot,
    selectBot,
    togglePause,
    pauseAll,
    ackEvent,
    importStrategy,
    updateStrategyStage,
  };
}
