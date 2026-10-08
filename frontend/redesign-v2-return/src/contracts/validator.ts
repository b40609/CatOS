/**
 * Strict Validator and Canonical Serializer for catOS v1 Contracts
 * Conforms to:
 * - catos/python_strategy.py
 * - catos/strategy_library.py
 * - catos/local_sim_control.py
 */

import type { StrategyArtifact, StrategyEntry } from './strategy';

export const CONTRACT_NAME = 'catos.python-strategy.v1';
export const TOKEN_REGEX = /^[A-Za-z0-9_-]{1,64}$/;

/**
 * Deterministic JSON serialization:
 * - Exact key sorting alphabetically at every depth
 * - Separators (',', ':') with no extraneous whitespace
 * - Unicode characters preserved directly in UTF-8
 * - Disallows NaN, Infinity
 */
export function canonicalJson(value: any): string {
  if (value === null || typeof value === 'boolean') {
    return JSON.stringify(value);
  }
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) {
      throw new Error('strategy_data_no_float: NaN or Infinity is forbidden');
    }
    return JSON.stringify(value);
  }
  if (typeof value === 'string') {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return '[' + value.map(canonicalJson).join(',') + ']';
  }
  if (typeof value === 'object') {
    const keys = Object.keys(value).sort();
    return '{' + keys.map(k => JSON.stringify(k) + ':' + canonicalJson(value[k])).join(',') + '}';
  }
  throw new Error(`strategy_data_type: unsupported type ${typeof value}`);
}

/**
 * Validates nested parameters and state objects:
 * - Depth <= 2
 * - Max 64 items per container
 * - Dict keys <= 64 chars
 * - String <= 4096 bytes
 * - Safe integer range
 * - STRICTLY NO FLOATS (must use Decimal string)
 */
export function validateData(value: any, depth = 0): void {
  if (depth > 2) {
    throw new Error('strategy_data_depth: 資料結構深度不可超過 2 層');
  }

  if (value === null || typeof value === 'boolean') {
    return;
  }

  if (typeof value === 'string') {
    const bytes = new TextEncoder().encode(value).length;
    if (bytes > 4096) {
      throw new Error(`strategy_data_size: 字串大小超出上限 (上限 4096 bytes, 實際 ${bytes} bytes)`);
    }
    return;
  }

  if (typeof value === 'number') {
    if (!Number.isInteger(value)) {
      throw new Error('strategy_data_no_float: 策略參數嚴禁使用浮點數 (Float is forbidden; 請使用 Decimal 字串，例如 "1.5")');
    }
    if (!Number.isSafeInteger(value) || Math.abs(value) > 2 ** 63 - 1) {
      throw new Error('strategy_integer_range: 整數超出 64-bit 安全整數範圍');
    }
    return;
  }

  if (Array.isArray(value)) {
    if (value.length > 64) {
      throw new Error(`strategy_data_size: 陣列長度不可超過 64 (實際 ${value.length})`);
    }
    for (const item of value) {
      validateData(item, depth + 1);
    }
    return;
  }

  if (typeof value === 'object') {
    const keys = Object.keys(value);
    if (keys.length > 64) {
      throw new Error(`strategy_data_size: 物件鍵數量不可超過 64 (實際 ${keys.length})`);
    }
    for (const key of keys) {
      if (typeof key !== 'string' || key.length > 64) {
        throw new Error('strategy_data_key: 鍵名必須為字串且長度不可超過 64');
      }
      validateData(value[key], depth + 1);
    }
    return;
  }

  throw new Error('strategy_data_no_float: 策略資料包含不允許的型別');
}

/**
 * Validates Python Strategy Artifact according to catos.python_strategy.py:
 * - Exactly 8 fields
 * - contract === 'catos.python-strategy.v1'
 * - strategy_id & version are 1-64 ASCII token
 * - text sizes: name <= 120, description <= 2000, source <= 12000 bytes
 * - defaults is valid dict, canonical size <= 4096 bytes
 * - warmup_bars is integer in [1, 16]
 * - source contains class Strategy
 */
