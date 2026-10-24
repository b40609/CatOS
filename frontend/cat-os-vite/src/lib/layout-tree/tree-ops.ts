import type { CardId } from "@/state/layoutStore";
import type { LayoutNode, LeafNode, SplitNode, SplitDirection, DropPosition } from "./types";
import { CARD_DEFAULT_MIN_HEIGHTS } from "@/components/catos/card-registry";

/**
 * 深度拷貝 LayoutNode 樹
 */
export function cloneTree(node: LayoutNode): LayoutNode {
  if (node.type === "leaf") {
    return {
      ...node,
      tabs: node.tabs ? [...node.tabs] : undefined,
    };
  }
  return {
    ...node,
    first: cloneTree(node.first),
    second: cloneTree(node.second),
  };
}

/**
 * 建立系統預設的「定案方案 2：上下分層 T-Split 解耦樹 (Row-First)」
 * 頂層水平分行 (col, 50:50)，上下兩層之垂直分割線徹底獨立解耦：
 * - 上半部：[帳戶權益 (equity)] ｜ [量化機器人 (bots)] ｜ [資產配置 Donut (allocation)]
 * - 下半部：[部位活動與在途防線 (positions)] ｜ [全域戰情日誌 (activity_deck)]
 * 垂直分割線互不綁架，持倉與在途盤口專注防線，獨立全域戰情日誌台彙總成交流與風控事件。
 */
export function createDefaultTree(): LayoutNode {
  return {
    type: "split",
    id: "split-root",
    direction: "col", // 上下分層
    ratio: 0.5,
    first: {
      type: "split",
      id: "split-top-tier",
      direction: "row", // 上半部左右分欄
      ratio: 0.72,
      first: {
        type: "split",
        id: "split-top-left",
        direction: "row",
        ratio: 0.58,
        first: { type: "leaf", id: "leaf-equity", cardId: "equity" },
        second: { type: "leaf", id: "leaf-bots", cardId: "bots" },
      },
      second: { type: "leaf", id: "leaf-allocation", cardId: "allocation" },
    },
    second: {
      type: "split",
      id: "split-bottom-tier",
      direction: "row", // 下半部左右分欄：部位活動與在途防線 ｜ 全域戰情日誌台 (定案)
      ratio: 0.52,
      first: { type: "leaf", id: "leaf-positions", cardId: "positions" },
      second: { type: "leaf", id: "leaf-activity-deck", cardId: "activity_deck" },
    },
  };
}

/**
 * 推薦佈局 2：4卡象限盯盤 (雙欄經典對稱 · 50:50 純粹平衡)
 * 左欄：[帳戶權益 (equity)] / [部位防線 (positions)]
 * 右欄：[量化機器人 (bots)] / [全域戰情日誌 (activity_deck)]
 */
export function createQuadTree(): LayoutNode {
  return {
    type: "split",
    id: "split-quad-root",
    direction: "row",
    ratio: 0.5,
    first: {
      type: "split",
      id: "split-quad-left",
      direction: "col",
      ratio: 0.5,
      first: { type: "leaf", id: "leaf-equity", cardId: "equity" },
      second: { type: "leaf", id: "leaf-positions", cardId: "positions" },
    },
    second: {
      type: "split",
      id: "split-quad-right",
      direction: "col",
      ratio: 0.5,
      first: { type: "leaf", id: "leaf-bots", cardId: "bots" },
      second: { type: "leaf", id: "leaf-activity-deck", cardId: "activity_deck" },
    },
  };
}

/**
 * 推薦佈局 3：3卡風控防線專注 (左側 60% 盤口主視野)
 * 左欄 (60%)：[部位活動與盤口防線 (positions)] 滿版廣角
 * 右欄 (40%)：[量化機器人 (bots)] / [全域戰情日誌 (activity_deck)]
 */
export function createSentinelTree(): LayoutNode {
  return {
    type: "split",
    id: "split-sentinel-root",
    direction: "row",
    ratio: 0.6,
    first: { type: "leaf", id: "leaf-positions", cardId: "positions" },
    second: {
      type: "split",
      id: "split-sentinel-right",
      direction: "col",
      ratio: 0.5,
      first: { type: "leaf", id: "leaf-bots", cardId: "bots" },
      second: { type: "leaf", id: "leaf-activity-deck", cardId: "activity_deck" },
    },
  };
}

