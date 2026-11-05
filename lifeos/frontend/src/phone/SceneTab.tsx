// The Scene tab: your school, live. The Ladder (who's popular, who's moving and why, what your standing is made of, the
// superlatives, the full rankings), the Crowd (the groups and your way in, people you could meet) and the Talk (what
// people are saying, who's fighting, who's together). Tap anyone on the ladder to make a move.
import React, { useEffect, useState } from "react";
import { Chip, LadderRow, LadderView, Line, phoneApi, pgo, SceneMini } from "./api";
import { Portrait } from "./art";
import { cx, errText, Lines, Sheet, StatChips } from "./kit";
import { usePhone } from "./PhoneContext";
import { SceneScreen } from "./Scene";

const SECTIONS = [["ladder", "Ladder"], ["crowd", "Crowd"], ["talk", "Talk"]] as const;
const SCOPES: [string, string][] = [["school", "Whole school"], ["grade", "My grade"], ["9", "Fr"], ["10", "So"], ["11", "Jr"], ["12", "Sr"]];
const TAG: Record<string, string> = { you: "you", friend: "friend", family: "family", crush: "crush", dating: "dating", rival: "rival", storyline: "your story" };

function Face({ p, size = 40 }: { p: SceneMini; size?: number }) {
  return <Portrait look={p.look} size={size} color={p.color} name={p.first} />;
}

function Move({ m }: { m: number | null | undefined }) {
  if (m === null || m === undefined) return null;
  if (m === 0) return <span className="ld-move same">–</span>;
  return <span className={cx("ld-move", m > 0 ? "up" : "down")}>{m > 0 ? "▲" : "▼"}{Math.abs(m)}</span>;
}

export default function SceneTab({ route }: { route: string[] }) {
  const sec = (SECTIONS.find(([k]) => k === route[0]) || SECTIONS[0])[0];
  return (
    <div className="pm-root sct">
      <header className="pm-head">
        <h1>Scene</h1>
        <div className="pm-seg" role="tablist">
          {SECTIONS.map(([k, l]) => (
            <button key={k} role="tab" aria-selected={sec === k} className={sec === k ? "on" : ""} onClick={() => pgo(k === "ladder" ? "scene" : `scene/${k}`)}>{l}</button>
          ))}
        </div>
      </header>
      <div className="pm-scroll">{sec === "ladder" ? <Ladder /> : <SceneScreen key={sec} section={sec} />}</div>
    </div>
  );
}

