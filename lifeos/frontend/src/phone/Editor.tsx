// The editor: change anyone, and anything between two people. On to start; switch it off on the Me tab.
// #/m/edit lists everyone; #/m/edit/<id> edits one person (and their relationships, in a sheet).
import React, { useEffect, useMemo, useState } from "react";
import { APT_LABEL, MOTIVE_WORDS, TRAIT_WORDS } from "../components/CharacterBuilder";
import { EdPair, EdPerson, EdPersonRow, EdRel, EdSchema, Look, phoneApi, pgo } from "./api";
import { Portrait } from "./art";
import LookPicker from "./art/LookPicker";
import { Field, Fold, Slider } from "./CreateStory";
import { AddSomeone, BodyFold, FlirtFold, NextFold, WhoFold } from "./EditorWho";
import { PIcon } from "./icons";
import { cx, errText, Sheet } from "./kit";
import { usePhone } from "./PhoneContext";
import "./create.css";

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const NEED_LABEL: Record<string, [string, string, string]> = {
  energy: ["Energy", "Wiped out", "Full tank"], social: ["Social", "Lonely", "Plenty of people time"],
  fun: ["Fun", "Bored", "Having a blast"], stress: ["Stress", "Calm", "Stressed out"],
};
const REL_ENDS: Record<string, [string, string]> = {
  affection: ["Can't stand them", "Inseparable"], attraction: ["Not at all", "Head over heels"], trust: ["None", "Completely"],
  respect: ["None", "Looks up to them"], rivalry: ["None", "Fierce"], familiarity: ["Strangers", "Know everything"],
};

let cache: { schema: EdSchema; people: EdPersonRow[] } | null = null;
async function loadAll(force = false) {
  if (!cache || force) cache = await phoneApi.editor();
  return cache;
}

function Head({ title, onBack, right }: { title: string; onBack: () => void; right?: React.ReactNode }) {
  return (
    <header className="ed-head">
      <button className="ed-back" onClick={onBack} aria-label="Back"><PIcon name="back" size={20} /></button>
      <b>{title}</b>
      <span>{right}</span>
    </header>
  );
}

export default function Editor({ route }: { route: string[] }) {
  const id = route[0];
  return <PersonEditor key={id} id={decodeURIComponent(id)} />;
}

// ------------------------------------------------------------------------------------------------ everyone

const FILTERS: [string, string][] = [["people", "Your people"], ["family", "Family"], ["grade", "Your grade"], ["all", "Everyone"]];

function PeopleList({ people, onPick, exclude }: { people: EdPersonRow[]; onPick: (p: EdPersonRow) => void; exclude?: string }) {
  const [q, setQ] = useState("");
  const [f, setF] = useState("people");
  const me = people.find((p) => p.me);
  const shown = people.filter((p) => {
    if (p.id === exclude) return false;
    if (q.trim()) return p.name.toLowerCase().includes(q.trim().toLowerCase());
    if (f === "people") return p.me || p.family || p.known;
    if (f === "family") return p.family;
    if (f === "grade") return p.grade === me?.grade && p.role === "student";
    return true;
  });
  return (
    <>
      <div className="ed-search"><input className="ph-input" placeholder="Search anyone by name" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      {!q.trim() && (
        <div className="ed-filters">
          {FILTERS.map(([k, l]) => (
            <button key={k} className={cx("ed-chip", f === k && "on")} onClick={() => setF(k)}>{l}</button>
          ))}
        </div>
      )}
      <div className="ed-list">
        {shown.slice(0, 160).map((p) => (
          <button key={p.id} className="ed-row" onClick={() => onPick(p)}>
            <Portrait look={p.look} size={44} color={p.color} name={p.first} />
            <span className="ed-row-m">
              <b>{p.name}{p.me ? " (you)" : ""}</b>
              <small>{p.year}{p.family && !p.me ? " · family" : ""}{p.label && !p.me ? ` · ${p.label}` : ""}</small>
            </span>
            <PIcon name="chevron" size={18} />
          </button>
        ))}
        {!shown.length && <div className="ph-dim ed-empty">Nobody here. Try Everyone, or search.</div>}
      </div>
    </>
  );
}

