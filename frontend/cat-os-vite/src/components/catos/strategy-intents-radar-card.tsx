import { useState } from "react";
import {
  Target,
  Zap,
} from "lucide-react";
import { CardHeaderTitle } from "./card-header-title";
import { cn } from "@/lib/utils";

export interface StrategyIntent {
  workerId: string;
  botName: string;
  strategyName: string;
  symbol: string;
  timeframe: string;
  currentPosition: string;
  targetIntent: string;
  intentDelta: string;
  intentAction: "增倉" | "減倉" | "平倉" | "維持" | "觀望";
  signalScore: number; // -100 to +100
  signalLabel: string;
  indicators: {
    upperDistance: string;
    upperLabel: string;
    midDistance: string;
    midLabel: string;
    lowerDistance: string;
    lowerLabel: string;
  };
  nextBarAction: string;
  ipcLatencyMs: number;
  computeTimeMs: number;
  lastUpdated: string;
  status: "INTENT_READY" | "HOLDING" | "STANDBY";
}

const DEFAULT_INTENTS: StrategyIntent[] = [
  {
    workerId: "worker_tabby_01",
    botName: "Tabby",
    strategyName: "獵貓動能 (Trend Following)",
    symbol: "BTC-USDT-SWAP",
    timeframe: "15m",
    currentPosition: "LONG 0.85 BTC",
    targetIntent: "LONG 1.10 BTC",
    intentDelta: "+0.25 BTC",
    intentAction: "增倉",
    signalScore: 82,
    signalLabel: "STRONG BUY 突破增倉",
    indicators: {
      upperDistance: "距 +1.14% ($62,850)",
      upperLabel: "唐奇安上軌 (DH)",
      midDistance: "站穩 +0.39% ($61,900)",
      midLabel: "EMA 20 成本線",
      lowerDistance: "防線 ($61,120)",
      lowerLabel: "唐奇安下軌 (DL)",
    },
    nextBarAction: "次根開盤市價委託 (Market Buy at Open)",
    ipcLatencyMs: 4,
    computeTimeMs: 8,
    lastUpdated: "11:15:00",
    status: "INTENT_READY",
  },
  {
    workerId: "worker_calico_02",
    botName: "Calico",
    strategyName: "夜視回歸 (Mean Reversion)",
    symbol: "ETH-USDT-SWAP",
    timeframe: "1H",
    currentPosition: "LONG 9.50 ETH",
    targetIntent: "LONG 9.50 ETH",
    intentDelta: "0.00 (HOLD)",
    intentAction: "維持",
    signalScore: 45,
    signalLabel: "NEUTRAL HOLD 區間持有",
    indicators: {
      upperDistance: "距 +1.32% ($3,420)",
      upperLabel: "布林上軌 (Upper)",
      midDistance: "貼近 ($3,350)",
      midLabel: "中軌回歸均線",
      lowerDistance: "加倉點 ($3,260)",
      lowerLabel: "布林下軌 (Lower)",
    },
    nextBarAction: "無意圖變更 (No-Op)",
    ipcLatencyMs: 6,
    computeTimeMs: 12,
    lastUpdated: "11:00:00",
    status: "HOLDING",
  },
  {
    workerId: "worker_mochi_03",
    botName: "Mochi",
    strategyName: "波動突破 (ATR Breakout)",
    symbol: "SOL-USDT-SWAP",
    timeframe: "15m",
    currentPosition: "LONG 95.00 SOL",
    targetIntent: "FLAT 0.00 SOL",
    intentDelta: "-95.00 SOL",
    intentAction: "平倉",
    signalScore: -68,
    signalLabel: "EXIT SIGNAL 停利出場",
    indicators: {
      upperDistance: "距 +1.11% ($154.50)",
      upperLabel: "目標停利線 (TP)",
      midDistance: "防守位 ($150.20)",
      midLabel: "動態移動止損 (TS)",
      lowerDistance: "支撐位 ($142.00)",
      lowerLabel: "波段支撐線",
    },
    nextBarAction: "次根開盤市價平倉 (Market Exit at Open)",
    ipcLatencyMs: 3,
    computeTimeMs: 5,
    lastUpdated: "11:15:00",
    status: "INTENT_READY",
  },
  {
    workerId: "worker_shiro_04",
    botName: "Shiro",
    strategyName: "宏觀避險 (Macro Hedging)",
    symbol: "BTC-USDT-SWAP",
    timeframe: "4H",
    currentPosition: "FLAT 0.00 BTC",
    targetIntent: "FLAT 0.00 BTC",
    intentDelta: "0.00 (STANDBY)",
    intentAction: "觀望",
    signalScore: 0,
    signalLabel: "IDLE 待命觀望",
    indicators: {
      upperDistance: "門檻 >= 8%",
      upperLabel: "避險觸發日損",
      midDistance: "正常 3.42%",
      midLabel: "當前日損水位",
      lowerDistance: "安全範圍",
      lowerLabel: "風控評級 SAFE",
    },
    nextBarAction: "無 (待命守護)",
    ipcLatencyMs: 5,
    computeTimeMs: 9,
    lastUpdated: "08:00:00",
    status: "STANDBY",
  },
];

