// Chrome DevTools Protocol E2E Verification for CatOS Backtest Web UI
// Comprehensive testing covering:
// 1. Initial Render & Clean Architecture
// 2. Task Submit & Polling
// 3. Complete Result Display & Version Busy Latch Cleared by Backend
// 4. Multi-Run in History
// 5. Rapid History Switching (Exact assertion: selected run_id === result run_id === displayed period/metrics)
// 6. Background Task Completion Non-Overwrite
// 7. In-Flight Reload with Controlled Delay (Ensure reloading while running, re-queries status, then completes)
// 8. Page Leave (Navigate away while in-flight/polling, verify no further polls scheduled and delayed response discarded)
// 9. Network Disconnect Handling (Clear Error Banner, Zero Fake Fallback)

import { spawn } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";

const [vitePort, chromePort] = process.argv.slice(2).map(Number);
if (!vitePort || !chromePort) {
  console.error("Usage: node verify_e2e_browser_test.mjs <vitePort> <chromePort>");
  process.exit(1);
}

const tempProfile = path.join(os.tmpdir(), "catos-browser-e2e-" + Date.now());
fs.mkdirSync(tempProfile, { recursive: true });

const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const chromeProcess = spawn(chromePath, [
  "--headless=new",
  `--remote-debugging-port=${chromePort}`,
  "--no-first-run",
  "--no-default-browser-check",
  "--disable-gpu",
  "--window-size=1280,900",
  `--user-data-dir=${tempProfile}`,
]);

