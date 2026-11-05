// Portraits: a head-and-shoulders bust drawn in SVG from a Look.
// Coordinates live in a 200x200 box; the face is centered at x=100.
import React, { useId } from "react";
import type { Look, Mood } from "../api";
import { EYE_PAL, HAIR_PAL, LONG_STYLES, SKIN_PAL, fullLook, hashStr, shade } from "./looks";

export type PortraitProps = { look?: Look | null; size?: number; mood?: Mood; color?: string; name?: string; ring?: string; shirt?: string; jersey?: number | null };

const INK = "#33242a";
const FACE = "M100 50 C125 50 136 68 136 92 C136 114 125 131 100 138 C75 131 64 114 64 92 C64 68 75 50 100 50 Z";
const TORSO = "M26 206 C28 174 54 157 86 151 Q100 158 114 151 C146 157 172 174 174 206 Z";
const NECK = "M88 122 L88 152 Q100 161 112 152 L112 122 Z";

type HairDef = { back?: string; front?: string; strands?: string[]; extra?: (c: [string, string, string], ink: string) => React.ReactNode;
  shadow?: boolean; soft?: boolean; backTone?: 0 | 1; frontTone?: 0 | 1; noStroke?: boolean };

// Curly outline helper: a ring of bumps following an ellipse arc.
function bumps(cx: number, cy: number, rx: number, ry: number, from: number, to: number, n: number, r: number): string {
  let d = "";
  for (let i = 0; i <= n; i++) {
    const a = ((from + ((to - from) * i) / n) * Math.PI) / 180;
    const x = cx + rx * Math.cos(a);
    const y = cy + ry * Math.sin(a);
    d += `M${(x - r).toFixed(1)} ${y.toFixed(1)} a${r} ${r} 0 1 0 ${2 * r} 0 a${r} ${r} 0 1 0 ${-2 * r} 0 `;
  }
  return d;
}

const CAP_SHORT = "M62 98 C56 64 76 39 102 39 C128 39 145 61 138 98 C136 85 132 77 126 71 C118 75 108 73 100 67 C94 73 84 75 76 71 C70 77 64 86 62 98 Z";

