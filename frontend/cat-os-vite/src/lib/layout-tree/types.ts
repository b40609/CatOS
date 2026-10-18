import type { CardId } from "@/state/layoutStore";

export type SplitDirection = "row" | "col";
// "row": 左右水平並排 (垂直分割線，col-resize)
// "col": 上下垂直排列 (水平分割線，row-resize)

// 依據使用者定案：徹底移除換位 (Center Swap)，專注於 VS Code 四向接縫分裂 (Dock / Split ⊞)
export type DropPosition = "left" | "right" | "top" | "bottom";

export interface LeafNode {
  type: "leaf";
  id: string;
  cardId: CardId;
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
