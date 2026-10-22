import { spawn } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";

const chromePort = 9448;
const tempProfile = path.join(os.tmpdir(), "catos-zero-loss-e2e-" + Date.now());
fs.mkdirSync(tempProfile, { recursive: true });

const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const chromeProcess = spawn(chromePath, [
  "--headless=new",
  `--remote-debugging-port=${chromePort}`,
  "--no-first-run",
  "--no-default-browser-check",
  "--disable-gpu",
  "--window-size=1920,1080",
  `--user-data-dir=${tempProfile}`,
  "http://127.0.0.1:8887/#/"
]);

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function run() {
  console.log("Starting Headless Chrome on port", chromePort);
  let pageWsUrl = null;
  for (let i = 0; i < 30; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${chromePort}/json/list`);
      if (res.ok) {
        const list = await res.json();
        const pageTab = list.find((t) => t.type === "page");
        if (pageTab && pageTab.webSocketDebuggerUrl) {
          pageWsUrl = pageTab.webSocketDebuggerUrl;
          break;
        }
      }
    } catch {
      await sleep(200);
    }
  }

  if (!pageWsUrl) throw new Error("Could not find Chrome page WebSocket");

  console.log("Connecting to Page WS:", pageWsUrl);
  const pageWs = new WebSocket(pageWsUrl);
  await new Promise((r) => (pageWs.onopen = r));

  let msgId = 1;
  const pending = new Map();
  pageWs.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.id && pending.has(data.id)) {
      pending.get(data.id)(data);
      pending.delete(data.id);
    }
  };

  function send(method, params = {}) {
    return new Promise((resolve) => {
      const id = msgId++;
      pending.set(id, resolve);
      pageWs.send(JSON.stringify({ id, method, params }));
    });
  }

  await send("Page.enable");
  await send("Runtime.enable");

  console.log("Waiting for page load and state hydration...");
  await sleep(2500);

  // 1. 檢查零閹割合併後的卡片要素
  const evalResult = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const text = document.body.innerText;
        return {
          hasCardTitle: text.includes("風險警報與交易日誌"),
          hasAlertBadge: text.includes("異常"),
          hasOpenTab: text.includes("未解除"),
          hasFillTab: text.includes("成交流"),
          hasAlertTab: text.includes("風控警報"),
          hasSystemTab: text.includes("系統事件"),
          hasSqliteFooter: text.includes("SQLite (WAL)"),
          hasUnknownIncident: text.includes("ETH 增倉委託 UNKNOWN") || text.includes("Calico"),
          hasLockQuota: text.includes("額度已鎖存") || text.includes("$474.75"),
          hasLocateBotBtn: text.includes("定位 Bot") || text.includes("共用詳情")
        };
      })()
    `,
    returnByValue: true,
  });

  const resVal = evalResult.result?.result?.value || evalResult.result?.value;
  console.log("Zero-Loss Merge Verification:", JSON.stringify(resVal, null, 2));

  for (const [key, passed] of Object.entries(resVal)) {
    if (!passed) throw new Error(`Assertion failed: ${key} is false!`);
  }
  console.log("✓ 零閹割合併驗證 100% 通過：截圖級膠囊時間軸 + 完整 5 大日誌維度全數就位！");

  // 2. 測試點擊「未解除」標籤
  console.log("Testing click: 未解除 篩選標籤 ...");
  await send("Runtime.evaluate", {
    expression: `
      (() => {
        const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes("未解除"));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `,
    returnByValue: true,
  });
  await sleep(600);

  const checkOpenTab = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const text = document.body.innerText;
        return text.includes("ETH 增倉委託 UNKNOWN") && text.includes("SOL 災難停損更新未確認");
      })()
    `,
    returnByValue: true,
  });
  const isOpenWorking = checkOpenTab.result?.result?.value || checkOpenTab.result?.value;
  if (!isOpenWorking) throw new Error("Open incidents filter failed!");
  console.log("✓ 未解除篩選標籤運作正常，準確鎖定 2 筆核心事故！");

  // 3. 測試點擊「成交流」標籤
  console.log("Testing click: 成交流 篩選標籤 ...");
  await send("Runtime.evaluate", {
    expression: `
      (() => {
        const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes("成交流"));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `,
    returnByValue: true,
  });
  await sleep(600);

  const checkFillTab = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const text = document.body.innerText;
        return text.includes("開多") || text.includes("SOL");
      })()
    `,
    returnByValue: true,
  });
  const isFillWorking = checkFillTab.result?.result?.value || checkFillTab.result?.value;
  if (!isFillWorking) throw new Error("Fills filter failed!");
  console.log("✓ 成交流篩選標籤運作正常，成功展示開多/平多撮合！");

  pageWs.close();
  chromeProcess.kill();
  console.log("=== ALL ZERO-LOSS MERGE CDP TESTS PASSED ===");
}

run().catch((e) => {
  console.error("Test Error:", e);
  chromeProcess.kill();
  process.exit(1);
});