const HAIR: Record<string, HairDef> = {
  bald: {},
  buzz: { front: "M65 90 C63 62 80 46 100 46 C120 46 137 62 135 90 C131 74 120 64 100 64 C80 64 69 74 65 90 Z", soft: true },
  short: { front: CAP_SHORT, shadow: true },
  crew: {
    front: "M63 96 C59 72 64 47 82 40 C94 35 108 35 120 40 C136 47 141 72 137 96 C134 84 130 76 124 72 C112 73 90 73 76 72 C70 77 66 85 63 96 Z",
    extra: (c) => <path d="M80 44 Q100 38 120 44" fill="none" stroke={c[2]} strokeWidth={3} strokeLinecap="round" opacity={0.7} />,
    shadow: true,
  },
  side_part: {
    front: "M62 98 C55 62 76 37 105 37 C131 37 147 60 138 98 C136 83 130 72 120 66 C104 71 84 66 73 57 C66 69 63 82 62 98 Z",
    extra: (c) => <>
      <path d="M79 43 Q76 51 73 58" fill="none" stroke={c[1]} strokeWidth={2.5} strokeLinecap="round" />
      <path d="M88 44 Q108 44 128 58" fill="none" stroke={c[2]} strokeWidth={3} strokeLinecap="round" opacity={0.6} />
    </>,
    shadow: true,
  },
  messy: {
    front: "M62 98 C56 72 62 52 71 46 L67 33 L82 41 L86 27 L97 38 L106 25 L112 38 L125 29 L125 43 L138 41 C143 55 145 75 138 98 C136 86 132 78 126 72 C121 78 113 72 107 66 C101 74 90 76 82 70 C76 78 66 86 62 98 Z",
    extra: (c) => <path d="M90 46 Q100 40 112 46" fill="none" stroke={c[2]} strokeWidth={3} strokeLinecap="round" opacity={0.6} />,
    shadow: true,
  },
  curly_short: {
    front: "M62 98 C56 66 74 42 100 42 C126 42 144 66 138 98 C135 84 128 74 118 70 C106 74 94 74 82 70 C72 74 65 84 62 98 Z",
    extra: (c, ink) => <g>
      <path d={bumps(100, 66, 36, 26, 176, 364, 13, 7)} fill={c[0]} stroke={ink} strokeWidth={1.8} />
      <path d="M68 70 C70 52 84 44 100 44 C116 44 130 52 132 70 Z" fill={c[0]} />
      {[[84, 54], [100, 50], [116, 54], [92, 62], [108, 62]].map(([x, y], i) => <path key={i} d={`M${x - 4} ${y} q4 -5 8 0`} fill="none" stroke={c[2]} strokeWidth={2} strokeLinecap="round" opacity={0.6} />)}
    </g>,
    shadow: true,
  },
  fade: {
    front: "M67 84 C63 57 79 39 100 39 C121 39 137 57 133 84 L127 71 C118 67 108 65.5 100 65.5 C92 65.5 82 67 73 71 Z",
    extra: (c) => <>
      <path d="M65 99 C63 90 64 82 67 78 L72 74 L72 97 Z" fill={c[0]} opacity={0.32} />
      <path d="M135 99 C137 90 136 82 133 78 L128 74 L128 97 Z" fill={c[0]} opacity={0.32} />
      <path d="M84 44 Q100 38 116 44" fill="none" stroke={c[2]} strokeWidth={3} strokeLinecap="round" opacity={0.6} />
    </>,
    shadow: true,
  },
  afro: {
    back: "M100 18 C138 18 158 44 158 78 C158 102 150 116 140 122 L60 122 C50 116 42 102 42 78 C42 44 62 18 100 18 Z",
    backTone: 0,
    extra: (c, ink) => <g>
      <path d={bumps(100, 76, 55, 55, 150, 390, 26, 6.5)} fill={c[0]} stroke={ink} strokeWidth={1.8} />
      <path d="M100 18 C138 18 158 44 158 78 C158 102 150 116 140 122 L60 122 C50 116 42 102 42 78 C42 44 62 18 100 18 Z" fill={c[0]} />
      <path d="M70 40 Q84 30 100 29" fill="none" stroke={c[2]} strokeWidth={4} strokeLinecap="round" opacity={0.45} />
    </g>,
    front: "M64 94 C62 72 74 58 100 58 C126 58 138 72 136 94 C130 80 118 70 100 70 C82 70 70 80 64 94 Z",
    frontTone: 0, noStroke: true,
    shadow: true,
  },
  bob: {
    back: "M60 112 L140 112 L143 140 C120 146 80 146 57 140 Z",
    front: "M54 139 C49 100 52 60 76 44 C86 38 114 38 124 44 C148 60 151 100 146 139 C138 143 130 142 124 138 C127 118 129 98 129 77 C116 74 104 70 96 66 C90 72 80 76 71 77 C71 98 73 118 76 138 C70 142 62 143 54 139 Z",
    extra: (c) => <path d="M80 48 Q100 41 120 48" fill="none" stroke={c[2]} strokeWidth={3} strokeLinecap="round" opacity={0.65} />,
    shadow: true,
  },
  long_straight: {
    back: "M58 94 C54 60 74 38 100 38 C126 38 146 60 142 94 L150 182 C134 190 118 186 110 180 L90 180 C82 186 66 190 50 182 Z",
    front: "M100 44 C80 44 63 57 61 80 C59 106 61 140 69 173 L84 171 C77 146 74 118 75 96 C78 80 86 66 98 57 L100 51 L102 57 C114 66 122 80 125 96 C126 118 123 146 116 171 L131 173 C139 140 141 106 139 80 C137 57 120 44 100 44 Z",
    extra: (c) => <g fill="none" stroke={c[2]} strokeWidth={2.5} strokeLinecap="round" opacity={0.55}>
      <path d="M90 52 Q76 62 70 84" /><path d="M110 52 Q124 62 130 84" />
    </g>,
    shadow: true,
  },
  long_wavy: {
    back: "M56 94 C52 58 74 36 100 36 C126 36 148 58 144 94 C152 114 142 128 150 146 C158 164 146 182 132 184 L68 184 C54 182 42 164 50 146 C58 128 48 114 56 94 Z",
    front: "M100 43 C79 43 63 56 61 78 C59 96 67 110 61 128 C56 146 64 164 74 175 L85 170 C77 160 72 148 77 136 C84 118 72 104 76 92 C82 76 94 64 110 58 C120 68 126 80 125 94 C128 106 118 120 124 136 C128 148 122 160 115 170 L126 175 C136 164 144 146 139 128 C133 110 141 96 139 78 C137 56 121 43 100 43 Z",
    extra: (c) => <g fill="none" stroke={c[2]} strokeWidth={2.5} strokeLinecap="round" opacity={0.55}>
      <path d="M86 52 Q72 64 68 86" /><path d="M116 54 Q128 64 132 84" />
    </g>,
    shadow: true,
  },
  ponytail: {
    back: "M126 56 C152 58 160 90 154 120 C150 140 142 156 134 166 C136 140 140 114 132 86 Z",
    front: "M64 96 C60 64 78 43 100 43 C122 43 140 64 136 96 C132 81 126 70 116 64 C104 61 90 61 82 66 C72 74 66 84 64 96 Z",
    extra: (c) => <>
      <path d="M78 52 Q100 44 122 54" fill="none" stroke={c[2]} strokeWidth={2.5} strokeLinecap="round" opacity={0.7} />
      <circle cx={130} cy={60} r={5} fill="#d84a6a" stroke={INK} strokeWidth={1.5} />
    </>,
    shadow: true,
  },
  bun: {
    back: "M100 14 C112 14 120 22 120 32 C120 42 112 50 100 50 C88 50 80 42 80 32 C80 22 88 14 100 14 Z",
    front: "M64 96 C60 64 78 43 100 43 C122 43 140 64 136 96 C132 81 126 70 116 64 C104 61 90 61 82 66 C72 74 66 84 64 96 Z",
    extra: (c) => <path d="M80 50 Q100 43 120 50" fill="none" stroke={c[2]} strokeWidth={2.5} strokeLinecap="round" opacity={0.7} />,
    shadow: true,
  },
  curly_long: {
    back: "M52 92 C48 54 72 32 100 32 C128 32 152 54 148 92 L156 176 C140 186 120 184 110 178 L90 178 C80 184 60 186 44 176 Z",
    backTone: 0,
    extra: (c, ink) => <g>
      <path d={bumps(100, 110, 52, 70, -100, 280, 34, 7)} fill={c[0]} stroke={ink} strokeWidth={1.7} />
      <path d="M52 92 C48 54 72 32 100 32 C128 32 152 54 148 92 L154 172 C140 180 120 180 110 176 L90 176 C80 180 60 180 46 172 Z" fill={c[0]} />
      {[[60, 120], [64, 146], [140, 120], [136, 146], [58, 96], [142, 96]].map(([x, y], i) => <path key={i} d={`M${x - 5} ${y} q5 -6 10 0 q-5 6 -10 0`} fill="none" stroke={c[1]} strokeWidth={1.8} opacity={0.7} />)}
    </g>,
    front: "M63 98 C58 64 77 43 100 43 C123 43 142 64 137 98 C133 82 124 72 112 68 Q106 74 100 70 Q94 74 88 68 C76 72 67 82 63 98 Z",
    frontTone: 0,
    shadow: true,
  },
  braids: {
    back: "M58 94 C54 60 74 38 100 38 C126 38 146 60 142 94 L148 184 L52 184 Z",
    front: "M64 98 C60 62 78 43 100 43 C122 43 140 62 136 98 C132 80 122 66 104 62 L100 52 L96 62 C78 66 68 80 64 98 Z",
    strands: ["M64 88 L60 178 L70 178 L74 92 Z", "M136 88 L140 178 L130 178 L126 92 Z"],
    extra: (c) => <g stroke={c[1]} strokeWidth={1.6} opacity={0.9}>
      {[100, 112, 124, 136, 148, 160, 172].map((y) => <React.Fragment key={y}>
        <path d={`M61 ${y} l11 5`} /><path d={`M139 ${y} l-11 5`} />
      </React.Fragment>)}
      <path d="M100 52 L100 62" stroke={c[1]} />
    </g>,
    shadow: true,
  },
  locs: {
    back: "M58 94 C54 60 74 38 100 38 C126 38 146 60 142 94 L146 168 L54 168 Z",
    front: "M64 98 C60 62 78 43 100 43 C122 43 140 62 136 98 C130 80 120 70 100 68 C80 70 70 80 64 98 Z",
    extra: (c, ink) => <g>
      {[[58, 84, 166, -3], [66, 90, 172, -1], [74, 92, 160, 1], [126, 92, 160, -1], [134, 90, 172, 1], [142, 84, 166, 3]].map(([x, y0, y1, k], i) => (
        <path key={i} d={`M${x} ${y0} C${x + k * 3} ${(y0 + y1) / 2} ${x - k * 2} ${y1 - 20} ${x + k} ${y1}`} fill="none" stroke={ink} strokeWidth={9.5} strokeLinecap="round" />
      ))}
      {[[58, 84, 166, -3], [66, 90, 172, -1], [74, 92, 160, 1], [126, 92, 160, -1], [134, 90, 172, 1], [142, 84, 166, 3]].map(([x, y0, y1, k], i) => (
        <path key={"i" + i} d={`M${x} ${y0} C${x + k * 3} ${(y0 + y1) / 2} ${x - k * 2} ${y1 - 20} ${x + k} ${y1}`} fill="none" stroke={c[0]} strokeWidth={6.5} strokeLinecap="round" />
      ))}
      {[80, 90, 100, 110, 120].map((x, i) => <path key={i} d={`M${x} 47 Q${x + 2} 56 ${x - 1} 65`} fill="none" stroke={c[1]} strokeWidth={2} opacity={0.7} />)}
    </g>,
    shadow: true,
  },
};

