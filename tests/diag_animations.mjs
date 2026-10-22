import { spawn } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";

const chromePort = 9452;
const tempProfile = path.join(os.tmpdir(), "catos-diag-e2e-" + Date.now());
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
  await sleep(2000);

  const diag = await send("Runtime.evaluate", {
    expression: `
      (() => {
        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        
        // 檢查光子束
        const beam = document.querySelector('.timeline-photon-beam');
        const beamParent = beam ? beam.parentElement : null;
        const beamRect = beam ? beam.getBoundingClientRect() : null;
        const parentRect = beamParent ? beamParent.getBoundingClientRect() : null;
        const beamStyle = beam ? window.getComputedStyle(beam) : null;
        
        // 檢查聲吶圓點
        const ripple = document.querySelector('.sonar-ripple-amber');
        const rippleStyle = ripple ? window.getComputedStyle(ripple) : null;
        const rippleRect = ripple ? ripple.getBoundingClientRect() : null;

        // 檢查全節點呼吸
        const breathe = document.querySelector('.dot-all-breathe');
        const breatheStyle = breathe ? window.getComputedStyle(breathe) : null;

        return {
          reducedMotion,
          beam: {
            exists: !!beam,
            rect: beamRect ? { width: beamRect.width, height: beamRect.height, top: beamRect.top, left: beamRect.left } : null,
            parentRect: parentRect ? { width: parentRect.width, height: parentRect.height } : null,
            animation: beamStyle ? beamStyle.animation : null,
            animationName: beamStyle ? beamStyle.animationName : null,
            display: beamStyle ? beamStyle.display : null,
            visibility: beamStyle ? beamStyle.visibility : null,
          },
          ripple: {
            exists: !!ripple,
            rect: rippleRect ? { width: rippleRect.width, height: rippleRect.height } : null,
            animation: rippleStyle ? rippleStyle.animation : null,
            animationName: rippleStyle ? rippleStyle.animationName : null,
          },
          breathe: {
            exists: !!breathe,
            animation: breatheStyle ? breatheStyle.animation : null,
            animationName: breatheStyle ? breatheStyle.animationName : null,
          }
        };
      })()
    `,
    returnByValue: true,
  });

  console.log("DIAGNOSTIC REPORT:", JSON.stringify(diag.result?.result?.value || diag.result?.value, null, 2));

  pageWs.close();
  chromeProcess.kill();
}

run().catch(console.error);
