/**
 * Kill-Switch control (work package B, docs/wp-b-kill-switch-proposal.md).
 *
 * - Kill: anyone, after a confirm dialog with a reason. Every local-sim run
 *   (including CLI replays) stops before its next bar and no new run starts.
 *   Nothing is flattened in local-sim; the Bot ledger latches manual_kill.
 * - 解除: the user only, with a reason and the typed confirmation word. It only
 *   lets new runs start; killed runs stay stopped. Agents must not clear it.
 */
import { useState } from "react";
import { OctagonX, ShieldCheck, Unlock } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ResearchApiError } from "@/adapters/research-api-adapter";
import { stateAdapter } from "@/state/stateAdapter";
import { useCatStore } from "@/state/catStore";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const ERROR_TEXT: Record<string, string> = {
  simulation_run_active: "還有 run 在跑，等它停下後再解除",
  kill_switch_confirmation_required: "確認字不符",
  kill_switch_reason_invalid: "原因要填 1 到 200 個字",
  kill_switch_not_engaged: "目前沒有觸發",
  request_id_conflict: "這個請求編號已用於另一個動作，請重新開啟對話框",
  page_version_mismatch_reload_required: "服務已更新，請重新整理頁面",
  service_instance_mismatch: "服務已重啟，請重新整理頁面",
  network_error: "沒有收到回應，請先確認狀態再重試",
};

function errorText(err: unknown): string {
  const detail = err instanceof ResearchApiError ? err.detail : "network_error";
  return ERROR_TEXT[detail] ?? detail;
}

function stamp(iso: string | undefined): string {
  if (!iso) return "—";
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? formatDateTime(ms) : iso;
}

