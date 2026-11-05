// Saves & Worlds: snapshots, files, new worlds and seeds.
import React, { useState } from "react";
import { api } from "../api";
import { go, useApi, useStore, PLACE } from "../store";
import { Empty, ErrorBox, Icon, Loading, Panel, Tag } from "../ui";
import "./lab.css";

function size(n: number) {
  if (!n) return "-";
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export default function Saves() {
  const { world, refresh, bump, toast } = useStore();
  const [openNow, setOpenNow] = useState(true);
  const { data, error, reload } = useApi<any[]>("/api/saves");
  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [nw, setNw] = useState({ gen_seed: "1234", students: "36", featured: true, sim_seed: "", name: "" });
  const [nwErr, setNwErr] = useState<string | null>(null);
  const [seed, setSeed] = useState("");
  const locked = !!world?.busy;

  const run = async (key: string, fn: () => Promise<any>) => {
    setBusy(key);
    try {
      await fn();
    } catch (e: any) {
      toast(e.message, "bad");
    } finally {
      setBusy(null);
    }
  };

  const save = () =>
    run("save", async () => {
      await api.post("/api/saves", { name: name.trim() || undefined, notes });
      setName("");
      setNotes("");
      toast("World saved.", "good");
      reload();
    });

  const load = (s: any) => {
    if (!window.confirm(`Load "${s.name}" (${s.date_label})? The current world is replaced. Its latest state is in the autosave only until the next autosave overwrites it - save it first if you want to keep it.`)) return;
    run("load" + s.id, async () => {
      await api.post(`/api/saves/${s.id}/load`);
      await refresh();
      bump();
      toast(`Loaded "${s.name}". The world is now at ${s.date_label}.`, "good");
      go("overview");
    });
  };

  const del = (s: any) => {
    if (!window.confirm(`Delete "${s.name}"? This can't be undone.${s.kind === "autosave" ? " (It's the autosave; a new one is written after the next advance or edit.)" : ""}`)) return;
    run("del" + s.id, async () => {
      await api.del(`/api/saves/${s.id}`);
      reload();
    });
  };

  const upload = (f: File | undefined) => {
    if (!f) return;
    run("upload", async () => {
      const r = await api.upload(`/api/saves/upload${openNow ? "?load=1" : ""}`, f);
      if (r.loaded) {
        await refresh();
        bump();
      }
      toast([r.loaded ? `${r.title || "The story"} is open, on ${r.date}.` : `Imported as save #${r.id}. Load it from the list to switch to it.`,
        r.said, r.kept ? "What was open before is kept here under Saves." : ""].filter(Boolean).join(" "), "good");
      if (r.newer) toast(r.newer, "warn");
      reload();
    });
  };

  const newWorld = () => {
    setNwErr(null);
    const gen = parseInt(nw.gen_seed, 10);
    const st = parseInt(nw.students, 10);
    if (!Number.isFinite(gen)) return setNwErr("Generation seed must be a whole number.");
    if (!(st >= 8 && st <= 60)) return setNwErr("Students must be between 8 and 60.");
    if (nw.sim_seed && !/^-?\d+$/.test(nw.sim_seed.trim())) return setNwErr("Simulation seed must be a whole number (or empty).");
    if (!window.confirm("Generate a new world? It replaces the current one. Save the current world first if you want to come back to it.")) return;
    run("new", async () => {
      try {
        await api.post("/api/sim/new", {
          gen_seed: gen,
          students: st,
          featured: nw.featured,
          sim_seed: nw.sim_seed.trim() === "" ? null : parseInt(nw.sim_seed, 10),
          name: nw.name.trim() || undefined,
        });
      } catch (e: any) {
        setNwErr(e.message);
        throw e;
      }
      await refresh();
      bump();
      reload();
      toast("A new world has been generated.", "good");
      go("overview");
    });
  };

  const changeSeed = () => {
    if (!/^-?\d+$/.test(seed.trim())) return toast("The seed must be a whole number.", "warn");
    run("seed", async () => {
      await api.post("/api/sim/seed", { seed: parseInt(seed, 10) });
      await refresh();
      bump();
      toast(`Simulation seed set to ${seed}. Everything from now on follows the new seed.`, "good");
      setSeed("");
    });
  };

  return (
    <div className="stack">
      <div className="page-h">
        <div>
          <h1>Saves &amp; Worlds</h1>
          <p>
            A save is the whole world - every character, relationship, memory, rule and the full history - in one snapshot. Randomness comes
            from the simulation seed plus the day, the time of day and the person, so there is no hidden random state: loading a save and
            advancing produces exactly what the original would have. The world autosaves after every advance and every lab edit.
          </p>
        </div>
      </div>

      <div className="grid g-main">
        <Panel title="Saved worlds" sub="Newest first." actions={<button className="small ghost" onClick={reload}>Refresh</button>}>
          <ErrorBox error={error} />
          {!data ? (
            <Loading />
          ) : !data.length ? (
            <Empty>No saves yet.</Empty>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="mini saves">
                <thead>
                  <tr><th>name</th><th>world date</th><th>seeds</th><th className="num">people</th><th className="num">events</th><th className="num">size</th><th>saved</th><th></th></tr>
                </thead>
                <tbody>
                  {data.map((s) => (
                    <tr key={s.id}>
                      <td>
                        <div className="row" style={{ gap: 6 }}>
                          <b>{s.name}</b>
                          {s.kind === "autosave" ? <Tag tone="info">autosave</Tag> : <Tag>#{s.id}</Tag>}
                        </div>
                        {s.notes && <div className="notes-s">{s.notes}</div>}
                      </td>
                      <td>{s.date_label}<div className="hint">day {s.day}</div></td>
                      <td className="seedline">world {s.gen_seed}<br />sim {s.seed}</td>
                      <td className="num">{s.population}</td>
                      <td className="num">{(s.events || 0).toLocaleString()}</td>
                      <td className="num">{size(s.size)}</td>
                      <td className="dim">{new Date(s.created * 1000).toLocaleString()}</td>
                      <td>
                        <div className="row" style={{ gap: 4, flexWrap: "nowrap" }}>
                          <button className="small" disabled={!!busy || locked} onClick={() => load(s)}>Load</button>
                          <a href={`/api/saves/${s.id}/download`} download><button className="small ghost" title="Download as a .lifeos file">Download</button></a>
                          <button className="small ghost" disabled={!!busy} onClick={() => del(s)}>Delete</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <div className="stack">
          <Panel title="Save the current world" sub={world ? `${world.name} · ${world.date}` : ""}>
            <div className="stack" style={{ gap: 8 }}>
              <input type="text" placeholder={world ? `Save - ${world.date}` : "Name"} value={name} onChange={(e) => setName(e.target.value)} />
              <textarea rows={2} placeholder="Notes (optional): what's going on, what you're about to try..." value={notes} onChange={(e) => setNotes(e.target.value)} />
              <div><button className="primary" disabled={!!busy || locked} onClick={save}><Icon name="save" size={15} /> Save snapshot</button></div>
            </div>
          </Panel>
          <Panel title="Open a backup or save file" sub="A .lifeos file: a backup from the phone app (Me → Back up my story) or a save from a lab. Its storylines and texting come with it.">
            <div className="filebox">
              <input type="file" accept=".lifeos,.json" disabled={!!busy || locked} onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ""; }} />
              {busy === "upload" && <span className="hint">Importing...</span>}
            </div>
            <label className="check" style={{ marginTop: 8 }}>
              <input type="checkbox" checked={openNow} onChange={(e) => setOpenNow(e.target.checked)} /> Open it right away (what's open now is kept here first)
            </label>
          </Panel>
        </div>
      </div>

      <div className="grid g2">
        <Panel title="Generate a new world" sub="The generation seed decides who lives in town; the same seed always builds the same people.">
          <div className="stack builder">
            <div className="form-grid">
              <div className="field"><label>Generation seed</label><input type="number" value={nw.gen_seed} onChange={(e) => setNw({ ...nw, gen_seed: e.target.value })} /></div>
              <div className="field"><label>Students (8-60)</label><input type="number" min={8} max={60} value={nw.students} onChange={(e) => setNw({ ...nw, students: e.target.value })} /></div>
              <div className="field"><label>Simulation seed (optional)</label><input type="text" placeholder="derived from the generation seed" value={nw.sim_seed} onChange={(e) => setNw({ ...nw, sim_seed: e.target.value })} /></div>
              <div className="field"><label>World name (optional)</label><input type="text" placeholder={PLACE.town} value={nw.name} onChange={(e) => setNw({ ...nw, name: e.target.value })} /></div>
            </div>
            <label className="row small" style={{ flexWrap: "nowrap", alignItems: "flex-start" }}>
              <input type="checkbox" checked={nw.featured} onChange={(e) => setNw({ ...nw, featured: e.target.checked })} />
              Include the featured demo cast (Marcus, Devon, Priya, Lena, Theo and the rest) alongside generated students
            </label>
            {nwErr && <ErrorBox error={nwErr} />}
            <div><button className="danger" disabled={!!busy || locked} onClick={newWorld}>Generate and replace the current world</button></div>
          </div>
        </Panel>

        <Panel title="Simulation seed" sub="Controls every random draw from here on.">
          <div className="stack">
            <div className="row">
              <span className="muted">Current seed</span>
              <b className="mono">{world?.seed}</b>
              <span className="dim small">· generation seed {world?.gen_seed}</span>
            </div>
            <p className="muted small" style={{ margin: 0 }}>
              The same seed applied to the same world state reproduces the same future, decision for decision. Changing it keeps everything that
              already happened and gives the rest of the story different luck: who says yes, how a tryout goes, who notices a rumor.
            </p>
            <div className="row">
              <input type="number" placeholder="new seed" value={seed} onChange={(e) => setSeed(e.target.value)} style={{ width: 160 }} />
              <button disabled={!seed || !!busy || locked} onClick={changeSeed}>Set seed</button>
            </div>
            {locked && <span className="hint">The simulation is advancing; these controls unlock when it finishes.</span>}
          </div>
        </Panel>
      </div>
    </div>
  );
}
