import {
  TrendingUp,
  LineChart,
  Bot,
  PieChart,
  Zap,
  ShieldAlert,
  Timer,
  Target,
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
    desc: "實時淨值資產、台北日切 00:00 風控基準、當日損益監控與 7D 走勢圖",
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
    nameZh: "槓桿倍數與資產曝險",
    nameEn: "Leverage & Allocation Donut",
    category: "資產風控",
    desc: "帳戶有效槓桿倍數、單幣曝險預算 50% 限制與多空甜甜圈資產分佈",
    icon: PieChart,
    badge: "3.0x 上限",
    spec: {
      dataFeed: "OKX SWAP WebSocket",
      latency: "100ms 實時",
      engine: "事前槓桿審計",
      tier: "核心防線",
      codeId: "LEVERAGE_DONUT_V1",
    },
  },
  {
    id: "positions",
    nameZh: "持倉明細與在途防線",
    nameEn: "Positions & P6 Protection",
    category: "交易執行",
    desc: "多空持倉明細、P6 災難停損防線覆蓋、在途掛單撤單與即時凍結保證金",
    icon: LineChart,
    badge: "P6 交易所防線",
    spec: {
      dataFeed: "OKX 專用子帳戶",
      latency: "事件驅動",
      engine: "Mark 取整停損",
      tier: "委託執行",
      codeId: "POSITIONS_P6_DECK",
    },
  },
  {
    id: "bots",
    nameZh: "策略機器人矩陣",
    nameEn: "Bots Runtime Matrix",
    category: "交易執行",
    desc: "4 隻專用 KOL 策略進程、單幣獨佔約束、Worker 心跳檢測與一鍵啟停",
    icon: Bot,
    badge: "單幣獨佔",
    spec: {
      dataFeed: "Supervisor IPC (JSON)",
      latency: "500ms 輪詢",
      engine: "無憑證策略隔離",
      tier: "委託執行",
      codeId: "BOT_SUPERVISOR_MATRIX",
    },
  },
  {
    id: "activity_deck",
    nameZh: "全域戰情日誌台",
    nameEn: "Unified Incident Deck",
    category: "日誌審計",
    desc: "極限二字 6 大時序維度：未解除、全部、風控、成交、委託與系統生命週期",
    icon: ScrollText,
    badge: "二字定案",
    spec: {
      dataFeed: "Local SQLite (WAL)",
      latency: "逐筆寫入",
      engine: "不可竄改日誌鏈",
      tier: "日誌審計",
      codeId: "ACTIVITY_DECK_V2",
    },
  },
  {
    id: "fills",
    nameZh: "即時成交流水",
    nameEn: "Recent Fills Stream",
    category: "交易執行",
    desc: "OKX SWAP 實時逐筆成交回報、S3 費用帳務、買賣單向與損益即時跳動",
    icon: Zap,
    badge: "S3 逐筆撮合",
    spec: {
      dataFeed: "OKX WS / Fills",
      latency: "即時推播",
      engine: "USDT 費用重放",
      tier: "委託執行",
      codeId: "FILLS_STREAM_S3",
    },
  },
  {
    id: "market_watch",
    nameZh: "標的行情與資金費率",
    nameEn: "Market Ticker & 8H Rates",
    category: "策略行情",
    desc: "BTC/ETH/SOL 實時標記價、8H 永續資金費率結算倒數與收盤倒數時鐘",
    icon: Timer,
    badge: "Closed Bar",
    spec: {
      dataFeed: "OKX Public Tickers",
      latency: "200ms Tick",
      engine: "K 線收盤對齊",
      tier: "策略情報",
      codeId: "MARKET_CLOCK_8H",
    },
  },
  {
    id: "strategy_intents",
    nameZh: "策略目標與訊號強度",
    nameEn: "Signals Radar & Intents",
    category: "策略行情",
    desc: "Worker 傳出的純資料委託意圖、多空訊號雷達與指標偏離度預警",
    icon: Target,
    badge: "純資料訊號",
    spec: {
      dataFeed: "Strategy Worker IPC",
      latency: "Bar 關閉時觸發",
      engine: "Jesse API Style",
      tier: "策略情報",
      codeId: "STRATEGY_RADAR_V1",
    },
  },
  {
    id: "incidents",
    nameZh: "風險警報與異常審計",
    nameEn: "Risk Alarms & Kill Switch",
    category: "日誌審計",
    desc: "撮合滑價偏離警報、UNKNOWN 委託熔斷鎖存與帳戶級硬日損防線",
    icon: ShieldAlert,
    badge: "熔斷鎖存",
    spec: {
      dataFeed: "Guardian 獨立看門狗",
      latency: "微秒級審計",
      engine: "Hard Kill-Switch",
      tier: "核心防線",
      codeId: "RISK_AUDIT_GUARDIAN",
    },
  },
];

/**
 * 各卡片預設最小安全閱讀高度 (px)
 * 供使用者隨時根據每張卡片的資料密度與排版需求自訂調整預設值
 */
export const CARD_DEFAULT_MIN_HEIGHTS: Record<CardId, number> = {
  equity: 340,           // 權益走勢圖 + 核心 KPI + 台北日切基準
  positions: 340,        // 持倉明細與在途委託雙檢視表 + 底部撤單統計
  bots: 320,             // 4 隻 KOL 機器人監控表格 + 狀態指示
  allocation: 320,       // 槓桿儀表板 + 甜甜圈圓餅圖 + 幣種曝險進度條
  activity_deck: 340,    // 全域戰情日誌時間軸
  fills: 280,            // 即時成交流水表
  market_watch: 260,     // 標的行情與資金費率
  strategy_intents: 280, // 策略目標與訊號強度雷達
  incidents: 300,        // 風險警報與異常審計
  bot_inspector: 380,    // 機器人深層檢測 (Master-Detail)
};