const BROWS: Record<string, [string, string]> = {
  neutral: ["M78 85 Q86 81 94 84", "M106 84 Q114 81 122 85"],
  happy: ["M78 83 Q86 78.5 94 82", "M106 82 Q114 78.5 122 83"],
  sad: ["M78 86 Q86 84.5 94 80", "M106 80 Q114 84.5 122 86"],
  angry: ["M78 81 Q86 83 94 88", "M106 88 Q114 83 122 81"],
  surprised: ["M78 80 Q86 73.5 94 79", "M106 79 Q114 73.5 122 80"],
  flirty: ["M78 84 Q86 80 94 83", "M106 80 Q114 75 122 79"],
  tired: ["M78 87 Q86 85.5 94 87", "M106 87 Q114 85.5 122 87"],
};

function Eye({ cx, mood, iris, skin, line, side, lash }: { cx: number; mood: string; iris: string; skin: string; line: string; side: -1 | 1; lash: boolean }) {
  const cy = 97;
  const big = mood === "surprised" ? 1.12 : 1;
  const w = 8.6 * big, h = 6.1 * big;
  const white = `M${cx - w} ${cy} Q${cx} ${cy - h * 1.35} ${cx + w} ${cy} Q${cx} ${cy + h} ${cx - w} ${cy} Z`;
  const r = mood === "surprised" ? 3.8 : 4.7;
  const ix = cx + side * 0.4;
  let lid: React.ReactNode = null;
  if (mood === "tired") lid = <path d={`M${cx - w - 1} ${cy - 0.5} Q${cx} ${cy - h * 1.6} ${cx + w + 1} ${cy - 0.5} L${cx + w + 1} ${cy - 8} L${cx - w - 1} ${cy - 8} Z`} fill={skin} />;
  if (mood === "flirty" && side === 1) lid = <path d={`M${cx - w - 1} ${cy - 1} Q${cx} ${cy - h * 1.5} ${cx + w + 1} ${cy - 1} L${cx + w + 1} ${cy - 9} L${cx - w - 1} ${cy - 9} Z`} fill={skin} />;
  if (mood === "angry") lid = <path d={side === -1 ? `M${cx - w - 1} ${cy - 7} L${cx + w + 1} ${cy - 1} L${cx + w + 1} ${cy - 9} Z` : `M${cx + w + 1} ${cy - 7} L${cx - w - 1} ${cy - 1} L${cx - w - 1} ${cy - 9} Z`} fill={skin} />;
  if (mood === "sad") lid = <path d={side === -1 ? `M${cx - w - 1} ${cy - 1} L${cx + w + 1} ${cy - 7} L${cx - w - 1} ${cy - 9} Z` : `M${cx + w + 1} ${cy - 1} L${cx - w - 1} ${cy - 7} L${cx + w + 1} ${cy - 9} Z`} fill={skin} />;
  const happyLower = mood === "happy" ? <path d={`M${cx - w - 1} ${cy + 3.2} Q${cx} ${cy - 1.2} ${cx + w + 1} ${cy + 3.2} L${cx + w + 1} ${cy + 8} L${cx - w - 1} ${cy + 8} Z`} fill={skin} /> : null;
  return (
    <g>
      <path d={white} fill="#fffaf6" />
      <circle cx={ix} cy={cy - 0.4} r={r} fill={iris} />
      <circle cx={ix} cy={cy - 0.4} r={r * 0.5} fill="#1a1214" />
      <circle cx={ix + 1.5} cy={cy - 2.1} r={1.35} fill="#fff" />
      <circle cx={ix - 1.6} cy={cy + 1.2} r={0.6} fill="#fff" opacity={0.8} />
      {lid}
      {happyLower}
      <path d={`M${cx - w - 0.6} ${cy + 0.2} Q${cx} ${cy - h * 1.45} ${cx + w + 0.6} ${cy - 0.2}`} fill="none" stroke={line} strokeWidth={2.4} strokeLinecap="round" />
      {lash && <path d={side === -1 ? `M${cx - w - 0.4} ${cy} l-3 -2.4` : `M${cx + w + 0.4} ${cy} l3 -2.4`} stroke={line} strokeWidth={2} strokeLinecap="round" />}
    </g>
  );
}

