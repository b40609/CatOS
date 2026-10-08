/**
 * catOS Institutional Quantitative Platform - Main Controller
 * Adapted directly from catOS-Frontend-Final Prototype A
 */

// Toggle Technical Popover
window.togglePopover = function() {
  const el = document.getElementById("status-popover-menu");
  if (el) el.classList.toggle("open");
};

// Close popover when clicked outside
document.addEventListener("click", function(e) {
  const trigger = document.querySelector(".status-popover-trigger");
  if (trigger && !trigger.contains(e.target)) {
    const menu = document.getElementById("status-popover-menu");
    if (menu) menu.classList.remove("open");
  }
});

// Toggle Incident Accordion
window.toggleIncident = function(el) {
  if (el) el.classList.toggle("open");
};

// Switch Time Range (7D, 30D, 90D)
window.setTimeRange = function(range, btn) {
  if (btn && btn.parentElement) {
    btn.parentElement.querySelectorAll("button").forEach(b => b.className = "btn");
    btn.className = "btn btn-primary";
  }
};

// 5-State Interactive Scenario Switcher
window.switchState = function(state, btn) {
  if (btn) {
    document.querySelectorAll(".state-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
  }

  const eqVal = document.getElementById("kpi-equity-val");
  const pnlVal = document.getElementById("kpi-pnl-val");
  const botsBadge = document.getElementById("kpi-bots-badge");
  const riskBadge = document.getElementById("kpi-risk-badge");
  const latchBadge = document.getElementById("latch-status-badge");
  const latchPnl = document.getElementById("latch-pnl-val");
  const needle = document.getElementById("gauge-needle");
  const popDot = document.getElementById("popover-dot");
  const popLabel = document.getElementById("popover-btn-label");

  if (!eqVal || !pnlVal) return;

  if (state === 'NORMAL') {
    eqVal.innerHTML = '125,480.50 <span style="font-size:13px; font-weight:normal; color:var(--text-secondary);">USDT</span>';
    pnlVal.innerHTML = '+1,240.80 <span style="font-size:13px; font-weight:normal;">USDT</span>';
    pnlVal.style.color = "var(--color-success)";
    botsBadge.className = "badge badge-success";
    botsBadge.textContent = "1 運行中";
    riskBadge.className = "badge badge-success";
    riskBadge.textContent = "NORMAL";
    latchBadge.className = "badge badge-success";
    latchBadge.textContent = "安全運行中";
    latchPnl.innerHTML = "+18.42 (+1.8%)";
    latchPnl.style.color = "var(--color-success)";
    needle.style.left = "76%";
    needle.setAttribute("data-label", "目前: +1.84% (安全緩衝 118.42 USDT)");
    popDot.className = "badge-dot dot-success";
    popLabel.textContent = "底座連線正常 · 16ms";
  } else if (state === 'SOFT_LATCH') {
    eqVal.innerHTML = '121,900.50 <span style="font-size:13px; font-weight:normal; color:var(--text-secondary);">USDT</span>';
    pnlVal.innerHTML = '-3,580.00 <span style="font-size:13px; font-weight:normal;">USDT</span>';
    pnlVal.style.color = "var(--color-danger)";
    botsBadge.className = "badge badge-warning";
    botsBadge.textContent = "1 軟限受阻";
    riskBadge.className = "badge badge-warning";
    riskBadge.textContent = "SOFT LATCH";
    latchBadge.className = "badge badge-warning";
    latchBadge.textContent = "SOFT LATCH 鎖存";
    latchPnl.innerHTML = "-3,580.00 (-2.85%)";
    latchPnl.style.color = "var(--color-danger)";
    needle.style.left = "38%";
    needle.setAttribute("data-label", "最高回撤 -10.20% (軟限鎖存中 · 反彈至 -2.85%)");
    popDot.className = "badge-dot dot-warning";
    popLabel.textContent = "日損軟限鎖存中";
  } else if (state === 'RETAINED_409') {
    eqVal.innerHTML = '124,110.00 <span style="font-size:13px; font-weight:normal; color:var(--text-secondary);">USDT</span>';
    pnlVal.innerHTML = '-210.00 <span style="font-size:13px; font-weight:normal;">USDT</span>';
    pnlVal.style.color = "var(--color-warning)";
    botsBadge.className = "badge badge-danger";
    botsBadge.textContent = "409 獨佔鎖定";
    riskBadge.className = "badge badge-warning";
    riskBadge.textContent = "ATTENTION";
    latchBadge.className = "badge badge-warning";
    latchBadge.textContent = "部位未清";
    needle.style.left = "62%";
    needle.setAttribute("data-label", "Bot 手動停止但仍持倉 -1 張 (409 阻擋新案例)");
    popDot.className = "badge-dot dot-warning";
    popLabel.textContent = "409 獨佔未釋放";
  } else if (state === 'EMPTY') {
    eqVal.innerHTML = '— <span style="font-size:13px; font-weight:normal; color:var(--text-secondary);">USDT</span>';
    pnlVal.innerHTML = '0.00 <span style="font-size:13px; font-weight:normal;">USDT</span>';
    pnlVal.style.color = "var(--text-muted)";
    botsBadge.className = "badge badge-secondary";
    botsBadge.textContent = "0 運行中";
    riskBadge.className = "badge badge-secondary";
    riskBadge.textContent = "STANDBY";
    latchBadge.className = "badge badge-secondary";
    latchBadge.textContent = "待命中";
    needle.style.left = "50%";
    needle.setAttribute("data-label", "尚未人工指派 Bot");
    popDot.className = "badge-dot dot-success";
    popLabel.textContent = "底座待命中 · 就緒";
  } else if (state === 'RECOVERY') {
    eqVal.innerHTML = '125,480.50 <span style="font-size:13px; font-weight:normal; color:var(--text-secondary);">USDT</span>';
    pnlVal.innerHTML = 'UNKNOWN';
    pnlVal.style.color = "var(--color-danger)";
    botsBadge.className = "badge badge-danger";
    botsBadge.textContent = "RECOVERY";
    riskBadge.className = "badge badge-danger";
    riskBadge.textContent = "RECOVERY_REQUIRED";
    latchBadge.className = "badge badge-danger";
    latchBadge.textContent = "來源漂移 / 需人工核對";
    needle.style.left = "20%";
    needle.setAttribute("data-label", "服務異常: 需核對代碼與重啟本機服務");
    popDot.className = "badge-dot dot-danger";
    popLabel.textContent = "需人工檢查 · 409";
  }
};

// URL parameters support
document.addEventListener("DOMContentLoaded", function() {
  const params = new URLSearchParams(window.location.search);
  const state = params.get("state") || params.get("scenario");
  if (state) {
    const btn = Array.from(document.querySelectorAll(".state-btn")).find(b => 
      b.getAttribute("onclick") && b.getAttribute("onclick").includes(state)
    );
    if (btn) switchState(state, btn);
  }
  if (params.get("popover") === "open") {
    togglePopover();
  }
});
