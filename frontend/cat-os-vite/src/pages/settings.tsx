import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { ShieldCheck, Database, Check, Terminal } from "lucide-react";
import { AppShell, PageHead, Panel } from "@/components/catos/shell";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "系統設定 (Settings) — catOS Quant Terminal" },
      { name: "description", content: "catOS 系統設定：OKX KOL 專用子帳戶約束、本機執行底座與介面個人化。" },
    ],
  }),
  component: SettingsPage,
});

function SettingsPage() {
  const [copied, setCopied] = useState(false);

  const handleCopyTag = () => {
    navigator.clipboard.writeText("41cb53c54d6dABDE");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <AppShell>
      <PageHead
        code="SYSTEM // SETTINGS"
        title="系統設定與執行約束"
        desc="OKX 專用子帳戶合約安全 · 本機 Localhost 執行邊界 · 介面偏好"
      />

      <div className="space-y-4">
        {/* ==================== 1. OKX KOL 交易員專用約束 ==================== */}
        <Panel
          title="OKX 交易所與專用子帳戶約束 (Broker Invariants)"
          meta={<span className="rounded bg-primary/10 border border-primary/20 px-2 py-0.5 text-[10px] font-mono text-primary">STRICT INVARIANTS</span>}
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-border/60 bg-background/40 p-3.5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-foreground">OKX 官方合作返佣 Tag</span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleCopyTag}
                  className="h-6 text-[10px] font-mono border-border bg-surface hover:bg-surface-raised"
                >
                  {copied ? <Check className="size-3 mr-1 text-up" /> : null}
                  {copied ? "已複製" : "複製 Tag"}
                </Button>
              </div>
              <p className="font-mono text-sm font-bold text-primary tracking-wider">
                "tag": "41cb53c54d6dABDE"
              </p>
              <p className="text-[11px] text-muted-foreground">
                由 Supervisor 強制注入所有 OKX SWAP 委託（含平倉與緊急通道），Worker 與策略不得修改或省略。
              </p>
            </div>

            <div className="rounded-lg border border-border/60 bg-background/40 p-3.5 space-y-2">
              <span className="text-xs font-semibold text-foreground">保證金與部位模式</span>
              <p className="font-mono text-sm font-bold text-foreground">
                cross (全倉) + net_mode (單向淨持倉)
              </p>
              <p className="text-[11px] text-muted-foreground">
                金額、價格、部位與保證金全面採用 Python Decimal 與 SQLite TEXT，禁止使用 float 浮點運算。
              </p>
            </div>
          </div>
        </Panel>

        {/* ==================== 2. 本機底座架構約束 ==================== */}
        <Panel
          title="本機專用執行底座架構 (Localhost Invariants)"
          meta={<span className="text-[10px] font-mono text-muted-foreground">Localhost Only</span>}
        >
          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between border-b border-border/50 pb-2">
              <div className="flex items-center gap-2">
                <Terminal className="size-4 text-primary" />
                <span className="font-medium text-foreground">後端與儲存核心</span>
              </div>
              <span className="font-mono text-muted-foreground">Python 3.11+ · SQLite (WAL 模式)</span>
            </div>

            <div className="flex items-center justify-between border-b border-border/50 pb-2">
              <div className="flex items-center gap-2">
                <ShieldCheck className="size-4 text-up" />
                <span className="font-medium text-foreground">嚴格禁止外部依賴</span>
              </div>
              <span className="font-mono text-muted-foreground">禁止 Docker · 禁止 PostgreSQL · 禁止 Redis</span>
            </div>

            <div className="flex items-center justify-between border-b border-border/50 pb-2">
              <div className="flex items-center gap-2">
                <Database className="size-4 text-primary" />
                <span className="font-medium text-foreground">FastAPI 監聽範圍</span>
              </div>
              <span className="font-mono text-muted-foreground">僅綁定 127.0.0.1 本機回送位址</span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="size-4 text-amber-400" />
                <span className="font-medium text-foreground">風控權益基準</span>
              </div>
              <span className="font-mono text-muted-foreground">有效槓桿上限 3.0x · 單幣預算上限 50%</span>
            </div>
          </div>
        </Panel>

        {/* ==================== 3. 介面個人化與縮放 ==================== */}
        <Panel title="介面外觀與數據密度 (Visual Density)">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-foreground">主題設計規範</p>
                <p className="text-[11px] text-muted-foreground">黑曜石與香檳金 (Noir & Gold) 高階量化專用</p>
              </div>
              <span className="rounded bg-secondary px-2.5 py-1 text-xs font-mono font-medium text-primary border border-border">
                Noir & Gold (Active)
              </span>
            </div>

            <div className="flex items-center justify-between border-t border-border/50 pt-3">
              <div>
                <p className="text-xs font-semibold text-foreground">卡片縮放與換位引擎</p>
                <p className="text-[11px] text-muted-foreground">120 FPS 影格節流 · 60:40 舒展四分割</p>
              </div>
              <span className="rounded bg-secondary px-2.5 py-1 text-xs font-mono font-medium text-foreground border border-border">
                120 FPS Engine (Enabled)
              </span>
            </div>
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}
