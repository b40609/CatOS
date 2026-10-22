import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState, useMemo } from "react";
import {
  Zap,
  ArrowUpRight,
  ShieldAlert,
  Layers,
  BarChart3,
  TrendingUp,
  Info,
  Search,
} from "lucide-react";
import { AppShell, PageHead, Panel } from "@/components/catos/shell";
import { PulseBeacon } from "@/components/catos/pulse-beacon";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/market-intel")({
  head: () => ({
    meta: [
      { title: "市場情報 (Market Intel) — catOS Quant Terminal" },
      { name: "description", content: "catOS 市場情報：Yaozi 哨兵情報流、OKX/幣安資金費率套利與多空情緒矩陣。" },
    ],
  }),
  component: MarketIntelPage,
});

interface YaoziAlert {
  id: string;
  symbol: string;
  title: string;
  time: string;
  summary: string;
  tag: string;
  tagLabel: string;
  severity: "high" | "medium" | "low";
  trigger: string;
  impact: string;
  actionGuide: string;
}

const YAOZI_ALERTS: YaoziAlert[] = [
  {
    id: "alert-01",
    symbol: "BTC-USDT-SWAP",
    title: "OKX 永續大額多頭清算告警",
    time: "10:14:02 UTC",
    summary: "過去 5 分鐘內 BTC-USDT 合約爆倉金額達 4.82M USDT，短線下探 63,800 支撐位，基差迅速收窄。",
    tag: "LIQUIDATION",
    tagLabel: "清算爆倉",
    severity: "high",
    trigger: "5 分鐘內單向爆倉額度 > 3,000,000 USDT",
    impact: "短線多單流動性踩踏，盤口滑價可能擴大至 5~10 bps",
    actionGuide: "維持策略續抱，嚴守 OKX 交易所端 P6 災難停損防線，禁止手動搶反彈加倉。",
  },
  {
    id: "alert-02",
    symbol: "SOL-USDT-SWAP",
    title: "資金費率顯著偏離 (OKX vs Binance)",
    time: "09:48:30 UTC",
    summary: "SOL-USDT 永續 8H 資金費率出現偏離，OKX +0.038% vs Binance +0.012%，基差年化達 28.5%，套利窗口開啟。",
    tag: "FUNDING_ARB",
    tagLabel: "費率套利",
    severity: "medium",
    trigger: "跨所 8H 資金費率偏離基差 > 0.020% (年化 > 20%)",
    impact: "多頭過度擁擠於 OKX，次根結算可能引發部分多頭平倉壓制價格",
    actionGuide: "可作為反轉訊號輔助權重，但策略核心決策仍依據 Closed Bar 訊號，不盲目跨所對沖。",
  },
  {
    id: "alert-03",
    symbol: "BTC-USDT-SWAP",
    title: "巨鯨鏈上大額轉移至交易所",
    time: "08:22:15 UTC",
    summary: "監測到 1,450 枚 BTC 自冷錢包轉入 OKX 充幣地址，鏈上確認數 3/3，現貨盤口拋壓可能增加。",
    tag: "WHALE_FLOW",
    tagLabel: "巨鯨異動",
    severity: "low",
    trigger: "單筆鏈上充幣至交易所 > 1,000 BTC 且確認數 >= 3",
    impact: "潛在現貨賣壓儲備，深度回踩時考驗 63,500 密集籌碼區",
    actionGuide: "密切監控唐奇安通道下軌防線，若收盤跌破則觸發策略市價平倉退出。",
  },
];

interface FundingRateRow {
  symbol: string;
  okxRate: string;
  binanceRate: string;
  basis: string;
  apr: string;
  signal: "套利機會" | "強烈訊號" | "空頭擠壓" | "平衡";
  settleCountdown: string;
  okx8hCostPer10k: string;
}

