// The phone app: your story in first person. Tabs: Story, Phone (texts + contacts), Home (family + pets), Me.
import { ScheduleScreen } from "./Schedule";
import "@fontsource/fredoka/latin-600.css";
import "@fontsource/nunito/latin-400.css";
import "@fontsource/nunito/latin-700.css";
import "@fontsource/nunito/latin-800.css";
import React, { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import { SAMPLE_SPEC, STANDALONE, pickFile, startFromFile } from "./StoryFiles";
import { pgo } from "./api";
import CreateStory from "./CreateStory";
import { Portrait, Scene } from "./art";
import Gallery from "./art/Gallery";
import HomeTab from "./HomeTab";
import { PIcon } from "./icons";
import { cx, errText, Toasts } from "./kit";
import MeTab from "./MeTab";
import Studio from "./Studio";
import TextingHub from "./TextingHub";
import Editor from "./Editor";
import { PhoneProvider, usePhone } from "./PhoneContext";
import Diagnostics, { applyHidden, applyPageScroll, applyPlain, hiddenParts, pageScrollOn, plainOn } from "./Diagnostics";
import PhoneTab from "./PhoneTab";
import PlayLine from "./PlayLine";
import SceneTab from "./SceneTab";
import SportsTab from "./SportsTab";
import StoryTab from "./StoryTab";
import "./phone.css";

// five quick taps on the same tab (the tab bar always shows, even when a screen won't): diagnostics, about that screen
let taps: { k: string; t: number }[] = [];
function tapTab(k: string) {
  const now = Date.now();
  taps = [...taps.filter((x) => x.k === k && now - x.t < 2500), { k, t: now }];
  if (taps.length >= 5) {
    taps = [];
    window.dispatchEvent(new Event("lifeos-diag"));
  }
}

export default function PhoneApp({ route }: { route: string[] }) {
  const [diag, setDiag] = useState(false);
  useEffect(() => {
    applyPlain(plainOn());
    applyPageScroll(pageScrollOn());
    applyHidden(hiddenParts());
    const open = () => setDiag(true);
    window.addEventListener("lifeos-diag", open);
    return () => window.removeEventListener("lifeos-diag", open);
  }, []);
  useEffect(() => {
    if (route[0] === "diag") setDiag(true);
    // page scrolling: a new screen starts at the top (a scrolling box did that by being new)
    if (document.documentElement.classList.contains("ph-docscroll")) window.scrollTo(0, 0);
  }, [route.join("/")]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    document.documentElement.classList.add("ph-html");
    const meta = document.querySelector('meta[name="theme-color"]');
    const prev = meta?.getAttribute("content");
    meta?.setAttribute("content", "#fff4e6");
    return () => {
      document.documentElement.classList.remove("ph-html");
      if (meta && prev) meta.setAttribute("content", prev);
    };
  }, []);
  return (
    <PhoneProvider>
      <div className="ph-root">
        <div className="ph-frame">
          <Oops route={route.join("/")}>
            <Shell route={route} />
          </Oops>
          <SlowNotes />
          <div id="ph-portal" />
          <Toasts />
          {diag && <Diagnostics onClose={() => { setDiag(false); if (route[0] === "diag") pgo(""); }} />}
        </div>
      </div>
    </PhoneProvider>
  );
}

/** The engine is taking a long time on something: say what, instead of a spinner that never explains itself. */
function SlowNotes() {
  const { toast } = usePhone();
  useEffect(() => {
    const on = (e: Event) => {
      const d = (e as CustomEvent).detail || {};
      toast(d.text || "Still working on it…", d.kind === "stuck" ? "bad" : undefined);
    };
    window.addEventListener("lifeos-slow", on);
    return () => window.removeEventListener("lifeos-slow", on);
  }, [toast]);
  return null;
}

