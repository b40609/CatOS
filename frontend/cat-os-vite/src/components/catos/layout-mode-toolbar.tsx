import { useState } from "react";
import { Lock, Unlock, Plus } from "lucide-react";
import { useLayoutStore } from "@/state/layoutStore";
import { WorkspaceProfileSelector } from "./workspace-profile-selector";
import { WidgetGalleryDrawer } from "./widget-gallery-drawer";
import { ALL_CARDS } from "./card-registry";
import { getAllLeaves } from "@/lib/layout-tree/tree-ops";
import { cn } from "@/lib/utils";

export function LayoutModeToolbar() {
  const { isEditing, setEditing, rootNode } = useLayoutStore();
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const currentLeaves = getAllLeaves(rootNode);
  const activeCount = currentLeaves.length;

  return (
    <>
      <div className="flex items-center gap-1.5 shrink-0 select-none">
        {/* 1. 工作區設定檔選擇器 */}
        <WorkspaceProfileSelector />

        {/* 2. 卡片庫抽屜開關 (編輯模式下高亮提示；平常亦可快速開啟檢閱) */}
        <button
          type="button"
          onClick={() => setIsDrawerOpen(true)}
          className={cn(
            "flex items-center gap-1.5 h-7 px-2.5 rounded-md text-[11px] font-mono transition-all cursor-pointer border shadow-xs",
            isDrawerOpen
              ? "bg-primary text-primary-foreground border-primary shadow-[0_0_12px_rgba(232,180,94,0.35)]"
              : isEditing
              ? "bg-primary/20 hover:bg-primary text-primary hover:text-primary-foreground border-primary/50"
              : "bg-surface-raised/80 hover:bg-secondary text-foreground hover:text-primary border-border/80 hover:border-primary/40"
          )}
          title="開啟 catOS 卡片庫抽屜 (檢閱、加入或拖曳卡片)"
        >
          <Plus className="size-3.5" />
          <span className="font-sans font-semibold tracking-tight hidden sm:inline">卡片庫</span>
          <span className="px-1 py-0.1 rounded text-[9.5px] font-mono bg-background/60 text-muted-foreground border border-border/60">
            {activeCount}/{ALL_CARDS.length}
          </span>
        </button>

        {/* 3. 鎖定盯盤 / 解鎖編輯模式按鈕 */}
        <button
          type="button"
          onClick={() => setEditing(!isEditing)}
          className={cn(
            "flex items-center gap-1.5 h-7 px-2.5 rounded-md text-[11px] font-mono transition-all cursor-pointer border shadow-xs",
            isEditing
              ? "bg-amber-500/20 text-amber-400 border-amber-500/50 shadow-[0_0_12px_rgba(245,158,11,0.25)] font-semibold"
              : "bg-surface-raised/80 hover:bg-secondary text-muted-foreground hover:text-foreground border-border/80 hover:border-primary/40"
          )}
          title={
            isEditing
              ? "目前處於編輯自訂狀態：可直接更換視圖、關閉卡片或拖曳排版。點擊完成鎖定。"
              : "目前處於盯盤鎖定狀態：防止盤中誤觸排版。點擊解鎖以自由調整介面。"
          }
        >
          {isEditing ? (
            <>
              <Unlock className="size-3.5 text-amber-400 animate-pulse" />
              <span className="font-sans">編輯中</span>
              <span className="size-1.5 rounded-full bg-amber-400 animate-ping ml-0.5" />
            </>
          ) : (
            <>
              <Lock className="size-3.5 text-muted-foreground" />
              <span className="font-sans hidden sm:inline">盯盤鎖定</span>
            </>
          )}
        </button>
      </div>

      {/* 4. 滑出式卡片庫抽屜 */}
      <WidgetGalleryDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
      />
    </>
  );
}