/**
 * 推薦佈局 4：6卡操盤旗艦 (全功能多螢全景監控)
 * 上層：[帳戶權益 (33%)] ｜ [量化機器人 (33%)] ｜ [標的行情 (34%)]
 * 下層：[部位防線 (40%)] ｜ [全域戰情日誌 (35%)] ｜ [即時成交流 (25%)]
 */
export function createFlagshipTree(): LayoutNode {
  return {
    type: "split",
    id: "split-flagship-root",
    direction: "col",
    ratio: 0.5,
    first: {
      type: "split",
      id: "split-flagship-top",
      direction: "row",
      ratio: 0.33,
      first: { type: "leaf", id: "leaf-equity", cardId: "equity" },
      second: {
        type: "split",
        id: "split-flagship-top-right",
        direction: "row",
        ratio: 0.5,
        first: { type: "leaf", id: "leaf-bots", cardId: "bots" },
        second: { type: "leaf", id: "leaf-market-watch", cardId: "market_watch" },
      },
    },
    second: {
      type: "split",
      id: "split-flagship-bottom",
      direction: "row",
      ratio: 0.4,
      first: { type: "leaf", id: "leaf-positions", cardId: "positions" },
      second: {
        type: "split",
        id: "split-flagship-bottom-right",
        direction: "row",
        ratio: 0.58,
        first: { type: "leaf", id: "leaf-activity-deck", cardId: "activity_deck" },
        second: { type: "leaf", id: "leaf-fills", cardId: "fills" },
      },
    },
  };
}

/**
 * 推薦佈局 5：單卡滿版專注 (100% 滿版展示單一卡片)
 */

/**
 * 方案 C：主從聯動固定分區 (Bloomberg Terminal 互鎖視圖)
 * 左側：[帳戶權益 (equity)] + [策略機器人 (bots)]
 * 右側：[機器人深層檢測 (bot_inspector)] + [全域戰情日誌 (activity_deck)]
 */
export function createMasterDetailTree(): LayoutNode {
  return {
    type: "split",
    id: "split-master-detail-root",
    direction: "row",
    ratio: 0.52,
    first: {
      type: "split",
      id: "split-md-left",
      direction: "col",
      ratio: 0.42,
      first: { type: "leaf", id: "leaf-equity", cardId: "equity" },
      second: { type: "leaf", id: "leaf-bots", cardId: "bots" },
    },
    second: {
      type: "split",
      id: "split-md-right",
      direction: "col",
      ratio: 0.58,
      first: { type: "leaf", id: "leaf-bot-inspector", cardId: "bot_inspector" },
      second: { type: "leaf", id: "leaf-activity-deck", cardId: "activity_deck" },
    },
  };
}

/**
 * 對照排版 1：策略機器人 vs 策略意圖 (50:50 左右並排比對)
 */
export function createCompareIntentTree(): LayoutNode {
  return {
    type: "split",
    id: "split-compare-intent",
    direction: "row",
    ratio: 0.5,
    first: { type: "leaf", id: "leaf-bots", cardId: "bots" },
    second: { type: "leaf", id: "leaf-strategy-intents", cardId: "strategy_intents" },
  };
}

/**
 * 對照排版 2：交易日誌 vs 即時成交流水 + 風險警報 (左右並排比對)
 */
export function createCompareActivityTree(): LayoutNode {
  return {
    type: "split",
    id: "split-compare-activity",
    direction: "row",
    ratio: 0.5,
    first: { type: "leaf", id: "leaf-activity-deck", cardId: "activity_deck" },
    second: {
      type: "split",
      id: "split-compare-activity-right",
      direction: "col",
      ratio: 0.5,
      first: { type: "leaf", id: "leaf-fills", cardId: "fills" },
      second: { type: "leaf", id: "leaf-incidents", cardId: "incidents" },
    },
  };
}

/**
 * 對照排版 3：全部 9 大卡片全景排版
 */
