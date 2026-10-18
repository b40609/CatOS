import { Wallet, TrendingUp, Bot, Activity } from "lucide-react";
import { useCatStore } from "@/state/catStore";
import { useI18n } from "@/lib/i18n";

export function UnifiedKpiStrip() {
  const kpis = useCatStore((s) => s.kpis);
  const bots = useCatStore((s) => s.bots);
  const { t, language } = useI18n();

  // Compute live active bots count from authoritative queue
  const runningBotsCount = bots.length > 0 ? bots.filter((b) => b.state === "running").length : (kpis?.running_bots_count ?? 4);
  const totalBotsCount = bots.length > 0 ? bots.length : (kpis?.total_bots_count ?? 6);

  // Format Total Equity from store or fallback
  const totalEquity = kpis?.total_equity && kpis.total_equity !== "--"
    ? Number(kpis.total_equity).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : "12,482,114.05";

  const equityDelta = kpis?.equity_change_pct ?? "↗ +0.47%";

  // Format Today's PnL
  const todayPnl = kpis?.today_pnl && kpis.today_pnl !== "--"
    ? (Number(kpis.today_pnl) >= 0 ? `+${Number(kpis.today_pnl).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : Number(kpis.today_pnl).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }))
    : "+58,447.77";

  const todayPnlPct = kpis?.today_pnl_pct && !kpis.today_pnl_pct.includes("NaN")
    ? (kpis.today_pnl_pct.startsWith("+") || kpis.today_pnl_pct.startsWith("↗") ? kpis.today_pnl_pct : `↗ ${kpis.today_pnl_pct}`)
    : "↗ +12.0%";

  const botsNote = language === "zh-TW" ? "1 暫停 · 1 待關注" : "1 paused · 1 attention";

  return (
    <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
      {/* 1. Total Equity */}
      <div className="group relative flex min-w-0 flex-col rounded-xl border border-border/70 bg-surface/85 p-3.5 backdrop-blur-md shadow-xs transition-all duration-150 hover:border-primary/50">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] font-normal text-muted-foreground">{t("total_equity")}</span>
          <span className="grid size-5.5 place-items-center rounded-md bg-secondary/60 text-muted-foreground group-hover:text-primary transition-colors">
            <Wallet className="size-3" strokeWidth={1.5} />
          </span>
        </div>
        <div className="mt-2 flex items-baseline gap-1.5">
          <span className="num text-xl font-bold tracking-tight text-foreground leading-none">
            {totalEquity}
          </span>
          <span className="text-[11px] text-muted-foreground num font-normal">USDT</span>
        </div>
        <div className="mt-2 flex items-center gap-1.5 text-[10px]">
          <span className="num font-semibold text-up">{equityDelta}</span>
          <span className="text-muted-foreground">{t("vs_yesterday")}</span>
        </div>
      </div>

      {/* 2. Today's PnL */}
      <div className="group relative flex min-w-0 flex-col rounded-xl border border-border/70 bg-surface/85 p-3.5 backdrop-blur-md shadow-xs transition-all duration-150 hover:border-up/50">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] font-normal text-muted-foreground">{t("today_pnl")}</span>
          <span className="grid size-5.5 place-items-center rounded-md bg-secondary/60 text-muted-foreground group-hover:text-up transition-colors">
            <TrendingUp className="size-3" strokeWidth={1.5} />
          </span>
        </div>
        <div className="mt-2 flex items-baseline gap-1.5">
          <span className="num text-xl font-bold tracking-tight text-up leading-none">
            {todayPnl}
          </span>
          <span className="text-[11px] text-muted-foreground num font-normal">USDT</span>
        </div>
        <div className="mt-2 flex items-center gap-1.5 text-[10px]">
          <span className="num font-semibold text-up">{todayPnlPct}</span>
          <span className="text-muted-foreground">{t("vs_yesterday")}</span>
        </div>
      </div>

      {/* 3. Active Bots */}
      <div className="group relative flex min-w-0 flex-col rounded-xl border border-border/70 bg-surface/85 p-3.5 backdrop-blur-md shadow-xs transition-all duration-150 hover:border-primary/50">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] font-normal text-muted-foreground">{t("active_bots")}</span>
          <span className="grid size-5.5 place-items-center rounded-md bg-secondary/60 text-muted-foreground group-hover:text-primary transition-colors">
            <Bot className="size-3" strokeWidth={1.5} />
          </span>
        </div>
        <div className="mt-2 flex items-baseline gap-1.5">
          <span className="num text-xl font-bold tracking-tight text-foreground leading-none">
            {runningBotsCount}
          </span>
          <span className="text-[11px] text-muted-foreground num font-normal">/ {totalBotsCount}</span>
        </div>
        <div className="mt-2 flex items-center gap-1.5 text-[10px]">
          <span className="num font-semibold text-up">{runningBotsCount} {t("running")}</span>
          <span className="text-muted-foreground truncate">{kpis?.bots_summary_note ?? botsNote}</span>
        </div>
      </div>

      {/* 4. Max Drawdown */}
      <div className="group relative flex min-w-0 flex-col rounded-xl border border-border/70 bg-surface/85 p-3.5 backdrop-blur-md shadow-xs transition-all duration-150 hover:border-down/50">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] font-normal text-muted-foreground">{t("max_drawdown")}</span>
          <span className="grid size-5.5 place-items-center rounded-md bg-secondary/60 text-muted-foreground group-hover:text-down transition-colors">
            <Activity className="size-3" strokeWidth={1.5} />
          </span>
        </div>
        <div className="mt-2 flex items-baseline gap-1.5">
          <span className="num text-xl font-bold tracking-tight text-foreground leading-none">
            -8.43
          </span>
          <span className="text-[11px] text-muted-foreground num font-normal">%</span>
        </div>
        <div className="mt-2 flex items-center gap-1.5 text-[10px]">
          <span className="num font-semibold text-down">↘ 1.24%</span>
          <span className="text-muted-foreground">{t("ytd")}</span>
        </div>
      </div>
    </div>
  );
}
