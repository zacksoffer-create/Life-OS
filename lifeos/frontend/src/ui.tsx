// Shared UI kit: panels, meters, avatars, names, events, charts, term bars.
import React, { useMemo, useState } from "react";
import { EventLite } from "./api";
import { go, useStore } from "./store";

export const cx = (...xs: any[]) => xs.filter(Boolean).join(" ");
export const fmt = (x: any, d = 0) => (typeof x === "number" ? x.toFixed(d) : x ?? "-");
export const signed = (x: number, d = 1) => (x > 0 ? "+" : "") + x.toFixed(d);
export const pretty = (s: string) => (s || "").replace(/_/g, " ").replace(/\./g, " · ");

// ---------- icons (inline, no dependency) ----------
const P: Record<string, string> = {
  overview: "M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z",
  people: "M16 11c1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3 1.34 3 3 3zM8 11c1.66 0 3-1.34 3-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5C15 14.17 10.33 13 8 13zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z",
  web: "M12 2a3 3 0 0 0-1 5.83V10H7.83A3 3 0 1 0 6 12.17V14a3 3 0 1 0 2 0v-2h8v2a3 3 0 1 0 2 0v-1.83A3 3 0 1 0 16.17 10H13V7.83A3 3 0 0 0 12 2z",
  play: "M8 5v14l11-7z",
  history: "M13 3a9 9 0 0 0-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42A8.95 8.95 0 0 0 13 21a9 9 0 0 0 0-18zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z",
  flask: "M7 2v2h1v6.6L3.3 18.4A2.3 2.3 0 0 0 5.3 22h13.4a2.3 2.3 0 0 0 2-3.6L16 10.6V4h1V2H7zm3 2h4v7.2l2.6 4.8H7.4L10 11.2V4z",
  sliders: "M3 17v2h6v-2H3zM3 5v2h10V5H3zm10 16v-2h8v-2h-8v-2h-2v6h2zM7 9v2H3v2h4v2h2V9H7zm14 4v-2H11v2h10zm-6-4h2V7h4V5h-4V3h-2v6z",
  book: "M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM9 4h2v5l-1-.75L9 9V4zm9 16H6V4h1v9l3-2.25L13 13V4h5v16z",
  save: "M17 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V7l-4-4zm-5 16a3 3 0 1 1 0-6 3 3 0 0 1 0 6zm3-10H5V5h10v4z",
  pause: "M6 19h4V5H6v14zm8-14v14h4V5h-4z",
  step: "M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z",
  search: "M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z",
  spark: "M7 2v11h3v9l7-12h-4l4-8z",
  heart: "M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z",
  info: "M11 7h2v2h-2zm0 4h2v6h-2zm1-9C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z",
  close: "M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z",
  plus: "M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z",
  link: "M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z",
};
export function Icon({ name, size = 18, className }: { name: string; size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={cx("icon", className)} aria-hidden>
      <path d={P[name] || P.info} fill="currentColor" />
    </svg>
  );
}

// ---------- layout ----------
export function Panel({ title, sub, actions, children, className, pad = true }: any) {
  return (
    <section className={cx("panel", className)}>
      {(title || actions) && (
        <header className="panel-h">
          <div>
            {title && <h3>{title}</h3>}
            {sub && <div className="sub">{sub}</div>}
          </div>
          {actions && <div className="panel-actions">{actions}</div>}
        </header>
      )}
      <div className={pad ? "panel-b" : ""}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, sub, tone, onClick }: any) {
  return (
    <div className={cx("stat", tone && `tone-${tone}`, onClick && "clickable")} onClick={onClick}>
      <div className="stat-v">{value}</div>
      <div className="stat-l">{label}</div>
      {sub && <div className="stat-s">{sub}</div>}
    </div>
  );
}

export function Tabs({ tabs, active, onChange }: { tabs: [string, string][]; active: string; onChange: (k: string) => void }) {
  return (
    <div className="tabs">
      {tabs.map(([k, l]) => (
        <button key={k} className={cx("tab", k === active && "on")} onClick={() => onChange(k)}>
          {l}
        </button>
      ))}
    </div>
  );
}