export function createFull9Tree(): LayoutNode {
  return {
    type: "split",
    id: "split-full9-root",
    direction: "col",
    ratio: 0.33,
    first: {
      type: "split",
      id: "split-full9-row1",
      direction: "row",
      ratio: 0.33,
      first: { type: "leaf", id: "leaf-equity", cardId: "equity" },
      second: {
        type: "split",
        id: "split-full9-row1-right",
        direction: "row",
        ratio: 0.5,
        first: { type: "leaf", id: "leaf-bots", cardId: "bots" },
        second: { type: "leaf", id: "leaf-market-watch", cardId: "market_watch" },
      },
    },
    second: {
      type: "split",
      id: "split-full9-bottom",
      direction: "col",
      ratio: 0.5,
      first: {
        type: "split",
        id: "split-full9-row2",
        direction: "row",
        ratio: 0.35,
        first: { type: "leaf", id: "leaf-positions", cardId: "positions" },
        second: {
          type: "split",
          id: "split-full9-row2-right",
          direction: "row",
          ratio: 0.5,
          first: { type: "leaf", id: "leaf-allocation", cardId: "allocation" },
          second: { type: "leaf", id: "leaf-strategy-intents", cardId: "strategy_intents" },
        },
      },
      second: {
        type: "split",
        id: "split-full9-row3",
        direction: "row",
        ratio: 0.45,
        first: { type: "leaf", id: "leaf-activity-deck", cardId: "activity_deck" },
        second: {
          type: "split",
          id: "split-full9-row3-right",
          direction: "row",
          ratio: 0.5,
          first: { type: "leaf", id: "leaf-fills", cardId: "fills" },
          second: { type: "leaf", id: "leaf-incidents", cardId: "incidents" },
        },
      },
    },
  };
}

export function createFocusTree(cardId: CardId = "positions"): LayoutNode {
  return {
    type: "leaf",
    id: "leaf-" + cardId,
    cardId,
  };
}


/**
 * 尋找指定 ID 的節點
 */
