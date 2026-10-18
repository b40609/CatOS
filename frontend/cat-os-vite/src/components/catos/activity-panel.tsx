import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { formatUsd, formatPct, toneOf } from "@/lib/v0-engine";
import { CardHeaderTitle } from "./card-header-title";

export type ActivityTab = "positions" | "orders" | "fills";

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
  p6Guard: string;
}

export interface OrderRow {
  id: string;
  botId: string;
  botName: string;
  symbol: string;
  side: "buy" | "sell";
  type: "限價" | "停損";
  price: string;
  qty: string;
  distPct: string;
  placed: string;
}

export interface FillRow {
  id: string;
  botId: string;
  botName: string;
  symbol: string;
  action: "開多" | "平多" | "開空" | "平空";
  side: "buy" | "sell";
  qty: string;
  price: string;
  pnl: number;
  time: string;
  tag: string;
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
    p6Guard: "OKX 59,500",
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
    p6Guard: "OKX 3,210",
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
    p6Guard: "OKX 142.0",
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
    p6Guard: "OKX 0.160",
  },
];

const DEFAULT_ORDERS: OrderRow[] = [
  { id: "o1", botId: "mochi", botName: "Mochi", symbol: "SOL-USDT-SWAP", side: "buy", type: "限價", price: "147.80", qty: "6.0", distPct: "-3.27%", placed: "09:30" },
  { id: "o2", botId: "mochi", botName: "Mochi", symbol: "SOL-USDT-SWAP", side: "buy", type: "限價", price: "146.90", qty: "6.0", distPct: "-3.86%", placed: "09:30" },
  { id: "o3", botId: "tabby", botName: "Tabby", symbol: "BTC-USDT-SWAP", side: "sell", type: "停損", price: "60,560.00", qty: "0.12", distPct: "-2.54%", placed: "09:15" },
  { id: "o4", botId: "calico", botName: "Calico", symbol: "ETH-USDT-SWAP", side: "sell", type: "停損", price: "3,250.00", qty: "2.40", distPct: "-3.71%", placed: "10/5 06:00" },
];

const DEFAULT_FILLS: FillRow[] = [
  { id: "f1", botId: "tabby", botName: "Tabby", symbol: "BTC-USDT-SWAP", action: "平空", side: "buy", qty: "0.12", price: "61,480.00", pnl: 142.5, time: "04:30:12", tag: "41cb53c54d6dABDE" },
  { id: "f2", botId: "calico", botName: "Calico", symbol: "ETH-USDT-SWAP", action: "開多", side: "buy", qty: "2.40", price: "3,320.00", pnl: 0, time: "10/5 06:00:00", tag: "41cb53c54d6dABDE" },
  { id: "f3", botId: "mochi", botName: "Mochi", symbol: "SOL-USDT-SWAP", action: "平多", side: "sell", qty: "12.00", price: "152.40", pnl: 68.2, time: "08:14:55", tag: "41cb53c54d6dABDE" },
  { id: "f4", botId: "tabby", botName: "Tabby", symbol: "DOGE-USDT-SWAP", action: "開多", side: "buy", qty: "8,000", price: "0.1680", pnl: 0, time: "09:00:22", tag: "41cb53c54d6dABDE" },
];

