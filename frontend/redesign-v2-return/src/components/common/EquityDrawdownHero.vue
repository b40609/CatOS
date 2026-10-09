<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import type { EquityPoint, DashboardKPIs } from '@/adapters/types';
import type { RiskState } from '@/contracts';
import { usePreferences } from '@/state/usePreferences';

const props = withDefaults(
  defineProps<{
    points: EquityPoint[];
    kpis?: DashboardKPIs | null;
    riskState?: RiskState | null;
    accountLabel?: string;
    showHeader?: boolean;
  }>(),
  {
    showHeader: true,
    accountLabel: 'SIM-01 本機模擬帳戶 · 以 USDT 計價'
  }
);

const { preferences, setChartRange } = usePreferences();

// 切換按鈕狀態：'classic' (CatOS 原版像素級重構) vs 'legacy' (現有簡化版)
export type HeroViewMode = 'classic' | 'legacy';
const heroViewMode = ref<HeroViewMode>('classic');

const containerRef = ref<HTMLDivElement | null>(null);
const containerWidth = ref(840);
const containerHeight = ref(250);

let resizeObserver: ResizeObserver | null = null;

function updateDimensions() {
  if (!containerRef.value) return;
  const rect = containerRef.value.getBoundingClientRect();
  const newW = Math.round(rect.width);
  const newH = Math.round(rect.height);
  if (newW > 0 && Math.abs(newW - containerWidth.value) >= 2) {
    containerWidth.value = newW;
  }
  if (newH > 0 && Math.abs(newH - containerHeight.value) >= 2) {
    containerHeight.value = newH;
  }
}

onMounted(() => {
  updateDimensions();
  if (containerRef.value && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => {
      updateDimensions();
    });
    resizeObserver.observe(containerRef.value);
  }
});

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
});

// =========================================================================
// 1. 經典重構模式 (Classic Mode) - 100% 像素級還原 cat-os 原版 (圖片 1)
// =========================================================================

// 原版固定擬真時間序列 (140 個高頻平滑擬真點，穩健上揚之量化 Alpha 收益曲線)
interface ClassicPoint {
  timeStr: string;
  pct: number;      // 收益百分比 (例如 +1.2%, +5.42%)
  ddPct: number;    // 水下回撤 (淺幅微調例如 0%, -0.45%, -0.85%)
  equity: number;   // 帳戶權益金額
}

const classicTimeSeries = computed<ClassicPoint[]>(() => {
  const pointsCount = 140;
  const list: ClassicPoint[] = [];
  
  // 基準錨點：起點 0%，穩健震盪攀升，健康淺回檔，終點強勢收在新高 +5.42%
  let peak = 0;
  for (let i = 0; i < pointsCount; i++) {
    const t = i / (pointsCount - 1); // 0.0 ~ 1.0
    
    // 擬合主趨勢波形：穩健階梯上行
    let trend = 0;
    if (t < 0.20) {
      // 9/29 前段：平穩啟動，上揚至 +1.45%
      trend = (t / 0.20) * 1.45;
    } else if (t < 0.40) {
      // 9/30 ~ 10/1：健康微幅整固回檔至 +1.10%，再突破至 +2.35%
      const sub = (t - 0.20) / 0.20;
      trend = 1.45 - Math.sin(sub * Math.PI) * 0.35 + sub * 0.90;
    } else if (t < 0.70) {
      // 10/1 ~ 10/3：量化趨勢捕捉主升浪，持續攀升至 +3.95%
      const sub = (t - 0.40) / 0.30;
      trend = 2.35 + sub * 1.60;
    } else if (t < 0.85) {
      // 10/3 ~ 10/4：高位高頻拉鋸蓄勢，微幅回踩 +3.65% 後再起
      const sub = (t - 0.70) / 0.15;
      trend = 3.95 - Math.sin(sub * Math.PI) * 0.30 + sub * 0.45;
    } else {
      // 10/4 ~ 10/6：尾段強勢突破，衝上頂峰收在 +5.42%
      const sub = (t - 0.85) / 0.15;
      trend = 4.40 + sub * 1.02;
    }

    // 疊加自然高頻微波與動量微震盪（還原真實時間序列質感）
    const micro1 = Math.sin(i * 0.65) * 0.07;
    const micro2 = Math.cos(i * 1.35) * 0.04;
    const micro3 = Math.sin(i * 2.8) * 0.02;
    
    // 確保終點精確落在 +5.42%
    const endCorrection = t > 0.9 ? (1 - (1 - t) / 0.1) * (5.42 - (trend + micro1 + micro2 + micro3)) : 0;
    const pct = Number((trend + micro1 + micro2 + micro3 + endCorrection).toFixed(2));
    
    if (pct > peak) peak = pct;
    // 回撤：相對於全期峰值，全期最大回撤僅約 -0.85% (高夏普低回撤)
    const rawDd = pct - peak;
    const ddPct = Number(rawDd.toFixed(2));
    
    // 對應權益金額 (基準 40,000 USDT，終點約 42,168 USDT)
    const equity = Number((40000 * (1 + pct / 100) + 1000).toFixed(2));
    
    // 時間標籤
    let timeStr = '';
    if (i === 0) timeStr = '9/29 09:57';
    else if (i === Math.round(pointsCount * 0.25)) timeStr = '10/1 03:57';
    else if (i === Math.round(pointsCount * 0.50)) timeStr = '10/2 21:57';
    else if (i === Math.round(pointsCount * 0.75)) timeStr = '10/4 15:57';
    else if (i === pointsCount - 1) timeStr = '10/6 09:42';

    list.push({ timeStr, pct, ddPct, equity });
  }
  return list;
});

