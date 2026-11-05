// Story setup: you, your family, your people, the town, then start the seven years.
import React, { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { go, useStore, PLACE } from "../store";
import { Modal, Panel, Tag, cx } from "../ui";
import CharacterBuilder, {
  COLORS, GRADE_LABEL, Person, PersonAvatar, SPORTS, Seg, Target, archLabel, cap, cleanPerson, displayName, friendlyError, heightLabel,
  randomName, relSentence, sectionForError, strengthWords, summaryLine, useStoryCatalog, yearLabel,
} from "../components/CharacterBuilder";
import "./storynew.css";
import { DRAFT_KEY, Draft, Family, Problem, TEMPLATES, buildSpec, defaultDraft, familyLast, loadDraft, newSeed, parseErrors, specToDraft } from "../story/draft";

const STEPS: [string, string][] = [["welcome", "Welcome"], ["you", "You"], ["family", "Family"], ["people", "Your people"], ["town", "The town"], ["review", "Review & start"]];
// ------------------------------------------------------------------ page
export default function StoryNew(_props: { route?: string[] }) {
  const { cat, error: catErr } = useStoryCatalog();
  const { world, refresh, bump, toast } = useStore();
  const [carry, setCarry] = useState(true);
  const [gwCount, setGwCount] = useState(0);
  useEffect(() => {
    if ((world as any)?.protagonist) api.get("/api/story/groundwork").then((g: any) => setGwCount(g.count || 0)).catch(() => setGwCount(0));
  }, [(world as any)?.protagonist]); // eslint-disable-line react-hooks/exhaustive-deps
  const [d, setD] = useState<Draft>(loadDraft);
  const [editing, setEditing] = useState<{ kind: "sibling" | "cast"; key: string; section?: string } | null>(null);
  const [youSection, setYouSection] = useState("basics");
  const [check, setCheck] = useState<{ status: "idle" | "checking" | "ok" | "bad"; errors: string[]; sibOrder: string[] }>({ status: "idle", errors: [], sibOrder: [] });
  const [starting, setStarting] = useState(false);
  const [nudge, setNudge] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    try {
      window.localStorage.setItem(DRAFT_KEY, JSON.stringify(d));
    } catch {
      /* storage unavailable */
    }
  }, [d]);

  const update = (patch: Partial<Draft>) => setD((x) => ({ ...x, ...patch }));
  const setStep = (i: number) => {
    setNudge(null);
    update({ step: i });
    document.querySelector(".content")?.scrollTo({ top: 0 });
  };
  const { spec, sibOrder } = useMemo(() => buildSpec(d), [d]);
  const specJson = JSON.stringify(spec);

  const problems = useMemo(() => (check.status === "bad" ? parseErrors(check.errors, check.sibOrder, d.cast) : []), [check, d.cast]);
  const errsFor = (who: string) => problems.filter((p) => p.who === who).map((p) => p.msg);
  const stepErrs = (step: string) => {
    if (step === "you") return errsFor("me").length;
    if (step === "family") return problems.filter((p) => p.who === "family" || d.siblings.some((s) => s.key === p.who)).length;
    if (step === "people") return problems.filter((p) => p.who === "people" || d.cast.some((c) => c.key === p.who)).length;
    if (step === "town") return errsFor("town").length;
    return 0;
  };

  const validate = async (s = spec, order = sibOrder) => {
    setCheck((c) => ({ ...c, status: "checking" }));
    try {
      await api.post("/api/story/validate", { spec: s });
      setCheck({ status: "ok", errors: [], sibOrder: order });
      return true;
    } catch (e: any) {
      setCheck({ status: "bad", errors: e.errors?.length ? e.errors : [e.message], sibOrder: order });
      return false;
    }
  };
  // keep the review step's check live
  useEffect(() => {
    if (d.step !== 5) return;
    const t = setTimeout(() => validate(), 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d.step, specJson]);

  const start = async () => {
    if (!(await validate())) {
      toast("A few things need fixing first. They're listed on the review page.", "warn");
      return;
    }
    setStarting(true);
    try {
      const bring = carry && gwCount > 0;
      const r: any = await api.post("/api/story/new", { spec, carry: bring });
      await refresh();
      bump();
      toast(`${spec.title} begins. First day of school.` + (bring && r?.carried?.done ? ` ${r.carried.done} of your changes came along.` : ""), "good");
      go("story");
    } catch (e: any) {
      if (e.errors?.length) setCheck({ status: "bad", errors: e.errors, sibOrder });
      toast(e.message || "Couldn't start the story", "bad");
    } finally {
      setStarting(false);
    }
  };

  const download = () => {
    const blob = new Blob([JSON.stringify({ format: "lifeos-story", version: 1, spec }, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    const name = (spec.title || "my-story").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    a.download = `${name || "my-story"}-cast.json`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      URL.revokeObjectURL(a.href);
      a.remove();
    }, 500);
  };
  const loadFile = async (f: File | undefined) => {
    if (!f) return;
    if (/\.lifeos$/i.test(f.name)) {  // a backup (from the phone, or a save): open the story itself, with its storylines
      if (fileRef.current) fileRef.current.value = "";
      if (hasStory && !window.confirm(`Open the story in ${f.name}? The story that's open now is kept under Saves & Worlds.`)) return;
      try {
        const res = await fetch("/api/phone/restore?keep=1", { method: "POST", body: await f.arrayBuffer(), headers: { "Content-Type": "application/octet-stream" } });
        const body = await res.json();
        if (!res.ok) throw new Error(body.detail || res.statusText);
        await refresh();
        bump();
        toast([`${body.title || "Your story"} is open, on ${body.date}.`, body.said].filter(Boolean).join(" "), "good");
        if (body.newer) toast(body.newer, "warn");
        go("story");
      } catch (e: any) {
        toast(`Couldn't open that backup: ${e.message}`, "bad");
      }
      return;
    }
    try {
      let j: any;
      if (/\.xlsx$/i.test(f.name)) {
        const res = await fetch("/api/story/import-sheet", { method: "POST", body: await f.arrayBuffer(), headers: { "Content-Type": "application/octet-stream" } });
        const body = await res.json();
        if (!res.ok) throw new Error([body.detail, ...(body.errors || [])].filter(Boolean).join(" · "));
        j = body;
      } else {
        const text = await f.text();
        const m = text.match(/\{[\s\S]*\}/);
        j = JSON.parse(m ? m[0] : text);
      }
      const s = j.spec || j;
      if (!s.protagonist) throw new Error("That file doesn't have a story cast in it.");
      setD(specToDraft(s));
      toast(`Loaded ${s.title || "the cast"}: ${1 + (s.siblings?.length || 0) + (s.cast?.length || 0)} people.`, "good");
    } catch (e: any) {
      toast(`Couldn't read that file: ${e.message}`, "bad");
    }
    if (fileRef.current) fileRef.current.value = "";
  };
  const startOver = () => {
    if (!window.confirm("Clear this setup and start over? (Download the cast first if you want to keep it.)")) return;
    setD(defaultDraft());
    setCheck({ status: "idle", errors: [], sibOrder: [] });
  };

  // people helpers
  const nextKey = (prefix: string) => {
    let n = d.seq;
    const used = new Set([...d.siblings, ...d.cast].map((p) => p.key));
    while (used.has(`${prefix}${n}`)) n++;
    return { key: `${prefix}${n}`, seq: n + 1 };
  };
  const pickColor = (i: number) => COLORS[(i * 5 + 3) % COLORS.length];
  const targets = (exclude?: string): Target[] => {
    const me: Target = { key: "me", name: d.protagonist.first?.trim() || "You", color: d.protagonist.color };
    const others = [...d.siblings, ...d.cast].filter((p) => p.key !== exclude).map((p, i) => ({ key: p.key!, name: displayName(p, `Person ${i + 1}`), color: p.color }));
    return [me, ...others];
  };
  const setSibling = (key: string, p: Person) => setD((x) => ({ ...x, siblings: x.siblings.map((s) => (s.key === key ? p : s)) }));
  const setCast = (key: string, p: Person) => setD((x) => ({ ...x, cast: x.cast.map((s) => (s.key === key ? p : s)) }));
  const removePerson = (key: string) =>
    setD((x) => {
      const strip = (p: Person) => ({ ...p, twin_of: p.twin_of === key ? undefined : p.twin_of, household: p.household === key ? undefined : p.household, relationships: (p.relationships || []).filter((r) => r.to !== key) });
      return { ...x, protagonist: strip(x.protagonist), siblings: x.siblings.filter((s) => s.key !== key).map(strip), cast: x.cast.filter((s) => s.key !== key).map(strip) };
    });

  if (catErr) return <div className="errorbox">Couldn't load the builder: {catErr}</div>;
  if (!cat || !world) return <div className="loading">Opening the character builder...</div>;

  const step = STEPS[d.step][0];
  const me = d.protagonist;
  const canNext = () => {
    if (step === "you" && !me.first?.trim()) return "Give yourself a first name to keep going.";
    if (step === "you" && !me.gender) return "Pick a gender to keep going.";
    return null;
  };
  const next = () => {
    const why = canNext();
    if (why) {
      setNudge(why);
      return;
    }
    setStep(Math.min(STEPS.length - 1, d.step + 1));
  };
  const editingPerson = editing ? (editing.kind === "sibling" ? d.siblings : d.cast).find((p) => p.key === editing.key) : null;
  const hasStory = !!(world as any).protagonist;

  return (
    <div className="sn">
      <div className="sn-head">
        <div>
          <div className="sn-kicker">New story</div>
          <h1>{d.title.trim() || (familyLast(d) ? `The ${familyLast(d)} Years` : "Build your story")}</h1>
        </div>
        <div className="row">
          <button className="small ghost" onClick={() => fileRef.current?.click()} title="Load people you saved before, or open a backup from the phone (.lifeos)">Load a cast file or backup</button>
          <button className="small ghost" onClick={download} title="Save everyone you've made to a file">Download cast</button>
          <input ref={fileRef} type="file" accept=".json,.xlsx,.txt,.lifeos,application/json" style={{ display: "none" }} onChange={(e) => loadFile(e.target.files?.[0])} />
        </div>
      </div>

      <div className="sn-steps">
        {STEPS.map(([k, l], i) => {
          const n = stepErrs(k);
          return (
            <button key={k} className={cx("sn-step", i === d.step && "on", i < d.step && "past")} onClick={() => (i <= d.step || !canNext() ? setStep(i) : setNudge(canNext()))}>
              <span className="sn-num">{i < d.step ? "✓" : i + 1}</span>
              <span className="sn-step-l">{l}</span>
              {n > 0 && <span className="cb-err-dot" title={`${n} thing${n > 1 ? "s" : ""} to fix`}>{n}</span>}
            </button>
          );
        })}
        <div className="sn-bar"><i style={{ width: `${(d.step / (STEPS.length - 1)) * 100}%` }} /></div>
      </div>

      <div className="sn-body">
        {step === "welcome" && <Welcome d={d} update={update} hasStory={hasStory} storyTitle={(world as any).story_title} onStartOver={startOver} onLoad={() => fileRef.current?.click()} />}
        {step === "you" && (
          <CharacterBuilder value={me} onChange={(p) => update({ protagonist: p })} cat={cat} mode="protagonist" people={targets().filter((t) => t.key !== "me")}
            errors={errsFor("me")} section={youSection} onSection={setYouSection} />
        )}
        {step === "family" && (
          <FamilyStep d={d} setD={setD} cat={cat} errsFor={errsFor} nextKey={nextKey} pickColor={pickColor}
            onEdit={(key, section) => setEditing({ kind: "sibling", key, section })} onRemove={removePerson} />
        )}
        {step === "people" && (
          <PeopleStep d={d} setD={setD} cat={cat} errsFor={errsFor} nextKey={nextKey} pickColor={pickColor}
            onEdit={(key, section) => setEditing({ kind: "cast", key, section })} onRemove={removePerson} />
        )}
        {step === "town" && <TownStep d={d} update={update} errs={errsFor("town")} />}
        {step === "review" && (
          <Review d={d} cat={cat} spec={spec} check={check} problems={problems} onFix={(who, msg) => {
            if (who === "me") { setYouSection(sectionForError(msg)); setStep(1); return; }
            if (who === "family") { setStep(2); return; }
            if (who === "people") { setStep(3); return; }
            if (who === "town") { setStep(4); return; }
            const sib = d.siblings.find((s) => s.key === who);
            if (sib) { setStep(2); setEditing({ kind: "sibling", key: who, section: sectionForError(msg) }); return; }
            if (d.cast.some((c) => c.key === who)) { setStep(3); setEditing({ kind: "cast", key: who, section: sectionForError(msg) }); }
          }} onRecheck={() => validate()} onStart={start} starting={starting} onDownload={download} onLoad={() => fileRef.current?.click()} onStartOver={startOver} hasStory={hasStory} />
        )}
      </div>

      <div className="sn-foot">
        <button disabled={d.step === 0} onClick={() => setStep(d.step - 1)}>← Back</button>
        {nudge && <span className="sn-nudge">{nudge}</span>}
        <span className="spacer" />
        <span className="hint">Saved automatically in this browser.</span>
        {d.step < STEPS.length - 1 ? (
          <button className="primary" onClick={next}>{d.step === 0 ? "Let's build you →" : `Next: ${STEPS[d.step + 1][1]} →`}</button>
        ) : (
          <>
            {gwCount > 0 && (
              <label className="check" title="Who people are, people you added, relationships you set in the editor, who your storylines are about">
                <input type="checkbox" checked={carry} onChange={(e) => setCarry(e.target.checked)} /> Bring my changes from the story that's open ({gwCount})
              </label>
            )}
            <button className="primary sn-big" disabled={starting || check.status === "checking"} onClick={start}>{starting ? "Building your world..." : "Start my story"}</button>
          </>
        )}
      </div>

      {editing && editingPerson && (
        <Modal wide title={<span className="row" style={{ gap: 10 }}><PersonAvatar p={editingPerson} size={28} /> {displayName(editingPerson, editing.kind === "sibling" ? "Your sibling" : "New person")}</span>} onClose={() => setEditing(null)}>
          <CharacterBuilder value={editingPerson} cat={cat} mode={editing.kind} people={targets(editingPerson.key)}
            onChange={(p) => (editing.kind === "sibling" ? setSibling(editing.key, p) : setCast(editing.key, p))}
            errors={errsFor(editing.key)} section={editing.section || "basics"} onSection={(s) => setEditing({ ...editing, section: s })} />
          <div className="row" style={{ marginTop: 14, justifyContent: "flex-end" }}>
            <button className="primary" onClick={() => setEditing(null)}>Done</button>
          </div>
        </Modal>
      )}

      {starting && (
        <div className="sn-building">
          <div className="sn-building-b">
            <div className="sn-spinner" />
            <h2>Building {PLACE.town}</h2>
            <p>Your family, your people and about {d.students_per_grade * 4} classmates, each with their own personality, history and friendships.</p>
          </div>
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ welcome
function Welcome({ d, update, hasStory, storyTitle, onStartOver, onLoad }: any) {
  const started = d.protagonist.first?.trim() || d.siblings.length || d.cast.length;
  return (
    <div className="stack">
      {hasStory && (
        <div className="callout warn">
          <b>You already have a story going{storyTitle ? `: ${storyTitle}` : ""}.</b> Starting a new one replaces the current world. If you want to keep it, save it under <a href="#/saves">Saves &amp; Worlds</a> first, or go <a href="#/story">back to your story</a>.
        </div>
      )}
      {started ? (
        <div className="callout">
          <b>Your setup from last time is still here.</b> Pick up where you left off, or <button className="small" onClick={onStartOver}>start over</button>
        </div>
      ) : null}
      <div className="sn-welcome">
        <div className="sn-welcome-l">
          <h2>Seven years in {PLACE.town}</h2>
          <p className="muted">You start on the first day of high school. You live one life; everyone else lives theirs, making their own choices, friendships, rivalries and mistakes, whether you're watching or not.</p>
          <div className="sn-arc">
            <div><b>Years 1-4</b><span>High school. Tryouts, JV and varsity, classes, parties, dances, friends and the people you fall for.</span></div>
            <div><b>Senior year</b><span>Recruiting, offers, admissions letters, and a decision about what comes next.</span></div>
            <div><b>Years 5-7</b><span>College or work. New roommates, new teams, and coming home for the holidays.</span></div>
          </div>
          <div className="cb-field" style={{ marginTop: 18, maxWidth: 460 }}>
            <div className="cb-field-l">Name your story</div>
            <input type="text" value={d.title} maxLength={60} placeholder="The ____ Years" onChange={(e) => update({ title: e.target.value })} />
            <div className="hint">Optional. You can change it any time before you start.</div>
          </div>
        </div>
        <div className="sn-welcome-r">
          <div className="sn-plan">
            <div className="sn-plan-h">What you'll set up</div>
            {[
              ["1", "You", "Name, personality, talent, body, sports and positions."],
              ["2", "Family", "Parents, your household, brothers and sisters (twins too)."],
              ["3", "Your people", "Best friend, crush, rivals, teammates, coaches."],
              ["4", "The town", "How many generated classmates fill each grade."],
            ].map(([n, t, s]) => (
              <div key={n} className="sn-plan-i"><span className="sn-num">{n}</span><div><b>{t}</b><div className="hint">{s}</div></div></div>
            ))}
            <div className="hint" style={{ marginTop: 10 }}>Anything you skip is generated. Only first names are required.</div>
            <button className="small" style={{ marginTop: 10 }} onClick={onLoad}>Have a cast file or worksheet? Load it</button>
          </div>
          <PlanFirst />
        </div>
      </div>
    </div>
  );
}

function PlanFirst() {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      const r = await fetch("/api/story/worksheet-prompt");
      const { prompt } = await r.json();
      await navigator.clipboard.writeText(prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      window.open("/api/story/worksheet-guide", "_blank");
    }
  };
  return (
    <div className="sn-plan" style={{ marginTop: 12 }}>
      <div className="sn-plan-h">Want to plan it first?</div>
      <div className="hint">Fill out the worksheet, or talk it through with ChatGPT or Claude before you decide on numbers. Then load the file here.</div>
      <div className="row" style={{ marginTop: 10, flexWrap: "wrap", gap: 8 }}>
        <a className="btn small" href="/api/story/worksheet.xlsx">Excel worksheet</a>
        <button className="small" onClick={copy}>{copied ? "Copied! Paste it into ChatGPT" : "Copy the ChatGPT prompt"}</button>
        <a className="btn small ghost" href="/api/story/worksheet-guide?download=1">Full guide (.md)</a>
      </div>
      <div className="hint" style={{ marginTop: 8 }}>The AI gives you back a block of JSON. Save it as a .json (or .txt) file and load it with the button above.</div>
      <div className="hint" style={{ marginTop: 6 }}><b>Playing on your phone?</b> You can make your story right in the phone app (<i>Create my story</i>). Or build it here, use <i>Download cast</i> at the top, and load that file in the phone app.</div>
    </div>
  );
}

// ------------------------------------------------------------------ family
const INCOME: [string, string][] = [["low", "Tight budget"], ["middle", "Comfortable"], ["high", "Well-off"]];
function closeness(v: number) {
  if (v <= -25) return "Constant fights";
  if (v < -5) return "Get on each other's nerves";
  if (v < 8) return "Normal siblings";
  if (v < 25) return "Pretty close";
  return "Super close";
}

function FamilyStep({ d, setD, cat, errsFor, nextKey, pickColor, onEdit, onRemove }: any) {
  const f: Family = d.family;
  const me: Person = d.protagonist;
  const last = familyLast(d);
  const setF = (patch: Partial<Family>) => setD((x: Draft) => ({ ...x, family: { ...x.family, ...patch } }));
  const add = (people: Partial<Person>[]) =>
    setD((x: Draft) => {
      let seq = x.seq;
      const used = new Set([...x.siblings, ...x.cast].map((p) => p.key));
      const made: Person[] = [];
      for (const [i, p] of people.entries()) {
        while (used.has(`sib${seq}`)) seq++;
        const key = `sib${seq}`;
        used.add(key);
        seq++;
        const twin = (p as any)._twinPrev ? made[i - 1]?.key : p.twin_of;
        const q: any = { first: "", gender: "m", grade: 10, color: pickColor(x.siblings.length + i + 1), ...p, key, twin_of: twin };
        delete q._twinPrev;
        made.push(q);
      }
      return { ...x, siblings: [...x.siblings, ...made], seq };
    });
  const used = new Set<string>([me.first, ...d.siblings.map((s: Person) => s.first)].filter(Boolean));
  const fillNames = () =>
    setD((x: Draft) => ({ ...x, siblings: x.siblings.map((s) => (s.first?.trim() ? s : { ...s, first: randomName(cat, s.gender || "m", used) })) }));
  const setSib = (key: string, patch: Partial<Person>) =>
    setD((x: Draft) => {
      let sibs = x.siblings.map((s) => (s.key === key ? { ...s, ...patch } : s));
      const cur = sibs.find((s) => s.key === key)!;
      if ("twin_of" in patch && patch.twin_of) {
        const grade = patch.twin_of === "me" ? x.protagonist.grade || 9 : sibs.find((s) => s.key === patch.twin_of)?.grade;
        sibs = sibs.map((s) => (s.key === key ? { ...s, grade } : s.key === patch.twin_of && s.twin_of === key ? { ...s, twin_of: undefined } : s));
      }
      if ("grade" in patch) {
        // twins share a grade
        sibs = sibs.map((s) => (s.twin_of === key ? { ...s, grade: patch.grade } : s));
        if (cur.twin_of === "me" && patch.grade !== (x.protagonist.grade || 9)) sibs = sibs.map((s) => (s.key === key ? { ...s, twin_of: undefined } : s));
        if (cur.twin_of && cur.twin_of !== "me") sibs = sibs.map((s) => (s.key === cur.twin_of ? { ...s, grade: patch.grade } : s));
      }
      return { ...x, siblings: sibs };
    });
  const famErrs = errsFor("family");
  return (
    <div className="stack">
      <div className="grid g-fam">
        <Panel title="Your household" sub="Everyone here lives with you.">
          <div className="cb-fields">
            <div className="cb-field">
              <div className="cb-field-l">Family last name</div>
              <input type="text" value={f.last} maxLength={30} placeholder={me.last?.trim() || "Generated"} onChange={(e) => setF({ last: e.target.value })} />
            </div>
            <div className="cb-field">
              <div className="cb-field-l">Parents / guardians</div>
              <div className="cb-inline">
                <input type="text" value={f.guardians[0]} placeholder="First guardian" onChange={(e) => setF({ guardians: [e.target.value, f.guardians[1]] })} />
                <input type="text" value={f.guardians[1]} placeholder="Second (optional)" onChange={(e) => setF({ guardians: [f.guardians[0], e.target.value] })} />
              </div>
              <div className="hint">First names are fine; {last ? `"${last}" is added` : "the family name is added"}. Leave blank to generate.</div>
            </div>
            <div className="cb-field wide">
              <div className="cb-field-l">How they parent</div>
              <div className="sn-style-grid">
                {cat.guardian_styles.map((s: any) => (
                  <button key={s.id} type="button" className={cx("sn-style-card", f.style === s.id && "on")} onClick={() => setF({ style: s.id })}>
                    <b>{cap(s.id)}</b>
                    <span>{cap(s.label)}</span>
                    <div className="sn-style-bars">
                      <i title={`warmth ${s.warmth}`}><em style={{ width: `${s.warmth}%`, background: "var(--good)" }} /></i>
                      <i title={`strictness ${s.strictness}`}><em style={{ width: `${s.strictness}%`, background: "var(--warm)" }} /></i>
                      <i title={`expectations ${s.expectations}`}><em style={{ width: `${s.expectations}%`, background: "var(--accent-2)" }} /></i>
                    </div>
                  </button>
                ))}
              </div>
              <div className="hint">Bars: warmth, strictness, expectations. Strict parents ground you more; warm ones are a better safety net.</div>
            </div>
            <div className="cb-field">
              <div className="cb-field-l">Money at home</div>
              <Seg value={f.income} options={INCOME} onChange={(v) => setF({ income: v })} />
            </div>
            <div className="cb-field">
              <div className="cb-field-l">Family pet</div>
              <Seg small value={f.petMode} options={[["none", "No pet"], ["chance", "Leave to chance"], ["random", "Yes, surprise me"], ["pick", "We have..."]]} onChange={(v) => setF({ petMode: v })} />
              {f.petMode === "pick" && (
                <div className="cb-inline">
                  <select value={f.pet.species} onChange={(e) => setF({ pet: { ...f.pet, species: e.target.value } })}>
                    {["dog", "cat", "rabbit"].map((s) => <option key={s} value={s}>a {s}</option>)}
                  </select>
                  <input type="text" value={f.pet.name} maxLength={20} placeholder="named..." onChange={(e) => setF({ pet: { ...f.pet, name: e.target.value } })} />
                </div>
              )}
            </div>
          </div>
          {famErrs.length > 0 && <div className="errorbox">{famErrs.join("\n")}</div>}
        </Panel>
      </div>

      <Panel title="Brothers & sisters" sub={`Older siblings are already at ${PLACE.short} when you get there, and their friends already know who you are.`}
        actions={
          <>
            <button className="small" onClick={() => add([{ gender: "m", grade: 12, archetype: "athlete" }])}>+ Older brother (senior)</button>
            <button className="small" onClick={() => { const g = Math.min(12, (me.grade || 9) + 1); add([{ gender: "f", grade: g }, { gender: "f", grade: g, _twinPrev: true } as any]); }}>+ Twin sisters (a year older)</button>
            <button className="small" onClick={() => add([{ gender: "f", grade: Math.min(12, (me.grade || 9) + 1) }])}>+ Sister</button>
            <button className="small" onClick={() => add([{ gender: "m", grade: Math.min(12, (me.grade || 9) + 1) }])}>+ Brother</button>
          </>
        }>
        {d.siblings.length === 0 ? (
          <div className="sn-empty">
            <div style={{ fontSize: 28 }}>👨‍👩‍👧‍👦</div>
            <div>No siblings yet. Only child is a perfectly good story too.</div>
            <div className="hint">Use the buttons above. Older siblings are in high school (grades 9-12); younger ones (6-8) start high school as freshmen in a later year.</div>
          </div>
        ) : (
          <>
            <div className="sn-sib-grid">
              {d.siblings.map((s: Person) => {
                const pointer = d.siblings.find((o: Person) => o.twin_of === s.key);
                const errs = errsFor(s.key);
                const twinOpts: [string, string][] = [["", "Not a twin"]];
                if ((s.grade || 9) === (me.grade || 9) || s.twin_of === "me") twinOpts.push(["me", `Your twin`]);
                for (const o of d.siblings as Person[]) if (o.key !== s.key && o.twin_of !== s.key) twinOpts.push([o.key!, `${o.first?.trim() || "Sibling"}'s twin`]);
                return (
                  <div key={s.key} className={cx("sn-sib-card", errs.length && "has-err")}>
                    <div className="sn-sib-top">
                      <PersonAvatar p={{ ...s, last: s.last || last }} size={46} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="cb-inline">
                          <input type="text" value={s.first} placeholder="First name" maxLength={30} onChange={(e) => setSib(s.key!, { first: e.target.value })} />
                          <button className="small" title="Random name" onClick={() => setSib(s.key!, { first: randomName(cat, s.gender || "m", used) })}>🎲</button>
                        </div>
                        <div className="hint" style={{ marginTop: 3 }}>{yearLabel(s)} · {archLabel(cat, s.archetype)}{pointer ? ` · twin of ${pointer.first || "a sibling"}` : s.twin_of === "me" ? " · your twin" : ""}</div>
                      </div>
                      <button className="ghost small" title="Remove" onClick={() => onRemove(s.key)}>×</button>
                    </div>
                    <div className="sn-sib-row">
                      <Seg small value={s.gender} options={[["m", "Brother"], ["f", "Sister"], ["nb", "Sibling (nb)"]]} onChange={(v) => setSib(s.key!, { gender: v })} />
                    </div>
                    <div className="sn-sib-row">
                      <Seg small value={s.grade || 9} options={[9, 10, 11, 12, 8, 7, 6].map((g) => [g, GRADE_LABEL[g]])} onChange={(v) => setSib(s.key!, { grade: v })} />
                    </div>
                    <div className="sn-sib-row two">
                      <select value={s.archetype || ""} onChange={(e) => setSib(s.key!, { archetype: e.target.value || undefined })}>
                        <option value="">Type: surprise me</option>
                        {cat.archetypes.map((a: any) => <option key={a.id} value={a.id}>{a.label}</option>)}
                      </select>
                      <select value={pointer ? "" : s.twin_of || ""} disabled={!!pointer} onChange={(e) => setSib(s.key!, { twin_of: e.target.value || undefined })}>
                        {pointer ? <option value="">Twin of {pointer.first || "a sibling"}</option> : twinOpts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                      </select>
                    </div>
                    {(s.grade || 9) > (me.grade || 9) && (
                      <div className="sn-sib-row">
                        <select value={pathValue(s.path)} onChange={(e) => setSib(s.key!, { path: pathFromValue(e.target.value) })} title="Where they end up after high school">
                          <option value="">After high school: let it play out</option>
                          {(cat.colleges || []).filter((c: any) => !c.local).flatMap((c: any) => c.sports.map((sp: string) => (
                            <option key={`${c.id}:${sp}`} value={`${c.id}:${sp}`}>Play {sp} at {c.short}</option>
                          )))}
                          {(cat.colleges || []).map((c: any) => <option key={`${c.id}:`} value={`${c.id}:`}>Go to {c.short} as a student</option>)}
                          <option value="work">Stay in town and work</option>
                        </select>
                      </div>
                    )}
                    <div className="sn-sib-close">
                      <div className="row between"><span className="cb-field-l">How you two get along</span><b className="small">{closeness(s.strength || 0)}</b></div>
                      <input type="range" className="slider" min={-40} max={40} value={s.strength || 0} onChange={(e) => setSib(s.key!, { strength: Number(e.target.value) })} />
                    </div>
                    {errs.length > 0 && <div className="errorbox small">{errs.join("\n")}</div>}
                    <button className="cb-link small" onClick={() => onEdit(s.key, errs.length ? sectionForError(errs[0]) : "basics")}>Customize everything →</button>
                  </div>
                );
              })}
            </div>
            {d.siblings.some((s: Person) => !s.first?.trim()) && (
              <div className="row" style={{ marginTop: 10 }}>
                <span className="hint">Some siblings don't have names yet.</span>
                <button className="small" onClick={fillNames}>🎲 Name them for me</button>
              </div>
            )}
          </>
        )}
      </Panel>
    </div>
  );
}

function pathValue(p: Person["path"]) {
  if (!p) return "";
  if (p.kind === "work") return "work";
  return `${p.college}:${p.sport || ""}`;
}
function pathFromValue(v: string): Person["path"] {
  if (!v) return null;
  if (v === "work") return { kind: "work" };
  const [college, sport] = v.split(":");
  return { kind: "college", college, sport: sport || null };
}

// ------------------------------------------------------------------ your people
function relToMe(p: Person, meName: string) {
  const r = (p.relationships || []).find((x) => x.to === "me");
  if (!r) return p.role === "staff" ? (p.coach_of ? `Coaches ${p.coach_of}` : "Works at the school") : "Starts out however the generator decides";
  const s = relSentence(r.type, p.first?.trim() || "They", "you");
  return `${s}${r.strength ? `, ${strengthWords(r.strength)}` : ""}`;
}

function PeopleStep({ d, setD, cat, errsFor, nextKey, pickColor, onEdit, onRemove }: any) {
  const me: Person = d.protagonist;
  const add = (tid: string) => {
    const t = TEMPLATES.find((x) => x.id === tid)!;
    const { key, seq } = nextKey("p");
    const p: Person = { first: "", gender: "m", grade: me.grade || 9, color: pickColor(d.cast.length + 7), ...t.make(me, d), key, template: t.label } as Person;
    setD((x: Draft) => ({ ...x, cast: [...x.cast, p], seq }));
    onEdit(key, "basics");
  };
  const students = d.cast.filter((c: Person) => c.role !== "staff");
  return (
    <div className="stack">
      <Panel title="Your people" sub="The people you want in your story. Each one is a full person with a life of their own; you decide where they start, not where they end up.">
        <div className="sn-tmpl-row">
          {TEMPLATES.map((t) => (
            <button key={t.id} className="sn-tmpl" onClick={() => add(t.id)}>
              <span className="sn-tmpl-i">{t.icon}</span>
              <span>{t.label}</span>
            </button>
          ))}
        </div>
        {d.cast.length === 0 ? (
          <div className="sn-empty">
            <div>Nobody yet. Add a best friend, a crush, a rival, a coach...</div>
            <div className="hint">You can add up to 40. Everyone else at {PLACE.short} is generated, and they all know each other in their own ways.</div>
          </div>
        ) : (
          <div className="sn-cast-grid">
            {d.cast.map((c: Person) => {
              const errs = errsFor(c.key);
              return (
                <div key={c.key} className={cx("sn-cast-card", errs.length && "has-err")} onClick={() => onEdit(c.key, errs.length ? sectionForError(errs[0]) : undefined)}>
                  <div className="row" style={{ flexWrap: "nowrap", alignItems: "flex-start" }}>
                    <PersonAvatar p={c} size={46} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="sn-cast-name">{displayName(c, "Needs a name")}{c.template && <Tag tone="dim">{c.template}</Tag>}</div>
                      <div className="hint">{yearLabel(c)}{c.role !== "staff" ? ` · ${archLabel(cat, c.archetype)}` : ""}{c.body?.height_in ? ` · ${heightLabel(c.body.height_in)}` : ""}</div>
                    </div>
                    <button className="ghost small" title="Remove" onClick={(e) => { e.stopPropagation(); onRemove(c.key); }}>×</button>
                  </div>
                  <div className="sn-cast-rel">{relToMe(c, me.first)}</div>
                  <div className="sn-cast-sum">{summaryLine(cat, c)}</div>
                  {c.role !== "staff" && students.length > 1 && (
                    <div className="row" onClick={(e) => e.stopPropagation()} style={{ gap: 6 }}>
                      <span className="hint">Lives with</span>
                      <select className="sn-small-select" value={c.household || ""} onChange={(e) => setD((x: Draft) => ({ ...x, cast: x.cast.map((y) => (y.key === c.key ? { ...y, household: e.target.value || undefined } : y)) }))}>
                        <option value="">their own family</option>
                        {students.filter((o: Person) => o.key !== c.key && o.household !== c.key).map((o: Person) => <option key={o.key} value={o.key}>{o.first?.trim() || "someone"}'s family (siblings)</option>)}
                      </select>
                    </div>
                  )}
                  {errs.length > 0 && <div className="errorbox small">{errs.join("\n")}</div>}
                  <div className="sn-cast-edit">Edit everything →</div>
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
}

// ------------------------------------------------------------------ town
function TownStep({ d, update, errs }: { d: Draft; update: (p: Partial<Draft>) => void; errs: string[] }) {
  const per = d.students_per_grade;
  const custom: Record<number, number> = { 9: 0, 10: 0, 11: 0, 12: 0 };
  for (const p of [d.protagonist, ...d.siblings, ...d.cast.filter((c) => c.role !== "staff")]) custom[p.grade || 9] = (custom[p.grade || 9] || 0) + 1;
  return (
    <div className="grid g2">
      <Panel title={PLACE.school} sub="Generated students fill out each grade around the people you made.">
        <div className="sn-town-big"><b>{per}</b><span>students per grade</span></div>
        <input type="range" className="slider" min={6} max={40} value={per} onChange={(e) => update({ students_per_grade: Number(e.target.value) })} />
        <div className="row between hint"><span>6 · small and tight-knit</span><span>40 · big and busy (slower)</span></div>
        <div className="sn-town-grades">
          {[9, 10, 11, 12].map((g) => {
            const mine = custom[g];
            const gen = Math.max(0, per - mine);
            return (
              <div key={g} className="sn-town-g">
                <b>{GRADE_LABEL[g]}s</b>
                <div className="sn-town-dots">
                  {Array.from({ length: mine }).map((_, i) => <i key={"m" + i} className="mine" />)}
                  {Array.from({ length: gen }).map((_, i) => <i key={"g" + i} />)}
                </div>
                <span className="hint">{mine} yours · {gen} generated</span>
              </div>
            );
          })}
        </div>
        <div className="hint" style={{ marginTop: 10 }}>More students means a richer social world but slower days. 10-14 is a good middle. Roughly {per * 4} students in all, plus teachers and coaches.</div>
        {errs.length > 0 && <div className="errorbox">{errs.join("\n")}</div>}
      </Panel>
      <Panel title="Seeds" sub={`Seeds make the world reproducible: the same setup and seeds give you the same ${PLACE.town} every time.`}>
        <div className="cb-fields">
          <div className="cb-field wide">
            <div className="cb-field-l">World seed</div>
            <div className="cb-inline">
              <input type="number" value={d.gen_seed} min={1} placeholder="random" onChange={(e) => update({ gen_seed: e.target.value === "" ? "" : Math.max(1, Math.round(Number(e.target.value))) })} />
              <button onClick={() => update({ gen_seed: newSeed() })}>🎲 New world</button>
            </div>
            <div className="hint">Decides who the generated students are and how everyone starts out.</div>
          </div>
          <div className="cb-field wide">
            <div className="cb-field-l">Simulation seed <span className="hint">optional</span></div>
            <div className="cb-inline">
              <input type="number" value={d.sim_seed} min={1} placeholder="derived from the world seed" onChange={(e) => update({ sim_seed: e.target.value === "" ? "" : Math.max(1, Math.round(Number(e.target.value))) })} />
              {d.sim_seed !== "" && <button className="ghost small" onClick={() => update({ sim_seed: "" })}>clear</button>}
            </div>
            <div className="hint">Decides how the days play out. Same world, different seed: a different seven years.</div>
          </div>
        </div>
      </Panel>
    </div>
  );
}

// ------------------------------------------------------------------ review
function MiniPerson({ p, cat, sub, errs, onClick, last }: { p: Person; cat: any; sub?: string; errs?: string[]; onClick?: () => void; last?: string }) {
  return (
    <div className={cx("sn-mini-p", onClick && "clickable", errs?.length && "has-err")} onClick={onClick}>
      <PersonAvatar p={{ ...p, last: p.last || last }} size={38} />
      <div style={{ minWidth: 0 }}>
        <div className="sn-mini-n">{displayName(p, "Needs a name")}{p.last?.trim() || !last || p.role === "staff" ? "" : ` ${last}`}</div>
        <div className="hint">{yearLabel(p)}{p.role !== "staff" ? ` · ${archLabel(cat, p.archetype)}` : ""}</div>
        {sub && <div className="sn-mini-s">{sub}</div>}
      </div>
      {errs && errs.length > 0 && <span className="cb-err-dot">{errs.length}</span>}
    </div>
  );
}

function Review({ d, cat, spec, check, problems, onFix, onRecheck, onStart, starting, onDownload, onLoad, onStartOver, hasStory }: any) {
  const me: Person = d.protagonist;
  const last = familyLast(d);
  const f: Family = d.family;
  const styleLabel = cat.guardian_styles.find((s: any) => s.id === f.style)?.label || f.style;
  const errsFor = (who: string) => problems.filter((p: Problem) => p.who === who).map((p: Problem) => p.msg);
  const plays = SPORTS.filter((s) => me.positions?.[s] || (me.interests?.[s] ?? 0) >= 40);
  const nameOf = (k: string) => {
    if (k === "me") return "you";
    const p: Person | undefined = [...d.siblings, ...d.cast].find((x: Person) => x.key === k);
    if (!p) return k;
    return p.first?.trim() || (p.template ? `Your ${p.template.toLowerCase()}` : d.siblings.includes(p) ? "A sibling" : "Someone");
  };
  return (
    <div className="stack">
      <div className="sn-review-hero" style={{ ["--c" as any]: me.color || "#57d9c3" }}>
        <PersonAvatar p={{ ...me, last: me.last || last }} size={84} glow />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="sn-kicker">Starring</div>
          <h2>{me.first?.trim() || "You"} {me.last?.trim() || last}</h2>
          <div className="muted">{yearLabel(me)} at {PLACE.short} · {archLabel(cat, me.archetype)}{me.body?.height_in ? ` · ${heightLabel(me.body.height_in)}` : ""}{me.body?.build ? ` ${me.body.build}` : ""}{me.jersey !== undefined && me.jersey !== null && String(me.jersey) !== "" ? ` · #${me.jersey}` : ""}</div>
          <div className="sn-review-sum">{summaryLine(cat, me)}</div>
          {plays.length > 0 && (
            <div className="chips" style={{ marginTop: 8 }}>
              {plays.map((s) => <Tag key={s} tone="accent">{cat.sports[s].label}{me.positions?.[s] ? ` · ${cat.sports[s].positions[me.positions[s]]}` : ""}</Tag>)}
            </div>
          )}
        </div>
        <button onClick={() => onFix("me", "basics")}>Edit you</button>
      </div>

      <div className="sn-review-check">
        {check.status === "checking" && <div className="callout">Checking everything...</div>}
        {check.status === "ok" && <div className="callout ok"><b>✓ Everything checks out.</b> {1 + d.siblings.length + d.cast.length} people you made, about {d.students_per_grade * 4 - 1 - d.siblings.length - d.cast.filter((c: Person) => c.role !== "staff").length} generated classmates.</div>}
        {check.status === "bad" && (
          <div className="callout warn">
            <b>A few things to fix before you start:</b>
            <div className="sn-fix-list">
              {problems.map((p: Problem, i: number) => (
                <div key={i} className="sn-fix">
                  <span><b>{p.who === "me" ? "You" : ["family", "people", "town", "other"].includes(p.who) ? cap(p.who) : nameOf(p.who) || "Someone"}:</b> {p.msg}</span>
                  {p.who !== "other" && <button className="small" onClick={() => onFix(p.who, p.msg)}>Fix</button>}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="grid g2">
        <Panel title={`The ${last || "family"} household`} sub={`${cap(styleLabel)} · ${INCOME.find((x) => x[0] === f.income)?.[1] || f.income}${f.petMode === "pick" && f.pet.name ? ` · ${f.pet.name} the ${f.pet.species}` : f.petMode === "random" ? " · a pet" : ""}`}
          actions={<button className="small" onClick={() => onFix("family", "")}>Edit</button>}>
          <div className="hint" style={{ marginBottom: 8 }}>Parents: {spec.family.guardians?.join(" & ") || "generated"}</div>
          {d.siblings.length ? (
            <div className="sn-mini-grid">
              {d.siblings.map((s: Person) => {
                const pointer = d.siblings.find((o: Person) => o.twin_of === s.key);
                const twin = s.twin_of === "me" ? "your twin" : s.twin_of ? `${nameOf(s.twin_of)}'s twin` : pointer ? `${pointer.first || "a sibling"}'s twin` : "";
                return <MiniPerson key={s.key} p={s} cat={cat} last={last} errs={errsFor(s.key)} sub={[twin, closeness(s.strength || 0)].filter(Boolean).join(" · ")} onClick={() => onFix(s.key, errsFor(s.key)[0] || "basics")} />;
              })}
            </div>
          ) : <div className="dim">No siblings.</div>}
        </Panel>
        <Panel title="Your people" sub={d.cast.length ? `${d.cast.length} ${d.cast.length === 1 ? "person" : "people"}` : "Nobody added; everyone is generated."} actions={<button className="small" onClick={() => onFix("people", "")}>Edit</button>}>
          {d.cast.length ? (
            <div className="sn-mini-grid">
              {d.cast.map((c: Person) => <MiniPerson key={c.key} p={c} cat={cat} errs={errsFor(c.key)} sub={relToMe(c, me.first)} onClick={() => onFix(c.key, errsFor(c.key)[0] || "basics")} />)}
            </div>
          ) : <div className="dim">You'll meet people as you go.</div>}
        </Panel>
      </div>

      <Panel title="The town" actions={<button className="small" onClick={() => onFix("town", "")}>Edit</button>}>
        <div className="row" style={{ gap: 24 }}>
          <span><b>{d.students_per_grade}</b> <span className="muted">students per grade</span></span>
          <span><span className="muted">world seed</span> <b>{spec.gen_seed ?? "random"}</b></span>
          <span><span className="muted">simulation seed</span> <b>{spec.sim_seed ?? "from the world seed"}</b></span>
          <span className="spacer" />
          <button className="small ghost" onClick={onRecheck}>Check again</button>
        </div>
      </Panel>

      <div className="sn-review-go">
        <div>
          <h3>Ready?</h3>
          <div className="muted">Day one: the first day of {GRADE_LABEL[me.grade || 9].toLowerCase()} year. {hasStory ? "This replaces the world that's running now." : ""}</div>
        </div>
        <div className="row">
          <button onClick={onDownload} title="Save everyone you made to a file you can load again later">Download this cast (.json)</button>
          <button onClick={onLoad}>Load a cast file or a phone backup</button>
          <button className="ghost" onClick={onStartOver}>Start over</button>
          <button className="primary sn-big" disabled={starting || check.status === "checking"} onClick={onStart}>{starting ? "Building..." : "Start my story"}</button>
        </div>
      </div>
    </div>
  );
}
