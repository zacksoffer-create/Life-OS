// Engine Workshop: tune the rules and the action catalog, round-trip the balancing workbook.
import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { go, useApi, useStore } from "../store";
import { cx, Empty, ErrorBox, Icon, Loading, Panel, pretty, Slider, Tabs, Tag } from "../ui";
import "./lab.css";

const NEED_KEYS = ["energy", "social", "fun", "stress"];
const MOTIVE_KEYS = ["achievement", "approval", "belonging", "pleasure", "altruism", "mastery"];
const TRAIT_KEYS = ["sociability", "confidence", "discipline", "ambition", "impulsivity", "empathy", "competitiveness", "curiosity", "volatility", "loyalty"];
const NUMERIC_FIELDS: [string, string, number][] = [
  ["base", "Base appeal", 50],
  ["risk", "Risk", 50],
  ["interest", "Interest weight", 50],
  ["obligation", "Commitment weight", 50],
  ["importance", "Event importance", 100],
];

export default function Workshop({ route }: { route: string[] }) {
  const tabs: [string, string][] = [["rules", "Rules"], ["actions", "Actions"], ["workbook", "Workbook"], ["log", "Change log"]];
  const tab = tabs.some(([k]) => k === route[1]) ? route[1] : "rules";
  return (
    <div className="stack">
      <div className="page-h">
        <div>
          <h1>Engine Workshop</h1>
          <p>
            The mechanics, as data. Change a weight, a threshold or an action's coefficients and the next simulated slot uses it. Every change
            is validated, logged in the world's history as a lab event, and travels with saves and experiments.
          </p>
        </div>
        <Tabs tabs={tabs} active={tab} onChange={(k) => go(`workshop/${k}`)} />
      </div>
      {tab === "rules" && <RulesTab />}
      {tab === "actions" && <ActionsTab />}
      {tab === "workbook" && <WorkbookTab />}
      {tab === "log" && <LogTab />}
    </div>
  );
}

const same = (a: any, b: any) => (typeof a === "number" && typeof b === "number" ? Math.abs(a - b) < 1e-9 : a === b);

// ------------------------------------------------------------------------------------
// Rules

function RulesTab() {
  const { refresh, bump, toast, world } = useStore();
  const { data, error, reload } = useApi<any>("/api/rules");
  const [staged, setStaged] = useState<Record<string, any>>({});
  const [note, setNote] = useState("");
  const [errors, setErrors] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("");

  if (error) return <ErrorBox error={error} />;
  if (!data) return <Loading what="Loading rules" />;
  const values = data.values;
  const defaults = data.defaults;
  const nStaged = Object.keys(staged).length;
  const modifiedCount = Object.keys(values).filter((k) => !same(values[k], defaults[k])).length;
  const locked = !!world?.busy;

  const stage = (k: string, v: any) => {
    setErrors(null);
    setStaged((s) => {
      const n = { ...s };
      if (same(v, values[k])) delete n[k];
      else n[k] = v;
      return n;
    });
  };

  const apply = async () => {
    setBusy(true);
    setErrors(null);
    try {
      const r = await api.put("/api/rules", { changes: staged, note });
      toast(r.applied.length ? `Applied ${r.applied.length} rule change${r.applied.length > 1 ? "s" : ""}. Rules version ${r.version}.` : "Nothing changed.", "good");
      setStaged({});
      setNote("");
      await refresh();
      bump();
      reload();
    } catch (e: any) {
      setErrors(e.errors && e.errors.length ? e.errors : [e.message]);
      toast("Some changes were rejected; nothing was applied.", "bad");
    } finally {
      setBusy(false);
    }
  };

  const reset = async (keys: string[] | null, what: string) => {
    if (!window.confirm(`Reset ${what} to the default values?`)) return;
    setBusy(true);
    try {
      const r = await api.post("/api/rules/reset", keys ? { keys } : {});
      toast(r.applied.length ? `Reset ${r.applied.length} parameter${r.applied.length > 1 ? "s" : ""}.` : "Already at defaults.", "good");
      setStaged((s) => {
        const n = { ...s };
        for (const k of keys || Object.keys(n)) delete n[k];
        return n;
      });
      await refresh();
      bump();
      reload();
    } catch (e: any) {
      toast(e.message, "bad");
    } finally {
      setBusy(false);
    }
  };

  const f = filter.trim().toLowerCase();
  return (
    <div className="stack">
      <div className="callout">
        Changes take effect from the <b>next simulated slot</b>; nothing that already happened is rewritten. Each applied batch becomes a
        <b> lab event</b> in the History Explorer, gets a rules version that decision traces point back to, and is stored with saves. Values are
        experimental design values, not established truths: tune them and watch what changes. {modifiedCount > 0 && <>Currently <b>{modifiedCount}</b> parameters differ from the defaults.</>}
      </div>
      <div className="applybar">
        <b>{nStaged ? `${nStaged} staged change${nStaged > 1 ? "s" : ""}` : "No staged changes"}</b>
        <input type="text" placeholder="Note for the change log (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
        <button className="primary" disabled={!nStaged || busy || locked} onClick={apply}>Apply {nStaged || ""} change{nStaged === 1 ? "" : "s"}</button>
        <button disabled={!nStaged || busy} onClick={() => { setStaged({}); setErrors(null); }}>Discard</button>
        <span className="spacer" />
        <input type="search" placeholder="Find a parameter..." value={filter} onChange={(e) => setFilter(e.target.value)} style={{ maxWidth: 200 }} />
        <button className="danger small" disabled={busy || locked || modifiedCount === 0} onClick={() => reset(null, "every parameter")}>Reset all</button>
        {locked && <span className="hint">The simulation is advancing; apply when it finishes.</span>}
      </div>
      {errors && (
        <div className="errorbox">
          The server rejected these changes (nothing was applied):
          <ul className="errlist">{errors.map((e) => <li key={e}>{e}</li>)}</ul>
        </div>
      )}
      {data.sections.map((sec: any) => {
        const params = sec.params.filter((p: any) => !f || p.label.toLowerCase().includes(f) || p.key.includes(f) || p.description.toLowerCase().includes(f));
        if (!params.length) return null;
        const secMod = sec.params.filter((p: any) => !same(values[p.key], defaults[p.key])).map((p: any) => p.key);
        return (
          <Panel key={sec.id} title={sec.label} sub={sec.description}
            actions={secMod.length > 0 && (
              <button className="small" disabled={busy || locked} onClick={() => reset(secMod, `the ${secMod.length} modified parameter(s) in ${sec.label}`)}>
                Reset section
              </button>
            )}>
            <div className="params">
              {params.map((p: any) => (
                <ParamRow key={p.key} p={p} value={values[p.key]} def={defaults[p.key]} staged={staged[p.key]} isStaged={p.key in staged}
                  onStage={(v: any) => stage(p.key, v)} />
              ))}
            </div>
          </Panel>
        );
      })}
    </div>
  );
}