/** The Studio's People tab: add someone, edit yourself, everyone in your world. */
export function EditorPeople() {
  const { toast, state, refresh } = usePhone();
  const [all, setAll] = useState<{ schema: EdSchema; people: EdPersonRow[] } | null>(null);
  const [adding, setAdding] = useState(false);
  const on = !!(state?.control as any)?.editor;
  useEffect(() => {
    if (on) loadAll(true).then(setAll).catch((e) => toast(errText(e), "bad"));
  }, [on]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!on) {
    return (
      <div className="ph-card">
        <p className="ph-dim small" style={{ marginTop: 0 }}>The editor is off, so people can't be changed right now.</p>
        <button className="ph-btn primary block" onClick={async () => {
          try {
            await phoneApi.control({ editor: true });
            await refresh();
          } catch (e) {
            toast(errText(e), "bad");
          }
        }}>Turn the editor on</button>
      </div>
    );
  }
  const me = all?.people.find((x) => x.me);
  return (
    <>
      <p className="ed-intro">
        Who everyone is: look, body and sports, personality, what's next after high school, how they feel about each other. Or
        add someone. Edits are quiet (no texts, no news), and they come along when you start over.
      </p>
      <div className="ed-top2">
        <button className="ph-btn primary block" onClick={() => setAdding(true)}><PIcon name="plus" size={17} /> Add someone</button>
        {me && <button className="ph-btn soft block" onClick={() => pgo(`edit/${encodeURIComponent(me.id)}`)}>Edit me</button>}
      </div>
      {all ? <PeopleList people={all.people} onPick={(p) => pgo(`edit/${encodeURIComponent(p.id)}`)} /> : <div className="ed-load"><span className="ph-spinner" /></div>}
      <Sheet open={adding} onClose={() => setAdding(false)} title="Add someone" full>
        {adding && <AddSomeone onDone={() => { setAdding(false); cache = null; }} />}
      </Sheet>
    </>
  );
}

// ------------------------------------------------------------------------------------------------ one person

type Draft = Record<string, any>;

function setIn(d: Draft, layer: string, key: string | null, v: any): Draft {
  if (key === null) return { ...d, [layer]: v };
  return { ...d, [layer]: { ...(d[layer] || {}), [key]: v } };
}

