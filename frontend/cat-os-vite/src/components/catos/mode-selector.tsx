import { useState, useRef, useEffect } from "react";
import { useCatStore } from "@/state/catStore";
import { stateAdapter } from "@/state/stateAdapter";
import type { BotMode } from "@/contracts";
import { cn } from "@/lib/utils";
import {
  Check,
  FlaskConical,
  Bot,
  Zap,
  type LucideIcon,
} from "lucide-react";

interface ModeOption {
  key: BotMode;
  label: string;
  tag: string;
  icon: LucideIcon;
  desc: string;
  dotClass: string;
  badgeClass: string;
  textClass: string;
}

const MODES: ModeOption[] = [
  {
    key: "local",
    label: "本機沙盒",
    tag: "LOCAL",
    icon: FlaskConical,
    desc: "本機沙盒展示 · 策略與風控模擬 (無真金風險)",
    dotClass: "bg-amber-400",
    badgeClass: "bg-amber-500/20 text-amber-400 border-amber-500/40",
    textClass: "text-amber-400",
  },
  {
    key: "demo",
    label: "Demo 模擬",
    tag: "DEMO",
    icon: Bot,
    desc: "OKX 模擬交易 · 專用子帳戶測試 (撮合行情同步)",
    dotClass: "bg-cyan-400",
    badgeClass: "bg-cyan-500/20 text-cyan-400 border-cyan-500/40",
    textClass: "text-cyan-400",
  },
  {
    key: "live",
    label: "Live 實盤",
    tag: "LIVE",
    icon: Zap,
    desc: "OKX 實盤連線 · 真實 USDT-M SWAP 交易 (警戒模式)",
    dotClass: "bg-rose-400",
    badgeClass: "bg-rose-500/20 text-rose-400 border-rose-500/40",
    textClass: "text-rose-400",
  },
];

/**
 * CatOS 環境模式切換器 (Mode Selector) - 定案方案 2：macOS Menu Bar 純 ICON 狀態燈
 * - 徹底消除「展示 ● 本機 ● Demo ● Live」文字平鋪冗餘
 * - 規格嚴格對齊控制中心（28x28px），頂部 Header 零文字干擾，極致釋放行情空間
 * - 支援多態動態圖標（FlaskConical / Bot / Zap）與右下角呼吸狀態光點
 * - 點擊展開 iOS 液態磨砂氣泡選單切換執行環境
 */
export function ModeSelector({ className }: { className?: string }) {
  const currentMode = useCatStore((s) => s.mode);
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const activeModeConfig = MODES.find((m) => m.key === currentMode) || MODES[0];
  const ActiveIcon = activeModeConfig.icon;

  const handleSelect = (mode: BotMode) => {
    void stateAdapter.setMode(mode).catch(console.error);
    setIsOpen(false);
  };

  // 點擊外部或 ESC 自動關閉下拉浮層
  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  return (
    <div ref={dropdownRef} className={cn("relative inline-flex items-center select-none", className)}>
      {/* macOS Menu Bar 純 ICON 狀態燈觸發按鈕 */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className={cn(
          "relative size-7 rounded-[7px] transition-all grid place-items-center cursor-pointer border select-none",
          isOpen
            ? "bg-primary/20 text-primary border-primary/50 shadow-[0_0_12px_rgba(232,180,94,0.35)]"
            : "bg-surface-raised/80 hover:bg-white/[0.08] border-border/80 hover:border-white/[0.16]",
          activeModeConfig.textClass
        )}
        title={`執行環境：${activeModeConfig.label} (點擊切換)`}
        aria-label={`環境切換 (${activeModeConfig.label})`}
      >
        <ActiveIcon className="size-3.5" />
        {/* 右下角微型狀態呼吸光點 */}
        <span
          className={cn(
            "absolute bottom-1 right-1 size-1.5 rounded-full border border-background",
            activeModeConfig.dotClass,
            currentMode === "local" && "animate-pulse"
          )}
        />
      </button>

      {/* 下拉浮層 Popover (iOS 液態磨砂質感) */}
      {isOpen && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="absolute right-0 top-8.5 z-50 w-[240px] rounded-xl bg-[#12141a]/95 backdrop-blur-2xl border border-white/[0.14] shadow-[0_16px_40px_rgba(0,0,0,0.85)] p-2 flex flex-col gap-1 animate-in fade-in zoom-in-95 duration-150"
        >
          <div className="px-2 py-1 border-b border-white/[0.08] flex items-center justify-between text-[10px] font-mono text-muted-foreground/80">
            <span>交易執行環境 (Environment)</span>
            <span className="text-[9px] text-primary/80">OKX SWAP</span>
          </div>

          <div className="flex flex-col gap-1 pt-1">
            {MODES.map((m) => {
              const isSelected = currentMode === m.key;
              const Icon = m.icon;
              return (
                <button
                  key={m.key}
                  type="button"
                  onClick={() => handleSelect(m.key)}
                  className={cn(
                    "flex items-start gap-2.5 px-2 py-2 rounded-lg text-left transition-all cursor-pointer border group",
                    isSelected
                      ? `${m.badgeClass} shadow-xs font-semibold`
                      : "border-transparent hover:bg-white/[0.06] text-foreground"
                  )}
                >
                  <div
                    className={cn(
                      "size-6 rounded-md flex items-center justify-center shrink-0 border mt-0.5",
                      isSelected
                        ? "bg-background/60 border-current"
                        : "bg-white/[0.04] border-white/[0.08] text-muted-foreground group-hover:text-foreground"
                    )}
                  >
                    <Icon className="size-3.5" />
                  </div>

                  <div className="flex flex-col min-w-0 flex-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold tracking-tight">{m.label}</span>
                      {isSelected && <Check className="size-3 text-current" />}
                    </div>
                    <p className="text-[10px] text-muted-foreground leading-tight font-sans mt-0.5 opacity-90">
                      {m.desc}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