export function Tag({ children, tone, title }: any) {
  return (
    <span className={cx("tag", tone && `tag-${tone}`)} title={title}>
      {children}
    </span>
  );
}

export function Empty({ children }: any) {
  return <div className="empty">{children}</div>;
}

export function Loading({ what = "Loading" }: { what?: string }) {
  return <div className="loading">{what}...</div>;
}

export function ErrorBox({ error }: { error: any }) {
  if (!error) return null;
  return <div className="errorbox">{String(error)}</div>;
}

export function Modal({ title, onClose, children, wide }: any) {
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className={cx("modal", wide && "wide")} onClick={(e) => e.stopPropagation()}>
        <header>
          <h3>{title}</h3>
          <button className="ghost icon-btn" onClick={onClose} aria-label="Close">
            <Icon name="close" />
          </button>
        </header>
        <div className="modal-b">{children}</div>
      </div>
    </div>
  );
}

// ---------- meters ----------
export function Meter({ value, max = 100, min = 0, color, label, right, invert, height = 6 }: any) {
  const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
  const c = color || (invert ? (value > 66 ? "var(--bad)" : value > 40 ? "var(--warm)" : "var(--good)") : "var(--accent)");
  return (
    <div className="meter-row">
      {label && <span className="meter-l">{label}</span>}
      <div className="meter" style={{ height }}>
        <div className="meter-f" style={{ width: pct + "%", background: c }} />
      </div>
      {right !== undefined && <span className="meter-r">{right}</span>}
    </div>
  );
}

// Signed bar for values in [-100, 100]
export function Signed({ value, max = 100, label, right }: any) {
  const v = Math.max(-max, Math.min(max, value || 0));
  const w = (Math.abs(v) / max) * 50;
  return (
    <div className="meter-row">
      {label && <span className="meter-l">{label}</span>}
      <div className="signed">
        <div className="mid" />
        <div className={cx("signed-f", v < 0 ? "neg" : "pos")} style={v < 0 ? { right: "50%", width: w + "%" } : { left: "50%", width: w + "%" }} />
      </div>
      {right !== undefined && <span className="meter-r">{right}</span>}
    </div>
  );
}

// ---------- people ----------
export function initials(name: string) {
  const p = (name || "?").replace(/^(Coach|Dr\.|Mr\.|Ms\.)\s+/, "").split(" ");
  return ((p[0] || "?")[0] + (p[1] ? p[1][0] : "")).toUpperCase();
}

export function moodColor(m: number) {
  return m >= 66 ? "var(--good)" : m >= 40 ? "var(--warm)" : "var(--bad)";
}

export function Avatar({ id, size = 34, ring = true, onClick }: { id: string; size?: number; ring?: boolean; onClick?: any }) {
  const { chars } = useStore();
  const c = chars[id];
  const name = c ? c.name : id;
  return (
    <div
      className="avatar"
      title={c ? `${c.name} · mood ${Math.round(c.mood)}` : id}
      onClick={onClick || (() => go(`characters/${id}`))}
      style={{
        width: size,
        height: size,
        fontSize: size * 0.38,
        background: c ? `linear-gradient(135deg, ${c.color}, ${c.color}88)` : "#444",
        boxShadow: ring && c ? `0 0 0 2px var(--bg), 0 0 0 ${size > 40 ? 4 : 3}px ${moodColor(c.mood)}` : undefined,
        opacity: c && c.status !== "active" ? 0.5 : 1,
      }}
    >
      {initials(name)}
    </div>
  );
}

export function Name({ id, full, plain }: { id: string; full?: boolean; plain?: boolean }) {
  const { chars } = useStore();
  const c = chars[id];
  if (!c) return <span className="name">{id}</span>;
  return (
    <a
      className={cx("name", plain && "plain")}
      href={`#/characters/${id}`}
      onClick={(e) => e.stopPropagation()}
      title={`${c.name}${c.grade ? ` · grade ${c.grade}` : ` · ${c.role_label || c.role}`}`}
    >
      {!plain && <span className="dot" style={{ background: c.color }} />}
      {full ? c.name : c.short}
    </a>
  );
}

