// Unit tests for the simulation adapter + state adapter + store (no network, no browser).
import { test, before, after, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';

let server, store, StateAdapter, SimulationApiAdapter, ResearchApiError, initial;
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', optimizeDeps: { noDiscovery: true, entries: [] } });
  ({ useCatStore: store } = await server.ssrLoadModule('/src/state/catStore.ts'));
  ({ StateAdapter } = await server.ssrLoadModule('/src/state/stateAdapter.ts'));
  ({ SimulationApiAdapter } = await server.ssrLoadModule('/src/adapters/simulation-api-adapter.ts'));
  ({ ResearchApiError } = await server.ssrLoadModule('/src/adapters/research-api-adapter.ts'));
  initial = store.getState();
});
after(async () => { await server?.close(); });

const PREFIX = '/api/workspace/simulation';
const INSTANCE_A = 'a'.repeat(32);
const INSTANCE_B = 'b'.repeat(32);
const BUILD = 'c'.repeat(64);
const RUN = 'd'.repeat(32);

const version = (over = {}) => ({
  contract: 'catos.simulation.v1', mode: 'local-sim-synthetic', build_id: BUILD, current_build_id: BUILD,
  restart_required: false, instance_id: INSTANCE_A, slot: 'idle', active_run_id: null,
  capabilities: { start: true, stop: false }, unavailable_reason: null, config: {}, ...over,
});
const bot = (over = {}) => ({
  version: 1, bot_id: 'sim-control-sma', mode: 'local', strategy_id: 'sma-trend', strategy_version: 'sma-parameters-v1',
  strategy_name: 'SMA', artifact_hash: 'f'.repeat(64), parameters: { period: 2, quantity: '2' }, inst_id: 'BTC-USDT-SWAP',
  symbol: 'BTC-USDT-SWAP', contract: null, timeframe_ms: 900000, trusted: true, created_at_ms: 1, state: 'stopped',
  current_run_id: null, active: false, run_count: 0, worker_pid: null, bars: 0, warmup_bars: 0, fills: 0,
  last_synthetic_time_ms: null, run_created_at_ms: null, finished_at_ms: null, account_source: null, position: null,
  average_entry: null, balance: null, realized_pnl: null, unrealized_pnl: null, equity: '9007199254740993.123456789',
  fees: null, funding_paid: null, mark: null, last_disposition: null, last_reason: null, ownership_retained: false, error: null, ...over,
});
const event = (seq, kind = 'run_state', payload = { state: 'running', previous: 'starting' }) => ({
  seq, run_id: RUN, bot_id: 'sim-control-sma', kind, wall_time_ms: 1_762_000_000_000 + seq, synthetic_time_ms: null,
  level: 'INFO', category: 'SYSTEM', payload,
});
const state = (v, over = {}) => ({
  contract: 'catos.simulation.v1', version: v, instance_id: INSTANCE_A, observed_at_ms: 1, unchanged: false,
  service: version(), strategies: [], bots: [bot({ version: v })], risk: null, positions: [], summary: null,
  events: { items: [], next_since: 0, omitted: 0 },
  domains: { service: v, bots: v, risk: v, positions: v, events: v }, ...over,
});

function json(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
}

function memoryStorage() {
  const map = new Map();
  return { getItem: (k) => map.get(k) ?? null, setItem: (k, v) => { map.set(k, v); }, removeItem: (k) => { map.delete(k); }, map };
}

/** Scripted fetch: routes by method+path prefix, records every call. */
function fakeFetch(routes) {
  const calls = [];
  const fn = async (url, init = {}) => {
    const method = init.method ?? 'GET';
    calls.push({ method, url, init, pendingAtSend: fn.storage ? fn.storage.getItem('catos.simulation.pending_command') : null });
    for (const [key, handler] of routes) {
      const [m, prefix] = key.split(' ');
      if (m === method && url.startsWith(prefix)) return handler({ url, init, calls });
    }
    throw new Error(`unexpected ${method} ${url}`);
  };
  fn.calls = calls;
  return fn;
}

let adapters = [];
beforeEach(() => { store.setState({ ...initial, connection: { ...initial.connection } }, true); });
afterEach(() => { for (const a of adapters) a.stopPolling(); adapters = []; });

