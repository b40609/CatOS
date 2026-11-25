import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronRight } from "lucide-react";
import { CardHeaderTitle } from "./card-header-title";
import { CardHeaderTabs } from "./card-header-tabs";
import { useCatStore } from "@/state/catStore";
import { useOverviewSignals } from "@/lib/overview-signals";
import { useRouter } from "@/lib/router";
import { cn } from "@/lib/utils";
import { formatTimeframe } from "@/lib/format";

export type PipelineTone = "ok" | "warn" | "gold" | "info" | "fail" | "muted";

interface PipelineRow {
  id: string;
  name: string;
  meta: string;
  stage: 0 | 1 | 2 | 3 | 4;
  stageLabel: string;
  progress: string;
  detail: string;
  color: string;
  tone: PipelineTone;
  route: string;
  active: boolean;
}

const STAGES = ["提案", "研究驗證", "待核准", "模擬盤", "實盤"] as const;
const STAGE_BAR_PCT = [10, 34, 58, 80, 100];

const PREVIEW_PIPELINE: PipelineRow[] = [
  { id: "don4h", name: "Donchian 通道突破", meta: "BTC · 4H", stage: 3, stageLabel: "模擬盤", progress: "23/30d", detail: "模擬盤第 23 天 · 剩 7 天滿期", color: "#e8b45e", tone: "ok", route: "/demo-bot", active: true },
  { id: "tsmom", name: "時間序列動能", meta: "BTC · 1D", stage: 3, stageLabel: "模擬盤", progress: "15/30d", detail: "模擬盤第 15 天 · 回撤 -16.5%", color: "#7faee2", tone: "ok", route: "/demo-bot", active: true },
  { id: "rsi", name: "均值回歸 RSI", meta: "ETH · 1H", stage: 3, stageLabel: "模擬盤", progress: "-0.61%", detail: "模擬偏差 -0.61%（警戒 0.50%）", color: "#f59e0b", tone: "warn", route: "/demo-bot", active: true },
  { id: "ens", name: "Donchian 多週期集成", meta: "BTC · 1D", stage: 2, stageLabel: "待核准", progress: "4/4 過", detail: "驗證通過 · 待 CLI 核准部署", color: "#e8b45e", tone: "gold", route: "/strategies", active: true },
  { id: "fund", name: "資金費擁擠過濾", meta: "BTC · 4H", stage: 1, stageLabel: "研究中", progress: "優化 62%", detail: "48 組參數優化執行中", color: "#7faee2", tone: "info", route: "/optimization", active: true },
  { id: "dcm", name: "DCM 突破後回踩", meta: "BTC · 15m", stage: 1, stageLabel: "未通過", progress: "淨損 -4.6%", detail: "扣除成本後負報酬", color: "#f43f5e", tone: "fail", route: "/backtest", active: false },
  { id: "vol", name: "波動率突破", meta: "SOL · 4H · Agent", stage: 0, stageLabel: "提案", progress: "待審", detail: "Agent 策略資料夾提案", color: "#a1a1aa", tone: "muted", route: "/strategies", active: false },
  { id: "wk", name: "週末效應", meta: "BTC · 1D", stage: 0, stageLabel: "提案", progress: "佇列", detail: "待排程回測", color: "#71717a", tone: "muted", route: "/strategies", active: false },
];

function tonePillClass(tone: PipelineTone): string {
  switch (tone) {
    case "ok": return "bg-emerald-500/15 border-emerald-500/35 text-emerald-400";
    case "warn": return "bg-amber-500/15 border-amber-500/35 text-amber-300";
    case "gold": return "bg-primary/15 border-primary/40 text-primary";
    case "info": return "bg-sky-500/15 border-sky-500/35 text-sky-300";
    case "fail": return "bg-rose-500/15 border-rose-500/35 text-rose-400";
    default: return "bg-white/[0.05] border-white/[0.12] text-zinc-400";
  }
}

function toneTextClass(tone: PipelineTone): string {
  switch (tone) {
    case "warn": return "text-amber-300 font-semibold";
    case "gold": return "text-primary font-semibold";
    case "fail": return "text-rose-400 font-semibold";
    case "ok": return "text-emerald-400";
    default: return "text-muted-foreground";
  }
}

/**
 * 策略管線卡片 (2A 定案 · 比例驅動自適應)
 * - 窄卡 (< 460px)：緊湊進度條態（< 340px 極窄收合進度條只留階段膠囊與進度）
 * - 標準卡 (460–819px)：策略名 + 5 階段軌道 + 箭頭
 * - 寬卡 (>= 820px)：策略名 + 5 階段軌道 + 右欄當前說明（避免軌道過度拉長）
 * - 扁卡 (< 200px)：自動緊縮行高
 */
