<script setup lang="ts">
import { ref, computed } from 'vue';
import {
  useV0Engine,
  STAGES,
  recommendedStrategy,
  formatPct,
  type Strategy,
  type Stage
} from '@/state/v0-engine';

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
}>();

const {
  strategies,
  bots,
  importStrategy,
  updateStrategyStage
} = useV0Engine();

const fileInputRef = ref<HTMLInputElement | null>(null);
const activeReviewStrategy = ref<Strategy | null>(null);
const userAcknowledged = ref(false);

const nextRecommended = computed(() => recommendedStrategy(strategies.value));
const rejectedStrategies = computed(() => strategies.value.filter(s => s.stage === 'rejected'));

const MCP_LOG = [
  { time: '08:51', text: '寫入 breakout_v2.py → v2.3（待檢查）' },
  { time: '08:49', text: '執行回測 breakout_v2.py v2.3 · 30 天合成資料' },
  { time: '08:44', text: '讀取 Calico 最近 50 筆成交' },
  { time: '08:40', text: '讀取策略清單' }
];

function handleFileChange(e: Event) {
  const target = e.target as HTMLInputElement;
  const file = target.files?.[0];
  if (file) {
    importStrategy(file.name);
  }
  target.value = '';
}

function openReview(s: Strategy) {
  activeReviewStrategy.value = s;
  userAcknowledged.value = false;
}

function closeReview() {
  activeReviewStrategy.value = null;
}

function trustStrategy(s: Strategy) {
  updateStrategyStage(s.id, 'trusted');
  closeReview();
}

function rejectStrategy(s: Strategy) {
  updateStrategyStage(s.id, 'rejected');
  closeReview();
}

function assignBot(s: Strategy) {
  updateStrategyStage(s.id, 'assigned');
}

function startSim(s: Strategy) {
  updateStrategyStage(s.id, 'simulating');
}

function openBot(botId: string) {
  emit('selectBot', botId);
}
</script>

