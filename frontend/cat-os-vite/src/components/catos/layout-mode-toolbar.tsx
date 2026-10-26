import { useState, useEffect } from "react";
import { SlidersHorizontal } from "lucide-react";
import { useLayoutStore } from "@/state/layoutStore";
import { WidgetGalleryDrawer } from "./widget-gallery-drawer";
import { cn } from "@/lib/utils";

/**
 * CatOS 頂部控制列 - macOS / iOS Control Center 風格純 ICON 按鈕
 * - 徹底剔除「幾卡幾頂部」冗餘標籤，螢幕每一像素皆服務於即時交易數據
 * - 28x28px 高密度磨砂微型按鈕，100% 對齊 macOS Menu Bar 控制中心直覺
 * - 支援全域快捷鍵 Alt + M / Alt + W (Mac: Option + M / W)
 */
export function LayoutModeToolbar() {
  const { profiles, currentProfileId } = useLayoutStore();
  const [isHubOpen, setIsHubOpen] = useState(false);

  const activeProfile = profiles.find((p) => p.id === currentProfileId) || profiles[0];

  // 支援全域快捷鍵 Alt + M 或 Alt + W 快速開啟 / 關閉控制中心
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
      <div className="flex items-center shrink-0 select-none">
        {/* macOS Menu Bar 控制中心微型按鈕 */}
        <button
          type="button"
          onClick={() => setIsHubOpen((prev) => !prev)}
          className={cn(
            "size-7 rounded-[7px] transition-all grid place-items-center cursor-pointer border select-none",
            isHubOpen
              ? "bg-primary text-primary-foreground border-primary shadow-[0_0_12px_rgba(232,180,94,0.35)]"
              : "bg-surface-raised/80 hover:bg-white/[0.08] text-muted-foreground hover:text-foreground border-border/80 hover:border-white/[0.16]"
          )}
          title={`控制中心 · 目前：${activeProfile?.shortName || activeProfile?.name || "預設排版"} (Alt+M / Alt+W)`}
          aria-label="控制中心"
        >
          <SlidersHorizontal className="size-3.5" />
        </button>
      </div>

      {/* CatOS 專屬 iOS/macOS 磨砂控制中心面板 */}
      <WidgetGalleryDrawer
        isOpen={isHubOpen}
        onClose={() => setIsHubOpen(false)}
      />
    </>
  );
}
