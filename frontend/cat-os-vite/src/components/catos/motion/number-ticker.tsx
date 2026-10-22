import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface NumberTickerProps {
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
  duration?: number; // ms
  flashOnChange?: boolean;
}

export function NumberTicker({
  value,
  decimals = 2,
  prefix = "",
  suffix = "",
  className,
  duration = 600,
  flashOnChange = true,
}: NumberTickerProps) {
  const [displayValue, setDisplayValue] = useState(value);
  const [flash, setFlash] = useState<"up" | "down" | null>(null);
  const prevValueRef = useRef(value);
  const startTimeRef = useRef<number | null>(null);
  const startValRef = useRef(value);
  const animFrameRef = useRef<number | null>(null);

  useEffect(() => {
    const prev = prevValueRef.current;
    if (prev === value) return;

    if (flashOnChange) {
      setFlash(value > prev ? "up" : "down");
      const timer = setTimeout(() => setFlash(null), 700);
      return () => clearTimeout(timer);
    }
  }, [value, flashOnChange]);

  useEffect(() => {
    startValRef.current = displayValue;
    startTimeRef.current = null;

    const animate = (timestamp: number) => {
      if (!startTimeRef.current) startTimeRef.current = timestamp;
      const elapsed = timestamp - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);

      // easeOutExpo 物理阻尼曲線：1 - Math.pow(2, -10 * progress)
      const ease = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      const current = startValRef.current + (value - startValRef.current) * ease;

      setDisplayValue(current);

      if (progress < 1) {
        animFrameRef.current = requestAnimationFrame(animate);
      } else {
        setDisplayValue(value);
        prevValueRef.current = value;
      }
    };

    animFrameRef.current = requestAnimationFrame(animate);

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [value, duration]);

  const formatted = displayValue.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  return (
    <span
      className={cn(
        "num font-mono transition-colors duration-300 inline-block tracking-tight",
        flash === "up" && "text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.5)]",
        flash === "down" && "text-rose-400 drop-shadow-[0_0_8px_rgba(244,63,94,0.5)]",
        className
      )}
    >
      {prefix}
      {formatted}
      {suffix}
    </span>
  );
}
