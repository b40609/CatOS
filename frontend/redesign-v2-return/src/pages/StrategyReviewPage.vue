<script setup lang="ts">
import { ref, computed } from 'vue';

type ReviewPeriod = '7D' | '30D' | '90D' | 'ALL';
const currentPeriod = ref<ReviewPeriod>('30D');

// KPI 指標數據
const metrics = computed(() => {
  if (currentPeriod.value === '7D') {
    return {
      maxDd: -2.85,
      maxDdDuration: '1 天 6 小時',
      calmarRatio: 4.12,
      sharpeRatio: 2.45,
      profitFactor: 2.68,
      avgRecoveryDays: '0.8 天'
    };
  }
  if (currentPeriod.value === '30D') {
    return {
      maxDd: -6.85,
      maxDdDuration: '4 天 18 小時',
      calmarRatio: 3.42,
      sharpeRatio: 2.18,
      profitFactor: 2.35,
      avgRecoveryDays: '1.6 天'
    };
  }
  return {
    maxDd: -9.40,
    maxDdDuration: '8 天 4 小時',
    calmarRatio: 2.85,
    sharpeRatio: 1.95,
    profitFactor: 2.10,
    avgRecoveryDays: '2.4 天'
  };
});

// 機器人回撤歸因
const botAttributions = ref([
  {
    name: 'BTC 波動網格 (Bot-01)',
    strategy: '動態網格',
    ddContribution: 4.18,
    pctOfTotal: 61,
    status: '需調整參數',
    statusType: 'warning',
    note: '單邊趨勢突破下軌造成浮虧，建議開啟 ATR 波動度自適應間距'
  },
  {
    name: 'ETH 雙向趨勢 (Bot-02)',
    strategy: 'EMA 趨勢突破',
    ddContribution: 1.92,
    pctOfTotal: 28,
    status: '運作正常',
    statusType: 'success',
    note: '震盪市假突破停損 2 次，整體回撤仍在合理統計區間'
  },
  {
    name: 'SOL 資金費率套利 (Bot-03)',
    strategy: '跨期現基差套利',
    ddContribution: 0.75,
    pctOfTotal: 11,
    status: '優異穩健',
    statusType: 'success',
    note: '僅在費率反轉時產生微幅滑價損耗，回撤平滑'
  }
]);

// 策略改進指引
const improvementTips = ref([
  {
    id: 1,
    title: '網格策略防單邊破網優化',
    action: '為 Bot-01 引入「大盤趨勢判定濾鏡」',
    detail: '當 BTC 日線跌破 MA30 時，網格自動暫停下方新掛單，可將歷史回撤深度壓低 35%。'
  },
  {
    id: 2,
    title: '回撤期停機保險絲（Circuit Breaker）設定',
    action: '設定動態回撤達 -5.0% 時將新開倉部位縮減 50%',
    detail: '可在極端震盪行情中保留更多可用保證金，避免被動去槓桿。'
  },
  {
    id: 3,
    title: '多空曝險相關性對沖',
    action: '降低 ETH 與 BTC 同向多頭部位重疊度',
    detail: '本次最大回撤期間多頭重疊度高達 88%，適度配置反向中性策略可有效平滑水下時間。'
  }
]);
</script>

