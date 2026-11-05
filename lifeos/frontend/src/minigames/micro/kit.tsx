// Shared bits for the quick class games: the shape of a round, tries dots, the pop-up call ("Perfect!"), timing helpers.
import React, { useEffect, useRef } from "react";

export type Skin = { id: string; title: string; how: string; badge: string };
export type Ended = { score: number; max: number; stats?: any; summary: string };
export type GameProps = { round: any; skin: Skin; onEnd: (r: Ended) => void };
export type Tone = "great" | "good" | "miss";

export const tone = (pts: number, full = 2): Tone => (pts >= full ? "great" : pts > 0 ? "good" : "miss");

export function buzz(ms = 12) {
  try {
    if (navigator.vibrate) navigator.vibrate(ms);
  } catch {
    /* no vibration on this device */
  }
}

/** One dot per try: green for a hit, gold for close, red for a miss, hollow for still to come. */
export function Dots({ results, n }: { results: number[]; n: number }) {
  return (
    <div className="mc-dots" aria-label={`${results.length} of ${n} done`}>
      {Array.from({ length: n }, (_, i) => (
        <i key={i} className={i < results.length ? tone(results[i]) : i === results.length ? "now" : ""} />
      ))}
    </div>
  );
}

/** The call after each try. key changes so the animation replays. */
export function Pop({ pop }: { pop: { text: string; tone: Tone; k: number } | null }) {
  if (!pop) return null;
  return <div key={pop.k} className={"mc-pop " + pop.tone}>{pop.text}</div>;
}

/** Calls fn every frame with seconds since start while active. */
export function useFrames(active: boolean, fn: (t: number) => void, dep: any = null) {
  const cb = useRef(fn);
  cb.current = fn;
  useEffect(() => {
    if (!active) return;
    const t0 = performance.now();
    let id = 0;
    const tick = () => {
      cb.current((performance.now() - t0) / 1000);
      id = requestAnimationFrame(tick);
    };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
  }, [active, dep]);
}

/** Space / Enter for people playing on a laptop. */
export function useKeys(down?: () => void, up?: () => void) {
  const d = useRef(down);
  const u = useRef(up);
  d.current = down;
  u.current = up;
  useEffect(() => {
    const isKey = (e: KeyboardEvent) => e.code === "Space" || e.code === "Enter";
    const kd = (e: KeyboardEvent) => {
      if (!isKey(e) || e.repeat) return;
      e.preventDefault();
      d.current?.();
    };
    const ku = (e: KeyboardEvent) => {
      if (!isKey(e)) return;
      e.preventDefault();
      u.current?.();
    };
    window.addEventListener("keydown", kd);
    window.addEventListener("keyup", ku);
    return () => {
      window.removeEventListener("keydown", kd);
      window.removeEventListener("keyup", ku);
    };
  }, []);
}

/** A thin bar that runs down over `secs`. */
export function TimerBar({ left, secs }: { left: number; secs: number }) {
  return (
    <div className="tv-timer mc-timer">
      <i style={{ width: `${Math.max(0, (left / secs) * 100)}%` }} className={left < secs * 0.3 ? "low" : ""} />
    </div>
  );
}

export const later = (ms: number, fn: () => void) => window.setTimeout(fn, ms);
