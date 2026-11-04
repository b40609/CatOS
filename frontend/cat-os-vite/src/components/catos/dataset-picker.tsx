import type { ResearchDatasetMeta } from "@/adapters/research-api-adapter";
import { cn } from "@/lib/utils";

/** The selected dataset, falling back to the first registered one when the id is unknown. */
export function pickDataset(datasets: ResearchDatasetMeta[] | undefined, id: string | null) {
  return datasets?.find((d) => d.id === id) ?? datasets?.[0] ?? null;
}

/** 研究資料集單選清單：合成資料與已抓取並通過雜湊核對的 OKX 公開歷史資料。 */
export function DatasetPicker({
  datasets,
  value,
  onChange,
}: {
  datasets: ResearchDatasetMeta[];
  value: string | null;
  onChange: (id: string) => void;
}) {
  const selected = pickDataset(datasets, value);
  return (
    <div className="space-y-1">
      <div role="radiogroup" aria-label="資料集" className="space-y-1">
        {datasets.map((d) => {
          const active = d.id === selected?.id;
          return (
            <button
              key={d.id}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(d.id)}
              className={cn(
                "w-full rounded border px-2.5 py-1.5 text-left font-mono text-xs transition-colors cursor-pointer",
                active
                  ? "border-primary/60 bg-primary/10 text-foreground"
                  : "border-border bg-background text-muted-foreground hover:bg-secondary/50",
              )}
            >
              <span className="flex items-center justify-between gap-2">
                <span className="truncate">{d.name}</span>
                <span className="shrink-0 text-t2 text-primary">{d.symbol}</span>
              </span>
            </button>
          );
        })}
      </div>
      {selected?.notice && <p className="text-t2 leading-relaxed text-muted-foreground">{selected.notice}</p>}
    </div>
  );
}