export function StrategyPipelineCard({ className }: { className?: string }) {
  const registeredStrategies = useCatStore((s) => s.strategies);
  const bots = useCatStore((s) => s.bots);
  const signals = useOverviewSignals();
  const { navigate } = useRouter();

  const cardRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ width: 640, height: 280 });
  const [activeOnly, setActiveOnly] = useState(false);

  useEffect(() => {
    const el = cardRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDims({ width: entry.contentRect.width, height: entry.contentRect.height });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const isNarrow = dims.width < 460;
  const isSuperNarrow = dims.width < 340;
  const isUltraWide = dims.width >= 680;
  const isWide = dims.width >= 580;
  const isFlat = dims.height < 200;

  const gridColsClass = isUltraWide
    ? "grid-cols-[192px_minmax(0,1fr)_172px_14px]"
    : isWide
    ? "grid-cols-[184px_minmax(0,1fr)_14px]"
    : "grid-cols-[156px_minmax(0,1fr)_14px]";

  const allRows = useMemo<PipelineRow[]>(() => {
    if (signals.previewPick) return PREVIEW_PIPELINE;

    const demoRuns = signals.demoBot?.runs ?? [];
    const approvals = signals.replay?.approvals ?? [];
    const replayRuns = signals.replay?.runs ?? [];
    const catalogStrats = signals.catalog?.strategies ?? [];

    const byId = new Map<string, { id: string; name: string; version: string; origin?: string }>();
    for (const s of catalogStrats) {
      byId.set(s.id, { id: s.id, name: s.name || s.id, version: s.version, origin: s.origin });
    }
    for (const s of registeredStrategies) {
      if (!byId.has(s.strategy_id)) {
        byId.set(s.strategy_id, { id: s.strategy_id, name: s.name || s.strategy_id, version: s.version, origin: "builtin" });
      }
    }

    const result: PipelineRow[] = [];
    for (const item of byId.values()) {
      const demo = demoRuns.find((r) => r.strategy_id === item.id);
      const activeApproval = approvals.find((a) => a.strategy_id === item.id && a.state === "active");
      const replay = replayRuns.find((r) => r.strategy_id === item.id);
      const localBot = bots.find((b) => b.strategy_id === item.id);
      const isBuiltinApproved = registeredStrategies.some((s) => s.strategy_id === item.id && s.approval_state === "approved");

      if (demo) {
        const tf = formatTimeframe(demo.timeframe_ms);
        const sym = demo.inst_id?.replace("-USDT-SWAP", "") ?? "BTC";
        const isStale = demo.state === "running" && demo.stale;
        const isFailed = demo.state === "failed";
        const isRunning = demo.state === "running" && !demo.stale;
        result.push({
          id: item.id,
          name: item.name,
          meta: `${sym} · ${tf} · OKX Demo`,
          stage: 3,
          stageLabel: isStale ? "無回應" : isFailed ? "錯誤停止" : isRunning ? "模擬盤" : "已停止",
          progress: isStale ? "無回應" : `${demo.bars} bars`,
          detail: `OKX 模擬盤 · ${demo.bars} 根 K 線 · ${demo.fills} 筆成交`,
          color: isFailed ? "#f43f5e" : isStale ? "#f59e0b" : "#e8b45e",
          tone: isFailed ? "fail" : isStale ? "warn" : "ok",
          route: "/demo-bot",
          active: true,
        });
      } else if (activeApproval) {
        const changed = activeApproval.source === "changed";
        const passed = replay?.consistency?.passed === true;
        result.push({
          id: item.id,
          name: item.name,
          meta: `${activeApproval.inst_id.replace("-USDT-SWAP", "")} · ${formatTimeframe(activeApproval.timeframe_ms)}`,
          stage: 2,
          stageLabel: changed ? "來源已變" : "已核准",
          progress: changed ? "需重核" : passed ? "重播一致" : "可上模擬盤",
          detail: changed ? "策略原始碼已變更，核准失效" : "有效核准 · 可由 CLI 啟動模擬盤 Bot",
          color: changed ? "#f43f5e" : "#e8b45e",
          tone: changed ? "fail" : "gold",
          route: "/strategies",
          active: true,
        });
      } else if (isBuiltinApproved || localBot) {
        result.push({
          id: item.id,
          name: item.name,
          meta: `${localBot?.inst_id?.replace("-USDT-SWAP", "") ?? "BTC"} · local-sim`,
          stage: 2,
          stageLabel: "本機已核准",
          progress: localBot ? `${localBot.bars} bars` : "已登錄",
          detail: "本機合成模擬內建製品",
          color: "#7faee2",
          tone: "info",
          route: "/strategies",
          active: true,
        });
      } else if (item.origin === "folder") {
        result.push({
          id: item.id,
          name: item.name,
          meta: "strategies/ 資料夾",
          stage: 0,
          stageLabel: "提案",
          progress: "待驗證",
          detail: "尚未核准 · 可先執行回測與滾動驗證",
          color: "#a1a1aa",
          tone: "muted",
          route: "/backtest",
          active: false,
        });
      } else {
        result.push({
          id: item.id,
          name: item.name,
          meta: item.version,
          stage: 1,
          stageLabel: "研究目錄",
          progress: "僅研究",
          detail: "尚無有效核准 · 僅供研究與回測",
          color: "#7faee2",
          tone: "info",
          route: "/backtest",
          active: false,
        });
      }
    }

    return result.sort((a, b) => b.stage - a.stage || a.name.localeCompare(b.name));
  }, [signals, registeredStrategies, bots]);

  const activeCount = allRows.filter((r) => r.active).length;
  const rows = activeOnly ? allRows.filter((r) => r.active) : allRows;

  return (
    <div ref={cardRef} className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40 relative", className)}>
      <div className="flex items-center justify-between px-3 h-9 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
        <CardHeaderTitle
          cardId="pipeline"
          title="策略管線"
          subtext={
            !isSuperNarrow ? (
              <span className="px-1.5 py-0.5 rounded bg-background/60 border border-border/60 text-t1 font-mono text-muted-foreground leading-none">
                {rows.length} 策略
              </span>
            ) : undefined
          }
        />
        <CardHeaderTabs<"all" | "active">
          items={[
            { id: "all", label: "全部", count: allRows.length },
            { id: "active", label: "進行中", count: activeCount },
          ]}
          value={activeOnly ? "active" : "all"}
          onChange={(id) => setActiveOnly(id === "active")}
        />
      </div>

      {/* 寬版 5 階段表頭 */}
      {!isNarrow && rows.length > 0 && (
        <div className={cn("grid gap-2.5 px-3 py-1.5 border-b border-border/70 bg-background/35 text-t1 font-mono text-muted-foreground shrink-0", gridColsClass)}>
          <span>策略 / 標的</span>
          <div className="grid grid-cols-5 text-center">
            {STAGES.map((label, idx) => (
              <span key={label} className={cn((idx === 2 || idx === 4) && "text-primary font-semibold")}>
                {label}
              </span>
            ))}
          </div>
          {isUltraWide && <span>當前進度與狀態</span>}
          <span />
        </div>
      )}

      <div className="flex-1 min-h-0 overflow-y-auto divide-y divide-border/40 custom-scrollbar pb-2">
        {rows.length === 0 ? (
          <div className="h-full flex items-center justify-center py-8 text-t2 font-mono text-muted-foreground">
            {signals.loaded ? "尚無策略紀錄" : "讀取策略管線中…"}
          </div>
        ) : (
          rows.map((row) => (
            <div
              key={row.id}
              onClick={() => navigate(row.route)}
              title={row.detail}
              className={cn(
                "px-3 hover:bg-white/[0.03] transition-colors cursor-pointer items-center group",
                isFlat ? "py-1.5" : "py-2.5",
                isNarrow ? "grid grid-cols-[minmax(0,1fr)_auto] gap-2" : cn("grid gap-2.5", gridColsClass)
              )}
            >
              <div className="min-w-0">
                <div className="text-t3 font-semibold text-foreground group-hover:text-primary transition-colors truncate leading-tight font-sans">
                  {row.name}
                </div>
                <div className="text-t1 font-mono text-muted-foreground/80 truncate mt-0.5">{row.meta}</div>
              </div>

              {isNarrow ? (
                <div className="flex items-center gap-1.5 font-mono text-t1 shrink-0">
                  <span className={cn("px-1.5 py-0.5 rounded border leading-none font-semibold", tonePillClass(row.tone))}>
                    {row.stageLabel}
                  </span>
                  {!isSuperNarrow && (
                    <span className="w-12 h-1.5 rounded-full bg-border overflow-hidden inline-block">
                      <span className="block h-full rounded-full" style={{ width: `${STAGE_BAR_PCT[row.stage]}%`, backgroundColor: row.color }} />
                    </span>
                  )}
                  <span className={cn("min-w-[40px] text-right", toneTextClass(row.tone))}>{row.progress}</span>
                </div>
              ) : (
                <>
                  <div className={cn("relative grid grid-cols-5 items-start pt-1", isFlat ? "h-7" : "h-8")}>
                    <span className="absolute left-[10%] right-[10%] top-[9px] h-[2px] bg-white/[0.09] rounded-full" />
                    <span
                      className="absolute left-[10%] top-[9px] h-[2px] rounded-full transition-all"
                      style={{ width: `${row.stage * 20}%`, backgroundColor: row.color }}
                    />
                    {STAGES.map((st, idx) => {
                      const isDone = idx < row.stage;
                      const isCurrent = idx === row.stage;
                      return (
                        <div key={st} className="relative z-10 flex flex-col items-center">
                          <span
                            className={cn(
                              "size-2.5 rounded-full border-2",
                              isDone && "border-transparent"
                            )}
                            style={{
                              borderColor: isDone || isCurrent ? row.color : "rgba(255,255,255,0.18)",
                              backgroundColor: isDone || isCurrent
                                ? row.color
                                : "var(--surface)",
                            }}
                          />
                          {isCurrent && (
                            <span className={cn("mt-1.5 text-t1 font-mono whitespace-nowrap leading-none", toneTextClass(row.tone))}>
                              {row.progress}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  {isUltraWide && (
                    <span className="text-t2 text-muted-foreground font-sans truncate">
                      {row.detail}
                    </span>
                  )}
                  <ChevronRight className="size-3.5 text-muted-foreground/30 group-hover:text-primary transition-colors justify-self-end" />
                </>
              )}
            </div>
          ))
        )}
      </div>

      <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-5 bg-gradient-to-t from-surface/90 to-transparent" />
    </div>
  );
}
