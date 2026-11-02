import { useState, useEffect, useMemo } from "react";
import { cn } from "@/lib/utils";
import { CardHeaderTitle } from "./card-header-title";
import { AlertTriangle, Clock } from "lucide-react";
import { PositionProtectionTable, type ProtectionMonitoringView } from './position-protection-table';
import { useLiveMarketStore } from "@/state/liveMarketStore";
import { useBotLensStore } from "@/state/botLensStore";
import { NumberTicker } from "./motion/number-ticker";

export type ActivityTab = "positions" | "orders";

export interface PositionRow {
  id: string;
  botId: string;
  botName: string;
  symbol: string;
  base: string;
  side: "long" | "short";
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
  mmr: string;
  fundingIntervalHours: number;
  p6StopPrice: string;
  p6DistPct: string;
  p6Status: "ACTIVE" | "UPDATING" | "ALERT";
  p6Rounding: "向上取整" | "向下取整";
  protectedNotional: string;
}

export interface OrderRow {
  id: string;
  clientOrderId: string;
  botId: string;
  botName: string;
  symbol: string;
  side: "buy" | "sell";
  type: string;
  price: string;
  qty: string;
  distPct: string;
  distTicks: string;
  frozenMargin: string;
  notionalUsd: string;
  placed: string;
  isUnknown?: boolean;
  statusText?: string;
  detail?: string;
}

interface ActivityPanelProps {
  className?: string;
  showHeader?: boolean;
  monitoring?: ProtectionMonitoringView;
}

