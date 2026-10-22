import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { ShieldCheck, RefreshCw, Lock, Unlock, HelpCircle, CheckCircle2 } from "lucide-react";
import { AppShell, PageHead, Panel } from "@/components/catos/shell";
import { DerivativesMetrics } from "@/components/catos/derivatives-metrics";
import { riskAlerts, riskRules as SEED } from "@/lib/mock/data";
import { useLiveNumber } from "@/hooks/use-live";
import { PulseBeacon } from "@/components/catos/pulse-beacon";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/risk")({
  head: () => ({
    meta: [
      { title: "風險控管 — catOS 曝險與熔斷儀表" },
      {
        name: "description",
        content: "catOS 風險控管：R1 風控期間基準、模擬曝險、槓桿、資金費率，搭配風控規則與警報時間軸。",
      },
    ],
  }),
  component: RiskManagement,
});

function Gauge({
  label,
  seed,
  vol,
  max,
  suffix,
  danger,
}: {
  label: string;
  seed: number;
  vol: number;
  max: number;
  suffix: string;
  danger: number;
}) {
  const { value } = useLiveNumber(seed, vol, 1700);
  const pct = Math.min(100, (value / max) * 100);
  const hot = value >= danger;
  const data = [
    { v: pct },
    { v: 100 - pct },
  ];

  return (
    <div className="panel flex flex-col items-center px-4 py-4">
      <p className="label-xs">{label}</p>
      <div className="relative h-[7.5rem] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="v"
              startAngle={210}
              endAngle={-30}
              innerRadius={42}
              outerRadius={56}
              stroke="none"
              isAnimationActive={false}
            >
              <Cell fill={hot ? "var(--color-down)" : "var(--color-gold)"} />
              <Cell fill="var(--color-surface-raised)" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <span
          className={cn(
            "num absolute inset-0 flex items-center justify-center pt-3 text-lg font-bold font-mono",
            hot ? "text-down" : "text-gold-bright",
          )}
        >
          {value.toFixed(2)}
          {suffix}
        </span>
      </div>
      <p className="num text-[0.65rem] text-muted-foreground font-mono">
        限額 {max}
        {suffix}
      </p>
    </div>
  );
}

const ALERT_TONE = {
  error: "border-down/60 text-down",
  warn: "border-warn/60 text-warn",
  info: "border-border text-muted-foreground",
} as const;

