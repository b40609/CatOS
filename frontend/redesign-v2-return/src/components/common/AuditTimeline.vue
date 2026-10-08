<script setup lang="ts">
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import type { AuditLogItem } from '@/contracts';




const props = withDefaults(
  defineProps<{
    events?: AuditLogItem[];
    compact?: boolean;
    showHeader?: boolean;
    maxHeight?: string;
  }>(),
  {
    events: () => [],
    compact: false,
    showHeader: true,
    maxHeight: '100%',
  }
);

const emit = defineEmits<{
  (e: 'maximize'): void;
}>();

const router = useRouter();

// Default expand the first item like in the reference screenshot
const expandedId = ref<string | null>(null);

watch(
  () => props.events,
  (evts) => {
    if (evts && evts.length > 0 && !expandedId.value) {
      expandedId.value = evts[0].id;
    }
  },
  { immediate: true }
);

function toggleItem(id: string) {
  expandedId.value = expandedId.value === id ? null : id;
}

function navigateToLogs() {
  router.push('/logs');
}

function navigateToBots() {
  router.push('/bots');
}

function getItemSource(evt: AuditLogItem): string {
  if (evt.details && evt.details.source) {
    return String(evt.details.source);
  }
  if (evt.category === 'RISK') return 'RiskEngine';
  if (evt.category === 'WORKER') return 'StrategyWorker';
  if (evt.category === 'ORDER') return 'OrderGateway';
  if (evt.category === 'SUPERVISOR') return 'Supervisor';
  return 'SystemAudit';
}

function getItemDescription(evt: AuditLogItem): string {
  if (evt.details && evt.details.description) {
    return String(evt.details.description);
  }
  // Fallback to formatted details
  if (evt.details && Object.keys(evt.details).length > 0) {
    const parts = Object.entries(evt.details)
      .filter(([k]) => k !== 'source' && k !== 'description')
      .map(([k, v]) => `${k}: ${v}`);
    if (parts.length > 0) {
      return parts.join(' · ');
    }
  }
  return evt.message;
}
</script>

