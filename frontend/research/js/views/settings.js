/**
 * catOS Prototype - Settings & Appearance Engine
 * Features:
 * - Professional Multi-Theme System: Muted Charcoal (Eye-care), Obsidian OLED, Bloomberg Amber, Nordic Slate, Default Terminal
 * - Fine-grained Brightness, Text Contrast, Accent Saturation, and Translucency Controls
 * - PnL Regional & Colorblind Palette Switcher (Green/Red, Red/Green, Blue/Orange)
 * - Information Density & UI Scale Tuning (Compact, Standard, Relaxed)
 * - Zen Minimalist Collapsible Sidebar Toggle
 * - Live Theme Preview Strip & Configuration Export/Import (JSON)
 * - Prototype Scenario Controller (Active, Clean Empty, Soft-Latch)
 * - Model Context Protocol (MCP) Integration Concept
 */

window.SettingsView = {
  render: function(state) {
    const data = window.CATOS_DATA;
    const mcp = data.settings.mcp;
    const scenario = state.scenario || 'active';
    const app = state.appearance || {
      preset: 'muted_charcoal',
      bgTone: 'charcoal',
      textContrast: 'soft',
      accentSaturation: 'muted',
      translucency: 'solid',
      elevation: 'subtle',
      fontScale: '100',
      tableDensity: 'standard',
      tabularMono: true,
      pnlPalette: 'traditional',
      chartGridOpacity: '50',
      zenSidebar: false
    };

    const presets = [
      {
        id: 'muted_charcoal',
        name: '護眼炭黑',
        tag: '推薦 · 消除刺眼',
        desc: '沉穩低反光炭黑底，柔和珍珠灰字，霧面低飽和金。長時盯盤無眩光、零酸澀。',
        colors: ['#12151b', '#202632', '#cfab4c', '#cdd3df', '#34d399']
      },
      {
        id: 'obsidian_oled',
        name: '黑曜石純黑',
        tag: 'OLED 極致',
        desc: '純黑 #000000 底色，搭配微階層面板與低反差灰白字，高階顯示器最深邃體驗。',
        colors: ['#000000', '#12161f', '#dcb347', '#d0d6e2', '#34d399']
      },
      {
        id: 'bloomberg_amber',
        name: '彭博終端暖琥珀',
        tag: '經典復古護眼',
        desc: '經典暗黑底搭配暖米灰字與暗琥珀金色系，極致溫潤，夜間無刺眼冷光。',
        colors: ['#090a0d', '#1b1f28', '#d9962e', '#d9cebc', '#34d399']
      },
      {
        id: 'nordic_slate',
        name: '深海冷灰',
        tag: '冷調青藍',
        desc: '深海冷藍灰底，搭配極光青藍作為強調色，完全無暖黃光干擾，沉穩科技感。',
        colors: ['#0b1016', '#1c2736', '#38bdf8', '#ccd6e4', '#38bdf8']
      },
      {
        id: 'default_terminal',
        name: '經典黑金',
        tag: '高對比高銳度',
        desc: '原始玄武黑階（#0b0d10）搭配高銳度亮琥珀金與白字，適合強光與高光環境。',
        colors: ['#0b0d10', '#1b1f27', '#e6b840', '#f0f2f5', '#34d399']
      }
    ];

    return `
      <div class="settings-view-container">

        <!-- 一、外觀、配色、深淺與排版引擎 (Appearance & Display Settings) -->
        <div class="settings-section">
          <div class="settings-section-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a7 7 0 0 0 0 14v6"/></svg>
            <span>外觀、主題配色與排版自訂 (Appearance & Display)</span>
            <span class="badge badge-gold">即時套用</span>
          </div>
          <div class="settings-section-desc">
            針對夜間長時盯盤、不同顯示器材質（OLED / IPS）與個人視覺舒適度調校。所有設定皆於毫秒級動態熱更新，並自動保存至本機。
          </div>

          <!-- 1. 主題預設集 (Theme Presets) -->
          <div style="font-size:12.5px; font-weight:600; color:var(--text-primary); margin-bottom:8px; display:flex; align-items:center; gap:6px;">
            <span>1. 專業主題預設集 (Theme Presets)</span>
            <span style="font-size:11px; font-weight:normal; color:var(--text-muted);">一鍵切換整體色彩光譜</span>
          </div>

          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:10px; margin-bottom:20px;">
            ${presets.map(p => {
              const isActive = app.preset === p.id;
              return `
                <div class="panel"
                     onclick="window.SettingsView.setThemePreset('${p.id}')"
                     style="padding:12px; cursor:pointer; border-color:${isActive ? 'var(--gold-primary)' : 'var(--border-subtle)'}; background:${isActive ? 'var(--bg-surface)' : 'var(--bg-panel)'}; transition:all 0.15s ease;">
                  <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:6px;">
                    <div>
                      <div style="font-weight:600; font-size:13px; color:var(--text-primary); display:flex; align-items:center; gap:6px;">
                        <span>${p.name}</span>
                        ${isActive ? '<span class="badge badge-gold" style="font-size:10px; padding:0 4px;">套用中</span>' : ''}
                      </div>
                      <div style="font-size:10.5px; color:var(--gold-primary); margin-top:2px;">${p.tag}</div>
                    </div>
                  </div>
                  <div style="font-size:11px; color:var(--text-muted); line-height:1.35; margin-bottom:8px;">
                    ${p.desc}
                  </div>
                  <!-- 色票預覽條 -->
                  <div style="display:flex; height:6px; border-radius:2px; overflow:hidden; border:1px solid rgba(255,255,255,0.06);">
                    ${p.colors.map(c => `<div style="flex:1; background:${c};"></div>`).join('')}
                  </div>
                </div>
              `;
            }).join('')}
          </div>

          <!-- 2. 細節深淺、對比度與色彩微調 (Fine-Tuning: Presets + Dynamic Sliders) -->
          <div style="font-size:12.5px; font-weight:600; color:var(--text-primary); margin-bottom:10px;">
            2. 細節深淺、對比度與色彩飽和度微調 (Fine-Tuning & Sliders)
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:20px;">

            <!-- 文字對比度與明暗 (解決白字刺眼) -->
            <div class="slider-control-card">
              <div class="slider-header-row">
                <div class="slider-title-wrap">
                  <div class="slider-main-title">文字明暗與眩光抑制 (Text Contrast)</div>
                  <div class="slider-sub-desc">抑制白字高光發散與刺眼光暈，提供柔和護眼觀看體驗。</div>
                </div>
                <span class="slider-val-tag" id="badge-textContrast">${app.textContrastValue || (app.textContrast === 'soft' ? 75 : (app.textContrast === 'crisp' ? 100 : 88))}%</span>
              </div>
              <div class="segmented-pill-group">
                <div class="segmented-pill ${app.textContrast === 'soft' && (!app.textContrastValue || app.textContrastValue === 75) ? 'active-all' : ''}"
                     id="pill-tc-soft"
                     onclick="window.SettingsView.setDimensionOption('textContrast', 'soft', 75)">
                  <span>柔和護眼 (75%)</span>
                </div>
                <div class="segmented-pill ${app.textContrast === 'standard' && (!app.textContrastValue || app.textContrastValue === 88) ? 'active-all' : ''}"
                     id="pill-tc-standard"
                     onclick="window.SettingsView.setDimensionOption('textContrast', 'standard', 88)">
                  <span>標準平衡 (88%)</span>
                </div>
                <div class="segmented-pill ${app.textContrast === 'crisp' && (!app.textContrastValue || app.textContrastValue === 100) ? 'active-all' : ''}"
                     id="pill-tc-crisp"
                     onclick="window.SettingsView.setDimensionOption('textContrast', 'crisp', 100)">
                  <span>高銳度 (100%)</span>
                </div>
              </div>
              <div class="slider-track-container">
                <span class="slider-bound-hint">55%</span>
                <input type="range" class="catos-slider" id="slider-textContrast" min="55" max="100" step="1"
                       value="${app.textContrastValue || (app.textContrast === 'soft' ? 75 : (app.textContrast === 'crisp' ? 100 : 88))}"
                       oninput="window.SettingsView.onSliderInput('textContrast', this.value)">
                <span class="slider-bound-hint right">100%</span>
              </div>
            </div>

            <!-- 強調色飽和度 (金色高光抑制) -->
            <div class="slider-control-card">
              <div class="slider-header-row">
                <div class="slider-title-wrap">
                  <div class="slider-main-title">強調色飽和度 (Accent Saturation)</div>
                  <div class="slider-sub-desc">控制介面金色、焦點與警示光暈的色彩飽和濃度。</div>
                </div>
                <span class="slider-val-tag" id="badge-accentSat">${app.accentSaturationValue || (app.accentSaturation === 'muted' ? 45 : (app.accentSaturation === 'vibrant' ? 100 : 72))}%</span>
              </div>
              <div class="segmented-pill-group">
                <div class="segmented-pill ${app.accentSaturation === 'muted' && (!app.accentSaturationValue || app.accentSaturationValue === 45) ? 'active-all' : ''}"
                     id="pill-as-muted"
                     onclick="window.SettingsView.setDimensionOption('accentSaturation', 'muted', 45)">
                  <span>低飽和霧金 (45%)</span>
                </div>
                <div class="segmented-pill ${app.accentSaturation === 'standard' && (!app.accentSaturationValue || app.accentSaturationValue === 72) ? 'active-all' : ''}"
                     id="pill-as-standard"
                     onclick="window.SettingsView.setDimensionOption('accentSaturation', 'standard', 72)">
                  <span>標準冷金 (72%)</span>
                </div>
                <div class="segmented-pill ${app.accentSaturation === 'vibrant' && (!app.accentSaturationValue || app.accentSaturationValue === 100) ? 'active-all' : ''}"
                     id="pill-as-vibrant"
                     onclick="window.SettingsView.setDimensionOption('accentSaturation', 'vibrant', 100)">
                  <span>高能亮金 (100%)</span>
                </div>
              </div>
              <div class="slider-track-container">
                <span class="slider-bound-hint">30%</span>
                <input type="range" class="catos-slider" id="slider-accentSat" min="30" max="100" step="1"
                       value="${app.accentSaturationValue || (app.accentSaturation === 'muted' ? 45 : (app.accentSaturation === 'vibrant' ? 100 : 72))}"
                       oninput="window.SettingsView.onSliderInput('accentSaturation', this.value)">
                <span class="slider-bound-hint right">100%</span>
              </div>
            </div>

            <!-- 頂部導覽列質感 (Translucency & Material) -->
            <div class="slider-control-card">
              <div class="slider-header-row">
                <div class="slider-title-wrap">
                  <div class="slider-main-title">導覽列質感 (Navbar Material & Translucency)</div>
                  <div class="slider-sub-desc">切換純沉浸實色、微透暗曜、透光磨砂或極光科技光暈。</div>
                </div>
                <span class="slider-val-tag" id="badge-translucency">${app.translucencyValue || (app.translucency === 'solid' ? 100 : (app.translucency === 'aero_frost' ? 55 : (app.translucency === 'cyber_glow' ? 70 : 80)))}%</span>
              </div>
              <div class="segmented-pill-group">
                <div class="segmented-pill ${app.translucency === 'solid' ? 'active-all' : ''}"
                     id="pill-tr-solid"
                     onclick="window.SettingsView.setDimensionOption('translucency', 'solid', 100)">
                  <span>全實底 (100%)</span>
                </div>
                <div class="segmented-pill ${app.translucency === 'subtle_glow' || app.translucency === 'blur_85' ? 'active-all' : ''}"
                     id="pill-tr-subtle_glow"
                     onclick="window.SettingsView.setDimensionOption('translucency', 'subtle_glow', 80)">
                  <span>微透暗曜 (80%)</span>
                </div>
                <div class="segmented-pill ${app.translucency === 'aero_frost' ? 'active-all' : ''}"
                     id="pill-tr-aero_frost"
                     onclick="window.SettingsView.setDimensionOption('translucency', 'aero_frost', 55)">
                  <span>透光磨砂 (55%)</span>
                </div>
                <div class="segmented-pill ${app.translucency === 'cyber_glow' ? 'active-all' : ''}"
                     id="pill-tr-cyber_glow"
                     onclick="window.SettingsView.setDimensionOption('translucency', 'cyber_glow', 70)">
                  <span>極光科技 (70%)</span>
                </div>
              </div>
              <div class="slider-track-container">
                <span class="slider-bound-hint">30%</span>
                <input type="range" class="catos-slider" id="slider-translucency" min="30" max="100" step="1"
                       value="${app.translucencyValue || (app.translucency === 'solid' ? 100 : (app.translucency === 'aero_frost' ? 55 : (app.translucency === 'cyber_glow' ? 70 : 80)))}"
                       oninput="window.SettingsView.onSliderInput('translucency', this.value)">
                <span class="slider-bound-hint right">100%</span>
              </div>
            </div>

            <!-- 漲跌色彩體系 -->
            <div class="slider-control-card">
              <div class="slider-header-row">
                <div class="slider-title-wrap">
                  <div class="slider-main-title">漲跌色彩體系 (PnL Palette)</div>
                  <div class="slider-sub-desc">支援亞洲慣用、國際標準與色盲/弱光友善藍橘模式。</div>
                </div>
                <span class="slider-val-tag">${app.pnlPalette === 'traditional' ? '綠漲/紅跌' : (app.pnlPalette === 'international' ? '紅漲/綠跌' : '藍漲/橘跌')}</span>
              </div>
              <div class="segmented-pill-group" style="height:34px;">
                <div class="segmented-pill ${app.pnlPalette === 'traditional' ? 'active-all' : ''}" onclick="window.SettingsView.updateAppearance('pnlPalette', 'traditional')">
                  <span style="color:var(--color-green); font-weight:600;">綠賺</span>/<span style="color:var(--color-red); font-weight:600;">紅虧</span>
                </div>
                <div class="segmented-pill ${app.pnlPalette === 'international' ? 'active-all' : ''}" onclick="window.SettingsView.updateAppearance('pnlPalette', 'international')">
                  <span style="color:var(--color-red); font-weight:600;">紅賺</span>/<span style="color:var(--color-green); font-weight:600;">綠虧</span>
                </div>
                <div class="segmented-pill ${app.pnlPalette === 'colorblind' ? 'active-all' : ''}" onclick="window.SettingsView.updateAppearance('pnlPalette', 'colorblind')">
                  <span style="color:#38bdf8; font-weight:600;">藍賺</span>/<span style="color:#fb923c; font-weight:600;">橘虧 (弱光)</span>
                </div>
              </div>
              <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">
                點擊立即切換全局 PnL 與 K 線行情顯示色彩。
              </div>
            </div>
          </div>

          <!-- 3. 排版尺寸、表格密度與視窗模式 (Density & Layout: Presets + Continuous Sliders) -->
          <div style="font-size:12.5px; font-weight:600; color:var(--text-primary); margin-bottom:10px;">
            3. 排版尺寸、表格密度與視窗模式 (Density & Continuous Zoom)
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; margin-bottom:20px;">
            <!-- UI 字體縮放 (80% ~ 130%) -->
            <div class="slider-control-card">
              <div class="slider-header-row">
                <div class="slider-title-wrap">
                  <div class="slider-main-title">UI 字體大小縮放</div>
                  <div class="slider-sub-desc">即時縮放全站字級與面板比例</div>
                </div>
                <span class="slider-val-tag" id="badge-fontScale">${app.fontScaleValue || app.fontScale || 100}%</span>
              </div>
              <div class="segmented-pill-group">
                <div class="segmented-pill ${app.fontScale === '88' ? 'active-all' : ''}"
                     id="pill-fs-88"
                     onclick="window.SettingsView.setDimensionOption('fontScale', '88', 88)">
                  <span>緊湊 88%</span>
                </div>
                <div class="segmented-pill ${app.fontScale === '100' ? 'active-all' : ''}"
                     id="pill-fs-100"
                     onclick="window.SettingsView.setDimensionOption('fontScale', '100', 100)">
                  <span>標準 100%</span>
                </div>
                <div class="segmented-pill ${app.fontScale === '112' ? 'active-all' : ''}"
                     id="pill-fs-112"
                     onclick="window.SettingsView.setDimensionOption('fontScale', '112', 112)">
                  <span>舒適 112%</span>
                </div>
                <div class="segmented-pill ${app.fontScale === '125' ? 'active-all' : ''}"
                     id="pill-fs-125"
                     onclick="window.SettingsView.setDimensionOption('fontScale', '125', 125)">
                  <span>大屏 125%</span>
                </div>
              </div>
              <div class="slider-track-container">
                <span class="slider-bound-hint">80%</span>
                <input type="range" class="catos-slider" id="slider-fontScale" min="80" max="130" step="1"
                       value="${app.fontScaleValue || app.fontScale || 100}"
                       oninput="window.SettingsView.onSliderInput('fontScale', this.value)">
                <span class="slider-bound-hint right">130%</span>
              </div>
            </div>

            <!-- 表格與日誌列高密度 (24px ~ 54px) -->
            <div class="slider-control-card">
              <div class="slider-header-row">
                <div class="slider-title-wrap">
                  <div class="slider-main-title">表格與日誌列高密度</div>
                  <div class="slider-sub-desc">控制所有表格與日誌行距高度</div>
                </div>
                <span class="slider-val-tag" id="badge-tableDensity">${app.tableDensityValue || (app.tableDensity === 'compact' ? 32 : (app.tableDensity === 'relaxed' ? 48 : 38))}px</span>
              </div>
              <div class="segmented-pill-group">
                <div class="segmented-pill ${app.tableDensity === 'ultra' ? 'active-all' : ''}"
                     id="pill-td-ultra"
                     onclick="window.SettingsView.setDimensionOption('tableDensity', 'ultra', 26)">
                  <span>極限 26px</span>
                </div>
                <div class="segmented-pill ${app.tableDensity === 'compact' ? 'active-all' : ''}"
                     id="pill-td-compact"
                     onclick="window.SettingsView.setDimensionOption('tableDensity', 'compact', 32)">
                  <span>高密 32px</span>
                </div>
                <div class="segmented-pill ${app.tableDensity === 'standard' ? 'active-all' : ''}"
                     id="pill-td-standard"
                     onclick="window.SettingsView.setDimensionOption('tableDensity', 'standard', 38)">
                  <span>標準 38px</span>
                </div>
                <div class="segmented-pill ${app.tableDensity === 'relaxed' ? 'active-all' : ''}"
                     id="pill-td-relaxed"
                     onclick="window.SettingsView.setDimensionOption('tableDensity', 'relaxed', 48)">
                  <span>寬鬆 48px</span>
                </div>
              </div>
              <div class="slider-track-container">
                <span class="slider-bound-hint">24px</span>
                <input type="range" class="catos-slider" id="slider-tableDensity" min="24" max="54" step="1"
                       value="${app.tableDensityValue || (app.tableDensity === 'compact' ? 32 : (app.tableDensity === 'relaxed' ? 48 : 38))}"
                       oninput="window.SettingsView.onSliderInput('tableDensity', this.value)">
                <span class="slider-bound-hint right">54px</span>
              </div>
            </div>

            <!-- 專注側邊欄 (Zen Mode & Width Slider) -->
            <div class="slider-control-card">
              <div class="slider-header-row">
                <div class="slider-title-wrap">
                  <div class="slider-main-title">專注側邊欄 (Sidebar & Zen)</div>
                  <div class="slider-sub-desc">&lt;100px 自動切入純圖標極簡專注模式</div>
                </div>
                <span class="slider-val-tag" id="badge-sidebarWidth">${app.sidebarWidth || (app.zenSidebar ? 58 : 238)}px</span>
              </div>
              <div class="segmented-pill-group">
                <div class="segmented-pill ${app.zenSidebar || app.sidebarWidth === 58 ? 'active-all' : ''}"
                     id="pill-sw-58"
                     onclick="window.SettingsView.setDimensionOption('sidebarWidth', 'zen', 58)">
                  <span>極簡專注 (58px)</span>
                </div>
                <div class="segmented-pill ${!app.zenSidebar && app.sidebarWidth === 210 ? 'active-all' : ''}"
                     id="pill-sw-210"
                     onclick="window.SettingsView.setDimensionOption('sidebarWidth', 'compact', 210)">
                  <span>緊湊 (210px)</span>
                </div>
                <div class="segmented-pill ${!app.zenSidebar && (!app.sidebarWidth || app.sidebarWidth === 238) ? 'active-all' : ''}"
                     id="pill-sw-238"
                     onclick="window.SettingsView.setDimensionOption('sidebarWidth', 'standard', 238)">
                  <span>標準 (238px)</span>
                </div>
                <div class="segmented-pill ${!app.zenSidebar && app.sidebarWidth === 270 ? 'active-all' : ''}"
                     id="pill-sw-270"
                     onclick="window.SettingsView.setDimensionOption('sidebarWidth', 'wide', 270)">
                  <span>寬闊 (270px)</span>
                </div>
              </div>
              <div class="slider-track-container">
                <span class="slider-bound-hint">58px</span>
                <input type="range" class="catos-slider" id="slider-sidebarWidth" min="58" max="280" step="2"
                       value="${app.sidebarWidth || (app.zenSidebar ? 58 : 238)}"
                       oninput="window.SettingsView.onSliderInput('sidebarWidth', this.value)">
                <span class="slider-bound-hint right">280px</span>
              </div>
            </div>
          </div>

          <!-- 4. 即時效果預覽與設定備份 (Live Preview & Backup) -->
          <div style="background:var(--bg-panel); border:1px solid var(--border-default); border-radius:var(--border-radius); padding:12px 14px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
              <span style="font-size:12px; font-weight:600; color:var(--text-primary); display:flex; align-items:center; gap:6px;">
                <span>即時舒適度展示條 (Live Comfort Preview)</span>
                <span style="font-size:11px; color:var(--text-muted); font-weight:normal;">[當前套用：${presets.find(p=>p.id===app.preset)?.name || '自訂'}]</span>
              </span>
              <div style="display:flex; gap:8px;">
                <button class="btn btn-sm btn-ghost" onclick="window.SettingsView.copyConfigJson()">複製配置 JSON</button>
                <button class="btn btn-sm btn-ghost" onclick="window.SettingsView.importConfigJson()">貼上匯入配置</button>
                <button class="btn btn-sm btn-ghost" onclick="window.SettingsView.resetAppearanceToRecommended()">還原護眼預設</button>
              </div>
            </div>

            <!-- 實際渲染預覽條 -->
            <div style="display:flex; align-items:center; gap:16px; padding:10px 14px; background:var(--bg-surface); border-radius:var(--border-radius-sm); border:1px solid var(--border-subtle); font-size:12.5px;">
              <span style="color:var(--text-primary); font-weight:600;">主要標題文字 (Text Primary)</span>
              <span style="color:var(--text-secondary);">次要輔助文字 (Text Secondary)</span>
              <span style="color:var(--text-muted); font-size:11.5px;">時戳 11:24:05 (Muted)</span>
              <span class="num" style="color:var(--color-green); font-weight:600;">+1,250.40 USDT (+2.4%)</span>
              <span class="num" style="color:var(--color-red); font-weight:600;">-380.00 USDT (-0.8%)</span>
              <button class="btn btn-sm btn-solid-gold" style="height:24px; padding:0 8px; font-size:11.5px;">操作按鈕 (Accent)</button>
            </div>
          </div>
        </div>

        <!-- 二、原型展示情境切換 (Prototype Scenario Controller) -->
        <div class="settings-section">
          <div class="settings-section-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
            <span>原型展示情境切換 (Prototype Scenario Controller)</span>
            <span class="badge badge-gold">評估專用</span>
          </div>
          <div class="settings-section-desc">
            切換後全域狀態將即時反應對應真實 UI 佈局，不依賴隨機跳動數據。
          </div>

          <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:12px; margin-bottom:14px;">
            <div class="panel" style="padding:14px; cursor:pointer; border-color:${scenario === 'active' ? 'var(--gold-primary)' : 'var(--border-default)'}; background:${scenario === 'active' ? 'var(--bg-surface)' : 'var(--bg-panel)'};" onclick="window.SettingsView.switchScenario('active')">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-weight:600; font-size:13.5px; color:var(--text-primary);">情境 A：活躍運作中</span>
                ${scenario === 'active' ? '<span class="badge badge-gold">當前選定</span>' : ''}
              </div>
              <div style="font-size:12px; color:var(--text-secondary); line-height:1.4;">
                3 個 Bot 運行中、帳戶資產 125,480.50 USDT、歷史回測數據完整、風控正常 NORMAL。
              </div>
            </div>

            <div class="panel" style="padding:14px; cursor:pointer; border-color:${scenario === 'empty' ? 'var(--gold-primary)' : 'var(--border-default)'}; background:${scenario === 'empty' ? 'var(--bg-surface)' : 'var(--bg-panel)'};" onclick="window.SettingsView.switchScenario('empty')">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-weight:600; font-size:13.5px; color:var(--text-primary);">情境 B：尚未啟動 Bot (空狀態)</span>
                ${scenario === 'empty' ? '<span class="badge badge-gold">當前選定</span>' : ''}
              </div>
              <div style="font-size:12px; color:var(--text-secondary); line-height:1.4;">
                嚴格不捏造帳戶數字，權益顯示「— USDT」，Bot 數量為 0，展示系統初次部屬時的空狀態導引。
              </div>
            </div>

            <div class="panel" style="padding:14px; cursor:pointer; border-color:${scenario === 'risk_latch' ? 'var(--gold-primary)' : 'var(--border-default)'}; background:${scenario === 'risk_latch' ? 'var(--bg-surface)' : 'var(--bg-panel)'};" onclick="window.SettingsView.switchScenario('risk_latch')">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-weight:600; font-size:13.5px; color:var(--text-primary);">情境 C：風控軟鎖存 (Soft-Latch)</span>
                ${scenario === 'risk_latch' ? '<span class="badge badge-gold">當前選定</span>' : ''}
              </div>
              <div style="font-size:12px; color:var(--text-secondary); line-height:1.4;">
                演示日損超標 (-2.85%) 觸發 Soft-Trip 時的 UI 鎖存警告、禁止新開倉與人工解除鎖存對話框。
              </div>
            </div>
          </div>

          <div style="display:flex; justify-content:flex-end;">
            <button class="btn btn-sm btn-ghost" onclick="window.SettingsView.resetPrototypeData()">
              重置原型儲存狀態 (Clear LocalStorage)
            </button>
          </div>
        </div>

        <!-- 三、Model Context Protocol (MCP) 架構概念 -->
        <div class="settings-section">
          <div class="settings-section-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
            <span>外部 Agent 連線與 MCP 架構概念展示</span>
            <span class="badge badge-cyan">Model Context Protocol</span>
          </div>
          <div class="settings-section-desc">
            catOS 規劃透過標準 MCP 協議提供唯讀策略 DSL、歷史回測數據查詢與沙盒優化調度接口。候選外部客戶端如下，目前均處於概念驗證與相容性評估中，不假裝已連線。
          </div>

          <div class="alert-banner alert-banner-info" style="margin-bottom:16px;">
            <div style="display:flex; align-items:center; gap:8px;">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
              <span>${mcp.evaluationNotice}</span>
            </div>
          </div>

          <div class="client-card-grid">
            ${mcp.clients.map(client => `
              <div class="client-card">
                <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
                  <span style="font-weight:600; font-size:14px; color:var(--text-primary);">${client.name}</span>
                  <span class="badge badge-amber">${client.statusBadge}</span>
                </div>
                <div style="font-size:12px; color:var(--gold-primary); margin-bottom:6px;">定位: ${client.role}</div>
                <div style="font-size:12px; color:var(--text-secondary); line-height:1.4; margin-bottom:10px;">
                  權限邊界: ${client.permissions}
                </div>
                <div style="font-size:11px; color:var(--text-muted); border-top:1px solid var(--border-subtle); padding-top:6px;">
                  通訊狀態: <span class="num">${client.lastPing}</span>
                </div>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- 四、執行底座與服務狀態 -->
        <div class="settings-section" style="margin-bottom:0;">
          <div class="settings-section-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 14 14"/></svg>
            <span>執行底座與服務狀態</span>
          </div>
          <div class="settings-section-desc">
            Supervisor 獨佔 API 憑證、網路連線、交易路由與 SQLite 寫入；Worker 僅負責純數據計算，無金鑰且不主動對外連網。
          </div>

          <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; font-size:12.5px;">
            <div style="padding:10px; background:var(--bg-surface); border-radius:var(--border-radius-sm); border:1px solid var(--border-subtle);">
              <div style="font-size:11px; color:var(--text-muted);">Supervisor 進程</div>
              <div class="num" style="font-weight:600; color:var(--color-green); margin-top:2px;">PID: ${data.meta.supervisor.pid} (ONLINE)</div>
            </div>
            <div style="padding:10px; background:var(--bg-surface); border-radius:var(--border-radius-sm); border:1px solid var(--border-subtle);">
              <div style="font-size:11px; color:var(--text-muted);">OKX WebSocket 連線</div>
              <div class="num" style="font-weight:600; color:var(--color-green); margin-top:2px;">21 ms (WSS / OKX-v5)</div>
            </div>
            <div style="padding:10px; background:var(--bg-surface); border-radius:var(--border-radius-sm); border:1px solid var(--border-subtle);">
              <div style="font-size:11px; color:var(--text-muted);">Worker 訊號計算</div>
              <div style="font-weight:600; color:var(--gold-primary); margin-top:2px;">Zero-Net (無聯網)</div>
            </div>
            <div style="padding:10px; background:var(--bg-surface); border-radius:var(--border-radius-sm); border:1px solid var(--border-subtle);">
              <div style="font-size:11px; color:var(--text-muted);">SQLite 風控鎖存資料庫</div>
              <div style="font-weight:600; color:var(--text-primary); margin-top:2px;">catos_state.db (Locked)</div>
            </div>
          </div>
        </div>
      </div>
    `;
  },

  setThemePreset: function(presetId) {
    const curr = Object.assign({}, window.appState.get('appearance'));
    curr.preset = presetId;
    if (presetId === 'muted_charcoal') {
      curr.textContrast = 'soft';
      curr.textContrastValue = 75;
      curr.accentSaturation = 'muted';
      curr.accentSaturationValue = 45;
    } else if (presetId === 'obsidian_oled') {
      curr.textContrast = 'soft';
      curr.textContrastValue = 80;
      curr.accentSaturation = 'standard';
      curr.accentSaturationValue = 72;
    } else if (presetId === 'bloomberg_amber') {
      curr.textContrast = 'soft';
      curr.textContrastValue = 88;
      curr.accentSaturation = 'standard';
      curr.accentSaturationValue = 80;
    } else if (presetId === 'nordic_slate') {
      curr.textContrast = 'standard';
      curr.textContrastValue = 88;
      curr.accentSaturation = 'muted';
      curr.accentSaturationValue = 50;
    } else if (presetId === 'default_terminal') {
      curr.textContrast = 'crisp';
      curr.textContrastValue = 100;
      curr.accentSaturation = 'vibrant';
      curr.accentSaturationValue = 100;
    }
    window.appState.set({ appearance: curr });
  },

  setDimensionOption: function(dim, optionId, sliderVal) {
    const curr = Object.assign({}, window.appState.get('appearance'));
    if (dim === 'textContrast') {
      curr.textContrast = optionId;
      curr.textContrastValue = sliderVal;
    } else if (dim === 'accentSaturation') {
      curr.accentSaturation = optionId;
      curr.accentSaturationValue = sliderVal;
    } else if (dim === 'translucency') {
      curr.translucency = optionId;
      curr.translucencyValue = sliderVal;
    } else if (dim === 'fontScale') {
      curr.fontScale = optionId;
      curr.fontScaleValue = sliderVal;
    } else if (dim === 'tableDensity') {
      curr.tableDensity = optionId;
      curr.tableDensityValue = sliderVal;
    } else if (dim === 'sidebarWidth') {
      if (optionId === 'zen' || sliderVal < 100) {
        curr.zenSidebar = true;
        curr.sidebarWidth = 58;
      } else {
        curr.zenSidebar = false;
        curr.sidebarWidth = sliderVal;
      }
    }
    window.appState.set({ appearance: curr });
  },

  onSliderInput: function(dim, rawVal) {
    const val = parseInt(rawVal, 10);
    const curr = Object.assign({}, window.appState.get('appearance'));

    if (dim === 'textContrast') {
      curr.textContrastValue = val;
      curr.textContrast = (val === 75 ? 'soft' : (val === 88 ? 'standard' : (val === 100 ? 'crisp' : 'custom')));
      const badge = document.getElementById('badge-textContrast');
      if (badge) badge.textContent = `${val}%`;
      ['soft', 'standard', 'crisp'].forEach(k => {
        const el = document.getElementById(`pill-tc-${k}`);
        if (el) el.classList.toggle('active-all', curr.textContrast === k);
      });
    } else if (dim === 'accentSaturation') {
      curr.accentSaturationValue = val;
      curr.accentSaturation = (val === 45 ? 'muted' : (val === 72 ? 'standard' : (val === 100 ? 'vibrant' : 'custom')));
      const badge = document.getElementById('badge-accentSat');
      if (badge) badge.textContent = `${val}%`;
      ['muted', 'standard', 'vibrant'].forEach(k => {
        const el = document.getElementById(`pill-as-${k}`);
        if (el) el.classList.toggle('active-all', curr.accentSaturation === k);
      });
    } else if (dim === 'translucency') {
      curr.translucencyValue = val;
      curr.translucency = (val === 100 ? 'solid' : (val === 80 ? 'subtle_glow' : (val === 55 ? 'aero_frost' : (val === 70 ? 'cyber_glow' : 'custom'))));
      const badge = document.getElementById('badge-translucency');
      if (badge) badge.textContent = `${val}%`;
      ['solid', 'subtle_glow', 'aero_frost', 'cyber_glow'].forEach(k => {
        const el = document.getElementById(`pill-tr-${k}`);
        if (el) el.classList.toggle('active-all', curr.translucency === k);
      });
    } else if (dim === 'fontScale') {
      curr.fontScaleValue = val;
      curr.fontScale = (val === 88 ? '88' : (val === 100 ? '100' : (val === 112 ? '112' : (val === 125 ? '125' : 'custom'))));
      const badge = document.getElementById('badge-fontScale');
      if (badge) badge.textContent = `${val}%`;
      ['88', '100', '112', '125'].forEach(k => {
        const el = document.getElementById(`pill-fs-${k}`);
        if (el) el.classList.toggle('active-all', curr.fontScale === k);
      });
    } else if (dim === 'tableDensity') {
      curr.tableDensityValue = val;
      curr.tableDensity = (val === 26 ? 'ultra' : (val === 32 ? 'compact' : (val === 38 ? 'standard' : (val === 48 ? 'relaxed' : 'custom'))));
      const badge = document.getElementById('badge-tableDensity');
      if (badge) badge.textContent = `${val}px`;
      ['ultra', 'compact', 'standard', 'relaxed'].forEach(k => {
        const el = document.getElementById(`pill-td-${k}`);
        if (el) el.classList.toggle('active-all', curr.tableDensity === k);
      });
    } else if (dim === 'sidebarWidth') {
      curr.sidebarWidth = val;
      curr.zenSidebar = (val < 100);
      const badge = document.getElementById('badge-sidebarWidth');
      if (badge) badge.textContent = `${val}px`;
      const p58 = document.getElementById('pill-sw-58');
      const p210 = document.getElementById('pill-sw-210');
      const p238 = document.getElementById('pill-sw-238');
      const p270 = document.getElementById('pill-sw-270');
      if (p58) p58.classList.toggle('active-all', curr.zenSidebar || val === 58);
      if (p210) p210.classList.toggle('active-all', !curr.zenSidebar && val === 210);
      if (p238) p238.classList.toggle('active-all', !curr.zenSidebar && val === 238);
      if (p270) p270.classList.toggle('active-all', !curr.zenSidebar && val === 270);
    }

    // Apply immediate reactive DOM reflection without re-rendering entire view
    window.appState.state.appearance = curr;
    window.appState.applyAppearanceToDom();

    // Debounced persist to LocalStorage
    if (this._saveTimer) clearTimeout(this._saveTimer);
    this._saveTimer = setTimeout(() => {
      window.appState.saveState();
    }, 200);
  },

  updateAppearance: function(key, val) {
    const curr = Object.assign({}, window.appState.get('appearance'));
    curr[key] = val;
    window.appState.set({ appearance: curr });
  },

  resetAppearanceToRecommended: function() {
    this.setThemePreset('muted_charcoal');
  },

  copyConfigJson: function() {
    const app = window.appState.get('appearance');
    const json = JSON.stringify(app, null, 2);
    if (navigator.clipboard) {
      navigator.clipboard.writeText(json).then(() => {
        alert('外觀配置 JSON 已複製到剪貼簿！');
      }).catch(() => {
        prompt('請複製以下外觀配置 JSON：', json);
      });
    } else {
      prompt('請複製以下外觀配置 JSON：', json);
    }
  },

  importConfigJson: function() {
    const input = prompt('請貼上外觀配置 JSON：');
    if (!input) return;
    try {
      const parsed = JSON.parse(input);
      window.appState.set({ appearance: Object.assign({}, window.appState.get('appearance'), parsed) });
      alert('外觀配置已成功套用！');
    } catch (e) {
      alert('無效的 JSON 格式，匯入失敗。');
    }
  },

  switchScenario: function(scen) {
    window.appState.set({ scenario: scen });
    alert(`已切換展示情境至：${scen === 'active' ? '情境 A：活躍運作中' : (scen === 'empty' ? '情境 B：全新空狀態 (未啟動 Bot)' : '情境 C：風控軟鎖存')}`);
  },

  resetPrototypeData: function() {
    if (confirm('確定重置本地所有快取與狀態嗎？將恢復至初始 Dashboard 頁面。')) {
      window.appState.resetAll();
    }
  }
};
