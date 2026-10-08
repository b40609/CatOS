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
  console.log('Launching headless Edge for Hero Comparison...');
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

  console.log('Waiting for Vue app mount and data render...');
  await sleep(3500);

  // 1. Capture Classic Mode (Default)
  console.log('1. Capturing Classic Hero Mode (CatOS 1:1 Pixel-Perfect)...');
  await capture('hero_compare_01_classic.png');

  // 2. Click Toggle Mode: Legacy
  console.log('2. Switching to Legacy Mode...');
  const switchRes = await evaluate(`
    (() => {
      const btns = Array.from(document.querySelectorAll('.btn-toggle-mode'));
      const legacyBtn = btns.find(b => b.textContent.includes('現有簡化版'));
      if (legacyBtn) {
        legacyBtn.click();
        return 'Clicked legacy button';
      }
      return 'Legacy button not found';
    })()
  `);
  console.log('Switch to Legacy result:', switchRes.result.value);
  await sleep(1000);

  // 3. Capture Legacy Mode
  console.log('3. Capturing Legacy Hero Mode...');
  await capture('hero_compare_02_legacy.png');

  // 4. Switch back to Classic Mode
  console.log('4. Switching back to Classic Mode...');
  await evaluate(`
    (() => {
      const btns = Array.from(document.querySelectorAll('.btn-toggle-mode'));
      const classicBtn = btns.find(b => b.textContent.includes('經典重構'));
      if (classicBtn) classicBtn.click();
    })()
  `);
  await sleep(800);
  console.log('5. Capturing Classic Mode Re-verified...');
  await capture('hero_compare_03_classic_restored.png');

  console.log('All hero comparison screenshots captured successfully!');
  ws.close();
  edge.kill();
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
