// Texting: everything you've added to how people text you (flirt lines, group chats, text lines), on its own page. Add more
// at the top (copy the ChatGPT prompt, paste or upload what it writes, check, add), and below, what you've added: totals and
// each pack, to turn on and off, edit or remove.
import React, { useState } from "react";
import AddTexting from "./AddTexting";
import DialogueCard, { PackRow, isTextingPack } from "./DialogueCard";
import { pgo } from "./api";
import { PIcon } from "./icons";
import { cx } from "./kit";

export default function TextingHub() {
  const [packs, setPacks] = useState<PackRow[] | null>(null);
  const [n, setN] = useState(0);  // (remounts the list after an add)
  const [view, setView] = useState<"add" | "yours">("add");
  const mine = (packs || []).filter(isTextingPack);
  const total = mine.reduce((a, p) => ({ flirt: a.flirt + (p.texting?.flirt || 0), group: a.group + (p.texting?.group_chats || 0),
    lines: a.lines + (p.texting?.lines || 0) }), { flirt: 0, group: 0, lines: 0 });
  return (
    <div className="ed texting-hub">
      <header className="ed-head">
        <button className="ed-back" onClick={() => pgo("me")} aria-label="Back"><PIcon name="back" size={20} /></button>
        <b>Texting</b>
        <span><button className="ed-all" onClick={() => pgo("studio")}>Studio</button></span>
      </header>
      <p className="ed-intro">
        Flirt lines and group chats you add go straight into your texts: options when you flirt (and when someone flirts with
        you), and conversations your crew, team and family start on their own.
      </p>
      <div className="tx-sum">
        <span><b>{total.flirt}</b><small>flirt lines</small></span>
        <span><b>{total.group}</b><small>group chats</small></span>
        <span><b>{total.lines}</b><small>text lines</small></span>
      </div>
      <nav className="st-tabs">
        <button className={cx(view === "add" && "on")} onClick={() => setView("add")}>Add texting</button>
        <button className={cx(view === "yours" && "on")} onClick={() => setView("yours")}>What you've added{mine.length ? ` (${mine.length})` : ""}</button>
      </nav>
      <div className="ed-body">
        {view === "add" ? (
          <AddTexting open inline onClose={() => setView("yours")} onAdded={() => setN((x) => x + 1)} />
        ) : null}
        <div style={{ display: view === "yours" ? "block" : "none" }}>
          <DialogueCard key={n} mode="texting" onData={(d) => setPacks(d.packs)} />
        </div>
      </div>
      <div style={{ height: 28 }} />
    </div>
  );
}
