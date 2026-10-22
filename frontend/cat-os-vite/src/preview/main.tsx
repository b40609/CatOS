/// <reference types="vite/client" />
import { useEffect } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { AuthProvider } from '@/lib/auth';
import { RouterProvider, useRouter } from '@/lib/router';
import { AppShell } from '@/components/catos/shell';
import { WorkspaceGrid } from '@/components/catos/workspace-grid';
import { AccountEquityBand } from '@/components/catos/account-equity-band';
import { V0BotTable } from '@/components/catos/v0-bot-table';
import { ActivityPanel } from '@/components/catos/activity-panel';
import { AllocationDonutCard } from '@/components/catos/allocation-donut-card';
import { UnifiedIncidentActivityCard } from '@/components/catos/unified-incident-activity-card';
import { IncidentTimelineCard } from '@/components/catos/incident-timeline-card';
import { MarketWatchCard } from '@/components/catos/market-watch-card';
import { StrategyIntentsRadarCard } from '@/components/catos/strategy-intents-radar-card';
import { LayoutModeToolbar } from '@/components/catos/layout-mode-toolbar';
import { CardHeaderTitle } from '@/components/catos/card-header-title';
import { PulseBeacon } from '@/components/catos/pulse-beacon';
import { ArrowDownLeft, ArrowUpRight, AlertCircle, ArrowLeft } from 'lucide-react';
import { cryptoMarkets, type Fill } from '@/lib/mock/data';
import { recentFills } from '@/lib/mock/terminal';
import { fmtMoney, fmtSigned, nowStamp, useLiveFeed } from '@/hooks/use-live';
import { useI18n } from '@/lib/i18n';
import { cn } from '@/lib/utils';
import { SharedInspectorSheet } from './shared-inspector-sheet';
import { stateAdapter } from '@/state/stateAdapter';
import type { CardId } from '@/state/layoutStore';
import '../styles/globals.css';

function makeFill(): Fill {
  const market = cryptoMarkets[Math.floor(Math.random() * cryptoMarkets.length)] ?? cryptoMarkets[0];
  return {
    id: crypto.randomUUID(),
    time: nowStamp(),
    symbol: `${market.code}-USDT-SWAP`,
    side: Math.random() > 0.5 ? 'BUY' : 'SELL',
    qty: Number((Math.random() * 2 + 0.1).toFixed(2)),
    price: market.price,
    pnl: Number(((Math.random() - 0.3) * 800).toFixed(2)),
  };
}

function PreviewDashboard() {
  const { path, navigate } = useRouter();
  const [fills] = useLiveFeed<Fill>(recentFills, makeFill, 6500, 5);
  const { t } = useI18n();

  useEffect(() => {
    void stateAdapter.init('normal');
  }, []);

  // 完整卡片工廠函數：100% 支援 8890 全部 9 大卡片庫，同時將增量整合注入原卡！
  const renderCard = (cardId: CardId) => {
    switch (cardId) {
      case 'equity':
        return <AccountEquityBand className="h-full" />;

      case 'bots':
        return <V0BotTable className="h-full" isIntegratedPreview />;

      case 'allocation':
        return <AllocationDonutCard className="h-full" />;

      case 'positions':
        return <ActivityPanel className="h-full" isIntegratedPreview />;

      case 'activity_deck':
        return <UnifiedIncidentActivityCard className="h-full" />;

      case 'market_watch':
        return <MarketWatchCard className="h-full" />;

      case 'strategy_intents':
        return <StrategyIntentsRadarCard className="h-full" />;

      case 'incidents':
        return <IncidentTimelineCard className="h-full" />;

      case 'fills':
        return (
          <div className="flex flex-col h-full w-full select-none overflow-hidden bg-surface/40">
            <div className="flex items-center justify-between px-3 py-2 bg-secondary/50 border-b border-border/80 shrink-0">
              <CardHeaderTitle
                cardId="fills"
                title={t('recent_fills')}
                subtext={
                  <span className="flex items-center gap-1.5 text-[9px] text-up font-mono ml-1">
                    <PulseBeacon size={4.5} />
                    {t('live')}
                  </span>
                }
              />
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto p-2.5">
              <ul className="-mt-1">
                {fills.map((f) => (
                  <li key={f.id} className="slide-in-row flex items-center gap-2 border-b border-border/60 py-1.5 last:border-0">
                    <span className={cn('grid size-5 shrink-0 place-items-center rounded', f.side === 'BUY' ? 'bg-up/10 text-up' : 'bg-down/10 text-down')}>
                      {f.side === 'BUY' ? <ArrowDownLeft className="size-2.5" /> : <ArrowUpRight className="size-2.5" />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="num text-[10px] font-medium text-foreground leading-tight">{f.symbol} <span className={cn('text-[8.5px]', f.side === 'BUY' ? 'text-up' : 'text-down')}>{f.side === 'BUY' ? t('buy') : t('sell')}</span></p>
                      <p className="mt-0.5 num text-[8.5px] text-muted-foreground leading-tight">{f.qty} @ {fmtMoney(f.price, f.price < 1 ? 4 : 2)}</p>
                    </div>
                    <div className="ml-auto text-right">
                      <p className={cn('num text-[10px] font-medium leading-tight', f.pnl >= 0 ? 'text-up' : 'text-down')}>{fmtSigned(f.pnl)}</p>
                      <p className="mt-0.5 num text-[8.5px] text-muted-foreground leading-tight">{f.time}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  // 路由核對：若點擊了非 Dashboard 路由，明確告知目前預覽邊界
  const isDashboardRoute = path === '/' || path === '';

  return (
    <AppShell
      dashboardTools={
        <div className="flex items-center gap-2 shrink min-w-0">
          <LayoutModeToolbar />
        </div>
      }
    >
      {isDashboardRoute ? (
        <div className="h-full w-full relative min-w-0 overflow-x-hidden">
          <WorkspaceGrid renderCard={renderCard} />
          <SharedInspectorSheet />
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center p-12 text-center max-w-lg mx-auto my-12 border border-border/80 rounded-xl bg-surface/80 backdrop-blur-md">
          <div className="size-10 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 mb-3">
            <AlertCircle className="size-5" />
          </div>
          <h2 className="text-base font-bold text-foreground mb-1">
            未在本次預覽範圍內
          </h2>
          <p className="text-xs text-muted-foreground leading-relaxed mb-4 font-mono">
            目前 8887 預覽專注於「Dashboard 戰情總覽收斂整合」，包含 Bot 策略意圖、全域日誌異常追查與 P6 部位保護確認。
            子頁面路由 (<code>{path}</code>) 未在本次工作包中啟用。
          </p>
          <button
            type="button"
            onClick={() => navigate('/')}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-primary/40 bg-primary/10 text-primary hover:bg-primary/20 text-xs font-semibold cursor-pointer transition-colors"
          >
            <ArrowLeft className="size-3.5" />
            <span>返回戰情總覽 (Dashboard)</span>
          </button>
        </div>
      )}
    </AppShell>
  );
}

const root = (import.meta.hot?.data.root as Root | undefined) ?? createRoot(document.getElementById('root')!);
if (import.meta.hot) import.meta.hot.data.root = root;
root.render(
  <AuthProvider>
    <RouterProvider>
      <PreviewDashboard />
    </RouterProvider>
  </AuthProvider>
);
