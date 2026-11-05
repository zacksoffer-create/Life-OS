// Quick hands: wait for it... then tap the instant it goes. Three tries; jumping early is a miss.
// The ruler skin drops a ruler for real and tells you where you caught it.
import React, { useEffect, useRef, useState } from "react";
import { buzz, Dots, GameProps, later, Pop, Tone, useFrames, useKeys } from "./kit";

const WAIT: Record<string, string> = { ruler: "Fingers ready…", catch: "Watch the ball…", hand: "Wait for the question…", test: "Wait for green…" };
const GO: Record<string, string> = { ruler: "It's falling!", catch: "Grab it!", hand: "Hand up!", test: "Tap!" };

export default function Reflex({ round, skin, onEnd }: GameProps) {
  const tries: { wait: number }[] = round.tries;
  const great: number = round.great_ms ?? 330;
  const ok: number = round.ok_ms ?? 520;
  const [i, setI] = useState(0);
  const [st, setSt] = useState<"wait" | "go" | "after">("wait");
  const [drop, setDrop] = useState(0);
  const [results, setResults] = useState<number[]>([]);
  const [pop, setPop] = useState<{ text: string; tone: Tone; k: number } | null>(null);
  const goAt = useRef(0);
  const timer = useRef(0);
  const ms = useRef<number[]>([]);
  const ruler = skin.id === "ruler";

  useEffect(() => {
    if (st !== "wait") return;
    timer.current = later(tries[i].wait * 1000, () => {
      goAt.current = performance.now();
      setSt("go");
    });
    return () => clearTimeout(timer.current);
  }, [i, st]); // eslint-disable-line react-hooks/exhaustive-deps

  useFrames(st === "go", (t) => {
    setDrop(t);
    if (t > 1.2) score(null);
  }, i);

  const score = (rt: number | null, early = false) => {
    if (st === "after") return;
    clearTimeout(timer.current);
    setSt("after");
    const pts = early || rt === null ? 0 : rt <= great ? 2 : rt <= ok ? 1 : 0;
    if (rt !== null) ms.current.push(Math.round(rt));
    if (pts) buzz(pts === 2 ? 25 : 12);
    const cm = rt === null ? 0 : Math.round(0.5 * 9.81 * (rt / 1000) ** 2 * 100);
    const text = early ? "Too early!" : rt === null ? "Too slow" : ruler ? `${cm} cm` : `${Math.round(rt)} ms`;
    setPop({ text, tone: pts === 2 ? "great" : pts ? "good" : "miss", k: i });
    const next = [...results, pts];
    setResults(next);
    later(900, () => {
      setPop(null);
      if (i + 1 >= tries.length) {
        const best = ms.current.length ? Math.min(...ms.current) : null;
        const summary = best === null ? "No clean catches" : ruler ? `Best catch at ${Math.round(0.5 * 9.81 * (best / 1000) ** 2 * 100)} cm` : `Best: ${best} ms`;
        onEnd({ score: next.reduce((a, b) => a + b, 0), max: tries.length * 2, summary, stats: { ms: ms.current } });
        return;
      }
      setDrop(0);
      setI(i + 1);
      setSt("wait");
    });
  };

  const tap = () => {
    if (st === "wait") score(null, true);
    else if (st === "go") score(performance.now() - goAt.current);
  };
  useKeys(tap);

  const fall = Math.min(100, 0.5 * 9.81 * drop * drop * 260); // px on screen, a little exaggerated so it reads
  return (
    <div className={"mc-field mc-reflex is-" + st} onPointerDown={(e) => { e.preventDefault(); tap(); }}>
      <div className="mc-row"><Dots results={results} n={tries.length} /><span className="mc-dim">Try {Math.min(i + 1, tries.length)} of {tries.length}</span></div>
      {ruler ? (
        <div className="mc-ruler-wrap">
          <div className="mc-ruler" style={{ transform: `translateY(${st === "wait" ? 0 : fall}px)` }}>
            {Array.from({ length: 12 }, (_, k) => <i key={k} />)}
          </div>
          <div className="mc-fingers" />
        </div>
      ) : (
        <div className="mc-light"><span>{st === "go" ? GO[skin.id] || "Tap!" : st === "wait" ? WAIT[skin.id] || "Wait for it…" : ""}</span></div>
      )}
      <Pop pop={pop} />
      <div className="mc-hint on">{st === "go" ? GO[skin.id] || "Tap!" : st === "wait" ? (ruler ? "Tap the second it drops" : "Don't jump early") : " "}</div>
    </div>
  );
}
