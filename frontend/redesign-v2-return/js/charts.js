/**
 * catOS v1 - Native High-Performance Canvas & SVG Charts
 * Zero external libraries, zero CDN, pure local computation.
 * High-density quantitative aesthetics with crisp rendering on HiDPI displays.
 */

/**
 * Render Equity Curve on HTML5 Canvas with HiDPI support
 * @param {HTMLCanvasElement} canvas 
 * @param {Array<{time: string, equity: number, drawdown?: number}>} points 
 * @param {Object} options 
 */
export function renderEquityChart(canvas, points, options = {}) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);

  const w = rect.width;
  const h = rect.height;

  // Clear
  ctx.clearRect(0, 0, w, h);

  if (!points || points.length === 0) {
    ctx.fillStyle = "#64748b";
    ctx.font = "12px monospace";
    ctx.textAlign = "center";
    ctx.fillText("尚無歷史權益點陣資料 (Standby)", w / 2, h / 2);
    return;
  }

  const padLeft = 55;
  const padRight = 15;
  const padTop = 15;
  const padBottom = 25;

  const chartW = w - padLeft - padRight;
  const chartH = h - padTop - padBottom;

  const values = points.map(p => p.equity);
  const minVal = Math.min(...values) * 0.995;
  const maxVal = Math.max(...values) * 1.005;
  const valRange = maxVal - minVal || 1;

  // Draw Grid Lines (Horizontal)
  ctx.strokeStyle = "#1e2638";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#64748b";
  ctx.font = "10px monospace";
  ctx.textAlign = "right";

  const gridSteps = 4;
  for (let i = 0; i <= gridSteps; i++) {
    const y = padTop + (chartH / gridSteps) * i;
    const v = maxVal - (valRange / gridSteps) * i;
    
    ctx.beginPath();
    ctx.moveTo(padLeft, y);
    ctx.lineTo(w - padRight, y);
    ctx.stroke();

    ctx.fillText(v.toFixed(0), padLeft - 6, y + 3);
  }

  // Draw Curve & Gradient Fill
  const coordX = i => padLeft + (i / (points.length - 1)) * chartW;
  const coordY = v => padTop + chartH - ((v - minVal) / valRange) * chartH;

  const accentColor = options.color || "#f59e0b"; // Amber Gold
  const grad = ctx.createLinearGradient(0, padTop, 0, padTop + chartH);
  grad.addColorStop(0, "rgba(245, 158, 11, 0.25)");
  grad.addColorStop(1, "rgba(245, 158, 11, 0.0)");

  // Path
  ctx.beginPath();
  points.forEach((p, i) => {
    const x = coordX(i);
    const y = coordY(p.equity);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });

  // Stroke Curve
  ctx.strokeStyle = accentColor;
  ctx.lineWidth = 2;
  ctx.stroke();

  // Fill Area
  ctx.lineTo(padLeft + chartW, padTop + chartH);
  ctx.lineTo(padLeft, padTop + chartH);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Draw Points / Markers (First and Last)
  const lastIdx = points.length - 1;
  const lastX = coordX(lastIdx);
  const lastY = coordY(points[lastIdx].equity);

  ctx.beginPath();
  ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
  ctx.fillStyle = "#ffffff";
  ctx.fill();
  ctx.strokeStyle = accentColor;
  ctx.lineWidth = 2;
  ctx.stroke();

  // X-Axis Time Labels
  ctx.fillStyle = "#64748b";
  ctx.textAlign = "left";
  ctx.fillText(points[0].time, padLeft, h - 6);
  ctx.textAlign = "right";
  ctx.fillText(points[lastIdx].time, w - padRight, h - 6);
  if (points.length > 2) {
    ctx.textAlign = "center";
    ctx.fillText(points[Math.floor(lastIdx / 2)].time, padLeft + chartW / 2, h - 6);
  }
}

/**
 * Render SVG Donut Chart for Margin / Exposure Allocation
 * @param {SVGElement} svg 
 * @param {Array<{coin: string, notional: string, pctOfBudget: string, color: string}>} items 
 */
export function renderDonutChart(svg, items) {
  if (!svg) return;
  svg.innerHTML = "";

  if (!items || items.length === 0) {
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", "50%");
    text.setAttribute("y", "50%");
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("fill", "#64748b");
    text.setAttribute("font-size", "11");
    text.textContent = "尚無配置資料";
    svg.appendChild(text);
    return;
  }

  const size = 130;
  const strokeWidth = 16;
  const radius = (size - strokeWidth) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * radius;

  let accumulatedPercent = 0;

  items.forEach(item => {
    const pct = parseFloat(item.pctOfBudget) / 100 || 0;
    if (pct <= 0) return;

    const strokeDasharray = `${pct * circumference} ${circumference}`;
    const strokeDashoffset = -accumulatedPercent * circumference;

    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", cx);
    circle.setAttribute("cy", cy);
    circle.setAttribute("r", radius);
    circle.setAttribute("fill", "transparent");
    circle.setAttribute("stroke", item.color || "#475569");
    circle.setAttribute("stroke-width", strokeWidth);
    circle.setAttribute("stroke-dasharray", strokeDasharray);
    circle.setAttribute("stroke-dashoffset", strokeDashoffset);
    circle.setAttribute("transform", `rotate(-90 ${cx} ${cy})`);
    circle.style.transition = "stroke-dashoffset 0.4s ease, stroke-dasharray 0.4s ease";

    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = `${item.coin}: ${item.pctOfBudget} (${item.notional} USDT)`;
    circle.appendChild(title);

    svg.appendChild(circle);
    accumulatedPercent += pct;
  });
}

/**
 * Generate 30D / 60D synthetic points for realistic quantitative curves
 * @param {number} days 
 * @param {number} startVal 
 * @param {number} endVal 
 * @returns {Array<{time: string, equity: number}>}
 */
export function generateSyntheticTrend(days = 30, startVal = 120000, endVal = 125480.50) {
  const points = [];
  const now = new Date();
  let current = startVal;
  const step = (endVal - startVal) / days;

  for (let i = days; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 24 * 3600 * 1000);
    const month = (d.getMonth() + 1).toString().padStart(2, "0");
    const day = d.getDate().toString().padStart(2, "0");
    const noise = (Math.sin(i * 0.8) + Math.cos(i * 1.5)) * 420;
    current += step + noise * 0.2;
    points.push({
      time: `${month}/${day}`,
      equity: Math.round(current * 100) / 100
    });
  }
  points[points.length - 1].equity = endVal;
  return points;
}
