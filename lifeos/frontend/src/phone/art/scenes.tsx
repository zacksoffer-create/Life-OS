// Scene illustrations: layered flat-vector backgrounds for every place in the story.
// Composition box is 390x480 (preserveAspectRatio slice), so it fills any phone-width card.
// Season changes foliage, snow and sky; the phase of the day tints everything and turns lights on.
import React, { useMemo } from "react";
import { renderToStaticMarkup } from "react-dom/server";

export type SceneProps = { art: string; season?: string; phase?: string; className?: string; children?: React.ReactNode };
type Time = "morning" | "day" | "golden" | "dusk" | "night";
type Ctx = { t: Time; s: string; id: string };

export function timeOf(phase?: string): Time {
  switch (phase) {
    case "dawn": return "morning";
    case "after_school": return "golden";
    case "evening": return "dusk";
    case "night": return "night";
    default: return "day";
  }
}

const SKY: Record<Time, [string, string]> = {
  morning: ["#ffc9a0", "#fff0d8"],
  day: ["#7ec8f6", "#d9f1ff"],
  golden: ["#ffa65c", "#ffe1a1"],
  dusk: ["#5d4c9e", "#f49a7a"],
  night: ["#0d1738", "#2d3c74"],
};
const WINTER_DAY: [string, string] = ["#a9c9e3", "#eef5fb"];
const TINT: Record<Time, [string, number, number]> = {
  // color, outdoor opacity, indoor opacity
  morning: ["#ff9f5a", 0.1, 0.06],
  day: ["#ffffff", 0, 0],
  golden: ["#ff8a2a", 0.16, 0.08],
  dusk: ["#3f2a78", 0.32, 0.16],
  night: ["#060c2e", 0.55, 0.26],
};
const lit = (t: Time) => t === "dusk" || t === "night";
const FOLIAGE: Record<string, [string, string, string]> = {
  spring: ["#86cf6c", "#5fae55", "#f6b8cf"],
  summer: ["#4aa55a", "#327f43", "#62b768"],
  fall: ["#e8902f", "#c9552b", "#f0bf3f"],
  winter: ["#b9c3cb", "#8f9aa4", "#ffffff"],
};
const GRASS: Record<string, [string, string]> = {
  spring: ["#8fd16f", "#76bd5c"], summer: ["#6fbd59", "#5aa64a"], fall: ["#a8b65a", "#8f9d48"], winter: ["#e9f0f5", "#d6e0e8"],
};
const OUT = "rgba(38,30,46,0.55)";

function Sky({ c, y = 0, h = 480, sun = true }: { c: Ctx; y?: number; h?: number; sun?: boolean }) {
  const [a, b] = c.s === "winter" && (c.t === "day" || c.t === "morning") ? WINTER_DAY : SKY[c.t];
  const gid = `sky${c.id}`;
  return (
    <g>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={a} />
          <stop offset="1" stopColor={b} />
        </linearGradient>
      </defs>
      <rect x={0} y={y} width={390} height={h} fill={`url(#${gid})`} />
      {sun && c.t === "night" && (
        <g>
          {[[40, 40], [90, 80], [150, 30], [220, 70], [300, 36], [350, 90], [260, 120], [120, 130], [30, 150], [330, 160]].map(([x, yy], i) => (
            <circle key={i} cx={x} cy={y + yy} r={i % 3 === 0 ? 1.8 : 1.1} fill="#fff" opacity={0.85} />
          ))}
          <circle cx={318} cy={y + 64} r={20} fill="#fdf3cf" />
          <circle cx={327} cy={y + 58} r={18} fill={a} />
        </g>
      )}
      {sun && c.t !== "night" && (
        <g>
          <circle cx={c.t === "morning" ? 70 : c.t === "golden" ? 320 : c.t === "dusk" ? 300 : 300} cy={y + (c.t === "day" ? 60 : c.t === "dusk" ? 150 : 110)} r={c.t === "day" ? 26 : 32}
            fill={c.t === "day" ? "#fff6c8" : c.t === "dusk" ? "#ffcf8a" : "#ffe7a6"} opacity={0.95} />
          <circle cx={c.t === "morning" ? 70 : 300} cy={y + (c.t === "day" ? 60 : 110)} r={c.t === "day" ? 44 : 56} fill="#fff6c8" opacity={0.18} />
        </g>
      )}
      {sun && c.t !== "night" && (
        <g fill="#fff" opacity={c.t === "dusk" ? 0.35 : 0.8}>
          <Cloud x={60} y={y + 60} s={1} />
          <Cloud x={230} y={y + 110} s={0.8} />
        </g>
      )}
    </g>
  );
}

function Cloud({ x, y, s }: { x: number; y: number; s: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <ellipse cx={0} cy={0} rx={30} ry={11} />
      <ellipse cx={-14} cy={-6} rx={14} ry={11} />
      <ellipse cx={8} cy={-10} rx={17} ry={14} />
    </g>
  );
}

function Tree({ x, y, s = 1, c, round = true }: { x: number; y: number; s?: number; c: Ctx; round?: boolean }) {
  const [a, b, d] = FOLIAGE[c.s] || FOLIAGE.summer;
  if (c.s === "winter") {
    return (
      <g transform={`translate(${x} ${y}) scale(${s})`} stroke="#6e5a4c" strokeLinecap="round" fill="none">
        <path d="M0 0 L0 -70" strokeWidth={8} />
        <path d="M0 -40 L-22 -66 M0 -52 L18 -80 M0 -64 L-8 -92 M-12 -54 L-28 -60 M10 -68 L28 -70" strokeWidth={4} />
        <path d="M-22 -66 l-6 -8 M18 -80 l6 -8 M-8 -92 l2 -9" strokeWidth={2.5} />
        <path d="M-26 -62 q4 -3 8 -1 M14 -78 q4 -3 8 0" stroke="#fff" strokeWidth={3} />
      </g>
    );
  }
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <path d="M-5 0 L-4 -46 L4 -46 L5 0 Z" fill="#7a5a43" stroke={OUT} strokeWidth={1.5} />
      {round ? (
        <g stroke={OUT} strokeWidth={1.5}>
          <circle cx={-20} cy={-58} r={24} fill={b} />
          <circle cx={20} cy={-60} r={24} fill={b} />
          <circle cx={0} cy={-80} r={30} fill={a} />
          <circle cx={-12} cy={-70} r={18} fill={a} stroke="none" />
          <circle cx={14} cy={-72} r={16} fill={a} stroke="none" />
          {c.s === "spring" && [[-14, -86], [8, -94], [22, -70], [-24, -60], [4, -66]].map(([px, py], i) => <circle key={i} cx={px} cy={py} r={3.5} fill={d} stroke="none" />)}
          {c.s === "fall" && [[-14, -86], [12, -90], [24, -66], [-22, -58]].map(([px, py], i) => <circle key={i} cx={px} cy={py} r={6} fill={d} stroke="none" />)}
        </g>
      ) : (
        <path d="M0 -120 L28 -40 L-28 -40 Z" fill={c.s === "fall" ? "#3f7a4a" : b} stroke={OUT} strokeWidth={1.5} />
      )}
    </g>
  );
}

function Window({ x, y, w, h, c, frame = "#f4efe6", panes = 2, outside }: { x: number; y: number; w: number; h: number; c: Ctx; frame?: string; panes?: number; outside?: React.ReactNode }) {
  const [a, b] = c.s === "winter" && (c.t === "day" || c.t === "morning") ? WINTER_DAY : SKY[c.t];
  const gid = `win${c.id}${x}${y}`;
  const cid = `winc${c.id}${x}${y}`;
  return (
    <g>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={a} /><stop offset="1" stopColor={b} /></linearGradient>
        <clipPath id={cid}><rect x={x} y={y} width={w} height={h} /></clipPath>
      </defs>
      <rect x={x} y={y} width={w} height={h} fill={`url(#${gid})`} />
      <g clipPath={`url(#${cid})`}>
        {c.t === "night" && <circle cx={x + w * 0.75} cy={y + h * 0.25} r={Math.min(w, h) * 0.08} fill="#fdf3cf" />}
        {outside}
        <path d={`M${x} ${y + h} L${x + w * 0.35} ${y} L${x + w * 0.55} ${y} L${x + w * 0.2} ${y + h} Z`} fill="#fff" opacity={c.t === "night" ? 0.05 : 0.22} />
      </g>
      <rect x={x} y={y} width={w} height={h} fill="none" stroke={frame} strokeWidth={8} />
      {Array.from({ length: panes - 1 }).map((_, i) => (
        <path key={i} d={`M${x + (w * (i + 1)) / panes} ${y} V${y + h}`} stroke={frame} strokeWidth={6} />
      ))}
      <path d={`M${x} ${y + h * 0.5} H${x + w}`} stroke={frame} strokeWidth={5} />
      <rect x={x - 4} y={y - 4} width={w + 8} height={h + 8} fill="none" stroke={OUT} strokeWidth={1.5} />
    </g>
  );
}

function OutsideTrees({ x, y, w, h, c }: { x: number; y: number; w: number; h: number; c: Ctx }) {
  const [, g2] = GRASS[c.s] || GRASS.summer;
  return (
    <g>
      <rect x={x} y={y + h * 0.72} width={w} height={h * 0.3} fill={g2} />
      <Tree x={x + w * 0.25} y={y + h * 0.82} s={h / 170} c={c} />
      <Tree x={x + w * 0.78} y={y + h * 0.86} s={h / 200} c={c} />
    </g>
  );
}

function Glow({ x, y, r, color = "#ffd27a", o = 0.55 }: { x: number; y: number; r: number; color?: string; o?: number }) {
  const gid = `g${Math.round(x)}${Math.round(y)}${r}`;
  return (
    <g>
      <defs>
        <radialGradient id={gid}><stop offset="0" stopColor={color} stopOpacity={o} /><stop offset="1" stopColor={color} stopOpacity={0} /></radialGradient>
      </defs>
      <circle cx={x} cy={y} r={r} fill={`url(#${gid})`} />
    </g>
  );
}

