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

  const colorPing =
    variant === "up"
      ? "bg-up/60"
      : variant === "warn"
      ? "bg-warn/60"
      : variant === "down"
      ? "bg-down/60"
      : "bg-gold/60";

  const breatheClass =
    variant === "warn"
      ? "status-breathe-warn"
      : "status-breathe";

  return (
    <span
      style={{ width: `${size}px`, height: `${size}px` }}
      className={cn("relative inline-flex shrink-0 items-center justify-center pointer-events-none", className)}
      title={title}
    >
      {/* 外層緩慢擴散漣漪微波 */}
      <span
        style={{ width: `${size}px`, height: `${size}px` }}
        className={cn("absolute inline-flex rounded-full animate-ping duration-1000", colorPing)}
      />
      {/* 內層核心微晶片點 + 自然呼吸光暈 */}
      <span
        style={{ width: `${size}px`, height: `${size}px` }}
        className={cn(
          "relative inline-flex rounded-full",
          colorBg,
          ring && "ring-[1.5px] ring-sidebar",
          breatheClass
        )}
      />
    </span>
  );
}
