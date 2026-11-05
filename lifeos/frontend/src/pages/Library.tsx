// Content Library: the data-driven catalogs the simulation runs on, browsable in one place.
import React, { useMemo, useState } from "react";
import { go, useApi } from "../store";
import Dialogue from "./LibraryDialogue";
import { cx, Empty, ErrorBox, Loading, Meter, Panel, pretty, Stat, Tabs, Tag } from "../ui";
import "./library.css";

const TABS: [string, string][] = [
  ["dialogue", "Dialogue"], ["actions", "Actions"], ["goals", "Goals"], ["templates", "Narrative templates"], ["world", "World"],
  ["people", "People"], ["attributes", "Attributes"], ["metrics", "Metrics"],
];
const FILE_FOR: Record<string, string> = {
  actions: "actions", goals: "goals", templates: "templates", world: "world", people: "people", attributes: "rules", metrics: "rules",
};
const MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const md = (x: any) => (Array.isArray(x) ? `${MONTHS[x[0]]} ${x[1]}` : "-");

export default function Library({ route }: { route: string[] }) {
  const tab = TABS.some(([k]) => k === route[1]) ? route[1] : "dialogue";
  const { data, error, loading } = useApi<any>("/api/catalogs");
  return (
    <div>
      <div className="page-h">
        <div>
          <h1>Content Library</h1>
          <p>Everything the simulation is made of: actions, goals, narrative templates, the town and its institutions, the people
            templates, and the attribute definitions. Engine numbers are tuned in the <a href="#/workshop">Engine Workshop</a>.</p>
        </div>
        <Tabs tabs={TABS} active={tab} onChange={(k) => go(`library/${k}`)} />
      </div>
      {tab === "dialogue" && <Dialogue />}
      {tab !== "dialogue" && <ErrorBox error={error} />}
      {tab !== "dialogue" && loading && !data && <Loading what="Loading catalogs" />}
      {tab !== "dialogue" && data && (
        <>
          <div className="callout lib-files">
            These are plain JSON files, the data-driven source of the simulation. Edit them directly and restart the server to reload.
            {" "}This tab comes from <code>lifeos/{data.files[FILE_FOR[tab]]}</code>.
            <div className="lib-filelist">
              {Object.entries(data.files).map(([k, f]: any) => <span key={k} className="tag mono">{f}</span>)}
            </div>
          </div>
          {tab === "actions" && <Actions actions={data.actions} />}
          {tab === "goals" && <Goals goals={data.goals} actions={data.actions} />}
          {tab === "templates" && <Templates templates={data.templates} />}
          {tab === "world" && <World world={data.world} />}
          {tab === "people" && <People people={data.people} />}
          {tab === "attributes" && <Attributes attributes={data.attributes} />}
          {tab === "metrics" && <Metrics metrics={data.metrics} />}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- actions

function Actions({ actions }: { actions: any[] }) {
  const [open, setOpen] = useState<string | null>(null);
  const [cat, setCat] = useState("");
  const [q, setQ] = useState("");
  const cats = useMemo(() => Array.from(new Set(actions.map((a) => a.category))).sort(), [actions]);
  const rows = actions.filter((a) => (!cat || a.category === cat) && (!q || (a.id + " " + a.label).toLowerCase().includes(q.toLowerCase())));
  return (
    <Panel title={`Actions (${actions.length})`}
      sub="What characters can choose to do. Utility = base + needs + motives + traits + interests + target terms + goals + memory + experience + habit + peers - risk + commitment. Numbers are edited in the Engine Workshop."
      actions={
        <>
          <input type="search" placeholder="Filter" value={q} onChange={(e) => setQ(e.target.value)} />
          <select value={cat} onChange={(e) => setCat(e.target.value)}>
            <option value="">All categories</option>
            {cats.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </>
      }>
      <table className="mini lib-table">
        <thead>
          <tr><th>id</th><th>label</th><th>category</th><th>slots</th><th>roles</th><th>target</th><th className="num">base</th><th className="num">risk</th><th>resolver</th><th></th></tr>
        </thead>
        <tbody>
          {rows.map((a) => (
            <React.Fragment key={a.id}>
              <tr className={cx("click", open === a.id && "sel")} onClick={() => setOpen(open === a.id ? null : a.id)}>
                <td className="mono">{a.id}</td>
                <td>{a.label}</td>
                <td><Tag>{a.category}</Tag></td>
                <td className="small">{a.slots.map(pretty).join(", ")}</td>
                <td className="small">{a.roles.join(", ")}</td>
                <td className="small">{a.target ? pretty(a.target) : <span className="dim">none</span>}</td>
                <td className="num">{Number(a.base).toFixed(1)}</td>
                <td className="num">{a.risk ? Number(a.risk).toFixed(2) : "-"}</td>
                <td className="mono small">{a.resolver}</td>
                <td>
                  {a.overridden && <Tag tone="warn">edited in this world</Tag>}
                  {a.enabled === false && <Tag tone="bad">disabled</Tag>}
                </td>
              </tr>
              {open === a.id && (
                <tr className="lib-expand">
                  <td colSpan={10}>
                    <ActionDetail a={a} />
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
      {!rows.length && <Empty>No actions match.</Empty>}
    </Panel>
  );
}

function Coefs({ title, obj, note }: { title: string; obj: Record<string, number>; note?: string }) {
  const entries = Object.entries(obj || {});
  return (
    <div className="lib-coefs">
      <div className="lib-coefs-h">{title}{note && <span className="hint"> · {note}</span>}</div>
      {entries.length === 0 ? <div className="dim small">none</div> : (
        <div className="chips">
          {entries.map(([k, v]) => (
            <span key={k} className={cx("tag", v > 0 ? "tag-good" : v < 0 ? "tag-bad" : "")}>{pretty(k)} {v > 0 ? "+" : ""}{v}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function ActionDetail({ a }: { a: any }) {
  const params = Object.entries(a.params || {});
  return (
    <div className="lib-detail">
      <div className="grid g3">
        <Coefs title="Needs" obj={a.needs} note="> 0 relieves the need" />
        <Coefs title="Motives" obj={a.motives} note="x person's motive x global weight" />
        <Coefs title="Traits" obj={a.traits} note="x (trait - 50) / 50" />
        <Coefs title="Toward the target" obj={a.target_terms} note="feelings about the person/group" />
        <div className="lib-coefs">
          <div className="lib-coefs-h">Other terms</div>
          <div className="chips">
            <span className="tag">interest {a.interest || 0}</span>
            <span className="tag">commitment {a.obligation || 0}</span>
            <span className="tag">risk {a.risk || 0}</span>
            <span className="tag">event importance {a.importance}</span>
          </div>
        </div>
        <div className="lib-coefs">
          <div className="lib-coefs-h">Requires</div>
          {a.requires && a.requires.length ? <div className="chips">{a.requires.map((r: string) => <span key={r} className="tag mono">{r}</span>)}</div> : <div className="dim small">nothing extra</div>}
          {a.tags && a.tags.length > 0 && <div className="chips lib-tags">{a.tags.map((t: string) => <Tag key={t} tone="info">{t}</Tag>)}</div>}
        </div>
      </div>
      {params.length > 0 && (
        <div className="lib-coefs">
          <div className="lib-coefs-h">Resolver parameters <span className="hint">· applied when the action is carried out ({a.resolver})</span></div>
          <div className="chips">
            {params.map(([k, v]) => <span key={k} className="tag mono">{k}: {typeof v === "object" ? JSON.stringify(v) : String(v)}</span>)}
          </div>
        </div>
      )}
      {a.override && (
        <div className="callout warn">This world has edited this action: <span className="mono">{JSON.stringify(a.override)}</span>. Reset it in the Engine Workshop.</div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- goals

const MATCH: Record<string, string> = {
  goal_target: "toward the goal's person/group", goal_skill: "in the goal's skill", any: "any target", popular: "toward popular people", job: "for a job",
};

function Goals({ goals, actions }: { goals: Record<string, any>; actions: any[] }) {
  const label = (id: string) => actions.find((a) => a.id === id)?.label || id;
  return (
    <Panel title={`Goal types (${Object.keys(goals).length})`}
      sub="Goals are generated from circumstances (interests, upcoming tryouts, crushes, grudges, GPA, loneliness). While active, they add utility to the actions listed here, scaled by the goal's priority.">
      <div className="lib-goals">
        {Object.entries(goals).map(([k, g]) => (
          <div key={k} className="lib-goal">
            <div className="row between">
              <div><b>{g.label.replace("{target}", "…")}</b> <span className="mono dim">{k}</span></div>
              <Tag>base priority {g.base_priority}</Tag>
            </div>
            <table className="mini">
              <tbody>
                {Object.entries(g.advances).map(([aid, [w, m]]: any) => (
                  <tr key={aid}>
                    <td>{label(aid)} <span className="mono dim">{aid}</span></td>
                    <td className="small muted">{MATCH[m] || m}</td>
                    <td className="lib-w"><Meter value={w} max={1.5} right={`x${w}`} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </Panel>
  );
}

// ---------------------------------------------------------------- templates

function Templates({ templates }: { templates: Record<string, string[]> }) {
  const [q, setQ] = useState("");
  const keys = Object.keys(templates).filter((k) => !q || k.toLowerCase().includes(q.toLowerCase()) ||
    templates[k].some((v) => v.toLowerCase().includes(q.toLowerCase())));
  const groups: Record<string, string[]> = {};
  for (const k of keys) {
    const g = k.split(".")[0];
    (groups[g] = groups[g] || []).push(k);
  }
  const total = Object.values(templates).reduce((a, v) => a + v.length, 0);
  return (
    <Panel title={`Narrative templates (${Object.keys(templates).length} keys, ${total} variants)`}
      sub="Text is written from each event's recorded outcome. A presentation-only random stream picks the variant, so editing text never changes what happens. Placeholders like {a} and {b} become names."
      actions={<input type="search" placeholder="Search templates" value={q} onChange={(e) => setQ(e.target.value)} />}>
      {!keys.length && <Empty>No templates match.</Empty>}
      <div className="lib-tpl">
        {Object.entries(groups).map(([g, ks]) => (
          <div key={g} className="lib-tpl-group">
            <h4>{pretty(g)}</h4>
            {ks.map((k) => (
              <div key={k} className="lib-tpl-row">
                <div className="mono small lib-tpl-key">{k}</div>
                <ul>{templates[k].map((v, i) => <li key={i}>{v}</li>)}</ul>
              </div>
            ))}
          </div>
        ))}
      </div>
    </Panel>
  );
}

// ---------------------------------------------------------------- world

function World({ world }: { world: any }) {
  const cal = world.calendar || {};
  return (
    <div className="stack">
      <Panel title={world.town?.name} sub={world.town?.tagline}>
        <div className="stats">
          <Stat label="School" value={<span className="lib-sv">{world.school?.name}</span>} sub={`the ${world.school?.mascot}`} />
          <Stat label="First day" value={<span className="lib-sv">{world.town?.start_date}</span>} />
          <Stat label="Institutions" value={world.groups.length} />
          <Stat label="Places" value={world.places.length} />
          <Stat label="Skills" value={world.skills.length} />
          <Stat label="Hobbies" value={world.hobbies.length} />
        </div>
      </Panel>
      <Panel title="Groups & institutions" sub="Teams and productions select by tryout or audition; clubs are open; the council is elected; jobs hire.">
        <table className="mini">
          <thead><tr><th>name</th><th>kind</th><th>selection</th><th className="num">capacity</th><th>skill</th><th>meets</th><th>season / key dates</th><th className="num">prestige</th></tr></thead>
          <tbody>
            {world.groups.map((g: any) => (
              <tr key={g.id}>
                <td><b>{g.name}</b> <span className="mono dim">{g.id}</span></td>
                <td><Tag>{g.kind}</Tag></td>
                <td>{g.selection}</td>
                <td className="num">{g.capacity}</td>
                <td>{g.skill || "-"}</td>
                <td className="small">{(g.practice_days || g.shift_days || []).map((d: number) => WD[d]).join(", ") || "-"}</td>
                <td className="small">
                  {g.season && <>season {md(g.season.start)} to {md(g.season.end)}; tryouts {md(g.tryout)}; games {WD[g.game_day]}</>}
                  {g.productions && g.productions.map((p: any) => <div key={p.id}>{p.name}: auditions {md(p.audition)}, opens {md(p.show)}</div>)}
                  {g.election && <>signups open {md(g.signup_open)}; election {md(g.election)}</>}
                  {g.pay && <>pays ${g.pay}/shift, age {g.min_age}+</>}
                </td>
                <td className="num">{g.prestige}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
      <div className="grid g2">
        <Panel title="Places" sub="Where people hang out. Cost is per person.">
          <table className="mini">
            <tbody>
              {world.places.map((p: any) => (
                <tr key={p.id}><td><b>{p.name}</b></td><td className="muted small">{p.vibe}</td><td className="num">{p.cost ? `$${p.cost}` : "free"}</td></tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <Panel title="Calendar" sub={`School year starts ${md(cal.school_year_start)}; a quiz every ${cal.quiz_every_days} days.`}>
          <div className="lib-coefs-h">Breaks</div>
          <div className="chips">{(cal.breaks || []).map((b: any) => <span key={b.name} className="tag">{b.name}: {md(b.from)} to {md(b.to)}</span>)}</div>
          <div className="lib-coefs-h lib-gap">Events</div>
          <table className="mini">
            <tbody>
              {(cal.events || []).map((e: any) => (
                <tr key={e.id}>
                  <td>{e.name}</td><td><Tag>{e.kind}</Tag></td><td className="small">{md(e.date)}</td>
                  <td className="small muted">{e.grades ? `grades ${e.grades.join(", ")}` : e.weight ? `weight ${e.weight}` : ""}{e.ask_window ? `, ask window ${e.ask_window}d` : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <Panel title="Skills" sub="Learned capabilities; each grows from an aptitude.">
          <table className="mini">
            <tbody>{world.skills.map((s: any) => <tr key={s.id}><td><b>{s.label}</b> <span className="mono dim">{s.id}</span></td><td>{s.kind}</td><td className="muted">from {s.aptitude}</td></tr>)}</tbody>
          </table>
        </Panel>
        <Panel title="Hobbies" sub="Leisure activities; some build a skill a little.">
          <table className="mini">
            <tbody>{world.hobbies.map((h: any) => <tr key={h.id}><td><b>{h.label}</b></td><td className="muted small">"{h.verb}"</td><td className="small">{h.skill || "-"}</td></tr>)}</tbody>
          </table>
        </Panel>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- people

function MeanBars({ obj }: { obj: Record<string, number> }) {
  return (
    <div className="meters">
      {Object.entries(obj).map(([k, v]) => <Meter key={k} label={pretty(k)} value={v} right={v} height={5} />)}
    </div>
  );
}

function People({ people }: { people: any }) {
  const [sel, setSel] = useState<string>(people.archetypes[0]?.id);
  const a = people.archetypes.find((x: any) => x.id === sel) || people.archetypes[0];
  const totalW = people.archetypes.reduce((s: number, x: any) => s + (x.weight || 1), 0);
  const names = people.names || {};
  return (
    <div className="stack">
      <Panel title="Archetypes" sub="Procedural characters start from an archetype's means; every value then gets random noise, so two athletes still differ.">
        <div className="chips lib-arch">
          {people.archetypes.map((x: any) => (
            <button key={x.id} className={cx("small", x.id === sel && "on")} onClick={() => setSel(x.id)}>
              {x.label} <span className="dim">{Math.round(((x.weight || 1) / totalW) * 100)}%</span>
            </button>
          ))}
        </div>
        {a && (
          <div className="grid g4 lib-archgrid">
            <div><div className="lib-coefs-h">Traits</div><MeanBars obj={a.traits} /></div>
            <div><div className="lib-coefs-h">Aptitudes</div><MeanBars obj={a.aptitudes} /></div>
            <div><div className="lib-coefs-h">Motives</div><MeanBars obj={a.motives} /></div>
            <div><div className="lib-coefs-h">Interests</div><MeanBars obj={a.interests} /><div className="hint">"sport" picks one or two sports at random.</div></div>
          </div>
        )}
      </Panel>
      <div className="grid g2">
        <Panel title={`School staff (${people.staff.length})`} sub="Staff are autonomous agents with their own traits; coaches' traits shape how they pick teams.">
          <table className="mini">
            <tbody>
              {people.staff.map((s: any) => (
                <tr key={s.id}>
                  <td><b>{s.title} {s.first} {s.last}</b><div className="hint">{s.role_label}</div></td>
                  <td className="small muted">{s.bio || ""}</td>
                  <td className="small">discipline {s.traits.discipline} · competitiveness {s.traits.competitiveness} · empathy {s.traits.empathy}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <Panel title="Households & names" sub="Guardians are household-level actors in v0.1, not autonomous agents.">
          <div className="lib-coefs-h">Guardian styles</div>
          <table className="mini">
            <thead><tr><th>style</th><th className="num">warmth</th><th className="num">strictness</th><th className="num">expectations</th><th className="num">away weekends</th></tr></thead>
            <tbody>
              {people.guardian_styles.map((g: any) => (
                <tr key={g.id}><td>{g.label}</td><td className="num">{g.warmth}</td><td className="num">{g.strictness}</td><td className="num">{g.expectations}</td><td className="num">{Math.round(g.permissive * 50)}%</td></tr>
              ))}
            </tbody>
          </table>
          <div className="lib-coefs-h lib-gap">Name pools</div>
          <div className="chips">
            {Object.entries(names).map(([k, v]: any) => <span key={k} className="tag">{k}: {v.length}</span>)}
            {people.pets && <span className="tag">pet species: {people.pets.map((p: any) => p.species).join(", ")}</span>}
          </div>
        </Panel>
      </div>
      <Panel title={`Featured cast (${people.featured.length})`} sub="Hand-written characters in the demo world. Everyone else is generated.">
        <div className="lib-featured">
          {people.featured.map((f: any) => (
            <div key={f.key} className="lib-feat">
              <div className="row between"><b>{f.first} {f.last}</b><Tag>grade {f.grade}</Tag></div>
              <div className="small muted">{f.archetype} · {f.household} household</div>
              <div className="small">{f.bio}</div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

// ---------------------------------------------------------------- attributes & metrics

function Attributes({ attributes }: { attributes: Record<string, any> }) {
  return (
    <div className="grid g2">
      {Object.entries(attributes).map(([k, layer]: any) => (
        <Panel key={k} title={layer.layer} sub={layer.about}>
          {Object.keys(layer.items).length === 0 ? (
            <div className="dim small">Defined by the skills catalog (see the World tab).</div>
          ) : (
            <dl className="kv">
              {Object.entries(layer.items).map(([name, about]: any) => (
                <React.Fragment key={name}><dt>{name}</dt><dd>{about}</dd></React.Fragment>
              ))}
            </dl>
          )}
        </Panel>
      ))}
    </div>
  );
}

function Metrics({ metrics }: { metrics: Record<string, string> }) {
  return (
    <Panel title={`World metrics (${Object.keys(metrics).length})`} sub="Computed from live state. Used on the overview, in the weekly time series, and to compare experiments.">
      <dl className="kv">
        {Object.entries(metrics).map(([k, v]) => <React.Fragment key={k}><dt className="mono">{k}</dt><dd>{v}</dd></React.Fragment>)}
      </dl>
    </Panel>
  );
}
