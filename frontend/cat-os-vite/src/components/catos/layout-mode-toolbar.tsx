import { useState, useEffect } from "react";
import { Cpu } from "lucide-react";
import { useLayoutStore } from "@/state/layoutStore";
import { WorkspaceProfileSelector } from "./workspace-profile-selector";
import { WidgetGalleryDrawer } from "./widget-gallery-drawer";
import { ALL_CARDS } from "./card-registry";
import { getAllLeaves } from "@/lib/layout-tree/tree-ops";
import { cn } from "@/lib/utils";

export function LayoutModeToolbar() {
  const { rootNode } = useLayoutStore();
  const [isHubOpen, setIsHubOpen] = useState(false);

  const currentLeaves = getAllLeaves(rootNode);
  const activeCount = currentLeaves.length;

  // 支援全域快捷鍵 Alt + M 快速開啟 / 關閉模組工坊
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.altKey && (e.key.toLowerCase() === "m" || e.key.toLowerCase() === "w")) {
        e.preventDefault();
        setIsHubOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <>
      <div className="flex items-center gap-1.5 shrink-0 select-none font-mono">
        {/* 1. 工作區設定檔選擇器 */}
        <WorkspaceProfileSelector />

        {/* 2. CatOS 模組工坊開關 (Module Hub) */}
        <button
          type="button"
          onClick={() => setIsHubOpen(true)}
          className={cn(
            "flex items-center gap-1.5 h-7 px-2.5 rounded-md text-[11px] font-mono transition-all cursor-pointer border shadow-xs select-none",
            isHubOpen
              ? "bg-primary text-primary-foreground border-primary shadow-[0_0_12px_rgba(232,180,94,0.35)]"
              : "bg-surface-raised/80 hover:bg-secondary text-foreground hover:text-primary border-border/80 hover:border-primary/40"
          )}
          title="開啟 catOS 模組工坊"
        >
          <Cpu className="size-3.5 text-primary" />
          <span className="font-sans font-semibold tracking-tight hidden sm:inline">模組工坊</span>
          <span className="px-1 py-0.1 rounded text-[9.5px] font-mono bg-background/60 text-muted-foreground border border-border/60">
            {activeCount}/{ALL_CARDS.length}
          </span>
        </button>
      </div>

      {/* CatOS 專屬工作區模組工坊 */}
      <WidgetGalleryDrawer
        isOpen={isHubOpen}
        onClose={() => setIsHubOpen(false)}
      />
    </>
  );
}
