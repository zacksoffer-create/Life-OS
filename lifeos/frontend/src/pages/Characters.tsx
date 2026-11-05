import React, { useMemo, useState } from "react";
import { api } from "../api";
import { go, useApi, useStore, PLACE } from "../store";
import {
  Avatar, Changes, Empty, ErrorBox, EventRow, Icon, Loading, Meter, Modal, Name, Panel, Signed, Slider, Stat, Tabs, Tag, cx, fmt, moodColor, pretty, signed,
} from "../ui";
import CharacterBuilder, { Person, Target, cleanPerson, heightLabel, sectionForError, useStoryCatalog } from "../components/CharacterBuilder";
import "./characters.css";

const TRAITS = ["sociability", "confidence", "discipline", "ambition", "impulsivity", "empathy", "competitiveness", "curiosity", "volatility", "loyalty"];
const APTS = ["athletic", "academic", "creativity", "technical", "charisma"];
const MOTIVES = ["achievement", "approval", "belonging", "pleasure", "altruism", "mastery"];
const NEEDS = ["energy", "social", "fun", "stress"];
const ARCHETYPES = ["athlete", "artist", "scholar", "socialite", "loner", "rebel", "leader", "techie", "performer", "caretaker", "drifter"];

export default function Characters({ route }: { route: string[] }) {
  const id = route[1];
  if (id) return <Detail id={id} />;
  return <List />;
}

// ------------------------------------------------------------------ list
function List() {
  const { charList } = useStore();
  const [q, setQ] = useState("");
  const [role, setRole] = useState("student");
  const [grade, setGrade] = useState("");
  const [sort, setSort] = useState("popularity");
  const [creating, setCreating] = useState(false);
  const list = useMemo(() => {
    let xs = charList.filter((c) => (role ? c.role === role : true) && (grade ? String(c.grade) === grade : true));
    if (q) {
      const ql = q.toLowerCase();
      xs = xs.filter((c) => (c.name + " " + c.archetype + " " + (c.clique?.name || "") + " " + c.bio + " " + c.memberships.map((m) => m.name).join(" ")).toLowerCase().includes(ql));
    }
    const key: Record<string, (c: any) => number> = {
      popularity: (c) => -c.popularity, mood: (c) => c.mood, stress: (c) => -c.stress, friends: (c) => -c.friends, name: () => 0, gpa: (c) => -c.gpa,
    };
    return [...xs].sort((a, b) => key[sort](a) - key[sort](b) || a.last.localeCompare(b.last));
  }, [charList, q, role, grade, sort]);
  return (
    <div className="stack">
      <div className="page-h">
        <div>
          <h1>Character Studio</h1>
          <p>Every person here makes their own choices. Open anyone to see who they are, what they want, how they see the people around them, and why they did what they did.</p>
        </div>
        <button className="primary" onClick={() => setCreating(true)}><Icon name="plus" size={15} /> Create a character</button>
      </div>
      <div className="row">
        <input type="search" placeholder="Search names, groups, cliques..." value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 260 }} />
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="student">Students</option>
          <option value="alumni">Alumni</option>
          <option value="staff">Staff</option>
          <option value="">Everyone</option>
        </select>
        <select value={grade} onChange={(e) => setGrade(e.target.value)}>
          <option value="">All grades</option>
          {[9, 10, 11, 12].map((g) => <option key={g} value={g}>Grade {g}</option>)}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="popularity">Sort: popularity</option>
          <option value="friends">Sort: friends</option>
          <option value="mood">Sort: lowest mood</option>
          <option value="stress">Sort: most stressed</option>
          <option value="gpa">Sort: GPA</option>
          <option value="name">Sort: name</option>
        </select>
        <span className="hint">{list.length} people</span>
      </div>
      <div className="cards">
        {list.map((c) => (
          <div key={c.id} className="ccard" onClick={() => go(`characters/${c.id}`)}>
            <div className="row" style={{ alignItems: "flex-start", flexWrap: "nowrap" }}>
              <Avatar id={c.id} size={44} />
              <div style={{ minWidth: 0 }}>
                <div className="ccard-name">{c.name} {c.featured && <span className="star" title="Featured demo character">★</span>}</div>
                <div className="hint">
                  {c.role === "student" ? `Grade ${c.grade}` : c.role === "staff" ? c.role_label : "Alumni"} · {c.archetype} · {c.pronouns}
                </div>
              </div>
            </div>
            <div className="ccard-bio">{c.bio}</div>
            <div className="meters">
              <Meter label="Mood" value={c.mood} color={moodColor(c.mood)} right={fmt(c.mood)} />
              <Meter label="Stress" value={c.stress} invert right={fmt(c.stress)} />
              {c.role !== "staff" && <Meter label="Popularity" value={c.popularity} color="var(--accent-2)" right={fmt(c.popularity)} />}
            </div>
            <div className="chips">
              {c.clique && <Tag tone="accent">{c.clique.name}</Tag>}
              {c.memberships.slice(0, 3).map((m) => <Tag key={m.id}>{m.name}</Tag>)}
              {c.partner && <Tag tone="romance">dating <Name id={c.partner} plain /></Tag>}
              {c.grounded && <Tag tone="warn">grounded</Tag>}
              {c.reputation.slice(0, 2).map(([k]) => <Tag key={k} tone="dim">{k}</Tag>)}
            </div>
          </div>
        ))}
      </div>
      {creating && <CreateModal onClose={() => setCreating(false)} />}
    </div>
  );
}

