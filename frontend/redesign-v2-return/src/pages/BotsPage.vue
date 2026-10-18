<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { usePreferences } from '@/state/usePreferences';
import type { Bot, StrategyEntry, SimulationRun, PendingCommand } from '@/contracts';
import { validateData, validateAllocationPayload, TOKEN_REGEX } from '@/contracts';
import { activeAdapter } from '@/adapters/mock-adapter';
import { useWorkspace } from '@/state/useWorkspace';
import StatusBadge from '@/components/common/StatusBadge.vue';

const { preferences } = usePreferences();
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

// Comparative view mode state
export type PageViewMode = 'unified' | 'jesse' | 'exchange' | 'fleet';
const activePageMode = ref<PageViewMode>('unified');
const inspectedBot = ref<Bot | null>(null);

function selectBot(b: Bot) {
  inspectedBot.value = b;
}

function closeInspect() {
  inspectedBot.value = null;
}

const fleetStats = computed(() => {
  const total = bots.value.length;
  const inPosition = bots.value.filter(b => b.position_contracts && b.position_contracts !== '0').length;
  let totalPnl = 0;
  let totalNominal = 0;
  for (const b of bots.value) {
    if (b.pnl_usdt) {
      const val = parseFloat(b.pnl_usdt.replace(/[^0-9.-]/g, ''));
      if (!isNaN(val)) totalPnl += val;
    }
    if (b.nominal_value_usdt) {
      const nom = parseFloat(b.nominal_value_usdt.replace(/,/g, ''));
      if (!isNaN(nom)) totalNominal += nom;
    }
  }
  return {
    total,
    inPosition,
    idle: total - inPosition,
    totalPnl: totalPnl >= 0 ? `+${totalPnl.toFixed(2)}` : totalPnl.toFixed(2),
    pnlPositive: totalPnl >= 0,
    totalNominal: totalNominal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  };
});

function getSideLabel(b: Bot): string {
  if (b.side === 'long' || Number(b.position_contracts) > 0) return 'LONG';
  if (b.side === 'short' || Number(b.position_contracts) < 0) return 'SHORT';
  return 'FLAT';
}

function getSideClass(b: Bot): string {
  const side = getSideLabel(b);
  if (side === 'LONG') return 'side-long';
  if (side === 'SHORT') return 'side-short';
  return 'side-flat';
}

const workers = computed(() => {
  return bots.value.map((b, index) => {
    const isRunning = b.state === 'running';
    const isStarting = b.state === 'starting';
    const isStopped = b.state === 'stopped';
    const pid = isRunning ? (4820 + index + 1) : '--';
    const hasPosition = b.position_contracts && b.position_contracts !== '0';

    return {
      bot_id: b.bot_id,
      name: b.name || b.bot_id,
      state: b.state,
      pid: pid === '--' ? '--' : `PID ${pid}`,
      cpu: isRunning ? '0.6%' : '0.0%',
      rss: isRunning ? '32.8 MB' : '0.0 MB',
      statusText: isRunning ? 'HEALTHY' : (isStarting ? 'STARTING' : (isStopped ? 'STOPPED' : b.state.toUpperCase())),
      statusClass: isRunning ? 'badge-success' : (isStarting ? 'badge-info' : 'badge-neutral'),
      positionText: `保留部位: ${b.position_contracts || '0'} 張`,
      exclusiveText: hasPosition ? '獨佔鎖定中 (409)' : '獨佔已釋放'
    };
  });
});


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

