import { ArrowUpRight, FlaskConical } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { AppShell, PageHead } from "@/components/catos/shell";
import { Button } from "@/components/ui/button";

export function WorkspacePage({ title, sub, code }: { title: string; sub: string; code: string }) {
  return (
    <AppShell>
      <PageHead title={title} code={code} desc={sub} right={<span className="rounded border border-border px-2 py-1 text-xs text-muted-foreground">Coming next</span>} />
      <div className="flex min-h-[440px] flex-col items-center justify-center border-y border-border text-center">
        <FlaskConical className="mb-5 size-9 text-muted-foreground" strokeWidth={1.2} />
        <h2 className="text-lg font-medium">No {title.toLowerCase()} activity yet</h2>
        <p className="mt-2 text-sm text-muted-foreground">尚無資料</p>
        <Button asChild variant="outline" size="sm" className="mt-6"><Link to="/">Back to Dashboard <ArrowUpRight /></Link></Button>
      </div>
    </AppShell>
  );
}