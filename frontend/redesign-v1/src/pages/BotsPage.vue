<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import type { Bot, StrategyEntry, SimulationRun, PendingCommand } from '@/contracts';
import { activeAdapter } from '@/adapters/mock-adapter';
import { useWorkspace } from '@/state/useWorkspace';
import StatusBadge from '@/components/common/StatusBadge.vue';

const { currentMode } = useWorkspace();
const bots = ref<Bot[]>([]);
const strategies = ref<StrategyEntry[]>([]);
const runs = ref<SimulationRun[]>([]);
const pendingCommand = ref<PendingCommand | null>(null);

const errorMsg = ref<string | null>(null);
const successMsg = ref<string | null>(null);
const isSubmitting = ref<boolean>(false);

// Allocate form state
const showAllocateModal = ref<boolean>(false);
const newBotId = ref<string>('');
const selectedStrategyHash = ref<string>('');
const customParametersJson = ref<string>('{}');
const isTrusted = ref<boolean>(false); // Strict Invariant: MUST NOT be pre-checked!

// Runs history drawer
const showHistory = ref<boolean>(false);
const selectedRun = ref<SimulationRun | null>(null);

function generateRequestId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID().replace(/-/g, '');
  }
  let s = '';
  while (s.length < 32) {
    s += Math.random().toString(16).slice(2);
  }
  return s.slice(0, 32);
}

const selectedStrategy = computed(() => {
  return strategies.value.find(s => s.artifact_hash === selectedStrategyHash.value) || strategies.value[0] || null;
});

async function loadData() {
  try {
    bots.value = await activeAdapter.fetchBotQueue();
    strategies.value = await activeAdapter.fetchStrategies();
    runs.value = await activeAdapter.fetchRuns();
    pendingCommand.value = activeAdapter.getPendingCommand();

    if (strategies.value.length && !selectedStrategyHash.value) {
      selectedStrategyHash.value = strategies.value[0].artifact_hash;
    }
  } catch (err: any) {
    errorMsg.value = err.message || '讀取資料失敗';
  }
}

onMounted(() => {
  loadData();
});

// Strict Invariant: reset trust and parameters when strategy changes
watch(selectedStrategyHash, (newHash) => {
  isTrusted.value = false;
  const strat = strategies.value.find(s => s.artifact_hash === newHash);
  if (strat) {
    customParametersJson.value = JSON.stringify(strat.artifact.defaults, null, 2);
  }
});

function openAllocateModal() {
  isTrusted.value = false; // Always force uncheck on open
  newBotId.value = '';
  if (selectedStrategy.value) {
    customParametersJson.value = JSON.stringify(selectedStrategy.value.artifact.defaults, null, 2);
  }
  showAllocateModal.value = true;
}

function closeAllocateModal() {
  isTrusted.value = false; // Always force uncheck on close
  showAllocateModal.value = false;
}

async function handleAllocate() {
  errorMsg.value = null;
  successMsg.value = null;

  if (currentMode.value !== 'local') {
    errorMsg.value = `當前處於 ${currentMode.value.toUpperCase()} 唯讀展示模式，控制已全域鎖定，禁止分配新機器人。`;
    return;
  }

  if (!newBotId.value.trim()) {
    errorMsg.value = '請輸入機器人識別碼 (Bot ID)';
    return;
  }
  if (!isTrusted.value) {
    errorMsg.value = '人工信任確認未勾選：安全邊界要求每次建立 Bot 必須親自審閱並確認信任策略製品。';
    return;
  }

  let parsedParams = {};
  try {
    parsedParams = JSON.parse(customParametersJson.value);
  } catch {
    errorMsg.value = '策略參數 JSON 格式不合規，請檢查輸入。';
    return;
  }

  const reqId = generateRequestId();
  isSubmitting.value = true;

  try {
    await activeAdapter.allocateBot(reqId, {
      bot_id: newBotId.value.trim(),
      artifact_hash: selectedStrategyHash.value,
      parameters: parsedParams,
      trusted: isTrusted.value,
      mode: 'local'
    });
    successMsg.value = `機器人 ${newBotId.value} 建立成功，已綁定不可變製品快照。`;
    closeAllocateModal();
    await loadData();
  } catch (err: any) {
    errorMsg.value = err.message || '分配機器人失敗';
  } finally {
    isSubmitting.value = false;
  }
}

