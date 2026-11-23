/**
 * Temporary design-comparison fixture (`?preview=pick` only).
 * Generated from real OKX BTC-USDT-SWAP 4H history (2024-10-24 12:00 -> 2024-11-16 08:00 Asia/Taipei,
 * BTC $67,134.4 -> $91,265.8, +35.94%) and synchronized with docs/design/2026-11-16-redesign-pick/{X,Y,Z}.html.
 * Never loaded in normal mode and never touches real backend state or data roots.
 */
import type { EventDTO, WorkspaceStateDTO } from '@/contracts';

const BASE_START_MS = 1729742400000; // 2024-10-24 12:00 Asia/Taipei
const DAY_START_MS = 1731686400000; // 2024-11-16 00:00 Asia/Taipei
const NOW_MS = 1731715200000; // 2024-11-16 08:00 Asia/Taipei
const FIXED_TAG = '41cb53c54d6dABDE';

// Real 138-bar 4H account equity & BTC close series from data/okx/BTC-USDT-SWAP/4H
const REAL_EQ_BARS: Array<[number, string, string, string]> = [[1729742400000,"10000.00","67134.4","0"],[1729756800000,"10000.00","67294.4","0"],[1729771200000,"10000.00","67699.7","0"],[1729785600000,"9998.98","68305.2","-1.02"],[1729800000000,"9995.90","68202.6","-4.10"],[1729814400000,"9990.00","68006","-10.00"],[1729828800000,"9976.23","67546.9","-23.77"],[1729843200000,"9992.95","68104.3","-7.05"],[1729857600000,"9980.40","67685.8","-19.60"],[1729872000000,"9955.58","66858.7","-44.42"],[1729886400000,"9950.67","66695","-49.33"],[1729900800000,"9956.91","66903","-43.09"],[1729915200000,"9959.89","67002.3","-40.11"],[1729929600000,"9963.76","67131.3","-36.24"],[1729944000000,"9956.46","66887.9","-43.54"],[1729958400000,"9965.18","67178.5","-34.82"],[1729972800000,"9962.82","67100","-37.18"],[1729987200000,"9968.71","67296.1","-31.29"],[1730001600000,"9965.82","67200","-34.18"],[1730016000000,"9963.58","67125.2","-36.42"],[1730030400000,"9983.53","67790.1","-16.47"],[1730044800000,"9985.27","67848.1","-14.73"],[1730059200000,"9990.67","68028.2","-9.33"],[1730073600000,"9981.70","67729.2","-18.30"],[1730088000000,"10002.53","68423.4","2.53"],[1730102400000,"10012.75","68764.2","12.75"],[1730116800000,"10004.74","68497.1","4.74"],[1730131200000,"10038.90","69635.9","38.90"],[1730145600000,"10048.98","69971.9","48.98"],[1730160000000,"10078.74","70963.7","78.74"],[1730174400000,"10080.60","71025.9","80.60"],[1730188800000,"10093.55","71457.5","93.55"],[1730203200000,"10122.15","72410.9","122.15"],[1730217600000,"10126.61","72559.5","126.61"],[1730232000000,"10132.36","72751.3","132.36"],[1730246400000,"10117.98","72271.7","117.98"],[1730260800000,"10117.17","72244.8","117.17"],[1730275200000,"10110.15","72010.7","110.15"],[1730289600000,"10111.66","72061.3","111.66"],[1730304000000,"10104.92","71836.4","104.92"],[1730318400000,"10120.12","72343.2","120.12"],[1730332800000,"10120.51","72356.2","120.51"],[1730347200000,"10122.27","72414.9","122.27"],[1730361600000,"10116.74","72230.5","116.74"],[1730376000000,"10067.88","70637.2","67.88"],[1730390400000,"10067.88","70110.2","67.88"],[1730404800000,"10067.88","70304.3","67.88"],[1730419200000,"10067.88","69373.5","67.88"],[1730433600000,"10067.19","69282.9","67.88"],[1730448000000,"10081.60","70003.6","67.88"],[1730462400000,"10069.41","69393.8","67.88"],[1730476800000,"10067.15","69281","67.88"],[1730491200000,"10071.47","69496.8","67.88"],[1730505600000,"10073.51","69598.9","67.88"],[1730520000000,"10091.43","69823.4","67.88"],[1730534400000,"10087.08","69606","67.88"],[1730548800000,"10083.03","69403.2","67.88"],[1730563200000,"10085.12","69508.1","67.88"],[1730577600000,"10082.62","69382.9","67.88"],[1730592000000,"10062.70","68387.1","67.88"],[1730606400000,"10063.12","68407.8","67.88"],[1730620800000,"10062.02","68353","67.88"],[1730635200000,"10057.01","68102.3","67.88"],[1730649600000,"10068.68","68685.8","67.88"],[1730664000000,"10070.50","68776.9","67.88"],[1730678400000,"10076.10","69056.7","67.88"],[1730692800000,"10067.57","68630.5","67.88"],[1730707200000,"10070.96","68800","67.88"],[1730721600000,"10067.69","68636.5","67.88"],[1730736000000,"10051.99","67851.6","67.88"],[1730750400000,"10052.14","67858.8","67.88"],[1730764800000,"10059.70","68237.1","67.88"],[1730779200000,"10072.84","68893.7","67.88"],[1730793600000,"10071.26","68815","67.88"],[1730808000000,"10086.68","69638","66.84"],[1730822400000,"10054.72","68998.7","47.66"],[1730836800000,"10073.88","69381.9","59.16"],[1730851200000,"10323.68","74378","209.04"],[1730865600000,"10275.75","73419.2","180.28"],[1730880000000,"10319.38","74292","206.46"],[1730894400000,"10319.58","74296.1","206.58"],[1730908800000,"10396.30","75830.3","252.61"],[1730923200000,"10384.70","75598.2","245.65"],[1730937600000,"10357.83","75061","229.53"],[1730952000000,"10343.93","74783","221.19"],[1730966400000,"10343.37","74771.8","220.85"],[1730980800000,"10407.78","76059.9","259.50"],[1730995200000,"10430.78","76520","273.30"],[1731009600000,"10378.12","75856","253.38"],[1731024000000,"10380.50","75903.5","254.81"],[1731038400000,"10394.20","76177.5","263.03"],[1731052800000,"10382.74","75948.3","256.15"],[1731067200000,"10406.07","76415.1","270.15"],[1731081600000,"10430.42","76902.1","284.76"],[1731096000000,"10410.40","76501.6","272.75"],[1731110400000,"10402.62","76346.1","268.08"],[1731124800000,"10412.27","76539.1","273.87"],[1731139200000,"10410.30","76499.6","272.69"],[1731153600000,"10401.01","76313.8","267.11"],[1731168000000,"10396.12","76216.1","264.18"],[1731182400000,"10419.72","76688","278.34"],[1731196800000,"10446.34","77220.2","294.31"],[1731211200000,"10527.54","78844.2","343.03"],[1731225600000,"10581.02","79914","375.12"],[1731240000000,"10570.32","79700","368.70"],[1731254400000,"10574.32","79779.9","371.10"],[1731268800000,"10604.29","80379.4","389.08"],[1731283200000,"10666.09","81615.2","426.16"],[1731297600000,"10640.92","81111.9","411.06"],[1731312000000,"10693.04","82154.2","442.33"],[1731326400000,"10790.19","84097.3","500.62"],[1731340800000,"10893.36","86160.7","562.52"],[1731355200000,"11020.32","88700.1","638.70"],[1731369600000,"10992.07","88135.1","621.75"],[1731384000000,"11037.76","89048.7","649.16"],[1731398400000,"10946.92","87232","594.66"],[1731412800000,"10915.32","86600","575.70"],[1731427200000,"11021.17","88716.9","639.21"],[1731441600000,"10982.76","87948.8","616.16"],[1731456000000,"10943.32","87159.9","592.50"],[1731470400000,"10953.72","87367.9","598.74"],[1731484800000,"10968.74","87668.2","607.75"],[1731499200000,"11213.39","92561.2","754.54"],[1731513600000,"11095.32","90200.1","683.70"],[1731528000000,"11104.51","90383.8","689.21"],[1731542400000,"11084.32","89979.9","677.10"],[1731556800000,"11125.32","90800","701.70"],[1731571200000,"11160.32","91499.9","722.70"],[1731585600000,"10983.62","87965.9","616.68"],[1731600000000,"11059.39","89481.3","662.14"],[1731614400000,"10952.79","87349.4","598.18"],[1731628800000,"10995.61","88205.8","623.87"],[1731643200000,"10967.82","87650.1","607.20"],[1731657600000,"11094.28","89742","669.96"],[1731672000000,"11029.26","88441.6","630.95"],[1731686400000,"11126.87","90393.8","689.51"],[1731700800000,"11159.68","91050","709.20"],[1731715200000,"11170.47","91265.8","715.67"]];
const REAL_TSMOM_BARS: Array<[number, string]> = [[1730433600000,"9999.31"],[1730462400000,"10001.53"],[1730491200000,"10003.59"],[1730520000000,"10010.12"],[1730548800000,"10001.72"],[1730577600000,"10001.31"],[1730606400000,"9981.81"],[1730635200000,"9975.70"],[1730664000000,"9989.19"],[1730692800000,"9986.26"],[1730721600000,"9986.38"],[1730750400000,"9970.83"],[1730779200000,"9991.53"],[1730808000000,"10006.41"],[1730836800000,"10001.29"],[1730865600000,"10082.04"],[1730894400000,"10099.57"],[1730923200000,"10125.62"],[1730952000000,"10109.31"],[1730980800000,"10134.85"],[1731009600000,"10130.77"],[1731038400000,"10137.20"],[1731067200000,"10141.95"],[1731096000000,"10143.68"],[1731124800000,"10144.43"],[1731153600000,"10139.93"],[1731182400000,"10147.41"],[1731211200000,"10190.54"],[1731240000000,"10207.65"],[1731268800000,"10221.24"],[1731297600000,"10235.89"],[1731326400000,"10295.60"],[1731355200000,"10387.65"],[1731384000000,"10394.63"],[1731412800000,"10345.65"],[1731441600000,"10372.63"],[1731470400000,"10361.01"],[1731499200000,"10464.88"],[1731528000000,"10421.33"],[1731556800000,"10429.65"],[1731585600000,"10372.97"],[1731614400000,"10360.64"],[1731643200000,"10366.65"],[1731672000000,"10382.48"],[1731700800000,"10434.65"],[1731715200000,"10438.97"]];
const REAL_RSI_BARS: Array<[number, string]> = [[1730520000000,"10013.43"],[1730563200000,"10013.43"],[1730606400000,"10013.43"],[1730649600000,"10013.43"],[1730692800000,"10013.43"],[1730736000000,"10013.43"],[1730779200000,"10013.43"],[1730822400000,"10013.43"],[1730865600000,"10013.43"],[1730908800000,"10013.43"],[1730952000000,"10013.43"],[1730995200000,"10013.43"],[1731038400000,"9993.97"],[1731081600000,"9993.97"],[1731124800000,"9993.97"],[1731168000000,"9993.97"],[1731211200000,"9993.97"],[1731254400000,"9993.97"],[1731297600000,"9993.97"],[1731340800000,"9993.97"],[1731384000000,"9993.97"],[1731427200000,"9993.97"],[1731470400000,"9993.97"],[1731513600000,"9993.97"],[1731556800000,"9993.97"],[1731600000000,"9993.97"],[1731643200000,"9993.97"],[1731686400000,"10015.83"],[1731715200000,"10015.83"]];