export function validateArtifact(manifest: any): StrategyArtifact {
  if (typeof manifest !== 'object' || manifest === null || Array.isArray(manifest)) {
    throw new Error('strategy_manifest_contract: 策略製品 manifest 必須為物件');
  }

  const expectedKeys = ['contract', 'strategy_id', 'version', 'name', 'description', 'source', 'defaults', 'warmup_bars'];
  const manifestKeys = Object.keys(manifest).sort();
  const sortedExpected = [...expectedKeys].sort();

  if (manifestKeys.length !== sortedExpected.length || manifestKeys.some((k, i) => k !== sortedExpected[i])) {
    throw new Error(`strategy_manifest_contract: 欄位不符契約。必須精確包含 8 欄 (${expectedKeys.join(', ')})`);
  }

  if (manifest.contract !== CONTRACT_NAME) {
    throw new Error(`strategy_manifest_contract: 契約識別碼必須為 "${CONTRACT_NAME}" (收到: "${manifest.contract}")`);
  }

  for (const idKey of ['strategy_id', 'version'] as const) {
    const val = manifest[idKey];
    if (typeof val !== 'string' || !TOKEN_REGEX.test(val)) {
      throw new Error(`strategy_identity: ${idKey} 格式無效 (必須為 1-64 字元英數字元、底線或連字號 Token，嚴禁小數點或空格)`);
    }
  }

  const encoder = new TextEncoder();

  const limits = [
    { key: 'name', max: 120 },
    { key: 'description', max: 2000 },
    { key: 'source', max: 12000 }
  ] as const;

  for (const item of limits) {
    const textVal = manifest[item.key];
    if (typeof textVal !== 'string') {
      throw new Error(`strategy_text_size: ${item.key} 必須為字串`);
    }
    const byteLen = encoder.encode(textVal).length;
    if (byteLen === 0 || byteLen > item.max) {
      throw new Error(`strategy_text_size: ${item.key} UTF-8 位元組長度必須在 1 至 ${item.max} 之間 (實際: ${byteLen} bytes)`);
    }
  }

  if (typeof manifest.defaults !== 'object' || manifest.defaults === null || Array.isArray(manifest.defaults)) {
    throw new Error('strategy_parameters_object: defaults 必須為字典物件');
  }
  validateData(manifest.defaults);

  const defaultsBytes = encoder.encode(canonicalJson(manifest.defaults)).length;
  if (defaultsBytes > 4096) {
    throw new Error(`strategy_parameters_size: defaults 正規化 JSON 大小超過 4096 bytes (實際: ${defaultsBytes} bytes)`);
  }

  const w = manifest.warmup_bars;
  if (typeof w !== 'number' || !Number.isInteger(w) || w < 1 || w > 16) {
    throw new Error(`strategy_warmup_range: warmup_bars 必須為 1 至 16 的整數 (收到: ${w})`);
  }

  // 前端字串簡易預檢 (Lightweight static sanity check)
  // 注意：前端檢驗僅為基本字串預檢 (includes('class Strategy'))，不可宣稱為 Python AST 語法與 Hook 分析。
  // 真實 Python AST 解析、契約方法簽名驗證與受信沙箱隔離，完全由後端 Python 核心 (catos/python_strategy.py) 負責。
  if (!manifest.source.includes('class Strategy')) {
    throw new Error('strategy_entrypoint_required: Python 原始碼缺少 class Strategy 入口類別');
  }

  return {
    contract: CONTRACT_NAME,
    strategy_id: manifest.strategy_id,
    version: manifest.version,
    name: manifest.name,
    description: manifest.description,
    source: manifest.source,
    defaults: JSON.parse(JSON.stringify(manifest.defaults)),
    warmup_bars: manifest.warmup_bars
  };
}

/**
 * Validates bot allocation binding:
 * - Exact key structure: artifact, artifact_hash, parameters
 * - artifact_hash matches digest(artifact)
 * - parameters are valid bounded object without float, <= 4096 bytes
 */