export function findNode(node: LayoutNode | null | undefined, id: string): LayoutNode | null {
  if (!node) return null;
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
export function getAllLeaves(node: LayoutNode | null | undefined): LeafNode[] {
  if (!node) return [];
  if (node.type === "leaf") return [node];
  return [...getAllLeaves(node.first), ...getAllLeaves(node.second)];
}

/**
 * 統計目前樹中的卡片總數
 */
export function countLeaves(node: LayoutNode | null | undefined): number {
  if (!node) return 0;
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
export function removeLeaf(root: LayoutNode, leafId: string): LayoutNode | null {
  if (root.type === "leaf") {
    if (root.id === leafId) return null;
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
 * 將卡片作為 Tab 分頁加入目標葉子節點 (Tab Stack / Dock)
 */
export function addTabToLeaf(
  root: LayoutNode,
  targetLeafId: string,
  cardId: CardId
): LayoutNode {
  const next = cloneTree(root);
  const target = findNode(next, targetLeafId);
  if (target && target.type === "leaf") {
    const existingTabs = target.tabs && target.tabs.length > 0 ? target.tabs : [target.cardId];
    if (!existingTabs.includes(cardId)) {
      target.tabs = [...existingTabs, cardId];
    }
    target.activeTab = cardId;
    target.cardId = cardId;
  }
  return next;
}

/**
 * 切換特定葉子節點中目前啟用的分頁 (Switch Active Tab)
 */
export function switchLeafTab(
  root: LayoutNode,
  targetLeafId: string,
  cardId: CardId
): LayoutNode {
  const next = cloneTree(root);
  const target = findNode(next, targetLeafId);
  if (target && target.type === "leaf") {
    target.activeTab = cardId;
    target.cardId = cardId;
  }
  return next;
}

/**
 * 從特定葉子節點中移除單一 Tab 分頁
 * 若移除後僅剩 0 個 Tab，則移除該葉子節點；若剩餘 1 個，則收斂為單卡。
 */
export function removeTabFromLeaf(
  root: LayoutNode,
  targetLeafId: string,
  cardIdToRemove: CardId
): LayoutNode | null {
  const next = cloneTree(root);
  const target = findNode(next, targetLeafId);
  if (!target || target.type !== "leaf") return root;

  const currentTabs = target.tabs && target.tabs.length > 0 ? target.tabs : [target.cardId];
  const nextTabs = currentTabs.filter((t) => t !== cardIdToRemove);

  if (nextTabs.length === 0) {
    // 該容器已空，自動剪除此葉子節點
    return removeLeaf(next, targetLeafId);
  }

  // 決定下一個 activeTab
  const nextActive = target.activeTab === cardIdToRemove
    ? nextTabs[0]
    : (target.activeTab || nextTabs[0]);

  target.tabs = nextTabs.length > 1 ? nextTabs : undefined;
  target.activeTab = nextActive;
  target.cardId = nextActive;

  return next;
}

/**
 * 拖曳卡片操作 (四向扇區分裂插入 ＋ 中央落點卡片對調換位 Central Swap ⇄)：
 * - 若落點為 center，觸發兩張卡片對調換位 (Swap ⇄) 或從卡片庫就地替換；
 * - 若落點為四周邊界，來源節點移出後原分支自動平滑合併填滿 (Auto-Merge)，並在目標邊界分裂展開 (Dock / Split ⊞)。
 */
export function moveAndSplit(
  root: LayoutNode,
  sourceLeafId: string,
  targetLeafId: string,
  dropPosition: DropPosition,
  newLeafId?: string,
  draggedCardId?: CardId
): LayoutNode {
  if (sourceLeafId === targetLeafId) return root;

  const isGalleryNew = sourceLeafId.startsWith("gallery-new-");
  const sourceNode = isGalleryNew ? null : (findNode(root, sourceLeafId) as LeafNode | null);
  const sourceCardId: CardId | undefined = isGalleryNew
    ? (draggedCardId || (sourceLeafId.replace("gallery-new-", "") as CardId))
    : sourceNode?.cardId;

  if (!sourceCardId) return root;

  // 1. 若落點為中央區域 (center)：觸發卡片對調換位 (Central Swap ⇄) 或自卡片庫就地替換
  if (dropPosition === "center") {
    if (isGalleryNew) {
      return replaceLeafCard(root, targetLeafId, sourceCardId);
    }
    return swapLeaves(root, sourceLeafId, targetLeafId);
  }

  // 2. 四邊邊界分裂：先從原樹中剪除來源節點 (原分支平滑合併關閉)
  let treeAfterPrune: LayoutNode | null = root;
  if (!isGalleryNew) {
    treeAfterPrune = removeLeaf(root, sourceLeafId);
    if (!treeAfterPrune) return root;
  }

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
    newLeafId || (isGalleryNew ? `leaf-${sourceCardId}-${Date.now()}` : sourceLeafId)
  );
}

/**
 * 遞迴計算 Layout Tree 在垂直方向上所需的最小安全閱讀高度 (px)
 * 當樹狀分割層級過多導致所需高度大於視窗高度時，以此數值作為畫布高度，觸發外層平滑縱向滾動
 */
export function calculateTreeMinHeight(
  node: LayoutNode | null | undefined,
  minHeights: Record<CardId, number> = CARD_DEFAULT_MIN_HEIGHTS
): number {
  if (!node) return 0;
  if (node.type === "leaf") {
    return minHeights[node.cardId] || 300;
  }
  const hFirst = calculateTreeMinHeight(node.first, minHeights);
  const hSecond = calculateTreeMinHeight(node.second, minHeights);
  if (node.direction === "row") {
    // 左右並排：高度取二者之較大值
    return Math.max(hFirst, hSecond);
  } else {
    // 上下垂直分割：二者高度相加 + 5px 間隙
    const sumMin = hFirst + hSecond + 5;
    const r = Math.max(0.1, Math.min(0.9, node.ratio));
    const ratioFirst = Math.ceil(hFirst / r);
    const ratioSecond = Math.ceil(hSecond / (1 - r));
    return Math.max(sumMin, Math.min(ratioFirst, ratioSecond));
  }
}


/**
 * 提交落位：將即時流體預演中的 preview-slot-* 節點正式轉化為永久葉子節點
 */
export function finalizeTree(node: LayoutNode): LayoutNode;
export function finalizeTree(node: LayoutNode | null | undefined): LayoutNode | null;
export function finalizeTree(node: LayoutNode | null | undefined): LayoutNode | null {
  if (!node) return null;
  if (node.type === "leaf") {
    if (node.id.startsWith("preview-slot-")) {
      return {
        type: "leaf",
        id: `leaf-${node.cardId}-${Date.now().toString(36)}`,
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
