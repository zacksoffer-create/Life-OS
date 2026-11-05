// Make your story on the phone: you, your look, who you are, your sports, your family, your people, then start.
// Same story spec as the lab's wizard (story/draft.ts), laid out for a thumb.
import React, { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import {
  APTS, APT_LABEL, ARCH_BLURB, BUILD_HINT, COLORS, GRADE_LABEL, MOTIVES, MOTIVE_WORDS, Person, SEASON, TEAMS, TRAITS, TRAIT_WORDS, sportsFor,
  archLabel, autoSkill, cap, displayName, heightLabel, lookOf, positionFit, randomLast, randomName, randomizePerson, shown, summaryLine,
  useStoryCatalog,
} from "../components/CharacterBuilder";
import { useStore } from "../store";
import { Draft, Problem, TEMPLATES, buildSpec, defaultDraft, familyLast, loadDraft, parseErrors, saveDraft, specToDraft } from "../story/draft";
import { Groundwork, Look, phoneApi, pgo } from "./api";
import { PetArt, Portrait } from "./art";
import LookPicker from "./art/LookPicker";
import { PIcon } from "./icons";
import { cx, errText, Sheet } from "./kit";
import { usePhone } from "./PhoneContext";
import { pickFile } from "./StoryFiles";
import "./create.css";

const KEY = "lifeos.phoneDraft.v1";
const STEPS: [string, string, string][] = [
  ["you", "You", "Start with the basics. Everything else can be left to chance."],
  ["look", "Your look", "Pick anything to lock it in, or leave it on auto."],
  ["type", "Who you are", "Your type sets the starting point. The sliders fine-tune it."],
  ["sports", "Sports", "What you play, where you play, and how good you are on day one."],
  ["family", "Your family", "Who you live with. Siblings are full people with their own lives."],
  ["people", "Your people", "Friends, a crush, a rival, a coach. Everyone else gets generated."],
  ["start", "Ready", "Look it over, then start freshman year."],
];
const INCOME: [string, string][] = [["low", "Tight budget"], ["middle", "Comfortable"], ["high", "Well-off"]];
const GENDERS: [string, string][] = [["m", "Guy"], ["f", "Girl"], ["nb", "Nonbinary"]];
const GRADES: [number, string][] = [[9, "Freshman"], [10, "Sophomore"], [11, "Junior"], [12, "Senior"]];
// younger kids you make: still in middle school, they start high school with a later freshman class
const LATER: [number, string][] = [[8, "Next year"], [7, "In 2 years"], [6, "In 3 years"]];
const YEAR_OF = ["freshman", "sophomore", "junior", "senior"];
function startsLine(g: number, myGrade: number, school: string) {
  const n = 9 - g;
  const you = myGrade + n <= 12 ? `your ${YEAR_OF[myGrade + n - 9]} year` : "after you graduate";
  return `In ${g}th grade now. Starts at ${school} as a freshman ${n === 1 ? "next fall" : `in ${n} years`}, ${you}.`;
}
function GradePick({ p, set, myGrade, cat, twin }: { p: Person; set: (x: Partial<Person>) => void; myGrade: number; cat: any; twin?: boolean }) {
  const g = p.grade || 9;
  return (
    <>
      <Field label="Grade" hint={twin ? "Twins share a grade." : undefined}>
        <Seg value={g} options={GRADES.map(([x, l]) => [x, x === myGrade ? `${l} (you)` : l] as [number, string])} onChange={(v) => set({ grade: v })} />
      </Field>
      <Field label="Or starts high school later" hint={g < 9 ? startsLine(g, myGrade, cat.school?.short || "school") : "Younger? They show up with that year's freshman class."}>
        <Seg value={g} options={LATER} onChange={(v) => set({ grade: v })} />
      </Field>
    </>
  );
}
const gradeWord = (g?: number) => (g && g < 9 ? `${GRADE_LABEL[g]} · starts ${g === 8 ? "next year" : `in ${9 - g} years`}` : GRADE_LABEL[g || 9]);
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTH_DAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
// relationships are stored from THEIR point of view ("crush" = they have a crush on you)
const REL_TO_YOU: [string, string][] = [
  ["best_friend", "Your best friend"], ["close_friend", "A close friend"], ["friend", "A friend"], ["acquaintance", "Someone you kind of know"],
  ["admirer", "You have a crush on them"], ["crush", "They have a crush on you"], ["mutual_crush", "You like each other"], ["dating", "You're dating"],
  ["ex", "Your ex"], ["rival", "Your rival"], ["enemy", "You can't stand each other"], ["teammate", "Grew up on teams together"],
  ["neighbor", "Your neighbor"], ["mentor", "They look up to you"],
];
const relLabel = (t?: string) => REL_TO_YOU.find(([k]) => k === t)?.[1] || "Someone in town";
const clamp = (x: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, x));

function closeness(v: number) {
  if (v <= -25) return "Constant fights";
  if (v < -5) return "Get on each other's nerves";
  if (v < 8) return "Normal siblings";
  if (v < 25) return "Pretty close";
  return "Super close";
}
function warmth(v: number) {
  if (v <= -25) return "Much colder than usual";
  if (v < -5) return "A little cooler";
  if (v < 8) return "Like you'd expect";
  if (v < 25) return "A little closer";
  return "Even closer than that";
}
function sibWord(p: Person) {
  return p.gender === "f" ? "sister" : p.gender === "m" ? "brother" : "sibling";
}
function attractionOf(p: Person): string {
  const a = [...(p.attracted_to || [])].sort().join(",");
  if (!a) return "auto";
  if (a === "f") return "f";
  if (a === "m") return "m";
  return "both";
}
function playsSport(p: Person, s: string) {
  if (p.positions?.[s]) return "yes";
  const iv = p.interests?.[s];
  if (iv === undefined) return "auto";
  return iv >= 40 ? "yes" : "no";
}
/** How a sibling on auto shows here: their own features, with the family's skin, hair color and eyes (from you). */
function sibLook(s: Person, me: Person): Look {
  const fam = lookOf(me);
  const own = s.look || {};
  return { ...lookOf(s), skin: own.skin ?? fam.skin, hair_color: own.hair_color ?? fam.hair_color, eyes: own.eyes ?? fam.eyes };
}
function withSport(p: Person, sport?: string | null): Partial<Person> {
  if (!sport) return {};
  return { interests: { ...(p.interests || {}), [sport]: Math.max(p.interests?.[sport] ?? 0, 80) } };
}
function playsList(p: Person) {
  return sportsFor(p.gender).filter((s) => playsSport(p, s) === "yes");
}

// ---------------------------------------------------------------- small pieces
export function Seg<T extends string | number>({ value, options, onChange, wrap }: { value: T | undefined; options: [T, React.ReactNode][]; onChange: (v: T) => void; wrap?: boolean }) {
  return (
    <div className={cx("ph-seg", "cs-seg", wrap && "wrap")}>
      {options.map(([v, l]) => (
        <button key={String(v)} type="button" className={cx(v === value && "on")} onClick={() => onChange(v)}>{l}</button>
      ))}
    </div>
  );
}

export function Field({ label, hint, children, right }: { label: React.ReactNode; hint?: React.ReactNode; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="cs-field">
      <div className="cs-field-l">
        <span>{label}</span>
        {right}
      </div>
      {children}
      {hint && <div className="cs-hint">{hint}</div>}
    </div>
  );
}