export function isPreviewPickMode(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return new URLSearchParams(window.location.search).get('preview') === 'pick';
  } catch {
    return false;
  }
}

export function buildPreviewPickState(): WorkspaceStateDTO {
  const rawEvents: Array<{ timeMs: number; event: Omit<EventDTO, 'seq'> }> = [];

  // 138 real 4H account equity points (attached to don4h so AccountEquityBand renders the exact X/Y/Z curve)
  for (let i = 0; i < REAL_EQ_BARS.length; i++) {
    const [timeMs, eq, closePx] = REAL_EQ_BARS[i];
    const isLast = i === REAL_EQ_BARS.length - 1;
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
          reason: isLast ? 'BTC 4H 收 91,265.8，高於平倉線 86,666.0 續抱' : 'bar_closed',
          target: i >= 74 || (i >= 3 && i < 44) ? '3' : '0',
          mark: closePx,
          account: {
            equity: eq,
            unrealized_pnl: isLast ? '648.83' : '0.00',
          },
          risk_state: { mode: 'RUN', health: 'HEALTHY', reasons: [] },
        },
      },
    });
  }

  // Sparkline points for tsmom and rsi (real BTC/ETH series)
  for (let i = 0; i < REAL_TSMOM_BARS.length; i++) {
    const [timeMs, eq] = REAL_TSMOM_BARS[i];
    const isLast = i === REAL_TSMOM_BARS.length - 1;
    rawEvents.push({
      timeMs: timeMs - 1000,
      event: {
        run_id: 'picktsmom00000000000000000000002',
        bot_id: 'tsmom',
        kind: 'signal',
        wall_time_ms: timeMs - 1000,
        synthetic_time_ms: timeMs,
        level: 'INFO',
        category: 'WORKER',
        payload: {
          seq: i + 1,
          disposition: 'HOLD',
          reason: isLast ? 'BTC 1D 90 日動能 +53.8%，續抱 2 張' : 'bar_closed',
          target: '2',
          mark: '91265.8',
          account: { equity: eq, unrealized_pnl: '439.66' },
          risk_state: { mode: 'RUN', health: 'HEALTHY', reasons: [] },
        },
      },
    });
  }

  for (let i = 0; i < REAL_RSI_BARS.length; i++) {
    const [timeMs, eq] = REAL_RSI_BARS[i];
    const isLast = i === REAL_RSI_BARS.length - 1;
    rawEvents.push({
      timeMs: timeMs - 2000,
      event: {
        run_id: 'pickrsi0000000000000000000000003',
        bot_id: 'rsi',
        kind: 'signal',
        wall_time_ms: timeMs - 2000,
        synthetic_time_ms: timeMs,
        level: isLast ? 'WARN' : 'INFO',
        category: isLast ? 'RISK' : 'WORKER',
        payload: {
          seq: i + 1,
          disposition: 'NO_INTENT',
          reason: isLast ? 'ETH 1H 收 3,124.8 (RSI 46)，偏差 -0.61% 超過 0.5% 提醒線' : 'bar_closed',
          target: '0',
          mark: '3124.8',
          account: { equity: eq, unrealized_pnl: '0.00' },
          risk_state: { mode: 'RUN', health: 'HEALTHY', reasons: [] },
        },
      },
    });
  }

  // Real trades synchronized with X/Y/Z
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
    {
        "timeMs": 1729785601000,
        "runId": "pickdon4h00000000000000000000001",
        "botId": "don4h",
        "side": "buy",
        "qty": "3",
        "price": "68305.20",
        "fee": "1.0200",
        "pos": "3",
        "equity": "9998.98",
        "cumFees": "1.0200"
    },
    {
        "timeMs": 1730376001000,
        "runId": "pickdon4h00000000000000000000001",
        "botId": "don4h",
        "side": "sell",
        "qty": "3",
        "price": "70637.20",
        "fee": "1.0600",
        "pos": "0",
        "equity": "10067.88",
        "cumFees": "2.0800"
    },
    {
        "timeMs": 1730433601000,
        "runId": "picktsmom00000000000000000000002",
        "botId": "tsmom",
        "side": "buy",
        "qty": "2",
        "price": "69282.90",
        "fee": "0.6900",
        "pos": "2",
        "equity": "10067.19",
        "cumFees": "2.7700"
    },
    {
        "timeMs": 1730505601000,
        "runId": "pickrsi0000000000000000000000003",
        "botId": "rsi",
        "side": "buy",
        "qty": "3",
        "price": "2508.40",
        "fee": "0.3800",
        "pos": "3",
        "equity": "10091.43",
        "cumFees": "3.1500"
    },
    {
        "timeMs": 1730520001000,
        "runId": "pickrsi0000000000000000000000003",
        "botId": "rsi",
        "side": "sell",
        "qty": "3",
        "price": "2555.70",
        "fee": "0.3800",
        "pos": "0",
        "equity": "10091.43",
        "cumFees": "3.5300"
    },
    {
        "timeMs": 1730808001000,
        "runId": "pickdon4h00000000000000000000001",
        "botId": "don4h",
        "side": "buy",
        "qty": "3",
        "price": "69638.00",
        "fee": "1.0400",
        "pos": "3",
        "equity": "10086.68",
        "cumFees": "4.5700"
    },
    {
        "timeMs": 1730995201000,
        "runId": "pickrsi0000000000000000000000003",
        "botId": "rsi",
        "side": "buy",
        "qty": "3",
        "price": "2892.50",
        "fee": "0.4300",
        "pos": "3",
        "equity": "10378.12",
        "cumFees": "5.0000"
    },
    {
        "timeMs": 1731009601000,
        "runId": "pickrsi0000000000000000000000003",
        "botId": "rsi",
        "side": "sell",
        "qty": "3",
        "price": "2830.50",
        "fee": "0.4300",
        "pos": "0",
        "equity": "10378.12",
        "cumFees": "5.4300"
    },
    {
        "timeMs": 1731643201000,
        "runId": "pickrsi0000000000000000000000003",
        "botId": "rsi",
        "side": "buy",
        "qty": "3",
        "price": "3052.00",
        "fee": "0.4700",
        "pos": "3",
        "equity": "11094.28",
        "cumFees": "5.9000"
    },
    {
        "timeMs": 1731657601000,
        "runId": "pickrsi0000000000000000000000003",
        "botId": "rsi",
        "side": "sell",
        "qty": "3",
        "price": "3128.00",
        "fee": "0.4700",
        "pos": "0",
        "equity": "11094.28",
        "cumFees": "6.3700"
    }
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

  // Day basis & reconciliation risk events
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
        basis: { day: 20241116, equity: '11029.26', period_start_ms: DAY_START_MS },
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
    instance_id: 'pickpreview000000000000000000002',
    observed_at_ms: NOW_MS + 2000,
    unchanged: false,
    service: {
      contract: 'catos.simulation.v1',
      mode: 'preview-pick',
      build_id: 'preview-pick-real-btc-20241024-1116',
      current_build_id: 'preview-pick-real-btc-20241024-1116',
      restart_required: false,
      instance_id: 'pickpreview000000000000000000002',
      slot: 'running',
      active_run_id: 'pickdon4h00000000000000000000001',
      capabilities: { start: false, stop: false },
      unavailable_reason: null,
      config: { mode: 'preview-pick', source: 'OKX BTC-USDT-SWAP 4H 真實上漲行情 (10/24-11/16)' },
    },
    strategies: [
      {
        strategy_id: 'donchian-breakout',
        version: 'donchian-parameters-v1',
        name: 'Donchian 通道突破',
        description: '突破近期高點做多，跌破低點平倉（4H · 模擬盤第 23 天）',
        artifact_hash: 'pickdon4h0000000000000000000000000000000000000000000000000000001',
        entry: 'catos.research_only_artifacts:DonchianBreakout',
        approval_state: 'approved',
        allowed_modes: ['local'],
        defaults: { parameters: { entry_bars: 16, exit_bars: 10, quantity: '3' }, warmup_bars: 40 },
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
        defaults: { parameters: { lookback_days: 90, quantity: '2' }, warmup_bars: 90 },
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
        parameters: { entry_bars: 16, exit_bars: 10, quantity: '3' },
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
        warmup_bars: 40,
        fills: 3,
        last_synthetic_time_ms: NOW_MS,
        run_created_at_ms: BASE_START_MS,
        finished_at_ms: null,
        account_source: 'signal_fill',
        position: '3',
        average_entry: '69638.00',
        balance: '10066.84',
        realized_pnl: '69.96',
        unrealized_pnl: '648.83',
        equity: '10715.67',
        fees: '3.1200',
        funding_paid: '0',
        mark: '91265.80',
        last_disposition: 'HOLD',
        last_reason: '收盤低於 86,666.0 平倉',
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
        parameters: { lookback_days: 90, quantity: '2' },
        inst_id: 'BTC-USDT-SWAP',
        symbol: 'BTC-USDT-SWAP',
        contract: { inst_id: 'BTC-USDT-SWAP', base_per_contract: '0.01', tick_size: '0.1', lot_size: '1', min_size: '1' },
        timeframe_ms: 86_400_000,
        trusted: true,
        created_at_ms: 1730433600000,
        state: 'running',
        current_run_id: 'picktsmom00000000000000000000002',
        active: true,
        run_count: 1,
        worker_pid: 41002,
        bars: 15,
        warmup_bars: 90,
        fills: 1,
        last_synthetic_time_ms: NOW_MS,
        run_created_at_ms: 1730433600000,
        finished_at_ms: null,
        account_source: 'signal_fill',
        position: '2',
        average_entry: '69282.90',
        balance: '9999.31',
        realized_pnl: '0.00',
        unrealized_pnl: '439.66',
        equity: '10438.97',
        fees: '0.6900',
        funding_paid: '0',
        mark: '91265.80',
        last_disposition: 'HOLD',
        last_reason: '90 天報酬 +53.8% 續抱',
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
        created_at_ms: 1730520000000,
        state: 'running',
        current_run_id: 'pickrsi0000000000000000000000003',
        active: true,
        run_count: 1,
        worker_pid: 41003,
        bars: 336,
        warmup_bars: 30,
        fills: 6,
        last_synthetic_time_ms: NOW_MS - 3_600_000,
        run_created_at_ms: 1730520000000,
        finished_at_ms: null,
        account_source: 'signal_fill',
        position: '0',
        average_entry: '0',
        balance: '10015.83',
        realized_pnl: '18.39',
        unrealized_pnl: '0.00',
        equity: '10015.83',
        fees: '2.5600',
        funding_paid: '0',
        mark: '3124.80',
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
      seq: 138,
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
        day: 20241116,
        equity: '11029.26',
        evidence_id: 'preview-pick-real-btc-day-20241116',
        account_alias: 'okx-demo-sync',
        environment: 'preview-pick',
        source: 'okx_real_history_4h',
        period_start_ms: DAY_START_MS,
      },
      snapshot: {
        seq: 138,
        time_ms: NOW_MS,
        valid_until_ms: NOW_MS + 900_000,
        equity: '11170.47',
        risk_equity: '11170.47',
        position: '5',
        mark: '91265.80',
        pending_buy: '0',
        pending_sell: '0',
        other_notional: '1825.32',
        external_net: '0',
        valuation_known: true,
        flows_known: true,
        margin_ok: true,
        position_verified: true,
        reduction_conflict: false,
        flow_basis_id: 'preview-pick-real-btc-day-20241116',
        flow_start_ms: DAY_START_MS,
      },
      derived: {
        period_pnl: '141.21',
        period_pnl_ratio: '0.01280322',
        notional: '4563.29',
        effective_leverage: '0.41',
        exposure_budget: '11170.47',
        symbol_budget: '5585.23',
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
        position: '3',
        average_entry: '69638.00',
        mark: '91265.80',
        unrealized_pnl: '648.83',
        notional: '2737.97',
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
        position: '2',
        average_entry: '69282.90',
        mark: '91265.80',
        unrealized_pnl: '439.66',
        notional: '1825.32',
        verified: true,
        protection: null,
        funding_interval_ms: null,
        funding_rate: null,
        liquidation_price: null,
        margin: null,
      },
    ],
    summary: {
      equity: '11170.47',
      realized_pnl: '88.35',
      unrealized_pnl: '1088.49',
      fees: '6.3700',
      period_pnl: '141.21',
      period_pnl_ratio: '0.01280322',
      period_start_ms: DAY_START_MS,
      basis_equity: '11029.26',
      running_bots: 3,
      total_bots: 3,
      risk_status: 'normal',
      effective_leverage: '0.41',
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
