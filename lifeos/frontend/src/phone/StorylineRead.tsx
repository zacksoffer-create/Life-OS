// Read a storyline and all its expansions the way they'd play: your seven years forward on a copy, every scene in order
// with its date (or why it won't come), how healthy it is, and the script of each scene laid out to read.
import React, { useEffect, useState } from "react";
import { phoneApi, ReadScene, StorylineRead as SR, Timing } from "./api";
import { cx, errText, Sheet } from "./kit";
import { PIcon } from "./icons";
import { usePhone } from "./PhoneContext";
import { CoverageGrid } from "./Schedule";

const OUT = /^(great|good|miss|yes|no|meh|bad)\s*:\s*(.*)$/i;
const SPEAK = /^([A-Za-z{][\w{}.' -]{0,30}?):\s+(.+)$/;
const CMD = /^(remember|forget)\s+(\S+)$/;

/** {a|b} versions as "a / b", {sis} names as the name. */
function fmt(t: string): React.ReactNode {
  return t.split(/(\{[^{}]*\})/).map((part, i) => {
    const m = /^\{([^{}]*)\}$/.exec(part);
    if (!m) return part;
    return m[1].includes("|") ? <span key={i} className="rd-var">{m[1].split("|").join(" / ")}</span> : <span key={i} className="rd-name">{m[1]}</span>;
  });
}

/** One scene's script, laid out to read: narration, who says what, the choices and what each one does. */
export function ScriptView({ src }: { src: string }) {
  const lines = src.split("\n");
  const body = lines.slice(1).filter((l) => l.trim() && !l.trim().startsWith("//"));
  return (
    <div className="rd-script">
      {body.map((raw, i) => {
        const depth = Math.floor((raw.length - raw.trimStart().length) / 4);
        let t = raw.trim();
        let fx = "";
        const bar = t.indexOf(" | ");
        if (bar > 0 && !/^\{[^}]*\|/.test(t.slice(Math.max(0, bar - 20), bar + 3))) {
          fx = t.slice(bar + 3);
          t = t.slice(0, bar).trim();
        } else if (t.startsWith("|")) {
          fx = t.slice(1).trim();
          t = "";
        }
        const pad = { paddingLeft: depth * 14 };
        const eff = fx ? <em className="rd-fx">{fx}</em> : null;
        if (t.startsWith("*")) {
          return <div key={i} className="rd-choice" style={pad}><span>▸</span><b>{fmt(t.replace(/^\*\s*/, ""))}</b>{eff}</div>;
        }
        const o = OUT.exec(t);
        if (o) return <div key={i} className="rd-out" style={pad}><i>{o[1]}</i>{fmt(o[2])}{eff}</div>;
        const c = CMD.exec(t);
        if (c) return <div key={i} className="rd-cmd" style={pad}>{c[1] === "remember" ? "remembers" : "forgets"} {c[2]}</div>;
        const m = SPEAK.exec(t);
        if (m) return <div key={i} className="rd-say" style={pad}><b>{fmt(m[1])}</b> {fmt(m[2])}{eff}</div>;
        return <div key={i} className="rd-narr" style={pad}>{fmt(t)}{eff}</div>;
      })}
    </div>
  );
}

function tagsOf(src: string): string {
  const m = /\[([^\]]*)\]/.exec(src.split("\n")[0] || "");
  return m ? m[1] : "";
}

const YEARS: [string, string][] = [["freshman", "Freshman"], ["sophomore", "Sophomore"], ["junior", "Junior"], ["senior", "Senior"],
  ["college_freshman", "College freshman"], ["college_sophomore", "College sophomore"], ["college_junior", "College junior"]];
const SEASONS: [string, string, number[]][] = [["fall", "Fall", [9, 10, 11]], ["winter", "Winter", [12, 1, 2]], ["spring", "Spring", [3, 4, 5]],
  ["summer", "Summer", [6, 7, 8]]];
const MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const MONTH_ORDER = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8];

function timingText(t: Timing | null): string {
  if (!t || (!t.years.length && !t.months.length)) return "whenever its scenes say";
  const ys = t.years.map((y) => YEARS.find((x) => x[0] === y)?.[1] || y).join(", ");
  const ss = SEASONS.filter((x) => x[2].every((m) => t.months.includes(m))).map((x) => x[1].toLowerCase()).join(", ");
  return [ys, ss].filter(Boolean).join(" · ") + (t.spread ? ", spread out" : "");
}

/** A storyline's timing by hand: its school years, seasons, and whether its scenes spread out across them. */
function TimingSheet({ part, onClose, onSaved }: { part: { pack: string; name: string; timing: Timing | null } | null; onClose: () => void; onSaved: () => void }) {
  const { toast } = usePhone();
  const [years, setYears] = useState<string[]>([]);
  const [seasons, setSeasons] = useState<string[]>([]);
  const [spread, setSpread] = useState(false);
  const [keepMonths, setKeepMonths] = useState(true);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const t = part?.timing;
    setKeepMonths(true);
    setYears(t?.years || []);
    setSeasons(SEASONS.filter((x) => t && x[2].every((m) => t.months.includes(m))).map((x) => x[0]));
    setSpread(!!t?.spread);
  }, [part?.pack]); // eslint-disable-line react-hooks/exhaustive-deps
  const flip = (a: string[], k: string) => (a.includes(k) ? a.filter((x) => x !== k) : [...a, k]);
  const save = async () => {
    if (!part) return;
    setBusy(true);
    try {
      await phoneApi.setTiming(part.pack, YEARS.map((y) => y[0]).filter((y) => years.includes(y)), seasons, spread, keepMonths);
      toast("Saved. Playing your seven years again…", "good");
      onSaved();
    } catch (e: any) {
      toast(e?.errors?.[0] || errText(e), "bad");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Sheet open={!!part} onClose={onClose} title={`When ${part?.name || "it"} happens`}>
      <div className="rd-tsheet">
        <div className="dl-sub">School years</div>
        <div className="rd-chips">{YEARS.map(([k, l]) => <button key={k} className={cx(years.includes(k) && "on")} onClick={() => setYears(flip(years, k))}>{l}</button>)}</div>
        <div className="dl-sub">Seasons <small>(none picked: the whole school year)</small></div>
        <div className="rd-chips">{SEASONS.map(([k, l]) => <button key={k} className={cx(seasons.includes(k) && "on")} onClick={() => setSeasons(flip(seasons, k))}>{l}</button>)}</div>
        <label className="dl-check"><input type="checkbox" checked={spread} disabled={!years.length} onChange={(e) => setSpread(e.target.checked)} />
          <span><b>Spread them out</b><small>Its scenes, in order, about evenly across {years.length ? "those years" : "the years you pick"}{seasons.length ? " and seasons" : ""}.</small></span></label>
        <label className="dl-check"><input type="checkbox" checked={keepMonths} disabled={!years.length} onChange={(e) => setKeepMonths(e.target.checked)} />
          <span><b>Keep each scene's own month</b><small>{keepMonths ? "Like Tryouts in November: it stays in November, and the rest spread around it." : "The spread decides every month (each scene's own month comes off its script)."}</small></span></label>
        <p className="ph-dim small">Every scene moves into the years you pick. Holidays and school days (Thanksgiving, prom...) keep their day. Tap a scene's date to move just that one.</p>
        <button className="ph-btn primary block" disabled={busy} onClick={save}>{busy ? <span className="ph-spinner small light" /> : "Save"}</button>
      </div>
    </Sheet>
  );
}

