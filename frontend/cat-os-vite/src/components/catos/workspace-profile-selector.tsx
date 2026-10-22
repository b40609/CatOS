import { useState, useRef, useEffect } from "react";
import {
  FolderKanban,
  Check,
  ChevronDown,
  Plus,
  Trash2,
  RotateCcw,
  Sparkles,
  Layers,
} from "lucide-react";
import {
  useLayoutStore,
  type LayoutPresetId,
} from "@/state/layoutStore";
import { cn } from "@/lib/utils";

interface SystemPresetOption {
  id: LayoutPresetId;
  name: string;
  tag: string;
  cardsCount: number;
}

const SYSTEM_PRESETS: SystemPresetOption[] = [
  { id: "tsplit", name: "5 卡標準戰情", tag: "出廠推薦", cardsCount: 5 },
  { id: "flagship", name: "9 卡全能旗艦", tag: "全景多螢", cardsCount: 9 },
  { id: "quad", name: "4 卡雙欄象限", tag: "經典對稱", cardsCount: 4 },
  { id: "focus_positions", name: "部位防線專注", tag: "單卡滿版", cardsCount: 1 },
];

export function WorkspaceProfileSelector() {
  const [isOpen, setIsOpen] = useState(false);
  const [isSavingNew, setIsSavingNew] = useState(false);
  const [newProfileName, setNewProfileName] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);

  const {
    profiles,
    currentProfileId,
    applyProfile,
    saveNewProfile,
    deleteProfile,
    applyLayoutPreset,
  } = useLayoutStore();

  const activeProfile = profiles.find((p) => p.id === currentProfileId) || profiles[0];

  // 點擊外部自動收起
  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
        setIsSavingNew(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
        setIsSavingNew(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const handleSaveSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProfileName.trim()) return;
    saveNewProfile(newProfileName.trim());
    setNewProfileName("");
    setIsSavingNew(false);
    setIsOpen(false);
  };

  const customProfiles = profiles.filter((p) => !p.isSystem);

  return (
    <div ref={dropdownRef} className="relative inline-flex items-center">
      {/* 觸發下拉按鈕 */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className={cn(
          "flex items-center gap-1.5 h-7 px-2.5 rounded-md text-[11px] font-mono transition-all cursor-pointer border select-none shadow-xs",
          isOpen
            ? "bg-secondary text-primary border-primary/50 shadow-[0_0_12px_rgba(232,180,94,0.2)]"
            : "bg-surface-raised/80 hover:bg-secondary text-foreground hover:text-primary border-border/80 hover:border-primary/40"
        )}
        title="切換與管理 CatOS 量化工作區配置 (Workspaces)"
      >
        <FolderKanban className="size-3.5 text-primary" />
        <span className="font-sans font-semibold tracking-tight max-w-[110px] sm:max-w-[150px] truncate">
          {activeProfile?.shortName || activeProfile?.name || "5 卡標準戰情"}
        </span>
        <ChevronDown
          className={cn("size-3 text-muted-foreground transition-transform duration-200", isOpen && "rotate-180")}
        />
      </button>

      {/* 下拉面板 */}
      {isOpen && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="absolute left-0 top-9 z-50 w-[300px] rounded-xl bg-[#14161b] border border-primary/50 shadow-[0_16px_40px_rgba(0,0,0,0.85)] p-2.5 select-none flex flex-col gap-2 animate-in fade-in zoom-in-95 duration-150"
        >
          {/* 面板標題 */}
          <div className="flex items-center justify-between pb-1.5 border-b border-border/70">
            <span className="text-[11px] font-bold text-foreground flex items-center gap-1.5 font-sans">
              <FolderKanban className="size-3.5 text-primary" />
              工作區設定檔 (Workspaces)
            </span>
            <span className="text-[9.5px] font-mono text-muted-foreground">
              {profiles.length} 組配置
            </span>
          </div>

          {/* 1. 系統內建推薦方案 */}
          <div className="flex flex-col gap-1">
            <span className="text-[9.5px] font-mono text-muted-foreground/80 px-1 uppercase tracking-wider">
              系統內建佈局
            </span>
            <div className="flex flex-col gap-0.5">
              {SYSTEM_PRESETS.map((preset) => {
                const isSelected = activeProfile?.id === "layout_tsplit_v1_core" && preset.id === "tsplit";

                return (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => {
                      applyLayoutPreset(preset.id);
                      setIsOpen(false);
                    }}
                    className={cn(
                      "flex items-center justify-between px-2 py-1.5 rounded-md text-[11px] transition-all cursor-pointer group text-left",
                      isSelected
                        ? "bg-primary/15 text-primary border border-primary/30 font-semibold"
                        : "hover:bg-secondary/70 text-foreground"
                    )}
                  >
                    <div className="flex items-center gap-1.5 min-w-0">
                      <Layers className="size-3 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                      <span className="truncate">{preset.name}</span>
                    </div>

                    <div className="flex items-center gap-1 shrink-0 font-mono text-[9px]">
                      <span className="px-1 py-0.1 rounded bg-background/60 border border-border/60 text-muted-foreground">
                        {preset.cardsCount} 卡
                      </span>
                      {isSelected && <Check className="size-3 text-primary ml-1" />}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 2. 我的自訂工作區清單 */}
          {customProfiles.length > 0 && (
            <div className="flex flex-col gap-1 pt-1.5 border-t border-border/60">
              <span className="text-[9.5px] font-mono text-muted-foreground/80 px-1 uppercase tracking-wider flex items-center justify-between">
                <span>我的自訂工作區</span>
                <span className="text-primary">{customProfiles.length} 個</span>
              </span>

              <div className="flex flex-col gap-0.5 max-h-[140px] overflow-y-auto pr-0.5">
                {customProfiles.map((p) => {
                  const isCurrent = p.id === currentProfileId;

                  return (
                    <div
                      key={p.id}
                      onClick={() => {
                        applyProfile(p.id);
                        setIsOpen(false);
                      }}
                      className={cn(
                        "flex items-center justify-between px-2 py-1.5 rounded-md text-[11px] transition-all cursor-pointer group",
                        isCurrent
                          ? "bg-primary/15 text-primary border border-primary/30 font-semibold"
                          : "hover:bg-secondary/70 text-foreground"
                      )}
                    >
                      <div className="flex items-center gap-1.5 min-w-0 flex-1">
                        <Sparkles className="size-3 text-amber-400 shrink-0" />
                        <span className="truncate">{p.name}</span>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        {isCurrent && <Check className="size-3 text-primary" />}
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteProfile(p.id);
                          }}
                          className="opacity-0 group-hover:opacity-100 p-0.5 rounded text-muted-foreground hover:text-rose-400 hover:bg-rose-400/10 transition-all cursor-pointer"
                          title="刪除此自訂版面"
                        >
                          <Trash2 className="size-3" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 3. 底部動作：另存為新工作區 或 重置 */}
          <div className="pt-2 border-t border-border/70 flex flex-col gap-1.5">
            {isSavingNew ? (
              <form onSubmit={handleSaveSubmit} className="flex flex-col gap-1.5">
                <input
                  type="text"
                  autoFocus
                  value={newProfileName}
                  onChange={(e) => setNewProfileName(e.target.value)}
                  placeholder="輸入新工作區名稱 (例如: Ryan 趨勢盤)..."
                  className="w-full px-2 py-1 rounded bg-background border border-primary/50 text-[10.5px] font-mono focus:outline-none focus:ring-1 focus:ring-primary/40 text-foreground"
                />
                <div className="flex items-center justify-end gap-1.5">
                  <button
                    type="button"
                    onClick={() => setIsSavingNew(false)}
                    className="px-2 py-0.5 rounded text-[10px] text-muted-foreground hover:text-foreground font-mono"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    disabled={!newProfileName.trim()}
                    className="px-2.5 py-0.5 rounded bg-primary text-primary-foreground text-[10px] font-semibold font-mono disabled:opacity-50"
                  >
                    保存配置
                  </button>
                </div>
              </form>
            ) : (
              <div className="flex items-center justify-between gap-1 text-[10.5px] font-mono">
                <button
                  type="button"
                  onClick={() => setIsSavingNew(true)}
                  className="flex items-center gap-1 px-2 py-1 rounded hover:bg-secondary text-primary hover:text-primary transition-colors cursor-pointer"
                >
                  <Plus className="size-3" />
                  <span>另存當前排版...</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    applyLayoutPreset("tsplit");
                    setIsOpen(false);
                  }}
                  className="flex items-center gap-1 px-2 py-1 rounded hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                  title="將畫面重置為出廠 5 卡標準戰情"
                >
                  <RotateCcw className="size-2.5" />
                  <span>還原出廠</span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
