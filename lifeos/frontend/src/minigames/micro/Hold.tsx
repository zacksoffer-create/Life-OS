// Hold it: press and hold, the level rises (faster the longer you hold), let go on the line. Three tries.
import React, { useRef, useState } from "react";
import { buzz, Dots, GameProps, later, Pop, Tone, useFrames, useKeys } from "./kit";

const LOOK: Record<string, { color: string; label: string; flat?: boolean }> = {
  beaker: { color: "#4fd1c5", label: "Pour" },
  throw: { color: "#ff9459", label: "Wind up" },
  brush: { color: "#2d3a8c", label: "Draw", flat: true },
  note: { color: "#b18cff", label: "Hold the note", flat: true },
  pour: { color: "#5ab0ff", label: "Fill" },
};

export default function Hold({ round, skin, onEnd }: GameProps) {
  const tries: { center: number; hw: number; T: number }[] = round.tries;
  const near: number = round.near ?? 0.05;
  const look = LOOK[skin.id] || LOOK.pour;
  const [i, setI] = useState(0);
  const [level, setLevel] = useState(0);
  const [holding, setHolding] = useState(false);
  const [results, setResults] = useState<number[]>([]);
  const [pop, setPop] = useState<{ text: string; tone: Tone; k: number } | null>(null);
  const live = useRef({ holding: false, level: 0, locked: false });
  const tr = tries[Math.min(i, tries.length - 1)];

  useFrames(holding, (t) => {
    const l = Math.min(1, (t / tr.T) ** (round.curve ?? 1.35));
    live.current.level = l;
    setLevel(l);
    if (l >= 1) release();
  }, i);

  const press = () => {
    if (live.current.locked || live.current.holding || i >= tries.length) return;
    live.current.holding = true;
    setHolding(true);
    buzz(6);
  };

  const release = () => {
    if (!live.current.holding) return;
    live.current.holding = false;
    live.current.locked = true;
    setHolding(false);
    const l = live.current.level;
    const d = Math.abs(l - tr.center);
    const pts = l >= 1 ? 0 : d <= tr.hw ? 2 : d <= tr.hw + near ? 1 : 0;
    const text = l >= 1 ? (skin.id === "beaker" || skin.id === "pour" ? "Spilled!" : "Too far!") : d <= tr.hw * 0.35 ? "Perfect!" : pts === 2 ? "On the line" : pts === 1 ? (l > tr.center ? "A bit over" : "A bit short") : l > tr.center ? "Way over" : "Too short";
    if (pts) buzz(pts === 2 ? 25 : 12);
    setPop({ text, tone: pts === 2 ? "great" : pts ? "good" : "miss", k: i });
    const next = [...results, pts];
    setResults(next);
    later(800, () => {
      setPop(null);
      if (i + 1 >= tries.length) {
        const hits = next.filter((p) => p === 2).length;
        onEnd({ score: next.reduce((a, b) => a + b, 0), max: tries.length * 2, summary: `${hits} of ${tries.length} on the line`, stats: { tries: next } });
        return;
      }
      live.current.level = 0;
      live.current.locked = false;
      setLevel(0);
      setI(i + 1);
    });
  };

  useKeys(press, release);
  const band = { lo: tr.center - tr.hw, hi: tr.center + tr.hw };
  const pos = (v: number) => `${Math.max(0, Math.min(1, v)) * 100}%`;
  return (
    <div
      className="mc-field mc-hold"
      onPointerDown={(e) => { e.preventDefault(); press(); }}
      onPointerUp={release}
      onPointerLeave={release}
      onPointerCancel={release}
      onContextMenu={(e) => e.preventDefault()}
    >
      <div className="mc-row"><Dots results={results} n={tries.length} /><span className="mc-dim">Try {Math.min(i + 1, tries.length)} of {tries.length}</span></div>
      <div className={"mc-vessel" + (look.flat ? " flat" : "") + " sk-" + skin.id} style={{ ["--fill" as any]: look.color }}>
        <div className="mc-near" style={look.flat ? { left: pos(band.lo - near), width: pos(band.hi - band.lo + 2 * near) } : { bottom: pos(band.lo - near), height: pos(band.hi - band.lo + 2 * near) }} />
        <div className="mc-band" style={look.flat ? { left: pos(band.lo), width: pos(band.hi - band.lo) } : { bottom: pos(band.lo), height: pos(band.hi - band.lo) }} />
        <div className="mc-liquid" style={look.flat ? { width: pos(level) } : { height: pos(level) }} />
        <div className="mc-mark" style={look.flat ? { left: pos(tr.center) } : { bottom: pos(tr.center) }} />
      </div>
      <Pop pop={pop} />
      <div className={"mc-hint" + (holding ? " on" : "")}>{holding ? "Let go on the line" : `Press and hold to ${look.label.toLowerCase()}`}</div>
    </div>
  );
}