function Mouth({ mood, lip }: { mood: string; lip: string }) {
  const s = { fill: "none", stroke: lip, strokeWidth: 2.4, strokeLinecap: "round" as const };
  switch (mood) {
    case "happy":
      return <g>
        <path d="M88.5 119 Q100 121.5 111.5 119 Q107.5 132 100 132 Q92.5 132 88.5 119 Z" fill="#8b3439" stroke={lip} strokeWidth={1.6} strokeLinejoin="round" />
        <path d="M90.5 120 Q100 122 109.5 120 L108.5 123.2 Q100 124.6 91.5 123.2 Z" fill="#fff" />
        <path d="M94 129 Q100 125.5 106 129 Q103 131.4 100 131.4 Q97 131.4 94 129 Z" fill="#e0737d" />
      </g>;
    case "sad":
      return <path d="M92 125.5 Q100 119.5 108 125.5" {...s} />;
    case "angry":
      return <path d="M92 124 Q100 120.5 108 124" {...s} />;
    case "surprised":
      return <ellipse cx={100} cy={124} rx={4.2} ry={5.2} fill="#7d3236" stroke={lip} strokeWidth={1.4} />;
    case "flirty":
      return <path d="M92 121.5 Q102 126 109.5 119" {...s} />;
    case "tired":
      return <path d="M93.5 122.5 Q100 123.5 106.5 122.5" {...s} />;
    default:
      return <path d="M92 121 Q100 125.5 108 121" {...s} />;
  }
}