<template>
  <div class="strategy-review-page">
    <!-- Header 頂部動作列 -->
    <div class="review-header">
      <div class="header-left">
        <h2 class="page-title">策略覆盤 · Strategy Review</h2>
        <span class="page-subtitle">實戰績效診斷 · 水下回撤分析 · 策略歸因改進</span>
      </div>
      <div class="header-right">
        <div class="period-selector" role="group" aria-label="覆盤分析週期">
          <button
            v-for="p in (['7D', '30D', '90D', 'ALL'] as ReviewPeriod[])"
            :key="p"
            type="button"
            :class="['period-btn', { active: currentPeriod === p }]"
            @click="currentPeriod = p"
          >
            {{ p }}
          </button>
        </div>
      </div>
    </div>

    <!-- 頂部 KPI 卡片列 -->
    <div class="kpi-grid">
      <div class="kpi-card highlight-danger">
        <div class="kpi-label">歷史最大回撤 (Max DD)</div>
        <div class="kpi-value text-risk font-mono">{{ metrics.maxDd.toFixed(2) }}%</div>
        <div class="kpi-sub">
          <span>風控門檻: -15.00%</span>
          <span class="safe-badge">餘裕安全</span>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">最長水下持續期</div>
        <div class="kpi-value text-accent font-mono">{{ metrics.maxDdDuration }}</div>
        <div class="kpi-sub">
          <span>平均修復: {{ metrics.avgRecoveryDays }}</span>
          <span class="status-tag">目前已脫離水下</span>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">卡瑪比率 (Calmar Ratio)</div>
        <div class="kpi-value text-gain font-mono">{{ metrics.calmarRatio.toFixed(2) }}</div>
        <div class="kpi-sub text-muted">年化收益 / 最大回撤</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">夏普比率 (Sharpe Ratio)</div>
        <div class="kpi-value text-white font-mono">{{ metrics.sharpeRatio.toFixed(2) }}</div>
        <div class="kpi-sub text-muted">無風險利率 4.5% 計算</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-label">盈虧比 (Profit Factor)</div>
        <div class="kpi-value text-gain font-mono">{{ metrics.profitFactor.toFixed(2) }}</div>
        <div class="kpi-sub text-muted">毛盈利 / 毛虧損</div>
      </div>
    </div>

    <!-- 核心水下圖卡片 -->
    <div class="card underwater-card">
      <div class="card-header">
        <div class="card-title-group">
          <div class="card-title">深度回撤水下圖 (Drawdown Underwater Analysis)</div>
          <span class="card-subtitle">監控實盤資產自歷史高點的回撤幅度與水下時間長度</span>
        </div>
        <div class="card-meta font-mono text-2xs text-muted">
          <span class="legend-dot dot-zero"></span> 0% 零軸基準
          <span class="legend-dot dot-dd ml-3"></span> 實盤回撤曲線
          <span class="legend-dot dot-limit ml-3"></span> -15% 風控熔斷線
        </div>
      </div>

      <div class="card-body">
        <!-- SVG 水下圖渲染 -->
        <div class="chart-wrapper">
          <svg class="underwater-svg" viewBox="0 0 1000 220" preserveAspectRatio="none">
            <defs>
              <linearGradient id="underwaterGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#ed7665" stop-opacity="0.05" />
                <stop offset="100%" stop-color="#ed7665" stop-opacity="0.38" />
              </linearGradient>
            </defs>

            <!-- 網格橫線 -->
            <line x1="40" y1="20" x2="980" y2="20" stroke="#353a41" stroke-width="1.5" />
            <text x="30" y="24" fill="#90969d" font-family="monospace" font-size="10" text-anchor="end">0.0%</text>

            <line x1="40" y1="70" x2="980" y2="70" stroke="#24282e" stroke-dasharray="3 3" />
            <text x="30" y="74" fill="#90969d" font-family="monospace" font-size="10" text-anchor="end">-4.0%</text>

            <line x1="40" y1="120" x2="980" y2="120" stroke="#24282e" stroke-dasharray="3 3" />
            <text x="30" y="124" fill="#90969d" font-family="monospace" font-size="10" text-anchor="end">-8.0%</text>

            <line x1="40" y1="170" x2="980" y2="170" stroke="#24282e" stroke-dasharray="3 3" />
            <text x="30" y="174" fill="#90969d" font-family="monospace" font-size="10" text-anchor="end">-12.0%</text>

            <!-- -15% 熔斷線 -->
            <line x1="40" y1="200" x2="980" y2="200" stroke="#ef4444" stroke-dasharray="4 4" stroke-width="1.2" />
            <text x="30" y="204" fill="#ef4444" font-family="monospace" font-size="10" font-weight="bold" text-anchor="end">-15%</text>

            <!-- 水下曲線填充與邊線 -->
            <path
              d="M 60 20
                 L 120 25
                 L 180 35
                 L 240 20
                 L 300 30
                 L 360 50
                 L 420 90
                 L 480 106
                 L 540 71
                 L 600 48
                 L 660 26
                 L 720 20
                 L 780 33
                 L 840 24
                 L 900 20
                 L 960 20
                 L 960 20
                 L 60 20 Z"
              fill="url(#underwaterGrad)"
            />

            <path
              d="M 60 20
                 L 120 25
                 L 180 35
                 L 240 20
                 L 300 30
                 L 360 50
                 L 420 90
                 L 480 106
                 L 540 71
                 L 600 48
                 L 660 26
                 L 720 20
                 L 780 33
                 L 840 24
                 L 900 20
                 L 960 20"
              fill="none"
              stroke="#ed7665"
              stroke-width="2"
              stroke-linejoin="round"
            />

            <!-- 關鍵事件錨點 -->
            <circle cx="480" cy="106" r="4.5" fill="#ed7665" stroke="#0e1115" stroke-width="2" />
            <text x="480" y="128" fill="#ed7665" font-family="monospace" font-size="10" font-weight="bold" text-anchor="middle">
              -6.85% (最大回撤)
            </text>

            <circle cx="720" cy="20" r="4" fill="#22c55e" stroke="#0e1115" stroke-width="2" />
            <text x="720" y="38" fill="#22c55e" font-family="monospace" font-size="9" text-anchor="middle">
              修復脫離
            </text>
          </svg>
        </div>

        <!-- 水下診斷摘要 -->
        <div class="underwater-info-bar">
          <div class="info-tag">💡 水下診斷摘要</div>
          <div class="info-content">
            最近一次顯著回撤發生於 09/20 ~ 09/24（深度 -6.85%），主因聯準會升息預期導致 BTC 短線急跌 8%；系統於第 5 天完成部位減倉並在震盪中全額修復。整體回撤修復效率評級為 <strong class="text-gain">A (優異)</strong>。
          </div>
        </div>
      </div>
    </div>

    <!-- 底部雙欄：回撤歸因 vs 策略改進指引 -->
    <div class="review-bottom-grid">
      <!-- 卡片 1: 機器人回撤歸因 -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">機器人回撤歸因分析 (Drawdown Attribution)</div>
          <span class="badge badge-accent">佔總回撤比例</span>
        </div>
        <div class="card-body">
          <div class="bot-attr-list">
            <div v-for="(bot, idx) in botAttributions" :key="idx" class="bot-attr-item">
              <div class="bot-attr-head">
                <div class="bot-name-group">
                  <span class="bot-name">{{ bot.name }}</span>
                  <span class="bot-strat">{{ bot.strategy }}</span>
                </div>
                <div class="bot-pct-group">
                  <span class="bot-dd text-risk font-mono">-{{ bot.ddContribution.toFixed(2) }}%</span>
                  <span class="bot-share text-muted font-mono">({{ bot.pctOfTotal }}%)</span>
                </div>
              </div>

              <!-- 比例長條 -->
              <div class="progress-bar-bg">
                <div
                  class="progress-bar-fill"
                  :style="{ width: `${bot.pctOfTotal}%`, background: bot.pctOfTotal > 50 ? '#ed7665' : 'var(--accent)' }"
                ></div>
              </div>

              <div class="bot-note text-2xs text-secondary mt-1">
                {{ bot.note }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 卡片 2: 覆盤優化與策略改進指引 -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">策略覆盤與改進建議 (Optimization Insights)</div>
          <span class="badge badge-success">3 條高價值建議</span>
        </div>
        <div class="card-body">
          <div class="insights-list">
            <div v-for="tip in improvementTips" :key="tip.id" class="insight-item">
              <div class="insight-num">0{{ tip.id }}</div>
              <div class="insight-content">
                <div class="insight-title">{{ tip.title }}</div>
                <div class="insight-action text-accent">{{ tip.action }}</div>
                <div class="insight-detail text-muted text-xs">{{ tip.detail }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.strategy-review-page {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  overflow-y: auto;
  flex: 1;
}

/* Header */
.review-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 4px;
}

.page-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

.page-subtitle {
  font-size: 11.5px;
  color: var(--text-muted);
  margin-top: 2px;
  display: block;
}

.period-selector {
  display: inline-flex;
  background: #111418;
  border: 1px solid #24282e;
  border-radius: 4px;
  padding: 2px;
  gap: 2px;
}

.period-btn {
  background: transparent;
  border: none;
  color: #9da4ad;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.period-btn:hover {
  color: #ffffff;
  background: #181d24;
}

.period-btn.active {
  background: var(--accent);
  color: #09090b;
  font-weight: 700;
}

/* KPI Cards */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--space-3);
}

