/**
 * catOS v1 - Data Model & Contract Constants
 * 
 * Strict Financial Rules:
 * - All numbers in data models must be Decimal strings (no float).
 * - Fixed OKX tag: "41cb53c54d6dABDE".
 * - Max allowed leverage: 3.0x.
 * - Single currency exposure budget ratio: 50%.
 * - Daily loss: Soft -10% (Stop increase exposure), Hard -20% (Market liquidation + Kill Switch).
 * - Daily baseline cutoff: Asia/Taipei (UTC+08:00) 00:00.
 * - Single bot contract exclusivity (contract locked until position empty and reconciled).
 * - "stopped / completed" does not mean position is flat or ownership is released.
 */

export const CATOS_CONTRACTS = {
  STRATEGY_CONTRACT: "catos.python-strategy.v1",
  WORKSPACE_CONTRACT: "catos.workspace.v1",
  FIXED_ORDER_TAG: "41cb53c54d6dABDE",
  DEFAULT_LEVERAGE_CAP: "3.0",
  DEFAULT_SINGLE_CURRENCY_CAP_RATIO: "0.50",
  DAILY_LOSS_SOFT_PERCENT: "-10.0",
  DAILY_LOSS_HARD_PERCENT: "-20.0",
  TIMEZONE: "Asia/Taipei (UTC+08:00)"
};

/**
 * Format a Decimal string with comma separators
 * @param {string} val 
 * @param {number} decimals 
 * @returns {string}
 */
export function formatDecimal(val, decimals = 2) {
  if (val === null || val === undefined || val === "" || val === "—") return "—";
  const num = parseFloat(val);
  if (isNaN(num)) return val;
  const parts = val.split(".");
  const intPart = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  if (decimals === 0) return intPart;
  const fracPart = parts[1] ? parts[1].padEnd(decimals, "0").slice(0, decimals) : "0".repeat(decimals);
  return `${intPart}.${fracPart}`;
}

/**
 * Shorten hash or ID for compact display
 * @param {string} hash 
 * @param {number} head 
 * @param {number} tail 
 * @returns {string}
 */
export function shortenHash(hash, head = 6, tail = 4) {
  if (!hash || hash.length <= head + tail) return hash || "—";
  return `${hash.slice(0, head)}…${hash.slice(-tail)}`;
}
