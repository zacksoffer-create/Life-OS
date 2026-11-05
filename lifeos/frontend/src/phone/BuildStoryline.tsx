// Write more, the way that holds up: (1) ChatGPT plans an outline (one line per scene) and the app turns it into the
// storyline; (2) ChatGPT writes the scenes a few at a time, each batch dropped into its place. The game owns the order,
// the timing and the branches, and anything fixable in what ChatGPT wrote is fixed (with a note), never refused.
import React, { useEffect, useRef, useState } from "react";
import { BatchPrompt, Checkup, OutlineCheck, OutlineEntry, SkippedScene, WritingRow, phoneApi } from "./api";
import { copyText } from "./DialogueCard";
import { PIcon } from "./icons";
import { cx, errText, Sheet } from "./kit";
import { usePhone } from "./PhoneContext";
import { pickFile } from "./StoryFiles";

const SIZES: [string, string, string][] = [["few", "A few", "6 to 8 scenes"], ["bunch", "A bunch", "12 to 18"], ["lot", "A lot", "30 to 45"]];
const IDEAS_NEW = ["My sister and her friends at the house", "A season with my brother on the same team", "Scenes in biology class all year",
  "Holidays with my family, every year", "My best friend and me getting into trouble"];
const IDEAS_EXP = ["Holidays with them", "Their friends coming around", "A season of their sport", "Summers", "A fight, a secret, making up"];

export type BuildStart = { expand?: string; expandName?: string; pack?: string } | null;

async function share(text: string, title: string) {
  try {
    await (navigator as any).share({ title, text });
  } catch { /* cancelled */ }
}

function Notes({ notes }: { notes: string[] }) {
  if (!notes.length) return null;
  return (
    <div className="bs-notes">
      <b>Fixed for you ({notes.length})</b>
      {notes.slice(0, 12).map((n, i) => <div key={i}>{n}</div>)}
      {notes.length > 12 && <div>…and {notes.length - 12} more</div>}
    </div>
  );
}

type LeftOutInfo = { scenes: SkippedScene[]; gaps?: SkippedScene[]; fix: string; errors?: string[] };

/** Scenes that didn't go in (they stay as they were) and scenes that went in with pieces missing, each with exactly what's
 * wrong, and a message for ChatGPT that asks for just those, whole. */
function LeftOut({ x }: { x: LeftOutInfo }) {
  const { toast } = usePhone();
  const gaps = x.gaps || [];
  const one = (sc: SkippedScene) => (
    <div key={sc.n} className="bs-left-sc">
      <span>Scene {sc.n}{sc.title ? ` (${sc.title})` : ""}</span>
      {sc.problems.slice(0, 6).map((p, i) => <small key={i}>{p}</small>)}
    </div>
  );
  return (
    <div className={cx("bs-left", !x.scenes.length && !x.errors?.length && "soft")}>
      {(x.scenes.length > 0 || !gaps.length) && <b>{x.scenes.length ? `Didn't go in (${x.scenes.length})` : "Couldn't add those"}</b>}
      {x.scenes.map(one)}
      {!x.scenes.length && !gaps.length && (x.errors || []).slice(0, 6).map((p, i) => <small key={i}>{p}</small>)}
      {x.scenes.length > 0 && <p className="ph-dim small">These stay as they were (an earlier version, or not written yet). The next prompt asks for them again.</p>}
      {gaps.length > 0 && <b className="bs-gap-h">Went in, but missing pieces ({gaps.length})</b>}
      {gaps.map(one)}
      {x.fix && (
        <button className="ph-btn soft block" onClick={async () => {
          const ok = await copyText(x.fix);
          toast(ok ? "Copied. Paste it to ChatGPT and paste its answer back here: the scenes it sends replace these." : "Couldn't copy.", ok ? "good" : "bad");
        }}>Copy a fix-it message for ChatGPT</button>
      )}
    </div>
  );
}

