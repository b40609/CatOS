import { Globe, Check } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useI18n, type Language } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function LanguageSelector() {
  const { language, setLanguage } = useI18n();

  const options: { id: Language; label: string; sub: string }[] = [
    { id: "zh-TW", label: "繁體中文", sub: "Traditional Chinese" },
    { id: "en", label: "English", sub: "US English" },
  ];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="flex h-7 items-center gap-1.5 rounded-md border border-border/80 bg-surface px-2.5 text-[11px] text-muted-foreground transition-colors hover:border-border hover:bg-secondary/60 hover:text-foreground focus:outline-none"
        title="切換語言 / Switch Language"
        aria-label="語言切換"
      >
        <Globe className="size-3.5 shrink-0 text-muted-foreground/80" strokeWidth={1.7} />
        <span className="font-medium tracking-wide">
          {language === "zh-TW" ? "繁體中文" : "EN"}
        </span>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="end"
        sideOffset={6}
        className="w-48 rounded-md border-border bg-popover p-1 shadow-xl"
      >
        <div className="px-2 py-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
          {language === "zh-TW" ? "介面語言 · LANGUAGE" : "INTERFACE LANGUAGE"}
        </div>
        {options.map((opt) => {
          const isSelected = language === opt.id;
          return (
            <DropdownMenuItem
              key={opt.id}
              onClick={() => setLanguage(opt.id)}
              className={cn(
                "flex cursor-pointer items-center justify-between rounded px-2.5 py-2 text-xs transition-colors",
                isSelected
                  ? "bg-secondary/90 font-medium text-primary"
                  : "text-foreground hover:bg-secondary/50"
              )}
            >
              <div className="flex flex-col">
                <span className="leading-tight">{opt.label}</span>
                <span className="text-[10px] text-muted-foreground font-mono mt-0.5">
                  {opt.sub}
                </span>
              </div>
              {isSelected && <Check className="size-3.5 shrink-0 text-primary" strokeWidth={2.5} />}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
