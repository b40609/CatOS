<script setup lang="ts">
import { usePreferences } from '@/state/usePreferences';

const {
  preferences,
  setLayout,
  setWorkspaceMode,
  setChartRange,
  setChartStyle,
  setBorderContrast,
  setCardDensity,
  setSidebarStyle,
  setSidebarWidth,
  resetSidebarWidth,
  setModeSwitcherPlacement,
  setUserProfilePlacement,
  setShowSidebarBadges,
  toggleBadge,
  resetToDefaults
} = usePreferences();
</script>

<template>
  <div class="settings-page">
    <Teleport to="#header-page-actions">
      <div class="header-actions-group">
        <button type="button" class="btn btn-sm btn-secondary" @click="resetToDefaults" title="重設所有自訂樣式為官方預設值">
          重設所有偏好
        </button>
      </div>
    </Teleport>

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
                <strong class="text-accent" style="display: block; margin-bottom: 4px;">方案 C：旗艦混合專業工作台 (Hybrid Executive Desk ⭐ 強烈推薦)</strong>
                <p class="text-secondary" style="margin: 0;">結合專業交易雙模式架構：平常處於「檢視鎖定模式」，面板固若金湯防手滑誤觸；點擊「⚙ 調整版面」解鎖進入「微調編輯模式」，浮現金色虛線對齊導軌、拖曳把手與縮放握把。內建 3 大官方實戰預設（戰情總覽 / 策略研究 / 夜間監控）、一鍵自動補滿、復原歷史、元件庫抽屜與單卡聚焦放大！</p>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- Card 1: Sidebar & Notification Badges Configuration -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">側邊欄外觀與分頁通知標籤 (Sidebar & Badges)</div>
          <span class="badge badge-accent">方案 D 定案推薦</span>
        </div>
        <div class="card-body form-body">
          <!-- Sidebar Style Choice -->
          <div class="form-group">
            <label class="form-label">側邊欄外觀風格</label>
            <div class="toggle-btn-row">
              <button
                type="button"
                :class="['btn btn-sm', preferences.sidebarStyle === 'A' ? 'btn-primary' : 'btn-secondary']"
                @click="setSidebarStyle('A')"
              >
                方案 A：經典融合 (雙行+分組小標)
              </button>
              <button
                type="button"
                :class="['btn btn-sm', preferences.sidebarStyle === 'B' ? 'btn-primary' : 'btn-secondary']"
                @click="setSidebarStyle('B')"
              >
                方案 B：1:1 Tabler 官方單行
              </button>
              <button
                type="button"
                :class="['btn btn-sm', preferences.sidebarStyle === 'C' ? 'btn-primary' : 'btn-secondary']"
                @click="setSidebarStyle('C')"
              >
                方案 C：極窄 Dock (64px)
              </button>
              <button
                type="button"
                :class="['btn btn-sm', preferences.sidebarStyle === 'D' ? 'btn-primary' : 'btn-secondary']"
                @click="setSidebarStyle('D')"
              >
                方案 D：旗艦發光工作台 (已定案)
              </button>
            </div>
            <p class="form-help">
              方案 D（已定案）採用 Bloomberg / OKX Web3 旗艦工作台風格，整合資產即時速覽小卡，並支援邊界無級拖移調整寬度 (190px ~ 420px) 與雙擊快速還原。
            </p>
          </div>

          <!-- Resizable Sidebar Width Control -->
          <div v-if="preferences.sidebarStyle !== 'C' && !preferences.sidebarFolded" class="form-group">
            <label class="form-label">側邊欄寬度 (支援滑鼠邊界拖移調整)</label>
            <div style="display: flex; align-items: center; gap: 12px;">
              <input
                type="range"
                min="190"
                max="420"
                :value="preferences.sidebarWidth || 245"
                @input="e => setSidebarWidth(Number((e.target as HTMLInputElement).value))"
                style="flex: 1; accent-color: var(--accent); cursor: pointer;"
              />
              <span class="font-mono text-accent" style="min-width: 55px; font-weight: 600;">{{ preferences.sidebarWidth || 245 }}px</span>
              <button type="button" class="btn btn-xs btn-secondary" @click="resetSidebarWidth">重設預設 (245px)</button>
            </div>
            <p class="form-help">
              除了此處滑桿，您可隨時將滑鼠懸停於側邊欄右側邊界直接拖移，或雙擊邊界瞬間重設回預設值。
            </p>
          </div>

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
                <span class="item-desc">Yaozi 社群與鏈上模組研發狀態徽章</span>
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

      <!-- Card 3: Mode Switcher Placement (4 UX Variants for User Selection) -->
      <div class="card mode-placement-card">
        <div class="card-header">
          <div class="card-title">交易帳戶/環境切換器排版 (Mode Switcher Placement)</div>
          <span class="badge badge-accent">4 種業界方案即時切換</span>
        </div>
        <div class="card-body form-body">
          <p class="form-help">
            請點選您偏好的交易環境切換鈕（本機 / Demo / Live）排版位置與互動風格，介面將即時套用：
          </p>

          <div class="placement-options-grid">
            <!-- Option 1: Linear / macOS Style -->
            <div
              class="placement-option-card"
              :class="{ active: preferences.modeSwitcherPlacement === 'sidebar_stack' }"
              @click="setModeSwitcherPlacement('sidebar_stack')"
            >
              <div class="opt-head">
                <span class="opt-badge">方案 1</span>
                <span class="opt-tag text-accent">推薦 · Linear / macOS 風格</span>
              </div>
              <div class="opt-title">側邊欄置頂滿寬膠囊 (Vertical Stacking)</div>
              <div class="opt-desc">
                品牌 LOGO 下方獨立一列滿寬 Segmented Control（各 33.3% 等分），視覺醒目大器，100% 貼合側邊欄寬度絕不破版。
              </div>
              <div class="opt-wireframe wireframe-stack">
                <div class="wire-brand-row">
                  <div class="wire-logo"></div>
                  <div class="wire-text"></div>
                </div>
                <div class="wire-mode-bar">
                  <span class="wire-btn active">本機</span>
                  <span class="wire-btn">Demo</span>
                  <span class="wire-btn">Live</span>
                </div>
              </div>
            </div>

            <!-- Option 2: OKX / TradingView Style -->
            <div
              class="placement-option-card"
              :class="{ active: preferences.modeSwitcherPlacement === 'top_header' }"
              @click="setModeSwitcherPlacement('top_header')"
            >
              <div class="opt-head">
                <span class="opt-badge">方案 2</span>
                <span class="opt-tag text-info">交易所標準 · OKX / TradingView</span>
              </div>
              <div class="opt-title">頂部全域狀態列右側 (Global Header Right)</div>
              <div class="opt-desc">
                移出側邊欄，改置於頂部 Header 右上角（緊鄰連線狀態）。符合交易所看盤視覺熱區，側邊欄頂部最乾淨純粹。
              </div>
              <div class="opt-wireframe wireframe-header">
                <div class="wire-topbar">
                  <div class="wire-page-title"></div>
                  <div class="wire-top-right">
                    <div class="wire-mode-pill">本機 · Demo · Live</div>
                    <div class="wire-telemetry">16ms</div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Option 3: Raycast / Slack Style -->
            <div
              class="placement-option-card"
              :class="{ active: preferences.modeSwitcherPlacement === 'dropdown_badge' }"
              @click="setModeSwitcherPlacement('dropdown_badge')"
            >
              <div class="opt-head">
                <span class="opt-badge">方案 3</span>
                <span class="opt-tag text-success">極簡俐落 · Raycast / Slack</span>
              </div>
              <div class="opt-title">LOGO 旁下拉標籤選單 (Dropdown Popover)</div>
              <div class="opt-desc">
                LOGO 旁僅保留精緻的 [ 本機 ▾ ] 狀態標籤，點擊浮現下拉選單切換，極度節省空間，整體視覺最極簡俐落。
              </div>
              <div class="opt-wireframe wireframe-dropdown">
                <div class="wire-brand-row">
                  <div class="wire-logo"></div>
                  <div class="wire-text"></div>
                  <div class="wire-dropdown-pill">本機 ▾</div>
                </div>
              </div>
            </div>

            <!-- Option 4: Terminal Dock Style -->
            <div
              class="placement-option-card"
              :class="{ active: preferences.modeSwitcherPlacement === 'sidebar_footer' }"
              @click="setModeSwitcherPlacement('sidebar_footer')"
            >
              <div class="opt-head">
                <span class="opt-badge">方案 4</span>
                <span class="opt-tag text-muted">終端底座 · Bloomberg / VS Code</span>
              </div>
              <div class="opt-title">側邊欄底部控制艙 (Sidebar Footer Dock)</div>
              <div class="opt-desc">
                置於側邊欄最底端，與「節點主機 127.0.0.1」合併為系統底座狀態控制艙，頂部空間 100% 留給導航標題。
              </div>
              <div class="opt-wireframe wireframe-footer">
                <div class="wire-footer-mode">
                  <span class="wire-btn active">本機</span>
                  <span class="wire-btn">Demo</span>
                  <span class="wire-btn">Live</span>
                </div>
                <div class="wire-node-row">節點: 127.0.0.1</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Card 4: User Profile & Settings Placement (個人面板與系統設定位置) -->
      <div class="card profile-placement-card">
        <div class="card-header">
          <div class="card-title">個人面板與系統設定位置 (User Profile & Settings Placement)</div>
          <span class="badge badge-accent">依指令雙位置皆已實作</span>
        </div>
        <div class="card-body form-body">
          <p class="form-help">
            「系統設定」已自側邊欄導航抽離，整合至使用者個人面板。您可自由選擇面板置放於左下角、右上角，或兩處同時啟用：
          </p>

          <div class="placement-options-grid profile-grid-3">
            <!-- Option 1: Bottom-Left Sidebar Footer (Linear / ChatGPT Style) -->
            <div
              class="placement-option-card"
              :class="{ active: preferences.userProfilePlacement === 'bottom_left' }"
              @click="setUserProfilePlacement('bottom_left')"
            >
              <div class="opt-head">
                <span class="opt-badge">位置 1</span>
                <span class="opt-tag text-accent">Linear / ChatGPT 風格</span>
              </div>
              <div class="opt-title">左下角側邊欄底座 (Sidebar Footer)</div>
              <div class="opt-desc">
                個人名片、PRO 標籤與設定集中於側邊欄最底端。展開時呈現精緻名片；收合或 Dock 模式下縮為 44px 頭像並以懸浮抽屜展開。
              </div>
              <div class="opt-wireframe wireframe-profile-bottom">
                <div class="wire-sidebar-box">
                  <div class="wire-nav-lines">
                    <span class="wire-nav-l"></span>
                    <span class="wire-nav-l"></span>
                    <span class="wire-nav-l"></span>
                  </div>
                  <div class="wire-user-card active-wire">
                    <div class="wire-u-avatar">K</div>
                    <div class="wire-u-meta">
                      <div class="wire-u-name">KOL 交易員</div>
                      <div class="wire-u-sub">OKX 專用子帳戶</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Option 2: Top-Right Global Header (OKX / TradingView Style) -->
            <div
              class="placement-option-card"
              :class="{ active: preferences.userProfilePlacement === 'top_right' }"
              @click="setUserProfilePlacement('top_right')"
            >
              <div class="opt-head">
                <span class="opt-badge">位置 2</span>
                <span class="opt-tag text-info">交易所標準 · OKX / TradingView</span>
              </div>
              <div class="opt-title">右上角全域狀態列 (Global Header Right)</div>
              <div class="opt-desc">
                以精簡膠囊型態整合於頂部 Header 右側，緊鄰 16ms 遙測監控。符合交易所專業看盤熱區，側邊欄保持最純粹的量化導航。
              </div>
              <div class="opt-wireframe wireframe-profile-top">
                <div class="wire-header-box">
                  <div class="wire-header-title">系統總覽</div>
                  <div class="wire-header-cluster">
                    <div class="wire-telemetry-tag">16ms</div>
                    <div class="wire-user-pill active-wire">
                      <div class="wire-u-avatar-sm">K</div>
                      <span>KOL 交易員 ▾</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Option 3: Both Positions Enabled (Recommended Dual-Access) -->
            <div
              class="placement-option-card"
              :class="{ active: preferences.userProfilePlacement === 'both' }"
              @click="setUserProfilePlacement('both')"
            >
              <div class="opt-head">
                <span class="opt-badge">位置 3</span>
                <span class="opt-tag text-success">推薦 · 雙向聯動</span>
              </div>
              <div class="opt-title">兩處同時啟用 (Both Positions)</div>
              <div class="opt-desc">
                同時在「左下角側邊欄」與「右上角頂部狀態列」展示個人面板。任何看盤或配置情境均可 1 鍵直達系統設定與金融不變量審查。
              </div>
              <div class="opt-wireframe wireframe-profile-both">
                <div class="wire-both-layout">
                  <div class="wire-both-header">
                    <div class="wire-h-dots"></div>
                    <div class="wire-h-pill-active">KOL 交易員 ▾</div>
                  </div>
                  <div class="wire-both-sidebar">
                    <div class="wire-both-footer-active">
                      <span class="wire-both-k">K</span>
                      <span>KOL 交易員 (OKX)</span>
                    </div>
                  </div>
                </div>
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
  background-color: rgba(220, 179, 71, 0.15);
  color: var(--accent);
  border: 1px solid rgba(220, 179, 71, 0.35);
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

