<script setup lang="ts">
import { ref, computed } from 'vue';
import type { RiskState } from '@/contracts';

const props = withDefaults(
  defineProps<{
    risk?: RiskState | null;
    kpi?: {
      label: string;
      value: string;
      unit?: string;
      subText?: string;
      subType?: 'pos' | 'neg' | 'neutral';
      borderType?: 'accent' | 'warning' | 'danger' | 'success';
    };
    initialLayout?: 'layout_a' | 'layout_b' | 'layout_c';
  }>(),
  {
    initialLayout: 'layout_a'
  }
);

export type RiskCardLayout = 'layout_a' | 'layout_b' | 'layout_c';
const activeLayout = ref<RiskCardLayout>(props.initialLayout);

// 風控三大不變量真實數據
const leverageCurrent = 1.85;
const leverageLimit = 3.00;
const leveragePct = Math.round((leverageCurrent / leverageLimit) * 100); // 62%

const drawdownCurrent = 0.30;
const softLimit = 10.0;
const drawdownPct = Math.max(8, Math.round((drawdownCurrent / softLimit) * 100)); // 實際 3%，視覺底限 8%

const singleCurrent = 42;
const singleLimit = 50;
const singlePct = Math.round((singleCurrent / singleLimit) * 100); // 84%

const statusText = computed(() => props.kpi?.value || 'NORMAL');