function Paw({ x, y, s = 1, fill = "#fff" }: { x: number; y: number; s?: number; fill?: string }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`} fill={fill}>
      <ellipse cx={0} cy={6} rx={9} ry={7.5} />
      <ellipse cx={-10} cy={-5} rx={4} ry={5} />
      <ellipse cx={-3.5} cy={-10} rx={4} ry={5} />
      <ellipse cx={3.5} cy={-10} rx={4} ry={5} />
      <ellipse cx={10} cy={-5} rx={4} ry={5} />
    </g>
  );
}

function Pendant({ x, y, len = 40, c, color = "#e98e5e" }: { x: number; y: number; len?: number; c: Ctx; color?: string }) {
  return (
    <g>
      <path d={`M${x} ${y} V${y + len}`} stroke="#4b3c3a" strokeWidth={2} />
      <path d={`M${x - 16} ${y + len + 14} Q${x} ${y + len - 6} ${x + 16} ${y + len + 14} Z`} fill={color} stroke={OUT} strokeWidth={1.5} />
      <ellipse cx={x} cy={y + len + 14} rx={8} ry={2.5} fill={lit(c.t) ? "#fff4c4" : "#f4e6c6"} />
    </g>
  );
}

function floorPlanks(y0: number, y1: number, color: string, line: string, n = 9) {
  const out: React.ReactNode[] = [<rect key="f" x={0} y={y0} width={390} height={y1 - y0} fill={color} />];
  for (let i = 1; i <= n; i++) {
    const t = i / n;
    const y = y0 + (y1 - y0) * t * t;
    out.push(<path key={i} d={`M0 ${y} H390`} stroke={line} strokeWidth={1.2} opacity={0.6} />);
  }
  return out;
}

// --- scenes ----------------------------------------------------------------------------------

type S = (c: Ctx) => { base: React.ReactNode; lights?: React.ReactNode; indoor?: boolean };

const homeMorning: S = (c) => ({
  indoor: true,
  base: (
    <g>
      <rect width={390} height={330} fill="#f5e4c8" />
      <rect y={300} width={390} height={30} fill="#ead3b0" />
      {/* upper cabinets */}
      <g fill="#a3bf9f" stroke={OUT} strokeWidth={1.5}>
        <rect x={10} y={38} width={100} height={92} rx={4} />
        <rect x={280} y={38} width={100} height={92} rx={4} />
      </g>
      <g stroke="#7f9e7b" strokeWidth={2}><path d="M60 42 V126 M330 42 V126" /></g>
      <g fill="#e7d9b8"><circle cx={54} cy={84} r={3} /><circle cx={66} cy={84} r={3} /><circle cx={324} cy={84} r={3} /><circle cx={336} cy={84} r={3} /></g>
      <Window x={135} y={66} w={120} h={130} c={c} outside={<OutsideTrees x={135} y={66} w={120} h={130} c={c} />} />
      <path d="M127 60 H263 L258 80 Q195 92 132 80 Z" fill="#e8846a" stroke={OUT} strokeWidth={1.5} />
      {/* counter & lower cabinets */}
      <rect x={0} y={228} width={390} height={16} fill="#efe8dc" stroke={OUT} strokeWidth={1.5} />
      <rect x={0} y={244} width={390} height={86} fill="#86a382" stroke={OUT} strokeWidth={1.5} />
      <g stroke="#6e8a6b" strokeWidth={2}>{[78, 156, 234, 312].map((x) => <path key={x} d={`M${x} 248 V326`} />)}</g>
      <g fill="#e7d9b8">{[60, 96, 138, 174, 216, 252, 294, 330].map((x) => <rect key={x} x={x} y={262} width={10} height={3} rx={1.5} />)}</g>
      <path d="M180 228 Q195 196 210 228" fill="none" stroke="#9aa3ad" strokeWidth={5} />
      <rect x={170} y={224} width={50} height={6} rx={3} fill="#c9d0d6" />
      {/* plant & toaster */}
      <rect x={300} y={204} width={26} height={24} rx={4} fill="#d36f56" stroke={OUT} strokeWidth={1.5} />
      <path d="M313 204 q-10 -18 -2 -26 q4 10 2 26 q10 -16 16 -16 q-4 12 -16 16" fill="#5aa65a" />
      <rect x={60} y={200} width={48} height={28} rx={8} fill="#cfd6dc" stroke={OUT} strokeWidth={1.5} />
      <path d="M70 200 v-6 M84 200 v-6" stroke="#8b8f94" strokeWidth={3} />
      <Pendant x={195} y={0} len={20} c={c} />
      {/* floor */}
      {floorPlanks(330, 480, "#c99a68", "#a97b4c")}
      {/* table */}
      <path d="M20 408 L370 408 L390 480 L0 480 Z" fill="#e1b98a" stroke={OUT} strokeWidth={1.5} />
      <path d="M20 408 L370 408" stroke="#f0d2a8" strokeWidth={4} />
      <ellipse cx={130} cy={432} rx={44} ry={13} fill="#fff" stroke={OUT} strokeWidth={1.5} />
      <path d="M86 430 Q130 470 174 430" fill="#7fb1d9" stroke={OUT} strokeWidth={1.5} />
      <g fill="#f3c25e">{[[110, 428], [124, 424], [138, 430], [150, 425], [118, 433], [144, 435]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r={4} />)}</g>
      <rect x={232} y={404} width={34} height={42} rx={5} fill="#f6f1e6" stroke={OUT} strokeWidth={1.5} />
      <path d="M266 414 q14 2 12 14 q-2 10 -12 10" fill="none" stroke="#f6f1e6" strokeWidth={5} />
      <path d="M244 398 q-6 -10 2 -18 M256 398 q-6 -12 2 -20" fill="none" stroke="#fff" strokeWidth={3} strokeLinecap="round" opacity={0.7} />
      <rect x={290} y={396} width={26} height={50} rx={4} fill="#ffb347" opacity={0.85} stroke={OUT} strokeWidth={1.5} />
      {(c.t === "morning" || c.t === "day" || c.t === "golden") && (
        <path d="M135 196 L255 196 L330 420 L60 420 Z" fill="#fff3c4" opacity={0.18} />
      )}
    </g>
  ),
  lights: lit(c.t) ? <Glow x={195} y={40} r={120} /> : null,
});

const classroom: S = (c) => ({
  indoor: true,
  base: (
    <g>
      <rect width={390} height={300} fill="#dfe8ea" />
      <rect y={288} width={390} height={12} fill="#b9c8cc" />
      <rect x={24} y={62} width={248} height={128} rx={4} fill="#b58a5c" />
      <rect x={32} y={70} width={232} height={112} fill="#2f5e4b" />
      <g fill="none" stroke="#f3f1e6" strokeWidth={2.4} strokeLinecap="round" opacity={0.85}>
        <path d="M50 96 q10 -12 20 0 t20 0 t20 0" />
        <path d="M50 120 h60 M50 136 h44" />
        <circle cx={180} cy={112} r={22} />
        <path d="M158 112 h44 M180 90 v44" />
        <path d="M222 150 l20 -30 l14 18 l16 -28" />
        <path d="M60 160 l20 0 m-6 -6 l6 6 l-6 6" />
        <path d="M120 162 q16 -10 32 0" />
      </g>
      <rect x={32} y={182} width={232} height={6} fill="#a0784c" />
      <rect x={60} y={184} width={30} height={4} fill="#fff" />
      <circle cx={322} cy={66} r={20} fill="#fff" stroke="#3b3b3b" strokeWidth={3} />
      {[0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330].map((a) => (
        <path key={a} d={`M${322 + 15 * Math.cos((a * Math.PI) / 180)} ${66 + 15 * Math.sin((a * Math.PI) / 180)} L${322 + 17.5 * Math.cos((a * Math.PI) / 180)} ${66 + 17.5 * Math.sin((a * Math.PI) / 180)}`} stroke="#3b3b3b" strokeWidth={1.5} />
      ))}
      <path d="M322 66 L322 54 M322 66 L331 70" stroke="#3b3b3b" strokeWidth={2.5} strokeLinecap="round" />
      <Window x={296} y={110} w={84} h={150} c={c} panes={1} outside={<OutsideTrees x={296} y={110} w={84} h={150} c={c} />} />
      <g>{[["#f6c85f", 44, 210], ["#7cc2e8", 84, 214], ["#f28c8c", 124, 208], ["#a7d98b", 164, 212]].map(([col, x, y], i) => (
        <rect key={i} x={x as number} y={y as number} width={30} height={36} fill={col as string} transform={`rotate(${i % 2 ? 3 : -3} ${x} ${y})`} stroke={OUT} strokeWidth={1} />
      ))}</g>
      <rect x={0} y={300} width={390} height={180} fill="#c3ad92" />
      <g stroke="#ad9679" strokeWidth={1.2}>{[330, 366, 412, 470].map((y) => <path key={y} d={`M0 ${y} H390`} />)}</g>
      {/* desks: back row, middle, front */}
      {[[300, 0.55], [350, 0.75], [420, 1.0]].map(([y, s], row) => (
        <g key={row}>
          {[0, 1, 2].map((i) => {
            const cx = 195 + (i - 1) * 130 * (s as number);
            const w = 92 * (s as number), d = 26 * (s as number);
            return (
              <g key={i}>
                <rect x={cx - w * 0.28} y={(y as number) - d * 0.2} width={w * 0.56} height={d * 2.1} rx={6} fill="#3f7cc0" stroke={OUT} strokeWidth={1.5} />
                <path d={`M${cx - w / 2} ${y} L${cx + w / 2} ${y} L${cx + w / 2 + 6 * (s as number)} ${(y as number) + d} L${cx - w / 2 - 6 * (s as number)} ${(y as number) + d} Z`} fill="#dcbb8c" stroke={OUT} strokeWidth={1.5} />
                <path d={`M${cx - w / 2 + 4} ${(y as number) + d} v${d * 1.4} M${cx + w / 2 - 4} ${(y as number) + d} v${d * 1.4}`} stroke="#6b6b6b" strokeWidth={3 * (s as number)} />
                {row === 2 && i === 1 && <rect x={cx - 18} y={(y as number) + 4} width={30} height={16} rx={2} fill="#fff" transform={`rotate(-6 ${cx} ${y})`} />}
              </g>
            );
          })}
        </g>
      ))}
    </g>
  ),
  lights: lit(c.t) ? <Glow x={150} y={20} r={160} color="#fff1c2" o={0.4} /> : null,
});

const schoolHall: S = (c) => {
  const vx = 195, vy = 222;
  const lockers = (side: -1 | 1) => {
    const out: React.ReactNode[] = [];
    const xs = side === -1 ? [0, 40, 76, 106, 130, 148] : [390, 350, 314, 284, 260, 242];
    for (let i = 0; i < xs.length - 1; i++) {
      const xa = xs[i], xb = xs[i + 1];
      const ta = (Math.abs(xa - vx) / vx), tb = (Math.abs(xb - vx) / vx);
      const ya1 = vy - 182 * ta, ya2 = vy + 200 * ta;
      const yb1 = vy - 182 * tb, yb2 = vy + 200 * tb;
      out.push(<path key={i} d={`M${xa} ${ya1} L${xb} ${yb1} L${xb} ${yb2} L${xa} ${ya2} Z`} fill={i % 2 ? "#2f8150" : "#2a7548"} stroke="#1d5233" strokeWidth={1.5} />);
      const ym = (ya1 + ya2) / 2, ymb = (yb1 + yb2) / 2;
      out.push(<path key={`v${i}`} d={`M${xa + (xb - xa) * 0.25} ${ya1 + (yb1 - ya1) * 0.25 + 10} l${(xb - xa) * 0.5} ${(yb1 - ya1) * 0.5}`} stroke="#1d5233" strokeWidth={2} opacity={0.7} />);
      out.push(<path key={`h${i}`} d={`M${xa + (xb - xa) * (side === -1 ? 0.8 : 0.2)} ${ym} L${xa + (xb - xa) * (side === -1 ? 0.8 : 0.2)} ${ym + 14}`} stroke="#c9d6cc" strokeWidth={3} strokeLinecap="round" />);
      void ymb;
    }
    return out;
  };
  return {
    indoor: true,
    base: (
      <g>
        <rect width={390} height={480} fill="#eae8e1" />
        <path d={`M0 0 L390 0 L242 ${vy - 56} L148 ${vy - 56} Z`} fill="#f4f3ee" />
        {[60, 120, 160].map((y, i) => (
          <path key={i} d={`M${vx - 60 + i * 18} ${y * 0.6 + 6} L${vx + 60 - i * 18} ${y * 0.6 + 6} L${vx + 52 - i * 18} ${y * 0.6 + 16} L${vx - 52 + i * 18} ${y * 0.6 + 16} Z`} fill="#fffbe6" stroke="#d9d4c4" strokeWidth={1} />
        ))}
        <path d={`M0 480 L390 480 L242 ${vy + 60} L148 ${vy + 60} Z`} fill="#cfd8d4" />
        {[0.15, 0.35, 0.6, 0.9].map((t, i) => <path key={i} d={`M${148 - 148 * t} ${vy + 60 + 200 * t} H${242 + 148 * t}`} stroke="#b9c4bf" strokeWidth={1.2} />)}
        {[-120, -40, 40, 120].map((dx, i) => <path key={`d${i}`} d={`M${vx + dx * 0.2} ${vy + 60} L${vx + dx * 2.6} 480`} stroke="#b9c4bf" strokeWidth={1.2} />)}
        <ellipse cx={vx} cy={vy + 150} rx={70} ry={14} fill="#fff" opacity={0.35} />
        <rect x={148} y={vy - 56} width={94} height={116} fill="#e2ddd0" />
        <rect x={166} y={vy - 30} width={58} height={90} fill="#b88b5c" stroke={OUT} strokeWidth={1.5} />
        <path d={`M195 ${vy - 30} V${vy + 60}`} stroke="#8e683f" strokeWidth={2} />
        <Window x={172} y={vy - 22} w={18} h={28} c={c} panes={1} frame="#b88b5c" />
        <Window x={200} y={vy - 22} w={18} h={28} c={c} panes={1} frame="#b88b5c" />
        {lockers(-1)}
        {lockers(1)}
        <path d="M120 40 L270 40 L270 74 L195 92 L120 74 Z" fill="#1f6b3c" stroke={OUT} strokeWidth={1.5} />
        <Paw x={195} y={60} s={1.1} />
        <rect x={292} y={226} width={46} height={40} fill="#f3e3b7" stroke="#b48a5c" strokeWidth={3} transform="skewY(-14) translate(0 78)" />
      </g>
    ),
    lights: lit(c.t) ? <Glow x={195} y={60} r={140} color="#fff6d8" o={0.35} /> : null,
  };
};

const cafeteria: S = (c) => ({
  indoor: true,
  base: (
    <g>
      <rect width={390} height={260} fill="#f2e7d4" />
      {[14, 108, 202, 296].map((x) => <Window key={x} x={x} y={60} w={80} h={130} c={c} panes={2} frame="#f9f5ec" outside={<OutsideTrees x={x} y={60} w={80} h={130} c={c} />} />)}
      <circle cx={195} cy={30} r={22} fill="#1f6b3c" stroke={OUT} strokeWidth={1.5} />
      <Paw x={195} y={31} s={1} />
      <rect y={206} width={390} height={54} fill="#d8c7aa" />
      <rect x={0} y={200} width={390} height={8} fill="#c4ae8a" />
      {/* serving counter */}
      <path d="M0 236 L120 236 L120 290 L0 300 Z" fill="#b7c3cc" stroke={OUT} strokeWidth={1.5} />
      <path d="M0 226 L118 226 L118 236 L0 236 Z" fill="#dfe6ea" />
      <path d="M6 214 L112 214" stroke="#cfe6f2" strokeWidth={4} opacity={0.8} />
      {/* floor tiles */}
      <rect y={260} width={390} height={220} fill="#e3d7c2" />
      {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => <path key={i} d={`M${-200 + i * 100} 480 L${120 + i * 22} 260`} stroke="#d2c4ab" strokeWidth={1.2} />)}
      {[290, 330, 390, 470].map((y) => <path key={y} d={`M0 ${y} H390`} stroke="#d2c4ab" strokeWidth={1.2} />)}
      {/* tables */}
      {[[284, 0.55], [334, 0.75], [404, 1.0]].map(([y, s], i) => {
        const w = 330 * (s as number);
        const x0 = 195 - w / 2 + 40;
        const yy = y as number;
        const k = s as number;
        return (
          <g key={i}>
            <path d={`M${x0 - 4 * k} ${yy - 10 * k} H${x0 + w + 4 * k} L${x0 + w + 8 * k} ${yy - 2 * k} H${x0 - 8 * k} Z`} fill="#3b7f5a" stroke={OUT} strokeWidth={1.2} />
            <path d={`M${x0} ${yy} H${x0 + w} L${x0 + w + 14 * k} ${yy + 34 * k} H${x0 - 14 * k} Z`} fill="#e6ebef" stroke={OUT} strokeWidth={1.5} />
            <path d={`M${x0 - 14 * k} ${yy + 34 * k} H${x0 + w + 14 * k} V${yy + 40 * k} H${x0 - 14 * k} Z`} fill="#b9c3cc" stroke={OUT} strokeWidth={1.2} />
            {[0.1, 0.36, 0.62, 0.84].map((t, j) => (
              <g key={j}>
                <path d={`M${x0 + w * t} ${yy + 8 * k} h${36 * k} l${2 * k} ${16 * k} h${-40 * k} Z`} fill={j % 2 ? "#ff9f5a" : "#5fb7c9"} stroke={OUT} strokeWidth={1} />
                <circle cx={x0 + w * t + 10 * k} cy={yy + 16 * k} r={4 * k} fill="#f2d16b" />
                <circle cx={x0 + w * t + 24 * k} cy={yy + 16 * k} r={4.5 * k} fill="#8bc36a" />
                <rect x={x0 + w * t + 32 * k} y={yy + 4 * k} width={6 * k} height={12 * k} rx={1} fill="#fff" stroke={OUT} strokeWidth={0.8} />
              </g>
            ))}
            <path d={`M${x0 - 6 * k} ${yy + 40 * k} H${x0 + w + 6 * k} L${x0 + w + 12 * k} ${yy + 48 * k} H${x0 - 12 * k} Z`} fill="#3b7f5a" stroke={OUT} strokeWidth={1.2} />
          </g>
        );
      })}
      {[100, 290].map((x) => <Pendant key={x} x={x} y={0} len={14} c={c} color="#f2f2ee" />)}
    </g>
  ),
  lights: lit(c.t) ? <><Glow x={100} y={34} r={110} color="#fff2c8" o={0.4} /><Glow x={290} y={34} r={110} color="#fff2c8" o={0.4} /></> : null,
});

const gym: S = (c) => ({
  indoor: true,
  base: (
    <g>
      <rect width={390} height={300} fill="#ece6da" />
      {[30, 110, 190, 270].map((x) => <Window key={x} x={x + 10} y={26} w={70} h={40} c={c} panes={3} frame="#d9d2c4" />)}
      <rect y={210} width={390} height={90} fill="#2a7548" />
      {[0, 65, 130, 195, 260, 325].map((x) => <path key={x} d={`M${x} 210 V300`} stroke="#1f5c38" strokeWidth={2} />)}
      {/* banners */}
      {[[30, 90], [350, 90]].map(([x, y], i) => (
        <g key={i}>
          <path d={`M${x - 20} ${y} H${x + 20} V${y + 46} L${x} ${y + 62} L${x - 20} ${y + 46} Z`} fill={i ? "#fff" : "#1f6b3c"} stroke={OUT} strokeWidth={1.5} />
          <Paw x={x} y={y + 26} s={0.9} fill={i ? "#1f6b3c" : "#fff"} />
        </g>
      ))}
      {/* scoreboard (no numbers) */}
      <rect x={60} y={96} width={70} height={40} rx={4} fill="#2c2f36" stroke={OUT} strokeWidth={1.5} />
      {[0, 1, 2].map((i) => <rect key={i} x={68 + i * 20} y={104} width={14} height={10} rx={2} fill={i === 1 ? "#ffb347" : "#ff5a4a"} opacity={0.85} />)}
      <rect x={68} y={120} width={54} height={6} rx={3} fill="#5bd18a" opacity={0.8} />
      {/* hoop */}
      <path d="M195 70 V100" stroke="#8a8f96" strokeWidth={6} />
      <rect x={157} y={100} width={76} height={50} rx={3} fill="#fbfbf8" stroke="#2f343b" strokeWidth={3} />
      <rect x={180} y={118} width={30} height={22} fill="none" stroke="#e8582c" strokeWidth={3} />
      <ellipse cx={195} cy={152} rx={17} ry={5} fill="none" stroke="#e8582c" strokeWidth={4} />
      <path d="M180 153 L186 176 M190 156 L192 178 M200 156 L198 178 M210 153 L204 176 M184 166 L206 166" stroke="#f4f4f4" strokeWidth={1.6} />
      {/* bleachers */}
      <g>{[0, 1, 2, 3].map((i) => <rect key={i} x={250 + i * 6} y={170 + i * 12} width={140 - i * 6} height={12} fill={i % 2 ? "#c9a46a" : "#b8925a"} stroke={OUT} strokeWidth={1} />)}</g>
      {/* hardwood */}
      {floorPlanks(300, 480, "#e5b57a", "#cf9d62", 10)}
      <path d="M90 300 L300 300 L360 480 L30 480 Z" fill="#2a7548" opacity={0.85} />
      <path d="M90 300 L300 300 L360 480 L30 480 Z" fill="none" stroke="#fff" strokeWidth={3} />
      <ellipse cx={195} cy={480} rx={150} ry={40} fill="none" stroke="#fff" strokeWidth={3} />
      <path d="M0 300 H390" stroke="#fff" strokeWidth={3} />
      <ellipse cx={195} cy={300} rx={260} ry={70} fill="none" stroke="#fff" strokeWidth={2.5} opacity={0.7} />
      <ellipse cx={120} cy={420} rx={60} ry={10} fill="#fff" opacity={0.15} />
    </g>
  ),
  lights: lit(c.t) ? <Glow x={195} y={20} r={200} color="#fff5d6" o={0.35} /> : null,
});

function StadiumLights({ x, y, c, s = 1 }: { x: number; y: number; c: Ctx; s?: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <path d="M0 0 V170" stroke="#7d8590" strokeWidth={5} />
      <rect x={-22} y={-26} width={44} height={26} rx={2} fill="#3d434c" stroke={OUT} strokeWidth={1.5} />
      {[0, 1, 2, 3].map((i) => [0, 1].map((j) => <rect key={`${i}${j}`} x={-19 + i * 10} y={-23 + j * 11} width={8} height={9} rx={1}
        fill={lit(c.t) ? "#fff9d8" : "#c9d2dc"} />))}
    </g>
  );
}

function Bleachers({ x, y, w, rows = 6, c, crowd = false }: { x: number; y: number; w: number; rows?: number; c: Ctx; crowd?: boolean }) {
  const out: React.ReactNode[] = [];
  for (let i = 0; i < rows; i++) {
    out.push(<rect key={i} x={x} y={y + i * 12} width={w} height={12} fill={i % 2 ? "#9aa6b1" : "#b4bec7"} stroke={OUT} strokeWidth={0.8} />);
    if (crowd) {
      for (let k = 0; k < w / 9; k++) {
        if ((k * 7 + i * 3) % 5 === 0) continue;
        out.push(<circle key={`${i}-${k}`} cx={x + 5 + k * 9} cy={y + i * 12 + 4} r={3.2} fill={["#1f6b3c", "#ffffff", "#f2c14e", "#d95d5d", "#3d6fb6", "#2b2b2b"][(k * 3 + i * 5) % 6]} />);
      }
    }
  }
  void c;
  return <g>{out}</g>;
}

const footballField: S = (c) => {
  const [g1, g2] = c.s === "winter" ? ["#9fbf8a", "#8fb07c"] : ["#5fae4f", "#4f9c42"];
  return {
    base: (
      <g>
        <Sky c={c} />
        <g>{[30, 90, 160, 230, 300, 360].map((x, i) => <Tree key={i} x={x} y={215} s={0.55} c={c} />)}</g>
        <Bleachers x={232} y={150} w={158} rows={6} c={c} crowd />
        <rect x={262} y={118} width={70} height={32} fill="#d9dde2" stroke={OUT} strokeWidth={1.5} />
        <rect x={270} y={126} width={54} height={12} fill={lit(c.t) ? "#ffe6a3" : "#9fc7e6"} />
        <StadiumLights x={40} y={60} c={c} />
        <StadiumLights x={350} y={40} c={c} s={0.9} />
        {/* field in perspective */}
        <path d="M0 230 L390 230 L390 480 L0 480 Z" fill="#b65a3e" />
        <path d="M30 232 L360 232 L470 480 L-80 480 Z" fill={g1} />
        {[0, 1, 2, 3, 4, 5, 6].map((i) => {
          const y0 = 232 + 248 * Math.pow(i / 7, 1.5), y1 = 232 + 248 * Math.pow((i + 1) / 7, 1.5);
          const xl = (y: number) => 30 - 110 * ((y - 232) / 248), xr = (y: number) => 360 + 110 * ((y - 232) / 248);
          return i % 2 ? <path key={i} d={`M${xl(y0)} ${y0} L${xr(y0)} ${y0} L${xr(y1)} ${y1} L${xl(y1)} ${y1} Z`} fill={g2} /> : null;
        })}
        {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => {
          const y = 232 + 248 * Math.pow(i / 7, 1.5);
          const t = (y - 232) / 248;
          return <path key={`l${i}`} d={`M${30 - 110 * t} ${y} H${360 + 110 * t}`} stroke="#fff" strokeWidth={1 + i * 0.45} opacity={0.85} />;
        })}
        <path d="M30 232 L-80 480 M360 232 L470 480" stroke="#fff" strokeWidth={3} />
        {[0.12, 0.3, 0.52, 0.78].map((t, i) => {
          const y = 232 + 248 * t;
          const xl = 30 - 110 * t, xr = 360 + 110 * t;
          return <g key={`hash${i}`} stroke="#fff" strokeWidth={1.4 + t * 2} opacity={0.8}>
            <path d={`M${xl + (xr - xl) * 0.38} ${y} v${4 + t * 6}`} /><path d={`M${xl + (xr - xl) * 0.62} ${y} v${4 + t * 6}`} />
          </g>;
        })}
        {/* far end zone */}
        <path d="M30 232 L360 232 L364 244 L26 244 Z" fill="#1f6b3c" />
        {/* goalposts */}
        <g stroke="#f2c932" strokeWidth={4} strokeLinecap="round" fill="none">
          <path d="M195 238 V206 M170 206 H220 M170 206 V158 M220 206 V158" />
        </g>
        {c.s === "winter" && <path d="M0 230 H390 V250 H0 Z" fill="#fff" opacity={0.5} />}

      </g>
    ),
    lights: lit(c.t) ? (
      <g>
        <Glow x={40} y={50} r={90} color="#fff9d8" o={0.6} />
        <Glow x={350} y={32} r={80} color="#fff9d8" o={0.6} />
        <path d="M40 60 L-40 480 L200 480 Z" fill="#fff8d0" opacity={0.08} />
        <path d="M350 44 L190 480 L430 480 Z" fill="#fff8d0" opacity={0.08} />
      </g>
    ) : null,
  };
};

const soccerField: S = (c) => {
  const [g1, g2] = c.s === "winter" ? ["#9fbf8a", "#8fb07c"] : ["#5cb04e", "#4c9e40"];
  // the pitch in perspective: x at depth t (0 = far touchline, 1 = near)
  const y = (t: number) => 236 + 244 * t;
  const xl = (t: number) => 40 - 120 * t, xr = (t: number) => 350 + 120 * t;
  const at = (u: number, t: number) => xl(t) + (xr(t) - xl(t)) * u;
  return {
    base: (
      <g>
        <Sky c={c} />
        <g>{[24, 80, 140, 250, 320, 372].map((x, i) => <Tree key={i} x={x} y={218} s={0.5} c={c} />)}</g>
        <Bleachers x={150} y={168} w={120} rows={4} c={c} crowd />
        <StadiumLights x={30} y={70} c={c} s={0.85} />
        <StadiumLights x={360} y={64} c={c} s={0.85} />
        <path d="M0 232 L390 232 L390 480 L0 480 Z" fill={g2} />
        <path d={`M${xl(0)} ${y(0)} L${xr(0)} ${y(0)} L${xr(1)} ${y(1)} L${xl(1)} ${y(1)} Z`} fill={g1} />
        {/* mowing stripes run toward you */}
        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => i % 2 ? (
          <path key={i} d={`M${at(i / 10, 0)} ${y(0)} L${at((i + 1) / 10, 0)} ${y(0)} L${at((i + 1) / 10, 1)} ${y(1)} L${at(i / 10, 1)} ${y(1)} Z`}
            fill={g2} opacity={0.75} />
        ) : null)}
        <g stroke="#fff" fill="none" opacity={0.9} strokeLinejoin="round">
          <path d={`M${xl(0)} ${y(0)} L${xr(0)} ${y(0)} L${xr(1)} ${y(1)} L${xl(1)} ${y(1)} Z`} strokeWidth={2.5} />
          {/* halfway line and center circle */}
          <path d={`M${at(0.5, 0)} ${y(0)} L${at(0.5, 1)} ${y(1)}`} strokeWidth={2.4} />
          <ellipse cx={at(0.5, 0.42)} cy={y(0.42)} rx={46} ry={22} strokeWidth={2.2} />
          {/* the box at the far end */}
          <path d={`M${at(0.3, 0)} ${y(0)} L${at(0.3, 0.12)} ${y(0.12)} L${at(0.7, 0.12)} ${y(0.12)} L${at(0.7, 0)} ${y(0)}`} strokeWidth={2} />
        </g>
        <circle cx={at(0.5, 0.42)} cy={y(0.42)} r={2.6} fill="#fff" />
        {/* the far goal with its net */}
        <g>
          <path d={`M${at(0.44, 0)} ${y(0)} V${y(0) - 18} H${at(0.56, 0)} V${y(0)}`} stroke="#fff" strokeWidth={3} fill="none" strokeLinecap="round" />
          <path d={`M${at(0.44, 0) + 3} ${y(0) - 15} H${at(0.56, 0) - 3} V${y(0) - 2} H${at(0.44, 0) + 3} Z`} fill="#fff" opacity={0.25} />
        </g>
        {/* a ball near the center spot */}
        <g transform={`translate(${at(0.56, 0.62)} ${y(0.62)})`}>
          <circle r={7} fill="#fff" stroke={OUT} strokeWidth={1.4} />
          <path d="M0 -3 L3 -1 L2 3 L-2 3 L-3 -1 Z" fill={OUT} />
        </g>
        {c.s === "winter" && <path d="M0 230 H390 V250 H0 Z" fill="#fff" opacity={0.5} />}
      </g>
    ),
    lights: lit(c.t) ? (
      <g>
        <Glow x={30} y={60} r={84} color="#fff9d8" o={0.55} />
        <Glow x={360} y={56} r={84} color="#fff9d8" o={0.55} />
      </g>
    ) : null,
  };
};

const baseballField: S = (c) => {
  const [g1, g2] = c.s === "winter" ? ["#a7c494", "#98b886"] : ["#62b252", "#55a147"];
  return {
    base: (
      <g>
        <Sky c={c} />
        <g>{[20, 80, 150, 240, 310, 370].map((x, i) => <Tree key={i} x={x} y={178} s={0.6} c={c} />)}</g>
        <StadiumLights x={30} y={40} c={c} s={0.85} />
        <StadiumLights x={362} y={52} c={c} s={0.8} />
        <path d="M0 176 Q195 150 390 176 L390 204 Q195 180 0 204 Z" fill="#2c6b45" stroke={OUT} strokeWidth={1.5} />
        <path d="M0 176 Q195 150 390 176" stroke="#f2c932" strokeWidth={3} fill="none" />
        <path d="M24 176 V120 M366 176 V120" stroke="#f2c932" strokeWidth={3} />
        {/* outfield */}
        <path d="M0 200 Q195 176 390 200 L390 480 L0 480 Z" fill={g1} />
        {[0, 1, 2, 3].map((i) => <path key={i} d={`M0 ${222 + i * 34} Q195 ${200 + i * 36} 390 ${222 + i * 34}`} stroke={g2} strokeWidth={14} fill="none" />)}
        {/* infield */}
        <path d="M195 470 L345 360 Q195 250 45 360 Z" fill="#c9915f" />
        <path d="M195 448 L300 372 L195 300 L90 372 Z" fill={g1} />
        <ellipse cx={195} cy={372} rx={20} ry={8} fill="#c9915f" />
        <rect x={190} y={369} width={10} height={3} fill="#fff" />
        {[[195, 452], [304, 372], [195, 296], [86, 372]].map(([x, y], i) => <rect key={i} x={x - 5} y={y - 5} width={10} height={10} fill="#fff" transform={`rotate(45 ${x} ${y})`} />)}
        <path d="M195 452 L410 296 M195 452 L-20 296" stroke="#fff" strokeWidth={2} opacity={0.85} />
        <ellipse cx={195} cy={466} rx={46} ry={14} fill="#c9915f" />
        {/* dugout */}
        <path d="M0 330 L60 312 L60 344 L0 364 Z" fill="#2f3a43" stroke={OUT} strokeWidth={1.5} />
        <path d="M0 324 L64 306 L64 312 L0 330 Z" fill="#1f6b3c" />
        {/* backstop netting edge */}
        <g stroke="#3b4148" strokeWidth={1} opacity={0.35}>
          {Array.from({ length: 12 }).map((_, i) => <path key={i} d={`M${300 + i * 9} 300 L${260 + i * 9} 480`} />)}
          {Array.from({ length: 12 }).map((_, i) => <path key={`b${i}`} d={`M${260 + i * 9} 300 L${300 + i * 9} 480`} />)}
        </g>
      </g>
    ),
    lights: lit(c.t) ? <><Glow x={30} y={36} r={80} color="#fff9d8" o={0.6} /><Glow x={362} y={46} r={72} color="#fff9d8" o={0.6} /></> : null,
  };
};

function Church({ x, y, c }: { x: number; y: number; c: Ctx }) {
  const snow = c.s === "winter";
  return (
    <g transform={`translate(${x} ${y})`}>
      <rect x={-8} y={-150} width={36} height={60} fill="#f7f5ef" stroke={OUT} strokeWidth={1.5} />
      <rect x={-4} y={-176} width={28} height={26} fill="#f7f5ef" stroke={OUT} strokeWidth={1.5} />
      <path d="M-4 -176 L10 -232 L24 -176 Z" fill="#f7f5ef" stroke={OUT} strokeWidth={1.5} />
      <path d="M2 -176 L10 -216 L18 -176 Z" fill="#e3e0d8" />
      <rect x={4} y={-140} width={12} height={16} rx={6} fill={lit(c.t) ? "#ffd88a" : "#6c7e92"} />
      <path d="M-40 -90 L10 -128 L60 -90 Z" fill={snow ? "#ffffff" : "#5f6670"} stroke={OUT} strokeWidth={1.5} />
      <rect x={-34} y={-90} width={88} height={90} fill="#f7f5ef" stroke={OUT} strokeWidth={1.5} />
      {[-22, 0, 22, 44].map((wx, i) => i === 1 ? null : <rect key={i} x={wx - 4} y={-72} width={12} height={26} rx={6} fill={lit(c.t) ? "#ffd88a" : "#6c7e92"} />)}
      <rect x={0} y={-36} width={20} height={36} rx={10} fill="#7b5236" />
    </g>
  );
}

const townGreen: S = (c) => {
  const [g1, g2] = GRASS[c.s] || GRASS.summer;
  return {
    base: (
      <g>
        <Sky c={c} />
        {/* houses */}
        {[[300, 220, "#f3e3b5"], [350, 226, "#d8e3ea"], [250, 228, "#f1f0eb"]].map(([x, y, col], i) => (
          <g key={i}>
            <path d={`M${(x as number) - 30} ${(y as number) - 30} L${x} ${(y as number) - 56} L${(x as number) + 30} ${(y as number) - 30} Z`} fill={c.s === "winter" ? "#fff" : "#6a5550"} stroke={OUT} strokeWidth={1.2} />
            <rect x={(x as number) - 28} y={(y as number) - 30} width={56} height={34} fill={col as string} stroke={OUT} strokeWidth={1.2} />
            {[-16, 6].map((dx) => <rect key={dx} x={(x as number) + dx} y={(y as number) - 22} width={10} height={12} fill={lit(c.t) ? "#ffd88a" : "#7f93a8"} />)}
          </g>
        ))}
        <Church x={110} y={232} c={c} />
        <rect y={226} width={390} height={254} fill={g1} />
        <path d="M0 260 Q120 240 210 262 T390 250 V480 H0 Z" fill={g2} />
        {/* path */}
        <path d="M150 480 Q190 360 230 300 Q250 270 300 256 L316 262 Q262 282 248 312 Q222 370 230 480 Z" fill={c.s === "winter" ? "#cfd9e1" : "#e8d9b8"} />
        {/* gazebo */}
        <g transform="translate(286 300)">
          <path d="M-40 -42 L0 -74 L40 -42 Z" fill={c.s === "winter" ? "#fff" : "#4f6b5c"} stroke={OUT} strokeWidth={1.5} />
          <path d="M0 -74 V-82" stroke="#d6d1c4" strokeWidth={3} />
          <rect x={-40} y={-42} width={80} height={6} fill="#f7f5ef" stroke={OUT} strokeWidth={1.2} />
          {[-34, -12, 12, 34].map((x) => <rect key={x} x={x - 2.5} y={-36} width={5} height={34} fill="#f7f5ef" stroke={OUT} strokeWidth={1} />)}
          <path d="M-38 -14 H38" stroke="#f7f5ef" strokeWidth={3} />
          <rect x={-44} y={-4} width={88} height={10} fill="#e9e5da" stroke={OUT} strokeWidth={1.2} />
        </g>
        <Tree x={40} y={330} s={1.25} c={c} />
        <Tree x={200} y={262} s={0.75} c={c} />
        <Tree x={370} y={360} s={1.35} c={c} />
        {/* bench & lamp */}
        <g transform="translate(110 400)">
          <rect x={-34} y={-18} width={68} height={6} rx={2} fill="#7b5236" stroke={OUT} strokeWidth={1} />
          <rect x={-34} y={-8} width={68} height={6} rx={2} fill="#8c6040" stroke={OUT} strokeWidth={1} />
          <path d="M-28 -2 V12 M28 -2 V12" stroke="#2f3a43" strokeWidth={3} />
        </g>
        <g transform="translate(330 430)">
          <path d="M0 0 V-84" stroke="#2f3a43" strokeWidth={4} />
          <path d="M-8 -84 H8 L5 -100 H-5 Z" fill="#2f3a43" />
          <rect x={-4.5} y={-97} width={9} height={11} fill={lit(c.t) ? "#ffe39a" : "#dfe7ee"} />
        </g>
        {c.s === "winter" && <g fill="#fff">{Array.from({ length: 30 }).map((_, i) => <circle key={i} cx={(i * 53) % 390} cy={(i * 97) % 300} r={1.8} opacity={0.8} />)}</g>}
      </g>
    ),
    lights: lit(c.t) ? <><Glow x={330} y={338} r={50} color="#ffe39a" o={0.7} /><Glow x={120} y={150} r={40} color="#ffd88a" o={0.35} /></> : null,
  };
};

const beach: S = (c) => {
  const winter = c.s === "winter";
  const water = winter ? ["#7d93a8", "#93a9bc"] : c.t === "night" ? ["#22325e", "#2e4170"] : ["#3f8fc4", "#7cc0e0"];
  const wid = `water${c.id}`;
  return {
    base: (
      <g>
        <Sky c={c} />
        <defs>
          <linearGradient id={wid} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={water[0]} /><stop offset="1" stopColor={water[1]} /></linearGradient>
        </defs>
        <rect y={230} width={390} height={120} fill={`url(#${wid})`} />
        {/* islands */}
        <path d="M20 232 Q50 214 80 232 Z" fill="#5b7a5f" />
        <path d="M120 232 Q140 220 160 232 Z" fill="#6b8a6c" />
        <path d="M300 232 Q330 210 370 232 Z" fill="#5b7a5f" />
        <g stroke="#fff" strokeWidth={1.6} opacity={0.5} strokeLinecap="round">
          {[[40, 260], [140, 280], [260, 268], [90, 310], [210, 320], [320, 300]].map(([x, y], i) => <path key={i} d={`M${x} ${y} h${18 + (i % 3) * 8}`} />)}
        </g>
        {!winter && (
          <g>
            {[[110, 246, 1], [230, 238, 0.7], [320, 252, 0.85]].map(([x, y, s], i) => (
              <g key={i} transform={`translate(${x} ${y}) scale(${s})`}>
                <path d="M0 0 L0 -40 L24 -4 Z" fill="#fff" stroke={OUT} strokeWidth={1.2} />
                <path d="M-2 -34 L-18 -4 L-2 -4 Z" fill="#f2f2ee" stroke={OUT} strokeWidth={1.2} />
                <path d="M-20 0 H26 L20 8 H-14 Z" fill={i === 1 ? "#d95d5d" : "#2f4f7a"} />
              </g>
            ))}
          </g>
        )}
        {/* jetty */}
        <g stroke={OUT} strokeWidth={1.4}>
          {[[392, 330, 26], [360, 318, 22], [330, 306, 18], [304, 296, 15], [282, 288, 12], [264, 282, 10]].map(([x, y, r], i) => (
            <ellipse key={i} cx={x} cy={y} rx={r * 1.4} ry={r} fill={i % 2 ? "#8a8f94" : "#9ea3a8"} />
          ))}
        </g>
        {/* sand */}
        <path d="M0 340 Q120 326 220 340 T390 336 V480 H0 Z" fill={winter ? "#e4dccb" : "#ecd7a6"} />
        <path d="M0 340 Q120 326 220 340 T390 336" stroke="#fff" strokeWidth={4} fill="none" opacity={0.7} />
        <g stroke={winter ? "#cfc6b4" : "#d9c08c"} strokeWidth={2} fill="none" opacity={0.7}>
          {[[40, 390], [160, 410], [260, 380], [320, 440], [90, 450]].map(([x, y], i) => <path key={i} d={`M${x} ${y} q12 -5 24 0 t24 0`} />)}
        </g>
        {/* beach grass */}
        <g stroke={winter ? "#a59a7f" : "#8aa456"} strokeWidth={3} strokeLinecap="round">
          {[10, 22, 34, 46, 58].map((x, i) => <path key={i} d={`M${x} 480 Q${x + 4} 440 ${x + (i % 2 ? 14 : -8)} ${410 + (i % 3) * 8}`} fill="none" />)}
        </g>
        {/* lifeguard chair */}
        {!winter && (
          <g transform="translate(250 420)" stroke="#f4f1ea" strokeWidth={5} strokeLinecap="round" fill="none">
            <path d="M-20 0 L-8 -70 M20 0 L8 -70 M-14 -36 H14" />
            <path d="M-16 -70 H16 V-92" stroke="#f4f1ea" />
            <rect x={-18} y={-104} width={36} height={14} fill="#d95d5d" stroke="none" />
          </g>
        )}
        {c.s === "summer" && (
          <g transform="translate(120 430)">
            <path d="M0 0 V-60" stroke="#6b5040" strokeWidth={3} />
            <path d="M-44 -54 Q0 -92 44 -54 Z" fill="#f5c15c" stroke={OUT} strokeWidth={1.5} />
            <path d="M-22 -60 Q0 -92 0 -92 Q0 -92 22 -60" fill="#e8685d" />
            <rect x={-26} y={-6} width={52} height={10} rx={3} fill="#5fb7c9" />
          </g>
        )}
        {winter && <g fill="#fff">{[[60, 400], [200, 450], [330, 400]].map(([x, y], i) => <ellipse key={i} cx={x} cy={y} rx={40} ry={8} opacity={0.8} />)}</g>}
      </g>
    ),
  };
};

