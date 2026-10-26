import React, { useRef, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { TreeSplitter } from "./tree-splitter";
import {
  CARD_TITLES,
  type CardId,
  useLayoutStore,
} from "@/state/layoutStore";
import type {
  LayoutNode,
  LeafNode,
} from "./types";
import { CardSlotContext } from "./card-slot-context";

interface TreeNodeRendererProps {
  node: LayoutNode;
  isResizing: boolean;
  canRemove: boolean;
  draggingLeafId?: string | null;
  onStartDrag: (sourceLeafId: string, sourceCardId: CardId, e: React.PointerEvent) => void;
  onRatioChange: (splitId: string, ratio: number, persist: boolean) => void;
  onResetSplit: (splitId: string) => void;
  onRemoveLeaf: (leafId: string) => void;
  renderCard: (cardId: CardId) => ReactNode;
}

export function TreeNodeRenderer(props: TreeNodeRendererProps) {
  const { node } = props;
  const seamStyle = useLayoutStore((s) => s.seamStyle);
  // 定案 5px 間隙：compact 模式下兩側各扣除 2.5px，合計恰好為 5.0px 微隙
  const gapOffset = seamStyle === "seamless" ? 0.5 : seamStyle === "compact" ? 2.5 : 4;

  if (node.type === "split") {
    const isRow = node.direction === "row";
    const ratio = node.ratio;

    return (
      <div
        className={cn(
          "flex min-w-0 min-h-0 flex-1",
          isRow ? "flex-row items-stretch" : "flex-col items-stretch",
          !props.isResizing && "transition-all duration-200"
        )}
      >
        {/* 第一子分支 (First Child) */}
        <div
          style={
            isRow
              ? { width: `calc(${ratio * 100}% - ${gapOffset}px)`, flex: "0 0 auto" }
              : { height: `calc(${ratio * 100}% - ${gapOffset}px)`, flex: "0 0 auto" }
          }
          className="flex min-w-0 min-h-0 overflow-hidden"
        >
          <TreeNodeRenderer {...props} node={node.first} />
        </div>

        {/* 120 FPS rAF 樹分割線 */}
        <TreeSplitter
          direction={node.direction}
          currentRatio={node.ratio}
          seamStyle={seamStyle}
          onRatioChange={(newRatio, persist) =>
            props.onRatioChange(node.id, newRatio, persist)
          }
          onReset={() => props.onResetSplit(node.id)}
        />

        {/* 第二子分支 (Second Child) */}
        <div
          style={
            isRow
              ? { width: `calc(${(1 - ratio) * 100}% - ${gapOffset}px)`, flex: "0 0 auto" }
              : { height: `calc(${(1 - ratio) * 100}% - ${gapOffset}px)`, flex: "0 0 auto" }
          }
          className="flex min-w-0 min-h-0 overflow-hidden"
        >
          <TreeNodeRenderer {...props} node={node.second} />
        </div>
      </div>
    );
  }

  // 葉子卡片節點 (Leaf Node)
  return <LeafCardPane {...props} leaf={node} />;
}

interface LeafCardPaneProps extends TreeNodeRendererProps {
  leaf: LeafNode;
}

function LeafCardPane({
  leaf,
  isResizing,
  draggingLeafId,
  onStartDrag,
  renderCard,
}: LeafCardPaneProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const seamStyle = useLayoutStore((s) => s.seamStyle);
  const replaceLeafNode = useLayoutStore((s) => s.replaceLeafNode);

  const cardId = leaf.cardId;
  const isDraggingThis = draggingLeafId === leaf.id;

  // 1. 如果此節點為「實時流體落位預演槽 (Live Landing Slot)」
  // 依據視覺決策鐵律：提供真實卡片即時預演 (WYSIWYG) 或極簡藍圖，徹底杜絕多餘的狀態提示文字噪音
  if (leaf.id.startsWith("preview-slot-")) {
    const dragPreviewMode = useLayoutStore.getState().dragPreviewMode;

    // 方案 A（推薦 · 所見即所得）：直接渲染真實卡片本體！
    // 預演狀態下外框呈現精緻的琥珀金微光輪廓，零文字噪音，放開滑鼠即刻落位
    if (dragPreviewMode === "real-card") {
      return (
        <div
          ref={containerRef}
          data-leaf-id={leaf.id}
          data-card-id={leaf.cardId}
          className={cn(
            "relative flex flex-col flex-1 min-w-0 min-h-0 overflow-hidden bg-surface/90 backdrop-blur-md ring-2 ring-primary/80 shadow-[0_0_30px_rgba(232,180,94,0.3)] animate-in zoom-in-95 duration-150 group/card",
            seamStyle === "seamless" && "rounded-none",
            seamStyle === "compact" && "rounded-md border border-primary/75",
            seamStyle === "floating" && "rounded-xl border border-primary/80"
          )}
        >
          {/* 頂部極細緻的微光狀態線（呼吸光暈，指示正在就位） */}
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-primary to-transparent animate-pulse z-20 pointer-events-none" />
          <div className="flex-1 min-h-0 flex flex-col overflow-hidden [&_.panel]:border-0 [&_.panel]:rounded-none [&_.panel]:bg-transparent [&_.panel]:backdrop-blur-none [&_.panel]:shadow-none">
            {renderCard(leaf.cardId)}
          </div>
        </div>
      );
    }

    // 方案 B：極簡純淨磨砂藍圖 (Minimal Blueprint · 零文字干擾)
    if (dragPreviewMode === "minimal-blueprint") {
      return (
        <div
          ref={containerRef}
          data-leaf-id={leaf.id}
          data-card-id={leaf.cardId}
          className={cn(
            "relative flex flex-col flex-1 min-w-0 min-h-0 overflow-hidden bg-primary/[0.08] border-2 border-dashed border-primary/70 backdrop-blur-sm animate-in zoom-in-95 duration-150 items-center justify-center select-none",
            seamStyle === "seamless" && "rounded-none",
            seamStyle === "compact" && "rounded-md",
            seamStyle === "floating" && "rounded-xl"
          )}
        >
          <div className="size-2 rounded-full bg-primary/70 animate-ping" />
        </div>
      );
    }

    // 方案 C：微縮標籤藍圖 (Mini Blueprint Card · 僅標題線框)
    return (
      <div
        ref={containerRef}
        data-leaf-id={leaf.id}
        data-card-id={leaf.cardId}
        className={cn(
          "relative flex flex-col flex-1 min-w-0 min-h-0 overflow-hidden bg-surface/80 border border-primary/50 shadow-sm animate-in zoom-in-95 duration-150 select-none",
          seamStyle === "seamless" && "rounded-none",
          seamStyle === "compact" && "rounded-md",
          seamStyle === "floating" && "rounded-xl"
        )}
      >
        <div className="flex items-center justify-between px-3 py-2 bg-secondary/50 border-b border-border/80 shrink-0">
          <span className="text-[12px] font-semibold text-primary">
            {CARD_TITLES[leaf.cardId]?.zh || leaf.cardId}
          </span>
          <span className="text-[10px] font-mono text-primary/80">⊞ 就位</span>
        </div>
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="w-16 h-1 bg-primary/20 rounded-full" />
        </div>
      </div>
    );
  }

  // 2. 一般卡片節點
  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    // 杜絕點擊按鈕、輸入框、Tab 等互動元素觸發拖曳
    if ((e.target as HTMLElement).closest("button, a, input, select, [role='button'], [data-no-drag]")) {
      return;
    }

    const rect = e.currentTarget.getBoundingClientRect();
    // 限制在卡片頂部 44px (Header 區域) 觸發
    if (e.clientY - rect.top > 44) {
      return;
    }

    // 關鍵防護 1：徹底阻止瀏覽器 HTML5 原生拖曳 (Native Drag-and-Drop) 與文字選取
    // 杜絕瀏覽器產生半透明 Drag Ghost Image 導致的全螢幕重影與指標事件吞噬！
    e.preventDefault();

    try {
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    } catch {
      // 容錯處理：若瀏覽器不支援 setPointerCapture 則靜默略過
    }

    onStartDrag(leaf.id, cardId, e);
  };

  return (
    <div
      ref={containerRef}
      data-leaf-id={leaf.id}
      data-card-id={cardId}
      draggable={false}
      onDragStart={(e) => e.preventDefault()}
      onPointerDown={handlePointerDown}
      className={cn(
        "relative flex flex-col flex-1 min-w-0 min-h-0 overflow-hidden bg-surface/90 backdrop-blur-md group/card select-none",
        seamStyle === "seamless" && "rounded-none border-0 shadow-none",
        seamStyle === "compact" && "rounded-md border border-border/75 shadow-xs",
        seamStyle === "floating" && "rounded-xl border border-border/80 shadow-xs",
        !isResizing && "transition-all duration-200",
        isResizing && "pointer-events-none select-none",
        isDraggingThis && "opacity-35 border-2 border-dashed border-primary/70 ring-1 ring-primary/30"
      )}
    >
      <div className="flex-1 min-h-0 flex flex-col overflow-hidden [&_.panel]:border-0 [&_.panel]:rounded-none [&_.panel]:bg-transparent [&_.panel]:backdrop-blur-none [&_.panel]:shadow-none">
        <CardSlotContext.Provider
          value={{
            leafId: leaf.id,
            cardId,
            replaceCard: (newCardId) => replaceLeafNode(leaf.id, newCardId),
          }}
        >
          {renderCard(cardId)}
        </CardSlotContext.Provider>
      </div>
    </div>
  );
}
