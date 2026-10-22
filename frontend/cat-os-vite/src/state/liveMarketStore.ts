import { create } from "zustand";
import { MARKET_TAPE_10M } from "@/lib/mock/market-tape-10m";

export interface BotLiveState {
  symbol: string;
  markPrice: number;
  entryPrice: number;
  qty: number;
  upnl: number;
  upnlPct: number;
  notional: number;
  lastDir: "up" | "down";
  p6DistPct: string;
}

export interface MarketQuote {
  symbol: string;
  code: string;
  price: number;
  change24h: number;
  high24h: number;
  low24h: number;
  funding: number;
  spreadBps: number;
  lastDir: "up" | "down";
}

interface LiveMarketState {
  isRunning: boolean;
  tickCount: number;
  lastUpdated: string;
  fundingCountdownSeconds: number;

  // 10 分鐘微觀行情循環帶 (600 秒真實行情回放)
  tapeIndex: number;
  tapeLength: number;
  tapeProgress: string;

  // 4 大標的即時行情
  quotes: Record<string, MarketQuote>;
  tickers: Record<string, MarketQuote>; // 別名

  // 帳戶整體資產與風控
  equity: number;
  totalEquity: number; // 別名
  todayPnl: number;
  todayPct: number;
  totalUpnl: number;
  realized: number;
  effectiveLeverage: number;
  totalNotional: number;
  totalHoldingsNominal: number; // 3 大持倉名義價值加總
  lastEquityDir: "up" | "down";

  // 曝險分配 (Donut & Bars)
  btcNotional: number;
  ethNotional: number;
  solNotional: number;
  inFlightNotional: number;
  availableBudget: number;

  // 各機器人動態狀態
  botsLive: Record<string, BotLiveState>;

  // Actions
  toggleRunning: () => void;
  triggerManualTick: () => void;
  seekTape: (index: number) => void;
  resetTape: () => void;
  decrementCountdown: () => void;
}

const INITIAL_BASE_EQUITY = 48550.00;
const INITIAL_TODAY_BASE = 1522.80;
const INITIAL_REALIZED = 7432.84;
const P6_STOP_BTC = 59500.0;
const P6_STOP_ETH = 3210.0;
const P6_STOP_SOL = 142.0;

