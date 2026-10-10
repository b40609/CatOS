import { createFileRoute } from "@tanstack/react-router";
import { Pause, Play, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { AppShell, PageHead, Panel } from "@/components/catos/shell";
import { logSeeds, nextLog, type LogLevel, type LogLine } from "@/lib/mock/data";
import { PulseBeacon } from "@/components/catos/pulse-beacon";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/logs")({
  head: () => ({
    meta: [
      { title: "系統日誌 — catOS" },
      {
        name: "description",
        content: "catOS 終端機風格系統日誌串流：INFO／WARN／ERROR／TRADE 等級篩選、關鍵字搜尋與即時追加。",
      },
      { property: "og:title", content: "系統日誌 — catOS" },
      {
        property: "og:description",
        content: "即時監看交易引擎與機器人的系統事件串流。",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: LogsPage,
});

const LEVEL_STYLE: Record<LogLevel, string> = {
  INFO: "text-info border-info/40",
  WARN: "text-warn border-warn/40",
  ERROR: "text-down border-down/40",
  TRADE: "text-gold-bright border-gold/50",
};

const FILTERS: (LogLevel | "ALL")[] = ["ALL", "INFO", "WARN", "ERROR", "TRADE"];

function LogsPage() {
  const [logs, setLogs] = useState<LogLine[]>(logSeeds);
  const [filter, setFilter] = useState<LogLevel | "ALL">("ALL");
  const [query, setQuery] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const bodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t = setInterval(() => {
      setLogs((prev) => {
        const added = [...prev, nextLog()];
        return added.length > 240 ? added.slice(added.length - 240) : added;
      });
    }, 2200);
    return () => clearInterval(t);
  }, []);

  const visible = useMemo(
    () =>
      logs.filter(
        (l) =>
          (filter === "ALL" || l.level === filter) &&
          (!query ||
            l.message.toLowerCase().includes(query.toLowerCase()) ||
            l.source.toLowerCase().includes(query.toLowerCase())),
      ),
    [logs, filter, query],
  );

  useEffect(() => {
    if (autoScroll && bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [visible, autoScroll]);

  return (
    <AppShell>
      <PageHead
        code="syslog // stream"
        title="系統日誌"
        desc="交易所行情、永續合約成交與風控事件的模擬串流。"
        right={
          <button
            type="button"
            onClick={() => setAutoScroll((v) => !v)}
            className={cn(
              "flex items-center gap-2 border px-3 py-1.5 font-mono text-[0.7rem] uppercase tracking-[0.12em] transition-colors",
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
        title="live stream"
        meta={
          <div className="flex items-center gap-2">
            <PulseBeacon size={5} />
            <span className="label-xs">{visible.length} lines</span>
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
                "border px-2.5 py-1 font-mono text-[0.65rem] tracking-[0.14em] transition-colors",
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
              placeholder="search logs..."
              className="w-44 bg-transparent font-mono text-[0.7rem] text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
            />
          </label>
        </div>

        <div
          ref={bodyRef}
          className="scanlines h-[34rem] overflow-y-auto border border-border bg-background/60 p-3"
        >
          <div className="font-mono text-[0.72rem] leading-relaxed">
            {visible.map((l) => (
              <div key={l.id} className="slide-in-row flex items-baseline gap-3 py-px">
                <span className="shrink-0 text-muted-foreground/70">{l.time}</span>
                <span
                  className={cn(
                    "shrink-0 border px-1.5 text-[0.6rem] tracking-[0.14em]",
                    LEVEL_STYLE[l.level],
                  )}
                >
                  {l.level}
                </span>
                <span className="shrink-0 text-gold-dim">[{l.source}]</span>
                <span className="text-foreground/85">{l.message}</span>
              </div>
            ))}
            {visible.length === 0 && (
              <p className="py-8 text-center text-muted-foreground">
                no matching log lines
              </p>
            )}
          </div>
        </div>
      </Panel>
    </AppShell>
  );
}
