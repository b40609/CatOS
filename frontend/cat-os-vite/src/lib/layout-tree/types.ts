import type { CardId } from "@/state/layoutStore";

export type SplitDirection = "row" | "col";
// "row": 左右水平並排 (垂直分割線，col-resize)
// "col": 上下垂直排列 (水平分割線，row-resize)

// 支援 VS Code 四向邊界分裂 (Dock / Split ⊞) 以及中央分頁堆疊 (Center Dock / Tab Stack)
export type DropPosition = "left" | "right" | "top" | "bottom" | "center";

export interface LeafNode {
  type: "leaf";
  id: string;
  cardId: CardId; // 基礎卡片 ID (作為 fallback / 預設)
  tabs?: CardId[]; // 多卡堆疊分頁清單，例如 ['positions', 'fills']
  activeTab?: CardId; // 當前聚焦中的 Tab
}

export interface SplitNode {
  type: "split";
  id: string;
  direction: SplitDirection;
  ratio: number; // 0.1 ~ 0.9
  first: LayoutNode;
  second: LayoutNode;
}

export type LayoutNode = LeafNode | SplitNode;

export interface DraggingInfo {
  sourceLeafId: string;
  sourceCardId: CardId;
}

export interface HoverDropTarget {
  targetLeafId: string;
  position: DropPosition;
}
