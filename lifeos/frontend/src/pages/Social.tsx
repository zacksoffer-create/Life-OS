import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY } from "d3-force";
import React, { useMemo, useState } from "react";
import { go, useApi, useStore } from "../store";
import { Avatar, Empty, Loading, Name, Names, Panel, Signed, Tabs, Tag, fmt } from "../ui";
import { RelationshipModal } from "./Characters";
import "./social.css";

const PALETTE = ["#57d9c3", "#9b8cff", "#ffb547", "#ff8fc7", "#6bb6ff", "#66d98f", "#ff9a6b", "#c6e46a", "#e78cff", "#7fd3ff"];
const GRADE_COLOR: Record<string, string> = { "9": "#66d98f", "10": "#6bb6ff", "11": "#9b8cff", "12": "#ffb547", alumni: "#8f96b8" };
const EDGE_STYLE: Record<string, { stroke: string; width: number; dash?: string; opacity: number }> = {
  mutual: { stroke: "#57d9c3", width: 2, opacity: 0.75 },
  one_sided: { stroke: "#57d9c3", width: 1.2, dash: "4 4", opacity: 0.5 },
  partner: { stroke: "#ff8fc7", width: 3.2, opacity: 0.95 },
  crush: { stroke: "#ff8fc7", width: 1.4, dash: "2 4", opacity: 0.8 },
  conflict: { stroke: "#ff6b81", width: 1.8, opacity: 0.8 },
  acquaintance: { stroke: "#4a5385", width: 1, opacity: 0.35 },
};

export default function Social({ route }: { route: string[] }) {
  const [mode, setMode] = useState("friends");
  const [color, setColor] = useState("clique");
  const [alumni, setAlumni] = useState(false);
  const [tab, setTab] = useState(route[1] === "groups" ? "groups" : "cliques");
  const [sel, setSel] = useState<string | null>(null);
  const [pair, setPair] = useState<[string, string] | null>(null);
  const { data, error } = useApi(`/api/social/graph?mode=${mode}&alumni=${alumni}`, [mode, alumni]);
  const groups = useApi("/api/groups");
  if (error) return <div className="errorbox">{error}</div>;
  return (
    <div className="stack">
      <div className="page-h">
        <div>
          <h1>Social Network</h1>
          <p>Who is close to whom, who wants more than friendship, and where the friction is. Lines are drawn from both people's own views, so a dashed line means only one of them calls it a friendship.</p>
        </div>
      </div>
      <div className="row">
        <Tabs tabs={[["friends", "Friendships"], ["romance", "Romance"], ["conflict", "Conflict"], ["all", "Everything"]]} active={mode} onChange={setMode} />
        <Tabs tabs={[["clique", "Color by clique"], ["grade", "Color by grade"]]} active={color} onChange={setColor} />
        <label className="row small muted" style={{ gap: 6 }}><input type="checkbox" checked={alumni} onChange={(e) => setAlumni(e.target.checked)} /> include alumni</label>
      </div>
      <div className="grid g-main">
        <Panel pad={false}>
          {!data ? <Loading what="Laying out the web" /> : <Graph data={data} color={color} sel={sel} onSel={setSel} onPair={(a, b) => setPair([a, b])} />}
          <div className="edge-legend">
            {Object.entries({ mutual: "mutual friends", one_sided: "one-sided", partner: "dating", crush: "crush", conflict: "rivalry / dislike", acquaintance: "know each other" }).map(([k, l]) => (
              <span key={k}><svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4" stroke={EDGE_STYLE[k].stroke} strokeWidth={EDGE_STYLE[k].width} strokeDasharray={EDGE_STYLE[k].dash} /></svg>{l}</span>
            ))}
            <span className="dim">node size = popularity · click a person, or a line between two people</span>
          </div>
        </Panel>
        <SidePanel data={data} sel={sel} onPair={(a, b) => setPair([a, b])} />
      </div>
      <Tabs tabs={[["cliques", "Cliques"], ["groups", "Groups & institutions"], ["gaps", "Perception gaps"], ["households", "Households"]]} active={tab} onChange={setTab} />
      {tab === "cliques" && <Cliques g={groups.data} />}
      {tab === "groups" && <Groups g={groups.data} />}
      {tab === "gaps" && <Gaps data={data} onPair={(a, b) => setPair([a, b])} />}
      {tab === "households" && <Households g={groups.data} />}
      {pair && <RelationshipModal a={pair[0]} b={pair[1]} onClose={() => setPair(null)} />}
    </div>
  );
}

