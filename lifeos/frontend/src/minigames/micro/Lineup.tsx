// In order: tap the cards in the right order (oldest first, smallest first, ABC...). Two rounds; one wrong tap ends a round.
import React, { useState } from "react";
import { buzz, Dots, GameProps, later, TimerBar, useFrames } from "./kit";

type Item = { label: string; value: any; reveal?: string; color?: string };
type Rd = { items: Item[]; order: number[]; how: string; show: string };

export default function Lineup({ round, onEnd }: GameProps) {
  const rounds: Rd[] = round.rounds;
  const secs: number = round.seconds ?? 8;
  const [r, setR] = useState(0);
  const [taps, setTaps] = useState<number[]>([]);
  const [bad, setBad] = useState<number | null>(null);
  const [over, setOver] = useState(false);
  const [left, setLeft] = useState(secs);
  const [results, setResults] = useState<number[]>([]);
  const [score, setScore] = useState(0);
  const rd = rounds[Math.min(r, rounds.length - 1)];

  useFrames(!over && r < rounds.length, (s) => {
    setLeft(secs - s);
    if (s >= secs) finish(taps.length);
  }, r);

  const finish = (got: number) => {
    if (over) return;
    setOver(true);
    const total = score + got;
    setScore(total);
    const n = rd.items.length;
    const next = [...results, got >= n ? 2 : got >= n / 2 ? 1 : 0];
    setResults(next);
    if (got >= n) buzz(25);
    later(rd.show === "reveal" || got < n ? 1400 : 700, () => {
      if (r + 1 >= rounds.length) {
        const max = rounds.reduce((a, b) => a + b.items.length, 0);
        onEnd({ score: total, max, summary: `${total} of ${max} in place`, stats: { rounds: next } });
        return;
      }
      setTaps([]);
      setBad(null);
      setOver(false);
      setLeft(secs);
      setR(r + 1);
    });
  };

  const tap = (k: number) => {
    if (over || taps.includes(k)) return;
    if (rd.order[taps.length] === k) {
      buzz(8);
      const t = [...taps, k];
      setTaps(t);
      if (t.length >= rd.items.length) finish(t.length);
    } else {
      setBad(k);
      finish(taps.length);
    }
  };

  return (
    <div className="mc-field mc-line">
      <div className="mc-row"><Dots results={results} n={rounds.length} /><span className="mc-dim">{rd.how}</span></div>
      <TimerBar left={left} secs={secs} />
      <div className="mc-cards" key={r}>
        {rd.items.map((it, k) => {
          const at = taps.indexOf(k);
          const rank = rd.order.indexOf(k);
          const st = at >= 0 ? " ok" : bad === k ? " bad" : over ? " shown" : "";
          return (
            <button key={k} className={"mc-card" + st} disabled={over || at >= 0} onPointerDown={(e) => { e.preventDefault(); tap(k); }}
              style={{ animationDelay: `${k * 50}ms` }}>
              <span className="mc-n">{at >= 0 ? at + 1 : over ? rank + 1 : ""}</span>
              {it.color && <span className="mc-sw" style={{ background: it.color }} />}
              <b>{it.label}</b>
              {over && it.reveal && <small>{it.reveal}</small>}
            </button>
          );
        })}
      </div>
    </div>
  );
}
