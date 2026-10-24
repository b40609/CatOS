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
    tooltip: "本機展示環境；主頁 Bot 操作只影響展示狀態，不會啟停後端策略",
    activeClass: "bg-amber-500/15 text-amber-400 border-amber-500/40 shadow-xs font-semibold",
    dotClass: "bg-amber-400",
  },
  {
    key: "demo",
    label: "Demo",
    tooltip: "尚未接入 Demo 帳戶；此選項僅切換展示模式",
    activeClass: "bg-cyan-500/15 text-cyan-400 border-cyan-500/40 shadow-xs font-semibold",
    dotClass: "bg-cyan-400",
  },
  {
    key: "live",
    label: "Live",
    tooltip: "尚未接入 Live 帳戶；此選項僅切換展示模式",
    activeClass: "bg-rose-500/15 text-rose-400 border-rose-500/40 shadow-xs font-semibold",
    dotClass: "bg-rose-400",
  },
];

export function ModeSelector({ className }: { className?: string }) {
  const currentMode = useCatStore((s) => s.mode);

  const handleSelect = (mode: BotMode) => {
    void stateAdapter.setMode(mode).catch(console.error);
  };

  return (
    <div
      className={cn(
        "inline-flex items-center p-0.5 rounded bg-background/80 border border-border/80 shadow-inner",
        className
      )}
      role="group"
      aria-label="展示環境模式切換"
    >
      <span className="px-1.5 text-[10px] text-muted-foreground" title="主頁、Bot 與風控使用展示資料；研究頁的真實研究契約另行標示">展示</span>
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