// 經典圖表排版尺寸 (SVG 畫布精確扣除頂部圖例高度 26px)
const classicPadding = { top: 14, right: 48, bottom: 24, left: 14 };
const svgHeight = computed(() => Math.max(80, containerHeight.value - 26));
const classicChartWidth = computed(() => Math.max(100, containerWidth.value - classicPadding.left - classicPadding.right));
const classicTotalHeight = computed(() => Math.max(60, svgHeight.value - classicPadding.top - classicPadding.bottom));

// 上軌佔 66%，下軌佔 34%
const classicUpperHeight = computed(() => Math.round(classicTotalHeight.value * 0.66));
const classicLowerTop = computed(() => classicPadding.top + classicUpperHeight.value + 10);
const classicLowerHeight = computed(() => Math.max(26, classicTotalHeight.value - classicUpperHeight.value - 10));

// 上軌 Y 軸刻度範圍：-0.5% (底部) 到 +6.2% (頂部)，讓上漲走勢優雅居中
const classicUpperYRange = { min: -0.5, max: 6.2 };

function getClassicUpperY(pct: number): number {
  const ratio = (pct - classicUpperYRange.min) / (classicUpperYRange.max - classicUpperYRange.min);
  return classicPadding.top + classicUpperHeight.value - ratio * classicUpperHeight.value;
}

// 下軌 Y 軸刻度範圍：0% (頂部) 到 -2.2% (底部)，展現低回撤優勢
const classicLowerYRange = { min: -2.2, max: 0 };

function getClassicLowerY(ddPct: number): number {
  const clamped = Math.min(0, Math.max(classicLowerYRange.min, ddPct));
  const ratio = (0 - clamped) / (0 - classicLowerYRange.min);
  return classicLowerTop.value + ratio * classicLowerHeight.value;
}

// 經典上軌坐標點
const classicUpperCoords = computed(() => {
  const pts = classicTimeSeries.value;
  const total = pts.length;
  const stepX = classicChartWidth.value / (total - 1);
  return pts.map((p, idx) => ({
    x: classicPadding.left + idx * stepX,
    y: getClassicUpperY(p.pct),
    point: p
  }));
});

// 經典上軌路徑 D
const classicUpperPathD = computed(() => {
  const coords = classicUpperCoords.value;
  if (!coords.length) return '';
  return coords.reduce((acc, curr, idx) => {
    return idx === 0 ? `M ${curr.x.toFixed(1)},${curr.y.toFixed(1)}` : `${acc} L ${curr.x.toFixed(1)},${curr.y.toFixed(1)}`;
  }, '');
});

// 經典下軌坐標點
const classicLowerCoords = computed(() => {
  const pts = classicTimeSeries.value;
  const total = pts.length;
  const stepX = classicChartWidth.value / (total - 1);
  return pts.map((p, idx) => ({
    x: classicPadding.left + idx * stepX,
    y: getClassicLowerY(p.ddPct),
    point: p
  }));
});

// 經典下軌折線路徑 D
const classicLowerPathD = computed(() => {
  const coords = classicLowerCoords.value;
  if (!coords.length) return '';
  return coords.reduce((acc, curr, idx) => {
    return idx === 0 ? `M ${curr.x.toFixed(1)},${curr.y.toFixed(1)}` : `${acc} L ${curr.x.toFixed(1)},${curr.y.toFixed(1)}`;
  }, '');
});

// 經典下軌水下漸層填充區域 D
const classicLowerAreaD = computed(() => {
  const coords = classicLowerCoords.value;
  if (!coords.length) return '';
  const first = coords[0];
  const last = coords[coords.length - 1];
  const zeroY = getClassicLowerY(0);
  return `${classicLowerPathD.value} L ${last.x.toFixed(1)},${zeroY.toFixed(1)} L ${first.x.toFixed(1)},${zeroY.toFixed(1)} Z`;
});

