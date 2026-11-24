import { cn } from "@/lib/utils";

export interface CardHeaderTabItem<T extends string = string> {
  id: T;
  label: string;
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
 * 固定 1px transparent 預設邊框，確保所有卡片按鈕高度、內距、字重與選中切換零抖動、100% 一致
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
        "flex items-center gap-0.5 bg-background/60 border border-border/60 rounded p-0.5 shrink-0 whitespace-nowrap select-none",
        className
      )}
    >
      {items.map((item) => {
        const isActive = item.id === value;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onChange(item.id)}
            className={cn(
              "px-2 py-0.5 rounded border text-t2 font-mono leading-snug transition-colors cursor-pointer whitespace-nowrap shrink-0",
              isActive
                ? "bg-secondary text-foreground font-semibold border-white/[0.12] shadow-xs"
                : item.tone === "critical"
                ? "border-transparent text-rose-400 hover:text-rose-300 hover:bg-white/[0.04] font-semibold"
                : item.tone === "alert"
                ? "border-transparent text-amber-300/90 hover:text-amber-200 hover:bg-white/[0.04] font-medium"
                : "border-transparent text-muted-foreground hover:text-foreground hover:bg-white/[0.04] font-medium"
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