function PersonEditor({ id }: { id: string }) {
  const { toast, refresh } = usePhone();
  const [p, setP] = useState<EdPerson | null>(null);
  const [schema, setSchema] = useState<EdSchema | null>(null);
  const [people, setPeople] = useState<EdPersonRow[]>([]);
  const [d, setD] = useState<Draft>({});
  const [busy, setBusy] = useState(false);
  const [pairWith, setPairWith] = useState<[string, string] | null>(null);  // [a, b]: how a feels about b first
  const [picking, setPicking] = useState(false);

  const load = async () => {
    try {
      const [all, one] = await Promise.all([loadAll(), phoneApi.editorPerson(id)]);
      setSchema(all.schema);
      setPeople(all.people);
      setP(one);
    } catch (e) {
      toast(errText(e), "bad");
    }
  };
  useEffect(() => {
    load();
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const val = (layer: string, key: string | null) => {
    if (key === null) return d[layer] !== undefined ? d[layer] : (p as any)?.[layer];
    return d[layer]?.[key] !== undefined ? d[layer][key] : ((p as any)?.[layer]?.[key] ?? 0);
  };
  const put = (layer: string, key: string | null, v: any) => setD((x) => setIn(x, layer, key, v));
  const changed = Object.keys(d).length > 0;
  const save = async () => {
    setBusy(true);
    try {
      const out = await phoneApi.editorSavePerson(id, d);
      setP(out);
      setD({});
      cache = null;
      toast("Saved", "good");
      refresh();
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(false);
    }
  };

  if (!p || !schema) return <div className="ed"><Head title="Editor" onBack={() => pgo("studio/people")} /><div className="ed-load"><span className="ph-spinner" /></div></div>;
  const me = people.find((x) => x.me);
  const look: Look = { ...p.look, ...(d.look || {}) } as Look;
  const who = p.is_me ? "you" : p.first;
  const slider = (layer: string, k: string, label: string, ends?: [string, string]) => (
    <Slider key={k} label={label} value={Number(val(layer, k))} onChange={(v) => put(layer, k, v)} left={ends?.[0]} rightWord={ends?.[1]} />
  );
  return (
    <div className="ed">
      <Head title={p.is_me ? "Edit you" : `Edit ${p.first}`} onBack={() => (window.history.length > 1 ? window.history.back() : pgo("studio/people"))}
        right={<button className="ed-all" onClick={() => pgo("studio/people")}>Everyone</button>} />
      <div className="ed-hero">
        <Portrait look={look} size={104} color={p.color} name={p.first} mood="happy" />
        <h2>{(d.first ?? p.first) + " " + (d.last ?? p.last)}</h2>
        <span>{p.year}{p.partner ? " · in a relationship" : ""}</span>
      </div>

      {!p.is_me && me && p.with_me && (
        <button className="ed-you" onClick={() => setPairWith([me.id, p.id])}>
          <span className="ed-you-l">
            <b>You and {p.first}</b>
            <small>You: {relLine(p.with_me.ab)} · {p.first}: {relLine(p.with_me.ba)}</small>
          </span>
          <span className="ed-pill">Edit</span>
        </button>
      )}

      <div className="ed-body">
        <Fold title="Name and bio" sub={`${d.first ?? p.first} ${d.last ?? p.last}`}>
          <Field label="First name"><input className="ph-input" value={val("first", null)} maxLength={40} onChange={(e) => put("first", null, e.target.value)} /></Field>
          <Field label="Last name"><input className="ph-input" value={val("last", null)} maxLength={40} onChange={(e) => put("last", null, e.target.value)} /></Field>
          <Field label="Bio"><textarea className="ph-input ed-bio" value={val("bio", null) || ""} maxLength={500} rows={3} onChange={(e) => put("bio", null, e.target.value)} /></Field>
        </Fold>
        <WhoFold p={p} val={val} put={put} />
        <Fold title="Look" sub={Object.keys(d.look || p.look_locked || {}).length ? "Set" : "Natural"}>
          <div className="cs-look">
            <LookPicker value={d.look ?? p.look_locked} base={p.look} onChange={(l) => put("look", null, l || {})} gender={p.gender} color={p.color}
              adult={p.role === "staff"} name={p.first} />
          </div>
        </Fold>
        <BodyFold p={p} val={val} put={put} />
        <Fold title="Personality" sub="What they're like">
          {schema.traits.map((k) => slider("traits", k, cap(k), TRAIT_WORDS[k] ? [cap(TRAIT_WORDS[k][1]), cap(TRAIT_WORDS[k][0])] : undefined))}
        </Fold>
        {!p.is_me && !p.staff && <FlirtFold p={p} val={val} put={put} />}
        <Fold title="Talents" sub="What comes naturally">
          {schema.aptitudes.map((k) => slider("aptitudes", k, APT_LABEL[k] || cap(k)))}
        </Fold>
        <Fold title="What drives them" sub="What they want most">
          {schema.motives.map((k) => slider("motives", k, cap(MOTIVE_WORDS[k] || k)))}
        </Fold>
        <Fold title="Skills" sub="How good they are">
          {schema.skills.map((s) => slider("skills", s.id, s.label))}
        </Fold>
        <Fold title="Interests" sub="How into things they are">
          {[...schema.interests].sort((a, b) => (Number(p.interests[b.id] || 0) - Number(p.interests[a.id] || 0))).map((s) => slider("interests", s.id, s.label))}
        </Fold>
        <NextFold p={p} val={val} put={put} />
        <Fold title="Right now" sub="Mood, energy, stress, money">
          <Slider label="Mood" value={Number(val("mood", null))} onChange={(v) => put("mood", null, v)} left="Miserable" rightWord="Great" />
          {schema.needs.map((k) => {
            const [l, lo, hi] = NEED_LABEL[k] || [cap(k), "", ""];
            return slider("needs", k, l, [lo, hi]);
          })}
          <Slider label="Popularity" value={Number(val("popularity", null))} onChange={(v) => put("popularity", null, v)} left="Unknown" rightWord="Everyone knows them" />
          {p.student && (
            <Slider label="GPA" value={Math.round(Number(val("gpa", null)) * 100)} min={0} max={400} show={(Number(val("gpa", null))).toFixed(2)}
              onChange={(v) => put("gpa", null, v / 100)} />
          )}
          <Field label="Money">
            <input className="ph-input" type="number" inputMode="decimal" min={0} max={100000} value={val("money", null)}
              onChange={(e) => put("money", null, e.target.value === "" ? 0 : Number(e.target.value))} />
          </Field>
        </Fold>

        <div className="ph-section-t">{p.is_me ? "Your people" : `${p.first}'s people`}</div>
        <p className="ph-dim small ph-tight">Tap anyone to set how {who === "you" ? "you feel about each other" : `${p.first} and they feel about each other`}.</p>
        <div className="ed-list">
          {p.rels.map((r) => (
            <button key={r.id} className="ed-row" onClick={() => setPairWith([p.id, r.id])}>
              <Portrait look={r.look} size={40} color={r.color} name={r.first} />
              <span className="ed-row-m">
                <b>{r.name}</b>
                <small>{r.roles.includes("partner") ? "dating · " : r.roles.includes("sibling") ? "sibling · " : ""}{relLine(r.ab)}{r.ba ? ` / ${relLine(r.ba)}` : ""}</small>
              </span>
              <PIcon name="chevron" size={18} />
            </button>
          ))}
          <button className="ed-row ed-add" onClick={() => setPicking(true)}>
            <span className="ed-plus"><PIcon name="plus" size={20} /></span>
            <span className="ed-row-m"><b>Someone else…</b><small>Anyone in your world</small></span>
          </button>
        </div>
        <div style={{ height: changed ? 96 : 28 }} />
      </div>

      {changed && (
        <div className="ed-save">
          <button className="ph-btn" onClick={() => setD({})} disabled={busy}>Undo</button>
          <button className="ph-btn primary" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save changes"}</button>
        </div>
      )}

      <Sheet open={picking} onClose={() => setPicking(false)} title={`${p.is_me ? "You" : p.first} and…`} full>
        {picking && <PeopleList people={people} exclude={p.id} onPick={(x) => { setPicking(false); setPairWith([p.id, x.id]); }} />}
      </Sheet>
      <Sheet open={!!pairWith} onClose={() => setPairWith(null)} full title="How they feel">
        {pairWith && <PairEditor a={pairWith[0]} b={pairWith[1]} schema={schema} onSaved={() => { cache = null; load(); refresh(); }} />}
      </Sheet>
    </div>
  );
}

function relLine(r: EdRel | null) {
  if (!r) return "strangers";
  return r.label + (r.crush ? " · crush" : "");
}

// ------------------------------------------------------------------------------------------------ two people

function PairEditor({ a, b, schema, onSaved }: { a: string; b: string; schema: EdSchema; onSaved: () => void }) {
  const { toast } = usePhone();
  const [pr, setPr] = useState<EdPair | null>(null);
  const [d, setD] = useState<{ ab: Record<string, number>; ba: Record<string, number> }>({ ab: {}, ba: {} });
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    phoneApi.editorPair(a, b).then(setPr).catch((e) => toast(errText(e), "bad"));
  }, [a, b]); // eslint-disable-line react-hooks/exhaustive-deps
  const send = async (body: any, msg: string) => {
    setBusy(true);
    try {
      setPr(await phoneApi.editorSavePair(a, b, body));
      setD({ ab: {}, ba: {} });
      toast(msg, "good");
      onSaved();
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(false);
    }
  };
  if (!pr) return <div className="ed-load"><span className="ph-spinner" /></div>;
  const changed = Object.keys(d.ab).length + Object.keys(d.ba).length > 0;
  const side = (key: "ab" | "ba", from: string, to: string) => {
    const r = pr[key];
    return (
      <div className="ed-side">
        <div className="ed-side-h">
          <b>How {from} feels about {to}</b>
          <span>{relLine(r)}</span>
        </div>
        {schema.rel_fields.map((f) => (
          <Slider key={f.id} label={f.label} min={f.min} max={f.max}
            value={d[key][f.id] ?? (r ? Number((r as any)[f.id]) : f.id === "trust" ? 30 : 0)}
            onChange={(v) => setD((x) => ({ ...x, [key]: { ...x[key], [f.id]: v } }))}
            left={REL_ENDS[f.id]?.[0]} rightWord={REL_ENDS[f.id]?.[1]} />
        ))}
      </div>
    );
  };
  const aName = pr.a.first;
  const bName = pr.b.first;
  return (
    <div className="ed-pair">
      <div className="ed-pair-top">
        <span><Portrait look={pr.a.look} size={58} color={pr.a.color} name={pr.a.first} /><b>{aName}</b></span>
        <span className={cx("ed-pair-mid", pr.dating && "dating")}>{pr.dating ? "Dating" : "&"}</span>
        <span><Portrait look={pr.b.look} size={58} color={pr.b.color} name={pr.b.first} /><b>{bName}</b></span>
      </div>
      <div className="ph-section-t">Quick set</div>
      <div className="ed-presets">
        {pr.presets.map((x) => (
          <button key={x.id} className={cx("ed-chip", x.id === "dating" && pr.dating && "on")} disabled={busy}
            onClick={() => send({ preset: x.id }, x.label)}>{x.label}</button>
        ))}
      </div>
      <p className="ph-dim small ph-tight">Dating is real: it ends whoever they were with before. Attraction past {schema.crush_at} is a crush.</p>
      {side("ab", aName, bName)}
      {side("ba", bName, aName)}
      <div style={{ height: changed ? 80 : 12 }} />
      {changed && (
        <div className="ed-save in-sheet">
          <button className="ph-btn" onClick={() => setD({ ab: {}, ba: {} })} disabled={busy}>Undo</button>
          <button className="ph-btn primary" onClick={() => send(d, "Saved")} disabled={busy}>{busy ? "Saving…" : "Save"}</button>
        </div>
      )}
    </div>
  );
}

