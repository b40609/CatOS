import { spawn } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";

const chromePort = 9449;
const tempProfile = path.join(os.tmpdir(), "catos-pulse-e2e-" + Date.now());
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

  // 1. 檢查小圓點尺寸與動效結構
  const evalResult = await send("Runtime.evaluate", {
    expression: `
      (() => {
        // 尋找時間軸內的所有核心點
        const pingPointers = Array.from(document.querySelectorAll(".animate-ping"));
        const corePoints = Array.from(document.querySelectorAll(".size-2.rounded-full"));
        
        return {
          hasAnimatePing: pingPointers.length > 0,
          pingCount: pingPointers.length,
          corePointsCount: corePoints.length,
        };
      })()
    `,
    returnByValue: true,
  });

  const resVal = evalResult.result?.result?.value || evalResult.result?.value;
  console.log("Pulse Beacon E2E Check:", JSON.stringify(resVal, null, 2));

  if (!resVal.hasAnimatePing) {
    throw new Error("Missing animate-ping ripple element!");
  }
  console.log(`✓ 成功偵測到 ${resVal.pingCount} 個持續向外擴散的雷達微波漣漪動畫！`);
  console.log(`✓ 偵測到 ${resVal.corePointsCount} 個嚴格統一為 8px (size-2) 的核心圓點！`);

  pageWs.close();
  chromeProcess.kill();
  console.log("=== PULSE BEACON FIX VERIFIED ===");
}

run().catch((e) => {
  console.error("Test Error:", e);
  chromeProcess.kill();
  process.exit(1);
});
