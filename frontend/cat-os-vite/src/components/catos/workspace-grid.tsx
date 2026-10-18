import { useState, useRef, useEffect, useCallback, type ReactNode } from "react";
import {
  useLayoutStore,
  type CardId,
} from "@/state/layoutStore";
import {
  countLeaves,
  moveAndSplit,
  finalizeTree,
} from "@/lib/layout-tree/tree-ops";
import { TreeNodeRenderer } from "@/lib/layout-tree/tree-node-renderer";
import type { LayoutNode, DropPosition } from "@/lib/layout-tree/types";
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

  // 開始拖曳卡片 (由卡片頂部 44px 標題列觸發)
  const handleStartDrag = useCallback(
    (sourceLeafId: string, sourceCardId: CardId, _e: React.PointerEvent) => {
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

      // 精確四向對角線象限判定：上、下、左、右 (徹底杜絕換位 Center Swap)
      const rect = hitSnapshot.rect;
      const relX = (clientX - rect.left) / rect.width;
      const relY = (clientY - rect.top) / rect.height;

      let pos: DropPosition = "right";
      if (relX + relY < 1) {
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
    <div className={cn("relative flex flex-col w-full min-w-0", draggingInfo ? "select-none" : "select-text")}>
      {/* 3. Layout Tree 容器主體 (維持穩定樹渲染，支援 120 FPS 自由縮放與卡片原地模組替換) */}
      <div
        ref={containerRef}
        className={cn(
          "relative flex flex-col w-full min-w-0 overflow-hidden",
          colHeightClass
        )}
      >
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
      </div>
    </div>
  );
}
