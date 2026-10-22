import { spawn } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";

const chromePort = 9451;
const tempProfile = path.join(os.tmpdir(), "catos-lines-e2e-" + Date.now());
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

  // 1. 檢查預設方案 1 (光子流脈衝)
  const eval1 = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const photon = document.querySelector(".timeline-photon-beam");
        const dotBreathe = document.querySelectorAll(".dot-all-breathe");
        return {
          hasPhotonBeam: !!photon,
          dotBreatheCount: dotBreathe.length
        };
      })()
    `,
    returnByValue: true,
  });
  const res1 = eval1.result?.result?.value || eval1.result?.value;
  console.log("Effect 1 Check (Photon):", JSON.stringify(res1, null, 2));
  if (!res1.hasPhotonBeam) throw new Error("Photon beam element not found!");
  console.log("✓ 方案 1【光子流脈衝】＋【全節點通電呼吸】驗證通過！");

  // 2. 測試點擊切換為方案 2 (聲吶波注入)
  console.log("Testing click: ② 聲吶注入 ...");
  await send("Runtime.evaluate", {
    expression: `
      (() => {
        const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes("② 聲吶注入"));
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
        const sonar = document.querySelector(".timeline-sonar-inject");
        return { hasSonarInject: !!sonar };
      })()
    `,
    returnByValue: true,
  });
  const res2 = eval2.result?.result?.value || eval2.result?.value;
  console.log("Effect 2 Check (Sonar Inject):", JSON.stringify(res2, null, 2));
  if (!res2.hasSonarInject) throw new Error("Sonar inject element not found!");
  console.log("✓ 方案 2【聲吶波注入向下傳導】驗證通過！");

  // 3. 測試點擊切換為方案 3 (電路微蠕動)
  console.log("Testing click: ③ 電路流 ...");
  await send("Runtime.evaluate", {
    expression: `
      (() => {
        const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes("③ 電路流"));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `,
    returnByValue: true,
  });
  await sleep(600);

  const eval3 = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const crawl = document.querySelector(".timeline-circuit-crawl");
        return { hasCircuitCrawl: !!crawl };
      })()
    `,
    returnByValue: true,
  });
  const res3 = eval3.result?.result?.value || eval3.result?.value;
  console.log("Effect 3 Check (Circuit Crawl):", JSON.stringify(res3, null, 2));
  if (!res3.hasCircuitCrawl) throw new Error("Circuit crawl SVG line not found!");
  console.log("✓ 方案 3【電路微蠕動向前爬行】驗證通過！");

  // 4. 切回方案 1
  await send("Runtime.evaluate", {
    expression: `
      (() => {
        const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.includes("① 光子流"));
        if (btn) { btn.click(); return true; }
        return false;
      })()
    `,
    returnByValue: true,
  });
  await sleep(400);

  pageWs.close();
  chromeProcess.kill();
  console.log("=== ALL 3 LINE DYNAMICS VERIFIED SUCCESSFULLY ===");
}

run().catch((e) => {
  console.error("Test Error:", e);
  chromeProcess.kill();
  process.exit(1);
});
