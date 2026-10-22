import { useState, useRef, useEffect } from "react";
import {
  Plus,
  LayoutGrid,
  Check,
  X,
  TrendingUp,
  LineChart,
  Bot,
  PieChart,
  Zap,
  ShieldAlert,
  Timer,
  Target,
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

export const ALL_CARDS: CardMeta[] = [
  {
    id: "equity",
    nameZh: "帳戶權益與損益",
    nameEn: "Equity & Drawdown",
    category: "資產風控",
    desc: "即時淨值資產、今日損益與 7D 響應式走勢圖",
    icon: TrendingUp,
  },
  {
    id: "positions",
    nameZh: "持倉明細與在途委託",
    nameEn: "Positions & Orders",
    category: "交易明細",
    desc: "多空持倉 (內嵌 P6 停損)、高密度在途掛單 (撤單/凍結保證金) 與成交流",
    icon: LineChart,
  },
  {
    id: "bots",
    nameZh: "策略機器人矩陣",
    nameEn: "Bots Matrix",
    category: "策略執行",
    desc: "4 隻專用 KOL 策略機器人、狀態監控與一鍵啟動/暫停",
    icon: Bot,
  },
  {
    id: "allocation",
    nameZh: "槓桿倍數與資產曝險",
    nameEn: "Leverage & Allocation",
    category: "資產風控",
    desc: "帳戶有效槓桿倍數、幣種名義曝險與多空 Donut 資產分佈環圖",
    icon: PieChart,
  },
  {
    id: "fills",
    nameZh: "即時成交流水",
    nameEn: "Recent Fills",
    category: "即時流水",
    desc: "OKX SWAP 實時逐筆成交流水與盈虧跳動",
    icon: Zap,
  },
  {
    id: "incidents",
    nameZh: "風險警報與異常事件",
    nameEn: "Risk Incidents",
    category: "系統監控",
    desc: "撮合滑價偏離、P6 保險停損更新與風控異常警報流",
    icon: ShieldAlert,
  },
  {
    id: "market_watch",
    nameZh: "標的行情與資金費率",
    nameEn: "Market Watch & Rates",
    category: "行情時鐘",
    desc: "BTC/ETH/SOL 即時報價、OKX 資金費率結算倒數與收盤定時器",
    icon: Timer,
  },
  {
    id: "strategy_intents",
    nameZh: "策略目標與訊號強度",
    nameEn: "Signals & Radar",
    category: "策略大腦",
    desc: "Worker 傳出的純資料目標意圖、多空訊號強度與突破/均線指標距離",
    icon: Target,
  },
  {
    id: "activity_deck",
    nameZh: "交易日誌與風險事件",
    nameEn: "Activity & Events",
    category: "動態流水",
    desc: "成交流水 + 風控警報 + 系統生命週期全域稽核日誌台",
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
  const canRemove = true;

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
        <span className="font-sans font-semibold tracking-tight">卡片管理</span>
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
                版面卡片編輯
              </span>
            </div>
            <span className="text-[9.5px] font-mono text-muted-foreground">
              點擊增刪卡片 · 即時排版
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
                        title="點擊從主畫面中移除"
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

          {/* 3. 底部定案標準重置 */}
          <div className="pt-2 border-t border-border/70 flex items-center justify-between text-[10.5px]">
            <span className="text-muted-foreground font-mono text-[10px]">定案排版架構</span>
            <button
              type="button"
              onClick={() => {
                applyLayoutPreset("tsplit");
                setIsOpen(false);
              }}
              className="px-2.5 py-1 rounded text-[10.5px] font-medium bg-primary/15 text-primary border border-primary/30 hover:bg-primary hover:text-primary-foreground transition-all cursor-pointer shadow-xs"
              title="將主畫面重置為定案之 5 卡標準戰情佈局"
            >
              重置為 5 卡標準版
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
