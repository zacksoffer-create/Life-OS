// Roles: everything your storylines need from your story, in one place. Each role: the storylines that use it, who fills it,
// and when nobody does, who's close and what they're missing (a one-tap fix where there is one), or someone made to fit.
// What you pick, fix or add here is groundwork: it comes back when you start over.
import React, { useEffect, useState } from "react";
import { RoleBoard, RoleRow, phoneApi, pgo } from "./api";
import { PIcon } from "./icons";
import { cx, errText } from "./kit";
import { usePhone } from "./PhoneContext";

const STATUS: Record<string, string> = { missing: "Nobody fits", open: "The game will pick", set: "Filled" };
const TYPE: Record<string, string> = { slot: "Storyline person", kind: "Someone in your life", req: "About you" };

function Role({ r, busy, run }: { r: RoleRow; busy: boolean; run: (fn: () => Promise<RoleBoard>, ok: string) => void }) {
  const canPick = r.type === "slot" || (r.type === "kind" && !r.single && r.options.length > 0);
  const edit = (id: string) => pgo(`edit/${encodeURIComponent(id)}`);
  return (
    <div className={cx("rl", r.status)}>
      <div className="rl-h">
        <span>
          <small>{TYPE[r.type]}</small>
          <b>{r.title}</b>
          {r.type === "slot" && r.label && <i>{r.label}</i>}
        </span>
        <em className={cx("rl-st", r.status)}>{STATUS[r.status]}</em>
      </div>
      <div className="rl-uses">{r.storylines.map((s) => `${s.name} (${s.scenes} scene${s.scenes === 1 ? "" : "s"})`).join(" · ")}</div>
      {r.who && (
        <div className="rl-who">
          <button className="rl-person" onClick={() => edit(r.who!.id)}>{r.who.name} <small>{r.who.year}</small></button>
          <span>{r.by === "you" ? "your pick" : r.by === "life" ? "right now" : "the game's pick"}</span>
        </div>
      )}
      {r.note && <p className="ph-dim small rl-note">{r.note}</p>}
      {canPick && r.options.length > 0 && (
        <select className="ph-input" disabled={busy} value={r.by === "you" ? r.who?.id || "" : ""}
          onChange={(e) => run(() => phoneApi.rolePick(r.key, e.target.value || null), e.target.value ? "Picked. Every storyline with this role uses them." : "Back to the game's pick.")}>
          <option value="">{r.type === "slot" && !r.who ? "Pick someone…" : "The game picks"}</option>
          {r.options.map((o) => <option key={o.id} value={o.id}>{o.name} ({o.year})</option>)}
        </select>
      )}
      {r.near.length > 0 && (
        <div className="rl-near">
          <b>Close</b>
          {r.near.map((n) => (
            <div key={n.id} className="rl-nrow">
              <button className="rl-person" onClick={() => edit(n.id)}>{n.name}</button>
              <span>{n.why}</span>
              {n.fix ? (
                <button className="ph-btn soft small" disabled={busy}
                  onClick={() => run(() => phoneApi.roleFix(r.key, n.id, n.fix!), `${n.first} fits now.`)}>{n.fix.label}</button>
              ) : <button className="ph-btn soft small" onClick={() => edit(n.id)}>Edit</button>}
            </div>
          ))}
        </div>
      )}
      {r.can_add && r.status !== "set" && (
        <button className="ph-btn soft block" disabled={busy}
          onClick={() => run(async () => (await phoneApi.roleAdd(r.key)).board, "Added someone who fits. Tap their name to make them yours.")}>
          <PIcon name="plus" size={15} /> Add someone who fits
        </button>
      )}
    </div>
  );
}

/** The Studio's Roles tab. */
export function RolesBody({ onOpen }: { onOpen?: (n: number) => void }) {
  const { toast, refresh } = usePhone();
  const [b, setB] = useState<RoleBoard | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    phoneApi.roles().then(setB).catch((e) => toast(errText(e), "bad"));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (b) onOpen?.(b.open);
  }, [b]); // eslint-disable-line react-hooks/exhaustive-deps
  const run = async (fn: () => Promise<RoleBoard>, ok: string) => {
    setBusy(true);
    try {
      setB(await fn());
      toast(ok, "good");
      refresh();
    } catch (e) {
      toast(errText(e), "bad");
    } finally {
      setBusy(false);
    }
  };
  const missing = b?.roles.filter((r) => r.status === "missing") || [];
  return (
    <>
      <p className="ed-intro">
        Everyone and everything your storylines need, from every storyline that's on. Pick who fills a role, make someone close fit,
        or add someone. All of it comes along when you start over.
      </p>
      <div className="ed-body">
      {!b ? <div className="ed-load"><span className="ph-spinner" /></div> : b.roles.length === 0 ? (
        <p className="ph-dim small">Your storylines don't need anyone in particular yet.</p>
      ) : (
        <>
          {missing.length > 0 && <div className="rl-sum">{missing.length} role{missing.length === 1 ? "" : "s"} nobody fits: those scenes wait until someone does.</div>}
          {b.roles.map((r) => <Role key={r.key} r={r} busy={busy} run={run} />)}
        </>
      )}
      </div>
    </>
  );
}
