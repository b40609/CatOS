import { useState, useEffect, useMemo } from "react";
import { cn } from "@/lib/utils";
import { CardHeaderTitle } from "./card-header-title";
import { AlertTriangle } from "lucide-react";
import { PositionProtectionTable, type ProtectionMonitoringView } from './position-protection-table';
import { useLiveMarketStore } from "@/state/liveMarketStore";
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
  p6StopPrice: string;
  p6DistPct: string;
  p6Status: "ACTIVE" | "UPDATING" | "ALERT";
  p6Rounding: "向上取整" | "向下取整";
  protectedNotional: string;
  p6ActiveStopPrice?: string;
  p6TargetStopPrice?: string;
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

const DEFAULT_POSITIONS: PositionRow[] = [
  {
    id: "p1",
    botId: "tabby",
    botName: "Tabby",
    symbol: "BTC-USDT-SWAP",
    base: "BTC",
    side: "long",
    qty: "0.85",
    entry: "61,480.00",
    mark: "62,140.50",
    notional: "52,820",
    upnl: 561.43,
    upnlPct: 1.07,
    leverage: "3x 全倉 (cross)",
    opened: "04:30",
    liqPrice: "54,210.00",
    distLiqPct: "+12.7%",
    mmr: "0.40%",
    p6StopPrice: "59,500.00",
    p6DistPct: "-4.25%",
    p6Status: "ACTIVE",
    p6Rounding: "向上取整",
    protectedNotional: "$52,820",
  },
  {
    id: "p2",
    botId: "calico",
    botName: "Calico",
    symbol: "ETH-USDT-SWAP",
    base: "ETH",
    side: "long",
    qty: "9.50",
    entry: "3,320.00",
    mark: "3,375.20",
    notional: "32,060",
    upnl: 524.40,
    upnlPct: 1.66,
    leverage: "3x 全倉 (cross)",
    opened: "10/5 06:00",
    liqPrice: "2,980.00",
    distLiqPct: "+11.7%",
    mmr: "0.40%",
    p6StopPrice: "3,210.00",
    p6DistPct: "-4.89%",
    p6Status: "ACTIVE",
    p6Rounding: "向上取整",
    protectedNotional: "$32,060",
  },
  {
    id: "p3",
    botId: "mochi",
    botName: "Mochi",
    symbol: "SOL-USDT-SWAP",
    base: "SOL",
    side: "long",
    qty: "95.00",
    entry: "148.20",
    mark: "152.80",
    notional: "14,516",
    upnl: 437.00,
    upnlPct: 3.10,
    leverage: "3x 全倉 (cross)",
    opened: "08:15",
    liqPrice: "131.50",
    distLiqPct: "+13.9%",
    mmr: "0.50%",
    p6StopPrice: "142.00",
    p6DistPct: "-7.07%",
    p6Status: "UPDATING",
    p6Rounding: "向上取整",
    protectedNotional: "$14,516",
  },
];

const INITIAL_ORDERS: OrderRow[] = [
  {
    id: "order_calico_unknown_01",
    clientOrderId: "cat_calico_unknown_01",
    botId: "calico",
    botName: "Calico",
    symbol: "ETH-USDT-SWAP",
    side: "buy",
    type: "限價/市價增倉",
    price: "3,375.00",
    qty: "0.60",
    distPct: "0.00%",
    distTicks: "0 ticks",
    frozenMargin: "$474.75",
    notionalUsd: "$2,025",
    placed: "11:10:02",
    isUnknown: true,
    statusText: "UNKNOWN · 待對帳",
    detail: "11:10:02 回覆逾時；是否成交尚未確認。額度仍保留，禁止盲目重送。",
  },
  {
    id: "o3",
    clientOrderId: "cat_mochi_0733",
    botId: "mochi",
    botName: "Mochi",
    symbol: "SOL-USDT-SWAP",
    side: "sell",
    type: "限價",
    price: "155.80",
    qty: "10.0",
    distPct: "+1.96%",
    distTicks: "+30 ticks",
    frozenMargin: "$145.80",
    notionalUsd: "$1,558",
    placed: "09:30",
  },
  {
    id: "o4",
    clientOrderId: "cat_mochi_0734",
    botId: "mochi",
    botName: "Mochi",
    symbol: "SOL-USDT-SWAP",
    side: "buy",
    type: "限價",
    price: "146.90",
    qty: "6.0",
    distPct: "-3.86%",
    distTicks: "-54 ticks",
    frozenMargin: "$298.10",
    notionalUsd: "$881",
    placed: "09:30",
  },
];

