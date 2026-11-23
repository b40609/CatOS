/**
 * Temporary design-comparison fixture (`?preview=pick` only).
 * Synchronizes 127.0.0.1:8770 Dashboard with docs/design/2026-11-16-redesign-pick/{X,Y,Z}.html
 * so the user can compare layout elements side-by-side using identical numbers and equity curve.
 * Never loaded in normal mode and never touches real backend state or data roots.
 */
import type { EventDTO, WorkspaceStateDTO } from '@/contracts';

const BASE_START_MS = Date.UTC(2026, 9, 24, 16, 0, 0);   // 2026-10-25 00:00 Asia/Taipei
const DAY_START_MS = Date.UTC(2026, 10, 15, 16, 0, 0);   // 2026-11-16 00:00 Asia/Taipei
const NOW_MS = Date.UTC(2026, 10, 16, 0, 0, 0);          // 2026-11-16 08:00 Asia/Taipei
const FIXED_TAG = '41cb53c54d6dABDE';

function rng(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

/** Deterministic anchored random walk — identical to X.html / Y.html / Z.html DB.eq. */
function anchoredPath(seed: number, n: number, vol: number, anchors: Array<[number, number]>): number[] {
  const r = rng(seed);
  const d: number[] = [0];
  for (let i = 1; i < n; i++) d.push(d[i - 1] + (r() - 0.5) * vol);
  const c = anchors
    .slice()
    .sort((a, b) => a[0] - b[0])
    .map(([i, v]): [number, number] => [i, v - d[i]]);
  return d.map((v, i) => {
    let k = 0;
    while (k < c.length - 2 && i > c[k + 1][0]) k++;
    const a = c[k];
    const b = c[Math.min(k + 1, c.length - 1)];
    const t = b[0] === a[0] ? 0 : Math.max(0, Math.min(1, (i - a[0]) / (b[0] - a[0])));
    return v + a[1] + (b[1] - a[1]) * t;
  });
}

function taipeiMs(month: number, day: number, hour: number, minute = 0, second = 0): number {
  return Date.UTC(2026, month - 1, day, hour - 8, minute, second);
}

export function isPreviewPickMode(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return new URLSearchParams(window.location.search).get('preview') === 'pick';
  } catch {
    return false;
  }
}

