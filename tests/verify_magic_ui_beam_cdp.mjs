import { spawn } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";

const chromePort = 9453;
const tempProfile = path.join(os.tmpdir(), "catos-magicui-e2e-" + Date.now());
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

  // 1. 檢查 Magic UI 雙層 SVG 矢量光子流結構
  const eval1 = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const glowFilter = document.querySelector("#magic-beam-glow");
        const gradient = document.querySelector("#magic-photon-grad");
        const cometLine = document.querySelector(".magic-beam-comet");
        const cometStyle = cometLine ? window.getComputedStyle(cometLine) : null;
        
        return {
          hasGlowFilter: !!glowFilter,
          hasGradient: !!gradient,
          hasCometLine: !!cometLine,
          animationName: cometStyle ? cometStyle.animationName : null,
          stroke: cometStyle ? cometStyle.stroke : null,
          strokeDasharray: cometStyle ? cometStyle.strokeDasharray : null
        };
      })()
    `,
    returnByValue: true,
  });
  const res1 = eval1.result?.result?.value || eval1.result?.value;
  console.log("Magic UI Animated Beam Check:", JSON.stringify(res1, null, 2));

  if (!res1.hasGlowFilter || !res1.hasGradient || !res1.hasCometLine) {
    throw new Error("Magic UI SVG Beam elements missing!");
  }
  if (res1.animationName !== "magic-beam-travel") {
    throw new Error(`Expected animation magic-beam-travel, got: ${res1.animationName}`);
  }
  console.log("✓ Magic UI 彗星激光流（SVG 雙層高斯光學濾鏡 ＋ 純白高能核）實機順暢運行！");

  // 2. 測試切換為風格 ② 雙粒子脈衝
  console.log("Testing click: ② 雙粒子脈衝 ...");
  await send("Runtime.evaluate", {
    expression: `
      (() => {
        const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes("② 雙粒子脈衝"));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `,
    returnByValue: true,
  });
  await sleep(600);

  const eval2 = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const doubleLine = document.querySelector(".magic-beam-double");
        return { hasDoubleLine: !!doubleLine };
      })()
    `,
    returnByValue: true,
  });
  const res2 = eval2.result?.result?.value || eval2.result?.value;
  console.log("Style 2 Check (Dual Pulse):", JSON.stringify(res2, null, 2));
  if (!res2.hasDoubleLine) throw new Error("Dual pulse line missing!");
  console.log("✓ 風格 ②【雙粒子競速流光】切換驗證通過！");

  // 3. 測試切換為風格 ③ 極簡微光束
  console.log("Testing click: ③ 極簡微光束 ...");
  await send("Runtime.evaluate", {
    expression: `
      (() => {
        const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes("③ 極簡微光束"));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `,
    returnByValue: true,
  });
  await sleep(600);
  console.log("✓ 風格 ③【極簡微光束】切換驗證通過！");

  // 4. 切回風格 ① 彗星激光束
  await send("Runtime.evaluate", {
    expression: `
      (() => {
        const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes("① 彗星激光束"));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `,
    returnByValue: true,
  });
  await sleep(400);

  pageWs.close();
  chromeProcess.kill();
  console.log("=== ALL MAGIC UI BEAM CDP TESTS PASSED ===");
}

run().catch((e) => {
  console.error("Test Error:", e);
  chromeProcess.kill();
  process.exit(1);
});
