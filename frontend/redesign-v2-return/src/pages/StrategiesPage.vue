<script setup lang="ts">
import { ref, onMounted } from 'vue';
import type { StrategyEntry, StrategyArtifact } from '@/contracts';
import { validateArtifact, TOKEN_REGEX } from '@/contracts';
import { activeAdapter } from '@/adapters/mock-adapter';

const strategies = ref<StrategyEntry[]>([]);
const selectedStrategy = ref<StrategyEntry | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);

const errorMsg = ref<string | null>(null);
const successMsg = ref<string | null>(null);
const isImporting = ref<boolean>(false);

// Metadata Form Modal State (aligned with v1 DOM contracts: import-id, import-version, etc.)
const showImportModal = ref<boolean>(false);
const importId = ref<string>('');
const importVersion = ref<string>('v1');
const importName = ref<string>('');
const importDescription = ref<string>('');
const importDefaults = ref<string>('{\n  "quantity": "-1",\n  "hold": false\n}');
const importWarmup = ref<number>(2);
const pendingPySource = ref<string>('');

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

async function loadData() {
  try {
    strategies.value = await activeAdapter.fetchStrategies();
    if (strategies.value.length && (!selectedStrategy.value || !strategies.value.some(s => s.artifact_hash === selectedStrategy.value?.artifact_hash))) {
      selectedStrategy.value = strategies.value[0];
    }
  } catch (err: any) {
    errorMsg.value = err.message || '讀取策略庫失敗';
  }
}

onMounted(() => {
  loadData();
});

function triggerFileInput() {
  errorMsg.value = null;
  successMsg.value = null;
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
    fileInputRef.value.click();
  }
}

async function handleFileUpload(event: Event) {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) return;

  errorMsg.value = null;
  successMsg.value = null;

  try {
    const text = await file.text();

    if (file.name.endsWith('.json')) {
      isImporting.value = true;
      let parsed: any;
      try {
        parsed = JSON.parse(text);
      } catch {
        throw new Error('JSON 檔案格式錯誤，無法解析');
      }

      const manifest = parsed.manifest || parsed;
      // Strict contract validation: 8 exact fields, TOKEN check, warmup range, no floats
      const artifact = validateArtifact(manifest);

      const reqId = generateRequestId();
      const created = await activeAdapter.createStrategy(reqId, artifact);
      await loadData();
      selectedStrategy.value = created;
      successMsg.value = `JSON 策略製品「${artifact.name}」匯入成功，已寫入不可變版本庫。`;
    } else if (file.name.endsWith('.py')) {
      const cleanBase = file.name.replace('.py', '').toLowerCase().replace(/[^a-z0-9_-]/g, '_');
      pendingPySource.value = text;

      // Extract header comments if present
      let extractedId = '';
      let extractedVersion = '';
      let extractedName = '';
      let extractedDesc = '';
      let extractedWarmup: number | null = null;
      let extractedDefaults: any = null;

      const lines = text.split('\n');
      for (const rawLine of lines) {
        const line = rawLine.trim();
        if (line.startsWith('# strategy_id:')) {
          extractedId = line.replace('# strategy_id:', '').trim();
        } else if (line.startsWith('# version:')) {
          extractedVersion = line.replace('# version:', '').trim();
        } else if (line.startsWith('# name:')) {
          extractedName = line.replace('# name:', '').trim();
        } else if (line.startsWith('# description:')) {
          extractedDesc = line.replace('# description:', '').trim();
        } else if (line.startsWith('# warmup_bars:')) {
          const rawW = line.replace('# warmup_bars:', '').trim();
          const w = Number(rawW);
          if (Number.isInteger(w)) extractedWarmup = w;
        } else if (line.startsWith('# defaults:')) {
          try {
            extractedDefaults = JSON.parse(line.replace('# defaults:', '').trim());
          } catch {
            // ignore
          }
        }
      }

      // Populate form state
      importId.value = extractedId || `custom_${cleanBase}`;
      importVersion.value = extractedVersion || 'file-v1';
      importName.value = extractedName || `自訂策略 (${file.name})`;
      importDescription.value = extractedDesc || `由 Python 檔案 ${file.name} 匯入之不可變製品`;
      importWarmup.value = extractedWarmup !== null ? extractedWarmup : 2;
      if (extractedDefaults) {
        importDefaults.value = JSON.stringify(extractedDefaults, null, 2);
      }

      // If all header comments are fully provided and valid TOKEN, auto-import directly
      if (extractedId && extractedVersion && extractedName && extractedDesc && extractedWarmup !== null && extractedDefaults) {
        isImporting.value = true;
        const manifest: StrategyArtifact = {
          contract: 'catos.python-strategy.v1',
          strategy_id: extractedId,
          version: extractedVersion,
          name: extractedName,
          description: extractedDesc,
          source: text,
          defaults: extractedDefaults,
          warmup_bars: extractedWarmup
        };
        const artifact = validateArtifact(manifest);
        const reqId = generateRequestId();
        const created = await activeAdapter.createStrategy(reqId, artifact);
        await loadData();
        selectedStrategy.value = created;
        successMsg.value = `Python 策略製品「${artifact.name}」已依標頭契約自動驗證匯入成功。`;
      } else {
        // Otherwise, open metadata form modal for user review/completion
        showImportModal.value = true;
      }
    } else {
      throw new Error('不支援的檔案格式，請上傳 .py 或 .json 策略製品');
    }
  } catch (err: any) {
    errorMsg.value = err.message || '匯入策略製品失敗';
  } finally {
    isImporting.value = false;
  }
}