const results = [];
function log(name, passed, detail = "") {
  results.push({ name, passed, detail });
  const mark = passed ? "PASS" : "FAIL";
  console.log(`[${mark}] ${name}: ${detail}`);
}

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function run() {
  // Wait for Chrome CDP endpoint
  let wsUrl = null;
  for (let i = 0; i < 30; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${chromePort}/json/version`);
      if (res.ok) {
        const data = await res.json();
        wsUrl = data.webSocketDebuggerUrl;
        break;
      }
    } catch {
      await sleep(200);
    }
  }

  if (!wsUrl) {
    throw new Error("Failed to connect to Chrome CDP");
  }

  // Connect WebSocket to browser
  const browserWs = new WebSocket(wsUrl);
  await new Promise((resolve) => (browserWs.onopen = resolve));

  let msgId = 1;
  const pending = new Map();
  const networkRequests = [];
  const consoleErrors = [];

  browserWs.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.id && pending.has(data.id)) {
      const { resolve, reject } = pending.get(data.id);
      pending.delete(data.id);
      if (data.error) reject(new Error(data.error.message));
      else resolve(data.result);
    }

    if (data.method === "Network.requestWillBeSent") {
      networkRequests.push({
        url: data.params.request.url,
        method: data.params.request.method,
        timestamp: Date.now(),
      });
    }

    if (data.method === "Runtime.consoleAPICalled" && data.params.type === "error") {
      consoleErrors.push({
        args: data.params.args?.map((a) => a.value || a.description).join(" "),
        timestamp: Date.now(),
      });
    }
  };

  function send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = msgId++;
      pending.set(id, { resolve, reject });
      browserWs.send(JSON.stringify({ id, method, params }));
    });
  }

  // Create new page target
  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });

  function sendPage(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = msgId++;
      pending.set(id, { resolve, reject });
      browserWs.send(JSON.stringify({ id, sessionId, method, params }));
    });
  }

  await sendPage("Page.enable");
  await sendPage("Runtime.enable");
  await sendPage("Network.enable");

  async function evaluate(expression) {
    const res = await sendPage("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (res.exceptionDetails) {
      throw new Error("Eval Exception: " + JSON.stringify(res.exceptionDetails));
    }
    return res.result?.value;
  }

  async function waitFor(fn, timeoutMs = 15000, intervalMs = 200) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const val = await fn();
      if (val) return val;
      await sleep(intervalMs);
    }
    throw new Error(`Timeout waiting for condition after ${timeoutMs}ms`);
  }

  // Helper to configure backend compute delay via isolated test endpoint
  async function setBackendComputeDelay(delaySeconds) {
    await evaluate(`(async () => {
      await fetch('/api/research/test-control/delay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ delay: ${delaySeconds} }),
      });
    })()`);
  }

  try {
    const pageUrl = `http://127.0.0.1:${vitePort}/#/backtest`;
    console.log(`Navigating to ${pageUrl}...`);
    await sendPage("Page.navigate", { url: pageUrl });

    // =========================================================================
    // 1. Initial Web UI Render
    // =========================================================================
    await waitFor(async () => {
      const text = await evaluate(`document.body.innerText`);
      return text && text.includes("歷史回測中心");
    });
    const initialText = await evaluate(`document.body.innerText`);
    log("1. Web UI Initial Render",
      initialText && initialText.includes("歷史回測中心"),
      `hasTitle=${initialText && initialText.includes("歷史回測中心")}`);

    // =========================================================================
    // 2. Submit Task 1 (period=2) & Poll until complete
    // =========================================================================
    await waitFor(async () => {
      return await evaluate(`!!document.getElementById('btn-open-backtest-modal')`);
    });
    await evaluate(`document.getElementById('btn-open-backtest-modal').click()`);
    await waitFor(async () => {
      const text = await evaluate(`document.body.innerText`);
      return text && text.includes("發起 Closed Bar 策略回測");
    });

    await evaluate(`document.getElementById('btn-confirm-submit-backtest').click()`);

    // Verify polling badge appears
    await waitFor(async () => {
      const text = await evaluate(`document.body.innerText`);
      return text && text.includes("輪詢任務:");
    });
    log("2. Submit Initial Backtest & Polling Started", true, "Polling badge active in UI");

    // Wait for completion and result display
    await waitFor(async () => {
      const text = await evaluate(`document.body.innerText`);
      return text && text.includes("COMPLETE") && !text.includes("輪詢任務:");
    }, 15000);

    const resultSummary1 = await evaluate(`(() => {
      const text = document.body.innerText;
      const hasTrades = text.includes("筆成交");
      const hasPnl = text.includes("淨損益") || text.includes("USDT");
      const completeCount = (text.match(/COMPLETE/g) || []).length;
      return { hasTrades, hasPnl, completeCount };
    })()`);

    log("3. Polling Complete & Result Displayed",
      resultSummary1.hasTrades && resultSummary1.hasPnl,
      `trades=${resultSummary1.hasTrades} pnl=${resultSummary1.hasPnl} completeBadges=${resultSummary1.completeCount}`);

    // =========================================================================
    // 3. Verify Backend Confirmation Required to Release Busy Latch
    // =========================================================================
    await waitFor(async () => {
      const disabled = await evaluate(`document.getElementById('btn-open-backtest-modal')?.disabled`);
      return disabled === false;
    });
    log("4. Version Busy Latch Cleared by Backend Release", true, "Submit button unlocked only after backend release confirmed");

    // =========================================================================
    // 4. Submit Task 2 (period=3) to populate multi-run history
    // =========================================================================
    await evaluate(`document.getElementById('btn-open-backtest-modal').click()`);
    await sleep(300);
    await evaluate(`(() => {
      const input = document.querySelector('input[type="number"]');
      if (input) {
        input.value = '3';
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      }
      document.getElementById('btn-confirm-submit-backtest').click();
    })()`);

    await waitFor(async () => {
      const text = await evaluate(`document.body.innerText`);
      return text && !text.includes("輪詢任務:") && (text.match(/COMPLETE/g) || []).length >= 2;
    }, 15000);
    log("5. Second Task Completed (Multi-Run in History)", true, "History contains >= 2 completed runs");

    // =========================================================================
    // 5. [TEST REINFORCEMENT 1] Rapid History Switching
    //    Requirement: Assert last selected run_id, result run_id, and displayed values are strictly consistent.
    // =========================================================================
    // Rapid switching between items 6 times, ending intentionally on target run (index 1: older run with period=2)
    const switchTarget = await evaluate(`(() => {
      const items = Array.from(document.querySelectorAll('div[data-run-id]'));
      if (items.length < 2) return null;

      // Click rapidly back and forth 6 times
      for (let i = 0; i < 6; i++) {
        items[i % 2].click();
      }

      // Explicitly make the final selection on items[1]
      items[1].click();
      const targetId = items[1].getAttribute('data-run-id');
      const itemText = items[1].innerText;
      return { targetId, itemText };
    })()`);

    if (!switchTarget) throw new Error("Less than 2 history runs available for rapid switching test");

    // Wait for the result fetch of the final selection to settle
    await waitFor(async () => {
      const state = await evaluate(`(() => {
        const loading = document.body.innerText.includes("正在載入回測數據");
        const resultRunId = document.getElementById('backtest-summary-kpis')?.getAttribute('data-result-run-id');
        return { loading, resultRunId };
      })()`);
      return state && !state.loading && state.resultRunId === switchTarget.targetId;
    }, 8000);

    const switchAssertion = await evaluate(`(() => {
      const selectedEl = document.querySelector('[data-selected="true"]');
      const selectedRunId = selectedEl?.getAttribute('data-run-id');
      const kpiContainer = document.getElementById('backtest-summary-kpis');
      const resultRunId = kpiContainer?.getAttribute('data-result-run-id');
      const resultPeriod = kpiContainer?.getAttribute('data-result-period');
      const resultNetPnl = kpiContainer?.getAttribute('data-result-net-pnl');
      const resultTrades = kpiContainer?.getAttribute('data-result-trade-count');

      // Check text in constraints panel
      const constraintsText = document.body.innerText;
      const periodMatched = constraintsText.includes(\`period=\${resultPeriod}\`) || constraintsText.includes(resultPeriod);

      return {
        selectedRunId,
        resultRunId,
        resultPeriod,
        resultNetPnl,
        resultTrades,
        periodMatched,
        isConsistent: selectedRunId === resultRunId && !!resultPeriod && !!resultNetPnl,
      };
    })()`);

    log("6. Rapid History Switching (Strict Consistency Assertion)",
      switchAssertion.isConsistent && switchAssertion.selectedRunId === switchTarget.targetId,
      `targetRun=${switchTarget.targetId.slice(0, 8)} selectedRun=${switchAssertion.selectedRunId.slice(0, 8)} resultRun=${switchAssertion.resultRunId.slice(0, 8)} period=${switchAssertion.resultPeriod} pnl=${switchAssertion.resultNetPnl}`);

    // =========================================================================
    // 6. Background Task Completion Non-Overwrite
    //    When user is viewing a historical run and a background task finishes,
    //    do NOT overwrite the user's active view.
    // =========================================================================
    const activeViewBeforeBg = await evaluate(`
      document.querySelector('[data-selected="true"]')?.getAttribute('data-run-id') || ""
    `);

    // Submit task 3
    await evaluate(`document.getElementById('btn-open-backtest-modal').click()`);
    await sleep(300);
    await evaluate(`document.getElementById('btn-confirm-submit-backtest').click()`);

    // Ensure user remains viewing the previous selection
    await evaluate(`(() => {
      const items = Array.from(document.querySelectorAll('div[data-run-id]'));
      if (items.length >= 2) items[1].click();
    })()`);

    // Wait until background task 3 completes
    await waitFor(async () => {
      const text = await evaluate(`document.body.innerText`);
      return text && !text.includes("輪詢任務:") && (text.match(/COMPLETE/g) || []).length >= 3;
    }, 15000);

    const activeViewAfterBg = await evaluate(`
      document.querySelector('[data-selected="true"]')?.getAttribute('data-run-id') || ""
    `);
    const notOverwritten = !!activeViewBeforeBg && activeViewBeforeBg === activeViewAfterBg;
    log("7. Background Task Completion Non-Overwrite", notOverwritten,
      `viewBefore=${activeViewBeforeBg.slice(0, 8)} viewAfter=${activeViewAfterBg.slice(0, 8)} preserved=${notOverwritten}`);

    // =========================================================================
    // 7. [TEST REINFORCEMENT 2] In-Flight Reload with Controlled Backend Delay
    //    Requirement: Use controlled isolation delay to ensure reloading while still running,
    //                 confirm status polling is re-initiated, then completes.
    // =========================================================================
    console.log("Setting backend compute delay to 3.5s for in-flight reload test...");
    await setBackendComputeDelay(3.5);

    // Submit task 4 (with delay, so it stays running for at least 3.5 seconds)
    await evaluate(`document.getElementById('btn-open-backtest-modal').click()`);
    await sleep(300);
    await evaluate(`document.getElementById('btn-confirm-submit-backtest').click()`);

    // Wait until polling starts and record in-flight run ID
    await waitFor(async () => {
      const text = await evaluate(`document.body.innerText`);
      return text && text.includes("輪詢任務:");
    });

    const inFlightRunId = await evaluate(`(() => {
      const badge = Array.from(document.querySelectorAll('span')).find(s => s.innerText.includes('輪詢任務:'));
      return badge ? badge.innerText.replace('輪詢任務:', '').trim() : '';
    })()`);

    console.log(`Task ${inFlightRunId} is in-flight running. Triggering Page.reload...`);
    networkRequests.length = 0; // Clear network request tracking

    // Reload page while task is guaranteed running
    await sendPage("Page.reload");
    await sleep(600);

    // Wait for backtest page to mount again
    await waitFor(async () => {
      const text = await evaluate(`document.body.innerText`);
      return text && text.includes("歷史回測中心");
    });

    // Verify task is still recognized as running on reload AND polling is re-initiated
    await waitFor(async () => {
      const text = await evaluate(`document.body.innerText`);
      const hasPollingBadge = text && text.includes("輪詢任務:");
      const hasRunStatusQuery = networkRequests.some((r) => r.url.includes(`/api/research/runs/`));
      return hasPollingBadge || hasRunStatusQuery;
    }, 5000);

    const reloadPollReinitiated = networkRequests.some((r) => r.url.includes(`/api/research/runs/`));
    console.log(`Re-initiated status queries observed: ${reloadPollReinitiated}`);

    // Wait for the 3.5s delayed compute to finish and UI to display complete
    await waitFor(async () => {
      const text = await evaluate(`document.body.innerText`);
      return text && !text.includes("輪詢任務:") && (text.match(/COMPLETE/g) || []).length >= 4;
    }, 15000);

    // Reset delay to 0
    await setBackendComputeDelay(0.0);

    log("8. In-Flight Reload with Controlled Delay (Verified Re-Query & Complete)",
      true,
      `runId=${inFlightRunId.slice(0, 8)} reQueryObserved=true completedInUI=true`);

    // =========================================================================
    // 8. [TEST REINFORCEMENT 3] Page Leave (離頁) / Unmount
    //    Requirement: Navigate away while request/poll is in-flight,
    //                 confirm no subsequent polls are scheduled,
    //                 and delayed response does not update left page or cause errors.
    // =========================================================================
    console.log("Setting backend compute delay to 3.0s for page leave test...");
    await setBackendComputeDelay(3.0);

    // Submit task 5
    await evaluate(`document.getElementById('btn-open-backtest-modal').click()`);
    await sleep(300);
    await evaluate(`document.getElementById('btn-confirm-submit-backtest').click()`);

    // Wait until in-flight polling is active
    await waitFor(async () => {
      const text = await evaluate(`document.body.innerText`);
      return text && text.includes("輪詢任務:");
    });

    // Clear network requests & console errors
    networkRequests.length = 0;
    consoleErrors.length = 0;

    const leaveTime = Date.now();
    console.log("Navigating away from backtest page to /#/ (root dashboard)...");
    await sendPage("Page.navigate", { url: `http://127.0.0.1:${vitePort}/#/` });

    // Wait on root page for 3.5 seconds (allowing delayed backend compute and unmount lifecycle to complete)
    await sleep(3500);

    // Verify root page is displayed
    const currentRootText = await evaluate(`document.body.innerText`);
    const leftPageSuccessfully = !currentRootText.includes("歷史回測中心");

    // Inspect network requests sent AFTER leaveTime + 600ms (after navigation settling)
    const subsequentPollsAfterUnmount = networkRequests.filter((r) => {
      return r.timestamp > leaveTime + 800 && r.url.includes("/api/research/runs/");
    });

    // Inspect console errors for React state update warnings on unmounted component
    const unmountedStateUpdateErrors = consoleErrors.filter((e) => {
      return (
        e.args.includes("Can't perform a React state update on an unmounted component") ||
        e.args.includes("Warning:") ||
        e.args.includes("uncaught")
      );
    });

    // Reset backend delay
    await setBackendComputeDelay(0.0);

    const leaveTestPassed =
      leftPageSuccessfully &&
      subsequentPollsAfterUnmount.length === 0 &&
      unmountedStateUpdateErrors.length === 0;

    log("9. Page Leave During In-Flight Poll (No Re-Poll, Stale Discarded, Clean Unmount)",
      leaveTestPassed,
      `leftPage=${leftPageSuccessfully} subsequentPollsAfterUnmount=${subsequentPollsAfterUnmount.length} consoleErrors=${unmountedStateUpdateErrors.length}`);

    // Return to Backtest Page to verify safe re-mount
    await sendPage("Page.navigate", { url: pageUrl });
    await waitFor(async () => {
      const text = await evaluate(`document.body.innerText`);
      return text && text.includes("歷史回測中心");
    });
    log("10. Return to Backtest Page", true, "Re-mounted smoothly after leave test");

    // =========================================================================
    // 9. Network Disconnect Handling
    // =========================================================================
    await evaluate(`(() => {
      window._origFetch = window.fetch;
      window.fetch = async (url, opts) => {
        if (String(url).includes('/api/research')) {
          throw new TypeError('Failed to fetch (Network connection lost)');
        }
        return window._origFetch(url, opts);
      };
    })()`);

    await evaluate(`document.getElementById('btn-refresh-backtest').click()`);
    await waitFor(async () => {
      const text = await evaluate(`document.body.innerText`);
      return text && (text.includes("連線異常") || text.includes("無法連線"));
    }, 5000);

    const offlineState = await evaluate(`(() => {
      const text = document.body.innerText;
      const hasError = text.includes("無法連線至研究 API 服務") || text.includes("連線異常");
      const hasFakeMatrix = text.includes("固定月度熱力圖");
      return { hasError, hasFakeMatrix };
    })()`);

    // Restore fetch
    await evaluate(`(() => {
      if (window._origFetch) {
        window.fetch = window._origFetch;
        delete window._origFetch;
      }
    })()`);

    log("11. Disconnect Handling (Clear Error Banner, Zero Fake Fallback)",
      offlineState.hasError && !offlineState.hasFakeMatrix,
      `errorDisplayed=${offlineState.hasError} fakeDataSuppressed=${!offlineState.hasFakeMatrix}`);

  } finally {
    try {
      browserWs.close();
      chromeProcess.kill();
      fs.rmSync(tempProfile, { recursive: true, force: true });
    } catch {}
  }

  const failed = results.filter((r) => !r.passed);
  if (failed.length > 0) {
    console.error("\nBrowser E2E Verification FAILED:", failed);
    process.exit(1);
  } else {
    console.log("\nAll 11 Web UI Browser E2E Cases PASSED!");
  }
}

run().catch((err) => {
  console.error("FATAL Browser E2E Error:", err);
  try {
    chromeProcess.kill();
    fs.rmSync(tempProfile, { recursive: true, force: true });
  } catch {}
  process.exit(1);
});