const bedroom: S = (c) => ({
  indoor: true,
  base: (
    <g>
      <rect width={390} height={320} fill="#9cc3c6" />
      <rect y={300} width={390} height={20} fill="#86aeb1" />
      <Window x={238} y={60} w={112} h={120} c={c} outside={<OutsideTrees x={238} y={60} w={112} h={120} c={c} />} />
      <path d="M230 54 H358 V66 H230 Z" fill="#6b7f8c" />
      <path d="M232 64 Q244 120 236 186 L226 186 Q232 120 222 64 Z" fill="#f2d3a3" />
      <path d="M356 64 Q344 120 352 186 L362 186 Q356 120 366 64 Z" fill="#f2d3a3" />
      {/* posters */}
      <g transform="rotate(-3 70 90)">
        <rect x={34} y={50} width={72} height={92} fill="#2f7a4a" stroke="#fff" strokeWidth={4} />
        <path d="M70 128 L96 102 L70 76 L44 102 Z" fill="none" stroke="#fff" strokeWidth={2.5} />
        <circle cx={70} cy={102} r={4} fill="#e8d1a8" />
      </g>
      <g transform="rotate(2 160 80)">
        <rect x={124} y={44} width={74} height={56} fill="#2b2d4a" stroke="#fff" strokeWidth={4} />
        <circle cx={150} cy={72} r={14} fill="#ff8f6b" />
        <circle cx={172} cy={66} r={9} fill="#ffd166" />
        <path d="M132 92 L190 92" stroke="#7bd3c6" strokeWidth={3} />
      </g>
      <path d="M126 116 L176 128 L126 140 Z" fill="#1f6b3c" stroke={OUT} strokeWidth={1.2} />
      <Paw x={142} y={128} s={0.5} />
      {/* shelf with trophies */}
      <rect x={130} y={190} width={90} height={7} fill="#b88b5c" stroke={OUT} strokeWidth={1} />
      {[[146, 0.9], [168, 1.2], [194, 1]].map(([x, s], i) => (
        <g key={i} transform={`translate(${x} 190) scale(${s})`}>
          <rect x={-7} y={-6} width={14} height={6} fill="#6b5040" />
          <path d="M-8 -22 H8 Q8 -10 0 -8 Q-8 -10 -8 -22 Z" fill="#f2c14e" stroke={OUT} strokeWidth={1} />
          <path d="M0 -8 V-6" stroke="#f2c14e" strokeWidth={3} />
        </g>
      ))}
      {/* floor */}
      {floorPlanks(320, 480, "#b98b5f", "#9d7149", 8)}
      <ellipse cx={180} cy={420} rx={130} ry={34} fill="#e58f6f" opacity={0.85} />
      <ellipse cx={180} cy={420} rx={110} ry={26} fill="none" stroke="#f6c3a6" strokeWidth={3} />
      {/* bed */}
      <rect x={-10} y={232} width={190} height={30} rx={6} fill="#8a6142" stroke={OUT} strokeWidth={1.5} />
      <rect x={-10} y={250} width={196} height={86} rx={10} fill="#3d6fb6" stroke={OUT} strokeWidth={1.5} />
      <path d="M-10 270 H186" stroke="#5c8bd0" strokeWidth={6} />
      <path d="M-10 296 H186" stroke="#5c8bd0" strokeWidth={6} />
      <rect x={6} y={226} width={70} height={30} rx={12} fill="#f6f1e6" stroke={OUT} strokeWidth={1.5} />
      <rect x={-10} y={330} width={196} height={16} fill="#6e4d34" />
      {/* desk */}
      <rect x={250} y={262} width={140} height={10} fill="#d1a674" stroke={OUT} strokeWidth={1.5} />
      <path d="M258 272 V360 M382 272 V360" stroke="#a37a4f" strokeWidth={8} />
      <path d="M296 262 L304 238 L344 238 L352 262 Z" fill="#2f343b" />
      <rect x={300} y={212} width={48} height={30} rx={3} fill="#3a404a" stroke={OUT} strokeWidth={1.5} />
      <rect x={303} y={215} width={42} height={24} fill={lit(c.t) ? "#9fd6ff" : "#5b6b80"} />
      <path d="M266 262 L272 214 M272 214 L292 208" stroke="#4a4f57" strokeWidth={3} />
      <path d="M282 200 L302 206 L296 218 L280 212 Z" fill="#ffb347" stroke={OUT} strokeWidth={1.2} />
    </g>
  ),
  lights: lit(c.t) ? <><Glow x={292} y={222} r={70} color="#ffd27a" o={0.6} /><Glow x={324} y={226} r={40} color="#9fd6ff" o={0.45} /></> : null,
});