function make(routes, mode = 'local') {
  const storage = memoryStorage();
  const fetch = fakeFetch(routes);
  fetch.storage = storage;
  const api = new SimulationApiAdapter({ fetch, storage });
  api.setMode(mode);
  const adapter = new StateAdapter(api);
  adapters.push(adapter);
  return { adapter, api, fetch, storage };
}

test('applyState rejects stale versions and accepts equal/newer ones per domain', () => {
  const { adapter } = make([]);
  assert.equal(adapter.applyState(state(5)), true);
  assert.equal(store.getState().bots[0].equity, '9007199254740993.123456789');
  assert.equal(adapter.applyState(state(4, { bots: [bot({ bot_id: 'stale' })] })), false);
  assert.equal(store.getState().bots[0].bot_id, 'sim-control-sma');
  assert.equal(adapter.applyState(state(5, { bots: [bot({ bot_id: 'equal' })] })), true);
  assert.equal(store.getState().bots[0].bot_id, 'equal');
  // A newer global version whose bots domain is older keeps the newer bots projection.
  assert.equal(adapter.applyState(state(6, { bots: [bot({ bot_id: 'older-bots' })], domains: { service: 6, bots: 3, risk: 6, positions: 6, events: 6 } })), true);
  assert.equal(store.getState().bots[0].bot_id, 'equal');
  assert.equal(store.getState().versionMap.bots, 5);
  assert.equal(store.getState().versionMap.global, 6);
});

test('a new backend instance clears every version and projection before applying', () => {
  const { adapter } = make([]);
  adapter.applyState(state(10, { events: { items: [event(1), event(2)], next_since: 2, omitted: 0 } }));
  assert.equal(store.getState().events.length, 2);
  assert.equal(store.getState().instanceId, INSTANCE_A);
  assert.equal(adapter.applyState(state(2, { instance_id: INSTANCE_B, bots: [bot({ bot_id: 'from-b' })] })), true);
  assert.equal(store.getState().instanceId, INSTANCE_B);
  assert.equal(store.getState().bots[0].bot_id, 'from-b');
  assert.equal(store.getState().versionMap.global, 2);
  assert.deepEqual(store.getState().events, []);
});

test('invalid versions are rejected by the store guard', () => {
  for (const v of [NaN, Infinity, -1, 1.5, Number.MAX_SAFE_INTEGER + 1]) {
    assert.equal(store.getState().applyAuthoritativeUpdate('bots', v, () => ({ bots: ['bad'] })), false);
  }
  assert.deepEqual(store.getState().bots, []);
  assert.deepEqual(store.getState().versionMap, {});
});

test('events merge by seq, backfill fills the gap, and omitted is reported not hidden', async () => {
  const { adapter, fetch } = make([
    ['GET /api/workspace/simulation/state', () => json(state(3, { events: { items: [event(5), event(6)], next_since: 6, omitted: 2 } }))],
    ['GET /api/workspace/simulation/events', ({ url }) => {
      const since = Number(new URL(url, 'http://127.0.0.1').searchParams.get('since'));
      return json({ items: [3, 4, 5, 6].filter((s) => s > since).map((s) => event(s)), next_since: 6, more: false, version: 3, omitted: 2 });
    }],
  ]);
  await adapter.init();
  assert.deepEqual(store.getState().events.map((e) => e.seq), [3, 4, 5, 6]);
  assert.equal(store.getState().eventsNextSince, 6);
  assert.equal(store.getState().eventsOmitted, 2);
  assert.equal(store.getState().connection.status, 'ok');
  assert.ok(fetch.calls.some((c) => c.url.includes('/events?since=0')));
  // Duplicate merge is idempotent.
  store.getState().mergeEvents([event(4), event(6)]);
  assert.deepEqual(store.getState().events.map((e) => e.seq), [3, 4, 5, 6]);
  assert.equal(adapter.pollIntervalMs(), 5000);
  adapter.applyState(state(4, { service: version({ active_run_id: RUN }) }));
  assert.equal(adapter.pollIntervalMs(), 1000);
});