/** Move one scene to a school year and month (or back to whatever its storyline says). */
function MoveSheet({ scene, onClose, onSaved }: { scene: ReadScene | null; onClose: () => void; onSaved: () => void }) {
  const { toast } = usePhone();
  const [year, setYear] = useState("");
  const [month, setMonth] = useState(0);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const t = scene ? /\[([^\]]*)\]/.exec(scene.src.split("\n")[0] || "")?.[1] || "" : "";
    const toks = t.toLowerCase().split(/\s*[·,;]\s*/);
    setYear(YEARS.find(([k]) => toks.includes(k.replace("_", " ")))?.[0] || "");
    setMonth(MONTHS.findIndex((m, i) => i > 0 && toks.includes(m.toLowerCase())) || 0);
  }, [scene?.sid]); // eslint-disable-line react-hooks/exhaustive-deps
  const save = async () => {
    if (!scene) return;
    setBusy(true);
    try {
      await phoneApi.moveScene(scene.pack, scene.sid, year, month);
      toast("Moved. Playing your seven years again…", "good");
      onSaved();
    } catch (e: any) {
      toast(e?.errors?.[0] || errText(e), "bad");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Sheet open={!!scene} onClose={onClose} title={`Move “${scene?.title || ""}”`}>
      <div className="rd-tsheet">
        <label className="dl-cast-row"><span>School year</span>
          <select className="ph-input" value={year} onChange={(e) => setYear(e.target.value)}>
            <option value="">Whatever the storyline says</option>
            {YEARS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </label>
        <label className="dl-cast-row"><span>Month</span>
          <select className="ph-input" value={month} disabled={scene?.dated} onChange={(e) => setMonth(Number(e.target.value))}>
            <option value={0}>Whatever the storyline says</option>
            {MONTH_ORDER.map((m) => <option key={m} value={m}>{MONTHS[m]}</option>)}
          </select>
        </label>
        {scene?.dated && <p className="ph-dim small">It's on a holiday or school day, so it keeps that day: pick the year it happens in.</p>}
        <button className="ph-btn primary block" disabled={busy} onClick={save}>{busy ? <span className="ph-spinner small light" /> : "Move it"}</button>
      </div>
    </Sheet>
  );
}

export default function StorylineRead({ pack, onClose, onExpand }: { pack: string | null; onClose: () => void; onExpand?: (pack: string) => void }) {
  const { toast } = usePhone();
  const [v, setV] = useState<SR | null>(null);
  const [only, setOnly] = useState<string | null>(null);
  const [timing, setTiming] = useState<SR["parts"][number] | null>(null);
  const [move, setMove] = useState<ReadScene | null>(null);
  const load = () => {
    if (pack) phoneApi.readStoryline(pack).then(setV).catch((e) => { toast(errText(e), "bad"); onClose(); });
  };
  useEffect(() => {
    setV(null);
    setOnly(null);
    load();
  }, [pack]); // eslint-disable-line react-hooks/exhaustive-deps
  const reload = () => {
    setTiming(null);
    setMove(null);
    setV(null);
    load();
  };
  const shown = (v?.scenes || []).filter((x) => !only || x.pack === only);
  let lastYear: string | null = "";
  return (
    <Sheet open={!!pack} onClose={onClose} full title={v?.title || "Storyline"}>
      {!v ? (
        <div className="rd-wait"><span className="ph-spinner" /><p className="ph-dim small">Playing your seven years forward on a copy…</p></div>
      ) : (
        <>
          <div className={cx("rd-health", v.plays === v.total ? "ok" : v.plays === 0 ? "bad" : "mid")}>
            <b>{v.plays} of {v.total}</b> scenes play in your seven years{v.unwritten ? ` · ${v.unwritten} more planned, not written yet` : ""}
            {v.wont.length > 0 && (
              <div className="rd-wont">
                {v.wont.map((w) => <div key={w.why}><b>{w.count} won't:</b> {w.why} <small>({w.titles.join(", ")}{w.count > w.titles.length ? "…" : ""})</small></div>)}
              </div>
            )}
          </div>
          {v.parts.length > 1 && (
            <div className="rd-parts">
              <button className={cx(!only && "on")} onClick={() => setOnly(null)}>All</button>
              {v.parts.map((p) => (
                <button key={p.pack} className={cx(only === p.pack && "on")} onClick={() => setOnly(p.pack)}>
                  {p.expands ? p.name.replace(`${p.expands}: `, "+ ") : p.name} <small>{p.plays}/{p.scenes}</small>
                </button>
              ))}
            </div>
          )}
          <div className="rd-timing">
            <div className="dl-sub">When it happens</div>
            {v.parts.filter((p) => p.timing && (!only || only === p.pack)).map((p) => (
              <button key={p.pack} className="rd-trow" onClick={() => setTiming(p)}>
                <span><b>{p.expands ? p.name.replace(`${p.expands}: `, "+ ") : p.name}</b><small>{timingText(p.timing)}</small></span>
                <em><PIcon name="chevron" size={14} /> Change</em>
              </button>
            ))}
            <p className="ph-dim small">Tap a scene's date to move just that scene.</p>
          </div>
          {onExpand && <button className="ph-btn soft block" onClick={() => onExpand(v.pack)}>Add an expansion</button>}
          <CoverageGrid c={v.coverage} />
          {shown.map((x) => {
            if (x.unwritten) {
              const showU = lastYear !== "Not written yet";
              lastYear = "Not written yet";
              return (
                <React.Fragment key={x.sid}>
                  {showU && <div className="rd-year">Not written yet</div>}
                  <div className="rd-scene unwritten">
                    <div className="rd-head"><b>{x.outline_n}. {x.title}</b><span className="rd-when">{x.when || "spaced out"}</span></div>
                    {x.summary && <p className="ph-dim small">{x.summary}</p>}
                    {x.if && <p className="ph-dim small">{x.if}</p>}
                  </div>
                </React.Fragment>
              );
            }
            const head = x.plays ? x.year : "Won't play";
            const show = head !== lastYear;
            lastYear = head;
            return (
              <React.Fragment key={x.sid}>
                {show && <div className={cx("rd-year", !x.plays && "bad")}>{head}</div>}
                <div className={cx("rd-scene", !x.plays && "off")}>
                  <div className="rd-head">
                    <b>{x.title}</b>
                    <button className={cx("rd-when", !x.plays && "bad")} onClick={() => setMove(x)}>{x.plays ? (x.date || "").replace(/, \d{4}$/, "") : "won't play"} ✎</button>
                  </div>
                  <div className="rd-tags">{x.storyline !== v.title && <i>{x.storyline.replace(`${v.title}: `, "+ ")}</i>}{tagsOf(x.src)}</div>
                  {!x.plays && x.why && <div className="rd-why">{x.why}{x.detail && typeof x.detail === "string" ? ` (${x.detail.replace(/_/g, " ")})` : ""}</div>}
                  <ScriptView src={x.src} />
                </div>
              </React.Fragment>
            );
          })}
        </>
      )}
      <TimingSheet part={timing} onClose={() => setTiming(null)} onSaved={reload} />
      <MoveSheet scene={move} onClose={() => setMove(null)} onSaved={reload} />
    </Sheet>
  );
}