function FacialHair({ kind, c, ink }: { kind: string; c: [string, string, string]; ink: string }) {
  const stache = "M87.5 117.5 Q93.5 111.5 100 114.5 Q106.5 111.5 112.5 117.5 Q106 116 100 117.6 Q94 116 87.5 117.5 Z";
  if (kind === "stubble")
    return <g opacity={0.24} fill={c[0]}>
      <path d="M66 104 C68 122 82 134 100 138 C118 134 132 122 134 104 C130 116 122 124 112 127 Q100 131 88 127 C78 124 70 116 66 104 Z" />
      <path d="M89 116.5 Q100 112.5 111 116.5 Q100 118.6 89 116.5 Z" />
    </g>;
  if (kind === "mustache") return <path d={stache} fill={c[0]} stroke={ink} strokeWidth={1.2} />;
  if (kind === "goatee")
    return <g fill={c[0]} stroke={ink} strokeWidth={1.2}>
      <path d={stache} />
      <path d="M93 128.5 Q100 126.5 107 128.5 Q106.5 137.5 100 138.6 Q93.5 137.5 93 128.5 Z" />
    </g>;
  if (kind === "beard")
    return <g fill={c[0]} stroke={ink} strokeWidth={1.4} strokeLinejoin="round">
      <path d="M65 96 C65 122 80 140 100 143 C120 140 135 122 135 96 C132 110 127 119 119 124 Q109 119.5 100 125.5 Q91 119.5 81 124 C73 119 68 110 65 96 Z" />
      <path d={stache} />
    </g>;
  return null;
}

