// Stop it: a needle swings back and forth; tap to stop it in the zone. Three tries, a little faster each time.
// The pendulum skin swings like a real one (fastest at the bottom, where the zone is).
import React, { useRef, useState } from "react";
import { buzz, Dots, GameProps, later, Pop, Tone, useFrames, useKeys } from "./kit";

const LABEL: Record<string, string> = { pendulum: "Stop it at the bottom", beat: "Hit the beat", jump: "Jump in on the zone", signal: "Hit the window" };
const CX = 100;
const CY = 108;
const R = 88;

function pt(a: number, r = R) {
  const rad = ((a - 90) * Math.PI) / 180;
  return [CX + r * Math.cos(rad), CY + r * Math.sin(rad)];
}
function arc(a0: number, a1: number, r = R) {
  const [x0, y0] = pt(a0, r);
  const [x1, y1] = pt(a1, r);
  return `M ${x0} ${y0} A ${r} ${r} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${x1} ${y1}`;
}

export default function Sweep({ round, skin, onEnd }: GameProps) {
  const tries: { center: number; hw: number; speed: number; phase: number }[] = round.tries;
  const near: number = round.near ?? 0.05;
  const timeout: number = round.timeout ?? 4.5;
  const pend = skin.id === "pendulum";
  const [i, setI] = useState(0);
  const [x, setX] = useState(0.5);
  const [going, setGoing] = useState(true);
  const [results, setResults] = useState<number[]>([]);
  const [pop, setPop] = useState<{ text: string; tone: Tone; k: number } | null>(null);
  const live = useRef({ x: 0.5, done: false });
  const tr = tries[Math.min(i, tries.length - 1)];

  const posAt = (t: number) => {
    const u = tr.phase + t * tr.speed;
    if (pend) return 0.5 + 0.5 * Math.sin(2 * Math.PI * u);
    const f = u - Math.floor(u);
    return f < 0.5 ? f * 2 : 2 - f * 2;
  };

  useFrames(going, (t) => {
    const v = posAt(t);
    live.current.x = v;
    setX(v);
    if (t > timeout) stop(true);
  }, i);

  const stop = (late = false) => {
    if (live.current.done || i >= tries.length) return;
    live.current.done = true;
    setGoing(false);
    const d = Math.abs(live.current.x - tr.center);
    const pts = late ? 0 : d <= tr.hw ? 2 : d <= tr.hw + near ? 1 : 0;
    if (pts) buzz(pts === 2 ? 25 : 12);
    setPop({ text: late ? "Too slow" : d <= tr.hw * 0.3 ? "Perfect!" : pts === 2 ? "Got it" : pts === 1 ? "Close" : "Missed", tone: pts === 2 ? "great" : pts ? "good" : "miss", k: i });
    const next = [...results, pts];
    setResults(next);
    later(750, () => {
      setPop(null);
      if (i + 1 >= tries.length) {
        const hits = next.filter((p) => p === 2).length;
        onEnd({ score: next.reduce((a, b) => a + b, 0), max: tries.length * 2, summary: `${hits} of ${tries.length} in the zone`, stats: { tries: next } });
        return;
      }
      live.current.done = false;
      setI(i + 1);
      setGoing(true);
    });
  };

  useKeys(() => stop());
  const ang = (v: number) => (pend ? (v - 0.5) * 110 : -90 + v * 180);
  const z0 = ang(tr.center - tr.hw);
  const z1 = ang(tr.center + tr.hw);
  const n0 = ang(Math.max(0, tr.center - tr.hw - near));
  const n1 = ang(Math.min(1, tr.center + tr.hw + near));
  return (
    <div className="mc-field mc-sweep" onPointerDown={(e) => { e.preventDefault(); stop(); }}>
      <div className="mc-row"><Dots results={results} n={tries.length} /><span className="mc-dim">Try {Math.min(i + 1, tries.length)} of {tries.length}</span></div>
      {pend ? (
        <svg viewBox="0 0 200 150" className="mc-gauge">
          <line x1="40" y1="8" x2="160" y2="8" className="mc-g-beam" />
          <path d={`M ${100 + 120 * Math.sin((n0 * Math.PI) / 180)} ${8 + 120 * Math.cos((n0 * Math.PI) / 180)} A 120 120 0 0 0 ${100 + 120 * Math.sin((n1 * Math.PI) / 180)} ${8 + 120 * Math.cos((n1 * Math.PI) / 180)}`} className="mc-g-near" />
          <path d={`M ${100 + 120 * Math.sin((z0 * Math.PI) / 180)} ${8 + 120 * Math.cos((z0 * Math.PI) / 180)} A 120 120 0 0 0 ${100 + 120 * Math.sin((z1 * Math.PI) / 180)} ${8 + 120 * Math.cos((z1 * Math.PI) / 180)}`} className="mc-g-zone" />
          <g transform={`rotate(${-ang(x)} 100 8)`}>
            <line x1="100" y1="8" x2="100" y2="118" className="mc-g-rod" />
            <circle cx="100" cy="122" r="11" className="mc-g-bob" />
          </g>
          <circle cx="100" cy="8" r="4" className="mc-g-hub" />
        </svg>
      ) : (
        <svg viewBox="0 0 200 122" className="mc-gauge">
          <path d={arc(-90, 90)} className="mc-g-track" />
          <path d={arc(n0, n1)} className="mc-g-near" />
          <path d={arc(z0, z1)} className="mc-g-zone" />
          <g transform={`rotate(${ang(x)} ${CX} ${CY})`}>
            <line x1={CX} y1={CY} x2={CX} y2={CY - R + 6} className="mc-g-needle" />
          </g>
          <circle cx={CX} cy={CY} r="7" className="mc-g-hub" />
        </svg>
      )}
      <Pop pop={pop} />
      <div className="mc-hint on">{LABEL[skin.id] || "Tap to stop it in the zone"}</div>
    </div>
  );
}
