// Flash: the squares light up in a pattern; tap it back. Two rounds, the second one a step longer.
import React, { useEffect, useState } from "react";
import { buzz, Dots, GameProps, later } from "./kit";

const HUES = [4, 28, 48, 142, 172, 200, 226, 266, 318];

export default function Flash({ round, onEnd }: GameProps) {
  const rounds: number[][] = round.rounds;
  const on: number = round.on ?? 420;
  const gap: number = round.gap ?? 170;
  const [r, setR] = useState(0);
  const [phase, setPhase] = useState<"watch" | "tap" | "after">("watch");
  const [lit, setLit] = useState<number | null>(null);
  const [k, setK] = useState(0);
  const [flash, setFlash] = useState<{ tile: number; ok: boolean } | null>(null);
  const [score, setScore] = useState(0);
  const [results, setResults] = useState<number[]>([]);
  const seq = rounds[Math.min(r, rounds.length - 1)];

  useEffect(() => {  // play the pattern
    if (phase !== "watch") return;
    const timers: number[] = [];
    let at = 650;
    seq.forEach((tile) => {
      timers.push(later(at, () => setLit(tile)));
      timers.push(later(at + on, () => setLit(null)));
      at += on + gap;
    });
    timers.push(later(at, () => setPhase("tap")));
    return () => timers.forEach(clearTimeout);
  }, [r, phase]); // eslint-disable-line react-hooks/exhaustive-deps

  const endRound = (got: number) => {
    const total = score + got;
    setScore(total);
    const next = [...results, got >= seq.length ? 2 : got > 0 ? 1 : 0];
    setResults(next);
    setPhase("after");
    later(850, () => {
      setFlash(null);
      if (r + 1 >= rounds.length) {
        const max = rounds.reduce((a, b) => a + b.length, 0);
        onEnd({ score: total, max, summary: `${total} of ${max} squares`, stats: { rounds: next } });
        return;
      }
      setK(0);
      setR(r + 1);
      setPhase("watch");
    });
  };

  const tap = (tile: number) => {
    if (phase !== "tap") return;
    if (tile === seq[k]) {
      buzz(8);
      setFlash({ tile, ok: true });
      later(160, () => setFlash((f) => (f && f.tile === tile ? null : f)));
      if (k + 1 >= seq.length) endRound(seq.length);
      else setK(k + 1);
    } else {
      setFlash({ tile, ok: false });
      endRound(k);
    }
  };

  return (
    <div className="mc-field mc-flash">
      <div className="mc-row"><Dots results={results} n={rounds.length} /><span className="mc-dim">{seq.length} squares</span></div>
      <div className={"mc-say " + phase}>{phase === "watch" ? "Watch…" : phase === "tap" ? `Your turn · ${k} of ${seq.length}` : results[results.length - 1] === 2 ? "Got it all" : "Lost it"}</div>
      <div className="mc-grid g3">
        {HUES.map((h, t) => (
          <button
            key={t}
            className={"mc-tile" + (lit === t ? " lit" : "") + (flash?.tile === t ? (flash.ok ? " ok" : " bad") : "")}
            style={{ ["--h" as any]: h }}
            disabled={phase !== "tap"}
            onPointerDown={(e) => { e.preventDefault(); tap(t); }}
            aria-label={`square ${t + 1}`}
          />
        ))}
      </div>
    </div>
  );
}