const FUNDING_RATES: FundingRateRow[] = [
  { symbol: "BTC-USDT-SWAP", okxRate: "+0.0100%", binanceRate: "+0.0098%", basis: "+0.0002%", apr: "0.22%", signal: "平衡", settleCountdown: "03:42:15", okx8hCostPer10k: "1.00 USDT" },
  { symbol: "ETH-USDT-SWAP", okxRate: "+0.0150%", binanceRate: "+0.0110%", basis: "+0.0040%", apr: "4.38%", signal: "套利機會", settleCountdown: "03:42:15", okx8hCostPer10k: "1.50 USDT" },
  { symbol: "SOL-USDT-SWAP", okxRate: "+0.0380%", binanceRate: "+0.0120%", basis: "+0.0260%", apr: "28.47%", signal: "強烈訊號", settleCountdown: "03:42:15", okx8hCostPer10k: "3.80 USDT" },
  { symbol: "DOGE-USDT-SWAP", okxRate: "-0.0050%", binanceRate: "+0.0020%", basis: "-0.0070%", apr: "7.66%", signal: "空頭擠壓", settleCountdown: "03:42:15", okx8hCostPer10k: "-0.50 USDT" },
];

interface RadarMetric {
  symbol: string;
  momentumScore: number; // 0-100
  momentumLabel: string;
  volatilityState: string;
  flow24hUsdt: string;
  flowDirection: "inflow" | "outflow";
  dexAnomaly: string;
}

const RADAR_METRICS: RadarMetric[] = [
  { symbol: "BTC-USDT-SWAP", momentumScore: 68, momentumLabel: "多頭動能延續", volatilityState: "中度擴散 (ATR 2.4%)", flow24hUsdt: "+14.8M", flowDirection: "inflow", dexAnomaly: "無異常" },
  { symbol: "ETH-USDT-SWAP", momentumScore: 52, momentumLabel: "箱型整理區間", volatilityState: "低波壓縮 (ATR 1.8%)", flow24hUsdt: "-3.2M", flowDirection: "outflow", dexAnomaly: "Uniswap V3 大額滑價" },
  { symbol: "SOL-USDT-SWAP", momentumScore: 74, momentumLabel: "強勢突破上軌", volatilityState: "高波發動 (ATR 4.2%)", flow24hUsdt: "+22.5M", flowDirection: "inflow", dexAnomaly: "Raydium 爆量" },
];

