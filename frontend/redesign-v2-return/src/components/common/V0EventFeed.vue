<script setup lang="ts">
import { computed } from 'vue';
import { useV0Engine, type DeskEvent } from '@/state/v0-engine';

const props = withDefaults(
  defineProps<{
    showHeader?: boolean;
  }>(),
  {
    showHeader: true
  }
);

const emit = defineEmits<{
  (e: 'selectBot', botId: string): void;
  (e: 'gotoStrategy', strategyId: string): void;
}>();

const {
  events: allEvents,
  ackedEvents,
  eventFilter,
  bots,
  ackEvent
} = useV0Engine();

const pendingEvents = computed(() =>
  allEvents.value.filter((e: DeskEvent) => e.actionable && !ackedEvents.value.includes(e.id))
);

const shownEvents = computed(() =>
  eventFilter.value === 'action' ? pendingEvents.value : allEvents.value
);

function getBotName(botId?: string) {
  if (!botId) return '';
  const b = bots.value.find(x => x.id === botId);
  return b ? b.name : botId;
}

function handleAck(eId: string) {
  ackEvent(eId);
}

function handleOpenBot(botId: string) {
  emit('selectBot', botId);
}

function handleOpenStrategy(stratId: string) {
  emit('gotoStrategy', stratId);
}
</script>

<template>
  <div class="v0-event-feed-panel">
    <!-- Header (獨立展示時才渲染) -->
    <div v-if="showHeader" class="panel-header">
      <div class="header-left">
        <div class="title-row">
          <span class="v0-chip">V0 移植版</span>
          <h3 class="panel-title">事件稽核流</h3>
        </div>
      </div>

      <div class="header-actions">
        <div class="segmented-control" role="group">
          <button
            type="button"
            class="seg-btn"
            :class="{ active: eventFilter === 'all' }"
            @click="eventFilter = 'all'"
          >
            全部 ({{ allEvents.length }})
          </button>
          <button
            type="button"
            class="seg-btn"
            :class="{ active: eventFilter === 'action' }"
            @click="eventFilter = 'action'"
          >
            待處理
            <span v-if="pendingEvents.length > 0" class="badge-num">{{ pendingEvents.length }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 緊湊模式過濾條 (showHeader === false) -->
    <!-- 嵌入模式：篩選切換鈕已統一移至外層卡片 Header 右上角 (與標題同一排) -->

    <!-- Event List -->
    <div class="feed-body">
      <div v-if="shownEvents.length === 0" class="empty-feed">
        <p>目前沒有待處理事件，系統狀態穩定。</p>
      </div>

      <ol v-else class="event-list">
        <li
          v-for="e in shownEvents"
          :key="e.id"
          class="event-item"
          :class="{ 'is-acked': ackedEvents.includes(e.id) }"
        >
          <!-- 嚴重度指示方塊 -->
          <span
            class="severity-indicator"
            :class="`sev-${e.severity}`"
            :title="`嚴重度：${e.severity}`"
          ></span>

          <div class="event-content">
            <div class="event-meta-row">
              <span class="category-tag">{{ e.category }}</span>
              <span class="event-time">{{ e.time }}</span>
            </div>

            <p class="event-title">{{ e.title }}</p>

            <p v-if="e.detail" class="event-detail">{{ e.detail }}</p>

            <!-- 快捷處置按鈕列 -->
            <div v-if="e.actionable || e.botId || e.strategyId" class="event-actions-row">
              <button
                v-if="e.strategyId"
                type="button"
                class="btn-action btn-strategy"
                @click="handleOpenStrategy(e.strategyId)"
              >
                在策略中心檢查
              </button>

              <button
                v-if="e.botId"
                type="button"
                class="btn-action"
                :class="{ 'btn-primary': !ackedEvents.includes(e.id) && !e.strategyId }"
                @click="handleOpenBot(e.botId)"
              >
                查看 {{ getBotName(e.botId) }}
              </button>

              <template v-if="e.actionable">
                <span v-if="ackedEvents.includes(e.id)" class="acked-label">
                  ✓ 已確認
                </span>
                <button
                  v-else
                  type="button"
                  class="btn-action btn-ack"
                  @click="handleAck(e.id)"
                >
                  確認
                </button>
              </template>
            </div>
          </div>
        </li>
      </ol>
    </div>
  </div>
</template>

<style scoped>
.v0-event-feed-panel {
  display: flex;
  flex-direction: column;
  background: transparent;
  border: none;
  border-radius: 4px;
  overflow: hidden;
  height: 100%;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #181c21;
  border-bottom: 1px solid #282c31;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.v0-chip {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  background: #181c21;
  color: #e8b45e;
  border: 1px solid #282c31;
  font-family: monospace;
}

.panel-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #e5e8ec;
}

