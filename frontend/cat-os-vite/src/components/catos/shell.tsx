import { Link, useRouterState } from "@tanstack/react-router";
import { AccountMenu } from "@/components/catos/account-menu";
import { Activity, Bot, LayoutDashboard, ScrollText, ShieldCheck, FlaskConical, SlidersHorizontal, ScanLine, Globe2, Settings2, PanelLeftClose, PanelLeftOpen, ChevronDown, Radio, Cat, type LucideIcon } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { useClock } from "@/hooks/use-live";
import { cn } from "@/lib/utils";

const GROUPS: { title: string; items: { to: string; label: string; sub: string; icon: LucideIcon }[] }[] = [
  { title: "Overview", items: [{ to: "/", label: "Dashboard", sub: "戰情總覽", icon: LayoutDashboard }] },
  { title: "Research", items: [
    { to: "/strategies", label: "Strategies", sub: "策略中心", icon: Activity },
    { to: "/backtest", label: "Backtest", sub: "歷史回測", icon: FlaskConical },
    { to: "/optimization", label: "Optimization", sub: "參數優化", icon: SlidersHorizontal },
    { to: "/review", label: "Review", sub: "策略覆盤", icon: ScanLine },
  ] },
  { title: "Execution & Risk", items: [
    { to: "/bots", label: "Bots", sub: "機器人管理", icon: Bot },
    { to: "/risk", label: "Risk Control", sub: "風控中心", icon: ShieldCheck },
  ] },
  { title: "Ecosystem & System", items: [
    { to: "/market-intel", label: "Market Intel", sub: "市場情報", icon: Globe2 },
    { to: "/logs", label: "Logs", sub: "系統日誌", icon: ScrollText },
    { to: "/settings", label: "Settings", sub: "系統設定", icon: Settings2 },
  ] },
];

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const current = GROUPS.flatMap((g) => g.items).find((n) => n.to === pathname);
  const clock = useClock();
  return (
    <div className="min-h-screen bg-background">
      <aside className={cn("fixed inset-y-0 left-0 z-30 flex flex-col border-r border-border bg-sidebar", collapsed ? "w-16" : "w-16 lg:w-[228px]")}>
        <Link to="/" className="flex h-16 shrink-0 items-center gap-2.5 px-4" title="CatOS Dashboard">
          <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground"><Cat className="size-5" strokeWidth={2} /></span>
          {!collapsed && <span className="hidden text-lg font-semibold lg:block">catOS<span className="ml-1.5 text-primary">.</span></span>}
        </Link>
        {!collapsed && <div className="mx-3 mb-3 hidden items-center gap-2 rounded-md border border-border bg-surface px-3 py-2.5 lg:flex"><span className="grid size-6 place-items-center rounded bg-secondary text-xs text-primary">M</span><span className="text-xs font-medium">Quant Workspace</span><ChevronDown className="ml-auto size-3 text-muted-foreground" /></div>}
        <nav aria-label="Main navigation" className="min-h-0 flex-1 space-y-4 overflow-y-auto px-2 pb-3">
          {GROUPS.map((group) => <div key={group.title}>
            {!collapsed && <p className="mb-1.5 hidden px-3 text-[10px] font-medium uppercase text-muted-foreground lg:block">{group.title}</p>}
            <div className="space-y-0.5">{group.items.map(({ to, label, sub, icon: Icon }) => <Link key={to} to={to} title={`${label} · ${sub}`} activeOptions={{ exact: to === "/" }} activeProps={{ className: "bg-secondary text-foreground [&_svg]:text-primary" }} inactiveProps={{ className: "text-muted-foreground hover:bg-secondary/60 hover:text-foreground" }} className="relative flex min-h-10 items-center gap-3 rounded-md px-3 py-2">
              <Icon className="size-4 shrink-0" strokeWidth={1.7} />
              {!collapsed && <span className="hidden min-w-0 flex-1 items-center justify-between gap-1 lg:flex"><span className="text-[12px] font-medium">{label}</span><span className="text-[10px] text-muted-foreground">{sub}</span></span>}
            </Link>)}</div>
          </div>)}
        </nav>
        {!collapsed && <div className="hidden lg:block"><div className="mx-4 mb-3 flex items-center gap-2 text-[10px] text-muted-foreground"><span className="size-1.5 rounded-full bg-up" />All systems operational <span className="ml-auto num">v2.0</span></div><AccountMenu /></div>}
      </aside>
      <div className={cn("min-w-0", collapsed ? "pl-16" : "pl-16 lg:pl-[228px]")}>
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-background/95 px-4 backdrop-blur lg:px-7">
          <Button variant="ghost" size="icon" onClick={() => setCollapsed((v) => !v)} title={collapsed ? "Expand sidebar" : "Collapse sidebar"} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} className="size-7 text-muted-foreground">{collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}</Button>
          <span className="hidden text-xs text-muted-foreground sm:block">Workspace</span><span className="text-xs text-muted-foreground">/</span><span className="text-xs">{current?.label ?? "Account"}</span>
          <div className="ml-auto flex items-center gap-4"><span className="rounded border border-warn/20 bg-warn/5 px-2 py-0.5 num text-[10px] text-warn">PAPER TRADING</span><span className="hidden items-center gap-1.5 text-[11px] text-muted-foreground sm:flex"><Radio className="size-3 text-up" />Engine online</span><span className="hidden num text-[10px] text-muted-foreground xl:block">{clock} UTC+8</span></div>
        </header>
        <main className="mx-auto max-w-[1700px] p-4 lg:px-7 lg:py-6">{children}</main>
        <footer className="flex flex-wrap justify-between gap-2 border-t border-border px-7 py-3 text-[10px] text-muted-foreground"><span className="flex items-center gap-2"><span className="size-1.5 rounded-full bg-up" />Binance <span className="num">18ms</span><span className="mx-1 text-border">|</span>OKX <span className="num">24ms</span></span><span>catOS Terminal · Simulated market data</span></footer>
      </div>
    </div>
  );
}

export function PageHead({ title, code, desc, right }: { title: string; code: string; desc: string; right?: ReactNode }) {
  return <div className="mb-5 flex flex-wrap items-center justify-between gap-4"><div><p className="mb-1 text-[10px] uppercase text-muted-foreground">{code}</p><h1 className="text-2xl font-semibold text-foreground">{title}</h1><p className="mt-1 text-xs text-muted-foreground">{desc}</p></div>{right}</div>;
}

export function Panel({ title, meta, className, children }: { title: string; meta?: ReactNode; className?: string; children: ReactNode }) {
  return <section className={cn("panel flex min-w-0 flex-col", className)}><header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3"><h2 className="text-xs font-medium text-foreground">{title}</h2>{meta}</header><div className="min-w-0 flex-1 p-4">{children}</div></section>;
}
