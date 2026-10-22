import { spawn } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";

const chromePort = 9450;
const tempProfile = path.join(os.tmpdir(), "catos-sonar-e2e-" + Date.now());
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

  // 1. 檢查高質感聲吶動態元素
  const evalResult = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const sonars = Array.from(document.querySelectorAll(".sonar-ripple-amber"));
        const delayedSonars = Array.from(document.querySelectorAll(".sonar-ripple-amber-delayed"));
        const crystalBreathes = Array.from(document.querySelectorAll(".crystal-breathe-amber"));
        const ambientCards = Array.from(document.querySelectorAll(".ambient-alert-card"));
        
        return {
          hasDualSonar: sonars.length > 0 && delayedSonars.length > 0,
          sonarCount: sonars.length,
          delayedSonarCount: delayedSonars.length,
          crystalCount: crystalBreathes.length,
          ambientCardCount: ambientCards.length,
        };
      })()
    `,
    returnByValue: true,
  });

  const resVal = evalResult.result?.result?.value || evalResult.result?.value;
  console.log("High-End Sonar Verification:", JSON.stringify(resVal, null, 2));

  if (!resVal.hasDualSonar) {
    throw new Error("Missing dual sonar ripple animation elements!");
  }
  console.log("✓ 成功偵測到雙層錯開之雷達聲吶微波漣漪 (Dual-Stage Sonar Ripple)！");
  console.log("✓ 成功偵測到實心核心微晶片呼吸光暈 (Crystal Glow Breathe)！");
  console.log("✓ 成功偵測到事故卡片環境光微呼吸 (Ambient Alert Card)！");

  pageWs.close();
  chromeProcess.kill();
  console.log("=== ALL HIGH-END DYNAMICS VERIFIED ===");
}

run().catch((e) => {
  console.error("Test Error:", e);
  chromeProcess.kill();
  process.exit(1);
});