export function validateBinding(bindingValue: any, expectedHash?: string): void {
  if (typeof bindingValue !== 'object' || bindingValue === null || Array.isArray(bindingValue)) {
    throw new Error('strategy_binding_contract: binding 必須為物件');
  }
  if (!bindingValue.artifact || typeof bindingValue.artifact !== 'object') {
    throw new Error('strategy_binding_contract: binding 缺少有效 artifact 物件');
  }
  const checkedArtifact = validateArtifact(bindingValue.artifact);
  if (expectedHash && bindingValue.artifact_hash !== expectedHash) {
    throw new Error(`strategy_artifact_hash_mismatch: artifact_hash (${bindingValue.artifact_hash}) 與預期製品 hash (${expectedHash}) 不符`);
  }
  if (typeof bindingValue.parameters !== 'object' || bindingValue.parameters === null || Array.isArray(bindingValue.parameters)) {
    throw new Error('strategy_parameters_object: parameters 必須為字典物件，不可為陣列或基本型別');
  }
  validateData(bindingValue.parameters);
  const paramBytes = new TextEncoder().encode(canonicalJson(bindingValue.parameters)).length;
  if (paramBytes > 4096) {
    throw new Error(`strategy_parameters_size: parameters 正規化 JSON 大小超過 4096 bytes (實際: ${paramBytes} bytes)`);
  }
}

/**
 * Validates complete allocation payload for allocateBot:
 * - bot_id matches TOKEN_REGEX (1-64 ASCII token)
 * - artifact_hash matches 64 hex
 * - parameters must be dictionary object (NOT array, NOT primitive)
 * - parameters canonical JSON size <= 4096 bytes
 * - trusted must be explicit true
 * - JavaScript safe integer boundary check: values beyond Number.MAX_SAFE_INTEGER lose precision in JS
 */
export function validateAllocationPayload(payload: any): void {
  if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) {
    throw new Error('bot_contract: 分配請求 payload 必須為字典物件');
  }

  if (!payload.bot_id || typeof payload.bot_id !== 'string' || !TOKEN_REGEX.test(payload.bot_id)) {
    throw new Error('bot_contract: Bot ID 格式無效 (必須為 1-64 字元英數字元、底線或連字號 Token，嚴禁小數點或空格)');
  }

  if (!payload.artifact_hash || typeof payload.artifact_hash !== 'string' || !/^[0-9a-f]{64}$/i.test(payload.artifact_hash)) {
    throw new Error('bot_contract: artifact_hash 必須為 64 字元十六進位 SHA-256 字串');
  }

  if (typeof payload.parameters !== 'object' || payload.parameters === null || Array.isArray(payload.parameters)) {
    throw new Error('strategy_parameters_object: parameters 必須為字典物件，不可為陣列或基本型別');
  }

  // Parameter boundary and float checks
  validateData(payload.parameters);

  const encoder = new TextEncoder();
  const canonicalParam = canonicalJson(payload.parameters);
  const paramBytes = encoder.encode(canonicalParam).length;
  if (paramBytes > 4096) {
    throw new Error(`strategy_parameters_size: parameters 正規化 JSON 大小超過 4096 bytes (實際: ${paramBytes} bytes)`);
  }

  if (payload.trusted !== true) {
    throw new Error('UNTRUSTED_STRATEGY: 建立 Bot 必須經過人工確認信任策略製品');
  }
}

/**
 * Computes canonical SHA-256 hex digest for StrategyArtifact
 */
export async function computeArtifactDigest(artifact: StrategyArtifact): Promise<string> {
  const checked = validateArtifact(artifact);
  const canonical = canonicalJson(checked);

  const cryptoObj = (typeof globalThis !== 'undefined' && globalThis.crypto) ? globalThis.crypto : (typeof crypto !== 'undefined' ? crypto : null);
  if (!cryptoObj || !cryptoObj.subtle || !cryptoObj.subtle.digest) {
    throw new Error('computeArtifactDigest: Crypto subtle implementation unavailable');
  }

  const encoder = new TextEncoder();
  const data = encoder.encode(canonical);
  const hashBuffer = await cryptoObj.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hashBuffer))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

