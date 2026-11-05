// Story Schedule (Lab): the story scheduler's controls and diagnostics. Pacing, today's queue, every storyline's counts,
// every scene's state with the exact reason it's waiting or can't happen, an episode timeline with chain arrows and
// warnings, a profile comparison on the same seed, the season map, and the dry-run report.
import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import { Panel, Tabs, Tag, cx } from "../ui";

type Row = { sid: string; pack: string; title: string; importance: string; window: any; window_rule: string | null; window_text: string; order: number;
  state: string; day?: number; date?: string; reason?: string; detail?: any; why: string; last?: any };
type Status = {
  /** season map rules, with each rule's window on this school's calendar */
  profile: string; profiles: Record<string, { label: string; about: string }>; settings: Record<string, any>; overrides: Record<string, any>;
  auto_scenes: boolean; day: number; date: string; queue: { sid: string; title: string; phase: string; importance: string; due: boolean }[];
  presented_today: number; target_today: number | null; backlog: number; oldest: number | null; overdue: number; majors_this_week: number;
  storylines: { pack: string; name: string; in_order: boolean; [k: string]: any }[]; scenes: Row[]; weights: Record<string, number>;
  migrated: { day: number; newly_eligible: string[] } | null; season_map: { id: string; label?: string; window_text?: string; anchor?: string }[];
};
type Timeline = { items: { sid: string; day: number; date: string; pack: string; importance: string; title: string; after: string[] }[];
  warnings: { sid: string; kind: string; text: string }[]; lanes: string[] };
type Compare = { days: number; runs: { profile: string; played: number; max_per_day: number; days_with_scenes: number; per_day: number[]; warnings: number; deadline_misses: number }[] };

const STATES = ["played", "presented", "queued", "eligible", "waiting", "expired", "unreachable"];
const TONE: Record<string, string> = { played: "good", queued: "warm", eligible: "warm", presented: "warm", waiting: "info", unreachable: "bad", expired: "bad" };
const MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const IMP_COLOR: Record<string, string> = { ambient: "#646c94", regular: "#6bb6ff", major: "#ffb547", finale: "#ff6b81" };

