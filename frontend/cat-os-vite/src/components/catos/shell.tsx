import { Link, useRouterState } from "@tanstack/react-router";
import { AccountMenu } from "@/components/catos/account-menu";
import { Activity, Bot, LayoutDashboard, ScrollText, ShieldCheck, FlaskConical, SlidersHorizontal, ScanLine, Globe2, Settings2, PanelLeftClose, PanelLeftOpen, Cat, type LucideIcon } from "lucide-react";
import { useState, useEffect, useRef, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n";
import { PulseBeacon } from "@/components/catos/pulse-beacon";
import { ModeSelector } from "@/components/catos/mode-selector";
import { CardManagerDropdown } from "@/components/catos/card-manager-dropdown";
import { cn } from "@/lib/utils";


interface NavigationItem {
  to: string;
  name: string;
  sub: string;
  icon: LucideIcon;
  hasPulse?: boolean;
}

interface NavigationGroup {
  key: string;
  titleZh: string;
  titleEn: string;
  titleMono: string;
  items: NavigationItem[];
}

const GROUPS: NavigationGroup[] = [
  {
    key: "overview",
    titleZh: "系統總覽",
    titleEn: "OVERVIEW",
    titleMono: "OVERVIEW",
    items: [
      { to: "/", name: "系統總覽", sub: "DASHBOARD", icon: LayoutDashboard },
    ],
  },
  {
    key: "strategy",
    titleZh: "策略與研究",
    titleEn: "STRATEGY & RESEARCH",
    titleMono: "STRATEGY",
    items: [
      { to: "/strategies", name: "策略中心", sub: "STRATEGY HUB", icon: Activity },
      { to: "/backtest", name: "歷史回測", sub: "BACKTESTING", icon: FlaskConical },
      { to: "/optimization", name: "參數優化", sub: "OPTIMIZATION", icon: SlidersHorizontal },
      { to: "/review", name: "策略覆盤", sub: "STRATEGY REVIEW", icon: ScanLine },
    ],
  },
  {
    key: "execution",
    titleZh: "執行與風控",
    titleEn: "EXECUTION & RISK",
    titleMono: "EXECUTION",
    items: [
      { to: "/bots", name: "機器人管理", sub: "BOT MANAGER", icon: Bot, hasPulse: true },
      { to: "/risk", name: "風控中心", sub: "RISK CONTROL", icon: ShieldCheck },
    ],
  },
  {
    key: "system",
    titleZh: "生態與系統",
    titleEn: "ECOSYSTEM & SYSTEM",
    titleMono: "SYSTEM",
    items: [
      { to: "/market-intel", name: "市場情報", sub: "MARKET INTEL", icon: Globe2 },
      { to: "/logs", name: "系統日誌", sub: "SYSTEM LOGS", icon: ScrollText },
      { to: "/settings", name: "系統設定", sub: "SETTINGS", icon: Settings2 },
    ],
  },
];

import {
  useSidebarStore,
  MIN_SIDEBAR_WIDTH,
  MAX_SIDEBAR_WIDTH,
  COLLAPSE_THRESHOLD,
  EXPAND_THRESHOLD,
} from "@/state/sidebarStore";

export function AppShell({ children }: { children: ReactNode }) {
  const {
    collapsed,
    sidebarWidth,
    setCollapsed,
    setSidebarWidth,
    resetSidebarWidth,
    toggleCollapsed,
  } = useSidebarStore();

  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const current = GROUPS.flatMap((g) => g.items).find((n) => n.to === pathname);
  const { t, language } = useI18n();

  const [isResizing, setIsResizing] = useState(false);

  // 使用 Refs 杜絕閉包陳舊問題，確保拖曳過程中有精確的段落感吸附與切換
  const collapsedRef = useRef(collapsed);
  collapsedRef.current = collapsed;
  const sidebarWidthRef = useRef(sidebarWidth);
  sidebarWidthRef.current = sidebarWidth;

  const handleResizerPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsResizing(true);
    const startX = e.clientX;
    const startW = collapsedRef.current ? 64 : sidebarWidthRef.current;

    const onPointerMove = (moveEvent: PointerEvent) => {
      const deltaX = moveEvent.clientX - startX;
      const rawTarget = startW + deltaX;

      // 1. 若當前為折疊（只有分頁圖案，64px）狀態
      if (collapsedRef.current) {
        // 向右拉動超過展開閥值 145px 時，段落感彈開恢復為展開側邊欄
        if (rawTarget > EXPAND_THRESHOLD) {
          collapsedRef.current = false;
          setCollapsed(false);
          const clamped = Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, rawTarget));
          setSidebarWidth(clamped);
        }
        return;
      }

      // 2. 若當前為展開狀態，向左拖曳縮小到閥值 135px 以下時，段落感吸附折疊為只有分頁圖案（64px）
      if (rawTarget < COLLAPSE_THRESHOLD) {
        collapsedRef.current = true;
        setCollapsed(true);
        return;
      }

      // 3. 正常寬度調整區間（190px ~ 420px）
      collapsedRef.current = false;
      setCollapsed(false);
      const clamped = Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, rawTarget));
      setSidebarWidth(clamped);
    };

    const onPointerUp = () => {
      setIsResizing(false);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointercancel", onPointerUp);
    };

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerUp);
  };

  const handleResizerDblClick = () => {
    collapsedRef.current = false;
    resetSidebarWidth();
  };

  // 拖曳調整期間鎖定全域光標與反白，杜絕閃爍
  useEffect(() => {
    if (isResizing) {
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    } else {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
    return () => {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isResizing]);

  // Global Ctrl+B shortcut to toggle sidebar collapse
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
        const target = e.target as HTMLElement | null;
        if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
          return;
        }
        e.preventDefault();
        toggleCollapsed();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggleCollapsed]);

  return (
    <div className="min-h-screen bg-background text-foreground antialiased selection:bg-primary/20 selection:text-primary">
      <aside
        style={{ width: collapsed ? 64 : sidebarWidth }}
        className={cn(
          "fixed inset-y-0 left-0 z-30 flex flex-col border-r border-border bg-sidebar select-none",
          !isResizing && "transition-all duration-200"
        )}
      >
        {/* Resizable Sidebar Splitter Sash (VS Code / Bloomberg / TradingView Pro) */}
        <div
          className={cn(
            "sidebar-resizer absolute top-0 -right-[5px] bottom-0 w-[10px] cursor-col-resize z-40 flex items-center justify-center select-none touch-none group",
            isResizing && "is-resizing"
          )}
          onPointerDown={handleResizerPointerDown}
          onDoubleClick={handleResizerDblClick}
          title={collapsed ? "雙擊或向右拖移展開側邊欄" : "拖移調整寬度 · 雙擊重設 (245px)"}
          role="separator"
          aria-orientation="vertical"
        >
          <div
            className={cn(
              "resizer-line absolute inset-y-0 left-[4px] w-[2px] transition-colors pointer-events-none",
              isResizing ? "bg-primary shadow-[0_0_8px_var(--color-primary)]/60" : "bg-transparent group-hover:bg-primary/70"
            )}
          />
        </div>

        {/* 頂部 Logo：展開時右側自然融合微型呼吸燈與版本號，乾淨俐落 */}
        <Link
          to="/"
          className={cn(
            "flex h-14 shrink-0 items-center transition-all",
            collapsed ? "justify-center px-0" : "gap-2.5 px-3.5"
          )}
          title="CatOS Dashboard"
        >
          <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground shadow-[0_0_12px_var(--color-primary)]/40">
            <Cat className="size-5" strokeWidth={2} />
          </span>
          {!collapsed && (
            <div className="flex items-center justify-between flex-1 min-w-0">
              <span className="text-lg font-semibold tracking-tight">
                catOS<span className="ml-0.5 text-primary">.</span>
              </span>
              <span className="font-mono text-[10px] text-muted-foreground/60">
                v2.0
              </span>
            </div>
          )}
        </Link>

        {/* 導覽選單（單行高密度、支援方案 A/B/C 標題與微型 Badge） */}
        <nav aria-label="Main navigation" className="min-h-0 flex-1 space-y-2 overflow-y-auto overflow-x-hidden px-2 pb-2 pt-1">
          {GROUPS.map((group) => (
            <div key={group.key} className="space-y-0.5">
              {!collapsed && (
                <p className="mb-1 mt-2.5 px-2.5 font-mono text-[9.5px] font-semibold uppercase tracking-wider text-muted-foreground/60 truncate">
                  {group.titleMono}
                </p>
              )}
              <div className="space-y-0.5">
                {group.items.map(({ to, name, sub, icon: Icon, hasPulse }) => (
                  <Link
                    key={to}
                    to={to}
                    title={`${language === "en" ? sub : name} (${language === "en" ? name : sub})`}
                    activeOptions={{ exact: to === "/" }}
                    activeProps={{ className: "bg-secondary text-foreground [&_svg]:text-primary font-medium shadow-xs" }}
                    inactiveProps={{ className: "text-muted-foreground hover:bg-secondary/60 hover:text-foreground" }}
                    className={cn(
                      "relative transition-all",
                      collapsed
                        ? "flex size-10 items-center justify-center mx-auto rounded-md group my-1"
                        : "flex min-h-[46px] items-center gap-3 rounded-md px-3 py-1.5"
                    )}
                  >
                    <span className="relative flex size-5 shrink-0 items-center justify-center">
                      <Icon className="size-4 shrink-0 transition-transform group-hover:scale-110" strokeWidth={1.8} />
                      {hasPulse && (
                        <PulseBeacon
                          size={5}
                          className="absolute -top-[1.5px] -right-[1.5px]"
                          title="狀態正常運行中"
                        />
                      )}
                    </span>
                    {!collapsed && (
                      <div className="flex flex-col min-w-0 flex-1 leading-tight">
                        <span className="text-[13px] font-medium text-foreground tracking-wide truncate">
                          {language === "en" ? sub : name}
                        </span>
                        <span className="text-[9.5px] font-mono font-semibold text-muted-foreground uppercase tracking-wider truncate mt-0.5">
                          {language === "en" ? name : sub}
                        </span>
                      </div>
                    )}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* 側邊欄底座：移除生硬橫線，自然無縫融入 */}
        <div className="mt-auto shrink-0 pb-1.5">
          <AccountMenu isFolded={collapsed} />
        </div>
      </aside>

      <div
        style={{ paddingLeft: collapsed ? 64 : sidebarWidth }}
        className={cn(
          "min-w-0",
          !isResizing && "transition-all duration-200"
        )}
      >
        {/* Breathing Room Top Navigation Header (z-40 確保頂部彈窗高於工作區分割條 z-20) */}
        <header className="sticky top-0 z-40 flex h-11 items-center justify-between border-b border-border bg-background/95 px-3 backdrop-blur lg:px-5 gap-2">
          <div className="flex items-center gap-2.5 shrink-0">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleCollapsed}
              title={collapsed ? "展開側邊欄 (Ctrl+B)" : "收合側邊欄 (Ctrl+B)"}
              aria-label={collapsed ? "展開側邊欄" : "收合側邊欄"}
              className="size-7 text-muted-foreground hover:bg-secondary hover:text-foreground"
            >
              {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
            </Button>

            {/* Breadcrumbs: Dim Workspace / Bright Active Page */}
            <div className="flex items-center gap-1.5 text-xs">
              <span className="hidden text-muted-foreground/75 sm:inline">{t("workspace_trail")}</span>
              <span className="hidden text-muted-foreground/40 sm:inline">/</span>
              <span className="font-medium text-foreground">{language === "en" ? (current?.sub ?? "Dashboard") : (current?.name ?? "系統總覽")}</span>
            </div>
          </div>

          {/* 右側：工作台卡片庫與核心交易模式切換 */}
          <div className="flex items-center gap-2 shrink-0">
            {current?.to === "/" && <CardManagerDropdown />}
            <ModeSelector />
            <span className="flex items-center gap-1.5 text-[11px] font-mono text-muted-foreground hidden sm:flex">
              <PulseBeacon size={4} variant="up" /> Engine online
            </span>
          </div>
        </header>

        <main className="w-full p-3 lg:p-4">{children}</main>

        {/* 頁面底座 Grounded Footer */}
        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-4 py-2 text-[10px] text-muted-foreground lg:px-6">
          <div className="flex items-center gap-2">
            <PulseBeacon size={4.5} />
            <span>Binance <span className="num font-medium text-foreground/80">18ms</span></span>
            <span className="mx-1 text-border">|</span>
            <span>OKX <span className="num font-medium text-foreground/80">24ms</span></span>
          </div>
          <div>catOS Terminal · {t("simulated_data")}</div>
        </footer>
      </div>
    </div>
  );
}

export function PageHead({
  title,
  code,
  desc,
  right,
}: {
  title: string;
  code: string;
  desc: string;
  dateText?: string;
  onExport?: () => void;
  isExported?: boolean;
  right?: ReactNode;
}) {
  return (
    <div className="mb-2 flex items-center justify-between gap-2 rounded border border-border/60 bg-secondary/20 px-2.5 py-1 backdrop-blur-xs text-xs">
      <div className="flex items-center gap-2 min-w-0">
        <span className="font-mono text-[9px] font-bold uppercase tracking-wider text-primary bg-primary/10 border border-primary/25 rounded px-1.5 py-0.2 shrink-0">
          {code}
        </span>
        <span className="font-semibold text-foreground tracking-tight text-xs truncate">
          {title}
        </span>
        {desc && (
          <span className="text-[10px] text-muted-foreground/75 hidden md:inline truncate">
            · {desc}
          </span>
        )}
      </div>
      {right && <div className="flex items-center gap-1.5 shrink-0">{right}</div>}
    </div>
  );
}

export function Panel({ title, meta, className, children }: { title: ReactNode; meta?: ReactNode; className?: string; children: ReactNode }) {
  return (
    <section className={cn("panel flex min-w-0 flex-col overflow-hidden", className)}>
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-3.5 py-2 shrink-0 bg-secondary/50">
        <div className="flex items-center gap-2">
          <h2 className="text-xs font-semibold text-foreground tracking-tight">{title}</h2>
        </div>
        {meta}
      </header>
      <div className="min-w-0 flex-1 p-3 flex flex-col overflow-hidden">{children}</div>
    </section>
  );
}