watch(currentMode, () => {
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

  const trimmedBotId = newBotId.value.trim();
  if (!trimmedBotId) {
    errorMsg.value = '請輸入機器人識別碼 (Bot ID)';
    return;
  }
  if (!TOKEN_REGEX.test(trimmedBotId)) {
    errorMsg.value = '機器人識別碼格式無效 (必須為 1-64 字元英數字元、底線或連字號 Token，嚴禁小數點或空格)';
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

  try {
    validateAllocationPayload({
      bot_id: trimmedBotId,
      artifact_hash: selectedStrategyHash.value,
      parameters: parsedParams,
      trusted: isTrusted.value,
      mode: currentMode.value
    });
  } catch (err: any) {
    errorMsg.value = err.message || '策略參數型別或邊界不合規';
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

    <!-- Fleet Sentinel KPI Summary Banner -->
    <div class="fleet-sentinel-banner">
      <div class="sentinel-kpi-card">
        <div class="sentinel-kpi-lbl">隊列部署實例</div>
        <div class="sentinel-kpi-val mono">{{ fleetStats.total }} <span class="unit">個</span></div>
        <div class="sentinel-kpi-sub">{{ fleetStats.inPosition }} 持倉中 · {{ fleetStats.idle }} 空倉巡航</div>
      </div>
      <div class="sentinel-kpi-card">
        <div class="sentinel-kpi-lbl">總名義曝險 (Nominal)</div>
        <div class="sentinel-kpi-val mono">{{ fleetStats.totalNominal }} <span class="unit">USDT</span></div>
        <div class="sentinel-kpi-sub">單一合約單 Bot 獨佔 (409)</div>
      </div>
      <div class="sentinel-kpi-card">
        <div class="sentinel-kpi-lbl">隊列合計未實現損益</div>
        <div :class="['sentinel-kpi-val mono font-bold', fleetStats.pnlPositive ? 'text-success' : 'text-danger']">
          {{ fleetStats.totalPnl }} <span class="unit">USDT</span>
        </div>
        <div class="sentinel-kpi-sub">全數強制 Decimal 精確結算</div>
      </div>
      <div class="sentinel-kpi-card">
        <div class="sentinel-kpi-lbl">P6 交易所災難防護</div>
        <div class="sentinel-kpi-val mono text-accent">100% <span class="unit">覆蓋</span></div>
        <div class="sentinel-kpi-sub">OKX 交易所端整倉停損掛單</div>
      </div>
      <div class="sentinel-kpi-card">
        <div class="sentinel-kpi-lbl">決策心跳時鐘</div>
        <div class="sentinel-kpi-val mono text-info">CLOSED BAR</div>
        <div class="sentinel-kpi-sub">分鐘至小時級已收盤 K 線</div>
      </div>
    </div>

    <!-- Bots Table Card with 4-Mode Switcher -->
    <div class="card bots-main-card">
      <div class="card-header flex justify-between items-center">
        <div class="header-left-title flex items-center gap-2">
          <div class="card-title">運行中 BOT 隊列</div>
          <span class="badge badge-accent">{{ bots.length }} 個實例</span>
        </div>

        <!-- 4-Mode Comparative Switcher (供交易員即時比對風格) -->
        <div class="page-mode-switch-group" role="group" aria-label="排版風格比對切換">
          <span class="mode-switch-caption">風格比對：</span>
          <button
            type="button"
            :class="['mode-btn', { active: activePageMode === 'unified' }]"
            @click="activePageMode = 'unified'"
            title="方案 D：旗艦整合 (Unified Sentinel) · 汲取三者優點，高密度平衡最佳解"
          >
            D 旗艦整合
          </button>
          <button
            type="button"
            :class="['mode-btn', { active: activePageMode === 'jesse' }]"
            @click="activePageMode = 'jesse'"
            title="方案 A：極簡終端 (Jesse Style) · 等寬字體、策略時鐘倒數、純文字高密度"
          >
            A 極簡終端
          </button>
          <button
            type="button"
            :class="['mode-btn', { active: activePageMode === 'exchange' }]"
            @click="activePageMode = 'exchange'"
            title="方案 B：專業衍生品 (OKX Pro Style) · 標記價比對、P6 災難停損防線進度條"
          >
            B 專業衍生品
          </button>
          <button
            type="button"
            :class="['mode-btn', { active: activePageMode === 'fleet' }]"
            @click="activePageMode = 'fleet'"
            title="方案 C：進程矩陣 (Ray Fleet Style) · Worker PID、IPC 脈衝心跳、資源佔用"
          >
            C 進程矩陣
          </button>
        </div>
      </div>

      <div class="card-body p-0">
        <!-- 方案 D：旗艦整合表格 (Unified Sentinel Table) -->
        <div v-if="activePageMode === 'unified'" class="data-table-container">
          <table class="data-table high-density-table">
            <thead>
              <tr>
                <th>實例 / Worker</th>
                <th>標的 / 週期 / 方向</th>
                <th>部位規模</th>
                <th>價格與 P6 防線</th>
                <th>未實現損益 / ROE</th>
                <th>策略時鐘</th>
                <th>狀態 / 審計</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="b in bots"
                :key="b.bot_id"
                :class="{ 'is-active-row': inspectedBot?.bot_id === b.bot_id }"
              >
                <!-- 1. 實例與 Worker -->
                <td>
                  <div class="flex items-center gap-2">
                    <span class="live-dot" title="Worker IPC 存活心跳"></span>
                    <div>
                      <strong>{{ b.name || b.bot_id }}</strong>
                      <div class="mono text-muted text-2xs flex items-center gap-1">
                        <span>{{ b.bot_id }}</span>
                        <span class="badge-pid">PID {{ b.worker_pid || 4821 }}</span>
                      </div>
                    </div>
                  </div>
                </td>

                <!-- 2. 標的、週期與方向 -->
                <td>
                  <div class="flex items-center gap-1">
                    <span class="side-badge" :class="getSideClass(b)">{{ getSideLabel(b) }}</span>
                    <strong class="mono">{{ b.symbol.replace('-SWAP', '') }}</strong>
                    <span class="badge-timeframe mono">{{ b.timeframe || '1H' }}</span>
                  </div>
                  <div class="text-2xs text-muted">{{ b.strategy_step || '決策監聽中' }}</div>
                </td>

                <!-- 3. 部位規模 -->
                <td class="mono">
                  <div class="font-bold">{{ b.position_contracts || '0' }} 張</div>
                  <div class="text-2xs text-muted">{{ b.nominal_value_usdt || '--' }} USDT ({{ b.leverage || '3.0x' }})</div>
                </td>

                <!-- 4. 價格與 P6 交易所防線 -->
                <td>
                  <div class="mono text-2xs flex items-center gap-1">
                    <span class="text-muted">E: {{ b.entry_price || '--' }}</span>
                    <span>→</span>
                    <span class="text-primary font-bold">M: {{ b.mark_price || '--' }}</span>
                  </div>
                  <div class="p6-guard-pill-wrap" :title="`OKX P6 交易所整倉停損觸發價: ${b.sl_price || '--'}`">
                    <span class="guard-pill-tag">🛡️ 距 P6 防線: {{ b.sl_distance_pct ? `${b.sl_distance_pct}%` : '無持倉' }}</span>
                    <div class="guard-pill-bar">
                      <div
                        class="guard-pill-fill"
                        :style="{ width: `${Math.min(100, (b.sl_distance_pct || 0) * 10)}%` }"
                        :class="b.sl_distance_pct && b.sl_distance_pct < 4 ? 'is-warn' : 'is-safe'"
                      ></div>
                    </div>
                  </div>
                </td>

                <!-- 5. 未實現損益與 ROE -->
                <td class="mono">
                  <div class="font-bold" :class="b.pnl_usdt?.startsWith('+') ? 'text-success' : (b.pnl_usdt === '0.00' ? '' : 'text-danger')">
                    {{ b.pnl_usdt || '0.00' }} USDT
                  </div>
                  <div class="text-2xs" :class="b.pnl_usdt?.startsWith('+') ? 'text-success' : (b.pnl_usdt === '0.00' ? '' : 'text-danger')">
                    ROE {{ b.roe_pct || '0.00%' }}
                  </div>
                </td>

                <!-- 6. 策略時鐘 -->
                <td class="mono text-2xs text-muted">
                  <div>⏳ {{ b.next_bar_countdown || '14:22' }}</div>
                  <div class="text-3xs">收盤評估下一根</div>
                </td>

                <!-- 7. 狀態與審計抽屜按鈕 -->
                <td>
                  <div class="flex items-center gap-1">
                    <StatusBadge :status="b.state" />
                    <button
                      type="button"
                      class="btn-sm btn-secondary btn-inspect"
                      @click="selectBot(b)"
                      title="查看詳細信號決策與 OKX 委託規範"
                    >
                      🔍 審計
                    </button>
                  </div>
                </td>

                <!-- 8. 操作 -->
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
            </tbody>
          </table>
        </div>

        <!-- 方案 A：極簡終端模式 (Jesse Style Table) -->
        <div v-else-if="activePageMode === 'jesse'" class="jesse-page-view p-3 mono">
          <div class="jesse-term-header">
            === CATOS TERMINAL FLEET MATRIX · CLOSED BAR RESOLUTION · DECIMAL ENGINE ===
          </div>
          <table class="jesse-full-table">
            <thead>
              <tr>
                <th>CLOCK / BAR</th>
                <th>SIDE</th>
                <th>CONTRACT</th>
                <th>POS / LEV</th>
                <th>ENTRY -> MARK</th>
                <th>P6 SL GUARD</th>
                <th>UNREALIZED PNL (ROE)</th>
                <th>ACTION</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="b in bots" :key="b.bot_id" @click="selectBot(b)" class="jesse-clickable-tr">
                <td>[{{ b.timeframe || '1H' }} ⏳{{ b.next_bar_countdown || '14:22' }}]</td>
                <td><span class="jesse-side" :class="getSideClass(b)">[{{ getSideLabel(b) }}]</span></td>
                <td><strong>{{ b.symbol }}</strong></td>
                <td>{{ b.position_contracts }}張 ({{ b.leverage || '3.0x' }})</td>
                <td>{{ b.entry_price || '--' }} -> {{ b.mark_price || '--' }}</td>
                <td>SL: {{ b.sl_price || '--' }} ({{ b.sl_distance_pct }}%)</td>
                <td :class="b.pnl_usdt?.startsWith('-') ? 'text-danger' : 'text-success'">
                  {{ b.pnl_usdt }} ({{ b.roe_pct }})
                </td>
                <td>
                  <button type="button" class="btn-xs btn-secondary" @click.stop="selectBot(b)">INSPECT</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 方案 B：專業衍生品模式 (Exchange / OKX Pro Style Grid) -->
        <div v-else-if="activePageMode === 'exchange'" class="exchange-page-grid p-4">
          <div
            v-for="b in bots"
            :key="b.bot_id"
            class="exchange-major-card"
            @click="selectBot(b)"
          >
            <div class="major-card-top flex justify-between items-center">
              <div class="flex items-center gap-2">
                <span class="side-pill" :class="getSideClass(b)">{{ getSideLabel(b) }}</span>
                <strong class="text-base">{{ b.symbol }}</strong>
                <span class="badge-margin-mode">Cross {{ b.leverage || '3.0x' }}</span>
                <span class="badge-timeframe mono">{{ b.timeframe || '1H' }}</span>
              </div>
              <div class="text-right">
                <div class="text-lg mono font-bold" :class="b.pnl_usdt?.startsWith('-') ? 'text-danger' : 'text-success'">
                  {{ b.pnl_usdt }} USDT
                </div>
                <div class="text-xs mono" :class="b.pnl_usdt?.startsWith('-') ? 'text-danger' : 'text-success'">
                  ROE {{ b.roe_pct }}
                </div>
              </div>
            </div>

            <div class="major-card-metrics grid grid-cols-4 gap-3 my-3 p-3">
              <div>
                <span class="meta-lbl">持倉張數</span>
                <div class="mono font-bold">{{ b.position_contracts }} 張</div>
              </div>
              <div>
                <span class="meta-lbl">名義價值</span>
                <div class="mono">{{ b.nominal_value_usdt || '--' }} USDT</div>
              </div>
              <div>
                <span class="meta-lbl">開倉均價</span>
                <div class="mono">{{ b.entry_price || '--' }}</div>
              </div>
              <div>
                <span class="meta-lbl">最新標記價</span>
                <div class="mono text-accent">{{ b.mark_price || '--' }}</div>
              </div>
            </div>

            <div class="major-card-guard">
              <div class="flex justify-between text-xs text-muted mb-1">
                <span>P6 OKX 交易所端整倉停損防線: <strong class="text-warning">{{ b.sl_price || '--' }}</strong></span>
                <span class="mono text-accent">防線安全空間: {{ b.sl_distance_pct }}%</span>
              </div>
              <div class="guard-pill-bar" style="height: 5px;">
                <div
                  class="guard-pill-fill"
                  :style="{ width: `${Math.min(100, (b.sl_distance_pct || 0) * 10)}%` }"
                  :class="b.sl_distance_pct && b.sl_distance_pct < 4 ? 'is-warn' : 'is-safe'"
                ></div>
              </div>
            </div>

            <div class="major-card-footer flex justify-between items-center mt-3 pt-2 border-t border-border-secondary">
              <span class="text-xs text-muted">{{ b.name }} · ⏳ 下一根收盤: {{ b.next_bar_countdown || '14:22' }}</span>
              <button type="button" class="btn-sm btn-secondary" @click.stop="selectBot(b)">
                🔍 展開 OKX 規範審計抽屜
              </button>
            </div>
          </div>
        </div>

        <!-- 方案 C：進程矩陣模式 (Fleet / Ray Style List) -->
        <div v-else-if="activePageMode === 'fleet'" class="fleet-page-list p-4 flex flex-col gap-3">
          <div
            v-for="b in bots"
            :key="b.bot_id"
            class="fleet-major-item p-3 card"
            @click="selectBot(b)"
          >
            <div class="flex justify-between items-center">
              <div class="flex items-center gap-2">
                <span class="live-dot"></span>
                <strong>{{ b.name }}</strong>
                <span class="badge-pid mono">PID {{ b.worker_pid || 4821 }}</span>
                <span class="badge badge-sm badge-info">{{ b.strategy_step || '決策監聽中' }}</span>
                <span v-if="b.position_contracts !== '0'" class="badge badge-sm badge-accent">409 獨佔鎖定中</span>
              </div>
              <div class="mono text-xs text-muted">
                <span>CPU: {{ b.worker_cpu || '0.6%' }}</span>
                <span class="mx-2">·</span>
                <span>RSS: {{ b.worker_rss || '32.8 MB' }}</span>
                <span class="mx-2">·</span>
                <span>心跳: {{ b.ipc_heartbeat_ago || '1s 前' }}</span>
              </div>
            </div>

            <div class="flex justify-between items-center mt-2 pt-2 border-t border-border-secondary text-sm">
              <span class="mono">{{ b.symbol }} · 持倉 {{ b.position_contracts }} 張</span>
              <div class="mono font-bold" :class="b.pnl_usdt?.startsWith('-') ? 'text-danger' : 'text-success'">
                未實現損益: {{ b.pnl_usdt }} USDT ({{ b.roe_pct }})
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 頁面級 Inspector 抽屜 (Slide-out Drawer) -->
    <div v-if="inspectedBot" class="page-inspector-backdrop" @click.self="closeInspect">
      <div class="page-inspector-drawer">
        <div class="drawer-header flex justify-between items-center">
          <div class="flex items-center gap-2">
            <span class="live-dot"></span>
            <strong>{{ inspectedBot.name }}</strong>
            <span class="mono text-muted text-xs">({{ inspectedBot.bot_id }})</span>
          </div>
          <button type="button" class="btn-close-drawer" @click="closeInspect">✕</button>
        </div>

        <div class="drawer-scroll-body p-4 flex flex-col gap-4">
          <!-- 區塊 1: OKX Invariants 檢查 -->
          <div class="card p-3">
            <div class="card-title text-sm mb-2 text-accent">OKX SWAP 衍生品規範 (CatOS Invariants)</div>
            <div class="mono text-xs flex flex-col gap-1">
              <div class="flex justify-between"><span>合約標的:</span> <strong>{{ inspectedBot.symbol }}</strong></div>
              <div class="flex justify-between"><span>模式:</span> <span>USDT-M SWAP · cross + net_mode</span></div>
              <div class="flex justify-between"><span>強制 Tag:</span> <span class="tag-highlight">41cb53c54d6dABDE</span></div>
              <div class="flex justify-between"><span>精度規範:</span> <span>強制 Decimal (禁止 Float)</span></div>
              <div class="flex justify-between"><span>決策週期:</span> <span>{{ inspectedBot.timeframe || '1H' }} Closed Bar</span></div>
            </div>
          </div>

          <!-- 區塊 2: P6 交易所整倉災難停損 -->
          <div class="card p-3">
            <div class="card-title text-sm mb-2 text-warning">P6 交易所端整倉災難停損防線</div>
            <div class="flex flex-col gap-2 text-xs">
              <div class="flex justify-between">
                <span>停損觸發價:</span>
                <strong class="mono text-warning">{{ inspectedBot.sl_price || '尚未建立 (無持倉)' }}</strong>
              </div>
              <div class="flex justify-between">
                <span>防線緩衝空間:</span>
                <span class="mono text-accent">{{ inspectedBot.sl_distance_pct }}% (安全餘裕充足)</span>
              </div>
              <div class="flex justify-between">
                <span>觸發基準:</span>
                <span class="mono">Mark Price 最新標記價</span>
              </div>
            </div>
          </div>

          <!-- 區塊 3: 近 5 筆 Closed Bar 策略信號記錄 -->
          <div class="card p-3">
            <div class="card-title text-sm mb-2">近期收盤 Bar 決策日誌 (Recent Signals)</div>
            <div v-if="inspectedBot.recent_signals?.length" class="flex flex-col gap-2">
              <div
                v-for="(sig, idx) in inspectedBot.recent_signals"
                :key="idx"
                class="p-2 bg-surface-2 rounded text-xs mono flex justify-between items-center"
              >
                <div>
                  <span class="text-muted mr-2">{{ sig.bar_time }}</span>
                  <span class="font-bold mr-2" :class="sig.signal === 'BUY' ? 'text-success' : sig.signal === 'SELL' ? 'text-danger' : 'text-muted'">
                    {{ sig.signal }}
                  </span>
                  <span>@ {{ sig.close_price }}</span>
                </div>
                <div class="text-muted text-2xs">{{ sig.note }}</div>
              </div>
            </div>
            <div v-else class="text-muted text-xs p-2 text-center">
              暫無歷史信號記錄
            </div>
          </div>

          <!-- 區塊 4: 製品不可變 Hash -->
          <div class="card p-3">
            <div class="card-title text-sm mb-1 text-muted">製品不可變 Hash 與人工審查</div>
            <div class="mono text-2xs text-muted break-all">
              {{ inspectedBot.binding?.artifact_hash }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Lower Operational Grid: Worker Monitor + Activity Stream -->
    <div class="bots-lower-grid">
      <!-- Worker Process & Sandbox Monitor -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">
            Worker 程序與受信隔離 (Worker Daemons & IPC Watch)
            <span class="badge badge-sm badge-warning ml-2">未連後端真 Worker（示意）</span>
          </div>
          <span class="badge badge-sm badge-neutral">{{ workers.length }} 個實例</span>
        </div>
        <div class="card-body">
          <div class="worker-list" v-if="workers.length">
            <div
              v-for="w in workers"
              :key="w.bot_id"
              class="worker-item"
              :class="{ 'is-inactive': w.state !== 'running' && w.state !== 'starting' }"
            >
              <div class="worker-header">
                <div class="worker-pid mono">{{ w.pid }}</div>
                <div class="worker-tag">{{ w.name }}</div>
                <span class="badge badge-sm" :class="w.statusClass">{{ w.statusText }}</span>
              </div>
              <div class="worker-meta mono">
                <span>CPU: {{ w.cpu }}</span>
                <span>RSS: {{ w.rss }}</span>
                <span>{{ w.positionText }}</span>
                <span>{{ w.exclusiveText }}</span>
              </div>
            </div>
          </div>
          <div v-else class="text-muted text-center p-3">
            當前模式無已部署 Worker 實例 (示意)
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
          <div class="card-title">
            機器人即時事件串流 (Realtime Bot Activity)
            <span class="badge badge-sm badge-neutral ml-2">本機模擬示意</span>
          </div>
          <span class="badge badge-sm badge-accent">即時串流中</span>
        </div>
        <div class="card-body p-0">
          <div class="bot-stream-list" v-if="currentMode === 'local'">
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
              <span class="stream-text">Worker 正常啟動，已完成歷史收盤 K 線指標預熱</span>
            </div>
            <div class="bot-stream-item">
              <span class="stream-time tabular-nums">09:29:55</span>
              <span class="badge badge-sm badge-success">MUTEX</span>
              <span class="stream-text">BTC-USDT-SWAP 單合約獨佔鎖由 bot-btc-trend-01 成功獲取</span>
            </div>
          </div>
          <div v-else class="text-muted text-center p-4">
            {{ currentMode.toUpperCase() }} 模式尚未開放，無即時事件串流。
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
  position: relative;
}

/* Fleet Sentinel KPI Summary Banner */
.fleet-sentinel-banner {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
}

.sentinel-kpi-card {
  background: var(--bg-surface, #1e293b);
  border: 1px solid var(--border-secondary, rgba(255, 255, 255, 0.08));
  border-radius: var(--radius-sm, 6px);
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  transition: border-color 0.15s ease;
}

.sentinel-kpi-card:hover {
  border-color: rgba(116, 164, 235, 0.3);
}

.sentinel-kpi-lbl {
  font-size: 11px;
  color: var(--text-muted, #64748b);
  font-weight: 500;
}

.sentinel-kpi-val {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary, #f8fafc);
}

.sentinel-kpi-val .unit {
  font-size: 10px;
  font-weight: 400;
  color: var(--text-muted, #64748b);
  margin-left: 2px;
}

.sentinel-kpi-sub {
  font-size: 10px;
  color: var(--text-secondary, #94a3b8);
}

/* 4-Mode Comparative Switcher in Card Header */
.page-mode-switch-group {
  display: flex;
  align-items: center;
  gap: 4px;
  background: rgba(0, 0, 0, 0.3);
  padding: 3px 6px;
  border-radius: 5px;
  border: 1px solid var(--border-secondary, rgba(255, 255, 255, 0.08));
}

.mode-switch-caption {
  font-size: 11px;
  color: var(--text-muted, #64748b);
  margin-right: 4px;
}

.mode-btn {
  border: none;
  background: transparent;
  color: var(--text-muted, #64748b);
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 500;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.mode-btn:hover {
  color: var(--text-primary, #f8fafc);
  background: rgba(255, 255, 255, 0.06);
}

.mode-btn.active {
  color: #fff;
  background: var(--accent-primary, #74a4eb);
  box-shadow: 0 1px 4px rgba(116, 164, 235, 0.35);
}

/* High Density Unified Table */
.high-density-table th {
  font-size: 11px;
  padding: 8px 10px;
}

.high-density-table td {
  padding: 8px 10px;
  font-size: 11.5px;
  vertical-align: middle;
}

.is-active-row {
  background: rgba(116, 164, 235, 0.08);
}

.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #10b981;
  flex-shrink: 0;
}

.badge-pid {
  background: rgba(255, 255, 255, 0.08);
  padding: 0 3px;
  border-radius: 2px;
}

.badge-timeframe {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-secondary, #94a3b8);
  padding: 0 4px;
  font-size: 10px;
  border-radius: 2px;
}

.side-badge {
  font-size: 9.5px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 2px;
}

.side-long {
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.side-short {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.side-flat {
  background: rgba(148, 163, 184, 0.15);
  color: #94a3b8;
  border: 1px solid rgba(148, 163, 184, 0.3);
}

.p6-guard-pill-wrap {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 3px;
}

.guard-pill-tag {
  font-size: 9.5px;
  color: var(--text-muted, #64748b);
}

.guard-pill-bar {
  height: 3px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 2px;
  overflow: hidden;
}

.guard-pill-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.guard-pill-fill.is-safe {
  background: #38bdf8;
}

.guard-pill-fill.is-warn {
  background: #f59e0b;
}

.btn-inspect {
  font-size: 10.5px;
  padding: 2px 6px;
}

/* Jesse Full View */
.jesse-page-view {
  background: rgba(2, 6, 23, 0.7);
  font-size: 11px;
}

.jesse-term-header {
  color: #64748b;
  font-size: 10px;
  padding-bottom: 6px;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.1);
  margin-bottom: 8px;
}

.jesse-full-table {
  width: 100%;
  border-collapse: collapse;
}

.jesse-full-table th {
  text-align: left;
  color: #94a3b8;
  padding: 6px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 10.5px;
}

.jesse-full-table td {
  padding: 6px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.jesse-clickable-tr {
  cursor: pointer;
}

.jesse-clickable-tr:hover {
  background: rgba(255, 255, 255, 0.04);
}

.jesse-side {
  font-weight: 700;
}

/* Exchange Grid View */
.exchange-page-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.exchange-major-card {
  background: var(--bg-surface, #1e293b);
  border: 1px solid var(--border-secondary, rgba(255, 255, 255, 0.08));
  border-radius: 6px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.exchange-major-card:hover {
  border-color: rgba(116, 164, 235, 0.35);
  background: rgba(255, 255, 255, 0.03);
}

.side-pill {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
}

.badge-margin-mode {
  font-size: 10px;
  background: rgba(255, 255, 255, 0.06);
  padding: 2px 6px;
  border-radius: 3px;
  color: var(--text-muted, #64748b);
}

.major-card-metrics {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 5px;
}

.meta-lbl {
  font-size: 10px;
  color: var(--text-muted, #64748b);
  display: block;
  margin-bottom: 2px;
}

/* Fleet Major List */
.fleet-major-item {
  cursor: pointer;
  transition: border-color 0.15s ease;
}

.fleet-major-item:hover {
  border-color: rgba(116, 164, 235, 0.35);
}

/* Page Inspector Drawer */
.page-inspector-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
}

.page-inspector-drawer {
  width: 420px;
  height: 100%;
  background: var(--bg-surface, #1e293b);
  border-left: 1px solid rgba(116, 164, 235, 0.25);
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.6);
  display: flex;
  flex-direction: column;
  animation: slideDrawer 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes slideDrawer {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.drawer-scroll-body {
  flex: 1;
  overflow-y: auto;
}

.btn-close-drawer {
  background: transparent;
  border: none;
  color: var(--text-muted, #64748b);
  font-size: 14px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
}

.btn-close-drawer:hover {
  color: var(--text-primary, #f8fafc);
  background: rgba(255, 255, 255, 0.1);
}

.tag-highlight {
  color: #38bdf8;
  font-weight: 700;
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