function Graph({ data, color, sel, onSel, onPair }: any) {
  const W = 900, H = 620;
  const [hover, setHover] = useState<any>(null);
  const layout = useMemo(() => {
    const nodes = data.nodes.map((n: any) => ({ ...n }));
    const idx: Record<string, any> = {};
    nodes.forEach((n: any) => (idx[n.id] = n));
    const links = data.edges.filter((e: any) => idx[e.a] && idx[e.b]).map((e: any) => ({ ...e, source: e.a, target: e.b }));
    const sim = forceSimulation(nodes)
      .force("link", forceLink(links).id((d: any) => d.id).distance((l: any) => (l.kind === "conflict" ? 170 : l.kind === "acquaintance" ? 140 : 70 - Math.min(30, l.weight / 3))).strength((l: any) => (l.kind === "conflict" ? 0.05 : l.kind === "acquaintance" ? 0.05 : 0.5)))
      .force("charge", forceManyBody().strength(-210))
      .force("center", forceCenter(W / 2, H / 2))
      .force("x", forceX(W / 2).strength(0.05))
      .force("y", forceY(H / 2).strength(0.07))
      .force("collide", forceCollide().radius((d: any) => 14 + d.popularity / 9))
      .stop();
    for (let i = 0; i < 320; i++) sim.tick();
    nodes.forEach((n: any) => {
      n.x = Math.max(24, Math.min(W - 24, n.x));
      n.y = Math.max(24, Math.min(H - 24, n.y));
    });
    return { nodes, links, idx };
  }, [data]);
  const cliqueColor: Record<string, string> = {};
  data.cliques.forEach((q: any, i: number) => (cliqueColor[q.id] = PALETTE[i % PALETTE.length]));
  const fill = (n: any) => (color === "grade" ? GRADE_COLOR[n.role === "alumni" ? "alumni" : String(n.grade)] : n.clique && cliqueColor[n.clique] ? cliqueColor[n.clique] : "#5d6488");
  const near = sel ? new Set(layout.links.filter((l: any) => l.source.id === sel || l.target.id === sel).flatMap((l: any) => [l.source.id, l.target.id])) : null;
  return (
    <div className="graph-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="graph" onClick={() => onSel(null)}>
        {layout.links.map((l: any, i: number) => {
          const st = EDGE_STYLE[l.kind] || EDGE_STYLE.acquaintance;
          const dim = sel && l.source.id !== sel && l.target.id !== sel;
          return (
            <g key={i} className="edge" onClick={(e) => { e.stopPropagation(); onPair(l.source.id, l.target.id); }}
              onMouseEnter={() => setHover(l)} onMouseLeave={() => setHover(null)}>
              <line x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y} stroke="transparent" strokeWidth={10} />
              <line x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y} stroke={st.stroke} strokeWidth={st.width}
                strokeDasharray={st.dash} opacity={dim ? 0.08 : st.opacity} />
            </g>
          );
        })}
        {layout.nodes.map((n: any) => {
          const r = 8 + n.popularity / 10;
          const dim = near && !near.has(n.id) && n.id !== sel;
          return (
            <g key={n.id} transform={`translate(${n.x},${n.y})`} className="node" opacity={dim ? 0.25 : 1}
              onClick={(e) => { e.stopPropagation(); onSel(n.id === sel ? null : n.id); }}>
              <circle r={r + 3} fill="none" stroke={n.id === sel ? "#fff" : "transparent"} strokeWidth={2} />
              <circle r={r} fill={fill(n)} stroke="#0c0f1d" strokeWidth={2} />
              <text y={r + 13} textAnchor="middle" className="node-label">{n.short}</text>
            </g>
          );
        })}
      </svg>
      {hover && (
        <div className="edge-tip">
          <b>{hover.source.short}</b> sees <b>{hover.target.short}</b> as {hover.ab.label}{hover.ab.crush ? " (crush)" : ""} ({fmt(hover.ab.affection)})<br />
          <b>{hover.target.short}</b> sees <b>{hover.source.short}</b> as {hover.ba.label}{hover.ba.crush ? " (crush)" : ""} ({fmt(hover.ba.affection)})
        </div>
      )}
    </div>
  );
}

