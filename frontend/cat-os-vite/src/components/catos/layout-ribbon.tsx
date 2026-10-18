import { useState } from "react";
import {
  Check,
  RotateCcw,
  SlidersHorizontal,
  Sparkles,
  Eye,
  Sliders,
  Maximize2,
  MousePointerClick,
  CheckCircle2,
} from "lucide-react";
import { useLayoutStore, type ToolbarMode } from "@/state/layoutStore";
import { cn } from "@/lib/utils";

export function LayoutRibbon() {
  const {
    toolbarMode,
    setToolbarMode,
    isEditing,
    setEditing,
    resetSplits,
    showToast,
  } = useLayoutStore();

  const [isFinalized, setIsFinalized] = useState(false);

  const CANDIDATES: {
    id: ToolbarMode;
    label: string;
    sub: string;
    icon: typeof Eye;
    badge: string;
    desc: string;
  }[] = [
    {
      id: "header",
      label: "方案 1: Header 右側整合",
      sub: "0px 額外浪費 · Bloomberg/VS Code 規範",
      icon: Eye,
      badge: "最推薦",
      desc: "完全拔除中間橫條！調整按鈕直接收進頂部全域 Header 右側，將 100% 垂直高度完整留給工作區。",
    },
    {
      id: "card",
      label: "方案 2: 卡片標頭內嵌",
      sub: "收納於左上「帳戶權益」右上角",
      icon: Sliders,
      badge: "內嵌式",
      desc: "完全拔除中間橫條！將按鈕放在左上角主卡片 Header（週期 24H/7D/30D 旁），不佔用任何全局橫向空間。",
    },
    {
      id: "always_on",
      label: "方案 3: 常態拖曳零按鈕",
      sub: "Zero-UI · 永遠無任何多餘按鈕",
      icon: Maximize2,
      badge: "極致乾淨",
      desc: "完全拔除中間橫條與按鈕！四分割常態允許拖曳拉伸與對調位置，雙擊中線自動還原 60:40，零按鈕視覺。",
    },
    {
      id: "ribbon",
      label: "方案 4: 獨立精簡橫條",
      sub: "純粹工具列 · 刪除所有自我說明廢話",
      icon: MousePointerClick,
      badge: "對照組",
      desc: "徹底刪除「已定案 60:40 · 純淨視野」等廢話文字，僅保留微型工具列，作為高度對照組。",
    },
  ];

  const currentCandidate = CANDIDATES.find((c) => c.id === toolbarMode) || CANDIDATES[0];

  return (
    <div className="relative mb-2 space-y-1.5 select-none">
      {/* 1. 方案切換評審列 (可隨時切換 4 種方案眼見為憑) */}
      {!isFinalized ? (
        <div className="rounded-lg border border-amber-500/30 bg-amber-950/20 px-3 py-2 text-xs shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-amber-500/20 pb-2">
            <div className="flex items-center gap-2">
              <span className="flex size-5 items-center justify-center rounded bg-amber-500/20 text-amber-400 font-bold text-xs">
                ⚙
              </span>
              <span className="font-semibold text-amber-200">
                「調整版面按鈕該放哪？」4 大候選方案即時切換評審
              </span>
              <span className="rounded bg-amber-500/10 px-1.5 py-0.5 font-mono text-[10px] text-amber-300">
                點擊下方按鈕直接切換體驗
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[11px] text-muted-foreground hidden md:inline">
                看滿意後可點擊：
              </span>
              <button
                type="button"
                onClick={() => {
                  setIsFinalized(true);
                  showToast(`已定案【${currentCandidate.label}】！評審列已隱藏。`);
                }}
                className="flex items-center gap-1 rounded bg-amber-500 hover:bg-amber-400 text-black px-2.5 py-1 text-[11px] font-bold transition-all cursor-pointer shadow-xs"
              >
                <CheckCircle2 className="size-3.5" />
                <span>定案此方案並隱藏評審列</span>
              </button>
            </div>
          </div>

          {/* 4 候選方案切換 Tabs */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-1.5 mt-2">
            {CANDIDATES.map((cand) => {
              const Icon = cand.icon;
              const isActive = toolbarMode === cand.id;
              return (
                <button
                  key={cand.id}
                  type="button"
                  onClick={() => setToolbarMode(cand.id)}
                  className={cn(
                    "flex flex-col text-left p-2 rounded-md border transition-all cursor-pointer relative",
                    isActive
                      ? "border-amber-400 bg-amber-500/15 shadow-[0_0_12px_rgba(245,158,11,0.2)] text-amber-100"
                      : "border-border/60 bg-secondary/40 text-muted-foreground hover:bg-secondary hover:text-foreground"
                  )}
                >
                  <div className="flex items-center justify-between w-full">
                    <div className="flex items-center gap-1.5">
                      <Icon className={cn("size-3.5", isActive ? "text-amber-400" : "text-muted-foreground")} />
                      <span className={cn("font-medium text-xs", isActive ? "text-amber-200 font-bold" : "")}>
                        {cand.label}
                      </span>
                    </div>
                    <span
                      className={cn(
                        "text-[9.5px] px-1 py-0.2 rounded font-mono font-semibold",
                        isActive ? "bg-amber-400 text-black" : "bg-secondary text-muted-foreground"
                      )}
                    >
                      {cand.badge}
                    </span>
                  </div>
                  <span className="text-[10px] text-muted-foreground/80 mt-1 line-clamp-1">
                    {cand.sub}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="mt-1.5 text-[11px] text-amber-300/80 font-mono">
            💡 當前切換效果：<strong>{currentCandidate.desc}</strong>
          </div>
        </div>
      ) : (
        /* 若已定案隱藏，保留右上角極小「重新切換方案」按鈕 */
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => setIsFinalized(false)}
            className="text-[10px] text-muted-foreground hover:text-amber-400 underline cursor-pointer"
          >
            ⚙ 重新評審版面工具按鈕位置方案 (當前: {currentCandidate.label})
          </button>
        </div>
      )}

      {/* 2. 方案 4 (獨立精簡橫條) 專用渲染區塊：徹底刪除廢話，僅留純粹工具列 */}
      {toolbarMode === "ribbon" && (
        <div className="flex items-center justify-between gap-2.5 rounded-lg border border-border/70 bg-[#16191e] px-3 py-1.5">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-[#90969d]">工作區控制項</span>
            {isEditing && (
              <span className="flex items-center gap-1.5 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary animate-pulse">
                <span className="size-1.5 rounded-full bg-primary" />
                <span>版面微調中</span>
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {isEditing && (
              <button
                type="button"
                onClick={resetSplits}
                className="flex items-center gap-1.5 rounded border border-border/80 bg-[#1d2127] px-2.5 py-1 text-[11px] text-[#90969d] hover:text-[#e5e8ec] transition-all cursor-pointer"
                title="還原 60:40 預設比例"
              >
                <RotateCcw className="size-3" />
                <span>還原 60:40</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => setEditing(!isEditing)}
              className={cn(
                "flex items-center gap-1.5 rounded px-3 py-1 text-xs font-semibold transition-all cursor-pointer shadow-xs",
                isEditing
                  ? "bg-primary text-primary-foreground hover:bg-primary/90"
                  : "border border-border/80 bg-[#1d2127] text-foreground hover:bg-[#252a32] hover:border-primary/50"
              )}
            >
              {isEditing ? (
                <>
                  <Check className="size-3.5" />
                  <span>完成鎖定</span>
                </>
              ) : (
                <>
                  <SlidersHorizontal className="size-3.5 text-primary" />
                  <span>⚙ 調整版面</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* 3. 編輯模式提示橫幅 (微調小撇步) */}
      {isEditing && toolbarMode !== "always_on" && (
        <div className="flex items-center justify-between rounded border border-primary/30 bg-primary/10 px-3 py-1 text-xs text-primary animate-in fade-in duration-200">
          <div className="flex items-center gap-2">
            <Sparkles className="size-3.5 shrink-0" />
            <span className="text-[11px]">
              <strong>微調小撇步：</strong> 拖動分割線自由拉伸比例 · 按住卡片標題列可拖曳邊緣分裂排版
            </span>
          </div>
          <button
            type="button"
            onClick={() => setEditing(false)}
            className="text-[10px] underline hover:opacity-80 cursor-pointer"
          >
            知道了
          </button>
        </div>
      )}
    </div>
  );
}