export function buildPreviewPickState(): WorkspaceStateDTO {
  const eqSeries = anchoredPath(7, 120, 18, [
    [0, 10000],
    [64, 10156],
    [74, 9969],
    [118, 10172.26],
    [119, 10214.37],
  ]);
  const tsmomSeries = anchoredPath(113, 24, 9, [[0, 10000], [23, 10087.17]]);
  const rsiSeries = anchoredPath(127, 24, 6, [[0, 10000], [23, 9987.60]]);

  const rawEvents: Array<{ timeMs: number; event: Omit<EventDTO, 'seq'> }> = [];

  // 120 account equity points (attached to don4h run so AccountEquityBand plots the exact X/Y/Z curve)
  for (let i = 0; i < eqSeries.length; i++) {
    const timeMs = i === 118
      ? DAY_START_MS
      : i === 119
        ? NOW_MS
        : Math.round(BASE_START_MS + (i / 118) * (DAY_START_MS - BASE_START_MS));
    const eq = eqSeries[i].toFixed(2);
    const isLast = i === 119;
    rawEvents.push({
      timeMs,
      event: {
        run_id: 'pickdon4h00000000000000000000001',
        bot_id: 'don4h',
        kind: 'signal',
        wall_time_ms: timeMs,
        synthetic_time_ms: timeMs,
        level: 'INFO',
        category: 'WORKER',
        payload: {
          seq: i + 1,
          disposition: isLast ? 'HOLD' : 'NO_INTENT',
          reason: isLast ? 'BTC 4H 收 105,431.0，平倉線之上續抱' : 'bar_closed',
          target: '2',
          mark: isLast ? '105477.00' : '103850.00',
          account: {
            equity: eq,
            unrealized_pnl: isLast ? '41.30' : '18.50',
          },
          risk_state: { mode: 'RUN', health: 'HEALTHY', reasons: [] },
        },
      },
    });
  }

  // Sparkline points for tsmom and rsi so all 3 bots show live curves in V0BotTable
  for (let i = 0; i < tsmomSeries.length; i++) {
    const timeMs = Math.round(taipeiMs(11, 2, 8, 0) + (i / (tsmomSeries.length - 1)) * (NOW_MS - taipeiMs(11, 2, 8, 0)) - 1000);
    rawEvents.push({
      timeMs,
      event: {
        run_id: 'picktsmom00000000000000000000002',
        bot_id: 'tsmom',
        kind: 'signal',
        wall_time_ms: timeMs,
        synthetic_time_ms: timeMs,
        level: 'INFO',
        category: 'WORKER',
        payload: {
          seq: i + 1,
          disposition: 'HOLD',
          reason: i === tsmomSeries.length - 1 ? 'BTC 1D 90 日動能 +14.2%，續抱' : 'bar_closed',
          target: '1',
          mark: '105477.00',
          account: { equity: tsmomSeries[i].toFixed(2), unrealized_pnl: '21.90' },
          risk_state: { mode: 'RUN', health: 'HEALTHY', reasons: [] },
        },
      },
    });
  }

  for (let i = 0; i < rsiSeries.length; i++) {
    const timeMs = Math.round(taipeiMs(11, 3, 8, 0) + (i / (rsiSeries.length - 1)) * (taipeiMs(11, 16, 7, 0) - taipeiMs(11, 3, 8, 0)));
    rawEvents.push({
      timeMs,
      event: {
        run_id: 'pickrsi0000000000000000000000003',
        bot_id: 'rsi',
        kind: 'signal',
        wall_time_ms: timeMs,
        synthetic_time_ms: timeMs,
        level: i === rsiSeries.length - 1 ? 'WARN' : 'INFO',
        category: i === rsiSeries.length - 1 ? 'RISK' : 'WORKER',
        payload: {
          seq: i + 1,
          disposition: 'NO_INTENT',
          reason: i === rsiSeries.length - 1 ? 'ETH 1H 收 3,412.6 (RSI 44)，偏差 -0.61% 超過 0.5% 提醒線' : 'bar_closed',
          target: '0',
          mark: '3412.60',
          account: { equity: rsiSeries[i].toFixed(2), unrealized_pnl: '0.00' },
          risk_state: { mode: 'RUN', health: 'HEALTHY', reasons: [] },
        },
      },
    });
  }

  // Synchronized fills (same 8 fills as X/Y/Z)
  const fills: Array<{
    timeMs: number;
    runId: string;
    botId: string;
    side: 'buy' | 'sell';
    qty: string;
    price: string;
    fee: string;
    pos: string;
    equity: string;
    cumFees: string;
  }> = [
    { timeMs: taipeiMs(11, 1, 4, 0, 1), runId: 'pickdon4h00000000000000000000001', botId: 'don4h', side: 'buy', qty: '2', price: '98540.00', fee: '0.9900', pos: '2', equity: '10042.10', cumFees: '0.9900' },
    { timeMs: taipeiMs(11, 4, 13, 0, 1), runId: 'pickrsi0000000000000000000000003', botId: 'rsi', side: 'sell', qty: '3', price: '3310.40', fee: '0.5000', pos: '0', equity: '10032.00', cumFees: '1.4900' },
    { timeMs: taipeiMs(11, 7, 16, 0, 1), runId: 'pickdon4h00000000000000000000001', botId: 'don4h', side: 'sell', qty: '2', price: '100950.20', fee: '1.0100', pos: '0', equity: '10080.20', cumFees: '2.5000' },
    { timeMs: taipeiMs(11, 9, 8, 0, 1), runId: 'picktsmom00000000000000000000002', botId: 'tsmom', side: 'buy', qty: '1', price: '103287.00', fee: '0.5200', pos: '1', equity: '10095.60', cumFees: '3.0200' },
    { timeMs: taipeiMs(11, 12, 8, 0, 1), runId: 'pickdon4h00000000000000000000001', botId: 'don4h', side: 'buy', qty: '1', price: '101411.60', fee: '0.5100', pos: '1', equity: '10134.80', cumFees: '3.5300' },
    { timeMs: taipeiMs(11, 15, 20, 0, 1), runId: 'pickrsi0000000000000000000000003', botId: 'rsi', side: 'buy', qty: '3', price: '3398.50', fee: '0.5100', pos: '3', equity: '10165.27', cumFees: '4.0400' },
    { timeMs: taipeiMs(11, 15, 21, 0, 1), runId: 'pickrsi0000000000000000000000003', botId: 'rsi', side: 'sell', qty: '3', price: '3421.80', fee: '0.5100', pos: '0', equity: '10172.26', cumFees: '4.5500' },
    { timeMs: taipeiMs(11, 16, 4, 0, 1), runId: 'pickdon4h00000000000000000000001', botId: 'don4h', side: 'buy', qty: '1', price: '105412.40', fee: '0.5300', pos: '2', equity: '10198.40', cumFees: '5.0800' },
  ];

  for (const fl of fills) {
    rawEvents.push({
      timeMs: fl.timeMs,
      event: {
        run_id: fl.runId,
        bot_id: fl.botId,
        kind: 'fill',
        wall_time_ms: fl.timeMs,
        synthetic_time_ms: fl.timeMs,
        level: 'INFO',
        category: 'ORDER',
        payload: {
          request: { side: fl.side, tag: FIXED_TAG },
          fill: { quantity: fl.qty, price: fl.price, fee: fl.fee },
          position: fl.pos,
          equity: fl.equity,
          fees: fl.cumFees,
          state: 'FILLED',
        },
      },
    });
  }

  // Synchronized day_basis & reconciliation risk events
  rawEvents.push({
    timeMs: DAY_START_MS + 3000,
    event: {
      run_id: 'pickdon4h00000000000000000000001',
      bot_id: 'don4h',
      kind: 'day_basis',
      wall_time_ms: DAY_START_MS + 3000,
      synthetic_time_ms: DAY_START_MS,
      level: 'INFO',
      category: 'RISK',
      payload: {
        basis: { day: 20261116, equity: '10172.26', period_start_ms: DAY_START_MS },
      },
    },
  });

  rawEvents.push({
    timeMs: NOW_MS + 2000,
    event: {
      run_id: 'pickdon4h00000000000000000000001',
      bot_id: 'don4h',
      kind: 'run_state',
      wall_time_ms: NOW_MS + 2000,
      synthetic_time_ms: NOW_MS,
      level: 'INFO',
      category: 'RISK',
      payload: { previous: 'reconciling', state: 'running (帳本與 OKX 部位、餘額一致)' },
    },
  });

  rawEvents.sort((a, b) => a.timeMs - b.timeMs);
  const events: EventDTO[] = rawEvents.map((entry, index) => ({
    ...entry.event,
    seq: index + 1,
  }));

  return {
    contract: 'catos.simulation.v1',
    version: 1,
    instance_id: 'pickpreview000000000000000000001',
    observed_at_ms: NOW_MS + 2000,
    unchanged: false,
    service: {
      contract: 'catos.simulation.v1',
      mode: 'preview-pick',
      build_id: 'preview-pick-sync-20261123',
      current_build_id: 'preview-pick-sync-20261123',
      restart_required: false,
      instance_id: 'pickpreview000000000000000000001',
      slot: 'running',
      active_run_id: 'pickdon4h00000000000000000000001',
      capabilities: { start: false, stop: false },
      unavailable_reason: null,
      config: { mode: 'preview-pick', note: '對照假資料（與 X／Y／Z 同步）' },
    },
    strategies: [
      {
        strategy_id: 'donchian-breakout',
        version: 'donchian-parameters-v1',
        name: 'Donchian 通道突破',
        description: '突破近期高點做多，跌破低點做空（4H · 模擬盤第 23 天）',
        artifact_hash: 'pickdon4h0000000000000000000000000000000000000000000000000000001',
        entry: 'catos.research_only_artifacts:DonchianBreakout',
        approval_state: 'approved',
        allowed_modes: ['local'],
        defaults: { parameters: { entry_bars: 192, exit_bars: 48, quantity: '2' }, warmup_bars: 192 },
        source_files: ['catos/research_only_artifacts/donchian_breakout.py'],
        kind: 'registered_python_module',
      },
      {
        strategy_id: 'tsmom',
        version: 'tsmom-parameters-v1',
        name: '時間序列動能',
        description: '過去一段時間在漲就持有，在跌就空手（1D · 模擬盤第 15 天）',
        artifact_hash: 'picktsmom0000000000000000000000000000000000000000000000000000002',
        entry: 'strategies.tsmom:TimeSeriesMomentum',
        approval_state: 'approved',
        allowed_modes: ['local'],
        defaults: { parameters: { lookback_days: 90, quantity: '1' }, warmup_bars: 90 },
        source_files: ['strategies/tsmom/strategy.py'],
        kind: 'registered_python_module',
      },
      {
        strategy_id: 'mean-reversion-rsi',
        version: 'rsi-parameters-v1',
        name: '均值回歸 RSI',
        description: '跌過頭買進，漲過頭賣出（1H · 模擬盤第 14 天 · 偏差 -0.61%）',
        artifact_hash: 'pickrsi000000000000000000000000000000000000000000000000000000003',
        entry: 'strategies.mean_reversion_rsi:MeanReversionRSI',
        approval_state: 'approved',
        allowed_modes: ['local'],
        defaults: { parameters: { period: 14, low: 28, high: 72, quantity: '3' }, warmup_bars: 30 },
        source_files: ['strategies/mean_reversion_rsi/strategy.py'],
        kind: 'registered_python_module',
      },
    ],
    bots: [
      {
        version: 1,
        bot_id: 'don4h',
        mode: 'local',
        strategy_id: 'donchian-breakout',
        strategy_version: 'donchian-parameters-v1',
        strategy_name: 'Donchian 通道突破',
        artifact_hash: 'pickdon4h0000000000000000000000000000000000000000000000000000001',
        parameters: { entry_bars: 192, exit_bars: 48, quantity: '2' },
        inst_id: 'BTC-USDT-SWAP',
        symbol: 'BTC-USDT-SWAP',
        contract: { inst_id: 'BTC-USDT-SWAP', base_per_contract: '0.01', tick_size: '0.1', lot_size: '1', min_size: '1' },
        timeframe_ms: 14_400_000,
        trusted: true,
        created_at_ms: BASE_START_MS,
        state: 'running',
        current_run_id: 'pickdon4h00000000000000000000001',
        active: true,
        run_count: 1,
        worker_pid: 41001,
        bars: 138,
        warmup_bars: 192,
        fills: 4,
        last_synthetic_time_ms: NOW_MS,
        run_created_at_ms: BASE_START_MS,
        finished_at_ms: null,
        account_source: 'signal_fill',
        position: '2',
        average_entry: '103412.00',
        balance: '10098.30',
        realized_pnl: '98.30',
        unrealized_pnl: '41.30',
        equity: '10139.60',
        fees: '3.0400',
        funding_paid: '0',
        mark: '105477.00',
        last_disposition: 'HOLD',
        last_reason: '收盤低於 102,880.0 平倉',
        ownership_retained: true,
        error: null,
      },
      {
        version: 1,
        bot_id: 'tsmom',
        mode: 'local',
        strategy_id: 'tsmom',
        strategy_version: 'tsmom-parameters-v1',
        strategy_name: '時間序列動能',
        artifact_hash: 'picktsmom0000000000000000000000000000000000000000000000000000002',
        parameters: { lookback_days: 90, quantity: '1' },
        inst_id: 'BTC-USDT-SWAP',
        symbol: 'BTC-USDT-SWAP',
        contract: { inst_id: 'BTC-USDT-SWAP', base_per_contract: '0.01', tick_size: '0.1', lot_size: '1', min_size: '1' },
        timeframe_ms: 86_400_000,
        trusted: true,
        created_at_ms: taipeiMs(11, 2, 8, 0),
        state: 'running',
        current_run_id: 'picktsmom00000000000000000000002',
        active: true,
        run_count: 1,
        worker_pid: 41002,
        bars: 15,
        warmup_bars: 90,
        fills: 1,
        last_synthetic_time_ms: NOW_MS,
        run_created_at_ms: taipeiMs(11, 2, 8, 0),
        finished_at_ms: null,
        account_source: 'signal_fill',
        position: '1',
        average_entry: '103287.00',
        balance: '10065.27',
        realized_pnl: '65.27',
        unrealized_pnl: '21.90',
        equity: '10087.17',
        fees: '0.5200',
        funding_paid: '0',
        mark: '105477.00',
        last_disposition: 'HOLD',
        last_reason: '90 天報酬轉負平倉',
        ownership_retained: true,
        error: null,
      },
      {
        version: 1,
        bot_id: 'rsi',
        mode: 'local',
        strategy_id: 'mean-reversion-rsi',
        strategy_version: 'rsi-parameters-v1',
        strategy_name: '均值回歸 RSI',
        artifact_hash: 'pickrsi000000000000000000000000000000000000000000000000000000003',
        parameters: { period: 14, low: 28, high: 72, quantity: '3' },
        inst_id: 'ETH-USDT-SWAP',
        symbol: 'ETH-USDT-SWAP',
        contract: { inst_id: 'ETH-USDT-SWAP', base_per_contract: '0.1', tick_size: '0.1', lot_size: '1', min_size: '1' },
        timeframe_ms: 3_600_000,
        trusted: true,
        created_at_ms: taipeiMs(11, 3, 8, 0),
        state: 'running',
        current_run_id: 'pickrsi0000000000000000000000003',
        active: true,
        run_count: 1,
        worker_pid: 41003,
        bars: 336,
        warmup_bars: 30,
        fills: 3,
        last_synthetic_time_ms: taipeiMs(11, 16, 7, 0),
        run_created_at_ms: taipeiMs(11, 3, 8, 0),
        finished_at_ms: null,
        account_source: 'signal_fill',
        position: '0',
        average_entry: '0',
        balance: '9987.60',
        realized_pnl: '-12.40',
        unrealized_pnl: '0.00',
        equity: '9987.60',
        fees: '1.5200',
        funding_paid: '0',
        mark: '3412.60',
        last_disposition: 'NO_INTENT',
        last_reason: '空手 · RSI < 28 買 3 張（偏差 -0.61%）',
        ownership_retained: false,
        error: null,
      },
    ],
    risk: {
      version: 1,
      run_id: 'pickdon4h00000000000000000000001',
      bot_id: 'don4h',
      run_state: 'running',
      seq: 120,
      time_ms: NOW_MS,
      mode: 'RUN',
      health: 'HEALTHY',
      phase: 'IDLE',
      reasons: [],
      epoch: 1,
      limits: {
        leverage: '1.0',
        symbol_share: '0.50',
        soft_loss: '0.05',
        hard_loss: '0.10',
      },
      basis: {
        day: 20261116,
        equity: '10172.26',
        evidence_id: 'preview-pick-day-20261116',
        account_alias: 'okx-demo-sync',
        environment: 'preview-pick',
        source: 'sync_fixture',
        period_start_ms: DAY_START_MS,
      },
      snapshot: {
        seq: 120,
        time_ms: NOW_MS,
        valid_until_ms: NOW_MS + 900_000,
        equity: '10214.37',
        risk_equity: '10214.37',
        position: '3',
        mark: '105477.00',
        pending_buy: '0',
        pending_sell: '0',
        other_notional: '1054.77',
        external_net: '0',
        valuation_known: true,
        flows_known: true,
        margin_ok: true,
        position_verified: true,
        reduction_conflict: false,
        flow_basis_id: 'preview-pick-day-20261116',
        flow_start_ms: DAY_START_MS,
      },
      derived: {
        period_pnl: '42.11',
        period_pnl_ratio: '0.00413969',
        notional: '3164.31',
        effective_leverage: '0.31',
        exposure_budget: '10214.37',
        symbol_budget: '5107.19',
        can_increase: true,
        status: 'normal',
      },
    },
    positions: [
      {
        bot_id: 'don4h',
        run_id: 'pickdon4h00000000000000000000001',
        run_state: 'running',
        inst_id: 'BTC-USDT-SWAP',
        symbol: 'BTC-USDT-SWAP',
        position: '2',
        average_entry: '103412.00',
        mark: '105477.00',
        unrealized_pnl: '41.30',
        notional: '2109.54',
        verified: true,
        protection: null,
        funding_interval_ms: null,
        funding_rate: null,
        liquidation_price: null,
        margin: null,
      },
      {
        bot_id: 'tsmom',
        run_id: 'picktsmom00000000000000000000002',
        run_state: 'running',
        inst_id: 'BTC-USDT-SWAP',
        symbol: 'BTC-USDT-SWAP',
        position: '1',
        average_entry: '103287.00',
        mark: '105477.00',
        unrealized_pnl: '21.90',
        notional: '1054.77',
        verified: true,
        protection: null,
        funding_interval_ms: null,
        funding_rate: null,
        liquidation_price: null,
        margin: null,
      },
    ],
    summary: {
      equity: '10214.37',
      realized_pnl: '151.17',
      unrealized_pnl: '63.20',
      fees: '5.0800',
      period_pnl: '42.11',
      period_pnl_ratio: '0.00413969',
      period_start_ms: DAY_START_MS,
      basis_equity: '10172.26',
      running_bots: 3,
      total_bots: 3,
      risk_status: 'normal',
      effective_leverage: '0.31',
      leverage_limit: '1.0',
      invariants: {
        fixed_tag: FIXED_TAG,
        settlement: 'cross_net_mode',
        arithmetic: 'decimal_text',
      },
    },
    kill_switch: {
      engaged: false,
      error: null,
      engaged_record: null,
      count: 0,
      recent: [],
      confirm_word: '解除',
      default_limits: {
        leverage: '1.0',
        symbol_share: '0.50',
        soft_loss: '0.05',
        hard_loss: '0.10',
      },
      version: 1,
    },
    events: {
      items: events,
      next_since: events.length,
      omitted: 0,
    },
    domains: {
      service: 1,
      bots: 1,
      risk: 1,
      positions: 1,
      events: 1,
    },
  };
}
