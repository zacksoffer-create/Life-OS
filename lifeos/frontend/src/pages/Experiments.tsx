// Experiment Center: build scenarios, run isolated seeded comparisons, read the results honestly.
import React, { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { go, useApi, useStore } from "../store";
import { cx, Empty, ErrorBox, Icon, LineChart, Loading, Meter, Name, Panel, pretty, signed, Stat, Tag } from "../ui";
import "./lab.css";

const PALETTE = ["#9aa1c4", "#57d9c3", "#ffb547", "#9b8cff", "#ff8fc7", "#6bb6ff", "#66d98f", "#ff6b81"];
const DEFAULT_FOCUS = ["mutual_friendships", "cliques", "exclusions", "conflicts", "popularity_gini", "avg_mood", "avg_stress", "avg_gpa"];
const SERIES_KEYS = ["mutual_friendships", "avg_friends", "isolated_students", "rivalries", "couples", "cliques",
  "popularity_gini", "avg_mood", "avg_stress", "avg_gpa", "conflicts", "exclusions", "rumors"];

export default function Experiments({ route }: { route: string[] }) {
  const id = route[1];
  if (id && /^\d+$/.test(id)) return <ExperimentResult id={Number(id)} />;
  return <ExperimentHome />;
}

// ------------------------------------------------------------------------------------
// shared helpers

function useRuleSchema() {
  const { data } = useApi<any>("/api/rules");
  return useMemo(() => {
    const params: Record<string, any> = {};
    for (const s of data?.sections || []) for (const p of s.params) params[p.key] = { ...p, sectionLabel: s.label };
    return { sections: data?.sections || [], params };
  }, [data]);
}

function RuleChips({ rules, params }: { rules: Record<string, any>; params: Record<string, any> }) {
  const entries = Object.entries(rules || {});
  if (!entries.length) return <span className="dim small">No rule changes (defaults of the base world)</span>;
  return (
    <div className="chips">
      {entries.map(([k, v]) => (
        <span className="rule-chip" key={k} title={params[k]?.description || k}>
          {params[k]?.label || k} = <b>{String(v)}</b>
          {params[k] && params[k].default !== undefined && <span className="dim"> (default {String(params[k].default)})</span>}
        </span>
      ))}
    </div>
  );
}

function baseLabel(b: any): string {
  if (!b) return "unknown base";
  if (b.kind === "fresh") return `Fresh world - generation seed ${b.gen_seed ?? 1234}, ${b.students ?? 36} students${b.featured === false ? "" : ", demo cast"}`;
  if (b.kind === "current") return `Snapshot of the current world${b.date ? ` on ${b.date}` : ""}`;
  if (b.kind === "save") return `Save #${b.save_id}${b.date ? ` (${b.date})` : ""}`;
  return b.kind;
}

function parseSeeds(text: string): { seeds: number[]; error: string | null } {
  const parts = text.split(/[\s,]+/).filter(Boolean);
  if (!parts.length) return { seeds: [], error: "Enter at least one seed." };
  const seeds: number[] = [];
  for (const p of parts) {
    if (!/^-?\d+$/.test(p)) return { seeds: [], error: `"${p}" is not a whole number.` };
    seeds.push(parseInt(p, 10));
  }
  if (new Set(seeds).size !== seeds.length) return { seeds, error: "Seeds must be distinct." };
  return { seeds, error: null };
}

function estimateSeconds(days: number, students: number, runs: number) {
  const perRun = Math.max(0.5, (days / 365) * 15 * Math.max(0.4, students / 36));
  const cores = Math.max(1, Math.min(6, (navigator as any).hardwareConcurrency || 2));
  return Math.ceil(runs / cores) * perRun;
}

function fmtSecs(s: number) {
  if (s < 60) return `${Math.round(s)}s`;
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

function fmtNum(v: any, d = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return "-";
  if (typeof v !== "number") return String(v);
  const r = Math.abs(v) >= 100 ? 0 : d;
  return v.toFixed(r);
}

// ------------------------------------------------------------------------------------
// home: presets, builder, past experiments

interface VariantDraft {
  name: string;
  rules: [string, any][];
}
interface Draft {
  name: string;
  about: string;
  baseKind: "fresh" | "current" | "save";
  genSeed: string;
  students: string;
  saveId: string;
  days: string;
  seeds: string;
  variants: VariantDraft[];
  focus: string[];
}

const emptyDraft = (): Draft => ({
  name: "My experiment",
  about: "",
  baseKind: "fresh",
  genSeed: "1234",
  students: "36",
  saveId: "",
  days: "120",
  seeds: "1, 2, 3",
  variants: [
    { name: "Baseline", rules: [] },
    { name: "Variant", rules: [] },
  ],
  focus: DEFAULT_FOCUS,
});

function presetToDraft(p: any): Draft {
  return {
    name: p.name,
    about: p.about || "",
    baseKind: "fresh",
    genSeed: "1234",
    students: "36",
    saveId: "",
    days: String(p.days),
    seeds: (p.seeds || []).join(", "),
    variants: p.variants.map((v: any) => ({ name: v.name, rules: Object.entries(v.rules || {}) })),
    focus: p.metrics || DEFAULT_FOCUS,
  };
}

function draftToSpec(d: Draft) {
  const { seeds } = parseSeeds(d.seeds);
  const base: any =
    d.baseKind === "fresh"
      ? { kind: "fresh", gen_seed: parseInt(d.genSeed, 10), students: parseInt(d.students, 10) }
      : d.baseKind === "save"
      ? { kind: "save", save_id: parseInt(d.saveId, 10) }
      : { kind: "current" };
  return {
    name: d.name.trim() || "Untitled experiment",
    about: d.about,
    base,
    days: parseInt(d.days, 10),
    seeds,
    variants: d.variants.map((v) => ({ name: v.name.trim(), rules: Object.fromEntries(v.rules.filter(([k]) => k)) })),
    metrics: d.focus,
  };
}

function ExperimentHome() {
  const { toast } = useStore();
  const { data, error, reload } = useApi<any>("/api/experiments");
  const cat = useApi<any>("/api/catalogs");
  const saves = useApi<any[]>("/api/saves");
  const schema = useRuleSchema();
  const [draft, setDraft] = useState<Draft>(emptyDraft());
  const [showBuilder, setShowBuilder] = useState(false);
  const [submitErr, setSubmitErr] = useState<string[] | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const running = (data?.experiments || []).some((e: any) => e.status === "running");
  useEffect(() => {
    if (!running) return;
    const t = setInterval(reload, 1500);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running]);
  const builderRef = useRef<HTMLDivElement>(null);
  const [openCount, setOpenCount] = useState(0);
  useEffect(() => {
    if (showBuilder && builderRef.current) builderRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [showBuilder, openCount]);
  const openBuilder = (d?: Draft) => {
    if (d) setDraft(d);
    setShowBuilder(true);
    setSubmitErr(null);
    setOpenCount((n) => n + 1);
  };

  const metricInfo: Record<string, string> = cat.data?.metrics || {};

  const launch = async (spec: any) => {
    setSubmitErr(null);
    setSubmitting(true);
    try {
      const r = await api.post("/api/experiments", spec);
      toast(`Experiment started: ${r.runs} isolated runs`, "good");
      go(`experiments/${r.id}`);
    } catch (e: any) {
      const errs = e.errors && e.errors.length ? e.errors : String(e.message).split("; ");
      setSubmitErr(errs);
      toast("The experiment was rejected - see the messages in the builder.", "bad");
      setShowBuilder(true);
      setOpenCount((n) => n + 1);
    } finally {
      setSubmitting(false);
    }
  };

  const runPreset = (p: any) =>
    launch({ name: p.name, about: p.about, base: { kind: "fresh", gen_seed: 1234, students: 36 }, days: p.days, seeds: p.seeds, variants: p.variants, metrics: p.metrics });

  const del = async (e: any) => {
    if (!window.confirm(`Delete the experiment "${e.name}" and its results?`)) return;
    try {
      await api.del(`/api/experiments/${e.id}`);
      reload();
    } catch (err: any) {
      toast(err.message, "bad");
    }
  };

  return (
    <div className="stack">
      <div className="page-h">
        <div>
          <h1>Experiment Center</h1>
          <p>
            Take one starting world, run it forward under different rules, and compare. Every run gets its own copy of the base world in its
            own worker process, so runs never share state. Variants reuse the baseline's seeds, so each pair differs only by the rule change and
            how far it rippled.
          </p>
        </div>
        <div className="row">
          <button className="primary" onClick={() => openBuilder()}>
            <Icon name="plus" size={15} /> New experiment
          </button>
        </div>
      </div>

      <Panel title="Ready-made experiments" sub="Each runs on a fresh copy of the demo school (generation seed 1234, 36 students). Customize to change anything.">
        {!data ? (
          <Loading />
        ) : (
          <div className="presets">
            {data.presets.map((p: any) => (
              <div className="preset" key={p.id}>
                <h4>{p.name}</h4>
                <p>{p.about}</p>
                <div className="meta">
                  <span>{p.days} days</span>
                  <span>{p.seeds.length === 1 ? "1 seed (deterministic)" : `${p.seeds.length} seeds (repeated runs)`}</span>
                  <span>{p.variants.length * p.seeds.length} runs</span>
                </div>
                <div className="stack" style={{ gap: 4 }}>
                  {p.variants.slice(1).map((v: any) => (
                    <div key={v.name} className="small">
                      <b>{v.name}:</b> <RuleChips rules={v.rules} params={schema.params} />
                    </div>
                  ))}
                </div>
                <div className="row">
                  <button className="primary small" disabled={submitting} onClick={() => runPreset(p)}>
                    <Icon name="play" size={13} /> Run
                  </button>
                  <button className="small" onClick={() => openBuilder(presetToDraft(p))}>
                    Customize
                  </button>
                  <span className="hint">about {fmtSecs(estimateSeconds(p.days, 36, p.variants.length * p.seeds.length))}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      {showBuilder && (
        <div ref={builderRef}>
        <Builder
          draft={draft}
          setDraft={setDraft}
          schema={schema}
          metricInfo={metricInfo}
          saves={saves.data || []}
          errors={submitErr}
          submitting={submitting}
          onRun={() => launch(draftToSpec(draft))}
          onClose={() => setShowBuilder(false)}
        />
        </div>
      )}

      <Panel title="Past experiments" sub="Results are stored in the local database and survive restarts.">
        <ErrorBox error={error} />
        {!data ? (
          <Loading />
        ) : !data.experiments.length ? (
          <Empty>No experiments yet. Run a preset above to see what a comparison looks like.</Empty>
        ) : (
          <table className="mini">
            <thead>
              <tr>
                <th>name</th><th>status</th><th>days</th><th>seeds</th><th>variants</th><th>started</th><th></th>
              </tr>
            </thead>
            <tbody>
              {data.experiments.map((e: any) => (
                <tr key={e.id} className="click" onClick={() => go(`experiments/${e.id}`)}>
                  <td><b>{e.name}</b></td>
                  <td style={{ minWidth: 140 }}>
                    {e.status === "running" ? (
                      <div>
                        <Meter value={e.progress?.done || 0} max={Math.max(1, e.progress?.total || 1)} color="var(--accent-2)" />
                        <span className="hint">{e.progress ? `${e.progress.done} of ${e.progress.total} runs` : "running"}</span>
                      </div>
                    ) : (
                      <Tag tone={e.status === "done" ? "good" : "bad"}>{e.status}</Tag>
                    )}
                  </td>
                  <td className="num">{e.days}</td>
                  <td className="mono">{(e.seeds || []).join(", ")}</td>
                  <td>{(e.variants || []).join(" vs ")}</td>
                  <td className="dim">{new Date(e.created * 1000).toLocaleString()}</td>
                  <td onClick={(ev) => ev.stopPropagation()}>
                    <button className="small ghost" onClick={() => del(e)} disabled={e.status === "running"}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

function Builder({ draft, setDraft, schema, metricInfo, saves, errors, submitting, onRun, onClose }: any) {
  const d: Draft = draft;
  const set = (patch: Partial<Draft>) => setDraft({ ...d, ...patch });
  const seedInfo = parseSeeds(d.seeds);
  const days = parseInt(d.days, 10);
  const students = d.baseKind === "fresh" ? parseInt(d.students, 10) || 36 : 36;
  const runs = d.variants.length * seedInfo.seeds.length;
  const local: string[] = [];
  if (!(days >= 7 && days <= 730)) local.push("Days must be between 7 and 730.");
  if (seedInfo.error) local.push(seedInfo.error);
  if (d.variants.length < 2) local.push("Add at least one variant besides the baseline.");
  const names = d.variants.map((v) => v.name.trim());
  if (names.some((n) => !n)) local.push("Every variant needs a name.");
  if (new Set(names).size !== names.length) local.push("Variant names must be different.");
  if (runs > 60) local.push("At most 60 runs (variants x seeds) per experiment.");
  if (d.baseKind === "save" && !d.saveId) local.push("Pick a save to use as the base.");
  if (d.variants.some((v) => v.rules.some(([k, val]) => !k || val === "" || val === null)))
    local.push("Every rule change needs a rule and a value (or remove it).");
  if (d.baseKind === "fresh" && !(students >= 8 && students <= 60)) local.push("Students must be between 8 and 60.");

  const updVariant = (i: number, v: VariantDraft) => set({ variants: d.variants.map((x, j) => (j === i ? v : x)) });
  const metricKeys = Object.keys(metricInfo).length ? Object.keys(metricInfo) : DEFAULT_FOCUS;

  return (
    <Panel
      title="Experiment builder"
      sub="Everything here is sent to the server and validated there too."
      className="builder"
      actions={<button className="ghost small" onClick={onClose}><Icon name="close" size={14} /> Close</button>}
    >
      <div className="stack">
        <div className="form-grid">
          <div className="field" style={{ gridColumn: "span 2" }}>
            <label>Name</label>
            <input type="text" value={d.name} onChange={(e) => set({ name: e.target.value })} />
          </div>
          <div className="field">
            <label>Days to simulate</label>
            <input type="number" min={7} max={730} value={d.days} onChange={(e) => set({ days: e.target.value })} />
            <span className="hint">7-730. A school year is 365.</span>
          </div>
          <div className="field">
            <label>Seeds</label>
            <input type="text" value={d.seeds} onChange={(e) => set({ seeds: e.target.value })} />
            <span className="hint">
              {seedInfo.seeds.length === 1
                ? "One seed: a deterministic paired comparison of two exact timelines."
                : `${seedInfo.seeds.length} seeds: a repeated-run measurement with intervals.`}
            </span>
          </div>
        </div>

        <div className="field">
          <span className="field-l">Base scenario</span>
          <div className="row">
            <div className="tabs">
              {[["fresh", "Fresh world"], ["current", "Current world"], ["save", "A save"]].map(([k, l]) => (
                <button key={k} className={cx("tab", d.baseKind === k && "on")} onClick={() => set({ baseKind: k as any })}>{l}</button>
              ))}
            </div>
            {d.baseKind === "fresh" && (
              <>
                <label className="small muted">generation seed</label>
                <input type="number" style={{ width: 100 }} value={d.genSeed} onChange={(e) => set({ genSeed: e.target.value })} />
                <label className="small muted">students</label>
                <input type="number" style={{ width: 80 }} min={8} max={60} value={d.students} onChange={(e) => set({ students: e.target.value })} />
                <span className="hint">The same generation seed always builds the same school.</span>
              </>
            )}
            {d.baseKind === "current" && <span className="hint">Copies the world as it is right now (history is left out of the copy).</span>}
            {d.baseKind === "save" && (
              <select value={d.saveId} onChange={(e) => set({ saveId: e.target.value })}>
                <option value="">Choose a save...</option>
                {saves.map((s: any) => (
                  <option key={s.id} value={s.id}>#{s.id} {s.name} ({s.date_label})</option>
                ))}
              </select>
            )}
          </div>
        </div>

        <div className="field">
          <span className="field-l">Variants (the first is the baseline everything is compared to)</span>
          <div className="grid g2">
            {d.variants.map((v, i) => (
              <VariantEditor key={i} index={i} v={v} schema={schema} onChange={(nv: VariantDraft) => updVariant(i, nv)}
                onRemove={d.variants.length > 2 && i > 0 ? () => set({ variants: d.variants.filter((_, j) => j !== i) }) : null} />
            ))}
          </div>
          <div>
            <button className="small" onClick={() => set({ variants: [...d.variants, { name: `Variant ${d.variants.length}`, rules: [] }] })}>
              <Icon name="plus" size={13} /> Add variant
            </button>
          </div>
        </div>

        <div className="field">
          <span className="field-l">Focus metrics (shown first in the results; every metric is still computed)</span>
          <div className="metric-chips">
            {metricKeys.map((k) => (
              <span key={k} className={cx("metric-chip", d.focus.includes(k) && "on")} title={metricInfo[k] || ""}
                onClick={() => set({ focus: d.focus.includes(k) ? d.focus.filter((x) => x !== k) : [...d.focus, k] })}>
                {pretty(k)}
              </span>
            ))}
          </div>
        </div>

        <div className="field">
          <label>Notes (optional)</label>
          <input type="text" value={d.about} onChange={(e) => set({ about: e.target.value })} placeholder="What are you trying to find out?" />
        </div>

        <div className="row between">
          <div className="run-summary">
            <span><b>{runs}</b> runs ({d.variants.length} variants x {seedInfo.seeds.length} seeds)</span>
            {runs > 0 && days >= 7 && <span>roughly <b>{fmtSecs(estimateSeconds(days, students, runs))}</b>, in parallel across CPU cores</span>}
          </div>
          <button className="primary" disabled={submitting || local.length > 0} onClick={onRun}>
            <Icon name="flask" size={15} /> {submitting ? "Starting..." : "Run experiment"}
          </button>
        </div>
        {local.length > 0 && <ul className="errlist">{local.map((e) => <li key={e}>{e}</li>)}</ul>}
        {errors && errors.length > 0 && (
          <div className="errorbox">
            The server rejected this experiment:
            <ul className="errlist">{errors.map((e: string) => <li key={e}>{e}</li>)}</ul>
          </div>
        )}
      </div>
    </Panel>
  );
}

function VariantEditor({ index, v, schema, onChange, onRemove }: any) {
  const params = schema.params;
  const used = new Set(v.rules.map(([k]: any) => k));
  const setRule = (i: number, k: string, val: any) => onChange({ ...v, rules: v.rules.map((r: any, j: number) => (j === i ? [k, val] : r)) });
  return (
    <div className={cx("variant-box", index === 0 && "base")}>
      <div className="row between">
        <div className="row" style={{ flex: 1 }}>
          <span className="swatch" style={{ background: PALETTE[index % PALETTE.length], width: 10, height: 10, borderRadius: 3, display: "inline-block" }} />
          <input type="text" value={v.name} onChange={(e) => onChange({ ...v, name: e.target.value })} style={{ flex: 1 }} />
          {index === 0 && <Tag tone="accent">baseline</Tag>}
        </div>
        {onRemove && <button className="ghost small" onClick={onRemove}>Remove</button>}
      </div>
      {v.rules.length === 0 && <span className="hint">{index === 0 ? "Usually left at the base world's rules." : "Add the rule changes that define this variant."}</span>}
      {v.rules.map(([k, val]: any, i: number) => {
        const p = params[k];
        return (
          <div className="variant-rule" key={i}>
            <select value={k} onChange={(e) => {
              const nk = e.target.value;
              setRule(i, nk, params[nk] ? params[nk].default : "");
            }}>
              <option value="">Choose a rule...</option>
              {schema.sections.map((s: any) => (
                <optgroup key={s.id} label={s.label}>
                  {s.params.map((pp: any) => (
                    <option key={pp.key} value={pp.key} disabled={used.has(pp.key) && pp.key !== k}>{pp.label}</option>
                  ))}
                </optgroup>
              ))}
            </select>
            {p && p.type === "bool" ? (
              <div className="toggle">
                <button className={cx(val === true && "on")} onClick={() => setRule(i, k, true)}>On</button>
                <button className={cx(val === false && "on")} onClick={() => setRule(i, k, false)}>Off</button>
              </div>
            ) : (
              <input type="number" value={val} min={p?.min} max={p?.max} step={p?.step || "any"} disabled={!p}
                onChange={(e) => setRule(i, k, e.target.value === "" ? "" : Number(e.target.value))} />
            )}
            <button className="ghost small" onClick={() => onChange({ ...v, rules: v.rules.filter((_: any, j: number) => j !== i) })}>
              <Icon name="close" size={13} />
            </button>
            {p && (
              <div className="range">
                {p.description} {p.type !== "bool" && <>Range {p.min}-{p.max}, default {String(p.default)}.</>}
                {p.type !== "bool" && typeof val === "number" && (val < p.min || val > p.max) && <span className="neg"> Out of range.</span>}
              </div>
            )}
          </div>
        );
      })}
      <div>
        <button className="small" onClick={() => onChange({ ...v, rules: [...v.rules, ["", ""]] })}>
          <Icon name="plus" size={12} /> Rule change
        </button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------------------------
// results

function ExperimentResult({ id }: { id: number }) {
  const { toast } = useStore();
  const { data, error, reload } = useApi<any>(`/api/experiments/${id}`, [id]);
  const schema = useRuleSchema();
  const groups = useApi<any>("/api/catalogs");
  const [showAll, setShowAll] = useState(false);
  const [seriesKey, setSeriesKey] = useState("mutual_friendships");

  const running = data?.status === "running";
  useEffect(() => {
    if (!running) return;
    const t = setInterval(reload, 1500);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running]);

  if (error) return <div className="stack"><BackLink /><ErrorBox error={error} /></div>;
  if (!data) return <Loading what="Loading experiment" />;
  const spec = data.spec;
  const res = data.result;
  const groupNames: Record<string, string> = {};
  for (const g of groups.data?.world?.groups || []) groupNames[g.id] = g.name;

  const rerun = async () => {
    try {
      const r = await api.post("/api/experiments", { ...spec, name: `${spec.name} (rerun)` });
      go(`experiments/${r.id}`);
    } catch (e: any) {
      toast(e.message, "bad");
    }
  };

  return (
    <div className="stack">
      <BackLink />
      <div className="page-h">
        <div>
          <h1>{data.name}</h1>
          <p>{spec.about || "Same starting world, different rules."}</p>
          <div className="row small muted" style={{ marginTop: 6 }}>
            <span>{baseLabel(res?.base_info || spec.base)}</span>·<span>{spec.days} days</span>·
            <span className="mono">seeds {spec.seeds.join(", ")}</span>
            {res?.elapsed !== undefined && <>·<span>finished in {fmtSecs(res.elapsed)}</span></>}
          </div>
        </div>
        <div className="row">
          <button onClick={rerun} title="Same spec, new experiment record. Same seeds give identical results.">Run again</button>
        </div>
      </div>

      {data.status === "running" && (
        <Panel title="Running">
          <Meter value={data.progress?.done || 0} max={Math.max(1, data.progress?.total || 1)} color="var(--accent-2)" />
          <p className="muted small">
            {data.progress ? `${data.progress.done} of ${data.progress.total} runs finished.` : "Starting..."} Each run simulates {spec.days} days on its own copy of the base world.
          </p>
        </Panel>
      )}
      {data.status === "failed" && <ErrorBox error={data.error || "The experiment failed."} />}

      {res && (
        <>
          <ModeBanner res={res} seeds={spec.seeds} />
          {res.notes?.length > 0 && (
            <Panel title="Read this before drawing conclusions">
              <ul className="notes">{res.notes.map((n: string, i: number) => <li key={i}>{n}</li>)}</ul>
            </Panel>
          )}

          <div className="grid g3">
            {res.variants.map((v: any, i: number) => (
              <div className="variant-card" key={v.name}>
                <div className="row between">
                  <b><span className="swatch" style={{ background: PALETTE[i % PALETTE.length] }} />{v.name}</b>
                  {i === 0 ? <Tag tone="accent">baseline</Tag> : <span className="hint">{v.seconds}s of compute</span>}
                </div>
                <RuleChips rules={v.rules} params={schema.params} />
                {i > 0 && res.divergence?.[v.name] && (
                  <div className="small muted">
                    Timelines split from the baseline:{" "}
                    {Object.entries(res.divergence[v.name]).map(([seed, day]: any) => (
                      <span key={seed} className="mono" style={{ marginRight: 10 }}>
                        seed {seed}: {day === null ? "never (identical)" : `day ${day} (within the first ${day - (res.base_info?.day || 0) + 1} day${day - (res.base_info?.day || 0) === 0 ? "" : "s"})`}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          {res.comparisons.map((c: any) => (
            <ComparisonTable key={c.variant} c={c} res={res} showAll={showAll} setShowAll={setShowAll} />
          ))}

          <Panel
            title="Over time"
            sub={res.mode === "repeated" ? "Average across seeds, sampled weekly." : "Sampled weekly."}
            actions={
              <select value={seriesKey} onChange={(e) => setSeriesKey(e.target.value)}>
                {SERIES_KEYS.filter((k) => res.series[res.baseline]?.[k]).map((k) => <option key={k} value={k}>{pretty(k)}</option>)}
              </select>
            }
          >
            <LineChart
              height={200}
              series={res.variants.map((v: any, i: number) => ({ name: v.name, color: PALETTE[i % PALETTE.length], values: res.series[v.name]?.[seriesKey] || [], dash: i === 0 }))}
              xLabels={(res.series[res.baseline]?.day || []).map((d: number) => `day ${d}`)}
            />
            <div className="hint">{res.metric_info?.[seriesKey]}</div>
          </Panel>

          <ActionsComparison res={res} />

          {res.mode === "deterministic" && res.characters && <CharacterDiffs res={res} groupNames={groupNames} />}
        </>
      )}
    </div>
  );
}

function BackLink() {
  return (
    <div>
      <a href="#/experiments" className="small muted">&larr; All experiments</a>
    </div>
  );
}

function ModeBanner({ res, seeds }: { res: any; seeds: number[] }) {
  if (res.mode === "deterministic") {
    return (
      <div className="mode-banner deterministic">
        <span className="badge">Deterministic</span>
        <div>
          <h3>A single paired timeline</h3>
          <p>
            One seed ({seeds[0]}). This shows exactly what changed in this one world - which lives, and when the timelines split. It is not
            evidence of an average effect: a different seed could go the other way. Re-run with several seeds to measure.
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="mode-banner repeated">
      <span className="badge">Repeated runs</span>
      <div>
        <h3>A measurement across {seeds.length} seeds</h3>
        <p>
          Each variant ran once per seed, paired with the baseline run on the same seed. Differences are averaged over seeds; intervals are 95%
          t-intervals on the per-seed paired differences. A highlighted row means its interval excludes zero - still provisional with few seeds.
        </p>
      </div>
    </div>
  );
}

function CiBar({ mean, ci, scale }: { mean: number; ci: number[] | null; scale: number }) {
  const s = Math.max(1e-9, scale);
  const pos = (v: number) => 50 + Math.max(-50, Math.min(50, (v / s) * 50));
  const color = mean > 0 ? "var(--good)" : mean < 0 ? "var(--bad)" : "var(--dim)";
  return (
    <div className="ci" title={ci ? `95% interval ${ci[0]} to ${ci[1]}` : `difference ${mean}`}>
      <div className="zero" />
      {ci && <div className="span" style={{ left: pos(ci[0]) + "%", width: Math.max(1, pos(ci[1]) - pos(ci[0])) + "%" }} />}
      <div className="pt" style={{ left: pos(mean) + "%", background: color }} />
    </div>
  );
}

function ComparisonTable({ c, res, showAll, setShowAll }: any) {
  const base = res.variants.find((v: any) => v.name === c.vs);
  const vv = res.variants.find((v: any) => v.name === c.variant);
  const repeated = res.mode === "repeated";
  const focus: string[] = (res.focus || []).filter((k: string) => c.metrics[k]);
  const rest = Object.keys(c.metrics).filter((k) => !focus.includes(k));
  const keys = showAll ? [...focus, ...rest] : focus.length ? focus : rest.slice(0, 8);
  const scaleOf = (k: string) => {
    const m = c.metrics[k];
    const vals = [Math.abs(m.mean), ...(m.ci95 ? m.ci95.map((x: number) => Math.abs(x)) : [])];
    return Math.max(...vals, 1e-9);
  };
  const clearCount = keys.filter((k) => c.metrics[k].interval_excludes_zero).length;
  return (
    <Panel
      title={`${c.variant} vs ${c.vs}`}
      sub={repeated ? `${clearCount} of ${keys.length} shown metrics have an interval that excludes zero.` : "Difference in this one paired timeline (variant minus baseline)."}
      actions={<button className="small" onClick={() => setShowAll(!showAll)}>{showAll ? "Focus metrics only" : `Show all ${Object.keys(c.metrics).length} metrics`}</button>}
    >
      <div style={{ overflowX: "auto" }}>
        <table className="cmp">
          <thead>
            <tr>
              <th>metric</th>
              <th className="num">{c.vs}</th>
              <th className="num">{c.variant}</th>
              <th className="num">difference</th>
              {repeated && <th>95% interval</th>}
              <th style={{ minWidth: 130 }}></th>
              {repeated && <th>direction</th>}
              {repeated && <th className="num">effect size</th>}
              {repeated && <th></th>}
            </tr>
          </thead>
          <tbody>
            {keys.map((k) => {
              const m = c.metrics[k];
              const b = base.metrics[k];
              const v = vv.metrics[k];
              return (
                <tr key={k} className={cx(focus.includes(k) && "focus", repeated && m.interval_excludes_zero && "clear")}>
                  <td><span className="metric-name" title={res.metric_info?.[k] || k}>{pretty(k)}</span></td>
                  <td className="num">{fmtNum(b.mean)}{repeated && <span className="dim"> ±{fmtNum(b.sd)}</span>}</td>
                  <td className="num">{fmtNum(v.mean)}{repeated && <span className="dim"> ±{fmtNum(v.sd)}</span>}</td>
                  <td className={cx("num", m.mean > 0 ? "pos" : m.mean < 0 ? "neg" : "")}><b>{m.mean === 0 ? "0" : signed(m.mean, Math.abs(m.mean) >= 100 ? 0 : 2)}</b></td>
                  {repeated && <td className="mono">{m.ci95 ? `[${fmtNum(m.ci95[0])}, ${fmtNum(m.ci95[1])}]` : "-"}</td>}
                  <td><CiBar mean={m.mean} ci={repeated ? m.ci95 : null} scale={scaleOf(k)} /></td>
                  {repeated && <td className="small muted">{m.direction}</td>}
                  {repeated && <td className="num">{m.effect_size === null || m.effect_size === undefined ? "-" : m.effect_size.toFixed(2)}</td>}
                  {repeated && (
                    <td>{m.interval_excludes_zero ? <span className="flag clear">clear</span> : <span className="flag unclear">unresolved</span>}</td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {repeated && <div className="hint" style={{ marginTop: 8 }}>"±" is the standard deviation across seeds. Effect size is the mean difference divided by the pooled standard deviation.</div>}
    </Panel>
  );
}

function ActionsComparison({ res }: { res: any }) {
  const names = res.variants.map((v: any) => v.name);
  const keys = useMemo(() => {
    const s = new Set<string>();
    for (const n of names) Object.keys(res.actions[n] || {}).slice(0, 14).forEach((k) => s.add(k));
    const base = res.actions[res.baseline] || {};
    return Array.from(s).sort((a, b) => (base[b] || 0) - (base[a] || 0));
  }, [res]);
  const max = Math.max(1, ...names.flatMap((n: string) => keys.map((k) => res.actions[n]?.[k] || 0)));
  return (
    <Panel title="What people actually did" sub={`Choices per run${res.mode === "repeated" ? " (averaged across seeds)" : ""}. Differences are vs ${res.baseline}.`}>
      <div style={{ overflowX: "auto" }}>
        <table className="cmp">
          <thead>
            <tr>
              <th>action</th>
              {names.map((n: string) => <th key={n}>{n}</th>)}
              {names.slice(1).map((n: string) => <th key={"d" + n} className="num">change ({n})</th>)}
            </tr>
          </thead>
          <tbody>
            {keys.map((k) => {
              const b = res.actions[res.baseline]?.[k] || 0;
              return (
                <tr key={k}>
                  <td>{pretty(k)}</td>
                  {names.map((n: string, i: number) => {
                    const v = res.actions[n]?.[k] || 0;
                    return (
                      <td key={n}>
                        <div className="vbar">
                          <div className="bar" style={{ width: Math.max(2, (v / max) * 140), background: PALETTE[i % PALETTE.length] }} />
                          <span className="n">{fmtNum(v, 1)}</span>
                        </div>
                      </td>
                    );
                  })}
                  {names.slice(1).map((n: string) => {
                    const d = (res.actions[n]?.[k] || 0) - b;
                    const pct = b > 0 ? (d / b) * 100 : null;
                    return (
                      <td key={"d" + n} className={cx("num", d > 0 ? "pos" : d < 0 ? "neg" : "")}>
                        {d === 0 ? "0" : signed(d, 1)}
                        {pct !== null && d !== 0 && <span className="dim"> ({signed(pct, 0)}%)</span>}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function CharacterDiffs({ res, groupNames }: { res: any; groupNames: Record<string, string> }) {
  const { chars } = useStore();
  const [onlyChanged, setOnlyChanged] = useState(true);
  const variants = res.variants.slice(1).map((v: any) => v.name);
  const nameOf: Record<string, string> = {};
  for (const c of res.characters) nameOf[c.id] = c.name;
  const P = ({ id }: { id: string | null }) => {
    if (!id) return <span className="dim">nobody</span>;
    if (chars[id]) return <Name id={id} />;
    return <span>{nameOf[id] || id}</span>;
  };
  const list = (ids: string[]) =>
    ids.length ? ids.map((x, i) => <React.Fragment key={x}>{i > 0 && ", "}<P id={x} /></React.Fragment>) : <span className="dim">-</span>;
  const rows = onlyChanged ? res.characters.filter((c: any) => c.change_score > 0) : res.characters;
  return (
    <Panel
      title="Whose lives changed"
      sub="Deterministic mode: the same people, the same seed, one rule different. Sorted by how much each person's outcome moved."
      actions={<button className="small" onClick={() => setOnlyChanged(!onlyChanged)}>{onlyChanged ? "Show everyone" : "Only people who changed"}</button>}
    >
      {!rows.length ? (
        <Empty>Nobody's outcome changed in this run.</Empty>
      ) : (
        <div style={{ overflowX: "auto" }} className="scroll">
          <table className="cmp">
            <thead>
              <tr>
                <th>person</th>
                {variants.length > 1 && <th>variant</th>}
                <th className="num">friends</th>
                <th className="num">popularity</th>
                <th className="num">mood</th>
                <th className="num">GPA</th>
                <th>groups</th>
                <th>partner</th>
                <th>friends gained</th>
                <th>friends lost</th>
                <th className="num">change</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c: any) =>
                variants.map((vn: string, vi: number) => {
                  const d = c.diff[vn];
                  if (!d) return null;
                  const sg = (x: number, digits = 1) => <span className={x > 0 ? "pos" : x < 0 ? "neg" : "dim"}>{x === 0 ? "0" : signed(x, digits)}</span>;
                  return (
                    <tr key={c.id + vn}>
                      <td>{vi === 0 && <><P id={c.id} /><div className="hint">baseline: {c.baseline.friends} friends, pop {c.baseline.popularity}</div></>}</td>
                      {variants.length > 1 && <td className="small">{vn}</td>}
                      <td className="num">{sg(d.friends, 0)}</td>
                      <td className="num">{sg(d.popularity)}</td>
                      <td className="num">{sg(d.mood)}</td>
                      <td className="num">{sg(d.gpa, 2)}</td>
                      <td className="small">
                        {d.memberships_gained.map((g: string) => <Tag key={"+" + g} tone="good">+ {groupNames[g] || g}</Tag>)}
                        {d.memberships_lost.map((g: string) => <Tag key={"-" + g} tone="bad">- {groupNames[g] || g}</Tag>)}
                        {!d.memberships_gained.length && !d.memberships_lost.length && <span className="dim">-</span>}
                      </td>
                      <td className="small">{d.partner ? <><P id={d.partner[0]} /> &rarr; <P id={d.partner[1]} /></> : <span className="dim">same</span>}</td>
                      <td className="small">{list(d.friends_gained)}</td>
                      <td className="small">{list(d.friends_lost)}</td>
                      <td className="num">{vi === 0 ? c.change_score : ""}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}
      <div className="row" style={{ marginTop: 10 }}>
        <Stat label="people whose outcome moved" value={res.characters.filter((c: any) => c.change_score > 0).length} />
        <Stat label="of" value={res.characters.length} sub="students and alumni" />
      </div>
    </Panel>
  );
}
