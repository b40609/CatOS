import { useLayoutStore, type DragPreviewMode } from "@/state/layoutStore";
import { cn } from "@/lib/utils";

const PREVIEW_CANDIDATES: { id: DragPreviewMode; label: string; desc: string }[] = [
  {
    id: "real-card",
    label: "方案 A：真實卡片即時排版 (所見即所得 · 推薦)",
    desc: "直接展開真實卡片與圖表，0 提示文字噪音，細緻金色呼吸邊框",
  },
  {
    id: "minimal-blueprint",
    label: "方案 B：極簡純淨磨砂藍圖 (零文字)",
    desc: "半透明暗金磨砂骨架，極致克制，完全無任何文字干擾",
  },
  {
    id: "mini-tag",
    label: "方案 C：微縮標籤藍圖 (微型標記)",
    desc: "保留正常卡片標題列與極細邊框，下方微型幾何輪廓",
  },
];

export function PreviewCandidateBar() {
  const dragPreviewMode = useLayoutStore((s) => s.dragPreviewMode);
  const setDragPreviewMode = useLayoutStore((s) => s.setDragPreviewMode);

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-1.5 mb-2 rounded border border-border/80 bg-surface/90 backdrop-blur-md shadow-xs select-none">
      <div className="flex items-center gap-2">
        <span className="text-[10.5px] font-mono font-bold text-primary flex items-center gap-1.5">
          <span className="size-1.5 rounded-full bg-primary animate-ping" />
          <span>拖曳落位預覽評審：</span>
        </span>
        <div className="flex items-center gap-1 bg-background/70 border border-border/70 rounded p-0.5">
          {PREVIEW_CANDIDATES.map((c) => {
            const active = dragPreviewMode === c.id;
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => setDragPreviewMode(c.id)}
                className={cn(
                  "px-2.5 py-1 text-[11px] font-medium rounded transition-all cursor-pointer flex items-center gap-1.5",
                  active
                    ? "bg-secondary text-primary border border-primary/50 shadow-xs font-semibold"
                    : "text-muted-foreground hover:text-foreground border border-transparent"
                )}
                title={c.desc}
              >
                <span>{c.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      <span className="text-[10px] font-mono text-muted-foreground">
        {PREVIEW_CANDIDATES.find((c) => c.id === dragPreviewMode)?.desc}
      </span>
    </div>
  );
}
