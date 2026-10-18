import { useCatStore } from "@/state/catStore";
import { stateAdapter } from "@/state/stateAdapter";
import type { BotMode } from "@/contracts";
import { cn } from "@/lib/utils";

const MODES: {
  key: BotMode;
  label: string;
  tooltip: string;
  activeClass: string;
  dotClass: string;
}[] = [
  {
    key: "local",
    label: "本機",
    tooltip: "本機模擬環境（可正常啟動與停止策略測試）",
    activeClass: "bg-amber-500/15 text-amber-400 border-amber-500/40 shadow-xs font-semibold",
    dotClass: "bg-amber-400",
  },
  {
    key: "demo",
    label: "Demo",
    tooltip: "Demo 模擬盤（唯讀隔離展示 · 禁止增倉與交易）",
    activeClass: "bg-cyan-500/15 text-cyan-400 border-cyan-500/40 shadow-xs font-semibold",
    dotClass: "bg-cyan-400",
  },
  {
    key: "live",
    label: "Live",
    tooltip: "Live 實盤（嚴格鎖定 · 依 INVARIANTS 限制真實金鑰）",
    activeClass: "bg-rose-500/15 text-rose-400 border-rose-500/40 shadow-xs font-semibold",
    dotClass: "bg-rose-400",
  },
];

export function ModeSelector({ className }: { className?: string }) {
  const currentMode = useCatStore((s) => s.mode);

  const handleSelect = (mode: BotMode) => {
    stateAdapter.setMode(mode);
  };

  return (
    <div
      className={cn(
        "inline-flex items-center p-0.5 rounded bg-background/80 border border-border/80 shadow-inner",
        className
      )}
      role="group"
      aria-label="工作區環境模式切換"
    >
      {MODES.map((m) => {
        const isActive = currentMode === m.key;
        return (
          <button
            key={m.key}
            type="button"
            onClick={() => handleSelect(m.key)}
            title={m.tooltip}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-mono transition-all cursor-pointer border",
              isActive
                ? m.activeClass
                : "text-muted-foreground hover:text-foreground border-transparent hover:bg-secondary/40"
            )}
          >
            <span
              className={cn(
                "size-1.5 rounded-full transition-opacity",
                isActive ? m.dotClass : "bg-muted-foreground/40",
                isActive && m.key === "local" && "animate-pulse"
              )}
            />
            <span>{m.label}</span>
          </button>
        );
      })}
    </div>
  );
}
