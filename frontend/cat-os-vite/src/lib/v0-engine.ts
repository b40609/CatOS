/**
 * Mathematical Engine ported from CatOS Vue3 (SIM-01 Account & 1:1 Series Simulation)
 * Provides deterministic equity series, drawdowns, multi-period summaries, and account snapshot.
 */

export type Period = '24H' | '7D' | '30D';
export const PERIODS: Period[] = ['24H', '7D', '30D'];
export const PERIOD_LABEL: Record<Period, string> = {
  '24H': '過去 24 小時',
  '7D': '過去 7 天',
  '30D': '過去 30 天',
};
export const PERIOD_LEN: Record<Period, number> = { '24H': 96, '7D': 672, '30D': 2880 };
export const TOTAL = 2880;
const STEP_MS = 15 * 60 * 1000;
const NOW_MS = Date.UTC(2026, 9, 6, 1, 42);

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

export function formatUsd(v: number, withSign = false, decimals = 2) {
  if (Number.isNaN(v)) return '—';
  const sign = withSign && v > 0 ? '+' : withSign && v < 0 ? '−' : '';
  return `${sign}$${Math.abs(v).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

export function toneOf(v: number) {
  if (v > 0) return 'text-emerald-400 font-semibold';
  if (v < 0) return 'text-rose-400 font-semibold';
  return 'text-muted-foreground';
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

export interface Bot {
  id: string;
  name: string;
  strategyId: string;
  symbol: string;
  timeframe: string;
  status: 'running' | 'paused';
  seed: number;
  drift: number;
  vol: number;
  guard: number;
  startIndex: number;
  pauseIndex?: number;
  capital: number;
}

export const INITIAL_BOTS: Bot[] = [
  {
    id: 'tabby',
    name: 'Tabby',
    strategyId: 'breakout_v22',
    symbol: 'BTC-USDT-SWAP',
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
    symbol: 'ETH-USDT-SWAP',
    timeframe: '1h',
    status: 'running',
    seed: 27,
    drift: 0.000085,
    vol: 0.0010,
    guard: -8,
    startIndex: 0,
    capital: 10000,
  },
  {
    id: 'mochi',
    name: 'Mochi',
    strategyId: 'grid_mm',
    symbol: 'SOL-USDT-SWAP',
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
    symbol: 'BTC-USDT-SWAP',
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
    v *= 1 + bot.drift + bot.vol * gauss(r);
    peak = Math.max(peak, v);
    out[i] = v;
  }
  seriesCache.set(key, out);
  return out;
}

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
  const base = series[baseIndex] || 1;
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

export const TODAY_BARS = 39;

export function accountSnapshot(bots: Bot[] = INITIAL_BOTS) {
  const series = accountSeries(bots);
  const equity = series[TOTAL - 1];
  const capital = bots.reduce((sum, b) => sum + b.capital, 0);

  // Exact figures calibrated to match Vue 3 state ($47,855.08)
  const upnl = 422.24;
  const realized = 7432.84;
  const todayPnl = 109.97;
  const todayPct = 0.23;

  return {
    equity,
    capital,
    totalPnl: equity - capital,
    todayPnl,
    todayPct,
    upnl,
    realized,
    positionsCount: 5,
  };
}
