<script setup lang="ts">
import { computed } from 'vue';
import { usePreferences } from '@/state/usePreferences';

const {
  preferences,
  setLayout,
  setWorkspaceMode,
  setChartRange,
  setChartStyle,
  setBorderContrast,
  setCardDensity,
  setShowSidebarBadges,
  toggleBadge,
  setLanguage
} = usePreferences();

const isEn = computed(() => preferences.value.language === 'en');
</script>

<template>
  <div class="settings-page">


    <div class="settings-grid">
      <!-- Card 0: Workspace Card Layout & Tiling Engine Selection -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">工作台卡片縮放與拖移佈局 (Workspace Card Layout Engine)</div>
          <span class="badge badge-accent">3 大候選方案體驗中</span>
        </div>
        <div class="card-body form-body">
          <div class="form-group">
            <label class="form-label">卡片縮放與拖移互動版本</label>
            <div class="toggle-btn-row">
              <button
                type="button"
                :class="['btn btn-sm', preferences.workspaceMode === 'tiling' ? 'btn-primary' : 'btn-secondary']"
                @click="setWorkspaceMode('tiling')"
              >
                方案 A：無縫連續分割 (Seamless Tiling)
              </button>
              <button
                type="button"
                :class="['btn btn-sm', preferences.workspaceMode === 'freeform' ? 'btn-primary' : 'btn-secondary']"
                @click="setWorkspaceMode('freeform')"
              >
                方案 B：12 欄自由網格 (Freeform Grid)
              </button>
              <button
                type="button"
                :class="['btn btn-sm', preferences.workspaceMode === 'hybrid' ? 'btn-primary' : 'btn-secondary']"
                @click="setWorkspaceMode('hybrid')"
              >
                方案 C：旗艦混合工作台 (Hybrid Executive Desk ⭐)
              </button>
            </div>
            <div class="workspace-mode-description-box" style="margin-top: 12px; padding: 12px; background: var(--bg-surface-elevated); border: 1px solid var(--border-secondary); border-radius: var(--radius-sm); font-size: 12px;">
              <template v-if="preferences.workspaceMode === 'tiling'">
                <strong class="text-accent" style="display: block; margin-bottom: 4px;">方案 A：OKX / TradingView 無縫連續分割瓦片 (Seamless Tiling)</strong>
                <p class="text-secondary" style="margin: 0;">卡片 100% 緊貼鋪滿（零縫隙浪費），卡片之間均為滑順的連續分割線。按住金色分割線拖移即時改變相鄰卡片寬高比例，雙擊分割線自動均分，支援右上角 ↗ 單卡最大化聚焦。</p>
              </template>
              <template v-else-if="preferences.workspaceMode === 'freeform'">
                <strong class="text-accent" style="display: block; margin-bottom: 4px;">方案 B：Grafana 模組化 12 欄自由拖曳與縮放網格 (Freeform Grid)</strong>
                <p class="text-secondary" style="margin: 0;">卡片皆為獨立 12 欄響應式模組。拖曳卡片標題左側把手 ⋮⋮ 自由交換前後順序；拖曳卡片右下角 ⤡ 把手自由拉伸 3~12 欄寬度與高度；提供「ϟ 自動補滿」一鍵重整行寬與消除間隙。</p>
              </template>
              <template v-else>
                <strong class="text-accent" style="display: block; margin-bottom: 4px;">方案 C：旗艦混合專業工作台 (Hybrid Executive Desk ⭐ 定案標準)</strong>
                <p class="text-secondary" style="margin: 0;">結合專業交易雙模式架構：平常處於「檢視鎖定模式」，面板固若金湯防手滑誤觸；點擊「⚙ 調整版面」解鎖進入「微調編輯模式」，浮現金色虛線對齊導軌、拖曳把手與縮放握把。內建定案「戰情總覽」實戰平衡配置、一鍵自動補滿、復原歷史、元件庫抽屜與單卡聚焦放大！</p>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- Card 1: Sidebar Notification Badges Configuration -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">側邊欄分頁通知標籤 (Sidebar Badges)</div>
        </div>
        <div class="card-body form-body">

          <!-- Master Badge Toggle -->
          <div class="form-group">
            <div class="badge-master-row">
              <div>
                <label class="form-label mb-0">各分頁通知標籤總開關</label>
                <p class="form-help mt-1">控制是否在側邊欄各分頁右側展示狀態徽章 (Badges)。</p>
              </div>
              <div class="toggle-switch-wrap">
                <button
                  type="button"
                  :class="['btn btn-sm', preferences.showSidebarBadges ? 'btn-primary' : 'btn-secondary']"
                  @click="setShowSidebarBadges(!preferences.showSidebarBadges)"
                >
                  {{ preferences.showSidebarBadges ? '● 已開啟總通知' : '○ 已隱藏總通知' }}
                </button>
              </div>
            </div>
          </div>

          <!-- Individual Badges Sub-toggles -->
          <div class="badges-sub-box" :class="{ 'disabled-box': !preferences.showSidebarBadges }">
            <div class="sub-box-title">各分頁通知項目細部設定</div>

            <!-- Item 1: Bot Manager Badge -->
            <div class="badge-toggle-item">
              <div class="badge-info-col">
                <span class="item-name">機器人管理 (Bot Manager)</span>
                <span class="item-desc">運行中與總配置數量計數徽章</span>
              </div>
              <div class="badge-action-col">
                <span class="demo-badge badge-accent">1/3</span>
                <button
                  type="button"
                  class="btn btn-xs"
                  :class="preferences.badgeBotsEnabled ? 'btn-primary' : 'btn-secondary'"
                  :disabled="!preferences.showSidebarBadges"
                  @click="toggleBadge('badgeBotsEnabled')"
                >
                  {{ preferences.badgeBotsEnabled ? '顯示' : '隱藏' }}
                </button>
              </div>
            </div>

            <!-- Item 2: Risk Control Badge -->
            <div class="badge-toggle-item">
              <div class="badge-info-col">
                <span class="item-name">風控中心 (Risk Control)</span>
                <span class="item-desc">日損鎖存與安全守護狀態徽章 (SAFE / SOFT)</span>
              </div>
              <div class="badge-action-col">
                <span class="demo-badge badge-neutral">SAFE</span>
                <button
                  type="button"
                  class="btn btn-xs"
                  :class="preferences.badgeRiskEnabled ? 'btn-primary' : 'btn-secondary'"
                  :disabled="!preferences.showSidebarBadges"
                  @click="toggleBadge('badgeRiskEnabled')"
                >
                  {{ preferences.badgeRiskEnabled ? '顯示' : '隱藏' }}
                </button>
              </div>
            </div>

            <!-- Item 3: Market Intel Badge -->
            <div class="badge-toggle-item">
              <div class="badge-info-col">
                <span class="item-name">市場情報 (Market Intel)</span>
                <span class="item-desc">社群與鏈上情報模組研發狀態徽章</span>
              </div>
              <div class="badge-action-col">
                <span class="demo-badge badge-info">DEV</span>
                <button
                  type="button"
                  class="btn btn-xs"
                  :class="preferences.badgeMarketEnabled ? 'btn-primary' : 'btn-secondary'"
                  :disabled="!preferences.showSidebarBadges"
                  @click="toggleBadge('badgeMarketEnabled')"
                >
                  {{ preferences.badgeMarketEnabled ? '顯示' : '隱藏' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Card 2: Dashboard Layout & Visual Tokens -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">儀表板排版與圖表美學 (Dashboard & Charts)</div>
        </div>
        <div class="card-body form-body">
          <div class="form-group">
            <label class="form-label">選擇預設首頁布局</label>
            <div class="layout-toggle-row">
              <button
                type="button"
                :class="['btn', preferences.dashboardLayout === 'A' ? 'btn-primary' : 'btn-secondary']"
                @click="setLayout('A')"
              >
                布局 A：完整多面板工作區
              </button>
              <button
                type="button"
                :class="['btn', preferences.dashboardLayout === 'B' ? 'btn-primary' : 'btn-secondary']"
                @click="setLayout('B')"
              >
                布局 B：閱讀焦點集中
              </button>
            </div>
            <p class="form-help">
              布局 A 提供經典多面板高資訊密度視圖；布局 B 將視線聚焦於大型趨勢與待處理事項。
            </p>
          </div>

          <div class="form-group">
            <label class="form-label">預設圖表時間週期</label>
            <div class="range-toggle-row">
              <button
                type="button"
                :class="['btn btn-sm', preferences.chartRange === '7D' ? 'btn-primary' : 'btn-secondary']"
                @click="setChartRange('7D')"
              >
                7 天 (7D)
              </button>
              <button
                type="button"
                :class="['btn btn-sm', preferences.chartRange === '30D' ? 'btn-primary' : 'btn-secondary']"
                @click="setChartRange('30D')"
              >
                30 天 (30D)
              </button>
              <button
                type="button"
                :class="['btn btn-sm', preferences.chartRange === '90D' ? 'btn-primary' : 'btn-secondary']"
                @click="setChartRange('90D')"
              >
                90 天 (90D)
              </button>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">圖表視覺風格 (Chart Style)</label>
            <div class="range-toggle-row">
              <button
                type="button"
                :class="['btn btn-sm', preferences.chartStyle === 'refined' ? 'btn-primary' : 'btn-secondary']"
                @click="setChartStyle('refined')"
              >
                精緻柔光 (推薦)
              </button>
              <button
                type="button"
                :class="['btn btn-sm', preferences.chartStyle === 'minimal' ? 'btn-primary' : 'btn-secondary']"
                @click="setChartStyle('minimal')"
              >
                極簡純線
              </button>
              <button
                type="button"
                :class="['btn btn-sm', preferences.chartStyle === 'classic' ? 'btn-primary' : 'btn-secondary']"
                @click="setChartStyle('classic')"
              >
                原版風格
              </button>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">邊框對比與深邃度 (Border & Surface)</label>
            <div class="range-toggle-row">
              <button
                type="button"
                :class="['btn btn-sm', preferences.borderContrast === 'high' ? 'btn-primary' : 'btn-secondary']"
                @click="setBorderContrast('high')"
              >
                強化銳利 (推薦)
              </button>
              <button
                type="button"
                :class="['btn btn-sm', preferences.borderContrast === 'standard' ? 'btn-primary' : 'btn-secondary']"
                @click="setBorderContrast('standard')"
              >
                標準對比
              </button>
              <button
                type="button"
                :class="['btn btn-sm', preferences.borderContrast === 'deep_black' ? 'btn-primary' : 'btn-secondary']"
                @click="setBorderContrast('deep_black')"
              >
                深邃純黑
              </button>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">工作區資訊密度 (Information Density)</label>
            <div class="range-toggle-row">
              <button
                type="button"
                :class="['btn btn-sm', preferences.cardDensity === 'standard' ? 'btn-primary' : 'btn-secondary']"
                @click="setCardDensity('standard')"
              >
                標準密度 (16px)
              </button>
              <button
                type="button"
                :class="['btn btn-sm', preferences.cardDensity === 'compact' ? 'btn-primary' : 'btn-secondary']"
                @click="setCardDensity('compact')"
              >
                高密度緊湊 (12px)
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Card 3: Global Language & Localization (English vs 繁體中文) -->
      <div class="card" id="card-language-settings">
        <div class="card-header">
          <div class="card-title">
            <span style="margin-right: 6px;">🌐</span>
            {{ isEn ? 'Language & Localization' : '系統語言與國際化 (Language & Localization)' }}
          </div>
          <span class="badge badge-accent">
            {{ preferences.language === 'en' ? 'ENGLISH (US)' : '繁體中文 (ZH-TW)' }}
          </span>
        </div>
        <div class="card-body form-body">
          <div class="form-group">
            <label class="form-label">
              {{ isEn ? 'Interface Display Language' : '全域介面語言 (Global Interface Language)' }}
            </label>
            <div class="toggle-btn-row">
              <button
                type="button"
                :class="['btn btn-sm', preferences.language === 'zh-TW' ? 'btn-primary' : 'btn-secondary']"
                @click="setLanguage('zh-TW')"
              >
                繁體中文 (Traditional Chinese)
              </button>
              <button
                type="button"
                :class="['btn btn-sm', preferences.language === 'en' ? 'btn-primary' : 'btn-secondary']"
                @click="setLanguage('en')"
              >
                English (United States)
              </button>
            </div>

            <!-- Detailed Explanation & Quant Invariants Banner -->
            <div class="lang-mode-description-box" style="margin-top: 12px; padding: 12px; background: var(--bg-surface-elevated); border: 1px solid var(--border-secondary); border-radius: var(--radius-sm); font-size: 12px;">
              <template v-if="preferences.language === 'zh-TW'">
                <strong class="text-accent" style="display: block; margin-bottom: 4px;">繁體中文（台灣／香港 KOL 專業交易標準）</strong>
                <p class="text-secondary" style="margin: 0; line-height: 1.5; font-size: 11.5px;">
                  全域同步切換側邊欄導航、頂部工具列、面板標題與表格表頭。依據 OKX / TradingView / Bloomberg 專業終端標準，核心態勢標籤（▲ LONG、▼ SHORT）、合約代碼（BTCUSDT）與金融指標縮寫（uPnL、DD、USDT）受保護維持國際緊湊格式，避免字串折行破壞高密度矩陣對齊。
                </p>
              </template>
              <template v-else>
                <strong class="text-accent" style="display: block; margin-bottom: 4px;">English (US Quantitative Trading Terminal Standard)</strong>
                <p class="text-secondary" style="margin: 0; line-height: 1.5; font-size: 11.5px;">
                  Globally applied across navigation sidebar, top status bar, widget titles, and table headers. Posture badges (▲ LONG, ▼ SHORT) and financial metrics (uPnL, DD, USDT) use standardized compact typography for zero-waste visual density.
                </p>
              </template>
            </div>

            <!-- Protected Data Jargon Table/Summary -->
            <div class="jargon-spec-summary" style="margin-top: 8px; display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 11px;">
              <div style="padding: 8px; background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 4px;">
                <span class="text-muted" style="display: block; margin-bottom: 2px;">{{ isEn ? 'UI Chrome & Navigation' : '外層導航與標題 (Chrome)' }}</span>
                <span class="font-mono text-accent">{{ isEn ? 'Fully Localized' : '100% 依語言切換' }}</span>
              </div>
              <div style="padding: 8px; background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 4px;">
                <span class="text-muted" style="display: block; margin-bottom: 2px;">{{ isEn ? 'Core Trading Data Matrix' : '核心量化態勢 (Data Matrix)' }}</span>
                <span class="font-mono text-success">{{ isEn ? 'Protected TV / ISO' : '保留國際標準 ▲ LONG / USDT' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  overflow-y: auto;
  flex: 1;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-4);
  align-items: start;
}

.form-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.mb-0 { margin-bottom: 0; }
.mt-1 { margin-top: 2px; }

.form-help {
  font-size: 11.5px;
  color: var(--text-muted);
  line-height: 1.4;
}

.layout-toggle-row, .range-toggle-row, .toggle-btn-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.fixed-spec-banner {
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  padding: 10px 14px;
}

.spec-badge {
  align-self: flex-start;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--accent);
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 3px;
  padding: 2px 8px;
}

.spec-desc {
  font-size: 11.5px;
  color: var(--text-muted);
  line-height: 1.5;
}

/* Master Badge Toggle */
.badge-master-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background-color: #06080b;
  border: 1px solid var(--border-secondary);
  border-radius: 4px;
}

/* Sub-badges Configuration Box */
.badges-sub-box {
  background-color: #06080b;
  border: 1px solid var(--border-secondary);
  border-radius: 4px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: opacity 0.2s ease;
}
.disabled-box {
  opacity: 0.45;
  pointer-events: none;
}
.sub-box-title {
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 700;
  color: #7b8fa7;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.badge-toggle-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}
.badge-toggle-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.badge-info-col {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.item-name {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-primary);
}
.item-desc {
  font-size: 11px;
  color: var(--text-muted);
}

.badge-action-col {
  display: flex;
  align-items: center;
  gap: 12px;
}

.demo-badge {
  font-size: 10px;
  font-family: var(--font-mono);
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 3px;
  line-height: 1.2;
}
.badge-accent {
  background-color: var(--accent-subtle);
  color: var(--accent);
  border: 1px solid var(--accent-border);
}
.badge-neutral {
  background-color: rgba(46, 160, 67, 0.12);
  color: #3fb950;
  border: 1px solid rgba(46, 160, 67, 0.3);
}
.badge-info {
  background-color: rgba(88, 166, 255, 0.12);
  color: #58a6ff;
  border: 1px solid rgba(88, 166, 255, 0.3);
}

.btn-xs {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 3px;
}

</style>