.panel-meta {
  font-size: 11px;
  color: #90969d;
  font-family: monospace;
}

.segmented-control {
  display: flex;
  background: #13161a;
  border: 1px solid #282c31;
  border-radius: 3px;
  padding: 2px;
  gap: 2px;
}

.seg-btn {
  background: transparent;
  border: none;
  color: #90969d;
  font-size: 11px;
  font-family: monospace;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 2px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.15s;
}

.seg-btn:hover {
  color: #e5e8ec;
}

.seg-btn.active {
  background: #1d2126;
  color: #e8b45e;
}

.badge-num {
  font-size: 9px;
  background: #ed7665;
  color: #0c0f12;
  font-weight: 700;
  padding: 0 4px;
  border-radius: 10px;
}

.feed-body {
  flex: 1;
  overflow-y: auto;
  padding: 0;
  background: #13161a;
}

.empty-feed {
  padding: 32px 16px;
  text-align: center;
  color: #90969d;
  font-size: 12px;
  font-family: monospace;
}

.event-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.event-item {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid #282c31;
  transition: opacity 0.2s, background 0.15s;
}

.event-item:hover {
  background: #1d2126;
}

.event-item.is-acked {
  opacity: 0.5;
}

.severity-indicator {
  width: 6px;
  height: 6px;
  border-radius: 2px;
  margin-top: 5px;
  flex-shrink: 0;
}

.sev-high {
  background: #ed7665;
  box-shadow: 0 0 6px rgba(237, 118, 101, 0.6);
}

.sev-medium {
  background: #e8b45e;
}

.sev-info {
  background: #90969d;
}

.event-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 0;
}

.event-meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-family: monospace;
  font-size: 10px;
}

.category-tag {
  color: #e8b45e;
  font-weight: 600;
}

.event-time {
  color: #90969d;
}

.event-title {
  margin: 0;
  font-size: 12px;
  font-weight: 500;
  color: #e5e8ec;
  line-height: 1.4;
}

.event-detail {
  margin: 0;
  font-size: 11px;
  color: #90969d;
  line-height: 1.4;
}

.event-actions-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  flex-wrap: wrap;
}

.btn-action {
  font-size: 11px;
  font-family: monospace;
  padding: 2px 7px;
  border-radius: 3px;
  background: #181c21;
  border: 1px solid #282c31;
  color: #e5e8ec;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-action:hover {
  background: #1d2126;
  color: #e8b45e;
  border-color: #e8b45e;
}

.btn-action.btn-primary {
  background: #e8b45e;
  color: #0c0f12;
  border-color: #e8b45e;
  font-weight: 700;
}

.btn-strategy {
  border-color: #e8b45e;
  color: #e8b45e;
}

.btn-ack {
  color: #e8b45e;
}

.acked-label {
  font-size: 10px;
  font-family: monospace;
  color: #90969d;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.compact-feed-toolbar {
  padding: 3px 8px;
  background: #13161a;
  border-bottom: 1px solid #1f2328;
  display: flex;
  align-items: center;
  min-height: 24px;
}
</style>