export function Slider({ label, value, auto, min = 0, max = 100, onChange, onAuto, left, rightWord, show }: {
  label: React.ReactNode; value: number; auto?: boolean; min?: number; max?: number; onChange: (v: number) => void; onAuto?: () => void;
  left?: string; rightWord?: string; show?: React.ReactNode;
}) {
  return (
    <div className={cx("cs-slider", auto && "auto")}>
      <div className="cs-slider-h">
        <b>{label}</b>
        <span className="cs-slider-v">
          {show ?? Math.round(value)}
          {auto ? <em>auto</em> : onAuto ? <button type="button" className="cs-mini-link" onClick={onAuto}>reset</button> : null}
        </span>
      </div>
      <input type="range" className="cs-range" min={min} max={max} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      {(left || rightWord) && (
        <div className="cs-slider-ends"><span>{left}</span><span>{rightWord}</span></div>
      )}
    </div>
  );
}

export function Fold({ title, sub, children, open: start = false }: { title: React.ReactNode; sub?: React.ReactNode; children: React.ReactNode; open?: boolean }) {
  const [open, setOpen] = useState(start);
  return (
    <div className={cx("cs-fold", open && "open")}>
      <button type="button" className="cs-fold-h" onClick={() => setOpen(!open)}>
        <div>
          <b>{title}</b>
          {sub && <span>{sub}</span>}
        </div>
        <PIcon name="chevron" size={18} />
      </button>
      {open && <div className="cs-fold-b">{children}</div>}
    </div>
  );
}

function NameInputs({ p, set, cat, lastPlaceholder, used }: { p: Person; set: (x: Partial<Person>) => void; cat: any; lastPlaceholder?: string; used: Set<string> }) {
  return (
    <div className="cs-names">
      <input className="ph-input" type="text" value={p.first} maxLength={24} placeholder="First name" autoCapitalize="words" onChange={(e) => set({ first: e.target.value })} />
      <input className="ph-input" type="text" value={p.last || ""} maxLength={30} placeholder={lastPlaceholder || "Last name"} autoCapitalize="words" onChange={(e) => set({ last: e.target.value })} />
      <button type="button" className="cs-dice" aria-label="Random name" onClick={() => set({ first: randomName(cat, p.gender || "m", used), ...(lastPlaceholder ? {} : { last: p.last || randomLast(cat) }) })}>🎲</button>
    </div>
  );
}