const dorm: S = (c) => ({
  indoor: true,
  base: (
    <g>
      <rect width={390} height={320} fill="#ece8df" />
      {Array.from({ length: 14 }).map((_, i) => <path key={i} d={`M0 ${i * 24} H390`} stroke="#ddd7cb" strokeWidth={1.5} />)}
      {Array.from({ length: 14 }).map((_, i) => Array.from({ length: 6 }).map((__, j) => (
        <path key={`${i}-${j}`} d={`M${j * 70 + (i % 2 ? 35 : 0)} ${i * 24} v24`} stroke="#ddd7cb" strokeWidth={1.5} />
      )))}
      <Window x={150} y={60} w={100} h={110} c={c} outside={
        <g>
          <rect x={150} y={120} width={100} height={50} fill="#a8533a" />
          {[160, 182, 204, 226].map((x) => <rect key={x} x={x} y={130} width={12} height={14} fill={lit(c.t) ? "#ffd88a" : "#e9e2d0"} />)}
          <Tree x={240} y={170} s={0.5} c={c} />
        </g>} />
      {/* string lights */}
      <path d="M0 30 Q100 52 195 34 T390 36" fill="none" stroke="#4a4a4a" strokeWidth={1.5} />
      {Array.from({ length: 12 }).map((_, i) => {
        const x = 16 + i * 32;
        const y = 34 + Math.sin(i * 0.9) * 8 + 6;
        return <circle key={i} cx={x} cy={y} r={4} fill={["#ffd166", "#ff8f6b", "#7bd3c6", "#c3a6ff"][i % 4]} />;
      })}
      {/* loft bed + desk */}
      <rect x={0} y={150} width={132} height={22} rx={4} fill="#c49a6a" stroke={OUT} strokeWidth={1.5} />
      <rect x={0} y={128} width={126} height={26} rx={8} fill="#7a5cb3" stroke={OUT} strokeWidth={1.5} />
      <rect x={4} y={120} width={44} height={16} rx={7} fill="#f3eee4" />
      <path d="M126 150 V330" stroke="#a87e52" strokeWidth={8} />
      <rect x={0} y={250} width={120} height={9} fill="#d1a674" stroke={OUT} strokeWidth={1.2} />
      <rect x={30} y={220} width={44} height={30} rx={3} fill="#3a404a" />
      <rect x={33} y={223} width={38} height={24} fill={lit(c.t) ? "#9fd6ff" : "#5b6b80"} />
      {/* roommate bed */}
      <rect x={270} y={250} width={130} height={60} rx={8} fill="#2f8f9d" stroke={OUT} strokeWidth={1.5} />
      <rect x={330} y={236} width={50} height={22} rx={9} fill="#f3eee4" stroke={OUT} strokeWidth={1.2} />
      <rect x={196} y={262} width={50} height={58} rx={4} fill="#e6e8ea" stroke={OUT} strokeWidth={1.5} />
      <path d="M200 286 H242" stroke="#c7cbcf" strokeWidth={2} />
      {floorPlanks(320, 480, "#c7b49a", "#b19d82", 7)}
      <rect x={110} y={380} width={180} height={60} rx={10} fill="#f0c25c" opacity={0.75} />
    </g>
  ),
  lights: lit(c.t) ? <Glow x={195} y={40} r={170} color="#ffd9a0" o={0.35} /> : null,
});

