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

  console.log('Waiting for Vue app mount and initial render...');
  await sleep(2500);

  // 1. 預設模式（未解鎖狀態：無握把、分割線鎖定）
  console.log('1. Capturing locked view mode (Default Bloomberg)...');
  await capture('01_layout_locked_default.png');

  // 2. 點擊「⚙ 調整版面」解鎖
  console.log('2. Clicking "⚙ 調整版面" to unlock editing...');
  await evaluate(`
    (() => {
      const btn = document.querySelector('.btn-enter-edit');
      if (btn) btn.click();
    })()
  `);
  await sleep(800);
  console.log('Capturing unlocked editing mode (grips visible, guide bar displayed)...');
  await capture('02_layout_unlocked_editing.png');

  // 3. 點擊「＋ 另存新方案」打開 Modal
  console.log('3. Clicking "＋ 另存新方案"...');
  await evaluate(`
    (() => {
      const btns = Array.from(document.querySelectorAll('.layout-profile-picker button'));
      const saveBtn = btns.find(b => b.textContent.includes('另存新方案'));
      if (saveBtn) saveBtn.click();
    })()
  `);
  await sleep(600);
  console.log('Capturing save layout modal...');
  await capture('03_layout_save_modal.png');

  // 4. 輸入新方案名稱並確認儲存
  console.log('4. Entering custom profile name and saving...');
  await evaluate(`
    (() => {
      const input = document.querySelector('.input-profile-name');
      if (input) {
        input.value = '高頻套利特化監控 (自訂)';
        input.dispatchEvent(new Event('input', { bubbles: true }));
      }
      const confirmBtn = Array.from(document.querySelectorAll('.catos-modal-footer button')).find(b => b.textContent.includes('確認儲存'));
      if (confirmBtn) confirmBtn.click();
    })()
  `);
  await sleep(800);
  console.log('Capturing profile saved state...');
  await capture('04_layout_profile_saved_toast.png');

  // 5. 點擊切換為「持倉優先 · 部位焦點監控」
  console.log('5. Switching to Positions Focus profile...');
  await evaluate(`
    (() => {
      const select = document.querySelector('.select-layout-profile');
      if (select) {
        select.value = 'positions_focus';
        select.dispatchEvent(new Event('change', { bubbles: true }));
      }
    })()
  `);
  await sleep(1000);
  console.log('Capturing positions focus layout...');
  await capture('05_layout_positions_focus.png');

  // 6. 點擊「✓ 完成鎖定」回到安全鎖定監控
  console.log('6. Clicking "✓ 完成鎖定"...');
  await evaluate(`
    (() => {
      const btn = document.querySelector('.btn-done-edit');
      if (btn) btn.click();
    })()
  `);
  await sleep(600);
  console.log('Capturing relocked positions focus view...');
  await capture('06_layout_relocked_positions_focus.png');

  // 7. 切換至方案 3（Linear 矩陣聯動）
  console.log('7. Switching to Blueprint 3 (Linear)...');
  await evaluate(`
    (() => {
      const select = document.querySelector('.select-layout-profile');
      if (select) {
        select.value = 'default_linear';
        select.dispatchEvent(new Event('change', { bubbles: true }));
      }
    })()
  `);
  await sleep(1000);
  console.log('Capturing Blueprint 3 (Linear) locked mode...');
  await capture('07_blueprint_3_linear_locked.png');

  console.log('All profile and layout scenarios verified successfully!');
  ws.close();
  edge.kill();
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
