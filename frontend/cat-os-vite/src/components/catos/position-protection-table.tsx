import { useState } from 'react';
import { cn } from '@/lib/utils';

export interface ProtectedPosition {
  bot: string; contract: string; quantity: string; entry: string; mark: string; pnl: string;
  notional: string; liquidation: string; distance: string; leverage: string;
  stop: string; confirmed: boolean; confirmation: string; detail: string; next: string;
  funding?: number;
}
export interface ProtectionMonitoringView {
  positions: ProtectedPosition[];
  orders: { id: string; bot: string; contract: string; intent: string; status: string; detail: string }[];
}

export function PositionProtectionTable({ positions, orders, tab }: ProtectionMonitoringView & { tab: 'positions' | 'orders' }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  if (tab === 'orders') return <div className="flex h-full flex-col">
    <table className="w-full text-left text-[11px]">
      <thead className="border-b border-border bg-background/40 font-mono text-[9.5px] text-muted-foreground"><tr>{['BOT / CONTRACT', '策略請求', '委託狀態 / 處理方式'].map(label => <th key={label} className="px-3 py-2 font-medium">{label}</th>)}</tr></thead>
      <tbody>{orders.map(order => <tr key={order.id} className="border-b border-border/40"><td className="px-3 py-3"><b>{order.bot}</b><div className="mt-1 font-mono text-[9px] text-muted-foreground">{order.contract}</div></td><td className="px-3 py-3">{order.intent}</td><td className="px-3 py-3"><b className="text-amber-400">{order.status}</b><p className="mt-1 text-[10px] leading-relaxed text-muted-foreground">{order.detail}</p></td></tr>)}</tbody>
    </table>
    <p className="mt-auto border-t border-border px-3 py-2 text-[10px] text-muted-foreground">委託尚無可信終態；保留額度，禁止盲目重送。此處為唯讀示範。</p>
  </div>;
  return <table className="w-full min-w-[720px] text-left text-[11px]">
    <thead className="sticky top-0 z-10 border-b border-border bg-surface font-mono text-[9.5px] text-muted-foreground"><tr>{['BOT / CONTRACT', '部位 / 名義金額 / 損益', '成本 / 標記價', '8H 資金費率', '預估強平 / 距爆倉', 'P6 災難停損 / 保護確認', '槓桿'].map(label => <th key={label} className="px-2 py-2 font-medium">{label}</th>)}</tr></thead>
    <tbody>{positions.map(position => {
      const fund = position.funding ?? (position.contract.includes('BTC') ? 0.0102 : position.contract.includes('ETH') ? 0.0084 : -0.0031);
      return (
      <tr key={position.bot} className="border-b border-border/40 align-top hover:bg-secondary/40">
        <td className="px-2 py-3"><b>{position.bot}</b><div className="mt-1 font-mono text-[9px] text-muted-foreground">{position.contract}</div></td>
        <td className="px-2 py-3 font-mono"><div className="whitespace-nowrap">多 {position.quantity}</div><div className="mt-1 text-[9px] text-muted-foreground">名義 ${position.notional}</div><div className="mt-1 text-[10px] text-emerald-400">{position.pnl}</div></td>
        <td className="px-2 py-3 font-mono"><div>${position.entry}</div><div className="mt-1 text-[10px] text-muted-foreground">${position.mark}</div></td>
        <td className="px-2 py-3 font-mono">
          <span className={cn('px-1 py-0.2 rounded text-[10px] font-bold', fund >= 0 ? 'bg-emerald-400/10 text-emerald-400' : 'bg-rose-400/10 text-rose-400')}>
            {fund >= 0 ? '+' : ''}{(fund * 100).toFixed(4)}%
          </span>
          <div className="mt-1 text-[9px] text-muted-foreground">8H 結算</div>
        </td>
        <td className="px-2 py-3 font-mono"><div>${position.liquidation}</div><div className="mt-1 text-[10px] text-emerald-400">{position.distance}</div></td>
        <td className="px-2 py-3"><div className="font-mono text-[11px] text-primary">{position.confirmed ? '保護價' : '更新目標'} ${position.stop}</div>
          <button type="button" aria-label={`${position.bot} 保護確認詳情`} aria-expanded={expanded === position.bot} onClick={() => setExpanded(expanded === position.bot ? null : position.bot)} className={cn('mt-1 rounded border px-1.5 py-0.5 text-left text-[10px]', position.confirmed ? 'border-emerald-400/25 bg-emerald-400/5 text-emerald-400' : 'border-amber-400/30 bg-amber-400/10 text-amber-400')}>{position.confirmation} {expanded === position.bot ? '▴' : '▾'}</button>
          {expanded === position.bot && <div className="mt-2 max-w-[340px] space-y-2 text-[10px] leading-relaxed"><p className="text-muted-foreground">{position.detail}</p><p className={position.confirmed ? 'text-muted-foreground' : 'text-amber-400'}>{position.next}</p></div>}
        </td>
        <td className="px-2 py-3 text-[10px]"><div className="whitespace-nowrap">{position.leverage}</div><div className="mt-1 text-[9px] text-muted-foreground">Net Mode</div></td>
      </tr>
      );
    })}</tbody>
  </table>;
}