function Brick({ x, y, w, h, c, columns = false }: { x: number; y: number; w: number; h: number; c: Ctx; columns?: boolean }) {
  const snow = c.s === "winter";
  const rows = Math.floor(h / 34);
  const cols = Math.floor(w / 26);
  return (
    <g>
      <path d={`M${x - 8} ${y} L${x + w / 2} ${y - 30} L${x + w + 8} ${y} Z`} fill={snow ? "#ffffff" : "#5c4a46"} stroke={OUT} strokeWidth={1.5} />
      <rect x={x} y={y} width={w} height={h} fill="#a9543a" stroke={OUT} strokeWidth={1.5} />
      {Array.from({ length: rows }).map((_, r) => Array.from({ length: cols }).map((__, k) => (
        <rect key={`${r}-${k}`} x={x + 8 + k * 26} y={y + 12 + r * 34} width={12} height={18} fill={lit(c.t) && (r + k) % 3 !== 0 ? "#ffd88a" : "#e9e2d0"} stroke="#f5efe2" strokeWidth={1.5} />
      )))}
      {columns && [0.3, 0.45, 0.55, 0.7].map((t, i) => <rect key={i} x={x + w * t - 3} y={y + h - 50} width={6} height={50} fill="#f5f2ea" />)}
    </g>
  );
}