export function ActivityPanel({ className, showHeader = true }: ActivityPanelProps) {
  const [tab, setTab] = useState<ActivityTab>("positions");
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

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {/* 1. 一體化 Header 與 3 Tab 切換開關 */}
      {showHeader && (
        <div className="flex items-center justify-between px-3 py-2 bg-secondary/50 border-b border-border/80 shrink-0">
          <CardHeaderTitle
            cardId="positions"
            title="部位與活動 (Positions & Activity)"
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
                  ? "bg-secondary text-primary border border-border font-semibold"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              掛單 ({DEFAULT_ORDERS.length})
            </button>

            <button
              type="button"
              onClick={() => setTab("fills")}
              className={cn(
                "px-2 py-0.5 text-[10.5px] font-mono font-medium rounded transition-colors cursor-pointer flex items-center gap-1",
                tab === "fills"
                  ? "bg-secondary text-primary border border-border font-semibold"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              成交流
            </button>
          </div>
        </div>
      )}

      {/* 2. 內容展示區 */}
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden">
        {/* ================= Tab 1: 持倉明細 ================= */}
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
                    <th className="px-1.5 text-right font-medium hidden md:table-cell">停損價 / 保證金率</th>
                <th className="py-2 pr-3 pl-1.5 text-right font-medium hidden lg:table-cell">LEVERAGE</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40 text-xs font-mono">
              {DEFAULT_POSITIONS.map((p) => {
                const flash = flashRows[p.id];
                return (
                  <tr
                    key={p.id}
                    className={cn(
                      "hover:bg-secondary/40 transition-colors",
                      flash === "up" && "flash-up",
                      flash === "down" && "flash-down"
                    )}
                  >
                    <td className="py-2 pl-3 pr-1.5">
                      <div className="flex flex-col">
                        <span className="text-[11px] font-bold text-foreground leading-tight">{p.symbol}</span>
                        <span className="text-[9px] text-muted-foreground leading-tight">
                          {p.botName} · OKX
                        </span>
                      </div>
                    </td>

                    <td className="px-1.5 py-2">
                      <span
                        className={cn(
                          "inline-flex items-center gap-0.5 rounded-[3px] border px-1 py-0.2 text-[8.5px] font-bold tracking-tight",
                          p.side === "long"
                            ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-400"
                            : "border-rose-400/30 bg-rose-400/10 text-rose-400"
                        )}
                      >
                        {p.side === "long" ? "▲多" : "▼空"}
                      </span>
                    </td>

                    <td className="px-1.5 py-2 text-right">
                      <div className="flex flex-col items-end">
                        <span className="text-[10.5px] font-bold text-foreground leading-tight">{p.qty} {p.base}</span>
                        <span className="text-[9px] text-muted-foreground leading-tight">${p.notional}</span>
                      </div>
                    </td>

                    <td className="px-1.5 py-2 text-right">
                      <div className="flex flex-col items-end">
                        <span className="text-[10.5px] text-foreground leading-tight">{p.entry}</span>
                        <span className="text-[9px] text-muted-foreground leading-tight">{p.mark}</span>
                      </div>
                    </td>

                    <td className="px-1.5 py-2 text-right">
                      <div className="flex flex-col items-end">
                        <span className={cn("text-[10.5px] font-bold leading-tight", toneOf(p.upnl))}>
                          {formatUsd(p.upnl, true)}
                        </span>
                        <span className={cn("text-[9px] leading-tight", toneOf(p.upnl))}>
                          {formatPct(p.upnlPct)}
                        </span>
                      </div>
                    </td>

                    <td className="px-1.5 py-2 text-right hidden sm:table-cell">
                      <div className="flex flex-col items-end">
                        <span className="text-[10px] text-foreground font-mono leading-tight font-medium">${p.liqPrice}</span>
                        <span className="text-[8.5px] text-emerald-400 font-semibold leading-tight flex items-center gap-0.5">
                          距爆倉 {p.distLiqPct}
                        </span>
                      </div>
                    </td>

                    <td className="px-1.5 py-2 text-right hidden md:table-cell">
                      <div className="flex flex-col items-end">
                        <span
                          className="text-[10px] text-primary font-mono leading-tight font-medium"
                          title="OKX 官方伺服器託管的市價停損觸發價"
                        >
                          停損 ${p.p6Guard.replace("OKX ", "")}
                        </span>
                        <span className="text-[8.5px] text-muted-foreground font-mono leading-tight">
                          維持率 {p.mmr}
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

        {/* ================= Tab 2: 當前掛單 ================= */}
        {tab === "orders" && (
          <table className="w-full text-left border-collapse table-auto">
            <thead className="border-b border-border/80 bg-background/40 text-[9.5px] font-mono text-muted-foreground sticky top-0 z-10 backdrop-blur-sm">
              <tr>
                <th className="py-2 pl-3 pr-1.5 font-medium">BOT / CONTRACT</th>
                <th className="px-1.5 font-medium">SIDE / TYPE</th>
                <th className="px-1.5 text-right font-medium">PRICE</th>
                <th className="px-1.5 text-right font-medium">QTY</th>
                <th className="px-1.5 text-right font-medium">DIST</th>
                <th className="py-2 pr-3 pl-1.5 text-right font-medium hidden sm:table-cell">TIME</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40 text-xs font-mono">
              {DEFAULT_ORDERS.map((o) => (
                <tr key={o.id} className="hover:bg-secondary/40 transition-colors">
                  <td className="py-2 pl-3 pr-1.5">
                    <div className="flex flex-col">
                      <span className="text-[11px] font-bold text-foreground leading-tight">{o.symbol}</span>
                      <span className="text-[9px] text-muted-foreground leading-tight">{o.botName}</span>
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

                  <td className="px-1.5 py-2 text-right font-bold text-foreground text-[10.5px]">{o.price}</td>
                  <td className="px-1.5 py-2 text-right text-muted-foreground text-[10px]">{o.qty}</td>
                  <td className="px-1.5 py-2 text-right text-amber-400/90 text-[10px]">{o.distPct}</td>
                  <td className="py-2 pr-3 pl-1.5 text-right text-muted-foreground text-[9px] hidden sm:table-cell">{o.placed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* ================= Tab 3: 最新成交流 ================= */}
        {tab === "fills" && (
          <table className="w-full text-left border-collapse table-auto">
            <thead className="border-b border-border/80 bg-background/40 text-[9.5px] font-mono text-muted-foreground sticky top-0 z-10 backdrop-blur-sm">
              <tr>
                <th className="py-2 pl-3 pr-1.5 font-medium">BOT / CONTRACT</th>
                <th className="px-1.5 font-medium">ACTION</th>
                <th className="px-1.5 text-right font-medium">PRICE & QTY</th>
                <th className="px-1.5 text-right font-medium">PnL</th>
                <th className="px-1.5 font-medium hidden md:table-cell">TAG</th>
                <th className="py-2 pr-3 pl-1.5 text-right font-medium">TIME</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40 text-xs font-mono">
              {DEFAULT_FILLS.map((f) => (
                <tr key={f.id} className="hover:bg-secondary/40 transition-colors">
                  <td className="py-2 pl-3 pr-1.5">
                    <div className="flex flex-col">
                      <span className="text-[11px] font-bold text-foreground leading-tight">{f.symbol}</span>
                      <span className="text-[9px] text-muted-foreground leading-tight">{f.botName}</span>
                    </div>
                  </td>

                  <td className="px-1.5 py-2">
                    <span
                      className={cn(
                        "px-1 py-0.2 rounded text-[8.5px] font-bold",
                        f.action.includes("多") ? "bg-emerald-400/10 text-emerald-400" : "bg-rose-400/10 text-rose-400"
                      )}
                    >
                      {f.action}
                    </span>
                  </td>

                  <td className="px-1.5 py-2 text-right">
                    <div className="flex flex-col items-end">
                      <span className="text-[10.5px] font-bold text-foreground leading-tight">${f.price}</span>
                      <span className="text-[9px] text-muted-foreground leading-tight">{f.qty}</span>
                    </div>
                  </td>

                  <td className="px-1.5 py-2 text-right">
                    {f.pnl !== 0 ? (
                      <span className={cn("text-[10.5px] font-bold", toneOf(f.pnl))}>
                        {formatUsd(f.pnl, true)}
                      </span>
                    ) : (
                      <span className="text-[9px] text-muted-foreground">開倉</span>
                    )}
                  </td>

                  <td className="px-1.5 py-2 hidden md:table-cell">
                    <span className="text-[8.5px] font-mono text-primary bg-primary/10 px-1 py-0.5 rounded border border-primary/20">
                      Tag: {f.tag.slice(0, 8)}
                    </span>
                  </td>

                  <td className="py-2 pr-3 pl-1.5 text-right text-muted-foreground text-[9px]">{f.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
