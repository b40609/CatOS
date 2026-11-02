import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import {
  Pause,
  Play,
  Plus,
  RotateCw,
  Cpu,
  Layers,
  ShieldCheck,
  CheckCircle2,
  ArrowRight,
  Clock,
  Server,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { AppShell } from "@/components/catos/shell";
import { strategies, type Bot } from "@/lib/mock/data";
import { fmtSigned } from "@/hooks/use-live";
import { PulseBeacon } from "@/components/catos/pulse-beacon";
import { cn } from "@/lib/utils";
import { INSPECTOR_BOTS, useInspectorStore } from "@/state/inspectorStore";

export const Route = createFileRoute("/bots")({
  head: () => ({
    meta: [
      { title: "實例監控 (Fleet) — catOS Quant Terminal" },
      {
        name: "description",
        content: "catOS 實例監控：監控各量化策略實例之運行狀態、合約持倉、延遲與即時損益，一鍵啟停重啟。",
      },
      { property: "og:title", content: "實例監控 (Fleet) — catOS Quant Terminal" },
      {
        property: "og:description",
        content: "監控各量化策略實例之運行狀態、合約持倉、延遲與即時損益，一鍵啟停重啟。",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: BotManagement,
});

const STATUS_META: Record<Bot["status"], { text: string; dot: string; label: string }> = {
  running: { text: "text-up", dot: "bg-up", label: "RUNNING" },
  paused: { text: "text-muted-foreground", dot: "bg-muted-foreground", label: "PAUSED" },
  error: { text: "text-down", dot: "bg-down", label: "ERROR" },
};

const BOT_FLEET: Bot[] = [
  {
    id: "tabby",
    name: "BOT-BTC-15M",
    strategy: "突破唐奇安 (breakout_v22)",
    market: "BTC-USDT-SWAP",
    status: "running",
    position: "LONG 1.20 BTC",
    pnlToday: 850.56,
    uptimeHours: 412,
    latencyMs: 18,
  },
  {
    id: "calico",
    name: "BOT-ETH-1H",
    strategy: "趨勢追蹤 (trend_follow)",
    market: "ETH-USDT-SWAP",
    status: "running",
    position: "LONG 13.50 ETH",
    pnlToday: 749.25,
    uptimeHours: 189,
    latencyMs: 24,
  },
  {
    id: "mochi",
    name: "BOT-SOL-5M",
    strategy: "自適應網格 (grid_mm)",
    market: "SOL-USDT-SWAP",
    status: "running",
    position: "LONG 135.0 SOL",
    pnlToday: 553.50,
    uptimeHours: 64,
    latencyMs: 12,
  },
  {
    id: "shiro",
    name: "BOT-ARB-1H",
    strategy: "跨所統計套利 (pairs)",
    market: "ARB-USDT-SWAP",
    status: "paused",
    position: "FLAT 0.00",
    pnlToday: 0.0,
    uptimeHours: 0,
    latencyMs: 0,
  },
];

function useLiveBots(seed: Bot[]) {
  const [rows, setRows] = useState(seed);
  useEffect(() => {
    const id = setInterval(() => {
      setRows((prev) =>
        prev.map((b) =>
          b.status === "running"
            ? {
                ...b,
                pnlToday: Number((b.pnlToday + (Math.random() - 0.44) * 26).toFixed(2)),
                latencyMs: Math.max(6, Math.round(b.latencyMs + (Math.random() - 0.5) * 4)),
              }
            : b,
        ),
      );
    }, 2400);
    return () => clearInterval(id);
  }, []);
  return [rows, setRows] as const;
}

function NewBotDialog({ onDeploy }: { onDeploy: (bot: Bot) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("BOT-AVAX-15M");
  const [strategyId, setStrategyId] = useState(strategies[0]?.id || "s1");
  const [market, setMarket] = useState("AVAX-USDT-SWAP");
  const [budget, setBudget] = useState("50,000 USDT");

  const handleDeploy = () => {
    const selectedStrat = strategies.find((s) => s.id === strategyId) || strategies[0];
    const newBot: Bot = {
      id: `bot-${Date.now().toString(36)}`,
      name,
      strategy: selectedStrat?.name || "SMA 趨勢追蹤",
      market,
      status: "running",
      position: `0.00 ${market.split("-")[0]}`,
      pnlToday: 0.0,
      latencyMs: 18,
      uptimeHours: 0,
    };
    onDeploy(newBot);
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button className="num flex items-center gap-1.5 border border-primary/60 bg-primary/10 px-3 py-1 text-xs font-semibold text-primary transition-colors hover:bg-primary hover:text-primary-foreground rounded cursor-pointer">
          <Plus className="size-3.5" /> 部署新策略實例
        </button>
      </DialogTrigger>
      <DialogContent className="border-border bg-surface max-w-md">
        <DialogHeader>
          <DialogTitle className="font-mono text-primary text-sm flex items-center gap-2">
            <Server className="size-4 text-primary" />
            部署新策略實例 (1 Bot : 1 SWAP)
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            catOS 嚴格規範：單一合約由單一 Bot 獨佔，OKX 專用子帳戶隔離。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-1">
          <div className="space-y-1">
            <Label className="text-[11px] font-mono text-muted-foreground">實例代號 (Worker ID)</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="BOT-AVAX-15M"
              className="font-mono text-xs bg-background h-8"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-[11px] font-mono text-muted-foreground">綁定策略模型</Label>
            <Select value={strategyId} onValueChange={setStrategyId}>
              <SelectTrigger className="bg-background text-xs h-8 font-mono">
                <SelectValue placeholder="選擇策略" />
              </SelectTrigger>
              <SelectContent className="border-border bg-surface">
                {strategies.map((s) => (
                  <SelectItem key={s.id} value={s.id} className="text-xs font-mono">
                    {s.name} · {s.code} ({s.kind})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-[11px] font-mono text-muted-foreground">OKX SWAP 合約代碼</Label>
              <Input
                value={market}
                onChange={(e) => setMarket(e.target.value)}
                className="font-mono text-xs bg-background h-8"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-[11px] font-mono text-muted-foreground">初始保證金預算</Label>
              <Input
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                className="font-mono text-xs bg-background h-8"
              />
            </div>
          </div>
          <div className="rounded border border-primary/25 bg-primary/5 p-2.5 text-[11px] space-y-1">
            <div className="flex items-center gap-1.5 text-primary font-medium">
              <CheckCircle2 className="size-3.5" />
              <span>Supervisor 強制注入參數</span>
            </div>
            <p className="text-muted-foreground font-mono text-[10px] pl-5">
              margin: cross · posMode: net_mode · 唯讀 Worker 無金鑰連線
            </p>
          </div>
        </div>
        <DialogFooter>
          <button
            onClick={handleDeploy}
            className="w-full border border-primary bg-primary text-primary-foreground font-semibold px-3 py-1.5 text-xs rounded hover:opacity-90 transition-opacity font-mono cursor-pointer"
          >
            確認部署並分配獨佔 Worker (本地模擬)
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function BotManagement() {
  const [rows, setRows] = useLiveBots(BOT_FLEET);
  const { selectedBotId: globalSelectedId, selectBot } = useInspectorStore();
  const [selectedBotId, setSelectedBotId] = useState<string>(globalSelectedId || "tabby");

  const handleSelect = (id: string) => {
    setSelectedBotId(id);
    selectBot(id);
  };

  const set = (id: string, status: Bot["status"]) =>
    setRows((prev) =>
      prev.map((b) =>
        b.id === id
          ? { ...b, status, uptimeHours: status === "running" ? b.uptimeHours : 0 }
          : b,
      ),
    );

  const totalBots = rows.length;
  const runningBots = rows.filter((b) => b.status === "running").length;
  const pausedBots = rows.filter((b) => b.status === "paused").length;
  const errorBots = rows.filter((b) => b.status === "error").length;
  const totalPnl = rows.reduce((acc, b) => acc + b.pnlToday, 0);
  const avgLatency = Math.round(rows.reduce((acc, b) => acc + b.latencyMs, 0) / (totalBots || 1));

  const selectedBot = rows.find((b) => b.id === selectedBotId) || rows[0];
  const inspector = INSPECTOR_BOTS[selectedBot?.id || "tabby"] || INSPECTOR_BOTS.tabby;

  return (
    <AppShell>
      {/* 頂部架構規範與狀態摘要條 */}
      <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2 rounded border border-border/80 bg-surface/90 px-3 py-1.5 text-xs font-mono shadow-xs backdrop-blur-md">
        <div className="flex items-center gap-2.5">
          <span className="font-mono text-[9.5px] font-bold text-primary bg-primary/10 border border-primary/25 rounded px-1.5 py-0.5 uppercase tracking-wider">
            FLEET
          </span>
          <span className="text-muted-foreground">總數: <strong className="text-foreground">{totalBots}</strong></span>
          <span className="text-border">|</span>
          <span className="text-up font-bold flex items-center gap-1"><PulseBeacon size={3.5} variant="up" /> 在線: {runningBots}</span>
          <span className="text-border">|</span>
          <span className="text-muted-foreground">暫停: <strong className="text-foreground">{pausedBots}</strong></span>
          <span className="text-border">|</span>
          <span className={cn("font-bold", errorBots > 0 ? "text-down" : "text-muted-foreground")}>異常: {errorBots}</span>
          <span className="text-border">|</span>
          <span className="text-muted-foreground">平均延遲: <strong className="text-primary font-bold">{avgLatency}ms</strong></span>
          <span className="text-border">|</span>
          <span className="text-muted-foreground">今日損益: <strong className={cn("font-bold", totalPnl >= 0 ? "text-up" : "text-down")}>{fmtSigned(totalPnl)}</strong></span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground font-mono hidden md:inline">1 Bot : 1 SWAP (展示資料 · 本地模擬)</span>
          <NewBotDialog onDeploy={(b) => { setRows((prev) => [b, ...prev]); handleSelect(b.id); }} />
        </div>
      </div>

      {/* 主體：左側機器人表格 + 右側深層審計面板 */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 items-start">
        {/* 左側：機器人表格 (佔 7 欄) */}
        <div className="lg:col-span-7 rounded-xl border border-border/80 bg-surface/90 overflow-hidden shadow-sm">
          <div className="flex items-center justify-between border-b border-border/80 px-3.5 py-2.5 bg-secondary/30">
            <div className="flex items-center gap-2">
              <Server className="size-4 text-primary" />
              <span className="text-xs font-semibold text-foreground">策略實例陣列 (Strategy Bot Fleet)</span>
            </div>
            <span className="text-[10.5px] font-mono text-muted-foreground">點選實例檢視完整審計鏈條</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-border/70 bg-secondary/10">
                  {["狀態", "實例代號", "綁定策略", "獨佔合約", "當前部位", "今日損益", "延遲", "操作"].map(
                    (h) => (
                      <th key={h} className="px-3 py-2 text-[10px] font-mono uppercase text-muted-foreground font-medium">
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {rows.map((b) => {
                  const m = STATUS_META[b.status];
                  const isSelected = b.id === selectedBot?.id;
                  return (
                    <tr
                      key={b.id}
                      onClick={() => handleSelect(b.id)}
                      className={cn(
                        "cursor-pointer transition-colors",
                        isSelected
                          ? "bg-secondary/60"
                          : "hover:bg-secondary/40",
                      )}
                    >
                      <td className="px-3 py-2.5">
                        <span className="flex items-center gap-1.5">
                          {b.status === "running" ? (
                            <PulseBeacon size={4} variant="up" />
                          ) : (
                            <span className={cn("size-1.5 rounded-full", m.dot)} />
                          )}
                          <span className={cn("font-mono text-[10px] font-bold", m.text)}>{m.label}</span>
                        </span>
                      </td>
                      <td className="font-mono px-3 py-2.5 text-foreground font-bold">{b.name}</td>
                      <td className="px-3 py-2.5 text-muted-foreground text-[11px]">{b.strategy}</td>
                      <td className="font-mono px-3 py-2.5 text-primary text-[11px] font-semibold">{b.market}</td>
                      <td className="font-mono px-3 py-2.5 text-foreground/90 text-[11px] font-medium">{b.position}</td>
                      <td className={cn("font-mono px-3 py-2.5 font-bold text-[11px]", b.pnlToday >= 0 ? "text-up" : "text-down")}>
                        {fmtSigned(b.pnlToday)}
                      </td>
                      <td className="font-mono px-3 py-2.5 text-muted-foreground text-[11px]">{b.latencyMs}ms</td>
                      <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                        <span className="flex items-center gap-1">
                          <button
                            title="啟動 Worker"
                            onClick={() => set(b.id, "running")}
                            className="rounded border border-border p-1 text-up hover:border-up/60 hover:bg-up/10 transition-colors cursor-pointer"
                          >
                            <Play className="size-2.5" />
                          </button>
                          <button
                            title="暫停決策"
                            onClick={() => set(b.id, "paused")}
                            className="rounded border border-border p-1 text-muted-foreground hover:border-primary/60 hover:bg-primary/10 transition-colors cursor-pointer"
                          >
                            <Pause className="size-2.5" />
                          </button>
                          <button
                            title="重啟進程"
                            onClick={() => set(b.id, "running")}
                            className="rounded border border-border p-1 text-primary hover:border-primary/60 hover:bg-primary/10 transition-colors cursor-pointer"
                          >
                            <RotateCw className="size-2.5" />
                          </button>
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* 右側：選中實例之深度管線與審計面板 (佔 5 欄) */}
        {selectedBot && (
          <div className="lg:col-span-5 rounded-xl border border-border/80 bg-surface/90 p-3.5 space-y-3 shadow-sm">
            
            {/* 1. 實例標頭與即時狀態 */}
            <div className="flex items-center justify-between border-b border-border/70 pb-2.5">
              <div className="flex items-center gap-2">
                <Cpu className="size-4 text-primary" />
                <div>
                  <h3 className="text-xs font-bold font-mono text-foreground">{selectedBot.name}</h3>
                  <p className="text-[10px] text-muted-foreground font-mono">{selectedBot.market} · {selectedBot.strategy}</p>
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                <span className={cn("px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase", STATUS_META[selectedBot.status].text, "bg-secondary")}>
                  {selectedBot.status}
                </span>
              </div>
            </div>

            {/* 2. 即時策略意圖與觸發標尺 */}
            <div className="rounded border border-border/70 bg-secondary/40 p-2.5 space-y-1.5 font-mono text-xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="px-1.5 py-0.2 rounded bg-primary/15 text-primary text-[9.5px] font-bold border border-primary/25">
                    即時意圖
                  </span>
                  <span className="font-bold text-foreground text-[11px]">
                    {inspector.intentSummary}
                  </span>
                </div>
                <div className="flex items-center gap-1 text-[9.5px] text-muted-foreground">
                  <Clock className="size-3 text-primary/80" />
                  <span>下次評估:</span>
                  <span className="text-foreground font-semibold">{inspector.nextEvalCountdown ?? "15m 收盤"}</span>
                </div>
              </div>

              {inspector.lowerExitPrice && inspector.lowerExitPrice !== "—" && (
                <div className="flex items-center gap-1.5 text-[9.5px] text-muted-foreground pt-0.5">
                  <span className="text-rose-400 font-semibold">[平倉下軌 {inspector.lowerExitPrice}]</span>
                  <span className="text-border">──────</span>
                  <span className="text-primary font-bold">(現價 {inspector.markPrice} · 續抱)</span>
                  <span className="text-border">──────</span>
                  <span className="text-emerald-400 font-semibold">[加倉上軌 {inspector.upperAddPrice}]</span>
                </div>
              )}
            </div>

            {/* 3. 五階段執行鏈條 (Pipeline Trace) */}
            <div className="rounded border border-border/70 bg-secondary/30 p-2.5 space-y-2">
              <div className="flex items-center justify-between text-[10.5px] font-bold text-muted-foreground uppercase">
                <div className="flex items-center gap-1.5">
                  <Layers className="size-3.5 text-primary" />
                  <span>五階段執行鏈條 (Pipeline Trace)</span>
                </div>
                <span className="text-[9.5px] font-mono text-primary font-semibold">
                  {inspector.traceLatency ?? "總延遲 48ms (OKX 28ms · 本地 20ms)"}
                </span>
              </div>

              {/* 橫向緊湊流向指示器 */}
              <div className="flex items-center justify-between gap-1 p-1.5 rounded bg-background/50 border border-border/60 overflow-x-auto">
                {inspector.stages.map((stage, idx) => (
                  <div key={stage.name} className="flex items-center gap-1 shrink-0">
                    <div className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[9.5px] font-mono font-medium bg-emerald-400/10 border border-emerald-400/25 text-emerald-300">
                      <span>0{idx + 1}</span>
                      <span>{stage.name}</span>
                      <CheckCircle2 className="size-2.5 text-emerald-400" />
                    </div>
                    {idx < inspector.stages.length - 1 && (
                      <ArrowRight className="size-2.5 text-muted-foreground/60 shrink-0" />
                    )}
                  </div>
                ))}
              </div>

              {/* 五階段具體依據清單 */}
              <div className="space-y-1.5 text-[10.5px] font-mono leading-tight pt-1">
                {inspector.stages.map((stage, idx) => (
                  <div key={stage.name} className="flex items-baseline justify-between border-b border-border/30 pb-1">
                    <span className="text-muted-foreground shrink-0 w-24">0{idx + 1} {stage.name}</span>
                    <span className="text-foreground/90 font-medium text-right truncate">
                      {stage.detail}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* 4. 交易所停損保護與 OKX 委託憑證 */}
            <div className="rounded border border-border/70 bg-secondary/30 p-2.5 space-y-2 font-mono">
              <div className="flex items-center justify-between text-[10.5px] font-bold text-muted-foreground uppercase">
                <div className="flex items-center gap-1.5">
                  <ShieldCheck className="size-3.5 text-primary" />
                  <span>交易所端硬停損 (OKX 條件單)</span>
                </div>
                <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-emerald-400/10 text-emerald-400 border border-emerald-400/30">
                  生效防護中
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[10px]">
                <div className="p-2 rounded bg-background/60 border border-border/60">
                  <span className="text-[9px] text-muted-foreground block">觸發停損價</span>
                  <span className="text-[12px] font-bold text-foreground block">{inspector.p6StopPrice}</span>
                  <span className="text-[9px] text-emerald-400 block">{inspector.p6DistPct} (距 Mark 價)</span>
                </div>
                <div className="p-2 rounded bg-background/60 border border-border/60">
                  <span className="text-[9px] text-muted-foreground block">交易所委託憑證</span>
                  <span className="text-[10px] font-semibold text-primary block truncate">{inspector.algoOrderId ?? "algo_41cb_948201"}</span>
                  <span className="text-[9px] text-muted-foreground block">成本: {inspector.costBasis ?? inspector.entryPrice}</span>
                </div>
              </div>

              <div className="space-y-1 text-[9.5px] text-muted-foreground border-t border-border/40 pt-1.5">
                <div className="flex items-center justify-between">
                  <span>單幣預算占用:</span>
                  <span className="text-foreground font-semibold">{inspector.p6BudgetPct}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>剩餘加倉額度:</span>
                  <span className="text-emerald-400 font-semibold">{inspector.remainingQuota ?? "$30,205 USDT"}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>日損鎖存狀態:</span>
                  <span className="text-up font-semibold">NORMAL (未觸發 10% 軟鎖存)</span>
                </div>
              </div>
            </div>

            {/* 5. 快速控制按鈕 */}
            <div className="flex gap-2 pt-1 font-mono">
              <button
                onClick={() => set(selectedBot.id, selectedBot.status === "running" ? "paused" : "running")}
                className="flex-1 rounded border border-border/80 bg-secondary/60 hover:bg-secondary py-1.5 text-xs font-semibold text-foreground transition-colors cursor-pointer"
              >
                {selectedBot.status === "running" ? "暫停決策" : "恢復運行"}
              </button>
              <button
                onClick={() => set(selectedBot.id, "running")}
                className="flex-1 rounded border border-primary/50 bg-primary/10 hover:bg-primary/20 py-1.5 text-xs font-semibold text-primary transition-colors cursor-pointer"
              >
                重啟 Worker
              </button>
            </div>

          </div>
        )}
      </div>
    </AppShell>
  );
}
