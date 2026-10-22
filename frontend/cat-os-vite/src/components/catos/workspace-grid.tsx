import { useState, useRef, useEffect, useCallback, type ReactNode } from "react";
import {
  useLayoutStore,
  RECOMMENDED_PRESETS,
  type CardId,
} from "@/state/layoutStore";
import {
  countLeaves,
  moveAndSplit,
  finalizeTree,
} from "@/lib/layout-tree/tree-ops";
import { TreeNodeRenderer } from "@/lib/layout-tree/tree-node-renderer";
import type { LayoutNode, DropPosition } from "@/lib/layout-tree/types";
import { ALL_CARDS } from "./card-registry";
import { LayoutGrid, Plus, ArrowRight, Layers } from "lucide-react";
import { cn } from "@/lib/utils";

interface WorkspaceGridProps {
  renderCard: (cardId: CardId) => ReactNode;
}

interface LeafSnapshot {
  id: string;
  cardId: CardId;
  rect: DOMRect;
}

interface DraggingState {
  sourceLeafId: string;
  sourceCardId: CardId;
}


function EmptyWorkspacePrompt() {
  const { applyLayoutPreset, addNewCard } = useLayoutStore();

  return (
    <div className="h-full w-full flex flex-col items-center justify-center p-6 select-none bg-surface/30 backdrop-blur-sm animate-in fade-in zoom-in-95 duration-200">
      <div className="max-w-[820px] w-full flex flex-col items-center text-center gap-5">
        {/* 微型狀態徽章 */}
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-primary/30 bg-primary/10 text-primary text-[11px] font-mono shadow-xs">
          <span className="size-1.5 rounded-full bg-primary animate-pulse" />
          工作區目前已清空 · 自由自訂模式
        </div>

        {/* 標題與說明 */}
        <div className="flex flex-col gap-1.5">
          <h2 className="text-xl font-bold text-foreground tracking-tight flex items-center justify-center gap-2">
            <LayoutGrid className="size-5 text-primary" />
            自訂您的 CatOS 量化戰情面板
          </h2>
          <p className="text-xs text-muted-foreground leading-relaxed max-w-lg">
            您已關閉所有卡片。可直接點選下方推薦的量化戰情排版立即就位，或透過快捷按鈕單點加入所需卡片：
          </p>
        </div>

        {/* 推薦預設排版卡片網格 (4 個主要推薦 + 單卡) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2.5 w-full mt-1">
          {RECOMMENDED_PRESETS.filter((p) => p.id !== "empty" && p.id !== "focus_positions").map((preset) => (
            <button
              key={preset.id}
              type="button"
              onClick={() => applyLayoutPreset(preset.id)}
              className="flex flex-col items-start p-3 rounded-lg border border-border/80 bg-surface/90 hover:border-primary/60 hover:bg-secondary/50 text-left transition-all group cursor-pointer shadow-xs"
            >
              <div className="flex items-center justify-between w-full mb-1.5">
                <span className="text-[12px] font-bold text-foreground group-hover:text-primary transition-colors">
                  {preset.shortName}
                </span>
                <span className="text-[9.5px] font-mono px-1.5 py-0.2 rounded bg-primary/15 text-primary border border-primary/30 font-semibold">
                  {preset.cardCount} 卡
                </span>
              </div>
              <p className="text-[10px] text-muted-foreground leading-tight line-clamp-2">
                {preset.desc}
              </p>
              <span className="mt-3 text-[10.5px] font-mono text-primary font-semibold flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
                套用排版 <ArrowRight className="size-3" />
              </span>
            </button>
          ))}
        </div>

        {/* 快捷單卡加入區 */}
        <div className="flex flex-col items-center gap-2 mt-2 w-full pt-4 border-t border-border/60">
          <span className="text-[10.5px] font-mono text-muted-foreground flex items-center gap-1.5">
            <Layers className="size-3.5 text-primary/70" />
            或由零開始自由單點組裝卡片：
          </span>
          <div className="flex flex-wrap items-center justify-center gap-1.5 max-w-2xl">
            {ALL_CARDS.map((card) => (
              <button
                key={card.id}
                type="button"
                onClick={() => addNewCard(card.id)}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-mono font-medium border border-border/70 bg-secondary/60 hover:bg-primary/15 hover:border-primary/50 hover:text-primary text-foreground transition-all cursor-pointer shadow-2xs"
              >
                <Plus className="size-3 text-primary" />
                <span>{card.nameZh}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function WorkspaceGrid({ renderCard }: WorkspaceGridProps) {
  const {
    rootNode,
    setRootNode,
    updateSplitRatio,
    removeLeafNode,
  } = useLayoutStore();

  const containerRef = useRef<HTMLDivElement>(null);
  const [isResizing, setIsResizing] = useState(false);

  // 實時流體排版預演 (Live Fluid Morphing) 狀態
  const [draggingInfo, setDraggingInfo] = useState<DraggingState | null>(null);
  const [previewTree, setPreviewTree] = useState<LayoutNode | null>(null);

  // 幾何位置快照：在 pointerdown 瞬間固化，杜絕 DOM 重排造成的震顫跳動迴圈 (Jitter Loop)
  const leafSnapshotsRef = useRef<LeafSnapshot[]>([]);
  const currentHoverRef = useRef<{ targetLeafId: string; pos: DropPosition } | null>(null);
  const rootNodeRef = useRef(rootNode);
  rootNodeRef.current = rootNode;

  const draggingInfoRef = useRef(draggingInfo);
  draggingInfoRef.current = draggingInfo;

  const previewTreeRef = useRef(previewTree);
  previewTreeRef.current = previewTree;

  // 統計目前樹中卡片數
  const totalLeaves = countLeaves(rootNode);
  const canRemove = totalLeaves > 1;

  // 120 FPS 自由拉伸比例處理
  const handleRatioChange = (splitId: string, ratio: number, persist: boolean) => {
    if (!persist) {
      setIsResizing(true);
    } else {
      setIsResizing(false);
    }
    updateSplitRatio(splitId, ratio, persist);
  };

  const handleResetSplit = (splitId: string) => {
    updateSplitRatio(splitId, splitId === "split-root" ? 0.6 : 0.5, true);
  };

  // 開始拖曳卡片 (由卡片頂部 44px 標題列或卡片庫抽屜觸發)
  const handleStartDrag = useCallback(
    (sourceLeafId: string, sourceCardId: CardId, _e?: React.PointerEvent) => {
      // 1. 快照當前所有卡片的真實視口幾何位置 (安定判定基準)
      const snapshots: LeafSnapshot[] = [];
      const leafElements = document.querySelectorAll<HTMLElement>("[data-leaf-id]");
      leafElements.forEach((el) => {
        const id = el.getAttribute("data-leaf-id");
        const cardId = el.getAttribute("data-card-id") as CardId;
        if (id && cardId && !id.startsWith("preview-slot-")) {
          snapshots.push({
            id,
            cardId,
            rect: el.getBoundingClientRect(),
          });
        }
      });

      leafSnapshotsRef.current = snapshots;
      currentHoverRef.current = null;
      setDraggingInfo({ sourceLeafId, sourceCardId });
      setPreviewTree(null);
    },
    []
  );

  // 全域監聽從卡片庫抽屜觸發的拖曳放置事件
  useEffect(() => {
    const handleGalleryDrag = (e: Event) => {
      const customEvent = e as CustomEvent<{ cardId: CardId; clientX?: number; clientY?: number }>;
      if (!customEvent.detail?.cardId) return;
      handleStartDrag(`gallery-new-${customEvent.detail.cardId}`, customEvent.detail.cardId);
    };

    window.addEventListener("catos-start-gallery-drag", handleGalleryDrag);
    return () => window.removeEventListener("catos-start-gallery-drag", handleGalleryDrag);
  }, [handleStartDrag]);

  // 全域監聽滑鼠 Pointer Events，達成實時流體排版預演
  useEffect(() => {
    if (!draggingInfo) return;

    const handlePointerMove = (e: PointerEvent) => {
      const currentDrag = draggingInfoRef.current;
      if (!currentDrag) return;

      const clientX = e.clientX;
      const clientY = e.clientY;

      // 檢查游標命中哪張卡片快照
      let hitSnapshot: LeafSnapshot | null = null;
      for (const snap of leafSnapshotsRef.current) {
        const { rect } = snap;
        if (
          clientX >= rect.left &&
          clientX <= rect.right &&
          clientY >= rect.top &&
          clientY <= rect.bottom
        ) {
          hitSnapshot = snap;
          break;
        }
      }

      // 若游標在自身卡片上或移出所有卡片：還原預覽樹
      if (!hitSnapshot || hitSnapshot.id === currentDrag.sourceLeafId) {
        if (currentHoverRef.current !== null) {
          currentHoverRef.current = null;
          setPreviewTree(null);
        }
        return;
      }

      // 五分區扇區判定：中央 40% 為 Tab 堆疊 (Dock as Tab)，外圍為四向邊界分裂 (Split)
      const rect = hitSnapshot.rect;
      const relX = (clientX - rect.left) / rect.width;
      const relY = (clientY - rect.top) / rect.height;

      let pos: DropPosition = "right";
      if (relX >= 0.25 && relX <= 0.75 && relY >= 0.25 && relY <= 0.75) {
        pos = "center";
      } else if (relX + relY < 1) {
        pos = relX < relY ? "left" : "top";
      } else {
        pos = relX < relY ? "bottom" : "right";
      }

      // 防震顫：若目標節點與扇區未變，維持當前預覽樹
      if (
        currentHoverRef.current?.targetLeafId === hitSnapshot.id &&
        currentHoverRef.current?.pos === pos
      ) {
        return;
      }

      currentHoverRef.current = { targetLeafId: hitSnapshot.id, pos };
      if (!rootNodeRef.current) return;

      // 核心演算法：先剪枝來源節點 (原位置瞬間收攏填滿)，再在目標節點分裂展開高對比落位槽
      const nextTree = moveAndSplit(
        rootNodeRef.current,
        currentDrag.sourceLeafId,
        hitSnapshot.id,
        pos,
        `preview-slot-${currentDrag.sourceCardId}`
      );
      setPreviewTree(nextTree);
    };

    const cleanupDrag = () => {
      setDraggingInfo(null);
      setPreviewTree(null);
      currentHoverRef.current = null;
      leafSnapshotsRef.current = [];
    };

    const handlePointerUp = () => {
      const activePreview = previewTreeRef.current;
      const currentDrag = draggingInfoRef.current;

      // 如果有落位預演樹，提交為最終佈局
      if (activePreview && currentDrag) {
        const finalTree = finalizeTree(activePreview);
        setRootNode(finalTree, true);
      }

      cleanupDrag();
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        cleanupDrag();
      }
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", cleanupDrag);
    window.addEventListener("blur", cleanupDrag);
    window.addEventListener("contextmenu", cleanupDrag);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      window.removeEventListener("pointercancel", cleanupDrag);
      window.removeEventListener("blur", cleanupDrag);
      window.removeEventListener("contextmenu", cleanupDrag);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [draggingInfo, setRootNode]);

  // 100% 垂直頂格滿版高度 (定案 Bloomberg AIM 5px 緊湊微隙，極致純淨 Zero-Waste)
  const colHeightClass = "h-[820px] lg:h-[calc(100vh-80px)] min-h-[660px]";

  // 當前渲染樹：若在預演中則直接渲染預演樹，達成極致直觀的即時版面形態演進 (Live Morphing)
  const displayTree = previewTree || rootNode;

  return (
    <div className={cn("relative flex flex-row w-full min-w-0 overflow-hidden", colHeightClass, draggingInfo ? "select-none" : "select-text")}>
      {/* 3. Layout Tree 容器主體 (維持穩定樹渲染，支援 120 FPS 自由縮放與卡片原地模組替換) */}
      <div
        ref={containerRef}
        className="relative flex flex-col flex-1 min-w-0 h-full overflow-hidden"
      >
        {displayTree ? (
          <TreeNodeRenderer
            node={displayTree}
            isResizing={isResizing}
            canRemove={canRemove}
            draggingLeafId={previewTree ? null : draggingInfo?.sourceLeafId}
            onStartDrag={handleStartDrag}
            onRatioChange={handleRatioChange}
            onResetSplit={handleResetSplit}
            onRemoveLeaf={removeLeafNode}
            renderCard={renderCard}
          />
        ) : (
          <EmptyWorkspacePrompt />
        )}
      </div>
    </div>
  );
}
