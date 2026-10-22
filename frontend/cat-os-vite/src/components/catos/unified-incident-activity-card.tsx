import { useState, useMemo, useRef, useEffect } from 'react';
import { usePreviewStore, type PreviewEvent } from '@/preview/preview-store';
import { CardHeaderTitle } from './card-header-title';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  ShieldAlert,
  Lock,
  Crosshair,
  Flame,
  Gauge,
  ArrowUp,
  Sliders,
  Copy,
  RotateCcw,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatUsd, toneOf } from '@/lib/v0-engine';

export type EventCategoryFilter = 'OPEN' | 'ALL' | 'FILL' | 'ALERT' | 'SYSTEM';
export type PhotonRunnerMode = 'sync_bottom_up' | 'sync_collision' | 'snappy_terminal';

export interface ModeMeta {
  id: PhotonRunnerMode;
  name: string;
  badge: string;
  desc: string;
}


export interface TuningState {
  durationSec: number;        // 巡航速度 (1.0s ~ 30.0s)
  photonLength: number;       // 光束長度 (15px ~ 120px)
  photonWidth: number;        // 光束粗細 (0.5px ~ 4.0px)
  photonBrightness: number;   // 光子輝度 (10% ~ 100%)
  glowSpread: number;         // 漫射羽化 (8px ~ 36px)
  bloomIntensity: number;     // 節點光暈 (0% ~ 250%)
  glassBlur: number;          // 毛玻璃度 (0px ~ 32px)
  cardShimmer: number;        // 稜鏡共振 (0% ~ 100%)
  borderOpacity: number;      // 邊框濃淡 (0% ~ 100%，0% 為完全無框)
}

export const TUNING_PRESETS: Record<string, { name: string; tag: string; desc: string; values: TuningState }> = {
  stealth_ghost: {
    name: '幽靈冷灰',
    tag: '無框·暫定',
    desc: '完全無框純淨數據行 · 極低存在感 · 僅保留節點微弱提示 · 不干擾盤面',
    values: {
      durationSec: 12.0,
      photonLength: 42,
      photonWidth: 1.0,
      photonBrightness: 35,
      glowSpread: 12,
      bloomIntensity: 45,
      glassBlur: 0,
      cardShimmer: 0,
      borderOpacity: 0,
    },
  },
  default_ios: {
    name: 'iOS 霜晶極光',
    tag: '推薦',
    desc: '黃金比例平衡 · 溫潤晶透 · 零視覺疲勞',
    values: {
      durationSec: 8.0,
      photonLength: 56,
      photonWidth: 1.5,
      photonBrightness: 80,
      glowSpread: 16,
      bloomIntensity: 100,
      glassBlur: 16,
      cardShimmer: 60,
      borderOpacity: 35,
    },
  },
  deep_breathe: {
    name: '慢流深呼吸',
    tag: '慢速',
    desc: '16s 極慢巡航 · 超長柔焦漫射 · 深度平靜',
    values: {
      durationSec: 16.0,
      photonLength: 85,
      photonWidth: 1.25,
      photonBrightness: 65,
      glowSpread: 24,
      bloomIntensity: 140,
      glassBlur: 20,
      cardShimmer: 80,
      borderOpacity: 45,
    },
  },
  quantum_needle: {
    name: '量子超纖針',
    tag: '敏捷',
    desc: '3.2s 敏捷滑行 · 26px 極短纖細 · 乾淨俐落',
    values: {
      durationSec: 3.2,
      photonLength: 26,
      photonWidth: 0.75,
      photonBrightness: 95,
      glowSpread: 10,
      bloomIntensity: 70,
      glassBlur: 12,
      cardShimmer: 40,
      borderOpacity: 20,
    },
  },
  high_energy: {
    name: '高能雷射',
    tag: '爆光',
    desc: '粗線條高飽和 · 強烈鏡頭 Bloom 爆光 · 告警首選',
    values: {
      durationSec: 5.0,
      photonLength: 95,
      photonWidth: 2.75,
      photonBrightness: 100,
      glowSpread: 28,
      bloomIntensity: 220,
      glassBlur: 24,
      cardShimmer: 100,
      borderOpacity: 65,
    },
  },
};

export const RUNNER_MODES: ModeMeta[] = [
  {
    id: 'sync_bottom_up',
    name: '【時序湧動】由下往上幾何對齊 (推薦 · 歷史至最新)',
    badge: '時序因果',
    desc: '時序湧動 ➜ 歷史事件 (底) 湧向即時狀態 (頂)，光子撫過節點瞬間精準觸發白金 Bloom',
  },
  {
    id: 'sync_collision',
    name: '【實時碰撞】由下往上 rAF 微碰撞偵測 (毫秒級零誤差)',
    badge: '零誤差',
    desc: '實時碰撞 ➜ rAF 每幀監測光子物理座標，碰上節點即時觸發呼吸，展開收合 100% 吻合',
  },
  {
    id: 'snappy_terminal',
    name: '【純靜態】Bloomberg 極速終端 (0 動態 · 純數據)',
    badge: '純靜態',
    desc: '純靜態 ➜ 0 動態干擾，1px 靜態磨砂導軌，純數據聚焦',
  },
];

interface UnifiedIncidentActivityCardProps {
  className?: string;
}

