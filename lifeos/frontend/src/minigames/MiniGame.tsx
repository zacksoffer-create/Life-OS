// The mini game host: plays a round full screen inside the phone, then hands the score back.
// HTML games (frontend/public/minigames/*.html) run in a frame and talk through the LifeOS bridge (see README there).
// Built-in games (the quiz, and the quick class games in ./micro) are React components.
import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Micro, { MICRO } from "./micro/Micro";
import Trivia from "./Trivia";
import "./minigames.css";

export type MGConfig = {
  session: string; game: string; title: string; kind: "html" | "builtin"; file?: string; mode: string; skill: number; difficulty: number;
  seed: number; me: string; them?: string | null; college?: boolean; sport?: string; opponent?: string; label?: string;
  questions?: { q: string; choices: string[]; answer: number; subject: string }[]; subject?: string; seconds?: number;
  round?: any; skin?: { id: string; title: string; how: string; badge: string }; how?: string;
};
export type MGResult = { score: number; max: number; stats?: any; summary?: string };

export default function MiniGame({ config, onDone, onQuit }: { config: MGConfig; onDone: (r: MGResult) => void; onQuit: () => void }) {
  const frame = useRef<HTMLIFrameElement>(null);
  const [loading, setLoading] = useState(config.kind === "html");
  const done = useRef(false);

  useEffect(() => {
    if (config.kind !== "html") return;
    const send = () => frame.current?.contentWindow?.postMessage({ type: "lifeos:init", config }, "*");
    const onMsg = (e: MessageEvent) => {
      const d = e.data;
      if (!d || d.type !== "lifeos:minigame" || e.source !== frame.current?.contentWindow) return;
      if (d.event === "ready") {
        setLoading(false);
        send();
      } else if (d.event === "finish" && !done.current) {
        const r = d.result || {};
        const max = Number(r.max) || 1;
        const score = Math.max(0, Math.min(max, Number(r.score) || 0));
        done.current = true;
        onDone({ score, max, stats: r.stats, summary: r.summary });
      } else if (d.event === "quit") {
        onQuit();
      }
    };
    window.addEventListener("message", onMsg);
    const t = setTimeout(() => { setLoading(false); send(); }, 3000);
    return () => {
      window.removeEventListener("message", onMsg);
      clearTimeout(t);
    };
  }, [config]); // eslint-disable-line react-hooks/exhaustive-deps

  const host = document.getElementById("ph-portal");
  const body = (
    <div className="mg-wrap" role="dialog" aria-label={config.title}>
      <div className="mg-top">
        <div className="mg-title">
          <b>{config.title}</b>
          <span>{config.mode === "clutch" ? `Game on the line${config.opponent ? ` vs ${config.opponent}` : ""}` : config.mode === "quiz" || config.mode === "class" ? config.subject : config.label || "Just for fun"}</span>
        </div>
        <button className="mg-x" onClick={onQuit} aria-label="Stop">✕</button>
      </div>
      <div className="mg-stage">
        {config.kind === "html" ? (
          <>
            <iframe ref={frame} className="mg-frame" title={config.title} src={`minigames/${config.file}?embed=1`} allow="autoplay; fullscreen" />
            {loading && <div className="mg-loading"><span className="ph-spinner" /></div>}
          </>
        ) : config.game === "trivia" ? (
          <Trivia config={config} onDone={(r) => { if (!done.current) { done.current = true; onDone(r); } }} />
        ) : MICRO[config.game] ? (
          <Micro config={config} onDone={(r) => { if (!done.current) { done.current = true; onDone(r); } }} />
        ) : (
          <div className="mg-loading">This game isn't built yet.</div>
        )}
      </div>
    </div>
  );
  return host ? createPortal(body, host) : body;
}
