import { createFileRoute } from "@tanstack/react-router";
import { Pause, Play, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { AppShell, PageHead, Panel } from "@/components/catos/shell";
import { PulseBeacon } from "@/components/catos/pulse-beacon";
import { eventTitle } from "@/components/catos/unified-incident-activity-card";
import { MAX_STORED_EVENTS, useCatStore } from "@/state/catStore";
import type { EventDTO, EventLevel } from "@/contracts";
import { formatClock, formatDateTime, shortId } from "@/lib/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/logs")({
  head: () => ({
    meta: [
      { title: "系統日誌 — catOS" },
      {
        name: "description",
        content: "catOS 系統日誌：本機模擬控制面事件流（run 狀態、訊號、成交、風控），可依等級篩選與關鍵字搜尋。",
      },
      { property: "og:title", content: "系統日誌 — catOS" },
      {
        property: "og:description",
        content: "監看本機模擬 Supervisor、Worker 與風控的控制面事件。",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: LogsPage,
});

type LogFilter = EventLevel | "TRADE" | "ALL";

const LEVEL_STYLE: Record<EventLevel, string> = {
  INFO: "text-info border-info/40",
  WARN: "text-warn border-warn/40",
  ERROR: "text-down border-down/40",
};
const TRADE_STYLE = "text-gold-bright border-gold/50";

const FILTERS: LogFilter[] = ["ALL", "INFO", "WARN", "ERROR", "TRADE"];

// TRADE = 成交類（category ORDER），其餘依 level 篩選
function matchesFilter(ev: EventDTO, filter: LogFilter): boolean {
  if (filter === "ALL") return true;
  if (filter === "TRADE") return ev.category === "ORDER";
  return ev.level === filter;
}

function LogsPage() {
  const events = useCatStore((s) => s.events);
  const eventsOmitted = useCatStore((s) => s.eventsOmitted);
  const bots = useCatStore((s) => s.bots);
  const connection = useCatStore((s) => s.connection);
  const [filter, setFilter] = useState<LogFilter>("ALL");
  const [query, setQuery] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const bodyRef = useRef<HTMLDivElement>(null);

  const instById = useMemo(() => {
    const map = new Map<string, string>();
    for (const bot of bots) if (bot.inst_id) map.set(bot.bot_id, bot.inst_id);
    return map;
  }, [bots]);

  // store 已依 seq 遞增排序；舊在上、新在下
  const lines = useMemo(
    () => events.map((ev) => ({ ev, title: eventTitle(ev, instById.get(ev.bot_id) ?? "合約") })),
    [events, instById],
  );

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return lines.filter(
      ({ ev, title }) =>
        matchesFilter(ev, filter) &&
        (!q ||
          title.toLowerCase().includes(q) ||
          ev.kind.toLowerCase().includes(q) ||
          ev.category.toLowerCase().includes(q) ||
          ev.run_id.toLowerCase().includes(q) ||
          ev.bot_id.toLowerCase().includes(q)),
    );
  }, [lines, filter, query]);

  useEffect(() => {
    if (autoScroll && bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [visible, autoScroll]);

  const emptyText =
    connection.status === "mode_not_open" ? "此模式未開放（demo/live 不在 v1 範圍）"
    : connection.status === "unavailable" ? `模擬服務不可用：${connection.detail ?? "unknown"}`
    : connection.status === "error" ? `無法連線：${connection.detail ?? "network_error"}`
    : "尚無事件 · 在實例監控頁啟動模擬 run 後顯示";

  return (
    <AppShell>
      <PageHead
        code="syslog // stream"
        title="系統日誌"
        desc="本機模擬控制面事件：run 狀態、訊號、成交與風控，依 seq 遞增"
        right={
          <button
            type="button"
            onClick={() => setAutoScroll((v) => !v)}
            className={cn(
              "flex items-center gap-2 border px-3 py-1.5 font-mono text-t3 uppercase tracking-[0.12em] transition-colors",
              autoScroll
                ? "border-gold/50 bg-accent text-gold-bright"
                : "border-border text-muted-foreground hover:bg-secondary/70",
            )}
          >
            {autoScroll ? <Pause className="size-3.5" /> : <Play className="size-3.5" />}
            auto-scroll {autoScroll ? "on" : "off"}
          </button>
        }
      />

      <Panel
        title="event stream"
        meta={
          <div className="flex items-center gap-2">
            <PulseBeacon size={5} variant={connection.status === "ok" ? "up" : "warn"} />
            <span className="label-xs" title={`前端最多保留最近 ${MAX_STORED_EVENTS} 筆`}>
              {visible.length} / {events.length} lines
            </span>
            {eventsOmitted > 0 && (
              <span className="font-mono text-t2 text-warn">後端緩衝已略過 {eventsOmitted} 筆</span>
            )}
          </div>
        }
      >
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {FILTERS.map((lv) => (
            <button
              key={lv}
              type="button"
              onClick={() => setFilter(lv)}
              className={cn(
                "border px-2.5 py-1 font-mono text-t2 tracking-[0.14em] transition-colors",
                filter === lv
                  ? "border-gold bg-accent text-gold-bright"
                  : "border-border text-muted-foreground hover:bg-secondary/70",
              )}
            >
              {lv}
            </button>
          ))}
          <label className="ml-auto flex items-center gap-2 border border-border px-2.5 py-1">
            <Search className="size-3.5 text-muted-foreground" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="search events..."
              className="w-44 bg-transparent font-mono text-t3 text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
            />
          </label>
        </div>

        <div
          ref={bodyRef}
          className="scanlines h-[34rem] overflow-y-auto border border-border bg-background/60 p-3"
        >
          <div className="font-mono text-t4 leading-relaxed">
            {visible.map(({ ev, title }) => {
              const trade = ev.category === "ORDER";
              return (
                <div
                  key={ev.seq}
                  className="slide-in-row flex items-baseline gap-3 py-px"
                  title={`seq ${ev.seq} · run ${ev.run_id} · ${ev.bot_id}${ev.synthetic_time_ms ? ` · 合成時間 ${formatDateTime(ev.synthetic_time_ms)}` : ""}`}
                >
                  <span className="shrink-0 text-muted-foreground/70">{formatClock(ev.wall_time_ms)}</span>
                  <span
                    className={cn(
                      "shrink-0 border px-1.5 text-t2 tracking-[0.14em]",
                      trade ? TRADE_STYLE : LEVEL_STYLE[ev.level],
                    )}
                  >
                    {trade ? "TRADE" : ev.level}
                  </span>
                  <span className="shrink-0 text-gold-dim">[{ev.category.toLowerCase()}]</span>
                  <span className="text-foreground/85">{title}</span>
                  <span className="ml-auto shrink-0 text-muted-foreground/50">
                    #{ev.seq} · {shortId(ev.run_id)}
                  </span>
                </div>
              );
            })}
            {visible.length === 0 && (
              <p className="py-8 text-center text-muted-foreground">
                {events.length === 0 ? emptyText : "沒有符合條件的事件"}
              </p>
            )}
          </div>
        </div>
      </Panel>
    </AppShell>
  );
}
