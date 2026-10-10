import { useState, useRef, type ReactNode } from "react";
import { useLayoutStore, type CardId, type SlotKey, CARD_TITLES } from "@/state/layoutStore";
import { cn } from "@/lib/utils";

interface WorkspaceGridProps {
  renderCard: (cardId: CardId) => ReactNode;
}

export function WorkspaceGrid({ renderCard }: WorkspaceGridProps) {
  const {
    isEditing,
    leftColWidth,
    setLeftColWidth,
    leftUpperHeight,
    setLeftUpperHeight,
    rightUpperHeight,
    setRightUpperHeight,
    slots,
    swapPanes,
    draggingSlot,
    setDraggingSlot,
    hoverSlot,
    setHoverSlot,
    resetSplits,
    updateCurrentProfile,
  } = useLayoutStore();

  const containerRef = useRef<HTMLDivElement>(null);
  const [isResizing, setIsResizing] = useState(false);

  // 1. 左右主欄垂直分割線拖曳 (Col Splitter) - 60:40 定案 120 FPS 高性能 rAF 拉伸
  const handleMainColSplitDown = (e: React.PointerEvent) => {
    if (!isEditing || !containerRef.current) return;
    e.preventDefault();
    setIsResizing(true);
    const startX = e.clientX;
    const startWidthPct = leftColWidth;
    const containerWidth = containerRef.current.getBoundingClientRect().width;

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    let rafId: number | null = null;

    const onPointerMove = (moveEvt: PointerEvent) => {
      if (rafId !== null) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        const deltaX = moveEvt.clientX - startX;
        const deltaPct = (deltaX / containerWidth) * 100;
        const newPct = Math.min(80, Math.max(35, Math.round(startWidthPct + deltaPct)));
        setLeftColWidth(newPct, false); // 拖曳中不呼叫 localStorage，零 I/O 阻塞
      });
    };

    const onPointerUp = () => {
      if (rafId !== null) cancelAnimationFrame(rafId);
      setIsResizing(false);
      updateCurrentProfile(); // 僅在放開滑鼠時持久化儲存一次
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
  };

  // 2. 左欄水平分割線拖曳 (Left Row Splitter) - 120 FPS 高性能 rAF 拉伸
  const handleLeftRowSplitDown = (e: React.PointerEvent) => {
    if (!isEditing) return;
    e.preventDefault();
    setIsResizing(true);
    const startY = e.clientY;
    const startHeightPct = leftUpperHeight;
    const targetCol = (e.currentTarget as HTMLElement).parentElement;
    if (!targetCol) return;
    const colHeight = targetCol.getBoundingClientRect().height;

    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";

    let rafId: number | null = null;

    const onPointerMove = (moveEvt: PointerEvent) => {
      if (rafId !== null) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        const deltaY = moveEvt.clientY - startY;
        const deltaPct = (deltaY / colHeight) * 100;
        const newPct = Math.min(74, Math.max(28, Math.round(startHeightPct + deltaPct)));
        setLeftUpperHeight(newPct, false); // 拖曳中不呼叫 localStorage
      });
    };

    const onPointerUp = () => {
      if (rafId !== null) cancelAnimationFrame(rafId);
      setIsResizing(false);
      updateCurrentProfile();
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
  };

  // 3. 右欄水平分割線拖曳 (Right Row Splitter) - 120 FPS 高性能 rAF 拉伸
  const handleRightRowSplitDown = (e: React.PointerEvent) => {
    if (!isEditing) return;
    e.preventDefault();
    setIsResizing(true);
    const startY = e.clientY;
    const startHeightPct = rightUpperHeight;
    const targetCol = (e.currentTarget as HTMLElement).parentElement;
    if (!targetCol) return;
    const colHeight = targetCol.getBoundingClientRect().height;

    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";

    let rafId: number | null = null;

    const onPointerMove = (moveEvt: PointerEvent) => {
      if (rafId !== null) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        const deltaY = moveEvt.clientY - startY;
        const deltaPct = (deltaY / colHeight) * 100;
        const newPct = Math.min(74, Math.max(28, Math.round(startHeightPct + deltaPct)));
        setRightUpperHeight(newPct, false); // 拖曳中不呼叫 localStorage
      });
    };

    const onPointerUp = () => {
      if (rafId !== null) cancelAnimationFrame(rafId);
      setIsResizing(false);
      updateCurrentProfile();
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
  };

  // 渲染單個卡片槽位 (1:1 復刻 8899 之換位反饋與定案邊界，拖曳時禁用 transition 杜絕延遲)
  const renderSlotPane = (slotKey: SlotKey, style?: React.CSSProperties) => {
    const cardId = slots[slotKey];
    const isDragSource = draggingSlot === slotKey;
    const isHoverTarget = hoverSlot === slotKey && draggingSlot !== slotKey;

    return (
      <div
        style={style}
        className={cn(
          "relative flex flex-col min-w-0 overflow-hidden rounded-xl border border-border/80 bg-card",
          !isResizing && "transition-all duration-200",
          isResizing && "pointer-events-none select-none",
          isEditing && "ring-1 ring-border/80 hover:ring-primary/60",
          isDragSource && "opacity-40 border-2 border-dashed border-primary/60 scale-[0.99]",
          isHoverTarget && "border-2 border-primary ring-2 ring-primary/40 shadow-[0_0_16px_rgba(232,180,94,0.35)] scale-[1.01]"
        )}
        onDragOver={(e) => {
          if (isEditing && draggingSlot && draggingSlot !== slotKey) {
            e.preventDefault();
            setHoverSlot(slotKey);
          }
        }}
        onDragLeave={() => {
          if (hoverSlot === slotKey) setHoverSlot(null);
        }}
        onDrop={(e) => {
          e.preventDefault();
          if (draggingSlot && draggingSlot !== slotKey) {
            swapPanes(draggingSlot, slotKey);
          }
          setDraggingSlot(null);
          setHoverSlot(null);
        }}
      >
        {/* 編輯模式下的卡片標題拖曳換位握把條 (8899 原封不動復刻，無多餘選項) */}
        {isEditing && (
          <div
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData("text/plain", slotKey);
              setDraggingSlot(slotKey);
            }}
            onDragEnd={() => {
              setDraggingSlot(null);
              setHoverSlot(null);
            }}
            className="flex items-center justify-between px-3.5 py-1.5 border-b border-border/80 bg-secondary/80 hover:bg-secondary cursor-grab active:cursor-grabbing select-none text-xs rounded-t-xl transition-colors group z-20 shrink-0 pointer-events-auto"
            title="按住此處拖曳可與其他卡片對調位置"
          >
            <div className="flex items-center gap-2">
              <span className="text-primary font-bold text-sm tracking-tighter group-hover:scale-110 transition-transform">⋮⋮</span>
              <span className="text-[11px] font-semibold text-foreground flex items-center gap-1.5">
                <span>{CARD_TITLES[cardId].icon}</span>
                <span>{CARD_TITLES[cardId].zh}</span>
              </span>
            </div>
            <span className="text-[10px] text-primary/80 font-mono tracking-wider font-medium">按住拖曳換位 ⇄</span>
          </div>
        )}

        {/* 拖曳目標落點視覺提示徽章 (DROP TO SWAP) */}
        {isHoverTarget && (
          <div className="absolute top-2.5 right-3 z-40 rounded px-2 py-0.5 text-[9px] font-extrabold text-primary bg-background/95 border border-primary/70 shadow-lg pointer-events-none animate-in fade-in">
            DROP TO SWAP
          </div>
        )}

        {/* 卡片內容主體 */}
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">{renderCard(cardId)}</div>
      </div>
    );
  };

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative flex flex-col lg:flex-row w-full items-stretch select-text",
        !isResizing && "transition-all duration-200"
      )}
    >
      {/* ==================== 左欄 (主視野 60%) ==================== */}
      <div
        style={{ width: `calc(${leftColWidth}% - 8px)` }}
        className={cn(
          "flex flex-col min-w-0 min-h-[690px]",
          !isResizing && "transition-all duration-200"
        )}
      >
        {/* 左上卡片 (預設: 走勢圖 50%) */}
        {renderSlotPane("leftUpper", { flex: `0 0 calc(${leftUpperHeight}% - 8px)` })}

        {/* 左欄水平分割條 (上下拉伸高度 · 提供標準 16px 間距) */}
        <div
          onPointerDown={handleLeftRowSplitDown}
          onDoubleClick={() => setLeftUpperHeight(50)}
          className={cn(
            "relative w-full h-4 z-20 flex items-center justify-center select-none group touch-none shrink-0",
            isEditing ? "cursor-row-resize" : "cursor-default"
          )}
          title={isEditing ? "拖曳調整上下卡片高度 · 雙擊還原 (50:50)" : undefined}
        >
          <div
            className={cn(
              "w-full h-[1px] transition-all duration-150 pointer-events-none",
              isEditing
                ? "bg-border/60 group-hover:bg-primary group-hover:h-[2px] group-hover:shadow-[0_0_8px_var(--primary)]"
                : "bg-border/30"
            )}
          />
        </div>

        {/* 左下卡片 (預設: 持倉明細 50%) */}
        {renderSlotPane("leftLower", { flex: `0 0 calc(${100 - leftUpperHeight}% - 8px)` })}
      </div>

      {/* ==================== 垂直主分欄分割線 (左右拉伸寬度 · 提供標準 16px 間距) ==================== */}
      <div
        onPointerDown={handleMainColSplitDown}
        onDoubleClick={resetSplits}
        className={cn(
          "relative hidden lg:flex items-center justify-center w-4 z-30 select-none group touch-none self-stretch shrink-0",
          isEditing ? "cursor-col-resize" : "cursor-default"
        )}
        title={isEditing ? "拖曳調整左右欄寬度比例 · 雙擊還原定案比例 (60:40)" : undefined}
      >
        <div
          className={cn(
            "h-full w-[1px] transition-all duration-150 pointer-events-none",
            isEditing
              ? "bg-border/60 group-hover:bg-primary group-hover:w-[2px] group-hover:shadow-[0_0_8px_var(--primary)]"
              : "bg-border/30"
          )}
        />
      </div>

      {/* ==================== 右欄 (輔助視野 40%) ==================== */}
      <div
        style={{ width: `calc(${100 - leftColWidth}% - 8px)` }}
        className={cn(
          "flex flex-col min-w-0 mt-4 lg:mt-0 min-h-[690px]",
          !isResizing && "transition-all duration-200"
        )}
      >
        {/* 右上卡片 (預設: 資產配置 50%) */}
        {renderSlotPane("rightUpper", { flex: `0 0 calc(${rightUpperHeight}% - 8px)` })}

        {/* 右欄水平分割條 (上下拉伸高度 · 提供標準 16px 間距) */}
        <div
          onPointerDown={handleRightRowSplitDown}
          onDoubleClick={() => setRightUpperHeight(50)}
          className={cn(
            "relative w-full h-4 z-20 flex items-center justify-center select-none group touch-none shrink-0",
            isEditing ? "cursor-row-resize" : "cursor-default"
          )}
          title={isEditing ? "拖曳調整上下卡片高度 · 雙擊還原 (50:50)" : undefined}
        >
          <div
            className={cn(
              "w-full h-[1px] transition-all duration-150 pointer-events-none",
              isEditing
                ? "bg-border/60 group-hover:bg-primary group-hover:h-[2px] group-hover:shadow-[0_0_8px_var(--primary)]"
                : "bg-border/30"
            )}
          />
        </div>

        {/* 右下卡片 (預設: 即時成交流 50%) */}
        {renderSlotPane("rightLower", { flex: `0 0 calc(${100 - rightUpperHeight}% - 8px)` })}
      </div>
    </div>
  );
}
