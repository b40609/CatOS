import { cn } from "@/lib/utils";

interface PulseBeaconProps {
  /** 圓點尺寸（像素），預設 5px */
  size?: number;
  /** 狀態顏色變體：up (翠綠在線), warn (琥珀警示), down (紅色故障), gold (黃金模式) */
  variant?: "up" | "warn" | "down" | "gold";
  /** 是否具備切邊隔離環（預設 true） */
  ring?: boolean;
  className?: string;
  title?: string;
}

/**
 * 靜態實心狀態指示點（全站一致不做無限循環呼吸或漣漪動畫，CAT-B-24）。
 */
export function PulseBeacon({
  size = 5,
  variant = "up",
  ring = true,
  className,
  title,
}: PulseBeaconProps) {
  const colorBg =
    variant === "up"
      ? "bg-up"
      : variant === "warn"
      ? "bg-warn"
      : variant === "down"
      ? "bg-down"
      : "bg-gold";

  return (
    <span
      style={{ width: `${size}px`, height: `${size}px` }}
      className={cn("relative inline-flex shrink-0 items-center justify-center", className)}
      title={title}
    >
      <span
        style={{ width: `${size}px`, height: `${size}px` }}
        className={cn(
          "relative inline-flex rounded-full",
          colorBg,
          ring && "ring-[1.5px] ring-sidebar"
        )}
      />
    </span>
  );
}