// 240 度同心拱形幾何模型 (開角 210° 至 -30°，總跨度 240° = 4π/3)
function createArc(cx: number, cy: number, r: number) {
  const sin30 = 0.5;
  const cos30 = 0.8660254;
  const x1 = cx - r * cos30;
  const y1 = cy + r * sin30;
  const x2 = cx + r * cos30;
  const y2 = cy + r * sin30;
  const path = `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 1 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
  const totalLength = (4 * Math.PI * r) / 3;
  return { path, totalLength };
}

// 方案 A/B 滿版拱環：圓心 (100, 75)，半徑 68, 55, 42，緊貼 viewBox="35 3 130 112"
const arcMain_outer = createArc(100, 75, 68);
const arcMain_mid = createArc(100, 75, 55);
const arcMain_inner = createArc(100, 75, 42);

// 方案 C 左右分欄緊湊拱環：圓心 (65, 54)，半徑 50, 39, 28，viewBox="19 2 92 84"
const arcC_outer = createArc(65, 54, 50);
const arcC_mid = createArc(65, 54, 39);
const arcC_inner = createArc(65, 54, 28);

// V0 規範金融色盤
const colors = {
  leverage: '#e8b45e', // 黃銅金
  drawdown: '#ed7665', // 珊瑚粉橙
  single: '#65cba7',   // 薄荷青綠
  trackBg: '#282c31',  // 軌道底色
};
</script>

<template>
  <div class="risk-status-container">
    <!-- 頂部超薄微型切換膠囊 (高度僅 20px) -->
    <div class="layout-switch-bar">
      <button
        type="button"
        :class="['switch-pill', { active: activeLayout === 'layout_a' }]"
        @click="activeLayout = 'layout_a'"
        title="方案 A：Tabler 官方 240° 同心拱環儀表"
      >
        A Tabler 原版
      </button>
      <button
        type="button"
        :class="['switch-pill', { active: activeLayout === 'layout_b' }]"
        @click="activeLayout = 'layout_b'"
        title="方案 B：科技漸層 核心預算儀表"
      >
        B 科技漸層
      </button>
      <button
        type="button"
        :class="['switch-pill', { active: activeLayout === 'layout_c' }]"
        @click="activeLayout = 'layout_c'"
        title="方案 C：左右分欄 交易終端佈局"
      >
        C 左右終端
      </button>
    </div>

    <!-- ======================================================= -->
    <!-- 方案 A：【Tabler 官方 240° 同心拱環】(滿版飽滿自適應) -->
    <!-- ======================================================= -->
    <div v-if="activeLayout === 'layout_a'" class="layout-canvas layout-a">
      <div class="gauge-center-stage">
        <svg viewBox="35 3 130 112" preserveAspectRatio="xMidYMid meet" class="gauge-svg">
          <!-- 軌道底色 -->
          <path :d="arcMain_outer.path" fill="none" :stroke="colors.trackBg" stroke-width="5.5" stroke-linecap="round" />
          <path :d="arcMain_mid.path" fill="none" :stroke="colors.trackBg" stroke-width="5.5" stroke-linecap="round" />
          <path :d="arcMain_inner.path" fill="none" :stroke="colors.trackBg" stroke-width="5.5" stroke-linecap="round" />

          <!-- 進度弧線 -->
          <path
            :d="arcMain_outer.path"
            fill="none"
            :stroke="colors.leverage"
            stroke-width="5.5"
            stroke-linecap="round"
            :stroke-dasharray="`${(leveragePct / 100) * arcMain_outer.totalLength} ${arcMain_outer.totalLength}`"
            class="arc-stroke"
          />
          <path
            :d="arcMain_mid.path"
            fill="none"
            :stroke="colors.drawdown"
            stroke-width="5.5"
            stroke-linecap="round"
            :stroke-dasharray="`${(drawdownPct / 100) * arcMain_mid.totalLength} ${arcMain_mid.totalLength}`"
            class="arc-stroke"
          />
          <path
            :d="arcMain_inner.path"
            fill="none"
            :stroke="colors.single"
            stroke-width="5.5"
            stroke-linecap="round"
            :stroke-dasharray="`${(singlePct / 100) * arcMain_inner.totalLength} ${arcMain_inner.totalLength}`"
            class="arc-stroke"
          />

          <!-- 圓心清晰狀態文字 (精確落於內環中心，字串簡練絕不壓線) -->
          <text x="100" y="65" text-anchor="middle" class="svg-title-a">{{ statusText }}</text>
          <text x="100" y="78" text-anchor="middle" class="svg-sub-a">● DISARMED</text>
        </svg>
      </div>

      <!-- 底部 Tabler 原版水平圖例 Strip -->
      <div class="legend-strip-a">
        <div class="legend-chip">
          <span class="dot" :style="{ backgroundColor: colors.leverage }"></span>
          <span class="name">槓桿</span>
          <span class="val mono">{{ leverageCurrent }}x</span>
        </div>
        <div class="legend-chip">
          <span class="dot" :style="{ backgroundColor: colors.drawdown }"></span>
          <span class="name">回撤</span>
          <span class="val mono">-{{ drawdownCurrent }}%</span>
        </div>
        <div class="legend-chip">
          <span class="dot" :style="{ backgroundColor: colors.single }"></span>
          <span class="name">單幣</span>
          <span class="val mono">{{ singleCurrent }}%</span>
        </div>
      </div>
    </div>

    <!-- ======================================================= -->
    <!-- 方案 B：【科技漸層 核心預算儀表】(焦點槓桿率 + 3微型卡片) -->
    <!-- ======================================================= -->
    <div v-else-if="activeLayout === 'layout_b'" class="layout-canvas layout-b">
      <div class="gauge-center-stage">
        <svg viewBox="35 3 130 112" preserveAspectRatio="xMidYMid meet" class="gauge-svg">
          <defs>
            <linearGradient id="grad-lev" x1="0%" y1="100%" x2="100%" y2="0%">
              <stop offset="0%" stop-color="#d97706" />
              <stop offset="100%" stop-color="#fbbf24" />
            </linearGradient>
            <linearGradient id="grad-dd" x1="0%" y1="100%" x2="100%" y2="0%">
              <stop offset="0%" stop-color="#0284c7" />
              <stop offset="100%" stop-color="#38bdf8" />
            </linearGradient>
            <linearGradient id="grad-sg" x1="0%" y1="100%" x2="100%" y2="0%">
              <stop offset="0%" stop-color="#16a34a" />
              <stop offset="100%" stop-color="#4ade80" />
            </linearGradient>
          </defs>

          <!-- 軌道底色 -->
          <path :d="arcMain_outer.path" fill="none" :stroke="colors.trackBg" stroke-width="5.5" stroke-linecap="round" />
          <path :d="arcMain_mid.path" fill="none" :stroke="colors.trackBg" stroke-width="5.5" stroke-linecap="round" />
          <path :d="arcMain_inner.path" fill="none" :stroke="colors.trackBg" stroke-width="5.5" stroke-linecap="round" />

          <!-- 漸層進度弧線 -->
          <path
            :d="arcMain_outer.path"
            fill="none"
            stroke="url(#grad-lev)"
            stroke-width="5.5"
            stroke-linecap="round"
            :stroke-dasharray="`${(leveragePct / 100) * arcMain_outer.totalLength} ${arcMain_outer.totalLength}`"
            class="arc-stroke"
          />
          <path
            :d="arcMain_mid.path"
            fill="none"
            stroke="url(#grad-dd)"
            stroke-width="5.5"
            stroke-linecap="round"
            :stroke-dasharray="`${(drawdownPct / 100) * arcMain_mid.totalLength} ${arcMain_mid.totalLength}`"
            class="arc-stroke"
          />
          <path
            :d="arcMain_inner.path"
            fill="none"
            stroke="url(#grad-sg)"
            stroke-width="5.5"
            stroke-linecap="round"
            :stroke-dasharray="`${(singlePct / 100) * arcMain_inner.totalLength} ${arcMain_inner.totalLength}`"
            class="arc-stroke"
          />

          <!-- 拱心大數值：聚焦槓桿預算 -->
          <text x="100" y="65" text-anchor="middle" class="svg-val-b mono">{{ leverageCurrent }}x</text>
          <text x="100" y="78" text-anchor="middle" class="svg-label-b">槓桿預算</text>
        </svg>
      </div>

      <!-- 底部 3 格科技終端微卡 -->
      <div class="cards-grid-b">
        <div class="pill-card-b">
          <span class="pc-lbl" style="color: #f59e0b;">● 槓桿預算</span>
          <span class="pc-val mono">{{ leverageCurrent }}x / {{ leverageLimit }}x</span>
        </div>
        <div class="pill-card-b">
          <span class="pc-lbl" style="color: #38bdf8;">● 日損軟限</span>
          <span class="pc-val mono">-{{ drawdownCurrent }}% / -{{ softLimit }}%</span>
        </div>
        <div class="pill-card-b">
          <span class="pc-lbl" style="color: #22c55e;">● 單幣佔比</span>
          <span class="pc-val mono">{{ singleCurrent }}% / {{ singleLimit }}%</span>
        </div>
      </div>
    </div>

    <!-- ======================================================= -->
    <!-- 方案 C：【左右分欄 交易終端佈局】(左自適應弧環，右數據長條) -->
    <!-- ======================================================= -->
    <div v-else-if="activeLayout === 'layout_c'" class="layout-canvas layout-c">
      <!-- 左側自適應拱弧 -->
      <div class="c-left-pane">
        <svg viewBox="19 2 92 84" preserveAspectRatio="xMidYMid meet" class="gauge-svg">
          <path :d="arcC_outer.path" fill="none" :stroke="colors.trackBg" stroke-width="4.5" stroke-linecap="round" />
          <path :d="arcC_mid.path" fill="none" :stroke="colors.trackBg" stroke-width="4.5" stroke-linecap="round" />
          <path :d="arcC_inner.path" fill="none" :stroke="colors.trackBg" stroke-width="4.5" stroke-linecap="round" />

          <path
            :d="arcC_outer.path"
            fill="none"
            :stroke="colors.leverage"
            stroke-width="4.5"
            stroke-linecap="round"
            :stroke-dasharray="`${(leveragePct / 100) * arcC_outer.totalLength} ${arcC_outer.totalLength}`"
            class="arc-stroke"
          />
          <path
            :d="arcC_mid.path"
            fill="none"
            :stroke="colors.drawdown"
            stroke-width="4.5"
            stroke-linecap="round"
            :stroke-dasharray="`${(drawdownPct / 100) * arcC_mid.totalLength} ${arcC_mid.totalLength}`"
            class="arc-stroke"
          />
          <path
            :d="arcC_inner.path"
            fill="none"
            :stroke="colors.single"
            stroke-width="4.5"
            stroke-linecap="round"
            :stroke-dasharray="`${(singlePct / 100) * arcC_inner.totalLength} ${arcC_inner.totalLength}`"
            class="arc-stroke"
          />

          <text x="65" y="48" text-anchor="middle" class="svg-c-status">{{ statusText }}</text>
          <text x="65" y="58" text-anchor="middle" class="svg-c-sub mono">SAFE</text>
        </svg>
      </div>

      <!-- 右側進度條與數值 -->
      <div class="c-right-pane">
        <div class="c-metric-row">
          <div class="cm-head">
            <span class="cm-tag"><span class="c-dot" style="background-color: #f59e0b;"></span> 槓桿率</span>
            <span class="cm-num mono"><strong>{{ leverageCurrent }}x</strong> / {{ leverageLimit }}x</span>
          </div>
          <div class="cm-bar-track">
            <div class="cm-bar-fill" :style="{ width: `${leveragePct}%`, backgroundColor: '#f59e0b' }"></div>
          </div>
        </div>

        <div class="c-metric-row">
          <div class="cm-head">
            <span class="cm-tag"><span class="c-dot" style="background-color: #38bdf8;"></span> 日損軟限</span>
            <span class="cm-num mono"><strong>-{{ drawdownCurrent }}%</strong> / -{{ softLimit }}%</span>
          </div>
          <div class="cm-bar-track">
            <div class="cm-bar-fill" :style="{ width: `${drawdownPct}%`, backgroundColor: '#38bdf8' }"></div>
          </div>
        </div>

        <div class="c-metric-row">
          <div class="cm-head">
            <span class="cm-tag"><span class="c-dot" style="background-color: #22c55e;"></span> 單幣上限</span>
            <span class="cm-num mono"><strong>{{ singleCurrent }}%</strong> / {{ singleLimit }}%</span>
          </div>
          <div class="cm-bar-track">
            <div class="cm-bar-fill" :style="{ width: `${singlePct}%`, backgroundColor: '#22c55e' }"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ======================================================= */
/* 頂級向量自適應架構 · 隨容器動態縮放 · 零死板截圖感 */
/* ======================================================= */

.risk-status-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: transparent;
  color: #e2e8f0;
  box-sizing: border-box;
  overflow: hidden;
  user-select: none;
}

/* 1. 頂部微型切換膠囊 (高度 20px) */
.layout-switch-bar {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 4px;
  padding: 1px 6px;
  background: rgba(0, 0, 0, 0.25);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  flex-shrink: 0;
  height: 20px;
  box-sizing: border-box;
}

.switch-pill {
  flex: 1;
  max-width: 110px;
  height: 16px;
  line-height: 14px;
  padding: 0 4px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 3px;
  color: #94a3b8;
  font-size: 9.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
  text-align: center;
}

.switch-pill:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.switch-pill.active {
  background: rgba(245, 158, 11, 0.18);
  border-color: #f59e0b;
  color: #fbbf24;
  font-weight: 700;
}

/* 2. 主畫布容器 */
.layout-canvas {
  flex: 1;
  width: 100%;
  min-height: 0;
  display: flex;
  box-sizing: border-box;
  overflow: hidden;
}

/* 方案 A / B 通用排版 */
.layout-a,
.layout-b {
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  padding: 2px 8px 4px;
  gap: 2px;
}

/* 中央圖表舞台 (flex: 1 彈性自適應，撐滿可用空間) */
.gauge-center-stage {
  flex: 1;
  width: 100%;
  min-height: 0;
  display: flex;
  justify-content: center;
  align-items: center;
}

.gauge-svg {
  width: 100%;
  height: 100%;
  max-height: 100%;
  display: block;
  overflow: visible;
}

.arc-stroke {
  transition: stroke-dasharray 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

/* SVG 內部文字樣式 (清晰高銳利度) */
.svg-title-a {
  font-size: 14px;
  font-weight: 900;
  fill: #ffffff;
  letter-spacing: 0.8px;
}

.svg-sub-a {
  font-size: 7px;
  font-weight: 700;
  fill: #22c55e;
  letter-spacing: 0.5px;
}

.svg-val-b {
  font-size: 16px;
  font-weight: 900;
  fill: #fbbf24;
  letter-spacing: -0.3px;
}

.svg-label-b {
  font-size: 7.5px;
  font-weight: 600;
  fill: #94a3b8;
}

/* 方案 A 底部 Legend Strip */
.legend-strip-a {
  display: flex;
  justify-content: space-between;
  width: 100%;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  padding: 2.5px 8px;
  box-sizing: border-box;
  flex-shrink: 0;
}

.legend-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
}

.dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  flex-shrink: 0;
}

.name {
  color: #94a3b8;
  font-weight: 500;
}

.val {
  color: #ffffff;
  font-weight: 700;
}

/* 方案 B 底部 3 格微卡片 */
.cards-grid-b {
  display: flex;
  gap: 4px;
  width: 100%;
  box-sizing: border-box;
  flex-shrink: 0;
}

.pill-card-b {
  flex: 1;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 3px;
  padding: 2px 4px;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.pc-lbl {
  font-size: 8.5px;
  font-weight: 600;
  white-space: nowrap;
}

.pc-val {
  font-size: 9.5px;
  font-weight: 700;
  color: #ffffff;
  white-space: nowrap;
}

/* 方案 C 左右分欄 */
.layout-c {
  flex-direction: row;
  align-items: center;
  padding: 2px 8px;
  gap: 10px;
}

.c-left-pane {
  flex: 0 0 44%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
}

.svg-c-status {
  font-size: 10px;
  font-weight: 900;
  fill: #65cba7;
}

.svg-c-sub {
  font-size: 6px;
  font-weight: 700;
  fill: #90969d;
}

.c-right-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 3.5px;
  min-height: 0;
}

.c-metric-row {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.cm-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 9px;
}

.cm-tag {
  display: flex;
  align-items: center;
  gap: 3.5px;
  color: #94a3b8;
  font-weight: 500;
}

.c-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
}

.cm-num {
  color: #94a3b8;
  font-size: 9px;
}

.cm-num strong {
  color: #ffffff;
  font-weight: 700;
}

.cm-bar-track {
  width: 100%;
  height: 3px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 1.5px;
  overflow: hidden;
}

.cm-bar-fill {
  height: 100%;
  border-radius: 1.5px;
  transition: width 0.4s ease;
}

.mono {
  font-family: 'JetBrains Mono', 'SF Mono', 'Roboto Mono', Menlo, Consolas, monospace;
}

/* ======================================================= */
/* 容器查詢優化 (Container Queries)：隨卡片高度智能調節字級與間距 */
/* ======================================================= */

/* 1. 卡片拉大時 (min-height: 160px) */
@container (min-height: 160px) {
  .layout-a,
  .layout-b {
    padding: 6px 12px 10px;
    gap: 8px;
  }
  .svg-title-a {
    font-size: 18px;
  }
  .svg-sub-a {
    font-size: 9.5px;
  }
  .svg-val-b {
    font-size: 22px;
  }
  .svg-label-b {
    font-size: 10px;
  }
  .legend-strip-a {
    padding: 6px 12px;
  }
  .legend-chip {
    font-size: 11.5px;
    gap: 6px;
  }
  .dot {
    width: 6.5px;
    height: 6.5px;
  }
  .cards-grid-b {
    gap: 6px;
  }
  .pill-card-b {
    padding: 5px 8px;
    gap: 2px;
  }
  .pc-lbl {
    font-size: 10.5px;
  }
  .pc-val {
    font-size: 12px;
  }
  .c-metric-row {
    gap: 3px;
  }
  .cm-head {
    font-size: 10.5px;
  }
  .cm-bar-track {
    height: 4px;
  }
}

/* 2. 卡片極矮時 (max-height: 110px) */
@container (max-height: 110px) {
  .layout-switch-bar {
    height: 17px;
    padding: 0 4px;
  }
  .switch-pill {
    height: 14px;
    line-height: 12px;
    font-size: 8.5px;
  }
  .layout-a,
  .layout-b {
    padding: 1px 6px 2px;
    gap: 1px;
  }
  .legend-strip-a {
    padding: 1.5px 6px;
  }
  .legend-chip {
    font-size: 8.5px;
  }
  .cards-grid-b {
    gap: 2px;
  }
  .pill-card-b {
    padding: 1px 3px;
  }
  .pc-lbl {
    font-size: 7.5px;
  }
  .pc-val {
    font-size: 8.5px;
  }
}
</style>