export function KillSwitchPanel({ compact = false }: { compact?: boolean }) {
  const kill = useCatStore((s) => s.killSwitch);
  const mode = useCatStore((s) => s.mode);
  const [dialog, setDialog] = useState<"engage" | "clear" | null>(null);
  const [reason, setReason] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const word = kill?.confirm_word ?? "解除";
  const engaged = kill?.engaged ?? false;
  const available = mode === "local" && kill !== null;

  function open(kind: "engage" | "clear") {
    setDialog(kind);
    setReason("");
    setConfirm("");
    setError(null);
  }

  async function submit() {
    if (!dialog) return;
    setBusy(true);
    setError(null);
    try {
      if (dialog === "engage") await stateAdapter.engageKill(reason.trim());
      else await stateAdapter.clearKill(reason.trim(), confirm);
      setDialog(null);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  const reasonOk = reason.trim().length >= 1 && reason.trim().length <= 200;
  const canSubmit = !busy && reasonOk && (dialog === "engage" || confirm === word);
  const last = kill?.engaged_record ?? null;

  return (
    <div className={cn("font-mono text-t2", compact ? "space-y-1.5" : "space-y-3")} data-testid="kill-switch-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {engaged ? <OctagonX className="size-4 text-red-400" /> : <ShieldCheck className="size-4 text-emerald-400" />}
          <span className={cn("font-bold", engaged ? "text-red-400" : "text-emerald-400")} data-testid="kill-switch-state">
            {!available ? "未連線" : engaged ? "Kill-Switch 已觸發" : "Kill-Switch 未觸發"}
          </span>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={!available || (engaged && !kill?.error)}
            onClick={() => open("engage")}
            className="flex h-7 items-center rounded border border-red-500/60 bg-red-500/10 px-3 text-xs font-semibold text-red-300 hover:bg-red-500/20 cursor-pointer disabled:cursor-not-allowed disabled:opacity-40"
          >
            <OctagonX className="mr-1 size-3.5" /> Kill
          </button>
          <button
            type="button"
            disabled={!available || !engaged || Boolean(kill?.error)}
            onClick={() => open("clear")}
            className="flex h-7 items-center rounded border border-border/80 bg-secondary/60 px-3 text-xs font-semibold text-foreground hover:bg-secondary cursor-pointer disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Unlock className="mr-1 size-3.5" /> 解除
          </button>
        </div>
      </div>

      {!available ? (
        <p className="text-amber-400">
          介面讀不到總開關狀態。要緊急停止，在專案資料夾的終端機執行：
          <code className="ml-1 text-foreground">.venv\Scripts\python.exe -m catos.cli kill engage --reason "原因"</code>
        </p>
      ) : kill?.error ? (
        <p className="text-amber-400">
          紀錄檔有問題，視同已觸發：{kill.error}。所有 run 會停下、新 run 無法啟動。紀錄檔不見或變空時可以再按 Kill 重寫觸發紀錄；內容損毀時不能寫入，但已視同觸發。
          要檢查的是 outputs/controls/kill-switch.jsonl 與旁邊的 .lock 檔；只有你本人確認後同時刪除這兩個檔，才會回到全新狀態。
        </p>
      ) : engaged && last ? (
        <p className="text-muted-foreground">
          {stamp(last.created_at as string)} 由 {last.actor === "cli" ? "終端機" : "介面"} 觸發：{last.reason as string}。
          所有模擬 run 已在下一根 K 線前停止，新 run 無法啟動；本機模擬不平倉，部位留在該 run 的帳本。
        </p>
      ) : (
        <p className="text-muted-foreground">
          按下後，所有本機模擬 run（含終端機的歷史重播）在下一根 K 線前停止，並禁止啟動新 run。只能由你人工解除。
        </p>
      )}

      {!compact && kill && kill.recent.length > 0 && (
        <div className="space-y-0.5 border-t border-border/40 pt-2 text-t1 text-muted-foreground">
          {kill.recent.slice(0, 5).map((record) => (
            <div key={record.record_id} className="flex gap-2">
              <span className="w-32 shrink-0">{stamp(record.created_at)}</span>
              <span className={cn("w-10 shrink-0", record.action === "engage" ? "text-red-400" : "text-emerald-400")}>
                {record.action === "engage" ? "觸發" : "解除"}
              </span>
              <span className="w-12 shrink-0">{record.actor === "cli" ? "終端機" : "介面"}</span>
              <span className="truncate" title={record.reason}>{record.reason}</span>
            </div>
          ))}
        </div>
      )}

      <Dialog open={dialog !== null} onOpenChange={(value) => { if (!value && !busy) setDialog(null); }}>
        <DialogContent className="max-w-md font-mono">
          <DialogHeader>
            <DialogTitle>{dialog === "engage" ? "觸發 Kill-Switch" : "解除 Kill-Switch"}</DialogTitle>
            <DialogDescription>
              {dialog === "engage"
                ? "所有本機模擬 run 會在下一根 K 線前停止，帳本鎖存 manual_kill，新 run 無法啟動。本機模擬不會平倉。"
                : "解除後可以再啟動新的 run。已被停止的 run 不會恢復，它們的帳本仍鎖存。"}
            </DialogDescription>
          </DialogHeader>
          <label className="space-y-1 text-t2">
            <span className="block text-muted-foreground">原因（必填）</span>
            <input
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              maxLength={200}
              autoFocus
              aria-label="原因"
              className="h-8 w-full rounded border border-border bg-background px-2 text-xs text-foreground"
            />
          </label>
          {dialog === "clear" && (
            <label className="space-y-1 text-t2">
              <span className="block text-muted-foreground">輸入「{word}」確認</span>
              <input
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                aria-label="確認字"
                className="h-8 w-full rounded border border-border bg-background px-2 text-xs text-foreground"
              />
            </label>
          )}
          {error && <p className="text-t2 text-amber-400" role="alert">{error}</p>}
          <DialogFooter>
            <button
              type="button"
              onClick={() => setDialog(null)}
              disabled={busy}
              className="h-8 rounded border border-border/80 px-3 text-xs text-muted-foreground hover:bg-secondary cursor-pointer disabled:opacity-40"
            >
              取消
            </button>
            <button
              type="button"
              onClick={() => void submit()}
              disabled={!canSubmit}
              className={cn(
                "h-8 rounded border px-3 text-xs font-semibold cursor-pointer disabled:cursor-not-allowed disabled:opacity-40",
                dialog === "engage"
                  ? "border-red-500/60 bg-red-500/15 text-red-300 hover:bg-red-500/25"
                  : "border-primary/50 bg-primary/10 text-primary hover:bg-primary/20",
              )}
            >
              {busy ? "送出中…" : dialog === "engage" ? "確認觸發" : "確認解除"}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
