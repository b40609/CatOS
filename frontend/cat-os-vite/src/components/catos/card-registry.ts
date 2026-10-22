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

export interface CardMeta {
  id: CardId;
  nameZh: string;
  nameEn: string;
  category: "資產風控" | "交易執行" | "策略行情" | "日誌審計";
  desc: string;
  icon: typeof TrendingUp;
  badge?: string;
}

export const ALL_CARDS: CardMeta[] = [
  {
    id: "equity",
    nameZh: "帳戶權益與損益",
    nameEn: "Equity & Drawdown",
    category: "資產風控",
    desc: "即時淨值資產、今日損益、回撤警報與 7D 響應式走勢圖",
    icon: TrendingUp,
    badge: "核心",
  },
  {
    id: "positions",
    nameZh: "持倉明細與在途委託",
    nameEn: "Positions & Orders",
    category: "交易執行",
    desc: "多空持倉明細、P6 災難停損防線、在途掛單撤單與即時凍結保證金",
    icon: LineChart,
    badge: "核心",
  },
  {
    id: "bots",
    nameZh: "策略機器人矩陣",
    nameEn: "Bots Matrix",
    category: "交易執行",
    desc: "4 隻專用 KOL 策略機器人、狀態監控、運行心跳與一鍵啟停",
    icon: Bot,
    badge: "核心",
  },
  {
    id: "allocation",
    nameZh: "槓桿倍數與資產曝險",
    nameEn: "Leverage & Allocation",
    category: "資產風控",
    desc: "帳戶有效槓桿倍數、幣種名義曝險額與多空 Donut 資產分佈環圖",
    icon: PieChart,
    badge: "核心",
  },
  {
    id: "activity_deck",
    nameZh: "交易日誌與風險事件",
    nameEn: "Activity & Events",
    category: "日誌審計",
    desc: "全域戰情日誌台，統合即時成交流水、風控警報與系統生命週期",
    icon: ScrollText,
    badge: "核心",
  },
  {
    id: "fills",
    nameZh: "即時成交流水",
    nameEn: "Recent Fills",
    category: "交易執行",
    desc: "OKX SWAP 實時逐筆成交流水、買賣單向、成交價格與損益跳動",
    icon: Zap,
  },
  {
    id: "market_watch",
    nameZh: "標的行情與資金費率",
    nameEn: "Market Watch & Rates",
    category: "策略行情",
    desc: "BTC/ETH/SOL 實時標記價、OKX 資金費率結算倒數計時與收盤時鐘",
    icon: Timer,
  },
  {
    id: "strategy_intents",
    nameZh: "策略目標與訊號強度",
    nameEn: "Signals & Radar",
    category: "策略行情",
    desc: "Worker 傳出的純資料目標意圖、多空訊號強度雷達與關鍵指標偏離度",
    icon: Target,
  },
  {
    id: "incidents",
    nameZh: "風險警報與異常事件",
    nameEn: "Risk Incidents",
    category: "日誌審計",
    desc: "撮合滑價偏離警報、P6 保險停損更新日誌與帳戶風控異常事件流",
    icon: ShieldAlert,
  },
];