<template>
  <div class="v0-pipeline-panel">
    <!-- Header (獨立展示時渲染) -->
    <div v-if="showHeader" class="panel-header">
      <div class="header-left">
        <div class="title-row">
          <h3 class="panel-title">策略中心</h3>
        </div>
      </div>

      <div class="header-actions">
        <input
          ref="fileInputRef"
          type="file"
          accept=".py"
          class="hidden"
          @change="handleFileChange"
        />
        <button
          type="button"
          class="btn-upload"
          @click="fileInputRef?.click()"
        >
          ⬆ 匯入 .py
        </button>
      </div>
    </div>

    <!-- 緊湊模式操作條 (showHeader === false) -->
    <div v-else class="compact-pipeline-toolbar">
      <input
        ref="fileInputRef"
        type="file"
        accept=".py"
        class="hidden"
        @change="handleFileChange"
      />
      <button
        type="button"
        class="btn-upload-mini"
        @click="fileInputRef?.click()"
      >
        ⬆ 匯入 .py
      </button>
    </div>

    <!-- 6-Stage Kanban Board -->
    <div class="pipeline-kanban">
      <div
        v-for="stg in STAGES"
        :key="stg.key"
        class="kanban-col"
      >
        <div class="col-header">
          <span class="col-title">{{ stg.label }}</span>
          <span class="col-hint">{{ stg.hint }}</span>
          <span class="col-count">
            {{ strategies.filter(s => s.stage === stg.key).length }}
          </span>
        </div>

        <div class="col-cards">
          <div
            v-for="strat in strategies.filter(s => s.stage === stg.key)"
            :key="strat.id"
            class="strategy-card"
            :class="{ 'is-highlighted': nextRecommended?.id === strat.id }"
          >
            <div class="card-head">
              <span class="card-file">{{ strat.file }}</span>
              <span class="card-ver">{{ strat.version }}</span>
              <span v-if="strat.origin === 'mcp'" class="mcp-badge">MCP</span>
            </div>

            <p class="card-summary">{{ strat.summary }}</p>

            <div v-if="strat.result" class="card-res">
              <span :class="strat.result.ret >= 0 ? 'text-gain' : 'text-risk'">
                {{ formatPct(strat.result.ret) }}
              </span>
              <span class="res-sub">· {{ strat.result.span }} · {{ strat.result.trades }} 筆</span>
            </div>

            <!-- Actions -->
            <div class="card-actions">
              <button
                v-if="strat.stage === 'import' || strat.stage === 'review'"
                type="button"
                class="btn-card-act"
                :class="{ 'btn-primary': nextRecommended?.id === strat.id }"
                @click="openReview(strat)"
              >
                檢查
              </button>

              <button
                v-else-if="strat.stage === 'trusted'"
                type="button"
                class="btn-card-act"
                @click="assignBot(strat)"
              >
                分配機器人
              </button>

              <button
                v-else-if="strat.stage === 'assigned'"
                type="button"
                class="btn-card-act btn-primary"
                @click="startSim(strat)"
              >
                啟動模擬
              </button>

              <button
                v-else-if="strat.stage === 'simulating' && strat.botId"
                type="button"
                class="btn-card-act"
                @click="openBot(strat.botId)"
              >
                查看機器人
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom Secondary Info: MCP Activity & Rejected -->
    <div class="pipeline-footer-grid">
      <div class="sub-panel">
        <div class="sub-header">
          <span class="sub-title">MCP 活動</span>
          <span class="sub-meta">1 用戶端 · 唯讀＋寫入草稿</span>
        </div>
        <ul class="mcp-list">
          <li v-for="l in MCP_LOG" :key="l.time + l.text" class="mcp-item">
            <span class="mcp-time">{{ l.time }}</span>
            <span class="mcp-text">{{ l.text }}</span>
          </li>
        </ul>
      </div>

      <div class="sub-panel">
        <div class="sub-header">
          <span class="sub-title">已退回策略</span>
          <span class="sub-meta">{{ rejectedStrategies.length }} 個檔案 · 保留在本機</span>
        </div>
        <div v-if="rejectedStrategies.length === 0" class="sub-empty">
          沒有退回的策略
        </div>
        <ul v-else class="mcp-list">
          <li v-for="s in rejectedStrategies" :key="s.id" class="mcp-item">
            <span>{{ s.file }}</span>
            <span class="text-neutral-500">{{ s.version }}</span>
          </li>
        </ul>
      </div>
    </div>

    <!-- Review Diff Dialog Overlay -->
    <div v-if="activeReviewStrategy" class="review-dialog-overlay" @click.self="closeReview">
      <div class="review-dialog-content">
        <div class="dlg-header">
          <div class="dlg-meta">
            {{ activeReviewStrategy.origin === 'mcp' ? `MCP 寫入 · ${activeReviewStrategy.time ?? ''}` : '本機匯入' }} · {{ activeReviewStrategy.summary }}
          </div>
          <h2 class="dlg-title">
            檢查 {{ activeReviewStrategy.file }} <span class="text-neutral-400 font-mono">{{ activeReviewStrategy.version }}</span>
          </h2>
          <p v-if="activeReviewStrategy.attnDetail" class="dlg-attn">
            {{ activeReviewStrategy.attnDetail }}
          </p>
          <button type="button" class="btn-close-dlg" @click="closeReview">✕</button>
        </div>

        <div v-if="activeReviewStrategy.review" class="dlg-body">
          <!-- Static Checks -->
          <div class="review-section">
            <h4 class="sec-title">靜態安全檢查</h4>
            <ul class="checks-list">
              <li v-for="chk in activeReviewStrategy.review.checks" :key="chk.label" class="check-item">
                <span class="chk-status" :class="chk.status === 'ok' ? 'status-ok' : 'status-warn'">
                  {{ chk.status === 'ok' ? '✓' : '⚠' }}
                </span>
                <div class="chk-text">
                  <div class="chk-label">{{ chk.label }}</div>
                  <div v-if="chk.note" class="chk-note">{{ chk.note }}</div>
                </div>
              </li>
            </ul>
          </div>

          <!-- Code Diff -->
          <div class="review-section">
            <h4 class="sec-title">
              程式碼差異
              <span class="text-neutral-500 font-mono text-xs font-normal">
                {{ activeReviewStrategy.review.diffLabel }}
              </span>
            </h4>
            <pre class="diff-block"><code><div
                v-for="(line, idx) in activeReviewStrategy.review.diff"
                :key="idx"
                class="diff-line"
                :class="{
                  'diff-add': line.type === '+',
                  'diff-del': line.type === '-'
                }"
              ><span class="diff-prefix">{{ line.type === ' ' ? ' ' : line.type }}</span>{{ line.text }}</div></code></pre>
          </div>
        </div>

        <!-- Footer Actions -->
        <div class="dlg-footer">
          <label v-if="activeReviewStrategy.review?.requiresAck" class="ack-row">
            <input v-model="userAcknowledged" type="checkbox" class="ack-cb" />
            <span>我已了解這份策略具備網路能力，仍要信任它。</span>
          </label>

          <div class="footer-btns">
            <button
              type="button"
              class="btn-dlg-reject"
              @click="rejectStrategy(activeReviewStrategy)"
            >
              退回
            </button>
            <button
              type="button"
              class="btn-dlg-trust"
              :disabled="activeReviewStrategy.review?.requiresAck && !userAcknowledged"
              @click="trustStrategy(activeReviewStrategy)"
            >
              信任 {{ activeReviewStrategy.version }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.v0-pipeline-panel {
  display: flex;
  flex-direction: column;
  background: transparent;
  border: none;
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
  background: rgba(232, 180, 94, 0.15);
  color: #e8b45e;
  border: 1px solid rgba(232, 180, 94, 0.3);
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

.btn-upload {
  background: #181c21;
  border: 1px solid #282c31;
  color: #e5e8ec;
  font-size: 11px;
  font-family: monospace;
  padding: 3px 8px;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-upload:hover {
  background: #1d2126;
  color: #ffffff;
  border-color: #e8b45e;
}

.pipeline-kanban {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 1px;
  background: #282c31;
  flex: 1;
  overflow-x: auto;
  min-height: 220px;
}

@media (max-width: 1100px) {
  .pipeline-kanban {
    grid-template-columns: repeat(3, 1fr);
  }
}

.kanban-col {
  background: #13161a;
  display: flex;
  flex-direction: column;
}

.col-header {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 6px 10px;
  border-bottom: 1px solid #282c31;
  background: #181c21;
}

.col-title {
  font-size: 11px;
  font-weight: 600;
  color: #e5e8ec;
}

.col-hint {
  font-size: 10px;
  color: #90969d;
  font-family: monospace;
}

.col-count {
  margin-left: auto;
  font-size: 10px;
  color: #90969d;
  font-family: monospace;
}

.col-cards {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
  overflow-y: auto;
}

.strategy-card {
  background: #13161a;
  border: 1px solid #282c31;
  border-radius: 3px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: border-color 0.15s;
}

.strategy-card.is-highlighted {
  border-color: #e8b45e;
  box-shadow: 0 0 6px rgba(232, 180, 94, 0.2);
}

.card-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: monospace;
}

.card-file {
  font-size: 11px;
  color: #e5e8ec;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-ver {
  font-size: 10px;
  color: #90969d;
}

.mcp-badge {
  margin-left: auto;
  font-size: 9px;
  background: rgba(232, 180, 94, 0.15);
  color: #e8b45e;
  padding: 0 4px;
  border-radius: 2px;
}

.card-summary {
  margin: 0;
  font-size: 11px;
  color: #90969d;
  line-height: 1.3;
}

.card-res {
  font-family: monospace;
  font-size: 10px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.res-sub {
  color: #90969d;
}

.card-actions {
  margin-top: 4px;
}

.btn-card-act {
  font-size: 10px;
  font-family: monospace;
  padding: 2px 6px;
  background: #181c21;
  border: 1px solid #282c31;
  color: #e5e8ec;
  border-radius: 2px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-card-act:hover {
  background: #1d2126;
  color: #ffffff;
  border-color: #e8b45e;
}

.btn-card-act.btn-primary {
  background: #e8b45e;
  color: #0c0f12;
  border-color: #e8b45e;
  font-weight: 600;
}

.pipeline-footer-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: #282c31;
  border-top: 1px solid #282c31;
}

.sub-panel {
  background: #13161a;
  padding: 8px 12px;
}

.sub-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.sub-title {
  font-size: 11px;
  font-weight: 600;
  color: #e5e8ec;
}

.sub-meta {
  font-size: 10px;
  color: #90969d;
  font-family: monospace;
}

.sub-empty {
  font-size: 11px;
  color: #90969d;
  font-family: monospace;
  padding: 4px 0;
}

.mcp-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mcp-item {
  display: flex;
  gap: 8px;
  font-family: monospace;
  font-size: 11px;
  color: #e5e8ec;
}

.mcp-time {
  color: #90969d;
  flex-shrink: 0;
}

/* Modal Dialog */
.review-dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 16px;
}

.review-dialog-content {
  background: #13161a;
  border: 1px solid #282c31;
  border-radius: 6px;
  width: 100%;
  max-width: 580px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8);
}

.dlg-header {
  position: relative;
  padding: 14px 16px;
  border-bottom: 1px solid #282c31;
}

.dlg-meta {
  font-size: 10px;
  font-family: monospace;
  color: #90969d;
}

.dlg-title {
  margin: 4px 0 0;
  font-size: 15px;
  font-weight: 600;
  color: #e5e8ec;
}

.dlg-attn {
  margin: 4px 0 0;
  font-size: 11px;
  color: #90969d;
  line-height: 1.4;
}

.btn-close-dlg {
  position: absolute;
  top: 12px;
  right: 12px;
  background: transparent;
  border: none;
  color: #90969d;
  font-size: 14px;
  cursor: pointer;
}

.btn-close-dlg:hover {
  color: #e5e8ec;
}

.dlg-body {
  padding: 14px 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.review-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sec-title {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: #e5e8ec;
  display: flex;
  align-items: center;
  gap: 8px;
}

.checks-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.check-item {
  display: flex;
  gap: 8px;
  font-size: 11px;
}

.chk-status {
  font-weight: bold;
}

.status-ok {
  color: #65cba7;
}

.status-warn {
  color: #e8b45e;
}

.chk-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chk-label {
  color: #e5e8ec;
}

.chk-note {
  font-family: monospace;
  font-size: 10px;
  color: #90969d;
}

.diff-block {
  margin: 0;
  padding: 8px;
  background: #0c0f12;
  border: 1px solid #282c31;
  border-radius: 4px;
  font-family: monospace;
  font-size: 11px;
  line-height: 1.5;
  overflow-x: auto;
}

.diff-line {
  padding: 1px 4px;
  color: #90969d;
}

.diff-add {
  background: rgba(101, 203, 167, 0.15);
  color: #65cba7;
}

.diff-del {
  background: rgba(237, 118, 101, 0.15);
  color: #ed7665;
}

.diff-prefix {
  display: inline-block;
  width: 14px;
  user-select: none;
  opacity: 0.7;
}

.dlg-footer {
  padding: 12px 16px;
  border-top: 1px solid #282c31;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #0f1216;
}

.ack-row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 11px;
  color: #e5e8ec;
  cursor: pointer;
}

.ack-cb {
  margin-top: 2px;
}

.footer-btns {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.btn-dlg-reject {
  background: #181c21;
  border: 1px solid #282c31;
  color: #e5e8ec;
  padding: 4px 12px;
  border-radius: 3px;
  font-size: 12px;
  cursor: pointer;
}

.btn-dlg-trust {
  background: #e8b45e;
  border: 1px solid #e8b45e;
  color: #0c0f12;
  padding: 4px 14px;
  border-radius: 3px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.btn-dlg-trust:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.text-gain {
  color: #65cba7;
}

.text-risk {
  color: #ed7665;
}

.compact-pipeline-toolbar {
  padding: 4px 10px;
  background: #13161a;
  border-bottom: 1px solid #282c31;
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.btn-upload-mini {
  background: #e8b45e;
  color: #0c0f12;
  border: 1px solid #e8b45e;
  font-size: 11px;
  font-family: monospace;
  padding: 2px 8px;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-upload-mini:hover {
  background: #d4a350;
}
</style>
