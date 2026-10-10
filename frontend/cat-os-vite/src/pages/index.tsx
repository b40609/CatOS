import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Area, ComposedChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ArrowDownLeft, ArrowUpRight, ChevronRight, CircleDot, Download, ShieldCheck, Wallet, TrendingUp, Activity, Bot, Power, MoreHorizontal } from "lucide-react";
import { AppShell, PageHead, Panel } from "@/components/catos/shell";
import { Button } from "@/components/ui/button";
import { DerivativesMetrics } from "@/components/catos/derivatives-metrics";
import { allocation, cryptoMarkets, type Fill } from "@/lib/mock/data";
import { dashboardRanges, getEquitySeries, openPositions, positionPnl, recentFills, type DashboardRange } from "@/lib/mock/terminal";
import { fmtMoney, fmtSigned, nowStamp, useLiveFeed, useLiveNumber } from "@/hooks/use-live";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({
  head: () => ({ meta: [
    { title: "Dashboard — catOS Quant Terminal" },
    { name: "description", content: "catOS 加密量化戰情總覽：權益與回撤、即時持倉、策略方向、資產配置與風控狀態。模擬交易終端。" },
    { property: "og:title", content: "Dashboard — catOS Quant Terminal" },
    { property: "og:description", content: "Crypto portfolio equity, drawdown, open positions, recent fills and risk posture in the catOS simulated quant terminal." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: Dashboard,
});

const allocationColors = ["var(--allocation-btc)", "var(--allocation-eth)", "var(--allocation-sol)", "var(--allocation-arb)", "var(--allocation-cash)"];
const allocationClasses = ["allocation-btc", "allocation-eth", "allocation-sol", "allocation-arb", "allocation-cash"];
const tooltipStyle = { background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 6, color: "var(--foreground)", fontSize: 11 };

function Posture({ side }: { side: "LONG" | "SHORT" | "IDLE" }) {
  return <span className={cn("inline-flex items-center gap-1 rounded border px-1.5 py-0.5 num text-[9px]", side === "LONG" ? "border-up/15 bg-up/10 text-up" : side === "SHORT" ? "border-down/15 bg-down/10 text-down" : "border-border bg-muted/40 text-muted-foreground")}>{side === "LONG" ? "▲" : side === "SHORT" ? "▼" : "○"} {side}</span>;
}

function Quote({ market }: { market: (typeof cryptoMarkets)[number] }) {
  const { value } = useLiveNumber(market.price, 0.00015, 4200);
  return <div className="flex min-w-0 items-center justify-between gap-3 border-r border-border px-4 py-2.5 last:border-r-0"><div className="flex items-center gap-2"><span className="grid size-6 shrink-0 place-items-center rounded-full border border-border bg-secondary num text-xs text-foreground">{market.code === "BTC" ? "₿" : market.code === "ETH" ? "Ξ" : market.code === "SOL" ? "◎" : "Ð"}</span><span className="text-[11px] font-medium">{market.code}<span className="text-muted-foreground">/USDT</span></span></div><div className="text-right"><p className="num text-[11px]">{fmtMoney(value, market.price < 1 ? 4 : 2)}</p><p className={cn("num text-[9px]", market.change >= 0 ? "text-up" : "text-down")}>{fmtSigned(market.change)}%</p></div></div>;
}

function Stat({ label, seed, note, delta, icon: Icon, signed = false, suffix = "", digits = 2 }: { label: string; seed: number; note: string; delta: string; icon: typeof Wallet; signed?: boolean; suffix?: string; digits?: number }) {
  const { value } = useLiveNumber(seed, 0.0001, 5400);
  return <div className="min-w-0 border-r border-border px-5 py-4 last:border-r-0"><div className="flex items-center justify-between gap-2"><p className="text-[11px] text-muted-foreground">{label}</p><Icon className="size-3.5 text-muted-foreground" strokeWidth={1.5} /></div><p className={cn("num mt-2.5 text-[24px] font-medium", signed ? "text-up" : "text-foreground")}>{signed ? fmtSigned(value, digits) : fmtMoney(value, digits)}<span className="ml-1.5 text-xs text-muted-foreground">{suffix}</span></p><div className="mt-2 flex flex-wrap gap-1.5 text-[10px]"><span className={seed < 0 ? "text-down" : "text-up"}>{delta}</span><span className="text-muted-foreground">{note}</span></div></div>;
}

function PositionRow({ position }: { position: (typeof openPositions)[number] }) {
  const { value: mark } = useLiveNumber(position.mark, 0.00012, 4600);
  const pnl = positionPnl({ ...position, mark });
  const pct = pnl / (position.entry * position.size) * 100;
  return <tr className="border-b border-border/60 last:border-0 hover:bg-secondary/30"><td className="py-3 pl-4 pr-3"><div className="flex items-center gap-2"><span className="grid size-7 place-items-center rounded-full border border-border bg-secondary num text-xs">{position.code === "BTC" ? "₿" : position.code === "ETH" ? "Ξ" : "◎"}</span><div><p className="num text-[11px] font-medium">{position.symbol}</p><p className="text-[9px] text-muted-foreground">{position.venue} · Perpetual</p></div></div></td><td className="px-3"><Posture side={position.side} /></td><td className="px-3 text-right num text-[11px]">{position.size}<span className="ml-1 text-muted-foreground">{position.code}</span></td><td className="px-3 text-right num text-[11px]">{fmtMoney(position.entry)}</td><td className="px-3 text-right num text-[11px]">{fmtMoney(mark)}</td><td className={cn("px-4 text-right num text-[11px]", pnl >= 0 ? "text-up" : "text-down")}><p>{fmtSigned(pnl)}</p><p className="text-[9px]">{fmtSigned(pct)}%</p></td></tr>;
}

function makeFill(): Fill {
  const market = cryptoMarkets[Math.floor(Math.random() * cryptoMarkets.length)] ?? cryptoMarkets[0];
  return { id: crypto.randomUUID(), time: nowStamp(), symbol: `${market.code}-PERP`, side: Math.random() > 0.5 ? "BUY" : "SELL", qty: Number((Math.random() * 2 + 0.1).toFixed(2)), price: market.price, pnl: Number(((Math.random() - 0.3) * 800).toFixed(2)) };
}

function Dashboard() {
  const [range, setRange] = useState<DashboardRange>("30D");
  const [fills] = useLiveFeed<Fill>(recentFills, makeFill, 6500, 5);
  const series = useMemo(() => getEquitySeries(range), [range]);
  const first = series[0];
  const last = series[series.length - 1];
  const returnPct = first && last ? (last.equity / first.equity - 1) * 100 : 0;
  const [positionView, setPositionView] = useState<"All" | "Long" | "Short">("All");
  const positions = openPositions.filter((p) => positionView === "All" || p.side === positionView.toUpperCase());
  const [exported, setExported] = useState(false);

  function exportSnapshot() {
    const rows = ["Symbol,Side,Size,Entry Price,Mark Price,Unrealized PnL", ...openPositions.map((p) => `${p.symbol},${p.side},${p.size},${p.entry},${p.mark},${positionPnl(p).toFixed(2)}`)];
    const url = URL.createObjectURL(new Blob([rows.join("\n")], { type: "text/csv" }));
    const a = document.createElement("a"); a.href = url; a.download = "catos-positions.csv"; a.click(); URL.revokeObjectURL(url);
    setExported(true); setTimeout(() => setExported(false), 2500);
  }

  return <AppShell>
    <PageHead code="Overview / 戰情總覽" title="Dashboard" desc="Your portfolio. Every position. One view." right={<div className="flex items-center gap-2"><span className="mr-2 hidden text-[11px] text-muted-foreground md:block">Oct 10, 2026</span><Button variant="outline" size="sm" onClick={exportSnapshot} className="gap-2 bg-surface text-[11px]"><Download />{exported ? "Exported" : "Export snapshot"}</Button></div>} />

    <div className="mb-4 grid grid-cols-1 overflow-hidden rounded-md border border-border bg-surface sm:grid-cols-2 xl:grid-cols-4">{cryptoMarkets.map((market) => <Quote key={market.code} market={market} />)}</div>

    <div className="mb-4 grid overflow-hidden rounded-md border border-border bg-surface sm:grid-cols-2 xl:grid-cols-4">
      <Stat label="Total equity" seed={12_483_920} suffix="USDT" note="vs. yesterday" delta="↗ +0.47%" icon={Wallet} />
      <Stat label="Today's PnL" seed={58_412.6} suffix="USDT" signed note="vs. yesterday" delta="↗ +12.8%" icon={TrendingUp} />
      <Stat label="Active bots" seed={4} digits={0} suffix="/ 6" note="1 paused · 1 attention" delta="4 running" icon={Bot} />
      <Stat label="Max drawdown" seed={-8.42} suffix="%" note="year to date" delta="↘ 1.24%" icon={Activity} />
    </div>

    <section aria-label="Risk status" className="mb-4 flex flex-wrap items-center gap-x-6 gap-y-3 rounded-md border border-up/20 bg-up/5 px-4 py-3">
      <div className="flex items-center gap-2"><ShieldCheck className="size-4 text-up" /><span className="text-[11px] font-medium text-up">Risk within limits</span></div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[10px]"><span className="text-muted-foreground">Effective leverage <strong className="ml-1.5 num font-normal text-foreground">2.81×</strong></span><span className="text-muted-foreground">Daily loss <strong className="ml-1.5 num font-normal text-foreground">0.00%</strong></span><span className="text-muted-foreground">Soft stop <strong className="ml-1 num font-normal text-warn">2.0%</strong><span className="mx-2 text-border">/</span>Hard stop <strong className="ml-1 num font-normal text-down">4.0%</strong></span><span className="flex items-center gap-1.5 text-muted-foreground"><Power className="size-3 text-up" />Kill-switch <strong className="font-normal text-up">ARMED</strong></span></div>
      <Link to="/risk" className="ml-auto flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground">Risk center <ChevronRight className="size-3" /></Link>
    </section>

    <div className="grid gap-4 xl:grid-cols-[minmax(0,2.25fr)_minmax(270px,1fr)]">
      <Panel title="Equity & Drawdown" meta={<div className="flex items-center gap-1 rounded-md bg-background p-0.5">{dashboardRanges.map((r) => <Button key={r} variant="ghost" size="sm" aria-pressed={range === r} onClick={() => setRange(r)} className={cn("h-6 rounded px-2.5 num text-[10px]", range === r ? "bg-secondary text-foreground" : "text-muted-foreground")}>{r}</Button>)}</div>}>
        <div className="mb-3 flex flex-wrap items-start justify-between gap-2"><div><span className="num text-xl font-medium">12,483,920.00</span><span className="ml-2 text-[10px] text-muted-foreground">USDT</span><p className="mt-1 num text-[10px] text-up" data-testid="range-return">+{returnPct.toFixed(2)}% <span className="font-sans text-muted-foreground">this period</span></p></div><div className="flex gap-4 pt-2 text-[9px] text-muted-foreground"><span className="flex items-center gap-1.5"><span className="h-0.5 w-3 bg-primary" />Equity</span><span className="flex items-center gap-1.5"><span className="h-0.5 w-3 bg-down" />Drawdown</span></div></div>
        <div className="terminal-chart h-[230px]" aria-label={`Equity and drawdown chart for ${range}`}>
          <ResponsiveContainer width="100%" height="100%"><ComposedChart data={series} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
            <defs><linearGradient id="equity-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--primary)" stopOpacity={0.18} /><stop offset="100%" stopColor="var(--primary)" stopOpacity={0.01} /></linearGradient><linearGradient id="dd-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--down)" stopOpacity={0.03} /><stop offset="100%" stopColor="var(--down)" stopOpacity={0.16} /></linearGradient></defs>
            <CartesianGrid stroke="var(--border)" vertical={false} strokeDasharray="3 4" />
            <XAxis dataKey="label" interval={13} tick={{ fill: "var(--muted-foreground)", fontSize: 9 }} tickLine={false} axisLine={false} minTickGap={25} />
            <YAxis yAxisId="equity" domain={['dataMin - 100000', 'dataMax + 100000']} tick={{ fill: "var(--muted-foreground)", fontSize: 9 }} tickFormatter={(v) => `${(v / 1e6).toFixed(1)}M`} axisLine={false} tickLine={false} width={65} />
            <YAxis yAxisId="drawdown" orientation="right" domain={[-10, 0]} tick={{ fill: "var(--muted-foreground)", fontSize: 9 }} tickFormatter={(v) => `${v}%`} axisLine={false} tickLine={false} width={35} ticks={[-10, -5, 0]} reversed />
            <Tooltip contentStyle={tooltipStyle} formatter={(v: number, name: string) => [name === "Drawdown" ? `${v.toFixed(2)}%` : `${fmtMoney(v)} USDT`, name]} />
            <Area yAxisId="drawdown" type="monotone" dataKey="drawdown" name="Drawdown" stroke="var(--down)" strokeOpacity={0.65} fill="url(#dd-fill)" strokeWidth={1} isAnimationActive={false} />
            <Area yAxisId="equity" type="monotone" dataKey="equity" name="Equity" stroke="var(--primary)" fill="url(#equity-fill)" strokeWidth={2} isAnimationActive={false} />
          </ComposedChart></ResponsiveContainer>
        </div>
        <div className="mt-2 flex items-center justify-between border-t border-border pt-3 text-[10px] text-muted-foreground"><span>Portfolio performance · {range}</span><span className="flex items-center gap-1.5"><span className="size-1 rounded-full bg-up" />Updated just now</span></div>
      </Panel>
      <Panel title="Asset Allocation" meta={<span className="text-[10px] text-muted-foreground">5 assets</span>}>
        <div className="relative h-[176px]"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={allocation} dataKey="value" nameKey="name" innerRadius={57} outerRadius={75} paddingAngle={3} stroke="var(--surface)" cornerRadius={2} isAnimationActive={false}>{allocation.map((a, i) => <Cell key={a.name} fill={allocationColors[i]} />)}</Pie><Tooltip contentStyle={tooltipStyle} formatter={(v: number) => `${v}%`} /></PieChart></ResponsiveContainer><div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center"><span className="text-[9px] text-muted-foreground">Total assets</span><span className="mt-1 num text-lg">12.48M</span><span className="mt-0.5 text-[9px] text-muted-foreground">USDT</span></div></div>
        <ul className="mt-2 space-y-2.5">{allocation.map((a, i) => <li key={a.name} className="flex items-center gap-2 text-[11px]"><span className={cn("size-1.5 rounded-full", allocationClasses[i])} /><span className="text-muted-foreground">{a.name}</span><span className="ml-auto num">{a.value.toFixed(1)}<span className="text-muted-foreground">%</span></span></li>)}</ul>
      </Panel>
    </div>

    <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,2.25fr)_minmax(270px,1fr)]">
      <section className="panel min-w-0"><header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3"><h2 className="flex items-center gap-2 text-xs font-medium">Open Positions<span className="grid size-4 place-items-center rounded bg-secondary num text-[9px] text-muted-foreground">4</span></h2><div className="flex gap-1">{(["All", "Long", "Short"] as const).map((v) => <Button key={v} variant="ghost" size="sm" className={cn("h-6 px-2 text-[10px]", positionView === v ? "bg-secondary text-foreground" : "text-muted-foreground")} onClick={() => setPositionView(v)} aria-pressed={positionView === v}>{v}</Button>)}</div></header>
        <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-left"><thead className="border-b border-border bg-background/25 text-[9px] text-muted-foreground"><tr><th className="py-2.5 pl-4 font-normal">Symbol</th><th className="px-3 font-normal">Side</th><th className="px-3 text-right font-normal">Size</th><th className="px-3 text-right font-normal">Entry Price</th><th className="px-3 text-right font-normal">Mark Price</th><th className="px-4 text-right font-normal">Unrealized PnL</th></tr></thead><tbody>{positions.map((p) => <PositionRow key={p.symbol} position={p} />)}</tbody></table></div>
        <div className="flex items-center justify-between border-t border-border px-4 py-3 text-[10px] text-muted-foreground"><span>{positions.length} open positions · USDT settled</span><Link to="/bots" className="flex items-center gap-1 hover:text-foreground">Manage bots <ArrowUpRight className="size-3" /></Link></div>
      </section>
      <Panel title="Recent Fills" meta={<span className="flex items-center gap-1.5 text-[9px] text-up"><span className="pulse-dot size-1 rounded-full bg-up" />LIVE</span>}>
        <ul className="-mt-2">{fills.map((f) => <li key={f.id} className="slide-in-row flex items-center gap-2.5 border-b border-border/60 py-2.5 last:border-0"><span className={cn("grid size-7 shrink-0 place-items-center rounded-md", f.side === "BUY" ? "bg-up/10 text-up" : "bg-down/10 text-down")}>{f.side === "BUY" ? <ArrowDownLeft className="size-3.5" /> : <ArrowUpRight className="size-3.5" />}</span><div className="min-w-0"><p className="num text-[10px]">{f.symbol} <span className={cn("text-[9px]", f.side === "BUY" ? "text-up" : "text-down")}>{f.side}</span></p><p className="mt-0.5 num text-[9px] text-muted-foreground">{f.qty} @ {fmtMoney(f.price, f.price < 1 ? 4 : 2)}</p></div><div className="ml-auto text-right"><p className={cn("num text-[10px]", f.pnl >= 0 ? "text-up" : "text-down")}>{fmtSigned(f.pnl)}</p><p className="mt-0.5 num text-[9px] text-muted-foreground">{f.time}</p></div></li>)}</ul>
      </Panel>
    </div>

    <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,2.25fr)_minmax(270px,1fr)]">
      <Panel title="Strategy Posture" meta={<Link to="/strategies" className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground">All strategies <ChevronRight className="size-3" /></Link>}>
        <div className="grid gap-4 sm:grid-cols-3">{[{ name: "Momentum", code: "CAT-MOM-01", side: "LONG" as const, market: "BTC / ETH", score: "84%" }, { name: "Volatility", code: "CAT-VOL-09", side: "SHORT" as const, market: "ETH-PERP", score: "76%" }, { name: "Market Making", code: "CAT-MM-02", side: "IDLE" as const, market: "SOL-PERP", score: "—" }].map((s) => <div key={s.code} className="border-r border-border pr-4 last:border-0"><div className="flex items-center justify-between gap-2"><span className="text-[11px] font-medium">{s.name}</span><Posture side={s.side} /></div><p className="mt-1 num text-[9px] text-muted-foreground">{s.code}</p><div className="mt-3 flex justify-between text-[10px] text-muted-foreground"><span>{s.market}</span><span className="num">{s.score}</span></div></div>)}</div>
      </Panel>
      <div className="flex items-center gap-3 border-y border-border px-2 py-4"><CircleDot className="size-5 text-primary" /><div><p className="text-xs font-medium">Portfolio in sync</p><p className="mt-1 text-[10px] text-muted-foreground">2 venues · 4 active bots · 24/7</p></div><MoreHorizontal className="ml-auto size-4 text-muted-foreground" /></div>
    </div>
    <div className="mt-5"><h2 className="mb-3 text-xs font-medium">Derivatives Market <span className="ml-1 text-[10px] font-normal text-muted-foreground">/ 衍生品市場</span></h2><DerivativesMetrics /></div>
  </AppShell>;
}