/** The Me tab card: open the editor (only shown while it's on). */
export function EditorCard() {
  return (
    <div className="ph-card ed-card">
      <div className="ed-card-t"><PIcon name="wand" size={20} /> <b>Editor</b></div>
      <p className="ph-dim small">Change anyone's personality, talents, look and mood, and set who likes who. Quiet: no texts, no news.</p>
      <div className="ed-card-b">
        <button className="ph-btn primary" onClick={() => pgo("studio/people")}>Edit anyone</button>
        <EditMeButton />
      </div>
    </div>
  );
}

function EditMeButton() {
  const { state } = usePhone();
  const id = state?.me?.id;
  return id ? <button className="ph-btn" onClick={() => pgo(`edit/${encodeURIComponent(id)}`)}>Edit me</button> : null;
}

/** First days of a story: a nudge to set the world up the way you want it. */
export function SetupNudge() {
  const { state } = usePhone();
  const key = `lifeos.editorNudge.${state?.title || ""}`;
  const [hidden, setHidden] = useState(() => {
    try {
      return localStorage.getItem(key) === "1";
    } catch {
      return false;
    }
  });
  const show = useMemo(() => !!state && !!(state.control as any).editor && state.progress.day <= 7 && !hidden, [state, hidden]);
  if (!show) return null;
  const hide = () => {
    setHidden(true);
    try {
      localStorage.setItem(key, "1");
    } catch {
      /* fine */
    }
  };
  return (
    <div className="ph-card ed-nudge">
      <div className="ed-card-t"><PIcon name="wand" size={20} /> <b>Set your world up</b></div>
      <p className="ph-dim small">Before it gets going: change anyone's personality or look, and set who's friends, who has a crush, who's dating.</p>
      <div className="ed-card-b">
        <button className="ph-btn primary" onClick={() => pgo("studio/people")}>Open the editor</button>
        <button className="ph-btn" onClick={hide}>Not now</button>
      </div>
    </div>
  );
}
