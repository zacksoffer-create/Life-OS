// Content Library > Dialogue: dialogue packs (texts, replies, narration, choices, scenes) written by you, ChatGPT or Claude.
import React, { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { addsLine, copyText } from "../phone/DialogueCard";
import { go, useStore } from "../store";
import { Panel, Tag, cx } from "../ui";

type PackRow = {
  id: string; name: string; author?: string; notes?: string; source: "builtin" | "yours"; enabled: boolean; ok: boolean;
  errors: string[]; warnings: string[]; summary: Record<string, number>; scenes: { id: string; title: string; who?: string }[];
};
type Packs = { packs: PackRow[]; scenes: string[]; lines: number };
type Check = { ok: boolean; errors: string[]; warnings: string[]; summary: Record<string, number>; name?: string };

export default function Dialogue() {
  const { toast, world, refresh } = useStore();
  const [data, setData] = useState<Packs | null>(null);
  const [text, setText] = useState("");
  const [check, setCheck] = useState<Check | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const load = () => api.get("/api/dialogue/packs").then(setData).catch((e) => toast(e.message, "bad"));
  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(key);
    try {
      await fn();
    } catch (e: any) {
      toast(e.message, "bad");
    } finally {
      setBusy(null);
    }
  };
  const doCheck = () => run("check", async () => setCheck(await api.post("/api/dialogue/check", { text })));
  const add = () => run("add", async () => {
    try {
      const r = await api.post("/api/dialogue/packs", { text });
      setData(r);
      setText("");
      setCheck(null);
      toast(`Pack added: ${addsLine(r.summary)}.`, "good");
    } catch (e: any) {
      setCheck({ ok: false, errors: e.errors?.length ? e.errors : [e.message], warnings: [], summary: {} });
    }
  });
  const loadFile = (f: File | undefined) => {
    if (!f) return;
    f.text().then((t) => {
      setText(t);
      setCheck(null);
    });
  };
  const copyPrompt = () => run("copy", async () => {
    const r = await api.get("/api/dialogue/prompt");
    toast((await copyText(r.prompt)) ? "Prompt copied. Paste it into ChatGPT or Claude and describe what you want." : "Couldn't copy.", "good");
  });
  const copyUpdate = (pid?: string) => run(pid ? `up:${pid}` : "up", async () => {
    const r = await api.get(`/api/dialogue/update-prompt${pid ? `?pack=${encodeURIComponent(pid)}` : ""}`);
    toast((await copyText(r.prompt)) ? (pid ? "Upgrade prompt copied, with the pack in it. Paste it into ChatGPT or Claude; the answer replaces the old pack."
      : "Upgrade prompt copied. Paste your pack where it says.") : "Couldn't copy.", "good");
  });
  const copyShow = () => run("show", async () => {
    const r = await api.get("/api/dialogue/show-prompt");
    toast((await copyText(r.prompt)) ? "Season plan prompt copied, with all your storylines in it." : "Couldn't copy.", "good");
  });
  const copyTexting = (pid?: string) => run(pid ? `tx:${pid}` : "tx", async () => {
    const r = await api.get(`/api/dialogue/texting-prompt${pid ? `?pack=${encodeURIComponent(pid)}` : ""}`);
    toast((await copyText(r.prompt)) ? (pid ? "Texting prompt copied, with the pack in it. The answer gives its people their own way of texting."
      : "Texting prompt copied. Paste your pack where it says.") : "Couldn't copy.", "good");
  });
  const toggle = (p: PackRow) => run(p.id, async () => setData(await api.post(`/api/dialogue/packs/${encodeURIComponent(p.id)}/enabled`, { enabled: !p.enabled })));
  const remove = (p: PackRow) => {
    if (!window.confirm(`Remove "${p.name}"?`)) return;
    run(p.id, async () => setData(await api.post(`/api/dialogue/packs/${encodeURIComponent(p.id)}/remove`, {})));
  };
  const tryScene = (sid: string) => run(sid, async () => {
    await api.post(`/api/dialogue/try/${encodeURIComponent(sid)}`, {});
    refresh();
    toast("Scene started. It's waiting on My Story.", "good");
    go("story");
  });

  return (
    <div className="stack">
      <Panel title="Storylines" sub="Storylines, scenes, texts, replies and chat lines, all written as story scripts: plain text, like a screenplay. Each storyline is its own .story file.">
        <div className="row" style={{ gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          <button className="primary" disabled={!!busy} onClick={copyPrompt}>Copy the ChatGPT prompt</button>
          <button disabled={!!busy} onClick={copyShow}>Make it one story (season plan prompt for all your storylines)</button>
          <a className="btn" href="/api/dialogue/guide.md?download=1">Download the script guide (.md)</a>
          <a className="btn" href="/api/dialogue/current?download=1">Download all current dialogue (.json)</a>
        </div>
        <ol className="muted" style={{ lineHeight: 1.7, margin: "0 0 12px", paddingLeft: 18 }}>
          <li>Copy the prompt into ChatGPT or Claude. It includes the script format and every list the game accepts.</li>
          <li>Replace the "What I want" line with your idea ("10 more texts from my older brother", "a scene where my twin sisters fight over the car").</li>
          <li>Paste the answer below, check it, add it. A storyline with the same title as one you have replaces it (that's how you update one).</li>
        </ol>
        <div className="hint" style={{ marginBottom: 6 }}>Paste a script (extra words around it are fine), or load a file:</div>
        <textarea value={text} onChange={(e) => { setText(e.target.value); setCheck(null); }} spellCheck={false}
          placeholder={"=== Title\ncast: bro = older brother, plays basketball\n\n--- First scene  [freshman · September]\nbro: ..."}
          style={{ width: "100%", minHeight: 180, fontFamily: "ui-monospace, Menlo, monospace", fontSize: 12.5 }} />
        <div className="row" style={{ gap: 8, marginTop: 8, flexWrap: "wrap" }}>
          <button disabled={!text.trim() || !!busy} onClick={doCheck}>{busy === "check" ? "Checking..." : "Check it"}</button>
          <button className="primary" disabled={!check?.ok || !!busy} onClick={add}>{busy === "add" ? "Adding..." : "Add it"}</button>
          <button onClick={() => fileRef.current?.click()}>Load a file</button>
          <input ref={fileRef} type="file" accept=".story,.txt,.md,.json" style={{ display: "none" }} onChange={(e) => loadFile(e.target.files?.[0])} />
        </div>
        {check && (
          <div className={cx("callout", check.ok ? "" : "warn")} style={{ marginTop: 12 }}>
            {check.ok ? <b>{check.name || "This script"} looks good: {addsLine(check.summary)}.</b> : <b>Needs fixing ({check.errors.length})</b>}
            {check.errors.length > 0 && (
              <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>{check.errors.slice(0, 30).map((e, i) => <li key={i}>{e}</li>)}</ul>
            )}
            {check.warnings.length > 0 && (
              <ul className="muted" style={{ margin: "6px 0 0", paddingLeft: 18 }}>{check.warnings.slice(0, 10).map((e, i) => <li key={i}>{e}</li>)}</ul>
            )}
            {!check.ok && (
              <button className="small" style={{ marginTop: 8 }} onClick={async () => {
                await copyText("The game found these problems in the script. Fix exactly these and send the whole script again as ONE code block (```):\n- " + check.errors.join("\n- ") + "\n\nThe script:\n```\n" + text.trim() + "\n```");
                toast("Copied. Paste it back to the AI.", "good");
              }}>Copy the problems for the AI</button>
            )}
          </div>
        )}
      </Panel>

      <Panel title={`Loaded packs (${data?.packs.length ?? 0})`}
        sub={data ? `${data.scenes.length} pack scenes and ${data.lines} text lines in play. Built-in packs live in backend/data/dialogue/; yours in lifeos/var/dialogue/.` : ""}>
        <div className="stack" style={{ gap: 10 }}>
          {data?.packs.map((p) => (
            <div key={p.id} className="lib-pack" style={{ opacity: p.enabled ? 1 : 0.6, border: "1px solid var(--line)", borderRadius: 12, padding: 12 }}>
              <div className="row" style={{ justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                <div>
                  <b>{p.name}</b> <Tag tone={p.source === "builtin" ? "accent" : "good"}>{p.source === "builtin" ? "built in" : "yours"}</Tag>
                  {!p.ok && <Tag tone="bad">has problems</Tag>}
                  <div className="hint">{p.author ? `by ${p.author} · ` : ""}{addsLine(p.summary)}</div>
                  {p.notes && <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>{p.notes}</div>}
                </div>
                <div className="row" style={{ gap: 6 }}>
                  <button className="small" disabled={!p.ok || busy === p.id} onClick={() => toggle(p)}>{p.enabled ? "Turn off" : "Turn on"}</button>
                  {p.source === "yours" && p.ok && <button className="small" disabled={!!busy} onClick={() => copyUpdate(p.id)}>Build it out (copy prompt)</button>}
                  {p.source === "yours" && p.ok && <button className="small" disabled={!!busy} onClick={() => copyTexting(p.id)}>Upgrade its texting</button>}
                  {p.source === "yours" && <button className="small ghost" onClick={() => remove(p)}>Remove</button>}
                </div>
              </div>
              {!p.ok && <ul className="muted" style={{ margin: "8px 0 0", paddingLeft: 18 }}>{p.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>}
              {p.scenes.length > 0 && (
                <div className="row" style={{ gap: 6, flexWrap: "wrap", marginTop: 10 }}>
                  {p.scenes.map((sc) => (
                    <button key={sc.id} className="small" disabled={!p.enabled || !(world as any)?.protagonist || !!busy} title={`Play "${sc.id}" now in your story`}
                      onClick={() => tryScene(sc.id)}>▶ {sc.title.replace(/\{(\w+)\}/g, (_, k) => `[${k.replace(/_first$/, "")}]`)}</button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
