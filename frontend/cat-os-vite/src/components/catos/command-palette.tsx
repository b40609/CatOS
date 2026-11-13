import { useState, useEffect } from "react";
import { useRouter } from "@/lib/router";
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandSeparator,
} from "@/components/ui/command";
import {
  LayoutDashboard,
  FlaskConical,
  SlidersHorizontal,
  ScanLine,
  ShieldCheck,
  ScrollText,
  Settings2,
  Bot,
  LayoutGrid,
  AlertOctagon,
  RefreshCw,
} from "lucide-react";
import { useLayoutStore, type LayoutPresetId } from "@/state/layoutStore";
import { useInspectorStore } from "@/state/inspectorStore";
import { useCatStore } from "@/state/catStore";
import { ACTIVE_STATES } from "@/contracts";
import { formatTimeframe } from "@/lib/format";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const { navigate } = useRouter();
  const { applyLayoutPreset } = useLayoutStore();
  const { selectBot } = useInspectorStore();
  const bots = useCatStore((s) => s.bots);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  const handleNav = (to: string) => {
    navigate(to);
    setOpen(false);
  };

  const handleApplyPreset = (preset: LayoutPresetId) => {
    applyLayoutPreset(preset);
    setOpen(false);
  };

  const handleSelectBot = (id: string) => {
    selectBot(id);
    navigate("/");
    setOpen(false);
    toast.info(`已聚焦機器人: ${id}`);
  };

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="輸入指令或快捷搜尋 (例如: 回測, 風控, T-Split, sim-control-sma)..." />
      <CommandList className="font-mono text-xs max-h-[380px]">
        <CommandEmpty>找不到符合的指令或目標</CommandEmpty>

        {/* 1. 頁面導航 */}
        <CommandGroup heading="頁面快速跳轉 (Navigation)">
          <CommandItem onSelect={() => handleNav("/")} className="cursor-pointer">
            <LayoutDashboard className="mr-2 size-4 text-primary" />
            <span>系統總覽 (Dashboard)</span>
          </CommandItem>
          <CommandItem onSelect={() => handleNav("/backtest")} className="cursor-pointer">
            <FlaskConical className="mr-2 size-4 text-primary" />
            <span>歷史回測 (Backtesting)</span>
          </CommandItem>
          <CommandItem onSelect={() => handleNav("/optimization")} className="cursor-pointer">
            <SlidersHorizontal className="mr-2 size-4 text-primary" />
            <span>參數優化 (Optuna Optimization)</span>
          </CommandItem>
          <CommandItem onSelect={() => handleNav("/review")} className="cursor-pointer">
            <ScanLine className="mr-2 size-4 text-primary" />
            <span>策略覆盤 (Strategy Review)</span>
          </CommandItem>
          {/* 搜尋 kill-switch 等字時優先導到風控中心（Kill-Switch 總開關與鎖存狀態） */}
          <CommandItem
            onSelect={() => handleNav("/risk")}
            keywords={["kill-switch", "re-arm", "熔斷", "鎖存"]}
            className="cursor-pointer"
          >
            <ShieldCheck className="mr-2 size-4 text-primary" />
            <span>風控中心 (Risk & R1 Period)</span>
          </CommandItem>
          <CommandItem onSelect={() => handleNav("/logs")} className="cursor-pointer">
            <ScrollText className="mr-2 size-4 text-primary" />
            <span>系統日誌 (System Logs)</span>
          </CommandItem>
          <CommandItem onSelect={() => handleNav("/settings")} className="cursor-pointer">
            <Settings2 className="mr-2 size-4 text-primary" />
            <span>系統設定 (Settings)</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {/* 2. 戰情工作台排版 */}
        <CommandGroup heading="工作台排版預設 (Layout Presets)">
          <CommandItem onSelect={() => handleApplyPreset("tsplit")} className="cursor-pointer">
            <LayoutGrid className="mr-2 size-4 text-primary" />
            <span>T-Split 5卡標準戰情 (上下解耦定案版)</span>
          </CommandItem>
          <CommandItem onSelect={() => handleApplyPreset("quad")} className="cursor-pointer">
            <LayoutGrid className="mr-2 size-4 text-primary" />
            <span>4卡象限盯盤 (雙欄對稱 50:50)</span>
          </CommandItem>
          <CommandItem onSelect={() => handleApplyPreset("full9")} className="cursor-pointer">
            <LayoutGrid className="mr-2 size-4 text-primary" />
            <span>9卡全景對照 (全卡片並開)</span>
          </CommandItem>
          <CommandItem onSelect={() => handleApplyPreset("empty")} className="cursor-pointer">
            <LayoutGrid className="mr-2 size-4 text-muted-foreground" />
            <span>一鍵清空主畫面卡片 (自由自訂)</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {/* 4. 機器人聚焦 */}
        <CommandGroup heading="策略機器人目標聚焦 (Bots)">
          {bots.length === 0 && (
            <CommandItem disabled className="text-muted-foreground">
              <Bot className="mr-2 size-4 text-muted-foreground" />
              <span>尚未取得模擬服務的 Bot 清單</span>
            </CommandItem>
          )}
          {bots.map((bot) => (
            <CommandItem key={bot.bot_id} onSelect={() => handleSelectBot(bot.bot_id)} className="cursor-pointer">
              <Bot className={cn("mr-2 size-4", ACTIVE_STATES.has(bot.state) ? "text-emerald-400" : "text-muted-foreground")} />
              <span>{bot.bot_id} ({bot.inst_id ?? "不適用"} · {formatTimeframe(bot.timeframe_ms)} · {bot.state})</span>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        {/* 5. 風控處置：Kill-Switch 導到風控中心，在那裡填原因並確認後才送出；對帳仍未接線 */}
        <CommandGroup heading="風控與應急處置 (Risk & Safety)">
          <CommandItem disabled className="text-muted-foreground">
            <RefreshCw className="mr-2 size-4 text-muted-foreground" />
            <span>帳戶與委託對帳 (Recon) · 未接線（v1 不連 OKX）</span>
          </CommandItem>
          <CommandItem onSelect={() => handleNav("/risk")} keywords={["kill", "緊急停止"]} className="cursor-pointer">
            <AlertOctagon className="mr-2 size-4 text-red-400" />
            <span>Emergency Kill-Switch · 前往風控中心</span>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
