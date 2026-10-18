import type { CardId } from "@/state/layoutStore";
import type { LayoutNode, LeafNode, SplitNode, SplitDirection, DropPosition } from "./types";

/**
 * 深度拷貝 LayoutNode 樹
 */
export function cloneTree(node: LayoutNode): LayoutNode {
  if (node.type === "leaf") {
    return { ...node };
  }
  return {
    ...node,
    first: cloneTree(node.first),
    second: cloneTree(node.second),
  };
}

/**
 * 建立系統預設的「量化核心四分割 (60:40)」樹
 */
export function createDefaultTree(): LayoutNode {
  return {
    type: "split",
    id: "split-root",
    direction: "row", // 左右分欄
    ratio: 0.6, // 左 60%, 右 40%
    first: {
      type: "split",
      id: "split-left",
      direction: "col", // 上下分列
      ratio: 0.5,
      first: { type: "leaf", id: "leaf-equity", cardId: "equity" },
      second: { type: "leaf", id: "leaf-positions", cardId: "positions" },
    },
    second: {
      type: "split",
      id: "split-right",
      direction: "col", // 上下分列
      ratio: 0.5,
      first: { type: "leaf", id: "leaf-exposure", cardId: "exposure" },
      second: { type: "leaf", id: "leaf-bots", cardId: "bots" },
    },
  };
}

/**
 * 建立三分割樹 (左一大圖 60%, 右二上下分列 40%)
 */
export function createTriSplitTree(): LayoutNode {
  return {
    type: "split",
    id: "split-root-tri",
    direction: "row",
    ratio: 0.6,
    first: { type: "leaf", id: "leaf-equity", cardId: "equity" },
    second: {
      type: "split",
      id: "split-right-tri",
      direction: "col",
      ratio: 0.5,
      first: { type: "leaf", id: "leaf-positions", cardId: "positions" },
      second: { type: "leaf", id: "leaf-exposure", cardId: "exposure" },
    },
  };
}

/**
 * 建立雙分欄樹 (左右 50:50)
 */
export function createDualSplitTree(): LayoutNode {
  return {
    type: "split",
    id: "split-root-dual",
    direction: "row",
    ratio: 0.5,
    first: { type: "leaf", id: "leaf-equity", cardId: "equity" },
    second: { type: "leaf", id: "leaf-positions", cardId: "positions" },
  };
}

/**
 * 尋找指定 ID 的節點
 */
export function findNode(node: LayoutNode, id: string): LayoutNode | null {
  if (node.id === id) return node;
  if (node.type === "split") {
    const foundFirst = findNode(node.first, id);
    if (foundFirst) return foundFirst;
    return findNode(node.second, id);
  }
  return null;
}

/**
 * 尋找目標節點的父節點 (必為 SplitNode)
 */
export function findParent(
  root: LayoutNode,
  targetId: string
): { parent: SplitNode; childKey: "first" | "second" } | null {
  if (root.type === "leaf") return null;

  if (root.first.id === targetId) {
    return { parent: root, childKey: "first" };
  }
  if (root.second.id === targetId) {
    return { parent: root, childKey: "second" };
  }

  const inFirst = findParent(root.first, targetId);
  if (inFirst) return inFirst;

  return findParent(root.second, targetId);
}

/**
 * 取得樹中所有的葉子卡片節點
 */
export function getAllLeaves(node: LayoutNode): LeafNode[] {
  if (node.type === "leaf") return [node];
  return [...getAllLeaves(node.first), ...getAllLeaves(node.second)];
}

/**
 * 統計目前樹中的卡片總數
 */
export function countLeaves(node: LayoutNode): number {
  if (node.type === "leaf") return 1;
  return countLeaves(node.first) + countLeaves(node.second);
}

/**
 * 更新指定 Split 節點的分割比例
 */
export function updateRatio(root: LayoutNode, splitId: string, ratio: number): LayoutNode {
  const boundedRatio = Math.min(0.85, Math.max(0.15, Number(ratio.toFixed(4))));
  const next = cloneTree(root);

  function apply(node: LayoutNode): boolean {
    if (node.type === "split") {
      if (node.id === splitId) {
        node.ratio = boundedRatio;
        return true;
      }
      return apply(node.first) || apply(node.second);
    }
    return false;
  }

  apply(next);
  return next;
}

/**
 * 將指定葉子節點分裂為兩個子節點 (插入分裂)
 * @param targetLeafId 目標葉子節點 ID
 * @param direction 分割方向 ("row" 為左右分欄, "col" 為上下分列)
 * @param side "before" (左/上) 或 "after" (右/下)
 * @param newCardId 新增的卡片 ID
 */
