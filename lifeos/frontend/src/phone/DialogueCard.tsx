// Storylines on the phone: everything is a story script (plain text, like a screenplay). Copy the prompt for ChatGPT,
// paste its answer back, read and edit any storyline's script, turn them on and off, try a scene.
import React, { useEffect, useState } from "react";
import { api } from "../api";
import { OldVersion, pgo, phoneApi } from "./api";
import { PIcon } from "./icons";
import { cx, errText, Sheet } from "./kit";
import { usePhone } from "./PhoneContext";
import { pickFile } from "./StoryFiles";
import BuildStoryline, { BuildStart } from "./BuildStoryline";
import ReviseSheet from "./ReviseSheet";
import { applyUpdate, subscribe, updateReady, UpdateState } from "../standalone/update";
import StorylineRead from "./StorylineRead";

type PackRow = {
  id: string; name: string; author?: string; notes?: string; source: "builtin" | "yours"; enabled: boolean; ok: boolean;
  errors: string[]; warnings: string[]; summary: Record<string, number>; scenes: { id: string; title: string; who?: string }[];
  in_order?: boolean; progress?: { done: number; of: number; next: string | null; in_order: boolean };
  kind?: "script" | "json"; cast?: { name: string; who: string; label: string }[]; expands?: string | null;
  outline?: { total: number; written: number } | null; texting?: { flirt: number; group_chats: number; lines: number }; games?: boolean;
};
export type { PackRow };
/** Texting you added (flirt lines, group chats, text lines), not a storyline: no scenes and no outline. */
export function isTextingPack(p: PackRow) {
  const t = p.texting;
  return !p.scenes.length && !p.outline && !!t && t.flirt + t.group_chats + t.lines > 0;
}
type Packs = { packs: PackRow[]; scenes: string[]; lines: number };
type Check = { ok: boolean; errors: string[]; warnings: string[]; summary: Record<string, number>; name?: string; script?: boolean };

/** "line 12: ..." -> 12 (the line a problem is on), or null. */
export function lineOf(msg: string): number | null {
  const m = /^(?:storyline )?line (\d+):/.exec(msg);
  return m ? Number(m[1]) : null;
}

/** Put the cursor on a line of a textarea (and scroll it into view). */
export function goToLine(ta: HTMLTextAreaElement | null, line: number) {
  if (!ta) return;
  const lines = ta.value.split("\n");
  const n = Math.max(1, Math.min(line, lines.length));
  let start = 0;
  for (let i = 0; i < n - 1; i++) start += lines[i].length + 1;
  ta.focus();
  ta.setSelectionRange(start, start + lines[n - 1].length);
  const lh = parseFloat(getComputedStyle(ta).lineHeight) || 18;
  ta.scrollTop = Math.max(0, (n - 4) * lh);
}

/** How many lines of a paste come before the script itself (ChatGPT's "Here you go!" and the ``` line). */
export function scriptOffset(text: string) {
  const ls = text.split("\n");
  const fence = ls.findIndex((l) => l.trim().startsWith("```"));
  if (fence >= 0) return fence + 1;
  let k = 0;
  while (k < ls.length && !ls[k].trim()) k++;
  return k;
}

export function fixMessage(errors: string[], text: string) {
  return "The LIFE OS game couldn't load this script. Fix exactly these problems and send the whole script again as ONE code block (```), nothing after it:\n\n- "
    + errors.join("\n- ") + "\n\nThe script:\n\n```\n" + text.trim() + "\n```\n";
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch {
      ok = false;
    }
    ta.remove();
    return ok;
  }
}

export function addsLine(s: Record<string, number>) {
  const parts: string[] = [];
  if (s.scenes) parts.push(`${s.scenes} scene${s.scenes === 1 ? "" : "s"}`);
  if (s.texts) parts.push(`${s.texts} text${s.texts === 1 ? "" : "s"}`);
  if (s.replies) parts.push(`${s.replies} repl${s.replies === 1 ? "y" : "ies"}`);
  if (s.moment_choices) parts.push(`${s.moment_choices} choice${s.moment_choices === 1 ? "" : "s"}`);
  if (s.narration) parts.push(`${s.narration} story line${s.narration === 1 ? "" : "s"}`);
  if (s.mods) parts.push(`${s.mods} mod${s.mods === 1 ? "" : "s"}`);
  if (s.lines) parts.push(`${s.lines} line${s.lines === 1 ? "" : "s"}`);
  if (s.trivia) parts.push(`${s.trivia} trivia`);
  return parts.join(" · ") || "nothing yet";
}

type CastKind = { who: string; label: string; current: { id: string; name: string } | null; options: { id: string; name: string; first: string }[] };
type CastSlot = { slot: string; label: string; who: string; current: { id: string; name: string; grade: string } | null;
  options: { id: string; name: string; first: string; year: string }[]; shared_with: string[] };
