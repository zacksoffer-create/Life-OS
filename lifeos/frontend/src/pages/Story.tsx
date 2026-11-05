// My Story: the playable life. You make the big calls; the simulation lives everything in between
// and every result on this page comes straight from recorded simulation state.
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { go, useApi, useStore, PLACE } from "../store";
import {
  Avatar, Calc, Changes, Empty, ErrorBox, EventRow, Icon, LineChart, Loading, Meter, Name, Panel, Signed, Stat, Tabs, Tag, TermBars,
  cx, fmt, moodColor, pretty, signed,
} from "../ui";
import "./story.css";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const SLOT_LABEL: Record<string, string> = { lunch: "Lunch", after_school: "After school", day: "Daytime", evening: "Evening" };

const FOCI: [string, string, string][] = [
  ["balanced", "Balanced", "No push. They follow their own personality."],
  ["athletics", "Athletics", "Practice, training, games, sign-ups."],
  ["academics", "School", "Studying and homework."],
  ["social", "Friends", "Hanging out, parties, meeting people."],
  ["romance", "Romance", "Flirting, dates, asking someone out."],
  ["family", "Family", "Time at home, the pet, helping people."],
  ["rest", "Downtime", "Rest, hobbies, recharging."],
  ["work", "Work", "Shifts at the job, picking up hours."],
];

const TOGGLES: [string, string, string][] = [
  ["stop_on_big", "Stop when something big happens", "Tryouts, injuries, offers, breakups, awards."],
  ["stop_before_games", "Stop before games", "So you can pick how you play that night."],
  ["ask_romance", "Ask me when someone asks me out", "Otherwise you answer on your own."],
  ["ask_invites", "Ask me about invitations", "Friends' invites wait in your inbox instead of being answered for you."],
];

const MOMENT_META: Record<string, [string, string]> = {
  first_day: ["New chapter", "var(--accent)"], college_arrival: ["New chapter", "var(--accent)"],
  cut: ["Tryouts", "var(--bad)"], injury: ["Injury", "var(--bad)"], benched: ["Playing time", "var(--warm)"],
  offer: ["Recruiting", "var(--good)"], college_decision: ["The big decision", "var(--accent-2)"], game_day: ["Game day", "var(--info)"],
  sibling_leaves: ["Family", "var(--info)"], rumor: ["Drama", "var(--warm)"], heartbreak: ["Heartbreak", "var(--romance)"],
  summer: ["Summer", "var(--warm)"], graduation: ["Graduation", "var(--good)"], year_review: ["Year in review", "var(--accent-2)"],
  asked_out: ["Romance", "var(--romance)"], asked_to_dance: ["Romance", "var(--romance)"],
  mlb_draft: ["MLB Draft", "var(--good)"], draft_passed: ["MLB Draft", "var(--warm)"], story_end: ["The end of the beginning", "var(--accent-2)"],
};

const KIND_TAG: Record<string, [string, string]> = {
  tryout: ["tryouts", "accent"], audition: ["auditions", "accent"], game: ["game", "info"], dance: ["dance", "romance"], exam: ["exam", "warn"],
  report_card: ["report card", "warn"], graduation: ["graduation", "good"], admissions: ["admissions", "good"],
  college_decision: ["decision", "good"], decision_day: ["decision day", "good"], election: ["election", "accent"], show: ["show", "info"],
};

const TIER_COLOR: Record<string, string> = {
  D1: "var(--warm)", D2: "var(--accent-2)", D3: "var(--info)", JUCO: "var(--muted)", CC: "var(--muted)",
  SEC: "var(--warm)", ACC: "var(--info)", "Big Ten": "var(--accent-2)", "Big East": "var(--good)", NE10: "var(--muted)",
};

function useDayLabel() {
  const { world } = useStore();
  return useCallback(
    (d: number, short = false) => {
      if (!world) return `day ${d}`;
      const base = Date.parse(world.iso + "T12:00:00Z") - world.day * 864e5;
      const opts: Intl.DateTimeFormatOptions = short
        ? { month: "short", day: "numeric", timeZone: "UTC" }
        : { weekday: "short", month: "short", day: "numeric", year: "numeric", timeZone: "UTC" };
      return new Date(base + d * 864e5).toLocaleDateString("en-US", opts);
    },
    [world]
  );
}

function Tier({ t }: { t: string | null }) {
  if (!t) return null;
  return <span className="tag tier" style={{ color: TIER_COLOR[t] || "var(--muted)", borderColor: TIER_COLOR[t] || undefined }}>{t}</span>;
}

function softmax(us: number[], T: number) {
  if (!us.length) return [];
  const m = Math.max(...us);
  const ws = us.map((u) => Math.exp((u - m) / T));
  const s = ws.reduce((a, b) => a + b, 0);
  return ws.map((w) => w / s);
}

const where = (loc: string, college?: any) =>
  loc === "hollow_creek" ? `home in ${PLACE.town}` : loc === "college" ? `at ${college?.name || "college"}` : loc === "away" ? "away at school" : pretty(loc || "");

function pathText(path: any) {
  if (!path || !path.kind) return null;
  if (path.kind === "work") return `Staying in ${PLACE.town} to work`;
  if (path.kind === "pro") return path.team ? `Pro ball: ${path.team} (round ${path.round}), starting at ${path.level}` : `Pro ball: signed as a free agent`;
  return path.sport ? `Playing ${path.sport} at ${path.name}${path.aid ? ` (${path.aid})` : path.scholarship ? " (scholarship)" : ""}` : `Going to ${path.name}`;
}

const money = (n: number) => (n >= 1e6 ? `$${(n / 1e6).toFixed(1)} million` : `$${Math.round(n / 1000).toLocaleString()}K`);

// ================================================================================================

export default function Story({ route }: { route: string[] }) {
  const { tick } = useStore();
  const [s, setS] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const busyRef = useRef(false);
  const load = useCallback(async () => {
    try {
      const d = await api.get("/api/story");
      setS(d);
      setErr(null);
      return d;
    } catch (e: any) {
      setErr(e.message);
      return null;
    }
  }, []);
  useEffect(() => {
    if (!busyRef.current) load();
  }, [tick, load]);
  if (err && !s) return <ErrorBox error={err} />;
  if (!s) return <Loading what="Opening your story" />;
  if (!s.active) return <NoStory onStarted={load} />;
  return <Active s={s} load={load} busyRef={busyRef} tab={route[1]} />;
}

