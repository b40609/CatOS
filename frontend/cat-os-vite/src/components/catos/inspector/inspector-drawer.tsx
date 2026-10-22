import React, { useEffect } from 'react';
import {
  Bot,
  ShieldAlert,
  Scale,
  Zap,
  ChevronRight,
  ChevronLeft,
  X,
  Pin,
  ArrowRight,
  Maximize2,
  Minimize2,
} from 'lucide-react';
import { useInspectorStore } from '@/state/inspectorStore';
import { usePreviewStore } from '@/preview/preview-store';
import { cn } from '@/lib/utils';

export function InspectorDrawer() {
  const {
    isOpen,
    activeTab,
    selectedBotId,
    width,
    isPinned,
    toggleOpen,
    setOpen,
    setActiveTab,
    setWidth,
    togglePin,
    selectBot,
  } = useInspectorStore();

  const {
    bots,
    positions,
    jumpToOrder,
    jumpToProtection,
  } = usePreviewStore();

  const currentBot = bots.find((b) => b.id === selectedBotId) || bots[0];
  const btcPos = positions.find((p) => p.symbol.includes('BTC')) || positions[0];
  const ethPos = positions.find((p) => p.symbol.includes('ETH')) || positions[1];
  const solPos = positions.find((p) => p.symbol.includes('SOL')) || positions[2];

  // 鍵盤快捷鍵：Ctrl + B 開啟/關閉 Inspector，Ctrl + 1~4 切換分頁，Esc 關閉
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
        e.preventDefault();
        toggleOpen();
      } else if (e.key === 'Escape' && isOpen && !isPinned) {
        setOpen(false);
      } else if ((e.ctrlKey || e.metaKey) && isOpen) {
        if (e.key === '1') {
          e.preventDefault();
          setActiveTab('bot');
        } else if (e.key === '2') {
          e.preventDefault();
          setActiveTab('p6');
        } else if (e.key === '3') {
          e.preventDefault();
          setActiveTab('r1');
        } else if (e.key === '4') {
          e.preventDefault();
          setActiveTab('fill');
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isPinned, toggleOpen, setOpen, setActiveTab]);

  return (
    <aside className="relative flex shrink-0 select-none z-30 transition-all duration-200">
      {/* ==================== 1. 常駐 36px 垂直微型錨定條 (Inspector Rail) ==================== */}
      <div className="w-9 bg-surface/95 border-l border-border/80 flex flex-col items-center justify-between py-2 shrink-0 backdrop-blur-md">
        <div className="flex flex-col items-center gap-1.5 w-full">
          {/* Bot 審計圖示 */}
          <RailButton
            active={isOpen && activeTab === 'bot'}
            icon={<Bot className="size-4" />}
            label="策略意圖 (Ctrl+1)"
            badgeDot={currentBot.warning ? 'bg-amber-400' : 'bg-emerald-400'}
            onClick={() => {
              if (isOpen && activeTab === 'bot') toggleOpen();
              else setActiveTab('bot');
            }}
          />

          {/* P6 災難防線圖示 */}
          <RailButton
            active={isOpen && activeTab === 'p6'}
            icon={<ShieldAlert className="size-4" />}
            label="P6 災難防線 (Ctrl+2)"
            badgeDot="bg-amber-400"
            onClick={() => {
              if (isOpen && activeTab === 'p6') toggleOpen();
              else setActiveTab('p6');
            }}
          />

          {/* R1 風控審計圖示 */}
          <RailButton
            active={isOpen && activeTab === 'r1'}
            icon={<Scale className="size-4" />}
            label="R1 風控審計 (Ctrl+3)"
            onClick={() => {
              if (isOpen && activeTab === 'r1') toggleOpen();
              else setActiveTab('r1');
            }}
          />

          {/* 實時撮合剖析圖示 */}
          <RailButton
            active={isOpen && activeTab === 'fill'}
            icon={<Zap className="size-4" />}
            label="撮合剖析 (Ctrl+4)"
            onClick={() => {
              if (isOpen && activeTab === 'fill') toggleOpen();
              else setActiveTab('fill');
            }}
          />
        </div>

        {/* 底部展開 / 收合箭頭 */}
        <button
          type="button"
          onClick={toggleOpen}
          className="size-7 rounded flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-secondary/60 transition-colors cursor-pointer"
          title={isOpen ? '收合抽屜 (Ctrl+B)' : '展開抽屜 (Ctrl+B)'}
        >
          {isOpen ? <ChevronRight className="size-3.5" /> : <ChevronLeft className="size-3.5" />}
        </button>
      </div>

      {/* ==================== 2. 非模態推擠式檢驗抽屜本體 (Push Drawer) ==================== */}
      {isOpen && (
        <div
          style={{ width: `${width}px` }}
          className="h-full bg-surface/98 border-l border-border/80 flex flex-col min-w-0 shadow-2xl backdrop-blur-md animate-in slide-in-from-right-4 duration-150 overflow-hidden"
        >
          {/* 抽屜頂部 Header */}
          <div className="flex items-center justify-between px-3 py-2 bg-secondary/50 border-b border-border/80 shrink-0">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-mono font-bold uppercase text-primary bg-primary/15 border border-primary/30 px-1.5 py-0.2 rounded">
                INSPECTOR
              </span>
              <span className="text-xs font-bold text-foreground">
                {activeTab === 'bot' && '策略意圖與五階段鏈'}
                {activeTab === 'p6' && 'P6 災難停損防線審查'}
                {activeTab === 'r1' && 'R1 風控期間審計 (00:00)'}
                {activeTab === 'fill' && '撮合滑價與手續費剖析'}
              </span>
            </div>

            <div className="flex items-center gap-1">
              {/* 切換寬度 380 ↔ 480 */}
              <button
                type="button"
                onClick={() => setWidth(width === 380 ? 480 : 380)}
                className="size-6 rounded flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-secondary/70 transition-colors cursor-pointer"
                title={width === 380 ? '擴展寬度 (480px)' : '標準寬度 (380px)'}
              >
                {width === 380 ? <Maximize2 className="size-3" /> : <Minimize2 className="size-3" />}
              </button>

              {/* 釘選常駐 */}
              <button
                type="button"
                onClick={togglePin}
                className={cn(
                  'size-6 rounded flex items-center justify-center transition-colors cursor-pointer',
                  isPinned
                    ? 'text-primary bg-primary/15 border border-primary/30'
                    : 'text-muted-foreground hover:text-foreground hover:bg-secondary/70'
                )}
                title={isPinned ? '已釘選常駐' : '釘選常駐 (不隨點擊外部關閉)'}
              >
                <Pin className="size-3" />
              </button>

              {/* 關閉按鈕 */}
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="size-6 rounded flex items-center justify-center text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors cursor-pointer"
                title="收合抽屜 (Esc)"
              >
                <X className="size-3.5" />
              </button>
            </div>
          </div>

          {/* 抽屜二級分頁切換 Pills */}
          <div className="grid grid-cols-4 gap-1 p-1.5 bg-secondary/30 border-b border-border/60 shrink-0 text-[11px] font-mono">
            <button
              type="button"
              onClick={() => setActiveTab('bot')}
              className={cn(
                'py-1 px-1.5 rounded text-center transition-all cursor-pointer truncate',
                activeTab === 'bot'
                  ? 'bg-surface/90 text-primary font-bold border border-primary/40 shadow-2xs'
                  : 'text-muted-foreground hover:text-foreground hover:bg-surface/40'
              )}
            >
              🤖 Bot 意圖
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('p6')}
              className={cn(
                'py-1 px-1.5 rounded text-center transition-all cursor-pointer truncate',
                activeTab === 'p6'
                  ? 'bg-surface/90 text-primary font-bold border border-primary/40 shadow-2xs'
                  : 'text-muted-foreground hover:text-foreground hover:bg-surface/40'
              )}
            >
              🛡️ P6 防線
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('r1')}
              className={cn(
                'py-1 px-1.5 rounded text-center transition-all cursor-pointer truncate',
                activeTab === 'r1'
                  ? 'bg-surface/90 text-primary font-bold border border-primary/40 shadow-2xs'
                  : 'text-muted-foreground hover:text-foreground hover:bg-surface/40'
              )}
            >
              ⚖️ R1 風控
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('fill')}
              className={cn(
                'py-1 px-1.5 rounded text-center transition-all cursor-pointer truncate',
                activeTab === 'fill'
                  ? 'bg-surface/90 text-primary font-bold border border-primary/40 shadow-2xs'
                  : 'text-muted-foreground hover:text-foreground hover:bg-surface/40'
              )}
            >
              ⚡ 撮合
            </button>
          </div>

          {/* ==================== 抽屜內容區域 ==================== */}
          <div className="flex-1 min-h-0 overflow-y-auto p-3 text-xs font-mono space-y-3.5">
            {/* ==================== TAB 1: BOT 意圖與五階段鏈 ==================== */}
            {activeTab === 'bot' && (
              <>
                {/* Bot 選擇器 */}
                <div className="flex items-center gap-1 overflow-x-auto no-scrollbar pb-0.5">
                  {bots.map((b) => (
                    <button
                      key={b.id}
                      type="button"
                      onClick={() => selectBot(b.id)}
                      className={cn(
                        'flex items-center gap-1 px-2 py-1 rounded text-[10.5px] border transition-all cursor-pointer shrink-0',
                        b.id === currentBot.id
                          ? 'bg-primary/15 text-primary border-primary/50 font-bold'
                          : 'bg-secondary/40 text-muted-foreground border-border/60 hover:text-foreground'
                      )}
                    >
                      <span className={cn('size-1.5 rounded-full', b.warning ? 'bg-amber-400' : 'bg-emerald-400')} />
                      <span>{b.name}</span>
                    </button>
                  ))}
                </div>

                {/* 當前意圖摘要卡 */}
                <div
                  className={cn(
                    'p-3 rounded-lg border',
                    currentBot.warning ? 'bg-amber-500/10 border-amber-500/30 text-amber-200' : 'bg-secondary/40 border-border/80'
                  )}
                >
                  <div className="flex items-center justify-between text-[10px] text-muted-foreground uppercase mb-1">
                    <span>當前意圖摘要 · {currentBot.symbol}</span>
                    <span className="text-primary font-bold">{currentBot.timeframe}</span>
                  </div>
                  <div className="text-sm font-semibold text-foreground">
                    {currentBot.intentSummary}
                  </div>
                </div>

                {/* 五階段鏈 (Five-Stage Lifecycle Chain) */}
                <div className="p-3 rounded-lg border border-border/80 bg-background/50 space-y-2.5">
                  <span className="text-[10px] text-muted-foreground font-bold uppercase tracking-wider block">
                    五階段流程鏈 (Lifecycle Trace)
                  </span>
                  <div className="space-y-2 relative before:absolute before:left-2 before:top-2 before:bottom-2 before:w-[1.5px] before:bg-border/80">
                    {currentBot.stages.map(([title, desc], idx) => {
                      return (
                        <div key={title} className="flex items-start gap-3 relative pl-5">
                          <span
                            className={cn(
                              'absolute left-0.5 top-0.5 size-3 rounded-full border flex items-center justify-center bg-background',
                              idx === 4 && currentBot.warning
                                ? 'border-amber-400 text-amber-400'
                                : 'border-emerald-400 text-emerald-400'
                            )}
                          >
                            <span className="size-1 rounded-full bg-current" />
                          </span>
                          <div className="flex-1">
                            <span className="text-[11px] font-bold text-foreground block">
                              {idx + 1}. {title}
                            </span>
                            <span className="text-[10px] text-muted-foreground leading-tight block mt-0.5">
                              {desc}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* 判定依據與風控限制 */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 rounded bg-background/50 border border-border/60">
                    <span className="text-[10px] text-muted-foreground block">判定條件</span>
                    <span className="text-[11px] font-semibold text-foreground mt-0.5 block line-clamp-2">
                      {currentBot.condition}
                    </span>
                  </div>
                  <div className="p-2.5 rounded bg-background/50 border border-border/60">
                    <span className="text-[10px] text-muted-foreground block">風控限制</span>
                    <span className="text-[11px] font-semibold text-foreground mt-0.5 block line-clamp-2">
                      {currentBot.riskLimit}
                    </span>
                  </div>
                </div>

                {/* 雙向連動按鈕 */}
                <div className="flex items-center gap-2 pt-1">
                  {currentBot.relatedOrderId && (
                    <button
                      type="button"
                      onClick={() => jumpToOrder(currentBot.relatedOrderId!)}
                      className="flex-1 py-1.5 px-2 rounded border border-primary/40 bg-primary/10 hover:bg-primary/20 text-primary text-[11px] font-semibold flex items-center justify-center gap-1 transition-colors cursor-pointer"
                    >
                      <ArrowRight className="size-3" />
                      定位關聯掛單 ({currentBot.relatedOrderId})
                    </button>
                  )}
                  {currentBot.relatedPositionId && (
                    <button
                      type="button"
                      onClick={() => jumpToProtection(currentBot.relatedPositionId!)}
                      className="flex-1 py-1.5 px-2 rounded border border-border hover:border-primary/50 bg-secondary/50 text-foreground text-[11px] font-semibold flex items-center justify-center gap-1 transition-colors cursor-pointer"
                    >
                      查看對應持倉
                    </button>
                  )}
                </div>
              </>
            )}

            {/* ==================== TAB 2: P6 災難停損防線 ==================== */}
            {activeTab === 'p6' && (
              <>
                <div className="p-2.5 rounded-lg border border-primary/30 bg-primary/5 space-y-1">
                  <div className="flex items-center justify-between text-primary font-bold">
                    <span>OKX 交易所端整倉停損</span>
                    <span className="text-[10px] font-mono">觸發源: Mark 價格</span>
                  </div>
                  <p className="text-[10.5px] text-muted-foreground leading-relaxed">
                    災難停損係主機離線或斷網時最後保險。向上/向下依提早觸發方向取整（多倉 CEIL 向上、空倉 FLOOR 向下）。
                  </p>
                </div>

                {/* 3 幣種防線卡片 */}
                <div className="space-y-2">
                  {[btcPos, ethPos, solPos].filter(Boolean).map((pos) => {
                    const isConfirmed = pos.p6Status === 'CONFIRMED';
                    return (
                      <div
                        key={pos.id}
                        className={cn(
                          'p-3 rounded-lg border transition-all',
                          isConfirmed ? 'bg-secondary/40 border-border/80' : 'bg-amber-500/10 border-amber-500/40'
                        )}
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="font-bold text-foreground text-xs">{pos.symbol}</span>
                          <span
                            className={cn(
                              'px-1.5 py-0.2 rounded text-[9.5px] font-bold border',
                              isConfirmed
                                ? 'bg-emerald-400/15 text-emerald-400 border-emerald-400/30'
                                : 'bg-amber-400/15 text-amber-300 border-amber-400/30'
                            )}
                          >
                            {isConfirmed ? '✓ 已確認生效' : '⚠️ 待取得終態'}
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-[10.5px]">
                          <div>
                            <span className="text-muted-foreground block">生效停損價</span>
                            <span className="text-foreground font-bold">{pos.p6ActiveStopPrice}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground block">更新目標價</span>
                            <span className="text-foreground font-bold">{pos.p6TargetStopPrice}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground block">覆蓋保護數量</span>
                            <span className="text-foreground">{pos.p6CoveredQty}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground block">確認來源</span>
                            <span className="text-muted-foreground">{pos.p6Source}</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}

            {/* ==================== TAB 3: R1 風控審計 (00:00) ==================== */}
            {activeTab === 'r1' && (
              <>
                <div className="p-3 rounded-lg border border-border/80 bg-secondary/40 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground font-bold uppercase">台北日風控基準 (E0)</span>
                    <span className="text-primary font-bold text-xs">$12,500.00 USDT</span>
                  </div>
                  <div className="text-[10.5px] text-muted-foreground leading-tight">
                    Asia/Taipei 00:00 切日 · 當日首次合格帳戶觀測建立固定基準，同日不可刷新，鎖存起算時間：00:00:15。
                  </div>
                </div>

                {/* 門檻距離雙儀表 */}
                <div className="p-3 rounded-lg border border-border/80 bg-background/50 space-y-3">
                  <div>
                    <div className="flex items-center justify-between text-[11px] mb-1">
                      <span className="text-amber-300 font-semibold">Soft 門檻 (-10% / -$1,250.00)</span>
                      <span className="text-muted-foreground font-bold">緩衝剩餘 $822.50</span>
                    </div>
                    <div className="w-full h-1.5 bg-secondary rounded-full overflow-hidden">
                      <div className="h-full bg-amber-400 rounded-full" style={{ width: '34.2%' }} />
                    </div>
                    <span className="text-[9.5px] text-muted-foreground mt-1 block">
                      當日累計損失 3.42% · 觸及則禁止新增曝險 (Soft Latch)
                    </span>
                  </div>

                  <div className="pt-2 border-t border-border/60">
                    <div className="flex items-center justify-between text-[11px] mb-1">
                      <span className="text-red-400 font-semibold">Hard 門檻 (-20% / -$2,500.00)</span>
                      <span className="text-muted-foreground font-bold">緩衝剩餘 $2,072.50</span>
                    </div>
                    <div className="w-full h-1.5 bg-secondary rounded-full overflow-hidden">
                      <div className="h-full bg-red-400 rounded-full" style={{ width: '17.1%' }} />
                    </div>
                    <span className="text-[9.5px] text-muted-foreground mt-1 block">
                      觸及則啟動緊急市價清倉並觸發 Kill-Switch 永久鎖存
                    </span>
                  </div>
                </div>

                <div className="p-2.5 rounded bg-background/50 border border-border/60 text-[10.5px] space-y-1">
                  <div className="text-muted-foreground">排除非策略外部流：<strong className="text-foreground">0.00 USDT</strong></div>
                  <div className="text-muted-foreground">風控鎖存狀態：<strong className="text-emerald-400">NORMAL (未鎖存)</strong></div>
                </div>
              </>
            )}

            {/* ==================== TAB 4: 撮合剖析 ==================== */}
            {activeTab === 'fill' && (
              <>
                <div className="p-2.5 rounded-lg border border-border/80 bg-secondary/40 text-[10.5px] space-y-1">
                  <div className="flex items-center justify-between text-foreground font-bold">
                    <span>OKX SWAP 撮合分析</span>
                    <span className="text-primary font-mono">net_mode · cross</span>
                  </div>
                  <p className="text-muted-foreground leading-tight">
                    後端 Supervisor 獨佔發單出口，注入專屬交易標籤，撮合結果直接持久化至 SQLite WAL。
                  </p>
                </div>

                <div className="space-y-2">
                  <div className="p-3 rounded-lg border border-border/80 bg-background/50 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-foreground">BTC-USDT-SWAP 平倉</span>
                      <span className="text-up font-bold">+$142.50</span>
                    </div>
                    <div className="grid grid-cols-2 gap-1 text-[10.5px] text-muted-foreground">
                      <span>成交價格: $63,420.50</span>
                      <span>數量: 0.05 BTC</span>
                      <span>滑價偏離: <strong className="text-emerald-400">+0.02% (極低)</strong></span>
                      <span>手續費: -0.63 USDT</span>
                    </div>
                  </div>

                  <div className="p-3 rounded-lg border border-border/80 bg-background/50 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-foreground">ETH-USDT-SWAP 開多</span>
                      <span className="text-muted-foreground">成交回報</span>
                    </div>
                    <div className="grid grid-cols-2 gap-1 text-[10.5px] text-muted-foreground">
                      <span>成交價格: $3,450.20</span>
                      <span>數量: 1.2 ETH</span>
                      <span>滑價偏離: <strong className="text-emerald-400">0.00%</strong></span>
                      <span>手續費: -1.04 USDT</span>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}

function RailButton({
  active,
  icon,
  label,
  badgeDot,
  onClick,
}: {
  active: boolean;
  icon: React.ReactNode;
  label: string;
  badgeDot?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'relative size-7 rounded flex items-center justify-center transition-all cursor-pointer group',
        active
          ? 'bg-primary/20 text-primary border border-primary/50 shadow-2xs'
          : 'text-muted-foreground hover:text-foreground hover:bg-secondary/60'
      )}
      title={label}
    >
      {icon}
      {badgeDot && (
        <span
          className={cn(
            'absolute top-1 right-1 size-1.5 rounded-full ring-1 ring-background',
            badgeDot
          )}
        />
      )}
    </button>
  );
}
