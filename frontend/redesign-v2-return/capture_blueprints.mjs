import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

const ARTIFACTS_DIR = 'C:\\Users\\user\\.gemini\\antigravity-ide\\brain\\6989ecc5-1388-42ea-b729-f86dd19c5b68';
const EDGE_PATH = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const USER_DATA = path.join(ARTIFACTS_DIR, 'edge_temp_profile');

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function run() {
  console.log('Launching headless Edge...');
  const edge = spawn(EDGE_PATH, [
    '--remote-debugging-port=9222',
    '--headless=new',
    '--disable-gpu',
    `--user-data-dir=${USER_DATA}`,
    '--window-size=1920,1080',
    'http://127.0.0.1:8910/#/'
  ]);

  let wsUrl = null;
  for (let i = 0; i < 20; i++) {
    await sleep(500);
    try {
      const res = await fetch('http://127.0.0.1:9222/json/list');
      const list = await res.json();
      if (list && list.length > 0 && list[0].webSocketDebuggerUrl) {
        wsUrl = list[0].webSocketDebuggerUrl;
        break;
      }
    } catch (e) {}
  }

  if (!wsUrl) {
    console.error('Failed to get CDP WebSocket URL');
    edge.kill();
    process.exit(1);
  }

  console.log('Connecting to CDP:', wsUrl);
  const ws = new WebSocket(wsUrl);

  await new Promise(r => ws.onopen = r);

  let idCounter = 1;
  function sendCommand(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = idCounter++;
      const handler = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.id === id) {
          ws.removeEventListener('message', handler);
          if (msg.error) reject(msg.error);
          else resolve(msg.result);
        }
      };
      ws.addEventListener('message', handler);
      ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async function capture(filename) {
    const res = await sendCommand('Page.captureScreenshot', { format: 'png' });
    const buffer = Buffer.from(res.data, 'base64');
    const outPath = path.join(ARTIFACTS_DIR, filename);
    fs.writeFileSync(outPath, buffer);
    console.log(`Saved screenshot: ${outPath} (${buffer.length} bytes)`);
    return outPath;
  }

  async function evaluate(expression) {
    return sendCommand('Runtime.evaluate', { expression, returnByValue: true });
  }

  console.log('Waiting for Vue app mount and data render...');
  await sleep(2500);

  // 1. Capture Blueprint 1: Bloomberg + Donut (Default Favorite)
  console.log('Capturing Scheme 1 (Bloomberg) with Donut Chart...');
  await capture('scheme_1_bloomberg_donut.png');

  // 2. Click Top Allocation Mode: Meter Bar
  console.log('Switching to Allocation Mode: Meter Bar...');
  await evaluate(`
    (() => {
      const btns = Array.from(document.querySelectorAll('.btn-alloc-mode'));
      const meterBtn = btns.find(b => b.textContent.includes('多空標尺'));
      if (meterBtn) meterBtn.click();
    })()
  `);
  await sleep(800);
  console.log('Capturing Scheme 1 (Bloomberg) with Meter Bar...');
  await capture('scheme_1_bloomberg_meter.png');

  // 3. Click Top Allocation Mode: Matrix
  console.log('Switching to Allocation Mode: Matrix...');
  await evaluate(`
    (() => {
      const btns = Array.from(document.querySelectorAll('.btn-alloc-mode'));
      const matrixBtn = btns.find(b => b.textContent.includes('資產矩陣'));
      if (matrixBtn) matrixBtn.click();
    })()
  `);
  await sleep(800);
  console.log('Capturing Scheme 1 (Bloomberg) with Asset Matrix...');
  await capture('scheme_1_bloomberg_matrix.png');

  // 4. Switch back to Donut, then switch to Scheme 3 (Linear)
  console.log('Switching to Scheme 3 (Linear Matrix) + Donut Chart...');
  await evaluate(`
    (() => {
      // 換回 Donut
      const allocBtns = Array.from(document.querySelectorAll('.btn-alloc-mode'));
      const donutBtn = allocBtns.find(b => b.textContent.includes('Donut'));
      if (donutBtn) donutBtn.click();

      // 切換方案 3 Linear
      const bpBtns = Array.from(document.querySelectorAll('.btn-bp-switch'));
      const linearBtn = bpBtns.find(b => b.textContent.includes('方案 3') || b.textContent.includes('Linear'));
      if (linearBtn) linearBtn.click();
    })()
  `);
  await sleep(1000);
  console.log('Capturing Scheme 3 (Linear Matrix) with Donut Chart...');
  await capture('scheme_3_linear_donut.png');

  console.log('All blueprints captured successfully!');
  ws.close();
  edge.kill();
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