function getFundingCountdown(intervalHours: number) {
  const now = new Date();
  const msInInterval = intervalHours * 3600 * 1000;
  const nowMs = now.getTime();
  const nextSettle = Math.ceil(nowMs / msInInterval) * msInInterval;
  const diffMs = Math.max(0, nextSettle - nowMs);
  const h = Math.floor(diffMs / 3600000);
  const m = Math.floor((diffMs % 3600000) / 60000);
  const s = Math.floor((diffMs % 60000) / 1000);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

const DEFAULT_POSITIONS: PositionRow[] = [
  {
    id: "p1",
    botId: "tabby",
    botName: "BOT-BTC-15M",
    symbol: "BTC-USDT-SWAP",
    base: "BTC",
    side: "long",
    qty: "1.20",
    entry: "61,480.00",
    mark: "62,112.80",
    notional: "74,535",
    upnl: 759.36,
    upnlPct: 1.03,
    leverage: "3x 全倉 (cross)",
    opened: "04:30",
    liqPrice: "54,210.00",
    distLiqPct: "+12.7%",
    mmr: "0.40%",
    fundingIntervalHours: 8,
    p6StopPrice: "59,500.00",
    p6DistPct: "-4.21%",
    p6Status: "ACTIVE",
    p6Rounding: "向上取整",
    protectedNotional: "$74,535",
  },
  {
    id: "p2",
    botId: "calico",
    botName: "BOT-ETH-1H",
    symbol: "ETH-USDT-SWAP",
    base: "ETH",
    side: "long",
    qty: "13.50",
    entry: "3,320.00",
    mark: "3,371.50",
    notional: "45,515",
    upnl: 695.25,
    upnlPct: 1.55,
    leverage: "3x 全倉 (cross)",
    opened: "10/5 06:00",
    liqPrice: "2,980.00",
    distLiqPct: "+11.6%",
    mmr: "0.40%",
    fundingIntervalHours: 8,
    p6StopPrice: "3,210.00",
    p6DistPct: "-4.79%",
    p6Status: "ACTIVE",
    p6Rounding: "向上取整",
    protectedNotional: "$45,515",
  },
  {
    id: "p3",
    botId: "mochi",
    botName: "BOT-SOL-5M",
    symbol: "SOL-USDT-SWAP",
    base: "SOL",
    side: "long",
    qty: "135.00",
    entry: "148.20",
    mark: "152.40",
    notional: "20,574",
    upnl: 567.00,
    upnlPct: 2.83,
    leverage: "3x 全倉 (cross)",
    opened: "08:15",
    liqPrice: "131.50",
    distLiqPct: "+13.7%",
    mmr: "0.50%",
    fundingIntervalHours: 4,
    p6StopPrice: "142.00",
    p6DistPct: "-6.82%",
    p6Status: "UPDATING",
    p6Rounding: "向上取整",
    protectedNotional: "$20,574",
  },
];

const INITIAL_ORDERS: OrderRow[] = [
  {
    id: "order_calico_unknown_01",
    clientOrderId: "cat_eth_unknown_01",
    botId: "calico",
    botName: "BOT-ETH-1H",
    symbol: "ETH-USDT-SWAP",
    side: "buy",
    type: "限價/市價增倉",
    price: "3,371.50",
    qty: "0.80",
    distPct: "0.00%",
    distTicks: "0 ticks",
    frozenMargin: "$674.25",
    notionalUsd: "$2,697",
    placed: "11:10:02",
    isUnknown: true,
    statusText: "UNKNOWN · 待對帳",
    detail: "11:10:02 回覆逾時；0.80 ETH 增倉是否成交尚未確認。額度仍保留，禁止盲目重送。",
  },
  {
    id: "o3",
    clientOrderId: "cat_sol_0733",
    botId: "mochi",
    botName: "BOT-SOL-5M",
    symbol: "SOL-USDT-SWAP",
    side: "sell",
    type: "限價",
    price: "156.00",
    qty: "20.0",
    distPct: "+2.36%",
    distTicks: "+36 ticks",
    frozenMargin: "$208.00",
    notionalUsd: "$3,120",
    placed: "09:30",
  },
  {
    id: "o4",
    clientOrderId: "cat_sol_0734",
    botId: "mochi",
    botName: "BOT-SOL-5M",
    symbol: "SOL-USDT-SWAP",
    side: "buy",
    type: "限價",
    price: "148.20",
    qty: "15.0",
    distPct: "-2.76%",
    distTicks: "-42 ticks",
    frozenMargin: "$296.40",
    notionalUsd: "$2,223",
    placed: "09:30",
  },
];

export function ActivityPanel({ className, showHeader = true, monitoring }: ActivityPanelProps) {
  const { tickers } = useLiveMarketStore();
  const { activeLens } = useBotLensStore();

  const [tab, setTab] = useState<ActivityTab>("positions");
  const [orders, setOrders] = useState<OrderRow[]>(INITIAL_ORDERS);
  const [closedIds, setClosedIds] = useState<string[]>([]);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [flashRows, setFlashRows] = useState<Record<string, "up" | "down">>({});

  // 獨立動態倒數（方案 1：支援 OKX 多週期 8h / 4h）
  const [fundingCountdowns, setFundingCountdowns] = useState<Record<number, string>>({
    8: "05:08:07",
    4: "01:08:07",
  });

  useEffect(() => {
    const update = () => {
      setFundingCountdowns({
        8: getFundingCountdown(8),
        4: getFundingCountdown(4),
      });
    };
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, []);

  // 模擬 Tick 波動微光跳動
  useEffect(() => {
    if (monitoring) return;
    const timer = setInterval(() => {
      const activePositions = DEFAULT_POSITIONS.filter((p) => !closedIds.includes(p.id));
      if (activePositions.length === 0) return;
      const targetIdx = Math.floor(Math.random() * activePositions.length);
      const isUp = Math.random() > 0.45;
      const targetPos = activePositions[targetIdx];
      if (!targetPos) return;

      setFlashRows((prev) => ({ ...prev, [targetPos.id]: isUp ? "up" : "down" }));
      setTimeout(() => {
        setFlashRows((prev) => {
          const next = { ...prev };
          delete next[targetPos.id];
          return next;
        });
      }, 700);
    }, 2400);
    return () => clearInterval(timer);
  }, [monitoring, closedIds]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // 市價平倉操作
  const handleClosePosition = (p: PositionRow, e: React.MouseEvent) => {
    e.stopPropagation();
    setClosedIds((prev) => [...prev, p.id]);
    showToast(`已送出市價平倉委託: ${p.symbol} ${p.qty} ${p.base} (Supervisor 強制注入 tag: 41cb53c54d6dABDE)`);
  };

  const handleCancelOrder = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const targetOrder = orders.find((o) => o.id === id);
    if (targetOrder?.isUnknown) {
      showToast("此委託處於 UNKNOWN 待對帳中；禁止手動撤銷或重送，須等待終態");
      return;
    }
    setOrders((prev) => prev.filter((o) => o.id !== id));
    showToast("已移除展示委託；未發送撤單請求");
  };

  const handleCancelAll = () => {
    if (orders.length === 0) return;
    const remaining = orders.filter((o) => o.isUnknown);
    setOrders(remaining);
    showToast("已清除展示委託；保留 UNKNOWN，未發送撤單請求");
  };

  const totalFrozen = useMemo(() => {
    return orders.reduce((sum, o) => {
      const num = Number(o.frozenMargin.replace("$", "").replace(",", ""));
      return sum + (Number.isNaN(num) ? 0 : num);
    }, 0);
  }, [orders]);

  // 動態盤口掛單距離計算
  const ordersData = useMemo(() => {
    return orders.map((o) => {
      if (o.isUnknown) return o;
      if (o.symbol === "SOL-USDT-SWAP") {
        const orderPrice = Number(o.price);
        const solMark = tickers.SOL.price;
        const distPctVal = ((orderPrice - solMark) / solMark) * 100;
        const ticksVal = Math.round((orderPrice - solMark) / 0.1);
        return {
          ...o,
          distPct: `${distPctVal >= 0 ? "+" : ""}${distPctVal.toFixed(2)}%`,
          distTicks: `${ticksVal >= 0 ? "+" : ""}${ticksVal} ticks`,
        };
      }
      return o;
    });
  }, [orders, tickers]);

  // 動態部位計算（連動即時行情撮合引擎）
  const liveDefaultPositions: PositionRow[] = useMemo(() => {
    const btcMark = tickers.BTC.price;
    const ethMark = tickers.ETH.price;
    const solMark = tickers.SOL.price;

    const btcNotional = 1.20 * btcMark;
    const btcUpnl = (btcMark - 61480.00) * 1.20;
    const btcUpnlPct = ((btcMark - 61480.00) / 61480.00) * 100;
    const btcDistLiq = ((btcMark - 54210.00) / btcMark) * 100;
    const btcP6Dist = ((59500.00 - btcMark) / btcMark) * 100;

    const ethNotional = 13.50 * ethMark;
    const ethUpnl = (ethMark - 3320.00) * 13.50;
    const ethUpnlPct = ((ethMark - 3320.00) / 3320.00) * 100;
    const ethDistLiq = ((ethMark - 2980.00) / ethMark) * 100;
    const ethP6Dist = ((3210.00 - ethMark) / ethMark) * 100;

    const solNotional = 135.00 * solMark;
    const solUpnl = (solMark - 148.20) * 135.00;
    const solUpnlPct = ((solMark - 148.20) / 148.20) * 100;
    const solDistLiq = ((solMark - 131.50) / solMark) * 100;
    const solP6Dist = ((142.00 - solMark) / solMark) * 100;

    return [
      {
        id: "p1",
        botId: "tabby",
        botName: "BOT-BTC-15M",
        symbol: "BTC-USDT-SWAP",
        base: "BTC",
        side: "long",
        qty: "1.20",
        entry: "61,480.00",
        mark: btcMark.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
        notional: Math.round(btcNotional).toLocaleString("en-US"),
        upnl: btcUpnl,
        upnlPct: btcUpnlPct,
        leverage: "3x 全倉 (cross)",
        opened: "04:30",
        liqPrice: "54,210.00",
        distLiqPct: `+${btcDistLiq.toFixed(1)}%`,
        mmr: "0.40%",
        fundingIntervalHours: 8,
        p6StopPrice: "59,500.00",
        p6DistPct: `${btcP6Dist.toFixed(2)}%`,
        p6Status: "ACTIVE",
        p6Rounding: "向上取整",
        protectedNotional: `$${Math.round(btcNotional).toLocaleString("en-US")}`,
      },
      {
        id: "p2",
        botId: "calico",
        botName: "BOT-ETH-1H",
        symbol: "ETH-USDT-SWAP",
        base: "ETH",
        side: "long",
        qty: "13.50",
        entry: "3,320.00",
        mark: ethMark.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
        notional: Math.round(ethNotional).toLocaleString("en-US"),
        upnl: ethUpnl,
        upnlPct: ethUpnlPct,
        leverage: "3x 全倉 (cross)",
        opened: "10/5 06:00",
        liqPrice: "2,980.00",
        distLiqPct: `+${ethDistLiq.toFixed(1)}%`,
        mmr: "0.40%",
        fundingIntervalHours: 8,
        p6StopPrice: "3,210.00",
        p6DistPct: `${ethP6Dist.toFixed(2)}%`,
        p6Status: "ACTIVE",
        p6Rounding: "向上取整",
        protectedNotional: `$${Math.round(ethNotional).toLocaleString("en-US")}`,
      },
      {
        id: "p3",
        botId: "mochi",
        botName: "BOT-SOL-5M",
        symbol: "SOL-USDT-SWAP",
        base: "SOL",
        side: "long",
        qty: "135.00",
        entry: "148.20",
        mark: solMark.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
        notional: Math.round(solNotional).toLocaleString("en-US"),
        upnl: solUpnl,
        upnlPct: solUpnlPct,
        leverage: "3x 全倉 (cross)",
        opened: "08:15",
        liqPrice: "131.50",
        distLiqPct: `+${solDistLiq.toFixed(1)}%`,
        mmr: "0.50%",
        fundingIntervalHours: 4,
        p6StopPrice: "142.00",
        p6DistPct: `${solP6Dist.toFixed(2)}%`,
        p6Status: "UPDATING",
        p6Rounding: "向上取整",
        protectedNotional: `$${Math.round(solNotional).toLocaleString("en-US")}`,
      },
    ];
  }, [tickers]);

  const positionsData = liveDefaultPositions.filter((p) => !closedIds.includes(p.id));

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {/* 1. 一體化 Header 與純淨 Tab 切換 (徹底拔除全域誤導倒數) */}
      {showHeader && (
        <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
          <CardHeaderTitle
            cardId="positions"
            title="持倉明細與交易所風控"
          />

          <div className="flex items-center gap-0.5 bg-background/60 border border-border/60 rounded p-0.5 shrink-0 whitespace-nowrap flex-nowrap">
            <button
              type="button"
              onClick={() => setTab("positions")}
              className={cn(
                "px-2 py-0.5 text-[10.5px] font-mono rounded transition-colors cursor-pointer whitespace-nowrap shrink-0",
                tab === "positions"
                  ? "bg-secondary text-foreground font-semibold shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              持倉({positionsData.length})
            </button>
            <button
              type="button"
              onClick={() => setTab("orders")}
              className={cn(
                "px-2 py-0.5 text-[10.5px] font-mono rounded transition-colors inline-flex items-center gap-1 cursor-pointer whitespace-nowrap shrink-0",
                tab === "orders"
                  ? "bg-secondary text-foreground font-semibold shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <span className="whitespace-nowrap">掛單({orders.length})</span>
              {orders.some((o) => o.isUnknown) && (
                <span className="size-1.5 rounded-full bg-amber-400 animate-pulse" title="有 UNKNOWN 待對帳單" />
              )}
            </button>
          </div>
        </div>
      )}

      {/* 2. 內容展示區 */}
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-auto flex flex-col justify-between min-w-0 max-w-full">
        {monitoring ? <PositionProtectionTable {...monitoring} tab={tab} /> : <>
        {/* ================= Tab 1: 持倉明細 (方案 1 · 各合約獨立資金費率週期與倒數) ================= */}
        {tab === "positions" && (
          <table className="w-full text-left border-collapse table-auto min-w-[540px]">
            <thead className="border-b border-border/80 bg-background/40 text-[9.5px] font-mono text-muted-foreground sticky top-0 z-10 backdrop-blur-sm">
              <tr>
                <th className="py-2.5 pl-3 pr-2 font-medium">合約 / 部位</th>
                <th className="px-2 text-right font-medium">開倉 / 標記價</th>
                <th className="px-2 text-right font-medium">未實現損益</th>
                <th className="px-2 text-right font-medium hidden sm:table-cell">資金費率</th>
                <th className="px-2 text-right font-medium hidden md:table-cell">強平安全墊</th>
                <th className="px-2 text-right font-medium">交易所強制停損</th>
                <th className="py-2.5 pr-3 pl-2 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40 text-xs">
              {positionsData.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-muted-foreground font-mono text-xs">
                    目前無未平倉部位 (已全部平倉)
                  </td>
                </tr>
              ) : (
                positionsData.map((p) => {
                  const flash = flashRows[p.id];
                  const isPositive = p.upnl >= 0;
                  const roePct = p.upnlPct * 3; // 3x 槓桿保證金報酬率
                  const countdown = fundingCountdowns[p.fundingIntervalHours] ?? "05:08:07";
                  const isLensMatch =
                    (activeLens === "tabby" && p.base === "BTC") ||
                    (activeLens === "calico" && p.base === "ETH") ||
                    (activeLens === "mochi" && p.base === "SOL");
                  const isOtherLens =
                    (activeLens === "tabby" || activeLens === "calico" || activeLens === "mochi") && !isLensMatch;

                  return (
                      <tr
                        key={p.id}
                        className={cn(
                          "hover:bg-secondary/30 transition-all group",
                          isLensMatch && "bg-primary/[0.08] ring-1 ring-primary/40",
                          isOtherLens && "opacity-60",
                          flash === "up" && "flash-up",
                          flash === "down" && "flash-down"
                        )}
                      >
                      {/* 1. 合約標的 + 方向標籤 + 實質持倉 (一體化) */}
                      <td className="py-2.5 pl-3 pr-2">
                        <div className="flex flex-col">
                          <div className="flex items-center gap-1.5">
                            <span
                              className={cn(
                                "px-1 py-0.2 rounded text-[8.5px] font-bold font-mono inline-flex items-center",
                                p.side === "long" ? "bg-emerald-400/10 text-emerald-400 border border-emerald-400/25" : "bg-rose-400/10 text-rose-400 border border-rose-400/25"
                              )}
                            >
                              {p.side === "long" ? "▲ 多" : "▼ 空"}
                            </span>
                            <span className="text-[12px] font-bold text-foreground leading-tight">{p.symbol}</span>
                          </div>
                          <span className="text-[10px] font-mono text-muted-foreground leading-tight pl-0.5 mt-0.5">
                            {p.qty} {p.base}
                          </span>
                        </div>
                      </td>

                      {/* 2. 開倉均價與最新標記價 */}
                      <td className="px-2 py-2.5 text-right font-mono">
                        <div className="flex flex-col items-end">
                          <span className="text-[11px] font-medium text-foreground leading-tight">${p.entry}</span>
                          <span className="text-[9.5px] text-muted-foreground leading-tight mt-0.5">
                            $<NumberTicker value={Number(p.mark.replace(/,/g, ""))} decimals={2} />
                          </span>
                        </div>
                      </td>

                      {/* 3. 未實現損益 (金額 + ROE) */}
                      <td className="px-2 py-2.5 text-right font-mono">
                        <div className="flex flex-col items-end">
                          <span className={cn("text-[12px] font-bold leading-tight flex items-center", isPositive ? "text-emerald-400" : "text-rose-400")}>
                            {isPositive ? "+" : ""}<NumberTicker value={p.upnl} decimals={2} prefix="$" />
                          </span>
                          <span className={cn("text-[9.5px] font-bold leading-tight mt-0.5", isPositive ? "text-emerald-400" : "text-rose-400")}>
                            +{roePct.toFixed(2)}% ROE
                          </span>
                        </div>
                      </td>

                      {/* 4. 資金費率 (方案 1 · 獨立合約週期 8h/4h + 專屬動態倒數) */}
                      <td className="px-2 py-2.5 text-right hidden sm:table-cell font-mono">
                        <div className="flex flex-col items-end">
                          <span
                            className={cn(
                              "px-1.5 py-0.2 rounded text-[9.5px] font-bold leading-tight inline-block",
                              p.base === "SOL"
                                ? "bg-rose-400/10 text-rose-400 border border-rose-400/25"
                                : "bg-emerald-400/10 text-emerald-400 border border-emerald-400/25"
                            )}
                          >
                            {p.base === "SOL" ? "-0.0031%" : p.base === "ETH" ? "+0.0084%" : "+0.0102%"}
                          </span>
                          <span className={cn(
                            "text-[8.5px] leading-tight mt-0.5 font-mono inline-flex items-center gap-1",
                            p.fundingIntervalHours === 4 ? "text-amber-400 font-semibold" : "text-muted-foreground"
                          )}>
                            <Clock className="size-2 text-primary/70 shrink-0" />
                            <span>{p.fundingIntervalHours}h ({countdown})</span>
                          </span>
                        </div>
                      </td>

                      {/* 5. 強平安全墊 (價格 + 距離) */}
                      <td className="px-2 py-2.5 text-right hidden md:table-cell font-mono">
                        <div className="flex flex-col items-end">
                          <span className="text-[11px] text-foreground font-semibold leading-tight">${p.liqPrice}</span>
                          <span className="text-[9.5px] text-emerald-400 font-semibold leading-tight mt-0.5">
                            安全 ({p.distLiqPct})
                          </span>
                        </div>
                      </td>

                      {/* 6. 交易所停損 (純淨價格 + 距離標籤) */}
                      <td className="px-2 py-2.5 text-right font-mono">
                        <div className="flex flex-col items-end">
                          <span className="text-[11px] text-foreground font-bold leading-tight">
                            ${p.p6StopPrice}
                          </span>
                          <span className={cn("text-[9.5px] font-semibold mt-0.5", p.p6Status === "ACTIVE" ? "text-emerald-400" : "text-amber-400")}>
                            {p.p6Status === "ACTIVE" ? `已掛載 (${p.p6DistPct})` : "更新待確認"}
                          </span>
                        </div>
                      </td>

                      {/* 7. 操作出口：單筆市價平倉 */}
                      <td className="py-2.5 pr-3 pl-2 text-right font-mono">
                        <div className="flex items-center justify-end">
                          <button
                            type="button"
                            onClick={(e) => handleClosePosition(p, e)}
                            className="px-2.5 py-0.5 rounded text-[10px] font-mono border border-rose-500/30 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 hover:border-rose-500/50 transition-all cursor-pointer"
                            title="以市價緊急平倉此合約部位 (注入 OKX tag: 41cb53c54d6dABDE)"
                          >
                            平倉
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        )}

        {/* ================= Tab 2: 在途掛單 (保留 UNKNOWN 保護) ================= */}
        {tab === "orders" && (
          ordersData.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
              <span className="text-xs font-mono">當前無任何在途掛單</span>
              <span className="text-[10px] font-mono text-muted-foreground/60 mt-1">所有限價單均已成交或取消</span>
            </div>
          ) : (
            <table className="w-full text-left border-collapse table-auto min-w-[540px]">
              <thead className="border-b border-border/80 bg-background/40 text-[9.5px] font-mono text-muted-foreground sticky top-0 z-10 backdrop-blur-sm">
                <tr>
                  <th className="py-2.5 pl-3 pr-1.5 font-medium">合約標的</th>
                  <th className="px-1.5 font-medium">方向 / 類型</th>
                  <th className="px-1.5 text-right font-medium">委託價格</th>
                  <th className="px-1.5 text-right font-medium">委託數量</th>
                  <th className="px-1.5 text-right font-medium">距離 (Ticks)</th>
                  <th className="px-1.5 text-right font-medium hidden sm:table-cell">凍結保證金</th>
                  <th className="py-2.5 pr-3 pl-1.5 text-right font-medium">操作 / 狀態</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40 text-xs font-mono">
                {ordersData.map((o) => (
                  <tr
                    key={o.id}
                    className={cn(
                      "hover:bg-secondary/40 transition-all group",
                      o.isUnknown && "bg-amber-500/[0.04]"
                    )}
                  >
                    <td className="py-2 pl-3 pr-1.5">
                      <div className="flex flex-col">
                        <span className="text-[11px] font-bold text-foreground leading-tight">{o.symbol}</span>
                        <span className="text-[9px] text-muted-foreground leading-tight">{o.clientOrderId}</span>
                      </div>
                    </td>

                    <td className="px-1.5 py-2">
                      <div className="flex items-center gap-1">
                        <span
                          className={cn(
                            "px-1 py-0.2 rounded text-[8.5px] font-bold",
                            o.side === "buy" ? "bg-emerald-400/10 text-emerald-400" : "bg-rose-400/10 text-rose-400"
                          )}
                        >
                          {o.side === "buy" ? "買入" : "賣出"}
                        </span>
                        <span className="text-[9.5px] text-muted-foreground">{o.type}</span>
                      </div>
                    </td>

                    <td className="px-1.5 py-2 text-right">
                      <span className="text-[10.5px] font-bold text-foreground">${o.price}</span>
                    </td>

                    <td className="px-1.5 py-2 text-right">
                      <span className="text-[10.5px] font-bold text-foreground">{o.qty}</span>
                    </td>

                    <td className="px-1.5 py-2 text-right">
                      <div className="flex flex-col items-end">
                        <span className="text-[10px] text-primary font-bold leading-tight">{o.distPct}</span>
                        <span className="text-[8.5px] text-muted-foreground leading-tight">{o.distTicks}</span>
                      </div>
                    </td>

                    <td className="px-1.5 py-2 text-right hidden sm:table-cell">
                      <div className="flex flex-col items-end">
                        <span className="text-[10px] text-foreground font-semibold leading-tight">{o.frozenMargin}</span>
                        <span className="text-[8.5px] text-muted-foreground leading-tight">{o.notionalUsd}</span>
                      </div>
                    </td>

                    <td className="py-2 pr-3 pl-1.5 text-right">
                      {o.isUnknown ? (
                        <div className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-[9px] font-bold text-amber-300">
                          <AlertTriangle className="size-2.5" />
                          <span>待對帳 (禁撤)</span>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={(e) => handleCancelOrder(o.id, e)}
                          className="px-2 py-0.5 rounded text-[9.5px] font-mono border border-border/80 bg-background/60 text-muted-foreground hover:text-foreground hover:bg-secondary transition-all cursor-pointer"
                        >
                          撤單
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
        </>}

        {/* 底部摘要與模式說明條 */}
        <div className="flex items-center justify-between px-3 py-1.5 border-t border-border/80 bg-secondary/30 text-[10px] font-mono text-muted-foreground shrink-0">
          {tab === "positions" ? (
            <div className="flex items-center gap-3">
              <span>持倉筆數: <strong className="text-foreground">{positionsData.length}</strong></span>
              <span className="text-border">|</span>
              <span>帳戶保證金模式: <strong className="text-emerald-400">3x cross (全倉) + net_mode</strong></span>
              <span className="text-border">|</span>
              <span>緊急處置: <strong className="text-rose-400">支援單筆市價平倉 (注入專屬 tag)</strong></span>
            </div>
          ) : (
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center gap-2">
                <span>在途凍結總保證金: <strong className="text-primary font-bold">${totalFrozen.toLocaleString()}</strong></span>
                {orders.some((o) => o.isUnknown) && (
                  <span className="text-amber-400 flex items-center gap-1 font-semibold">
                    · 含 UNKNOWN 鎖存委託，禁止盲目撤銷重送
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={handleCancelAll}
                className="px-2 py-0.5 rounded text-[9.5px] border border-border/80 bg-background/80 hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                撤銷常規掛單 (保留待對帳)
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 微型 Toast 訊息反饋 */}
      {toastMessage && (
        <div className="absolute bottom-10 right-4 z-50 rounded border border-primary/40 bg-background/95 px-3 py-2 text-xs font-mono text-foreground shadow-lg backdrop-blur-md animate-in fade-in slide-in-from-bottom-2 duration-150 flex items-center gap-2">
          <span className="size-2 rounded-full bg-primary animate-ping" />
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
}