/* ========================================================
   Mode Switcher Placement Option Cards (4 UX Variants)
   ======================================================== */
.mode-placement-card,
.profile-placement-card {
  grid-column: span 2;
}

.placement-options-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3);
}

.placement-option-card {
  background: #090c10;
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  padding: 14px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all 0.15s ease;
  user-select: none;
}

.placement-option-card:hover {
  background: #0f141d;
  border-color: #3b4c63;
}

.placement-option-card.active {
  background: #121822;
  border: 2px solid var(--accent);
}

.opt-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.opt-badge {
  font-size: 10px;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
}

.opt-tag {
  font-size: 10px;
  font-family: var(--font-mono);
  font-weight: 600;
}

.opt-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.opt-desc {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.4;
}

/* Wireframe Mini Previews */
.opt-wireframe {
  margin-top: 4px;
  background: #06080b;
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-xs);
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.wire-brand-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wire-logo {
  width: 14px;
  height: 14px;
  background: var(--accent);
  border-radius: 2px;
}

.wire-text {
  width: 60px;
  height: 6px;
  background: #252e3c;
  border-radius: 2px;
}

.wire-mode-bar {
  display: flex;
  background: #111620;
  border: 1px solid #1e2634;
  border-radius: 3px;
  padding: 2px;
  gap: 2px;
}