<template>
  <div class="incident-stream-root" :class="{ 'is-compact': compact }">
    <!-- Stream Header matching user reference image -->
    <div v-if="showHeader" class="stream-header">
      <div class="header-title-group">
        <span class="main-title">系統日誌動態</span>
      </div>

      <div class="header-action-group">
        <button type="button" class="btn-all-logs" @click="navigateToLogs" title="前往日誌總覽頁">
          完整日誌 →
        </button>
        <button type="button" class="btn-fullscreen-toggle" @click="emit('maximize')" title="全螢幕聚焦檢視">
          ⤢
        </button>
      </div>
    </div>



    <!-- Scrollable Stream Container -->
    <div class="stream-scroll-area" :style="{ maxHeight }">
      <div v-if="events.length" class="stream-timeline">
        <!-- Incident Items -->
        <div
          v-for="(evt, idx) in events"
          :key="evt.id"
          class="incident-entry"
          :class="[
            `level-${evt.level.toLowerCase()}`,
            {
              'is-expanded': expandedId === evt.id,
              'is-first': idx === 0,
              'is-last': idx === events.length - 1
            }
          ]"
        >
          <!-- Left Status Dot on Timeline -->
          <div class="dot-col">
            <span
              class="incident-dot"
              :class="[
                evt.level === 'WARN' ? 'dot-warn' : (evt.level === 'ERROR' ? 'dot-error' : 'dot-info')
              ]"
            ></span>
          </div>

          <!-- Right Content Area -->
          <div class="incident-content">
            <!-- Row Header: Timestamp + Level Badge + Message Title + Arrow -->
            <div class="entry-row" @click="toggleItem(evt.id)">
              <span class="entry-time mono tabular-nums">{{ evt.timestamp }}</span>

              <span
                class="entry-badge mono"
                :class="[
                  evt.level === 'WARN' ? 'badge-warn' : (evt.level === 'ERROR' ? 'badge-error' : 'badge-info')
                ]"
              >
                {{ evt.level }}
              </span>

              <span class="entry-title">{{ evt.message }}</span>

              <span class="entry-caret">
                <span v-if="expandedId === evt.id" class="caret-arrow caret-up">▲</span>
                <span v-else class="caret-arrow caret-down">▼</span>
              </span>
            </div>

            <!-- Expanded Drawer Box (matches user image) -->
            <div v-if="expandedId === evt.id" class="entry-drawer">
              <!-- Description Text -->
              <p class="drawer-desc">
                {{ getItemDescription(evt) }}
              </p>

              <!-- Footer with Quick Links on Left & Source on Right -->
              <div class="drawer-footer">
                <div class="quick-links">
                  <a href="javascript:void(0)" class="link-gold" @click.stop="navigateToBots">
                    查看 Bot 詳情 →
                  </a>
                  <a href="javascript:void(0)" class="link-subtle" @click.stop="navigateToLogs">
                    相關日誌 →
                  </a>
                </div>

                <div class="source-tag">
                  <span class="source-label">來源:</span>
                  <span class="source-value">{{ getItemSource(evt) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="stream-empty-safe">
        <div class="safe-badge-pill">
          <span class="safe-pulse-dot"></span>
          <span class="safe-status-text">系統運作正常 · 無異常警報</span>
        </div>
        <p class="safe-desc">過去 24 小時未偵測到風控攔截、滑價異常或執行錯誤。</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.incident-stream-root {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  font-family: inherit;
  color: var(--text-primary);
  background: transparent;
}

/* Header */
.stream-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 4px 12px 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  margin-bottom: 10px;
  flex-shrink: 0;
}

.header-title-group {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.main-title {
  font-size: 13px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.3px;
}

.sub-title {
  font-size: 10px;
  font-weight: 600;
  color: #64748b;
  letter-spacing: 1.2px;
}

.header-action-group {
  display: flex;
  align-items: center;
  gap: 8px;
}



.btn-all-logs {
  background: transparent;
  border: none;
  color: #eab308;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  padding: 2px 4px;
  transition: all 0.15s ease;
}

.btn-all-logs:hover {
  color: #facc15;
  text-decoration: underline;
}

.btn-fullscreen-toggle {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-xs);
  color: #94a3b8;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-fullscreen-toggle:hover {
  background: rgba(51, 65, 85, 0.8);
  color: #ffffff;
  border-color: rgba(255, 255, 255, 0.2);
}

/* Scroll Area */
.stream-scroll-area {
  flex: 1;
  min-height: 0;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 4px;
}

/* Stream Timeline Spine - Unbroken continuous rail */
.stream-timeline {
  position: relative;
  display: flex;
  flex-direction: column;
}

/* Continuous 1px vertical rail strictly unbroken from top dot to bottom */
.stream-timeline::before {
  content: '';
  position: absolute;
  left: 8px;
  top: 9px;
  bottom: 8px;
  width: 1px;
  background: #1e3a5f;
  transform: translateX(-50%);
  z-index: 1;
  pointer-events: none;
}

/* Incident Entry Row - strictly aligned */
.incident-entry {
  position: relative;
  display: flex;
  align-items: stretch;
  gap: 8px;
  margin: 0;
  padding: 0;
}

/* Dot Column - 16px even width ensures zero subpixel rounding error */
.dot-col {
  position: relative;
  width: 16px;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 6px;
  flex-shrink: 0;
  align-self: stretch;
  z-index: 2;
}

/* Solid dot strictly centered horizontally and vertically */
.incident-dot {
  position: relative;
  z-index: 2;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #38bdf8;
  flex-shrink: 0;
  transition: all 0.15s ease;
}

.dot-warn {
  background: #f59e0b;
}

.dot-error {
  background: #ef4444;
}

.dot-info {
  background: #38bdf8;
}

/* Content Area - holds the vertical gap so the dot-col spine stretches uninterrupted */
.incident-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding-bottom: 14px;
}

