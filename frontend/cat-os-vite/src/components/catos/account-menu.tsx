import {
  Check,
  ChevronsUpDown,
  Copy,
  Globe,
  KeyRound,
  LogIn,
  LogOut,
  Palette,
  TrendingUp,
  User,
} from "lucide-react";
import { useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { usePersonalOs } from "@/state/personalOsStore";
import { PersonalOsModal } from "@/components/catos/personal-os-modal";
import { cn } from "@/lib/utils";

const itemCls =
  "gap-2.5 rounded-lg px-2.5 py-2 text-sm text-foreground/90 transition-colors hover:bg-secondary/70 focus:bg-accent focus:text-foreground [&_svg]:size-4 [&_svg]:text-muted-foreground focus:[&_svg]:text-primary cursor-pointer";

export function AccountMenu({ isFolded = false }: { isFolded?: boolean }) {
  const { user, ready, signOut, signInGoogle } = useAuth();
  const { language, setLanguage } = useI18n();
  const [copied, setCopied] = useState(false);

  // 個人化作業系統狀態 (Avatar, Name, Badge, Theme, Colors, Density, API)
  const {
    avatar,
    displayName,
    subAccountAlias,
    traderBadge,
    surfaceTone,
    accentColor,
    colorConvention,
    fontScale,
    ping,
  } = usePersonalOs();

  // 定案方案 A：macOS 系統偏好設定浮窗 (5 大專業 Tab)
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalTab, setModalTab] = useState<"presets" | "identity" | "theme" | "trading" | "api">("presets");

  const openPreferences = (tab: "presets" | "identity" | "theme" | "trading" | "api") => {
    setModalTab(tab);
    setIsModalOpen(true);
  };

  if (!ready) return <div className="h-[3.75rem]" />;

  if (!user)
    return (
      <div className="px-2">
        <button
          onClick={signInGoogle}
          className={cn(
            "flex items-center rounded-xl border border-dashed border-border/80 text-left transition-colors hover:bg-secondary/60",
            isFolded ? "size-10 justify-center mx-auto" : "w-full gap-3 px-3 py-2.5"
          )}
          title={language === "zh-TW" ? "登入帳戶" : "Sign In"}
        >
          <span className="grid size-7 place-items-center rounded-full border border-border text-muted-foreground">
            <LogIn className="size-3.5" />
          </span>
          {!isFolded && (
            <span className="leading-tight">
              <span className="block text-sm text-foreground font-medium">
                {language === "zh-TW" ? "登入帳戶" : "Sign In"}
              </span>
              <span className="text-[10px] text-muted-foreground">guest mode</span>
            </span>
          )}
        </button>
      </div>
    );

  const displayEmail = user.email || "trader@gmail.com";
  const effectiveName = displayName || user.name || "CatOS";

  return (
    <>
      <div className="px-2">
        <DropdownMenu>
          {/* 定案方案 2：純淨幽靈（Ghost）底座——完全零灰塊，滑鼠指過去背景純黑，文字純白提亮 + 圖標微彈 */}
          <DropdownMenuTrigger
            className={cn(
              "group flex items-center outline-none select-none text-left bg-transparent hover:bg-transparent transition-all",
              isFolded
                ? "size-10 justify-center mx-auto"
                : "w-full gap-2.5 px-2.5 py-1.5"
            )}
            title={isFolded ? `${effectiveName} (${displayEmail})` : undefined}
          >
            {/* 定案「無界純淨」：無外圈、消除基線下沉、Hover 微彈 */}
            <span
              className={cn(
                "flex items-center justify-center leading-none select-none text-foreground shrink-0 transition-transform duration-200 group-hover:scale-115",
                isFolded ? "size-10 text-[20px]" : "size-7 text-[18px]"
              )}
            >
              {avatar}
            </span>

            {!isFolded && (
              <>
                <div className="flex min-w-0 flex-1 flex-col justify-center leading-tight">
                  <span className="block truncate text-[13px] font-medium text-foreground/90 transition-colors group-hover:text-foreground group-hover:font-semibold">
                    {effectiveName}
                  </span>
                  <span className="mt-0.5 block truncate text-[11px] font-normal text-muted-foreground/75 transition-colors group-hover:text-muted-foreground">
                    {displayEmail}
                  </span>
                </div>
                <ChevronsUpDown className="size-3.5 text-muted-foreground transition-colors group-hover:text-primary shrink-0" />
              </>
            )}
          </DropdownMenuTrigger>

          <DropdownMenuContent
            side="top"
            align="start"
            sideOffset={8}
            className="w-[20.5rem] rounded-2xl border border-border/70 bg-popover/90 p-1.5 shadow-2xl backdrop-blur-2xl"
          >
            {/* 用戶資訊卡片：單行優雅整合，自訂身分徽章，點擊頭像直接進入個人身分設定 */}
            <div className="rounded-xl bg-secondary/35 p-3 mb-1.5">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => openPreferences("identity")}
                  title={language === "zh-TW" ? "點擊變更頭像與交易員檔案" : "Change avatar & profile"}
                  className="flex size-9 items-center justify-center text-[22px] leading-none shrink-0 rounded-lg hover:bg-secondary/60 transition-transform active:scale-95"
                >
                  <span>{avatar}</span>
                </button>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-1">
                    <p className="truncate text-sm font-semibold text-foreground">{effectiveName}</p>
                    <span className="shrink-0 rounded bg-secondary px-1.5 py-0.2 font-mono text-[9px] text-muted-foreground/90 border border-border/40">
                      {traderBadge}
                    </span>
                  </div>
                  {/* Email 單行帶快速複製按鈕與子帳戶提示 */}
                  <div className="mt-0.5 flex items-center justify-between text-[11px]">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className="truncate text-muted-foreground">{displayEmail}</span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigator.clipboard.writeText(displayEmail);
                          setCopied(true);
                          setTimeout(() => setCopied(false), 1200);
                        }}
                        className="flex items-center text-muted-foreground hover:text-foreground transition-colors p-0.5"
                        title={language === "zh-TW" ? "複製 Email" : "Copy Email"}
                      >
                        {copied ? <Check className="size-3 text-up" /> : <Copy className="size-3" />}
                      </button>
                      {copied && <span className="font-mono text-[9px] text-up font-medium">copied</span>}
                    </div>
                    <span className="font-mono text-[9.5px] text-muted-foreground/70 shrink-0">
                      {subAccountAlias}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* 定案方案 A：macOS 系統偏好設定 4 大專業分頁入口 */}
            <DropdownMenuGroup className="space-y-0.5">
              {/* 1. 交易員身分 */}
              <DropdownMenuItem
                onClick={() => openPreferences("identity")}
                className={itemCls}
              >
                <User />
                <span>{language === "zh-TW" ? "交易員個人身分" : "Trader Identity"}</span>
                <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                  {effectiveName}
                </span>
              </DropdownMenuItem>

              {/* 2. 系統主題 (獨立於漲跌色) */}
              <DropdownMenuItem
                onClick={() => openPreferences("theme")}
                className={itemCls}
              >
                <Palette />
                <span>{language === "zh-TW" ? "作業系統主題與強調色" : "System Theme & Accent"}</span>
                <span className="ml-auto font-mono text-[10px] text-muted-foreground uppercase">
                  {surfaceTone} · {accentColor}
                </span>
              </DropdownMenuItem>

              {/* 3. 看盤手感 (漲跌色彩慣例 · 完全獨立！) */}
              <DropdownMenuItem
                onClick={() => openPreferences("trading")}
                className={itemCls}
              >
                <TrendingUp />
                <span>{language === "zh-TW" ? "看盤色彩與字號密度" : "Trading Colors & Density"}</span>
                <span className="ml-auto font-mono text-[10px] text-up font-medium">
                  {colorConvention === "green-up" ? "綠漲" : colorConvention === "red-up" ? "紅漲" : colorConvention === "blue-up" ? "天藍漲" : "金黃漲"} · {fontScale.split("-")[1] || "100"}%
                </span>
              </DropdownMenuItem>

              {/* 4. OKX 專用子帳戶 API */}
              <DropdownMenuItem
                onClick={() => openPreferences("api")}
                className={itemCls}
              >
                <KeyRound />
                <span>{language === "zh-TW" ? "OKX 專用子帳戶 API" : "OKX Sub-Account API"}</span>
                <span className="ml-auto flex items-center gap-1.5 rounded-full bg-up/10 px-2 py-0.5 font-mono text-[10px] font-medium text-up">
                  <span className="size-1.5 rounded-full bg-up animate-pulse" />
                  3 LIVE · {ping}ms
                </span>
              </DropdownMenuItem>
            </DropdownMenuGroup>

            {/* 無框平滑滑動語言切換槽 Language Switcher */}
            <div className="my-1.5 rounded-xl bg-secondary/40 p-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-muted-foreground">
                  <Globe className="size-3.5" />
                  <span>{language === "zh-TW" ? "介面語言" : "Language"}</span>
                </span>
                <div className="flex items-center rounded-lg bg-background/80 p-0.5 border border-border/50">
                  <button
                    type="button"
                    onClick={() => setLanguage("zh-TW")}
                    className={cn(
                      "rounded-md px-2.5 py-1 text-[11px] transition-all",
                      language === "zh-TW"
                        ? "bg-secondary text-foreground shadow-xs font-semibold"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    繁中
                  </button>
                  <button
                    type="button"
                    onClick={() => setLanguage("en")}
                    className={cn(
                      "rounded-md px-2.5 py-1 text-[11px] transition-all",
                      language === "en"
                        ? "bg-secondary text-foreground shadow-xs font-semibold"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    EN
                  </button>
                </div>
              </div>
            </div>

            <DropdownMenuSeparator className="my-1 bg-border/60" />

            {/* 退出本機終端 */}
            <div>
              <DropdownMenuItem
                onClick={signOut}
                className={cn(itemCls, "text-down focus:text-down [&_svg]:text-down focus:[&_svg]:text-down")}
              >
                <LogOut />
                <span>{language === "zh-TW" ? "鎖定 / 退出終端" : "Lock / Exit Terminal"}</span>
              </DropdownMenuItem>
            </div>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* 定案方案 A: macOS 系統偏好設定浮窗 (4 大專業 Tab) */}
      <PersonalOsModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        initialTab={modalTab}
      />
    </>
  );
}
