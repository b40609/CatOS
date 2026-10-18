import { cn } from "@/lib/utils";
import type { DropPosition } from "./types";
import type { DragPreviewMode } from "@/state/layoutStore";

interface DropIndicatorProps {
  position: DropPosition;
  sourceTitle?: string;
  mode?: DragPreviewMode;
}

export function DropIndicator({
  position,
  sourceTitle = "待落位卡片",
  mode = "real-card",
}: DropIndicatorProps) {
  // 計算幾何落點區域 (嚴格對齊 50% 分割與 5px 間隙)
  const getContainerStyle = () => {
    switch (position) {
      case "left":
        return {
          wrapper: "left-0 top-0 bottom-0 w-1/2 p-1.5",
          seam: "right-0 top-0 bottom-0 w-[3px]",
          dirLabel: "← 插入左側分欄",
        };
      case "right":
        return {
          wrapper: "right-0 top-0 bottom-0 w-1/2 p-1.5",
          seam: "left-0 top-0 bottom-0 w-[3px]",
          dirLabel: "→ 插入右側分欄",
        };
      case "top":
        return {
          wrapper: "top-0 left-0 right-0 h-1/2 p-1.5",
          seam: "bottom-0 left-0 right-0 h-[3px]",
          dirLabel: "↑ 插入上方分列",
        };
      case "bottom":
      default:
        return {
          wrapper: "bottom-0 left-0 right-0 h-1/2 p-1.5",
          seam: "top-0 left-0 right-0 h-[3px]",
          dirLabel: "↓ 插入下方分列",
        };
    }
  };

  const layout = getContainerStyle();

  // 方案 B：極簡磨砂藍圖
  if (mode === "minimal-blueprint") {
    return (
      <div className={cn("absolute z-50 pointer-events-none transition-all duration-150", layout.wrapper)}>
        {/* 接縫微隙引導光軌 */}
        {layout.seam && (
          <div
            className={cn(
              "absolute bg-primary shadow-[0_0_20px_rgba(232,180,94,0.9)] animate-pulse",
              layout.seam
            )}
          />
        )}
        {/* 極淡磨砂磁吸氣場 */}
        <div className="w-full h-full rounded-md border-2 border-dashed border-primary/80 bg-primary/[0.08] backdrop-blur-[2px] flex items-center justify-center transition-all">
          <span className="text-xs font-mono font-bold text-primary bg-background/90 px-2.5 py-1 rounded shadow-md border border-primary/40 flex items-center gap-1.5">
            <span className="size-1.5 rounded-full bg-primary animate-ping" />
            <span>{layout.dirLabel}</span>
          </span>
        </div>
      </div>
    );
  }

  // 方案 B：macOS Sequoia / Windows 11 Snap 磨砂藍圖骨架 (極致純淨，模擬落位後排版)
  return (
    <div
      className={cn(
        "absolute z-50 pointer-events-none transition-all duration-150 animate-in fade-in-90",
        layout.wrapper
      )}
    >
      <div className="w-full h-full rounded-md border-2 border-primary/90 bg-background/92 backdrop-blur-md shadow-[0_8px_32px_rgba(0,0,0,0.85),0_0_20px_rgba(232,180,94,0.3)] flex flex-col overflow-hidden p-3 transition-all">
        {/* 頂部微縮標題列：完全模擬真實卡片頂格樣貌 */}
        <div className="flex items-center justify-between border-b border-border/80 pb-2 mb-2">
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="size-2 rounded-full bg-primary animate-ping" />
            <span className="text-primary font-mono text-xs font-bold truncate">
              {sourceTitle}
            </span>
          </div>
          <span className="text-[10px] font-mono text-primary font-bold bg-primary/20 px-2 py-0.5 rounded border border-primary/50">
            {layout.dirLabel}
          </span>
        </div>

        {/* 內部藍圖線框 (Wireframe Silhouette)：直觀呈現數據面板將在此展開 */}
        <div className="flex-1 flex flex-col justify-center gap-2 px-2 py-1 opacity-70">
          <div className="h-3 w-1/3 bg-primary/30 rounded animate-pulse" />
          <div className="h-6 w-2/3 bg-foreground/15 rounded" />
          <div className="flex-1 min-h-[36px] border border-dashed border-primary/40 rounded flex items-center justify-center bg-primary/[0.03]">
            <span className="text-[11px] font-mono text-primary/90 font-semibold tracking-wider">
              ⊞ DROP TO SPLIT SLOT
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