function RiskManagement() {
  const [rules, setRules] = useState(SEED);
  const [latchState, setLatchState] = useState<"NORMAL" | "SOFT_LATCH" | "HARD_KILL_SWITCH">("NORMAL");
  const [openRearmDialog, setOpenRearmDialog] = useState(false);
  const [rearmSuccess, setRearmSuccess] = useState(false);

  const handleRearm = () => {
    setLatchState("NORMAL");
    setOpenRearmDialog(false);
    setRearmSuccess(true);
    setTimeout(() => setRearmSuccess(false), 3000);
  };

  return (
    <AppShell>
      <PageHead
        code="guardian // risk-engine"
        title="風險控管中心"
        desc="E_risk = E_verified · Asia/Taipei 00:00 風控期間基準 · Soft 10% / Hard 20% 鎖存"
        right={
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 text-[11px] font-mono text-muted-foreground bg-secondary/80 border border-border/80 rounded px-2.5 py-1">
              <PulseBeacon size={4} />
              <span>展示資料 · 本地風控模擬</span>
            </span>
          </div>
        }
      />

      {/* 風控架構條款橫幅 (Scheme B 滿版純淨視野) */}
      <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/80 bg-surface/90 px-3.5 py-2 text-xs font-mono shadow-xs backdrop-blur-md">
        <div className="flex items-center gap-2.5">
          <span className="font-mono text-[9px] uppercase font-bold text-primary bg-primary/15 border border-primary/30 rounded px-1.5 py-0.2">
            GUARDIAN CORE
          </span>
          <span className="text-muted-foreground">
            規則鎖存: <strong className="text-foreground">Soft 10% (禁增倉) / Hard 20% (市價清倉 + 熔斷)</strong>
          </span>
          <span className="text-border">|</span>
          <span className="text-muted-foreground">Asia/Taipei 00:00 切日 · 僅人工恢復</span>
        </div>
        <div className="flex items-center gap-2 text-[10.5px] text-muted-foreground">
          <span>R1 本地 Python PASS</span>
          <span className="text-border">|</span>
          <span>HTTP 控制路由未掛載 (前端示範模式)</span>
        </div>
      </div>

      {/* ==================== R1 風控期間基準專用面板 ==================== */}
      <Panel
        title={
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-4 text-primary" />
            <span>R1 風控期間基準 (Risk Period Baseline · 2026-10-20 核准)</span>
          </div>
        }
        meta={
          <div className="flex items-center gap-2">
            {rearmSuccess && (
              <span className="text-up font-mono text-[10.5px] flex items-center gap-1">
                <CheckCircle2 className="size-3.5" /> 已完成人工 Re-arm (本地模擬)
              </span>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setOpenRearmDialog(true)}
              className="h-6 text-[10.5px] font-mono border-border bg-surface hover:bg-surface-raised"
            >
              <RefreshCw className="size-3 mr-1" /> 人工核准 Re-arm
            </Button>
          </div>
        }
      >
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 font-mono text-xs">
          <div className="rounded-lg border border-border/60 bg-background/40 p-3 space-y-1">
            <span className="text-[10px] text-muted-foreground block">起算時間 (Asia/Taipei)</span>
            <span className="text-sm font-bold text-foreground block">2026-10-20 00:00:15</span>
            <span className="text-[9.5px] text-muted-foreground">首次合格觀測原子建立</span>
          </div>

          <div className="rounded-lg border border-border/60 bg-background/40 p-3 space-y-1">
            <span className="text-[10px] text-muted-foreground block">風控期間基準權益 (E0)</span>
            <span className="text-sm font-bold text-primary block">12,500.00000000 USDT</span>
            <span className="text-[9.5px] text-muted-foreground">同日基準鎖定 · 不因虧損替換</span>
          </div>

          <div className="rounded-lg border border-border/60 bg-background/40 p-3 space-y-1">
            <span className="text-[10px] text-muted-foreground block">風控期間損益 (ΔEquity)</span>
            <span className="text-sm font-bold text-down block">-427.50000000 USDT</span>
            <span className="text-[9.5px] text-down font-medium">虧損 -3.42% (距 Soft 6.58%)</span>
          </div>

          <div className="rounded-lg border border-border/60 bg-background/40 p-3 space-y-1">
            <span className="text-[10px] text-muted-foreground block">鎖存狀態 (Latch Status)</span>
            <span className={cn(
              "text-sm font-bold block flex items-center gap-1",
              latchState === "NORMAL" ? "text-up" : "text-down"
            )}>
              {latchState === "NORMAL" ? <Unlock className="size-3.5" /> : <Lock className="size-3.5" />}
              {latchState}
            </span>
            <span className="text-[9.5px] text-muted-foreground">
              {latchState === "NORMAL" ? "未觸發 · 允許正常增倉" : "已鎖存 · 禁增倉"}
            </span>
          </div>
        </div>

        <div className="mt-3 pt-2.5 border-t border-border/40 text-[10.5px] font-mono text-muted-foreground flex flex-wrap items-center justify-between gap-2">
          <span>
            門檻: <strong className="text-foreground">Soft 10% (-1,250.00 USDT)</strong> · <strong className="text-foreground">Hard 20% (-2,500.00 USDT)</strong>
          </span>
          <span>
            約束: 排除起算後外部入出金 · 跨日/重啟/入金不自動解除鎖存 · 僅限人工判定恢復
          </span>
        </div>
      </Panel>

      {/* 4 大核心儀表盤 */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4 mt-3">
        <Gauge label="總曝險名目價值 (Total Exposure)" seed={18.42} vol={0.004} max={30} suffix="M" danger={26} />
        <Gauge label="帳戶有效槓桿 (Effective Leverage)" seed={2.81} vol={0.006} max={3.0} suffix="x" danger={2.85} />
        <Gauge label="單幣預算占比 (Single-Asset Cap)" seed={42.8} vol={0.005} max={50.0} suffix="%" danger={45.0} />
        <Gauge label="風控期間虧損 (Drawdown vs E0)" seed={3.42} vol={0.005} max={10.0} suffix="%" danger={8.0} />
      </div>

      <div className="mt-3"><DerivativesMetrics /></div>

      <div className="mt-3 grid gap-3 xl:grid-cols-[1.5fr_1fr]">
        <Panel title="risk rules · 風控規則設定 (示範)">
          <ul className="space-y-4">
            {rules.map((r) => (
              <li key={r.id} className="border-b border-border/60 pb-4 last:border-0 last:pb-0">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm text-foreground/90">{r.name}</p>
                    <p className="text-[0.7rem] text-muted-foreground">{r.desc}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="num text-sm text-gold-bright font-mono font-semibold">
                      {r.value}
                      {r.unit}
                    </span>
                    <Switch
                      checked={r.enabled}
                      onCheckedChange={(v) =>
                        setRules((prev) =>
                          prev.map((x) => (x.id === r.id ? { ...x, enabled: v } : x)),
                        )
                      }
                    />
                  </div>
                </div>
                <Slider
                  className="mt-3"
                  value={[r.value]}
                  min={r.min}
                  max={r.max}
                  step={r.unit === "/min" ? 10 : r.unit === "x" ? 0.5 : 1}
                  disabled={!r.enabled}
                  onValueChange={([v]) =>
                    setRules((prev) =>
                      prev.map((x) => (x.id === r.id ? { ...x, value: v ?? x.value } : x)),
                    )
                  }
                />
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="alert timeline · 警報時間軸" meta={<span className="label-xs">today</span>}>
          <ol className="relative space-y-4 border-l border-border pl-4">
            {riskAlerts.map((a) => (
              <li key={a.id} className="relative">
                <span
                  className={cn(
                    "absolute -left-[1.32rem] top-1.5 size-1.5 rounded-full",
                    a.level === "error"
                      ? "bg-down"
                      : a.level === "warn"
                        ? "bg-warn"
                        : "bg-muted-foreground",
                  )}
                />
                <div className="flex items-center gap-2">
                  <span className="num text-[0.7rem] text-muted-foreground font-mono">{a.time}</span>
                  <span
                    className={cn(
                      "num border px-1.5 py-0.5 text-[0.6rem] uppercase font-mono font-semibold",
                      ALERT_TONE[a.level],
                    )}
                  >
                    {a.level}
                  </span>
                </div>
                <p className="mt-1 text-xs text-foreground/85 leading-relaxed">{a.text}</p>
              </li>
            ))}
          </ol>
        </Panel>
      </div>

      {/* ==================== 人工核准 Re-arm 對話框 ==================== */}
      <Dialog open={openRearmDialog} onOpenChange={setOpenRearmDialog}>
        <DialogContent className="border-border bg-surface max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm font-bold text-foreground flex items-center gap-2">
              <RefreshCw className="size-4 text-primary" /> 人工核准解除風控鎖存 (Re-arm)
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              R1 核心規範：鎖存不因跨日、重啟或入金自動解除，需人工核實原風險原因已排除。
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2 text-xs font-mono">
            <div className="rounded border border-primary/25 bg-primary/5 p-3 space-y-1.5 text-[11px]">
              <span className="text-primary font-semibold flex items-center gap-1.5">
                <HelpCircle className="size-3.5" /> 系統執行邊界提醒
              </span>
              <p className="text-muted-foreground leading-relaxed">
                目前前端處於 Localhost 模擬展示階段，後端 R1 local-sim 已通過 197/197 獨立驗收，但尚未掛載 HTTP 控制路由。此處重置為本地狀態示範，不會對外發送真實訂單或修改資料庫。
              </p>
            </div>

            <div className="rounded border border-border/60 bg-background/50 p-2.5 space-y-1 text-[10.5px]">
              <div className="flex justify-between">
                <span className="text-muted-foreground">目前鎖存狀態:</span>
                <span className="text-foreground font-bold">{latchState}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">恢復後狀態:</span>
                <span className="text-up font-bold">NORMAL (允許增倉)</span>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setOpenRearmDialog(false)}
              className="text-xs font-mono h-8"
            >
              取消
            </Button>
            <Button
              size="sm"
              onClick={handleRearm}
              className="text-xs font-mono h-8 bg-primary text-primary-foreground hover:bg-primary/90"
            >
              確認人工恢復 (Re-arm)
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