const COUNT_KEY = "lifeos.batchCount";
function savedCount(): number {
  try {
    const n = Number(localStorage.getItem(COUNT_KEY));
    return [1, 3, 6].includes(n) ? n : 3;
  } catch {
    return 3;
  }
}

function rowNote(r: WritingRow): { text: string; warn: boolean } {
  if (r.needs_fixing) return { text: `${r.written}/${r.total} · ${r.needs_fixing} to fix`, warn: true };
  if (r.written >= r.total) return { text: r.stuck ? `done · ${r.stuck} can't come` : "all written", warn: !!r.stuck };
  return { text: `${r.written}/${r.total} written`, warn: false };
}

/** The storylines you're writing, side by side: tap one to switch to it (no closing, no digging). */
function Switcher({ rows, pack, onPick }: { rows: WritingRow[]; pack: string | null; onPick: (p: string) => void }) {
  if (rows.length < (pack ? 2 : 1)) return null;
  return (
    <div className="bs-switch">
      {rows.map((r) => {
        const n = rowNote(r);
        return (
          <button key={r.pack} type="button" className={cx(r.pack === pack && "on")} onClick={() => r.pack !== pack && onPick(r.pack)}>
            <b>{r.name}</b>
            <small className={cx(n.warn && "warn")}>{n.text}</small>
          </button>
        );
      })}
    </div>
  );
}

function OutlineList({ entries, now }: { entries: OutlineEntry[]; now?: number[] }) {
  return (
    <ol className="bs-outline">
      {entries.map((e) => (
        <li key={e.n} className={cx(e.written && "done", now?.includes(e.n) && "now")}>
          <span className="bs-n">{e.written ? "✓" : e.n}</span>
          <span className="bs-t"><b>{e.title}</b>{e.when && <i>{e.when}</i>}{e.summary && <small>{e.summary}</small>}
            {e.if && <em>{e.if}</em>}</span>
        </li>
      ))}
    </ol>
  );
}

