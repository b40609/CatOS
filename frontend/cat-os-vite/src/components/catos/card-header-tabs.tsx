import { cn } from "@/lib/utils";

export interface CardHeaderTabItem<T extends string = string> {
  id: T;
  label: string;
  count?: number;
  tone?: "default" | "alert" | "critical";
}

interface CardHeaderTabsProps<T extends string = string> {
  items: readonly CardHeaderTabItem<T>[];
  value: T;
  onChange: (id: T) => void;
  className?: string;
}

/**
 * 系統總覽卡片右上角統一分頁切換列
 * - 採外框軌道＋括號等寬計數＋主題色立體選中膠囊
 * - 所有強調色皆讀取全域 CSS 主題變數（--primary / --border / --background），跟隨 Personal OS 主題切換即時變色
 */
export function CardHeaderTabs<T extends string>({
  items,
  value,
  onChange,
  className,
}: CardHeaderTabsProps<T>) {
  return (
    <div
      className={cn(
        "flex items-center gap-0.5 bg-background/70 border border-border rounded-md p-0.5 shrink-0 whitespace-nowrap select-none",
        className
      )}
    >
      {items.map((item) => {
        const isActive = item.id === value;
        const text = item.count !== undefined ? `${item.label}(${item.count})` : item.label;

        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onChange(item.id)}
            className={cn(
              "px-2 py-0.5 rounded border text-t2 font-mono leading-snug transition-colors cursor-pointer whitespace-nowrap shrink-0 tabular-nums outline-none focus:outline-none focus-visible:ring-1 focus-visible:ring-primary/60",
              isActive
                ? "bg-primary/15 border-primary/45 text-primary font-semibold shadow-xs"
                : item.tone === "critical"
                ? "border-transparent text-rose-400 hover:text-rose-300 hover:bg-white/[0.04] font-semibold"
                : item.tone === "alert"
                ? "border-transparent text-amber-400 hover:text-amber-300 hover:bg-white/[0.04]"
                : "border-transparent text-muted-foreground hover:text-foreground hover:bg-white/[0.04]"
            )}
          >
            {text}
          </button>
        );
      })}
    </div>
  );
}
