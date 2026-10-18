import { createFileRoute } from "@tanstack/react-router";
import { Zap, ArrowUpRight } from "lucide-react";
import { AppShell, PageHead, Panel } from "@/components/catos/shell";
import { PulseBeacon } from "@/components/catos/pulse-beacon";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/market-intel")({
  head: () => ({
    meta: [
      { title: "市場情報 (Market Intel) — catOS Quant Terminal" },
      { name: "description", content: "catOS 市場情報：Yaozi 情報流、OKX/幣安資金費率套利與多空情緒矩陣。" },
    ],
  }),
  component: MarketIntelPage,
});

interface YaoziAlert {
  id: string;
  title: string;
  time: string;
  summary: string;
  tag: string;
  severity: "high" | "medium" | "low";
}

const YAOZI_ALERTS: YaoziAlert[] = [
  {
    id: "alert-01",
    title: "OKX 永續大額多頭清算告警",
    time: "10:14:02",
    summary: "過去 5 分鐘內 BTC-USDT 合約爆倉金額達 4.82M USDT，短線下探 63,800 支撐位，基差迅速收窄。",
    tag: "LIQUIDATION",
    severity: "high",
  },
  {
    id: "alert-02",
    title: "資金費率顯著偏離 (OKX vs Binance)",
    time: "09:48:30",
    summary: "SOL-USDT 永續 8H 資金費率出現偏離，OKX +0.038% vs Binance +0.012%，基差年化達 28.5%，套利窗口開啟。",
    tag: "FUNDING_ARB",
    severity: "medium",
  },
  {
    id: "alert-03",
    title: "巨鯨鏈上大額轉移至交易所",
    time: "08:22:15",
    summary: "監測到 1,450 枚 BTC 自冷錢包轉入 OKX 充幣地址，鏈上確認數 3/3，現貨盤口拋壓可能增加。",
    tag: "WHALE_FLOW",
    severity: "low",
  },
];

const FUNDING_RATES = [
  { symbol: "BTC-USDT-SWAP", okxRate: "+0.0100%", binanceRate: "+0.0098%", basis: "+0.0002%", apr: "0.22%", signal: "平衡" },
  { symbol: "ETH-USDT-SWAP", okxRate: "+0.0150%", binanceRate: "+0.0110%", basis: "+0.0040%", apr: "4.38%", signal: "套利機會" },
  { symbol: "SOL-USDT-SWAP", okxRate: "+0.0380%", binanceRate: "+0.0120%", basis: "+0.0260%", apr: "28.47%", signal: "強烈訊號" },
  { symbol: "DOGE-USDT-SWAP", okxRate: "-0.0050%", binanceRate: "+0.0020%", basis: "-0.0070%", apr: "7.66%", signal: "空頭擠壓" },
];

function MarketIntelPage() {
  return (
    <AppShell>
      <PageHead
        code="ECOSYSTEM // MARKET INTEL"
        title="市場情報與 Yaozi 哨兵"
        desc="多市場情報流 · 資金費率跨所套利基差 · 獨立情報源交付"
        right={
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 text-[11px] font-mono text-primary bg-primary/10 border border-primary/25 rounded px-2 py-0.5">
              <PulseBeacon size={4} />
              <span>YAOZI STREAM LIVE</span>
            </span>
          </div>
        }
      />

      <div className="space-y-4">
        {/* 頂部整合政策提醒橫幅 */}
        <div className="rounded-xl border border-primary/30 bg-primary/5 p-3 text-xs text-foreground/90 backdrop-blur-md flex items-center gap-2.5">
          <Zap className="size-4 text-primary shrink-0" />
          <span>
            <strong>架構整合約定</strong>：市場情報為獨立情報模組，整合至同一 localhost 分頁交付，切換頁面不控制策略生命週期，不干擾 Supervisor 交易風控。
          </span>
        </div>

        {/* ==================== Yaozi 即時情報卡片清單 ==================== */}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {YAOZI_ALERTS.map((alert) => (
            <div
              key={alert.id}
              className="rounded-xl border border-border/80 bg-surface/90 p-4 shadow-xs backdrop-blur-md flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className={cn(
                    "text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded",
                    alert.severity === "high" ? "bg-down/15 text-down border border-down/30" :
                    alert.severity === "medium" ? "bg-amber-500/15 text-amber-400 border border-amber-500/30" :
                    "bg-secondary text-muted-foreground"
                  )}>
                    {alert.tag}
                  </span>
                  <span className="font-mono text-[10px] text-muted-foreground">{alert.time}</span>
                </div>
                <h3 className="mt-2 text-xs font-semibold text-foreground tracking-tight">{alert.title}</h3>
                <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed">{alert.summary}</p>
              </div>
              <div className="mt-3 pt-2.5 border-t border-border/40 flex items-center justify-between text-[10px] font-mono text-muted-foreground">
                <span>來源：Yaozi Sentinel</span>
                <span className="text-primary hover:underline cursor-pointer flex items-center">
                  詳情 <ArrowUpRight className="size-3 ml-0.5" />
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* ==================== 跨所資金費率套利監測矩陣 ==================== */}
        <Panel
          title="資金費率偏離與套利監測 (Funding Rate Matrix · 8H 結算)"
          meta={<span className="text-[10px] font-mono text-muted-foreground">OKX vs Binance</span>}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead className="border-b border-border text-[10px] font-mono text-muted-foreground bg-background/30">
                <tr>
                  <th className="py-2.5 px-3 font-normal">標的合約</th>
                  <th className="py-2.5 px-3 text-right font-normal">OKX 費率</th>
                  <th className="py-2.5 px-3 text-right font-normal">Binance 費率</th>
                  <th className="py-2.5 px-3 text-right font-normal">偏離基差</th>
                  <th className="py-2.5 px-3 text-right font-normal">年化 APR</th>
                  <th className="py-2.5 px-3 text-right font-normal">訊號狀態</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40 font-mono">
                {FUNDING_RATES.map((row) => (
                  <tr key={row.symbol} className="hover:bg-secondary/30 transition-colors">
                    <td className="py-2.5 px-3 font-medium text-foreground">{row.symbol}</td>
                    <td className="py-2.5 px-3 text-right text-muted-foreground">{row.okxRate}</td>
                    <td className="py-2.5 px-3 text-right text-muted-foreground">{row.binanceRate}</td>
                    <td className="py-2.5 px-3 text-right font-semibold text-primary">{row.basis}</td>
                    <td className="py-2.5 px-3 text-right text-foreground font-bold">{row.apr}</td>
                    <td className="py-2.5 px-3 text-right">
                      <span className={cn(
                        "rounded px-1.5 py-0.5 text-[9px] font-semibold",
                        row.signal === "強烈訊號" ? "bg-primary/20 text-primary border border-primary/40" :
                        row.signal === "套利機會" ? "bg-emerald-500/15 text-emerald-400" :
                        row.signal === "空頭擠壓" ? "bg-down/15 text-down" :
                        "text-muted-foreground"
                      )}>
                        {row.signal}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}
