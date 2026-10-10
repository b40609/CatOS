<script setup lang="ts">
import { ref, onMounted } from 'vue';
import type { StrategyEntry, StrategyArtifact } from '@/contracts';
import { activeAdapter } from '@/adapters/mock-adapter';
import StatusBadge from '@/components/common/StatusBadge.vue';

const strategies = ref<StrategyEntry[]>([]);
const selectedStrategy = ref<StrategyEntry | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);

const errorMsg = ref<string | null>(null);
const successMsg = ref<string | null>(null);
const isImporting = ref<boolean>(false);

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
  isImporting.value = true;

  try {
    const text = await file.text();
    let artifact: StrategyArtifact;

    if (file.name.endsWith('.json')) {
      let parsed: any;
      try {
        parsed = JSON.parse(text);
      } catch {
        throw new Error('JSON 檔案格式錯誤，無法解析');
      }

      // Check manifest format
      const manifest = parsed.manifest || parsed;
      if (manifest.contract !== 'catos.python-strategy.v1') {
        throw new Error(`契約識別碼錯誤：預期 catos.python-strategy.v1，收到 ${manifest.contract || '無'}`);
      }
      if (!manifest.strategy_id || !manifest.version || !manifest.source) {
        throw new Error('JSON 製品缺少必要欄位 (strategy_id, version, source)');
      }

      artifact = {
        contract: 'catos.python-strategy.v1',
        strategy_id: String(manifest.strategy_id),
        version: String(manifest.version),
        name: manifest.name || file.name.replace('.json', ''),
        description: manifest.description || '由 JSON 製品檔案匯入',
        source: manifest.source,
        defaults: manifest.defaults || { period: '2', quantity: '2' },
        warmup_bars: Number(manifest.warmup_bars) || 2
      };
    } else if (file.name.endsWith('.py')) {
      // 依據 catos.python-strategy.v1 核心契約規範解析
      const cleanBase = file.name.replace('.py', '').toLowerCase().replace(/[^a-z0-9_-]/g, '_');
      
      let strategyId = `custom-${cleanBase}`;
      let version = 'file-v1'; // 核心規範預設版本識別碼
      let name = `自訂策略 (${file.name})`;
      let description = `由 Python 原始碼檔案 ${file.name} 匯入之不可變製品`;
      let warmupBars = 2;
      let defaults: Record<string, any> = { quantity: "-1", hold: false };

      // 檢查 source 大小邊界 (limits: source_utf8_bytes <= 12000)
      const utf8Bytes = new TextEncoder().encode(text).length;
      if (utf8Bytes > 12000) {
        throw new Error(`策略原始碼超出 12,000 bytes 限制 (當前: ${utf8Bytes} bytes)`);
      }

      // 檢查契約必要結構
      if (!text.includes('class Strategy')) {
        throw new Error('Python 策略契約不符：缺少 class Strategy 定義');
      }

      // 解析檔案標頭註解元資料
      const lines = text.split('\n');
      for (const rawLine of lines) {
        const line = rawLine.trim();
        if (line.startsWith('# strategy_id:')) {
          strategyId = line.replace('# strategy_id:', '').trim();
        } else if (line.startsWith('# version:')) {
          version = line.replace('# version:', '').trim();
        } else if (line.startsWith('# name:')) {
          name = line.replace('# name:', '').trim();
        } else if (line.startsWith('# description:')) {
          description = line.replace('# description:', '').trim();
        } else if (line.startsWith('# warmup_bars:')) {
          const w = parseInt(line.replace('# warmup_bars:', '').trim(), 10);
          if (!isNaN(w) && w >= 1 && w <= 16) warmupBars = w;
        } else if (line.startsWith('# defaults:')) {
          try {
            defaults = JSON.parse(line.replace('# defaults:', '').trim());
          } catch {
            // retain fallback
          }
        }
      }

      artifact = {
        contract: 'catos.python-strategy.v1',
        strategy_id: strategyId,
        version: version,
        name: name,
        description: description,
        source: text,
        defaults: defaults,
        warmup_bars: warmupBars
      };
    } else {
      throw new Error('不支援的檔案格式，請上傳 .py 或 .json 策略製品');
    }

    const reqId = generateRequestId();
    const created = await activeAdapter.createStrategy(reqId, artifact);
    await loadData();
    selectedStrategy.value = created;
    successMsg.value = `策略製品「${artifact.name}」匯入成功，已寫入不可變版本庫。`;
  } catch (err: any) {
    errorMsg.value = err.message || '匯入策略製品失敗';
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

.banner-info {
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.4);
  color: #93c5fd;
}

.strategies-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: var(--space-4);
  flex: 1;
  min-height: 480px;
}

.strategy-list-col {
  height: 100%;
}

.list-body {
  padding: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  overflow-y: auto;
  max-height: calc(100vh - 180px);
}

.strat-item {
  padding: var(--space-3);
  border-radius: var(--radius-xs);
  background: var(--bg-surface);
  border: 1px solid var(--border-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.strat-item:hover {
  background: var(--bg-surface-hover);
  border-color: var(--border-focus);
}

.strat-item.active {
  background: rgba(207, 171, 76, 0.08);
  border-color: var(--accent);
}

.strat-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
}

.strat-sub {
  font-size: 11px;
  color: var(--text-secondary);
}

.strat-hash {
  font-size: 10px;
}

.strategy-detail-col {
  overflow-y: auto;
}

.detail-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
  background: var(--bg-surface);
  padding: var(--space-3);
  border-radius: var(--radius-xs);
  border: 1px solid var(--border-secondary);
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
  font-size: 10.5px;
  color: var(--text-muted);
}

.info-item .val {
  font-size: var(--text-xs);
  color: var(--text-primary);
}

.section-title {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.code-box {
  background: var(--bg-base);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-xs);
  padding: var(--space-3);
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-primary);
  max-height: 240px;
  overflow-y: auto;
  line-height: 1.45;
}

.text-accent { color: var(--accent); }
</style>
