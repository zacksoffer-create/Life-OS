// Odd one out: a grid of the same thing and one that's off (a typo, a missing accent, a mutation, a shade). Three rounds.
import React, { useState } from "react";
import { buzz, Dots, GameProps, later, TimerBar, useFrames } from "./kit";

type Rd = { tiles: string[]; odd: number; cols: number; color?: boolean };

export default function OddOne({ round, onEnd }: GameProps) {
  const rounds: Rd[] = round.rounds;
  const secs: number = round.seconds ?? 5;
  const fast: number = round.fast ?? 2.4;
  const [r, setR] = useState(0);
  const [left, setLeft] = useState(secs);
  const [hit, setHit] = useState<number | null>(null);
  const [results, setResults] = useState<number[]>([]);
  const rd = rounds[Math.min(r, rounds.length - 1)];

  useFrames(hit === null && r < rounds.length, (s) => {
    setLeft(secs - s);
    if (s >= secs) pick(-1, s);
  }, r);

  const pick = (k: number, s = secs - left) => {
    if (hit !== null) return;
    const ok = k === rd.odd;
    const pts = ok ? (s <= fast ? 2 : 1) : 0;
    if (ok) buzz(18);
    setHit(k);
    const next = [...results, pts];
    setResults(next);
    later(ok ? 520 : 900, () => {
      setHit(null);
      if (r + 1 >= rounds.length) {
        const found = next.filter((p) => p > 0).length;
        onEnd({ score: next.reduce((a, b) => a + b, 0), max: rounds.length * 2, summary: `${found} of ${rounds.length} found`, stats: { rounds: next } });
        return;
      }
      setLeft(secs);
      setR(r + 1);
    });
  };

  return (
    <div className="mc-field mc-odd">
      <div className="mc-row"><Dots results={results} n={rounds.length} /><span className="mc-dim">Round {Math.min(r + 1, rounds.length)} of {rounds.length}</span></div>
      <TimerBar left={left} secs={secs} />
      <div className={"mc-grid" + (round.mono ? " mono" : "")} style={{ gridTemplateColumns: `repeat(${rd.cols}, 1fr)` }} key={r}>
        {rd.tiles.map((t, k) => {
          const st = hit === null ? "" : k === rd.odd ? " right" : k === hit ? " wrong" : " dim";
          return (
            <button
              key={k}
              className={"mc-cell" + (rd.color ? " swatch" : "") + st}
              style={rd.color ? { background: t } : undefined}
              disabled={hit !== null}
              onPointerDown={(e) => { e.preventDefault(); pick(k); }}
            >
              {rd.color ? "" : t}
            </button>
          );
        })}
      </div>
      {hit === -1 && <div className="tv-late">Time. It was the one in green.</div>}
    </div>
  );
}