.wire-btn {
  flex: 1;
  text-align: center;
  font-size: 9px;
  font-family: var(--font-mono);
  padding: 2px 4px;
  border-radius: 2px;
  color: #7b8fa7;
}

.wire-btn.active {
  background: var(--accent);
  color: #080a0d;
  font-weight: 700;
}

.wire-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.wire-page-title {
  width: 48px;
  height: 6px;
  background: #252e3c;
  border-radius: 2px;
}

.wire-top-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

.wire-mode-pill {
  font-size: 9px;
  font-family: var(--font-mono);
  background: rgba(220, 179, 71, 0.15);
  color: var(--accent);
  border: 1px solid rgba(220, 179, 71, 0.3);
  padding: 1px 6px;
  border-radius: 3px;
}

.wire-telemetry {
  font-size: 8.5px;
  font-family: var(--font-mono);
  color: #3fb950;
  background: rgba(46, 160, 67, 0.12);
  padding: 1px 4px;
  border-radius: 2px;
}

.wire-dropdown-pill {
  font-size: 9px;
  font-family: var(--font-mono);
  font-weight: 600;
  background: rgba(220, 179, 71, 0.18);
  color: var(--accent);
  border: 1px solid rgba(220, 179, 71, 0.35);
  padding: 1px 6px;
  border-radius: 3px;
  margin-left: auto;
}