test('unchanged polls leave projections alone and 503 is surfaced as unavailable', async () => {
  let calls = 0;
  const { adapter } = make([
    ['GET /api/workspace/simulation/state', ({ url }) => {
      calls++;
      if (calls === 1) return json(state(7));
      if (url.includes('since_version=7')) return json({ contract: 'catos.simulation.v1', version: 7, instance_id: INSTANCE_A, observed_at_ms: 2, unchanged: true });
      return json({ detail: 'simulation_metadata_unavailable' }, 503);
    }],
    ['GET /api/workspace/simulation/events', () => json({ items: [], next_since: 0, more: false, version: 7, omitted: 0 })],
  ]);
  await adapter.init();
  adapter.stopPolling();
  const bots = store.getState().bots;
  await adapter.refreshNowFull(); // full refresh without since → 503 path
  assert.equal(store.getState().connection.status, 'unavailable');
  assert.equal(store.getState().connection.detail, 'simulation_metadata_unavailable');
  assert.equal(store.getState().bots, bots);
});

for (const mode of ['demo', 'live']) {
  test(`${mode}: no request is sent, reads are typed unavailable, mutations reject 403`, async () => {
    const { adapter, api, fetch } = make([
      ['GET /api/workspace/simulation/state', () => json(state(1))],
      ['GET /api/workspace/simulation/events', () => json({ items: [], next_since: 0, more: false, version: 1, omitted: 0 })],
    ]);
    await adapter.init();
    adapter.applyState(state(10, { bots: [bot({ bot_id: 'local-v10' })] }));
    store.setState({ pendingCommand: { path: 'x', command_type: 'start_bot', body: { request_id: 'e'.repeat(32) }, build: BUILD, instance: INSTANCE_A, timestamp_ms: 1 } });
    const before = fetch.calls.length;
    const switching = adapter.setMode(mode);
    assert.equal(store.getState().mode, mode);
    assert.deepEqual(store.getState().bots, []);
    assert.equal(store.getState().summary, null);
    assert.deepEqual(store.getState().versionMap, {});
    assert.equal(store.getState().pendingCommand, null);
    await switching;
    assert.equal(fetch.calls.length, before, 'no HTTP request in demo/live');
    assert.equal(store.getState().connection.status, 'mode_not_open');
    assert.equal(store.getState().connection.polling, false);
    assert.deepEqual(await api.fetchState(), { available: false, reason: 'mode_not_open', mode });
    assert.deepEqual(await api.fetchEvents(0, 10), { available: false, reason: 'mode_not_open', mode });
    await assert.rejects(api.startBot('sim-control-sma'), (e) => e instanceof ResearchApiError && e.status === 403 && e.detail === 'mode_not_available');
    await assert.rejects(adapter.stopBot(RUN), (e) => e.status === 403 && e.detail === 'mode_not_available');
    assert.equal(fetch.calls.length, before);
    await adapter.setMode('local');
    assert.equal(store.getState().mode, 'local');
    assert.equal(store.getState().bots[0].bot_id, 'sim-control-sma');
    assert.equal(store.getState().versionMap.bots, 1);
  });
}

test('startBot persists a 32-hex request_id before POST, sends build/instance headers and clears on response', async () => {
  const { adapter, fetch, storage } = make([
    ['GET /api/workspace/simulation/version', () => json(version())],
    ['GET /api/workspace/simulation/state', () => json(state(1))],
    ['GET /api/workspace/simulation/events', () => json({ items: [], next_since: 0, more: false, version: 1, omitted: 0 })],
    ['POST /api/workspace/simulation/bots/start', ({ init }) => {
      const body = JSON.parse(init.body);
      return json({ run: { run_id: RUN, request_id: body.request_id, control_state: 'starting' }, bot: bot(), version: 2 }, 202);
    }],
  ]);
  await adapter.init();
  adapter.stopPolling();
  await adapter.startBot('sim-control-sma');
  const post = fetch.calls.find((c) => c.method === 'POST');
  assert.ok(post, 'POST sent');
  const body = JSON.parse(post.init.body);
  assert.deepEqual(Object.keys(body).sort(), ['bot_id', 'request_id']);
  assert.match(body.request_id, /^[0-9a-f]{32}$/);
  assert.equal(post.init.headers['X-CatOS-Build'], BUILD);
  assert.equal(post.init.headers['X-CatOS-Instance'], INSTANCE_A);
  assert.equal(post.init.headers['Content-Type'], 'application/json');
  assert.ok(post.pendingAtSend, 'PendingCommand stored before the request left');
  assert.equal(JSON.parse(post.pendingAtSend).body.request_id, body.request_id);
  assert.equal(storage.getItem('catos.simulation.pending_command'), null, 'cleared after a definitive response');
  assert.equal(store.getState().pendingCommand, null);
  assert.equal(store.getState().commandHistory[0].status, 'success');
  assert.equal(store.getState().commandHistory[0].run_id, RUN);
  // A 409 is definitive too: pending cleared, failure recorded with the backend code.
  fetch.calls.length = 0;
  const { adapter: a2, storage: s2 } = make([
    ['GET /api/workspace/simulation/version', () => json(version())],
    ['GET /api/workspace/simulation/state', () => json(state(1))],
    ['GET /api/workspace/simulation/events', () => json({ items: [], next_since: 0, more: false, version: 1, omitted: 0 })],
    ['POST /api/workspace/simulation/bots/start', () => json({ detail: 'simulation_slot_occupied' }, 409)],
  ]);
  await a2.init();
  a2.stopPolling();
  await assert.rejects(a2.startBot('sim-control-sma'), (e) => e.status === 409 && e.detail === 'simulation_slot_occupied');
  assert.equal(s2.getItem('catos.simulation.pending_command'), null);
  assert.equal(store.getState().commandHistory[0].status, 'failed');
  assert.equal(store.getState().commandHistory[0].error_code, 'simulation_slot_occupied');
});