async function handleStart(botId: string) {
  errorMsg.value = null;
  successMsg.value = null;

  if (currentMode.value !== 'local') {
    errorMsg.value = `當前處於 ${currentMode.value.toUpperCase()} 唯讀展示模式，控制已全域鎖定，禁止啟動機器人。`;
    return;
  }

  const reqId = generateRequestId();
  isSubmitting.value = true;

  try {
    const res = await activeAdapter.startBot(reqId, botId);
    successMsg.value = `機器人 ${botId} 啟動成功 (Run ID: ${res.run_id.slice(0, 8)})`;
    await loadData();
  } catch (err: any) {
    errorMsg.value = err.message || '啟動失敗';
    pendingCommand.value = activeAdapter.getPendingCommand();
  } finally {
    isSubmitting.value = false;
  }
}

async function handleStop(bot: Bot) {
  errorMsg.value = null;
  successMsg.value = null;

  if (currentMode.value !== 'local') {
    errorMsg.value = `當前處於 ${currentMode.value.toUpperCase()} 唯讀展示模式，控制已全域鎖定，禁止停止機器人。`;
    return;
  }

  if (!bot.current_run_id) {
    errorMsg.value = `機器人 ${bot.bot_id} 尚未綁定有效 Run ID，無法停止`;
    return;
  }

  const reqId = generateRequestId();
  isSubmitting.value = true;

  try {
    await activeAdapter.stopBot(reqId, bot.current_run_id);
    successMsg.value = `機器人 ${bot.bot_id} 停止命令已受理。若持有部位將保留獨佔與曝險。`;
    await loadData();
  } catch (err: any) {
    errorMsg.value = err.message || '停止失敗';
    pendingCommand.value = activeAdapter.getPendingCommand();
  } finally {
    isSubmitting.value = false;
  }
}

async function handleRetryPending() {
  if (!pendingCommand.value) return;
  errorMsg.value = null;
  successMsg.value = null;
  isSubmitting.value = true;

  try {
    await activeAdapter.retryPendingCommand();
    successMsg.value = '原命令手動重送成功。';
    pendingCommand.value = null;
    await loadData();
  } catch (err: any) {
    errorMsg.value = '重送命令仍失敗：' + (err.message || '服務無響應');
  } finally {
    isSubmitting.value = false;
  }
}

function handleClearPending() {
  activeAdapter.clearPendingCommand();
  pendingCommand.value = null;
  successMsg.value = '已清除未完成的暫存命令。';
}
</script>

