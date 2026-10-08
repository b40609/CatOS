<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import type { ExposureAllocationItem } from '@/contracts';

const props = withDefaults(
  defineProps<{
    items?: ExposureAllocationItem[];
    centerValue?: string;
    centerLabel?: string;
    showHeader?: boolean;
    initialMode?: 'ranked_assets' | 'leveraged' | 'raw_margin' | 'compare_all';
  }>(),
  {
    showHeader: true,
    initialMode: 'ranked_assets', // 定案預設：幣種排行視圖
  }
);

// 業務視圖切換 (定案排版：Bloomberg 終端網格規格)
export type ViewMode = 'ranked_assets' | 'leveraged' | 'raw_margin' | 'compare_all';
const activeMode = ref<ViewMode>(props.initialMode || 'ranked_assets');
const hoveredIndex = ref<number | null>(null);

// 容器自適應監聽 (右欄面板常態套用優雅水平排版)
const containerRef = ref<HTMLDivElement | null>(null);
const containerHeight = ref<number>(250);
const isCompactHeight = computed(() => containerHeight.value < 360);

let resizeObserver: ResizeObserver | null = null;

function updateDimensions() {
  if (!containerRef.value) return;
  const rect = containerRef.value.getBoundingClientRect();
  if (rect.height > 0) {
    containerHeight.value = Math.round(rect.height);
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

// 中心是否顯示數值 (Tabler 原版：純淨留空 vs 中心顯示總額)
const showCenterText = ref<boolean>(false);

// 定案配色：低彩度、高質感的幣種資料系列色 (收斂刺眼霓虹感)
const cryptoColors = {
  btc: 'var(--primary, #e8b45e)',       // BTC 蜂蜜金
  in_flight: 'var(--info-accent, #7faee2)', // ETH / 在途凍結 雅緻瓦藍
  available: 'var(--gain, #65cba7)',     // 可用額度 薄荷青
  alt: '#8b8df8',                        // SOL 沉穩淡靛
  neutral: 'var(--muted-foreground, #90969d)' // 中性灰
};

// 1. 幣種排行資料 (定案主力視圖)
const rankedAssets = computed(() => [
  { rank: 1, symbol: 'BTC', label: 'BTC-USDT', shortLabel: 'BTC', sub: '持有中', nominal_usdt: '596.60', pct_share: 73.7, color: cryptoColors.btc },
  { rank: 2, symbol: 'ETH', label: 'ETH-USDT', shortLabel: 'ETH', sub: '掛單中', nominal_usdt: '213.08', pct_share: 26.3, color: cryptoColors.in_flight },
  { rank: 3, symbol: 'SOL', label: 'SOL-USDT', shortLabel: 'SOL', sub: '空倉', nominal_usdt: '0.00', pct_share: 0.0, color: cryptoColors.alt }
]);

// 2. 名義曝險資料
const leveragedItems = computed(() => [
  { label: 'BTC 永續持倉', shortLabel: 'BTC 持倉', symbol: 'BTC', sub: '持倉', nominal_usdt: '596.60', pct_share: 42, color: cryptoColors.btc },
  { label: '在途委託凍結', shortLabel: '在途凍結', symbol: '在途', sub: '凍結', nominal_usdt: '213.08', pct_share: 15, color: cryptoColors.in_flight },
  { label: '可用曝險額度', shortLabel: '可用額度', symbol: '可用', sub: '剩餘', nominal_usdt: '610.82', pct_share: 43, color: cryptoColors.available }
]);

// 3. 真實保證金資料
const rawMarginItems = computed(() => [
  { label: '佔用本金', shortLabel: '佔用本金', symbol: '佔用', sub: '保證金', nominal_usdt: '80.97', pct_share: 0.07, color: cryptoColors.btc },
  { label: '自由未佔用', shortLabel: '自由現金', symbol: '可用', sub: '本金', nominal_usdt: '125,400', pct_share: 99.93, color: cryptoColors.available }
]);

// 4. 雙軸對照資料
const compareRows = computed(() => [
  { label: 'BTC 持倉', shortLabel: 'BTC', symbol: 'BTC', sub: '槓桿', raw_usdt: '59.66', nominal_usdt: '596.60', pct_share: 42, color: cryptoColors.btc },
  { label: '在途委託', shortLabel: '在途', symbol: '在途', sub: '委託', raw_usdt: '21.31', nominal_usdt: '213.08', pct_share: 15, color: cryptoColors.in_flight },
  { label: '可用額度', shortLabel: '可用', symbol: '可用', sub: '預算', raw_usdt: '125.4k', nominal_usdt: '610.82', pct_share: 43, color: cryptoColors.available }
]);

// 當前活耀切片資料
const currentItems = computed(() => {
  if (activeMode.value === 'leveraged') return leveragedItems.value;
  if (activeMode.value === 'raw_margin') return rawMarginItems.value;
  if (activeMode.value === 'compare_all') return compareRows.value;
  return rankedAssets.value;
});

// 總計資料（用於 2x2 對稱網格第 4 格平衡卡片）
const totalSummary = computed(() => {
  if (activeMode.value === 'raw_margin') {
    return { label: '帳戶總權益', shortLabel: '總權益', symbol: '總額', sub: '權益', nominal_usdt: '125,480.97', pct_share: 100, color: '#e2e8f0' };
  }
  return { label: '總曝險上限', shortLabel: '總額度', symbol: '總額', sub: '上限', nominal_usdt: '1,420.50', pct_share: 100, color: '#e2e8f0' };
});

// 自適應精密尺寸 (矮高度時 74px 直徑，標準時 88px 直徑)
const size = computed(() => (isCompactHeight.value ? 74 : 88));
const strokeWidth = computed(() => (isCompactHeight.value ? 11 : 13));
const radius = computed(() => (size.value - strokeWidth.value) / 2);
const circumference = computed(() => 2 * Math.PI * radius.value);

const slices = computed(() => {
  let accumulated = 0;
  const gapPx = 2.0;

  return currentItems.value.map((item, idx) => {
    let effectivePct = item.pct_share;
    if (activeMode.value === 'raw_margin' && item.pct_share < 1 && item.pct_share > 0) {
      effectivePct = 6.0;
    }
    const fullArc = (effectivePct / 100) * circumference.value;
    const arcLength = Math.max(0, fullArc - gapPx);
    const strokeDasharray = `${arcLength} ${circumference.value - arcLength}`;
    const strokeDashoffset = -accumulated;
    accumulated += fullArc;

    return {
      ...item,
      strokeColor: item.color,
      strokeDasharray,
      strokeDashoffset,
      isHovered: hoveredIndex.value === idx
    };
  });
});

function formatUsdt(val?: string | number): string {
  if (val === undefined || val === null) return '0.00';
  if (typeof val === 'string' && val.includes('k')) return val;
  const cleanStr = typeof val === 'string' ? val.replace(/,/g, '') : String(val);
  const num = parseFloat(cleanStr);
  if (isNaN(num)) return String(val);
  if (num >= 100000) {
    return Math.round(num).toLocaleString('en-US');
  }
  return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
</script>

<template>
  <div
    ref="containerRef"
    class="donut-card card tabler-donut-style layout-terminal-grid"
    :class="{ 'no-header': !showHeader, 'is-compact-h': isCompactHeight }"
  >
    <!-- 頂部卡片頭部 (Header，當獨立於 Pane 外時顯示) -->
    <div v-if="showHeader" class="card-header tabler-header">
      <div class="header-titles">
        <h3 class="card-title">資產曝險配置</h3>
        <p class="card-subtitle">定案終端網格 · 幣種排行視圖</p>
      </div>
      <button
        type="button"
        class="center-mode-toggle"
        :class="{ active: showCenterText }"
        @click="showCenterText = !showCenterText"
        title="切換 Tabler 原版純淨留空 / 顯示中央數值"
      >
        {{ showCenterText ? '中心：總額' : '中心：留空' }}
      </button>
    </div>

    <!-- 業務視圖切換列 (4 等分 Micro-tabs，幣種排行作為主力視圖) -->
    <div class="view-mode-tabs-bar">
      <button
        type="button"
        :class="['mode-tab', { active: activeMode === 'ranked_assets' }]"
        @click="activeMode = 'ranked_assets'"
      >
        幣種排行
      </button>
      <button
        type="button"
        :class="['mode-tab', { active: activeMode === 'leveraged' }]"
        @click="activeMode = 'leveraged'"
      >
        名義曝險
      </button>
      <button
        type="button"
        :class="['mode-tab', { active: activeMode === 'raw_margin' }]"
        @click="activeMode = 'raw_margin'"
      >
        真實本金
      </button>
      <button
        type="button"
        :class="['mode-tab', { active: activeMode === 'compare_all' }]"
        @click="activeMode = 'compare_all'"
      >
        雙軸對照
      </button>
    </div>

    <!-- ======================================================= -->
    <!-- 模式 A：矮高度水平雙欄自適應視圖 (< 235px 槽位專用，零截斷)   -->
    <!-- ======================================================= -->
    <div v-if="isCompactHeight" class="compact-h-body">
      <!-- 左側：Donut 環圖 -->
      <div class="compact-donut-col">
        <div class="tabler-donut-container" :style="{ width: `${size}px`, height: `${size}px` }">
          <svg :width="size" :height="size" class="tabler-svg">
            <circle :cx="size/2" :cy="size/2" :r="radius" fill="none" stroke="#212529" :stroke-width="strokeWidth" />
            <circle
              v-for="(s, idx) in slices"
              :key="s.label"
              :cx="size/2" :cy="size/2" :r="radius"
              fill="none"
              :stroke="s.strokeColor"
              :stroke-width="s.isHovered ? strokeWidth + 2 : strokeWidth"
              :stroke-dasharray="s.strokeDasharray"
              :stroke-dashoffset="s.strokeDashoffset"
              class="tabler-slice"
              :class="{ 'is-hovered': s.isHovered }"
              @mouseenter="hoveredIndex = idx"
              @mouseleave="hoveredIndex = null"
            />
          </svg>
          <div v-if="showCenterText" class="tabler-center-text">
            <span class="tc-val mono text-xs">{{ activeMode === 'raw_margin' ? '125k' : '1.4k' }}</span>
          </div>
        </div>
      </div>

      <!-- 右側：緊湊資產條列與微型風控指示 -->
      <div class="compact-data-col">
        <div class="compact-asset-rows">
          <div
            v-for="(item, idx) in currentItems"
            :key="item.label"
            class="compact-asset-row"
            :class="{ 'is-active': hoveredIndex === idx }"
            @mouseenter="hoveredIndex = idx"
            @mouseleave="hoveredIndex = null"
          >
            <div class="car-left">
              <span class="dot-indicator" :style="{ backgroundColor: item.color, boxShadow: `0 0 5px ${item.color}66` }"></span>
              <span class="car-sym">{{ (item as any).symbol || item.shortLabel }}</span>
            </div>
            <div class="car-right mono">
              <span class="car-pct" :style="{ color: item.color }">{{ item.pct_share }}%</span>
              <span class="car-val">{{ formatUsdt((item as any).nominal_usdt || (item as any).raw_usdt) }} <span class="car-u">U</span></span>
            </div>
          </div>
        </div>

        <div class="compact-risk-strip">
          <span class="c-metric"><span class="cm-lbl">槓桿</span><span class="cm-val mono text-success">0.01x</span></span>
          <span class="c-metric"><span class="cm-lbl">在途</span><span class="cm-val mono text-accent">213 U</span></span>
          <span class="c-metric"><span class="cm-lbl">可用</span><span class="cm-val mono text-primary">375k U</span></span>
        </div>
      </div>
    </div>

    <!-- ======================================================= -->
    <!-- 模式 B：標準高資訊密度終端網格 (>= 235px 槽位，極致平衡)   -->
    <!-- ======================================================= -->
    <div v-else class="terminal-grid-body">
      <!-- 頂部置中 Tabler Donut (88px 精密幾何比例) -->
      <div class="donut-center-wrap">
        <div class="tabler-donut-container" :style="{ width: `${size}px`, height: `${size}px` }">
          <svg :width="size" :height="size" class="tabler-svg">
            <!-- 底環背景軌道 -->
            <circle :cx="size/2" :cy="size/2" :r="radius" fill="none" stroke="#212529" :stroke-width="strokeWidth" />
            <!-- 多幣種切片環 -->
            <circle
              v-for="(s, idx) in slices"
              :key="s.label"
              :cx="size/2" :cy="size/2" :r="radius"
              fill="none"
              :stroke="s.strokeColor"
              :stroke-width="s.isHovered ? strokeWidth + 2 : strokeWidth"
              :stroke-dasharray="s.strokeDasharray"
              :stroke-dashoffset="s.strokeDashoffset"
              class="tabler-slice"
              :class="{ 'is-hovered': s.isHovered }"
              @mouseenter="hoveredIndex = idx"
              @mouseleave="hoveredIndex = null"
            />
          </svg>
          <!-- 中心選配數值 -->
          <div v-if="showCenterText" class="tabler-center-text">
            <span class="tc-val mono">{{ activeMode === 'raw_margin' ? '125.4k' : '1,420' }}</span>
            <span class="tc-lbl">{{ activeMode === 'raw_margin' ? '總權益' : '總額度' }}</span>
          </div>
        </div>
      </div>

      <!-- 下方：2x2 對稱微型金融卡片矩陣 (極致工整、高資訊密度) -->
      <div class="layout-b-grid">
        <div
          v-for="(item, idx) in currentItems"
          :key="item.label"
          class="grid-card"
          :class="{ 'is-active': hoveredIndex === idx }"
          :style="{ borderLeftColor: item.color }"
          @mouseenter="hoveredIndex = idx"
          @mouseleave="hoveredIndex = null"
        >
          <div class="gc-top">
            <div class="gc-name">
              <span class="dot-indicator" :style="{ backgroundColor: item.color, boxShadow: `0 0 6px ${item.color}66` }"></span>
              <span class="gc-symbol">{{ (item as any).symbol || item.shortLabel }}</span>
            </div>
            <span class="gc-pct mono" :style="{ color: item.color }">{{ item.pct_share }}%</span>
          </div>
          <div class="gc-bot mono">
            <span class="gc-val">{{ formatUsdt((item as any).nominal_usdt || (item as any).raw_usdt) }}</span>
            <span class="gc-unit">USDT</span>
          </div>
        </div>

        <!-- 第 4 格：總額指標卡 (保持 2x2 對稱平衡，消弭空白) -->
        <div v-if="currentItems.length === 3" class="grid-card summary-card">
          <div class="gc-top">
            <div class="gc-name">
              <span class="dot-indicator" style="background-color: #94a3b8;"></span>
              <span class="gc-symbol" style="color: #94a3b8;">{{ totalSummary.shortLabel }}</span>
            </div>
            <span class="gc-pct mono" style="color: #94a3b8;">100%</span>
          </div>
          <div class="gc-bot mono">
            <span class="gc-val" style="color: #e2e8f0;">{{ formatUsdt(totalSummary.nominal_usdt) }}</span>
            <span class="gc-unit">USDT</span>
          </div>
        </div>
      </div>

      <!-- 底部簡約風控條 (100% 完整顯示，零截斷) -->
      <div class="tabler-quick-strip">
        <span class="c-metric"><span class="cm-lbl">槓桿</span><span class="cm-val mono text-success">0.01x</span></span>
        <span class="c-metric"><span class="cm-lbl">在途</span><span class="cm-val mono text-accent">213 U</span></span>
        <span class="c-metric"><span class="cm-lbl">可用</span><span class="cm-val mono text-primary">375k U</span></span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ======================================================= */
/* 定案樣式系統：Bloomberg 終端網格 · 專為 290px × 340px 打造 */
/* ======================================================= */

.donut-card.tabler-donut-style {
  background: transparent;
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  -webkit-font-smoothing: antialiased;
}

/* 1. 卡片頭部 (當獨立顯示時) */
.tabler-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.02);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.header-titles .card-title {
  font-size: 13px;
  font-weight: 700;
  color: #ffffff;
  margin: 0;
}

.header-titles .card-subtitle {
  font-size: 10.5px;
  color: #94a3b8;
  margin: 1px 0 0 0;
}

.center-mode-toggle {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #94a3b8;
  font-size: 9.5px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 3px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;
}

.center-mode-toggle:hover {
  color: #ffffff;
}

.center-mode-toggle.active {
  border-color: #f59e0b;
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.12);
}

/* 2. 業務視圖切換列 (4 等分 Micro-tabs) */
.view-mode-tabs-bar {
  display: flex;
  background: rgba(0, 0, 0, 0.25);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  padding: 2px;
}

.mode-tab {
  flex: 1;
  text-align: center;
  padding: 4px 0;
  background: transparent;
  border: none;
  border-radius: 2px;
  color: #94a3b8;
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.mode-tab:hover {
  color: #ffffff;
}

.mode-tab.active {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
  font-weight: 700;
}

/* 2.5 矮高度水平雙欄自適應視圖 (< 235px 槽位專用) */
.compact-h-body {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  gap: 12px;
  overflow: hidden;
  box-sizing: border-box;
}

.compact-donut-col {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.compact-data-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
}

.compact-asset-rows {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.compact-asset-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2.5px 6px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 3px;
  font-size: 11px;
  transition: all 0.15s ease;
}

.compact-asset-row:hover,
.compact-asset-row.is-active {
  background: rgba(255, 255, 255, 0.07);
}

.car-left {
  display: flex;
  align-items: center;
  gap: 5px;
}

.car-sym {
  font-weight: 700;
  color: #f1f5f9;
  font-size: 11px;
}

.car-right {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
}

.car-pct {
  font-weight: 700;
}

.car-val {
  color: #ffffff;
  font-weight: 600;
}

.car-u {
  font-size: 9px;
  color: #64748b;
}

.compact-risk-strip {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 2px;
  padding: 2px 6px;
  font-size: 9.5px;
}

/* 3. 網格本體容器 */
.terminal-grid-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 6px 8px 6px;
  overflow: hidden;
  box-sizing: border-box;
}

/* 4. Donut 圓環本體 (置中微型比例) */
.donut-center-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 2px 0;
  flex-shrink: 0;
}

