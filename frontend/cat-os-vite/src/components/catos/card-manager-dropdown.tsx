import { useState, useRef, useEffect } from "react";
import {
  Plus,
  LayoutGrid,
  Check,
  X,
  TrendingUp,
  LineChart,
  Bot,
  Sliders,
  PieChart,
  Zap,
} from "lucide-react";
import {
  useLayoutStore,
  type CardId,
} from "@/state/layoutStore";
import { getAllLeaves } from "@/lib/layout-tree/tree-ops";
import { cn } from "@/lib/utils";

interface CardMeta {
  id: CardId;
  nameZh: string;
  nameEn: string;
  category: string;
  desc: string;
  icon: typeof TrendingUp;
}

const ALL_CARDS: CardMeta[] = [
  {
    id: "equity",
    nameZh: "帳戶權益走勢",
    nameEn: "Equity & Drawdown",
    category: "資產風控",
    desc: "即時權益淨值、今日/週期損益與 7D 響應式走勢圖",
    icon: TrendingUp,
  },
  {
    id: "positions",
    nameZh: "部位與活動清單",
    nameEn: "Positions & Activity",
    category: "交易明細",
    desc: "多空持倉、限價停損掛單與即時成交流 (Tab 切換)",
    icon: LineChart,
  },
  {
    id: "bots",
    nameZh: "量化機器人矩陣",
    nameEn: "Bots Matrix",
    category: "策略執行",
    desc: "4 隻專用 KOL 策略機器人、狀態監控與一鍵啟動/暫停",
    icon: Bot,
  },
  {
    id: "exposure",
    nameZh: "多空部位配置標尺",
    nameEn: "Exposure & Margin",
    category: "風險敞口",
    desc: "雙向持倉標尺、單幣 ±50% 曝險預算防護線",
    icon: Sliders,
  },
  {
    id: "allocation",
    nameZh: "合約曝險與保證金",
    nameEn: "Exposure Donut",
    category: "資產配置",
    desc: "5 大幣種曝險甜甜圈圖與閒置保證金比例分析",
    icon: PieChart,
  },
  {
    id: "fills",
    nameZh: "最新成交動態",
    nameEn: "Recent Fills",
    category: "即時流水",
    desc: "OKX SWAP 獨佔 Tag 實時成交流水與盈虧跳動",
    icon: Zap,
  },
];

