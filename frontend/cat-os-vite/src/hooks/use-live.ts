import { useEffect, useRef, useState } from "react";

/** Random-walk a number on an interval. Client-only; SSR renders the seed. */
export function useLiveNumber(seed: number, vol = 0.0015, ms = 1400) {
  const [value, setValue] = useState(seed);
  const [dir, setDir] = useState<"up" | "down" | null>(null);

  useEffect(() => {
    const id = setInterval(() => {
      setValue((prev) => {
        const delta = prev * vol * (Math.random() - 0.45) * 2;
        const next = prev + delta;
        setDir(delta >= 0 ? "up" : "down");
        return next;
      });
    }, ms);
    return () => clearInterval(id);
  }, [vol, ms]);

  return { value, dir };
}

/** Append generated items to a capped, newest-first list. */
export function useLiveFeed<T>(seed: T[], make: () => T, ms = 3200, cap = 40, enabled = true) {
  const [items, setItems] = useState<T[]>(seed);
  const makeRef = useRef(make);
  makeRef.current = make;

  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => {
      setItems((prev) => [makeRef.current(), ...prev].slice(0, cap));
    }, ms);
    return () => clearInterval(id);
  }, [ms, cap, enabled]);

  return [items, setItems] as const;
}

/** Rolling series for live charts. */
export function useLiveSeries(seed: number[], vol = 1.2, ms = 1600) {
  const [series, setSeries] = useState(seed);
  useEffect(() => {
    const id = setInterval(() => {
      setSeries((prev) => {
        const last = prev[prev.length - 1] ?? 100;
        const next = Math.max(5, last + (Math.random() - 0.44) * vol * 4);
        return [...prev.slice(1), Number(next.toFixed(2))];
      });
    }, ms);
    return () => clearInterval(id);
  }, [vol, ms]);
  return series;
}

/** Ticking clock, mounted only after hydration to avoid SSR mismatch. */
export function useClock() {
  const [now, setNow] = useState<string>("--:--:--");
  useEffect(() => {
    const tick = () =>
      setNow(
        new Date().toLocaleTimeString("en-GB", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
      );
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return now;
}

export function nowStamp(withMs = false) {
  const d = new Date();
  const base = d.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  return withMs ? `${base}.${String(d.getMilliseconds()).padStart(3, "0")}` : base;
}

export function fmtMoney(n: number, digits = 0) {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function fmtSigned(n: number, digits = 2) {
  const s = n.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  return n >= 0 ? `+${s}` : s;
}
