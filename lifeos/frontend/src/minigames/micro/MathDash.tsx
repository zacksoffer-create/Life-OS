// Quick math: five problems, a few seconds each, three answers to pick from. (Also "Make change" and "How many atoms?".)
import React, { useRef, useState } from "react";
import { buzz, Dots, GameProps, later, TimerBar, useFrames } from "./kit";

type P = { q: string; choices: string[]; answer: number };

export default function MathDash({ round, onEnd }: GameProps) {
  const probs: P[] = round.problems;
  const secs: number = round.seconds ?? 3.6;
  const [i, setI] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [left, setLeft] = useState(secs);
  const [results, setResults] = useState<number[]>([]);
  const times = useRef<number[]>([]);
  const t = useRef(0);
  const p = probs[Math.min(i, probs.length - 1)];

  useFrames(picked === null && i < probs.length, (s) => {
    t.current = s;
    setLeft(secs - s);
    if (s >= secs) answer(-1);
  }, i);

  const answer = (k: number) => {
    if (picked !== null) return;
    const ok = k === p.answer;
    times.current.push(Math.round(t.current * 10) / 10);
    setPicked(k);
    if (ok) buzz(15);
    const next = [...results, ok ? 2 : 0];
    setResults(next);
    later(ok ? 380 : 750, () => {
      setPicked(null);
      if (i + 1 >= probs.length) {
        const right = next.filter((x) => x).length;
        onEnd({ score: right, max: probs.length, summary: `${right} of ${probs.length}`, stats: { times: times.current } });
        return;
      }
      setLeft(secs);
      setI(i + 1);
    });
  };

  return (
    <div className="mc-field mc-math">
      <div className="mc-row"><Dots results={results} n={probs.length} /><span className="mc-dim">{round.prompt || "Quick math"}</span></div>
      <TimerBar left={left} secs={secs} />
      <div className={"mc-q" + (p.q.length > 12 ? " long" : "")} key={i}>{p.q}</div>
      <div className="mc-opts">
        {p.choices.map((c, k) => {
          const st = picked === null ? "" : k === p.answer ? "right" : k === picked ? "wrong" : "dim";
          return (
            <button key={k} className={"mc-opt " + st} disabled={picked !== null} onPointerDown={(e) => { e.preventDefault(); answer(k); }}>
              {c}
            </button>
          );
        })}
      </div>
      {picked === -1 && <div className="tv-late">Time.</div>}
    </div>
  );
}