function Problems({ items, onFix, who }: { items: Problem[]; onFix?: (p: Problem) => void; who?: (p: Problem) => string | null }) {
  if (!items.length) return null;
  return (
    <div className="cs-problems">
      <b>A few things to fix first</b>
      {items.map((p, i) => (
        <button key={i} type="button" className="cs-problem" onClick={() => onFix?.(p)} disabled={!onFix}>
          <span>{who?.(p) ? <><b>{who(p)}:</b> </> : null}{p.msg}</span>
          {onFix && <PIcon name="chevron" size={16} />}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- the creator
export default function CreateStory({ hasStory }: { hasStory: boolean }) {
  const { cat, error: catErr } = useStoryCatalog();
  const { refresh, toast } = usePhone();
  const lab = useStore();
  const [d, setD] = useState<Draft>(() => {
    const x = loadDraft(KEY);
    return { ...x, step: clamp(x.step || 0, 0, STEPS.length - 1) };
  });
  const [editing, setEditing] = useState<{ kind: "sibling" | "cast"; key: string } | null>(null);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => saveDraft(d, KEY), [d]);
  const step = d.step;
  const [id, title, sub] = STEPS[step];
  const go = (i: number) => {
    setD((x) => ({ ...x, step: clamp(i, 0, STEPS.length - 1) }));
    scroller.current?.scrollTo({ top: 0 });
  };
  const back = () => (step > 0 ? go(step - 1) : pgo(hasStory ? "me" : ""));
  const me = d.protagonist;
  const setMe = (patch: Partial<Person>) => setD((x) => ({ ...x, protagonist: { ...x.protagonist, ...patch } }));
  const usedNames = useMemo(() => new Set<string>([me.first, ...d.siblings.map((s) => s.first), ...d.cast.map((c) => c.first)].filter(Boolean)), [me.first, d.siblings, d.cast]);
  const pickColor = (i: number) => COLORS[(COLORS.indexOf(me.color || COLORS[0]) + 3 + i * 5) % COLORS.length];

  const nextKey = (prefix: string, x: Draft, n = 1) => {
    const used = new Set([...x.siblings, ...x.cast].map((p) => p.key));
    const keys: string[] = [];
    let seq = x.seq;
    while (keys.length < n) {
      const k = `${prefix}${seq++}`;
      if (!used.has(k)) keys.push(k);
    }
    return { keys, seq };
  };
  const addSiblings = (people: Partial<Person>[], twins?: boolean) => {
    const { keys, seq } = nextKey("sib", d, people.length);
    const made: Person[] = people.map((p, i) => ({
      first: "", gender: "m", grade: 10, color: pickColor(d.siblings.length + i + 1), ...p, key: keys[i],
      ...(twins && i > 0 ? { twin_of: keys[0] } : {}),
    }) as Person);
    setD((x) => ({ ...x, siblings: [...x.siblings, ...made], seq: Math.max(x.seq, seq) }));
    setEditing({ kind: "sibling", key: keys[0] });
  };
  const addPerson = (tid: string) => {
    const t = TEMPLATES.find((x) => x.id === tid)!;
    const { keys, seq } = nextKey("p", d);
    const p: Person = { first: "", gender: "m", grade: me.grade || 9, color: pickColor(d.cast.length + 7), ...t.make(me, d), key: keys[0], template: t.label } as Person;
    setD((x) => ({ ...x, cast: [...x.cast, p], seq: Math.max(x.seq, seq) }));
    setEditing({ kind: "cast", key: keys[0] });
  };
  const setSib = (key: string, patch: Partial<Person>) =>
    setD((x) => {
      let sibs = x.siblings.map((s) => (s.key === key ? { ...s, ...patch } : s));
      const cur = sibs.find((s) => s.key === key)!;
      if ("twin_of" in patch && patch.twin_of) {
        const grade = patch.twin_of === "me" ? x.protagonist.grade || 9 : sibs.find((s) => s.key === patch.twin_of)?.grade;
        sibs = sibs.map((s) => (s.key === key ? { ...s, grade } : s.key === patch.twin_of && s.twin_of === key ? { ...s, twin_of: undefined } : s));
      }
      if ("grade" in patch) {
        sibs = sibs.map((s) => (s.twin_of === key ? { ...s, grade: patch.grade } : s));
        if (cur.twin_of === "me" && patch.grade !== (x.protagonist.grade || 9)) sibs = sibs.map((s) => (s.key === key ? { ...s, twin_of: undefined } : s));
        if (cur.twin_of && cur.twin_of !== "me") sibs = sibs.map((s) => (s.key === cur.twin_of ? { ...s, grade: patch.grade } : s));
      }
      return { ...x, siblings: sibs };
    });
  const setCast = (key: string, patch: Partial<Person>) => setD((x) => ({ ...x, cast: x.cast.map((c) => (c.key === key ? { ...c, ...patch } : c)) }));
  const remove = (kind: "sibling" | "cast", key: string) => {
    setEditing(null);
    setD((x) =>
      kind === "sibling"
        ? { ...x, siblings: x.siblings.filter((s) => s.key !== key).map((s) => (s.twin_of === key ? { ...s, twin_of: undefined } : s)) }
        : { ...x, cast: x.cast.map((c) => ({ ...c, relationships: c.relationships?.filter((r) => r.to !== key), household: c.household === key ? undefined : c.household })).filter((c) => c.key !== key) },
    );
  };

  const fixProblem = (p: Problem) => {
    if (p.who === "me") go(/look/.test(p.msg) ? 1 : /position|jersey|height|build|skill|interest/.test(p.msg) ? 3 : 0);
    else if (p.who === "family") go(4);
    else if (p.who === "people") go(5);
    else if (p.who === "town" || p.who === "other") go(6);
    else if (d.siblings.some((s) => s.key === p.who)) {
      go(4);
      setEditing({ kind: "sibling", key: p.who });
    } else if (d.cast.some((c) => c.key === p.who)) {
      go(5);
      setEditing({ kind: "cast", key: p.who });
    }
  };

  const check = async (): Promise<boolean> => {
    const { spec, sibOrder } = buildSpec(d);
    try {
      await api.post("/api/story/validate", { spec });
      setProblems([]);
      return true;
    } catch (e: any) {
      const errs: string[] = e?.body?.errors || e?.errors || [];
      const items = errs.length ? parseErrors(errs, sibOrder, d.cast) : [{ who: "other", msg: errText(e) }];
      setProblems(items);
      return false;
    }
  };
  const [gw, setGw] = useState<Groundwork | null>(null);
  const [carry, setCarry] = useState(true);
  useEffect(() => {
    if (hasStory) phoneApi.groundwork().then(setGw).catch(() => setGw(null));
  }, [hasStory]);
  const start = async () => {
    if (!me.first.trim()) {
      setProblems([{ who: "me", msg: "You need a first name." }]);
      return;
    }
    if (hasStory && !window.confirm("Starting this replaces the story on this phone. Back it up first (Me tab) if you want to keep it. Start the new one?")) return;
    setBusy("start");
    try {
      if (!(await check())) return;
      const { spec } = buildSpec(d);
      const bring = !!(gw && gw.count && carry);
      const r: any = await api.post("/api/story/new", { spec, carry: bring });
      setD((x) => ({ ...x, step: 0 }));
      await refresh();
      lab.refresh();
      const c = r?.carried;
      toast(`${spec.title} starts now. First day of freshman year.` + (bring && c?.done ? ` ${c.done} of your changes came along.` : "")
        + (bring && c?.skipped?.length ? ` ${c.skipped.length} couldn't (someone who isn't in this setup).` : ""), "good");
      pgo("");
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  const next = async () => {
    if (step === 0 && !me.first.trim()) {
      toast("Give yourself a first name first.", "bad");
      return;
    }
    if (step === STEPS.length - 2) {
      setBusy("check");
      await check();
      setBusy(null);
    }
    go(step + 1);
  };
  const saveCast = async () => {
    const { spec } = buildSpec(d);
    const name = `${(spec.title || "My story").replace(/[^\w\- ]+/g, "").trim() || "My story"} cast.json`;
    const blob = new Blob([JSON.stringify(spec, null, 2)], { type: "application/json" });
    const file = new File([blob], name, { type: "application/json" });
    const nav: any = navigator;
    if (nav.canShare && nav.canShare({ files: [file] })) {
      try {
        await nav.share({ files: [file], title: name });
        return;
      } catch (e: any) {
        if (e?.name === "AbortError") return;
      }
    }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      URL.revokeObjectURL(a.href);
      a.remove();
    }, 1000);
  };
  const loadCast = async () => {
    const f = await pickFile(".json,.txt,.xlsx,application/json,text/plain");
    if (!f) return;
    try {
      let spec: any;
      if (/\.xlsx$/i.test(f.name)) {
        const res = await fetch("/api/story/import-sheet", { method: "POST", body: await f.arrayBuffer(), headers: { "Content-Type": "application/octet-stream" } });
        const body = await res.json();
        if (!res.ok) throw new Error([body.detail, ...(body.errors || [])].filter(Boolean).join(" · "));
        spec = body.spec;
      } else {
        const m = (await f.text()).match(/\{[\s\S]*\}/);
        if (!m) throw new Error("That file doesn't have a story cast in it.");
        const j = JSON.parse(m[0]);
        spec = j.spec || j;
      }
      if (!spec?.protagonist) throw new Error("That file doesn't have a story cast in it.");
      setD({ ...specToDraft(spec), step: 0 });
      setProblems([]);
      toast("Loaded. Look it over and change anything you want.", "good");
    } catch (e) {
      toast(errText(e), "bad");
    }
  };
  const startOver = () => {
    if (!window.confirm("Clear everything here and start from a blank story?")) return;
    setD(defaultDraft());
    setProblems([]);
  };

  const sib = editing?.kind === "sibling" ? d.siblings.find((s) => s.key === editing.key) : undefined;
  const person = editing?.kind === "cast" ? d.cast.find((c) => c.key === editing.key) : undefined;

  if (catErr) {
    return (
      <div className="ph-loading">
        <div className="ph-loading-t">Couldn't load the story builder</div>
        <p className="ph-dim">{catErr}</p>
        <button className="ph-btn primary" onClick={() => window.location.reload()}>Try again</button>
      </div>
    );
  }
  if (!cat) {
    return (
      <div className="ph-loading">
        <div className="ph-spinner" />
        <div className="ph-loading-t">Getting the builder ready…</div>
      </div>
    );
  }
  return (
    <div className="cs-wrap">
      <header className="cs-top">
        <button type="button" className="cs-back" onClick={back} aria-label="Back"><PIcon name="back" size={20} /></button>
        <div className="cs-top-m">
          <div className="cs-kicker">Step {step + 1} of {STEPS.length}</div>
          <div className="cs-dots">{STEPS.map(([k], i) => <button key={k} type="button" aria-label={STEPS[i][1]} className={cx(i === step && "on", i < step && "done")} onClick={() => go(i)} />)}</div>
        </div>
        <Portrait size={38} look={lookOf(me)} color={me.color || COLORS[0]} mood="happy" name={me.first || "you"} />
      </header>
      <div className="cs-scroll" ref={scroller}>
        <div className="cs-head">
          <h2>{title}</h2>
          <p>{sub}</p>
        </div>
        <div className="ph-pad cs-body" key={id}>
          {id === "you" && <YouStep me={me} setMe={setMe} cat={cat} used={usedNames} onLoad={loadCast} onReset={startOver} />}
          {id === "look" && (
            <div className="cs-look">
              <LookPicker value={me.look} base={lookOf(me)} onChange={(look) => setMe({ look })} gender={me.gender || undefined} color={me.color} name={me.first || "you"} />
            </div>
          )}
          {id === "type" && <TypeStep p={me} set={setMe} cat={cat} />}
          {id === "sports" && <SportsStep p={me} set={setMe} cat={cat} />}
          {id === "family" && <FamilyStep d={d} setD={setD} cat={cat} add={addSiblings} edit={(key) => setEditing({ kind: "sibling", key })} />}
          {id === "people" && <PeopleStep d={d} add={addPerson} edit={(key) => setEditing({ kind: "cast", key })} />}
          {id === "start" && <StartStep d={d} setD={setD} cat={cat} problems={problems} onFix={fixProblem} onSave={saveCast} edit={(i) => go(i)} />}
        </div>
      </div>
      <footer className="cs-foot">
        {step < STEPS.length - 1 ? (
          <button type="button" className="ph-btn primary block big" disabled={!!busy} onClick={next}>
            {busy === "check" ? <span className="ph-spinner small light" /> : null}
            {step === 0 && !me.first.trim() ? "Next" : `Next: ${STEPS[step + 1][1]}`}
          </button>
        ) : (
          <>
          {gw && gw.count > 0 && (
            <label className="cs-carry">
              <input type="checkbox" checked={carry} onChange={(e) => setCarry(e.target.checked)} />
              <span><b>Bring my changes from this run ({gw.count})</b>
                <small>Who people are, people you added, relationships you set, who your storylines are about. Anyone who's
                  in this setup gets them (change someone here and here wins for what you changed).</small></span>
            </label>
          )}
          <button type="button" className="ph-btn primary block big" disabled={!!busy} onClick={start}>
            {busy === "start" ? <><span className="ph-spinner small light" /> Building your world…</> : <><PIcon name="sparkle" size={18} /> Start my story</>}
          </button>
          </>
        )}
      </footer>
      <Sheet open={!!sib} onClose={() => setEditing(null)} full title={sib ? displayName(sib, `New ${sibWord(sib)}`) : ""}>
        {sib && (
          <SiblingEditor p={sib} d={d} cat={cat} set={(patch) => setSib(sib.key!, patch)} used={usedNames}
            problems={problems.filter((x) => x.who === sib.key)} onRemove={() => remove("sibling", sib.key!)} onDone={() => setEditing(null)} />
        )}
      </Sheet>
      <Sheet open={!!person} onClose={() => setEditing(null)} full title={person ? displayName(person, person.template ? `Your ${person.template.toLowerCase()}` : "New person") : ""}>
        {person && (
          <PersonEditor p={person} d={d} cat={cat} set={(patch) => setCast(person.key!, patch)} used={usedNames}
            problems={problems.filter((x) => x.who === person.key)} onRemove={() => remove("cast", person.key!)} onDone={() => setEditing(null)} />
        )}
      </Sheet>
    </div>
  );
}

// ---------------------------------------------------------------- steps
function YouStep({ me, setMe, cat, used, onLoad, onReset }: { me: Person; setMe: (p: Partial<Person>) => void; cat: any; used: Set<string>; onLoad: () => void; onReset: () => void }) {
  const att = attractionOf(me);
  const bd = me.birthday || null;
  const setBd = (m: number, day: number) => setMe({ birthday: m && day ? [m, Math.min(day, MONTH_DAYS[m - 1])] : null });
  return (
    <>
      <div className="cs-me">
        <Portrait size={112} look={lookOf(me)} color={me.color || COLORS[0]} mood="happy" name={me.first || "you"} />
        <div>
          <div className="cs-me-n">{displayName(me, "You")}</div>
          <div className="ph-dim">Freshman at {cat.school?.short || "school"} · {archLabel(cat, me.archetype)}</div>
          {playsList(me).length > 0 && <div className="cs-chips">{playsList(me).map((s) => <span key={s}>{cap(s)}{me.positions?.[s] ? ` · ${me.positions[s]}` : ""}</span>)}</div>}
        </div>
      </div>
      <Field label="Your name">
        <NameInputs p={me} set={setMe} cat={cat} used={used} />
      </Field>
      <Field label="You are">
        <Seg value={me.gender || undefined} options={GENDERS as [any, string][]} onChange={(v) => setMe({ gender: v as any })} />
      </Field>
      <Field label="You're into" hint={att === "auto" ? "Left open, it's decided by the world when the story starts." : undefined}>
        <Seg value={att} options={[["f", "Girls"], ["m", "Guys"], ["both", "Both"], ["auto", "Let it play out"]]}
          onChange={(v) => setMe({ attracted_to: v === "auto" ? undefined : v === "both" ? ["f", "m"] : [v as any] })} />
      </Field>
      <Field label="Birthday" hint="Optional. It shows up in the story (and in the family chat).">
        <div className="cs-row2">
          <select className="ph-input" value={bd?.[0] || ""} onChange={(e) => setBd(Number(e.target.value), bd?.[1] || 1)}>
            <option value="">Month</option>
            {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          </select>
          <select className="ph-input" value={bd?.[1] || ""} disabled={!bd?.[0]} onChange={(e) => setBd(bd?.[0] || 1, Number(e.target.value))}>
            <option value="">Day</option>
            {Array.from({ length: MONTH_DAYS[(bd?.[0] || 1) - 1] }, (_, i) => <option key={i} value={i + 1}>{i + 1}</option>)}
          </select>
        </div>
      </Field>
      <Field label="Your color" hint="Your accent around the app.">
        <div className="cs-colors">
          {COLORS.map((c) => <button key={c} type="button" aria-label={c} className={cx(me.color === c && "on")} style={{ background: c }} onClick={() => setMe({ color: c })} />)}
        </div>
      </Field>
      <div className="cs-quiet">
        <button type="button" className="ph-link" onClick={onLoad}><PIcon name="upload" size={15} /> Load a cast file to edit</button>
        <button type="button" className="ph-link" onClick={onReset}>Start over</button>
      </div>
    </>
  );
}

function TypeStep({ p, set, cat }: { p: Person; set: (x: Partial<Person>) => void; cat: any }) {
  const layer = (name: "traits" | "aptitudes" | "motives", keys: string[], label: (k: string) => React.ReactNode, ends?: (k: string) => [string, string]) => (
    <>
      {keys.map((k) => {
        const auto = p[name]?.[k] === undefined;
        const v = shown(cat, p, name, k);
        const e = ends?.(k);
        return (
          <Slider key={k} label={label(k)} value={v} auto={auto} left={e?.[0]} rightWord={e?.[1]}
            onChange={(x) => set({ [name]: { ...(p[name] || {}), [k]: x } } as any)}
            onAuto={() => {
              const o = { ...(p[name] || {}) };
              delete o[k];
              set({ [name]: o } as any);
            }} />
        );
      })}
    </>
  );
  return (
    <>
      <div className="cs-arch">
        {cat.archetypes.map((a: any) => (
          <button key={a.id} type="button" className={cx(p.archetype === a.id && "on")} onClick={() => set({ archetype: a.id })}>
            <b>{a.label}</b>
            <span>{ARCH_BLURB[a.id] || ""}</span>
          </button>
        ))}
        <button type="button" className={cx(!p.archetype && "on")} onClick={() => set({ archetype: undefined })}>
          <b>Surprise me</b>
          <span>Let the world decide.</span>
        </button>
      </div>
      <div className="cs-sum">
        <div className="cs-sum-t">How people would describe you</div>
        <p>{summaryLine(cat, p)}</p>
        <div className="cs-sum-a">
          <button type="button" className="ph-btn soft" onClick={() => set(randomizePerson(cat, p, ["traits", "aptitudes", "motives"]))}>🎲 Roll a personality</button>
          {(p.traits || p.aptitudes || p.motives) && <button type="button" className="ph-link" onClick={() => set({ traits: undefined, aptitudes: undefined, motives: undefined })}>Back to auto</button>}
        </div>
      </div>
      <Fold title="Personality" sub="Ten traits, from your type unless you move them">
        {layer("traits", TRAITS, (k) => cap(TRAIT_WORDS[k]?.[0] || k), (k) => [TRAIT_WORDS[k]?.[1] || "", TRAIT_WORDS[k]?.[0] || ""])}
      </Fold>
      <Fold title="Talent" sub="What comes naturally">
        {layer("aptitudes", APTS, (k) => APT_LABEL[k] || cap(k))}
      </Fold>
      <Fold title="What drives you" sub="What you go after when nobody's telling you what to do">
        {layer("motives", MOTIVES, (k) => cap(MOTIVE_WORDS[k] || k))}
      </Fold>
    </>
  );
}

function SportsStep({ p, set, cat }: { p: Person; set: (x: Partial<Person>) => void; cat: any }) {
  const body = p.body || {};
  const defH = p.gender === "f" ? 64 : 69;
  const h = body.height_in;
  const setBody = (patch: any) => set({ body: { ...body, ...patch } });
  const setPlay = (s: string, st: string) => {
    const ints = { ...(p.interests || {}) };
    const pos = { ...(p.positions || {}) };
    const sk = { ...(p.skills || {}) };
    if (st === "yes") ints[s] = Math.max(ints[s] ?? 0, 80);
    if (st === "no") {
      ints[s] = 10;
      delete pos[s];
      delete sk[s];
    }
    if (st === "auto") {
      delete ints[s];
      delete pos[s];
      delete sk[s];
    }
    set({ interests: ints, positions: pos, skills: sk });
  };
  return (
    <>
      <div className="cs-card">
        <Slider label="Height" value={h || defH} auto={!h} min={58} max={84} show={heightLabel(h || defH)} onChange={(x) => setBody({ height_in: x })} onAuto={() => setBody({ height_in: undefined })}
          left={`4'10"`} rightWord={`7'0"`} />
        <div className="cs-hint">Height matters most in basketball, a little for pitchers and keepers. Freshmen still grow some.</div>
        <div className="cs-field-l" style={{ marginTop: 12 }}><span>Build</span>{!body.build && <em className="cs-auto">auto</em>}</div>
        <div className="cs-builds">
          {cat.builds.map((b: string) => (
            <button key={b} type="button" className={cx(body.build === b && "on")} onClick={() => setBody({ build: body.build === b ? undefined : b })}>
              <b>{cap(b)}</b>
              <span>{BUILD_HINT[b]}</span>
            </button>
          ))}
        </div>
        <div className="cs-field-l" style={{ marginTop: 12 }}><span>Jersey number</span></div>
        <input className="ph-input cs-num" type="number" inputMode="numeric" min={0} max={99} value={p.jersey ?? ""} placeholder="Any"
          onChange={(e) => set({ jersey: e.target.value === "" ? null : clamp(Math.round(Number(e.target.value)), 0, 99) })} />
      </div>
      {sportsFor(p.gender).map((s) => {
        const sp = cat.sports[s];
        const st = playsSport(p, s);
        const iv = p.interests?.[s];
        const sk = p.skills?.[s];
        const auto = autoSkill(cat, p, { id: s, aptitude: "athletic" });
        const skv = sk ?? auto;
        return (
          <div key={s} className={cx("cs-card cs-sport", st === "yes" && "on")}>
            <div className="cs-sport-h">
              <div>
                <b>{sp.label}</b>
                <span>{SEASON[sp.season] || sp.season}</span>
              </div>
            </div>
            <Seg value={st} options={[["yes", "I play"], ["auto", "Maybe"], ["no", "Not for me"]]} onChange={(v) => setPlay(s, v)} />
            {st === "yes" && (
              <>
                <div className="cs-field-l" style={{ marginTop: 12 }}><span>Position</span></div>
                <div className="cs-pos">
                  {Object.entries(sp.positions).map(([k, label]: any) => {
                    const fit = h || body.build ? positionFit(s, k, h || defH, body.build || "average") : 0;
                    return (
                      <button key={k} type="button" className={cx(p.positions?.[s] === k && "on")} onClick={() => set({ positions: { ...(p.positions || {}), [s]: k } })}>
                        <b>{k}</b>
                        <span>{label}</span>
                        {fit >= 2 && <i className="good">{fit >= 5 ? "great fit" : "good fit"}</i>}
                        {fit <= -4 && <i className="bad">tough fit</i>}
                      </button>
                    );
                  })}
                  <button type="button" className={cx(!p.positions?.[s] && "on")} onClick={() => {
                    const pos = { ...(p.positions || {}) };
                    delete pos[s];
                    set({ positions: pos });
                  }}>
                    <b>?</b>
                    <span>Coach decides</span>
                  </button>
                </div>
                <Slider label="Skill on day one" value={skv} auto={sk === undefined} min={0} max={90}
                  show={<>{Math.round(skv)} <small>{skv >= 55 ? "varsity-ready" : skv >= 40 ? "solid freshman" : "raw"}</small></>}
                  onChange={(x) => set({ skills: { ...(p.skills || {}), [s]: x } })}
                  onAuto={() => {
                    const o = { ...(p.skills || {}) };
                    delete o[s];
                    set({ skills: o });
                  }} />
                <Slider label="Love for the game" value={iv ?? 80} min={40} max={100} onChange={(x) => set({ interests: { ...(p.interests || {}), [s]: x } })} />
              </>
            )}
            {st === "auto" && <div className="cs-hint">Depends on your type and a little luck.</div>}
            {st === "no" && <div className="cs-hint">You won't try out. (You could still change your mind later.)</div>}
          </div>
        );
      })}
      <div className="cs-hint cs-center">Skills grow with practice, games and coaching. Starting at 40 to 50 is a normal freshman; 55+ can make varsity early.</div>
    </>
  );
}

function FamilyStep({ d, setD, cat, add, edit }: { d: Draft; setD: React.Dispatch<React.SetStateAction<Draft>>; cat: any; add: (p: Partial<Person>[], twins?: boolean) => void; edit: (key: string) => void }) {
  const f = d.family;
  const me = d.protagonist;
  const last = familyLast(d);
  const setF = (patch: Partial<Draft["family"]>) => setD((x) => ({ ...x, family: { ...x.family, ...patch } }));
  const species = f.pet.species || "dog";
  const spc = cat.pets?.[species] || { label: cap(species), breeds: [], coats: [] };
  const full = d.siblings.length >= 6;
  const myGrade = me.grade || 9;
  const quick: [string, () => void][] = [
    ["Older brother", () => add([{ gender: "m", grade: 12 }])],
    ["Older sister", () => add([{ gender: "f", grade: 11 }])],
    ["Twin sisters", () => add([{ gender: "f", grade: 10 }, { gender: "f", grade: 10 }], true)],
    ["Twin brothers", () => add([{ gender: "m", grade: 10 }, { gender: "m", grade: 10 }], true)],
    ["My twin", () => add([{ gender: me.gender || "m", grade: myGrade, twin_of: "me" }])],
    ["Younger brother", () => add([{ gender: "m", grade: 8 }])],
    ["Younger sister", () => add([{ gender: "f", grade: 7 }])],
  ];
  return (
    <>
      <div className="cs-card">
        <Field label="Family last name">
          <input className="ph-input" type="text" value={f.last} maxLength={30} placeholder={me.last?.trim() || "Generated"} autoCapitalize="words" onChange={(e) => setF({ last: e.target.value })} />
        </Field>
        <Field label="Your parents" hint={`First names are fine; ${last ? `"${last}" gets added` : "the family name gets added"}. Leave them blank to generate.`}>
          <div className="cs-row2">
            <input className="ph-input" type="text" value={f.guardians[0]} placeholder="Parent" autoCapitalize="words" onChange={(e) => setF({ guardians: [e.target.value, f.guardians[1]] })} />
            <input className="ph-input" type="text" value={f.guardians[1]} placeholder="Other parent" autoCapitalize="words" onChange={(e) => setF({ guardians: [f.guardians[0], e.target.value] })} />
          </div>
        </Field>
        <Field label="How they parent">
          <div className="cs-styles">
            {cat.guardian_styles.map((s: any) => (
              <button key={s.id} type="button" className={cx(f.style === s.id && "on")} onClick={() => setF({ style: s.id })}>
                <b>{cap(s.id)}</b>
                <span>{cap(s.label)}</span>
              </button>
            ))}
          </div>
        </Field>
        <Field label="Money at home">
          <Seg value={f.income} options={INCOME} onChange={(v) => setF({ income: v })} />
        </Field>
      </div>

      <div className="ph-section-t">Pet</div>
      <div className="cs-card">
        <Seg wrap value={f.petMode} options={[["none", "No pet"], ["chance", "Leave to chance"], ["random", "Surprise me"], ["pick", "We have one"]]} onChange={(v) => setF({ petMode: v as any })} />
        {f.petMode === "pick" && (
          <div className="cs-pet">
            <div className="cs-pet-art"><PetArt species={species} coat={f.pet.coat} breed={f.pet.breed} mood="happy" size={120} /></div>
            <Seg value={species} options={Object.keys(cat.pets || { dog: 1, cat: 1, rabbit: 1 }).map((k) => [k, cat.pets?.[k]?.label || cap(k)] as [string, string])}
              onChange={(v) => setF({ pet: { ...f.pet, species: v, breed: undefined, coat: undefined } })} />
            <input className="ph-input" type="text" value={f.pet.name} maxLength={20} placeholder={`Your ${spc.label.toLowerCase()}'s name`} autoCapitalize="words"
              onChange={(e) => setF({ pet: { ...f.pet, name: e.target.value } })} />
            <select className="ph-input" value={f.pet.breed || ""} onChange={(e) => setF({ pet: { ...f.pet, breed: e.target.value || undefined } })}>
              <option value="">Any breed</option>
              {spc.breeds.map((b: string) => <option key={b} value={b}>{b}</option>)}
            </select>
            <div className="cs-coats">
              {spc.coats.map((c: string) => (
                <button key={c} type="button" className={cx(f.pet.coat === c && "on")} onClick={() => setF({ pet: { ...f.pet, coat: f.pet.coat === c ? undefined : c } })}>
                  <PetArt species={species} coat={c} breed={f.pet.breed} size={52} />
                  <span>{cap(c)}</span>
                </button>
              ))}
            </div>
            {!f.pet.name.trim() && <div className="cs-hint warn">Give them a name, or they won't come home with you.</div>}
            <div className="cs-hint">You'll set up who feeds and walks them once, on the first day.</div>
          </div>
        )}
        {f.petMode === "chance" && <div className="cs-hint">Some families have one, some don't.</div>}
        {f.petMode === "random" && <div className="cs-hint">You'll have a pet. You'll meet them on the first day.</div>}
      </div>

      <div className="ph-section-t">Brothers and sisters</div>
      {d.siblings.length === 0 && <div className="cs-empty">No siblings yet. Only child? Leave it empty.</div>}
      <div className="ph-list">
        {d.siblings.map((s) => {
          const twin = s.twin_of === "me" ? "your twin" : s.twin_of ? `twin of ${d.siblings.find((x) => x.key === s.twin_of)?.first || "their twin"}` : d.siblings.find((x) => x.twin_of === s.key) ? "a twin" : "";
          return (
            <button key={s.key} type="button" className="ph-row" onClick={() => edit(s.key!)}>
              <Portrait look={sibLook(s, me)} size={46} color={s.color} name={s.first || "sibling"} />
              <div className="ph-row-main">
                <b>{displayName(s, `Unnamed ${sibWord(s)}`)}</b>
                <span className="ph-dim">
                  {(s.grade || 10) < 9 ? `Younger ${sibWord(s)} · ${gradeWord(s.grade)}` : `${GRADE_LABEL[s.grade || 10]} ${sibWord(s)}`}{twin ? ` · ${twin}` : ""}{s.path?.college ? ` · then ${cat.colleges.find((c: any) => c.id === s.path!.college)?.short || s.path.college}${s.path.sport ? ` ${s.path.sport}` : ""}` : ""}
                </span>
              </div>
              <PIcon name="chevron" size={18} />
            </button>
          );
        })}
      </div>
      {!full && (
        <div className="cs-adds">
          {quick.map(([label, fn]) => <button key={label} type="button" onClick={fn}>+ {label}</button>)}
        </div>
      )}
      <div className="cs-hint">Older siblings and twins are in high school with you. Younger ones are in middle school and start high school as freshmen in a later year, with that year's class. Twins share a grade and a birthday.</div>
    </>
  );
}

function PeopleStep({ d, add, edit }: { d: Draft; add: (tid: string) => void; edit: (key: string) => void }) {
  return (
    <>
      <div className="cs-adds big">
        {TEMPLATES.map((t) => (
          <button key={t.id} type="button" onClick={() => add(t.id)}>
            <span className="cs-add-i">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>
      {d.cast.length > 0 && <div className="ph-section-t">In your story</div>}
      <div className="ph-list">
        {d.cast.map((c) => {
          const rel = c.relationships?.find((r) => r.to === "me");
          return (
            <button key={c.key} type="button" className="ph-row" onClick={() => edit(c.key!)}>
              <Portrait look={lookOf(c)} size={46} color={c.color} name={c.first || "someone"} />
              <div className="ph-row-main">
                <b>{displayName(c, c.template ? `Your ${c.template.toLowerCase()}` : "New person")}</b>
                <span className="ph-dim">{c.role === "staff" ? `${cap(c.coach_of || "")} coach` : `${gradeWord(c.grade)} · ${relLabel(rel?.type)}`}</span>
              </div>
              <PIcon name="chevron" size={18} />
            </button>
          );
        })}
      </div>
      {d.cast.length === 0 && <div className="cs-empty">Nobody yet. Add the people you want in your story, or skip this and meet everyone fresh.</div>}
      <div className="cs-hint">Everyone else in town is generated, with their own families, friends and plans. Someone younger? Add a <b>Future freshman</b>: they show up with that year's freshman class.</div>
    </>
  );
}

function StartStep({ d, setD, cat, problems, onFix, onSave, edit }: {
  d: Draft; setD: React.Dispatch<React.SetStateAction<Draft>>; cat: any; problems: Problem[]; onFix: (p: Problem) => void; onSave: () => void; edit: (step: number) => void;
}) {
  const me = d.protagonist;
  const last = familyLast(d);
  const f = d.family;
  const petLine = f.petMode === "none" ? "No pet" : f.petMode === "chance" ? "Maybe a pet" : f.petMode === "random" ? "A surprise pet" : f.pet.name.trim() ? `${f.pet.name.trim()}, your ${f.pet.breed ? f.pet.breed.toLowerCase() : f.pet.species}` : "A pet (needs a name)";
  const parents = f.guardians.map((x) => x.trim()).filter(Boolean);
  return (
    <>
      <Problems items={problems} onFix={onFix} who={(p) => {
        if (p.who === "me") return "You";
        if (p.who === "family") return "Family";
        if (p.who === "town" || p.who === "other" || p.who === "people") return null;
        const s = d.siblings.find((x) => x.key === p.who);
        if (s) return displayName(s, `Your ${GRADE_LABEL[s.grade || 10].toLowerCase()} ${sibWord(s)}`);
        const c = d.cast.find((x) => x.key === p.who);
        return c ? displayName(c, c.template ? `Your ${c.template.toLowerCase()}` : "Someone you added") : null;
      }} />
      <div className="cs-card cs-review">
        <button type="button" className="cs-rev-row" onClick={() => edit(0)}>
          <Portrait size={64} look={lookOf(me)} color={me.color || COLORS[0]} mood="happy" name={me.first || "you"} />
          <div>
            <b>{displayName(me, "You")}</b>
            <span>Freshman · {archLabel(cat, me.archetype)}{me.body?.height_in ? ` · ${heightLabel(me.body.height_in)}` : ""}</span>
            <span>{playsList(me).length ? playsList(me).map((s) => `${cap(s)}${me.positions?.[s] ? ` (${me.positions[s]})` : ""}`).join(", ") : "No sports picked"}{me.jersey != null ? ` · #${me.jersey}` : ""}</span>
          </div>
        </button>
        <button type="button" className="cs-rev-row" onClick={() => edit(4)}>
          <div className="cs-rev-i">🏠</div>
          <div>
            <b>The {last || "family"} house</b>
            <span>{parents.length ? parents.join(" and ") : "Parents generated"} · {cap(f.style)} · {INCOME.find(([k]) => k === f.income)?.[1]}</span>
            <span>{d.siblings.length ? d.siblings.map((s) => `${s.first || "?"} (${GRADE_LABEL[s.grade || 10].toLowerCase()})`).join(", ") : "No siblings"} · {petLine}</span>
          </div>
        </button>
        <button type="button" className="cs-rev-row" onClick={() => edit(5)}>
          <div className="cs-rev-i">👥</div>
          <div>
            <b>{d.cast.length ? `${d.cast.length} of your people` : "Nobody added"}</b>
            <span>{d.cast.length ? d.cast.map((c) => `${c.first || "?"} (${c.role === "staff" ? "coach" : relLabel(c.relationships?.find((r) => r.to === "me")?.type).toLowerCase()})`).join(", ") : "You'll meet everyone fresh."}</span>
          </div>
        </button>
      </div>
      <Field label="Name your story">
        <input className="ph-input" type="text" value={d.title} maxLength={60} placeholder={last ? `The ${last} Years` : "My Story"} onChange={(e) => setD((x) => ({ ...x, title: e.target.value }))} />
      </Field>
      <div className="cs-card">
        <Slider label="Kids per grade" value={d.students_per_grade} min={6} max={40} onChange={(x) => setD((y) => ({ ...y, students_per_grade: x }))} left="small, quick" rightWord="big, slower" />
        <div className="cs-hint">How many classmates the town starts with in each grade, plus everyone you made. Teams get bigger with the school. 12 to 20 plays smoothly on a phone; past 30, days take a few seconds. Every fall a new freshman class comes in, about the size of the class that graduated.</div>
      </div>
      <div className="cs-card cs-what">
        <b>What happens next</b>
        <p>You start on the first day of freshman year at {cat.school?.short || "school"}. You'll get texts, meet people, try out, and make the calls. Seven years: high school, then college, and if you're good enough, the draft.</p>
      </div>
      <button type="button" className="ph-btn soft block" onClick={onSave}><PIcon name="download" size={17} /> Save as a cast file</button>
      <div className="cs-hint cs-center">The cast file opens in the lab on your computer too.</div>
    </>
  );
}

// ---------------------------------------------------------------- people editors
function TypeChips({ p, set, cat }: { p: Person; set: (x: Partial<Person>) => void; cat: any }) {
  return (
    <div className="cs-typechips">
      <button type="button" className={cx(!p.archetype && "on")} onClick={() => set({ archetype: undefined })}>Surprise me</button>
      {cat.archetypes.map((a: any) => (
        <button key={a.id} type="button" className={cx(p.archetype === a.id && "on")} onClick={() => set({ archetype: a.id })}>{a.label}</button>
      ))}
    </div>
  );
}

function SportChips({ p, set }: { p: Person; set: (x: Partial<Person>) => void }) {
  return (
    <div className="ph-seg cs-seg wrap">
      {sportsFor(p.gender).map((s) => {
        const on = playsSport(p, s) === "yes";
        return (
          <button key={s} type="button" className={cx(on && "on")} onClick={() => {
            const ints = { ...(p.interests || {}) };
            const pos = { ...(p.positions || {}) };
            if (on) {
              delete ints[s];
              delete pos[s];
            } else ints[s] = 80;
            set({ interests: ints, positions: pos });
          }}>{on ? "✓ " : ""}{cap(s)}</button>
        );
      })}
    </div>
  );
}

function EditorTop({ p, cat, look }: { p: Person; cat: any; look?: Look }) {
  return (
    <div className="cs-ed-top">
      <Portrait size={84} look={look || lookOf(p)} color={p.color || "#9aa1c4"} mood="happy" name={p.first || "someone"} />
      <p>{summaryLine(cat, p)}</p>
    </div>
  );
}

function LookFold({ p, set, look, family }: { p: Person; set: (x: Partial<Person>) => void; look?: Look; family?: boolean }) {
  return (
    <Fold title="Their look" sub={p.look && Object.keys(p.look).length ? "Locked in" : family ? "On auto: looks like family" : "On auto"}>
      <div className="cs-look">
        <LookPicker value={p.look} base={look || lookOf(p)} onChange={(look) => set({ look })} gender={p.gender || undefined} color={p.color} adult={p.role === "staff"} name={p.first || "someone"} />
      </div>
    </Fold>
  );
}

function EditorFoot({ onRemove, onDone, what }: { onRemove: () => void; onDone: () => void; what: string }) {
  return (
    <div className="cs-ed-foot">
      <button type="button" className="ph-btn primary block" onClick={onDone}>Done</button>
      <button type="button" className="ph-link center cs-remove" onClick={() => window.confirm(`Take this ${what} out of your story?`) && onRemove()}>Remove {what}</button>
    </div>
  );
}

function SiblingEditor({ p, d, cat, set, used, problems, onRemove, onDone }: {
  p: Person; d: Draft; cat: any; set: (x: Partial<Person>) => void; used: Set<string>; problems: Problem[]; onRemove: () => void; onDone: () => void;
}) {
  const me = d.protagonist;
  const myGrade = me.grade || 9;
  const others = d.siblings.filter((s) => s.key !== p.key);
  const twinOpts: [string, string][] = [["", "Not a twin"], ...(p.grade === myGrade || p.twin_of === "me" ? [["me", "Your twin"] as [string, string]] : []),
    ...others.map((s) => [s.key!, `Twin of ${s.first || "them"}`] as [string, string])];
  const path = p.path || null;
  const mode = !path ? "auto" : path.kind === "work" ? "work" : path.sport ? "sport" : "college";
  const cols: any[] = cat.colleges || [];
  const col = cols.find((c) => c.id === path?.college);
  const setPath = (m: string) => {
    if (m === "auto") set({ path: null });
    else if (m === "work") set({ path: { kind: "work" } });
    else if (m === "college") set({ path: { kind: "college", college: path?.college || "uconn", sport: null } });
    else {
      const c = cols.find((x) => x.id === (path?.college || "uconn")) || cols[0];
      const fav = playsList(p)[0];
      const sport = fav && c.sports.includes(fav) ? fav : c.sports[0] || null;
      set({ path: { kind: "college", college: c.id, sport }, ...withSport(p, sport) });
    }
  };
  const famLast = familyLast(d);
  const look = sibLook(p, me);
  return (
    <div className="cs-ed">
      <EditorTop p={p} cat={cat} look={look} />
      <Problems items={problems} />
      <Field label="Name">
        <NameInputs p={p} set={set} cat={cat} used={used} lastPlaceholder={famLast || "Family last name"} />
      </Field>
      <Field label="They're your">
        <Seg value={p.gender || undefined} options={[["m", "Brother"], ["f", "Sister"], ["nb", "Sibling"]]} onChange={(v) => set({ gender: v as any })} />
      </Field>
      <GradePick p={{ ...p, grade: p.grade || 10 }} set={set} myGrade={myGrade} cat={cat} twin={!!p.twin_of} />
      {twinOpts.length > 1 && (
        <Field label="Twin">
          <Seg wrap value={p.twin_of || ""} options={twinOpts} onChange={(v) => set({ twin_of: v || undefined })} />
        </Field>
      )}
      <Field label="Their type">
        <TypeChips p={p} set={set} cat={cat} />
      </Field>
      <Field label="Plays">
        <SportChips p={p} set={set} />
      </Field>
      <div className="cs-card flat">
        <Slider label="How you two get along" value={p.strength || 0} min={-40} max={40} show={closeness(p.strength || 0)} onChange={(x) => set({ strength: x })} left="fight a lot" rightWord="super close" />
      </div>
      <Field label="After high school" hint={mode === "auto" ? "They figure it out like everyone else: grades, offers and luck." : mode === "sport" && col ? `Goes to ${col.short} to play ${path?.sport}.` : undefined}>
        <Seg wrap value={mode} options={[["auto", "Let it play out"], ["college", "College"], ["sport", "College + sport"], ["work", "Work"]]} onChange={setPath} />
        {(mode === "college" || mode === "sport") && (
          <div className="cs-row2" style={{ marginTop: 8 }}>
            <select className="ph-input" value={path?.college || ""} onChange={(e) => {
              const c = cols.find((x) => x.id === e.target.value);
              let sport = mode === "sport" ? path?.sport || c?.sports?.[0] || null : null;
              if (sport && c && !c.sports.includes(sport)) sport = c.sports[0] || null;
              set({ path: { kind: "college", college: e.target.value, sport }, ...withSport(p, sport) });
            }}>
              {cols.map((c) => <option key={c.id} value={c.id}>{c.short}</option>)}
            </select>
            {mode === "sport" && (
              <select className="ph-input" value={path?.sport || ""} onChange={(e) => set({ path: { kind: "college", college: path?.college || "uconn", sport: e.target.value }, ...withSport(p, e.target.value) })}>
                {(col?.sports || []).map((s: string) => <option key={s} value={s}>{cap(s)}</option>)}
              </select>
            )}
          </div>
        )}
      </Field>
      <LookFold p={p} set={set} look={look} family />
      <EditorFoot onRemove={onRemove} onDone={onDone} what={sibWord(p)} />
    </div>
  );
}

function PersonEditor({ p, d, cat, set, used, problems, onRemove, onDone }: {
  p: Person; d: Draft; cat: any; set: (x: Partial<Person>) => void; used: Set<string>; problems: Problem[]; onRemove: () => void; onDone: () => void;
}) {
  const staff = p.role === "staff";
  const rel = p.relationships?.find((r) => r.to === "me");
  const setRel = (patch: { type?: string; strength?: number }) => {
    const others = (p.relationships || []).filter((r) => r.to !== "me");
    const next = { to: "me", type: rel?.type || "friend", ...(rel?.strength ? { strength: rel.strength } : {}), ...patch };
    set({ relationships: [...others, next] });
  };
  const romance = ["admirer", "crush", "mutual_crush", "dating", "ex"].includes(rel?.type || "");
  const me = d.protagonist;
  const mismatch = romance && me.gender && p.attracted_to?.length && !p.attracted_to.includes(me.gender as any);
  return (
    <div className="cs-ed">
      <EditorTop p={p} cat={cat} />
      <Problems items={problems} />
      <Field label="Name">
        <NameInputs p={p} set={set} cat={cat} used={used} />
      </Field>
      <Field label="Gender">
        <Seg value={p.gender || undefined} options={GENDERS as [any, string][]} onChange={(v) => set({ gender: v as any })} />
      </Field>
      {staff ? (
        <>
          <Field label="What they coach">
            <Seg value={p.coach_of || "football"} options={TEAMS} onChange={(v) => set({ coach_of: v })} wrap />
          </Field>
          <Field label="What you call them">
            <Seg value={p.title || "Coach"} options={[["Coach", "Coach"], ["Mr.", "Mr."], ["Ms.", "Ms."], ["Mrs.", "Mrs."]]} onChange={(v) => set({ title: v })} />
          </Field>
        </>
      ) : (
        <>
          <GradePick p={p} set={set} myGrade={me.grade || 9} cat={cat} />
          <Field label="Who they are to you">
            <div className="cs-rels">
              {REL_TO_YOU.map(([k, label]) => (
                <button key={k} type="button" className={cx(rel?.type === k && "on")} onClick={() => setRel({ type: k })}>{label}</button>
              ))}
            </div>
          </Field>
          {romance && (
            <Field label="They're into" hint={mismatch ? "Heads up: that doesn't line up with who you are, so the spark may not be mutual." : undefined}>
              <Seg value={attractionOf(p)} options={[["f", "Girls"], ["m", "Guys"], ["both", "Both"], ["auto", "Auto"]]}
                onChange={(v) => set({ attracted_to: v === "auto" ? undefined : v === "both" ? ["f", "m"] : [v as any] })} />
            </Field>
          )}
          {rel && (
            <div className="cs-card flat">
              <Slider label="How strong" value={rel.strength || 0} min={-40} max={40} show={warmth(rel.strength || 0)} onChange={(x) => setRel({ strength: x })} left="cooler" rightWord="closer" />
            </div>
          )}
          <Field label="Their type">
            <TypeChips p={p} set={set} cat={cat} />
          </Field>
          <Field label="Plays">
            <SportChips p={p} set={set} />
          </Field>
        </>
      )}
      <LookFold p={p} set={set} />
      <EditorFoot onRemove={onRemove} onDone={onDone} what={staff ? "coach" : "person"} />
    </div>
  );
}
