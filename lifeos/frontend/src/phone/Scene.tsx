// Phone → Scene: your school's world from where you're standing. Where you stand, the groups (and your way in), who's
// together, who's popular, and friends of friends you could meet (ask a friend to introduce you: free, once a day).
import React, { useEffect, useState } from "react";
import { Chip, Line, phoneApi, pgo, Rumor, SceneMini, SceneView } from "./api";
import { Portrait } from "./art";
import { cx, errText, Lines, Sheet, StatChips } from "./kit";
import { usePhone } from "./PhoneContext";

function Face({ p, size = 40 }: { p: SceneMini; size?: number }) {
  return <Portrait look={p.look} size={size} color={p.color} name={p.first} />;
}

/** The Scene tab's Crowd (the groups and your way in, people you could meet) and Talk (what people are saying, who's
 * fighting, who's together) sections. */
export function SceneScreen({ section }: { section: "crowd" | "talk" }) {
  const { toast, refresh } = usePhone();
  const [v, setV] = useState<SceneView | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [out, setOut] = useState<{ lines: Line[]; chips: Chip[]; title: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const load = () => phoneApi.scene().then(setV).catch((e) => toast(errText(e), "bad"));
  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  if (!v) return <div className="pm-empty"><span className="ph-spinner" /></div>;

  const intro = async (via: string, to: string) => {
    setBusy(true);
    try {
      const r = await phoneApi.sceneIntro(via, to);
      setV(r.scene);
      setOut({ lines: r.lines, chips: r.chips, title: "Introduced" });
      refresh();
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(false);
    }
  };
  const rumor = async (id: string, what: string) => {
    setBusy(true);
    try {
      const r = await phoneApi.sceneRumor(id, what);
      setV(r.scene);
      setOut({ lines: r.lines, chips: r.chips, title: "What you did" });
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
      refresh();
    } catch (e) {
      toast(errText(e), "bad");
    }
  };
  const talk = section === "talk";
  return (
    <div className="sc">
      {talk && <>
      <div className="sc-h">What people are saying</div>
      {v.talk.length === 0 && <div className="sc-dim">You haven't heard anything yet. Your friends will fill you in.</div>}
      {v.talk.slice(0, 8).map((t) => <RumorCard key={t.id} t={t} busy={busy} onAct={rumor} />)}
      {v.fights.length > 0 && (
        <>
          <div className="sc-sub">Still not speaking</div>
          {v.fights.map((f) => (
            <div key={f.a + f.b} className="sc-fight"><b>{f.a} & {f.b}</b><small>since {f.when} · over {f.reason}</small></div>
          ))}
        </>
      )}
      </>}

      {!talk && <>
      <div className="sc-h">The groups</div>
      {v.groups.length === 0 && <div className="sc-dim">No real groups have formed yet. Give it a few weeks.</div>}
      {v.groups.map((g) => (
        <div key={g.id} className={cx("sc-group", g.mine && "mine")}>
          <button className="sc-group-top" onClick={() => setOpen(open === g.id ? null : g.id)}>
            <div className="sc-faces">
              {g.members.slice(0, 5).map((m) => <span key={m.id} className={cx(m.friend && "fr", m.me && "me")}><Face p={m} size={34} /></span>)}
              {g.size > 5 && <span className="sc-more">+{g.size - 5}</span>}
            </div>
            <div className="sc-group-m">
              <b>{g.name}</b>
              <small>{g.mine ? "Your group" : g.friends ? `${g.friends} friend${g.friends === 1 ? "" : "s"} here` : "You don't know anyone"} · {g.standing}{g.vibe ? ` · ${g.vibe}` : ""}</small>
            </div>
          </button>
          {open === g.id && (
            <div className="sc-group-b">
              {g.members.map((m) => (
                <button key={m.id} className="sc-person" onClick={() => !m.me && pgo(`phone/contact/${encodeURIComponent(m.id)}`)}>
                  <Face p={m} size={36} />
                  <span><b>{m.name}{m.me ? " (you)" : ""}</b><small>{m.year}{m.family ? " · family" : m.friend ? " · your friend" : ""}</small></span>
                </button>
              ))}
              {!g.mine && g.way_in && (
                <div className="sc-way">
                  <span>Your way in: <b>{g.way_in.first}</b>. Hang out, get close to the rest, and next time the groups shift you're in.</span>
                  <button className="ph-btn primary" onClick={() => plan(g.way_in!.id)}>Hang out with {g.way_in.first}</button>
                </div>
              )}
              {!g.mine && !g.way_in && <div className="sc-dim">No way in yet. Meet one of them first (see People you could meet).</div>}
            </div>
          )}
        </div>
      ))}

      <div className="sc-h">People you could meet</div>
      {v.meet.length === 0 && <div className="sc-dim">Nobody new through your friends right now. Make more friends and their friends show up here.</div>}
      {v.meet.length > 0 && <div className="sc-dim small">Ask a friend to introduce you. It's free, one a day{v.intro_today ? " (used today)" : ""}.</div>}
      {v.meet.map((p) => (
        <div key={p.id} className="sc-meet">
          <Face p={p} size={44} />
          <span className="sc-meet-m"><b>{p.name}</b><small>{p.year} · friends with {p.mutual.join(", ")}</small></span>
          <button className="sc-ask" disabled={busy || v.intro_today} onClick={() => intro(p.via.id, p.id)}>Ask {p.via.first}</button>
        </div>
      ))}

      </>}

      {talk && <>
      <div className="sc-h">Who's together</div>
      {v.couples.length === 0 && <div className="sc-dim">Nobody's official yet.</div>}
      {v.couples.map((c) => (
        <div key={c.a.id + c.b.id} className={cx("sc-couple", c.you && "you")}>
          <span className="sc-pair"><Face p={c.a} size={34} /><Face p={c.b} size={34} /></span>
          <span className="sc-couple-m"><b>{c.a.first} & {c.b.first}</b><small>since {c.since}</small></span>
          {c.new && <span className="sc-new">new</span>}
        </div>
      ))}
      {v.breakups.length > 0 && (
        <>
          <div className="sc-sub">Just broke up</div>
          {v.breakups.map((c) => (
            <div key={c.a.id + c.b.id} className="sc-couple split">
              <span className="sc-pair"><Face p={c.a} size={30} /><Face p={c.b} size={30} /></span>
              <span className="sc-couple-m"><b>{c.a.first} & {c.b.first}</b><small>{c.when}</small></span>
            </div>
          ))}
        </>
      )}

      </>}
      <div style={{ height: 20 }} />

      <Sheet open={!!out} onClose={() => setOut(null)} title={out?.title}>
        {out && (
          <>
            <Lines lines={out.lines} />
            <StatChips chips={out.chips} />
            <button className="ph-btn primary block" onClick={() => setOut(null)}>Nice</button>
          </>
        )}
      </Sheet>
    </div>
  );
}

const ACTS: Record<string, [string, string][]> = {
  you: [["deny", "Set the record straight"], ["own", "Own it"], ["find", "Who started it?"]],
  them: [["tell", "Warn them"], ["pass", "Pass it on"], ["drop", "Keep it to yourself"]],
};
const DID: Record<string, string> = { deny: "You set the record straight.", own: "You owned it.", find: "You asked around.", tell: "You warned them.",
  pass: "You passed it on.", drop: "You kept it to yourself." };

function RumorCard({ t, busy, onAct }: { t: Rumor; busy: boolean; onAct: (id: string, what: string) => void }) {
  const acts = ACTS[t.about_you ? "you" : "them"];
  return (
    <div className={cx("sc-rumor", t.about_you && "you")}>
      <div className="sc-rumor-top">
        {t.about ? <Portrait look={t.about.look} size={36} color={t.about.color} name={t.about.first} /> : <span className="sc-rumor-dot">!</span>}
        <div className="sc-rumor-m">
          <p>“{t.text}”</p>
          <small>
            {t.about_you ? "About you" : t.from ? `${t.from} told you` : "You heard it"} · {t.spread}
            {t.about_you && t.true !== null ? (t.true ? " · it's true" : " · it's not true") : ""}
          </small>
        </div>
        {t.new && <span className="sc-new">new</span>}
      </div>
      {t.acted ? (
        <div className="sc-done">{DID[t.acted] || "Done."}{t.origin ? ` It started with ${t.origin}.` : ""}</div>
      ) : (
        <div className="sc-acts">
          {acts.map(([k, l]) => (
            <button key={k} disabled={busy} onClick={() => onAct(t.id, k)}>{k === "tell" && t.about ? `Warn ${t.about.first}` : l}</button>
          ))}
        </div>
      )}
    </div>
  );
}