export function Names({ ids, max = 6 }: { ids: string[]; max?: number }) {
  const shown = ids.slice(0, max);
  return (
    <span>
      {shown.map((id, i) => (
        <React.Fragment key={id}>
          {i > 0 && (i === shown.length - 1 && ids.length <= max ? " and " : ", ")}
          <Name id={id} />
        </React.Fragment>
      ))}
      {ids.length > max && ` +${ids.length - max}`}
    </span>
  );
}

// ---------- events ----------
const TYPE_META: Record<string, [string, string]> = {
  interact: ["chat", "social"], lunch_table: ["lunch", "social"], exclusion: ["excluded", "bad"], milestone: ["milestone", "accent"],
  ask_out: ["romance", "romance"], ask_to_dance: ["romance", "romance"], break_up: ["breakup", "bad"], confront: ["conflict", "bad"],
  apologize: ["make-up", "good"], gossip: ["gossip", "warn"], spread_rumor: ["rumor", "bad"], rumor_reached: ["rumor", "warn"],
  tease: ["mockery", "bad"], prank: ["prank", "warn"], sneak_out: ["sneaking", "warn"], tryout: ["tryout", "accent"],
  audition: ["audition", "accent"], game: ["game", "info"], show: ["show", "info"], practice: ["practice", "dim"], dance: ["dance", "romance"],
  party: ["party", "warn"], election: ["election", "accent"], exam: ["exam", "info"], household: ["family", "info"], job: ["job", "dim"],
  sign_up: ["sign-up", "dim"], quit_group: ["quit", "warn"], goal: ["goal", "accent"], clique: ["clique", "accent"],
  graduation: ["graduation", "good"], new_year: ["new year", "good"], lab: ["lab", "warn"], mentor: ["mentor", "good"],
  birthday: ["birthday", "good"], season_end: ["season", "dim"], throw_party: ["party", "warn"], classes: ["school", "dim"],
};
export function typeMeta(t: string): [string, string] {
  const k = t.split(".")[0];
  return TYPE_META[k] || [k.replace(/_/g, " "), "dim"];
}

export function ImportanceDot({ v }: { v: number }) {
  const c = v >= 40 ? "var(--bad)" : v >= 25 ? "var(--warm)" : v >= 12 ? "var(--accent)" : "var(--dim)";
  return <span className="imp" style={{ background: c }} title={`importance ${v}`} />;
}

export function EventRow({ ev, compact, showDate = true }: { ev: EventLite; compact?: boolean; showDate?: boolean }) {
  const [label, tone] = typeMeta(ev.type);
  const people = Array.from(new Set([...(ev.actors || []), ...(ev.targets || [])])).slice(0, compact ? 2 : 4);
  return (
    <div className={cx("ev", compact && "compact")} onClick={() => go(`history/event/${ev.id}`)}>
      <div className="ev-av">
        {people.map((p) => (
          <Avatar key={p} id={p} size={compact ? 22 : 26} ring={false} onClick={(e: any) => { e.stopPropagation(); go(`characters/${p}`); }} />
        ))}
      </div>
      <div className="ev-body">
        <div className="ev-text">{ev.text}</div>
        <div className="ev-meta">
          <Tag tone={tone}>{label}</Tag>
          {showDate && <span>{ev.date}</span>}
          {ev.trace && <span className="hint">decision trace</span>}
          {ev.has_calc && <span className="hint">calculation</span>}
          {ev.n_changes > 0 && <span className="hint">{ev.n_changes} changes</span>}
        </div>
      </div>
      <ImportanceDot v={ev.importance} />
    </div>
  );
}

