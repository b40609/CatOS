import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Pause, Play, Plus, RotateCw, ShieldAlert, Cpu, Network, CheckCircle2, Server } from "lucide-react";
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
import { AppShell, PageHead } from "@/components/catos/shell";
import { bots as SEED, strategies, type Bot } from "@/lib/mock/data";
import { fmtSigned } from "@/hooks/use-live";
import { PulseBeacon } from "@/components/catos/pulse-beacon";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/bots")({
  head: () => ({
    meta: [
      { title: "機器人管理 — catOS 交易機器人監控" },
      {
        name: "description",
        content: "catOS 機器人管理：監控每台交易機器人的狀態、持倉、延遲與今日損益，一鍵啟停重啟。",
      },
      { property: "og:title", content: "機器人管理 — catOS 交易機器人監控" },
      {
        property: "og:description",
        content: "監控每台交易機器人的狀態、持倉、延遲與今日損益，一鍵啟停重啟。",
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

function useLiveBots(seed: Bot[]) {
  const [rows, setRows] = useState(seed);
  useEffect(() => {
    const id = setInterval(() => {
      setRows((prev) =>
        prev.map((b) =>
          b.status === "running"
            ? {
                ...b,
                pnlToday: Number((b.pnlToday + (Math.random() - 0.44) * 260).toFixed(2)),
                latencyMs: Math.max(6, Math.round(b.latencyMs + (Math.random() - 0.5) * 6)),
              }
            : b,
        ),
      );
    }, 1800);
    return () => clearInterval(id);
  }, []);
  return [rows, setRows] as const;
}

function NewBotDialog() {
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button className="num flex items-center gap-1.5 border border-primary/60 bg-primary/10 px-3 py-1 text-xs font-semibold text-primary transition-colors hover:bg-primary hover:text-primary-foreground rounded">
          <Plus className="size-3.5" /> 部署新機器人
        </button>
      </DialogTrigger>
      <DialogContent className="border-border bg-surface max-w-md">
        <DialogHeader>
          <DialogTitle className="font-mono text-primary text-sm flex items-center gap-2">
            <Server className="size-4 text-primary" />
            部署新 Bot 執行單元 (1 Bot : 1 SWAP)
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            catOS 嚴格規範：單一合約由單一 Bot 獨佔，強制注入 KOL 返佣 Tag。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-1">
          <div className="space-y-1">
            <Label className="text-[11px] font-mono text-muted-foreground">機器人名稱 (Worker ID)</Label>
            <Input placeholder="CAT-07 / SEOUL" className="font-mono text-xs bg-background h-8" />
          </div>
          <div className="space-y-1">
            <Label className="text-[11px] font-mono text-muted-foreground">綁定策略模型</Label>
            <Select defaultValue={strategies[0]?.id}>
              <SelectTrigger className="bg-background text-xs h-8">
                <SelectValue placeholder="選擇策略" />
              </SelectTrigger>
              <SelectContent className="border-border bg-surface">
                {strategies.map((s) => (
                  <SelectItem key={s.id} value={s.id} className="text-xs">
                    {s.name} · {s.code} ({s.kind})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-[11px] font-mono text-muted-foreground">OKX SWAP 合約代碼</Label>
              <Input defaultValue="BTC-USDT-SWAP" className="font-mono text-xs bg-background h-8" />
            </div>
            <div className="space-y-1">
              <Label className="text-[11px] font-mono text-muted-foreground">初始保證金預算</Label>
              <Input defaultValue="500,000 USDT" className="font-mono text-xs bg-background h-8" />
            </div>
          </div>
          <div className="rounded border border-primary/25 bg-primary/5 p-2.5 text-[11px] space-y-1">
            <div className="flex items-center gap-1.5 text-primary font-medium">
              <CheckCircle2 className="size-3.5" />
              <span>Supervisor 強制注入參數</span>
            </div>
            <p className="text-muted-foreground font-mono text-[10px] pl-5">
              tag: "41cb53c54d6dABDE" · margin: cross · posMode: net_mode
            </p>
          </div>
        </div>
        <DialogFooter>
          <button
            onClick={() => setOpen(false)}
            className="w-full border border-primary bg-primary text-primary-foreground font-semibold px-3 py-1.5 text-xs rounded hover:opacity-90 transition-opacity"
          >
            確認部署並分配獨佔 Worker
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function BotManagement() {
  const [rows, setRows] = useLiveBots(SEED);
  const [selectedBotId, setSelectedBotId] = useState<string>("b1");

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

  return (
    <AppShell>
      <PageHead
        code="engine // bot-fleet"
        title="機器人管理集群"
        desc="OKX 專用子帳戶 · 1 Bot : 1 SWAP 獨佔合約 · 毫秒級 IPC 監控"
        right={<NewBotDialog />}
      />

      {/* 頂部架構規範與狀態摘要條 */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2.5 rounded-lg border border-primary/25 bg-primary/5 px-3 py-2 text-xs">
        <div className="flex items-center gap-2">
          <ShieldAlert className="size-4 text-primary shrink-0" />
          <span className="font-semibold text-foreground">OKX 執行架構約定：</span>
          <span className="text-muted-foreground font-mono text-[11px]">
            1 Bot : 1 SWAP 獨佔 · Supervisor 強制注入 tag: 41cb53c54d6dABDE · cross + net_mode
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-mono">
          <span className="text-muted-foreground">子帳戶隔離: <span className="text-up font-bold">VERIFIED</span></span>
          <span className="text-border">|</span>
          <span className="text-muted-foreground">平均延遲: <span className="text-primary font-bold">{avgLatency}ms</span></span>
          <span className="text-border">|</span>
          <span className="text-muted-foreground">集群今日損益: <span className={cn("font-bold", totalPnl >= 0 ? "text-up" : "text-down")}>{fmtSigned(totalPnl)}</span></span>
        </div>
      </div>

      {/* 4 大核心 KPI 指標卡 */}
      <div className="mb-3 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        <div className="rounded-lg border border-border/80 bg-surface/90 p-2.5">
          <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">集群總節點</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="font-mono text-lg font-bold text-foreground">{totalBots}</span>
            <span className="text-[10px] text-muted-foreground font-mono">Workers</span>
          </div>
        </div>
        <div className="rounded-lg border border-up/30 bg-up/5 p-2.5">
          <span className="text-[10px] font-mono uppercase tracking-wider text-up">在線運行中</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="font-mono text-lg font-bold text-up">{runningBots}</span>
            <span className="flex items-center gap-1 text-[10px] text-up font-mono">
              <PulseBeacon size={4} variant="up" /> ACTIVE
            </span>
          </div>
        </div>
        <div className="rounded-lg border border-border/80 bg-surface/90 p-2.5">
          <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">暫停維護</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="font-mono text-lg font-bold text-muted-foreground">{pausedBots}</span>
            <span className="text-[10px] text-muted-foreground font-mono">PAUSED</span>
          </div>
        </div>
        <div className="rounded-lg border border-down/30 bg-down/5 p-2.5">
          <span className="text-[10px] font-mono uppercase tracking-wider text-down">異常警告</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="font-mono text-lg font-bold text-down">{errorBots}</span>
            <span className="text-[10px] text-down font-mono">{errorBots > 0 ? "ATTENTION" : "CLEAR"}</span>
          </div>
        </div>
      </div>

      {/* 主體：左側機器人表格 + 右側選中機器人審計詳情面板 */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 items-start">
        {/* 左側：機器人表格 (佔 8 欄) */}
        <div className="lg:col-span-8 rounded-xl border border-border/80 bg-surface/90 overflow-hidden shadow-sm">
          <div className="flex items-center justify-between border-b border-border/80 px-3.5 py-2 bg-secondary/30">
            <div className="flex items-center gap-2">
              <Server className="size-3.5 text-primary" />
              <span className="text-xs font-semibold text-foreground">活躍機器人陣列 (Bot Fleet Table)</span>
            </div>
            <span className="text-[10px] font-mono text-muted-foreground">點選列檢視執行期細節</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[56rem] text-left text-xs">
              <thead>
                <tr className="border-b border-border/70 bg-secondary/10">
                  {["狀態", "名稱 / ID", "綁定策略", "獨佔合約", "當前部位", "今日損益", "延遲", "運行", "操作"].map(
                    (h) => (
                      <th key={h} className="px-3 py-2 text-[10px] font-mono uppercase text-muted-foreground font-medium">
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {rows.map((b) => {
                  const m = STATUS_META[b.status];
                  const isSelected = b.id === selectedBot?.id;
                  return (
                    <tr
                      key={b.id}
                      onClick={() => setSelectedBotId(b.id)}
                      className={cn(
                        "border-b border-border/50 cursor-pointer transition-colors",
                        isSelected
                          ? "bg-primary/10 border-l-2 border-l-primary"
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
                      <td className="font-mono px-3 py-2.5 text-foreground font-medium">{b.name}</td>
                      <td className="px-3 py-2.5 text-muted-foreground text-[11px]">{b.strategy}</td>
                      <td className="font-mono px-3 py-2.5 text-primary text-[11px] font-semibold">{b.market}</td>
                      <td className="font-mono px-3 py-2.5 text-foreground/90 text-[11px]">{b.position}</td>
                      <td className={cn("font-mono px-3 py-2.5 font-bold text-[11px]", b.pnlToday >= 0 ? "text-up" : "text-down")}>
                        {fmtSigned(b.pnlToday)}
                      </td>
                      <td className="font-mono px-3 py-2.5 text-muted-foreground text-[11px]">{b.latencyMs}ms</td>
                      <td className="font-mono px-3 py-2.5 text-muted-foreground text-[11px]">{b.uptimeHours}h</td>
                      <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                        <span className="flex items-center gap-1">
                          <button
                            title="啟動 Worker"
                            onClick={() => set(b.id, "running")}
                            className="rounded border border-border p-1 text-up hover:border-up/60 hover:bg-up/10 transition-colors"
                          >
                            <Play className="size-2.5" />
                          </button>
                          <button
                            title="暫停決策"
                            onClick={() => set(b.id, "paused")}
                            className="rounded border border-border p-1 text-muted-foreground hover:border-primary/60 hover:bg-primary/10 transition-colors"
                          >
                            <Pause className="size-2.5" />
                          </button>
                          <button
                            title="重啟進程"
                            onClick={() => set(b.id, "running")}
                            className="rounded border border-border p-1 text-primary hover:border-primary/60 hover:bg-primary/10 transition-colors"
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

        {/* 右側：選中機器人即時審計卡 (佔 4 欄) */}
        {selectedBot && (
          <div className="lg:col-span-4 rounded-xl border border-border/80 bg-surface/90 p-3.5 space-y-3.5 shadow-sm">
            <div className="flex items-center justify-between border-b border-border/70 pb-2">
              <div className="flex items-center gap-2">
                <Cpu className="size-4 text-primary" />
                <div>
                  <h3 className="text-xs font-bold font-mono text-foreground">{selectedBot.name}</h3>
                  <p className="text-[10px] text-muted-foreground">獨立 Worker 程序細節</p>
                </div>
              </div>
              <span className={cn("px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase", STATUS_META[selectedBot.status].text, "bg-secondary")}>
                {selectedBot.status}
              </span>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between items-center py-1 border-b border-border/40">
                <span className="text-[11px] text-muted-foreground">獨佔合約 (1:1)</span>
                <span className="font-mono text-primary font-bold">{selectedBot.market}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-border/40">
                <span className="text-[11px] text-muted-foreground">當前部位</span>
                <span className="font-mono font-semibold text-foreground">{selectedBot.position}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-border/40">
                <span className="text-[11px] text-muted-foreground">今日累計損益</span>
                <span className={cn("font-mono font-bold", selectedBot.pnlToday >= 0 ? "text-up" : "text-down")}>
                  {fmtSigned(selectedBot.pnlToday)}
                </span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-border/40">
                <span className="text-[11px] text-muted-foreground">OKX API 延遲</span>
                <span className="font-mono text-foreground">{selectedBot.latencyMs} ms</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-border/40">
                <span className="text-[11px] text-muted-foreground">連續運行時間</span>
                <span className="font-mono text-foreground">{selectedBot.uptimeHours} 小時</span>
              </div>
            </div>

            <div className="rounded-lg border border-border/60 bg-secondary/30 p-2.5 space-y-1.5 text-[11px]">
              <div className="flex items-center gap-1.5 text-primary font-semibold">
                <Network className="size-3.5" />
                <span>風控與執行契約 (Invariants)</span>
              </div>
              <div className="text-[10px] font-mono text-muted-foreground space-y-1">
                <div className="flex justify-between">
                  <span>OKX Order Tag:</span>
                  <span className="text-foreground">41cb53c54d6dABDE</span>
                </div>
                <div className="flex justify-between">
                  <span>Margin & Mode:</span>
                  <span className="text-foreground">cross + net_mode</span>
                </div>
                <div className="flex justify-between">
                  <span>P6 災難停損:</span>
                  <span className="text-foreground">15.0% (Mark Tick Floor)</span>
                </div>
                <div className="flex justify-between">
                  <span>決策方式:</span>
                  <span className="text-foreground">Closed Bar (Decimal Core)</span>
                </div>
              </div>
            </div>

            <div className="flex gap-2 pt-1">
              <button
                onClick={() => set(selectedBot.id, selectedBot.status === "running" ? "paused" : "running")}
                className="flex-1 rounded border border-border/80 bg-secondary/60 hover:bg-secondary py-1.5 text-xs font-semibold text-foreground transition-colors"
              >
                {selectedBot.status === "running" ? "暫停決策" : "恢復運行"}
              </button>
              <button
                onClick={() => set(selectedBot.id, "running")}
                className="flex-1 rounded border border-primary/50 bg-primary/10 hover:bg-primary/20 py-1.5 text-xs font-semibold text-primary transition-colors"
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
