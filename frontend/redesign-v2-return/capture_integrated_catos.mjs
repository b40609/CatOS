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
  console.log('Launching headless Edge for Integrated Cat-OS test...');
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

  console.log('Navigating to http://127.0.0.1:8910/#/ ...');
  await sendCommand('Page.navigate', { url: 'http://127.0.0.1:8910/#/' });

  console.log('Waiting for Vue app mount and iframe render...');
  await sleep(4000);

  // 1. Capture Integrated Native Cat-OS Workstation (Default Blueprint)
  console.log('1. Capturing Integrated Cat-OS Workstation (Default Blueprint)...');
  await capture('catos_integrated_01_default.png');

  // 2. Click Blueprint 1: Bloomberg
  console.log('2. Switching to Scheme 1 (Bloomberg)...');
  await evaluate(`
    (() => {
      const btns = Array.from(document.querySelectorAll('.btn-bp-switch'));
      const bbgBtn = btns.find(b => b.textContent.includes('Bloomberg'));
      if (bbgBtn) bbgBtn.click();
    })()
  `);
  await sleep(1000);
  console.log('Capturing Scheme 1 (Bloomberg)...');
  await capture('catos_integrated_02_bloomberg.png');

  // 3. Switch back to CatOS Native Workstation
  console.log('3. Switching back to CatOS Native Workstation...');
  await evaluate(`
    (() => {
      const btns = Array.from(document.querySelectorAll('.btn-bp-switch'));
      const catosBtn = btns.find(b => b.textContent.includes('CatOS 原版工作站'));
      if (catosBtn) catosBtn.click();
    })()
  `);
  await sleep(1500);
  console.log('Capturing CatOS Native Workstation restored...');
  await capture('catos_integrated_03_catos_restored.png');

  console.log('All integrated verification screenshots captured successfully!');
  ws.close();
  edge.kill();
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
