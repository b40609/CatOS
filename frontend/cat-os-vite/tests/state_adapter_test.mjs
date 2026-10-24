import { test, before, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';

let server, store, adapter, mockAdapter, initial;
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', optimizeDeps: { noDiscovery: true, entries: [] } });
  ({ useCatStore: store } = await server.ssrLoadModule('/src/state/catStore.ts'));
  ({ stateAdapter: adapter } = await server.ssrLoadModule('/src/state/stateAdapter.ts'));
  ({ mockAdapter } = await server.ssrLoadModule('/src/adapters/mock-adapter.ts'));
  initial = store.getState();
});
beforeEach(() => { store.setState(initial, true); mockAdapter.setMode('local'); });
after(async () => { await server?.close(); });

test('production adapter rejects stale events and accepts equal/newer versions', () => {
  assert.equal(adapter.handleEvent({ domain: 'bots', version: 5, payload: [] }), true);
  assert.equal(adapter.handleEvent({ domain: 'bots', version: 4, payload: ['stale'] }), false);
  assert.deepEqual(store.getState().bots, []);
  assert.equal(adapter.handleEvent({ domain: 'bots', version: 5, payload: [] }), true);
  assert.equal(adapter.handleEvent({ domain: 'bots', version: 6, payload: [] }), true);
  assert.equal(store.getState().versionMap.bots, 6);
});

test('late bulk hydration cannot overwrite a newer event in the same domain', () => {
  adapter.handleEvent({ domain: 'kpis', version: 9, payload: { total_equity: '9007199254740993.123456789' } });
  store.getState().hydrateAll({ version: 3, kpis: { total_equity: '1' }, bots: [] });
  assert.equal(store.getState().kpis.total_equity, '9007199254740993.123456789');
  assert.equal(store.getState().versionMap.kpis, 9);
  assert.equal(store.getState().versionMap.bots, 3);
  assert.equal(adapter.handleEvent({ domain: 'bots', version: 2, payload: ['stale'] }), false);
});

test('production version guards reject invalid sequence numbers', () => {
  for (const version of [NaN, Infinity, -1, 1.5, Number.MAX_SAFE_INTEGER + 1]) {
    assert.equal(adapter.handleEvent({ domain: 'kpis', version, payload: { total_equity: 'bad' } }), false);
    store.getState().hydrateAll({ version, kpis: { total_equity: 'bad' } });
  }
  assert.equal(store.getState().kpis, null);
  assert.deepEqual(store.getState().versionMap, {});
});

test('real mock adapter keeps local Decimal strings and locks Demo/Live projections', async () => {
  await adapter.init();
  assert.match(store.getState().kpis.total_equity, /^\d+\.\d+$/);
  assert.equal(typeof store.getState().kpis.effective_leverage, 'string');
  assert.ok(store.getState().bots.length > 0);
  for (const mode of ['demo', 'live']) {
    await adapter.setMode(mode);
    assert.equal(store.getState().mode, mode);
    assert.deepEqual(store.getState().bots, []);
    assert.equal(store.getState().kpis.total_equity, '--');
    assert.equal(store.getState().kpis.risk_status, 'UNAVAILABLE');
  }
});

for (const mode of ['demo', 'live']) {
  test(`Local v10 is cleared immediately on switching to ${mode} and Local can reload`, async (t) => {
    await adapter.init();
    adapter.handleEvent({ domain: 'bots', version: 10, payload: [{ bot_id: 'previous-local' }] });
    adapter.handleEvent({ domain: 'kpis', version: 10, payload: { total_equity: '12345' } });
    store.setState({ pendingCommands: [{ request_id: 'local-pending' }], commandHistory: [{ request_id: 'local-history' }] });
    const pending = t.mock.method(mockAdapter, 'getPendingCommand', () => ({ request_id: 'local-pending' }));
    const history = t.mock.method(mockAdapter, 'getCommandLogs', () => [{ request_id: 'local-history' }]);

    const switching = adapter.setMode(mode);
    assert.equal(store.getState().mode, mode);
    assert.equal(store.getState().kpis, null);
    assert.deepEqual(store.getState().bots, []);
    assert.equal(store.getState().risk, null);
    assert.equal(store.getState().telemetry, null);
    assert.deepEqual(store.getState().versionMap, {});
    assert.deepEqual(store.getState().pendingCommands, []);
    assert.deepEqual(store.getState().commandHistory, []);
    await switching;
    assert.equal(store.getState().kpis.total_equity, '--');
    assert.deepEqual(store.getState().bots, []);
    assert.deepEqual(store.getState().pendingCommands, []);
    assert.deepEqual(store.getState().commandHistory, []);
    assert.equal(pending.mock.callCount(), 0);
    assert.equal(history.mock.callCount(), 0);
    pending.mock.restore();
    history.mock.restore();

    await adapter.setMode('local');
    assert.ok(store.getState().bots.length > 0);
    assert.notEqual(store.getState().bots[0].bot_id, 'previous-local');
    assert.match(store.getState().kpis.total_equity, /^\d+\.\d+$/);
    assert.equal(store.getState().versionMap.bots, 1);
    assert.equal(adapter.handleEvent({ domain: 'bots', version: 8, payload: [] }), true);
    assert.equal(adapter.handleEvent({ domain: 'bots', version: 7, payload: ['stale'] }), false);
  });
}

test('selecting the current mode preserves its monotonic versions and projections', async () => {
  await adapter.init();
  adapter.handleEvent({ domain: 'kpis', version: 10, payload: { total_equity: '12345' } });
  await adapter.setMode('local');
  assert.equal(store.getState().kpis.total_equity, '12345');
  assert.equal(store.getState().versionMap.kpis, 10);
});

test('a delayed Local hydration is discarded after Local to Demo to Local', async (t) => {
  const fetchKPIs = mockAdapter.fetchDashboardKPIs.bind(mockAdapter);
  let release;
  const delayed = new Promise(resolve => { release = resolve; });
  let first = true;
  t.mock.method(mockAdapter, 'fetchDashboardKPIs', () => {
    if (first) { first = false; return delayed; }
    return fetchKPIs();
  });
  const oldLoad = adapter.init();
  await adapter.setMode('demo');
  await adapter.setMode('local');
  const current = store.getState().kpis;
  release({ ...current, total_equity: 'previous-session' });
  await oldLoad;
  assert.deepEqual(store.getState().kpis, current);
  assert.notEqual(store.getState().kpis.total_equity, 'previous-session');
});