export function CardManagerDropdown() {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const {
    rootNode,
    addNewCard,
    removeLeafNode,
    applyLayoutPreset,
  } = useLayoutStore();

  // 取得當前樹中所有正在顯示的葉子節點
  const currentLeaves = getAllLeaves(rootNode);
  const activeCardIds = currentLeaves.map((l) => l.cardId);
  const canRemove = currentLeaves.length > 1;

  // 點擊外部自動收起下拉選單
  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsOpen(false);
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const handleToggleCard = (cardId: CardId) => {
    const existingLeaf = currentLeaves.find((l) => l.cardId === cardId);
    if (existingLeaf) {
      // 若已在主畫面中且允許移除，則點擊移除
      if (canRemove) {
        removeLeafNode(existingLeaf.id);
      }
    } else {
      // 若不在主畫面中，加入卡片
      addNewCard(cardId);
    }
  };

  return (
    <div ref={dropdownRef} className="relative inline-flex items-center">
      {/* 頂部顯眼的新增卡片觸發按鈕 */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className={cn(
          "flex items-center gap-1.5 h-7 px-2.5 rounded-md text-[11px] font-mono font-medium transition-all cursor-pointer border shadow-xs select-none",
          isOpen
            ? "bg-primary text-primary-foreground border-primary shadow-[0_0_12px_rgba(232,180,94,0.35)]"
            : "bg-surface-raised/80 hover:bg-secondary text-foreground hover:text-primary border-border/80 hover:border-primary/50"
        )}
        title="開啟卡片庫，自由選擇主畫面要顯示的卡片"
      >
        <Plus className={cn("size-3.5 transition-transform duration-200", isOpen && "rotate-45")} />
        <span className="font-sans font-semibold tracking-tight">新增卡片</span>
        <span
          className={cn(
            "ml-0.5 px-1 py-0.2 rounded text-[9.5px] font-mono",
            isOpen
              ? "bg-primary-foreground/20 text-primary-foreground"
              : "bg-background/60 text-muted-foreground border border-border/60"
          )}
        >
          {activeCardIds.length}/{ALL_CARDS.length}
        </span>
      </button>

      {/* 下拉卡片庫面板 (完全實心不透明背景，杜絕底層文字透光與事件穿透) */}
      {isOpen && (
        <div
          onClick={(e) => e.stopPropagation()}
          onPointerDown={(e) => e.stopPropagation()}
          className="absolute right-0 top-9 z-50 w-[360px] rounded-xl bg-surface border border-primary/50 shadow-[0_16px_48px_rgba(0,0,0,0.85),0_0_24px_rgba(232,180,94,0.15)] animate-in fade-in zoom-in-95 duration-150 p-3 select-none flex flex-col gap-2.5"
        >
          {/* 1. 面板標題列 */}
          <div className="flex items-center justify-between pb-2 border-b border-border/70">
            <div className="flex items-center gap-1.5">
              <LayoutGrid className="size-3.5 text-primary" />
              <span className="text-[12px] font-bold text-foreground tracking-tight">
                主畫面卡片庫
              </span>
            </div>
            <span className="text-[9.5px] font-mono text-muted-foreground">
              點擊開關卡片 · 即時排版
            </span>
          </div>

          {/* 2. 6 大量化卡片列表 */}
          <div className="flex flex-col gap-1.5 max-h-[340px] overflow-y-auto pr-0.5">
            {ALL_CARDS.map((card) => {
              const isAdded = activeCardIds.includes(card.id);
              const Icon = card.icon;

              return (
                <div
                  key={card.id}
                  onClick={() => handleToggleCard(card.id)}
                  className={cn(
                    "flex items-center justify-between p-2 rounded-lg border transition-all cursor-pointer group",
                    isAdded
                      ? "bg-secondary/40 border-primary/30 hover:border-rose-400/50 hover:bg-rose-400/[0.04]"
                      : "bg-background/40 border-border/60 hover:border-primary/60 hover:bg-secondary/60"
                  )}
                >
                  <div className="flex items-center gap-2.5 min-w-0 flex-1">
                    <div
                      className={cn(
                        "grid size-7 place-items-center rounded-md border shrink-0 transition-colors",
                        isAdded
                          ? "bg-primary/10 border-primary/40 text-primary"
                          : "bg-surface-raised border-border/80 text-muted-foreground group-hover:text-primary group-hover:border-primary/40"
                      )}
                    >
                      <Icon className="size-3.5" />
                    </div>

                    <div className="flex flex-col min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[11.5px] font-semibold text-foreground tracking-tight truncate">
                          {card.nameZh}
                        </span>
                        <span className="text-[9px] font-mono text-muted-foreground/70 hidden sm:inline">
                          {card.category}
                        </span>
                      </div>
                      <span className="text-[9.5px] text-muted-foreground/80 leading-tight truncate">
                        {card.desc}
                      </span>
                    </div>
                  </div>

                  {/* 狀態切換開關 */}
                  <div className="ml-2 shrink-0">
                    {isAdded ? (
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono transition-colors",
                          canRemove
                            ? "text-emerald-400 bg-emerald-400/10 border border-emerald-400/25 group-hover:bg-rose-400/15 group-hover:text-rose-400 group-hover:border-rose-400/30"
                            : "text-emerald-400/80 bg-emerald-400/10 border border-emerald-400/20"
                        )}
                        title={canRemove ? "點擊從主畫面中移除" : "保護中 (主畫面至少需保留 1 張卡片)"}
                      >
                        <Check className="size-2.5 group-hover:hidden" />
                        <X className="size-2.5 hidden group-hover:inline" />
                        <span className="group-hover:hidden">已在主畫面</span>
                        <span className="hidden group-hover:inline">
                          {canRemove ? "移除卡片" : "已鎖定"}
                        </span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10.5px] font-mono font-semibold text-primary bg-primary/15 border border-primary/40 group-hover:bg-primary group-hover:text-primary-foreground transition-all shadow-xs">
                        <Plus className="size-2.5" />
                        加入主畫面
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* 3. 底部快速預設與還原 */}
          <div className="pt-2 border-t border-border/70 flex items-center justify-between text-[10px] font-mono">
            <span className="text-muted-foreground">快速佈局預設：</span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => {
                  applyLayoutPreset("quad");
                  setIsOpen(false);
                }}
                className="px-1.5 py-0.5 rounded bg-secondary hover:bg-primary/20 hover:text-primary text-muted-foreground border border-border/60 transition-colors cursor-pointer"
                title="恢復為量化核心四分割 (60:40)"
              >
                四分割
              </button>
              <button
                type="button"
                onClick={() => {
                  applyLayoutPreset("tri");
                  setIsOpen(false);
                }}
                className="px-1.5 py-0.5 rounded bg-secondary hover:bg-primary/20 hover:text-primary text-muted-foreground border border-border/60 transition-colors cursor-pointer"
                title="主視野三分割 (左一右二)"
              >
                三分割
              </button>
              <button
                type="button"
                onClick={() => {
                  applyLayoutPreset("dual");
                  setIsOpen(false);
                }}
                className="px-1.5 py-0.5 rounded bg-secondary hover:bg-primary/20 hover:text-primary text-muted-foreground border border-border/60 transition-colors cursor-pointer"
                title="雙分欄佈局 (50:50)"
              >
                雙分欄
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