function SidePanel({ data, sel, onPair }: any) {
  const { chars } = useStore();
  if (!data) return <Panel title="Details"><Loading /></Panel>;
  if (!sel) {
    const kinds: Record<string, number> = {};
    data.edges.forEach((e: any) => (kinds[e.kind] = (kinds[e.kind] || 0) + 1));
    return (
      <Panel title="Reading the map" sub="Pick someone to focus on their connections">
        <div className="stack" style={{ gap: 10 }}>
          <div className="chips">{Object.entries(kinds).map(([k, v]) => <Tag key={k}>{k.replace("_", "-")}: {v}</Tag>)}</div>
          <div className="muted small">
            Friendships are judged separately by each person: a pair only gets a solid line when <b>both</b> count the other as a friend.
            Clusters you see here are what the weekly clique detector picks up.
          </div>
          <div>
            <div className="hint" style={{ marginBottom: 6 }}>Cliques right now</div>
            {data.cliques.map((q: any, i: number) => (
              <div key={q.id} className="row small" style={{ marginBottom: 6 }}>
                <span className="swatch" style={{ background: PALETTE[i % PALETTE.length] }} /> <b>{q.name}</b> <span className="dim">{q.members.length}</span>
              </div>
            ))}
            {!data.cliques.length && <div className="dim small">none yet</div>}
          </div>
        </div>
      </Panel>
    );
  }
  const c = chars[sel];
  const mine = data.edges.filter((e: any) => e.a === sel || e.b === sel).map((e: any) => {
    const other = e.a === sel ? e.b : e.a;
    const myView = e.a === sel ? e.ab : e.ba;
    const theirView = e.a === sel ? e.ba : e.ab;
    return { other, kind: e.kind, myView, theirView };
  }).sort((x: any, y: any) => y.myView.affection - x.myView.affection);
  return (
    <Panel title={c?.name} sub={c ? `${c.role === "student" ? "Grade " + c.grade : c.role} · ${c.archetype}` : ""}
      actions={<button className="small" onClick={() => go(`characters/${sel}`)}>Open profile</button>}>
      <div className="row" style={{ marginBottom: 10 }}>
        <Avatar id={sel} size={48} />
        <div className="small muted">{c?.bio}</div>
      </div>
      <div className="hint" style={{ marginBottom: 6 }}>Connections in this view ({mine.length})</div>
      <div className="scroll short">
        {mine.map((m: any) => (
          <div key={m.other} className="conn" onClick={() => onPair(sel, m.other)}>
            <Name id={m.other} />
            <div style={{ flex: 1 }}><Signed value={m.myView.affection} /></div>
            <span className="small dim">{m.myView.label}{m.theirView.label !== m.myView.label ? ` / they: ${m.theirView.label}` : ""}</span>
          </div>
        ))}
        {!mine.length && <Empty>No connections in this view.</Empty>}
      </div>
    </Panel>
  );
}

function Cliques({ g }: any) {
  if (!g) return <Loading />;
  const active = g.cliques.filter((q: any) => q.active);
  const past = g.cliques.filter((q: any) => !q.active);
  return (
    <div className="grid g3">
      {active.map((q: any) => (
        <Panel key={q.id} title={q.name} sub={`formed day ${q.formed} · ${q.members.length} members · avg popularity ${fmt(q.popularity)}`}>
          <div className="row" style={{ gap: 4, marginBottom: 8 }}>{q.members.map((m: string) => <Avatar key={m} id={m} size={30} ring={false} />)}</div>
          <div className="small"><Names ids={q.members} max={10} /></div>
          <div className="chips" style={{ marginTop: 8 }}>{(q.interests || []).map(([k, v]: any) => <Tag key={k}>{k.replace(/_/g, " ")} {fmt(v)}</Tag>)}</div>
          {q.history?.length > 1 && <div className="hint" style={{ marginTop: 8 }}>{q.history.length - 1} membership changes since it formed</div>}
        </Panel>
      ))}
      {!active.length && <Empty>No cliques yet.</Empty>}
      {past.length > 0 && (
        <Panel title="Cliques that broke apart">
          {past.slice(-8).map((q: any) => <div key={q.id} className="small">{q.name} <span className="hint">day {q.formed}-{q.dissolved}</span></div>)}
        </Panel>
      )}
    </div>
  );
}

