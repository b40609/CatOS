import React, { useRef, useState } from "react";
import { cn } from "@/lib/utils";
import type { SplitDirection } from "./types";
import { useLayoutStore, type SeamStyle } from "@/state/layoutStore";

interface TreeSplitterProps {
  direction: SplitDirection;
  currentRatio: number;
  onRatioChange: (newRatio: number, persist: boolean) => void;
  onReset: () => void;
  seamStyle?: SeamStyle;
}

export function TreeSplitter({
  direction,
  currentRatio,
  onRatioChange,
  onReset,
  seamStyle: propSeamStyle,
}: TreeSplitterProps) {
  const storeSeamStyle = useLayoutStore((s) => s.seamStyle);
  const seamStyle = propSeamStyle || storeSeamStyle || "seamless";

  const [isDragging, setIsDragging] = useState(false);
  const splitterRef = useRef<HTMLDivElement>(null);

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    const splitterEl = splitterRef.current;
    if (!splitterEl) return;

    // 取得父容器尺寸
    const parent = splitterEl.parentElement;
    if (!parent) return;

    const parentRect = parent.getBoundingClientRect();
    const isRow = direction === "row";
    const containerSize = isRow ? parentRect.width : parentRect.height;
    if (containerSize <= 0) return;

    setIsDragging(true);
    const startCoord = isRow ? e.clientX : e.clientY;
    const startRatio = currentRatio;

    document.body.style.cursor = isRow ? "col-resize" : "row-resize";
    document.body.style.userSelect = "none";

    let rafId: number | null = null;
    let latestRatio = startRatio;

    const onPointerMove = (moveEvt: PointerEvent) => {
      if (rafId !== null) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        const currentCoord = isRow ? moveEvt.clientX : moveEvt.clientY;
        const delta = currentCoord - startCoord;
        const deltaRatio = delta / containerSize;
        const nextRatio = Math.min(0.85, Math.max(0.15, Number((startRatio + deltaRatio).toFixed(4))));
        latestRatio = nextRatio;
        onRatioChange(nextRatio, false); // 拖曳中 120 FPS rAF，不呼叫持久化，0 I/O 阻塞
      });
    };

    const onPointerUp = () => {
      if (rafId !== null) cancelAnimationFrame(rafId);
      setIsDragging(false);
      onRatioChange(latestRatio, true); // 放開滑鼠時持久化儲存
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointercancel", onPointerUp);
    };

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerUp);
  };

  const isRow = direction === "row";

  return (
    <div
      ref={splitterRef}
      onPointerDown={handlePointerDown}
      onDoubleClick={onReset}
      className={cn(
        "relative flex items-center justify-center select-none group touch-none shrink-0 transition-colors z-20",
        seamStyle === "compact" && (
          isRow
            ? "w-[5px] cursor-col-resize self-stretch before:absolute before:inset-y-0 before:-inset-x-1.5 before:z-10"
            : "h-[5px] cursor-row-resize w-full before:absolute before:inset-x-0 before:-inset-y-1.5 before:z-10"
        ),
        seamStyle === "seamless" && (
          isRow
            ? "w-2.5 cursor-col-resize self-stretch -mx-[4px]"
            : "h-2.5 cursor-row-resize w-full -my-[4px]"
        ),
        seamStyle === "floating" && (
          isRow
            ? "w-2.5 cursor-col-resize self-stretch -mx-[3px]"
            : "h-2.5 cursor-row-resize w-full -my-[3px]"
        )
      )}
      title="拖曳自由拉伸 · 雙擊還原 50:50"
    >
      {/* 分割線本體 (Bloomberg AIM 5px 微隙：平時內斂 1px 暗線，hover 浮現金色鐳射導軌) */}
      <div
        className={cn(
          "transition-all duration-150 pointer-events-none",
          isRow ? "h-full w-[1px]" : "w-full h-[1px]",
          seamStyle === "compact" && (
            isDragging
              ? "bg-primary shadow-[0_0_10px_var(--primary)] w-[1.5px] h-[1.5px]"
              : "bg-border/30 group-hover:bg-primary/90 group-hover:shadow-[0_0_8px_var(--primary)]"
          ),
          seamStyle === "seamless" && (
            isDragging
              ? "bg-primary shadow-[0_0_10px_var(--primary)] w-[1.5px] h-[1.5px]"
              : "bg-border/75 group-hover:bg-primary group-hover:shadow-[0_0_8px_var(--primary)]"
          ),
          seamStyle === "floating" && (
            isDragging
              ? "bg-primary shadow-[0_0_10px_var(--primary)]"
              : "bg-transparent group-hover:bg-primary/80 group-hover:shadow-[0_0_6px_var(--primary)]"
          )
        )}
      />
    </div>
  );
}