async function handleConfirmModalImport() {
  errorMsg.value = null;
  successMsg.value = null;
  isImporting.value = true;

  try {
    let parsedDefaults: any;
    try {
      parsedDefaults = JSON.parse(importDefaults.value);
    } catch {
      throw new Error('預設參數 JSON 格式錯誤，請檢查輸入');
    }

    const manifest: StrategyArtifact = {
      contract: 'catos.python-strategy.v1',
      strategy_id: importId.value.trim(),
      version: importVersion.value.trim(),
      name: importName.value.trim(),
      description: importDescription.value.trim(),
      source: pendingPySource.value,
      defaults: parsedDefaults,
      warmup_bars: Number(importWarmup.value)
    };

    // Strict validation
    const checked = validateArtifact(manifest);
    const reqId = generateRequestId();
    const created = await activeAdapter.createStrategy(reqId, checked);
    await loadData();
    selectedStrategy.value = created;
    successMsg.value = `Python 策略「${checked.name}」元資料確認並匯入成功。`;
    showImportModal.value = false;
  } catch (err: any) {
    errorMsg.value = err.message || '匯入失敗';
  } finally {
    isImporting.value = false;
  }
}
</script>

<template>
  <div class="strategies-page">
    <!-- Hidden file input for .py and .json -->
    <input
      type="file"
      id="strategy-file"
      ref="fileInputRef"
      accept=".py,.json"
      style="display: none"
      @change="handleFileUpload"
    />

    <!-- Teleport Actions to Unified Header -->
    <Teleport to="#header-page-actions">
      <div class="header-actions-group">
        <button
          type="button"
          class="btn btn-sm btn-primary"
          :disabled="isImporting"
          @click="triggerFileInput"
        >
          {{ isImporting ? '匯入中...' : '+ 匯入 .py / JSON 製品' }}
        </button>
      </div>
    </Teleport>

    <!-- Alert banners -->
    <div v-if="errorMsg" class="banner banner-danger">
      <span>{{ errorMsg }}</span>
      <button type="button" class="btn-sm btn-secondary" @click="errorMsg = null">關閉</button>
    </div>
    <div v-if="successMsg" class="banner banner-success">
      <span>{{ successMsg }}</span>
      <button type="button" class="btn-sm btn-secondary" @click="successMsg = null">關閉</button>
    </div>

    <!-- Python Metadata Modal (DOM inputs align with v1.js: import-id, import-version, etc.) -->
    <div v-if="showImportModal" class="modal-backdrop">
      <div class="modal card">
        <div class="card-header">
          <div class="card-title">Python 策略元資料確認 (catos.python-strategy.v1)</div>
          <button type="button" class="btn-icon" @click="showImportModal = false">✕</button>
        </div>
        <div class="card-body">
          <p class="modal-desc text-muted">
            依據 CatOS 核心契約規範，Python 原始碼需配置對應的不可變製品元資料。請檢查並確認：
          </p>

          <div class="form-group">
            <label for="import-id">策略識別碼 (Strategy ID, 1-64 Token)</label>
            <input id="import-id" v-model="importId" class="input mono" placeholder="e.g. counter-python" />
          </div>

          <div class="form-group">
            <label for="import-version">版本識別碼 (Version, 1-64 Token，禁句點)</label>
            <input id="import-version" v-model="importVersion" class="input mono" placeholder="e.g. file-v1 或 v1_0" />
          </div>

          <div class="form-group">
            <label for="import-name">策略名稱 (1-120 字元)</label>
            <input id="import-name" v-model="importName" class="input" placeholder="e.g. Counter Python 實例" />
          </div>

          <div class="form-group">
            <label for="import-description">策略說明 (1-2000 字元)</label>
            <textarea id="import-description" v-model="importDescription" class="input textarea" rows="2"></textarea>
          </div>

          <div class="form-row">
            <div class="form-group flex-1">
              <label for="import-warmup">預熱收盤 K 線根數 (1-16)</label>
              <input id="import-warmup" type="number" min="1" max="16" v-model.number="importWarmup" class="input mono" />
            </div>
          </div>

          <div class="form-group">
            <label for="import-defaults">預設通用參數 JSON (禁用 float，金額/數量請用字串)</label>
            <textarea id="import-defaults" v-model="importDefaults" class="input textarea mono" rows="4"></textarea>
          </div>
        </div>
        <div class="card-footer modal-actions">
          <button type="button" class="btn btn-secondary" @click="showImportModal = false">取消</button>
          <button
            type="button"
            id="import-strategy"
            class="btn btn-primary"
            :disabled="isImporting"
            @click="handleConfirmModalImport"
          >
            {{ isImporting ? '驗證寫入中...' : '確認匯入製品' }}
          </button>
        </div>
      </div>
    </div>

    <div class="strategies-layout">
      <!-- Left list -->
      <div class="strategy-list-col card">
        <div class="card-header">
          <div class="card-title">已註冊版本庫</div>
          <div class="card-actions-row">
            <span class="badge badge-neutral">{{ strategies.length }} 版本</span>
          </div>
        </div>
        <div class="card-body list-body">
          <div
            v-for="s in strategies"
            :key="s.artifact_hash"
            :class="['strat-item', { active: selectedStrategy?.artifact_hash === s.artifact_hash }]"
            @click="selectedStrategy = s"
          >
            <div class="strat-title">{{ s.artifact.name }}</div>
            <div class="strat-sub mono">
              <span>{{ s.artifact.strategy_id }} · v{{ s.artifact.version }}</span>
            </div>
            <div class="strat-hash mono text-muted">
              Hash: {{ s.artifact_hash.slice(0, 16) }}...
            </div>
          </div>
        </div>
      </div>

      <!-- Right detail view -->
      <div class="strategy-detail-col card" v-if="selectedStrategy">
        <div class="card-header">
          <div class="card-title">
            <span>{{ selectedStrategy.artifact.name }}</span>
            <span class="badge badge-accent">不可變製品</span>
          </div>
          <div class="card-actions">
            <!-- Strict: Prototype preview only, not claimed as backend AST verified -->
            <span class="badge badge-neutral">原型語法預檢 (示意)</span>
          </div>
        </div>

        <div class="card-body detail-body">
          <div class="info-grid">
            <div class="info-item">
              <span class="lbl">製品契約</span>
              <span class="val mono">{{ selectedStrategy.artifact.contract }}</span>
            </div>
            <div class="info-item">
              <span class="lbl">預熱根數 (Warmup)</span>
              <span class="val mono">{{ selectedStrategy.artifact.warmup_bars }} 根已收盤 K 線</span>
            </div>
            <div class="info-item full">
              <span class="lbl">完整 SHA-256 Hash</span>
              <span class="val mono text-accent">{{ selectedStrategy.artifact_hash }}</span>
            </div>
            <div class="info-item full">
              <span class="lbl">策略描述</span>
              <span class="val">{{ selectedStrategy.artifact.description }}</span>
            </div>
          </div>

          <div class="defaults-section">
            <div class="section-title">預設通用參數 (通用 JSON 契約，禁用 float)</div>
            <pre class="code-box">{{ JSON.stringify(selectedStrategy.artifact.defaults, null, 2) }}</pre>
          </div>

          <div class="source-section">
            <div class="section-title">策略原始碼 (Worker 隔離執行，普通 Python 程序非 OS 沙箱)</div>
            <pre class="code-box">{{ selectedStrategy.artifact.source }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.strategies-page {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  height: 100%;
  overflow-y: auto;
}

.banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
}

