import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Pause, Play, Plus, RotateCw } from "lucide-react";
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
        <button className="num flex items-center gap-2 border border-gold/60 bg-accent px-3 py-1.5 text-xs text-gold-bright transition-colors hover:bg-gold hover:text-primary-foreground">
          <Plus className="size-3.5" /> 新增機器人
        </button>
      </DialogTrigger>
      <DialogContent className="border-border bg-surface">
        <DialogHeader>
          <DialogTitle className="font-mono text-gold-bright">部署新機器人</DialogTitle>
          <DialogDescription>介面示範用途，設定不會實際送出。</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label className="label-xs">名稱</Label>
            <Input placeholder="CAT-07 / SEOUL" className="num bg-background" />
          </div>
          <div className="space-y-1.5">
            <Label className="label-xs">綁定策略</Label>
            <Select>
              <SelectTrigger className="bg-background">
                <SelectValue placeholder="選擇策略" />
              </SelectTrigger>
              <SelectContent>
                {strategies.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name} · {s.code}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="label-xs">市場</Label>
              <Input placeholder="BTC-PERP" className="num bg-background" />
            </div>
            <div className="space-y-1.5">
              <Label className="label-xs">初始資金</Label>
              <Input placeholder="500,000 USDT" className="num bg-background" />
            </div>
          </div>
        </div>
        <DialogFooter>
          <button
            onClick={() => setOpen(false)}
            className="num border border-gold/60 px-3 py-1.5 text-xs text-gold-bright hover:bg-accent"
          >
            部署
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function BotManagement() {
  const [rows, setRows] = useLiveBots(SEED);
  const set = (id: string, status: Bot["status"]) =>
    setRows((prev) =>
      prev.map((b) =>
        b.id === id
          ? { ...b, status, uptimeHours: status === "running" ? b.uptimeHours : 0 }
          : b,
      ),
    );

  return (
    <AppShell>
      <PageHead
        code="module / bot-management"
        title="機器人管理"
        desc="交易所節點、幣種持倉與 24/7 運行指標 · 模擬數據"
        right={<NewBotDialog />}
      />

      <div className="mb-3 grid gap-3 sm:grid-cols-3">
        {(["running", "paused", "error"] as const).map((st) => (
          <div key={st} className="panel flex items-center gap-3 px-4 py-3">
            <span className={cn("size-2 rounded-full", STATUS_META[st].dot)} />
            <span className="label-xs">{STATUS_META[st].label}</span>
            <span className="num ml-auto text-xl text-gold-bright">
              {rows.filter((b) => b.status === st).length}
            </span>
          </div>
        ))}
      </div>

      <div className="panel overflow-x-auto">
        <table className="w-full min-w-[62rem] text-left text-xs">
          <thead>
            <tr className="border-b border-border">
              {["狀態", "機器人", "策略", "市場", "持倉", "今日損益", "延遲", "運行時間", "操作"].map(
                (h) => (
                  <th key={h} className="label-xs px-4 py-2.5 font-normal">
                    {h}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((b) => {
              const m = STATUS_META[b.status];
              return (
                <tr key={b.id} className="border-b border-border/60 hover:bg-secondary/50">
                  <td className="px-4 py-2.5">
                    <span className="flex items-center gap-2">
                      <span
                        className={cn(
                          "size-1.5 rounded-full",
                          m.dot,
                          b.status === "running" && "pulse-dot",
                        )}
                      />
                      <span className={cn("num text-[0.65rem]", m.text)}>{m.label}</span>
                    </span>
                  </td>
                  <td className="num px-4 py-2.5 text-foreground/90">{b.name}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{b.strategy}</td>
                  <td className="num px-4 py-2.5 text-muted-foreground">{b.market}</td>
                  <td className="num px-4 py-2.5 text-foreground/80">{b.position}</td>
                  <td
                    className={cn("num px-4 py-2.5", b.pnlToday >= 0 ? "text-up" : "text-down")}
                  >
                    {fmtSigned(b.pnlToday)}
                  </td>
                  <td className="num px-4 py-2.5 text-muted-foreground">{b.latencyMs} ms</td>
                  <td className="num px-4 py-2.5 text-muted-foreground">{b.uptimeHours} h</td>
                  <td className="px-4 py-2.5">
                    <span className="flex gap-1">
                      <button
                        aria-label="啟動"
                        onClick={() => set(b.id, "running")}
                        className="border border-border p-1 text-up transition-colors hover:border-up/60"
                      >
                        <Play className="size-3" />
                      </button>
                      <button
                        aria-label="暫停"
                        onClick={() => set(b.id, "paused")}
                        className="border border-border p-1 text-muted-foreground transition-colors hover:border-gold/60"
                      >
                        <Pause className="size-3" />
                      </button>
                      <button
                        aria-label="重啟"
                        onClick={() => set(b.id, "running")}
                        className="border border-border p-1 text-gold transition-colors hover:border-gold/60"
                      >
                        <RotateCw className="size-3" />
                      </button>
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
