import {
  TrendingUp,
  GitBranch,
  Bot,
  PieChart,
  ScrollText,
} from "lucide-react";
import type { CardId } from "@/state/layoutStore";

export interface CardSpec {
  dataFeed: string;
  latency: string;
  engine: string;
  tier: "核心防線" | "委託執行" | "策略情報" | "日誌審計";
  codeId: string;
}

export interface CardMeta {
  id: CardId;
  nameZh: string;
  nameEn: string;
  category: "資產風控" | "交易執行" | "策略行情" | "日誌審計";
  desc: string;
  icon: typeof TrendingUp;
  badge?: string;
  minHeight?: number;
  spec: CardSpec;
}

export const ALL_CARDS: CardMeta[] = [
  {
    id: "equity",
    nameZh: "帳戶權益與損益",
    nameEn: "Equity & Verified Drawdown",
    category: "資產風控",
    desc: "實時淨值資產、台北日切 00:00 風控基準、風控期間損益與權益曲線",
    icon: TrendingUp,
    badge: "R1 基準",
    spec: {
      dataFeed: "Supervisor API / DB",
      latency: "1s 心跳",
      engine: "Decimal E_risk",
      tier: "核心防線",
      codeId: "EQUITY_MONITOR_V1",
    },
  },
  {
    id: "allocation",
    nameZh: "曝險額度",
    nameEn: "Exposure & Multi-View Donut",
    category: "資產風控",
    desc: "按策略／幣種／多空／損益／保證金 5 視角監控曝險上限，點擊圓環切換 % / x / $",
    icon: PieChart,
    badge: "1.0x／單幣 0.5x",
    spec: {
      dataFeed: "Supervisor Risk Projection",
      latency: "實時對帳",
      engine: "事前槓桿審計",
      tier: "核心防線",
      codeId: "EXPOSURE_DONUT_V2",
    },
  },
  {
    id: "bots",
    nameZh: "策略實例與持倉",
    nameEn: "Bots & Positions Matrix",
    category: "交易執行",
    desc: "策略實例、多空持倉、均價／標記價、P6 停損與掛單合一寬表，點擊列展開詳情",
    icon: Bot,
    badge: "實例＋持倉合一",
    spec: {
      dataFeed: "Supervisor IPC / Positions",
      latency: "500ms 輪詢",
      engine: "無憑證策略隔離",
      tier: "委託執行",
      codeId: "BOTS_POSITIONS_V2",
    },
  },
  {
    id: "pipeline",
    nameZh: "策略管線",
    nameEn: "Strategy Pipeline",
    category: "策略行情",
    desc: "5 階段生命週期軌道（提案 → 研究驗證 → 待核准 → 模擬盤 → 實盤），窄卡自動轉進度條",
    icon: GitBranch,
    badge: "5 階段軌道",
    spec: {
      dataFeed: "Catalog / Replay / Demo Bot",
      latency: "30s 輪詢",
      engine: "唯讀生命週期投影",
      tier: "策略情報",
      codeId: "STRATEGY_PIPELINE_V1",
    },
  },
  {
    id: "activity_deck",
    nameZh: "待處理與事件審計",
    nameEn: "Action Queue & Audit Log",
    category: "日誌審計",
    desc: "依嚴重度排序的待處理佇列（鎖存／警戒／待核准）與完整事件審計成交流水",
    icon: ScrollText,
    badge: "待處理＋流水",
    spec: {
      dataFeed: "Local SQLite (WAL) / Signals",
      latency: "逐筆寫入",
      engine: "不可竄改日誌鏈",
      tier: "日誌審計",
      codeId: "ACTION_AUDIT_DECK_V3",
    },
  },
];

/**
 * 各卡片最小安全閱讀高度 (px)：確保 5 卡標準佈局完整貼合單一視窗，僅在極限多層堆疊時撐開捲動
 */
export const CARD_DEFAULT_MIN_HEIGHTS: Partial<Record<CardId, number>> = {
  equity: 170,
  allocation: 170,
  bots: 165,
  pipeline: 165,
  activity_deck: 220,
  positions: 165,
  fills: 160,
  incidents: 160,
  bot_inspector: 200,
};
