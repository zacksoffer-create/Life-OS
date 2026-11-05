// Add texting: flirt lines and group chat conversations. You pick what (which parts of flirting, which style, how many);
// the game builds ChatGPT a template from its own texting slots; ChatGPT fills it in; you paste it and Add it. Every
// section that works goes in right away; any that don't are listed with why, with a fix-it message for just those.
import React, { useEffect, useState } from "react";
import { TextingBreakdown, phoneApi } from "./api";
import { copyText } from "./DialogueCard";
import { PIcon } from "./icons";
import { cx, errText, Sheet } from "./kit";
import { usePhone } from "./PhoneContext";
import { pickFile } from "./StoryFiles";

const WHAT: [string, string][] = [["flirt", "Flirting"], ["group", "Group chats"], ["both", "Both"]];
const PARTS: [string, string][] = [["start", "Starting it"], ["react", "How they react"], ["keep", "Keeping it going"],
  ["first", "When they flirt first"], ["end", "How it ends"]];
const STYLES: [string, string][] = [["all", "Every style"], ["tease", "Teasing / sarcastic"], ["sweet", "Sweet"], ["bold", "Bold"],
  ["funny", "Funny"], ["cheesy", "Cheesy"]];
const SIZES: [string, string][] = [["few", "A few"], ["bunch", "A bunch"], ["lot", "A lot"]];
const IDEAS: Record<string, string[]> = {
  flirt: ["More teasing, less cheesy", "Shy and sweet", "Sarcastic and funny", "Bolder, for once we're already flirty", "Ways to let someone down nicely"],
  group: ["The boys roasting each other", "Fantasy football trash talk", "My team before the rivalry game", "Family chaos at the holidays"],
  both: ["Sarcastic flirting, and the boys roasting each other", "Sweet flirting, and family group chat chaos"],
};
const CHAT: Record<string, string> = { crew: "Crew", team: "Team", family: "Family" };
const WHEN: Record<string, string> = { weekend: "weekend", school_day: "school day", school_night: "school night", winter: "winter",
  has_pet: "pet", pregame: "game tomorrow", win: "after a win", loss: "after a loss" };

type Result = { breakdown: TextingBreakdown; skipped: { header: string; why: string }[]; fix: string | null };

async function share(text: string, title: string) {
  try {
    await (navigator as any).share({ title, text });
  } catch { /* cancelled */ }
}