function CreateModal({ onClose }: any) {
  const { refresh, bump, toast, world, charList, chars } = useStore();
  const { cat } = useStoryCatalog();
  const prot: string | null = (world as any)?.protagonist || null;
  const [mode, setMode] = useState("build");
  const [person, setPerson] = useState<Person>({ first: "", gender: "f", grade: 9, color: "#ff8fc7" });
  const [household, setHousehold] = useState("new");
  const [section, setSection] = useState("basics");
  const [errs, setErrs] = useState<string[]>([]);
  const [spec, setSpec] = useState<any>({ grade: 9, archetype: "", first: "", last: "", gender: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const done = async (c: any) => {
    await refresh();
    bump();
    toast(`${c.name} joined ${c.role === "staff" ? "the staff" : PLACE.school}.`, "good");
    onClose();
    go(`characters/${c.id}`);
  };
  const quick = async () => {
    setBusy(true);
    try {
      const body: any = { grade: Number(spec.grade) };
      if (spec.archetype) body.archetype = spec.archetype;
      if (spec.last) body.last = spec.last;
      await done(await api.post("/api/characters", body));
    } catch (e: any) {
      setErr([e.message, ...(e.errors || [])].join("\n"));
    } finally {
      setBusy(false);
    }
  };
  const build = async () => {
    if (!person.first.trim() || !person.gender) {
      setErrs(["character: a first name and a gender are required"]);
      setSection("basics");
      return;
    }
    setBusy(true);
    try {
      const body = cleanPerson(person, "studio");
      if (household === "family" && prot && person.role !== "staff") body.household = "family";
      await done(await api.post("/api/characters", body));
    } catch (e: any) {
      const list = e.errors?.length ? e.errors : [e.message];
      setErrs(list);
      setSection(sectionForError(list[0] || ""));
    } finally {
      setBusy(false);
    }
  };
  const people: Target[] = [
    ...(prot && chars[prot] ? [{ key: "me", name: chars[prot].name }] : []),
    ...charList.filter((c) => c.status === "active" && c.id !== prot && (c.role === "student" || c.role === "staff"))
      .map((c) => ({ key: c.id, name: `${c.name} (${c.role === "staff" ? c.role_label || "staff" : `grade ${c.grade}`})` })),
  ];
  return (
    <Modal title="Create a character" onClose={onClose} wide>
      <div className="row between" style={{ marginBottom: 14 }}>
        <Tabs tabs={[["build", "Build someone"], ["quick", "Quick random person"]]} active={mode} onChange={setMode} />
        {mode === "build" && <span className="hint">They join the running world today, with realistic starting relationships with everyone else.</span>}
      </div>
      {mode === "build" ? (
        <>
          <CharacterBuilder value={person} onChange={setPerson} cat={cat} mode="studio" people={people} errors={errs.map((e) => e.replace(/^character:?\s*/, ""))}
            section={section} onSection={setSection}
            sideExtra={person.role !== "staff" && (
              <div className="cb-field" style={{ marginTop: 12, textAlign: "left" }}>
                <div className="cb-field-l">Where they live</div>
                <select value={household} onChange={(e) => setHousehold(e.target.value)}>
                  <option value="new">With their own family</option>
                  {prot && chars[prot] && <option value="family">With {chars[prot].first}'s family (a sibling)</option>}
                </select>
              </div>
            )} />
          <div className="row" style={{ marginTop: 14, justifyContent: "flex-end" }}>
            <button onClick={onClose}>Cancel</button>
            <button className="primary" onClick={build} disabled={busy}>{busy ? "Creating..." : `Create ${person.first.trim() || "them"}`}</button>
          </div>
        </>
      ) : (
        <>
          <p className="muted">The generator builds a full person from an archetype (with noise), puts them in a household, and gives them realistic starting relationships with their classmates. You can fine-tune everything afterwards in the Edit tab.</p>
          <div className="form">
            <label>Grade<select value={spec.grade} onChange={(e) => setSpec({ ...spec, grade: e.target.value })}>{[9, 10, 11, 12].map((g) => <option key={g}>{g}</option>)}</select></label>
            <label>Archetype<select value={spec.archetype} onChange={(e) => setSpec({ ...spec, archetype: e.target.value })}><option value="">Random</option>{ARCHETYPES.map((a) => <option key={a}>{a}</option>)}</select></label>
            <label>Last name<input type="text" value={spec.last} placeholder="random (new household)" onChange={(e) => setSpec({ ...spec, last: e.target.value })} /></label>
          </div>
          <ErrorBox error={err} />
          <div className="row" style={{ marginTop: 12 }}>
            <button className="primary" onClick={quick} disabled={busy}>Generate</button>
            <button onClick={onClose}>Cancel</button>
          </div>
        </>
      )}
    </Modal>
  );
}

// ------------------------------------------------------------------ detail
function Detail({ id }: { id: string }) {
  const { data: c, error, reload } = useApi(`/api/characters/${id}`, [id]);
  const [tab, setTab] = useState("profile");
  const [relWith, setRelWith] = useState<string | null>(null);
  if (error) return <div className="errorbox">{error}</div>;
  if (!c) return <Loading what="Opening their file" />;
  const h = c.household_info;
  return (
    <div className="stack">
      <div className="hero panel">
        <div className="panel-b row" style={{ alignItems: "flex-start", gap: 18, flexWrap: "nowrap" }}>
          <Avatar id={c.id} size={76} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="row">
              <h1>{c.name}</h1>
              {c.featured && <Tag tone="warn">featured</Tag>}
              <Tag>{c.role === "student" ? `Grade ${c.grade}` : c.role === "staff" ? c.role_label : "Alumni"}</Tag>
              <Tag>{c.archetype}</Tag>
              <Tag tone="dim">{c.pronouns} · age {c.age}</Tag>
              {c.grounded && <Tag tone="warn">grounded</Tag>}
            </div>
            <p className="muted" style={{ margin: "6px 0 10px" }}>{c.bio}</p>
            <div className="chips">
              {c.clique && <Tag tone="accent">{c.clique.name}</Tag>}
              {c.memberships.map((m: any) => <Tag key={m.id}>{m.name}</Tag>)}
              {c.partner && <Tag tone="romance">dating <Name id={c.partner} plain /></Tag>}
              {c.reputation.map(([k, v]: any) => <Tag key={k} tone="dim" title={`reputation strength ${v}`}>{k}</Tag>)}
            </div>
          </div>
          <div className="stack" style={{ gap: 8, alignItems: "flex-end" }}>
            {c.role !== "staff" && <button className="primary" onClick={() => go(`play/${c.id}`)}><Icon name="play" size={14} /> Live as {c.first}</button>}
            <button onClick={() => go(`history/char/${c.id}`)}>Full history</button>
            <button onClick={() => go("characters")}>All characters</button>
          </div>
        </div>
      </div>

      <div className="stats">
        <Stat label="Mood" value={fmt(c.mood)} tone={c.mood >= 60 ? "good" : c.mood < 40 ? "bad" : "warn"} />
        <Stat label="Stress" value={fmt(c.needs.stress)} tone={c.needs.stress > 60 ? "bad" : undefined} />
        <Stat label="Popularity" value={fmt(c.popularity)} sub="percentile among students" />
        <Stat label="Friends" value={c.friends} sub="people they count as friends" />
        <Stat label="GPA" value={fmt(c.gpa, 2)} />
        <Stat label="Money" value={`$${fmt(c.money)}`} />
        <Stat label="Active goals" value={c.goals.filter((g: any) => g.status === "active").length} />
      </div>

      <Tabs tabs={[["profile", "Profile"], ["relationships", `Relationships (${c.relationships.length})`], ["timeline", "Timeline"], ["decisions", "Decisions"], ["memories", `Memories (${c.memories.length})`], ["edit", "Edit"]]}
        active={tab} onChange={setTab} />

      {tab === "profile" && <Profile c={c} h={h} />}
      {tab === "relationships" && <Relationships c={c} onOpen={setRelWith} />}
      {tab === "timeline" && <Timeline c={c} />}
      {tab === "decisions" && <Decisions c={c} />}
      {tab === "memories" && <Memories c={c} />}
      {tab === "edit" && <Edit c={c} onSaved={reload} />}
      {relWith && <RelationshipModal a={c.id} b={relWith} onClose={() => setRelWith(null)} />}
    </div>
  );
}

function LayerPanel({ title, about, values, keys, color, docs }: any) {
  return (
    <Panel title={title} sub={about}>
      <div className="meters">
        {keys.map((k: string) => (
          <div key={k} title={docs?.[k] || ""}>
            <Meter label={k} value={values[k] ?? 0} color={color} right={fmt(values[k])} />
          </div>
        ))}
      </div>
    </Panel>
  );
}

function Profile({ c, h }: any) {
  const d = c.docs;
  const goalsActive = c.goals.filter((g: any) => g.status === "active");
  const goalsDone = c.goals.filter((g: any) => g.status !== "active").slice(0, 8);
  const athlete = Object.keys(c.positions || {}).length > 0 || (c.seasons || []).length > 0 || !!c.path?.kind || (c.awards || []).length > 0;
  return (
    <div className="stack">
    {athlete && <AthletePanel c={c} />}
    <div className="grid g3">
      <LayerPanel title="Personality" about={d.traits.about} values={c.traits} keys={TRAITS} color="var(--accent-2)" docs={d.traits.items} />
      <div className="stack">
        <LayerPanel title="Natural aptitude" about={d.aptitudes.about} values={c.aptitudes} keys={APTS} color="var(--warm)" docs={d.aptitudes.items} />
        <Panel title="Learned skills" sub="Grow with practice up to a ceiling set by aptitude; fade without use.">
          <div className="meters">
            {c.skills.filter((s: any) => s.value >= 3).map((s: any) => (
              <div key={s.id} className="meter-row" title={`ceiling ${s.cap} · recent practice ${s.practice}`}>
                <span className="meter-l">{s.label}</span>
                <div className="meter skillbar" style={{ height: 8 }}>
                  <div className="meter-f" style={{ width: `${s.value}%`, background: "var(--accent)" }} />
                  <div className="cap" style={{ left: `${s.cap}%` }} />
                </div>
                <span className="meter-r">{fmt(s.value)}</span>
              </div>
            ))}
          </div>
          <div className="hint" style={{ marginTop: 6 }}>The tick on each bar marks their talent ceiling.</div>
        </Panel>
      </div>
      <div className="stack">
        <LayerPanel title="What they want" about={d.motives.about} values={c.motives} keys={MOTIVES} color="var(--romance)" docs={d.motives.items} />
        <Panel title="Right now" sub={d.needs.about}>
          <div className="meters">
            <Meter label="mood" value={c.mood} color={moodColor(c.mood)} right={fmt(c.mood)} />
            {NEEDS.map((n) => <Meter key={n} label={n} value={c.needs[n]} invert={n === "stress"} color={n === "stress" ? undefined : "var(--info)"} right={fmt(c.needs[n])} />)}
          </div>
        </Panel>
      </div>
      <Panel title="Goals" sub="Generated from circumstances. Each one adds weight to the actions that serve it.">
        {goalsActive.length ? goalsActive.map((g: any) => (
          <div key={g.id} className="goal">
            <div className="row between"><b>{g.label}</b><Tag tone="accent">priority {fmt(g.priority)}</Tag></div>
            <div className="hint">since day {g.created}{g.progress ? ` · progress ${fmt(g.progress, 1)}` : ""}{g.note === "retry" ? " · a second attempt" : ""}</div>
          </div>
        )) : <Empty>No active goals.</Empty>}
        {goalsDone.length > 0 && (
          <>
            <div className="hint" style={{ margin: "10px 0 4px" }}>Closed goals</div>
            {goalsDone.map((g: any) => (
              <div key={g.id} className="row between small" style={{ padding: "3px 0" }}>
                <span>{g.label}</span>
                <Tag tone={g.status === "achieved" ? "good" : g.status === "failed" ? "bad" : "dim"}>{g.status}</Tag>
              </div>
            ))}
          </>
        )}
      </Panel>
      <Panel title="Interests & reputation">
        <div className="hint" style={{ marginBottom: 4 }}>Interests (drift with enjoyment and with friends)</div>
        <div className="meters">
          {c.all_interests.slice(0, 7).map(([k, v]: any) => <Meter key={k} label={k.replace(/_/g, " ")} value={v} color="var(--good)" right={fmt(v)} />)}
        </div>
        <div className="hint" style={{ margin: "12px 0 4px" }}>Reputation (what people say about them)</div>
        <div className="chips">
          {Object.entries(c.reputation_all).filter(([, v]: any) => v >= 1).sort((a: any, b: any) => b[1] - a[1]).map(([k, v]: any) => <Tag key={k}>{k} {fmt(v)}</Tag>)}
          {!Object.keys(c.reputation_all).length && <span className="dim">No reputation yet.</span>}
        </div>
      </Panel>
      <Panel title="Circumstances" sub="External conditions: family, money, groups">
        {h ? (
          <dl className="kv">
            <dt>Household</dt><dd>{h.name}</dd>
            <dt>Guardians</dt><dd>{h.guardians.join(", ")} <span className="hint">({h.style_label})</span></dd>
            <dt>Income</dt><dd>{h.income}</dd>
            <dt>Siblings</dt><dd>{h.members.filter((m: string) => m !== c.id).map((m: string) => <Name key={m} id={m} />)}{h.members.length < 2 && <span className="dim">none</span>}</dd>
            {h.pet && (<><dt>Pet</dt><dd>{h.pet.name} the {h.pet.species}</dd></>)}
          </dl>
        ) : <div className="muted">{c.role_label}</div>}
        <div className="hint" style={{ margin: "12px 0 4px" }}>Learned expectations (how actions have gone before)</div>
        <div className="chips">
          {Object.entries(c.expectations).slice(0, 8).map(([k, v]: any) => <Tag key={k} tone={v > 0.1 ? "good" : v < -0.1 ? "bad" : "dim"}>{pretty(k)} {signed(v, 2)}</Tag>)}
        </div>
        {c.achievements.length > 0 && (
          <>
            <div className="hint" style={{ margin: "12px 0 4px" }}>Achievements</div>
            {c.achievements.slice(0, 6).map((a: any, i: number) => <div key={i} className="small">🏅 {a.label} <span className="hint">day {a.day}</span></div>)}
          </>
        )}
        {c.past_memberships.length > 0 && (
          <>
            <div className="hint" style={{ margin: "12px 0 4px" }}>Past groups</div>
            {c.past_memberships.slice(-6).reverse().map((p: any, i: number) => <div key={i} className="small">{p.name} <span className="hint">left day {p.to}: {p.why}</span></div>)}
          </>
        )}
      </Panel>
    </div>
    </div>
  );
}

// ------------------------------------------------------------------ athlete
const SPORT_ORDER = ["football", "basketball", "soccer", "baseball", "softball"];
const statNum = (v: any) => (typeof v === "number" ? (Number.isInteger(v) ? String(v) : v.toFixed(1)) : v ?? "-");
function derived(sport: string, line: any): Record<string, string> {
  const out: Record<string, string> = {};
  if (sport === "baseball" || sport === "softball") {
    if (line.ab > 0) out.AVG = (line.h / line.ab).toFixed(3).replace(/^0/, "");
    if (line.ip > 0) out.ERA = ((line.er * 9) / line.ip).toFixed(2);
  }
  return out;
}

function AthletePanel({ c }: any) {
  const { cat } = useStoryCatalog();
  const sports = cat?.sports || {};
  const colleges: Record<string, any> = Object.fromEntries((cat?.colleges || []).map((x: any) => [x.id, x]));
  const body = c.body || {};
  const seasons: any[] = c.seasons || [];
  const rec = c.recruiting || {};
  const interest = Object.entries(rec.interest || {}).map(([k, v]: any) => {
    const [col, sport] = k.split(":");
    return { col, sport, level: v, name: colleges[col]?.short || colleges[col]?.name || col, tier: colleges[col]?.conference || colleges[col]?.tier };
  }).sort((a, b) => b.level - a.level).slice(0, 8);
  const path = c.path?.kind ? c.path : null;
  const bySport = SPORT_ORDER.filter((s) => seasons.some((x) => x.sport === s) || c.positions?.[s]);
  return (
    <Panel title="Athlete" sub={[body.height_in ? heightLabel(body.height_in) : null, body.build, c.jersey ? `#${c.jersey}` : null].filter(Boolean).join(" · ") || undefined}>
      <div className="ath">
        <div className="ath-pos">
          {SPORT_ORDER.filter((s) => c.positions?.[s]).map((s) => (
            <div key={s} className="ath-pos-i">
              <span className="hint">{sports[s]?.label || s}</span>
              <b>{c.positions[s]}</b>
              <span className="small muted">{sports[s]?.positions?.[c.positions[s]] || ""}</span>
            </div>
          ))}
          {path && (
            <div className="ath-path">
              <span className="hint">After high school</span>
              <b>{path.kind === "pro" ? (path.team ? `Pro ball: ${path.team}, round ${path.round} (pick ${path.pick}), starting at ${path.level}` : "Pro ball: undrafted free agent")
                : path.kind === "college" ? (path.sport ? `Playing ${path.sport} at ${path.name || colleges[path.college]?.name || path.college}` : `Studying at ${path.name || colleges[path.college]?.name || path.college}`) : `Working in ${PLACE.town}`}</b>
              <span className="small muted">{[path.conference || path.tier, path.aid || (path.scholarship ? "scholarship" : null)].filter(Boolean).join(" · ")}</span>
            </div>
          )}
        </div>
        {bySport.map((sport) => {
          const rows = seasons.filter((x) => x.sport === sport);
          const keys = Object.keys(sports[sport]?.stats || {}).filter((k) => rows.some((r) => r.line?.[k]));
          const car = c.career?.[sport];
          if (!rows.length) return null;
          const dcols = Array.from(new Set(rows.flatMap((r) => Object.keys(derived(sport, r.line || {})))));
          return (
            <div key={sport} className="ath-sport">
              <div className="ath-sport-h"><b>{sports[sport]?.label || sport}</b>{car && <span className="hint">{car.seasons} season{car.seasons === 1 ? "" : "s"} · {car.games} games · {car.wins}-{car.losses}</span>}</div>
              <div style={{ overflowX: "auto" }}>
                <table className="mini">
                  <thead>
                    <tr>
                      <th>season</th><th>team</th><th className="num">G</th><th className="num">GS</th><th className="num">W-L</th>
                      {keys.map((k) => <th key={k} className="num">{sports[sport].stats[k]}</th>)}
                      {dcols.map((l) => <th key={l} className="num">{l}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => {
                      const [, yr, level] = r.key.split(":");
                      return (
                        <tr key={r.key}>
                          <td>{yr} <Tag tone={level === "varsity" ? "accent" : "dim"}>{level === "jv" ? "JV" : level}</Tag></td>
                          <td className="dim">{r.team_name}</td>
                          <td className="num">{r.games}</td>
                          <td className="num">{r.starts}</td>
                          <td className="num">{r.wins}-{r.losses}</td>
                          {keys.map((k) => <td key={k} className="num">{statNum(r.line?.[k] ?? 0)}</td>)}
                          {dcols.map((l) => <td key={l} className="num">{derived(sport, r.line || {})[l] ?? "-"}</td>)}
                        </tr>
                      );
                    })}
                    {car && rows.length > 1 && (
                      <tr className="ath-total">
                        <td><b>Career</b></td><td />
                        <td className="num">{car.games}</td><td className="num">{car.starts}</td><td className="num">{car.wins}-{car.losses}</td>
                        {keys.map((k) => <td key={k} className="num"><b>{statNum(car.line?.[k] ?? 0)}</b></td>)}
                        {dcols.map((l) => <td key={l} className="num"><b>{derived(sport, car.line || {})[l] ?? "-"}</b></td>)}
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
        {!seasons.length && <div className="hint">No games played yet. Season stats show up here after their first game.</div>}
        <div className="ath-grid">
          <div>
            <div className="hint" style={{ marginBottom: 4 }}>Awards</div>
            {(c.awards || []).length ? c.awards.map((a: any, i: number) => <div key={i} className="small">🏆 {a.label} <span className="hint">{a.season?.split(":")[1] || ""}</span></div>) : <div className="dim small">None yet.</div>}
          </div>
          <div>
            <div className="hint" style={{ marginBottom: 4 }}>Recruiting{rec.score && Object.keys(rec.score).length ? ` · ${Object.entries(rec.score).map(([s, v]: any) => `${s} ${Math.round(v)}`).join(" · ")}` : ""}</div>
            {(rec.offers || []).map((o: any, i: number) => (
              <div key={i} className="small"><Tag tone="good">offer</Tag> {o.short || o.name} <span className="hint">{o.conference || o.tier} · {o.sport}{o.aid ? ` · ${o.aid}` : o.scholarship ? " · scholarship" : ""}</span></div>
            ))}
            {interest.filter((x) => !(rec.offers || []).some((o: any) => o.college === x.col && o.sport === x.sport)).map((x) => (
              <div key={x.col + x.sport} className="small"><Tag tone="dim">interest {x.level}</Tag> {x.name} <span className="hint">{x.tier} · {x.sport}</span></div>
            ))}
            {!(rec.offers || []).length && !interest.length && <div className="dim small">No college interest yet. Coaches start watching sophomores who produce.</div>}
          </div>
          <div>
            <div className="hint" style={{ marginBottom: 4 }}>Admissions</div>
            {(rec.admits || []).length ? rec.admits.map((a: any, i: number) => <div key={i} className="small">✉️ {a.short || a.name} <span className="hint">{a.conference || a.tier}</span></div>) : <div className="dim small">Letters arrive senior year.</div>}
          </div>
        </div>
      </div>
    </Panel>
  );
}

const LABEL_TONE: Record<string, string> = { "best friend": "good", "close friend": "good", friend: "accent", acquaintance: "dim", stranger: "dim", rival: "warn", dislikes: "bad" };

function Relationships({ c, onOpen }: any) {
  const { chars } = useStore();
  const [filter, setFilter] = useState("close");
  const rels = c.relationships.filter((r: any) => {
    const o = chars[r.id];
    if (!o) return false;
    if (filter === "close") return r.mine.familiarity >= 15 || r.mine.crush || r.roles.length;
    if (filter === "romance") return r.mine.crush || (r.theirs && r.theirs.crush) || r.roles.includes("partner") || r.roles.includes("ex");
    if (filter === "conflict") return r.mine.label === "rival" || r.mine.label === "dislikes" || r.mine.grudge > 15;
    if (filter === "gaps") return r.theirs && Math.abs(r.mine.affection - r.theirs.affection) > 15;
    return true;
  });
  return (
    <Panel title="How they see everyone (and how everyone sees them)"
      sub="Each side of a relationship is its own record. 'Thinks they feel' is their belief about the other person, which can be wrong."
      actions={<Tabs tabs={[["close", "People they know"], ["romance", "Romance"], ["conflict", "Friction"], ["gaps", "Perception gaps"], ["all", "All"]]} active={filter} onChange={setFilter} />}>
      <table className="mini rels">
        <thead>
          <tr><th>person</th><th>{c.first} sees them as</th><th>affection</th><th>thinks they feel</th><th>they actually feel</th><th>they see {c.first} as</th><th>trust</th><th>attraction</th><th>rivalry</th><th>roles</th></tr>
        </thead>
        <tbody>
          {rels.map((r: any) => {
            const gap = r.theirs ? r.mine.perceived - r.theirs.affection : 0;
            return (
              <tr key={r.id} className="click" onClick={() => onOpen(r.id)}>
                <td><Name id={r.id} full /></td>
                <td><Tag tone={LABEL_TONE[r.mine.label]}>{r.mine.label}</Tag> {r.mine.crush && <Tag tone="romance">crush</Tag>}</td>
                <td style={{ minWidth: 110 }}><Signed value={r.mine.affection} right={fmt(r.mine.affection)} /></td>
                <td className="num">{fmt(r.mine.perceived)}{r.theirs && Math.abs(gap) > 20 && <span className={gap > 0 ? "neg" : "pos"} title="their belief is off by this much"> ({signed(gap, 0)})</span>}</td>
                <td className="num">{r.theirs ? fmt(r.theirs.affection) : "-"}</td>
                <td>{r.theirs ? <><Tag tone={LABEL_TONE[r.theirs.label]}>{r.theirs.label}</Tag> {r.theirs.crush && <Tag tone="romance">crush</Tag>}</> : <span className="dim">doesn't know them</span>}</td>
                <td className="num">{fmt(r.mine.trust)}</td>
                <td className="num">{fmt(r.mine.attraction)}</td>
                <td className="num">{fmt(r.mine.rivalry)}</td>
                <td>{r.roles.map((x: string) => <Tag key={x}>{x.split(":")[0]}</Tag>)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {!rels.length && <Empty>Nobody in this view.</Empty>}
    </Panel>
  );
}

export function RelationshipModal({ a, b, onClose }: { a: string; b: string; onClose: () => void }) {
  const { data, error } = useApi(`/api/relationship/${a}/${b}`, [a, b]);
  const { chars } = useStore();
  const A = chars[a], B = chars[b];
  return (
    <Modal title={<span><Name id={a} full /> &amp; <Name id={b} full /></span>} onClose={onClose} wide>
      {error && <div className="errorbox">{error}</div>}
      {!data ? <Loading /> : (
        <div className="stack">
          <div className="row">{data.roles.map((r: string) => <Tag key={r} tone="accent">{r.split(":").join(" · ")}</Tag>)}{data.satisfaction && <span className="hint">relationship satisfaction: {A?.short} {data.satisfaction[a]}, {B?.short} {data.satisfaction[b]}</span>}</div>
          <div className="grid g2">
            {[[a, b, data.ab], [b, a, data.ba]].map(([x, y, r]: any) => (
              <Panel key={x} title={<span><Name id={x} /> about <Name id={y} /></span>} sub={r ? `${r.label}${r.crush ? " · crush" : ""} · known since day ${r.met_day}` : "no relationship record"}>
                {r && (
                  <div className="meters">
                    <Signed label="affection" value={r.affection} right={fmt(r.affection)} />
                    <Signed label="respect" value={r.respect} right={fmt(r.respect)} />
                    <Meter label="familiarity" value={r.familiarity} right={fmt(r.familiarity)} />
                    <Meter label="trust" value={r.trust} color="var(--info)" right={fmt(r.trust)} />
                    <Meter label="attraction" value={r.attraction} color="var(--romance)" right={fmt(r.attraction)} />
                    <Meter label="rivalry" value={r.rivalry} color="var(--warm)" right={fmt(r.rivalry)} />
                    <Signed label="thinks they feel" value={r.perceived} right={fmt(r.perceived)} />
                    <div className="hint">peak affection {fmt(r.peak_affection)} · grudge {fmt(r.grudge)} · {r.pos} good / {r.neg} bad interactions</div>
                    {r.milestones?.length > 0 && (
                      <div className="chips">{r.milestones.map((m: any, i: number) => <Tag key={i} tone="accent">day {m[0]}: {m[1].replace(/_/g, " ")}</Tag>)}</div>
                    )}
                  </div>
                )}
              </Panel>
            ))}
          </div>
          <div className="grid g2">
            <Panel title="Shared history" sub="Events involving both of them">
              <div className="evlist scroll short">
                {data.events.length ? data.events.map((e: any) => <EventRow key={e.id} ev={e} compact />) : <Empty>No shared events recorded yet.</Empty>}
              </div>
            </Panel>
            <Panel title="What they remember about each other">
              {[a, b].map((x) => (
                <div key={x} style={{ marginBottom: 10 }}>
                  <div className="hint"><Name id={x} /> remembers</div>
                  {data.memories[x].length ? data.memories[x].slice(0, 6).map((m: any) => (
                    <div key={m.id} className="small mem"><span className={m.valence >= 0 ? "pos" : "neg"}>{m.valence >= 0 ? "+" : "−"}</span> {m.text} <span className="hint">day {m.day}</span></div>
                  )) : <div className="dim small">nothing specific</div>}
                </div>
              ))}
            </Panel>
          </div>
        </div>
      )}
    </Modal>
  );
}

function Timeline({ c }: any) {
  const [min, setMin] = useState(12);
  const evs = c.timeline.filter((e: any) => e.importance >= min);
  return (
    <Panel title={`${c.first}'s story so far`} sub="Their recorded events, newest first. Routine events older than the retention window are folded into counters."
      actions={<Tabs tabs={[["0", "Everything"], ["12", "Notable"], ["25", "Major"]]} active={String(min)} onChange={(k) => setMin(Number(k))} />}>
      <div className="evlist">{evs.length ? evs.map((e: any) => <EventRow key={e.id} ev={e} />) : <Empty>Nothing at this level yet.</Empty>}</div>
    </Panel>
  );
}

function Decisions({ c }: any) {
  return (
    <Panel title="Recent decisions" sub="Every choice is a recorded calculation. Open one to see every option they weighed, each term's contribution, the random roll and what followed.">
      {c.decisions.length ? (
        <table className="mini">
          <thead><tr><th>when</th><th>slot</th><th>chose</th><th>target</th><th className="num">how likely</th><th className="num">options</th><th></th></tr></thead>
          <tbody>
            {c.decisions.map((d: any) => (
              <tr key={d.id} className="click" onClick={() => go(`history/trace/${d.id}`)}>
                <td className="dim">{d.date}</td>
                <td>{pretty(d.slot)}</td>
                <td>{d.label}{d.player && <Tag tone="warn">you chose</Tag>}{d.cancelled && <Tag tone="dim">changed plans</Tag>}</td>
                <td>{d.target_name || (d.target && !String(d.target).includes(":") ? <Name id={d.target} /> : "")}</td>
                <td className="num">{(d.prob * 100).toFixed(0)}%</td>
                <td className="num">{d.n}</td>
                <td><span className="hint">inspect</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <Empty>No decision traces in the retention window.</Empty>}
    </Panel>
  );
}

function Memories({ c }: any) {
  return (
    <Panel title="Memories" sub="Significant experiences. They fade with time (intense ones last longer) and shape how this person approaches the people involved.">
      {c.memories.length ? c.memories.map((m: any) => (
        <div key={m.id} className="mem-row">
          <div className={cx("mem-v", m.valence >= 0 ? "pos" : "neg")}>{signed(m.valence, 2)}</div>
          <div style={{ flex: 1 }}>
            <div>{m.text}</div>
            <div className="hint">day {m.day} · intensity {m.intensity} · {m.kind.replace(/_/g, " ")}{m.with.length ? " · " : ""}{m.with.map((w: string) => <Name key={w} id={w} />)}</div>
          </div>
          {m.event && <button className="small ghost" onClick={() => go(`history/event/${m.event}`)}>event</button>}
        </div>
      )) : <Empty>No memories yet.</Empty>}
    </Panel>
  );
}

function Edit({ c, onSaved }: any) {
  const { toast, refresh, bump } = useStore();
  const [draft, setDraft] = useState<any>({});
  const [err, setErr] = useState<string | null>(null);
  const [last, setLast] = useState<any>(null);
  const val = (layer: string, k: string) => draft[layer]?.[k] ?? c[layer][k];
  const set = (layer: string, k: string, v: number) => setDraft({ ...draft, [layer]: { ...(draft[layer] || {}), [k]: v } });
  const n: number = Object.values(draft).reduce((s: number, x: any) => s + (typeof x === "object" ? Object.keys(x).length : 1), 0) as number;
  const save = async () => {
    try {
      const r = await api.patch(`/api/characters/${c.id}`, draft);
      setDraft({});
      setErr(null);
      setLast(r.event);
      toast("Saved. The change is logged as a lab edit in history.", "good");
      await refresh();
      bump();
      onSaved();
    } catch (e: any) {
      setErr([e.message, ...(e.errors || [])].join("\n"));
    }
  };
  const block = (title: string, layer: string, keys: string[], about: string) => (
    <Panel title={title} sub={about}>
      {keys.map((k) => (
        <div key={k} className="edit-row">
          <span>{k}</span>
          <Slider min={0} max={100} step={1} value={val(layer, k)} onChange={(v: number) => set(layer, k, v)} />
          <input type="number" min={0} max={100} value={Math.round(val(layer, k))} onChange={(e) => set(layer, k, Number(e.target.value))} />
          {draft[layer]?.[k] !== undefined && <span className="hint">was {fmt(c[layer][k])}</span>}
        </div>
      ))}
    </Panel>
  );
  return (
    <div className="stack">
      <div className="callout">
        Edits are validated (0-100) and recorded as a <b>lab edit</b> event, so the history shows exactly when and how you intervened.
        Everything they do afterwards follows from the new values. Try lowering someone's discipline and watch their week change.
      </div>
      <div className="row">
        <button className="primary" disabled={!n} onClick={save}>Save {n || ""} change{n === 1 ? "" : "s"}</button>
        <button disabled={!n} onClick={() => setDraft({})}>Discard</button>
      </div>
      <ErrorBox error={err} />
      {last && <Panel title="Recorded change"><Changes changes={last.changes} /></Panel>}
      <div className="grid g2">
        {block("Personality", "traits", TRAITS, "Stable tendencies")}
        <div className="stack">
          {block("Natural aptitude", "aptitudes", APTS, "Potential: growth rate and ceiling")}
          {block("Motivations", "motives", MOTIVES, "What they want")}
          {block("Current condition", "needs", NEEDS, "Temporary; will keep changing")}
        </div>
      </div>
      <Panel title="Bio">
        <textarea rows={3} value={draft.bio ?? c.bio} onChange={(e) => setDraft({ ...draft, bio: e.target.value })} />
      </Panel>
    </div>
  );
}