// ---------- charts ----------
export function LineChart({ series, height = 160, xLabels, yLabel, fmtY }: {
  series: { name: string; color: string; values: number[]; dash?: boolean }[];
  height?: number;
  xLabels?: string[];
  yLabel?: string;
  fmtY?: (v: number) => string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 600;
  const H = height;
  const pad = { l: 38, r: 10, t: 10, b: 22 };
  const all = series.flatMap((s) => s.values).filter((v) => Number.isFinite(v));
  if (!all.length) return <Empty>No data yet. Advance time to build a history.</Empty>;
  let lo = Math.min(...all);
  let hi = Math.max(...all);
  if (hi - lo < 1e-9) {
    hi += 1;
    lo -= 1;
  }
  const n = Math.max(...series.map((s) => s.values.length));
  const x = (i: number) => pad.l + (n <= 1 ? 0 : (i / (n - 1)) * (W - pad.l - pad.r));
  const y = (v: number) => pad.t + (1 - (v - lo) / (hi - lo)) * (H - pad.t - pad.b);
  const ticks = [lo, (lo + hi) / 2, hi];
  const f = fmtY || ((v: number) => (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1)));
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height }}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          const px = ((e.clientX - r.left) / r.width) * W;
          const i = Math.round(((px - pad.l) / (W - pad.l - pad.r)) * (n - 1));
          setHover(Math.max(0, Math.min(n - 1, i)));
        }}>
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} className="grid" />
            <text x={pad.l - 6} y={y(t) + 3} className="axis" textAnchor="end">{f(t)}</text>
          </g>
        ))}
        {series.map((s) => (
          <polyline key={s.name} fill="none" stroke={s.color} strokeWidth={2} strokeDasharray={s.dash ? "5 4" : undefined}
            vectorEffect="non-scaling-stroke"
            points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")} />
        ))}
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={H - pad.b} className="cursor" />}
        {xLabels && xLabels.length > 1 && (
          <>
            <text x={pad.l} y={H - 6} className="axis">{xLabels[0]}</text>
            <text x={W - pad.r} y={H - 6} className="axis" textAnchor="end">{xLabels[xLabels.length - 1]}</text>
          </>
        )}
      </svg>
      <div className="legend">
        {series.map((s) => (
          <span key={s.name}>
            <i style={{ background: s.color }} />
            {s.name}
            {hover !== null && s.values[hover] !== undefined && <b> {f(s.values[hover])}</b>}
          </span>
        ))}
        {hover !== null && xLabels && <span className="dim">{xLabels[hover]}</span>}
        {yLabel && <span className="dim">{yLabel}</span>}
      </div>
    </div>
  );
}

