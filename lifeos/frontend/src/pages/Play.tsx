import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { go, useStore, PLACE } from "../store";
import { Avatar, Calc, Changes, Empty, ErrorBox, EventRow, Icon, Loading, Meter, Name, Panel, Tag, TermBars, cx, fmt, moodColor, pretty, signed } from "../ui";
import "./play.css";

const SLOT_LABEL: Record<string, string> = { lunch: "Lunch", after_school: "After school", day: "Daytime", evening: "Evening" };

export default function Play({ route }: { route: string[] }) {
  const id = route[1];
  if (!id) return <Picker />;
  return <Session id={id} key={id} />;
}

function Picker() {
  const { charList } = useStore();
  const studs = charList.filter((c) => c.role === "student");
  return (
    <div className="stack">
      <div className="page-h">
        <div>
          <h1>Live a Life</h1>
          <p>Step into one person's shoes. At each decision point you see the options they actually have and how likely they'd be to pick each one on their own. You choose; the simulation decides how it goes. Everyone else keeps living autonomously around you.</p>
        </div>
      </div>
      <div className="pick-grid">
        {studs.map((c) => (
          <div key={c.id} className="pick" onClick={() => go(`play/${c.id}`)}>
            <Avatar id={c.id} size={46} />
            <div>
              <b>{c.name}</b> {c.featured && <span className="star">★</span>}
              <div className="hint">Grade {c.grade} · {c.archetype}</div>
              <div className="small muted clamp2">{c.bio}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Session({ id }: { id: string }) {
  const { chars, refresh, bump, toast } = useStore();
  const [opts, setOpts] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<number | null>(null);
  const [log, setLog] = useState<any[]>([]);
  const [hideOdds, setHideOdds] = useState(false);
  const c = chars[id];

  const load = async () => {
    setBusy(true);
    setErr(null);
    try {
      setOpts(await api.post(`/api/play/${id}/options`));
      await refresh();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const act = async (index: number, label: string) => {
    setBusy(true);
    try {
      const r = await api.post(`/api/play/${id}/act`, { index });
      setLog((l) => [{ when: `${opts.date} · ${SLOT_LABEL[opts.slot] || opts.slot}`, choice: label, auto: index < 0, ...r }, ...l]);
      setOpen(null);
      await refresh();
      bump();
      setOpts(await api.post(`/api/play/${id}/options`));
    } catch (e: any) {
      toast(e.message, "bad");
    } finally {
      setBusy(false);
    }
  };

  const groups = useMemo(() => {
    if (!opts) return [];
    const by: Record<string, any[]> = {};
    for (const o of opts.options) (by[o.category] = by[o.category] || []).push(o);
    return Object.entries(by).sort((a, b) => Math.max(...b[1].map((o) => o.prob)) - Math.max(...a[1].map((o) => o.prob)));
  }, [opts]);

  if (!c) return <Loading />;
  return (
    <div className="stack">
      <div className="page-h">
        <div className="row" style={{ alignItems: "center" }}>
          <Avatar id={id} size={54} />
          <div>
            <h1>Living as {c.name}</h1>
            <p style={{ margin: 0 }}>{c.bio}</p>
          </div>
        </div>
        <div className="row">
          <label className="row small muted" style={{ gap: 6 }}><input type="checkbox" checked={hideOdds} onChange={(e) => setHideOdds(e.target.checked)} /> hide their inclinations</label>
          <button onClick={() => go(`characters/${id}`)}>Profile</button>
          <button onClick={() => go("play")}>Switch person</button>
        </div>
      </div>
      <ErrorBox error={err} />
      {!opts ? <Loading what="Moving to their next decision" /> : (
        <div className="grid g-main">
          <div className="stack">
            <Panel title={`${opts.date} · ${SLOT_LABEL[opts.slot] || opts.slot}`}
              sub={`${opts.options.length} options. Getting here moved the clock to ${c.first}'s next decision; everyone else acted on their own along the way.`}
              actions={<button disabled={busy} onClick={() => act(-1, "let them decide")} title="They choose for themselves, using the same odds shown below"><Icon name="spark" size={14} /> Let {c.first} decide</button>}>
              {opts.today.length > 0 && (
                <div className="chips" style={{ marginBottom: 10 }}>{opts.today.map((t: any, i: number) => <Tag key={i} tone="accent">today: {t.name}</Tag>)}</div>
              )}
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
                        {!hideOdds && (
                          <div className="opt-odds" title={`utility ${o.utility}`}>
                            <div className="meter" style={{ height: 6, width: 90 }}><div className="meter-f" style={{ width: `${Math.max(2, o.prob * 100)}%`, background: "var(--accent-2)" }} /></div>
                            <span>{(o.prob * 100).toFixed(o.prob < 0.01 ? 1 : 0)}%</span>
                          </div>
                        )}
                        <button className="primary small" disabled={busy} onClick={(e) => { e.stopPropagation(); act(o.index, `${o.label}${o.target_name ? " · " + o.target_name : ""}`); }}>Choose</button>
                      </div>
                      {open === o.index && (
                        <div className="opt-why">
                          {o.terms ? <TermBars terms={o.terms} total={o.utility} /> :
                            <div className="dim small">The full term breakdown is recorded for the top options; this one scored {o.utility}.</div>}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ))}
              <div className="hint" style={{ marginTop: 10 }}>
                Percentages are how likely {c.first} is to pick each option on their own (softmax at temperature {opts.temperature}). Choosing an option never guarantees how it turns out.
              </div>
            </Panel>
            {log.length > 0 && (
              <Panel title="What happened" sub="Newest first. Each result is resolved by the same rules and randomness as everyone else's.">
                {log.map((l, i) => <Outcome key={i} l={l} first={c.first} />)}
              </Panel>
            )}
          </div>
          <div className="stack">
            <Panel title="How they're doing">
              <div className="meters">
                <Meter label="mood" value={opts.mood} color={moodColor(opts.mood)} right={fmt(opts.mood)} />
                {["energy", "social", "fun", "stress"].map((n) => <Meter key={n} label={n} value={opts.needs[n]} invert={n === "stress"} color={n === "stress" ? undefined : "var(--info)"} right={fmt(opts.needs[n])} />)}
              </div>
              <div className="hint" style={{ marginTop: 8 }}>${fmt(opts.money)} in their pocket</div>
            </Panel>
            <Panel title="What they're working toward">
              {opts.goals.length ? opts.goals.map((g: any) => (
                <div key={g.id} className="row between small" style={{ padding: "4px 0" }}><span>{g.label}</span><Tag tone="accent">{fmt(g.priority)}</Tag></div>
              )) : <Empty>No active goals.</Empty>}
            </Panel>
            <Panel title={`Meanwhile in ${PLACE.town}`} sub="Notable things that happened while the clock moved">
              <div className="evlist">{opts.skipped_events.length ? opts.skipped_events.slice().reverse().map((e: any) => <EventRow key={e.id} ev={e} compact />) : <Empty>Quiet.</Empty>}</div>
            </Panel>
          </div>
        </div>
      )}
    </div>
  );
}

function Outcome({ l, first }: any) {
  const [more, setMore] = useState(false);
  const mood = l.mood_after - l.mood_before;
  return (
    <div className="outcome">
      <div className="row between">
        <div><span className="hint">{l.when}</span> <b>{l.auto ? `${first} decided` : `You chose: ${l.choice}`}</b></div>
        <span className={mood >= 0 ? "pos" : "neg"}>mood {signed(mood)}</span>
      </div>
      <div className="evlist">{l.events.length ? l.events.map((e: any) => <EventRow key={e.id} ev={e} compact showDate={false} />) : <div className="dim small">Nothing recorded for them in that slot.</div>}</div>
      <button className="small ghost" onClick={() => setMore(!more)}>{more ? "Hide details" : "Show the dice and the changes"}</button>
      {more && l.events.map((e: any) => (
        <div key={e.id} style={{ marginTop: 8 }}>
          <Calc calc={e.calc} />
          {e.changes?.length > 0 && <Changes changes={e.changes.slice(0, 40)} />}
        </div>
      ))}
    </div>
  );
}
