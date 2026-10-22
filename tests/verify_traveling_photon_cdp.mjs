import { spawn } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";

const chromePort = 9454;
const tempProfile = path.join(os.tmpdir(), "catos-traveling-e2e-" + Date.now());
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

  // 1. 測量時間點 T1 的光子 Y 軸座標
  const sample1 = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const runner = document.querySelector(".photon-run-single");
        if (!runner) return null;
        const rect = runner.getBoundingClientRect();
        return { top: rect.top, left: rect.left, width: rect.width, height: rect.height };
      })()
    `,
    returnByValue: true,
  });
  const pos1 = sample1.result?.result?.value || sample1.result?.value;
  console.log("T1 Runner Position:", JSON.stringify(pos1, null, 2));

  // 等待 500 毫秒
  await sleep(500);

  // 2. 測量時間點 T2 的光子 Y 軸座標
  const sample2 = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const runner = document.querySelector(".photon-run-single");
        if (!runner) return null;
        const rect = runner.getBoundingClientRect();
        return { top: rect.top, left: rect.left, width: rect.width, height: rect.height };
      })()
    `,
    returnByValue: true,
  });
  const pos2 = sample2.result?.result?.value || sample2.result?.value;
  console.log("T2 Runner Position:", JSON.stringify(pos2, null, 2));

  if (!pos1 || !pos2) {
    throw new Error("Runner element not found in DOM!");
  }

  const deltaY = Math.abs(pos2.top - pos1.top);
  console.log(`Displacement Delta Y = ${deltaY.toFixed(2)} px`);

  if (deltaY < 5) {
    throw new Error("Photon runner is stationary or not displacing!");
  }

  console.log("✓ 成功驗證：光子能量球在時間軸上真真切切地產生 Y 軸位移奔跑（非原地閃爍）！");

  // 3. 測試切換至模式 ② 往返巡邏
  console.log("Testing click: ② 往返巡邏 ...");
  await send("Runtime.evaluate", {
    expression: `
      (() => {
        const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes("② 往返巡邏"));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `,
    returnByValue: true,
  });
  await sleep(600);

  const evalBounce = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const bounce = document.querySelector(".photon-run-bounce");
        return { hasBounce: !!bounce };
      })()
    `,
    returnByValue: true,
  });
  const resBounce = evalBounce.result?.result?.value || evalBounce.result?.value;
  console.log("Bounce Check:", JSON.stringify(resBounce, null, 2));
  if (!resBounce.hasBounce) throw new Error("Bounce runner element missing!");
  console.log("✓ 模式 ②【往返巡邏】切換驗證通過！");

  // 4. 切回模式 ① 單向穿梭
  await send("Runtime.evaluate", {
    expression: `
      (() => {
        const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes("① 單向穿梭"));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `,
    returnByValue: true,
  });
  await sleep(400);

  pageWs.close();
  chromeProcess.kill();
  console.log("=== ALL TRAVELING RUNNER TESTS PASSED ===");
}

run().catch((e) => {
  console.error("Test Error:", e);
  chromeProcess.kill();
  process.exit(1);
});
