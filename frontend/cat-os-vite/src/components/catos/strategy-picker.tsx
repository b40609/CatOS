import type { ResearchStrategyMeta } from "@/adapters/research-api-adapter";
import { pickStrategy } from "@/lib/research-strategies";
import { cn } from "@/lib/utils";

/** 研究策略單選清單：catalog 登錄的固定白名單策略。 */
export function StrategyPicker({
  strategies,
  value,
  onChange,
}: {
  strategies: ResearchStrategyMeta[];
  value: string | null;
  onChange: (id: string) => void;
}) {
  const selected = pickStrategy(strategies, value);
  return (
    <div role="radiogroup" aria-label="策略" className="space-y-1">
      {strategies.map((s) => {
        const active = s.id === selected?.id;
        return (
          <button
            key={s.id}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(s.id)}
            className={cn(
              "w-full rounded border px-2.5 py-1.5 text-left font-mono text-xs transition-colors cursor-pointer",
              active
                ? "border-primary/60 bg-primary/10 text-foreground"
                : "border-border bg-background text-muted-foreground hover:bg-secondary/50",
            )}
          >
            <span className="flex items-center justify-between gap-2">
              <span className="truncate">{s.name}</span>
              <span className="shrink-0 text-t2 text-primary">{s.id}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