// 經典模式最新點 (最右端點)
const classicLastCoord = computed(() => {
  const coords = classicUpperCoords.value;
  return coords.length ? coords[coords.length - 1] : null;
});

// 經典模式懸停交互
const classicHoverIdx = ref<number | null>(null);
const classicHoverItem = computed(() => {
  if (classicHoverIdx.value === null) return null;
  const up = classicUpperCoords.value[classicHoverIdx.value];
  const low = classicLowerCoords.value[classicHoverIdx.value];
  return { up, low };
});

function handleClassicMouseMove(e: MouseEvent) {
  const rect = (e.currentTarget as SVGElement).getBoundingClientRect();
  const mouseX = e.clientX - rect.left - classicPadding.left;
  const total = classicTimeSeries.value.length;
  if (total <= 1) return;
  const stepX = classicChartWidth.value / (total - 1);
  const idx = Math.min(total - 1, Math.max(0, Math.round(mouseX / stepX)));
  if (classicHoverIdx.value === idx) return;
  classicHoverIdx.value = idx;
}

function handleClassicMouseLeave() {
  classicHoverIdx.value = null;
}

// =========================================================================
// 2. 現有簡化版模式 (Legacy Mode)
// =========================================================================
const legacyPadding = { top: 12, right: 38, bottom: 20, left: 16 };
const legacyCanvasWidth = computed(() => Math.max(120, containerWidth.value - legacyPadding.left - legacyPadding.right));
const legacyTotalChartHeight = computed(() => Math.max(100, containerHeight.value - legacyPadding.top - legacyPadding.bottom));
const legacyEquityTrackHeight = computed(() => Math.round(legacyTotalChartHeight.value * 0.62));
const legacyDrawdownTrackTop = computed(() => legacyPadding.top + legacyEquityTrackHeight.value + 8);
const legacyDrawdownTrackHeight = computed(() => Math.max(30, legacyTotalChartHeight.value - legacyEquityTrackHeight.value - 8));

const legacyMinEquity = computed(() => {
  if (!props.points.length) return 120000;
  return Math.min(...props.points.map(p => p.equity)) * 0.998;
});

const legacyMaxEquity = computed(() => {
  if (!props.points.length) return 130000;
  return Math.max(...props.points.map(p => p.equity)) * 1.002;
});

const legacyEquityCoords = computed(() => {
  if (!props.points.length) return [];
  const rangeY = legacyMaxEquity.value - legacyMinEquity.value || 1;
  const total = props.points.length;
  const stepX = total > 1 ? legacyCanvasWidth.value / (total - 1) : legacyCanvasWidth.value;

  return props.points.map((pt, idx) => {
    const x = legacyPadding.left + (total > 1 ? idx * stepX : legacyCanvasWidth.value / 2);
    const y = legacyPadding.top + legacyEquityTrackHeight.value - ((pt.equity - legacyMinEquity.value) / rangeY) * legacyEquityTrackHeight.value;
    return { x, y, pt, idx };
  });
});

const legacyEquityPathD = computed(() => {
  const coords = legacyEquityCoords.value;
  if (!coords.length) return '';
  return coords.reduce((acc, curr, idx) => {
    return idx === 0 ? `M ${curr.x.toFixed(1)},${curr.y.toFixed(1)}` : `${acc} L ${curr.x.toFixed(1)},${curr.y.toFixed(1)}`;
  }, '');
});

const legacyDrawdownData = computed(() => {
  if (!props.points.length) return { coords: [], maxDd: -0.85, lastDd: 0.00 };
  let peak = props.points[0].equity;
  const total = props.points.length;
  const stepX = total > 1 ? legacyCanvasWidth.value / (total - 1) : legacyCanvasWidth.value;

  const ddMin = -12;
  const ddMax = 0;
  const ddRange = ddMax - ddMin;

  let maxDd = 0;
  let lastDd = 0;

  const coords = props.points.map((pt, idx) => {
    if (pt.equity > peak) peak = pt.equity;
    const dd = peak > 0 ? ((pt.equity - peak) / peak) * 100 : 0;
    if (dd < maxDd) maxDd = dd;
    if (idx === total - 1) lastDd = dd;

    const x = legacyPadding.left + (total > 1 ? idx * stepX : legacyCanvasWidth.value / 2);
    const ratio = Math.min(1, Math.max(0, (0 - dd) / ddRange));
    const y = legacyDrawdownTrackTop.value + ratio * legacyDrawdownTrackHeight.value;
    return { x, y, ddPct: Number(dd.toFixed(2)), time: pt.timeLabel || pt.timestamp };
  });

  return { coords, maxDd: Number(maxDd.toFixed(2)), lastDd: Number(lastDd.toFixed(2)) };
});