const campus: S = (c) => {
  const [g1, g2] = GRASS[c.s] || GRASS.summer;
  return {
    base: (
      <g>
        <Sky c={c} />
        <Brick x={0} y={170} w={130} h={110} c={c} columns />
        <Brick x={260} y={176} w={130} h={104} c={c} columns />
        {/* clock tower */}
        <rect x={160} y={110} width={70} height={170} fill="#a9543a" stroke={OUT} strokeWidth={1.5} />
        <path d="M154 110 L195 54 L236 110 Z" fill={c.s === "winter" ? "#fff" : "#4f6b5c"} stroke={OUT} strokeWidth={1.5} />
        <circle cx={195} cy={140} r={18} fill="#f7f2e4" stroke={OUT} strokeWidth={2} />
        <path d="M195 140 V128 M195 140 L204 145" stroke="#2f2f2f" strokeWidth={2.5} strokeLinecap="round" />
        {[0, 1, 2].map((i) => <rect key={i} x={176 + i * 14} y={178} width={9} height={22} rx={4} fill={lit(c.t) ? "#ffd88a" : "#e9e2d0"} />)}
        <rect x={182} y={240} width={26} height={40} rx={12} fill="#6e4a32" />
        <rect y={276} width={390} height={204} fill={g1} />
        <path d="M0 330 Q195 300 390 330 V480 H0 Z" fill={g2} />
        <path d="M195 280 L120 480 M195 280 L270 480 M0 360 Q195 340 390 360" stroke={c.s === "winter" ? "#cfd9e1" : "#e8d9b8"} strokeWidth={22} fill="none" />
        <Tree x={50} y={360} s={1.1} c={c} />
        <Tree x={345} y={380} s={1.2} c={c} />
        <Tree x={110} y={300} s={0.6} c={c} />
        <Tree x={290} y={300} s={0.6} c={c} />
        <g transform="translate(250 430)">
          <path d="M0 0 V-80" stroke="#2f3a43" strokeWidth={4} />
          <circle cx={0} cy={-86} r={8} fill={lit(c.t) ? "#ffe39a" : "#e9eef2"} stroke="#2f3a43" strokeWidth={2} />
        </g>
      </g>
    ),
    lights: lit(c.t) ? <Glow x={250} y={344} r={50} color="#ffe39a" o={0.7} /> : null,
  };
};