export default function Schedule() {
  const { toast, refresh } = useStore();
  const [st, setSt] = useState<Status | null>(null);
  const [tab, setTab] = useState("scenes");
  const [busy, setBusy] = useState<string | null>(null);
  const [filter, setFilter] = useState<{ state: string; pack: string; q: string }>({ state: "", pack: "", q: "" });
  const [tl, setTl] = useState<Timeline | null>(null);
  const [cmp, setCmp] = useState<Compare | null>(null);
  const [days, setDays] = useState(60);
  const load = () => api.get("/api/story/schedule").then(setSt).catch((e) => toast(e.message, "bad"));
  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (tab === "timeline") api.get("/api/story/schedule/timeline").then(setTl).catch((e) => toast(e.message, "bad"));
  }, [tab, st?.day, st?.presented_today]); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (key: string, fn: () => Promise<any>) => {
    setBusy(key);
    try {
      await fn();
    } catch (e: any) {
      toast(e.message, "bad");
    } finally {
      setBusy(null);
    }
  };
  const settings = (body: any) => run("settings", async () => setSt(await api.post("/api/story/schedule/settings", body)));
  const step = (what: string) => run(what, async () => {
    const r = await api.post("/api/story/schedule/step", { what });
    setSt(r.status);
    toast(r.played.length ? `Played ${r.played.length}: ${r.played.slice(0, 4).join(", ")}${r.played.length > 4 ? "…" : ""}` : "Nothing was ready.", r.played.length ? "good" : undefined);
    refresh();
  });
  const release = (sid: string) => run("rel:" + sid, async () => {
    const r = await api.post("/api/story/schedule/release", { sid });
    toast(`${r.moment.title} is waiting for you on My Story.`, "good");
    load();
    refresh();
  });
  const pin = (sid: string, months: number[] | undefined, importance?: string) => run("pin:" + sid, async () => {
    const body: any = {};
    if (months !== undefined) body.scene_windows = { [sid]: months };
    if (importance) body.importance = { [sid]: importance };
    setSt(await api.post("/api/story/schedule/season_map", body));
  });

  const rows = useMemo(() => (st?.scenes || []).filter((r) => (!filter.state || r.state === filter.state) && (!filter.pack || r.pack === filter.pack)
    && (!filter.q || (r.sid + " " + r.title).toLowerCase().includes(filter.q.toLowerCase()))), [st, filter]);
  if (!st) return <div className="loading">Reading the schedule...</div>;
  const names: Record<string, string> = Object.fromEntries(st.storylines.map((s) => [s.pack, s.name]));
  const totals = STATES.map((k) => [k, st.scenes.filter((r) => r.state === k).length] as [string, number]);

  return (
    <div className="page sched">
      <div className="page-h">
        <h1>Story Schedule</h1>
        <p className="muted">When storyline scenes happen, why the rest are waiting, and what a pacing change would do. Days and scenes are separate:
          many scenes can happen on one day, and nothing authored is spaced out just to slow it down.</p>
      </div>

      <div className="sched-top">
        <Panel title="Pacing" sub={st.profiles[st.profile]?.about}>
          <div className="sched-profiles">
            {Object.entries(st.profiles).map(([k, p]) => (
              <button key={k} className={cx(st.profile === k && "on")} disabled={!!busy} onClick={() => settings({ pacing: k })}>{p.label}</button>
            ))}
          </div>
          <label className="sched-check">
            <input type="checkbox" checked={st.auto_scenes} onChange={(e) => settings({ auto_scenes: e.target.checked })} /> Let the character decide story scenes
            <small className="muted"> (off: scenes wait for the player)</small>
          </label>
          <div className="sched-over">
            {(["school", "weekend"] as const).map((k) => (
              <label key={k}>{k === "school" ? "School day" : "Weekend"} target
                <input defaultValue={st.settings[k] ? st.settings[k].join("-") : "all"} onBlur={(e) => {
                  const v = e.target.value.trim();
                  const m = v.match(/^(\d+)\s*-\s*(\d+)$/);
                  settings({ overrides: { ...st.overrides, [k]: v === "all" ? null : m ? [Number(m[1]), Number(m[2])] : [Number(v), Number(v)] } });
                }} />
              </label>
            ))}
            {(["chapter_gap", "global_gap", "major_week", "aging_days"] as const).map((k) => (
              <label key={k}>{{ chapter_gap: "Chapter gap (days)", global_gap: "Days between any scenes", major_week: "Major beats / week", aging_days: "Unplayed plan kept (days)" }[k]}
                <input type="number" min={0} defaultValue={st.settings[k] ?? ""} onBlur={(e) => settings({ overrides: { ...st.overrides, [k]: e.target.value === "" ? null : Number(e.target.value) } })} />
              </label>
            ))}
            {Object.keys(st.overrides).length > 0 && <button className="ghost" onClick={() => settings({ overrides: {} })}>Clear overrides</button>}
          </div>
        </Panel>
        <Panel title={`Today · ${st.date}`} sub={`${st.presented_today} presented${st.target_today !== null ? ` of a target ${st.target_today}` : ""} · ${st.majors_this_week} major this week`}>
          <div className="sched-steps">
            <button disabled={!!busy} onClick={() => step("scene")}>Step one scene</button>
            <button disabled={!!busy} onClick={() => step("today")}>Finish today</button>
            <button disabled={!!busy} onClick={() => step("day")}>Step a day</button>
            <button disabled={!!busy} onClick={() => step("week")}>Fast-forward a week</button>
          </div>
          <div className="sched-queue">
            {st.queue.length === 0 && <span className="muted">Nothing left in today's plan.</span>}
            {st.queue.map((q) => <span key={q.sid} className="sched-q" style={{ borderColor: IMP_COLOR[q.importance] }}>{q.title || q.sid}<i>{q.phase.replace("_", " ")}{q.due ? " · due" : ""}</i></span>)}
          </div>
          <div className="sched-meta muted">Queue {st.queue.length} · backlog {st.backlog}{st.oldest !== null ? ` (oldest day ${st.oldest})` : ""} · overdue {st.overdue}
            {st.migrated?.newly_eligible?.length ? ` · ${st.migrated.newly_eligible.length} became eligible when this save moved to the new scheduler` : ""}</div>
          <div className="sched-totals">{totals.map(([k, n]) => n > 0 && <Tag key={k} tone={TONE[k]}>{n} {k}</Tag>)}</div>
        </Panel>
      </div>

      <Tabs tabs={[["scenes", "Scenes"], ["storylines", "Storylines"], ["timeline", "Timeline"], ["compare", "Compare pacing"], ["season", "Season map"], ["report", "Report"]]} active={tab} onChange={setTab} />

      {tab === "storylines" && (
        <Panel title="Storylines" sub="Weight: how central a storyline is when several are ready (main arcs first).">
          <table className="cmp">
            <thead><tr><th>Storyline</th><th>Order</th>{STATES.map((k) => <th key={k}>{k}</th>)}<th>Weight</th></tr></thead>
            <tbody>
              {st.storylines.map((s) => (
                <tr key={s.pack} className="click" onClick={() => { setFilter({ ...filter, pack: s.pack }); setTab("scenes"); }}>
                  <td><b>{s.name}</b></td><td className="muted">{s.in_order ? "in order" : "any"}</td>
                  {STATES.map((k) => <td key={k} className={cx(!s[k] && "muted")}>{s[k] || 0}</td>)}
                  <td onClick={(e) => e.stopPropagation()}>
                    <input className="sched-w" type="number" step={0.5} min={0} defaultValue={st.weights[s.pack] ?? 1}
                      onBlur={(e) => settings({ weights: { ...st.weights, [s.pack]: Number(e.target.value) } })} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}

      {tab === "scenes" && (
        <Panel title="Scenes" sub={`${rows.length} of ${st.scenes.length}. Not yet = it can still happen; unreachable = it can't in this run (and why).`}
          actions={<div className="row">
            <select value={filter.state} onChange={(e) => setFilter({ ...filter, state: e.target.value })}><option value="">Any state</option>{STATES.map((k) => <option key={k}>{k}</option>)}</select>
            <select value={filter.pack} onChange={(e) => setFilter({ ...filter, pack: e.target.value })}><option value="">Every storyline</option>{st.storylines.map((s) => <option key={s.pack} value={s.pack}>{s.name}</option>)}</select>
            <input placeholder="Find a scene" value={filter.q} onChange={(e) => setFilter({ ...filter, q: e.target.value })} />
          </div>}>
          <div className="sched-scroll">
            <table className="cmp">
              <thead><tr><th>Scene</th><th>Storyline</th><th>State</th><th>Why / when</th><th>Season</th><th>Importance</th><th /></tr></thead>
              <tbody>
                {rows.slice(0, 600).map((r) => (
                  <tr key={r.sid}>
                    <td><b>{r.title}</b><div className="muted mono">{r.sid}</div></td>
                    <td className="muted">{names[r.pack] || r.pack}</td>
                    <td><Tag tone={TONE[r.state]}>{r.state}</Tag></td>
                    <td>{r.state === "played" ? r.date : <>{r.reason && <span className="mono">{r.reason}</span>} {r.why}{r.detail !== null && r.detail !== undefined && r.reason ? ` (${Array.isArray(r.detail) ? r.detail.map((m: number) => MONTHS[m] || m).join(", ") : String(r.detail)})` : ""}</>}</td>
                    <td>
                      <div>{r.window_text || <span className="muted">any time</span>}</div>
                      {r.window_rule && <div className="muted small">{r.window_rule}</div>}
                      <input className="sched-months" defaultValue={Array.isArray(r.window) && r.window_rule === "your override" ? r.window.join(",") : ""} placeholder="pin months"
                        title="Pin the months this scene can happen (comma separated, like 3,4). Leave empty to keep the season map's window."
                        onBlur={(e) => {
                          const v = e.target.value.trim();
                          if (v) pin(r.sid, v.split(",").map((x) => Number(x.trim())).filter((x) => x >= 1 && x <= 12));
                        }} />
                    </td>
                    <td>
                      <select value={r.importance} onChange={(e) => pin(r.sid, undefined, e.target.value)}>
                        {["ambient", "regular", "major", "finale"].map((k) => <option key={k}>{k}</option>)}
                      </select>
                    </td>
                    <td>{r.state !== "played" && r.state !== "presented" && <button className="ghost small" disabled={!!busy} onClick={() => release(r.sid)} title="Start it now, whatever is holding it (testing)">Release</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length > 600 && <div className="muted">Showing 600. Filter to see the rest.</div>}
          </div>
        </Panel>
      )}

      {tab === "timeline" && <TimelinePanel tl={tl} names={names} />}

      {tab === "compare" && (
        <Panel title="Compare pacing on the same seed" sub="Runs copies of this world forward (fast: calendar and stories only) under each profile. Your story doesn't change."
          actions={<div className="row">
            <input type="number" min={7} max={2600} value={days} onChange={(e) => setDays(Number(e.target.value))} style={{ width: 80 }} /> days
            <button disabled={!!busy} onClick={() => run("cmp", async () => setCmp(await api.post("/api/story/schedule/compare", { profiles: ["relaxed", "standard", "dense", "uncapped"], days })))}>Run</button>
          </div>}>
          {cmp ? <CompareView cmp={cmp} /> : <div className="muted">Pick a length and run it.</div>}
        </Panel>
      )}

      {tab === "season" && (
        <Panel title="Season map" sub="Broad windows for scenes that don't say when. A scene's own months, dates or not_before/not_after always win; pin any scene's months on the Scenes tab.">
          <table className="cmp">
            <thead><tr><th>Rule</th><th>Months</th></tr></thead>
            <tbody>
              {st.season_map.map((r) => (
                <tr key={r.id}><td><b>{r.label || r.id}</b><div className="muted mono">{r.id}</div></td>
                  <td>{r.window_text}{r.anchor && <div className="muted small">from the school calendar: {r.anchor}</div>}</td></tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}

      {tab === "report" && (
        <Panel title="Dry-run report" sub="Plays the story forward on a copy with the character answering every scene, then lists every scene: when it played, or why not; deadline misses; contradictions; cast identity.">
          <div className="row">
            <a className="btn" href="/api/story/schedule/report?days=2565&fmt=md" download="story-schedule-report.md">Seven years, fast (markdown)</a>
            <a className="btn ghost" href="/api/story/schedule/report?days=2565&fmt=json" target="_blank" rel="noreferrer">Same, as JSON</a>
            <a className="btn ghost" href="/api/story/schedule/report?days=120&full=1&fmt=md" download="story-schedule-120-days-full.md">120 days, whole town simulated</a>
          </div>
          <p className="muted small">The fast run moves only the calendar and the stories (seconds). The full run simulates everyone and takes about a minute per simulated month.</p>
        </Panel>
      )}
    </div>
  );
}

function TimelinePanel({ tl, names }: { tl: Timeline | null; names: Record<string, string> }) {
  if (!tl) return <Panel title="Timeline"><div className="muted">Loading…</div></Panel>;
  if (!tl.items.length) return <Panel title="Timeline"><div className="muted">Nothing has played yet.</div></Panel>;
  const d0 = Math.min(...tl.items.map((i) => i.day));
  const d1 = Math.max(...tl.items.map((i) => i.day));
  const span = Math.max(1, d1 - d0);
  const lanes = tl.lanes;
  const W = Math.max(900, Math.min(6000, span * 6 + 200));
  const LH = 34;
  const H = lanes.length * LH + 40;
  const x = (d: number) => 170 + ((d - d0) / span) * (W - 200);
  const pos: Record<string, [number, number]> = {};
  tl.items.forEach((i) => { pos[i.sid] = [x(i.day), 30 + lanes.indexOf(i.pack) * LH + LH / 2]; });
  return (
    <Panel title="Episode timeline" sub={`${tl.items.length} played · lanes are storylines · arrows are "after" links · color is importance`}>
      {tl.warnings.length > 0 ? (
        <div className="sched-warn">{tl.warnings.map((w, i) => <div key={i}>⚠ {w.text}</div>)}</div>
      ) : <div className="sched-ok">No contradictions: everything in season, after its prerequisites and in chapter order.</div>}
      <div className="sched-tl">
        <svg width={W} height={H}>
          {lanes.map((l, i) => (
            <g key={l}>
              <line x1={160} x2={W - 20} y1={30 + i * LH + LH / 2} y2={30 + i * LH + LH / 2} stroke="#262e52" />
              <text x={8} y={30 + i * LH + LH / 2 + 4} fill="#9aa1c4" fontSize={11}>{(names[l] || l).slice(0, 24)}</text>
            </g>
          ))}
          {tl.items.flatMap((i) => i.after.filter((a) => pos[a]).map((a) => (
            <line key={i.sid + a} x1={pos[a][0]} y1={pos[a][1]} x2={pos[i.sid][0]} y2={pos[i.sid][1]} stroke="#9b8cff" strokeOpacity={0.5} markerEnd="url(#arr)" />
          )))}
          <defs><marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L8 4 L0 8z" fill="#9b8cff" /></marker></defs>
          {tl.items.map((i) => (
            <circle key={i.sid} cx={pos[i.sid][0]} cy={pos[i.sid][1]} r={i.importance === "finale" ? 7 : i.importance === "major" ? 6 : 4.5} fill={IMP_COLOR[i.importance]}>
              <title>{`${i.title}\n${i.date} · ${i.importance}`}</title>
            </circle>
          ))}
          <text x={170} y={16} fill="#646c94" fontSize={11}>{tl.items[0].date}</text>
          <text x={W - 20} y={16} fill="#646c94" fontSize={11} textAnchor="end">{tl.items[tl.items.length - 1].date}</text>
        </svg>
      </div>
    </Panel>
  );
}

function CompareView({ cmp }: { cmp: Compare }) {
  const max = Math.max(1, ...cmp.runs.flatMap((r) => r.per_day));
  return (
    <div className="sched-cmp">
      <table className="cmp">
        <thead><tr><th>Profile</th><th>Scenes</th><th>Most in a day</th><th>Days with scenes</th><th>Contradictions</th><th>Deadline misses</th></tr></thead>
        <tbody>{cmp.runs.map((r) => <tr key={r.profile}><td><b>{r.profile}</b></td><td>{r.played}</td><td>{r.max_per_day}</td><td>{r.days_with_scenes} of {cmp.days}</td>
          <td className={cx(r.warnings ? "bad" : "muted")}>{r.warnings}</td><td className={cx(r.deadline_misses ? "bad" : "muted")}>{r.deadline_misses}</td></tr>)}</tbody>
      </table>
      {cmp.runs.map((r) => (
        <div key={r.profile} className="sched-bars">
          <span>{r.profile}</span>
          <div>{r.per_day.map((n, i) => <i key={i} style={{ height: `${(n / max) * 100}%` }} title={`day ${i + 1}: ${n}`} />)}</div>
        </div>
      ))}
    </div>
  );
}