function ParamRow({ p, value, def, staged, isStaged, onStage }: any) {
  const cur = isStaged ? staged : value;
  const [text, setText] = useState(String(cur));
  useEffect(() => {
    setText((t) => (t !== "" && Number(t) === cur ? t : String(cur)));
  }, [cur]);
  const modified = !same(value, def);
  const outOfRange = p.type !== "bool" && typeof cur === "number" && ((p.min !== undefined && cur < p.min) || (p.max !== undefined && cur > p.max));
  return (
    <div className={cx("param", isStaged ? "staged" : modified && "modified")}>
      <div>
        <div className="p-l">{p.label}</div>
        <div className="p-k">{p.key}</div>
        <div className="p-d">{p.description}</div>
      </div>
      <div className="p-c">
        {p.type === "bool" ? (
          <div className="toggle">
            <button className={cx(cur === true && "on")} onClick={() => onStage(true)}>On</button>
            <button className={cx(cur === false && "on")} onClick={() => onStage(false)}>Off</button>
          </div>
        ) : (
          <>
            <Slider value={typeof cur === "number" ? cur : def} min={p.min} max={p.max} step={p.step || (p.type === "int" ? 1 : 0.1)} onChange={(v: number) => onStage(p.type === "int" ? Math.round(v) : v)} />
            <input type="number" value={text} step={p.step || "any"}
              onChange={(e) => {
                setText(e.target.value);
                const v = Number(e.target.value);
                if (e.target.value !== "" && Number.isFinite(v)) onStage(v);
              }} />
          </>
        )}
      </div>
      <div className="p-m">
        <span>default {String(def)}{p.type !== "bool" && <> · {p.min}-{p.max}</>}</span>
        {isStaged && <span className="was">was {String(value)}</span>}
        {outOfRange && <span className="neg">outside the allowed range</span>}
        {!same(cur, def) && <button className="small ghost" onClick={() => onStage(def)}>reset</button>}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------------------------
// Actions

function ActionsTab() {
  const { data, error, reload } = useApi<any>("/api/catalogs");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  if (error) return <ErrorBox error={error} />;
  if (!data) return <Loading what="Loading the action catalog" />;
  const actions: any[] = data.actions;
  const ql = q.trim().toLowerCase();
  const shown = actions.filter((a) => !ql || a.id.includes(ql) || a.label.toLowerCase().includes(ql) || a.category.includes(ql));
  const cats = Array.from(new Set(shown.map((a) => a.category)));
  const current = actions.find((a) => a.id === (sel || actions[0]?.id));
  const overridden = actions.filter((a) => a.overridden).length;
  return (
    <div className="grid g-side">
      <Panel title="Actions" sub={`${actions.length} actions · ${overridden} edited`} pad>
        <input type="search" placeholder="Search actions..." value={q} onChange={(e) => setQ(e.target.value)} style={{ width: "100%", marginBottom: 8 }} />
        <div className="actlist">
          {cats.map((cat) => (
            <React.Fragment key={cat}>
              <div className="actcat">{cat}</div>
              {shown.filter((a) => a.category === cat).map((a) => (
                <div key={a.id} className={cx("actitem", current?.id === a.id && "on")} onClick={() => setSel(a.id)}>
                  <div>
                    <div>{a.label}</div>
                    <div className="id">{a.id}</div>
                  </div>
                  <div className="row" style={{ gap: 4 }}>
                    {a.overridden && <Tag tone="warn">edited</Tag>}
                    {!a.enabled && <Tag tone="bad">off</Tag>}
                  </div>
                </div>
              ))}
            </React.Fragment>
          ))}
          {!shown.length && <Empty>No action matches.</Empty>}
        </div>
      </Panel>
      {current ? <ActionEditor key={current.id + JSON.stringify(current.override || {})} a={current} onSaved={reload} /> : <Empty>Pick an action.</Empty>}
    </div>
  );
}

function ActionEditor({ a, onSaved }: { a: any; onSaved: () => void }) {
  const { toast, refresh, bump, world } = useStore();
  const [edit, setEdit] = useState<Record<string, any>>({});
  const [errors, setErrors] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const locked = !!world?.busy;

  const val = (field: string, key?: string) => {
    if (key) {
      const e = edit[field]?.[key];
      return e !== undefined ? e : a[field]?.[key] ?? 0;
    }
    return edit[field] !== undefined ? edit[field] : a[field];
  };
  const setVal = (field: string, v: any, key?: string) => {
    setErrors(null);
    setEdit((s) => {
      const n = { ...s };
      if (key) {
        const sub = { ...(n[field] || {}) };
        const orig = a[field]?.[key] ?? 0;
        if (same(Number(v), orig) && v !== "") delete sub[key];
        else sub[key] = v;
        if (Object.keys(sub).length) n[field] = sub;
        else delete n[field];
      } else {
        if (same(field === "enabled" ? v : Number(v), a[field]) && v !== "") delete n[field];
        else n[field] = v;
      }
      return n;
    });
  };
  const changes = useMemo(() => {
    const out: Record<string, any> = {};
    for (const [k, v] of Object.entries(edit)) {
      if (v && typeof v === "object") {
        const sub: Record<string, number> = {};
        for (const [kk, vv] of Object.entries(v)) sub[kk] = vv === "" ? (NaN as any) : Number(vv);
        out[k] = sub;
      } else out[k] = k === "enabled" ? v : v === "" ? NaN : Number(v);
    }
    return out;
  }, [edit]);
  const nChanges = Object.values(changes).reduce((n: number, v: any) => n + (v && typeof v === "object" ? Object.keys(v).length : 1), 0);

  const save = async () => {
    setBusy(true);
    setErrors(null);
    try {
      const bad = JSON.stringify(changes).includes("null");
      if (bad) throw Object.assign(new Error("Every edited field needs a number."), { errors: ["Every edited field needs a number."] });
      await api.put(`/api/catalogs/actions/${a.id}`, { changes });
      toast(`Saved changes to "${a.label}".`, "good");
      setEdit({});
      await refresh();
      bump();
      onSaved();
    } catch (e: any) {
      setErrors(e.errors && e.errors.length ? e.errors : [e.message]);
    } finally {
      setBusy(false);
    }
  };
  const resetOverride = async () => {
    if (!window.confirm(`Throw away every edit to "${a.label}" and go back to the catalog file's values?`)) return;
    setBusy(true);
    try {
      await api.del(`/api/catalogs/actions/${a.id}/override`);
      toast(`"${a.label}" is back to the catalog values.`, "good");
      setEdit({});
      await refresh();
      bump();
      onSaved();
    } catch (e: any) {
      toast(e.message, "bad");
    } finally {
      setBusy(false);
    }
  };

  const coefBlock = (field: string, title: string, keys: string[], help: string) => (
    <div className="stack" style={{ gap: 6 }}>
      <div className="row between">
        <b className="small">{title}</b>
        <span className="hint">{help}</span>
      </div>
      <div className="coef-grid">
        {keys.map((k) => {
          const changed = edit[field]?.[k] !== undefined;
          return (
            <div className={cx("coef", changed && "changed")} key={k}>
              <label>{pretty(k)}{(a[field]?.[k] ?? 0) !== 0 && !changed && <span className="dim"> · set</span>}</label>
              <input type="number" step={0.1} min={-10} max={10} value={val(field, k)} onChange={(e) => setVal(field, e.target.value, k)} />
            </div>
          );
        })}
      </div>
    </div>
  );

  const ttKeys = Object.keys(a.target_terms || {});
  return (
    <div className="stack">
      <Panel
        title={<span>{a.label} <span className="mono dim">{a.id}</span></span>}
        sub={`${a.category} · slots: ${a.slots.join(", ")} · roles: ${a.roles.join(", ")} · target: ${a.target || "none"} · resolver: ${a.resolver}`}
        actions={
          <>
            {a.overridden && <Tag tone="warn">edited in this world</Tag>}
            {a.overridden && <button className="small" disabled={busy || locked} onClick={resetOverride}>Reset to catalog</button>}
          </>
        }
      >
        <div className="stack">
          <div className="formula">
            utility = base + needs + motives + traits + interest + feelings toward the target + goals + memories + learned experience + habit +
            peer conformity - risk + commitment + situation; then one option is drawn by softmax with the person's temperature.
            <div className="dim" style={{ marginTop: 6 }}>
              Needs coefficients &gt; 0 mean the action relieves that need (more attractive the more urgent it is); &lt; 0 means it costs it. Motive and
              trait coefficients scale the person's own motive or trait. Everything is multiplied again by the global weights on the Rules tab.
            </div>
          </div>
          {a.requires?.length > 0 && <div className="small muted">Requires: {a.requires.map((r: string) => <span key={r} className="rule-chip" style={{ marginRight: 4 }}>{r}</span>)}</div>}
          <div className="row">
            <span className="field-l">Enabled</span>
            <div className="toggle">
              <button className={cx(val("enabled") === true && "on")} onClick={() => setVal("enabled", true)}>On</button>
              <button className={cx(val("enabled") === false && "on")} onClick={() => setVal("enabled", false)}>Off</button>
            </div>
            <span className="hint">Disabled actions are never offered to anyone.</span>
          </div>
          <div className="coef-grid">
            {NUMERIC_FIELDS.map(([k, label, lim]) => (
              <div className={cx("coef", edit[k] !== undefined && "changed")} key={k}>
                <label>{label}</label>
                <input type="number" step={k === "importance" ? 1 : 0.1} min={-lim} max={lim} value={val(k) ?? 0} onChange={(e) => setVal(k, e.target.value)} />
              </div>
            ))}
          </div>
          {coefBlock("needs", "Needs", NEED_KEYS, "-10 to 10, x need urgency x 30")}
          {coefBlock("motives", "Motives", MOTIVE_KEYS, "-10 to 10, x the person's motive x 15")}
          {coefBlock("traits", "Traits", TRAIT_KEYS, "-10 to 10, x (trait - 50) / 50 x 10")}
          {ttKeys.length > 0 && coefBlock("target_terms", "Toward the target", ttKeys, "only terms this action has")}
          <div className="row between">
            <span className="small muted">{nChanges ? `${nChanges} edited field${nChanges > 1 ? "s" : ""}` : "No edits"}</span>
            <div className="row">
              <button disabled={!nChanges || busy} onClick={() => { setEdit({}); setErrors(null); }}>Discard</button>
              <button className="primary" disabled={!nChanges || busy || locked} onClick={save}>Save to this world</button>
            </div>
          </div>
          {errors && (
            <div className="errorbox">
              Rejected:
              <ul className="errlist">{errors.map((e) => <li key={e}>{e}</li>)}</ul>
            </div>
          )}
        </div>
      </Panel>
      <Panel title="Resolver parameters" sub="What happens when the action is carried out. Read-only here; edit backend/data/actions.json to change them.">
        <pre className="json">{JSON.stringify(a.params || {}, null, 2)}</pre>
        {a.override && (
          <>
            <div className="field-l" style={{ marginTop: 10 }}>This world's override</div>
            <pre className="json">{JSON.stringify(a.override, null, 2)}</pre>
          </>
        )}
      </Panel>
    </div>
  );
}

// ------------------------------------------------------------------------------------
// Workbook

function WorkbookTab() {
  const { toast, refresh, bump, world } = useStore();
  const [report, setReport] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const upload = async (f: File | undefined) => {
    if (!f) return;
    setBusy(true);
    setErr(null);
    setReport(null);
    try {
      const r = await api.upload("/api/import/workbook", f);
      setReport(r);
      const n = r.rules.length + r.actions.length + r.characters.length;
      toast(n ? `Imported ${n} change set${n > 1 ? "s" : ""}${r.errors.length ? `, ${r.errors.length} rejected` : ""}.` : "No differences found in the workbook.", r.errors.length ? "warn" : "good");
      await refresh();
      bump();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="grid g2">
      <Panel title="Balancing workbook" sub="The start of the master spreadsheet workflow.">
        <div className="stack">
          <p className="muted" style={{ margin: 0 }}>
            Exports the current world's <b>Rules</b>, <b>Actions</b> (base, risk and every need/motive/trait coefficient), <b>Characters</b> (traits,
            aptitudes, motives, bio) and <b>Groups</b> to Excel. Edit the white columns, save, and import it here. Every cell goes through the same
            validation as the app; anything invalid is listed and skipped.
          </p>
          <div>
            <a href="/api/export/workbook" download>
              <button className="primary"><Icon name="book" size={15} /> Download balancing workbook (.xlsx)</button>
            </a>
          </div>
          <div className="filebox">
            <span className="field-l">Import an edited workbook</span>
            <input type="file" accept=".xlsx" disabled={busy || !!world?.busy} onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ""; }} />
            {busy && <span className="hint">Importing...</span>}
          </div>
          {err && <ErrorBox error={err} />}
        </div>
      </Panel>
      <Panel title="Import report">
        {!report ? (
          <Empty>Import a workbook to see exactly what changed and what was rejected.</Empty>
        ) : (
          <div className="stack">
            <div>
              <div className="field-l">Rules changed ({report.rules.length})</div>
              {report.rules.length ? (
                <table className="mini"><tbody>
                  {report.rules.map((r: any) => <tr key={r[0]}><td className="mono">{r[0]}</td><td className="num">{String(r[1])}</td><td>&rarr;</td><td className="num"><b>{String(r[2])}</b></td></tr>)}
                </tbody></table>
              ) : <span className="dim small">none</span>}
            </div>
            <div>
              <div className="field-l">Actions changed ({report.actions.length})</div>
              {report.actions.length ? report.actions.map((x: any) => (
                <div key={x.action} className="small"><span className="mono">{x.action}</span> <span className="dim">{JSON.stringify(x.changes)}</span></div>
              )) : <span className="dim small">none</span>}
            </div>
            <div>
              <div className="field-l">Characters changed ({report.characters.length})</div>
              {report.characters.length ? report.characters.map((x: any) => (
                <div key={x.id} className="small"><a href={`#/characters/${x.id}`}>{x.id}</a> <span className="dim">{JSON.stringify(x.changes)}</span></div>
              )) : <span className="dim small">none</span>}
            </div>
            <div>
              <div className="field-l">Rejected cells ({report.errors.length})</div>
              {report.errors.length ? <ul className="errlist">{report.errors.map((e: string, i: number) => <li key={i}>{e}</li>)}</ul> : <span className="dim small">none</span>}
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}

// ------------------------------------------------------------------------------------
// Change log

function LogTab() {
  const { data, error } = useApi<any>("/api/rules");
  if (error) return <ErrorBox error={error} />;
  if (!data) return <Loading />;
  const labels: Record<string, string> = {};
  for (const s of data.sections) for (const p of s.params) labels[p.key] = p.label;
  return (
    <Panel title="Rule change log" sub={`Newest first. Current rules version ${data.version}. Action edits appear in the History Explorer as lab events.`}>
      {!data.changes.length ? (
        <Empty>No rule changes in this world yet. Everything is at the values it started with.</Empty>
      ) : (
        <table className="mini">
          <thead><tr><th>day</th><th>changes</th><th>note</th><th>version</th></tr></thead>
          <tbody>
            {data.changes.map((c: any, i: number) => (
              <tr key={i}>
                <td className="num">day {c.day}</td>
                <td>
                  {c.changes.map((x: any) => (
                    <div key={x[0]}>
                      <span title={x[0]}>{labels[x[0]] || x[0]}</span>: <span className="dim">{String(x[1])}</span> &rarr; <b>{String(x[2])}</b>
                    </div>
                  ))}
                </td>
                <td className="muted">{c.note || "-"}</td>
                <td className="mono">{c.version}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}
