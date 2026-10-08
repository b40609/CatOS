/**
 * catOS v1 - Mock Scenarios Data
 * Represents 4 explicit system states for UI verification and Codex integration:
 * 1. normal: Rich active trading data, normal connections
 * 2. empty: Honest empty state, no zero padding, waiting for assignment
 * 3. locked_409: Bot stopped with position retained (-1.00 contract), contract ownership locked
 * 4. recovery: Risk threshold warning, RECOVERY_REQUIRED, disabled actions
 */

export const SCENARIOS = {
  normal: {
    name: "正常運行 (Normal Running)",
    status: {
      connection: "connected",
      ping: "14ms",
      mode: "localhost",
      supervisor: "ONLINE (PID: 49772)",
      workerIsolation: "P1 Python Subprocess (JSON IPC)",
      storage: "SQLite (WAL)",
      buildId: "f791e202bb000bf2cce06433849fd3c86c8d49e0837cb77545ec73cc5b6d39ee",
      instanceId: "868721f213644b64a81cb88b1a447d3b",
      orderTag: "41cb53c54d6dABDE"
    },
    kpi: {
      totalEquity: "125480.50",
      currency: "USDT",
      equityVerified: "125480.50",
      dailyPnl: "1240.80",
      dailyPnlPct: "+1.00%",
      dailyCutoff: "Asia/Taipei 00:00",
      activeBots: { running: 2, warning: 1, stopped: 0, total: 3 },
      effectiveLeverage: "1.85",
      maxAllowedLeverage: "3.00",
      totalNotionalExposure: "232138.92",
      totalExposureBudget: "376441.50", /* 3.0 * 125480.50 */
      singleCoinCap: "188220.75",     /* 50% * 376441.50 */
      marginUsed: "28450.00",
      marginAvailable: "97030.50",
      riskState: "NORMAL"
    },
    riskLatch: {
      initialDailyEquity: "124239.70",
      currentPnl: "+1240.80",
      currentPnlPct: "+1.00",
      softThresholdPct: "-10.00",
      softThresholdVal: "-12423.97",
      hardThresholdPct: "-20.00",
      hardThresholdVal: "-24847.94",
      cushionToSoft: "13664.77",
      latchActive: false,
      latchReason: "NONE"
    },
    bots: [
      {
        id: "bot-btc-trend-01",
        name: "BTC Trend Follower v1.2",
        contract: "BTC-USDT-SWAP",
        version: "v1.2.0-rc3",
        versionHash: "a1c49e7b2f0981d4",
        status: "RUNNING",
        direction: "LONG",
        positionSize: "0.45",
        positionUnit: "BTC",
        entryPrice: "64250.00",
        markPrice: "65120.50",
        unrealizedPnl: "+391.72",
        pnlPct: "+1.35%",
        leverage: "2.0x",
        margin: "14652.11",
        ownershipLocked: true,
        disasterStopPct: "3.5%",
        lastSignalAt: "10:45:00"
      },
      {
        id: "bot-eth-breakout-02",
        name: "ETH Vol Breakout",
        contract: "ETH-USDT-SWAP",
        version: "v1.0.1",
        versionHash: "98ef32d7b884c102",
        status: "RUNNING",
        direction: "LONG",
        positionSize: "5.20",
        positionUnit: "ETH",
        entryPrice: "3420.00",
        markPrice: "3445.80",
        unrealizedPnl: "+134.16",
        pnlPct: "+0.75%",
        leverage: "1.5x",
        margin: "11946.44",
        ownershipLocked: true,
        disasterStopPct: "4.0%",
        lastSignalAt: "11:15:00"
      },
      {
        id: "bot-sol-grid-03",
        name: "SOL Neutral Grid",
        contract: "SOL-USDT-SWAP",
        version: "v1.1.4",
        versionHash: "447ac9018be238ff",
        status: "WARNING",
        direction: "SHORT",
        positionSize: "28.00",
        positionUnit: "SOL",
        entryPrice: "152.40",
        markPrice: "154.20",
        unrealizedPnl: "-50.40",
        pnlPct: "-1.18%",
        leverage: "1.0x",
        margin: "1851.45",
        ownershipLocked: true,
        disasterStopPct: "0.0%",
        lastSignalAt: "11:20:00",
        warningMsg: "滑價逼近警戒門檻 (2.8 bps / 3.0 bps)"
      }
    ],
    allocation: {
      usedMargin: "28450.00",
      freeMargin: "97030.50",
      coins: [
        { coin: "BTC", notional: "29304.22", pctOfBudget: "7.78%", color: "#f59e0b" },
        { coin: "ETH", notional: "17918.16", pctOfBudget: "4.76%", color: "#8b5cf6" },
        { coin: "SOL", notional: "4317.60", pctOfBudget: "1.15%", color: "#06b6d4" },
        { coin: "AVAILABLE", notional: "324901.52", pctOfBudget: "86.31%", color: "#1e293b" }
      ]
    },
    incidents: [
      { id: "inc-101", time: "11:20:04", level: "WARN", title: "SOL-USDT-SWAP 撮合滑價警示", desc: "滑價 2.8 bps，逼近設定之 3.0 bps 門檻；已記錄審計軌跡。" },
      { id: "inc-100", time: "11:15:00", level: "INFO", title: "ETH 突破訊號確認", desc: "15m Bar 收盤確認突破，注入 Tag 41cb53c54d6dABDE 開倉 5.2 ETH。" },
      { id: "inc-099", time: "10:45:00", level: "INFO", title: "BTC 加倉意圖執行成功", desc: "市價下一根開盤成交，滑價 0.4 bps，符合 P7 Decimal 核心撮合規範。" },
      { id: "inc-098", time: "08:00:00", level: "INFO", title: "Asia/Taipei 00:00 切日對帳通過", desc: "已實現損益、資金費率無異常，日初權益基準設定為 124,239.70 USDT。" }
    ],
    research: [
      { id: "res-01", name: "Dual-SMA-Momentum", timeframe: "15m Closed Bar", sharpe: "2.14", netProfitPct: "+36.84%", maxDrawdown: "-8.2%", bars: "8,400 (Warmup 200)", status: "COMPLETED" },
      { id: "res-02", name: "Bollinger-Reversal-v2", timeframe: "1h Closed Bar", sharpe: "1.85", netProfitPct: "+24.12%", maxDrawdown: "-11.4%", bars: "4,200 (Warmup 100)", status: "COMPLETED" }
    ],
    yaozi: [
      { id: "yao-01", time: "11:05", title: "OKX BTC 資金費率偏離警報", tag: "費率異動", desc: "年化費率偏離至 +24.8%，可能引發期現套利回補潮。", status: "開發中 · 僅供參考" },
      { id: "yao-02", time: "10:30", title: "巨鯨鏈上轉入 1,200 BTC 至交易所", tag: "鏈上大額", desc: "地址 1P5Z... 異動，請關注短線下檔支撐。", status: "開發中 · 僅供參考" }
    ],
    attentionItems: [
      { id: "att-01", level: "warning", title: "SOL 網格滑價偏高 (2.8 bps)", desc: "接近單次容許上限 3.0 bps，建議關注流動性深度。", action: "檢查深度", target: "bot-sol-grid-03" },
      { id: "att-02", level: "info", title: "AI MCP 新增不可變策略版本", desc: "策略版本 v1.3.0-opt 已上傳至版本庫，待人工檢查並手動建立 Bot。", action: "前往策略庫", target: "/workspace/research" },
      { id: "att-03", level: "info", title: "日損安全距離充足", desc: "距離 Soft 門檻 (-10%) 仍有 13,664.77 USDT 緩衝，策略正常運作中。", action: "風控詳情", target: "/workspace/risk" }
    ]
  },

  empty: {
    name: "空資料待命 (Empty Standby)",
    status: {
      connection: "connected",
      ping: "16ms",
      mode: "localhost",
      supervisor: "ONLINE (PID: 49772)",
      workerIsolation: "P1 Python Subprocess",
      storage: "SQLite (WAL)",
      buildId: "f791e202bb000bf2cce06433849fd3c86c8d49e0837cb77545ec73cc5b6d39ee",
      instanceId: "868721f213644b64a81cb88b1a447d3b",
      orderTag: "41cb53c54d6dABDE"
    },
    kpi: {
      totalEquity: "—",
      currency: "USDT",
      equityVerified: "—",
      dailyPnl: "—",
      dailyPnlPct: "—",
      dailyCutoff: "Asia/Taipei 00:00",
      activeBots: { running: 0, warning: 0, stopped: 0, total: 0 },
      effectiveLeverage: "—",
      maxAllowedLeverage: "3.00",
      totalNotionalExposure: "0.00",
      totalExposureBudget: "—",
      singleCoinCap: "—",
      marginUsed: "0.00",
      marginAvailable: "—",
      riskState: "STANDBY"
    },
    riskLatch: {
      initialDailyEquity: "—",
      currentPnl: "0.00",
      currentPnlPct: "0.00",
      softThresholdPct: "-10.00",
      softThresholdVal: "—",
      hardThresholdPct: "-20.00",
      hardThresholdVal: "—",
      cushionToSoft: "—",
      latchActive: false,
      latchReason: "NONE"
    },
    bots: [],
    allocation: {
      usedMargin: "0.00",
      freeMargin: "0.00",
      coins: []
    },
    incidents: [],
    research: [],
    yaozi: [],
    attentionItems: [
      { id: "att-empty-1", level: "info", title: "工作區已就緒，尚未部署 Bot", desc: "請由策略中心匯入受信策略製品，並手動指派運行。", action: "前往策略中心", target: "/workspace/research" }
    ]
  },

  locked_409: {
    name: "持倉停止 409 鎖定 (Stopped Position Retained)",
    status: {
      connection: "connected",
      ping: "18ms",
      mode: "localhost",
      supervisor: "ONLINE (PID: 49772)",
      workerIsolation: "P1 Python Subprocess",
      storage: "SQLite (WAL)",
      buildId: "f791e202bb000bf2cce06433849fd3c86c8d49e0837cb77545ec73cc5b6d39ee",
      instanceId: "868721f213644b64a81cb88b1a447d3b",
      orderTag: "41cb53c54d6dABDE"
    },
    kpi: {
      totalEquity: "1000.00",
      currency: "USDT",
      equityVerified: "1000.00",
      dailyPnl: "-18.42",
      dailyPnlPct: "-1.84%",
      dailyCutoff: "Asia/Taipei 00:00",
      activeBots: { running: 0, warning: 0, stopped: 1, total: 1 },
      effectiveLeverage: "0.65",
      maxAllowedLeverage: "3.00",
      totalNotionalExposure: "650.00",
      totalExposureBudget: "3000.00",
      singleCoinCap: "1500.00",
      marginUsed: "65.00",
      marginAvailable: "935.00",
      riskState: "ATTENTION_409"
    },
    riskLatch: {
      initialDailyEquity: "1018.42",
      currentPnl: "-18.42",
      currentPnlPct: "-1.84",
      softThresholdPct: "-10.00",
      softThresholdVal: "-101.84",
      hardThresholdPct: "-20.00",
      hardThresholdVal: "-203.68",
      cushionToSoft: "83.42",
      latchActive: false,
      latchReason: "NONE"
    },
    bots: [
      {
        id: "bot-hold-01",
        name: "Hold Bot (Stopped with Position)",
        contract: "BTC-USDT-SWAP",
        version: "v1.0.0",
        versionHash: "57fbbba71120098f",
        status: "STOPPED",
        direction: "SHORT",
        positionSize: "1.00",
        positionUnit: "CONT",
        entryPrice: "65000.00",
        markPrice: "65184.20",
        unrealizedPnl: "-18.42",
        pnlPct: "-2.83%",
        leverage: "10.0x",
        margin: "65.00",
        ownershipLocked: true,
        disasterStopPct: "0.0%",
        lastSignalAt: "09:30:00",
        is409Locked: true,
        conflictMsg: "Bot 已停止但仍保留 -1.00 張持倉！合約獨佔未釋放，409 阻擋新案例啟動。"
      }
    ],
    allocation: {
      usedMargin: "65.00",
      freeMargin: "935.00",
      coins: [
        { coin: "BTC", notional: "650.00", pctOfBudget: "21.67%", color: "#f59e0b" },
        { coin: "AVAILABLE", notional: "2350.00", pctOfBudget: "78.33%", color: "#1e293b" }
      ]
    },
    incidents: [
      { id: "inc-409-1", time: "09:35:12", level: "DANGER", title: "409 simulation_ownership_or_risk_retained", desc: "合約 BTC-USDT-SWAP 仍有持倉 (-1.00 張)，拒絕啟動新 Bot。系統禁止隨 Worker 死亡釋放獨佔。" },
      { id: "inc-409-2", time: "09:30:00", level: "WARN", title: "Bot 手動停止但未平倉", desc: "操作員觸發 stop，依據金融不變量不自動市價清倉，部位保留供人工處置。" }
    ],
    research: [],
    yaozi: [],
    attentionItems: [
      {
        id: "att-409",
        level: "urgent",
        title: "409 衝突：Bot hold-01 停用但仍保留 -1 張部位",
        desc: "BTC-USDT-SWAP 合約獨佔未釋放，禁止新案例啟動。系統不自動市價清倉，需由交易員人工處置。",
        action: "人工處置持倉",
        target: "bot-hold-01"
      }
    ]
  },

  recovery: {
    name: "風控警報 / 需人工恢復 (Recovery Required)",
    status: {
      connection: "warning",
      ping: "22ms",
      mode: "localhost",
      supervisor: "ONLINE (LATCHED)",
      workerIsolation: "P1 Python Subprocess",
      storage: "SQLite (WAL)",
      buildId: "f791e202bb000bf2cce06433849fd3c86c8d49e0837cb77545ec73cc5b6d39ee",
      instanceId: "868721f213644b64a81cb88b1a447d3b",
      orderTag: "41cb53c54d6dABDE"
    },
    kpi: {
      totalEquity: "89500.00",
      currency: "USDT",
      equityVerified: "89500.00",
      dailyPnl: "-10500.00",
      dailyPnlPct: "-10.50%",
      dailyCutoff: "Asia/Taipei 00:00",
      activeBots: { running: 1, warning: 1, stopped: 1, total: 3 },
      effectiveLeverage: "2.40",
      maxAllowedLeverage: "3.00",
      totalNotionalExposure: "214800.00",
      totalExposureBudget: "268500.00",
      singleCoinCap: "134250.00",
      marginUsed: "26800.00",
      marginAvailable: "62700.00",
      riskState: "RECOVERY_REQUIRED"
    },
    riskLatch: {
      initialDailyEquity: "100000.00",
      currentPnl: "-10500.00",
      currentPnlPct: "-10.50",
      softThresholdPct: "-10.00",
      softThresholdVal: "-10000.00",
      hardThresholdPct: "-20.00",
      hardThresholdVal: "-20000.00",
      cushionToSoft: "0.00",
      latchActive: true,
      latchReason: "SOFT_DAILY_LOSS_EXCEEDED"
    },
    bots: [
      {
        id: "bot-eth-01",
        name: "ETH Momentum (Exposure Blocked)",
        contract: "ETH-USDT-SWAP",
        version: "v1.1.0",
        versionHash: "7b10fa8894ce3321",
        status: "LATCHED",
        direction: "LONG",
        positionSize: "15.00",
        positionUnit: "ETH",
        entryPrice: "3550.00",
        markPrice: "3380.00",
        unrealizedPnl: "-2550.00",
        pnlPct: "-4.79%",
        leverage: "2.0x",
        margin: "25350.00",
        ownershipLocked: true,
        disasterStopPct: "5.0%",
        lastSignalAt: "10:10:00",
        warningMsg: "日損觸發 Soft 門檻 (-10.5%)，系統鎖存禁止增倉，僅允許合法減倉。"
      }
    ],
    allocation: {
      usedMargin: "26800.00",
      freeMargin: "62700.00",
      coins: [
        { coin: "ETH", notional: "50700.00", pctOfBudget: "18.88%", color: "#8b5cf6" },
        { coin: "AVAILABLE", notional: "217800.00", pctOfBudget: "81.12%", color: "#1e293b" }
      ]
    },
    incidents: [
      { id: "inc-rec-1", time: "10:15:22", level: "DANGER", title: "日損觸發 Soft 門檻 (-10.50%)", desc: "鎖存生效 (LATCH ACTIVE)。當日禁止所有增倉委託，合法減倉始終允許。需人工審核恢復。" },
      { id: "inc-rec-2", time: "10:10:00", level: "WARN", title: "ETH 部位回撤告警", desc: "盤中浮虧擴大至 -2,550 USDT，請檢查保證金水位。" }
    ],
    research: [],
    yaozi: [],
    attentionItems: [
      {
        id: "att-rec",
        level: "urgent",
        title: "日損 Soft 鎖存已觸發 (-10.50%)",
        desc: "依據風控規則，禁止新增曝險，僅允許減倉。日損鎖存跨日/入金不自動重設，需人工核驗後 Re-arm。",
        action: "查看風控鎖存",
        target: "/workspace/risk"
      }
    ]
  }
};
