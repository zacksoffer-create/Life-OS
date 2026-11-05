// The quiz: one question at a time, a timer, instant feedback. Used for class quizzes, midterms and finals.
import React, { useEffect, useRef, useState } from "react";
import type { MGConfig, MGResult } from "./MiniGame";

const SUBJECT: Record<string, string> = {
  english: "English", math: "Math", biology: "Biology", chemistry: "Chemistry", physics: "Physics", us_history: "U.S. History",
  world_history: "World History", government: "Government", spanish: "Spanish", health: "Health", art: "Art", music: "Music",
  tech: "Tech", psychology: "Psychology", economics: "Economics", general: "Trivia",
};

export default function Trivia({ config, onDone }: { config: MGConfig; onDone: (r: MGResult) => void }) {
  const qs = config.questions || [];
  const secs = config.seconds || 15;
  const [i, setI] = useState(-1);
  const [picked, setPicked] = useState<number | null>(null);
  const [right, setRight] = useState(0);
  const [streak, setStreak] = useState(0);
  const [left, setLeft] = useState(secs);
  const times = useRef<number[]>([]);
  const t0 = useRef(0);
  const q = i >= 0 ? qs[i] : null;

  useEffect(() => {
    if (i < 0 || i >= qs.length || picked !== null) return;
    t0.current = performance.now();
    setLeft(secs);
    const id = setInterval(() => {
      const l = secs - (performance.now() - t0.current) / 1000;
      if (l <= 0) {
        clearInterval(id);
        answer(-1);
      } else setLeft(l);
    }, 100);
    return () => clearInterval(id);
  }, [i, picked]); // eslint-disable-line react-hooks/exhaustive-deps

  const answer = (k: number) => {
    if (!q || picked !== null) return;
    const ok = k === q.answer;
    times.current.push(Math.round((performance.now() - t0.current) / 100) / 10);
    setPicked(k);
    if (ok) {
      setRight((r) => r + 1);
      setStreak((s) => s + 1);
      if (navigator.vibrate) navigator.vibrate(15);
    } else setStreak(0);
    setTimeout(() => {
      setPicked(null);
      if (i + 1 >= qs.length) setI(qs.length);
      else setI(i + 1);
    }, ok ? 750 : 1400);
  };

  if (i < 0) {
    return (
      <div className="tv tv-intro">
        <div className="tv-badge">{config.subject || "Quiz"}</div>
        <h2>{config.mode === "class" ? config.title : `${qs.length} questions`}</h2>
        <p>{config.mode === "class" ? `${qs.length} quick questions, ${secs} seconds each.` : `${secs} seconds each. Tap the right answer before the bar runs out.`}</p>
        <button className="tv-go" onClick={() => setI(0)}>Start</button>
      </div>
    );
  }
  if (i >= qs.length) {
    const pct = qs.length ? right / qs.length : 0;
    return (
      <div className="tv tv-intro">
        <div className={"tv-score " + (pct >= 0.8 ? "great" : pct >= 0.5 ? "good" : "miss")}>{right}<small>/{qs.length}</small></div>
        <h2>{pct >= 0.8 ? "Nailed it." : pct >= 0.5 ? "Not bad." : "Rough one."}</h2>
        <p>{pct >= 0.8 ? "That one's going on the fridge." : pct >= 0.5 ? "You'll take it." : "There's always the next one."}</p>
        <button className="tv-go" onClick={() => onDone({ score: right, max: qs.length, stats: { times: times.current }, summary: `${right} of ${qs.length}` })}>
          {config.mode === "class" ? "Back to class" : "Hand it in"}
        </button>
      </div>
    );
  }
  return (
    <div className="tv">
      <div className="tv-head">
        <span>{SUBJECT[q!.subject] || q!.subject} · {i + 1} of {qs.length}</span>
        <span>{streak >= 2 ? `🔥 ${streak} in a row` : `${right} right`}</span>
      </div>
      <div className="tv-timer"><i style={{ width: `${(left / secs) * 100}%` }} className={left < 4 ? "low" : ""} /></div>
      <div className="tv-q" key={i}>{q!.q}</div>
      <div className="tv-opts">
        {q!.choices.map((c, k) => {
          const state = picked === null ? "" : k === q!.answer ? "right" : k === picked ? "wrong" : "dim";
          return (
            <button key={k} className={"tv-opt " + state} disabled={picked !== null} onClick={() => answer(k)}>
              <span className="tv-l">{"ABCD"[k]}</span>{c}
            </button>
          );
        })}
      </div>
      {picked === -1 && <div className="tv-late">Time's up.</div>}
    </div>
  );
}
