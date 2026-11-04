import { useState } from "react";
import { cn } from "@/lib/utils";
import { useCatStore } from "@/state/catStore";
import { stateAdapter } from "@/state/stateAdapter";
import { shortId } from "@/lib/format";

const SLOT_LABEL: Record<string, string> = {
  idle: "閒置", starting: "啟動中", running: "運行中", stopping: "停止中",
  recovery_required: "待恢復", unavailable: "不可用",
};

/**
 * 頂部模擬服務狀態列：取代原行情帶（v1 沒有行情來源）。
 * 顯示連線狀態、服務槽位、build 漂移與未完成命令；不產生任何請求以外的副作用。
 */
export function SimulationStatusStrip({ className }: { className?: string }) {
  const service = useCatStore((s) => s.service);
  const connection = useCatStore((s) => s.connection);
  const mode = useCatStore((s) => s.mode);
  const pending = useCatStore((s) => s.pendingCommand);
  const [busy, setBusy] = useState(false);

  const statusTone =
    connection.status === "ok" ? "text-emerald-400" :
    connection.status === "loading" || connection.status === "idle" ? "text-muted-foreground" :
    connection.status === "mode_not_open" ? "text-cyan-400" : "text-rose-400";

  const statusText =
    connection.status === "ok" ? "已連線" :
    connection.status === "loading" ? "載入中" :
    connection.status === "idle" ? "未初始化" :
    connection.status === "mode_not_open" ? "模式未開放" :
    connection.status === "unavailable" ? `不可用 ${connection.detail ?? ""}` :
    `連線錯誤 ${connection.detail ?? ""}`;

  const retry = async () => {
    setBusy(true);
    try { await stateAdapter.retryPendingCommand(); } catch { /* recorded in command history */ } finally { setBusy(false); }
  };

  return (
    <div className={cn("flex items-center gap-2 text-t1 font-mono whitespace-nowrap min-w-0", className)}>
      <span className={cn("flex items-center gap-1", statusTone)}>
        <span className={cn("size-1.5 rounded-full", connection.status === "ok" ? "bg-emerald-400" : connection.status === "mode_not_open" ? "bg-cyan-400" : connection.status === "loading" ? "bg-muted-foreground animate-pulse" : "bg-rose-400")} />
        {mode === "local" ? "本機模擬" : mode.toUpperCase()} · {statusText}
      </span>
      {service && (
        <>
          <span className="text-border">|</span>
          <span className="text-muted-foreground">槽位 <strong className="text-foreground">{SLOT_LABEL[service.slot] ?? service.slot}</strong></span>
          <span className="text-border">|</span>
          <span className="text-muted-foreground" title={service.instance_id}>instance {shortId(service.instance_id)}</span>
          {service.restart_required && (
            <span className="px-1.5 py-0.2 rounded border border-amber-500/40 bg-amber-500/10 text-amber-300 font-semibold"
                  title={`loaded ${shortId(service.build_id)} ≠ current ${shortId(service.current_build_id)}`}>
              來源已變更 · 需重啟服務
            </span>
          )}
          {service.unavailable_reason && (
            <span className="px-1.5 py-0.2 rounded border border-rose-500/40 bg-rose-500/10 text-rose-300">{service.unavailable_reason}</span>
          )}
        </>
      )}
      {pending && (
        <span className="flex items-center gap-1 px-1.5 py-0.2 rounded border border-amber-500/40 bg-amber-500/10 text-amber-200"
              title={`request_id ${pending.body.request_id} 已送出但未收到回應；重送使用同一 request_id`}>
          命令結果未知 ({pending.command_type} {shortId(pending.body.request_id)})
          <button type="button" disabled={busy} onClick={() => void retry()}
                  className="underline underline-offset-2 hover:text-foreground disabled:opacity-50 cursor-pointer">重送</button>
          <button type="button" onClick={() => stateAdapter.discardPendingCommand()}
                  className="underline underline-offset-2 hover:text-foreground cursor-pointer">捨棄</button>
        </span>
      )}
    </div>
  );
}
