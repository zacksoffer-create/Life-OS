import React from "react";
import { api } from "./api";
import Characters from "./pages/Characters";
import Experiments from "./pages/Experiments";
import History from "./pages/History";
import Library from "./pages/Library";
import Overview from "./pages/Overview";
import Play from "./pages/Play";
import Saves from "./pages/Saves";
import Schedule from "./pages/Schedule";
import Social from "./pages/Social";
import Story from "./pages/Story";
import StoryNew from "./pages/StoryNew";
import Workshop from "./pages/Workshop";
import Connect from "./pages/Connect";
import PhoneApp from "./phone/PhoneApp";
import { SPEEDS, useRoute, useStore } from "./store";
import { cx, Icon, Meter } from "./ui";

const NAV: [string, string, string, string?][] = [
  ["story", "My Story", "play"],
  ["connect", "Play on Your Phone", "spark"],
  ["overview", "World Overview", "overview"],
  ["characters", "Character Studio", "people"],
  ["social", "Social Network", "web"],
  ["play", "Live Any Life", "spark"],
  ["history", "History Explorer", "history", "Lab"],
  ["schedule", "Story Schedule", "history"],
  ["experiments", "Experiment Center", "flask"],
  ["workshop", "Engine Workshop", "sliders"],
  ["library", "Content Library", "book"],
  ["saves", "Saves & Worlds", "save"],
];

const PHASE_LABEL: Record<string, string> = { dawn: "Morning", classes: "Classes", lunch: "Lunch", after_school: "After school", day: "Daytime", evening: "Evening", night: "Night" };

function TopBar() {
  const { world, advance, job, auto, setAuto, speed, setSpeed, toast, bump, refresh } = useStore();
  if (!world) return <div className="topbar" />;
  const busy = !!job || world.busy;
  const pi = world.phases.indexOf(world.phase);
  const go = async (days: number, label: string) => {
    const j = await advance(days);
    if (j && j.status === "done" && days > 1) toast(`Advanced ${label}: ${j.new_events} new events in ${j.seconds}s`, "good");
  };
  const quickSave = async () => {
    try {
      await api.post("/api/saves", { name: `Quick save - ${world.date}` });
      toast("Saved. Find it under Saves & Worlds.", "good");
      bump();
    } catch (e: any) {
      toast(e.message, "bad");
    }
  };
  return (
    <div className="topbar">
      <div className="clock">
        <div className="date">{world.date}</div>
        <div className="meta">
          <span>{world.term}</span>·<span>Year {world.year}</span>·<span>{PHASE_LABEL[world.phase] || world.phase}</span>
          <span className="phases" title="Phases of the day">
            {world.phases.map((p, i) => <i key={p} title={PHASE_LABEL[p] || p} className={cx(i < pi && "done", i === pi && "now")} />)}
          </span>
        </div>
      </div>
      <div className="controls">
        <button onClick={() => go(1, "a day")} disabled={busy || auto} title="Advance one day"><Icon name="step" size={14} /> Day</button>
        <button onClick={() => go(7, "a week")} disabled={busy || auto}>Week</button>
        <button onClick={() => go(30, "a month")} disabled={busy || auto}>Month</button>
        <button onClick={() => go(365, "a year")} disabled={busy || auto} title="A simulated year takes roughly 25-35 seconds">Year</button>
        <span className="sep" />
        <button className={cx(auto && "on")} onClick={() => setAuto(!auto)} title="Keep advancing until paused">
          <Icon name={auto ? "pause" : "play"} size={14} /> {auto ? "Pause" : "Auto"}
        </button>
        <select value={speed} onChange={(e) => setSpeed(e.target.value)} title="Auto speed">
          {SPEEDS.map((s) => <option key={s.id} value={s.id}>{s.label} ({s.days === 1 ? "1 day" : `${s.days} days`}/step)</option>)}
        </select>
        <span className="sep" />
        <button className="ghost" onClick={quickSave} disabled={busy} title="Save a snapshot"><Icon name="save" size={15} /> Save</button>
        <button className="ghost" onClick={() => { refresh(); bump(); }} title="Reload from the server">Refresh</button>
      </div>
      {job && job.status === "running" && (
        <div className="jobbar">
          <Meter value={job.done} max={Math.max(1, job.days)} color="var(--accent-2)" />
          <small>Simulating day {job.done} of {job.days}...</small>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const route = useRoute();
  const { world, error, toasts } = useStore();
  const page = route[0];
  if (page === "m") return <PhoneApp route={route.slice(1)} />;
  let body: React.ReactNode;
  if (error && !world) {
    body = (
      <div className="offline panel">
        <div className="panel-b">
          <h2>Can't reach the simulation server</h2>
          <p className="muted">{error}</p>
          <p className="muted">Start it from the <code>lifeos</code> folder with <code>python run.py</code>, then reload this page.</p>
        </div>
      </div>
    );
  } else if (!world) {
    body = <div className="loading">Waking up the town...</div>;
  } else {
    body = {
      story: route[1] === "new" ? <StoryNew route={route} /> : <Story route={route} />,
      overview: <Overview />,
      characters: <Characters route={route} />,
      social: <Social route={route} />,
      play: <Play route={route} />,
      history: <History route={route} />,
      schedule: <Schedule />,
      experiments: <Experiments route={route} />,
      workshop: <Workshop route={route} />,
      library: <Library route={route} />,
      saves: <Saves />,
      connect: <Connect />,
    }[page] || <Overview />;
  }
  return (
    <div className="app">
      <aside className="side">
        <div className="brand">
          <div className="logo"><i /> LIFE OS</div>
          <div className="tag-line">Living World Laboratory · v0.1</div>
        </div>
        <nav className="nav">
          {NAV.map(([k, label, icon, group]) => (
            <React.Fragment key={k}>
              {group && <div className="group-l">{group}</div>}
              <a href={`#/${k}`} className={cx(page === k && "on")}>
                <Icon name={icon} /> {label}
              </a>
            </React.Fragment>
          ))}
        </nav>
        {world && (
          <div className="side-foot">
            <div><b>{world.town?.name || world.name}</b></div>
            <div>{world.population.student || 0} students · {world.population.staff || 0} staff{world.population.alumni ? ` · ${world.population.alumni} alumni` : ""}</div>
            <div>world seed {world.gen_seed} · sim seed {world.seed}</div>
            <div>rules {world.rules_version}{world.action_overrides.length ? ` · ${world.action_overrides.length} action edits` : ""}</div>
            <div>{world.events.toLocaleString()} events on record</div>
          </div>
        )}
      </aside>
      <div className="main">
        <TopBar />
        <div className="content">{body}</div>
      </div>
      <div className="toasts">
        {toasts.map((t) => <div key={t.id} className={cx("toast", t.tone)}>{t.msg}</div>)}
      </div>
    </div>
  );
}
