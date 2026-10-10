import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AppShell, PageHead, Panel } from "@/components/catos/shell";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/profile")({
  head: () => ({
    meta: [
      { title: "個人資料 · catOS" },
      { name: "description", content: "管理你的 catOS 暱稱、頭像與帳號資訊。" },
      { property: "og:title", content: "個人資料 · catOS" },
      { property: "og:description", content: "管理你的 catOS 帳號。" },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: ProfilePage,
});

const AVATARS = ["^ω^", "₿", "Ξ", "◎", "Ð", "🐱", "🚀", "🐋"];

function ProfilePage() {
  return (
    <AppShell>
      <ProfileBody />
    </AppShell>
  );
}

function ProfileBody() {
  const { user, updateProfile } = useAuth();
  const [name, setName] = useState(user?.name ?? "");
  const [saved, setSaved] = useState(false);
  useEffect(() => setName(user?.name ?? ""), [user?.name]);
  if (!user) return null;

  return (
    <>
      <PageHead code="ACCOUNT // PROFILE" title="個人資料" desc="暱稱與頭像 · 僅存於本機瀏覽器" />
      <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        <Panel title="identity">
          <div className="flex items-center gap-4">
            <span className="grid size-16 place-items-center border border-gold/50 font-mono text-2xl text-gold">{user.avatar}</span>
            <div>
              <p className="text-lg text-gold-bright">{user.name}</p>
              <p className="num text-sm text-muted-foreground">{user.email}</p>
              <p className="label-xs mt-1">via {user.provider} · since {user.joinedAt.slice(0, 10)}</p>
            </div>
          </div>
        </Panel>
        <Panel title="edit">
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              updateProfile({ name: name.trim() || user.name });
              setSaved(true);
              setTimeout(() => setSaved(false), 1500);
            }}
          >
            <div className="space-y-1.5">
              <Label htmlFor="pname">暱稱</Label>
              <Input id="pname" value={name} onChange={(e) => setName(e.target.value)} className="bg-background" />
            </div>
            <div className="space-y-1.5">
              <Label>頭像</Label>
              <div className="flex flex-wrap gap-2">
                {AVATARS.map((a) => (
                  <button
                    key={a}
                    type="button"
                    onClick={() => updateProfile({ avatar: a })}
                    className={cn(
                      "grid size-10 place-items-center border font-mono",
                      user.avatar === a ? "border-gold text-gold-bright" : "border-border text-muted-foreground hover:border-gold/50",
                    )}
                  >
                    {a}
                  </button>
                ))}
              </div>
            </div>
            <button type="submit" className="bg-primary px-4 py-2 font-mono text-sm uppercase tracking-[0.12em] text-primary-foreground hover:bg-primary/90">
              {saved ? "Saved ✓" : "Save"}
            </button>
          </form>
        </Panel>
      </div>
    </>
  );
}
