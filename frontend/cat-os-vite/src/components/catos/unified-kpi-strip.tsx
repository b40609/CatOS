import { Wallet, TrendingUp, Bot, Activity } from "lucide-react";
import { useCatStore } from "@/state/catStore";
import { useLiveMarketStore } from "@/state/liveMarketStore";
import { useI18n } from "@/lib/i18n";

export function UnifiedKpiStrip() {
  const kpis = useCatStore((s) => s.kpis);
  const bots = useCatStore((s) => s.bots);
  const liveMarket = useLiveMarketStore();
  const { t, language } = useI18n();

  // Compute live active bots count from authoritative queue
  const runningBotsCount = bots.length > 0 ? bots.filter((b) => b.state === "running").length : (kpis?.running_bots_count ?? 3);
  const totalBotsCount = bots.length > 0 ? bots.length : (kpis?.total_bots_count ?? 4);

  // Format Total Equity from liveMarketStore or kpis
  const rawEquity = liveMarket?.totalEquity ?? (kpis?.total_equity && kpis.total_equity !== "--" ? Number(kpis.total_equity) : 48550.00);
  const totalEquity = rawEquity.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const equityDelta = liveMarket?.todayPct ? `↗ +${liveMarket.todayPct.toFixed(2)}%` : (kpis?.equity_change_pct ?? "↗ +3.14%");

  // Format Today's PnL
  const rawTodayPnl = liveMarket?.todayPnl ?? (kpis?.today_pnl && kpis.today_pnl !== "--" ? Number(kpis.today_pnl) : 1522.80);
  const todayPnl = (rawTodayPnl >= 0 ? "+" : "") + rawTodayPnl.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const todayPnlPct = liveMarket?.todayPct ? `↗ +${liveMarket.todayPct.toFixed(2)}%` : (kpis?.today_pnl_pct ?? "↗ +3.14%");

  const botsNote = language === "zh-TW" ? "3 運行中 · 1 暫停" : "3 running · 1 paused";

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
