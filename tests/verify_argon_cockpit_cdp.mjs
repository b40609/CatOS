import { spawn } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";

const chromePort = 9445;
const tempProfile = path.join(os.tmpdir(), "catos-argon-e2e-" + Date.now());
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

  // 1. 執行 DOM 查詢評估
  const evalResult = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const text = document.body.innerText;
        return {
          hasArgonBtn: text.includes("★ Argon 旗艦終端"),
          hasSupOnline: text.includes("SUP: ONLINE"),
          hasEquity: text.includes("$12,480.00"),
          hasPnl: text.includes("+$294.54"),
          hasMatrix: text.includes("全息部位與意圖矩陣"),
          hasTriage: text.includes("異常處置與風控鎖存台"),
          hasDock: text.includes("即時成交流水 (含滑價歸因)"),
          hasUnknownDelta: text.includes("Diff: +0.60 ETH (1 UNKNOWN 待對帳)"),
          hasP6Guard: text.includes("OK $59.5k")
        };
      })()
    `,
    returnByValue: true,
  });

  const checks = evalResult.result?.result?.value || evalResult.result?.value || evalResult;
  console.log("Argon Cockpit Verification Results:", JSON.stringify(checks, null, 2));

  for (const [key, passed] of Object.entries(checks)) {
    if (!passed) {
      throw new Error(`Assertion failed: ${key} is false!`);
    }
  }
  console.log("✓ Argon 駕駛艙全要素驗證 100% 通過！");

  // 2. 測試切換回經典 5 卡佈局 (點擊 ③ 5 卡收斂版)
  console.log("Testing click: ③ 5 卡收斂版 ...");
  await send("Runtime.evaluate", {
    expression: `
      (() => {
        const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes("③ 5 卡收斂版"));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `,
    returnByValue: true,
  });
  await sleep(1000);

  const checkClassic = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const text = document.body.innerText;
        return {
          hasClassicPositions: text.includes("持倉明細與在途委託"),
          hasClassicDeck: text.includes("交易日誌與風險事件"),
          hasClassicBots: text.includes("策略機器人矩陣"),
        };
      })()
    `,
    returnByValue: true,
  });

  console.log("Classic Layout Verification:", JSON.stringify(checkClassic.result.value, null, 2));
  const classicVal = checkClassic.result?.result?.value || checkClassic.result?.value;
  for (const [key, passed] of Object.entries(classicVal)) {
    if (!passed) {
      throw new Error(`Classic layout assertion failed: ${key} is false!`);
    }
  }
  console.log("✓ 舊版 5 卡定案版面 (T-Split) 100% 完整保留，切換自如！");

  // 3. 測試點擊切回 ★ Argon 旗艦終端
  console.log("Testing click: ★ Argon 旗艦終端 ...");
  await send("Runtime.evaluate", {
    expression: `
      (() => {
        const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes("★ Argon 旗艦終端"));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `,
    returnByValue: true,
  });
  await sleep(1000);

  const checkArgonAgain = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const text = document.body.innerText;
        return text.includes("全息部位與意圖矩陣") && text.includes("異常處置與風控鎖存台");
      })()
    `,
    returnByValue: true,
  });

  const againVal = checkArgonAgain.result?.result?.value || checkArgonAgain.result?.value;
  if (!againVal) {
    throw new Error("Failed to switch back to Argon Cockpit!");
  }
  console.log("✓ 成功切回 ★ Argon 旗艦終端！");

  pageWs.close();
  chromeProcess.kill();
  console.log("=== ALL E2E CDP TESTS PASSED ===");
}

run().catch((e) => {
  console.error("Test Error:", e);
  chromeProcess.kill();
  process.exit(1);
});
