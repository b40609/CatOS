/**
 * Presentation-only formatting for backend Decimal strings.
 *
 * Money and ratios stay strings end to end: rounding, sign detection and the
 * percent shift below are done on the digits, never through a JS number, so
 * "999.91375990" is shown as "999.91" without ever existing as a float.
 */
import type { DecimalString } from '@/contracts';

const DECIMAL_RE = /^[+-]?(\d+)(?:\.(\d*))?$/;

interface Parts {
  negative: boolean;
  int: string;
  frac: string;
}

function parse(value: DecimalString): Parts | null {
  const trimmed = value.trim();
  const match = DECIMAL_RE.exec(trimmed);
  if (!match) {
    // Scientific notation ("0E-7") only appears for exact zeros from Python's Decimal.
    if (/^[+-]?0(?:\.0*)?E[+-]?\d+$/i.test(trimmed)) return { negative: false, int: '0', frac: '' };
    return null;
  }
  return { negative: trimmed.startsWith('-'), int: match[1], frac: match[2] ?? '' };
}

function isZero(parts: Parts) {
  return /^0*$/.test(parts.int) && /^0*$/.test(parts.frac);
}

/** Round half-up to `digits` fractional digits using integer arithmetic. */
function roundTo(parts: Parts, digits: number): Parts {
  const frac = parts.frac.padEnd(digits + 1, '0');
  const kept = frac.slice(0, digits);
  const next = frac.charCodeAt(digits) - 48;
  let scaled = BigInt(parts.int + kept);
  if (next >= 5) scaled += 1n;
  const text = scaled.toString().padStart(digits + 1, '0');
  const int = text.slice(0, text.length - digits) || '0';
  return { negative: parts.negative, int, frac: digits ? text.slice(text.length - digits) : '' };
}

function group(int: string) {
  return int.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

export interface DecimalFormatOptions {
  digits?: number;      // fractional digits, default 2
  sign?: boolean;       // prefix "+" for positive values
  prefix?: string;      // e.g. "$"
  suffix?: string;      // e.g. "x" or "%"
  grouping?: boolean;   // thousands separators, default true
}

/** Format a Decimal string; returns `fallback` when the value is null or malformed. */
export function formatDecimal(
  value: DecimalString | null | undefined,
  options: DecimalFormatOptions = {},
  fallback = '不適用',
): string {
  if (value === null || value === undefined) return fallback;
  const parsed = parse(value);
  if (!parsed) return fallback;
  const { digits = 2, sign = false, prefix = '', suffix = '', grouping = true } = options;
  const rounded = roundTo(parsed, digits);
  const zero = isZero(rounded);
  const magnitude = (grouping ? group(rounded.int) : rounded.int) + (digits ? '.' + rounded.frac : '');
  const signText = zero ? '' : rounded.negative ? '-' : sign ? '+' : '';
  return `${signText}${prefix}${magnitude}${suffix}`;
}

/** Shift the decimal point right by `places` (×10^places) on the digit string. */
export function shiftDecimal(value: DecimalString, places: number): DecimalString {
  const parsed = parse(value);
  if (!parsed) return value;
  const digits = parsed.int + parsed.frac;
  const point = parsed.int.length + places;
  let int: string;
  let frac: string;
  if (point <= 0) {
    int = '0';
    frac = '0'.repeat(-point) + digits;
  } else if (point >= digits.length) {
    int = digits + '0'.repeat(point - digits.length);
    frac = '';
  } else {
    int = digits.slice(0, point);
    frac = digits.slice(point);
  }
  int = int.replace(/^0+(?=\d)/, '');
  return `${parsed.negative ? '-' : ''}${int}${frac ? '.' + frac : ''}`;
}

/** Ratio string ("0.00321") rendered as a percent ("+0.32%"). */
export function formatRatioPct(
  value: DecimalString | null | undefined,
  options: Omit<DecimalFormatOptions, 'suffix' | 'prefix'> = {},
  fallback = '不適用',
): string {
  if (value === null || value === undefined) return fallback;
  const parsed = parse(value);
  if (!parsed) return fallback;
  return formatDecimal(shiftDecimal(value, 2), { digits: 2, sign: true, ...options, suffix: '%' }, fallback);
}

/** Exact comparison of two Decimal strings; null when either side is missing or malformed. */
export function compareDecimal(
  a: DecimalString | null | undefined,
  b: DecimalString | null | undefined,
): -1 | 0 | 1 | null {
  if (a === null || a === undefined || b === null || b === undefined) return null;
  const left = parse(a);
  const right = parse(b);
  if (!left || !right) return null;
  const digits = Math.max(left.frac.length, right.frac.length);
  const scaled = (p: Parts) => {
    const magnitude = BigInt(p.int + p.frac.padEnd(digits, '0'));
    return p.negative ? -magnitude : magnitude;
  };
  const x = scaled(left);
  const y = scaled(right);
  return x < y ? -1 : x > y ? 1 : 0;
}

/** Drawdown magnitude ("6.1193…", >= 0) shown as "-6.12%"; zero stays "0.00%". */
export function formatDrawdownPct(magnitude: DecimalString | null | undefined, fallback = '--'): string {
  const text = formatDecimal(magnitude, { digits: 2, suffix: '%' }, fallback);
  return text === fallback || text === '0.00%' ? text : `-${text}`;
}

export type Sign = 'positive' | 'negative' | 'zero';

export function signOf(value: DecimalString | null | undefined): Sign | null {
  if (value === null || value === undefined) return null;
  const parsed = parse(value);
  if (!parsed) return null;
  if (isZero(parsed)) return 'zero';
  return parsed.negative ? 'negative' : 'positive';
}

/** Tailwind tone for a signed Decimal string. */
export function toneOf(value: DecimalString | null | undefined): string {
  const sign = signOf(value);
  if (sign === 'positive') return 'text-emerald-400 font-semibold';
  if (sign === 'negative') return 'text-rose-400 font-semibold';
  return 'text-muted-foreground';
}

/**
 * Chart geometry needs a float to place a pixel. This is the single place that
 * conversion happens; the result must never be formatted back into a money
 * label (use the original string for that).
 */
export function toPlotNumber(value: DecimalString | null | undefined): number {
  if (value === null || value === undefined) return Number.NaN;
  const n = Number(value);
  return Number.isFinite(n) ? n : Number.NaN;
}

const TAIPEI = 'Asia/Taipei';

export function formatClock(ms: number | null | undefined, withSeconds = true): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms)) return '不適用';
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: TAIPEI,
    hour: '2-digit',
    minute: '2-digit',
    ...(withSeconds ? { second: '2-digit' } : {}),
    hour12: false,
  }).format(new Date(ms));
}

/** `MM/DD HH:mm` in Asia/Taipei (month first, unambiguous for a zh-TW terminal). */
export function formatDateTime(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms)) return '不適用';
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: TAIPEI, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(new Date(ms));
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '00';
  return `${get('month')}/${get('day')} ${get('hour')}:${get('minute')}`;
}

export function formatTimeframe(ms: number | null | undefined): string {
  if (!ms) return '不適用';
  if (ms % 3_600_000 === 0) return `${ms / 3_600_000}h`;
  if (ms % 60_000 === 0) return `${ms / 60_000}m`;
  return `${ms}ms`;
}

export function shortId(id: string | null | undefined, length = 8): string {
  return id ? id.slice(0, length) : '不適用';
}
