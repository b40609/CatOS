import { useState } from "react";
import { useLayoutStore, type GripStyle } from "@/state/layoutStore";
import { cn } from "@/lib/utils";
import { Sparkles, Check } from "lucide-react";

export function GripCandidateBar() {
  const { gripStyle, setGripStyle } = useLayoutStore();
  const [collapsed, setCollapsed] = useState(false);

  const CANDIDATES: {
    id: GripStyle;
    num: string;
    label: string;
    sub: string;
    badge: string;
    desc: string;
  }[] = [
    {
      id: "clean_text",
      num: "方案 1",
      label: "TradingView 純粹無圖示",
      sub: "Zero-Icon · 0 冗餘符號",
      badge: "最純粹",
      desc: "徹底拔除粗糙抓手符號！標題列本身即為拖曳熱區，保持頂級終端純淨度。",
    },
    {
      id: "precision_dots",
      num: "方案 2",
      label: "Linear 精工微型點",
      sub: "Micro Grip · 懸停浮現",
      badge: "現代感",
      desc: "12px 向量超精細微點，常態低調融合深黑背景，滑鼠移上時亮起金光。",
    },
    {
      id: "accent_notch",
      num: "方案 3",
      label: "Raycast 科技刻度條",
      sub: "Laser Notch · 俐落導軌",
      badge: "高科技",
      desc: "標題左側 2px 金色導軌刻度條，擺脫按鈕感，猶如專業硬體指示燈。",
    },
    {
      id: "tactical_icon",
      num: "方案 4",
      label: "彭博專業業務圖示",
      sub: "Tactical Icon · 專屬識別",
      badge: "業務感",
      desc: "以權益折線、部位圖層、槓桿標尺等專業微型圖標取代抽象抓手。",
    },
  ];

  if (collapsed) {
    return (
      <div className="absolute top-2 right-4 z-40">
        <button
          type="button"
          onClick={() => setCollapsed(false)}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-secondary/90 border border-primary/40 text-primary hover:bg-secondary text-[11px] font-mono font-medium shadow-md transition-all cursor-pointer"
        >
          <Sparkles className="size-3 text-primary animate-pulse" />
          <span>抓手方案切換 ({CANDIDATES.find(c => c.id === gripStyle)?.num})</span>
        </button>
      </div>
    );
  }

  return (
    <div className="relative z-30 mb-2 px-3 py-1.5 rounded-lg border border-primary/30 bg-surface/90 backdrop-blur-md shadow-md animate-in fade-in select-none">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex size-4 items-center justify-center rounded bg-primary/20 text-primary text-[10px] font-bold">
            ✦
          </span>
          <span className="text-[11px] font-bold text-foreground">
            拖曳抓手視覺評審候選（點擊立即實時切換）：
          </span>
        </div>

        {/* 方案切換按鈕組 */}
        <div className="flex flex-wrap items-center gap-1.5">
          {CANDIDATES.map((c) => {
            const active = gripStyle === c.id;
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => setGripStyle(c.id)}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-medium transition-all cursor-pointer border",
                  active
                    ? "bg-primary/20 border-primary text-primary font-bold shadow-xs"
                    : "bg-secondary/40 border-border/60 text-muted-foreground hover:text-foreground hover:bg-secondary/80"
                )}
                title={c.desc}
              >
                {active && <Check className="size-3 text-primary" />}
                <span>{c.num}: {c.label}</span>
                <span className={cn(
                  "text-[9px] font-mono px-1 rounded",
                  active ? "bg-primary text-black font-bold" : "bg-background/60 text-muted-foreground"
                )}>
                  {c.badge}
                </span>
              </button>
            );
          })}

          <button
            type="button"
            onClick={() => setCollapsed(true)}
            className="ml-2 text-[10px] text-muted-foreground/70 hover:text-foreground underline cursor-pointer"
            title="暫時收合評審條"
          >
            收合
          </button>
        </div>
      </div>
    </div>
  );
}
