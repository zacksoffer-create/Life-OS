// Fix or change a storyline you already have, without writing it again: what's broken goes to ChatGPT in one prompt (just
// those scenes, as they are, with what's wrong), or say what you want changed; paste the reply back and those scenes (and
// cast lines) are replaced in place. Undo puts back what was there. Who's in it switches a set person and a role, no
// ChatGPT needed.
import React, { useEffect, useState } from "react";
import { CastLine, ReviseResult, ReviseView, phoneApi } from "./api";
import { copyText } from "./DialogueCard";
import { PIcon } from "./icons";
import { cx, errText, Sheet } from "./kit";
import { usePhone } from "./PhoneContext";
import { pickFile } from "./StoryFiles";

async function share(text: string, title: string) {
  try {
    await (navigator as any).share({ title, text });
  } catch { /* cancelled */ }
}

function label(s: { n: number | null; title: string }) {
  return s.n ? `Scene ${s.n}: ${s.title}` : s.title;
}

function CastRow({ c, roles, pack, onSaved }: { c: CastLine; roles: string[]; pack: string; onSaved: (cast: CastLine[]) => void }) {
  const { toast } = usePhone();
  const [edit, setEdit] = useState(false);
  const [val, setVal] = useState(c.value);
  const [busy, setBusy] = useState(false);
  useEffect(() => setVal(c.value), [c.value]);
  // keep "girl" / "guy" when picking a role, so a role still fits who they were
  const gender = /\b(girl|guy)\b/i.exec(c.value)?.[1];
  const save = async () => {
    setBusy(true);
    try {
      onSaved((await phoneApi.reviseCast(pack, c.name, val)).cast);
      setEdit(false);
      toast(`${c.name} is now: ${val}`, "good");
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="rv-cast">
      <div className="rv-cast-h">
        <span><b>{c.name}</b><small>{c.value}</small></span>
        <i className={cx("rv-tag", c.named ? "one" : "role")}>{c.named ? "One person" : "A role"}</i>
        {!edit && <button className="ph-link" onClick={() => setEdit(true)}>Change</button>}
      </div>
      {edit && (
        <div className="rv-cast-b">
          <input className="ph-input" value={val} onChange={(e) => setVal(e.target.value)} placeholder="A name (Danny Russo) or a role (friend, guy)" />
          <div className="ed-chips">
            {roles.map((r) => (
              <button key={r} type="button" onClick={() => setVal(gender && !/brother|sister/.test(r) ? `${r}, ${gender}` : r)}>{r}</button>
            ))}
          </div>
          <p className="ph-dim small">A name makes it that one person. A role lets the game pick whoever fits in your story (and keep them).
            Add things like <i>plays basketball</i>, <i>close</i>, <i>2 years older</i> after a comma. Their lines don't change.</p>
          <div className="sch-row2">
            <button className="ph-btn primary block" disabled={busy || !val.trim() || val.trim() === c.value} onClick={save}>
              {busy ? <span className="ph-spinner small light" /> : "Save"}
            </button>
            <button className="ph-btn soft block" disabled={busy} onClick={() => { setVal(c.value); setEdit(false); }}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ReviseSheet({ pack, onClose, onChanged }: { pack: string | null; onClose: () => void; onChanged: () => void }) {
  const { toast } = usePhone();
  const [view, setView] = useState<ReviseView | null>(null);
  const [ask, setAsk] = useState("");
  const [paste, setPaste] = useState("");
  const [res, setRes] = useState<ReviseResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const load = async (pid: string) => {
    try {
      setView(await phoneApi.revise(pid));
    } catch (e) {
      toast(errText(e), "bad");
    }
  };
  useEffect(() => {
    setView(null);
    setAsk("");
    setPaste("");
    setRes(null);
    setOpen(null);
    if (pack) load(pack);
  }, [pack]); // eslint-disable-line react-hooks/exhaustive-deps
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
  const copy = (k: string, get: () => Promise<string>, what: string) => run(k, async () => {
    const ok = await copyText(await get());
    toast(ok ? `Copied the ${what}. Paste it into ChatGPT, then paste its reply below.` : "Couldn't copy. Try Share.", ok ? "good" : "bad");
  });
  const apply = () => run("apply", async () => {
    if (!pack) return;
    const r = await phoneApi.reviseApply(pack, paste);
    setRes(r);
    if (r.ok) {
      setPaste("");
      onChanged();
      await load(pack);
      const n = r.replaced.length;
      toast(`Put in: ${[n ? `${n} scene${n === 1 ? "" : "s"}` : "", r.head.length ? "the top lines" : ""].filter(Boolean).join(" and ")}.`
        + (r.still.length ? ` ${r.still.length} still broken.` : " Nothing's broken."), r.still.length || r.skipped.length ? undefined : "good");
    } else {
      toast(r.errors?.[0] || "Nothing in that could go in.", "bad");
    }
  });
  const undo = () => run("undo", async () => {
    if (!pack || !window.confirm("Put back the storyline as it was before your last paste?")) return;
    setView(await phoneApi.reviseUndo(pack));
    setRes(null);
    onChanged();
    toast("Put back.", "good");
  });
  const fromFile = async () => {
    const f = await pickFile(".txt,.story,.md,text/plain");
    if (f) setPaste(await f.text());
  };
  const ideas = view ? [
    ...view.cast.filter((c) => c.named).slice(0, 2).map((c) => `Make ${c.name} a role (whoever fits) instead of ${c.value}`),
    "Every scene ends on a real decision",
    "More back-and-forth before each choice",
    "Make the choices matter more later on",
  ] : [];
  const broken = view?.scenes || [];
  return (
    <Sheet open={!!pack} onClose={onClose} full title={view ? `Fix or change: ${view.name}` : "Fix or change"}>
      {!view ? <div className="pm-empty"><span className="ph-spinner" /></div> : (
        <div className="bs rv">
          <div className="sch-step"><i>1</i><b>{broken.length ? `What's broken (${broken.length} scene${broken.length === 1 ? "" : "s"})` : "What's broken"}</b></div>
          {broken.length ? (
            <>
              <div className="rv-list">
                {broken.map((s) => (
                  <button key={s.key} type="button" className={cx("rv-sc", open === s.key && "open")} onClick={() => setOpen(open === s.key ? null : s.key)}>
                    <b>{label(s)}</b>
                    {s.problems.map((p, i) => <small key={i}>{p}</small>)}
                    {open === s.key && s.src && <pre className="rv-src">{s.src}</pre>}
                  </button>
                ))}
              </div>
              <div className="sch-row2">
                <button className="ph-btn primary block" disabled={!!busy} onClick={() => copy("fix", async () => (await phoneApi.reviseFixPrompt(view.pack)).prompt, "fix-it prompt")}>
                  {busy === "fix" ? <span className="ph-spinner small light" /> : "Copy the fix-it prompt"}
                </button>
                {"share" in navigator && <button className="ph-btn block" disabled={!!busy}
                  onClick={() => run("share", async () => share((await phoneApi.reviseFixPrompt(view.pack)).prompt, "LIFE OS: fix these scenes"))}>Share</button>}
              </div>
              <p className="ph-dim small">It has just these scenes as they are now, with what's wrong with each. ChatGPT sends them back fixed; paste that below.</p>
            </>
          ) : (
            <p className="ph-dim small">Nothing's broken: all {view.scene_count} scenes ask you something, and every choice has what happens after it.</p>
          )}

          <div className="sch-step"><i>2</i><b>Or change something</b></div>
          <textarea className="ph-input" rows={3} value={ask} onChange={(e) => setAsk(e.target.value)}
            placeholder="Like: make Danny any friend instead of one set person. Move it to junior year. Make Nicole nicer in scene 4." />
          <div className="sch-sugg">{ideas.map((s) => <button key={s} onClick={() => setAsk(s)}>{s}</button>)}</div>
          <button className="ph-btn primary block" disabled={!!busy || !ask.trim()}
            onClick={() => copy("change", async () => (await phoneApi.reviseChangePrompt(view.pack, ask)).prompt, "change prompt")}>
            {busy === "change" ? <span className="ph-spinner small light" /> : "Copy the change prompt"}
          </button>
          <p className="ph-dim small">ChatGPT gets the storyline as it is and sends back only what changes (and fixes anything broken on the way), so a long one never gets cut off.</p>

          <div className="sch-step"><i>3</i><b>Paste ChatGPT's reply</b></div>
          <textarea className="ph-input mono" rows={6} value={paste} onChange={(e) => setPaste(e.target.value)}
            placeholder={broken[0] ? `--- ${broken[0].n ? `${broken[0].n}. ` : ""}${broken[0].title}\n...` : "cast: danny = friend, guy\n\n--- Scene title\n..."} />
          <div className="sch-row2">
            <button className="ph-btn primary block" disabled={!!busy || !paste.trim()} onClick={apply}>
              {busy === "apply" ? <span className="ph-spinner small light" /> : "Put it in"}
            </button>
            <button className="ph-btn soft block" disabled={!!busy} onClick={fromFile}><PIcon name="upload" size={15} /> Or a file</button>
          </div>
          <p className="ph-dim small">Each scene replaces the one with the same {view.outlined ? "number" : "title"}; everything else stays as it is.
            A scene that still can't go in stays as it was.</p>
          {res && (
            <div className={cx("bs-left", res.ok && !res.skipped.length && "soft")}>
              {res.replaced.length > 0 && <><b>Put in ({res.replaced.length})</b>{res.replaced.map((t) => <div key={t} className="bs-left-sc"><span>{t}</span></div>)}</>}
              {res.head.length > 0 && <><b className="bs-gap-h">Changed</b>{res.head.map((t) => <div key={t} className="bs-left-sc"><span className="mono">{t}</span></div>)}</>}
              {res.skipped.length > 0 && <><b className="bs-gap-h">Didn't go in ({res.skipped.length})</b>
                {res.skipped.map((s) => <div key={s.title} className="bs-left-sc"><span>{s.title}</span>{s.problems.slice(0, 4).map((p, i) => <small key={i}>{p}</small>)}</div>)}</>}
              {res.ok && <b className="bs-gap-h">{res.still.length ? `Still broken (${res.still.length})` : "Nothing's broken now"}</b>}
              {res.fix_prompt && (
                <button className="ph-btn soft block" onClick={async () => {
                  const ok = await copyText(res.fix_prompt);
                  toast(ok ? "Copied: a fix-it message for what's still broken." : "Couldn't copy.", ok ? "good" : "bad");
                }}>Copy a fix-it message for what's left</button>
              )}
            </div>
          )}
          {view.can_undo && (
            <button className="ph-link center" disabled={!!busy} onClick={undo}>Undo my last paste</button>
          )}

          {view.cast.length > 0 && (
            <>
              <div className="sch-step"><i>4</i><b>Who's in it</b></div>
              <p className="ph-dim small">Switch anyone between one set person and a role, right here (no ChatGPT).</p>
              {view.cast.map((c) => <CastRow key={c.name} c={c} roles={view.roles} pack={view.pack} onSaved={(cast) => { setView({ ...view, cast }); onChanged(); }} />)}
            </>
          )}
        </div>
      )}
    </Sheet>
  );
}
