import { spawn } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";

const chromePort = 9446;
const tempProfile = path.join(os.tmpdir(), "catos-unified-e2e-" + Date.now());
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

  // 1. 檢查合併後的卡片標題與 3 大方案切換按鈕
  const checkInitial = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const text = document.body.innerText;
        return {
          hasCardTitle: text.includes("全域事件與風險日誌"),
          hasVariantA: text.includes("A. Linear 流線型"),
          hasVariantB: text.includes("B. Datadog 置頂型"),
          hasVariantC: text.includes("C. Bloomberg 雙層型"),
          hasAccordionDetail: text.includes("風控衝擊") || text.includes("額度已鎖存"),
          hasUnknownTitle: text.includes("增倉委託回覆逾時") || text.includes("Calico")
        };
      })()
    `,
    returnByValue: true,
  });

  const resVal = checkInitial.result?.result?.value || checkInitial.result?.value;
  console.log("Unified Card Initial Check (Variant A):", JSON.stringify(resVal, null, 2));
  for (const [key, passed] of Object.entries(resVal)) {
    if (!passed) throw new Error(`Assertion failed: ${key} is false!`);
  }
  console.log("✓ 方案 A (Linear 流線時間軸 + 小圓點 + 手風琴展開) 驗證通過！");

  // 2. 測試切換至方案 B (Datadog 置頂型)
  console.log("Testing click: B. Datadog 置頂型 ...");
  await send("Runtime.evaluate", {
    expression: `
      (() => {
        const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes("B. Datadog 置頂型"));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `,
    returnByValue: true,
  });
  await sleep(600);

  const checkB = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const text = document.body.innerText;
        return {
          hasStickyGroup: text.includes("未解除異常待處置"),
          hasHighPriority: text.includes("高優先級")
        };
      })()
    `,
    returnByValue: true,
  });
  const resB = checkB.result?.result?.value || checkB.result?.value;
  console.log("Variant B Check:", JSON.stringify(resB, null, 2));
  if (!resB.hasStickyGroup) throw new Error("Variant B sticky group missing!");
  console.log("✓ 方案 B (Datadog 置頂異常卡片 + 時間軸) 驗證通過！");

  // 3. 測試切換至方案 C (Bloomberg 雙層型)
  console.log("Testing click: C. Bloomberg 雙層型 ...");
  await send("Runtime.evaluate", {
    expression: `
      (() => {
        const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes("C. Bloomberg 雙層型"));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `,
    returnByValue: true,
  });
  await sleep(600);

  const checkC = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const text = document.body.innerText;
        return {
          hasStatusStrip: text.includes("異常狀態：")
        };
      })()
    `,
    returnByValue: true,
  });
  const resC = checkC.result?.result?.value || checkC.result?.value;
  console.log("Variant C Check:", JSON.stringify(resC, null, 2));
  if (!resC.hasStatusStrip) throw new Error("Variant C status strip missing!");
  console.log("✓ 方案 C (Bloomberg 雙層終端分割) 驗證通過！");

  // 4. 切回方案 A
  await send("Runtime.evaluate", {
    expression: `
      (() => {
        const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes("A. Linear 流線型"));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `,
    returnByValue: true,
  });
  await sleep(400);

  pageWs.close();
  chromeProcess.kill();
  console.log("=== ALL UNIFIED CARD E2E TESTS PASSED ===");
}

run().catch((e) => {
  console.error("Test Error:", e);
  chromeProcess.kill();
  process.exit(1);
});
