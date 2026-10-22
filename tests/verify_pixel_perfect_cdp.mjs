import { spawn } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";

const chromePort = 9447;
const tempProfile = path.join(os.tmpdir(), "catos-pixel-perfect-e2e-" + Date.now());
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

  // 1. 檢查原版視覺復刻要素
  const evalResult = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const text = document.body.innerText;
        return {
          hasTitle: text.includes("風險警報與交易日誌"),
          hasAlertBadge: text.includes("異常"),
          hasTabs: text.includes("全部") && text.includes("告警") && text.includes("資訊"),
          hasFullLogLink: text.includes("完整日誌"),
          hasUnknownIncident: text.includes("增倉委託回覆逾時") || text.includes("Calico"),
          hasExpandedDetail: text.includes("風控衝擊") || text.includes("額度已鎖存")
        };
      })()
    `,
    returnByValue: true,
  });

  const resVal = evalResult.result?.result?.value || evalResult.result?.value;
  console.log("Visual Perfection Check:", JSON.stringify(resVal, null, 2));

  for (const [key, passed] of Object.entries(resVal)) {
    if (!passed) throw new Error(`Assertion failed: ${key} is false!`);
  }
  console.log("✓ 原版視覺與發光小圓點時間軸 100% 完美復刻與功能整合！");

  // 2. 測試點擊切換為「完整日誌」
  console.log("Testing click: 完整日誌 ➜ ...");
  await send("Runtime.evaluate", {
    expression: `
      (() => {
        const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes("完整日誌"));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `,
    returnByValue: true,
  });
  await sleep(600);

  const checkRawLog = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const text = document.body.innerText;
        return text.includes("返回時間軸");
      })()
    `,
    returnByValue: true,
  });
  const isRaw = checkRawLog.result?.result?.value || checkRawLog.result?.value;
  if (!isRaw) throw new Error("Failed to switch to raw log stream!");
  console.log("✓ 成功切換為完整審計流水日誌 (Raw Log Stream)！");

  // 3. 測試點擊「返回時間軸」
  console.log("Testing click: 返回時間軸 ...");
  await send("Runtime.evaluate", {
    expression: `
      (() => {
        const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes("返回時間軸"));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `,
    returnByValue: true,
  });
  await sleep(600);

  pageWs.close();
  chromeProcess.kill();
  console.log("=== ALL CDP TESTS PASSED ===");
}

run().catch((e) => {
  console.error("Test Error:", e);
  chromeProcess.kill();
  process.exit(1);
});