.banner-danger {
  background: var(--color-danger-bg);
  border: 1px solid var(--color-danger-border);
  color: #ffc2bf;
}

.banner-success {
  background: var(--color-success-bg);
  border: 1px solid var(--color-success-border);
  color: #7ee787;
}

.strategies-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: var(--space-4);
  flex: 1;
  min-height: 0;
}

.strategy-list-col {
  display: flex;
  flex-direction: column;
}

.list-body {
  padding: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  overflow-y: auto;
}

.strat-item {
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--bg-surface-elevated);
  border: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: all 0.15s ease;
}

.strat-item:hover {
  background: var(--bg-surface-hover);
  border-color: var(--border-highlight);
}

.strat-item.active {
  border-color: var(--accent);
  background: var(--bg-surface-active);
}

.strat-title {
  font-weight: 600;
  font-size: var(--text-sm);
  color: var(--text-primary);
}

.strat-sub {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  margin-top: 2px;
}

.strat-hash {
  font-size: var(--text-2xs);
  margin-top: 4px;
}

.strategy-detail-col {
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.detail-body {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3);
  background: var(--bg-surface-elevated);
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-subtle);
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.info-item.full {
  grid-column: span 2;
}

.info-item .lbl {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.info-item .val {
  font-size: var(--text-xs);
  color: var(--text-primary);
  word-break: break-all;
}

.section-title {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.code-box {
  background: var(--bg-base);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 280px;
  overflow-y: auto;
}

/* Modal styles */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: var(--space-4);
}

.modal {
  width: 100%;
  max-width: 540px;
  background: var(--bg-surface);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-md);
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.6);
  max-height: 90vh;
  overflow-y: auto;
}

.modal-desc {
  font-size: var(--text-xs);
  margin-bottom: var(--space-3);
  line-height: 1.5;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: var(--space-3);
}

.form-group label {
  font-size: var(--text-2xs);
  color: var(--text-secondary);
  font-weight: 500;
}

.input {
  background: var(--bg-base);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 6px 10px;
  color: var(--text-primary);
  font-size: var(--text-xs);
}

.input:focus {
  outline: none;
  border-color: var(--accent);
}

.textarea {
  resize: vertical;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}
</style>