export function Portrait({ look, size = 56, mood = "neutral", color, name, ring, shirt, jersey }: PortraitProps) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const L = look && look.skin ? look : fullLook(look as any, name || "someone");
  const [skin, skinShade, skinLine, blush] = SKIN_PAL[L.skin] || SKIN_PAL.light;
  const hc = HAIR_PAL[L.hair_color] || HAIR_PAL.brown;
  const hairInk = shade(hc[1], -0.35);
  const iris = EYE_PAL[L.eyes] || EYE_PAL.brown;
  const H = HAIR[L.hair] || HAIR.short;
  const tint = color || ["#8fb6d9", "#e9a8b8", "#a8d5b5", "#f2c58f", "#b9a8e6", "#9ed3d8", "#f0b49a"][hashStr(name || `${L.skin}${L.hair}${L.hair_color}`) % 7];
  const bgA = shade(tint, 0.72);
  const bgB = shade(tint, 0.45);
  const top = shirt || (color ? shade(color, -0.15) : ["#3f6fb5", "#c4566a", "#4b8b6a", "#7a5cb3", "#d08a35", "#2f8f9d"][hashStr(name || L.skin) % 6]);
  const isJersey = typeof jersey === "number";
  const lash = LONG_STYLES.has(L.hair);
  const lip = shade(skinLine, -0.05);
  const clip = `pc${uid}`, faceClip = `pf${uid}`, bg = `pb${uid}`;
  return (
    <svg width={size} height={size} viewBox="17 15 166 166" role="img" aria-label={name || "portrait"} style={{ display: "block", flexShrink: 0 }}>
      <defs>
        <clipPath id={clip}><circle cx={100} cy={98} r={83} /></clipPath>
        <clipPath id={faceClip}><path d={FACE} /></clipPath>
        <radialGradient id={bg} cx="50%" cy="38%" r="70%">
          <stop offset="0%" stopColor={bgA} />
          <stop offset="100%" stopColor={bgB} />
        </radialGradient>
      </defs>
      <g clipPath={`url(#${clip})`}>
        <rect width={200} height={200} fill={`url(#${bg})`} />
        {/* hair behind */}
        {H.back && <path d={H.back} fill={hc[H.backTone ?? 1]} stroke={hairInk} strokeWidth={2} strokeLinejoin="round" />}
        {L.hair === "afro" || L.hair === "curly_long" ? H.extra?.(hc, hairInk) : null}
        {/* body */}
        <path d={TORSO} fill={isJersey ? "#1f6b3c" : top} stroke={INK} strokeWidth={2.2} strokeLinejoin="round" />
        {isJersey ? (
          <g>
            <path d="M40 176 C47 166 58 160 70 157" fill="none" stroke="#fff" strokeWidth={6} strokeLinecap="round" />
            <path d="M160 176 C153 166 142 160 130 157" fill="none" stroke="#fff" strokeWidth={6} strokeLinecap="round" />
            <text x={127} y={173} textAnchor="middle" fontFamily="'Fredoka', 'Nunito', system-ui, sans-serif" fontWeight={800} fontSize={15}
              fill="#fff" stroke="#123f23" strokeWidth={1.4} paintOrder="stroke">{jersey}</text>
          </g>
        ) : (
          <path d="M150 168 C160 176 168 188 172 206 L152 206 C152 190 150 178 150 168 Z" fill={shade(top, -0.18)} opacity={0.6} />
        )}
        <path d={NECK} fill={skin} stroke={INK} strokeWidth={2.2} strokeLinejoin="round" />
        <path d="M88 126 Q100 140 112 126 L112 138 Q100 149 88 138 Z" fill={skinShade} />
        {isJersey ? <path d="M86 151 L100 167 L114 151" fill="none" stroke="#fff" strokeWidth={4.5} strokeLinejoin="round" />
          : <path d="M85 151.5 Q100 166 115 151.5" fill="none" stroke={shade(top, -0.3)} strokeWidth={3} strokeLinecap="round" />}
        {/* ears */}
        <ellipse cx={64.5} cy={99} rx={6.5} ry={10} fill={skin} stroke={INK} strokeWidth={2.2} />
        <ellipse cx={135.5} cy={99} rx={6.5} ry={10} fill={skin} stroke={INK} strokeWidth={2.2} />
        <path d="M63 95 Q66 99 63.5 103" fill="none" stroke={skinShade} strokeWidth={2} strokeLinecap="round" />
        <path d="M137 95 Q134 99 136.5 103" fill="none" stroke={skinShade} strokeWidth={2} strokeLinecap="round" />
        {/* face */}
        <path d={FACE} fill={skin} />
        <g clipPath={`url(#${faceClip})`}>
          <path d="M126 70 C136 88 134 116 112 134 C130 128 140 110 140 90 C140 82 134 74 126 70 Z" fill={skinShade} opacity={0.55} />
          {H.front && H.shadow && <path d={H.front} transform="translate(1.5 5)" fill={skinShade} opacity={0.7} />}
          {H.strands && H.shadow && H.strands.map((d, i) => <path key={i} d={d} transform="translate(0 4)" fill={skinShade} opacity={0.5} />)}
        </g>
        <path d={FACE} fill="none" stroke={INK} strokeWidth={2.2} />
        {L.freckles && (
          <g fill={shade(skinShade, -0.15)} opacity={0.75}>
            {[[80, 106], [84.5, 108.5], [78, 110.5], [88.5, 106.5], [120, 106], [115.5, 108.5], [122, 110.5], [111.5, 106.5]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r={1} />)}
          </g>
        )}
        {(mood === "flirty" || mood === "happy") && (
          <g fill={blush} opacity={mood === "flirty" ? 0.42 : 0.22}>
            <ellipse cx={80} cy={110} rx={7} ry={3.6} />
            <ellipse cx={120} cy={110} rx={7} ry={3.6} />
          </g>
        )}
        <Eye cx={86} mood={mood} iris={iris} skin={skin} line={INK} side={-1} lash={lash} />
        <Eye cx={114} mood={mood} iris={iris} skin={skin} line={INK} side={1} lash={lash} />
        <g fill="none" stroke={L.hair === "bald" ? shade(skinLine, -0.1) : hc[1]} strokeWidth={4} strokeLinecap="round">
          <path d={BROWS[mood]?.[0] || BROWS.neutral[0]} />
          <path d={BROWS[mood]?.[1] || BROWS.neutral[1]} />
        </g>
        <path d="M100.5 100 Q97 107.5 98.6 110.4 Q101 111.8 104 110" fill="none" stroke={skinLine} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" opacity={0.75} />
        <FacialHair kind={L.facial_hair} c={hc} ink={hairInk} />
        <Mouth mood={mood} lip={lip} />
        {/* hair in front */}
        {H.strands?.map((d, i) => <path key={i} d={d} fill={hc[0]} stroke={hairInk} strokeWidth={2} strokeLinejoin="round" />)}
        {H.front && (H.soft
          ? <path d={H.front} fill={hc[0]} opacity={0.82} />
          : <path d={H.front} fill={hc[H.frontTone ?? 0]} stroke={H.noStroke ? "none" : hairInk} strokeWidth={2} strokeLinejoin="round" />)}
        {L.hair !== "afro" && L.hair !== "curly_long" ? H.extra?.(hc, hairInk) : null}
        {L.hair === "bald" && <path d="M84 60 Q96 54 110 57" fill="none" stroke="#fff" strokeWidth={4} strokeLinecap="round" opacity={0.35} />}
        {L.glasses && (
          <g fill="rgba(255,255,255,0.14)" stroke="#2b2733" strokeWidth={2.4}>
            <rect x={74.5} y={89} width={23} height={16} rx={6} />
            <rect x={102.5} y={89} width={23} height={16} rx={6} />
            <path d="M97.5 95.5 Q100 93 102.5 95.5" fill="none" />
            <path d="M74.5 94 L65 92" fill="none" />
            <path d="M125.5 94 L135 92" fill="none" />
          </g>
        )}
      </g>
      {ring && <circle cx={100} cy={98} r={80} fill="none" stroke={ring} strokeWidth={6} />}
    </svg>
  );
}
