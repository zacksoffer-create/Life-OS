// Story Studio: the groundwork for your stories in one place. People (who everyone is, adding someone), Storylines (write
// more, paste, every storyline) and Roles (what your storylines need from your world, and who fills it). Texting has its
// own page.
import React, { useEffect, useState } from "react";
import { phoneApi, pgo } from "./api";
import DialogueCard from "./DialogueCard";
import { EditorPeople } from "./Editor";
import { PIcon } from "./icons";
import { cx, Sheet } from "./kit";
import { RolesBody } from "./Roles";
import StartOver from "./StartOver";
import "./create.css";

const TABS: [string, string][] = [["people", "People"], ["storylines", "Storylines"], ["roles", "Roles"]];

export default function Studio({ route }: { route: string[] }) {
  const tab = TABS.some(([k]) => k === route[0]) ? route[0] : "storylines";
  const [open, setOpen] = useState(0);
  const [restart, setRestart] = useState(false);
  useEffect(() => {
    phoneApi.roles().then((b) => setOpen(b.open)).catch(() => setOpen(0));
  }, []);
  return (
    <div className="ed studio">
      <header className="ed-head">
        <button className="ed-back" onClick={() => pgo("me")} aria-label="Back"><PIcon name="back" size={20} /></button>
        <b>Story Studio</b>
        <span><button className="ed-all" onClick={() => pgo("texting")}>Texting</button></span>
      </header>
      <nav className="st-tabs">
        {TABS.map(([k, l]) => (
          <button key={k} className={cx(tab === k && "on")} onClick={() => pgo(`studio/${k}`)}>
            {l}{k === "roles" && open > 0 && <i className="st-badge">{open}</i>}
          </button>
        ))}
      </nav>
      <div className="st-body" key={tab}>
        {tab === "people" && <div className="ed-body"><EditorPeople /></div>}
        {tab === "storylines" && <div className="ed-body"><DialogueCard /></div>}
        {tab === "roles" && <RolesBody onOpen={setOpen} />}
      </div>
      <div className="st-foot">
        <button className="ph-link" onClick={() => setRestart(true)}>Ready to replay? Start over keeps all of this</button>
      </div>
      <Sheet open={restart} onClose={() => setRestart(false)} title="Start over" full>
        {restart && <StartOver onDone={() => setRestart(false)} />}
      </Sheet>
    </div>
  );
}