.incident-entry.is-last .incident-content {
  padding-bottom: 4px;
}

/* Main Entry Header Row strictly centered to dot at 9px */
.entry-row {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 0 4px;
  min-height: 18px;
  line-height: 18px;
  border-radius: var(--radius-xs);
  transition: background 0.12s ease;
}

.entry-row:hover {
  background: rgba(255, 255, 255, 0.03);
}

.entry-time {
  font-size: 11px;
  color: #64748b;
  letter-spacing: 0.3px;
  flex-shrink: 0;
}

.entry-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 3px;
  letter-spacing: 0.3px;
  flex-shrink: 0;
}

.badge-warn {
  background: rgba(232, 180, 94, 0.15);
  color: #e8b45e;
  border: 1px solid rgba(232, 180, 94, 0.35);
}

.badge-error {
  background: rgba(237, 118, 101, 0.15);
  color: #ed7665;
  border: 1px solid rgba(237, 118, 101, 0.35);
}

.badge-info {
  background: rgba(116, 164, 235, 0.15);
  color: #74a4eb;
  border: 1px solid rgba(116, 164, 235, 0.35);
}

.entry-title {
  font-size: 12px;
  font-weight: 700;
  color: #e5e8ec;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  letter-spacing: 0.2px;
}

.entry-caret {
  margin-left: auto;
  font-size: 9px;
  padding-right: 4px;
  flex-shrink: 0;
}

.caret-arrow {
  display: inline-block;
  font-size: 8px;
}

.caret-up {
  color: #90969d;
}

.caret-down {
  color: #475569;
}

/* Expanded Drawer Box (Identical to user screenshot) */
.entry-drawer {
  margin-top: 8px;
  padding: 12px 14px;
  background: #181c21;
  border: 1px solid #282c31;
  border-radius: 4px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  animation: drawer-fade 0.18s ease;
}

@keyframes drawer-fade {
  from {
    opacity: 0;
    transform: translateY(-3px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.drawer-desc {
  margin: 0 0 10px 0;
  font-size: 12px;
  line-height: 1.6;
  color: #e5e8ec;
  letter-spacing: 0.2px;
}

.drawer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 10px;
  padding-top: 2px;
  font-size: 11px;
}

.source-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
  margin-left: auto;
  font-size: 11px;
}

.source-label {
  color: #90969d;
  font-size: 11px;
}

.source-value {
  color: #e8b45e;
  font-weight: 500;
  font-size: 11px;
}

.quick-links {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  white-space: nowrap;
}

.link-gold {
  color: #e8b45e;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
}

.link-gold:hover {
  color: #f0c375;
  text-decoration: underline;
}

.link-subtle {
  color: #94a3b8;
  text-decoration: none;
  cursor: pointer;
}

.link-subtle:hover {
  color: #e2e8f0;
  text-decoration: underline;
}

/* Empty State */
.stream-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  font-size: 11px;
  color: #64748b;
}

.empty-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #475569;
}

/* ========================================================
   v0-reference Typography & Incident Hierarchy Rules
   ======================================================== */
