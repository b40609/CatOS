import { useInspectorStore, type InspectorPresentationMode } from "@/state/inspectorStore";
import { cn } from "@/lib/utils";
import { Terminal, Rows3, LayoutGrid, MessageSquareText, Sparkles } from "lucide-react";

interface ModeOption {
  id: InspectorPresentationMode;
  labelZh: string;
  industryRef: string;
  icon: typeof Terminal;
  desc: string;
}

const MODES: ModeOption[] = [
  {
    id: "bottom_dock",
    labelZh: "方案 A · 底部停靠 Console",
    industryRef: "TradingView / VS Code",
    icon: Terminal,
    desc: "底層水平橫向多頁籤面板，不壓縮表格欄位，時序鏈最直觀",
  },
  {
    id: "inline_row",
    labelZh: "方案 B · 行內展開 Accordion",
    industryRef: "OKX 專業版 / Datadog",
    icon: Rows3,
    desc: "點擊表格行原地展開巢狀子區塊，視線零位移",
  },
  {
    id: "master_detail",
    labelZh: "方案 C · 主從聯動固定卡片",
    industryRef: "Bloomberg Terminal",
    icon: LayoutGrid,
    desc: "利用 T-Split 網格內置固定 Inspector 卡片，點擊即時連動，零彈窗",
  },
  {
    id: "popover_peek",
    labelZh: "方案 D · 錨點懸浮氣泡",
    industryRef: "Linear / GitHub Peek",
    icon: MessageSquareText,
    desc: "游標懸浮或點擊標籤彈出半透明浮動微型卡，移開即隱藏",
  },
  {
    id: "all_active",
    labelZh: "★ 全開自由體驗 (Hybrid)",
    industryRef: "全功能綜合",
    icon: Sparkles,
    desc: "同時啟用四種互動方式，體驗極致終端操作流",
  },
];

export function InspectorModeBar() {
  const { presentationMode, setPresentationMode, selectedBotId } = useInspectorStore();
  const currentMode = MODES.find((m) => m.id === presentationMode) ?? MODES[0];

  return (
    <div className="mb-2 p-2 rounded-lg border border-primary/30 bg-secondary/30 backdrop-blur-md flex flex-wrap items-center justify-between gap-2 shadow-xs">
      {/* 左側：模式選擇器按鈕組 */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-primary px-2 py-1 rounded bg-primary/10 border border-primary/25 shrink-0">
          呈現模式初選
        </span>

        <div className="flex flex-wrap items-center gap-1">
          {MODES.map((mode) => {
            const Icon = mode.icon;
            const isActive = presentationMode === mode.id;

            return (
              <button
                key={mode.id}
                type="button"
                onClick={() => setPresentationMode(mode.id)}
                title={mode.desc}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-mono font-semibold transition-all cursor-pointer border",
                  isActive
                    ? "bg-primary text-primary-foreground border-primary shadow-xs"
                    : "bg-surface/80 text-muted-foreground border-border/80 hover:bg-secondary hover:text-foreground hover:border-border"
                )}
              >
                <Icon className="size-3.5" />
                <span>{mode.labelZh}</span>
                <span className={cn(
                  "text-[9px] px-1 py-0.2 rounded font-normal hidden xl:inline",
                  isActive ? "bg-black/20 text-white" : "bg-background/60 text-muted-foreground"
                )}>
                  {mode.industryRef}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 右側：當前模式特色說明 */}
      <div className="flex items-center gap-2 text-[10px] font-mono text-muted-foreground">
        <span className="hidden lg:inline text-foreground/80">
          <strong className="text-primary font-semibold">{currentMode.industryRef}</strong>：{currentMode.desc}
        </span>
        <span className="px-1.5 py-0.5 rounded bg-background/80 border border-border/60 text-primary font-bold">
          選中: {selectedBotId}
        </span>
      </div>
    </div>
  );
}