// ---------- no story yet ----------
function NoStory({ onStarted }: { onStarted: () => Promise<any> }) {
  const { charList, refresh, toast } = useStore();
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const studs = charList.filter((c) => c.role === "student" && c.status === "active" && (!q || c.name.toLowerCase().includes(q.toLowerCase())));
  const pick = async (id: string) => {
    setBusy(true);
    try {
      await api.post("/api/story/protagonist", { id });
      await refresh();
      await onStarted();
    } catch (e: any) {
      toast(e.message, "bad");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="stack">
      <div className="st-hero">
        <div className="st-kick">My Story</div>
        <h1>Your story starts here</h1>
        <p>
          Build yourself, your family and the people in your life, then live seven years: four years of high school and three after.
          You make the big calls. The simulation lives everything in between, and it always shows you why things happened.
        </p>
        <div className="st-hero-steps">
          <span><b>1</b>You</span>
          <span><b>2</b>Your family</span>
          <span><b>3</b>Your people</span>
          <span><b>4</b>The town</span>
          <span><b>5</b>Start living</span>
        </div>
        <button className="primary st-big" onClick={() => go("story/new")}>
          <Icon name="play" size={16} /> Start your story
        </button>
      </div>
      <Panel title={`Or play as someone already in ${PLACE.town}`} sub="Pick anyone in the current world and their life becomes your story, starting today."
        actions={<input type="search" placeholder="Search names" value={q} onChange={(e) => setQ(e.target.value)} />}>
        {studs.length ? (
          <div className="pick-grid">
            {studs.slice(0, 60).map((c) => (
              <div key={c.id} className="pick" onClick={() => !busy && pick(c.id)}>
                <Avatar id={c.id} size={42} onClick={() => undefined} />
                <div>
                  <b>{c.name}</b>
                  <div className="hint">{(c as any).year_label || `Grade ${c.grade}`} · {c.archetype}</div>
                  <div className="small muted clamp2">{c.bio}</div>
                </div>
              </div>
            ))}
          </div>
        ) : <Empty>No students match.</Empty>}
      </Panel>
    </div>
  );
}

// ---------- the active story ----------
const TAB_KEYS = ["sports", "people", "story", "me"];

function Active({ s, load, busyRef, tab }: { s: any; load: () => Promise<any>; busyRef: React.MutableRefObject<boolean>; tab?: string }) {
  const { refresh, toast } = useStore();
  const dayLabel = useDayLabel();
  const me = s.me;
  const p = s.protagonist;
  const [running, setRunning] = useState<any>(null);
  const [log, setLog] = useState<any[]>([]);
  const [choosing, setChoosing] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [showOlder, setShowOlder] = useState(false);
  const active = TAB_KEYS.includes(tab || "") ? (tab as string) : "sports";

  const sync = async () => {
    const [d] = await Promise.all([load(), refresh()]);
    return d;
  };
  const push = (t: any) => setLog((l) => [{ ...t, key: Date.now() + Math.random() }, ...l].slice(0, 15));

  const lock = async (fn: () => Promise<void>) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try {
      await fn();
    } catch (e: any) {
      toast(e.message, "bad");
      await sync();
    } finally {
      busyRef.current = false;
      setBusy(false);
      setRunning(null);
    }
  };

  const openChoices = async () => {
    try {
      setChoosing(await api.post(`/api/play/${p}/options`));
    } catch (e: any) {
      toast(e.message, "warn");
    }
  };

  const advance = (until: string) =>
    lock(async () => {
      setChoosing(null);
      let j = await api.post("/api/story/advance", { until });
      setRunning({ until, job: j });
      let n = 0;
      while (j.status === "running") {
        await sleep(350);
        j = await api.get("/api/sim/job");
        setRunning({ until, job: j });
        if (++n % 5 === 0) refresh();
      }
      if (j.status === "failed") toast(`The simulation hit an error: ${j.error}`, "bad");
      const d = await sync();
      const evs = d && d.active ? d.feed.filter((e: any) => e.id >= j.start_event) : [];
      push({ kind: "advance", until, job: j, events: evs, inbox: d?.inbox || [] });
      if (j.stop === "decision" && d && d.active && !d.moments.length) await openChoices();
    });

  const act = (index: number, label: string) =>
    lock(async () => {
      const at = choosing ? `${choosing.date} · ${SLOT_LABEL[choosing.slot] || choosing.slot}` : "";
      const r = await api.post(`/api/play/${p}/act`, { index });
      setChoosing(null);
      await sync();
      push({ kind: "act", label, auto: index < 0, at, r });
    });

  const resolve = (m: any, index: number | null, label?: string) =>
    lock(async () => {
      const r = await api.post(`/api/story/moment/${m.id}`, index === null ? {} : { index });
      await sync();
      push({ kind: "moment", m, label: label || r.event?.data?.choice, auto: index === null, ev: r.event });
    });

  const setControl = async (patch: any) => {
    try {
      await api.post("/api/story/control", patch);
      await load();
    } catch (e: any) {
      toast(e.message, "bad");
    }
  };

  const answerInvite = (inv: any, accept: boolean) =>
    lock(async () => {
      const r = await api.post(`/api/story/inbox/${inv.id}`, { accept });
      toast(accept ? r.note || "You'll say yes at your next free moment." : `You told ${inv.from_name} not this time.`, accept ? "good" : "info");
      await sync();
    });

  const moments = s.moments || [];
  const latest = log[0];
  const older = log.slice(1);

  let now: React.ReactNode;
  let interrupt = true;
  if (running) now = <Running r={running} first={me.first} dayLabel={dayLabel} />;
  else if (moments.length) now = <MomentCard m={moments[0]} more={moments.length - 1} s={s} busy={busy} onPick={(i, l) => resolve(moments[0], i, l)} />;
  else if (choosing) now = <ChoicePanel opts={choosing} first={me.first} busy={busy} onAct={act} onCancel={() => setChoosing(null)} />;
  else {
    now = <Controls s={s} busy={busy} onAdvance={advance} onControl={setControl} />;
    interrupt = false;
  }
  // When something is waiting on you, the headline stays on top and the "along the way" list moves under it.
  const split = !!latest && latest.kind === "advance" && interrupt && !running;

  return (
    <div className="stack" style={{ gap: 0 }}>
      <Header s={s} />
      <div className="grid g-main">
        <div className="stack">
          <div className="st-now">
            <div className="st-now-h">
              <div>
                <div className="st-kick">Now</div>
                <h2>{s.date} · {s.term}</h2>
              </div>
              {!running && !moments.length && !choosing && (
                <span className="hint">Focus: <b className="muted">{(FOCI.find((f) => f[0] === s.control.focus) || FOCI[0])[1]}</b></span>
              )}
            </div>
            {latest && !running && <Turn t={latest} s={s} dayLabel={dayLabel} part={split ? "head" : "all"} />}
            {now}
            {split && <Turn t={latest} s={s} dayLabel={dayLabel} part="body" />}
          </div>
          {older.length > 0 && (
            <Panel title="Earlier this session" actions={<button className="small ghost" onClick={() => setShowOlder(!showOlder)}>{showOlder ? "Hide" : `Show ${older.length}`}</button>}>
              {showOlder ? <div className="stack" style={{ gap: 8 }}>{older.map((t) => <Turn key={t.key} t={t} s={s} dayLabel={dayLabel} />)}</div>
                : <div className="hint">Your last {older.length} turns are kept here until you leave the page. Everything is also in the Story so far tab.</div>}
            </Panel>
          )}
        </div>
        <div className="stack">
          <QuickMe s={s} />
          {(s.inbox.length > 0 || s.control.ask_invites) && <Inbox s={s} busy={busy} onAnswer={answerInvite} />}
          <Upcoming s={s} />
        </div>
      </div>
      <div style={{ marginTop: 16 }} className="stack">
        <Tabs tabs={[["sports", "Sports"], ["people", "People"], ["story", "Story so far"], ["me", "Me"]]} active={active} onChange={(k) => go(`story/${k}`)} />
        {active === "sports" && <SportsTab s={s} />}
        {active === "people" && <PeopleTab s={s} />}
        {active === "story" && <StorySoFar s={s} />}
        {active === "me" && <MeTab s={s} dayLabel={dayLabel} />}
      </div>
    </div>
  );
}