function MarketIntelPage() {
  const [dbState, setDbState] = useState<"checking" | "unavailable" | "connected">("checking");
  const [dbReason, setDbReason] = useState<string>("market_intel_not_found");
  const [alertFilter, setAlertFilter] = useState<string>("ALL");
  const [fundingFilter, setFundingFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedAlert, setSelectedAlert] = useState<YaoziAlert | null>(null);
  const [selectedFunding, setSelectedFunding] = useState<FundingRateRow | null>(null);

  // Probe backend local Yaozi market intel reader
  useEffect(() => {
    let active = true;
    const probe = async () => {
      try {
        const res = await fetch("/intel/today");
        if (!active) return;
        if (res.ok) {
          setDbState("connected");
        } else {
          setDbState("unavailable");
          try {
            const data = await res.json();
            if (data?.detail?.reason) {
              setDbReason(data.detail.reason);
            }
          } catch {
            // Keep default
          }
        }
      } catch {
        if (!active) return;
        setDbState("unavailable");
      }
    };
    probe();
    return () => {
      active = false;
    };
  }, []);

  const filteredAlerts = useMemo(() => {
    return YAOZI_ALERTS.filter((a) => {
      const matchFilter = alertFilter === "ALL" || a.tag === alertFilter;
      const matchSearch =
        !searchQuery ||
        a.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.summary.toLowerCase().includes(searchQuery.toLowerCase());
      return matchFilter && matchSearch;
    });
  }, [alertFilter, searchQuery]);

  const filteredFundingRates = useMemo(() => {
    return FUNDING_RATES.filter((f) => {
      const matchFilter = fundingFilter === "ALL" || f.signal === fundingFilter;
      const matchSearch =
        !searchQuery ||
        f.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
        f.signal.toLowerCase().includes(searchQuery.toLowerCase());
      return matchFilter && matchSearch;
    });
  }, [fundingFilter, searchQuery]);

  return (
    <AppShell>
      <PageHead
        code="ECOSYSTEM // MARKET INTEL"
        title="市場情報與 Yaozi 哨兵"
        desc="多市場情報流 · 資金費率跨所套利基差 · 獨立情報源交付"
        right={
          <div className="flex items-center gap-2">
            {dbState === "connected" ? (
              <span className="flex items-center gap-1.5 text-[11px] font-mono text-up bg-up/10 border border-up/25 rounded px-2 py-0.5">
                <PulseBeacon size={4} variant="up" />
                <span>YAOZI DB CONNECTED</span>
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-[11px] font-mono text-muted-foreground bg-secondary/80 border border-border/80 rounded px-2 py-0.5">
                <PulseBeacon size={4} />
                <span>示範情報模式 ({dbReason})</span>
              </span>
            )}
          </div>
        }
      />

      <div className="space-y-3">
        {/* ==================== 頂部整合政策與資料邊界橫幅 (Scheme B 滿版純淨視野) ==================== */}
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/80 bg-surface/90 px-3.5 py-2 text-xs font-mono shadow-xs backdrop-blur-md">
          <div className="flex items-center gap-2.5">
            <Zap className="size-3.5 text-primary shrink-0" />
            <span className="text-muted-foreground">
              架構職責: <strong className="text-foreground">獨立 Yaozi 情報源 · 整合至同一 Localhost 分頁交付</strong>
            </span>
            <span className="text-border">|</span>
            <span className="text-muted-foreground">
              切換分頁不控制策略生命週期
            </span>
          </div>
          <div className="flex items-center gap-2 text-[10.5px]">
            <span className="rounded bg-primary/10 border border-primary/20 px-2 py-0.5 text-primary font-semibold">
              展示資料 · 本地情境模擬
            </span>
            <span className="text-muted-foreground hidden sm:inline">
              (真實交易請待 market_intel.sqlite 採集掛載)
            </span>
          </div>
        </div>

        {/* ==================== Yaozi 即時哨兵情報卡片清單 ==================== */}
        <Panel
          title={
            <div className="flex items-center gap-2">
              <ShieldAlert className="size-3.5 text-primary" />
              <span>Yaozi 哨兵異象告警 (Sentinel Alerts)</span>
            </div>
          }
          meta={
            <div className="flex items-center gap-1.5">
              {(["ALL", "LIQUIDATION", "FUNDING_ARB", "WHALE_FLOW"] as const).map((tag) => {
                const label =
                  tag === "ALL"
                    ? `全部 (${YAOZI_ALERTS.length})`
                    : tag === "LIQUIDATION"
                    ? "清算爆倉"
                    : tag === "FUNDING_ARB"
                    ? "費率套利"
                    : "巨鯨異動";
                return (
                  <button
                    key={tag}
                    onClick={() => setAlertFilter(tag)}
                    className={cn(
                      "px-2 py-0.5 rounded text-[10.5px] font-mono transition-colors",
                      alertFilter === tag
                        ? "bg-primary text-primary-foreground font-semibold"
                        : "bg-secondary/60 text-muted-foreground hover:bg-secondary hover:text-foreground"
                    )}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          }
        >
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {filteredAlerts.map((alert) => (
              <div
                key={alert.id}
                onClick={() => setSelectedAlert(alert)}
                className="rounded-xl border border-border/80 bg-surface/90 p-3.5 shadow-xs backdrop-blur-md flex flex-col justify-between hover:border-primary/50 cursor-pointer transition-all hover:bg-secondary/20"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={cn(
                          "text-[9.5px] font-mono font-semibold px-1.5 py-0.5 rounded",
                          alert.severity === "high"
                            ? "bg-down/15 text-down border border-down/30"
                            : alert.severity === "medium"
                            ? "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                            : "bg-secondary text-muted-foreground"
                        )}
                      >
                        {alert.tagLabel}
                      </span>
                      <span className="font-mono text-[10px] text-primary font-medium">{alert.symbol}</span>
                    </div>
                    <span className="font-mono text-[10px] text-muted-foreground">{alert.time}</span>
                  </div>
                  <h3 className="mt-2 text-xs font-semibold text-foreground tracking-tight">{alert.title}</h3>
                  <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed line-clamp-2">{alert.summary}</p>
                </div>
                <div className="mt-3 pt-2.5 border-t border-border/40 flex items-center justify-between text-[10px] font-mono text-muted-foreground">
                  <span>來源：Yaozi Sentinel</span>
                  <span className="text-primary font-medium flex items-center group-hover:underline">
                    點擊查看處置指引 <ArrowUpRight className="size-3 ml-0.5" />
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Panel>

        {/* ==================== 跨所資金費率套利監測矩陣 ==================== */}
        <Panel
          title={
            <div className="flex items-center gap-2">
              <TrendingUp className="size-3.5 text-primary" />
              <span>資金費率偏離與跨所套利監測 (Funding Rate Matrix · 8H 結算)</span>
            </div>
          }
          meta={
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1">
                {(["ALL", "套利機會", "強烈訊號", "空頭擠壓", "平衡"] as const).map((sig) => (
                  <button
                    key={sig}
                    onClick={() => setFundingFilter(sig)}
                    className={cn(
                      "px-2 py-0.5 rounded text-[10px] font-mono transition-colors",
                      fundingFilter === sig
                        ? "bg-primary text-primary-foreground font-semibold"
                        : "bg-secondary/60 text-muted-foreground hover:bg-secondary hover:text-foreground"
                    )}
                  >
                    {sig === "ALL" ? "全部" : sig}
                  </button>
                ))}
              </div>
              <div className="relative">
                <Search className="size-3 absolute left-2 top-1.5 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="搜尋合約..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-6 w-28 rounded bg-background/80 pl-6 pr-2 font-mono text-[10px] text-foreground border border-border/60 focus:outline-none focus:border-primary"
                />
              </div>
            </div>
          }
        >
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead className="border-b border-border text-[10px] font-mono text-muted-foreground bg-background/30">
                <tr>
                  <th className="py-2 px-3 font-normal">標的合約</th>
                  <th className="py-2 px-3 text-right font-normal">OKX 8H 費率</th>
                  <th className="py-2 px-3 text-right font-normal">Binance 8H 費率</th>
                  <th className="py-2 px-3 text-right font-normal">偏離基差 (Basis)</th>
                  <th className="py-2 px-3 text-right font-normal">年化 APR</th>
                  <th className="py-2 px-3 text-right font-normal">每萬 USDT 成本</th>
                  <th className="py-2 px-3 text-right font-normal">下期結算倒數</th>
                  <th className="py-2 px-3 text-right font-normal">訊號狀態</th>
                  <th className="py-2 px-3 text-center font-normal">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40 font-mono">
                {filteredFundingRates.map((row) => (
                  <tr
                    key={row.symbol}
                    onClick={() => setSelectedFunding(row)}
                    className="hover:bg-secondary/30 transition-colors cursor-pointer"
                  >
                    <td className="py-2.5 px-3 font-medium text-foreground">{row.symbol}</td>
                    <td className="py-2.5 px-3 text-right text-muted-foreground">{row.okxRate}</td>
                    <td className="py-2.5 px-3 text-right text-muted-foreground">{row.binanceRate}</td>
                    <td className="py-2.5 px-3 text-right font-semibold text-primary">{row.basis}</td>
                    <td className="py-2.5 px-3 text-right text-foreground font-bold">{row.apr}</td>
                    <td className="py-2.5 px-3 text-right text-muted-foreground">{row.okx8hCostPer10k}</td>
                    <td className="py-2.5 px-3 text-right text-muted-foreground">{row.settleCountdown}</td>
                    <td className="py-2.5 px-3 text-right">
                      <span
                        className={cn(
                          "rounded px-1.5 py-0.5 text-[9px] font-semibold",
                          row.signal === "強烈訊號"
                            ? "bg-primary/20 text-primary border border-primary/40"
                            : row.signal === "套利機會"
                            ? "bg-emerald-500/15 text-emerald-400"
                            : row.signal === "空頭擠壓"
                            ? "bg-down/15 text-down"
                            : "text-muted-foreground"
                        )}
                      >
                        {row.signal}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <span className="text-[10px] text-primary hover:underline">詳情</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        {/* ==================== Yaozi Sentinel 多維情報曲面預覽 ==================== */}
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {/* 左欄：多維決策曲面與動能雷達 */}
          <Panel
            title={
              <div className="flex items-center gap-2">
                <BarChart3 className="size-3.5 text-primary" />
                <span>多維標的決策曲面 (Decision Surface · 示範)</span>
              </div>
            }
            meta={<span className="text-[10px] font-mono text-muted-foreground">/intel/decision-surface</span>}
          >
            <div className="space-y-2.5">
              {RADAR_METRICS.map((item) => (
                <div
                  key={item.symbol}
                  className="rounded-lg border border-border/60 bg-background/40 p-2.5 flex items-center justify-between text-xs"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-foreground">{item.symbol}</span>
                      <span className="rounded bg-secondary px-1.5 py-0.2 text-[9px] font-mono text-primary">
                        {item.momentumLabel}
                      </span>
                    </div>
                    <p className="font-mono text-[10px] text-muted-foreground">
                      波動狀態: {item.volatilityState} · DEX 異象: {item.dexAnomaly}
                    </p>
                  </div>
                  <div className="text-right font-mono">
                    <span className="text-sm font-bold text-primary">{item.momentumScore}</span>
                    <span className="text-[10px] text-muted-foreground"> / 100</span>
                    <p className={cn("text-[10px] font-semibold", item.flowDirection === "inflow" ? "text-up" : "text-down")}>
                      24H {item.flow24hUsdt}
                    </p>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 pt-2 border-t border-border/40 text-[10px] font-mono text-muted-foreground flex items-center justify-between">
              <span>契約邊界: 僅作為輔助情報流，非自動交易觸發依據</span>
              <span className="text-primary">本地 DB 就緒時自動切換</span>
            </div>
          </Panel>

          {/* 右欄：大戶籌碼與鏈上異象 */}
          <Panel
            title={
              <div className="flex items-center gap-2">
                <Layers className="size-3.5 text-primary" />
                <span>資金流向與大戶籌碼 (Capital Flow & Dealer Activity)</span>
              </div>
            }
            meta={<span className="text-[10px] font-mono text-muted-foreground">/intel/raw-flow</span>}
          >
            <div className="space-y-3 text-xs">
              <div className="rounded-lg border border-border/60 bg-background/40 p-3 space-y-2">
                <div className="flex items-center justify-between font-mono">
                  <span className="text-muted-foreground">OKX SWAP 24H 大額訂單淨買入</span>
                  <span className="font-bold text-up">+42.6M USDT</span>
                </div>
                <div className="h-2 w-full bg-secondary rounded-full overflow-hidden flex">
                  <div className="bg-up h-full" style={{ width: "68%" }} title="主動買盤 68%" />
                  <div className="bg-down h-full" style={{ width: "32%" }} title="主動賣盤 32%" />
                </div>
                <div className="flex justify-between text-[10px] font-mono text-muted-foreground">
                  <span>主動買單 68%</span>
                  <span>主動賣單 32%</span>
                </div>
              </div>

              <div className="rounded-lg border border-border/60 bg-background/40 p-3 space-y-1.5 font-mono text-[11px]">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">交易所冷錢包淨流出:</span>
                  <span className="text-foreground font-semibold">-2,180 BTC (流動性收緊)</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">未平倉合約 (OI) 變化:</span>
                  <span className="text-up font-semibold">+4.8% (資金積極進場)</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">合約與現貨基差 (Basis):</span>
                  <span className="text-primary font-semibold">+18.50 USDT (升水區間)</span>
                </div>
              </div>
            </div>

            <div className="mt-3 pt-2 border-t border-border/40 text-[10px] font-mono text-muted-foreground flex items-center justify-between">
              <span>儲存格式: SQLite (WAL) · 唯讀訪存</span>
              <span className="text-primary">嚴禁 Float 計算</span>
            </div>
          </Panel>
        </div>
      </div>

      {/* ==================== 告警詳情與處置指引彈窗 ==================== */}
      {selectedAlert && (
        <Dialog open={!!selectedAlert} onOpenChange={(open) => !open && setSelectedAlert(null)}>
          <DialogContent className="border-border bg-surface max-w-lg">
            <DialogHeader>
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "text-[10px] font-mono font-semibold px-2 py-0.5 rounded",
                    selectedAlert.severity === "high"
                      ? "bg-down/15 text-down border border-down/30"
                      : "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                  )}
                >
                  {selectedAlert.tagLabel}
                </span>
                <span className="font-mono text-xs text-primary font-bold">{selectedAlert.symbol}</span>
                <span className="ml-auto font-mono text-[11px] text-muted-foreground">{selectedAlert.time}</span>
              </div>
              <DialogTitle className="text-sm font-bold text-foreground mt-2">
                {selectedAlert.title}
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground">
                事件 ID: {selectedAlert.id} · 來源: Yaozi Sentinel (示範情報流)
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 py-2 text-xs">
              <div className="rounded-lg border border-border/60 bg-background/50 p-3 space-y-1">
                <span className="font-semibold text-foreground text-[11px]">情報摘要</span>
                <p className="text-muted-foreground leading-relaxed">{selectedAlert.summary}</p>
              </div>

              <div className="space-y-2 font-mono text-[11px]">
                <div className="flex justify-between border-b border-border/40 pb-1.5">
                  <span className="text-muted-foreground">偵測觸發條件:</span>
                  <span className="text-foreground">{selectedAlert.trigger}</span>
                </div>
                <div className="flex justify-between border-b border-border/40 pb-1.5">
                  <span className="text-muted-foreground">盤口衝擊評估:</span>
                  <span className="text-amber-400">{selectedAlert.impact}</span>
                </div>
              </div>

              <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 space-y-1">
                <span className="font-semibold text-primary text-[11px] flex items-center gap-1.5">
                  <Info className="size-3.5" /> 策略與交易員處置指引
                </span>
                <p className="text-muted-foreground text-xs leading-relaxed">{selectedAlert.actionGuide}</p>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedAlert(null)}
                className="h-8 text-xs font-mono"
              >
                關閉面板
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* ==================== 資金費率跨所基差計算彈窗 ==================== */}
      {selectedFunding && (
        <Dialog open={!!selectedFunding} onOpenChange={(open) => !open && setSelectedFunding(null)}>
          <DialogContent className="border-border bg-surface max-w-md">
            <DialogHeader>
              <DialogTitle className="text-sm font-bold text-foreground flex items-center gap-2">
                <span>{selectedFunding.symbol}</span>
                <span className="text-xs text-primary font-normal">8H 資金費率跨所套利試算</span>
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground">
                OKX 永續 SWAP vs Binance 永續合約基差
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 py-2 text-xs font-mono">
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded border border-border/60 bg-background/50 p-2.5 text-center">
                  <span className="text-[10px] text-muted-foreground block">OKX 8H 費率</span>
                  <span className="text-sm font-bold text-foreground mt-0.5 block">{selectedFunding.okxRate}</span>
                </div>
                <div className="rounded border border-border/60 bg-background/50 p-2.5 text-center">
                  <span className="text-[10px] text-muted-foreground block">Binance 8H 費率</span>
                  <span className="text-sm font-bold text-muted-foreground mt-0.5 block">{selectedFunding.binanceRate}</span>
                </div>
              </div>

              <div className="rounded border border-primary/30 bg-primary/5 p-3 space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">偏離基差 (Basis):</span>
                  <span className="font-bold text-primary">{selectedFunding.basis}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">理論年化收益 (APR):</span>
                  <span className="font-bold text-foreground">{selectedFunding.apr}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">每 10,000 USDT 持倉成本:</span>
                  <span className="font-bold text-foreground">{selectedFunding.okx8hCostPer10k}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">下期結算倒數:</span>
                  <span className="text-foreground">{selectedFunding.settleCountdown}</span>
                </div>
              </div>

              <p className="text-[10px] text-muted-foreground leading-relaxed">
                ※ 資金費率結算週期為 00:00 / 08:00 / 16:00 UTC。CatOS 策略以 Closed Bar 決策為主，跨所費率基差僅作為市場情緒與動態持倉成本參考，不進行未授權之自動雙邊對沖套利。
              </p>
            </div>

            <div className="pt-2 flex justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedFunding(null)}
                className="h-8 text-xs font-mono"
              >
                關閉
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </AppShell>
  );
}
