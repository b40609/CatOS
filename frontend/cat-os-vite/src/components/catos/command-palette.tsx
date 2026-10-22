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
  Globe2,
  ScrollText,
  Settings2,
  Bot,
  LayoutGrid,
  AlertOctagon,
  RefreshCw,
} from "lucide-react";
import { useLayoutStore, type LayoutPresetId } from "@/state/layoutStore";
import { useInspectorStore } from "@/state/inspectorStore";
import { toast } from "sonner";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const { navigate } = useRouter();
  const { applyLayoutPreset } = useLayoutStore();
  const { selectBot } = useInspectorStore();

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
      <CommandInput placeholder="輸入指令或快捷搜尋 (例如: 回測, tabby, T-Split, 底部Console)..." />
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
          <CommandItem onSelect={() => handleNav("/risk")} className="cursor-pointer">
            <ShieldCheck className="mr-2 size-4 text-primary" />
            <span>風控中心 (Risk & R1 Period)</span>
          </CommandItem>
          <CommandItem onSelect={() => handleNav("/market-intel")} className="cursor-pointer">
            <Globe2 className="mr-2 size-4 text-primary" />
            <span>市場情報 (Market Intel)</span>
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
          <CommandItem onSelect={() => handleSelectBot("tabby")} className="cursor-pointer">
            <Bot className="mr-2 size-4 text-emerald-400" />
            <span>tabby-btc-trend (BTC-USDT-SWAP · 1h)</span>
          </CommandItem>
          <CommandItem onSelect={() => handleSelectBot("calico")} className="cursor-pointer">
            <Bot className="mr-2 size-4 text-emerald-400" />
            <span>calico-eth-pullback (ETH-USDT-SWAP · 15m)</span>
          </CommandItem>
          <CommandItem onSelect={() => handleSelectBot("mochi")} className="cursor-pointer">
            <Bot className="mr-2 size-4 text-amber-400" />
            <span>mochi-sol-breakout (SOL-USDT-SWAP · 5m · P6更新待確認)</span>
          </CommandItem>
          <CommandItem onSelect={() => handleSelectBot("shiro")} className="cursor-pointer">
            <Bot className="mr-2 size-4 text-muted-foreground" />
            <span>shiro-arbitrage (BTC-USDT-SWAP · 1m · 已暫停)</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {/* 5. 風控處置 (Mock 模擬) */}
        <CommandGroup heading="風控與應急處置 (Risk & Safety)">
          <CommandItem
            onSelect={() => {
              setOpen(false);
              toast.info("已執行帳戶快速對帳檢查，本地與 OKX 完全一致 (Recon Pass)");
            }}
            className="cursor-pointer"
          >
            <RefreshCw className="mr-2 size-4 text-primary" />
            <span>執行帳戶與委託強制對帳 (Recon Audit)</span>
          </CommandItem>
          <CommandItem
            onSelect={() => {
              setOpen(false);
              toast.error("已觸發模擬緊急停止 (Kill-Switch Latch 已鎖存)");
            }}
            className="cursor-pointer text-destructive"
          >
            <AlertOctagon className="mr-2 size-4 text-destructive" />
            <span>觸發 Emergency Kill-Switch (模擬鎖存)</span>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
