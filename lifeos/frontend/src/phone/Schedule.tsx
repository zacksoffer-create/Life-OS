// Story schedule (Me → How much story a day → Story schedule): every storyline, what's played, what's ready, what's
// waiting and exactly why, and a dry run of the next seven years you can save as a report.
import React, { useEffect, useState } from "react";
import { AddPreview, Coverage, pgo, phoneApi, ScheduleReport, ScheduleRow, ScheduleView } from "./api";
import { copyText } from "./DialogueCard";
import { PIcon } from "./icons";
import { cx, errText, Sheet } from "./kit";
import { usePhone } from "./PhoneContext";
import { pickFile } from "./StoryFiles";

const STATE_LABEL: Record<string, string> = {
  played: "Played", presented: "On now", queued: "Today", eligible: "Ready", waiting: "Not yet", unreachable: "Won't happen", expired: "Missed",
};
const MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function why(r: ScheduleRow): string {
  const d = r.detail;
  const extra = d === null || d === undefined ? "" : Array.isArray(d) ? ` (${d.map((m: number) => MONTHS[m] || m).join(", ")})` : ` (${String(d).replace(/_/g, " ")})`;
  return r.why ? r.why + extra : "";
}

export function ScheduleScreen() {
  const { toast } = usePhone();
  const [v, setV] = useState<ScheduleView | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [rowOpen, setRowOpen] = useState<string | null>(null);
  const [weave, setWeave] = useState<{ pack: string; after: string; title: string } | null>(null);
  const [rep, setRep] = useState<ScheduleReport | null>(null);
  const [running, setRunning] = useState(false);
  useEffect(() => {
    phoneApi.schedule().then(setV).catch((e) => toast(errText(e), "bad"));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const back = () => (window.history.length > 1 ? window.history.back() : (window.location.hash = "#/m/me"));
  if (!v) return <div className="sch"><button className="sch-back" onClick={back}><PIcon name="chevron" size={18} /> Back</button><div className="pm-empty"><span className="ph-spinner" /></div></div>;

  const runReport = async () => {
    setRunning(true);
    try {
      setRep(await phoneApi.scheduleReport(7 * 365));
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setRunning(false);
    }
  };
  const save = () => {
    if (!rep?.markdown) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([rep.markdown], { type: "text/markdown" }));
    a.download = "story-schedule-report.md";
    a.click();
  };
  const prof = v.profiles[v.profile];
  return (
    <div className="sch">
      <button className="sch-back" onClick={back}><PIcon name="chevron" size={18} /> Back</button>
      <h2>Story schedule</h2>
      <div className="sch-top">
        <div><b>{prof?.label || v.profile}</b><small>{prof?.about}</small></div>
        <div className="sch-today"><b>{v.presented_today}</b><small>scene{v.presented_today === 1 ? "" : "s"} today{v.queue.length ? ` · ${v.queue.length} more coming` : ""}</small></div>
      </div>
      {v.queue.length > 0 && (
        <div className="sch-queue">
          {v.queue.map((q) => <span key={q.sid} className={cx("sch-q", "imp-" + q.importance)}>{q.title || q.sid}<i>{q.phase.replace("_", " ")}</i></span>)}
        </div>
      )}
      <div className="sch-h">Storylines</div>
      {v.storylines.map((s) => {
        const rows = v.scenes.filter((r) => r.pack === s.pack);
        return (
          <div key={s.pack} className={cx("sch-line", open === s.pack && "open")}>
            <button className="sch-line-top" onClick={() => setOpen(open === s.pack ? null : s.pack)}>
              <span className="sch-line-m"><b>{s.name}</b><small>{s.in_order ? "In order" : "Any order"} · {rows.length} scenes</small></span>
              <span className="sch-chips">
                <i className="c-played">{s.played}</i>
                {(s.eligible + s.queued) > 0 && <i className="c-ready">{s.eligible + s.queued}</i>}
                {s.waiting > 0 && <i className="c-wait">{s.waiting}</i>}
                {(s.unreachable + s.expired) > 0 && <i className="c-no">{s.unreachable + s.expired}</i>}
              </span>
            </button>
            {open === s.pack && (
              <div className="sch-rows">
                <button className="ph-btn primary block sch-play" onClick={() => pgo(`playline/${encodeURIComponent(s.pack)}`)}>
                  <PIcon name="skip" size={16} /> Play it start to finish
                </button>
                {rows.map((r) => (
                  <div key={r.sid}>
                    <button className={cx("sch-row", "st-" + r.state, rowOpen === r.sid && "on")} onClick={() => setRowOpen(rowOpen === r.sid ? null : r.sid)}>
                      <span className="sch-st">{STATE_LABEL[r.state] || r.state}</span>
                      <span className="sch-row-m">
                        <b>{r.title}</b>
                        <small>
                          {r.state === "played" ? r.date : why(r)}
                          {r.window_text && r.state !== "played" ? ` · season: ${r.window_text}` : ""}
                          {r.importance === "major" || r.importance === "finale" ? ` · ${r.importance}` : ""}
                        </small>
                      </span>
                    </button>
                    {rowOpen === r.sid && (
                      <div className="sch-row-acts">
                        <button className="ph-link" onClick={() => pgo(`playline/${encodeURIComponent(s.pack)}/${encodeURIComponent(r.sid)}`)}>Play from here</button>
                        <button className="ph-link" onClick={() => setWeave({ pack: s.pack, after: r.sid, title: r.title })}>Add a scene after this</button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
      <Sheet open={!!weave} onClose={() => setWeave(null)} title="Add a scene here" full>
        {weave && (
          <>
            <p className="ph-dim small" style={{ marginTop: 0 }}>Right after “{weave.title}”. ChatGPT gets this storyline in its own words, what else is going on then, and exactly how to slot it in.</p>
            <AddToStory key={weave.after} target={{ pack: weave.pack, after: weave.after }} onAdded={() => {
              setWeave(null);
              phoneApi.schedule().then(setV);
            }} />
          </>
        )}
      </Sheet>
      <div className="sch-legend"><i className="c-played" /> played <i className="c-ready" /> ready <i className="c-wait" /> not yet <i className="c-no" /> won't happen</div>

      <div className="sch-h">Check the next seven years</div>
      <div className="sch-card">
        <p>Plays your stories forward on a copy (your real story doesn't change), with your character answering every scene, and lists every scene: when it would play or why it can't, anything out of season or out of order, and who each storyline's people are.</p>
        <button className="ph-btn primary block" onClick={runReport} disabled={running}>{running ? <span className="ph-spinner small light" /> : "Run the check"}</button>
        {rep && (
          <div className="sch-rep">
            <div className="sch-rep-counts">
              {Object.entries(rep.counts).map(([k, n]) => <span key={k}><b>{n}</b><small>{STATE_LABEL[k] || k}</small></span>)}
            </div>
            <div className="sch-rep-h">Who's who</div>
            {rep.identity.map((r) => <div key={r.slot} className={cx("sch-rep-l", r.problems.length > 0 && "bad")}>{r.slot}: {r.name || "nobody"}{r.problems.length ? ` — ${r.problems.join("; ")}` : ""}</div>)}
            <div className="sch-rep-h">Contradictions</div>
            {rep.warnings.length ? rep.warnings.map((x, i) => <div key={i} className="sch-rep-l bad">{x.text}</div>) : <div className="sch-rep-l ok">None: everything in season and in order.</div>}
            {rep.deadline_misses.length > 0 && <div className="sch-rep-l bad">{rep.deadline_misses.length} scene{rep.deadline_misses.length === 1 ? "" : "s"} missed their window</div>}
            {rep.busiest_days.length > 0 && <div className="sch-rep-l">Busiest days: {rep.busiest_days.map((b) => `${b.date} (${b.scenes})`).join(", ")}</div>}
            {rep.coverage && <CoverageGrid c={rep.coverage} />}
            <button className="ph-btn block" onClick={save}>Save the full report</button>
          </div>
        )}
      </div>
      <div className="sch-h">Add to your story</div>
      <AddToStory onAdded={() => phoneApi.schedule().then(setV)} />
      <div style={{ height: 30 }} />
    </div>
  );
}

/** Scenes per month for each of the seven years: where the story is full and where it's thin. */
export function CoverageGrid({ c }: { c: Coverage }) {
  const max = Math.max(1, ...c.years.flatMap((y) => y.months));
  return (
    <div className="sch-cov">
      <div className="sch-rep-h">Your seven years, month by month</div>
      <div className="sch-cov-g">
        <span />
        {c.months.map((m) => <i key={m}>{m[0]}</i>)}
        {c.years.map((y) => (
          <React.Fragment key={y.key}>
            <b title={`${y.total} scenes`}>{y.label.replace("College ", "C. ")}</b>
            {y.months.map((n, i) => <span key={i} className="sch-cov-c" style={{ opacity: n ? 0.25 + 0.75 * (n / max) : 1 }} data-n={n || ""} title={`${c.months[i]}: ${n}`} />)}
          </React.Fragment>
        ))}
      </div>
      {c.quiet.length > 0 && <div className="sch-rep-l">Quiet stretches: {c.quiet.slice(0, 4).map((q) => `${q.from.replace(/^\w+, /, "")} to ${q.to.replace(/^\w+, /, "")}`).join(" · ")}</div>}
    </div>
  );
}

/** Ask ChatGPT for more story with a prompt that knows yours, then check what it wrote on a copy before adding it. */
/** Add to your story with ChatGPT: say what you want, copy the prompt, paste the answer, check it on a copy, add it.
 * With a target, it's one spot in one storyline ("add a scene right here"); without, the whole story. */
const SIZE_LABEL: Record<string, string> = { few: "A few", bunch: "A bunch", lot: "A lot" };

export function AddToStory({ onAdded, target, expand }: { onAdded: () => void; target?: { pack: string; after: string | null }; expand?: string }) {
  const { toast, refresh } = usePhone();
  const [ask, setAsk] = useState("");
  const [sugg, setSugg] = useState<string[]>([]);
  const [size, setSize] = useState("bunch");
  const [prompt, setPrompt] = useState<{ text: string; checked: boolean; where?: string; expand?: string; has?: string[] } | null>(null);
  const [paste, setPaste] = useState("");
  const [pv, setPv] = useState<AddPreview | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => {
    if (!target) phoneApi.addPrompt("").then((r) => setSugg(expand ? r.ideas : r.suggestions)).catch(() => undefined);
    setPrompt(null);
    setPv(null);
  }, [expand]); // eslint-disable-line react-hooks/exhaustive-deps
  const run = async (k: string, fn: () => Promise<void>) => {
    setBusy(k);
    try {
      await fn();
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  const make = () => run("make", async () => {
    if (target) {
      const r = await phoneApi.weave(target.pack, target.after, ask);
      setPrompt({ text: r.prompt, checked: true, where: r.where });
    } else if (expand) {
      const r = await phoneApi.expand(expand, ask, size);
      setPrompt({ text: r.prompt, checked: true, expand: r.title, has: r.expansions });
    } else {
      const r = await phoneApi.addPrompt(ask, size);
      setPrompt({ text: r.prompt, checked: r.checked });
    }
  });
  const copy = async () => {
    if (!prompt) return;
    toast((await copyText(prompt.text)) ? "Copied. Paste it into ChatGPT." : "Couldn't copy. Try Share.", "good");
  };
  const share = async () => {
    if (!prompt) return;
    try {
      await (navigator as any).share({ title: "LIFE OS: add to my story", text: prompt.text });
    } catch { /* cancelled */ }
  };
  const check = (t = paste) => run("check", async () => setPv(await phoneApi.addPreview(t, target)));
  const fromFile = async () => {
    const f = await pickFile(".txt,.story,.md,text/plain");
    if (!f) return;
    const t = await f.text();
    setPaste(t);
    check(t);
  };
  const add = () => run("add", async () => {
    if (target) await phoneApi.addInsert(target.pack, target.after, paste);
    else await phoneApi.addPack(paste, expand);
    toast(target ? "Added. It's in the storyline's script now, right where it goes." : `Added: ${pv?.name || "your new scenes"}.`, "good");
    setPv(null);
    setPaste("");
    setPrompt(null);
    onAdded();
    refresh();
  });
  const playedNew = (pv?.new || []).filter((x) => x.state === "played");
  const notNew = (pv?.new || []).filter((x) => x.state !== "played");
  return (
    <div className="sch-card sch-add">
      <div className="sch-step"><i>1</i><b>{target ? "What happens here?" : expand ? "What should this expansion be?" : "What do you want?"}</b></div>
      <textarea className="ph-input" rows={3} value={ask}
        placeholder={target ? "Like: he gets benched and won't talk about it. Or leave it empty and ChatGPT fills the gap."
          : expand ? "Like: their friends hanging out at the house. Holidays with them. A season of her soccer team."
            : "Like: a bunch of scenes in biology class. My sister's friends hanging out at the house. Holidays with my family."}
        onChange={(e) => setAsk(e.target.value)} />
      <div className="sch-sugg">{sugg.map((s) => <button key={s} onClick={() => setAsk(s)}>{s}</button>)}</div>
      {!target && (
        <div className="sch-size">
          <span>How much</span>
          {Object.keys(SIZE_LABEL).map((k) => <button key={k} className={cx(size === k && "on")} onClick={() => setSize(k)}>{SIZE_LABEL[k]}</button>)}
        </div>
      )}
      <button className="ph-btn primary block" disabled={!!busy} onClick={make}>{busy === "make" ? <span className="ph-spinner small light" /> : "Make my ChatGPT prompt"}</button>
      {prompt && (
        <div className="sch-prompt">
          {prompt.expand ? (
            <p className="ph-dim small">Ready: it has {prompt.expand}'s whole script{prompt.has && prompt.has.length ? `, the ${prompt.has.length} expansion${prompt.has.length === 1 ? "" : "s"} it already has` : ""},
              the facts it remembers, your family and cast. ChatGPT sends back just the expansion; it goes in as its own piece, under {prompt.expand}.</p>
          ) : prompt.where ? (
            <p className="ph-dim small">Ready: it goes {prompt.where.replace(/\.$/, "")}. The prompt has this storyline's script, what you chose when you played it,
              what else is going on then, and your family and cast. ChatGPT sends back just the new scene; the game puts it in right there.</p>
          ) : (
            <p className="ph-dim small">Ready: it has your family and cast, every storyline and its scenes, {prompt.checked ? "how your seven years play right now (from your last check), " : ""}and the rules for an answer the game can load.
              {!prompt.checked && " Run the check above first and the prompt will know where your story is thin."}</p>
          )}
          <div className="sch-row2">
            <button className="ph-btn block" onClick={copy}>Copy</button>
            {"share" in navigator && <button className="ph-btn block" onClick={share}>Share to ChatGPT</button>}
          </div>
        </div>
      )}
      <div className="sch-step"><i>2</i><b>Paste what ChatGPT gives you</b></div>
      <textarea className="ph-input mono" rows={4} value={paste} placeholder="Paste the whole answer. The game finds the script inside it." onChange={(e) => { setPaste(e.target.value); setPv(null); }} />
      <div className="sch-row2">
        <button className="ph-btn block" disabled={!!busy || !paste.trim()} onClick={() => check()}>{busy === "check" ? <span className="ph-spinner small" /> : "Check it"}</button>
        <button className="ph-btn soft block" disabled={!!busy} onClick={fromFile}><PIcon name="upload" size={15} /> Or a file</button>
      </div>
      <p className="ph-dim small sch-hint">Checking plays your seven years forward on a copy with it in. Nothing is saved until you add it.</p>
      {pv && !pv.ok && (
        <div className="sch-pv bad">
          <b>It needs a fix before it can load</b>
          {pv.errors.slice(0, 6).map((e, i) => <div key={i} className="sch-rep-l bad">{e}</div>)}
          {pv.errors.length > 6 && <div className="sch-rep-l">…and {pv.errors.length - 6} more</div>}
          {pv.fix_prompt && <button className="ph-btn block" onClick={async () => toast((await copyText(pv.fix_prompt!)) ? "Copied. Paste it back to ChatGPT." : "Couldn't copy.", "good")}>Copy a fix-it message for ChatGPT</button>}
        </div>
      )}
      {pv && pv.ok && (
        <div className="sch-pv">
          <b>{target ? "Your new scene" : pv.name}</b>
          <div className="sch-rep-l ok">{pv.new?.length || 0} new scene{pv.new?.length === 1 ? "" : "s"}: {playedNew.length} play in your seven years
            {playedNew.length ? ` (${playedNew[0].date} to ${playedNew[playedNew.length - 1].date})` : ""}.</div>
          {pv.before !== null && pv.before !== undefined && <div className="sch-rep-l">Your story: {pv.before} scenes play now, {pv.played_total} with this.</div>}
          {notNew.length > 0 && <>
            <div className="sch-rep-h">Won't play</div>
            {notNew.slice(0, 6).map((x) => <div key={x.sid} className="sch-rep-l bad">{x.title}: {x.why || x.reason}{x.detail ? ` (${x.detail})` : ""}</div>)}
          </>}
          {(pv.changed || []).length > 0 && <>
            <div className="sch-rep-h">Changes to scenes you have</div>
            {pv.changed!.slice(0, 8).map((x) => <div key={x.sid} className="sch-rep-l">{x.title}: {x.state === "played" ? `plays ${x.date}` : x.why || x.reason}</div>)}
          </>}
          {pv.warnings.length > 0 && <>
            <div className="sch-rep-h">Heads up (it still loads)</div>
            {pv.warnings.slice(0, 3).map((x, i) => <div key={i} className="sch-rep-l">{x}</div>)}
          </>}
          {(pv.already_there || []).length > 0 && <div className="sch-rep-l bad">Already in your story (skipped): {pv.already_there!.join(", ")}</div>}
          {pv.coverage && <CoverageGrid c={pv.coverage} />}
          <button className="ph-btn primary block" disabled={!!busy} onClick={add}>{busy === "add" ? <span className="ph-spinner small light" /> : "Add it to my story"}</button>
          <p className="ph-dim small">{target ? "It goes into this storyline's script, right after that scene. You can read and edit it under Me > Storylines."
            : expand ? `It goes in as an expansion of ${prompt?.expand || "the storyline"}: its own piece, under it in Me > Storylines.`
            : pv.replaces && pv.replaces.length ? "A storyline you have comes back with the same title: this replaces it." : "Each storyline goes in as its own script: on or off any time under Me > Storylines."}</p>
        </div>
      )}
    </div>
  );
}
