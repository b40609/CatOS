import { type ReactNode } from "react";
import { X } from "lucide-react";
import { useLayoutStore, type CardId } from "@/state/layoutStore";
import { countLeaves, getAllLeaves } from "@/lib/layout-tree/tree-ops";
import { cn } from "@/lib/utils";

interface CardHeaderTitleProps {
  cardId: CardId;
  title: string;
  subtext?: ReactNode;
  className?: string;
  onPointerDown?: (e: React.PointerEvent<HTMLDivElement>) => void;
}

/**
 * 卡片標題列 (TradingView 純粹無圖示定案版 · Zero-Icon)
 * 徹底杜絕多餘圖示冗餘，滑鼠移入即可直觀抓取拖曳，按住即可進行邊緣接縫分裂 (Dock / Split ⊞)
 * 懸停時標題右側柔和微顯關閉按鈕 (×)，讓用戶完全自主決定主畫面卡片組合
 */
export function CardHeaderTitle({
  cardId,
  title,
  subtext,
  className,
  onPointerDown,
}: CardHeaderTitleProps) {
  const rootNode = useLayoutStore((s) => s.rootNode);
  const removeLeafNode = useLayoutStore((s) => s.removeLeafNode);

  const totalLeaves = countLeaves(rootNode);
  const canRemove = totalLeaves > 1;

  const handleClose = (e: React.MouseEvent) => {
    e.stopPropagation();
    const leaves = getAllLeaves(rootNode);
    const targetLeaf = leaves.find((l) => l.cardId === cardId);
    if (targetLeaf) {
      removeLeafNode(targetLeaf.id);
    }
  };

  return (
    <div
      draggable={false}
      onDragStart={(e) => e.preventDefault()}
      onPointerDown={onPointerDown}
      className={cn(
        "flex items-center gap-1.5 cursor-grab active:cursor-grabbing select-none touch-none group/title py-0.5 px-1.5 -ml-1.5 rounded transition-colors hover:bg-secondary/60",
        className
      )}
      title="按住拖曳可邊緣接縫分裂 (Dock / Split ⊞)"
    >
      <span className="text-[12px] font-semibold text-foreground tracking-tight group-hover/title:text-foreground/90 select-none">
        {title}
      </span>

      {subtext}

      {/* 懸停微顯關閉按鈕 (僅在卡片數 > 1 時呈現，點擊平滑關閉空間自動合併) */}
      {canRemove && (
        <button
          type="button"
          onClick={handleClose}
          className="size-4 rounded grid place-items-center text-muted-foreground/40 hover:text-rose-400 hover:bg-rose-400/20 opacity-0 group-hover/title:opacity-100 transition-opacity cursor-pointer ml-0.5"
          title="從主畫面關閉此卡片 (可由頂部「新增卡片」隨時加回)"
          data-no-drag
        >
          <X className="size-2.5" />
        </button>
      )}
    </div>
  );
}
