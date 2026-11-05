// The rest of the full editor: what the story builder sets when you make someone (gender, who they're into, birthday,
// type, height and build, sports and jersey, what's next after high school), changeable any time, and adding someone new.
import React, { useState } from "react";
import { ARCH_BLURB, BUILD_HINT, SEASON, archLabel, cap, heightLabel, sportsFor, useStoryCatalog } from "../components/CharacterBuilder";
import { EdPerson, phoneApi, pgo } from "./api";
import { Field, Fold, Seg, Slider } from "./CreateStory";
import { cx, errText } from "./kit";
import { usePhone } from "./PhoneContext";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTH_DAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
const GENDER: [string, string][] = [["f", "Girl"], ["m", "Guy"], ["nb", "Nonbinary"]];
const INTO: [string, string][] = [["f", "Girls"], ["m", "Guys"], ["both", "Both"], ["all", "Anyone"], ["none", "No one"]];

function intoOf(a: string[] | undefined): string {
  const k = [...(a || [])].sort().join(",");
  return k === "f" ? "f" : k === "m" ? "m" : k === "f,m" ? "both" : k === "f,m,nb" ? "all" : k === "" ? "none" : "all";
}
const INTO_LIST: Record<string, string[]> = { f: ["f"], m: ["m"], both: ["f", "m"], all: ["f", "m", "nb"], none: [] };
// who a new person is to you (the builder's relationships, from your side)
const TO_ME: [string, string][] = [["friend", "A friend"], ["close_friend", "A close friend"], ["best_friend", "Your best friend"],
  ["acquaintance", "Someone you know"], ["teammate", "Grew up on your teams"], ["neighbor", "Your neighbor"], ["crush", "Has a crush on you"],
  ["admirer", "You have a crush on them"], ["mutual_crush", "You like each other"], ["dating", "Dating you"], ["ex", "Your ex"],
  ["rival", "Your rival"], ["enemy", "Can't stand you"], ["mentor", "Looks up to you"]];

type Val = (layer: string, key: string | null) => any;
type Put = (layer: string, key: string | null, v: any) => void;