const diningHall: S = (c) => ({
  indoor: true,
  base: (
    <g>
      <rect width={390} height={480} fill="#efe3cf" />
      <path d="M0 0 H390 L300 120 H90 Z" fill="#8a5f3e" />
      {[0, 1, 2, 3, 4].map((i) => <path key={i} d={`M${i * 97.5} 0 L${90 + i * 52.5} 120`} stroke="#6b4a30" strokeWidth={6} />)}
      <path d="M90 120 H300" stroke="#6b4a30" strokeWidth={8} />
      {[[10, 150, 50, 140], [330, 150, 50, 140], [100, 130, 36, 100], [254, 130, 36, 100]].map(([x, y, w, h], i) => (
        <g key={i}>
          <Window x={x} y={y} w={w} h={h} c={c} panes={2} frame="#d8c8ab" />
          <path d={`M${x - 4} ${y} Q${x + w / 2} ${y - w * 0.7} ${x + w + 4} ${y}`} fill="#d8c8ab" stroke={OUT} strokeWidth={1.2} />
        </g>
      ))}
      <rect y={280} width={390} height={200} fill="#b9b2a4" />
      {[300, 340, 400, 470].map((y) => <path key={y} d={`M0 ${y} H390`} stroke="#a59e90" strokeWidth={1.2} />)}
      {[-1, 1].map((side) => {
        const X = (inner: number, outer: number, t: number) => 195 + side * (inner + (outer - inner) * t);
        return (
          <g key={side}>
            {/* outer bench */}
            <path d={`M${X(76, 76, 0)} 276 L${X(84, 84, 0)} 276 L${X(214, 214, 1)} 480 L${X(196, 196, 1)} 480 Z`} fill="#7a5233" stroke={OUT} strokeWidth={1.2} />
            {/* table */}
            <path d={`M${X(26, 26, 0)} 268 L${X(72, 72, 0)} 268 L${X(190, 190, 1)} 480 L${X(60, 60, 1)} 480 Z`} fill="#b9824f" stroke={OUT} strokeWidth={1.5} />
            <path d={`M${X(49, 49, 0)} 268 L${X(125, 125, 1)} 480`} stroke="#9c6b3e" strokeWidth={2} opacity={0.6} />
            {[0.18, 0.38, 0.6, 0.84].map((t, i) => {
              const y = 268 + 212 * t;
              const k = 0.5 + t;
              return (
                <g key={i}>
                  <ellipse cx={X(38, 92, t)} cy={y} rx={8 * k} ry={4 * k} fill="#f6f1e6" stroke={OUT} strokeWidth={1} />
                  <ellipse cx={X(60, 156, t)} cy={y + 4 * k} rx={8 * k} ry={4 * k} fill="#f6f1e6" stroke={OUT} strokeWidth={1} />
                  <rect x={X(50, 124, t) - 2.5 * k} y={y - 8 * k} width={5 * k} height={8 * k} rx={1} fill="#e9f3f7" stroke={OUT} strokeWidth={0.8} />
                </g>
              );
            })}
          </g>
        );
      })}
      {[[195, 140, 1], [120, 110, 0.7], [270, 110, 0.7]].map(([x, y, s], i) => (
        <g key={i} transform={`translate(${x} ${y}) scale(${s})`}>
          <path d="M0 -110 V-20" stroke="#4b3c3a" strokeWidth={2} />
          <ellipse cx={0} cy={-14} rx={30} ry={8} fill="#c9a24e" stroke={OUT} strokeWidth={1.2} />
          {[-22, -8, 8, 22].map((dx) => <rect key={dx} x={dx - 2} y={-26} width={4} height={12} fill="#fff6d8" />)}
        </g>
      ))}
    </g>
  ),
  lights: <>{[[195, 120], [120, 96], [270, 96]].map(([x, y], i) => <Glow key={i} x={x} y={y} r={lit(c.t) ? 90 : 50} color="#ffe2a0" o={lit(c.t) ? 0.5 : 0.25} />)}</>,
});

