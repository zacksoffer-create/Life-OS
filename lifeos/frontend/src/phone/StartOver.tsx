// Start over: back to the first day, in the same town with the same people (built from your setup), with the groundwork
// you've done (who people are, people you added, relationships you set, who your storylines are about) or without it.
import React, { useEffect, useState } from "react";
import { Groundwork, GroundworkRow, phoneApi, pgo } from "./api";
import { Seg } from "./CreateStory";
import { PIcon } from "./icons";
import { errText } from "./kit";
import { usePhone } from "./PhoneContext";

const KIND: Record<string, string> = { added: "Added", person: "Who they are", pair: "Relationship", slot: "Storyline person", pick: "Storyline pick" };

export function GroundworkList({ g, onRemove }: { g: Groundwork; onRemove?: (r: GroundworkRow) => void }) {
  if (!g.rows.length) {
    return <p className="ph-dim small">Nothing yet. What you change in the editor (who someone is, people you add, relationships you set)
      and who your storylines are about show up here.</p>;
  }
  return (
    <div className="gw-list">
      {g.rows.map((r) => (
        <div key={`${r.kind}:${r.key}`} className="gw-row">
          <span className="gw-m">
            <small>{KIND[r.kind] || r.kind}</small>
            <b>{r.title}</b>
            {r.what && <i>{r.what}</i>}
          </span>
          {onRemove && <button className="gw-x" aria-label="Leave it out" onClick={() => onRemove(r)}>×</button>}
        </div>
      ))}
    </div>
  );
}

export default function StartOver({ onDone }: { onDone: () => void }) {
  const { toast, refresh } = usePhone();
  const [g, setG] = useState<Groundwork | null>(null);
  const [keep, setKeep] = useState<"keep" | "clean">("keep");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    phoneApi.groundwork().then(setG).catch((e) => toast(errText(e), "bad"));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const remove = async (r: GroundworkRow) => {
    try {
      setG(await phoneApi.groundworkRemove(r.kind, r.key));
    } catch (e) {
      toast(errText(e), "bad");
    }
  };
  const go = async () => {
    setBusy(true);
    try {
      const r = await phoneApi.restart(keep === "keep");
      const c = r.carried || { done: 0, skipped: [] };
      toast(["Back to the first day.", keep === "keep" && c.done ? `${c.done} of your changes came along.` : "",
        c.skipped.length ? `${c.skipped.length} couldn't: ${c.skipped.slice(0, 2).join("; ")}` : ""].filter(Boolean).join(" "), "good");
      await refresh();
      onDone();
      pgo("");
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="gw">
      <p className="ph-dim small">Back to the first day of freshman year, in the same town with the same people (it's built from your
        setup). Your storylines and texting stay. What happened in this run ends: back it up first if you want to keep it.</p>
      <Seg value={keep} options={[["keep", "Keep my changes"], ["clean", "Just my setup"]]} onChange={(v) => setKeep(v)} />
      {keep === "keep" && (
        <>
          <div className="gw-h">What comes along{g ? ` (${g.count})` : ""}</div>
          {g ? <GroundworkList g={g} onRemove={remove} /> : <div className="ed-load"><span className="ph-spinner" /></div>}
          {g && g.count > 0 && <p className="ph-dim small">Tap × to leave something out (it stays as it is in this run). Mood, grades,
            money and skills start fresh: that's how the run went, not who they are.</p>}
        </>
      )}
      <button className="ph-btn primary block" disabled={busy} onClick={go}>
        {busy ? <><span className="ph-spinner small light" /> Building the first day…</> : <><PIcon name="sparkle" size={17} /> Start over</>}
      </button>
      <button className="ph-btn soft block" disabled={busy} onClick={() => { onDone(); pgo("create"); }}>Change the setup first</button>
      <p className="ph-dim small">Changing the setup (Make a new story) can bring these along too: there's a box for it on the last step.</p>
    </div>
  );
}
