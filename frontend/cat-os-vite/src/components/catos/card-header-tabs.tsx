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
 * 系統總覽卡片右上角統一分頁切換列（融合定案：霧藍微光選中膠囊 × Linear 獨立微底數標）
 * - 去厚重雙層外框，未選中純文字＋獨立圓角數標方塊，選中項呈現霧藍微光膠囊
 * - 固定 1px border 佔位，切換零抖動，全總覽 4 張卡 100% 一致
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
        "flex items-center gap-1 shrink-0 whitespace-nowrap select-none",
        className
      )}
    >
      {items.map((item) => {
        const isActive = item.id === value;
        const countClass = isActive
          ? "bg-[#7faee2]/25 text-[#d7e8fb]"
          : item.tone === "critical"
          ? "bg-rose-500/20 text-rose-300"
          : item.tone === "alert"
          ? "bg-amber-500/20 text-amber-300"
          : "bg-white/[0.07] text-muted-foreground";

        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onChange(item.id)}
            className={cn(
              "inline-flex items-center gap-1.5 px-2 py-0.5 rounded border text-t2 font-sans leading-snug transition-colors cursor-pointer whitespace-nowrap shrink-0",
              isActive
                ? "bg-[#7faee2]/[0.15] border-[#7faee2]/45 text-[#b8d4f2] font-semibold"
                : item.tone === "critical"
                ? "border-transparent text-rose-300/90 hover:text-rose-200 hover:bg-white/[0.04] font-medium"
                : item.tone === "alert"
                ? "border-transparent text-amber-300/90 hover:text-amber-200 hover:bg-white/[0.04] font-medium"
                : "border-transparent text-muted-foreground hover:text-foreground hover:bg-white/[0.04] font-medium"
            )}
          >
            <span>{item.label}</span>
            {item.count !== undefined && (
              <span
                className={cn(
                  "px-1 rounded text-t1 font-mono font-semibold leading-tight tabular-nums",
                  countClass
                )}
              >
                {item.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