interface StrategyIntentsRadarCardProps {
  className?: string;
}

export function StrategyIntentsRadarCard({ className }: StrategyIntentsRadarCardProps) {
  const [intents] = useState<StrategyIntent[]>(DEFAULT_INTENTS);
  const [selectedWorkerId, setSelectedWorkerId] = useState<string>("worker_tabby_01");

  const getActionBadge = (action: StrategyIntent["intentAction"]) => {
    switch (action) {
      case "增倉":
        return "text-emerald-400 bg-emerald-500/15 border-emerald-500/30";
      case "減倉":
        return "text-amber-400 bg-amber-500/15 border-amber-500/30";
      case "平倉":
        return "text-rose-400 bg-rose-500/15 border-rose-500/30";
      case "維持":
        return "text-primary bg-primary/15 border-primary/30";
      case "觀望":
      default:
        return "text-muted-foreground bg-muted-foreground/10 border-border/70";
    }
  };

  return (
    <div className={cn("flex flex-col h-full w-full select-none overflow-hidden bg-surface/40", className)}>
      {/* 1. Header 標題列 (Zero-Waste: 整合標題、IPC 狀態與即時微光) */}
      <div className="flex items-center justify-between px-3 py-2 bg-secondary/50 border-b border-border/80 shrink-0">
        <CardHeaderTitle
          cardId="strategy_intents"
          title="策略目標與訊號強度"
          subtext={
            <div className="flex items-center gap-1.5 ml-1">
              <span className="flex items-center gap-1 text-[9px] font-mono text-emerald-400 bg-emerald-400/10 px-1.5 py-0.2 rounded border border-emerald-400/25">
                <span className="size-1.5 rounded-full bg-emerald-400 animate-pulse" />
                IPC JSON v2
              </span>
              <span className="text-[9px] font-mono text-muted-foreground hidden sm:inline">
                4 Workers OK
              </span>
            </div>
          }
        />

        {/* 核心架構約束微徽章 */}
        <div className="flex items-center gap-1.5 text-[9.5px] font-mono text-muted-foreground">
          <span className="text-primary font-semibold hidden md:inline">Supervisor 獨佔交易</span>
          <span className="px-1.5 py-0.5 rounded bg-background/80 border border-border/70 text-foreground font-mono">
            純資料意圖
          </span>
        </div>
      </div>

      {/* 2. Worker 策略大腦意圖清單 */}
      <div className="flex-1 min-h-0 overflow-y-auto p-2.5 flex flex-col gap-2">
        {intents.map((item) => {
          const isSelected = item.workerId === selectedWorkerId;
          const isReady = item.status === "INTENT_READY";

          return (
            <div
              key={item.workerId}
              onClick={() => setSelectedWorkerId(item.workerId)}
              className={cn(
                "p-2.5 rounded-lg border transition-all cursor-pointer flex flex-col gap-2 group",
                isSelected
                  ? "bg-secondary/50 border-primary/50 shadow-xs"
                  : "bg-surface/70 border-border/70 hover:border-border/90 hover:bg-secondary/30"
              )}
            >
              {/* 上半部：Bot 資訊、標的、週期與目標意圖 */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div
                    className={cn(
                      "grid size-6 place-items-center rounded border shrink-0",
                      isReady
                        ? "bg-primary/15 border-primary/40 text-primary"
                        : "bg-surface-raised border-border/70 text-muted-foreground"
                    )}
                  >
                    <Target className="size-3" />
                  </div>

                  <div className="flex flex-col">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[11.5px] font-bold text-foreground tracking-tight">
                        {item.botName}
                      </span>
                      <span className="text-[9.5px] font-mono font-semibold text-primary">
                        {item.symbol}
                      </span>
                      <span className="text-[9px] font-mono px-1 rounded bg-background/80 text-muted-foreground border border-border/60">
                        {item.timeframe}
                      </span>
                    </div>
                    <span className="text-[9px] text-muted-foreground truncate">
                      {item.strategyName}
                    </span>
                  </div>
                </div>

                {/* 意圖方向與增減幅度 */}
                <div className="flex flex-col items-end text-right">
                  <div className="flex items-center gap-1.5">
                    <span
                      className={cn(
                        "text-[9.5px] font-mono font-bold px-1.5 py-0.2 rounded border",
                        getActionBadge(item.intentAction)
                      )}
                    >
                      {item.intentAction}: {item.intentDelta}
                    </span>
                  </div>
                  <span className="text-[9px] font-mono text-muted-foreground mt-0.5">
                    當前: {item.currentPosition.split(" ")[1]} → 目標: {item.targetIntent.split(" ")[1]}
                  </span>
                </div>
              </div>

              {/* 中半部：訊號強度長條與指標技術距離 */}
              <div className="p-2 rounded bg-background/60 border border-border/60 flex flex-col gap-1.5 font-mono text-[10px]">
                {/* 訊號強度進度條 */}
                <div className="flex items-center justify-between">
                  <span className="text-[9.5px] text-muted-foreground">
                    訊號強度: <span className="text-foreground font-semibold">{item.signalLabel}</span>
                  </span>
                  <span
                    className={cn(
                      "text-[9.5px] font-bold",
                      item.signalScore > 50
                        ? "text-emerald-400"
                        : item.signalScore < 0
                        ? "text-rose-400"
                        : "text-amber-400"
                    )}
                  >
                    {item.signalScore > 0 ? "+" : ""}
                    {item.signalScore}%
                  </span>
                </div>

                <div className="w-full bg-secondary h-1.5 rounded-full overflow-hidden border border-border/50">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all duration-500",
                      item.signalScore > 50
                        ? "bg-emerald-400"
                        : item.signalScore < 0
                        ? "bg-rose-400"
                        : "bg-primary"
                    )}
                    style={{ width: `${Math.max(10, Math.abs(item.signalScore))}%` }}
                  />
                </div>

                {/* 3 點指標技術距離 (唐奇安突破 / 均線共振) */}
                <div className="grid grid-cols-3 gap-1.5 pt-1 border-t border-border/50 text-[9px] text-muted-foreground">
                  <div className="flex flex-col">
                    <span className="truncate">{item.indicators.upperLabel}</span>
                    <span className="text-foreground font-semibold truncate">
                      {item.indicators.upperDistance}
                    </span>
                  </div>
                  <div className="flex flex-col text-center">
                    <span className="truncate">{item.indicators.midLabel}</span>
                    <span className="text-primary font-semibold truncate">
                      {item.indicators.midDistance}
                    </span>
                  </div>
                  <div className="flex flex-col text-right">
                    <span className="truncate">{item.indicators.lowerLabel}</span>
                    <span className="text-foreground font-semibold truncate">
                      {item.indicators.lowerDistance}
                    </span>
                  </div>
                </div>
              </div>

              {/* 下半部：次根委託動作預覽與 IPC 健全度 */}
              <div className="flex items-center justify-between text-[9px] font-mono text-muted-foreground">
                <div className="flex items-center gap-1 truncate">
                  <Zap className="size-2.5 text-primary shrink-0" />
                  <span className="text-foreground font-semibold truncate">
                    預備委託: {item.nextBarAction}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span>IPC {item.ipcLatencyMs}ms</span>
                  <span>·</span>
                  <span>運算 {item.computeTimeMs}ms</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