function Breakdown({ c }: { c: TextingBreakdown }) {
  return (
    <div className="tx-break">
      {c.flirt_total > 0 && (
        <>
          <b>Flirting: {c.flirt_total} line{c.flirt_total === 1 ? "" : "s"}</b>
          <ul>{c.flirt.map((f) => <li key={f.label}><span>{f.label}</span><i>{f.n}</i></li>)}</ul>
        </>
      )}
      {c.texting > 0 && <b>Other texting lines: {c.texting}</b>}
      {c.group_chats.length > 0 && (
        <>
          <b>Group chats: {c.group_chats.length}</b>
          <ul className="tx-gc">
            {c.group_chats.map((g, i) => (
              <li key={i}>
                <small>{[CHAT[g.chat] || g.chat, ...g.when.map((w) => WHEN[w] || w)].join(" · ")} · {g.replies} ways to jump in</small>
                <span>“{g.first}”</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function FixIt({ fix, label }: { fix: string; label?: string }) {
  const { toast } = usePhone();
  return (
    <button className="ph-btn soft block" onClick={async () => {
      const ok = await copyText(fix);
      toast(ok ? "Copied. Send it to ChatGPT, then paste its new answer here." : "Couldn't copy.", ok ? "good" : "bad");
    }}>{label || "Copy a fix-it message for ChatGPT"}</button>
  );
}

export default function AddTexting({ open, onClose, onAdded, inline }: { open: boolean; onClose: () => void; onAdded?: () => void; inline?: boolean }) {
  const { toast } = usePhone();
  const [what, setWhat] = useState("flirt");
  const [parts, setParts] = useState<string[]>(PARTS.map(([k]) => k));
  const [style, setStyle] = useState("all");
  const [ask, setAsk] = useState("");
  const [size, setSize] = useState("bunch");
  const [paste, setPaste] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [size_, setSizeInfo] = useState<{ sections: number; lines: number; group_chats: number } | null>(null);
  const [done, setDone] = useState<Result | null>(null);
  const [problem, setProblem] = useState<{ errors: string[]; fix: string } | null>(null);
  const flirting = what !== "group";
  useEffect(() => {
    if (open) {
      setPaste("");
      setDone(null);
      setProblem(null);
    }
  }, [open]);
  useEffect(() => {  // how big ChatGPT's job is, for what's picked
    let gone = false;
    phoneApi.textingPrompt(what, "", size, parts, style).then((r) => !gone && setSizeInfo(r)).catch(() => undefined);
    return () => { gone = true; };
  }, [what, size, style, parts.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps
  const run = async (k: string, fn: () => Promise<void>) => {
    setBusy(k);
    try {
      await fn();
    } catch (e: any) {
      if (e?.data?.fix_prompt) setProblem({ errors: e.errors || [], fix: e.data.fix_prompt });
      toast(e?.errors?.[0] || errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  const prompt = () => phoneApi.textingPrompt(what, ask, size, parts, style);
  const copy = () => run("copy", async () => {
    const ok = await copyText((await prompt()).prompt);
    toast(ok ? "Copied. Paste it into ChatGPT, then paste what it writes below." : "Couldn't copy. Try Share.", ok ? "good" : "bad");
  });
  const fromFile = async () => {
    const f = await pickFile(".txt,.story,.md,text/plain");
    if (f) {
      setPaste(await f.text());
      setProblem(null);
    }
  };
  const add = () => run("add", async () => {
    setProblem(null);
    const r = await phoneApi.textingAdd(paste);
    setDone({ breakdown: r.breakdown, skipped: r.skipped || [], fix: r.fix_prompt });
    setPaste("");
    onAdded?.();
    toast(r.skipped?.length ? `Added. ${r.skipped.length} section${r.skipped.length === 1 ? "" : "s"} didn't go in: see below.` : "Added. It's live now.",
      r.skipped?.length ? undefined : "good");
  });
  const togglePart = (k: string) => setParts((p) => (p.includes(k) ? (p.length > 1 ? p.filter((x) => x !== k) : p) : [...p, k]));

  const body = (
    <div className="bs">
      {done ? (
        <div className="bs-done">
          <b>Added. It's in the game now.</b>
          <Breakdown c={done.breakdown} />
          {done.skipped.length > 0 && (
            <div className="bs-left soft">
              <b className="bs-gap-h">Didn't go in ({done.skipped.length})</b>
              {done.skipped.map((s, i) => <div key={i} className="bs-left-sc"><span>{s.header}</span><small>{s.why}</small></div>)}
              {done.fix && <FixIt fix={done.fix} label="Copy a fix-it message for just these" />}
            </div>
          )}
          <p className="ph-dim small">Flirt lines show up as options when you flirt (and when someone flirts with you); group chats start up on
            their own, a few nights a week. Turn it off, edit or remove it under What you've added.</p>
          <button className="ph-btn primary block" onClick={() => setDone(null)}>Add more</button>
        </div>
      ) : (
        <>
          <div className="sch-step"><i>1</i><b>What do you want to add?</b></div>
          <div className="sch-size">
            {WHAT.map(([k, l]) => <button key={k} className={cx(what === k && "on")} onClick={() => setWhat(k)}>{l}</button>)}
          </div>
          {flirting && (
            <>
              <div className="tx-pick-l">Which parts of flirting</div>
              <div className="ed-chips">
                {PARTS.map(([k, l]) => <button key={k} className={cx(parts.includes(k) && "on")} onClick={() => togglePart(k)}>{l}</button>)}
              </div>
              <div className="tx-pick-l">Style</div>
              <div className="ed-chips">
                {STYLES.map(([k, l]) => <button key={k} className={cx(style === k && "on")} onClick={() => setStyle(k)}>{l}</button>)}
              </div>
            </>
          )}
          <textarea className="ph-input" rows={2} value={ask} onChange={(e) => setAsk(e.target.value)}
            placeholder={what === "group" ? "Like: the boys roasting each other about fantasy football." : "Like: more teasing, a little sarcastic. Less cheesy."} />
          <div className="sch-sugg">{IDEAS[what].map((s) => <button key={s} onClick={() => setAsk(s)}>{s}</button>)}</div>
          <div className="sch-size"><span>How much</span>
            {SIZES.map(([k, l]) => <button key={k} className={cx(size === k && "on")} onClick={() => setSize(k)}>{l}</button>)}
          </div>
          {size_ && (
            <p className="ph-dim small tx-job">
              ChatGPT fills in {[size_.sections ? `${size_.sections} flirt section${size_.sections === 1 ? "" : "s"} (about ${size_.lines} lines)` : "",
                size_.group_chats ? `${size_.group_chats} group chats` : ""].filter(Boolean).join(" and ")}.
              {size_.sections > 30 ? " That's a long answer: if ChatGPT stops partway, pick fewer parts or one style." : ""}
            </p>
          )}
          <div className="sch-row2">
            <button className="ph-btn primary block" disabled={!!busy} onClick={copy}>{busy === "copy" ? <span className="ph-spinner small light" /> : "Copy the ChatGPT prompt"}</button>
            {"share" in navigator && (
              <button className="ph-btn block" disabled={!!busy} onClick={() => run("share", async () => share((await prompt()).prompt, "LIFE OS: texting"))}>Share</button>
            )}
          </div>
          <div className="sch-step"><i>2</i><b>Paste what ChatGPT wrote</b></div>
          <textarea className="ph-input mono" rows={6} value={paste}
            placeholder={"flirt tease:\n  ok who said you could be this funny\nflirt payoff plans:\n  diner friday. you're buying fries"}
            onChange={(e) => { setPaste(e.target.value); setProblem(null); }} />
          <div className="sch-row2">
            <button className="ph-btn primary block" disabled={!!busy || !paste.trim()} onClick={add}>{busy === "add" ? <span className="ph-spinner small light" /> : "Add it"}</button>
            <button className="ph-btn soft block" disabled={!!busy} onClick={fromFile}><PIcon name="upload" size={15} /> Or a file</button>
          </div>
          {problem && (
            <div className="bs-left">
              <b>{problem.errors[0] || "That couldn't go in"}</b>
              {problem.errors.slice(1, 8).map((x, i) => <small key={i}>{x}</small>)}
              <FixIt fix={problem.fix} />
            </div>
          )}
          <p className="ph-dim small">Everything that works goes in; anything that doesn't is listed, with a message for ChatGPT to fix just that.</p>
        </>
      )}
    </div>
  );
  return inline ? body : <Sheet open={open} onClose={onClose} full title="Add texting">{body}</Sheet>;
}