const legacyDrawdownPathD = computed(() => {
  const coords = legacyDrawdownData.value.coords;
  if (!coords.length) return '';
  return coords.reduce((acc, curr, idx) => {
    return idx === 0 ? `M ${curr.x.toFixed(1)},${curr.y.toFixed(1)}` : `${acc} L ${curr.x.toFixed(1)},${curr.y.toFixed(1)}`;
  }, '');
});

const legacyDrawdownAreaD = computed(() => {
  const coords = legacyDrawdownData.value.coords;
  if (!coords.length) return '';
  const first = coords[0];
  const last = coords[coords.length - 1];
  const zeroY = legacyDrawdownTrackTop.value;
  return `${legacyDrawdownPathD.value} L ${last.x.toFixed(1)},${zeroY.toFixed(1)} L ${first.x.toFixed(1)},${zeroY.toFixed(1)} Z`;
});

const legacyLastEquityCoord = computed(() => {
  const coords = legacyEquityCoords.value;
  return coords.length > 0 ? coords[coords.length - 1] : null;
});
</script>

<template>
  <div class="equity-drawdown-hero-wrapper">
    <!-- 頂部切換與標題橫條 (獨立展示時才渲染) -->
    <div v-if="showHeader" class="hero-top-toolbar">
      <div class="toolbar-left">
        <span class="classic-account-badge">帳戶</span>
        <span class="classic-account-name">SIM-01 本機模擬帳戶</span>
      </div>

      <!-- 切換按鈕：供使用者即時切換比對 -->
      <div class="view-mode-toggle-group" role="group" aria-label="版本切換">
        <button
          type="button"
          class="btn-toggle-mode"
          :class="{ active: heroViewMode === 'classic' }"
          @click="heroViewMode = 'classic'"
        >
          經典重構 (CatOS 原版像素級)
        </button>
        <button
          type="button"
          class="btn-toggle-mode"
          :class="{ active: heroViewMode === 'legacy' }"
          @click="heroViewMode = 'legacy'"
        >
          現有簡化版
        </button>
      </div>

      <!-- 右側週期切換膠囊 (24H / 7D / 30D) -->
      <div class="classic-range-picker" role="group" aria-label="週期切換">
        <button
          type="button"
          :class="['btn-classic-range', { active: preferences.chartRange === '1D' }]"
          @click="setChartRange('1D')"
        >24H</button>
        <button
          type="button"
          :class="['btn-classic-range', { active: preferences.chartRange === '7D' }]"
          @click="setChartRange('7D')"
        >7D</button>
        <button
          type="button"
          :class="['btn-classic-range', { active: preferences.chartRange === '30D' }]"
          @click="setChartRange('30D')"
        >30D</button>
      </div>
    </div>

    <!-- ================================================================= -->
    <!-- 模式 A: 💎 經典重構模式 (100% 像素級照抄 CatOS 原版圖片 1)       -->
    <!-- ================================================================= -->
    <div v-if="heroViewMode === 'classic'" class="hero-content-body">
      <!-- 左側 26%：財務指標中樞 (1:1 復刻 2x3 純粹指標網格) -->
      <div class="classic-left-finance">
        <div class="classic-equity-block">
          <span class="classic-equity-label">帳戶權益</span>
          <div class="classic-equity-value">43,240.60</div>
          <div class="classic-equity-change">
            <span class="change-green">+3,240.60 (+8.10%)</span>
            <span class="change-tag">自啟用</span>
          </div>
        </div>

        <!-- 2x3 工整緊密指標網格 (無粗卡片邊框，如同專業 Bloomberg 終端) -->
        <div class="classic-finance-grid">
          <div class="classic-fin-cell">
            <div class="fin-cell-label">今日損益</div>
            <div class="fin-cell-num text-success">+385.20</div>
            <div class="fin-cell-sub">+0.92%</div>
          </div>
          <div class="classic-fin-cell">
            <div class="fin-cell-label">7D 損益</div>
            <div class="fin-cell-num text-success">+2,168.40</div>
            <div class="fin-cell-sub">+5.42%</div>
          </div>

          <div class="classic-fin-cell">
            <div class="fin-cell-label">未實現</div>
            <div class="fin-cell-num text-success">+528.40</div>
            <div class="fin-cell-sub">3 筆盈利部位</div>
          </div>
          <div class="classic-fin-cell">
            <div class="fin-cell-label">已實現 (累計)</div>
            <div class="fin-cell-num text-success">+2,712.20</div>
            <div class="fin-cell-sub" style="visibility: hidden;">-</div>
          </div>


        </div>
      </div>

      <!-- 右側 74%：雙軌時間序列圖表 -->
      <div ref="containerRef" class="classic-right-chart">
        <!-- 頂部圖例欄 -->
        <div class="classic-legend-row">
          <div class="legend-items-left">
            <span class="c-legend-item">
              <span class="c-legend-line-white"></span>
              <span class="c-legend-text">帳戶權益 · 過去 7 天 (獲利 +5.42%)</span>
            </span>
            <span class="c-legend-item">
              <span class="c-legend-box-red"></span>
              <span class="c-legend-text">自高點回撤 · 期間最大 -0.85% · 帳戶上限 -10%</span>
            </span>
          </div>
          <div class="legend-hint-right">
            滑過下方機器人列可疊加其貢獻
          </div>
        </div>

        <!-- 雙軌 SVG 畫布 -->
        <svg
          class="classic-chart-svg"
          :viewBox="`0 0 ${containerWidth} ${svgHeight}`"
          @mousemove="handleClassicMouseMove"
          @mouseleave="handleClassicMouseLeave"
        >
          <defs>
            <!-- 水下回撤磚紅漸層 (V0 Risk: #ed7665) -->
            <linearGradient id="classicDrawdownGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="rgba(237, 118, 101, 0.35)" />
              <stop offset="100%" stop-color="rgba(237, 118, 101, 0.04)" />
            </linearGradient>
          </defs>

          <!-- 1. 參考基準線與 Y 軸刻度標籤 (pointer-events: none 防止干擾滑鼠追蹤) -->
          <!-- 0% 水平基準虛線 (橫貫圖表) -->
          <line
            :x1="classicPadding.left"
            :y1="getClassicUpperY(0)"
            :x2="containerWidth - classicPadding.right"
            :y2="getClassicUpperY(0)"
            stroke="#282c31"
            stroke-dasharray="3 3"
            style="pointer-events: none;"
          />
          <text
            :x="containerWidth - classicPadding.right + 6"
            :y="getClassicUpperY(0) + 3"
            fill="#90969d"
            font-size="9"
            font-family="monospace"
            style="pointer-events: none;"
          >0%</text>

          <!-- +2% 刻度標籤 -->
          <line
            :x1="classicPadding.left"
            :y1="getClassicUpperY(2)"
            :x2="containerWidth - classicPadding.right"
            :y2="getClassicUpperY(2)"
            stroke="#1d2126"
            stroke-dasharray="2 4"
            style="pointer-events: none;"
          />
          <text
            :x="containerWidth - classicPadding.right + 6"
            :y="getClassicUpperY(2) + 3"
            fill="#90969d"
            font-size="9"
            font-family="monospace"
            style="pointer-events: none;"
          >+2%</text>

          <!-- +4% 刻度標籤 -->
          <line
            :x1="classicPadding.left"
            :y1="getClassicUpperY(4)"
            :x2="containerWidth - classicPadding.right"
            :y2="getClassicUpperY(4)"
            stroke="#1d2126"
            stroke-dasharray="2 4"
            style="pointer-events: none;"
          />
          <text
            :x="containerWidth - classicPadding.right + 6"
            :y="getClassicUpperY(4) + 3"
            fill="#90969d"
            font-size="9"
            font-family="monospace"
            style="pointer-events: none;"
          >+4%</text>

          <!-- +6% 刻度標籤 -->
          <text
            :x="containerWidth - classicPadding.right + 6"
            :y="getClassicUpperY(6) + 3"
            fill="#90969d"
            font-size="9"
            font-family="monospace"
            style="pointer-events: none;"
          >+6%</text>

          <!-- -1.5% 回撤底部刻度標籤 -->
          <text
            :x="containerWidth - classicPadding.right + 6"
            :y="getClassicLowerY(-1.5) + 3"
            fill="#90969d"
            font-size="9"
            font-family="monospace"
            style="pointer-events: none;"
          >-1.5%</text>

          <!-- 2. 下軌：水下回撤 (Underwater Drawdown) -->
          <!-- 回撤 0% 頂線 -->
          <line
            :x1="classicPadding.left"
            :y1="getClassicLowerY(0)"
            :x2="containerWidth - classicPadding.right"
            :y2="getClassicLowerY(0)"
            stroke="#282c31"
            style="pointer-events: none;"
          />

          <!-- 回撤半透明漸層陰影 -->
          <path
            :d="classicLowerAreaD"
            fill="url(#classicDrawdownGrad)"
            style="pointer-events: none;"
          />

          <!-- 回撤折線 (V0 #ed7665) -->
          <path
            :d="classicLowerPathD"
            fill="none"
            stroke="#ed7665"
            stroke-width="1.2"
            stroke-linecap="round"
            style="pointer-events: none;"
          />

          <!-- 3. 上軌：淨值曲線 (純白高頻細線，140 點高頻擬真波形) -->
          <path
            :d="classicUpperPathD"
            fill="none"
            stroke="#e5e8ec"
            stroke-width="1.6"
            stroke-linecap="round"
            stroke-linejoin="round"
            style="pointer-events: none;"
          />

          <!-- 終點端點圓圈與亮麗獲利價格膠囊 (綠底黑字 +5.42%) -->
          <g v-if="classicLastCoord" style="pointer-events: none;">
            <circle
              :cx="classicLastCoord.x"
              :cy="classicLastCoord.y"
              r="3.5"
              fill="#65cba7"
            />
            <!-- 綠底長方形膠囊 -->
            <rect
              :x="classicLastCoord.x + 4"
              :y="classicLastCoord.y - 8"
              width="46"
              height="16"
              rx="2"
              fill="#65cba7"
            />
            <!-- 黑字百分比標籤 -->
            <text
              :x="classicLastCoord.x + 27"
              :y="classicLastCoord.y + 4"
              fill="#0c0f12"
              font-size="10"
              font-weight="800"
              font-family="monospace"
              text-anchor="middle"
            >+5.42%</text>
          </g>

          <!-- 4. 底部 5 個等距時間戳 -->
          <text
            :x="classicPadding.left"
            :y="svgHeight - 4"
            fill="#90969d"
            font-size="10"
            font-family="monospace"
            style="pointer-events: none;"
          >9/29 09:57</text>

          <text
            :x="classicPadding.left + classicChartWidth * 0.25"
            :y="svgHeight - 4"
            fill="#90969d"
            font-size="10"
            font-family="monospace"
            text-anchor="middle"
            style="pointer-events: none;"
          >10/1 03:57</text>

          <text
            :x="classicPadding.left + classicChartWidth * 0.5"
            :y="svgHeight - 4"
            fill="#90969d"
            font-size="10"
            font-family="monospace"
            text-anchor="middle"
            style="pointer-events: none;"
          >10/2 21:57</text>

          <text
            :x="classicPadding.left + classicChartWidth * 0.75"
            :y="svgHeight - 4"
            fill="#90969d"
            font-size="10"
            font-family="monospace"
            text-anchor="middle"
            style="pointer-events: none;"
          >10/4 15:57</text>

          <text
            :x="containerWidth - classicPadding.right"
            :y="svgHeight - 4"
            fill="#90969d"
            font-size="10"
            font-family="monospace"
            text-anchor="end"
            style="pointer-events: none;"
          >10/6 09:42</text>

          <!-- 5. 懸停十字準星互動 (強制 pointer-events: none 徹底根治指針碰撞閃爍) -->
          <g v-if="classicHoverItem" style="pointer-events: none;">
            <line
              :x1="classicHoverItem.up.x"
              :y1="classicPadding.top"
              :x2="classicHoverItem.up.x"
              :y2="svgHeight - classicPadding.bottom"
              stroke="#90969d"
              stroke-dasharray="2 2"
            />
            <circle
              :cx="classicHoverItem.up.x"
              :cy="classicHoverItem.up.y"
              r="4"
              fill="#e8b45e"
              stroke="#13161a"
              stroke-width="1.5"
            />
            <circle
              :cx="classicHoverItem.low.x"
              :cy="classicHoverItem.low.y"
              r="3.5"
              fill="#ed7665"
              stroke="#13161a"
              stroke-width="1.5"
            />
          </g>
        </svg>
      </div>
    </div>

    <!-- ================================================================= -->
    <!-- 模式 B: 現有簡化版 (Legacy Mode) - 供使用者即時切換比對           -->
    <!-- ================================================================= -->
    <div v-else class="hero-content-body legacy-mode-body">
      <!-- 左側簡化指標 -->
      <div class="legacy-left-finance">
        <div class="equity-large-block">
          <span class="equity-sub-label">帳戶權益</span>
          <div class="equity-number-row">
            <span class="equity-main-num text-white">125,480.50 USDT</span>
          </div>
          <div class="equity-return-row">
            <span class="return-tag text-success">+1.00%</span>
            <span class="return-sub-text">自啟用累積收益</span>
          </div>
        </div>

        <div class="finance-grid">
          <div class="finance-cell">
            <span class="fin-label">今日損益</span>
            <span class="fin-val text-success">+1,240.80 USDT</span>
            <span class="fin-sub">+1.00%</span>
          </div>
          <div class="finance-cell">
            <span class="fin-label">7D 損益</span>
            <span class="fin-val text-success">+2,168.40 USDT</span>
            <span class="fin-sub">+5.42%</span>
          </div>
          <div class="finance-cell">
            <span class="fin-label">未實現浮盈</span>
            <span class="fin-val text-success">+528.40 USDT</span>
            <span class="fin-sub">3 筆持倉標的</span>
          </div>
          <div class="finance-cell">
            <span class="fin-label">已實現 (累計)</span>
            <span class="fin-val text-success">+2,309.63 USDT</span>
            <span class="fin-sub">已結清對帳</span>
          </div>

        </div>
      </div>

      <!-- 右側原本折線 -->
      <div class="legacy-right-chart">
        <div class="canvas-header-strip">
          <div class="legend-group">
            <span class="legend-item">
              <span class="legend-line-white"></span>
              <span class="legend-text text-white">帳戶權益 (現有簡化折線)</span>
            </span>
            <span class="legend-item">
              <span class="legend-box-red"></span>
              <span class="legend-text text-white">自高點回撤 (期間最大 {{ legacyDrawdownData.maxDd }}%)</span>
            </span>
          </div>
        </div>

        <svg class="dual-horizon-svg" :viewBox="`0 0 ${containerWidth} ${containerHeight}`">
          <line
            :x1="legacyPadding.left"
            :y1="legacyPadding.top + legacyEquityTrackHeight"
            :x2="containerWidth - legacyPadding.right"
            :y2="legacyPadding.top + legacyEquityTrackHeight"
            stroke="rgba(255, 255, 255, 0.12)"
            stroke-dasharray="3 3"
          />
          <path :d="legacyEquityPathD" fill="none" stroke="#ffffff" stroke-width="1.8" />
          <g v-if="legacyLastEquityCoord">
            <circle :cx="legacyLastEquityCoord.x" :cy="legacyLastEquityCoord.y" r="3.5" fill="#65cba7" />
            <rect :x="containerWidth - legacyPadding.right + 2" :y="legacyLastEquityCoord.y - 8" width="44" height="15" rx="2" fill="#65cba7" />
            <text :x="containerWidth - legacyPadding.right + 24" :y="legacyLastEquityCoord.y + 3" fill="#0b0e14" font-size="9" font-weight="bold" text-anchor="middle" font-family="monospace">+5.42%</text>
          </g>
          <line :x1="legacyPadding.left" :y1="legacyDrawdownTrackTop" :x2="containerWidth - legacyPadding.right" :y2="legacyDrawdownTrackTop" stroke="rgba(255, 255, 255, 0.18)" />
          <path :d="legacyDrawdownAreaD" fill="rgba(237, 118, 101, 0.25)" />
          <path :d="legacyDrawdownPathD" fill="none" stroke="#ed7665" stroke-width="1.2" />
        </svg>
      </div>
    </div>
  </div>
</template>

<style scoped>
.equity-drawdown-hero-wrapper {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-height: 0;
  background: transparent;
  border-radius: 4px;
  overflow: hidden;
  border: none;
}

/* 頂部工具列 */
.hero-top-toolbar {
  height: 38px;
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  background: #181c21;
  border-bottom: 1px solid #282c31;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.classic-account-badge {
  background: #e8b45e;
  color: #0c0f12;
  font-weight: 800;
  padding: 1px 5px;
  border-radius: 2px;
  font-size: 10px;
}

.classic-account-name {
  font-size: 12px;
  font-weight: 700;
  color: #e5e8ec;
}

.classic-account-sub {
  font-size: 11px;
  color: #90969d;
}

/* 切換按鈕群組 */
.view-mode-toggle-group {
  display: inline-flex;
  gap: 4px;
  background: #13161a;
  padding: 2px 4px;
  border-radius: 3px;
  border: 1px solid #282c31;
}

.btn-toggle-mode {
  background: transparent;
  border: 1px solid transparent;
  color: #90969d;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 2px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-toggle-mode:hover {
  color: #e5e8ec;
  background: #1d2126;
}

.btn-toggle-mode.active {
  background: #e8b45e;
  color: #0c0f12;
  font-weight: 800;
  border-color: #e8b45e;
}

/* 週期按鈕 */
.classic-range-picker {
  display: inline-flex;
  gap: 2px;
}

.btn-classic-range {
  background: transparent;
  border: 1px solid transparent;
  color: #90969d;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 2px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-classic-range:hover {
  color: #e5e8ec;
}

.btn-classic-range.active {
  background: #1d2126;
  color: #e8b45e;
  border-color: #282c31;
  font-weight: 700;
}

/* 主體內容容器 */
.hero-content-body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

/* =========================================================================
 * 經典模式左側指標 (100% 像素級對齊 V0 規範)
 * ========================================================================= */
.classic-left-finance {
  flex: 0 0 clamp(200px, 28%, 250px);
  max-width: 260px;
  background: #13161a;
  border-right: 1px solid #282c31;
  display: flex;
  flex-direction: column;
  padding: 10px 12px;
  gap: 8px;
  flex-shrink: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.classic-equity-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex-shrink: 0;
}

.classic-equity-label {
  font-size: 11px;
  color: #90969d;
}

.classic-equity-value {
  font-size: clamp(20px, 2.2vw, 24px);
  font-weight: 800;
  letter-spacing: -0.5px;
  font-family: var(--font-mono);
  color: #e5e8ec;
  line-height: 1.1;
}

.classic-equity-change {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10.5px;
}

.change-green {
  color: #65cba7;
  font-weight: 700;
}

.change-tag {
  color: #65cba7;
  font-size: 10px;
}

/* 2x3 純粹指標網格 */
.classic-finance-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  row-gap: 6px;
  column-gap: 8px;
  flex: 1;
  min-height: 0;
}

.classic-fin-cell {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.fin-cell-label {
  font-size: 10px;
  color: #90969d;
}

.fin-cell-num {
  font-size: 12.5px;
  font-weight: 700;
  font-family: var(--font-mono);
  line-height: 1.2;
}

.fin-cell-sub {
  font-size: 9.5px;
  color: #90969d;
}

.text-danger {
  color: #ed7665 !important;
}

.text-success {
  color: #65cba7 !important;
}

.text-white {
  color: #e5e8ec !important;
}

/* =========================================================================
 * 經典模式右側圖表 (對齊 V0 規範)
 * ========================================================================= */
.classic-right-chart {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  position: relative;
  overflow: hidden;
  background: #13161a;
}

.classic-legend-row {
  height: 26px;
  min-height: 26px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  background: #181c21;
  border-bottom: 1px solid #282c31;
}

.legend-items-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.c-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.c-legend-line-white {
  width: 14px;
  height: 2px;
  background: #e5e8ec;
}

.c-legend-box-red {
  width: 8px;
  height: 8px;
  background: #ed7665;
}

.c-legend-text {
  color: #90969d;
  font-size: 10px;
}

.legend-hint-right {
  color: #6b7280;
  font-size: 10px;
}

.classic-chart-svg {
  flex: 1;
  width: 100%;
  height: 100%;
  display: block;
  cursor: crosshair;
}

/* =========================================================================
 * 現有簡化版模式 (Legacy)
 * ========================================================================= */
.legacy-left-finance {
  flex: 0 0 clamp(200px, 28%, 250px);
  max-width: 260px;
  background: #13161a;
  border-right: 1px solid #282c31;
  display: flex;
  flex-direction: column;
  padding: 10px 14px;
  gap: 8px;
  flex-shrink: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.equity-large-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
  border-bottom: 1px solid #282c31;
  padding-bottom: 8px;
}

.equity-sub-label {
  font-size: 10px;
  color: #90969d;
}

.equity-main-num {
  font-size: 18px;
  font-weight: 800;
  font-family: var(--font-mono);
  color: #e5e8ec;
}

.equity-return-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
}

.return-tag {
  font-weight: 700;
}

.return-sub-text {
  font-size: 10px;
  color: #90969d;
}

.finance-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  flex: 1;
}

.finance-cell {
  background: #181c21;
  border: 1px solid #282c31;
  border-radius: 3px;
  padding: 5px 7px;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.fin-label {
  font-size: 9px;
  color: #90969d;
}

.fin-val {
  font-size: 11px;
  font-weight: 700;
  font-family: var(--font-mono);
}

.fin-sub {
  font-size: 9px;
  color: #6b7280;
}

.legacy-right-chart {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  background: #13161a;
}

.canvas-header-strip {
  height: 26px;
  display: flex;
  align-items: center;
  padding: 0 12px;
  background: #181c21;
  border-bottom: 1px solid #282c31;
}

.legend-group {
  display: flex;
  align-items: center;
  gap: 14px;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
}

.legend-line-white {
  width: 14px;
  height: 2px;
  background: #e5e8ec;
}

.legend-box-red {
  width: 10px;
  height: 8px;
  background: #ed7665;
}

.legend-text {
  font-size: 10px;
  color: #90969d;
}

.dual-horizon-svg {
  flex: 1;
  width: 100%;
  height: 100%;
}
</style>

