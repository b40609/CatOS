import {
  Check,
  RotateCcw,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react";
import { useLayoutStore } from "@/state/layoutStore";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function LayoutRibbon() {
  const { language } = useI18n();
  const {
    isEditing,
    setEditing,
    resetSplits,
    toastMessage,
  } = useLayoutStore();

  return (
    <div className="relative mb-3 space-y-2 select-none">
      {/* 頂部執行工具帶：定案方案 A (Bloomberg 經典)，僅保留調整版面與解鎖編輯控件 */}
      <div className="flex items-center justify-between gap-2.5 rounded-xl border border-border/60 bg-secondary/30 px-3.5 py-1.5 backdrop-blur-md">
        
        {/* 左側：定案方案 舒展四分割 60:40 靜態識別標籤 / 編輯中狀態 */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span>🔲</span>
            <span className="font-medium text-foreground">
              {language === "zh-TW" ? "舒展四分割版面 (已定案)" : "Quad Grid Layout (Finalized)"}
            </span>
            <span className="font-mono text-[10.5px] font-semibold text-primary">60:40</span>
          </div>

          {/* 編輯微調動態脈衝指示燈 (僅在解鎖編輯時顯示) */}
          {isEditing && (
            <span className="ml-1.5 flex items-center gap-1.5 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary animate-pulse">
              <span className="size-1.5 rounded-full bg-primary" />
              <span>{language === "zh-TW" ? "版面微調中" : "Editing Layout"}</span>
            </span>
          )}
        </div>

        {/* 右側：還原比例與「⚙ 調整版面 / ✓ 完成鎖定」按鈕 */}
        <div className="flex items-center gap-2">
          {/* 解鎖模式下的還原比例按鈕 */}
          {isEditing && (
            <button
              type="button"
              onClick={resetSplits}
              className="flex items-center gap-1.5 rounded-lg border border-border/60 bg-secondary/50 px-2.5 py-1 text-[11px] text-muted-foreground hover:text-foreground transition-all cursor-pointer shadow-xs"
              title="還原預設黃金比例 (60:40)"
            >
              <RotateCcw className="size-3" />
              <span>{language === "zh-TW" ? "還原比例 (60:40)" : "Reset Ratio"}</span>
            </button>
          )}

          {/* 核心開關：解鎖 / 完成鎖定 */}
          <button
            type="button"
            onClick={() => setEditing(!isEditing)}
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-semibold transition-all cursor-pointer shadow-xs",
              isEditing
                ? "bg-primary text-primary-foreground hover:bg-primary/90"
                : "border border-border/80 bg-secondary/60 text-foreground hover:bg-secondary hover:border-primary/50"
            )}
            title={isEditing ? "鎖定工作台並固定卡片尺寸" : "解鎖工作台：拖曳分割線縮放大小、拖曳標題換位"}
          >
            {isEditing ? (
              <>
                <Check className="size-3.5" />
                <span>{language === "zh-TW" ? "完成鎖定" : "Lock Layout"}</span>
              </>
            ) : (
              <>
                <SlidersHorizontal className="size-3.5 text-primary" />
                <span>{language === "zh-TW" ? "⚙ 調整版面" : "⚙ Adjust Layout"}</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* 編輯模式提示橫幅 (微調小撇步) */}
      {isEditing && (
        <div className="flex items-center justify-between rounded-lg border border-primary/30 bg-primary/10 px-3.5 py-1.5 text-xs text-primary animate-in fade-in duration-200">
          <div className="flex items-center gap-2">
            <Sparkles className="size-3.5 shrink-0" />
            <span className="text-[11px]">
              <strong>{language === "zh-TW" ? "微調小撇步：" : "Quick Tips:"}</strong>{" "}
              {language === "zh-TW"
                ? "拖動中央分割線自由拉伸寬度 · 拖動水平線調整卡片高度 · 按住卡片抓手 ⋮⋮ 可直接對調位置"
                : "Drag splitters to resize · Drag ⋮⋮ grip to swap card positions"}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setEditing(false)}
            className="text-[10px] opacity-75 hover:opacity-100 cursor-pointer ml-2"
          >
            ✕ {language === "zh-TW" ? "收起" : "Close"}
          </button>
        </div>
      )}

      {/* Toast 提示浮條 */}
      {toastMessage && (
        <div className="absolute top-12 left-1/2 -translate-x-1/2 z-50 rounded-full border border-border/70 bg-popover/95 px-4 py-1.5 shadow-2xl backdrop-blur-xl text-xs font-mono text-foreground flex items-center gap-2 animate-in fade-in slide-in-from-top-1">
          <span className="size-1.5 rounded-full bg-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
}