// ---------- header with the 7-year bar ----------
function Header({ s }: { s: any }) {
  const me = s.me;
  const pr = s.progress;
  const chapters = useMemo(() => {
    const g0 = typeof me.grade === "number" ? Math.max(9, Math.min(12, me.grade - (pr.year - 1))) : 9;
    const out: [string, string][] = [];
    for (let i = 0; i < 7; i++) {
      const g = g0 + i;
      if (g <= 12) out.push([["Fr", "So", "Jr", "Sr"][g - 9], ["Freshman", "Sophomore", "Junior", "Senior"][g - 9]]);
      else if (me.path?.kind === "work") out.push([`Year ${g - 12} out`, `Year ${g - 12} after high school`]);
      else out.push([`College ${g - 12}`, `College year ${g - 12}`]);
    }
    if (out.length && me.path?.kind !== "work") out[out.length - 1] = [`${out[out.length - 1][0]} · Draft`, `${out[out.length - 1][1]}, then the MLB Draft in July`];
    return out;
  }, [me.grade, me.path?.kind, pr.year]);
  const place = me.path?.kind === "pro" ? (me.path.level ? `pro ball (${me.path.level})` : "pro ball")
    : me.school === "college" && s.college ? s.college.name : me.school === "hchs" ? PLACE.school : me.location === "hollow_creek" ? PLACE.town : pretty(me.location);
  return (
    <div className="st-head">
      <Avatar id={me.id} size={64} />
      <div style={{ minWidth: 0 }}>
        <div className="st-kick">{s.title || "My Story"}</div>
        <h1>{me.name}</h1>
        <div className="st-meta">
          <Tag tone="accent">{me.year_label}</Tag>
          <span>{me.age} years old</span>
          <span>·</span>
          <span>{place}</span>
          {me.partner && <><span>·</span><Tag tone="romance">dating <Name id={me.partner} /></Tag></>}
          {me.injured && <Tag tone="bad">injured</Tag>}
          {me.path?.kind === "pro" && <Tag tone="good">{me.path.team ? `${me.path.team} · round ${me.path.round}` : "pro ball"}</Tag>}
        </div>
      </div>
      <div className="st-head-r">
        <div className="row">
          <button className="small" onClick={() => go(`characters/${me.id}`)}>Full profile</button>
          <button className="small ghost" onClick={() => go("story/new")}>New story</button>
        </div>
        <div className="hint">Year {Math.min(7, pr.year)} of 7 · day {pr.day.toLocaleString()} of {pr.total.toLocaleString()}</div>
      </div>
      <div className="st-prog">
        <div className="st-prog-bar" title={`${pr.pct}% of your seven years`}>
          <div className="st-prog-fill" style={{ width: `${Math.max(0.6, pr.pct)}%` }} />
          <div className="st-prog-ticks">{chapters.map((_, i) => <i key={i} />)}</div>
        </div>
        <div className="st-chapters">
          {chapters.map(([short, long], i) => (
            <span key={i} title={long} className={cx(i + 1 < pr.year && "done", i + 1 === pr.year && "now")}>{short}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------- moments ----------
function MomentCard({ m, more, s, busy, onPick }: { m: any; more: number; s: any; busy: boolean; onPick: (i: number | null, label?: string) => void }) {
  const [kicker, color] = MOMENT_META[m.kind] || ["A moment", "var(--accent)"];
  return (
    <div className="st-moment" style={{ ["--k" as any]: color }}>
      <div className="st-kicker">{kicker}{more > 0 && <span className="dim"> · {more} more waiting after this</span>}</div>
      <h2>{m.title}</h2>
      <p className="st-mtext">{m.text}</p>
      <MomentContext m={m} s={s} />
      {m.kind === "college_decision" ? (
        <PathCards m={m} first={s.me.first} busy={busy} onPick={onPick} />
      ) : (
        <div className="st-choices">
          {m.choices.map((c: any, i: number) => (
            <button key={i} className="st-choice" disabled={busy} onClick={() => onPick(i, c.label)}>
              <b>{c.label}</b>
              {c.hint && <span>{c.hint}</span>}
            </button>
          ))}
        </div>
      )}
      <div className="row between">
        <button className="ghost small st-let" disabled={busy} onClick={() => onPick(null)} title="They choose based on their own personality">
          <Icon name="spark" size={13} /> Let {s.me.first} decide
        </button>
        <span className="hint">Choices set things in motion. How they turn out can still depend on the dice and on who you are.</span>
      </div>
    </div>
  );
}

function MomentContext({ m, s }: { m: any; s: any }) {
  const ctx = m.ctx || {};
  const chips: React.ReactNode[] = [];
  for (const k of ["other", "coach", "sibling", "roommate"]) {
    const id = ctx[k];
    if (typeof id === "string" && id) {
      const rel = s.people.find((x: any) => x.id === id) || s.family.find((x: any) => x.id === id);
      chips.push(
        <span key={k} className="st-chip">
          <Avatar id={id} size={22} ring={false} />
          <Name id={id} full />
          {rel?.mine && <span className="dim">· you: {rel.mine.label}{k === "other" ? `, attraction ${fmt(rel.mine.attraction)}` : ""}</span>}
        </span>
      );
    }
  }
  if (m.kind === "game_day") {
    const t = s.teams.find((x: any) => x.sport === ctx.sport) || s.teams[0];
    if (t) chips.push(<span key="t" className="st-chip plain">{t.name} {t.level === "jv" ? "JV" : ""} · {t.record.w}-{t.record.l} · you're {t.starter ? "a starter" : "on the bench"}</span>);
  }
  if (m.kind === "offer") chips.push(<span key="o" className="st-chip plain"><Tier t={ctx.tier} /> {ctx.sport}</span>);
  if (m.kind === "injury" && ctx.weeks) chips.push(<span key="i" className="st-chip plain">about {ctx.weeks} week{ctx.weeks === 1 ? "" : "s"} out{s.me.injured_until ? ` · until ${s.me.injured_until}` : ""}</span>);
  if (!chips.length) return null;
  return <div className="st-mctx">{chips}</div>;
}

function PathCards({ m, first, busy, onPick }: { m: any; first: string; busy: boolean; onPick: (i: number | null, label?: string) => void }) {
  const paths: any[] = m.ctx.paths || [];
  const probs = softmax(paths.map((p) => p.utility), 6);
  const best = probs.indexOf(Math.max(...probs));
  return (
    <>
      <div className="st-paths">
        {paths.map((p, i) => (
          <div key={i} className={cx("st-path", i === best && "best")}>
            <div className="row between">
              <h4>{p.kind === "work" ? "Stay home and work" : p.name}</h4>
              <Tier t={p.conference || p.tier} />
            </div>
            <div className="st-path-l">
              {p.kind === "work" ? `Get a job in ${PLACE.town}, stay close to family and friends.` : p.sport ? `Play ${p.sport} for them.` : "Go as a regular student. No team spot promised."}
            </div>
            <div className="chips">
              {p.sport && <Tag tone="accent">{p.sport}</Tag>}
              {p.scholarship && <Tag tone="good">{p.aid || "scholarship"}</Tag>}{p.program ? <Tag tone="dim">program {p.program}</Tag> : null}
              {p.kind === "college" && !p.sport && <Tag>student</Tag>}
              {p.kind === "work" && <Tag tone="info">work</Tag>}
            </div>
            <Meter value={probs[i] * 100} color="var(--accent-2)" label={`${first}'s gut`} right={`${Math.round(probs[i] * 100)}%`} />
            <button className={i === best ? "primary" : ""} disabled={busy} onClick={() => onPick(i, p.label)}>Choose this</button>
          </div>
        ))}
      </div>
      <div className="hint" style={{ marginTop: 8 }}>
        "Gut" is how likely {first} would be to pick each one alone, from their own scores for each path (level of the program, love of the sport, a scholarship, ambition, money at home).
      </div>
    </>
  );
}

// ---------- recap of a turn ----------
const STOP_TAG: Record<string, string> = { moment: "your call", decision: "your move", invite: "invitation", event: "big moment", time: "done" };
const STOP_TYPES = ["tryout", "audition", "injury", "recruiting", "award", "path", "ask_out", "ask_to_dance", "break_up", "election",
  "rumor_reached", "graduation", "exclusion", "admissions"];

function Turn({ t, s, dayLabel, part = "all" }: { t: any; s: any; dayLabel: (d: number, short?: boolean) => string; part?: "all" | "head" | "body" }) {
  const [more, setMore] = useState(false);
  const first = s.me.first;
  const p = s.protagonist;
  if (t.kind === "advance") {
    const j = t.job;
    const days = (j.end_day ?? j.start_day) - j.start_day;
    const evs: any[] = t.events || [];
    let head = "";
    let tone = "info";
    if (j.status === "failed") {
      head = `Something went wrong: ${j.error}`;
      tone = "bad";
    } else if (j.stop === "moment") {
      head = "Something came up. Your call.";
      tone = "accent";
    } else if (j.stop === "decision") {
      head = "Your next choice is here.";
      tone = "accent";
    } else if (j.stop === "invite") {
      const inv = t.inbox[t.inbox.length - 1];
      head = inv ? `${inv.from_name} invited you to ${inv.action === "date" ? "go on a date" : "hang out"}. It's in your inbox.` : "You have an invitation waiting.";
      tone = "social";
    } else if (j.stop === "event") {
      const big = [...evs].filter((e) => STOP_TYPES.includes(e.type.split(".")[0]) || e.importance >= 40)
        .sort((a, b) => b.importance - a.importance || b.id - a.id)[0] || evs[0];
      head = big ? `Stopped: ${big.text}` : "Something big just happened.";
      tone = "warn";
    } else {
      head = t.until === "moment" ? `A quiet stretch. ${days} days went by and nothing big happened.`
        : t.until === "decision" ? "Moved to the next free moment." : `Skipped ahead ${days} day${days === 1 ? "" : "s"}.`;
    }
    // Lead with what happened to you; things you were only around for are one tap away.
    const mine = evs.filter((e) => e.actors.includes(p) || e.targets.includes(p));
    const shown = more ? evs : (mine.length ? mine : evs).slice(0, 5);
    const hidden = evs.length - shown.length;
    const body = (
      <>
        {evs.length > 0 ? (
          <div className="evlist">{shown.map((e: any) => <EventRow key={e.id} ev={e} compact />)}</div>
        ) : days > 0 ? <div className="hint" style={{ marginTop: 6 }}>Nothing notable happened to {first} along the way.</div> : null}
        {(hidden > 0 || more) && <button className="small ghost" onClick={() => setMore(!more)}>{more ? "Show less" : `Show ${hidden} more from along the way`}</button>}
      </>
    );
    if (part === "body") {
      if (!evs.length) return null;
      return <div className="st-turn"><div className="st-sec-l">Along the way</div>{body}</div>;
    }
    return (
      <div className="st-turn">
        <div className="st-turn-h">
          <div>
            <b>{head}</b>
            <div className="st-when">{days > 0 ? `${dayLabel(j.start_day)} → ${dayLabel(j.end_day)} · ${days} day${days === 1 ? "" : "s"} lived` : "Same day"}{j.seconds ? ` · ${j.seconds}s` : ""}</div>
          </div>
          <Tag tone={tone}>{STOP_TAG[j.stop] || "done"}</Tag>
        </div>
        {part === "all" && body}
      </div>
    );
  }
  if (t.kind === "act") {
    const r = t.r;
    const dm = r.mood_after - r.mood_before;
    return (
      <div className="st-turn">
        <div className="st-turn-h">
          <div>
            <b>{t.auto ? `${first} decided for themselves` : `You chose: ${t.label}`}</b>
            <div className="st-when">{t.at}</div>
          </div>
          <span className={dm >= 0 ? "pos small" : "neg small"}>mood {signed(dm)}</span>
        </div>
        <div className="evlist">{r.events.length ? r.events.map((e: any) => <EventRow key={e.id} ev={e} compact showDate={false} />) : <div className="hint">Nothing recorded for {first} in that slot.</div>}</div>
        {r.events.length > 0 && <button className="small ghost" onClick={() => setMore(!more)}>{more ? "Hide details" : "Show the dice and what changed"}</button>}
        {more && r.events.map((e: any) => (
          <div key={e.id} style={{ marginTop: 8 }}>
            <Calc calc={e.calc} />
            {e.changes?.length > 0 && <Changes changes={e.changes.slice(0, 40)} />}
          </div>
        ))}
      </div>
    );
  }
  // moment
  const ev = t.ev || {};
  const roll = (ev.calc || []).find((c: any) => c.step === "how it goes");
  const outcome = ev.data?.outcome;
  return (
    <div className="st-turn">
      <div className="st-turn-h">
        <div>
          <b>{t.m.title}</b>
          <div className="st-when">{t.auto ? `${first} decided: ${t.label}` : `You chose: ${t.label}`}</div>
        </div>
        {outcome && <Tag tone={outcome === "success" ? "good" : "bad"}>{outcome === "success" ? "it worked" : "didn't go your way"}</Tag>}
      </div>
      {roll && <Roll roll={roll} />}
      {ev.changes?.length > 0 && (
        <>
          <button className="small ghost" onClick={() => setMore(!more)}>{more ? "Hide what changed" : `What changed (${ev.changes.length})`}</button>
          {more && <Changes changes={ev.changes.slice(0, 40)} />}
        </>
      )}
    </div>
  );
}

function Roll({ roll }: { roll: any }) {
  const [open, setOpen] = useState(false);
  const ok = roll.roll < roll.p;
  return (
    <div>
      <div className="st-roll">
        <span>How it goes: <b>{Math.round(roll.p * 100)}%</b> chance</span>
        <div className="st-dice" title="Green is the chance it works. The white pin is where the roll landed.">
          <div className="ok" style={{ width: `${roll.p * 100}%` }} />
          <div className="pin" style={{ left: `calc(${Math.min(99.5, roll.roll * 100)}% - 1px)` }} />
        </div>
        <span>rolled <b>{roll.roll.toFixed(2)}</b> → <b className={ok ? "pos" : "neg"}>{ok ? "it worked" : "not this time"}</b></span>
        <button className="small ghost" onClick={() => setOpen(!open)}>{open ? "hide" : "why"}</button>
      </div>
      {open && (
        <div className="small muted" style={{ marginTop: 6 }}>
          {roll.terms.map((t: any, i: number) => <div key={i}>{t[0]}: <b>{signed(t[1] * 100, 0)}%</b></div>)}
          <div className="hint">{roll.rule}</div>
        </div>
      )}
    </div>
  );
}

// ---------- running ----------
function Running({ r, first, dayLabel }: { r: any; first: string; dayLabel: (d: number) => string }) {
  const j = r.job;
  const open = r.until === "moment";
  const pct = j.days ? (100 * (j.done || 0)) / j.days : 0;
  return (
    <div className="st-running">
      <b>Living {first}'s life{open ? " until something happens" : ""}...</b>
      {open ? <div className="st-indet"><i /></div> : <div className="meter" style={{ height: 8 }}><div className="meter-f" style={{ width: `${pct}%`, background: "var(--accent)" }} /></div>}
      <div className="hint">{j.done || 0} day{j.done === 1 ? "" : "s"} so far · now {dayLabel(j.start_day + (j.done || 0))}</div>
    </div>
  );
}

// ---------- the play controls ----------
function Controls({ s, busy, onAdvance, onControl }: { s: any; busy: boolean; onAdvance: (u: string) => void; onControl: (p: any) => void }) {
  const first = s.me.first;
  const [opts, setOpts] = useState(false);
  // Optimistic: the switch flips right away and settles when the server answers.
  const [local, setLocal] = useState<any>({});
  useEffect(() => setLocal({}), [s.control]);
  const ctl = { ...s.control, ...local };
  const set = (patch: any) => {
    setLocal((l: any) => ({ ...l, ...patch }));
    onControl(patch);
  };
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="st-go">
        <button className="primary st-big" disabled={busy} onClick={() => onAdvance("moment")} title="Live day by day until something comes up">
          <Icon name="play" size={16} /> Live until something happens
        </button>
        <button disabled={busy} onClick={() => onAdvance("decision")} title="Jump to the next free moment and pick what to do yourself">
          Make the next choice myself
        </button>
        <div className="st-skip">
          skip
          <button className="small" disabled={busy} onClick={() => onAdvance("day")}>a day</button>
          <button className="small" disabled={busy} onClick={() => onAdvance("week")}>a week</button>
          <button className="small" disabled={busy} onClick={() => onAdvance("month")}>a month</button>
        </div>
      </div>
      <div>
        <div className="st-sec-l">Focus</div>
        <div className="st-focus">
          {FOCI.map(([k, l, d]) => (
            <button key={k} className={cx("st-f", ctl.focus === k && "on")} disabled={busy} onClick={() => set({ focus: k })}>
              <b>{l}</b>
              <span>{d}</span>
            </button>
          ))}
        </div>
        <div className="hint" style={{ marginTop: 6 }}>
          When {first} decides on their own, your focus adds a +7 pull toward those kinds of choices. It nudges; it doesn't force. You'll see it in every decision's "why".
        </div>
      </div>
      <div>
        <button className="small ghost" onClick={() => setOpts(!opts)} style={{ paddingLeft: 0 }}>
          {opts ? "▾" : "▸"} When should the story stop and ask me?
        </button>
        {opts && (
          <div className="st-toggles" style={{ marginTop: 6 }}>
            {TOGGLES.map(([k, l, d]) => (
              <label key={k} className="st-toggle">
                <input type="checkbox" checked={!!ctl[k]} disabled={busy} onChange={(e) => set({ [k]: e.target.checked })} />
                <div>{l}<span>{d}</span></div>
              </label>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- making a choice yourself ----------
function ChoicePanel({ opts, first, busy, onAct, onCancel }: { opts: any; first: string; busy: boolean; onAct: (i: number, l: string) => void; onCancel: () => void }) {
  const { chars } = useStore();
  const [open, setOpen] = useState<number | null>(null);
  const groups = useMemo(() => {
    const by: Record<string, any[]> = {};
    for (const o of opts.options) (by[o.category] = by[o.category] || []).push(o);
    return Object.entries(by).sort((a, b) => Math.max(...b[1].map((o) => o.prob)) - Math.max(...a[1].map((o) => o.prob)));
  }, [opts]);
  return (
    <div className="st-moment" style={{ ["--k" as any]: "var(--accent)" }}>
      <div className="row between">
        <div>
          <div className="st-kicker">Your move</div>
          <h2>{SLOT_LABEL[opts.slot] || opts.slot}, {opts.date}</h2>
        </div>
        <div className="row">
          <button disabled={busy} onClick={() => onAct(-1, "let them decide")} title="They pick using the same odds shown below">
            <Icon name="spark" size={14} /> Let {first} decide
          </button>
          <button className="ghost small" disabled={busy} onClick={onCancel}>Back</button>
        </div>
      </div>
      {opts.today.length > 0 && <div className="chips" style={{ margin: "6px 0 10px" }}>{opts.today.map((t: any, i: number) => <Tag key={i} tone="accent">today: {t.name}</Tag>)}</div>}
      <div className="hint" style={{ marginBottom: 8 }}>The percentage is how likely {first} is to pick it on their own. Tap an option to see why.</div>
      {groups.map(([cat, list]) => (
        <div key={cat} className="opt-group">
          <div className="hint opt-cat">{pretty(cat)}</div>
          {list.map((o: any) => (
            <div key={o.index} className={cx("opt", open === o.index && "open")}>
              <div className="opt-main" onClick={() => setOpen(open === o.index ? null : o.index)}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="opt-title">
                    {o.label}
                    {o.target_name && <> <span className="dim">·</span> {o.target && chars[o.target] ? <Name id={o.target} full /> : <span>{o.target_name}</span>}</>}
                    {o.risk >= 0.3 && <Tag tone="warn">risky</Tag>}
                  </div>
                  <div className="hint clamp1">{o.why}</div>
                </div>
                <div className="opt-odds" title={`utility ${o.utility}`}>
                  <div className="meter" style={{ height: 6, width: 80 }}><div className="meter-f" style={{ width: `${Math.max(2, o.prob * 100)}%`, background: "var(--accent-2)" }} /></div>
                  <span>{(o.prob * 100).toFixed(o.prob < 0.01 ? 1 : 0)}%</span>
                </div>
                <button className="primary small" disabled={busy} onClick={(e) => { e.stopPropagation(); onAct(o.index, `${o.label}${o.target_name ? " · " + o.target_name : ""}`); }}>Choose</button>
              </div>
              {open === o.index && (
                <div className="opt-why">
                  {o.terms ? <TermBars terms={o.terms} total={o.utility} /> : <div className="dim small">The full breakdown is recorded for the top options; this one scored {o.utility}.</div>}
                </div>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

// ---------- sidebar ----------
function QuickMe({ s }: { s: any }) {
  const me = s.me;
  const needs = me.needs || {};
  return (
    <Panel title="How you're doing" actions={<button className="small ghost" onClick={() => go("story/me")}>More</button>}>
      {me.injured && <div className="st-injury"><b>Hurt: {me.injury || "injury"}.</b> Out until {me.injured_until}. No games or practice till then.</div>}
      <div className="meters">
        <Meter label="mood" value={me.mood} color={moodColor(me.mood)} right={fmt(me.mood)} />
        {["energy", "social", "fun", "stress"].filter((n) => n in needs).map((n) => (
          <Meter key={n} label={n} value={needs[n]} invert={n === "stress"} color={n === "stress" ? undefined : "var(--info)"} right={fmt(needs[n])} />
        ))}
      </div>
      <div className="st-quick">
        <Stat label="GPA" value={fmt(me.gpa, 2)} tone={me.gpa >= 3.3 ? "good" : me.gpa < 2.3 ? "bad" : undefined} />
        <Stat label="friends" value={me.friends} />
        <Stat label="money" value={`$${Math.round(me.money)}`} />
      </div>
      {me.memberships.length > 0 && (
        <div className="chips" style={{ marginTop: 10 }}>{me.memberships.map((m: any) => <Tag key={m.id} tone={m.kind === "team" ? "accent" : "dim"}>{m.name}</Tag>)}</div>
      )}
    </Panel>
  );
}

function Inbox({ s, busy, onAnswer }: { s: any; busy: boolean; onAnswer: (inv: any, accept: boolean) => void }) {
  const queued = s.inbox.some((i: any) => i.id === s.control?.queued?.invite) ? s.control.queued.invite : null;
  const dayLabel = useDayLabel();
  return (
    <Panel title={`Inbox${s.inbox.length ? ` (${s.inbox.length})` : ""}`} sub="Invitations waiting on your answer">
      {s.inbox.length ? s.inbox.map((inv: any) => (
        <div key={inv.id} className="st-inv">
          <Avatar id={inv.from} size={32} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div><Name id={inv.from} full /> wants to {inv.action === "date" ? "go on a date" : "hang out"}</div>
            <div className="hint">asked {dayLabel(inv.day, true)}, {(SLOT_LABEL[inv.slot] || inv.slot).toLowerCase()}</div>
          </div>
          {queued === inv.id ? <Tag tone="good">you said yes</Tag> : (
            <div className="row" style={{ gap: 4 }}>
              <button className="small primary" disabled={busy} onClick={() => onAnswer(inv, true)}>Yes</button>
              <button className="small" disabled={busy} onClick={() => onAnswer(inv, false)}>No</button>
            </div>
          )}
        </div>
      )) : <Empty>Nothing waiting. When a friend invites you, it'll show up here.</Empty>}
      {queued && <div className="hint" style={{ marginTop: 6 }}>You'll say yes at your next free moment.</div>}
    </Panel>
  );
}

function Upcoming({ s }: { s: any }) {
  const { world } = useStore();
  const today = world?.day ?? 0;
  return (
    <Panel title="Coming up" sub="The next five weeks on your calendar">
      {s.upcoming.length ? s.upcoming.map((u: any, i: number) => {
        const d = u.day - today;
        const [l, tone] = KIND_TAG[u.kind] || [pretty(u.kind), "dim"];
        return (
          <div key={i} className="st-up">
            <div className="st-in">{d <= 0 ? <b>today</b> : <><b>{d}</b>day{d === 1 ? "" : "s"}</>}</div>
            <div><div>{u.name}</div><div className="hint">{u.date}</div></div>
            <Tag tone={tone}>{l}</Tag>
          </div>
        );
      }) : <Empty>Nothing on the calendar for the next few weeks.</Empty>}
    </Panel>
  );
}

// ---------- sports ----------
function SportsTab({ s }: { s: any }) {
  return (
    <div className="stack">
      <div className="grid g2 st-top">
        <Teams s={s} />
        <Recruiting s={s} />
      </div>
      {(s.draft?.projection || s.draft?.result) && <DraftBoard s={s} />}
      <Seasons s={s} />
      <BoxScores s={s} />
      <Trophies s={s} />
    </div>
  );
}

function Teams({ s }: { s: any }) {
  const cat = s.sports_catalog;
  const me = s.me;
  const tryouts = s.upcoming.filter((u: any) => u.kind === "tryout");
  return (
    <Panel title="Your teams" sub={Object.entries(me.positions || {}).map(([sp, pos]: any) => `${cat[sp]?.label || sp}: ${cat[sp]?.positions?.[pos] || pos}`).join(" · ")}
      actions={me.jersey !== null && me.jersey !== undefined && <span className="st-jersey">#{me.jersey}</span>}>
      {s.teams.length ? (
        <div className="st-teams">
          {s.teams.map((t: any) => (
            <div key={t.id} className="st-team">
              <div className="row between">
                <h4>{t.name}</h4>
                <Tag tone={t.level === "jv" ? "info" : "accent"}>{t.level === "jv" ? "JV" : "Varsity"}</Tag>
              </div>
              <div className="row" style={{ margin: "6px 0" }}>
                {t.starter ? <Tag tone="good">starter</Tag> : <Tag tone="warn">bench{t.bench_streak ? ` · ${t.bench_streak} straight` : ""}</Tag>}
                {t.captain && <Tag tone="accent">captain</Tag>}
                {t.position && <Tag>{cat[t.sport]?.positions?.[t.position] || t.position}</Tag>}
              </div>
              <Meter label="your rating" value={t.rating} right={fmt(t.rating)} color="var(--accent)" />
              <div className="row between small muted" style={{ marginTop: 6 }}>
                <span>Varsity record <b>{t.record.w}-{t.record.l}</b></span>
                {t.coach && <Name id={t.coach} full />}
              </div>
              <div className="hint" style={{ marginTop: 4 }}>{t.next_game ? `Next: ${t.next_game.name}, ${t.next_game.date}` : "No more games on the schedule this season."}</div>
            </div>
          ))}
        </div>
      ) : (
        <Empty>
          You're not on a team right now.
          {tryouts.length > 0 ? <> Next up: <b>{tryouts[0].name}</b> on {tryouts[0].date}.</> : " Each team holds tryouts before its season: football and soccer in early September, basketball in November, baseball and softball in March. Boys and girls have separate teams."}
        </Empty>
      )}
      <div className="hint" style={{ marginTop: 8 }}>Rating = skill, athletic ability, fitness, body type for the position and confidence. Coaches start the highest-rated players.</div>
    </Panel>
  );
}

function statCols(sport: string, cat: any, lines: any[]) {
  const labels: Record<string, string> = cat[sport]?.stats || {};
  const keys = Object.keys(labels).filter((k) => lines.some((l) => l && l[k]));
  return keys.map((k) => [k, labels[k]] as [string, string]);
}

function extraCols(sport: string, line: any, games: number) {
  const out: [string, string][] = [];
  if (sport === "baseball" || sport === "softball") {
    out.push(["AVG", line.ab ? (line.h / line.ab).toFixed(3).replace(/^0/, "") : "-"]);
    if (line.ip) out.push(["ERA", ((line.er || 0) * 9 / line.ip).toFixed(2)]);
  }
  if (sport === "basketball" && games) out.push(["PPG", ((line.pts || 0) / games).toFixed(1)]);
  if (sport === "soccer" && games) out.push(["G/game", ((line.goals || 0) / games).toFixed(2)]);
  return out;
}

function Seasons({ s }: { s: any }) {
  const cat = s.sports_catalog;
  const [perGame, setPerGame] = useState(false);
  const bySport: Record<string, any[]> = {};
  for (const st of s.seasons) (bySport[st.sport] = bySport[st.sport] || []).push(st);
  const sports = Object.keys(cat).filter((k) => bySport[k]);
  const val = (v: number, g: number) => (perGame && g ? (v / g).toFixed(1) : String(Math.round(v * 10) / 10));
  return (
    <Panel title="Season by season" sub="Every game you've played, added up. JV and varsity are kept separate."
      actions={sports.length > 0 && <Tabs tabs={[["tot", "Totals"], ["pg", "Per game"]]} active={perGame ? "pg" : "tot"} onChange={(k) => setPerGame(k === "pg")} />}>
      {sports.length ? sports.map((sp) => {
        const rows = bySport[sp];
        const car = s.career[sp];
        const cols = statCols(sp, cat, [...rows.map((r) => r.line), car?.line]);
        const ex = extraCols(sp, car?.line || {}, car?.games || 0).map((x) => x[0]);
        return (
          <div key={sp}>
            <div className="st-sport-h"><h3>{cat[sp].label}</h3>{car && <span className="hint">{car.seasons} season{car.seasons === 1 ? "" : "s"}</span>}</div>
            <div className="st-wrap">
              <table className="mini st-stats">
                <thead>
                  <tr>
                    <th>Season</th><th>Team</th><th>G</th><th>GS</th><th>W-L</th>
                    {cols.map(([k, l]) => <th key={k}>{l}</th>)}
                    {ex.map((e) => <th key={e}>{e}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => {
                    const [, yr, lvl] = r.key.split(":");
                    return (
                      <tr key={r.key}>
                        <td>{yr}</td>
                        <td>{r.team_name} {lvl === "jv" ? <Tag tone="info">JV</Tag> : <Tag tone="accent">V</Tag>}</td>
                        <td>{r.games}</td><td>{r.starts}</td><td>{r.wins}-{r.losses}</td>
                        {cols.map(([k]) => <td key={k}>{val(r.line[k] || 0, r.games)}</td>)}
                        {extraCols(sp, r.line, r.games).map(([k, v]) => <td key={k}>{v}</td>)}
                      </tr>
                    );
                  })}
                  {car && rows.length > 1 && (
                    <tr className="st-career">
                      <td>Career</td><td></td><td>{car.games}</td><td>{car.starts}</td><td>{car.wins}-{car.losses}</td>
                      {cols.map(([k]) => <td key={k}>{val(car.line[k] || 0, car.games)}</td>)}
                      {extraCols(sp, car.line, car.games).map(([k, v]) => <td key={k}>{v}</td>)}
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        );
      }) : <Empty>No games yet. Make a team and your stats start counting from your first game.</Empty>}
    </Panel>
  );
}

function lineText(line: any, sport: string, cat: any) {
  const labels: Record<string, string> = cat[sport]?.stats || {};
  const parts = Object.entries(line || {}).filter(([, v]) => v).map(([k, v]) => `${v} ${labels[k] || k}`);
  return parts.length ? parts.join(", ") : "no stats";
}

function BoxScores({ s }: { s: any }) {
  const p = s.protagonist;
  const cat = s.sports_catalog;
  const stamp = `${s.progress.day}:${s.feed[0]?.id ?? 0}`;
  const { data } = useApi<any>(`/api/events?char=${encodeURIComponent(p)}&type=game&limit=60`, [p, stamp]);
  const games = (data?.items || []).filter((e: any) => e.actors.includes(p) && (e.outcome === "win" || e.outcome === "loss")).slice(0, 8);
  const [sel, setSel] = useState<number | null>(null);
  const id = sel ?? games[0]?.id ?? null;
  const { data: ev } = useApi<any>(id !== null ? `/api/events/${id}` : null, [id]);
  const d = ev?.data;
  const box = d?.box || {};
  const sport = d?.sport;
  const ids = Object.keys(box).sort((a, b) => Number(box[b].starter) - Number(box[a].starter) || (box[b].perf || 0) - (box[a].perf || 0));
  const cols = sport ? statCols(sport, cat, ids.map((k) => box[k].line)) : [];
  return (
    <Panel title="Box scores" sub="Your most recent games. Tap one to see everyone's line.">
      {games.length ? (
        <>
          <div className="st-games">
            {games.map((g: any) => (
              <div key={g.id} className={cx("st-game", g.id === id && "sel")} onClick={() => setSel(g.id)}>
                <Tag tone={g.outcome === "win" ? "good" : "bad"}>{g.outcome === "win" ? "W" : "L"}</Tag>
                <span className="clamp1">{g.text}</span>
                <span className="hint">{g.date}</span>
              </div>
            ))}
          </div>
          {d && (
            <>
              <div className="row between" style={{ margin: "8px 0 4px" }}>
                <b>{d.group} vs {d.opponent}, {d.score}</b>
                <span className="hint">{d.fans ? `${d.fans} people you know in the stands` : ""}</span>
              </div>
              {box[p] && <div className="small" style={{ marginBottom: 6 }}>Your line: <b>{lineText(box[p].line, sport, cat)}</b>{box[p].approach && box[p].approach !== "normal" ? <span className="hint"> · played {pretty(box[p].approach)}</span> : null}</div>}
              <div className="st-wrap">
                <table className="mini st-stats">
                  <thead>
                    <tr><th>Player</th><th>Pos</th>{cols.map(([k, l]) => <th key={k}>{l}</th>)}<th>perf</th></tr>
                  </thead>
                  <tbody>
                    {ids.map((k) => (
                      <tr key={k} className={cx(k === p && "me")}>
                        <td><Name id={k} /> {box[k].starter ? "" : <span className="hint">bench</span>}</td>
                        <td>{box[k].pos}</td>
                        {cols.map(([c]) => <td key={c}>{box[k].line[c] || 0}</td>)}
                        <td>{fmt(box[k].perf)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="hint" style={{ marginTop: 6 }}>"perf" is each player's performance that night: their rating plus luck. <a href={`#/history/event/${id}`}>Open the full game record</a></div>
            </>
          )}
        </>
      ) : <Empty>{s.seasons.length ? "No recent box scores on record. Older games get folded into your season totals as history is trimmed." : "No games played yet."}</Empty>}
    </Panel>
  );
}

function Trophies({ s }: { s: any }) {
  const cat = s.sports_catalog;
  return (
    <Panel title="Trophy case" sub="Season awards are voted at the end of each season">
      {s.awards.length ? (
        <div className="st-trophies">
          {s.awards.map((a: any, i: number) => (
            <div key={i} className="st-trophy">
              <div className="cup">🏆</div>
              <b>{a.label}</b>
              <div className="hint">{cat[a.sport]?.label || a.sport} · {(a.season || "").split(":")[1] || ""}</div>
            </div>
          ))}
        </div>
      ) : <Empty>Nothing yet. MVPs and All-Conference picks land here.</Empty>}
    </Panel>
  );
}

function DraftBoard({ s }: { s: any }) {
  const d = s.draft;
  const r = d.result;
  const pj = d.projection;
  const grade = s.me.grade;
  return (
    <Panel title="MLB Draft board" sub="20 rounds every July. College players are eligible after junior year.">
      {r && (
        <div className="st-commit" style={{ marginBottom: 12 }}>
          <div className="st-kick">{r.year} draft</div>
          {r.status === "undrafted" || r.status === "returned_undrafted" ? <b>Went undrafted</b> : (
            <b>Round {r.round}, pick {r.pick}: {r.team}</b>
          )}
          {r.bonus ? <div className="small muted">Slot value about {money(r.bonus)} · starts at {r.level}</div> : null}
          <div className="small muted">{r.status === "signed" ? "Signed." : r.status === "returned" || r.status === "returned_undrafted" ? "Went back to school for another year." : r.status === "drafted" ? "Decision pending." : ""}</div>
        </div>
      )}
      {pj && (
        <div className="grid g2">
          <div>
            <div className="st-quick" style={{ marginTop: 0 }}>
              <Stat label="scout score" value={fmt(pj.score)} />
              <Stat label="projected" value={pj.round ? `Round ${pj.round}` : "undrafted"} />
              <Stat label="around pick" value={pj.round ? String(pj.pick) : "—"} />
            </div>
            <div className="hint" style={{ marginTop: 8 }}>
              {grade && grade < 15 ? `Eligible after your junior year (${15 - grade === 1 ? "next" : "in " + (15 - grade)} season${15 - grade === 1 ? "" : "s"}).` : "Eligible this July."} Projections move with every season. Draft day adds some luck.
            </div>
          </div>
          <div className="meters">
            {pj.terms.map(([k, v]: [string, number]) => <Signed key={k} label={k} value={v} right={fmt(v)} />)}
          </div>
        </div>
      )}
    </Panel>
  );
}

function Recruiting({ s }: { s: any }) {
  const rec = s.recruiting;
  const me = s.me;
  const cat = s.sports_catalog;
  const committed = pathText(me.path);
  const scores = Object.entries(rec.score || {});
  return (
    <Panel title="Recruiting board" sub="Who's watching, who's offering">
      {committed && (
        <div className="st-commit">
          <div className="st-kick">Decided</div>
          <b>{committed}</b>
          {(me.path.conference || me.path.tier) && <> <Tier t={me.path.conference || me.path.tier} /></>}
        </div>
      )}
      {scores.length > 0 && (
        <div className="st-quick" style={{ marginTop: 0, marginBottom: 12 }}>
          {scores.map(([sp, v]: any) => <Stat key={sp} label={`${cat[sp]?.label || sp} scout grade`} value={fmt(v)} />)}
        </div>
      )}
      {rec.offers.length > 0 && (
        <>
          <div className="st-sec-l">Offers</div>
          <div className="st-offers">
            {rec.offers.map((o: any, i: number) => (
              <div key={i} className="st-offer">
                <div className="row between"><b>{o.short || o.name}</b><Tier t={o.conference || o.tier} /></div>
                <div className="small muted">{o.sport} · {o.aid || (o.scholarship ? "scholarship" : "roster spot")}</div>
                {o.min_gpa ? <div className={cx("small", me.gpa < o.min_gpa ? "bad-t" : "dim")}>{me.gpa < o.min_gpa ? `Needs a ${o.min_gpa.toFixed(1)} GPA. You're at ${me.gpa.toFixed(2)}.` : `GPA ${o.min_gpa.toFixed(1)}+ to keep it`}</div> : null}
              </div>
            ))}
          </div>
        </>
      )}
      {rec.interest.length > 0 ? (
        <>
          <div className="st-sec-l">Interest</div>
          <div className="meters">
            {rec.interest.map((x: any, i: number) => (
              <Meter key={i} label={<span><Tier t={x.conference || x.tier} /> {x.short || x.name} <span className="dim">· {x.sport}{x.min_gpa ? ` · ${x.min_gpa.toFixed(1)} GPA` : ""}</span></span>} value={x.level} right={x.level}
                color={x.level >= 75 ? "var(--good)" : x.level >= 50 ? "var(--accent)" : "var(--dim)"} />
            ))}
          </div>
        </>
      ) : !rec.offers.length && !committed && (
        <Empty>
          {(me.grade || 0) < 10 ? "Colleges start watching in sophomore year." : "No college interest yet."} Strong seasons raise your scout grade; offers come junior and senior year if you're good enough and your GPA holds up.
        </Empty>
      )}
      {(rec.lost_offers || []).length > 0 && (
        <>
          <div className="st-sec-l" style={{ marginTop: 12 }}>Lost over grades</div>
          <div className="chips">{rec.lost_offers.map((o: any, i: number) => <Tag key={i} tone="bad">{o.short || o.name} {o.sport} (needed {o.min_gpa?.toFixed(1)})</Tag>)}</div>
        </>
      )}
      {rec.admits.length > 0 && (
        <>
          <div className="st-sec-l" style={{ marginTop: 12 }}>Admitted as a student</div>
          <div className="chips">{rec.admits.map((a: any, i: number) => <Tag key={i} tone="good">{a.short || a.name}</Tag>)}</div>
        </>
      )}
    </Panel>
  );
}

// ---------- people ----------
function Feel({ r, label }: { r: any; label: string }) {
  if (!r) return <div className="hint">{label}: haven't met</div>;
  return <Signed label={label} value={r.affection} right={fmt(r.affection)} />;
}

function PeopleTab({ s }: { s: any }) {
  const { chars } = useStore();
  const h = s.household;
  return (
    <div className="grid g2">
      <Panel title={h?.name || "Family"} sub={h ? `${h.style_label} · ${pretty(h.income || "")} income` : ""}>
        {h && (
          <div className="small muted" style={{ marginBottom: 10 }}>
            Parents: <b className="muted">{(h.guardians || []).join(" & ") || "-"}</b>
            {h.pet && <> · {h.pet.species} <b className="muted">{h.pet.name}</b></>}
          </div>
        )}
        {s.family.length ? s.family.map((f: any) => (
          <div key={f.id} className="st-sib" onClick={() => go(`characters/${f.id}`)}>
            <Avatar id={f.id} size={40} />
            <div style={{ minWidth: 0 }}>
              <div className="row between">
                <div><Name id={f.id} full /> <span className="hint">{f.year_label}</span> {f.twin && <Tag tone="accent">{f.twin_of === s.protagonist ? "your twin" : `twin of ${chars[f.twin_of]?.first ?? "a sibling"}`}</Tag>}</div>
                <span className="hint">{where(f.location, s.college)}</span>
              </div>
              {pathText(f.path) && <div className="small muted">{pathText(f.path)}</div>}
              <div className="meters" style={{ marginTop: 6 }}>
                <Feel r={f.mine} label="you → them" />
                <Feel r={f.theirs} label="them → you" />
              </div>
            </div>
          </div>
        )) : <Empty>No siblings.</Empty>}
      </Panel>
      <Panel title="Your people" sub="The relationships that matter most right now. Both sides feel things differently.">
        {s.people.length ? s.people.map((x: any) => {
          const m = x.mine;
          const t = x.theirs;
          return (
            <div key={x.id} className="st-person" onClick={() => go(`characters/${x.id}`)}>
              <Avatar id={x.id} size={34} />
              <div style={{ minWidth: 0 }}>
                <div className="row" style={{ gap: 6 }}>
                  <Name id={x.id} full />
                  <Tag tone={m.label === "rival" ? "bad" : m.affection >= 30 ? "good" : m.affection <= -20 ? "bad" : undefined}>{m.label}</Tag>
                  {x.roles.filter((r: string) => r !== "sibling").map((r: string) => <Tag key={r} tone={r === "partner" ? "romance" : r === "ex" ? "warn" : "info"}>{r}</Tag>)}
                  {m.crush && <Tag tone="romance">your crush</Tag>}
                  {t?.crush && <Tag tone="romance" title="This is the simulation's truth. Your character may not know.">likes you</Tag>}
                </div>
                <div className="hint">
                  {t ? `They see you as: ${t.label}` : "They barely know you"}
                  {m.rivalry >= 30 && ` · rivalry ${fmt(m.rivalry)}`}
                  {x.location !== "hollow_creek" && ` · ${where(x.location, s.college)}`}
                </div>
              </div>
              <div className="meters">
                <Signed label="you" value={m.affection} right={fmt(m.affection)} />
                <Signed label="them" value={t?.affection ?? 0} right={t ? fmt(t.affection) : "-"} />
              </div>
            </div>
          );
        }) : <Empty>Nobody yet. Get out there.</Empty>}
      </Panel>
    </div>
  );
}

// ---------- story so far ----------
function StorySoFar({ s }: { s: any }) {
  return (
    <div className="grid g-main">
      <Panel title="Story so far" sub="The notable things in your life, newest first. Tap any event to see exactly why it happened.">
        <div className="evlist scroll">{s.feed.length ? s.feed.map((e: any) => <EventRow key={e.id} ev={e} />) : <Empty>Your story hasn't started yet.</Empty>}</div>
        <div className="row" style={{ marginTop: 8 }}>
          <button className="small" onClick={() => go(`characters/${s.protagonist}`)}>Full timeline</button>
          <button className="small ghost" onClick={() => go("history")}>Everything in {PLACE.town}</button>
        </div>
      </Panel>
      <Upcoming s={s} />
    </div>
  );
}

// ---------- me ----------
function MeTab({ s, dayLabel }: { s: any; dayLabel: (d: number, short?: boolean) => string }) {
  const me = s.me;
  const cat = s.sports_catalog;
  const gh: [number, number][] = me.gpa_history || [];
  const ht = me.body?.height_in;
  return (
    <div className="grid g3">
      <Panel title="Mind and body">
        {me.injured && <div className="st-injury"><b>Hurt: {me.injury || "injury"}.</b> Out until {me.injured_until}.</div>}
        <div className="meters">
          <Meter label="mood" value={me.mood} color={moodColor(me.mood)} right={fmt(me.mood)} />
          {Object.entries(me.needs || {}).map(([n, v]: any) => (
            <Meter key={n} label={n} value={v} invert={n === "stress"} color={n === "stress" ? undefined : "var(--info)"} right={fmt(v)} />
          ))}
          <Meter label="popularity" value={me.popularity} color="var(--accent-2)" right={fmt(me.popularity)} />
        </div>
        <dl className="kv" style={{ marginTop: 12 }}>
          {ht && <><dt>Height</dt><dd>{Math.floor(ht / 12)}'{ht % 12}"</dd></>}
          {me.body?.build && <><dt>Build</dt><dd>{me.body.build}</dd></>}
          {me.body?.weight_lb && <><dt>Weight</dt><dd>{me.body.weight_lb} lb</dd></>}
          {me.jersey !== null && me.jersey !== undefined && <><dt>Jersey</dt><dd>#{me.jersey}</dd></>}
          {Object.entries(me.positions || {}).map(([sp, pos]: any) => <React.Fragment key={sp}><dt>{cat[sp]?.label || sp}</dt><dd>{cat[sp]?.positions?.[pos] || pos}</dd></React.Fragment>)}
          <dt>Money</dt><dd>${fmt(me.money, 2)}</dd>
        </dl>
      </Panel>
      <Panel title="School" sub={`GPA ${fmt(me.gpa, 2)}`}>
        {gh.length > 1 ? (
          <LineChart series={[{ name: "GPA", color: "var(--accent)", values: gh.map((x) => x[1]) }]} xLabels={gh.map((x) => dayLabel(x[0]))} height={150} fmtY={(v) => v.toFixed(2)} />
        ) : <Empty>Your GPA chart fills in with each report card.</Empty>}
        {gh.length > 0 && (
          <table className="mini" style={{ marginTop: 8 }}>
            <tbody>{gh.slice().reverse().slice(0, 8).map((x, i) => <tr key={i}><td>{dayLabel(x[0])}</td><td className="num"><b>{x[1].toFixed(2)}</b></td></tr>)}</tbody>
          </table>
        )}
      </Panel>
      <Panel title="What you're working toward">
        {me.goals.length ? me.goals.map((g: any) => (
          <div key={g.id} className="row between small" style={{ padding: "5px 0", borderBottom: "1px solid var(--line)" }}>
            <span>{g.label}</span><Tag tone="accent">priority {fmt(g.priority)}</Tag>
          </div>
        )) : <Empty>No active goals.</Empty>}
        {me.interests?.length > 0 && (
          <>
            <div className="st-sec-l" style={{ marginTop: 12 }}>Into</div>
            <div className="chips">{me.interests.map(([k, v]: any) => <Tag key={k}>{pretty(k)} {v}</Tag>)}</div>
          </>
        )}
        {me.reputation?.length > 0 && (
          <>
            <div className="st-sec-l" style={{ marginTop: 12 }}>Known for</div>
            <div className="chips">{me.reputation.map(([k, v]: any) => <Tag key={k} tone={v >= 0 ? "good" : "bad"}>{pretty(k)}</Tag>)}</div>
          </>
        )}
      </Panel>
    </div>
  );
}