<template>
  <div class="bots-page">
    <!-- Teleport Actions to Unified Header -->
    <Teleport to="#header-page-actions">
      <div class="header-actions-group">
        <button
          type="button"
          class="btn btn-sm btn-secondary"
          @click="showHistory = !showHistory"
        >
          {{ showHistory ? '關閉歷史' : '執行成果歷史' }}
        </button>
        <button
          type="button"
          class="btn btn-sm btn-primary"
          :disabled="currentMode !== 'local' || isSubmitting"
          :title="currentMode !== 'local' ? 'Demo / Live 模式下控制已全域鎖定，禁止分配新機器人' : ''"
          @click="openAllocateModal"
        >
          + 分配新機器人
        </button>
      </div>
    </Teleport>

    <!-- Mode Readonly Lock Banner -->
    <div v-if="currentMode !== 'local'" class="banner banner-warning">
      <div class="banner-text">
        <strong>🔒 模式唯讀鎖定中 ({{ currentMode.toUpperCase() }})：</strong>
        <span>唯讀隔離展示模式下，所有交易控制、機器人啟動、停止與分配操作已全域鎖定。</span>
      </div>
    </div>

    <!-- Pending command retry banner -->
    <div v-if="pendingCommand" class="banner banner-warning">
      <div class="banner-text">
        <strong>⚠️ 保留原命令，等待確認／手動重送</strong>
        <span>路徑: {{ pendingCommand.path }} · Request ID: {{ pendingCommand.body.request_id }}</span>
      </div>
      <div class="banner-actions">
        <button type="button" class="btn-sm btn-primary" :disabled="currentMode !== 'local' || isSubmitting" @click="handleRetryPending">
          重送原命令
        </button>
        <button type="button" class="btn-sm btn-secondary" @click="handleClearPending">
          清除待送
        </button>
      </div>
    </div>

    <!-- Alert banners -->
    <div v-if="errorMsg" class="banner banner-danger">
      <span>{{ errorMsg }}</span>
      <button type="button" class="btn-sm btn-secondary" @click="errorMsg = null">關閉</button>
    </div>
    <div v-if="successMsg" class="banner banner-info">
      <span>{{ successMsg }}</span>
      <button type="button" class="btn-sm btn-secondary" @click="successMsg = null">關閉</button>
    </div>

    <!-- Bots Table Card -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">已部署實例清單</div>
        <div class="card-actions">
          <span class="badge badge-accent">{{ bots.length }} 個部署</span>
        </div>
      </div>

      <div class="card-body p-0">
        <div class="data-table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>機器人 ID / 名稱</th>
                <th>合約代碼</th>
                <th>綁定製品 Hash</th>
                <th>人工信任</th>
                <th>持倉張數</th>
                <th>當前損益</th>
                <th>運行狀態</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="b in bots" :key="b.bot_id">
                <td>
                  <strong>{{ b.name || b.bot_id }}</strong>
                  <div class="mono text-muted text-2xs">{{ b.bot_id }}</div>
                </td>
                <td class="mono">{{ b.symbol }}</td>
                <td class="mono text-muted text-2xs" :title="b.binding.artifact_hash">
                  {{ b.binding.artifact_hash.slice(0, 16) }}...
                </td>
                <td>
                  <span class="badge badge-sm badge-success" v-if="b.trusted">已確認信任</span>
                  <span class="badge badge-sm badge-warning" v-else>未信任</span>
                </td>
                <td class="tabular-nums">
                  <span :class="b.position_contracts !== '0' ? 'text-accent font-bold' : ''">
                    {{ b.position_contracts || '0' }} 張
                  </span>
                </td>
                <td class="tabular-nums">
                  <span :class="b.pnl_usdt?.startsWith('+') ? 'text-success' : (b.pnl_usdt === '0.00' ? '' : 'text-danger')">
                    {{ b.pnl_usdt || '0.00' }} USDT
                  </span>
                </td>
                <td>
                  <StatusBadge :status="b.state" />
                </td>
                <td>
                  <div class="action-buttons">
                    <button
                      v-if="['stopped', 'failed', 'completed'].includes(b.state)"
                      type="button"
                      class="btn btn-sm btn-primary"
                      :disabled="currentMode !== 'local' || isSubmitting"
                      :title="currentMode !== 'local' ? 'Demo / Live 模式下控制已鎖定，禁止啟動' : ''"
                      @click="handleStart(b.bot_id)"
                    >
                      啟動
                    </button>
                    <button
                      v-if="['running', 'starting'].includes(b.state)"
                      type="button"
                      class="btn btn-sm btn-danger"
                      :disabled="currentMode !== 'local' || isSubmitting"
                      :title="currentMode !== 'local' ? 'Demo / Live 模式下控制已鎖定，禁止停止' : ''"
                      @click="handleStop(b)"
                    >
                      停止
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="!bots.length">
                <td colspan="8" class="text-center text-muted p-4">
                  目前尚無已部署機器人，請點擊右上角「+ 分配新機器人」。
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Lower Operational Grid: Worker Monitor + Activity Stream -->
    <div class="bots-lower-grid">
      <!-- Worker Process & Sandbox Monitor -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">Worker 程序與受信隔離 (Worker Daemons & IPC Watch)</div>
          <span class="badge badge-sm badge-neutral">3 進程實例</span>
        </div>
        <div class="card-body">
          <div class="worker-list">
            <div class="worker-item">
              <div class="worker-header">
                <div class="worker-pid mono">PID 4821</div>
                <div class="worker-tag">BTC 趨勢突破主線</div>
                <span class="badge badge-sm badge-success">HEALTHY</span>
              </div>
              <div class="worker-meta mono">
                <span>CPU: 0.6%</span>
                <span>RSS: 32.8 MB</span>
                <span>IPC 延遲: 1.2ms</span>
                <span>心跳: 100%</span>
              </div>
            </div>

            <div class="worker-item is-inactive">
              <div class="worker-header">
                <div class="worker-pid mono">PID 4825</div>
                <div class="worker-tag">ETH 動態震盪網格</div>
                <span class="badge badge-sm badge-neutral">STOPPED</span>
              </div>
              <div class="worker-meta mono">
                <span>CPU: 0.0%</span>
                <span>RSS: 0.0 MB</span>
                <span>保留部位: 0 張</span>
                <span>獨佔已釋放</span>
              </div>
            </div>

            <div class="worker-item is-inactive">
              <div class="worker-header">
                <div class="worker-pid mono">PID 4829</div>
                <div class="worker-tag">SOL 試驗波段 04</div>
                <span class="badge badge-sm badge-neutral">STOPPED</span>
              </div>
              <div class="worker-meta mono">
                <span>CPU: 0.0%</span>
                <span>RSS: 0.0 MB</span>
                <span>保留部位: 0 張</span>
                <span>獨佔已釋放</span>
              </div>
            </div>
          </div>

          <!-- Invariant checks -->
          <div class="ipc-invariants-box">
            <div class="inv-row">
              <span class="inv-badge ok">✓</span>
              <span><strong>受信策略邊界 (P1)</strong>：僅執行選定策略，獨立 Python Worker 進程</span>
            </div>
            <div class="inv-row">
              <span class="inv-badge ok">✓</span>
              <span><strong>憑證隔離</strong>：Supervisor 獨佔 API Key，不向 Worker 提供簽名器</span>
            </div>
            <div class="inv-row">
              <span class="inv-badge ok">✓</span>
              <span><strong>OKX 固定標籤</strong>：所有委託強制注入 <code class="mono text-accent">41cb53c54d6dABDE</code></span>
            </div>
          </div>
        </div>
      </div>

      <!-- Live Bot Event Stream -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">機器人即時事件串流 (Realtime Bot Activity)</div>
          <span class="badge badge-sm badge-accent">即時串流中</span>
        </div>
        <div class="card-body p-0">
          <div class="bot-stream-list">
            <div class="bot-stream-item">
              <span class="stream-time tabular-nums">11:10:02</span>
              <span class="badge badge-sm badge-neutral">15m BAR</span>
              <span class="stream-text">BTC-USDT-SWAP 收到已收盤 K 線 (Closed Bar)，策略訊號: HOLD</span>
            </div>
            <div class="bot-stream-item">
              <span class="stream-time tabular-nums">10:24:15</span>
              <span class="badge badge-sm badge-accent">ORDER</span>
              <span class="stream-text">BTC-USDT-SWAP 市價撮合成交 1.00 張 @ 64,250.00 USDT，tag: 41cb53c54d6dABDE</span>
            </div>
            <div class="bot-stream-item">
              <span class="stream-time tabular-nums">09:30:10</span>
              <span class="badge badge-sm badge-info">WARMUP</span>
              <span class="stream-text">Worker PID 4821 正常啟動，已完成 8 根歷史收盤 K 線指標預熱</span>
            </div>
            <div class="bot-stream-item">
              <span class="stream-time tabular-nums">09:29:55</span>
              <span class="badge badge-sm badge-success">MUTEX</span>
              <span class="stream-text">BTC-USDT-SWAP 單合約獨佔鎖由 bot-btc-trend-01 成功獲取</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Execution Results History Section -->
    <div v-if="showHistory" class="card history-card">
      <div class="card-header">
        <div class="card-title">短程模擬執行成果歷史 (Immutable Runs)</div>
        <span class="badge badge-neutral">{{ runs.length }} 筆案例</span>
      </div>
      <div class="card-body p-0">
        <div class="data-table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>關聯 Bot</th>
                <th>終態狀態</th>
                <th>進度 (Bar)</th>
                <th>撮合成交</th>
                <th>終態持倉</th>
                <th>帳戶淨值 (USDT)</th>
                <th>累積手續費</th>
                <th>部位獨佔保留</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in runs" :key="r.run_id">
                <td class="mono text-2xs">{{ r.run_id.slice(0, 16) }}...</td>
                <td class="mono">{{ r.bot_id }}</td>
                <td><StatusBadge :status="r.control_state" /></td>
                <td class="tabular-nums">{{ r.current_bar }}/{{ r.total_bars }}</td>
                <td class="tabular-nums">{{ r.trade_count }} 筆</td>
                <td class="tabular-nums">
                  <span :class="r.position_contracts !== '0' ? 'text-accent font-bold' : ''">
                    {{ r.position_contracts }} 張
                  </span>
                </td>
                <td class="tabular-nums font-mono">{{ r.equity_usdt }}</td>
                <td class="tabular-nums font-mono text-muted">{{ r.fee_usdt }}</td>
                <td>
                  <span v-if="r.ownership_retained" class="badge badge-sm badge-danger">409 鎖定</span>
                  <span v-else class="badge badge-sm badge-neutral">已釋放</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Allocate Modal -->
    <div v-if="showAllocateModal" class="modal-backdrop">
      <div class="modal-box card">
        <div class="card-header">
          <div class="card-title">人工審閱並分配新機器人</div>
          <button type="button" class="btn-close" @click="closeAllocateModal">✕</button>
        </div>
        <div class="card-body modal-form">
          <div class="form-group">
            <label class="form-label">機器人識別碼 (Bot ID)</label>
            <input
              v-model="newBotId"
              type="text"
              class="form-input"
              placeholder="例如: review-new-bot 或 bot-sol-01"
            />
          </div>

          <div class="form-group">
            <label class="form-label">選擇策略製品 (不可變版本快照)</label>
            <select v-model="selectedStrategyHash" class="form-select">
              <option
                v-for="s in strategies"
                :key="s.artifact_hash"
                :value="s.artifact_hash"
              >
                {{ s.artifact.name }} (v{{ s.artifact.version }} · Hash: {{ s.artifact_hash.slice(0, 8) }})
              </option>
            </select>
          </div>

          <!-- Strategy details review -->
          <div v-if="selectedStrategy" class="strategy-review-box">
            <div class="review-row">
              <span class="lbl">策略 ID:</span>
              <span class="mono">{{ selectedStrategy.artifact.strategy_id }} (v{{ selectedStrategy.artifact.version }})</span>
            </div>
            <div class="review-row">
              <span class="lbl">完整 Hash:</span>
              <span class="mono text-2xs text-accent">{{ selectedStrategy.artifact_hash }}</span>
            </div>
            <div class="review-row">
              <span class="lbl">策略說明:</span>
              <span>{{ selectedStrategy.artifact.description }}</span>
            </div>
          </div>

          <!-- Bounded JSON parameters input -->
          <div class="form-group">
            <label class="form-label">
              策略執行參數 (通用有界 JSON 契約，禁用 float，小數使用 Decimal 字串)
            </label>
            <textarea
              v-model="customParametersJson"
              class="form-textarea mono text-2xs"
              rows="4"
              placeholder='{"period": "2", "quantity": "2"}'
            ></textarea>
          </div>

          <div class="trust-confirmation-box">
            <label class="trust-checkbox-label">
              <input v-model="isTrusted" type="checkbox" class="trust-checkbox" />
              <span>我已親自審閱此策略原始碼與相依套件，確認並給予人工授權信任。</span>
            </label>
            <div class="trust-note">
              依據受信邊界政策（P1）：策略以普通獨立 Python Worker 執行，非 OS 安全沙箱。切換策略或重新開啟必須重新審閱確認，嚴禁預先勾選信任。
            </div>
          </div>

          <div class="modal-actions">
            <button type="button" class="btn btn-secondary" @click="closeAllocateModal">取消</button>
            <button
              type="button"
              class="btn btn-primary"
              :disabled="!isTrusted || isSubmitting"
              @click="handleAllocate"
            >
              {{ isSubmitting ? '建立中...' : '確認建立並綁定快照' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bots-page {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  height: 100%;
  overflow-y: auto;
}

.action-buttons {
  display: flex;
  gap: 6px;
}

.banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
}

.banner-warning {
  background: var(--color-warning-bg);
  border: 1px solid var(--color-warning-border);
  color: #ffe6b0;
}

.banner-danger {
  background: var(--color-danger-bg);
  border: 1px solid var(--color-danger-border);
  color: #ffc2bf;
}

.banner-info {
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.4);
  color: #93c5fd;
}

