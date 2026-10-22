import { Fragment, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface BotMonitorRow {
  id: string;
  name: string;
  contract: string;
  strategy: string;
  position: string;
  pnl: string;
  summary: string;
  status: string;
  phase: string;
  warning?: boolean;
  paused?: boolean;
  bar: string;
  target: string;
  condition: string;
  stages: [string, string][];
  next: string;
}

export interface BotMonitoringView {
  mode: 'summary' | 'details';
  rows: BotMonitorRow[];
}

export function BotMonitorTable({ mode, rows }: BotMonitoringView) {
  const [expanded, setExpanded] = useState<string | null>(null);
  return <div className="flex min-h-0 flex-1 flex-col">
    <div className="min-h-0 flex-1 overflow-auto">
      <table className="w-full border-collapse text-left text-[11px]">
        <thead className="sticky top-0 z-10 border-b border-border/80 bg-surface font-mono text-[9.5px] text-muted-foreground">
          <tr><th className="py-2 pl-3 font-medium">BOT / STRATEGY</th><th className="px-2 font-medium">部位 / 未實現損益</th>
            <th className="px-2 font-medium">執行狀態</th><th className="pr-3 text-right font-medium">詳情</th></tr>
        </thead>
        <tbody>{rows.map(row => <Fragment key={row.id}>
          <tr className={cn('border-b border-border/40 hover:bg-secondary/40', expanded === row.id && 'bg-secondary/50')}>
            <td className="py-2 pl-3 pr-1">
              <div className="flex items-center gap-2"><span className={cn('size-1.5 shrink-0 rounded-full', row.paused ? 'bg-muted-foreground' : row.warning ? 'bg-amber-400' : 'bg-emerald-400')} /><b className="text-[12px]">{row.name}</b></div>
              <div className="mt-1 font-mono text-[9px] text-primary">{row.contract}</div><div className="font-mono text-[9px] text-muted-foreground">{row.strategy}</div>
            </td>
            <td className="px-2 py-2 font-mono"><div className="whitespace-nowrap font-semibold">{row.position}</div><div className={cn('mt-1 text-[10px]', row.paused ? 'text-muted-foreground' : 'text-emerald-400')}>{row.pnl}</div></td>
            <td className="px-2 py-2"><span className={cn('whitespace-nowrap rounded border px-1.5 py-0.5 text-[10px]', row.warning ? 'border-amber-400/30 bg-amber-400/10 text-amber-400' : 'border-border bg-background/50 text-muted-foreground')}>{row.status}</span><div className="mt-1.5 text-[9px] text-muted-foreground">{row.phase}</div></td>
            <td className="pr-3 text-right"><button type="button" aria-label={`${row.name} 意圖詳情`} aria-expanded={expanded === row.id} aria-controls={`intent-${row.id}`} onClick={() => setExpanded(expanded === row.id ? null : row.id)} className="inline-flex items-center gap-1 rounded border border-border bg-background/60 px-1.5 py-1 text-[10px] text-muted-foreground hover:text-primary">{expanded === row.id ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}{expanded === row.id ? '收合' : '展開'}</button></td>
          </tr>
          {mode === 'summary' && <tr className="border-b border-border/60"><td colSpan={4} className="bg-secondary/20 px-3 py-1.5"><div data-intent-summary={row.id} className="text-[11px] leading-relaxed"><span className="mr-2 text-[9px] text-muted-foreground">意圖</span>{row.summary}</div></td></tr>}
          {expanded === row.id && <tr id={`intent-${row.id}`}><td colSpan={4} className="border-b border-border bg-background/50 px-3 py-3">
            <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1"><b className="text-primary">{row.name} · {row.summary}</b><span className="font-mono text-[10px] text-muted-foreground">{row.bar} · UTC+8</span></div>
            <p className="text-[11px]">目前 {row.position} → 目標 {row.target}</p><p className="mt-1 text-[10px] text-muted-foreground">條件：{row.condition}</p>
            <div className="my-3 grid grid-cols-5 gap-1">{row.stages.map(([label, value], index) => <div key={label} className="rounded border border-border/70 bg-secondary/30 px-2 py-1.5"><div className="text-[9px] text-muted-foreground">{index + 1}. {label}</div><div className={cn('mt-1 text-[10px]', row.warning && index >= 2 ? 'text-amber-400' : 'text-foreground')}>{value}</div></div>)}</div>
            <p className={cn('text-[10px] leading-relaxed', row.warning ? 'text-amber-400' : 'text-muted-foreground')}>{row.next}</p>
          </td></tr>}
        </Fragment>)}</tbody>
      </table>
    </div>
    <div className="shrink-0 border-t border-border/80 bg-secondary/70 px-3 py-1 font-mono text-[9px] text-muted-foreground">最後快照 11:15:00 · 已收盤 K 線意圖 · 點「展開」查看資料 → 意圖 → 風控 → 委託 → 對帳</div>
  </div>;
}
