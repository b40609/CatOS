import { useState, useEffect, useMemo } from "react";
import { cn } from "@/lib/utils";
import { CardHeaderTitle } from "./card-header-title";
import { ShieldCheck } from "lucide-react";

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
}

export interface OrderRow {
  id: string;
  clientOrderId: string;
  botId: string;
  botName: string;
  symbol: string;
  side: "buy" | "sell";
  type: "限價" | "停損" | "POST_ONLY";
  price: string;
  qty: string;
  distPct: string;
  distTicks: string;
  frozenMargin: string;
  notionalUsd: string;
  placed: string;
}

interface ActivityPanelProps {
  className?: string;
  showHeader?: boolean;
}

const DEFAULT_POSITIONS: PositionRow[] = [
  {
    id: "p1",
    botId: "tabby",
    botName: "Tabby",
    symbol: "BTC-USDT-SWAP",
    base: "BTC",
    side: "long",
    qty: "0.12",
    entry: "61,480.00",
    mark: "62,140.50",
    notional: "7,457",
    upnl: 79.26,
    upnlPct: 1.06,
    leverage: "3x 全倉 (cross)",
    opened: "04:30",
    liqPrice: "54,210.00",
    distLiqPct: "+12.7%",
    mmr: "0.40%",
    p6StopPrice: "59,500.00",
    p6DistPct: "-4.24%",
    p6Status: "ACTIVE",
    p6Rounding: "向上取整",
    protectedNotional: "$7,457",
  },
  {
    id: "p2",
    botId: "calico",
    botName: "Calico",
    symbol: "ETH-USDT-SWAP",
    base: "ETH",
    side: "long",
    qty: "2.40",
    entry: "3,320.00",
    mark: "3,375.20",
    notional: "5,880",
    upnl: 132.48,
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
    protectedNotional: "$5,880",
  },
  {
    id: "p3",
    botId: "mochi",
    botName: "Mochi",
    symbol: "SOL-USDT-SWAP",
    base: "SOL",
    side: "long",
    qty: "18.00",
    entry: "148.20",
    mark: "152.80",
    notional: "2,750",
    upnl: 82.8,
    upnlPct: 3.1,
    leverage: "3x 全倉 (cross)",
    opened: "08:15",
    liqPrice: "131.50",
    distLiqPct: "+13.9%",
    mmr: "0.50%",
    p6StopPrice: "142.00",
    p6DistPct: "-7.06%",
    p6Status: "ACTIVE",
    p6Rounding: "向上取整",
    protectedNotional: "$2,750",
  },
  {
    id: "p4",
    botId: "tabby",
    botName: "Tabby",
    symbol: "DOGE-USDT-SWAP",
    base: "DOGE",
    side: "long",
    qty: "8,000",
    entry: "0.1680",
    mark: "0.1740",
    notional: "1,392",
    upnl: 48.0,
    upnlPct: 3.57,
    leverage: "3x 全倉 (cross)",
    opened: "09:00",
    liqPrice: "0.1420",
    distLiqPct: "+18.4%",
    mmr: "0.80%",
    p6StopPrice: "0.1600",
    p6DistPct: "-8.05%",
    p6Status: "ACTIVE",
    p6Rounding: "向上取整",
    protectedNotional: "$1,392",
  },
];