export function UnifiedIncidentActivityCard({ className }: UnifiedIncidentActivityCardProps) {
  const { events, openInspector, triggerHighlight, highlightTarget } = usePreviewStore();

  // 預設展開最新的未解除告警 (Calico UNKNOWN)
  const [expandedId, setExpandedId] = useState<string | null>('evt_unknown_calico');
  const [category, setCategory] = useState<EventCategoryFilter>('ALL');

  // 預設採用由下往上時序湧動對齊
  const [runnerMode, setRunnerMode] = useState<PhotonRunnerMode>('sync_bottom_up');

  // 微調控制狀態 (9 大核心參數，預設幽靈冷灰·無框)
  const [tuning, setTuning] = useState<TuningState>(TUNING_PRESETS.stealth_ghost.values);
  const [activePreset, setActivePreset] = useState<string>('stealth_ghost');
  const [isCopied, setIsCopied] = useState<boolean>(false);
  const [isTuningOpen, setIsTuningOpen] = useState<boolean>(true);

  const updateTuning = <K extends keyof TuningState>(key: K, value: TuningState[K]) => {
    setTuning((prev) => ({ ...prev, [key]: value }));
    setActivePreset('custom');
  };

  const applyPreset = (presetKey: string) => {
    const p = TUNING_PRESETS[presetKey];
    if (p) {
      setTuning(p.values);
      setActivePreset(presetKey);
    }
  };

  const copyParams = () => {
    const json = JSON.stringify(tuning, null, 2);
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(json);
    }
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  // DOM 容器與節點座標引用
  const containerRef = useRef<HTMLDivElement>(null);
  const nodeRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  // 方案 A/時序湧動：量測各節點真實 offsetTop 相對於底部的延遲 (秒)
  const [bottomUpDelays, setBottomUpDelays] = useState<Record<string, number>>({});

  // 方案 B：碰撞即時狀態
  const [hitTimestamps, setHitTimestamps] = useState<Record<string, number>>({});
  const [photonBottomPercent, setPhotonBottomPercent] = useState<number>(0);

  // 統計各類別事件筆數
  const stats = useMemo(() => {
    const open = events.filter((e) => e.resolution === 'open' && (e.category === 'ALERT' || e.severity === 'WARN')).length;
    const fills = events.filter((e) => e.category === 'FILL').length;
    const alerts = events.filter((e) => e.category === 'ALERT').length;
    const system = events.filter((e) => e.category === 'SYSTEM').length;
    return { open, fills, alerts, system, total: events.length };
  }, [events]);

  // 篩選後事件列表 (未解除優先置頂，保持時間序列)
  const filteredEvents = useMemo(() => {
    const list = events.filter((e) => {
      if (category === 'ALL') return true;
      if (category === 'OPEN') return e.resolution === 'open' && (e.category === 'ALERT' || e.severity === 'WARN');
      return e.category === category;
    });

    return [...list].sort((a, b) => {
      const aOpen = Number(a.resolution === 'open' && (a.category === 'ALERT' || a.severity === 'WARN'));
      const bOpen = Number(b.resolution === 'open' && (b.category === 'ALERT' || b.severity === 'WARN'));
      return bOpen - aOpen;
    });
  }, [events, category]);

  // 由下往上物理幾何計算：當前節點距離容器底部的真實像素距離比率
  useEffect(() => {
    if (!containerRef.current) return;
    const totalH = containerRef.current.scrollHeight;
    if (totalH <= 0) return;

    const newDelays: Record<string, number> = {};
    filteredEvents.forEach((ev) => {
      const el = nodeRefs.current.get(ev.id);
      if (el) {
        const nodeY = el.offsetTop + 8;
        // 由下往上：離底部的距離 = totalH - nodeY
        const distFromBottom = Math.max(0, totalH - nodeY);
        const ratio = Math.max(0, Math.min(1, distFromBottom / totalH));
        newDelays[ev.id] = Number((ratio * tuning.durationSec).toFixed(3));
      }
    });
    setBottomUpDelays(newDelays);
  }, [filteredEvents, expandedId, tuning.durationSec]);

  // 方案 B：由下往上真實碰撞偵測循環 (Bottom-Up rAF)
  useEffect(() => {
    if (runnerMode !== 'sync_collision') return;

    let rafId: number;
    let startTime = performance.now();

    const loop = (now: number) => {
      const elapsed = (now - startTime) / 1000;
      const progress = (elapsed % tuning.durationSec) / tuning.durationSec; // 0 ~ 1 由下往上
      setPhotonBottomPercent(progress * 100);

      if (containerRef.current) {
        const totalH = containerRef.current.scrollHeight;
        // 光子當前距離頂部的 Y 座標 (由 bottom=0% 往上移動到 bottom=100%)
        const currentPhotonY = totalH - (progress * totalH);

        filteredEvents.forEach((ev) => {
          const el = nodeRefs.current.get(ev.id);
          if (el) {
            const nodeY = el.offsetTop + 8;
            const dist = Math.abs(currentPhotonY - nodeY);

            // 當光子進入節點 16px 碰撞半徑，且間隔大於 500ms
            if (dist < 16) {
              setHitTimestamps((prev) => {
                const lastHit = prev[ev.id] || 0;
                if (now - lastHit > 500) {
                  return { ...prev, [ev.id]: now };
                }
                return prev;
              });
            }
          }
        });
      }

      rafId = requestAnimationFrame(loop);
    };

    rafId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafId);
  }, [runnerMode, tuning.durationSec, filteredEvents, expandedId]);

  const toggleIncident = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  // 小圓點與標籤樣式：所有圓點核心絕對等大 (8px)
  const getBadgeMeta = (ev: PreviewEvent) => {
    const isWarn = ev.severity === 'WARN' || ev.category === 'ALERT';
    const isTrade = ev.category === 'FILL' || ev.severity === 'TRADE';
    const isOpen = ev.resolution === 'open' && isWarn;
    const isOk = ev.severity === 'OK' || ev.resolution === 'resolved';

    if (isOpen) {
      return {
        label: 'WARN',
        badgeClass: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
        coreClass: 'bg-amber-400 ring-2 ring-background',
        isSonar: true,
      };
    }
    if (isWarn && !isOpen) {
      return {
        label: 'WARN',
        badgeClass: 'bg-amber-500/10 text-amber-400/70 border-amber-500/30',
        coreClass: 'bg-amber-500/70 shadow-[0_0_4px_rgba(245,158,11,0.4)] ring-2 ring-background',
        isSonar: false,
      };
    }
    if (isTrade) {
      return {
        label: ev.action || '成交',
        badgeClass: ev.action?.includes('空')
          ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
          : 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
        coreClass: 'bg-emerald-400 shadow-[0_0_6px_rgba(16,185,129,0.6)] ring-2 ring-background',
        isSonar: false,
      };
    }
    if (isOk) {
      return {
        label: 'OK',
        badgeClass: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
        coreClass: 'bg-emerald-400 shadow-[0_0_6px_rgba(16,185,129,0.5)] ring-2 ring-background',
        isSonar: false,
      };
    }
    return {
      label: 'INFO',
      badgeClass: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
      coreClass: 'bg-sky-400 shadow-[0_0_6px_rgba(56,189,248,0.6)] ring-2 ring-background',
      isSonar: false,
    };
  };

  return (
    <div className={cn('flex flex-col h-full w-full select-none overflow-hidden bg-surface/40 font-mono', className)}>
      {/* 1. Header 區域：整合卡片標題 + 異常膠囊 + 速度滑桿 (1~30s) + 方案切換 */}
      <div className="flex flex-wrap items-center justify-between px-3 py-2 bg-secondary/50 border-b border-border/80 shrink-0 gap-2">
        <div className="flex items-center gap-2">
          <CardHeaderTitle
            cardId="activity_deck"
            title="風險警報與交易日誌"
            subtext=""
          />
          {stats.open > 0 ? (
            <span className="flex items-center gap-1 text-[9px] px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse font-semibold">
              <ShieldAlert className="size-2.5" />
              <span>{stats.open} 異常</span>
            </span>
          ) : (
            <span className="flex items-center gap-1 text-[9px] px-1.5 py-0.2 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-semibold">
              <CheckCircle2 className="size-2.5" />
              <span>系統正常</span>
            </span>
          )}
        </div>

        {/* 右側：模式選擇 + 微調控制板開關 */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* 微調控制板展開開關 */}
          <button
            type="button"
            onClick={() => setIsTuningOpen(!isTuningOpen)}
            className={cn(
              "flex items-center gap-1 rounded px-2 py-0.5 text-[9px] border transition-colors cursor-pointer shadow-2xs font-medium",
              isTuningOpen
                ? "bg-primary/20 text-primary border-primary/50 font-bold"
                : "bg-background/90 text-muted-foreground hover:text-foreground border-border/80"
            )}
            title="開啟/收合微調控制板 (8大滑桿 + 5大風格預設)"
          >
            <Sliders className="size-2.5 text-primary" />
            <span>視覺微調板 ({activePreset === 'custom' ? '自訂參數' : TUNING_PRESETS[activePreset]?.name || '自訂'})</span>
          </button>

          {/* 方案選擇選單 */}
          <div className="flex items-center gap-1 bg-background/90 border border-primary/40 rounded px-1.5 py-0.5 text-[9px] shadow-2xs">
            <span className="text-primary font-bold mr-0.5 flex items-center gap-0.5">
              <Flame className="size-2.5" />
              模式：
            </span>
            <select
              value={runnerMode}
              onChange={(e) => setRunnerMode(e.target.value as PhotonRunnerMode)}
              className="bg-secondary/90 hover:bg-secondary text-foreground border border-border/80 rounded px-1.5 py-0.5 text-[9px] font-mono cursor-pointer outline-none focus:border-primary transition-colors font-medium"
              title="選擇同步模式"
            >
              {RUNNER_MODES.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} [{m.badge}]
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* 2. 微調實驗控制板 (8 大滑桿 + 5 大風格預設 + 參數複製) */}
      {isTuningOpen && (
        <div className="bg-secondary/40 border-b border-border/70 px-3 py-2 text-[9px] flex flex-col gap-2 shrink-0">
          {/* 上排：風格預設快捷鍵 + 複製 + 重置 */}
          <div className="flex items-center justify-between gap-1.5 flex-wrap">
            <div className="flex items-center gap-1 flex-wrap">
              <span className="text-muted-foreground flex items-center gap-1 font-bold mr-1">
                <Sparkles className="size-2.5 text-primary" />
                預設：
              </span>
              {Object.entries(TUNING_PRESETS).map(([key, p]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => applyPreset(key)}
                  className={cn(
                    "px-1.5 py-0.5 rounded text-[8.5px] font-medium border transition-colors cursor-pointer",
                    activePreset === key
                      ? "bg-primary/25 text-primary border-primary/50 font-bold shadow-2xs"
                      : "bg-background/80 text-muted-foreground hover:text-foreground border-border/70"
                  )}
                  title={p.desc}
                >
                  {p.name} [{p.tag}]
                </button>
              ))}
            </div>

            <div className="flex items-center gap-1.5">
              {/* 一鍵無框/有框切換 */}
              <button
                type="button"
                onClick={() => updateTuning('borderOpacity', tuning.borderOpacity === 0 ? 35 : 0)}
                className={cn(
                  "px-2 py-0.5 rounded text-[8.5px] font-medium border transition-colors cursor-pointer flex items-center gap-1 shadow-2xs",
                  tuning.borderOpacity === 0
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40 font-bold"
                    : "bg-background/80 text-muted-foreground hover:text-foreground border-border/70"
                )}
                title="點擊切換無框或卡片框"
              >
                <span>{tuning.borderOpacity === 0 ? '✓ 無框模式' : '卡片框'}</span>
              </button>
              <button
                type="button"
                onClick={copyParams}
                className="px-2 py-0.5 rounded text-[8.5px] bg-background/80 hover:bg-background text-zinc-300 hover:text-zinc-100 border border-border/70 flex items-center gap-1 cursor-pointer transition-colors shadow-2xs"
                title="複製目前數值 JSON"
              >
                <Copy className="size-2.5 text-primary" />
                <span>{isCopied ? '已複製參數!' : '複製目前參數'}</span>
              </button>
              <button
                type="button"
                onClick={() => applyPreset('stealth_ghost')}
                className="px-2 py-0.5 rounded text-[8.5px] bg-background/80 hover:bg-background text-zinc-400 hover:text-zinc-200 border border-border/70 flex items-center gap-1 cursor-pointer transition-colors"
                title="重置為幽靈冷灰 (無框)"
              >
                <RotateCcw className="size-2.5" />
                <span>重置</span>
              </button>
            </div>
          </div>

          {/* 下排：9 個微調滑桿矩陣 */}
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 lg:grid-cols-9 gap-1.5">
            {/* 1. 巡航速度 */}
            <div className="flex flex-col gap-0.5 bg-background/90 border border-border/70 rounded p-1 shadow-2xs">
              <div className="flex items-center justify-between text-[8px] text-muted-foreground">
                <span className="font-medium flex items-center gap-0.5">
                  <Gauge className="size-2 text-primary shrink-0" />
                  <span>巡航速度</span>
                </span>
                <span className="text-primary font-bold font-mono flex items-center gap-0.5">
                  <ArrowUp className="size-2 text-primary/80" />
                  <span>{tuning.durationSec.toFixed(1)}s</span>
                </span>
              </div>
              <input
                type="range"
                min="1.0"
                max="30.0"
                step="0.5"
                value={tuning.durationSec}
                onChange={(e) => updateTuning('durationSec', parseFloat(e.target.value))}
                className="w-full h-1 bg-secondary rounded appearance-none cursor-pointer accent-primary"
                title="調整由下往上光子週期 (1.0s ~ 30.0s)"
              />
            </div>

            {/* 2. 光束長度 */}
            <div className="flex flex-col gap-0.5 bg-background/90 border border-border/70 rounded p-1 shadow-2xs">
              <div className="flex items-center justify-between text-[8px] text-muted-foreground">
                <span className="font-medium">光束長度</span>
                <span className="text-primary font-bold font-mono">{tuning.photonLength}px</span>
              </div>
              <input
                type="range"
                min="15"
                max="120"
                step="5"
                value={tuning.photonLength}
                onChange={(e) => updateTuning('photonLength', parseInt(e.target.value))}
                className="w-full h-1 bg-secondary rounded appearance-none cursor-pointer accent-primary"
                title="光子本體與拖尾長度 (15px ~ 120px)"
              />
            </div>

            {/* 3. 光束粗細 */}
            <div className="flex flex-col gap-0.5 bg-background/90 border border-border/70 rounded p-1 shadow-2xs">
              <div className="flex items-center justify-between text-[8px] text-muted-foreground">
                <span className="font-medium">光束粗細</span>
                <span className="text-primary font-bold font-mono">{tuning.photonWidth.toFixed(2)}px</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="4.0"
                step="0.25"
                value={tuning.photonWidth}
                onChange={(e) => updateTuning('photonWidth', parseFloat(e.target.value))}
                className="w-full h-1 bg-secondary rounded appearance-none cursor-pointer accent-primary"
                title="中心核心光絲粗細 (0.5px ~ 4.0px)"
              />
            </div>

            {/* 4. 光子輝度 */}
            <div className="flex flex-col gap-0.5 bg-background/90 border border-border/70 rounded p-1 shadow-2xs">
              <div className="flex items-center justify-between text-[8px] text-muted-foreground">
                <span className="font-medium">光子輝度</span>
                <span className="text-primary font-bold font-mono">{tuning.photonBrightness}%</span>
              </div>
              <input
                type="range"
                min="10"
                max="100"
                step="5"
                value={tuning.photonBrightness}
                onChange={(e) => updateTuning('photonBrightness', parseInt(e.target.value))}
                className="w-full h-1 bg-secondary rounded appearance-none cursor-pointer accent-primary"
                title="光子整體不透明度與發光強度 (10% ~ 100%)"
              />
            </div>

            {/* 5. 漫射羽化 */}
            <div className="flex flex-col gap-0.5 bg-background/90 border border-border/70 rounded p-1 shadow-2xs">
              <div className="flex items-center justify-between text-[8px] text-muted-foreground">
                <span className="font-medium">漫射羽化</span>
                <span className="text-primary font-bold font-mono">{tuning.glowSpread}px</span>
              </div>
              <input
                type="range"
                min="8"
                max="36"
                step="2"
                value={tuning.glowSpread}
                onChange={(e) => updateTuning('glowSpread', parseInt(e.target.value))}
                className="w-full h-1 bg-secondary rounded appearance-none cursor-pointer accent-primary"
                title="兩側高斯磨砂柔光暈染半徑 (8px ~ 36px)"
              />
            </div>

            {/* 6. 節點光暈 */}
            <div className="flex flex-col gap-0.5 bg-background/90 border border-border/70 rounded p-1 shadow-2xs">
              <div className="flex items-center justify-between text-[8px] text-muted-foreground">
                <span className="font-medium">節點光暈</span>
                <span className="text-primary font-bold font-mono">{tuning.bloomIntensity}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="250"
                step="10"
                value={tuning.bloomIntensity}
                onChange={(e) => updateTuning('bloomIntensity', parseInt(e.target.value))}
                className="w-full h-1 bg-secondary rounded appearance-none cursor-pointer accent-primary"
                title="節點被穿透時的白金 Bloom 爆光強度 (0% ~ 250%)"
              />
            </div>

            {/* 7. 毛玻璃度 */}
            <div className="flex flex-col gap-0.5 bg-background/90 border border-border/70 rounded p-1 shadow-2xs">
              <div className="flex items-center justify-between text-[8px] text-muted-foreground">
                <span className="font-medium">毛玻璃度</span>
                <span className="text-primary font-bold font-mono">{tuning.glassBlur}px</span>
              </div>
              <input
                type="range"
                min="0"
                max="32"
                step="2"
                value={tuning.glassBlur}
                onChange={(e) => updateTuning('glassBlur', parseInt(e.target.value))}
                className="w-full h-1 bg-secondary rounded appearance-none cursor-pointer accent-primary"
                title="卡片背景磨砂模糊半徑 (0px ~ 32px)"
              />
            </div>

            {/* 8. 稜鏡共振 */}
            <div className="flex flex-col gap-0.5 bg-background/90 border border-border/70 rounded p-1 shadow-2xs">
              <div className="flex items-center justify-between text-[8px] text-muted-foreground">
                <span className="font-medium">稜鏡共振</span>
                <span className="text-primary font-bold font-mono">{tuning.cardShimmer}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="10"
                value={tuning.cardShimmer}
                onChange={(e) => updateTuning('cardShimmer', parseInt(e.target.value))}
                className="w-full h-1 bg-secondary rounded appearance-none cursor-pointer accent-primary"
                title="光子經過時卡片邊框的 1px 晶透微閃 (0% ~ 100%)"
              />
            </div>

            {/* 9. 邊框濃淡 (0% 為完全無框) */}
            <div className="flex flex-col gap-0.5 bg-background/90 border border-border/70 rounded p-1 shadow-2xs">
              <div className="flex items-center justify-between text-[8px] text-muted-foreground">
                <span className="font-medium">邊框濃淡</span>
                <span className={cn("font-bold font-mono", tuning.borderOpacity === 0 ? "text-emerald-400 font-semibold" : "text-primary")}>
                  {tuning.borderOpacity === 0 ? '無框(0%)' : `${tuning.borderOpacity}%`}
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={tuning.borderOpacity}
                onChange={(e) => updateTuning('borderOpacity', parseInt(e.target.value))}
                className="w-full h-1 bg-secondary rounded appearance-none cursor-pointer accent-primary"
                title="卡片外框描邊透明度 (0% 為完全無框純淨數據行)"
              />
            </div>
          </div>
        </div>
      )}

      {/* 2. 類別過濾工具列 */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-secondary/30 border-b border-border/60 text-[9.5px] shrink-0">
        <div className="flex items-center gap-1">
          <span className="text-muted-foreground mr-1">分類：</span>
          {[
            { id: 'OPEN', label: `未解除 (${stats.open})`, isAlert: stats.open > 0 },
            { id: 'ALL', label: `全部 (${stats.total})` },
            { id: 'FILL', label: `成交流 (${stats.fills})` },
            { id: 'ALERT', label: `風控警報 (${stats.alerts})` },
            { id: 'SYSTEM', label: `系統事件 (${stats.system})` },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setCategory(tab.id as EventCategoryFilter)}
              className={cn(
                'px-1.5 py-0.2 rounded transition-colors cursor-pointer font-medium',
                category === tab.id
                  ? 'bg-secondary text-primary font-bold border border-border shadow-xs'
                  : tab.isAlert
                  ? 'text-amber-400 hover:text-amber-300 font-semibold'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <span className="text-[9px] text-muted-foreground hidden md:inline truncate max-w-[55%]">
          {RUNNER_MODES.find((m) => m.id === runnerMode)?.desc}
        </span>
      </div>

      {/* 3. 核心時間軸內容區 (使用 key 保證每次速度變更時重置相位，零相位漂移) */}
      <div
        key={`timeline-${tuning.durationSec}-${expandedId}-${runnerMode}`}
        ref={containerRef}
        className="flex-1 min-h-0 overflow-y-auto p-3 pr-2 relative"
        style={{
          '--photon-duration': `${tuning.durationSec}s`,
          '--photon-length': `${tuning.photonLength}px`,
          '--photon-width': `${tuning.photonWidth}px`,
          '--photon-opacity': `${(tuning.photonBrightness / 100).toFixed(2)}`,
          '--bloom-intensity': `${(tuning.bloomIntensity / 100).toFixed(2)}`,
          '--glass-blur': `${tuning.glassBlur}px`,
          '--card-shimmer-opacity': `${(tuning.cardShimmer / 100).toFixed(2)}`,
        } as React.CSSProperties}
      >
        {filteredEvents.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-muted-foreground text-xs gap-1">
            <CheckCircle2 className="size-6 text-emerald-400/80 mb-1" />
            <span className="font-semibold text-foreground text-[11px]">無符合條件之事件</span>
            <span className="text-[10px]">系統平穩運行中，所有風控指標正常</span>
          </div>
        ) : (
          <div className="relative pl-3 space-y-2.5">
            {/* 導軌系統：由下往上向上湧動 */}
            <div className="absolute left-[20px] -translate-x-1/2 top-2 bottom-2 w-[20px] pointer-events-none z-0 overflow-hidden">
              {/* 1. 底層 1px 磨砂暗色導軌線 */}
              <div className="absolute left-[10px] -translate-x-1/2 top-0 bottom-0 w-[1px] bg-white/[0.10]" />

              {/* 2. 由下往上光子漫射流束 */}
              {runnerMode === 'sync_bottom_up' && (
                /* 方案 A：等速向上光子 (時序因果流) */
                <div
                  className="absolute left-[2px] bottom-0 w-[20px]"
                  style={{ animation: `photon-travel-upward ${tuning.durationSec}s linear infinite` }}
                >
                  <div
                    className="photon-aurora-glow-up"
                    style={{
                      width: `${tuning.glowSpread}px`,
                      height: `${Math.round(tuning.photonLength * 1.25)}px`,
                      opacity: tuning.photonBrightness / 100,
                      filter: `blur(${Math.max(2, Math.round(tuning.glowSpread * 0.28))}px)`,
                    }}
                  />
                  <div
                    className="photon-aurora-core-up"
                    style={{
                      width: `${tuning.photonWidth}px`,
                      height: `${tuning.photonLength}px`,
                      opacity: Math.min(1, (tuning.photonBrightness / 100) * 1.2),
                      boxShadow: `0 0 ${Math.round(8 * (tuning.bloomIntensity / 100))}px ${Math.round(1 * (tuning.bloomIntensity / 100))}px rgba(251, 191, 36, 0.6)`,
                    }}
                  />
                </div>
              )}

              {runnerMode === 'sync_collision' && (
                /* 方案 B：由下往上實時碰撞驅動 */
                <div
                  className="absolute left-[2px] w-[20px] translate-y-1/2 transition-none"
                  style={{ bottom: `${photonBottomPercent}%` }}
                >
                  <div
                    className="photon-aurora-glow-up !top-0"
                    style={{
                      width: `${tuning.glowSpread}px`,
                      height: `${Math.round(tuning.photonLength * 1.25)}px`,
                      opacity: tuning.photonBrightness / 100,
                      filter: `blur(${Math.max(2, Math.round(tuning.glowSpread * 0.28))}px)`,
                    }}
                  />
                  <div
                    className="photon-aurora-core-up !top-0"
                    style={{
                      width: `${tuning.photonWidth}px`,
                      height: `${tuning.photonLength}px`,
                      opacity: Math.min(1, (tuning.photonBrightness / 100) * 1.2),
                      boxShadow: `0 0 ${Math.round(8 * (tuning.bloomIntensity / 100))}px ${Math.round(1 * (tuning.bloomIntensity / 100))}px rgba(251, 191, 36, 0.6)`,
                    }}
                  />
                </div>
              )}

              {/* snappy_terminal：純靜態，無動態光束 */}
            </div>

            {filteredEvents.map((ev) => {
              const isExp = expandedId === ev.id;
              const meta = getBadgeMeta(ev);
              const isFill = ev.category === 'FILL';
              const isWarn = ev.severity === 'WARN' || ev.category === 'ALERT';
              const isOk = ev.severity === 'OK' || ev.resolution === 'resolved';
              const isOpen = ev.resolution === 'open' && isWarn;
              const isHighlighted = highlightTarget.type === 'event' && highlightTarget.id === ev.id;

              // 方案 B：檢查碰撞時間戳 (500ms 內)
              const lastHit = hitTimestamps[ev.id] || 0;
              const isCollisionActive = runnerMode === 'sync_collision' && (performance.now() - lastHit < 500);

              // 方案 A：取得該節點離底部的真實幾何延遲 (秒)
              const bottomDelay = bottomUpDelays[ev.id] ?? 0;

              return (
                <div
                  key={ev.id}
                  ref={(el) => {
                    if (el) nodeRefs.current.set(ev.id, el);
                    else nodeRefs.current.delete(ev.id);
                  }}
                  className="relative flex items-start gap-2.5 group"
                >
                  {/* 時間軸節點小圓點容器 */}
                  <div className="relative mt-1 shrink-0 z-10 flex items-center justify-center size-4 pointer-events-none">
                    {/* 由下往上光子穿透之次表面柔霧微光環 */}
                    {runnerMode === 'sync_bottom_up' && (
                      <span
                        className={cn(
                          "absolute inline-flex size-2.5 rounded-full pointer-events-none",
                          isWarn ? "bg-amber-400/80" : isFill || isOk ? "bg-emerald-400/80" : "bg-sky-400/80"
                        )}
                        style={{
                          animation: `optical-halation-fade ${tuning.durationSec}s cubic-bezier(0.16, 1, 0.3, 1) infinite`,
                          animationDelay: `${bottomDelay}s`,
                          opacity: tuning.bloomIntensity === 0 ? 0 : undefined,
                        }}
                      />
                    )}

                    {runnerMode === 'sync_collision' && isCollisionActive && (
                      <span
                        className={cn(
                          "absolute inline-flex size-3 rounded-full optical-halation-active pointer-events-none",
                          isWarn ? "bg-amber-400/80" : isFill || isOk ? "bg-emerald-400/80" : "bg-sky-400/80"
                        )}
                      />
                    )}

                    {/* 實心核心點：鎖死 8px 零變形，由下往上光子經過時產生白金光學 Bloom */}
                    <span
                      className={cn(
                        'relative inline-flex size-2 rounded-full transition-all duration-150',
                        meta.coreClass,
                        isOpen && 'crystal-breathe-subtle',
                        runnerMode === 'sync_collision' && isCollisionActive && (
                          isWarn
                            ? 'crystal-bloom-amber-active'
                            : isFill || isOk
                            ? 'crystal-bloom-emerald-active'
                            : 'crystal-bloom-sky-active'
                        )
                      )}
                      style={
                        runnerMode === 'sync_bottom_up'
                          ? {
                              animation: `${
                                isWarn
                                  ? 'crystal-optical-bloom-amber'
                                  : isFill || isOk
                                  ? 'crystal-optical-bloom-emerald'
                                  : 'crystal-optical-bloom-sky'
                              } ${tuning.durationSec}s cubic-bezier(0.16, 1, 0.3, 1) infinite`,
                              animationDelay: `${bottomDelay}s`,
                              filter: tuning.bloomIntensity > 100 ? `drop-shadow(0 0 ${(tuning.bloomIntensity - 100) / 25}px rgba(255,255,255,0.45))` : undefined,
                            }
                          : undefined
                      }
                    />
                  </div>

                  {/* 事件行容器：支援「無框純淨數據流」或「iOS 半透明磨砂玻璃卡片」 */}
                  <div
                    onClick={() => toggleIncident(ev.id)}
                    className={cn(
                      'flex-1 min-w-0 transition-all duration-150 cursor-pointer p-2.5',
                      tuning.borderOpacity === 0
                        ? cn(
                            'rounded-md',
                            isOpen && !isExp
                              ? 'bg-amber-500/[0.025] hover:bg-amber-500/[0.05]'
                              : isExp
                              ? 'bg-white/[0.04]'
                              : 'hover:bg-white/[0.035]'
                          )
                        : cn(
                            'rounded-lg',
                            isOpen && !isExp
                              ? 'ios-glass-card-warn'
                              : isExp
                              ? 'ios-glass-card-active'
                              : 'ios-glass-card'
                          ),
                      isHighlighted && 'ring-1 ring-primary bg-primary/10 shadow-[0_0_16px_rgba(232,180,94,0.35)]',
                      runnerMode === 'sync_collision' && isCollisionActive && 'card-hit-shimmer-active'
                    )}
                    style={{
                      ...(runnerMode === 'sync_bottom_up' && tuning.cardShimmer > 0 && tuning.borderOpacity > 0
                        ? {
                            animation: `card-prism-shimmer ${tuning.durationSec}s ease-out infinite`,
                            animationDelay: `${bottomDelay}s`,
                          }
                        : {}),
                      backdropFilter: tuning.borderOpacity > 0 && tuning.glassBlur > 0 ? `blur(${tuning.glassBlur}px) saturate(180%)` : undefined,
                      WebkitBackdropFilter: tuning.borderOpacity > 0 && tuning.glassBlur > 0 ? `blur(${tuning.glassBlur}px) saturate(180%)` : undefined,
                      ...(tuning.borderOpacity > 0
                        ? {
                            borderColor: `rgba(255, 255, 255, ${(tuning.borderOpacity / 100 * 0.16).toFixed(3)})`,
                            boxShadow: `inset 0 1px 0 0 rgba(255, 255, 255, ${(tuning.borderOpacity / 100 * 0.14).toFixed(3)})`,
                          }
                        : {
                            border: 'none',
                            borderWidth: 0,
                            borderColor: 'transparent',
                            boxShadow: 'none',
                          }),
                    }}
                  >
                    {/* 表頭一行：時間 + 標籤 + 關聯 Bot + 標題 + 右側 PnL/狀態 + 箭頭 */}
                    <div className="flex items-center justify-between gap-1.5 text-[10px]">
                      <div className="flex items-center gap-1.5 min-w-0">
                        {/* 時間戳 */}
                        <span className="text-zinc-400 text-[9px] shrink-0 font-medium">{ev.time}</span>

                        {/* 類型 Badge */}
                        <span className={cn('px-1 py-0.2 rounded text-[8px] font-bold border shrink-0', meta.badgeClass)}>
                          {meta.label}
                        </span>

                        {/* 關聯 Bot 或來源 */}
                        {(ev.botName || ev.source) && (
                          <span className="text-muted-foreground text-[9px] shrink-0 hidden sm:inline">
                            [{ev.botName || ev.source}]
                          </span>
                        )}

                        {/* 事件主標題 */}
                        <span className="font-semibold text-foreground text-[10.5px] truncate leading-tight">
                          {isFill && ev.symbol ? `${ev.symbol} · ${ev.qty} @ $${ev.price}` : ev.title}
                        </span>
                      </div>

                      {/* 右側：PnL 盈虧 / 狀態標籤 / 展開箭頭 */}
                      <div className="flex items-center gap-2 shrink-0">
                        {isFill ? (
                          ev.pnl && ev.pnl !== 0 ? (
                            <span className={cn('text-[10.5px] font-bold', toneOf(ev.pnl))}>
                              {formatUsd(ev.pnl, true)}
                            </span>
                          ) : (
                            <span className="text-[9px] text-muted-foreground">開倉撮合</span>
                          )
                        ) : isOpen ? (
                          <span className="text-[8.5px] font-bold text-amber-400 bg-amber-400/10 px-1.5 py-0.2 rounded border border-amber-400/30 animate-pulse">
                            未解除
                          </span>
                        ) : ev.resolution === 'resolved' ? (
                          <span className="text-[8.5px] text-muted-foreground/70 hidden sm:inline">已解除</span>
                        ) : null}

                        <button
                          type="button"
                          className="text-muted-foreground group-hover:text-foreground shrink-0 transition-transform duration-200"
                          aria-label={isExp ? '收合' : '展開'}
                        >
                          {isExp ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
                        </button>
                      </div>
                    </div>

                    {/* 展開詳情面板 */}
                    {isExp && (
                      <div
                        onClick={(e) => e.stopPropagation()}
                        className="mt-2 pt-2 border-t border-white/[0.08] text-[9.5px] space-y-1.5 text-zinc-300 snap-accordion-enter"
                      >
                        {/* 詳細說明 */}
                        <p className="leading-relaxed text-foreground/90 font-normal">
                          {ev.detail}
                        </p>

                        {/* 事故衝擊與風控判定 (Impact) */}
                        {ev.impact && (
                          <div className="p-1.5 rounded-md bg-amber-500/10 border border-amber-500/25 text-[9px] text-amber-300 flex items-start gap-1.5 backdrop-blur-sm">
                            <AlertTriangle className="size-3 shrink-0 mt-0.5 text-amber-400" />
                            <div>
                              <span className="font-bold">風控衝擊：</span>
                              <span>{ev.impact}</span>
                            </div>
                          </div>
                        )}

                        {/* 下一步處置導引 (Next Step) */}
                        {ev.nextStep && (
                          <p className="text-[9px] text-muted-foreground leading-relaxed">
                            <span className="font-semibold text-foreground">下一步處置：</span>
                            <span>{ev.nextStep}</span>
                          </p>
                        )}

                        {/* 底部操作按鈕與來源列 */}
                        <div className="flex items-center justify-between pt-1 border-t border-white/[0.06] text-[8.5px] text-muted-foreground">
                          <div className="flex items-center gap-1.5">
                            <span>來源:</span>
                            <code className="text-primary bg-primary/10 px-1 py-0.2 rounded border border-primary/20">
                              {ev.source}
                            </code>
                            {ev.id === 'evt_unknown_calico' && (
                              <span className="flex items-center gap-1 text-amber-400 font-semibold ml-1 bg-amber-500/10 px-1.5 py-0.2 rounded border border-amber-500/25">
                                <Lock className="size-2.5" />
                                額度已鎖存 ($474.75)
                              </span>
                            )}
                          </div>

                          <div className="flex items-center gap-2">
                            {ev.botId && (
                              <button
                                type="button"
                                onClick={() => triggerHighlight('bot', ev.botId!)}
                                className="text-amber-400 hover:text-amber-300 font-semibold flex items-center gap-0.5 cursor-pointer"
                              >
                                <Crosshair className="size-2.5" />
                                <span>定位 Bot</span>
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => openInspector('event', ev.id)}
                              className="text-zinc-400 hover:text-foreground flex items-center gap-0.5 cursor-pointer"
                              title="開啟共用詳情抽屜"
                            >
                              <span>共用詳情</span>
                              <ExternalLink className="size-2.5" />
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