/** If something on a screen breaks, say so and offer a way back, instead of the whole app going blank. */
class Oops extends React.Component<{ route: string; children: React.ReactNode }, { err: string | null; at: string }> {
  state = { err: null as string | null, at: "" };
  static getDerivedStateFromError(e: any) {
    return { err: String(e?.message || e).slice(0, 300) };
  }
  componentDidUpdate(prev: { route: string }) {
    if (prev.route !== this.props.route && this.state.err) this.setState({ err: null });  // a new screen: try again
  }
  render() {
    if (!this.state.err) return this.props.children;
    return (
      <div className="ph-oops">
        <b>Something went wrong on this screen.</b>
        <p>Your story is fine and nothing was lost. Go back and try again.</p>
        <small>{this.state.err}</small>
        <button className="ph-btn primary block" onClick={() => { this.setState({ err: null }); window.location.hash = "#/m/me"; }}>Back</button>
        <button className="ph-btn soft block" onClick={() => window.location.reload()}>Restart the app</button>
      </div>
    );
  }
}

function Shell({ route }: { route: string[] }) {
  const { state, error, refresh } = usePhone();
  const tab = route[0] || "story";
  // keep the badges fresh when coming back to the app
  useEffect(() => {
    const onVis = () => document.visibilityState === "visible" && refresh();
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [refresh]);
  useEffect(() => {
    if (tab !== "story") refresh();
  }, [tab]); // eslint-disable-line react-hooks/exhaustive-deps

  if (tab === "gallery") return <div className="ph-screen"><Gallery /></div>;
  if (!state) {
    return (
      <div className="ph-loading">
        {error ? (
          <>
            <div className="ph-loading-t">Can't reach your game</div>
            <p>{error}</p>
            <p className="ph-dim">Make sure LIFE OS is running on your computer and your phone is on the same Wi-Fi.</p>
            <button className="ph-btn primary" onClick={() => refresh()}>Try again</button>
          </>
        ) : (
          <>
            <div className="ph-spinner" />
            <div className="ph-loading-t">Waking up {""}your story…</div>
          </>
        )}
      </div>
    );
  }
  if (tab === "create") return <CreateStory hasStory={!!state.active} />;
  if (!state.active) return <Welcome />;
  let body: React.ReactNode;
  if (tab === "phone") body = <PhoneTab route={route.slice(1)} />;
  else if (tab === "home") body = <HomeTab />;
  else if (tab === "scene") body = <SceneTab route={route.slice(1)} />;
  else if (tab === "sports") body = <SportsTab route={route.slice(1)} />;
  else if (tab === "me") body = <MeTab />;
  else if (tab === "edit") body = route[1] ? <Editor route={route.slice(1)} /> : <Studio route={["people"]} />;
  else if (tab === "studio") body = <Studio route={route.slice(1)} />;
  else if (tab === "roles") body = <Studio route={["roles"]} />;
  else if (tab === "texting") body = <TextingHub />;
  else if (tab === "schedule") body = <ScheduleScreen />;
  else if (tab === "playline") body = <PlayLine route={route.slice(1)} />;
  else body = <StoryTab />;
  return (
    <>
      <div className={cx("ph-screen", "tab-" + tab)} key={tab}>{body}</div>
      <TabBar tab={tab} />
    </>
  );
}

function TabBar({ tab }: { tab: string }) {
  const { state } = usePhone();
  const items: [string, string, string, React.ReactNode?][] = [
    ["story", "Story", "story", state?.moments.length ? <i className="ph-dot" /> : null],
    ["scene", "Scene", "people", null],
    ["sports", "Sports", "trophy", null],
    ["phone", "Phone", "phone", state?.unread ? <b className="ph-badge">{state.unread > 99 ? "99+" : state.unread}</b> : state?.needs_reply ? <i className="ph-dot" /> : null],
    ["home", "Home", "home", state?.pet_setup_needed ? <i className="ph-dot" /> : null],
    ["me", "Me", "me", null],
  ];
  return (
    <nav className="ph-tabbar">
      {items.map(([k, label, icon, badge]) => (
        <button key={k} className={cx("ph-tab", tab === k && "on")} onClick={() => { tapTab(k); pgo(k === "story" ? "" : k); }}>
          <span className="ph-tab-i"><PIcon name={icon} size={23} stroke={tab === k ? 2.4 : 2} />{badge}</span>
          <span className="ph-tab-l">{label}</span>
        </button>
      ))}
    </nav>
  );
}

function Welcome() {
  const { refresh, toast } = usePhone();
  const lab = useStore();
  const [list, setList] = useState<any[] | null>(null);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => {
    api.get("/api/characters").then((cs: any[]) => setList(cs.filter((c) => c.role === "student" && c.status === "active"))).catch(() => setList([]));
  }, []);
  const pick = async (id: string) => {
    setBusy(id);
    try {
      await api.post("/api/story/protagonist", { id });
      await refresh();
      lab.refresh();
      pgo("");
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  const fromFile = async () => {
    const f = await pickFile(".json,.txt,.xlsx,.lifeos,application/json,text/plain");
    if (!f) return;
    setBusy("file");
    try {
      toast(await startFromFile(f), "good");
      await refresh();
      lab.refresh();
      pgo("");
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  const sample = async () => {
    setBusy("sample");
    try {
      await api.post("/api/story/new", { spec: SAMPLE_SPEC });
      await refresh();
      lab.refresh();
      pgo("");
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  const shown = (list || []).filter((c) => !q || c.name.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="ph-screen ph-welcome">
      <div className="ph-hero welcome">
        <Scene art="school_hall" season="fall" phase="after_school" className="ph-hero-art" />
        <div className="ph-hero-fade" />
        <div className="ph-hero-text">
          <div className="ph-kicker">LIFE OS</div>
          <h1>Seven years. One life. Yours.</h1>
          <p>Freshman year through college. Every choice is yours, and everyone else is living their own life too.</p>
        </div>
      </div>
      <div className="ph-pad">
        <div className="ph-card">
          <div className="ph-card-row">
            <div className="ph-icon-bubble"><PIcon name="sparkle" size={22} /></div>
            <div>
              <h3>Make your story</h3>
              <p className="ph-dim">You, your family, your siblings, your pet and your people, right here on your phone. Takes a few minutes; anything you skip gets filled in.</p>
            </div>
          </div>
          <button className="ph-btn primary block big" disabled={!!busy} onClick={() => pgo("create")}>
            <PIcon name="sparkle" size={18} /> Create my story
          </button>
          <button className="ph-btn soft block" disabled={!!busy} onClick={fromFile}>
            {busy === "file" ? <span className="ph-spinner small" /> : <PIcon name="upload" size={17} />} Load a cast file or backup
          </button>
          <div className="ph-welcome-more">
            <button className="ph-link" disabled={!!busy} onClick={sample}>
              {busy === "sample" ? <span className="ph-spinner small" /> : null} Try a sample story
            </button>
            {!STANDALONE && <a className="ph-link" href="#/story/new">Story builder on the computer</a>}
          </div>
        </div>
        <div className="ph-section-t">Or play as someone already in town</div>
        <input className="ph-input" type="search" placeholder="Search by name" value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="ph-list">
          {list === null && <div className="ph-dim ph-center">Loading people…</div>}
          {shown.slice(0, 60).map((c) => (
            <button key={c.id} className="ph-row" onClick={() => pick(c.id)} disabled={!!busy}>
              <Portrait look={c.look} size={46} color={c.color} name={c.first} />
              <div className="ph-row-main">
                <b>{c.name}</b>
                <span className="ph-dim">{c.year_label}{c.memberships?.length ? ` · ${c.memberships.slice(0, 2).map((m: any) => m.name).join(", ")}` : ""}</span>
              </div>
              {busy === c.id ? <span className="ph-spinner small" /> : <PIcon name="chevron" size={18} />}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