type Lockable = { kind: string; who: string; sport: string | null; slot: string };
const KIND_WORD: Record<string, string> = { older_brother: "older brother", older_sister: "older sister", younger_brother: "younger brother",
  younger_sister: "younger sister", brother: "brother", sister: "sister", twin: "twin", older_sibling: "older brother or sister",
  younger_sibling: "younger brother or sister", sibling: "brother or sister", friend: "friend", teammate: "teammate" };
const LOCK_TO: Record<string, string[]> = { older_sibling: ["older_brother", "older_sister"], younger_sibling: ["younger_brother", "younger_sister"],
  sibling: ["brother", "sister"], friend: ["friend"], teammate: ["teammate"], twin: ["twin"], older_brother: ["older_brother"],
  older_sister: ["older_sister"], younger_brother: ["younger_brother"], younger_sister: ["younger_sister"], brother: ["brother"], sister: ["sister"] };

/** Who a storyline is about in your story: the game picks the best fit and keeps them; you can change it. A storyline can
 * also be locked onto one named person (a cast slot): the same person every time, in every pack that names them. */
function WhoItsAbout({ pack, onChanged }: { pack: string; onChanged: () => void }) {
  const { toast } = usePhone();
  const [kinds, setKinds] = useState<CastKind[] | null>(null);
  const [slots, setSlots] = useState<CastSlot[]>([]);
  const [lockable, setLockable] = useState<Lockable[]>([]);
  const [lock, setLock] = useState<{ kind: string; who: string; sport: string; close: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.get(`/api/dialogue/cast?pack=${encodeURIComponent(pack)}`).then((r) => {
    setKinds(r.kinds);
    setSlots(r.slots || []);
    setLockable(r.lockable || []);
  }).catch(() => setKinds([]));
  useEffect(() => {
    load();
  }, [pack]); // eslint-disable-line react-hooks/exhaustive-deps
  const pick = async (who: string, char: string) => {
    try {
      const r = await api.post("/api/dialogue/cast", { pack, who, char: char || null });
      setKinds(r.kinds);
      toast("Got it. This storyline is about them from now on.", "good");
    } catch (e) {
      toast(errText(e), "bad");
    }
  };
  const pickSlot = async (slot: string, char: string) => {
    try {
      const r = await api.post("/api/dialogue/cast", { pack, slot, char });
      setSlots(r.slots || []);
      toast("Got it. Every storyline about them uses this person.", "good");
    } catch (e) {
      toast(errText(e), "bad");
    }
  };
  const fit = async (slot: string) => {
    try {
      const r = await phoneApi.editorFit(slot);
      toast(`${r.name} is in your story now, and this storyline is about them. Edit them any time (the editor), and they come along when you start over.`, "good");
      load();
      onChanged();
    } catch (e) {
      toast(errText(e), "bad");
    }
  };
  const doLock = async () => {
    if (!lock) return;
    setBusy(true);
    try {
      const body: any = { slot: lock.who, who: lock.who, replace: [lock.kind], sport: lock.sport || null };
      if (lock.close) Object.assign(body, { bond: { familiarity: 95, affection: 75, trust: 75 }, floor: { affection: 55, trust: 55 } });
      const r = await api.post(`/api/dialogue/packs/${encodeURIComponent(pack)}/lock-cast`, body);
      toast(r.bound ? `Locked: ${r.locked} scenes are about ${r.bound.name} now.` : `Locked ${r.locked} scenes. Nobody in your story fits yet, so they'll wait.`, "good");
      setLock(null);
      onChanged();
      load();
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(false);
    }
  };
  const many = (kinds || []).filter((k) => k.options.length > 1 || k.current);
  if (!many.length && !slots.length && !lockable.length) return null;
  return (
    <div className="dl-cast">
      <div className="dl-sub">Who it's about</div>
      {slots.map((s) => (
        <div key={s.slot} className="dl-slot">
          <label className="dl-cast-row">
            <span>{s.slot.replace(/_/g, " ")}<small>{s.label}</small></span>
            {s.options.length > 0 ? (
              <select className="ph-input" value={s.current?.id || ""} onChange={(e) => pickSlot(s.slot, e.target.value)}>
                {!s.current && <option value="">Nobody yet</option>}
                {s.options.map((o) => <option key={o.id} value={o.id}>{o.name} ({o.year})</option>)}
              </select>
            ) : <em className="dl-none">Nobody in your story fits</em>}
          </label>
          {s.options.length === 0 && (
            <button className="dl-lock" onClick={() => fit(s.slot)}><PIcon name="plus" size={14} /> Add someone who fits ({s.label})</button>
          )}
          {s.shared_with.length > 0 && <small className="dl-shared">Same person in {s.shared_with.join(", ")}</small>}
        </div>
      ))}
      {many.map((k) => (
        <label key={k.who} className="dl-cast-row">
          <span>{k.label}</span>
          <select className="ph-input" value={k.current?.id || ""} onChange={(e) => pick(k.who, e.target.value)}>
            {!k.current && <option value="">Game picks (best fit)</option>}
            {k.options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        </label>
      ))}
      {lockable.map((l) => (
        <button key={l.kind} className="dl-lock" onClick={() => setLock({ kind: l.kind, who: l.who, sport: l.sport || "", close: false })}>
          <PIcon name="check" size={14} /> Lock its {KIND_WORD[l.kind] || l.kind} scenes onto one person
        </button>
      ))}
      <p className="ph-dim small">The same person every time this storyline comes up, in its scenes and its texts.</p>
      <Sheet open={!!lock} onClose={() => setLock(null)} title="Lock who it's about">
        {lock && (
          <div className="dl-lock-sheet">
            <p className="ph-dim small">Its scenes about your {KIND_WORD[lock.kind] || lock.kind} will be about one specific person: bound once, kept through graduation and college, and shared with every storyline locked to the same person. If nobody fits, those scenes wait instead of using someone else.</p>
            <label className="dl-cast-row"><span>Who it is</span>
              <select className="ph-input" value={lock.who} onChange={(e) => setLock({ ...lock, who: e.target.value })}>
                {(LOCK_TO[lock.kind] || [lock.kind]).map((k) => <option key={k} value={k}>Your {KIND_WORD[k] || k}</option>)}
              </select>
            </label>
            <label className="dl-cast-row"><span>Who plays</span>
              <select className="ph-input" value={lock.sport} onChange={(e) => setLock({ ...lock, sport: e.target.value })}>
                <option value="">Any (no sport needed)</option>
                {["basketball", "football", "baseball", "soccer", "softball"].map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label className="dl-check"><input type="checkbox" checked={lock.close} onChange={(e) => setLock({ ...lock, close: e.target.checked })} />
              <span><b>Inseparable</b><small>Start close (or closer) and stay close: any one choice can sting, but the bond holds.</small></span></label>
            <button className="ph-btn primary block" disabled={busy} onClick={doLock}>{busy ? "Locking…" : "Lock it"}</button>
          </div>
        )}
      </Sheet>
    </div>
  );
}

/** Which engine this is, and whether a newer one is out (with the button to get it). */
export function EngineLine() {
  const [engine, setEngine] = useState<string>("");
  const [upd, setUpd] = useState<UpdateState | null>(null);
  useEffect(() => {
    api.get("/api/version").then((r) => setEngine(r.engine)).catch(() => undefined);
    return subscribe(setUpd);
  }, []);
  if (!engine) return null;
  // the screens' own build (their file name), so an update that only changes screens shows here too
  const screens = [...document.querySelectorAll("script[src]")].map((e) => (e as HTMLScriptElement).src.split("/").pop() || "")
    .find((n) => /^play-/.test(n))?.replace(/^play-|\.js$/g, "");
  return (
    <p className="ph-dim small dl-engine">
      Engine {engine}{screens ? ` · screens ${screens}` : ""}
      {upd && upd.latest && (updateReady(upd) ? (
        <>
          {" · "}a newer one is out{" "}
          <button className="dl-engine-go" disabled={upd.updating} onClick={() => applyUpdate()}>
            {upd.updating ? "Updating…" : "Update"}
          </button>
        </>
      ) : " · the newest")}
    </p>
  );
}

/** Your storylines (mode "storylines": write more, paste a script, every storyline) or your texting packs (mode "texting":
 * just the list). */
export default function DialogueCard({ mode = "storylines", onData }: { mode?: "storylines" | "texting"; onData?: (d: Packs) => void }) {
  const { refresh, toast } = usePhone();
  const [data, setData] = useState<Packs | null>(null);
  const [paste, setPaste] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [edit, setEdit] = useState<PackRow | null>(null);
  const [read, setRead] = useState<string | null>(null);
  const [build, setBuild] = useState<BuildStart>(null);
  const [revise, setRevise] = useState<string | null>(null);
  const expandOf = (p: PackRow): BuildStart => {
    const top = p.expands ? data?.packs.find((x) => x.name === p.expands && !x.expands) : p;
    return { expand: top?.id || p.id, expandName: top?.name || p.name };
  };
  const [guide, setGuide] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const load = () => api.get("/api/dialogue/packs").then((d) => { setData(d); onData?.(d); }).catch(() => setData(null));
  useEffect(() => {
    load();
  }, []);

  const copyPrompt = async () => {
    setBusy("copy");
    try {
      const r = await api.get("/api/dialogue/prompt");
      const ok = await copyText(r.prompt);
      toast(ok ? "Copied. Paste it into ChatGPT, say what you want, then paste its answer here." : "Couldn't copy on this phone. Try again.", ok ? "good" : "bad");
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  // the prompt that upgrades a pack you already have (with ?pack= it carries the pack itself); texting: just its people's texting
  const copyUpdate = async (pid?: string, kind: "update" | "texting" = "update") => {
    setBusy(pid ? `${kind === "texting" ? "tx" : "up"}:${pid}` : kind === "texting" ? "tx" : "up");
    try {
      const r = await api.get(`/api/dialogue/${kind === "texting" ? "texting" : "update"}-prompt${pid ? `?pack=${encodeURIComponent(pid)}` : ""}`);
      const ok = await copyText(r.prompt);
      toast(ok ? (pid ? "Copied, with your pack in it. Paste it into ChatGPT, then paste its answer back here: it replaces the old one."
        : "Copied. Paste it into ChatGPT, add your pack where it says, then paste the answer back here.") : "Couldn't copy on this phone. Try again.", ok ? "good" : "bad");
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  const copyGames = async (pid: string) => {
    setBusy(`gm:${pid}`);
    try {
      const r = await api.get(`/api/dialogue/games-prompt?pack=${encodeURIComponent(pid)}`);
      const ok = await copyText(r.prompt);
      toast(ok ? "Copied. Paste it into ChatGPT, then paste its answer with Paste a script: it updates this storyline (the old one stays under Older versions)."
        : "Couldn't copy.", ok ? "good" : "bad");
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  const copyShow = async () => {
    setBusy("show");
    try {
      const r = await api.get("/api/dialogue/show-prompt");
      const ok = await copyText(r.prompt);
      toast(ok ? "Copied, with all your storylines in it. Paste it into ChatGPT, then paste its answer back here." : "Couldn't copy on this phone. Try again.", ok ? "good" : "bad");
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  const showGuide = async () => {
    try {
      setGuide((await api.get("/api/dialogue/guide")).text);
    } catch (e) {
      toast(errText(e), "bad");
    }
  };
  const setOrder = async (p: PackRow, on: boolean) => {
    setBusy(p.id);
    try {
      setData(await api.post(`/api/dialogue/packs/${encodeURIComponent(p.id)}/order`, { in_order: on }));
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  const toggle = async (p: PackRow) => {
    setBusy(p.id);
    try {
      setData(await api.post(`/api/dialogue/packs/${encodeURIComponent(p.id)}/enabled`, { enabled: !p.enabled }));
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  const remove = async (p: PackRow) => {
    if (!window.confirm(`Remove "${p.name}" from this phone?`)) return;
    setBusy(p.id);
    try {
      setData(await api.post(`/api/dialogue/packs/${encodeURIComponent(p.id)}/remove`, {}));
      setOpen(null);
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  const tryScene = async (sid: string) => {
    setBusy(sid);
    try {
      await api.post(`/api/dialogue/try/${encodeURIComponent(sid)}`, {});
      await refresh();
      toast("Here it is. It's in your story now.", "good");
      pgo("");
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };

  const tx = mode === "texting";
  const list = ordered(data?.packs || []).filter((p) => isTextingPack(p) === tx);
  return (
    <>
      <div className="ph-card dl-card">
        {tx ? (
          !list.length && <p className="ph-dim small" style={{ margin: 0 }}>Nothing added yet. What you add shows up here, to turn on and off, edit or remove.</p>
        ) : (
        <>
        <p className="ph-dim small" style={{ marginTop: 0 }}>
          Storylines are written as story scripts: plain text, like a screenplay. <b>Write more</b> walks you through it with
          ChatGPT; open any storyline to read it, write its next scenes, add an expansion or edit its script.
          {data && <> Right now: <b>{data.scenes.length}</b> scenes.</>}
        </p>
        <div className="ph-filebtns">
          <button className="ph-btn primary block" disabled={!!busy} onClick={() => setBuild({})}>
            <PIcon name="chat" size={17} /> Write more
          </button>
          <button className="ph-btn soft block" disabled={!!busy} onClick={() => setPaste(true)}>
            <PIcon name="plus" size={17} /> Paste a script
          </button>
        </div>
        </>
        )}
        <div className="dl-list">
          {list.map((p) => (
            <div key={p.id} className={cx("dl-pack", !p.enabled && "off", p.expands && "exp")}>
              <button className="dl-pack-h" onClick={() => setOpen(open === p.id ? null : p.id)}>
                <span className="dl-pack-m">
                  <b>{p.expands ? <><i className="dl-plus">+</i>{p.name.replace(`${p.expands}: `, "")}</> : p.name}</b>
                  {p.outline && p.outline.written < p.outline.total && <small className="dl-progress">{p.outline.written} of {p.outline.total} scenes written</small>}
                  <small>{p.kind === "json" ? "Old format · " : ""}{p.ok ? (p.progress && p.in_order && p.progress.of
                    ? (p.progress.done >= p.progress.of ? `All ${p.progress.of} chapters done` : `Chapter ${p.progress.done + 1} of ${p.progress.of} next`)
                    : tx ? textingLine(p) : addsLine(p.summary)) : "has problems"}</small>
                </span>
                <span className={cx("ph-switch", p.enabled && "on")} role="switch" aria-checked={p.enabled}
                  onClick={(e) => { e.stopPropagation(); if (p.ok && busy !== p.id) toggle(p); }}><i /></span>
              </button>
              {open === p.id && (
                <div className="dl-pack-b">
                  {p.notes && <p className="ph-dim small">{p.notes}</p>}
                  {p.cast && p.cast.length > 0 && <p className="ph-dim small dl-castline">{p.cast.map((c) => `${c.name}: ${c.label}`).join(" · ")}</p>}
                  {!p.ok && <Problems errors={p.errors} warnings={[]} />}
                  {p.outline && p.outline.written < p.outline.total && (
                    <button className="ph-btn primary block" onClick={() => setBuild({ pack: p.id })}>
                      <PIcon name="chat" size={16} /> Write the next scenes ({p.outline.written} of {p.outline.total} written)
                    </button>
                  )}
                  {p.outline && p.outline.total > 0 && p.outline.written >= p.outline.total && (
                    <button className="ph-btn soft block" onClick={() => setBuild({ pack: p.id })}>
                      <PIcon name="check" size={16} /> Check its scenes (every one asks you something)
                    </button>
                  )}
                  {p.kind === "script" && p.ok && (
                    <div className="dl-acts">
                      <button className={cx("ph-btn", p.outline && p.outline.written < p.outline.total ? "soft" : "primary")} onClick={() => setRead(p.id)}>
                        <PIcon name="book" size={16} /> Read it
                      </button>
                      <button className="ph-btn soft" onClick={() => setBuild(expandOf(p))}>
                        <PIcon name="plus" size={16} /> Add an expansion
                      </button>
                    </div>
                  )}
                  {p.kind === "script" && p.ok && !tx && p.id.startsWith("yours:") && (
                    <button className="ph-btn soft block" onClick={() => setRevise(p.id)}>
                      <PIcon name="check" size={16} /> Fix or change it
                    </button>
                  )}
                  {p.kind === "script" && (
                    <button className="ph-btn soft block" onClick={() => setEdit(p)}>
                      <PIcon name="chat" size={17} /> Edit the script
                    </button>
                  )}
                  {p.kind === "json" && <p className="ph-dim small">This one's in the old JSON format. Ask ChatGPT to rewrite it as a story script (copy the prompt above) and paste that in; then remove this one.</p>}
                  {p.ok && <WhoItsAbout pack={p.id} onChanged={load} />}
                  {p.ok && p.scenes.length > 1 && (
                    <label className="dl-order">
                      <span><b>Play in order</b><small>{p.in_order
                        ? `Its scenes come as chapters, in the order they're written, a few days apart.${p.progress?.next ? ` Next: ${p.progress.next.replace(/\{(\w+)\}/g, "…")}` : ""}`
                        : "Its scenes come up now and then, in any order."}</small></span>
                      <span className={cx("ph-switch", p.in_order && "on")} role="switch" aria-checked={!!p.in_order}
                        onClick={() => setOrder(p, !p.in_order)}><i /></span>
                    </label>
                  )}
                  {p.scenes.length > 0 && (
                    <>
                      <div className="dl-sub">Scenes</div>
                      {p.scenes.map((sc) => (
                        <div key={sc.id} className="dl-scene">
                          <span><b>{sc.title.replace(/\{(\w+)\}/g, (_, k) => (k === "pet" ? "your pet" : k.replace(/_first$/, "").replace("them", "someone").replace("_", " ")))}</b>
                            {sc.who && <small>{sc.who.replace(/_/g, " ")}</small>}</span>
                          <button className="dl-try" disabled={!p.enabled || !!busy} onClick={() => tryScene(sc.id)}>
                            {busy === sc.id ? <span className="ph-spinner small" /> : "Play now"}
                          </button>
                        </div>
                      ))}
                    </>
                  )}
                  {!tx && p.source === "yours" && p.ok && p.kind === "script" && !p.expands && (
                    <button className="ph-btn soft block" disabled={!!busy} onClick={() => copyUpdate(p.id)}>
                      {busy === `up:${p.id}` ? <span className="ph-spinner small" /> : <PIcon name="chat" size={17} />} Build it out: copy the prompt for ChatGPT
                    </button>
                  )}
                  {!tx && p.games && p.source === "yours" && p.ok && p.kind === "script" && (
                    <button className="ph-btn soft block" disabled={!!busy} onClick={() => copyGames(p.id)}>
                      {busy === `gm:${p.id}` ? <span className="ph-spinner small" /> : <PIcon name="trophy" size={17} />} Match it to your real games: copy the prompt
                    </button>
                  )}
                  {!tx && p.source === "yours" && p.ok && p.kind === "script" && (
                    <button className="ph-btn soft block" disabled={!!busy} onClick={() => copyUpdate(p.id, "texting")}>
                      {busy === `tx:${p.id}` ? <span className="ph-spinner small" /> : <PIcon name="chat" size={17} />} Upgrade its texting: copy the prompt
                    </button>
                  )}
                  {p.source === "yours" && <button className="ph-link dl-remove" onClick={() => remove(p)}>{tx ? "Remove this" : "Remove this storyline"}</button>}
                </div>
              )}
            </div>
          ))}
        </div>
        {!tx && (
          <details className="dl-more">
            <summary>How it works and more tools</summary>
        <ol className="dl-how">
          <li><b>Write more</b>: say what you want. ChatGPT plans it as an outline (one line per scene); you check it and make it.</li>
          <li>Then the scenes, a few at a time: copy the prompt, paste what ChatGPT writes. The game puts each one in its place and times it through the year.</li>
          <li>Anything fixable in what ChatGPT wrote is fixed for you (with a note). Tap <b>Read it</b> to read the whole storyline in the order it plays.</li>
        </ol>
        <button className="ph-link" onClick={showGuide}>How scripts work</button>
        <p className="ph-dim small">
          <button className="ph-btn soft block dl-show" disabled={!!busy} onClick={copyShow}>
            <PIcon name="book" size={17} /> Make it one story: copy the season plan prompt
          </button>
          <span className="ph-dim small">All your storylines at once: ChatGPT plans when each one's scenes come across your seven years and writes crossovers that tie them together.</span>
        </p>
          </details>
        )}
      </div>
      {!tx && <OlderVersions onRestored={load} />}
      <PasteSheet open={paste} onClose={() => setPaste(false)} onAdded={(d) => { setData(d); setPaste(false); }} />
      <ScriptSheet pack={edit} onClose={() => setEdit(null)} onSaved={(d) => setData(d)} />
      <StorylineRead pack={read} onClose={() => setRead(null)} onExpand={(pid) => {
        setRead(null);
        const p = data?.packs.find((x) => x.id === pid);
        setBuild(p ? expandOf(p) : { expand: pid });
      }} />
      <ReviseSheet pack={revise} onClose={() => { setRevise(null); load(); }} onChanged={load} />
      <BuildStoryline start={build} onClose={() => { setBuild(null); load(); }} onChanged={load} onRead={(pid) => { setBuild(null); setRead(pid); }} />
      <Sheet open={guide !== null} onClose={() => setGuide(null)} full title="How scripts work">
        <pre className="dl-guide">{guide}</pre>
      </Sheet>
    </>
  );
}

/** "3 flirt lines · 1 group chat" */
function textingLine(p: PackRow) {
  const t = p.texting || { flirt: 0, group_chats: 0, lines: 0 };
  const bit = (n: number, w: string) => (n ? `${n} ${w}${n === 1 ? "" : "s"}` : "");
  return [bit(t.flirt, "flirt line"), bit(t.group_chats, "group chat"), bit(t.lines, "text line")].filter(Boolean).join(" · ") || "nothing yet";
}

export /** Storylines with their expansions right under them. */
function ordered(ps: PackRow[]): PackRow[] {
  const kids: Record<string, PackRow[]> = {};
  for (const p of ps) if (p.expands) (kids[p.expands] = kids[p.expands] || []).push(p);
  const out: PackRow[] = [];
  const placed = new Set<string>();
  for (const p of ps) {
    if (p.expands && ps.some((x) => x.name === p.expands && !x.expands)) continue;
    out.push(p);
    placed.add(p.id);
    for (const k of p.expands ? [] : kids[p.name] || []) {
      out.push(k);
      placed.add(k.id);
    }
  }
  return out.concat(ps.filter((p) => !placed.has(p.id)));
}

function Problems({ errors, warnings, onLine }: { errors: string[]; warnings: string[]; onLine?: (n: number) => void }) {
  if (!errors.length && !warnings.length) return null;
  return (
    <div className="dl-problems">
      {errors.length > 0 && <b>Needs fixing ({errors.length}){onLine && lineOf(errors[0]) ? <small> · tap one to go to its line</small> : null}</b>}
      {errors.slice(0, 12).map((e, i) => {
        const n = lineOf(e);
        return onLine && n ? <button key={i} className="dl-err dl-errbtn" onClick={() => onLine(n)}>{e}</button> : <div key={i} className="dl-err">{e}</div>;
      })}
      {errors.length > 12 && <div className="dl-err">…and {errors.length - 12} more</div>}
      {warnings.slice(0, 6).map((e, i) => <div key={`w${i}`} className="dl-warn">{e}</div>)}
    </div>
  );
}

/** What was replaced, edited or removed, the last few of each storyline: bring any of them back. */
function OlderVersions({ onRestored }: { onRestored: () => void }) {
  const { toast } = usePhone();
  const [open, setOpen] = useState(false);
  const [list, setList] = useState<OldVersion[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => {
    if (open) phoneApi.history().then((r) => setList(r.versions)).catch(() => setList([]));
  }, [open]);
  const restore = async (v: OldVersion) => {
    setBusy(v.file);
    try {
      await phoneApi.restore(v.file);
      toast(`${v.title} is back (what was there is kept as an older version).`, "good");
      onRestored();
      setList((await phoneApi.history()).versions);
    } catch (e: any) {
      toast(errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  return (
    <div className="dl-older">
      <button className="dl-older-head" onClick={() => setOpen(!open)}>
        <b>Older versions</b><small>replaced, edited or removed storylines: bring one back</small><span>{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        list === null ? <span className="ph-spinner small" /> : list.length === 0 ? <p className="ph-dim small">Nothing yet.</p> : (
          <ul>
            {list.slice(0, 15).map((v) => (
              <li key={v.file}>
                <span><b>{v.title}</b><small>{v.scenes} scene{v.scenes === 1 ? "" : "s"} · {v.why} · {new Date(v.at * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</small></span>
                <button className="ph-btn soft" disabled={!!busy} onClick={() => restore(v)}>{busy === v.file ? <span className="ph-spinner small" /> : "Restore"}</button>
              </li>
            ))}
          </ul>
        )
      )}
    </div>
  );
}

function PasteSheet({ open, onClose, onAdded }: { open: boolean; onClose: () => void; onAdded: (d: Packs) => void }) {
  const { toast } = usePhone();
  const [text, setText] = useState("");
  const [check, setCheck] = useState<Check | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const ref = React.useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (!open) setCheck(null);
  }, [open]);
  const doCheck = async (t = text) => {
    if (!t.trim()) return null;
    setBusy("check");
    try {
      const r: Check = await api.post("/api/dialogue/check", { text: t });
      setCheck(r);
      return r;
    } catch (e) {
      toast(errText(e), "bad");
      return null;
    } finally {
      setBusy(null);
    }
  };
  const add = async () => {
    setBusy("add");
    try {
      const r = await api.post("/api/dialogue/packs", { text });
      toast(`Added. ${addsLine(r.summary)}.`, "good");
      setText("");
      onAdded(r);
    } catch (e: any) {
      setCheck({ ok: false, errors: e?.errors?.length ? e.errors : [errText(e)], warnings: [], summary: {} });
    } finally {
      setBusy(null);
    }
  };
  const fromClipboard = async () => {
    try {
      const t = await navigator.clipboard.readText();
      if (t) {
        setText(t);
        doCheck(t);
      }
    } catch {
      toast("Tap the box and paste instead (press and hold, then Paste).", "bad");
    }
  };
  const fromFile = async () => {
    const f = await pickFile(".story,.txt,.md,.json,text/plain,application/json");
    if (!f) return;
    const t = await f.text();
    setText(t);
    doCheck(t);
  };
  return (
    <Sheet open={open} onClose={onClose} full title="Paste a script">
      <p className="ph-dim small" style={{ marginTop: 0 }}>Paste ChatGPT's whole answer: extra words around the script are fine.
        A storyline with the same title as one you have replaces it (that's how you update one).</p>
      <div className="dl-paste-btns">
        <button className="ph-btn soft" onClick={fromClipboard}>Paste from clipboard</button>
        <button className="ph-btn soft" onClick={fromFile}><PIcon name="upload" size={16} /> File</button>
      </div>
      <textarea ref={ref} className="ph-input dl-text" value={text} placeholder={"=== Title\ncast: bro = older brother\n\n--- First scene  [freshman · September]\n..."}
        onChange={(e) => { setText(e.target.value); setCheck(null); }} spellCheck={false} autoCapitalize="off" autoCorrect="off" />
      {check && (
        check.ok ? (
          <div className="dl-ok">
            <b>{check.name || "This script"} looks good.</b> It adds {addsLine(check.summary)}.
            {check.warnings.length > 0 && <Problems errors={[]} warnings={check.warnings} />}
          </div>
        ) : (
          <>
            <Problems errors={check.errors} warnings={check.warnings} onLine={(n) => goToLine(ref.current, n + scriptOffset(text))} />
            <button className="ph-link center" onClick={async () => {
              const ok = await copyText(fixMessage(check.errors, text));
              toast(ok ? "Copied. Paste it back to ChatGPT." : "Couldn't copy.", ok ? "good" : "bad");
            }}>Copy the problems for ChatGPT</button>
          </>
        )
      )}
      <div className="dl-paste-foot">
        {!check?.ok ? (
          <button className="ph-btn primary block" disabled={!text.trim() || !!busy} onClick={() => doCheck()}>
            {busy === "check" ? <span className="ph-spinner small light" /> : null} Check it
          </button>
        ) : (
          <button className="ph-btn primary block" disabled={!!busy} onClick={add}>
            {busy === "add" ? <span className="ph-spinner small light" /> : <PIcon name="plus" size={17} />} Add to my game
          </button>
        )}
      </div>
    </Sheet>
  );
}

/** One storyline's script: read it, edit it, check it, save it (nothing changes until it's clean). */
function ScriptSheet({ pack, onClose, onSaved }: { pack: PackRow | null; onClose: () => void; onSaved: (d: Packs) => void }) {
  const { toast } = usePhone();
  const [text, setText] = useState<string | null>(null);
  const [orig, setOrig] = useState("");
  const [check, setCheck] = useState<Check | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const ref = React.useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    setText(null);
    setCheck(null);
    if (!pack) return;
    api.get(`/api/dialogue/packs/${encodeURIComponent(pack.id)}/script`).then((r) => {
      setText(r.text);
      setOrig(r.text);
    }).catch((e) => toast(errText(e), "bad"));
  }, [pack?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const doCheck = async () => {
    if (text === null) return;
    setBusy("check");
    try {
      setCheck(await api.post("/api/dialogue/check", { text }));
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(null);
    }
  };
  const save = async () => {
    if (!pack || text === null) return;
    setBusy("save");
    try {
      const r = await api.post(`/api/dialogue/packs/${encodeURIComponent(pack.id)}/script`, { text });
      toast(`Saved. ${addsLine(r.summary)}.`, "good");
      setOrig(text);
      setCheck(null);
      onSaved(r);
    } catch (e: any) {
      setCheck({ ok: false, errors: e?.errors?.length ? e.errors : [errText(e)], warnings: [], summary: {} });
    } finally {
      setBusy(null);
    }
  };
  const changed = text !== null && text !== orig;
  const lines = text === null ? 0 : text.split("\n").length;
  return (
    <Sheet open={!!pack} onClose={() => { if (!changed || window.confirm("Close without saving your changes?")) onClose(); }} full title={pack?.name || "Script"}>
      {text === null ? <div className="pm-empty"><span className="ph-spinner" /></div> : (
        <>
          <div className="dl-paste-btns">
            <button className="ph-btn soft" onClick={async () => toast((await copyText(text)) ? "Copied the script." : "Couldn't copy.", "good")}>Copy</button>
            <button className="ph-btn soft" disabled={!changed} onClick={() => { setText(orig); setCheck(null); }}>Undo changes</button>
          </div>
          <textarea ref={ref} className="ph-input dl-text dl-script" value={text} onChange={(e) => { setText(e.target.value); setCheck(null); }}
            spellCheck={false} autoCapitalize="off" autoCorrect="off" />
          <small className="ph-dim dl-count">{lines} lines{changed ? " · edited" : ""}</small>
          {check && (check.ok
            ? <div className="dl-ok"><b>Looks good.</b> {addsLine(check.summary)}.{check.warnings.length > 0 && <Problems errors={[]} warnings={check.warnings} />}</div>
            : (
              <>
                <Problems errors={check.errors} warnings={check.warnings} onLine={(n) => goToLine(ref.current, n)} />
                <button className="ph-link center" onClick={async () => {
                  const ok = await copyText(fixMessage(check.errors, text));
                  toast(ok ? "Copied. Paste it to ChatGPT." : "Couldn't copy.", ok ? "good" : "bad");
                }}>Copy the problems for ChatGPT</button>
              </>
            ))}
          <div className="dl-paste-foot">
            <button className="ph-btn soft block" disabled={!!busy} onClick={doCheck}>
              {busy === "check" ? <span className="ph-spinner small" /> : null} Check it
            </button>
            <button className="ph-btn primary block" disabled={!changed || !!busy} onClick={save}>
              {busy === "save" ? <span className="ph-spinner small light" /> : null} Save
            </button>
          </div>
        </>
      )}
    </Sheet>
  );
}
