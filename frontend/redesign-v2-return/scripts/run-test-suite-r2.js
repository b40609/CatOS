import { spawn, execSync } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '../');

const evidenceDir = path.resolve(projectRoot, 'evidence/local-resume-20261005-r2');
fs.mkdirSync(evidenceDir, { recursive: true });

const TEST_PORT = 8902;
const TEST_HOST = '127.0.0.1';

function checkPort(port) {
  try {
    const out = execSync(`pwsh -Command "Get-NetTCPConnection -LocalPort ${port} -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"`, { encoding: 'utf-8' });
    const pids = out.split('\n').map(l => l.trim()).filter(Boolean);
    return pids.length > 0 ? pids : null;
  } catch {
    return null;
  }
}

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function waitForPort(port, maxWaitMs = 10000) {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    const pids = checkPort(port);
    if (pids) return pids;
    await sleep(200);
  }
  throw new Error(`Port ${port} did not become active within ${maxWaitMs}ms`);
}

async function main() {
  console.log('=== Step 1: Pre-run Port Check ===');
  const initialPortOccupants = checkPort(TEST_PORT);
  console.log(`Port ${TEST_PORT} initial status:`, initialPortOccupants ? `Occupied by PID: ${initialPortOccupants.join(', ')}` : 'FREE (OK)');
  if (initialPortOccupants) {
    throw new Error(`Port ${TEST_PORT} is unexpectedly occupied before test by PID ${initialPortOccupants.join(', ')}`);
  }

  const lifecycle = {
    testPort: TEST_PORT,
    testHost: TEST_HOST,
    previewCommand: `npx vite preview --outDir dist-local-resume-r2 --port ${TEST_PORT} --strictPort --host ${TEST_HOST}`,
    initialPortFree: true,
    startTime: new Date().toISOString(),
    serverPid: null,
    exitCode: null,
    exitSignal: null,
    exitTime: null,
    finalPortFree: false,
    testPassed: false
  };

  console.log('\n=== Step 2: Spawning Preview Server ===');
  const previewProcess = spawn('cmd.exe', ['/c', 'npx', 'vite', 'preview', '--outDir', 'dist-local-resume-r2', '--port', String(TEST_PORT), '--strictPort', '--host', TEST_HOST], {
    cwd: projectRoot,
    stdio: ['ignore', 'pipe', 'pipe']
  });

  lifecycle.serverPid = previewProcess.pid;
  console.log(`Preview server spawned with OS PID: ${previewProcess.pid}`);

  previewProcess.stdout.on('data', data => {
    // console.log(`[Preview stdout]: ${data}`);
  });
  previewProcess.stderr.on('data', data => {
    // console.error(`[Preview stderr]: ${data}`);
  });

  let exitPromise = new Promise(resolve => {
    previewProcess.on('exit', (code, signal) => {
      lifecycle.exitCode = code;
      lifecycle.exitSignal = signal;
      lifecycle.exitTime = new Date().toISOString();
      console.log(`Preview process (PID ${lifecycle.serverPid}) exited with code ${code}, signal ${signal}`);
      resolve();
    });
  });

  try {
    console.log(`Waiting for port ${TEST_PORT} to become active...`);
    const owningPids = await waitForPort(TEST_PORT, 12000);
    console.log(`Port ${TEST_PORT} active, owning PID: ${owningPids.join(', ')}`);

    console.log('\n=== Step 3: Executing R2 Verification Suite ===');
    const verifyScript = path.resolve(__dirname, 'verify-fixes-r2.js');
    execSync(`node "${verifyScript}"`, {
      cwd: projectRoot,
      stdio: 'inherit',
      env: {
        ...process.env,
        APP_URL: `http://${TEST_HOST}:${TEST_PORT}/?enable_test_adapter=1`,
        CHROME_PATH: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
      }
    });

    lifecycle.testPassed = true;
    console.log('\n✓ R2 Verification Suite completed successfully!');
  } catch (err) {
    console.error('\n✗ Test execution failed:', err.message);
    lifecycle.testPassed = false;
    lifecycle.error = err.message;
  } finally {
    console.log('\n=== Step 4: Gracefully Terminating Preview Server ===');
    if (lifecycle.serverPid) {
      try {
        // Kill tree gracefully on Windows
        execSync(`taskkill /pid ${lifecycle.serverPid} /T /F`);
      } catch (killErr) {
        console.warn('Kill task error:', killErr.message);
      }
    }
    await exitPromise;

    console.log('\n=== Step 5: Post-run Port Release Check ===');
    await sleep(500);
    const postPortOccupants = checkPort(TEST_PORT);
    lifecycle.finalPortFree = !postPortOccupants;
    console.log(`Port ${TEST_PORT} post-test status:`, postPortOccupants ? `Occupied by PID: ${postPortOccupants.join(', ')}` : 'RELEASED (OK)');

    const lifecyclePath = path.join(evidenceDir, 'fixture-lifecycle.json');
    fs.writeFileSync(lifecyclePath, JSON.stringify(lifecycle, null, 2), 'utf-8');
    console.log('Fixture lifecycle evidence saved to:', lifecyclePath);

    if (!lifecycle.testPassed || !lifecycle.finalPortFree) {
      process.exit(1);
    }
  }
}

main().catch(err => {
  console.error('Test runner fatal error:', err);
  process.exit(1);
});