.tabler-donut-container {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tabler-svg {
  transform: rotate(-90deg);
  overflow: visible;
}

.tabler-slice {
  transition: stroke-width 0.18s ease, opacity 0.18s ease;
  cursor: pointer;
}

.tabler-slice:hover,
.tabler-slice.is-hovered {
  opacity: 1;
}

.tabler-center-text {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  text-align: center;
}

.tc-val {
  font-size: 12px;
  font-weight: 800;
  color: #ffffff;
  line-height: 1.1;
}

.tc-lbl {
  font-size: 8px;
  font-weight: 600;
  color: #94a3b8;
  margin-top: 1px;
}

.dot-indicator {
  width: 5.5px;
  height: 5.5px;
  border-radius: 50%;
  flex-shrink: 0;
  display: inline-block;
}

/* 5. 2x2 對稱微型金融卡片網格 */
.layout-b-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  margin: 3px 0;
}

.grid-card {
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-left-width: 2.5px;
  border-radius: 3px;
  padding: 3.5px 5.5px;
  display: flex;
  flex-direction: column;
  gap: 1.5px;
  transition: all 0.15s ease;
  cursor: pointer;
}

.grid-card:hover,
.grid-card.is-active {
  background: rgba(255, 255, 255, 0.06);
}

.summary-card {
  border-left-color: #64748b !important;
  background: rgba(255, 255, 255, 0.015);
}