export default function BuildStoryline({ start, onClose, onChanged, onRead }: {
  start: BuildStart; onClose: () => void; onChanged: () => void; onRead: (pack: string) => void;
}) {
  const { toast } = usePhone();
  const [pack, setPack] = useState<string | null>(null);
  const [ask, setAsk] = useState("");
  const [size, setSize] = useState("bunch");
  const [paste, setPaste] = useState("");
  const [check, setCheck] = useState<OutlineCheck | null>(null);
  const [batch, setBatch] = useState<BatchPrompt | null>(null);
  const [entries, setEntries] = useState<OutlineEntry[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [count, setCountRaw] = useState(savedCount);
  const [leftOut, setLeftOut] = useState<LeftOutInfo | null>(null);
  const [rows, setRows] = useState<WritingRow[]>([]);
  const [ck, setCk] = useState<Checkup | null>(null);
  const top = useRef<HTMLDivElement>(null);
  const setCount = (n: number) => {
    setCountRaw(n);
    try {
      localStorage.setItem(COUNT_KEY, String(n));
    } catch { /* private mode */ }
  };
  const loadRows = async () => {
    try {
      setRows((await phoneApi.writing()).storylines);
    } catch { /* no story yet */ }
  };
  const loadCheck = async (pid: string) => {
    try {
      setCk(await phoneApi.checkup(pid));
    } catch {
      setCk(null);
    }
  };
  const toTop = () => {
    const el = top.current?.closest(".ph-sheet-b") as HTMLElement | null;
    if (el) el.scrollTo({ top: 0, behavior: "smooth" });
  };
  // switch to another storyline right here: its next prompt, its progress, its checkup
  const open = (pid: string | null) => {
    setPack(pid);
    setPaste("");
    setCheck(null);
    setBatch(null);
    setNotes([]);
    setEntries([]);
    setLeftOut(null);
    setCk(null);
    if (pid) {
      loadBatch(pid, count);
      loadCheck(pid);
    }
    toTop();
  };
  useEffect(() => {
    if (!start) return;
    setAsk("");
    open(start.pack || null);
    loadRows();
  }, [start]); // eslint-disable-line react-hooks/exhaustive-deps
  const run = async (k: string, fn: () => Promise<void>) => {
    setBusy(k);
    try {
      await fn();
    } catch (e: any) {
      toast(e?.errors?.[0] || errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  async function loadBatch(pid: string, n: number) {
    const b = await phoneApi.batchPrompt(pid, n);
    setBatch(b);
  }
  const fromFile = async () => {
    const f = await pickFile(".txt,.story,.md,text/plain");
    if (f) setPaste(await f.text());
  };

  // step 1: the outline
  const copyOutline = () => run("copy", async () => {
    const r = await phoneApi.outlinePrompt(ask, size, start?.expand);
    const ok = await copyText(r.prompt);
    toast(ok ? "Copied. Paste it into ChatGPT, then paste its outline below." : "Couldn't copy. Try Share.", ok ? "good" : "bad");
  });
  const shareOutline = () => run("share", async () => share((await phoneApi.outlinePrompt(ask, size, start?.expand)).prompt, "LIFE OS: plan a storyline"));
  const checkOutline = () => run("check", async () => setCheck(await phoneApi.outline(paste, false, start?.expand)));
  const create = () => run("create", async () => {
    const r = await phoneApi.outline(paste, true, start?.expand);
    setPack(r.pack!);
    setPaste("");
    setCheck(null);
    setNotes(r.notes);
    onChanged();
    await loadBatch(r.pack!, count);
    loadRows();
    toTop();
    toast(`${r.title}: ${r.outline.length} scenes planned. Now the scenes, a few at a time.`, "good");
  });

  // step 2: scenes, a batch at a time
  const copyBatch = () => run("copy", async () => {
    if (!batch?.prompt) return;
    const ok = await copyText(batch.prompt);
    toast(ok ? `Copied: ${batch.first === batch.last ? `scene ${batch.first}` : `scenes ${batch.first} to ${batch.last}`}. Paste ChatGPT's answer below.` : "Couldn't copy. Try Share.", ok ? "good" : "bad");
  });
  const addBatch = async () => {
    if (!pack) return;
    setBusy("add");
    try {
      const r = await phoneApi.addScenes(pack, paste);
      setNotes(r.notes);
      setEntries(r.outline);
      setLeftOut(r.skipped?.length || r.gaps?.length ? { scenes: r.skipped || [], gaps: r.gaps || [], fix: r.fix_prompt } : null);
      setPaste("");
      onChanged();
      await loadBatch(pack, count);
      loadRows();
      loadCheck(pack);
      if (!r.skipped?.length && !r.gaps?.length) toTop();  // all good: straight back up to the next prompt
      const n = r.skipped?.length || 0;
      const g = r.gaps?.length || 0;
      if (r.got.length) {
        toast(`Added scene${r.got.length === 1 ? "" : "s"} ${r.got.join(", ")}. ${r.written} of ${r.total} written.`
          + (n ? ` ${n} didn't go in: see below.` : g ? ` ${g} ${g === 1 ? "is" : "are"} missing pieces: see below.` : ""), n || g ? undefined : "good");
      } else {
        toast(n ? "None of those went in: see below for what to fix." : "Added.", n ? "bad" : "good");
      }
    } catch (e: any) {
      const d = e?.data;
      if (d?.skipped?.length || d?.fix_prompt) setLeftOut({ scenes: d.skipped || [], fix: d.fix_prompt || "", errors: e.errors });
      else if (e?.errors?.length) setLeftOut({ scenes: [], fix: "", errors: e.errors });
      toast(e?.errors?.[0] || errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };

  // the next storyline that still has scenes to write (or fix), after this one
  const nextRow = (() => {
    const todo = rows.filter((r) => r.written < r.total || r.needs_fixing);
    if (!todo.length) return null;
    const i = rows.findIndex((r) => r.pack === pack);
    const after = [...rows.slice(i + 1), ...rows.slice(0, Math.max(0, i))].filter((r) => todo.includes(r));
    return after[0] || null;
  })();
  const nextBtn = nextRow && nextRow.pack !== pack && (
    <button type="button" className="bs-next" onClick={() => open(nextRow.pack)}>
      <span><b>Next storyline: {nextRow.name}</b><small>{rowNote(nextRow).text}</small></span>
      <PIcon name="chevron" size={16} />
    </button>
  );
  // earlier scenes of this storyline that need fixing (the ones just added show in their own list above)
  const shown = new Set((leftOut?.gaps || []).map((g) => g.n));
  const older = (ck?.gaps || []).filter((g) => !shown.has(g.n));
  const fixCard = older.length > 0 && (
    <div className="bs-fixcard">
      <LeftOut x={{ scenes: [], gaps: older, fix: ck?.fix_prompt || "" }} />
    </div>
  );

  const title = pack ? (rows.find((r) => r.pack === pack)?.name || "Write the scenes") : start?.expand ? `More of ${start.expandName || "it"}` : "Write more";
  return (
    <Sheet open={!!start} onClose={onClose} full title={title}>
      <div ref={top} />
      {!pack ? (
        <div className="bs">
          <div className="bs-steps"><span className="on">1 Plan it</span><span>2 Write the scenes</span></div>
          <div className="sch-step"><i>1</i><b>{start?.expand ? "What should this part be?" : "What's it about?"}</b></div>
          <textarea className="ph-input" rows={3} value={ask} onChange={(e) => setAsk(e.target.value)}
            placeholder={start?.expand ? "Like: holidays with them. Their friends coming around." : "Like: my sister's friends hanging out at the house. A bunch of scenes in biology class."} />
          <div className="sch-sugg">{(start?.expand ? IDEAS_EXP : IDEAS_NEW).map((s) => <button key={s} onClick={() => setAsk(s)}>{s}</button>)}</div>
          <div className="sch-size"><span>How many scenes</span>
            {SIZES.map(([k, l, d]) => <button key={k} className={cx(size === k && "on")} onClick={() => setSize(k)} title={d}>{l}</button>)}
          </div>
          <div className="sch-row2">
            <button className="ph-btn primary block" disabled={!!busy} onClick={copyOutline}>{busy === "copy" ? <span className="ph-spinner small light" /> : "Copy the outline prompt"}</button>
            {"share" in navigator && <button className="ph-btn block" disabled={!!busy} onClick={shareOutline}>Share</button>}
          </div>
          <p className="ph-dim small">ChatGPT plans it as one line per scene (short, so nothing gets cut off). You'll see it before anything is made.</p>
          <div className="sch-step"><i>2</i><b>Paste ChatGPT's outline</b></div>
          <textarea className="ph-input mono" rows={5} value={paste} placeholder={"=== Title\ncast: mike = Mike Soffer\nyears: freshman\n\noutline:\n1. ... | September | ..."}
            onChange={(e) => { setPaste(e.target.value); setCheck(null); }} />
          <div className="sch-row2">
            <button className="ph-btn block" disabled={!!busy || !paste.trim()} onClick={checkOutline}>{busy === "check" ? <span className="ph-spinner small" /> : "Check it"}</button>
            <button className="ph-btn soft block" disabled={!!busy} onClick={fromFile}><PIcon name="upload" size={15} /> Or a file</button>
          </div>
          {check && (
            <div className="bs-check">
              <b className="bs-title">{check.title}</b>
              {check.expands && <small className="ph-dim">More of {check.expands}</small>}
              {check.about && <p className="ph-dim small">{check.about}</p>}
              {check.cast.length > 0 && <p className="ph-dim small">People: {check.cast.map((c) => `${c.name} (${c.label})`).join(", ")}</p>}
              <OutlineList entries={check.outline} />
              <Notes notes={[...check.notes, ...check.warnings]} />
              <button className="ph-btn primary block" disabled={!!busy} onClick={create}>
                {busy === "create" ? <span className="ph-spinner small light" /> : `Make it: ${check.outline.length} scenes`}
              </button>
              <p className="ph-dim small">The game puts them in order and spaces them through the year (holidays and school days on their day). Nothing plays until its scene is written.</p>
            </div>
          )}
          {!start?.expand && rows.some((r) => r.written < r.total || r.needs_fixing) && (
            <div className="bs-keep">
              <div className="sch-step"><i>↺</i><b>Or keep writing one of yours</b></div>
              <Switcher rows={rows.filter((r) => r.written < r.total || r.needs_fixing)} pack={null} onPick={open} />
            </div>
          )}
        </div>
      ) : (
        <div className="bs">
          <Switcher rows={rows} pack={pack} onPick={open} />
          {batch && (
            <div className="bs-progress">
              <div className="bs-bar"><i style={{ width: `${(100 * batch.written) / Math.max(1, batch.total)}%` }} /></div>
              <b>{batch.written} of {batch.total} scenes written</b>
            </div>
          )}
          {batch && !batch.done ? (
            <>
              <div className="sch-step"><i>1</i><b>Copy the prompt for {batch.first === batch.last ? `scene ${batch.first}` : `scenes ${batch.first} to ${batch.last}`}</b></div>
              <p className="ph-dim small">{(batch.titles || []).join(" · ")}</p>
              <div className="sch-size"><span>Scenes per prompt</span>
                {[1, 3, 6].map((n) => <button key={n} className={cx(count === n && "on")} onClick={() => { setCount(n); if (pack) run("load", () => loadBatch(pack, n)); }}>{n}</button>)}
              </div>
              <div className="sch-row2">
                <button className="ph-btn primary block" disabled={!!busy} onClick={copyBatch}>{busy === "copy" ? <span className="ph-spinner small light" /> : "Copy the prompt"}</button>
                {"share" in navigator && <button className="ph-btn block" disabled={!!busy} onClick={() => batch.prompt && share(batch.prompt, "LIFE OS: write scenes")}>Share</button>}
              </div>
              <div className="sch-step"><i>2</i><b>Paste the scenes ChatGPT wrote</b></div>
              <textarea className="ph-input mono" rows={6} value={paste} placeholder={`--- ${batch.first}. ${(batch.titles || [""])[0]}\n...`} onChange={(e) => setPaste(e.target.value)} />
              <div className="sch-row2">
                <button className="ph-btn primary block" disabled={!!busy || !paste.trim()} onClick={addBatch}>{busy === "add" ? <span className="ph-spinner small light" /> : "Add these scenes"}</button>
                <button className="ph-btn soft block" disabled={!!busy} onClick={fromFile}><PIcon name="upload" size={15} /> Or a file</button>
              </div>
              {leftOut && <LeftOut x={leftOut} />}
              {fixCard}
              {nextBtn}
            </>
          ) : batch?.done ? (
            <div className="bs-done">
              <b>All {batch.total} scenes are written{older.length ? `, ${older.length} to fix` : ""}.</b>
              {fixCard}
              {!older.length && <button className="ph-btn primary block" onClick={() => pack && onRead(pack)}>Read it</button>}
              {nextBtn}
            </div>
          ) : <div className="pm-empty"><span className="ph-spinner" /></div>}
          <Notes notes={notes} />
          {entries.length > 0 && <OutlineList entries={entries} now={batch && !batch.done ? Array.from({ length: (batch.last || 0) - (batch.first || 0) + 1 }, (_, i) => (batch.first || 0) + i) : []} />}
          {pack && <button className="ph-link center" onClick={() => onRead(pack)}>Read it so far</button>}
        </div>
      )}
    </Sheet>
  );
}