export function splitLeaf(
  root: LayoutNode,
  targetLeafId: string,
  direction: SplitDirection,
  side: "before" | "after",
  newCardId: CardId,
  preservedLeafId?: string
): LayoutNode {
  const next = cloneTree(root);
  const targetNode = findNode(next, targetLeafId);
  if (!targetNode || targetNode.type !== "leaf") return next;

  const randSuffix = Math.random().toString(36).substring(2, 7);
  const newSplitId = `split_${Date.now()}_${randSuffix}`;
  const newLeafId = preservedLeafId || `leaf_${Date.now()}_${randSuffix}`;

  const newLeaf: LeafNode = {
    type: "leaf",
    id: newLeafId,
    cardId: newCardId,
  };

  const oldLeafCopy: LeafNode = {
    type: "leaf",
    id: targetNode.id,
    cardId: targetNode.cardId,
  };

  const newSplit: SplitNode = {
    type: "split",
    id: newSplitId,
    direction,
    ratio: 0.5,
    first: side === "before" ? newLeaf : oldLeafCopy,
    second: side === "before" ? oldLeafCopy : newLeaf,
  };

  // 如果目標本身就是根節點
  if (next.id === targetLeafId) {
    return newSplit;
  }

  // 否則找到其父節點並替換
  const parentInfo = findParent(next, targetLeafId);
  if (parentInfo) {
    parentInfo.parent[parentInfo.childKey] = newSplit;
  }

  return next;
}

/**
 * 移除指定葉子節點並自動合併兄弟分支 (Auto-Collapse / Merge)
 * 兄弟節點將直接取代父 SplitNode，填滿剩餘空間
 */
export function removeLeaf(root: LayoutNode, leafId: string): LayoutNode {
  if (root.type === "leaf") {
    // 樹只剩一張卡片時不可移除
    return root;
  }

  const next = cloneTree(root);
  const parentInfo = findParent(next, leafId);
  if (!parentInfo) return next;

  const { parent, childKey } = parentInfo;
  const sibling = childKey === "first" ? parent.second : parent.first;

  // 若父節點就是根節點，則由兄弟節點成為新根節點
  if (parent.id === next.id) {
    return sibling;
  }

  // 否則找到父節點的父節點 (祖父節點)，將祖父節點指向兄弟節點
  const grandParentInfo = findParent(next, parent.id);
  if (grandParentInfo) {
    grandParentInfo.parent[grandParentInfo.childKey] = sibling;
  }

  return next;
}

/**
 * 就地替換指定葉子節點的卡片內容
 */
export function replaceLeafCard(root: LayoutNode, leafId: string, newCardId: CardId): LayoutNode {
  const next = cloneTree(root);
  const node = findNode(next, leafId);
  if (node && node.type === "leaf") {
    node.cardId = newCardId;
    node.id = `leaf-${newCardId}`;
  }
  return next;
}

/**
 * 交換兩張葉子節點的卡片內容與身份 (Center Swap ⇄)
 */
export function swapLeaves(root: LayoutNode, leafIdA: string, leafIdB: string): LayoutNode {
  if (leafIdA === leafIdB) return root;
  const next = cloneTree(root);
  const nodeA = findNode(next, leafIdA);
  const nodeB = findNode(next, leafIdB);

  if (nodeA && nodeB && nodeA.type === "leaf" && nodeB.type === "leaf") {
    const tempCardId = nodeA.cardId;
    const tempId = nodeA.id;
    nodeA.cardId = nodeB.cardId;
    nodeA.id = nodeB.id;
    nodeB.cardId = tempCardId;
    nodeB.id = tempId;
  }

  return next;
}

/**
 * 拖曳卡片操作 (VS Code 四向扇區分裂插入)：
 * 依使用者確認徹底移除多餘的換位 (Swap)；
 * 來源節點移出後，原分支自動平滑合併填滿 (Auto-Merge)；
 * 目標位置依據扇區分裂展開 (Dock / Split ⊞)。
 */
export function moveAndSplit(
  root: LayoutNode,
  sourceLeafId: string,
  targetLeafId: string,
  dropPosition: DropPosition,
  newLeafId?: string
): LayoutNode {
  if (sourceLeafId === targetLeafId) return root;

  // 1. 記錄來源卡片型別
  const sourceNode = findNode(root, sourceLeafId);
  if (!sourceNode || sourceNode.type !== "leaf") return root;
  const sourceCardId = sourceNode.cardId;

  // 2. 先從原樹中剪除來源節點 (原分支平滑合併關閉，消除卡片移走後仍站著位置的BUG)
  const treeAfterPrune = removeLeaf(root, sourceLeafId);

  // 3. 決定新分裂的方向與前後位置
  let direction: SplitDirection = "row";
  let side: "before" | "after" = "after";

  switch (dropPosition) {
    case "left":
      direction = "row";
      side = "before";
      break;
    case "right":
      direction = "row";
      side = "after";
      break;
    case "top":
      direction = "col";
      side = "before";
      break;
    case "bottom":
      direction = "col";
      side = "after";
      break;
  }

  // 4. 在剪枝後的樹中對目標節點進行分裂插入
  return splitLeaf(
    treeAfterPrune,
    targetLeafId,
    direction,
    side,
    sourceCardId,
    newLeafId || sourceLeafId
  );
}

/**
 * 提交落位：將即時流體預演中的 preview-slot-* 節點正式轉化為永久葉子節點
 */
export function finalizeTree(node: LayoutNode): LayoutNode {
  if (node.type === "leaf") {
    if (node.id.startsWith("preview-slot-")) {
      return {
        type: "leaf",
        id: `leaf-${node.cardId}`,
        cardId: node.cardId,
      };
    }
    return { ...node };
  }
  return {
    ...node,
    first: finalizeTree(node.first),
    second: finalizeTree(node.second),
  };
}