test('a network failure keeps the pending command and retry replays the same request_id', async () => {
  let fail = true;
  const seen = [];
  const { adapter, storage } = make([
    ['GET /api/workspace/simulation/version', () => json(version())],
    ['GET /api/workspace/simulation/state', () => json(state(1))],
    ['GET /api/workspace/simulation/events', () => json({ items: [], next_since: 0, more: false, version: 1, omitted: 0 })],
    ['POST /api/workspace/simulation/runs/', ({ init }) => {
      seen.push(JSON.parse(init.body).request_id);
      if (fail) throw new TypeError('fetch failed');
      return json({ run_id: RUN, control_state: 'stopping' }, 202);
    }],
  ]);
  await adapter.init();
  adapter.stopPolling();
  await assert.rejects(adapter.stopBot(RUN), (e) => e.status === 0 && e.detail === 'network_error');
  const pending = JSON.parse(storage.getItem('catos.simulation.pending_command'));
  assert.equal(pending.command_type, 'stop_bot');
  assert.equal(pending.path, `${PREFIX}/runs/${RUN}/stop`);
  assert.equal(store.getState().pendingCommand.body.request_id, pending.body.request_id);
  assert.equal(store.getState().commandHistory[0].status, 'uncertain');
  fail = false;
  await adapter.retryPendingCommand();
  assert.deepEqual(seen, [pending.body.request_id, pending.body.request_id]);
  assert.equal(storage.getItem('catos.simulation.pending_command'), null);
  assert.equal(store.getState().pendingCommand, null);
  assert.equal(store.getState().commandHistory[0].status, 'success');
});

test('equityCurve picks signal.account.equity of the given run only, as strings', () => {
  const events = [
    event(1, 'signal', { seq: 3, account: { equity: '1000.00000001' } }),
    { ...event(2, 'signal', { seq: 4, account: { equity: '999.5' } }), run_id: 'other' },
    event(3, 'fill', { equity: '5' }),
    event(4, 'signal', { seq: 4, account: { equity: '1003.21' } }),
  ];
  assert.deepEqual(StateAdapter.equityCurve(events, RUN).map((p) => p.equity), ['1000.00000001', '1003.21']);
  assert.deepEqual(StateAdapter.equityCurve(events, null), []);
});

test('compareDecimal compares Decimal strings exactly, beyond float precision', async () => {
  const { compareDecimal } = await server.ssrLoadModule('/src/lib/format.ts');
  assert.equal(compareDecimal('1.10', '1.1'), 0);
  assert.equal(compareDecimal('2.5', '3.0'), -1);
  assert.equal(compareDecimal('-0.5', '0'), -1);
  assert.equal(compareDecimal('0E-7', '0.000'), 0);
  // 9007199254740993 is not representable as a double; Number() would call these equal.
  assert.equal(compareDecimal('9007199254740993.1', '9007199254740993.09'), 1);
  assert.equal(compareDecimal('9007199254740993', '9007199254740992'), 1);
  assert.equal(compareDecimal(null, '1'), null);
  assert.equal(compareDecimal('abc', '1'), null);
});