.kpi-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.kpi-card.highlight-danger {
  border-color: rgba(237, 118, 101, 0.35);
  background: linear-gradient(180deg, rgba(237, 118, 101, 0.06) 0%, var(--bg-surface) 100%);
}

.kpi-label {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
}

.kpi-value {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
}

.kpi-sub {
  font-size: 10.5px;
  color: var(--text-muted);
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 2px;
}

.safe-badge {
  font-size: 9.5px;
  color: #3fb950;
  background: rgba(46, 160, 67, 0.15);
  border: 1px solid rgba(46, 160, 67, 0.3);
  padding: 1px 5px;
  border-radius: 2px;
  font-weight: 600;
}

.status-tag {
  font-size: 9.5px;
  color: var(--accent);
  background: var(--accent-subtle);
  border: 1px solid var(--accent-border);
  padding: 1px 5px;
  border-radius: 2px;
}

/* Underwater Card */
.underwater-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
}

.card-title-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.card-subtitle {
  font-size: 11px;
  color: var(--text-muted);
}

.legend-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
}
.dot-zero { background: #353a41; }
.dot-dd { background: #ed7665; }
.dot-limit { background: #ef4444; }

.ml-3 { margin-left: 12px; }

.chart-wrapper {
  width: 100%;
  height: 220px;
  background: #080a0e;
  border: 1px solid #1a1e24;
  border-radius: 3px;
  overflow: hidden;
  position: relative;
}

.underwater-svg {
  width: 100%;
  height: 100%;
}

.underwater-info-bar {
  margin-top: 10px;
  display: flex;
  gap: 12px;
  background: #0d1117;
  border: 1px solid var(--border-secondary);
  border-radius: 3px;
  padding: 8px 12px;
  font-size: 11.5px;
  align-items: center;
}

.info-tag {
  font-weight: 700;
  color: var(--accent);
  white-space: nowrap;
}

.info-content {
  color: var(--text-secondary);
  line-height: 1.4;
}

/* Bottom Grid */
.review-bottom-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.bot-attr-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.bot-attr-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bot-attr-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.bot-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.bot-strat {
  font-size: 10.5px;
  color: var(--text-muted);
  margin-left: 8px;
}

.bot-dd {
  font-size: 12px;
  font-weight: 700;
}

.bot-share {
  font-size: 11px;
  margin-left: 6px;
}

.progress-bar-bg {
  width: 100%;
  height: 6px;
  background: #181d24;
  border-radius: 2px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

/* Insights List */
.insights-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.insight-item {
  display: flex;
  gap: 12px;
  padding: 8px 10px;
  background: #090c10;
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-xs);
}

.insight-num {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 800;
  color: var(--accent);
  opacity: 0.8;
}

.insight-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.insight-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
}

.insight-action {
  font-size: 11px;
  font-weight: 600;
}

.insight-detail {
  font-size: 10.5px;
  line-height: 1.4;
}

/* Utilities */
.text-risk { color: #ed7665; }
.text-gain { color: #3fb950; }
.text-accent { color: var(--accent); }
.text-white { color: #ffffff; }
.text-muted { color: var(--text-muted); }
.text-secondary { color: var(--text-secondary); }
.font-mono { font-family: var(--font-mono); }
</style>