.banner-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.banner-actions {
  display: flex;
  gap: 6px;
}

.strategy-review-box {
  background: var(--bg-surface);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-xs);
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 11px;
}

.review-row {
  display: flex;
  gap: 6px;
}

.review-row .lbl {
  color: var(--text-muted);
  flex-shrink: 0;
}

.form-textarea {
  padding: 8px 10px;
  background: var(--bg-base);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-xs);
  color: var(--text-primary);
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  resize: vertical;
}

/* Modal styles */
.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-box {
  width: 520px;
  max-width: 90vw;
  background: var(--bg-surface-elevated);
}

.btn-close {
  color: var(--text-muted);
  background: transparent;
  border: none;
  font-size: 16px;
  cursor: pointer;
}

.modal-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  font-weight: 500;
}

.form-input, .form-select {
  padding: 8px 10px;
  background: var(--bg-base);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-xs);
  color: var(--text-primary);
  font-size: var(--text-xs);
  font-family: var(--font-sans);
}

.trust-confirmation-box {
  background: var(--color-warning-bg);
  border: 1px solid var(--color-warning-border);
  padding: 12px;
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.trust-checkbox-label {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: var(--text-xs);
  color: #ffdf9e;
  cursor: pointer;
}

.trust-checkbox {
  margin-top: 2px;
}

.trust-note {
  font-size: 10px;
  color: var(--text-muted);
  line-height: 1.4;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.p-0 { padding: 0 !important; }
.p-4 { padding: var(--space-4) !important; }
.font-bold { font-weight: 700; }
.text-accent { color: var(--accent); }
.text-success { color: var(--color-success); }
.text-danger { color: var(--color-danger); }
.text-center { text-align: center; }

/* Lower Operational Grid */
.bots-lower-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
  margin-top: var(--space-4);
}

.worker-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.worker-item {
  padding: 10px 12px;
  background: var(--bg-surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: all 0.15s ease;
}

.worker-item:hover {
  border-color: var(--border-highlight);
  background: var(--bg-surface-hover);
}

.worker-item.is-inactive {
  opacity: 0.65;
  background: var(--bg-base);
}

.worker-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.worker-pid {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  background: var(--bg-base);
  padding: 1px 5px;
  border-radius: 2px;
}

.worker-tag {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}

.worker-meta {
  display: flex;
  gap: 12px;
  font-size: 10.5px;
  color: var(--text-secondary);
}

.ipc-invariants-box {
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-secondary);
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 11px;
}

.inv-row {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
}

.inv-badge.ok {
  color: var(--color-success);
  font-weight: 700;
}

/* Bot Activity Stream */
.bot-stream-list {
  display: flex;
  flex-direction: column;
  max-height: 320px;
  overflow-y: auto;
}

.bot-stream-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-secondary);
  font-size: 11.5px;
  transition: background-color 0.1s ease;
}

.bot-stream-item:hover {
  background-color: var(--bg-surface-hover);
}

.stream-time {
  font-size: 10px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  flex-shrink: 0;
}

.stream-text {
  color: var(--text-primary);
  flex: 1;
  font-size: 11.5px;
}
</style>