.wire-footer-mode {
  display: flex;
  background: #111620;
  border: 1px solid #1e2634;
  border-radius: 3px;
  padding: 2px;
  gap: 2px;
}

.wire-node-row {
  font-size: 8.5px;
  font-family: var(--font-mono);
  color: #55677d;
}

/* ========================================================
   Profile Placement Option Cards & Wireframes
   ======================================================== */
.profile-grid-3 {
  grid-template-columns: repeat(3, 1fr) !important;
}

@media (max-width: 1200px) {
  .profile-grid-3 {
    grid-template-columns: 1fr !important;
  }
}

.wireframe-profile-bottom {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  height: 72px;
}

.wire-sidebar-box {
  background: #090c10;
  border: 1px solid #1a2230;
  border-radius: 4px;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.wire-nav-lines {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.wire-nav-l {
  height: 3px;
  background: #1b2330;
  border-radius: 1px;
  width: 50%;
}

.wire-user-card {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #141b25;
  border: 1px solid rgba(220, 179, 71, 0.4);
  border-radius: 3px;
  padding: 4px 6px;
}

.wire-u-avatar {
  width: 18px;
  height: 18px;
  background: #1e2634;
  border: 1px solid var(--accent);
  color: var(--accent);
  font-size: 9px;
  font-weight: 700;
  border-radius: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.wire-u-meta {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.wire-u-name {
  font-size: 8.5px;
  font-weight: 600;
  color: #f0f4f8;
}

.wire-u-sub {
  font-size: 7.5px;
  color: #7b8ea5;
}

.wireframe-profile-top {
  display: flex;
  align-items: center;
  height: 72px;
}

.wire-header-box {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #090c10;
  border: 1px solid #1a2230;
  border-radius: 4px;
  padding: 8px;
}

.wire-header-title {
  font-size: 8.5px;
  color: #8fa0b5;
}

.wire-header-cluster {
  display: flex;
  align-items: center;
  gap: 6px;
}

.wire-telemetry-tag {
  font-size: 8px;
  font-family: var(--font-mono);
  color: #3fb950;
  background: rgba(46, 160, 67, 0.12);
  padding: 1px 4px;
  border-radius: 2px;
}

.wire-user-pill {
  display: flex;
  align-items: center;
  gap: 4px;
  background: #141b25;
  border: 1px solid rgba(220, 179, 71, 0.4);
  border-radius: 3px;
  padding: 2px 6px;
  font-size: 8.5px;
  color: var(--accent);
  font-weight: 600;
}

.wire-u-avatar-sm {
  width: 12px;
  height: 12px;
  background: #1e2634;
  color: var(--accent);
  border-radius: 2px;
  font-size: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.wireframe-profile-both {
  height: 72px;
  display: flex;
  align-items: center;
}

.wire-both-layout {
  width: 100%;
  background: #090c10;
  border: 1px solid #1a2230;
  border-radius: 4px;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.wire-both-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.wire-h-dots {
  width: 24px;
  height: 4px;
  background: #1a2332;
  border-radius: 2px;
}

.wire-h-pill-active {
  font-size: 7.5px;
  font-weight: 600;
  background: rgba(220, 179, 71, 0.15);
  border: 1px solid var(--accent);
  color: var(--accent);
  padding: 1px 4px;
  border-radius: 2px;
}

.wire-both-footer-active {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 7.5px;
  background: #141b25;
  border: 1px solid var(--accent);
  color: var(--accent);
  padding: 2px 4px;
  border-radius: 2px;
}

.wire-both-k {
  width: 10px;
  height: 10px;
  background: var(--accent);
  color: #080a0d;
  font-weight: 800;
  font-size: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 1px;
}
</style>