/** Who they are: gender, pronouns, who they're into, birthday, type. */
export function WhoFold({ p, val, put }: { p: EdPerson; val: Val; put: Put }) {
  const { cat } = useStoryCatalog();
  const gender = val("gender", null);
  const bd: number[] = val("birthday", null) || [9, 1];
  const into = intoOf(val("attracted_to", null));
  return (
    <Fold title="Who they are" sub={[GENDER.find(([k]) => k === gender)?.[1], `into ${INTO.find(([k]) => k === into)?.[1].toLowerCase()}`,
      `${MONTHS[bd[0] - 1]} ${bd[1]}`].filter(Boolean).join(" · ")}>
      <Field label="Gender">
        <Seg value={gender} options={GENDER} onChange={(v) => put("gender", null, v)} />
      </Field>
      <Field label="Pronouns" hint="Changing gender sets these; change them here if you want something else.">
        <input className="ph-input" value={val("pronouns", null) || ""} maxLength={20} onChange={(e) => put("pronouns", null, e.target.value)} />
      </Field>
      <Field label={p.is_me ? "You're into" : "Into"} hint="Who they can have a crush on, date, or ask to a dance. Family and teachers never.">
        <Seg value={into} options={INTO} wrap onChange={(v) => put("attracted_to", null, INTO_LIST[v])} />
      </Field>
      <Field label="Birthday">
        <div className="ed-bd">
          <select className="ph-input" value={bd[0]} onChange={(e) => put("birthday", null, [Number(e.target.value), Math.min(bd[1], MONTH_DAYS[Number(e.target.value) - 1])])}>
            {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          </select>
          <select className="ph-input" value={bd[1]} onChange={(e) => put("birthday", null, [bd[0], Number(e.target.value)])}>
            {Array.from({ length: MONTH_DAYS[bd[0] - 1] }, (_, i) => <option key={i} value={i + 1}>{i + 1}</option>)}
          </select>
        </div>
      </Field>
      {cat && !p.staff && (
        <Field label="Type" hint={ARCH_BLURB[val("archetype", null)] || "The kind of kid they are. It's a label: the sliders below are who they really are."}>
          <div className="ed-chips">
            {cat.archetypes.map((a: any) => (
              <button key={a.id} type="button" className={cx(val("archetype", null) === a.id && "on")} onClick={() => put("archetype", null, a.id)}>
                {archLabel(cat, a.id)}
              </button>
            ))}
          </div>
        </Field>
      )}
    </Fold>
  );
}

const FLIRT: [string, string][] = [["1", "Loves it"], ["0", "It's fine"], ["-1", "Not into it"]];

/** What works when you flirt with them: each style, from their personality unless you set it. */
export function FlirtFold({ p, val, put }: { p: EdPerson; val: Val; put: Put }) {
  if (!p.flirt) return null;
  const now = (s: { style: string; value: number; personality: number; set: boolean }) => {
    const v = val("flirt", null)?.[s.style];
    return v === undefined ? s.value : v === null ? s.personality : Number(v);
  };
  const mine = (s: { style: string; set: boolean }) => {
    const v = val("flirt", null)?.[s.style];
    return v === undefined ? s.set : v !== null;
  };
  const loves = p.flirt.styles.filter((s) => now(s) === 1).map((s) => s.label.toLowerCase());
  const any = p.flirt.styles.some(mine);
  return (
    <Fold title="Flirting" sub={loves.length ? `Loves ${loves.join(" and ")}` : "Nothing in particular"}>
      <p className="ph-dim small ed-flirt-hint">
        What works when you flirt with {p.first}: what lands, gets a laugh, or falls flat. It starts from their personality; set any of it
        and that's how it goes. What you've already figured out about them updates too.
      </p>
      {p.flirt.styles.map((s) => (
        <Field key={s.style} label={s.label} right={<small className="ed-flirt-src">{mine(s) ? "set by you" : "their personality"}</small>}>
          <Seg value={String(now(s))} options={FLIRT} onChange={(v) => put("flirt", s.style, Number(v))} />
        </Field>
      ))}
      {any && (
        <button type="button" className="ph-btn soft block" onClick={() => put("flirt", null, Object.fromEntries(p.flirt!.styles.map((s) => [s.style, null])))}>
          Back to their personality
        </button>
      )}
    </Fold>
  );
}

/** Height, build, jersey, and which sports they play (a position) or don't. */
export function BodyFold({ p, val, put }: { p: EdPerson; val: Val; put: Put }) {
  const { cat } = useStoryCatalog();
  if (!cat) return null;
  const body = val("body", null) || {};
  const pos: Record<string, string | null> = val("positions", null) || {};
  const h = body.height_in;
  const defH = val("gender", null) === "f" ? 64 : 69;
  const setBody = (patch: any) => put("body", null, { ...body, ...patch });
  const plays = Object.entries(pos).filter(([, v]) => v).map(([s, v]) => `${cap(s)} (${v})`);
  return (
    <Fold title="Body and sports" sub={[h ? heightLabel(h) : null, body.build ? cap(body.build) : null, plays.join(", ") || "No position set"].filter(Boolean).join(" · ")}>
      <Slider label="Height" value={h || defH} auto={!h} min={58} max={84} show={heightLabel(h || defH)}
        onChange={(x) => setBody({ height_in: x })} onAuto={() => setBody({ height_in: null })} left={`4'10"`} rightWord={`7'0"`} />
      <div className="cs-field-l" style={{ marginTop: 10 }}><span>Build</span>{!body.build && <em className="cs-auto">auto</em>}</div>
      <div className="cs-builds">
        {cat.builds.map((b: string) => (
          <button key={b} type="button" className={cx(body.build === b && "on")} onClick={() => setBody({ build: body.build === b ? null : b })}>
            <b>{cap(b)}</b>
            <span>{BUILD_HINT[b]}</span>
          </button>
        ))}
      </div>
      {!p.staff && (
        <>
          <Field label="Jersey number">
            <input className="ph-input cs-num" type="number" inputMode="numeric" min={0} max={99} value={val("jersey", null) ?? ""} placeholder="Any"
              onChange={(e) => put("jersey", null, e.target.value === "" ? null : Math.max(0, Math.min(99, Math.round(Number(e.target.value)))))} />
          </Field>
          <div className="cs-field-l" style={{ marginTop: 10 }}><span>Position, sport by sport</span></div>
          <p className="ph-dim small ph-tight">A position is the spot they play when they make the team (tryouts and the coach still decide who's on it).</p>
          {sportsFor(val("gender", null)).map((s) => {
            const sp = cat.sports[s];
            if (!sp?.positions) return null;
            return (
              <div key={s} className="ed-sport">
                <b>{sp.label} <small>{SEASON[sp.season] || sp.season}</small></b>
                <div className="ed-chips">
                  <button type="button" className={cx(!pos[s] && "on")} onClick={() => put("positions", null, { ...pos, [s]: null })}>None</button>
                  {Object.entries(sp.positions).map(([k, label]: any) => (
                    <button key={k} type="button" title={label} className={cx(pos[s] === k && "on")} onClick={() => put("positions", null, { ...pos, [s]: k })}>{k}</button>
                  ))}
                </div>
              </div>
            );
          })}
        </>
      )}
    </Fold>
  );
}

/** After high school: let it play out, college (maybe to play a sport), or work. */
export function NextFold({ p, val, put }: { p: EdPerson; val: Val; put: Put }) {
  const { cat } = useStoryCatalog();
  if (!cat || p.staff) return null;
  const path = val("path", null) || {};
  const mode = !path.kind && !path.college ? "auto" : path.kind === "work" ? "work" : "college";
  const cols = [...(cat.colleges || [])].sort((a: any, b: any) => String(a.name).localeCompare(String(b.name)));
  const col = cols.find((c: any) => c.id === path.college);
  return (
    <Fold title="After high school" sub={mode === "auto" ? "Let it play out" : mode === "work" ? "Straight to work" : `${col?.short || col?.name || "College"}${path.sport ? ` · ${path.sport}` : ""}`}>
      <Seg value={mode} options={[["auto", "Let it play out"], ["college", "College"], ["work", "Work"]]}
        onChange={(v) => put("path", null, v === "auto" ? null : v === "work" ? { kind: "work" } : { kind: "college", college: path.college || cols[0]?.id })} />
      {mode === "college" && (
        <>
          <Field label="Where">
            <select className="ph-input" value={path.college || ""} onChange={(e) => put("path", null, { kind: "college", college: e.target.value })}>
              {cols.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </Field>
          <Field label="To play a sport there?" hint="Only sports that school has a team for work.">
            <select className="ph-input" value={path.sport || ""} onChange={(e) => put("path", null, { kind: "college", college: path.college, sport: e.target.value || undefined })}>
              <option value="">No, just school</option>
              {sportsFor(val("gender", null)).map((s) => <option key={s} value={s}>{cat.sports[s]?.label || cap(s)}</option>)}
            </select>
          </Field>
        </>
      )}
    </Fold>
  );
}

/** Someone new, mid-story: the basics, then you're on their page to set everything else. */
export function AddSomeone({ onDone }: { onDone: () => void }) {
  const { toast, refresh } = usePhone();
  const { cat } = useStoryCatalog();
  const [f, setF] = useState<any>({ first: "", last: "", gender: "f", kind: "student", grade: 9, to_me: "", archetype: "" });
  const [busy, setBusy] = useState(false);
  const set = (x: any) => setF((o: any) => ({ ...o, ...x }));
  const add = async () => {
    setBusy(true);
    try {
      const body: any = { first: f.first, last: f.last, gender: f.gender, archetype: f.archetype || undefined, to_me: f.to_me || undefined };
      if (f.kind === "staff") body.role = "staff";
      else if (f.kind === "family") Object.assign(body, { grade: f.grade, family: true });
      else body.grade = f.grade;
      const r = await phoneApi.editorNew(body);
      toast(`${r.name} is in your world.`, "good");
      refresh();
      onDone();
      pgo(`edit/${encodeURIComponent(r.id)}`);
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="ed-new">
      <p className="ph-dim small">Add a new kid at school, a sibling, or a teacher or coach. Set the basics here; everything else (look,
        personality, sports...) is on their page right after.</p>
      <Field label="Name">
        <div className="ed-bd">
          <input className="ph-input" placeholder="First" value={f.first} maxLength={40} onChange={(e) => set({ first: e.target.value })} />
          <input className="ph-input" placeholder={f.kind === "family" ? "(your last name)" : "Last"} value={f.last} maxLength={40} disabled={f.kind === "family"}
            onChange={(e) => set({ last: e.target.value })} />
        </div>
      </Field>
      <Field label="Gender"><Seg value={f.gender} options={GENDER} onChange={(v) => set({ gender: v })} /></Field>
      <Field label="Who they are">
        <Seg value={f.kind} wrap options={[["student", "A student"], ["family", "My sibling"], ["staff", "Teacher or coach"]]} onChange={(v) => set({ kind: v })} />
      </Field>
      {f.kind !== "staff" && (
        <Field label="Grade">
          <Seg value={f.grade} options={[[9, "9th"], [10, "10th"], [11, "11th"], [12, "12th"]]} onChange={(v) => set({ grade: v })} />
        </Field>
      )}
      {f.kind !== "family" && (
        <Field label="To you">
          <select className="ph-input" value={f.to_me} onChange={(e) => set({ to_me: e.target.value })}>
            <option value="">Strangers for now</option>
            {TO_ME.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </Field>
      )}
      {cat && f.kind !== "staff" && (
        <Field label="Type">
          <div className="ed-chips">
            <button type="button" className={cx(!f.archetype && "on")} onClick={() => set({ archetype: "" })}>Surprise me</button>
            {cat.archetypes.map((a: any) => (
              <button key={a.id} type="button" className={cx(f.archetype === a.id && "on")} onClick={() => set({ archetype: a.id })}>{archLabel(cat, a.id)}</button>
            ))}
          </div>
        </Field>
      )}
      <button className="ph-btn primary block" disabled={busy || !f.first.trim()} onClick={add}>{busy ? "Adding…" : "Add them"}</button>
    </div>
  );
}
