// Play a storyline start to finish, right now, to see what's in it: chapter after chapter, your choices steering the
// branches, on a copy of your story (nothing here counts). From any chapter: add a scene right there.
import React, { useEffect, useRef, useState } from "react";
import { Moment, phoneApi, pgo, PlayRead, PlayStep } from "./api";
import { PIcon } from "./icons";
import { cx, errText, Lines, Sheet, Talk } from "./kit";
import { usePhone } from "./PhoneContext";
import { AddToStory } from "./Schedule";
import { MomentCard } from "./StoryTab";

export default function PlayLine({ route }: { route: string[] }) {
  const pack = route[0] || "";
  const from = route[1] || undefined;
  const { toast } = usePhone();
  const [step, setStep] = useState<PlayStep | null>(null);
  const [chapters, setChapters] = useState<{ sid: string; title: string }[]>([]);
  const [beat, setBeat] = useState<Moment | null>(null);
  const [said, setSaid] = useState<PlayRead[]>([]);
  const [chapterDone, setChapterDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [weave, setWeave] = useState<{ after: string | null; title: string } | null>(null);
  const [list, setList] = useState(false);
  const top = useRef<HTMLDivElement>(null);

  const run = async (fn: () => Promise<void>) => {
    if (busy) return;
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(false);
    }
  };
  const show = (r: PlayStep) => {
    setStep(r);
    setBeat(r.moment || null);
    setSaid([]);
    setChapterDone(false);
    top.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const start = (at?: string) => run(async () => {
    const r = await phoneApi.playStart(pack, at);
    if (r.chapters) setChapters(r.chapters);
    setList(false);
    show(r);
  });
  useEffect(() => {
    start(from);
    return () => { phoneApi.playStop().catch(() => undefined); };
  }, [pack, from]); // eslint-disable-line react-hooks/exhaustive-deps

  const pick = (_m: Moment, i: number | null) => run(async () => {
    const r = await phoneApi.playChoose(i);
    setSaid((s) => [...s, r]);
    setBeat(r.moment);
    setChapterDone(r.chapter_done);
  });
  const next = () => run(async () => show(await phoneApi.playNext()));
  const back = () => (window.history.length > 1 ? window.history.back() : pgo("schedule"));
  const cur = step && !step.done && step.chapter ? chapters[step.chapter - 1] : null;
  const last = chapters[chapters.length - 1];

  return (
    <div className="pl" ref={top}>
      <button className="sch-back" onClick={back}><PIcon name="chevron" size={18} /> Back</button>
      <div className="pl-h">
        <div className="ph-kicker">Play it start to finish</div>
        <h2>{step?.storyline || "…"}</h2>
        {step && <div className="pl-prog"><i style={{ width: `${Math.round(100 * (step.done ? 1 : ((step.chapter || 1) - (chapterDone ? 0 : 1)) / Math.max(1, step.of)))}%` }} /></div>}
        <small>{step?.done ? `All ${step.of} chapters` : step?.chapter ? `Chapter ${step.chapter} of ${step.of}` : ""} · on a copy of your story: nothing here counts, and the dates are skipped so you can read straight through.</small>
      </div>

      {(step?.skipped || []).map((s) => (
        <div key={s.sid} className="pl-skip"><b>Chapter {s.chapter} · {s.title}</b> doesn't happen on this path: {s.why}.</div>
      ))}

      {!step && <div className="pm-empty"><span className="ph-spinner" /></div>}

      {said.map((r, k) => (
        <div key={k} className="pl-read">
          {k === 0 && <div className="ph-kicker">{r.read.storyline}</div>}
          {k === 0 ? <h3>{r.read.title}</h3> : null}
          <Talk className="pl-text" text={r.read.text} />
          <div className="pl-chose">You: “{r.read.chose}”</div>
          <Lines lines={r.lines} />
        </div>
      ))}
      {beat && <MomentCard m={beat} more={0} busy={busy} onPick={pick} />}

      {chapterDone && step && !step.done && (
        <div className="pl-next">
          <button className="ph-btn primary block big" disabled={busy} onClick={next}>
            {busy ? <span className="ph-spinner small light" /> : <>{(step.chapter || 0) < step.of ? "Next chapter" : "Finish"} <PIcon name="chevron" size={18} /></>}
          </button>
          {cur && <button className="ph-btn block" onClick={() => setWeave({ after: cur.sid, title: cur.title })}><PIcon name="plus" size={16} /> Add a scene after this one</button>}
        </div>
      )}

      {step?.done && (
        <div className="pl-done">
          <b>That's the whole storyline.</b>
          {(step.path || []).length > 0 && (
            <div className="pl-path">
              {step.path!.map((c) => <div key={c.sid}><span>{c.title}</span><small>{c.picks.length ? c.picks.map((p) => `“${p}”`).join(" → ") : "…"}</small></div>)}
            </div>
          )}
          <button className="ph-btn primary block" onClick={() => start()}>Play it again (choose differently)</button>
          {last && <button className="ph-btn block" onClick={() => setWeave({ after: last.sid, title: last.title })}><PIcon name="plus" size={16} /> Add what happens next</button>}
        </div>
      )}

      {chapters.length > 0 && (
        <div className="pl-list">
          <button className="pl-list-h" onClick={() => setList(!list)}>
            <span>All chapters ({chapters.length})</span><PIcon name="chevron" size={16} className={cx("pl-caret", list && "open")} />
          </button>
          {list && chapters.map((c, k) => (
            <div key={c.sid} className={cx("pl-ch", cur?.sid === c.sid && "on")}>
              <span className="pl-n">{k + 1}</span>
              <span className="pl-t">{c.title}</span>
              <button className="ph-link" disabled={busy} onClick={() => start(c.sid)}>Play from here</button>
              <button className="ph-link" onClick={() => setWeave({ after: c.sid, title: c.title })}>Add after</button>
            </div>
          ))}
        </div>
      )}

      <Sheet open={!!weave} onClose={() => setWeave(null)} title="Add a scene here" full>
        {weave && (
          <>
            <p className="ph-dim small" style={{ marginTop: 0 }}>Right after “{weave.title}”. ChatGPT gets this storyline in its own words, what you just chose, what else is going on then, and exactly how to slot it in.</p>
            <AddToStory key={weave.after || "start"} target={{ pack, after: weave.after }} onAdded={() => {
              setWeave(null);
              toast("Added. Play it again to read it in place.", "good");
              start(weave.after || undefined);
            }} />
          </>
        )}
      </Sheet>
    </div>
  );
}