const stadium: S = (c) => ({
  base: (
    <g>
      <Sky c={c} h={200} />
      {/* far stands */}
      <path d="M0 120 Q195 80 390 120 L390 230 L0 230 Z" fill="#7e8893" />
      {Array.from({ length: 6 }).map((_, r) => (
        <path key={r} d={`M0 ${130 + r * 16} Q195 ${92 + r * 16} 390 ${130 + r * 16}`} stroke={r % 2 ? "#6d7680" : "#8e98a3"} strokeWidth={10} fill="none" />
      ))}
      {Array.from({ length: 160 }).map((_, i) => {
        const x = (i * 37) % 390;
        const r = Math.floor(i / 27);
        const y = 128 + r * 16 - 38 * Math.sin((x / 390) * Math.PI) + 1;
        return <circle key={i} cx={x} cy={y} r={3} fill={["#c8102e", "#ffffff", "#f2c14e", "#2b2b2b", "#3d6fb6"][(i * 7) % 5]} />;
      })}
      <StadiumLights x={30} y={50} c={c} s={0.8} />
      <StadiumLights x={360} y={50} c={c} s={0.8} />
      {/* field */}
      <path d="M-40 230 Q195 200 430 230 L430 380 Q195 350 -40 380 Z" fill={c.s === "winter" ? "#9fbf8a" : "#58a94a"} />
      {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => <path key={i} d={`M${30 + i * 41} ${222 - Math.sin(((30 + i * 41) / 390) * Math.PI) * 18} L${-10 + i * 51} ${370 - Math.sin(((-10 + i * 51) / 390) * Math.PI) * 26}`} stroke="#fff" strokeWidth={1.8} opacity={0.8} />)}
      {/* near stands */}
      <path d="M0 360 Q195 330 390 360 L390 480 L0 480 Z" fill="#5b636c" />
      {Array.from({ length: 4 }).map((_, r) => (
        <g key={r}>
          {Array.from({ length: 20 }).map((__, k) => {
            const x = 10 + k * 20 + (r % 2) * 10;
            const y = 386 + r * 24 - Math.sin((x / 390) * Math.PI) * 20;
            return (
              <g key={k}>
                <rect x={x - 8} y={y} width={16} height={12} rx={3} fill={r % 2 ? "#c8102e" : "#a90c26"} />
                {(k + r) % 3 !== 0 && <circle cx={x} cy={y - 4} r={6} fill={["#e8b38f", "#8a5a3c", "#f3d1b5", "#c48e64", "#5c3a26"][(k + r * 3) % 5]} />}
              </g>
            );
          })}
        </g>
      ))}
    </g>
  ),
  lights: lit(c.t) ? <><Glow x={30} y={40} r={80} color="#fff9d8" o={0.6} /><Glow x={360} y={40} r={80} color="#fff9d8" o={0.6} /></> : null,
});

const ballpark: S = (c) => {
  const [g1, g2] = c.s === "winter" ? ["#a7c494", "#98b886"] : ["#5fb04f", "#52a044"];
  return {
    base: (
      <g>
        <Sky c={c} />
        <path d="M0 160 Q100 130 200 150 T390 140 V200 H0 Z" fill="#6d8f6a" />
        <g>{[30, 120, 210, 300, 370].map((x, i) => <Tree key={i} x={x} y={190} s={0.5} c={c} />)}</g>
        {/* outfield wall with blank board */}
        <path d="M0 190 Q195 170 390 190 L390 222 Q195 202 0 222 Z" fill="#245e3c" stroke={OUT} strokeWidth={1.5} />
        <rect x={150} y={118} width={90} height={52} rx={3} fill="#1f2a33" stroke={OUT} strokeWidth={1.5} />
        {[0, 1, 2, 3].map((i) => <rect key={i} x={158 + i * 20} y={128} width={14} height={10} fill={i % 2 ? "#f2c14e" : "#e9eef2"} opacity={0.85} />)}
        <rect x={158} y={146} width={74} height={14} fill="#2e8f5a" opacity={0.85} />
        <path d="M195 170 V188" stroke="#3b4148" strokeWidth={5} />
        {[[40, 176, "#d95d5d"], [90, 172, "#3d6fb6"], [300, 172, "#f2c14e"], [350, 176, "#5bd18a"]].map(([x, y, col], i) => (
          <rect key={i} x={(x as number) - 18} y={y as number} width={36} height={14} fill={col as string} opacity={0.9} />
        ))}
        <StadiumLights x={28} y={50} c={c} s={0.85} />
        <StadiumLights x={364} y={56} c={c} s={0.8} />
        <path d="M0 218 Q195 196 390 218 L390 480 L0 480 Z" fill={g1} />
        {[0, 1, 2].map((i) => <path key={i} d={`M0 ${240 + i * 34} Q195 ${218 + i * 36} 390 ${240 + i * 34}`} stroke={g2} strokeWidth={14} fill="none" />)}
        <path d="M195 420 L330 330 Q195 236 60 330 Z" fill="#c9915f" />
        <path d="M195 400 L285 340 L195 282 L105 340 Z" fill={g1} />
        <ellipse cx={195} cy={340} rx={18} ry={7} fill="#c9915f" />
        {[[195, 404], [288, 340], [195, 278], [102, 340]].map(([x, y], i) => <rect key={i} x={x - 4.5} y={y - 4.5} width={9} height={9} fill="#fff" transform={`rotate(45 ${x} ${y})`} />)}
        {/* seats & netting */}
        <path d="M0 420 Q195 400 390 420 L390 480 L0 480 Z" fill="#2f6b45" />
        {Array.from({ length: 2 }).map((_, r) => Array.from({ length: 22 }).map((__, k) => {
          const x = 4 + k * 18 + r * 9;
          const y = 432 + r * 22;
          return <rect key={`${r}-${k}`} x={x} y={y} width={14} height={14} rx={3} fill="#1f5233" stroke={OUT} strokeWidth={0.8} />;
        }))}
        <g stroke="#2b2f36" strokeWidth={0.8} opacity={0.25}>
          {Array.from({ length: 40 }).map((_, i) => <path key={i} d={`M${i * 10} 260 V420`} />)}
          {Array.from({ length: 16 }).map((_, i) => <path key={`h${i}`} d={`M0 ${260 + i * 10} H390`} />)}
        </g>
      </g>
    ),
    lights: lit(c.t) ? <><Glow x={28} y={46} r={80} color="#fff9d8" o={0.6} /><Glow x={364} y={50} r={72} color="#fff9d8" o={0.6} /></> : null,
  };
};

export const SCENES: Record<string, S> = {
  home_morning: homeMorning, classroom, school_hall: schoolHall, cafeteria, gym, football_field: footballField, soccer_field: soccerField,
  baseball_field: baseballField, town_green: townGreen, beach, bedroom, dorm, campus, dining_hall: diningHall, stadium, ballpark,
};
export const SCENE_KEYS = Object.keys(SCENES);

function sceneSvg(art: string, season: string, phase: string, id: string) {
  const c: Ctx = { t: timeOf(phase), s: ["spring", "summer", "fall", "winter"].includes(season) ? season : "fall", id };
  const sc = (SCENES[art] || SCENES.town_green)(c);
  const [tc, oOut, oIn] = TINT[c.t];
  const o = sc.indoor ? oIn : oOut;
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={390} height={480} viewBox="0 0 390 480" preserveAspectRatio="xMidYMid slice">
      {sc.base}
      {/* time-of-day tint: a plain see-through layer (mix-blend-mode: multiply here made iPhone Safari stop drawing) */}
      {o > 0 && <rect width={390} height={480} fill={tc} opacity={o * 0.85} />}
      {sc.lights}
    </svg>
  );
}

// Each scene is drawn once (per place, season and time of day) and shown as a flat image. As a live drawing (hundreds of
// shapes) iPhone Safari could fail to redraw it when the page changed around it, leaving the whole Story screen blank a
// moment after it loaded; an image redraws for free.
const IMG_CACHE = new Map<string, string>();

function sceneImage(art: string, season: string, phase: string): string {
  const key = `${art}|${season}|${phase}`;
  let url = IMG_CACHE.get(key);
  if (!url) {
    const markup = renderToStaticMarkup(sceneSvg(art, season, phase, "s" + key.replace(/[^a-zA-Z0-9]/g, "")));
    url = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(markup);
    if (IMG_CACHE.size > 60) IMG_CACHE.clear();
    IMG_CACHE.set(key, url);
  }
  return url;
}

export function SceneArt({ art, season = "fall", phase = "day" }: { art: string; season?: string; phase?: string }) {
  const src = useMemo(() => sceneImage(art, season, phase), [art, season, phase]);
  return (
    <img src={src} alt="" aria-hidden="true" draggable={false} decoding="async"
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
  );
}

export function Scene({ art, season, phase, className, children }: SceneProps) {
  return (
    <div className={["art-scene", className].filter(Boolean).join(" ")} style={{ position: "relative", overflow: "hidden" }}>
      <SceneArt art={art} season={season} phase={phase} />
      <div className="art-scene-c" style={{ position: "relative", zIndex: 1, height: "100%" }}>{children}</div>
    </div>
  );
}
