import type { BotMonitorRow } from '@/components/catos/bot-monitor-table';
import type { ProtectionMonitoringView } from '@/components/catos/position-protection-table';
import type { MonitoredEvent } from '@/components/catos/unified-activity-deck-card';

// Fixed display strings only; this fixture does not perform trading arithmetic.
export const bots: BotMonitorRow[] = [
  { id: 'tabby', name: 'Tabby', contract: 'BTC-USDT-SWAP · 15m', strategy: 'breakout_v22', position: '0.85 BTC', pnl: '+$561.43',
    summary: '續抱多單，尚未出現出場訊號。', status: '續抱', phase: '等待下一根收盤', bar: '11:00 收盤 K 線', target: '維持 0.85 BTC',
    condition: '已收盤價格仍在策略持有區間；策略停損條件未成立。',
    stages: [['資料', '11:00 已收盤'], ['意圖', 'HOLD'], ['風控', '無新增曝險'], ['委託', '無新委託'], ['對帳', '部位已同步']],
    next: '下一次評估：11:15 K 線收盤後；交易所端災難停損已確認。' },
  { id: 'calico', name: 'Calico', contract: 'ETH-USDT-SWAP · 1h', strategy: 'trend_follow', position: '9.50 ETH', pnl: '+$524.40',
    summary: '策略要求增持至 10.5 ETH，委託待對帳。', status: 'UNKNOWN', phase: '保留額度 · 禁增倉', warning: true,
    bar: '11:00 收盤 K 線', target: '10.50 ETH（尚未達成）', condition: '收盤趨勢條件成立；增倉委託已送出，但回覆逾時，不能確認是否成交。',
    stages: [['資料', '11:00 已收盤'], ['意圖', '目標 10.5 ETH'], ['風控', '額度仍保留'], ['委託', 'UNKNOWN'], ['對帳', '等待可信終態']],
    next: '下一步：核對原委託與成交來源。未取得可信終態前，不盲目重送、不釋放額度；合法減倉依既有路徑。' },
  { id: 'mochi', name: 'Mochi', contract: 'SOL-USDT-SWAP · 5m', strategy: 'grid_mm', position: '95.0 SOL', pnl: '+$437.00',
    summary: '策略要求增持至 105 SOL，保護待確認而擋下。', status: '禁增倉', phase: 'P6 更新待確認', warning: true,
    bar: '11:10 收盤 K 線', target: '105.0 SOL（尚未達成）', condition: '收盤加倉條件成立；交易所端災難停損更新尚未確認，Supervisor 阻擋新增曝險。',
    stages: [['資料', '11:10 已收盤'], ['意圖', '目標 105 SOL'], ['風控', '保護未確認'], ['委託', '未送增倉單'], ['對帳', '現有部位同步']],
    next: '下一步：檢查保護委託終態。此限制不會自動減持；不能把更新目標價當成已生效保護。' },
  { id: 'shiro', name: 'Shiro', contract: 'ARB-USDT-SWAP · 1h', strategy: 'pairs', position: '空倉', pnl: '—',
    summary: '已暫停，不產生新策略意圖。', status: '暫停', phase: '未啟用', paused: true,
    bar: '未評估', target: '無新目標', condition: 'Bot 暫停，尚未取得合約執行權。',
    stages: [['資料', '未評估'], ['意圖', '無'], ['風控', '未啟用'], ['委託', '無'], ['對帳', '空倉']],
    next: '目前沒有待處理的策略意圖。' },
];