export function Spark({ values, color = "var(--accent)", height = 28 }: { values: number[]; color?: string; height?: number }) {
  if (!values || values.length < 2) return null;
  const lo = Math.min(...values);
  const hi = Math.max(...values) + 1e-9;
  const W = 100;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * W},${height - 2 - ((v - lo) / (hi - lo)) * (height - 4)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${height}`} preserveAspectRatio="none" style={{ width: "100%", height }}>
      <polyline fill="none" stroke={color} strokeWidth={1.6} vectorEffect="non-scaling-stroke" points={pts} />
    </svg>
  );
}

// Horizontal bars for decision terms: each term's signed contribution to utility.
export function TermBars({ terms, total }: { terms: [string, number, string?][]; total?: number }) {
  const max = Math.max(1, ...terms.map((t) => Math.abs(t[1])));
  const sorted = useMemo(() => [...terms].sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])), [terms]);
  return (
    <div className="terms">
      {sorted.map(([label, v, note], i) => (
        <div className="term" key={i} title={note || ""}>
          <span className="term-l">{label}</span>
          <div className="term-bar">
            <div className="mid" />
            <div className={cx("term-f", v < 0 ? "neg" : "pos")}
              style={v < 0 ? { right: "50%", width: (Math.abs(v) / max) * 50 + "%" } : { left: "50%", width: (Math.abs(v) / max) * 50 + "%" }} />
          </div>
          <span className={cx("term-v", v < 0 ? "neg" : "pos")}>{signed(v)}</span>
          {note && <span className="term-n">{note}</span>}
        </div>
      ))}
      {total !== undefined && (
        <div className="term total">
          <span className="term-l">= utility</span>
          <div className="term-bar" />
          <span className="term-v">{total.toFixed(1)}</span>
        </div>
      )}
    </div>
  );
}

export function Calc({ calc }: { calc: any[] }) {
  if (!calc || !calc.length) return null;
  return (
    <div className="calcs">
      {calc.map((c, i) => (
        <div className="calc" key={i}>
          <div className="calc-h">
            <b>{c.step}</b>
            {c.outcome !== undefined && <Tag tone="accent">{String(c.outcome)}</Tag>}
          </div>
          {c.terms && (
            <table className="mini">
              <tbody>
                {c.terms.map((t: any, j: number) => (
                  <tr key={j}>
                    <td>{t[0]}</td>
                    <td className="num">{typeof t[1] === "number" ? t[1].toFixed(3) : String(t[1])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="calc-f">
            {c.total !== undefined && <span>total <b>{typeof c.total === "number" ? c.total.toFixed(3) : c.total}</b></span>}
            {c.p !== undefined && c.p !== null && <span>probability <b>{(c.p * 100).toFixed(1)}%</b></span>}
            {c.p_caught !== undefined && <span>P(caught) <b>{(c.p_caught * 100).toFixed(1)}%</b></span>}
            {c.p_grounded !== undefined && c.p_grounded !== null && <span>P(grounded) <b>{(c.p_grounded * 100).toFixed(1)}%</b></span>}
            {c.roll !== undefined && <span>random roll <b>{c.roll}</b></span>}
          </div>
          {c.rule && <div className="calc-rule">{c.rule}</div>}
          {c.rows && <CalcRows rows={c.rows} weights={c.weights} />}
          {c.votes && (
            <div className="votes">
              {Object.entries(c.votes).sort((a: any, b: any) => b[1] - a[1]).map(([k, v]: any) => (
                <span key={k}><Name id={k} /> {v}</span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function CalcRows({ rows, weights }: any) {
  return (
    <>
      {weights && (
        <div className="calc-rule">
          weights: {Object.entries(weights).filter(([, v]) => v !== null).map(([k, v]: any) => `${k} ${typeof v === "number" ? v.toFixed(2) : v}`).join(" · ")}
        </div>
      )}
      <table className="mini">
        <thead>
          <tr><th>candidate</th><th>performance</th><th>effort</th><th>favor</th><th>seniority</th><th>score</th><th></th></tr>
        </thead>
        <tbody>
          {rows.map((r: any) => (
            <tr key={r.char}>
              <td><Name id={r.char} /></td>
              <td className="num">{r.performance}</td>
              <td className="num">{r.effort}</td>
              <td className="num">{r.favor}</td>
              <td className="num">{r.seniority}</td>
              <td className="num"><b>{r.score}</b></td>
              <td>{r.made ? <Tag tone="good">made it</Tag> : <Tag tone="bad">cut</Tag>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

export function Changes({ changes }: { changes: any[] }) {
  const { chars } = useStore();
  if (!changes || !changes.length) return <Empty>No recorded state changes.</Empty>;
  const ent = (e: string) => {
    if (e.includes(">")) {
      const [a, b] = e.split(">");
      return <span><Name id={a} /> <span className="dim">about</span> <Name id={b} /></span>;
    }
    if (e.includes("|")) {
      const [a, b] = e.split("|");
      return <span><Name id={a} /> &amp; <Name id={b} /></span>;
    }
    return chars[e] ? <Name id={e} /> : <span>{e}</span>;
  };
  return (
    <table className="mini changes">
      <thead>
        <tr><th>who</th><th>what</th><th>before</th><th>after</th><th>change</th><th>why</th></tr>
      </thead>
      <tbody>
        {changes.map((c, i) => {
          const num = typeof c[2] === "number" && typeof c[3] === "number";
          const d = num ? c[3] - c[2] : null;
          return (
            <tr key={i}>
              <td>{ent(c[0])}</td>
              <td>{pretty(c[1])}</td>
              <td className="num">{c[2] === null ? "-" : String(c[2])}</td>
              <td className="num">{c[3] === null ? "-" : String(c[3])}</td>
              <td className={cx("num", d !== null && (d > 0 ? "pos" : "neg"))}>{d !== null ? signed(d) : ""}</td>
              <td className="dim">{c[4]}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function Pager({ total, offset, limit, onChange }: any) {
  if (total <= limit) return null;
  return (
    <div className="pager">
      <button disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>Newer</button>
      <span>{offset + 1}-{Math.min(total, offset + limit)} of {total}</span>
      <button disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>Older</button>
    </div>
  );
}

export function Slider({ value, min, max, step, onChange, disabled }: any) {
  return (
    <input type="range" className="slider" min={min} max={max} step={step} value={value} disabled={disabled}
      onChange={(e) => onChange(parseFloat(e.target.value))} />
  );
}
