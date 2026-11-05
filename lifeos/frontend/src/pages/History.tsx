// History Explorer: browse every recorded event, walk causal chains, and inspect decision traces.
import React, { useEffect, useMemo, useState } from "react";
import { EventLite, qs } from "../api";
import { go, useApi, useStore } from "../store";
import {
  Avatar, Calc, Changes, cx, Empty, ErrorBox, EventRow, Icon, Loading, Meter, Name, Pager, Panel, pretty, signed, Stat, Tag,
  TermBars, typeMeta,
} from "../ui";
import "./history.css";

const PAGE = 60;
const SLOT_LABEL: Record<string, string> = {
  dawn: "morning", classes: "classes", lunch: "lunch", after_school: "after school", day: "daytime", evening: "evening", night: "night",
};

export default function History({ route }: { route: string[] }) {
  if (route[1] === "event" && route[2]) return <EventDetail id={route[2]} />;
  if (route[1] === "trace" && route[2]) return <TracePage id={route[2]} />;
  return <Explorer initialChar={route[1] === "char" ? route[2] : undefined} />;
}

// ---------------------------------------------------------------- explorer

function Explorer({ initialChar }: { initialChar?: string }) {
  const { charList, world } = useStore();
  const [char, setChar] = useState(initialChar || "");
  const [type, setType] = useState("");
  const [minImp, setMinImp] = useState(0);
  const [dayFrom, setDayFrom] = useState("");
  const [dayTo, setDayTo] = useState("");
  const [q, setQ] = useState("");
  const [qLive, setQLive] = useState("");
  const [offset, setOffset] = useState(0);

  useEffect(() => setChar(initialChar || ""), [initialChar]);
  useEffect(() => {
    const t = setTimeout(() => setQ(qLive.trim()), 300);
    return () => clearTimeout(t);
  }, [qLive]);
  useEffect(() => setOffset(0), [char, type, minImp, dayFrom, dayTo, q]);

  const path = "/api/events" + qs({
    char, type, q, min_importance: minImp || undefined, limit: PAGE, offset,
    day_from: dayFrom === "" ? undefined : dayFrom, day_to: dayTo === "" ? undefined : dayTo,
  });
  const { data, loading, error } = useApi<any>(path, [path]);

  const people = useMemo(
    () => [...charList].sort((a, b) => (a.role === b.role ? a.name.localeCompare(b.name) : a.role === "student" ? -1 : 1)),
    [charList]
  );
  const anyFilter = char || type || minImp || dayFrom !== "" || dayTo !== "" || q;
  const reset = () => {
    setChar(""); setType(""); setMinImp(0); setDayFrom(""); setDayTo(""); setQLive(""); setQ("");
    if (initialChar) go("history");
  };

  return (
    <div>
      <div className="page-h">
        <div>
          <h1>History Explorer</h1>
          <p>Every event the simulation recorded, newest first. Open one to see the calculation behind it, the exact state changes it made,
            what caused it, what it led to, and the decision that started it.</p>
        </div>
        <a className="dl" href="/api/export/events.csv" download>
          <button><Icon name="link" size={14} /> Download events (CSV)</button>
        </a>
      </div>

      <Panel>
        <div className="hx-filters">
          <label>
            <span>Character</span>
            <select value={char} onChange={(e) => setChar(e.target.value)}>
              <option value="">Everyone</option>
              {people.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}{c.grade ? ` (grade ${c.grade})` : c.role !== "student" ? ` (${c.role})` : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Event type</span>
            <select value={type} onChange={(e) => setType(e.target.value)}>
              <option value="">All types</option>
              {(data?.types || []).map((t: string) => <option key={t} value={t}>{typeMeta(t)[0]} ({t})</option>)}
            </select>
          </label>
          <label>
            <span>Importance</span>
            <select value={minImp} onChange={(e) => setMinImp(parseFloat(e.target.value))}>
              <option value={0}>All</option>
              <option value={10}>10+ (notable)</option>
              <option value={20}>20+ (significant)</option>
              <option value={35}>35+ (major)</option>
            </select>
          </label>
          <label className="narrow">
            <span>From day</span>
            <input type="number" min={0} max={world?.day} value={dayFrom} placeholder="0" onChange={(e) => setDayFrom(e.target.value)} />
          </label>
          <label className="narrow">
            <span>To day</span>
            <input type="number" min={0} max={world?.day} value={dayTo} placeholder={String(world?.day ?? "")} onChange={(e) => setDayTo(e.target.value)} />
          </label>
          <label className="grow">
            <span>Search text</span>
            <input type="search" value={qLive} placeholder="e.g. tryouts, party, Priya" onChange={(e) => setQLive(e.target.value)} />
          </label>
          {anyFilter && <button className="ghost small" onClick={reset}>Clear filters</button>}
        </div>
      </Panel>

      <div className="hx-summary">
        {data && (
          <>
            <span><b>{data.total.toLocaleString()}</b> matching events{char && <> involving <Name id={char} /></>}</span>
            {world && <span className="dim">Today is day {world.day} ({world.date}).</span>}
            {data.folded_total > 0 && (
              <span className="dim" title="History retention folds old low-importance events into per-character counters">
                {data.folded_total.toLocaleString()} older routine events were folded into counters by history retention.
              </span>
            )}
          </>
        )}
      </div>

      {char && data?.folded && Object.keys(data.folded).length > 0 && <Folded folded={data.folded} />}

      <Panel pad>
        <ErrorBox error={error} />
        {loading && !data && <Loading what="Reading history" />}
        {data && !data.items.length && <Empty>No events match these filters.</Empty>}
        {data && data.items.length > 0 && (
          <div className="evlist">
            {data.items.map((ev: EventLite) => <EventRow key={ev.id} ev={ev} />)}
          </div>
        )}
        {data && <Pager total={data.total} offset={offset} limit={PAGE} onChange={setOffset} />}
      </Panel>
    </div>
  );
}

function Folded({ folded }: { folded: Record<string, number> }) {
  const rows = Object.entries(folded).sort((a, b) => b[1] - a[1]);
  return (
    <div className="callout hx-folded">
      <b>Folded routine events for this person: </b>
      {rows.map(([t, n]) => <span key={t} className="tag">{pretty(t)} x{n}</span>)}
    </div>
  );
}

// ---------------------------------------------------------------- event detail

function EventDetail({ id }: { id: string }) {
  const { data: ev, error, loading } = useApi<any>(`/api/events/${id}`, [id]);
  if (error) return <div><Back /><ErrorBox error={error} /></div>;
  if (loading || !ev) return <Loading what="Opening event" />;
  const [label, tone] = typeMeta(ev.type);
  const people: string[] = Array.from(new Set<string>([...(ev.actors || []), ...(ev.targets || []), ...(ev.involved || [])]));
  const memories: [string, string][] = ev.memories || [];
  const traces: [string, number][] = Object.entries(ev.traces || {}) as any;
  const dataRows = Object.entries(ev.data || {}).filter(([k, v]) => v !== null && v !== undefined && typeof v !== "object" && k !== "action");

  return (
    <div className="hx-detail">
      <Back />
      <div className="hx-headline panel">
        <div className="panel-b">
          <div className="row">
            <Tag tone={tone}>{label}</Tag>
            {ev.outcome && <Tag>{pretty(ev.outcome)}</Tag>}
            {ev.data?.player && <Tag tone="warn">player choice</Tag>}
            {ev.data?.fallback && <Tag tone="info">plan B</Tag>}
            <span className="dim">event #{ev.id}</span>
          </div>
          <h2 className="hx-text">{ev.text}</h2>
          <div className="stats hx-stats">
            <Stat label="Date" value={<span className="hx-small-v">{ev.date}</span>} sub={`day ${ev.day}`} />
            <Stat label="When" value={<span className="hx-small-v">{SLOT_LABEL[ev.slot] || ev.slot || "-"}</span>} />
            <Stat label="Type" value={<span className="hx-small-v">{ev.type}</span>} sub={ev.outcome || ""} />
            <Stat label="Importance" value={ev.importance} sub={importanceWord(ev.importance)} />
            <Stat label="State changes" value={(ev.changes || []).length} />
          </div>
        </div>
      </div>

      <div className="grid g-main">
        <div className="stack">
          {ev.calc && ev.calc.length > 0 && (
            <Panel title="How the outcome was decided" sub="Every factor, probability and random roll the engine used, as recorded at the time.">
              <Calc calc={ev.calc} />
            </Panel>
          )}
          <Panel title="What changed" sub="The state changes this event actually applied (before and after values, with the reason).">
            <div className="scroll">
              <Changes changes={ev.changes || []} />
            </div>
          </Panel>
          {ev.trace_obj && (
            <Panel title="The decision behind it" sub={<>Decision trace #{ev.trace_obj.id} · <a href={`#/history/trace/${ev.trace_obj.id}`}>open on its own page</a></>}>
              <TraceInspector tr={ev.trace_obj} embedded />
            </Panel>
          )}
          {ev.trace_missing && (
            <div className="callout warn">
              This event came from a routine decision whose trace has since been dropped by history retention. Important decisions keep their
              traces permanently; routine ones are kept for a window you can change in <a href="#/workshop">Engine Workshop</a> under History retention.
            </div>
          )}
        </div>

        <div className="stack">
          <Panel title="People involved">
            {people.length === 0 && <Empty>Nobody specific (a world-level event).</Empty>}
            <div className="hx-people">
              {people.map((p) => (
                <div key={p} className="hx-person">
                  <Avatar id={p} size={30} />
                  <div>
                    <Name id={p} full />
                    <div className="hint">
                      {(ev.actors || []).includes(p) ? "actor" : (ev.targets || []).includes(p) ? "target" : "involved"}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Caused by" sub="Earlier events this one is linked to.">
            {ev.cause_events && ev.cause_events.length ? (
              <div className="evlist">{ev.cause_events.map((e: EventLite) => <EventRow key={e.id} ev={e} compact />)}</div>
            ) : (
              <Empty>No recorded cause. It came from someone's own decision or the calendar.</Empty>
            )}
          </Panel>

          <Panel title="Led to" sub="Later events that cite this one as a cause.">
            {ev.consequences && ev.consequences.length ? (
              <div className="evlist">{ev.consequences.map((e: EventLite) => <EventRow key={e.id} ev={e} compact />)}</div>
            ) : (
              <Empty>No recorded consequences yet.</Empty>
            )}
          </Panel>

          {traces.length > 0 && (
            <Panel title="Decisions that fed into this" sub="Everyone whose choice put them here (for group events like practices, parties and lunch tables).">
              <div className="hx-tracelinks">
                {traces.map(([cid, tid]) => (
                  <a key={cid} href={`#/history/trace/${tid}`} className="hx-tracelink">
                    <Avatar id={cid} size={22} ring={false} onClick={() => go(`history/trace/${tid}`)} />
                    <Name id={cid} plain />
                    <span className="hint">trace #{tid}</span>
                  </a>
                ))}
              </div>
            </Panel>
          )}

          {memories.length > 0 && (
            <Panel title="Memories formed" sub="Memories persist and influence future choices toward the people involved.">
              <div className="hx-mems">
                {memories.map(([cid, mid]) => (
                  <div key={cid + mid} className="row">
                    <Name id={cid} />
                    <span className="mono dim">{mid}</span>
                    <a className="hint" href={`#/characters/${cid}`}>see their memories</a>
                  </div>
                ))}
              </div>
            </Panel>
          )}

          {dataRows.length > 0 && (
            <Panel title="Recorded details">
              <dl className="kv">
                {dataRows.map(([k, v]) => (
                  <React.Fragment key={k}>
                    <dt>{pretty(k)}</dt>
                    <dd>{String(v)}</dd>
                  </React.Fragment>
                ))}
              </dl>
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}

function importanceWord(v: number) {
  return v >= 40 ? "major" : v >= 25 ? "significant" : v >= 12 ? "notable" : "routine";
}

function Back() {
  return (
    <div className="hx-back">
      <button className="ghost small" onClick={() => (window.history.length > 1 ? window.history.back() : go("history"))}>Back</button>
      <a href="#/history" className="hint">History Explorer</a>
    </div>
  );
}

// ---------------------------------------------------------------- trace inspector

function TracePage({ id }: { id: string }) {
  const { data: tr, error, loading } = useApi<any>(`/api/traces/${id}`, [id]);
  if (error) return <div><Back /><ErrorBox error={error} /></div>;
  if (loading || !tr) return <Loading what="Opening decision trace" />;
  return (
    <div className="hx-detail">
      <Back />
      <div className="page-h">
        <div>
          <h1>Decision trace #{tr.id}</h1>
          <p>Exactly how this choice was computed: which options were available and why, the weighted terms behind each one,
            the probabilities, and the random roll that picked one.</p>
        </div>
      </div>
      <Panel>
        <TraceInspector tr={tr} />
      </Panel>
      {tr.event_obj && (
        <Panel title="What happened as a result" className="hx-gap">
          <EventRow ev={tr.event_obj} />
        </Panel>
      )}
    </div>
  );
}

function candName(row: any, chars: Record<string, any>) {
  if (row.target_name) return row.target_name;
  if (row.target && chars[row.target]) return chars[row.target].name;
  return row.target ? pretty(String(row.target)) : "";
}

function summarize(row: any) {
  if (!row?.terms) return null;
  const terms: [string, number, string?][] = row.terms;
  const pushes = terms.filter((t) => t[1] > 0.05 && !t[0].startsWith("base appeal")).sort((a, b) => b[1] - a[1]).slice(0, 3);
  const pulls = terms.filter((t) => t[1] < -0.05).sort((a, b) => a[1] - b[1]).slice(0, 3);
  return { pushes, pulls };
}

export function TraceInspector({ tr, embedded }: { tr: any; embedded?: boolean }) {
  const { chars } = useStore();
  const rows: any[] = tr.candidates || [];
  const chosenIdx = Math.max(0, rows.findIndex((r) => r.chosen));
  const chosen = rows[chosenIdx];
  const [sel, setSel] = useState<number>(chosenIdx);
  useEffect(() => setSel(chosenIdx), [tr.id, chosenIdx]);
  const top = rows[0];
  const maxP = Math.max(0.0001, ...rows.map((r) => r.prob));
  const s = summarize(chosen);
  const selRow = rows[sel];
  const actionName = (r: any) => r?.label || pretty(r?.action || "");
  const rank = chosenIdx + 1;

  return (
    <div className="tr">
      <div className="tr-head">
        <Avatar id={tr.char} size={embedded ? 34 : 44} />
        <div>
          <div className="tr-who"><Name id={tr.char} full /> <span className="dim">decided during {SLOT_LABEL[tr.slot] || tr.slot} on {tr.date}</span></div>
          <div className="row tr-tags">
            {tr.player_choice ? <Tag tone="warn">chosen by the player</Tag> : <Tag tone="accent">autonomous</Tag>}
            {tr.cancelled && <Tag tone="info">plan dropped: {tr.cancelled}</Tag>}
            <Tag>{tr.n} options</Tag>
            <Tag title="Softmax temperature: higher means noisier choices">temperature {Number(tr.temperature).toFixed(2)}</Tag>
            <Tag title="The uniform random number that picked the option">random roll {Number(tr.roll).toFixed(4)}</Tag>
            {tr.rules_version && <Tag title="Rule set in effect">rules {tr.rules_version}</Tag>}
          </div>
        </div>
      </div>

      <div className="callout tr-summary">
        {tr.player_choice ? (
          <>
            The player picked <b>{actionName(chosen)}{candName(chosen, chars) ? ` (${candName(chosen, chars)})` : ""}</b>. On their own,{" "}
            <Name id={tr.char} /> would have chosen this {(chosen.prob * 100).toFixed(1)}% of the time; their most likely option was{" "}
            <b>{actionName(top)}{candName(top, chars) ? ` (${candName(top, chars)})` : ""}</b> at {(top.prob * 100).toFixed(1)}%.
          </>
        ) : (
          <>
            Chose <b>{actionName(chosen)}{candName(chosen, chars) ? ` (${candName(chosen, chars)})` : ""}</b>, which had a{" "}
            <b>{(chosen.prob * 100).toFixed(1)}%</b> chance{rank === 1 ? ", the most likely option" : `, ranked #${rank} of ${tr.n} by utility`}.
            Each option owns a share of the range 0 to 1 equal to its probability; the random roll was {Number(tr.roll).toFixed(3)}.
          </>
        )}
        {s && (s.pushes.length > 0 || s.pulls.length > 0) && (
          <div className="tr-why">
            {s.pushes.length > 0 && <>Biggest pushes: {s.pushes.map((t, i) => <span key={i}>{i > 0 && ", "}{t[0]} <b className="pos">{signed(t[1])}</b></span>)}. </>}
            {s.pulls.length > 0 && <>Biggest pulls: {s.pulls.map((t, i) => <span key={i}>{i > 0 && ", "}{t[0]} <b className="neg">{signed(t[1])}</b></span>)}.</>}
          </div>
        )}
        {(tr.event || tr.event_obj) && (
          <div className="tr-why"><a href={`#/history/event/${tr.event || tr.event_obj?.id}`}>See what happened (event #{tr.event || tr.event_obj?.id})</a></div>
        )}
      </div>

      <div className={cx("tr-body", embedded && "embedded")}>
        <div className="tr-cands">
          <table className="mini">
            <thead>
              <tr><th>#</th><th>option</th><th>target</th><th className="num">utility</th><th>probability</th></tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className={cx(r.terms && "click", i === sel && "sel", r.chosen && "tr-chosen")}
                  onClick={() => r.terms && setSel(i)} title={r.why}>
                  <td className="dim">{i + 1}</td>
                  <td>
                    {actionName(r)}
                    {r.chosen && <Tag tone="good">chosen</Tag>}
                    <div className="hint tr-whyrow">{r.why}</div>
                  </td>
                  <td>{r.target && chars[r.target] ? <Name id={r.target} /> : <span className="muted">{candName(r, chars)}</span>}</td>
                  <td className="num">{Number(r.utility).toFixed(1)}</td>
                  <td className="tr-p">
                    <Meter value={r.prob} max={maxP} color={r.chosen ? "var(--good)" : "var(--accent-2)"} right={`${(r.prob * 100).toFixed(1)}%`} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="hint tr-note">The top options (and the chosen one) keep a full term breakdown; click a row with one to inspect it.</div>
        </div>
        <div className="tr-terms">
          {selRow?.terms ? (
            <>
              <div className="tr-terms-h">
                <b>{actionName(selRow)}</b>{candName(selRow, chars) && <> → {candName(selRow, chars)}</>}
                <div className="hint">Why it was available: {selRow.why}</div>
              </div>
              <TermBars terms={selRow.terms} total={selRow.utility} />
            </>
          ) : (
            <Empty>No term breakdown was kept for this option.</Empty>
          )}
        </div>
      </div>

      {tr.weights && Object.keys(tr.weights).length > 0 && (
        <details className="tr-weights">
          <summary>Global weights in effect ({Object.keys(tr.weights).length})</summary>
          <div className="chips">
            {Object.entries(tr.weights).map(([k, v]: any) => (
              <span key={k} className={cx("tag", typeof v === "number" && v !== 1 && !k.endsWith("shortlist_size") && !k.endsWith("temperature") && "tag-warn")}>
                {k} = {typeof v === "number" ? v : String(v)}
              </span>
            ))}
          </div>
          <div className="hint">Edit these in the <a href="#/workshop">Engine Workshop</a>. Highlighted values differ from 1.</div>
        </details>
      )}
    </div>
  );
}