export const protection: ProtectionMonitoringView = {
  positions: [
    { bot: 'Tabby', contract: 'BTC-USDT-SWAP', quantity: '0.85 BTC', entry: '61,480.00', mark: '62,140.50', pnl: '+$561.43', stop: '59,500.00', confirmed: true,
      notional: '52,819.43', liquidation: '54,210.00', distance: '12.7%', leverage: '3x Cross',
      confirmation: '已確認 · 11:14:58', detail: '來源：合成 OKX 保護委託快照；有效保護數量 0.85 BTC，mark 觸發，多倉向上取整。', next: '目前保護與部位數量一致；均價變更時仍須重新確認。' },
    { bot: 'Calico', contract: 'ETH-USDT-SWAP', quantity: '9.50 ETH', entry: '3,320.00', mark: '3,375.20', pnl: '+$524.40', stop: '3,210.00', confirmed: true,
      notional: '32,064.40', liquidation: '2,980.00', distance: '11.7%', leverage: '3x Cross',
      confirmation: '已確認 · 11:14:58', detail: '來源：合成 OKX 保護委託快照；有效保護數量 9.50 ETH。增倉委託 UNKNOWN，保護確認僅涵蓋目前已核對的部位。', next: '先完成增倉委託對帳；若部位改變，必須重新確認保護覆蓋。' },
    { bot: 'Mochi', contract: 'SOL-USDT-SWAP', quantity: '95.0 SOL', entry: '148.20', mark: '152.80', pnl: '+$437.00', stop: '142.00', confirmed: false,
      notional: '14,516.00', liquidation: '131.50', distance: '13.9%', leverage: '3x Cross',
      confirmation: '更新待確認 · 禁增倉', detail: '11:09:18 更新請求尚無可信終態；目前有效保護價與覆蓋量未確認。$142.00 僅為更新目標，不能視為已生效。來源：合成保護回報。',
      next: '下一步：檢查交易所保護委託終態，完成核對前禁止增加曝險，不自動減持。' },
  ],
  orders: [{ id: 'fixture-eth-01', bot: 'Calico', contract: 'ETH-USDT-SWAP', intent: '增加 1.00 ETH → 目標 10.50 ETH', status: 'UNKNOWN · 待對帳', detail: '11:10:02 回覆逾時；是否接受或成交尚未確認。此筆請求額度仍保留。' }],
};

export const events: MonitoredEvent[] = [
  { id: 'unknown', time: '11:10:02', category: 'ALERT', severity: 'WARN', source: 'Supervisor', botName: 'Calico', title: 'ETH 增倉委託 UNKNOWN', resolution: 'open',
    detail: '策略目標 10.50 ETH；目前核對部位 9.50 ETH。送單回覆逾時，尚未確認最終結果。', impact: '增倉受限，對應額度保持占用；不能直接認定委託失敗。', nextStep: '核對原委託與成交來源，取得可信終態；禁止盲目重送。' },
  { id: 'protection', time: '11:09:18', category: 'ALERT', severity: 'WARN', source: 'P6 Guard', botName: 'Mochi', title: 'SOL 災難停損更新未確認', resolution: 'open',
    detail: '現有部位 95 SOL；保護更新目標 $142.00，尚未確認生效。105 SOL 策略目標的增倉委託未送出。', impact: '禁止增加曝險；不自動減持，合法減倉依既有路徑。', nextStep: '核對保護委託終態與覆蓋數量；確認前不顯示「保護中」。' },
  { id: 'heartbeat', time: '11:14:58', category: 'SYSTEM', severity: 'OK', source: 'Supervisor', title: '部位核對完成 · 保護仍有 1 筆待確認', detail: 'BTC、ETH、SOL 已核對目前部位；P6 確認 2/3，Mochi 未確認狀態持續保留。' },
  { id: 'resolved', time: '10:45:16', category: 'ALERT', severity: 'WARN', source: 'Market Feed', botName: 'Tabby', title: 'BTC 收盤 K 線延遲 · 已恢復', resolution: 'resolved',
    detail: '10:45:16 已補齊並核對收盤資料，恢復後重新評估；目前沒有此項資料限制。歷史告警仍保留於日誌。', nextStep: '此事件已解除，無待處理事項；不影響其他未解除原因。' },
  { id: 'fill', time: '10:30:00', category: 'FILL', severity: 'TRADE', source: 'OKX-SWAP', botName: 'Mochi', title: 'SOL 開多成交', symbol: 'SOL-USDT-SWAP', action: '開多', side: 'buy', qty: '95.0', price: '148.20',
    detail: '合成成交紀錄：部位 95.0 SOL。後續保護更新狀態請見未解除事件。' },
  { id: 'paused', time: '09:30:10', category: 'SYSTEM', severity: 'INFO', source: 'Supervisor', botName: 'Shiro', title: 'Shiro 已暫停 · 空倉', detail: '沒有在途委託，未取得合約執行權；不產生新策略意圖。' },
];