function Ladder() {
  const { toast, refresh } = usePhone();
  const [scope, setScope] = useState("school");
  const [v, setV] = useState<LadderView | null>(null);
  const [shown, setShown] = useState(25);
  const [who, setWho] = useState<LadderRow | null>(null);
  const [out, setOut] = useState<{ lines: Line[]; chips: Chip[]; title: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const load = (s = scope) => phoneApi.ladder(s).then(setV).catch((e) => toast(errText(e), "bad"));
  useEffect(() => {
    load(scope);
    setShown(25);
  }, [scope]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!v) return <div className="pm-empty"><span className="ph-spinner" /></div>;
  const y = v.you;

  const intro = async (via: string, to: string) => {
    setBusy(true);
    try {
      const r = await phoneApi.sceneIntro(via, to);
      setWho(null);
      setOut({ lines: r.lines, chips: r.chips, title: "Introduced" });
      load();
      refresh();
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(false);
    }
  };
  const plan = async (id: string) => {
    try {
      toast((await phoneApi.scenePlan(id)).note, "good");
      setWho(null);
      refresh();
    } catch (e) {
      toast(errText(e), "bad");
    }
  };

  return (
    <div className="ld">
      <YouCard v={v} onWho={setWho} />

      <div className="sc-h">What your standing is made of</div>
      <div className="ld-parts">
        {y.parts.map((p) => (
          <div key={p.key} className="ld-part">
            <div className="ld-part-h"><b>{p.label}</b><i><span style={{ width: `${Math.max(4, Math.min(100, p.score))}%` }} /></i></div>
            <small>{p.line}</small>
          </div>
        ))}
        <div className="ld-tip"><b>Your next move</b>{y.tip}</div>
      </div>

      {y.this_week.length > 0 && (
        <>
          <div className="sc-h">Your week</div>
          <div className="ld-week">{y.this_week.map((e, k) => <div key={k}><p>{e.text}</p><small>{e.date}</small></div>)}</div>
        </>
      )}

      {v.storyline_people.length > 0 && (
        <>
          <div className="sc-h">Your storylines' people</div>
          <div className="ld-cast">
            {v.storyline_people.map((p) => (
              <button key={p.id} onClick={() => setWho(p)}>
                <Face p={p} size={52} />
                <b>{p.first}</b>
                <small>{p.rank ? <>#{p.rank} <Move m={p.move} /></> : p.known_for}</small>
                <em>{p.storylines[0]}</em>
              </button>
            ))}
          </div>
        </>
      )}

      <div className="sc-h">Who's moving{v.week_of ? <small> since {v.week_of.replace(/^\w+, /, "")}</small> : null}</div>
      {!v.movers.up.length && !v.movers.down.length ? (
        <div className="sc-dim">Nobody's moved yet. Rankings update every week: check back after the next one.</div>
      ) : (
        <div className="ld-movers">
          {[["Rising", v.movers.up], ["Falling", v.movers.down]].map(([label, list]) => (list as LadderRow[]).length > 0 && (
            <div key={label as string}>
              <div className="sc-sub">{label as string}</div>
              {(list as LadderRow[]).map((p) => (
                <button key={p.id} className="ld-mover" onClick={() => setWho(p)}>
                  <Face p={p} size={38} />
                  <span><b>{p.first} <Move m={p.move} /></b><small>{p.why || `#${p.rank} now`}</small></span>
                </button>
              ))}
            </div>
          ))}
        </div>
      )}

      <div className="sc-h">Superlatives</div>
      <div className="ld-sup">
        {v.superlatives.map((s) => (
          <div key={s.key} className={cx("ld-sup-c", s.winner.you && "you")}>
            <small>{s.label}</small>
            <div className="ld-sup-w">
              <Face p={s.winner} size={44} />
              {s.partner && <span className="ld-sup-p"><Face p={s.partner} size={44} /></span>}
            </div>
            <b>{s.winner.you ? "You" : s.winner.first}{s.partner ? ` & ${s.partner.first}` : ""}</b>
            {!s.winner.you && s.you && s.you <= 10 && <em>You're #{s.you}</em>}
          </div>
        ))}
      </div>

      <div className="sc-h">The rankings</div>
      <div className="ld-scopes">
        {SCOPES.map(([k, l]) => <button key={k} className={cx(scope === k && "on")} onClick={() => setScope(k)}>{l}</button>)}
      </div>
      <div className="ld-rows">
        {v.rows.slice(0, shown).map((r) => (
          <button key={r.id} className={cx("ld-row", r.tags.includes("you") && "you", (r.scope_rank || 0) <= 3 && "top")} onClick={() => !r.tags.includes("you") && setWho(r)}>
            <span className="ld-n">{r.scope_rank}</span>
            <Face p={r} size={38} />
            <span className="ld-row-m">
              <b>{r.tags.includes("you") ? "You" : r.name}</b>
              <small>{[r.known_for, scope === "school" ? r.year : null].filter(Boolean).join(" · ")}</small>
              {r.tags.filter((t) => t !== "you").length > 0 && (
                <span className="ld-tags">{r.tags.filter((t) => t !== "you").map((t) => <i key={t} className={"t-" + t}>{TAG[t] || t}</i>)}</span>
              )}
            </span>
            <Move m={r.move} />
          </button>
        ))}
      </div>
      {v.rows.length > shown && <button className="ph-more" onClick={() => setShown(shown + 50)}>Show more ({v.rows.length - shown})</button>}
      <div style={{ height: 24 }} />

      <PersonSheet p={who} busy={busy} onClose={() => setWho(null)} onIntro={intro} onPlan={plan} />
      <Sheet open={!!out} onClose={() => setOut(null)} title={out?.title}>
        {out && <><Lines lines={out.lines} /><StatChips chips={out.chips} /><button className="ph-btn primary block" onClick={() => setOut(null)}>Nice</button></>}
      </Sheet>
    </div>
  );
}

function YouCard({ v, onWho }: { v: LadderView; onWho: (p: LadderRow) => void }) {
  const y = v.you;
  const h = y.history;
  // your rank over time, zoomed to your own range (better ranks higher up)
  const lo = Math.min(...h.map((x) => x.rank)), hi = Math.max(...h.map((x) => x.rank));
  const pts = h.length >= 2 ? h.map((x, i) => [i / (h.length - 1), hi === lo ? 0.5 : (x.rank - lo) / (hi - lo)]) : [];
  return (
    <div className="ld-you">
      <div className="ld-you-top">
        <div className="ld-rank"><b>#{y.rank}</b><small>of {y.of}</small></div>
        <div className="ld-you-m">
          <b>{y.tier}</b>
          <span>#{y.grade_rank} of {y.grade_of} {y.grade_label.toLowerCase()} <Move m={y.move} /></span>
        </div>
      </div>
      {pts.length > 1 && (
        <svg className="ld-spark" viewBox="0 0 100 30" preserveAspectRatio="none" aria-label="Your rank over time">
          <polyline points={pts.map(([x, yy]) => `${x * 100},${2 + yy * 26}`).join(" ")} />
        </svg>
      )}
      {pts.length > 1 && <small className="ld-spark-l">Since {h[0].date.replace(/^\w+, /, "")}: {h[0].rank > y.rank ? `up ${h[0].rank - y.rank}` : h[0].rank < y.rank ? `down ${y.rank - h[0].rank}` : "holding steady"} · best #{lo}{hi !== lo ? `, lowest #${hi}` : ""}</small>}
      {y.next_up && (
        <button className="ld-next" onClick={() => onWho(y.next_up!)}>
          <Face p={y.next_up} size={30} />
          <span>Next up: <b>{y.next_up.first}</b> at #{y.next_up.rank}{y.next_up.known_for ? `, ${y.next_up.known_for}` : ""}</span>
        </button>
      )}
      {!y.next_up && <div className="ld-next top">You're the most popular person at school.</div>}
    </div>
  );
}

function PersonSheet({ p, busy, onClose, onIntro, onPlan }: {
  p: LadderRow | null; busy: boolean; onClose: () => void; onIntro: (via: string, to: string) => void; onPlan: (id: string) => void;
}) {
  return (
    <Sheet open={!!p} onClose={onClose} title={p?.name}>
      {p && (
        <div className="ld-person">
          <div className="ld-person-top">
            <Face p={p} size={64} />
            <div>
              <b>{p.rank ? `#${p.rank} at school` : p.known_for} <Move m={p.move} /></b>
              <small>{[p.year, p.rank ? p.known_for : null].filter(Boolean).join(" · ")}</small>
              {p.label && <small>To you: {p.label}</small>}
              {p.tags.length > 0 && <span className="ld-tags">{p.tags.map((t) => <i key={t} className={"t-" + t}>{TAG[t] || t}</i>)}</span>}
            </div>
          </div>
          {p.storylines.length > 0 && <p className="ph-dim small">In your storylines: {p.storylines.join(", ")}.</p>}
          {p.why && <p className="ph-dim small">Lately: {p.why}</p>}
          <div className="ld-acts">
            {p.via && <button className="ph-btn primary block" disabled={busy} onClick={() => onIntro(p.via!.id, p.id)}>Ask {p.via.first} to introduce you</button>}
            {(p.tags.includes("friend") || p.tags.includes("family") || p.tags.includes("dating") || p.tags.includes("crush")) &&
              <button className="ph-btn primary block" onClick={() => onPlan(p.id)}>Make plans with {p.first}</button>}
            <button className="ph-btn block" onClick={() => pgo(`phone/contact/${encodeURIComponent(p.id)}`)}>{p.label ? `Text ${p.first}` : `About ${p.first}`}</button>
          </div>
          {!p.via && !p.label && <p className="ph-dim small">You don't know {p.first} yet, and none of your friends do either. Their circle is the way in: see the Crowd.</p>}
        </div>
      )}
    </Sheet>
  );
}