:global([data-theme="v0-reference"]) .main-title {
  font-size: var(--theme-section-title-size, 13px) !important;
  font-weight: var(--theme-section-title-weight, 500) !important;
  color: var(--theme-event-title-color, #e5e8ec) !important;
}

:global([data-theme="v0-reference"]) .sub-title {
  font-size: var(--theme-meta-size, 10px) !important;
  font-weight: 400 !important;
  color: var(--theme-meta-color, #90969d) !important;
}

:global([data-theme="v0-reference"]) .btn-all-logs {
  font-size: var(--theme-button-size, 11px) !important;
  font-weight: var(--theme-button-weight, 400) !important;
  color: var(--primary, #e8b45e) !important;
}

:global([data-theme="v0-reference"]) .stream-timeline::before {
  background: var(--border, #282c31) !important;
}

:global([data-theme="v0-reference"]) .incident-dot {
  box-shadow: none !important;
}
:global([data-theme="v0-reference"]) .dot-info,
.dot-info {
  background: var(--info-accent, #74a4eb) !important;
  box-shadow: none !important;
}
:global([data-theme="v0-reference"]) .dot-warn {
  background: var(--primary, #e8b45e) !important;
  box-shadow: none !important;
}
:global([data-theme="v0-reference"]) .dot-error {
  background: var(--risk, #ed7665) !important;
  box-shadow: none !important;
}

:global([data-theme="v0-reference"]) .entry-time {
  font-size: var(--theme-meta-size, 10px) !important;
  font-weight: 400 !important;
  color: var(--theme-meta-color, #90969d) !important;
}

:global([data-theme="v0-reference"]) .entry-badge {
  font-size: 9.5px !important;
  font-weight: 600 !important;
  border-radius: 3px !important;
  letter-spacing: 0.04em !important;
  padding: 1.5px 5.5px !important;
  line-height: 1.15 !important;
}

:global([data-theme="v0-reference"]) .badge-info,
.badge-info {
  background: var(--info-bg, rgba(116, 164, 235, 0.15)) !important;
  color: var(--info-accent, #74a4eb) !important;
  border: 1px solid var(--info-border, rgba(116, 164, 235, 0.45)) !important;
  font-weight: 600 !important;
}

:global([data-theme="v0-reference"]) .badge-warn {
  background: rgba(232, 180, 94, 0.12) !important;
  color: var(--primary, #e8b45e) !important;
  border: 1px solid rgba(232, 180, 94, 0.35) !important;
  font-weight: 600 !important;
}

:global([data-theme="v0-reference"]) .badge-error {
  background: rgba(237, 118, 101, 0.12) !important;
  color: var(--risk, #ed7665) !important;
  border: 1px solid rgba(237, 118, 101, 0.35) !important;
  font-weight: 600 !important;
}

:global([data-theme="v0-reference"]) .entry-title {
  font-size: var(--theme-event-title-size, 12px) !important;
  font-weight: var(--theme-event-title-weight, 400) !important;
  line-height: var(--theme-event-title-leading, 1.625) !important;
  color: var(--theme-event-title-color, #e5e8ec) !important;
}

:global([data-theme="v0-reference"]) .entry-drawer {
  background: var(--card, #13161a) !important;
  border: 1px solid var(--border, #282c31) !important;
  border-radius: var(--radius, .375rem) !important;
}

:global([data-theme="v0-reference"]) .drawer-desc {
  font-size: var(--theme-detail-size, 11px) !important;
  font-weight: 400 !important;
  line-height: var(--theme-detail-leading, 1.625) !important;
  color: var(--theme-detail-color, #90969d) !important;
}

:global([data-theme="v0-reference"]) .source-label {
  font-size: var(--theme-meta-size, 10px) !important;
  font-weight: 400 !important;
  color: var(--theme-meta-color, #90969d) !important;
}

:global([data-theme="v0-reference"]) .source-value,
.source-value {
  font-size: var(--theme-meta-size, 10px) !important;
  font-weight: 500 !important;
  color: var(--info-accent, #74a4eb) !important;
}

:global([data-theme="v0-reference"]) .link-gold {
  color: var(--primary, #e8b45e) !important;
  font-size: 11px !important;
  font-weight: 400 !important;
}

:global([data-theme="v0-reference"]) .link-subtle {
  color: var(--muted-foreground, #90969d) !important;
  font-size: 11px !important;
  font-weight: 400 !important;
}

/* Empty Safe State */
.stream-empty-safe {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  text-align: center;
  gap: 8px;
}

.safe-badge-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.25);
  border-radius: 9999px;
  padding: 4px 12px;
}

.safe-pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
}

.safe-status-text {
  font-size: 11.5px;
  font-weight: 600;
  color: #10b981;
  letter-spacing: 0.2px;
}

.safe-desc {
  font-size: 11px;
  color: #64748b;
  margin: 0;
  max-width: 320px;
  line-height: 1.5;
}
</style>