function Groups({ g }: any) {
  if (!g) return <Loading />;
  const order: Record<string, number> = { team: 0, production: 1, council: 2, club: 3, job: 4 };
  return (
    <div className="grid g3">
      {[...g.groups].sort((a: any, b: any) => order[a.kind] - order[b.kind]).map((gr: any) => (
        <Panel key={gr.id} title={gr.name} sub={`${gr.kind} · ${gr.selection === "open" ? "open membership" : gr.selection} · ${gr.members.length}/${gr.capacity}`}>
          {gr.staff && <div className="small" style={{ marginBottom: 6 }}>Led by <Name id={gr.staff} full /></div>}
          {gr.kind === "team" && <div className="small muted">{gr.in_season ? `In season · ${gr.record.w}-${gr.record.l}` : "Off season"}{gr.history?.length ? ` · last season ${gr.history[gr.history.length - 1].record.w}-${gr.history[gr.history.length - 1].record.l}` : ""}</div>}
          {gr.production && <div className="small muted">Rehearsing {gr.production.name}{gr.production.lead ? <> · lead <Name id={gr.production.lead} /></> : ""}</div>}
          <div className="row" style={{ gap: 4, margin: "8px 0" }}>
            {gr.members.map((m: string) => (
              <div key={m} className="member" title={gr.absences[m] ? `missed ${gr.absences[m]} of the last sessions` : ""}>
                <Avatar id={m} size={28} ring={false} />
                {gr.leaders.includes(m) && <span className="crown">★</span>}
              </div>
            ))}
            {!gr.members.length && <span className="dim small">no members right now</span>}
          </div>
          {gr.cut?.length > 0 && <div className="small dim">Cut at tryouts (eligible for a call-up): <Names ids={gr.cut.map((x: any) => x[0])} max={6} /></div>}
          {gr.upcoming?.length > 0 && (
            <div className="small dim" style={{ marginTop: 6 }}>Next: {gr.upcoming.slice(0, 2).map((u: any) => `${u.name} (${u.date})`).join(" · ")}</div>
          )}
        </Panel>
      ))}
    </div>
  );
}

function Gaps({ data, onPair }: any) {
  if (!data) return <Loading />;
  return (
    <Panel title="Where two people disagree about their relationship"
      sub="Each side keeps its own feelings and its own belief about the other. These pairs differ the most.">
      <table className="mini">
        <thead><tr><th>A</th><th>A's view</th><th>affection</th><th>B</th><th>B's view</th><th>affection</th><th>gap</th><th>A thinks B feels</th><th>B thinks A feels</th></tr></thead>
        <tbody>
          {data.asymmetric.map((x: any) => (
            <tr key={x.a + x.b} className="click" onClick={() => onPair(x.a, x.b)}>
              <td><Name id={x.a} /></td><td><Tag>{x.a_label}</Tag></td><td className="num">{fmt(x.ab)}</td>
              <td><Name id={x.b} /></td><td><Tag>{x.b_label}</Tag></td><td className="num">{fmt(x.ba)}</td>
              <td className="num"><b>{fmt(x.gap)}</b></td>
              <td className="num">{fmt(x.a_perceived)}</td><td className="num">{fmt(x.b_perceived)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!data.asymmetric.length && <Empty>No lopsided relationships yet.</Empty>}
    </Panel>
  );
}

function Households({ g }: any) {
  if (!g) return <Loading />;
  const hs = g.households.filter((h: any) => h.members.length);
  return (
    <div className="grid g4">
      {hs.map((h: any) => (
        <Panel key={h.id} title={h.name} sub={`${h.style_label} · ${h.income} income`}>
          <div className="small muted">Guardians: {h.guardians.join(", ")}</div>
          {h.pet && <div className="small muted">Pet: {h.pet.name} the {h.pet.species}</div>}
          <div className="row" style={{ marginTop: 8 }}>{h.members.map((m: string) => <span key={m} className="row" style={{ gap: 4 }}><Avatar id={m} size={24} ring={false} /><Name id={m} /></span>)}</div>
        </Panel>
      ))}
    </div>
  );
}