export function ActivityPanel({ className, showHeader = true, monitoring }: ActivityPanelProps) {
  const { tickers } = useLiveMarketStore();
  const [tab, setTab] = useState<ActivityTab>("positions");
  const [orders, setOrders] = useState<OrderRow[]>(INITIAL_ORDERS);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [flashRows, setFlashRows] = useState<Record<string, "up" | "down">>({});

  // 模擬 Tick 波動微光跳動
  useEffect(() => {
    if (monitoring) return;
    const timer = setInterval(() => {
      const targetIdx = Math.floor(Math.random() * DEFAULT_POSITIONS.length);
      const isUp = Math.random() > 0.45;
      const targetPos = DEFAULT_POSITIONS[targetIdx];
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
  }, [monitoring]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 2500);
  };

  const handleCancelOrder = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const targetOrder = orders.find((o) => o.id === id);
    if (targetOrder?.isUnknown) {
      showToast("此委託處於 UNKNOWN 待對帳中；禁止手動撤銷或重送，須等待終態");
      return;
    }
    setOrders((prev) => prev.filter((o) => o.id !== id));
    showToast("已成功發出撤單請求");
  };

  const handleCancelAll = () => {
    if (orders.length === 0) return;
    // UNKNOWN 單受保護不隨意取消
    const remaining = orders.filter((o) => o.isUnknown);
    setOrders(remaining);
    showToast("已全撤在途限價委託 · UNKNOWN 待對帳單受保護保留");
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

    const btcNotional = 0.85 * btcMark;
    const btcUpnl = (btcMark - 61480.00) * 0.85;
    const btcUpnlPct = ((btcMark - 61480.00) / 61480.00) * 100;
    const btcDistLiq = ((btcMark - 54210.00) / btcMark) * 100;
    const btcP6Dist = ((59500.00 - btcMark) / btcMark) * 100;

    const ethNotional = 9.50 * ethMark;
    const ethUpnl = (ethMark - 3320.00) * 9.50;
    const ethUpnlPct = ((ethMark - 3320.00) / 3320.00) * 100;
    const ethDistLiq = ((ethMark - 2980.00) / ethMark) * 100;
    const ethP6Dist = ((3210.00 - ethMark) / ethMark) * 100;

    const solNotional = 95.00 * solMark;
    const solUpnl = (solMark - 148.20) * 95.00;
    const solUpnlPct = ((solMark - 148.20) / 148.20) * 100;
    const solDistLiq = ((solMark - 131.50) / solMark) * 100;
    const solP6Dist = ((142.00 - solMark) / solMark) * 100;

    return [
      {
        id: "p1",
        botId: "tabby",
        botName: "Tabby",
        symbol: "BTC-USDT-SWAP",
        base: "BTC",
        side: "long",
        qty: "0.85",
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
        p6StopPrice: "59,500.00",
        p6DistPct: `${btcP6Dist.toFixed(2)}%`,
        p6Status: "ACTIVE",
        p6Rounding: "向上取整",
        protectedNotional: `$${Math.round(btcNotional).toLocaleString("en-US")}`,
      },
      {
        id: "p2",
        botId: "calico",
        botName: "Calico",
        symbol: "ETH-USDT-SWAP",
        base: "ETH",
        side: "long",
        qty: "9.50",
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
        p6StopPrice: "3,210.00",
        p6DistPct: `${ethP6Dist.toFixed(2)}%`,
        p6Status: "ACTIVE",
        p6Rounding: "向上取整",
        protectedNotional: `$${Math.round(ethNotional).toLocaleString("en-US")}`,
      },
      {
        id: "p3",
        botId: "mochi",
        botName: "Mochi",
        symbol: "SOL-USDT-SWAP",
        base: "SOL",
        side: "long",
        qty: "95.00",
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
        p6StopPrice: "142.00",
        p6DistPct: `${solP6Dist.toFixed(2)}%`,
        p6Status: "UPDATING",
        p6Rounding: "向上取整",
        protectedNotional: `$${Math.round(solNotional).toLocaleString("en-US")}`,
      },
    ];
  }, [tickers]);

  const positionsData = liveDefaultPositions;

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {/* 1. 一體化 Header 與 2 Tab 切換開關 */}
      {showHeader && (
        <div className="flex items-center justify-between px-3 py-2 bg-secondary/50 border-b border-border/80 shrink-0">
          <CardHeaderTitle
            cardId="positions"
            title="持倉明細與在途委託"
            subtext={
              <div className="flex items-center gap-1.5 ml-1">
                <span className="flex items-center gap-1 text-[9px] font-mono px-1.5 py-0.2 rounded border text-emerald-400 bg-emerald-400/10 border-emerald-400/25">
                  <span className="size-1.5 rounded-full bg-emerald-400" />
                  P6 交易所端 100% 錨定
                </span>
              </div>
            }
          />

          <div className="flex items-center gap-1 bg-background/60 border border-border/60 rounded p-0.5">
            <button
              type="button"
              onClick={() => setTab("positions")}
              className={cn(
                "px-2 py-0.5 text-[10.5px] font-mono font-medium rounded transition-colors cursor-pointer",
                tab === "positions"
                  ? "bg-secondary text-primary border border-border font-semibold shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              持倉 ({positionsData.length})
            </button>

            <button
              type="button"
              onClick={() => setTab("orders")}
              className={cn(
                "px-2 py-0.5 text-[10.5px] font-mono font-medium rounded transition-colors cursor-pointer",
                tab === "orders"
                  ? "bg-secondary text-primary border border-border font-semibold shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              掛單 ({orders.length})
            </button>
          </div>
        </div>
      )}

      {/* 2. 內容展示區 */}
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-auto flex flex-col justify-between min-w-0 max-w-full">
        {monitoring ? <PositionProtectionTable {...monitoring} tab={tab} /> : <>
        {/* ================= Tab 1: 持倉明細 (原部位表 + P6 保護確認整合) ================= */}
        {tab === "positions" && (
          <table className="w-full text-left border-collapse table-auto min-w-[540px]">
            <thead className="border-b border-border/80 bg-background/40 text-[9.5px] font-mono text-muted-foreground sticky top-0 z-10 backdrop-blur-sm">
              <tr>
                <th className="py-2 pl-3 pr-1.5 font-medium">BOT / CONTRACT</th>
                <th className="px-1.5 font-medium">SIDE</th>
                <th className="px-1.5 text-right font-medium">SIZE / NOTIONAL</th>
                <th className="px-1.5 text-right font-medium">ENTRY / MARK</th>
                <th className="px-1.5 text-right font-medium">UNREALIZED PnL</th>
                <th className="px-1.5 text-right font-medium hidden sm:table-cell">預估強平 / 距爆倉</th>
                <th className="px-1.5 text-right font-medium">P6 災難停損 (OKX)</th>
                <th className="py-2 pr-3 pl-1.5 text-right font-medium hidden lg:table-cell">LEVERAGE</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40 text-xs">
              {positionsData.map((p) => {
                const flash = flashRows[p.id];
                const isPositive = p.upnl >= 0;

                return (
                  <tr
                    key={p.id}
                    className={cn(
                      "hover:bg-secondary/40 transition-all group",
                      flash === "up" && "flash-up",
                      flash === "down" && "flash-down"
                    )}
                  >
                    <td className="py-2 pl-3 pr-1.5">
                      <div className="flex flex-col">
                        <span className="text-[11px] font-bold text-foreground leading-tight">{p.symbol}</span>
                        <span className="text-[9px] text-muted-foreground leading-tight">{p.botName}</span>
                      </div>
                    </td>

                    <td className="px-1.5 py-2">
                      <span
                        className={cn(
                          "px-1 py-0.2 rounded text-[8.5px] font-bold",
                          p.side === "long" ? "bg-emerald-400/10 text-emerald-400" : "bg-rose-400/10 text-rose-400"
                        )}
                      >
                        {p.side === "long" ? "多" : "空"}
                      </span>
                    </td>

                    <td className="px-1.5 py-2 text-right font-mono">
                      <div className="flex flex-col items-end">
                        <span className="text-[10.5px] font-bold text-foreground leading-tight">{p.qty} {p.base}</span>
                        <span className="text-[9px] text-muted-foreground leading-tight flex items-center">
                          <NumberTicker value={Number(p.notional.replace(/,/g, ""))} decimals={0} prefix="$" />
                        </span>
                      </div>
                    </td>

                    <td className="px-1.5 py-2 text-right font-mono">
                      <div className="flex flex-col items-end">
                        <span className="text-[10.5px] font-medium text-foreground leading-tight">${p.entry}</span>
                        <span className="text-[9px] text-muted-foreground leading-tight flex items-center">
                          <NumberTicker value={Number(p.mark.replace(/,/g, ""))} decimals={2} prefix="$" />
                        </span>
                      </div>
                    </td>

                    <td className="px-1.5 py-2 text-right font-mono">
                      <div className="flex flex-col items-end">
                        <span className={cn("text-[10.5px] font-bold leading-tight flex items-center", isPositive ? "text-up" : "text-down")}>
                          {isPositive ? "+" : ""}<NumberTicker value={p.upnl} decimals={2} prefix="$" />
                        </span>
                        <span className={cn("text-[9px] leading-tight flex items-center", isPositive ? "text-up" : "text-down")}>
                          {isPositive ? "+" : ""}<NumberTicker value={p.upnlPct} decimals={2} suffix="%" />
                        </span>
                      </div>
                    </td>

                    <td className="px-1.5 py-2 text-right hidden sm:table-cell">
                      <div className="flex flex-col items-end font-mono">
                        <span className="text-[10px] text-foreground leading-tight">${p.liqPrice}</span>
                        <span className="text-[8.5px] text-emerald-400 font-semibold leading-tight flex items-center gap-0.5">
                          距爆倉 {p.distLiqPct}
                        </span>
                      </div>
                    </td>

                    {/* P6 災難停損 (OKX 交易所端) */}
                    <td className="px-1.5 py-2 text-right">
                      <div className="flex flex-col items-end">
                        <div className="flex items-center gap-1 font-mono">
                          <span className="text-[10.5px] text-primary font-bold leading-tight">
                            ${p.p6StopPrice}
                          </span>
                          <span className="text-[9px] text-amber-400/90 font-semibold">
                            ({p.p6DistPct})
                          </span>
                        </div>
                        <span className="text-[8.5px] text-emerald-400 font-mono leading-tight flex items-center gap-1 mt-0.5">
                          <span className="size-1 rounded-full bg-emerald-400" />
                          OKX {p.p6Rounding}
                        </span>
                      </div>
                    </td>

                    <td className="py-2 pr-3 pl-1.5 text-right hidden lg:table-cell">
                      <div className="flex flex-col items-end">
                        <span className="text-[9.5px] text-foreground font-semibold leading-tight">{p.leverage}</span>
                        <span className="text-[8.5px] text-emerald-400 leading-tight">Net Mode</span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}

        {/* ================= Tab 2: 當前掛單 (高密度盤口掛單 + UNKNOWN 待對帳單) ================= */}
        {tab === "orders" && (
          <div className="flex flex-col h-full justify-between">
            {orders.length === 0 ? (
              <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground font-mono">
                <span className="text-sm text-foreground font-bold">目前無在途掛單</span>
                <span className="text-[10px] text-muted-foreground mt-1">策略次根委託意圖觸發時將即時顯示於此</span>
              </div>
            ) : (
              <table className="w-full text-left border-collapse table-auto min-w-[620px]">
                <thead className="border-b border-border/80 bg-background/40 text-[9.5px] font-mono text-muted-foreground sticky top-0 z-10 backdrop-blur-sm">
                  <tr>
                    <th className="py-2 pl-3 pr-1.5 font-medium">BOT / CONTRACT</th>
                    <th className="px-1.5 font-medium">SIDE / TYPE</th>
                    <th className="px-1.5 text-right font-medium">PRICE</th>
                    <th className="px-1.5 text-right font-medium">QTY</th>
                    <th className="px-1.5 text-right font-medium">DIST (TICKS)</th>
                    <th className="px-1.5 text-right font-medium hidden sm:table-cell">FROZEN MARGIN</th>
                    <th className="py-2 pr-3 pl-1.5 text-right font-medium">ACTION / STATUS</th>
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
                            <span className="text-[9px] text-muted-foreground leading-tight">{o.botName} · {o.clientOrderId}</span>
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
                              {o.side === "buy" ? "買" : "賣"}
                            </span>
                            <span className="text-[9px] text-muted-foreground">{o.type}</span>
                          </div>
                        </td>

                        <td className="px-1.5 py-2 text-right font-bold text-foreground text-[10.5px]">${o.price}</td>
                        <td className="px-1.5 py-2 text-right text-muted-foreground text-[10px]">{o.qty}</td>
                        <td className="px-1.5 py-2 text-right text-[10px]">
                          {o.isUnknown ? (
                            <span className="text-amber-400 font-semibold">待對帳</span>
                          ) : (
                            <>
                              <span className="text-amber-400 font-semibold">{o.distPct}</span>
                              <span className="text-[8.5px] text-muted-foreground block">{o.distTicks}</span>
                            </>
                          )}
                        </td>
                        <td className="px-1.5 py-2 text-right text-[10.5px] font-semibold text-foreground hidden sm:table-cell">
                          {o.frozenMargin}
                        </td>
                        <td className="py-2 pr-3 pl-1.5 text-right">
                          {o.isUnknown ? (
                            <span
                              className="px-2 py-0.5 rounded text-[9px] font-bold text-amber-300 bg-amber-400/15 border border-amber-400/40 inline-flex items-center gap-1"
                              title={o.detail || "11:10:02 回覆逾時；額度保留待對帳"}
                            >
                              <AlertTriangle className="size-2.5" />
                              <span>UNKNOWN 待對帳</span>
                            </span>
                          ) : (
                            <button
                              type="button"
                              onClick={(e) => handleCancelOrder(o.id, e)}
                              className="px-1.5 py-0.5 rounded text-[9.5px] text-muted-foreground hover:text-rose-400 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/30 transition-all cursor-pointer"
                            >
                              撤單
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            )}

            {/* 掛單頁底部統計與控制 */}
            <div className="px-3 py-1.5 bg-secondary/60 border-t border-border/80 flex items-center justify-between text-[9.5px] font-mono text-muted-foreground shrink-0 mt-auto">
              <div className="flex items-center gap-2">
                <span>在途凍結: <strong className="text-foreground">${totalFrozen.toFixed(2)}</strong></span>
                <span className="text-border">|</span>
                <span>在途總額: <strong className="text-foreground">$5,464</strong></span>
                {toastMessage && (
                  <span className="text-amber-400 font-semibold bg-amber-500/10 px-1 rounded animate-in fade-in">
                    {toastMessage}
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={handleCancelAll}
                disabled={orders.filter(o => !o.isUnknown).length === 0}
                className={cn(
                  "px-2 py-0.5 rounded text-[9px] font-semibold transition-all cursor-pointer",
                  orders.filter(o => !o.isUnknown).length > 0
                    ? "text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30"
                    : "text-muted-foreground/40 cursor-not-allowed border border-transparent"
                )}
              >
                一鍵全撤在途限價單
              </button>
            </div>
          </div>
        )}
        </>}
      </div>
    </div>
  );
}