export const useLiveMarketStore = create<LiveMarketState>((set, get) => {
  const p0 = MARKET_TAPE_10M[0]!;

  const calcP6Dist = (mark: number, stop: number) => {
    if (stop <= 0) return "無持倉";
    const diff = ((stop - mark) / mark) * 100;
    return `${diff >= 0 ? "+" : ""}${diff.toFixed(2)}%`;
  };

  const calcBot = (symbol: string, mark: number, entry: number, qty: number, stop: number, dir: "up" | "down"): BotLiveState => {
    const upnl = Number(((mark - entry) * qty).toFixed(2));
    const upnlPct = Number((((mark - entry) / entry) * 100).toFixed(2));
    const notional = Number((mark * qty).toFixed(0));
    const p6DistPct = calcP6Dist(mark, stop);
    return { symbol, markPrice: mark, entryPrice: entry, qty, upnl, upnlPct, notional, lastDir: dir, p6DistPct };
  };

  // 依據 CatOS 5 萬刀帳戶標準分配：Tabby (BTC 0.85)、Calico (ETH 9.50)、Mochi (SOL 95.00)
  const initialBots: Record<string, BotLiveState> = {
    tabby: calcBot("BTC-USDT-SWAP", p0.btc, 61480.0, 0.85, P6_STOP_BTC, "up"),
    calico: calcBot("ETH-USDT-SWAP", p0.eth, 3320.0, 9.50, P6_STOP_ETH, "up"),
    mochi: calcBot("SOL-USDT-SWAP", p0.sol, 148.2, 95.0, P6_STOP_SOL, "up"),
    shiro: calcBot("BTC-USDT-SWAP", p0.btc, 0, 0, 0, "up"),
  };

  const initialUpnl = initialBots.tabby.upnl + initialBots.calico.upnl + initialBots.mochi.upnl;
  const initialNotional = initialBots.tabby.notional + initialBots.calico.notional + initialBots.mochi.notional;
  const initialInFlight = 5578.0; // 限價委託在途凍結

  const initialQuotes: Record<string, MarketQuote> = {
    BTC: {
      symbol: "BTC-USDT-SWAP",
      code: "BTC",
      price: p0.btc,
      change24h: p0.btcChg,
      high24h: 62850.0,
      low24h: 61120.0,
      funding: 0.0102,
      spreadBps: p0.spreadBps,
      lastDir: "up",
    },
    ETH: {
      symbol: "ETH-USDT-SWAP",
      code: "ETH",
      price: p0.eth,
      change24h: p0.ethChg,
      high24h: 3440.0,
      low24h: 3280.0,
      funding: 0.0084,
      spreadBps: p0.spreadBps,
      lastDir: "up",
    },
    SOL: {
      symbol: "SOL-USDT-SWAP",
      code: "SOL",
      price: p0.sol,
      change24h: p0.solChg,
      high24h: 156.5,
      low24h: 146.2,
      funding: -0.0031,
      spreadBps: p0.spreadBps,
      lastDir: "down",
    },
    DOGE: {
      symbol: "DOGE-USDT-SWAP",
      code: "DOGE",
      price: p0.doge,
      change24h: p0.dogeChg,
      high24h: 0.181,
      low24h: 0.165,
      funding: 0.0148,
      spreadBps: p0.spreadBps,
      lastDir: "up",
    },
  };

  const computeStateForIndex = (index: number, prevIndex: number, currentTickCount: number) => {
    const point = MARKET_TAPE_10M[index]!;
    const prevPoint = MARKET_TAPE_10M[prevIndex]!;

    const btcDelta = point.btc - prevPoint.btc;
    const ethDelta = point.eth - prevPoint.eth;
    const solDelta = point.sol - prevPoint.sol;
    const dogeDelta = point.doge - prevPoint.doge;

    const btcDir: "up" | "down" = btcDelta >= 0 ? "up" : "down";
    const ethDir: "up" | "down" = ethDelta >= 0 ? "up" : "down";
    const solDir: "up" | "down" = solDelta >= 0 ? "up" : "down";
    const dogeDir: "up" | "down" = dogeDelta >= 0 ? "up" : "down";

    const tabby = calcBot("BTC-USDT-SWAP", point.btc, 61480.0, 0.85, P6_STOP_BTC, btcDir);
    const calico = calcBot("ETH-USDT-SWAP", point.eth, 3320.0, 9.50, P6_STOP_ETH, ethDir);
    const mochi = calcBot("SOL-USDT-SWAP", point.sol, 148.2, 95.0, P6_STOP_SOL, solDir);
    const shiro = calcBot("BTC-USDT-SWAP", point.btc, 0, 0, 0, "up");

    const newTotalUpnl = Number((tabby.upnl + calico.upnl + mochi.upnl).toFixed(2));
    const newTotalNotional = tabby.notional + calico.notional + mochi.notional;
    const upnlDelta = newTotalUpnl - initialUpnl;

    const newEquity = Number((INITIAL_BASE_EQUITY + upnlDelta).toFixed(2));
    const newTodayPnl = Number((INITIAL_TODAY_BASE + upnlDelta).toFixed(2));
    const newTodayPct = Number(((newTodayPnl / (INITIAL_BASE_EQUITY - INITIAL_TODAY_BASE)) * 100).toFixed(2));
    const newLeverage = Number(((newTotalNotional + initialInFlight) / newEquity).toFixed(2));
    const newAvailableBudget = Number((newEquity * 3.0 - newTotalNotional - initialInFlight).toFixed(0));

    const newQuotes: Record<string, MarketQuote> = {
      BTC: {
        symbol: "BTC-USDT-SWAP",
        code: "BTC",
        price: point.btc,
        change24h: point.btcChg,
        high24h: 62850.0,
        low24h: 61120.0,
        funding: 0.0102,
        spreadBps: point.spreadBps,
        lastDir: btcDir,
      },
      ETH: {
        symbol: "ETH-USDT-SWAP",
        code: "ETH",
        price: point.eth,
        change24h: point.ethChg,
        high24h: 3440.0,
        low24h: 3280.0,
        funding: 0.0084,
        spreadBps: point.spreadBps,
        lastDir: ethDir,
      },
      SOL: {
        symbol: "SOL-USDT-SWAP",
        code: "SOL",
        price: point.sol,
        change24h: point.solChg,
        high24h: 156.5,
        low24h: 146.2,
        funding: -0.0031,
        spreadBps: point.spreadBps,
        lastDir: solDir,
      },
      DOGE: {
        symbol: "DOGE-USDT-SWAP",
        code: "DOGE",
        price: point.doge,
        change24h: point.dogeChg,
        high24h: 0.181,
        low24h: 0.165,
        funding: 0.0148,
        spreadBps: point.spreadBps,
        lastDir: dogeDir,
      },
    };

    const minPart = Math.floor(index / 60).toString().padStart(2, "0");
    const secPart = (index % 60).toString().padStart(2, "0");
    const progress = `${minPart}:${secPart} / 10:00`;

    return {
      tickCount: currentTickCount + 1,
      tapeIndex: index,
      tapeProgress: progress,
      lastUpdated: point.time,
      quotes: newQuotes,
      tickers: newQuotes,
      equity: newEquity,
      totalEquity: newEquity,
      todayPnl: newTodayPnl,
      todayPct: newTodayPct,
      totalUpnl: newTotalUpnl,
      effectiveLeverage: newLeverage,
      totalNotional: newTotalNotional,
      totalHoldingsNominal: newTotalNotional,
      lastEquityDir: upnlDelta >= 0 ? ("up" as const) : ("down" as const),

      btcNotional: tabby.notional,
      ethNotional: calico.notional,
      solNotional: mochi.notional,
      availableBudget: newAvailableBudget,

      botsLive: { tabby, calico, mochi, shiro },
    };
  };

  return {
    isRunning: true,
    tickCount: 0,
    lastUpdated: p0.time,
    fundingCountdownSeconds: 13155, // 03:39:15

    tapeIndex: 0,
    tapeLength: MARKET_TAPE_10M.length,
    tapeProgress: "00:00 / 10:00",

    quotes: initialQuotes,
    tickers: initialQuotes,

    equity: INITIAL_BASE_EQUITY,
    totalEquity: INITIAL_BASE_EQUITY,
    todayPnl: INITIAL_TODAY_BASE,
    todayPct: Number(((INITIAL_TODAY_BASE / INITIAL_BASE_EQUITY) * 100).toFixed(2)),
    totalUpnl: initialUpnl,
    realized: INITIAL_REALIZED,
    effectiveLeverage: Number(((initialNotional + initialInFlight) / INITIAL_BASE_EQUITY).toFixed(2)),
    totalNotional: initialNotional,
    totalHoldingsNominal: initialNotional,
    lastEquityDir: "up",

    btcNotional: initialBots.tabby.notional,
    ethNotional: initialBots.calico.notional,
    solNotional: initialBots.mochi.notional,
    inFlightNotional: initialInFlight,
    availableBudget: Number((INITIAL_BASE_EQUITY * 3.0 - initialNotional - initialInFlight).toFixed(0)),

    botsLive: initialBots,

    toggleRunning: () => {
      set((s) => ({ isRunning: !s.isRunning }));
    },

    decrementCountdown: () => {
      set((s) => ({
        fundingCountdownSeconds: s.fundingCountdownSeconds > 0 ? s.fundingCountdownSeconds - 1 : 28800,
      }));
    },

    triggerManualTick: () => {
      const state = get();
      if (!state.isRunning) return;
      const nextIndex = (state.tapeIndex + 1) % MARKET_TAPE_10M.length;
      set(computeStateForIndex(nextIndex, state.tapeIndex, state.tickCount));
    },

    seekTape: (index: number) => {
      const state = get();
      const safeIndex = Math.max(0, Math.min(MARKET_TAPE_10M.length - 1, index));
      set(computeStateForIndex(safeIndex, state.tapeIndex, state.tickCount));
    },

    resetTape: () => {
      const state = get();
      set(computeStateForIndex(0, state.tapeIndex, state.tickCount));
    },
  };
});

