// The quick class games: one intro (what it is, how to play, one tap to start), the game, one result screen.
// Every game reports score/max; great is 80%+, good 50%+, like every other mini game.
import React, { useState } from "react";
import type { MGConfig, MGResult } from "../MiniGame";
import Flash from "./Flash";
import Hold from "./Hold";
import { buzz, Ended, GameProps, Skin } from "./kit";
import Lineup from "./Lineup";
import MathDash from "./MathDash";
import OddOne from "./OddOne";
import Reflex from "./Reflex";
import Sweep from "./Sweep";

export const MICRO: Record<string, (p: GameProps) => JSX.Element> = { hold: Hold, sweep: Sweep, mathdash: MathDash, flash: Flash, oddone: OddOne, lineup: Lineup, reflex: Reflex };

const GLYPH: Record<string, string> = { hold: "◐", sweep: "◠", mathdash: "±", flash: "▦", oddone: "◇", lineup: "123", reflex: "⚡" };
const HEAD = {
  great: ["Nailed it.", "Clean.", "Too easy."],
  good: ["Not bad.", "Solid.", "You'll take it."],
  miss: ["Rough one.", "Not today.", "Next time."],
};

export default function Micro({ config, onDone }: { config: MGConfig; onDone: (r: MGResult) => void }) {
  const [phase, setPhase] = useState<"intro" | "play" | "done">("intro");
  const [res, setRes] = useState<Ended | null>(null);
  const Game = MICRO[config.game];
  const skin: Skin = config.skin || { id: "generic", title: config.title, how: "", badge: "Just for fun" };
  if (!Game) return <div className="mg-loading">This game isn't built yet.</div>;

  if (phase === "intro") {
    return (
      <div className="tv tv-intro mc-intro">
        <div className="tv-badge">{skin.badge}</div>
        <div className={"mc-glyph g-" + config.game} aria-hidden>{GLYPH[config.game]}</div>
        <h2>{skin.title}</h2>
        <p>{skin.how}</p>
        <button className="tv-go" onClick={() => { buzz(10); setPhase("play"); }}>Go</button>
      </div>
    );
  }
  if (phase === "play") {
    return (
      <div className="tv mc-stage">
        <Game round={config.round} skin={skin} onEnd={(r) => { setRes(r); setPhase("done"); }} />
      </div>
    );
  }
  const pct = res && res.max ? res.score / res.max : 0;
  const tier = pct >= 0.8 ? "great" : pct >= 0.5 ? "good" : "miss";
  const head = HEAD[tier][(config.seed || 0) % 3];
  return (
    <div className="tv tv-intro mc-result">
      <div className={"tv-score " + tier}>{Math.round(pct * 100)}<small>%</small></div>
      <h2>{head}</h2>
      <p>{res?.summary}</p>
      <button className="tv-go" onClick={() => res && onDone({ score: res.score, max: res.max, stats: res.stats, summary: res.summary })}>
        {config.mode === "class" ? "Back to class" : "Done"}
      </button>
    </div>
  );
}