const INITIAL_ORDERS: OrderRow[] = [
  {
    id: "o1",
    clientOrderId: "cat_tabby_0941",
    botId: "tabby",
    botName: "Tabby",
    symbol: "BTC-USDT-SWAP",
    side: "buy",
    type: "POST_ONLY",
    price: "63,920.00",
    qty: "0.08",
    distPct: "-0.41%",
    distTicks: "-26 ticks",
    frozenMargin: "$511.36",
    notionalUsd: "$5,113",
    placed: "11:02",
  },
  {
    id: "o2",
    clientOrderId: "cat_calico_0812",
    botId: "calico",
    botName: "Calico",
    symbol: "ETH-USDT-SWAP",
    side: "buy",
    type: "限價",
    price: "3,165.00",
    qty: "1.50",
    distPct: "-0.55%",
    distTicks: "-17 ticks",
    frozenMargin: "$474.75",
    notionalUsd: "$4,747",
    placed: "10:45",
  },
  {
    id: "o3",
    clientOrderId: "cat_mochi_0733",
    botId: "mochi",
    botName: "Mochi",
    symbol: "SOL-USDT-SWAP",
    side: "sell",
    type: "限價",
    price: "145.80",
    qty: "10.0",
    distPct: "+2.40%",
    distTicks: "+34 ticks",
    frozenMargin: "$145.80",
    notionalUsd: "$1,458",
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

export function ActivityPanel({ className, showHeader = true }: ActivityPanelProps) {
  const [tab, setTab] = useState<ActivityTab>("positions");
  const [orders, setOrders] = useState<OrderRow[]>(INITIAL_ORDERS);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [flashRows, setFlashRows] = useState<Record<string, "up" | "down">>({});

  // 模擬 Tick 波動微光跳動 (已定案固化)
  useEffect(() => {
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
  }, []);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 2500);
  };

  const handleCancelOrder = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setOrders((prev) => prev.filter((o) => o.id !== id));
    showToast("已成功發出撤單請求");
  };

  const handleCancelAll = () => {
    if (orders.length === 0) return;
    setOrders([]);
    showToast("已全撤在途限價委託 · 緊急平倉通道保持就緒");
  };

  const totalFrozen = useMemo(() => {
    return orders.reduce((sum, o) => {
      const num = Number(o.frozenMargin.replace("$", "").replace(",", ""));
      return sum + (Number.isNaN(num) ? 0 : num);
    }, 0);
  }, [orders]);

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {/* 1. 一體化 Header 與 3 Tab 切換開關 (方案 A：內嵌 P6 交易所端防線指示) */}
      {showHeader && (
        <div className="flex items-center justify-between px-3 py-2 bg-secondary/50 border-b border-border/80 shrink-0">
          <CardHeaderTitle
            cardId="positions"
            title="部位活動與盤口防線"
            subtext={
              <div className="flex items-center gap-1.5 ml-1">
                <span className="flex items-center gap-1 text-[9px] font-mono text-emerald-400 bg-emerald-400/10 px-1.5 py-0.2 rounded border border-emerald-400/25">
                  <span className="size-1.5 rounded-full bg-emerald-400 animate-pulse" />
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
                  ? "bg-secondary text-primary border border-border font-semibold"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              持倉 ({DEFAULT_POSITIONS.length})
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
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden flex flex-col justify-between">
        {/* ================= Tab 1: 持倉明細 (方案 A: 深度整合 P6 災難防線) ================= */}
        {tab === "positions" && (
          <table className="w-full text-left border-collapse table-auto">
            <thead className="border-b border-border/80 bg-background/40 text-[9.5px] font-mono text-muted-foreground sticky top-0 z-10 backdrop-blur-sm">
              <tr>
                <th className="py-2 pl-3 pr-1.5 font-medium">BOT / CONTRACT</th>
                <th className="px-1.5 font-medium">SIDE</th>
                <th className="px-1.5 text-right font-medium">SIZE / NOTIONAL</th>
                <th className="px-1.5 text-right font-medium">ENTRY / MARK</th>
                <th className="px-1.5 text-right font-medium">UNREALIZED PnL</th>
                <th className="px-1.5 text-right font-medium hidden sm:table-cell">預估強平 / 距爆倉</th>
                <th className="px-1.5 text-right font-medium hidden md:table-cell">P6 災難停損 (OKX)</th>
                <th className="py-2 pr-3 pl-1.5 text-right font-medium hidden lg:table-cell">LEVERAGE</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40 text-xs">
              {DEFAULT_POSITIONS.map((p) => {
                const flash = flashRows[p.id];
                const isPositive = p.upnl >= 0;

                return (
                  <tr
                    key={p.id}
                    className={cn(
                      "hover:bg-secondary/40 transition-colors group",
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
                        <span className="text-[9px] text-muted-foreground leading-tight">${p.notional}</span>
                      </div>
                    </td>

                    <td className="px-1.5 py-2 text-right font-mono">
                      <div className="flex flex-col items-end">
                        <span className="text-[10.5px] font-medium text-foreground leading-tight">${p.entry}</span>
                        <span className="text-[9px] text-muted-foreground leading-tight">${p.mark}</span>
                      </div>
                    </td>

                    <td className="px-1.5 py-2 text-right font-mono">
                      <div className="flex flex-col items-end">
                        <span className={cn("text-[10.5px] font-bold leading-tight", isPositive ? "text-up" : "text-down")}>
                          {isPositive ? "+" : ""}${p.upnl.toFixed(2)}
                        </span>
                        <span className={cn("text-[9px] leading-tight", isPositive ? "text-up" : "text-down")}>
                          {isPositive ? "+" : ""}{p.upnlPct.toFixed(2)}%
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

                    {/* 方案 A: 深度整合 P6 災難停損防線欄 */}
                    <td className="px-1.5 py-2 text-right hidden md:table-cell">
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

        {/* ================= Tab 2: 當前掛單 (方案 A: 高密度在途掛單 + 凍結保證金 + 一鍵全撤) ================= */}
        {tab === "orders" && (
          <div className="flex flex-col h-full justify-between">
            {orders.length === 0 ? (
              <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground font-mono">
                <span className="text-sm text-foreground font-bold">目前無在途掛單</span>
                <span className="text-[10px] text-muted-foreground mt-1">策略次根委託意圖觸發時將即時顯示於此</span>
              </div>
            ) : (
              <table className="w-full text-left border-collapse table-auto">
                <thead className="border-b border-border/80 bg-background/40 text-[9.5px] font-mono text-muted-foreground sticky top-0 z-10 backdrop-blur-sm">
                  <tr>
                    <th className="py-2 pl-3 pr-1.5 font-medium">BOT / CONTRACT</th>
                    <th className="px-1.5 font-medium">SIDE / TYPE</th>
                    <th className="px-1.5 text-right font-medium">PRICE</th>
                    <th className="px-1.5 text-right font-medium">QTY</th>
                    <th className="px-1.5 text-right font-medium">DIST (TICKS)</th>
                    <th className="px-1.5 text-right font-medium hidden sm:table-cell">FROZEN MARGIN</th>
                    <th className="py-2 pr-3 pl-1.5 text-right font-medium">ACTION</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40 text-xs font-mono">
                  {orders.map((o) => (
                    <tr key={o.id} className="hover:bg-secondary/40 transition-colors group">
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
                        <span className="text-amber-400 font-semibold">{o.distPct}</span>
                        <span className="text-[8.5px] text-muted-foreground block">{o.distTicks}</span>
                      </td>
                      <td className="px-1.5 py-2 text-right text-[10.5px] font-semibold text-foreground hidden sm:table-cell">
                        {o.frozenMargin}
                      </td>
                      <td className="py-2 pr-3 pl-1.5 text-right">
                        <button
                          type="button"
                          onClick={(e) => handleCancelOrder(o.id, e)}
                          className="px-1.5 py-0.5 rounded text-[9.5px] text-muted-foreground hover:text-rose-400 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/30 transition-all cursor-pointer"
                        >
                          撤單
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {/* 方案 A: 掛單頁底部統計與全撤單控制 */}
            <div className="px-3 py-1.5 bg-secondary/60 border-t border-border/80 flex items-center justify-between text-[9.5px] font-mono text-muted-foreground shrink-0 mt-auto">
              <div className="flex items-center gap-2">
                <span>在途凍結: <strong className="text-foreground">${totalFrozen.toFixed(2)}</strong></span>
                <span className="text-border">|</span>
                <span>在途總額: <strong className="text-foreground">$11,319</strong></span>
                {toastMessage && (
                  <span className="text-amber-400 font-semibold bg-amber-500/10 px-1 rounded animate-in fade-in">
                    {toastMessage}
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={handleCancelAll}
                disabled={orders.length === 0}
                className={cn(
                  "px-2 py-0.5 rounded text-[9px] font-semibold transition-all cursor-pointer",
                  orders.length > 0
                    ? "text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30"
                    : "text-muted-foreground/40 cursor-not-allowed border border-transparent"
                )}
              >
                一鍵全撤在途單
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 底部微型防線狀態 */}
      <div className="px-3 py-1 bg-secondary/70 border-t border-border/80 flex items-center justify-between text-[9px] font-mono text-muted-foreground shrink-0">
        <div className="flex items-center gap-1.5 truncate">
          <ShieldCheck className="size-3 text-emerald-400 shrink-0" />
          <span className="truncate">
            OKX 交易所端 P6 災難防線：Mark 觸發 · 提早取整 · 均價變動自動重錨
          </span>
        </div>
        <span className="text-foreground font-semibold shrink-0 hidden sm:inline">
          4 幣保護中
        </span>
      </div>
    </div>
  );
}