.gc-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.gc-name {
  display: flex;
  align-items: center;
  gap: 3.5px;
}

.gc-symbol {
  font-size: 10.5px;
  font-weight: 700;
  color: #f1f5f9;
}

.gc-pct {
  font-size: 10.5px;
  font-weight: 800;
}

.gc-bot {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.gc-val {
  font-size: 11px;
  font-weight: 700;
  color: #ffffff;
}

.gc-unit {
  font-size: 8px;
  color: #64748b;
  font-weight: 600;
}

/* 6. 底部風控條 */
.tabler-quick-strip {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 3px;
  padding: 3px 6px;
  margin-top: 3px;
  flex-shrink: 0;
}

.c-metric {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 9.5px;
}

.cm-lbl { color: #94a3b8; font-weight: 500; font-size: 9px; }
.cm-val { font-weight: 700; }

.mono {
  font-family: 'JetBrains Mono', 'SF Mono', 'Roboto Mono', 'Fira Code', Menlo, Monaco, Consolas, monospace;
}

.text-success { color: #65cba7 !important; }
.text-accent { color: #e8b45e !important; }
.text-primary { color: #e5e8ec !important; }

:global([data-theme="v0-reference"]) .mono,
:global([data-theme="v0-reference"]) .tabular-nums {
  font-family: var(--default-mono-font-family, "IBM Plex Mono", monospace) !important;
}

:global([data-theme="v0-reference"]) .text-success {
  color: var(--gain, #65cba7) !important;
}

:global([data-theme="v0-reference"]) .text-accent {
  color: var(--primary, #e8b45e) !important;
}

:global([data-theme="v0-reference"]) .text-primary {
  color: var(--foreground, #e5e8ec) !important;
}

:global([data-theme="v0-reference"]) .gc-symbol {
  font-size: 11px !important;
  font-weight: 500 !important;
  color: var(--foreground, #e5e8ec) !important;
}

:global([data-theme="v0-reference"]) .gc-pct {
  font-size: 11px !important;
  font-weight: 400 !important;
}

:global([data-theme="v0-reference"]) .gc-val {
  font-size: 11px !important;
  font-weight: 400 !important;
  color: var(--foreground, #e5e8ec) !important;
}

:global([data-theme="v0-reference"]) .gc-unit {
  font-size: 10px !important;
  color: var(--muted-foreground, #90969d) !important;
  font-weight: 400 !important;
}

:global([data-theme="v0-reference"]) .tc-val {
  font-size: 12px !important;
  font-weight: 500 !important;
  color: var(--foreground, #e5e8ec) !important;
}

:global([data-theme="v0-reference"]) .tc-lbl {
  font-size: 9px !important;
  font-weight: 400 !important;
  color: var(--muted-foreground, #90969d) !important;
}

:global([data-theme="v0-reference"]) .cm-lbl {
  color: var(--muted-foreground, #90969d) !important;
  font-weight: 400 !important;
  font-size: 10px !important;
}

:global([data-theme="v0-reference"]) .cm-val {
  font-size: 10px !important;
  font-weight: 400 !important;
}

:global([data-theme="v0-reference"]) .grid-card {
  background: var(--card, #13161a) !important;
  border: 1px solid var(--border, #282c31) !important;
}
</style>
