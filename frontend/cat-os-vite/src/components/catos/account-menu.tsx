import { Link } from "@tanstack/react-router";
import {
  BarChart3,
  ChevronsUpDown,
  Copy,
  KeyRound,
  LifeBuoy,
  LogIn,
  LogOut,
  Settings,
  User,
  Wallet,
} from "lucide-react";
import { useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/lib/auth";
import { fmtMoney, useLiveNumber } from "@/hooks/use-live";
import { cn } from "@/lib/utils";

const itemCls =
  "gap-2.5 rounded-none px-2.5 py-2 text-sm text-foreground/85 focus:bg-accent focus:text-gold-bright [&_svg]:size-4 [&_svg]:text-muted-foreground focus:[&_svg]:text-gold";

export function AccountMenu() {
  const { user, ready, signOut, signInGoogle } = useAuth();
  const { value: pnl } = useLiveNumber(48_216, 0.004, 2000);
  const [copied, setCopied] = useState(false);

  if (!ready) return <div className="h-[4.25rem] border-t border-border" />;

  if (!user)
    return (
      <div className="border-t border-border p-2">
        <button
          onClick={signInGoogle}
          className="flex w-full items-center gap-3 border border-dashed border-gold/40 px-3 py-2.5 text-left transition-colors hover:bg-accent"
        >
          <span className="grid size-9 place-items-center border border-border text-muted-foreground">
            <LogIn className="size-4" />
          </span>
          <span className="leading-tight">
            <span className="block text-sm text-gold">登入帳戶</span>
            <span className="label-xs">guest mode</span>
          </span>
        </button>
      </div>
    );

  const uid = "UID 8820·4417";

  return (
    <div className="border-t border-border p-2">
      <DropdownMenu>
        <DropdownMenuTrigger className="group flex w-full items-center gap-3 border border-transparent px-2 py-2 text-left outline-none transition-colors hover:border-border hover:bg-secondary/70 data-[state=open]:border-gold/40 data-[state=open]:bg-accent">
          <span className="relative">
            <span className="grid size-9 place-items-center border border-gold/50 bg-background font-mono text-sm text-gold-bright">
              {user.avatar}
            </span>
            <span className="absolute -right-0.5 -bottom-0.5 size-2.5 rounded-full border-2 border-sidebar bg-up" />
          </span>
          <span className="min-w-0 flex-1 leading-tight">
            <span className="block truncate text-sm text-foreground">{user.name}</span>
            <span className="mt-0.5 flex items-center gap-1.5">
              <span className="border border-gold/40 px-1 font-mono text-[0.55rem] tracking-wider text-gold">
                VIP 3
              </span>
              <span className="num text-[0.65rem] text-up">+{fmtMoney(pnl)}</span>
            </span>
          </span>
          <ChevronsUpDown className="size-3.5 text-muted-foreground group-hover:text-gold" />
        </DropdownMenuTrigger>

        <DropdownMenuContent
          side="top"
          align="start"
          sideOffset={8}
          className="w-[16.5rem] rounded-none border-border bg-popover p-0 shadow-2xl"
        >
          <div className="scanlines border-b border-border p-3">
            <div className="flex items-center gap-3">
              <span className="grid size-10 place-items-center border border-gold/50 font-mono text-gold-bright">
                {user.avatar}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm text-gold-bright">{user.name}</p>
                <p className="num truncate text-[0.7rem] text-muted-foreground">{user.email}</p>
              </div>
            </div>
            <button
              onClick={() => {
                setCopied(true);
                setTimeout(() => setCopied(false), 1200);
              }}
              className="num mt-2 flex items-center gap-1.5 text-[0.65rem] text-muted-foreground hover:text-gold"
            >
              {uid} <Copy className="size-3" /> {copied && <span className="text-up">copied</span>}
            </button>
            <div className="mt-3 grid grid-cols-2 gap-px border border-border bg-border">
              <div className="bg-popover px-2 py-1.5">
                <p className="label-xs">equity</p>
                <p className="num text-xs text-foreground">₮ 12.48M</p>
              </div>
              <div className="bg-popover px-2 py-1.5">
                <p className="label-xs">30d pnl</p>
                <p className="num text-xs text-up">+{fmtMoney(pnl)}</p>
              </div>
            </div>
          </div>

          <DropdownMenuGroup className="p-1">
            <DropdownMenuItem asChild className={itemCls}>
              <Link to="/profile">
                <User /> 個人資料
                <DropdownMenuShortcut>⌘P</DropdownMenuShortcut>
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild className={itemCls}>
              <Link to="/">
                <BarChart3 /> 績效分析
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem className={itemCls}>
              <Wallet /> 錢包與資產
            </DropdownMenuItem>
            <DropdownMenuItem className={itemCls}>
              <KeyRound /> 交易所 API 金鑰
              <span className="ml-auto border border-up/40 px-1 font-mono text-[0.55rem] text-up">3 LIVE</span>
            </DropdownMenuItem>
          </DropdownMenuGroup>
          <DropdownMenuSeparator className="m-0 bg-border" />
          <DropdownMenuGroup className="p-1">
            <DropdownMenuItem className={itemCls}>
              <Settings /> 設定與隱私
            </DropdownMenuItem>
            <DropdownMenuItem className={itemCls}>
              <LifeBuoy /> 說明中心
            </DropdownMenuItem>
          </DropdownMenuGroup>
          <DropdownMenuSeparator className="m-0 bg-border" />
          <div className="p-1">
            <DropdownMenuItem
              onClick={signOut}
              className={cn(itemCls, "text-down focus:text-down [&_svg]:text-down focus:[&_svg]:text-down")}
            >
              <LogOut /> 登出
              <DropdownMenuShortcut>⇧⌘Q</DropdownMenuShortcut>
            </DropdownMenuItem>
          </div>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
