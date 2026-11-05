// Pet illustrations: sitting dogs, cats and rabbits in the same style as the portraits.
import React, { useId } from "react";
import { shade } from "./looks";

export type PetArtProps = { species: string; coat?: string; breed?: string; mood?: string; size?: number };

const INK = "#33242a";
const COAT: Record<string, [string, string]> = {
  // [main, light]
  golden: ["#dca456", "#f1d3a0"], black: ["#2e2a2b", "#5a5354"], chocolate: ["#6b4229", "#9a6b4b"], cream: ["#efdcb6", "#fbf1dc"],
  tricolor: ["#2e2a2b", "#f6efe4"], brindle: ["#8a5a35", "#c49a6b"], gray: ["#8f9399", "#c9ccd1"], white: ["#f6f2ea", "#ffffff"],
  orange: ["#e38b3c", "#f6c998"], calico: ["#f6efe4", "#ffffff"], tabby: ["#9c8a76", "#d4c6b4"], brown: ["#8a5d3b", "#c49a72"],
  spotted: ["#f6f2ea", "#ffffff"],
};

type Mood = "thrilled" | "happy" | "okay" | "mopey" | "miserable";
function moodOf(m?: string): Mood {
  return (["thrilled", "happy", "okay", "mopey", "miserable"].includes(m || "") ? m : "happy") as Mood;
}

function Eyes({ y, dx, mood, iris = "#2a1c18", cat = false }: { y: number; dx: number; mood: Mood; iris?: string; cat?: boolean }) {
  const xs = [100 - dx, 100 + dx];
  if (mood === "thrilled" || (mood === "happy" && cat)) {
    return <g fill="none" stroke={INK} strokeWidth={3.4} strokeLinecap="round">{xs.map((x) => <path key={x} d={`M${x - 6} ${y + 2} Q${x} ${y - 6} ${x + 6} ${y + 2}`} />)}</g>;
  }
  if (mood === "mopey" || mood === "miserable") {
    return (
      <g>
        {xs.map((x) => (
          <g key={x}>
            <ellipse cx={x} cy={y + 1} rx={5.4} ry={5} fill={iris} />
            <path d={`M${x - 7} ${y - 1} L${x + 7} ${y - 1} L${x + 7} ${y - 7} L${x - 7} ${y - 7} Z`} fill="currentColor" />
            <path d={`M${x - 6.5} ${y - 1.5} Q${x} ${y + 1} ${x + 6.5} ${y - 1.5}`} fill="none" stroke={INK} strokeWidth={2.4} strokeLinecap="round" />
          </g>
        ))}
        {mood === "miserable" && <path d={`M${xs[1] + 3} ${y + 6} q-3 6 0 9 q3 -3 0 -9`} fill="#8fd0ff" stroke="#4a8fc4" strokeWidth={1} />}
      </g>
    );
  }
  return (
    <g>
      {xs.map((x) => (
        <g key={x}>
          {cat ? <ellipse cx={x} cy={y} rx={6.5} ry={7} fill={iris} /> : <ellipse cx={x} cy={y} rx={5.6} ry={6.2} fill={iris} />}
          {cat && <ellipse cx={x} cy={y} rx={1.8} ry={5.4} fill="#151012" />}
          <circle cx={x + 2} cy={y - 2.4} r={1.9} fill="#fff" />
        </g>
      ))}
    </g>
  );
}

function Dog({ coat, breed, mood }: { coat: string; breed: string; mood: Mood }) {
  const [main, light] = COAT[coat] || COAT.golden;
  const dark = shade(main, -0.25);
  const b = breed.toLowerCase();
  const pointed = /shepherd|corgi|collie|husky/.test(b);
  const small = /corgi|beagle/.test(b);
  const curly = /doodle|poodle/.test(b);
  const mix = /mix/.test(b);
  const boxer = /boxer/.test(b);
  const tri = coat === "tricolor" || /bernese|beagle/.test(b);
  const down = mood === "mopey" || mood === "miserable";
  const happy = mood === "happy" || mood === "thrilled";
  const s = small ? 0.88 : 1;
  const tail = happy ? "M138 156 Q170 140 164 104" : down ? "M136 168 Q156 182 170 184" : "M138 160 Q166 156 172 134";
  const earL = pointed
    ? (down ? "M74 70 L48 52 L80 54 Z" : "M74 66 L66 30 L92 54 Z")
    : boxer ? "M72 62 Q60 66 64 84 Q74 78 80 66 Z"
      : (down ? "M72 62 C56 70 52 104 64 114 C72 108 78 92 80 68 Z" : "M72 60 C56 64 54 98 64 108 C72 104 78 88 80 66 Z");
  const earR = pointed
    ? (down ? "M126 70 L152 52 L120 54 Z" : "M126 66 L134 30 L108 54 Z")
    : boxer ? "M128 62 Q140 66 136 84 Q126 78 120 66 Z"
      : (down ? "M128 62 C144 70 148 104 136 114 C128 108 122 92 120 68 Z" : "M128 60 C144 64 146 98 136 108 C128 104 122 88 120 66 Z");
  const earR2 = mix && !down ? "M126 66 L134 32 L108 54 Z" : earR;
  return (
    <g transform={`translate(${100 - 100 * s} ${200 - 200 * s}) scale(${s})`} color={main}>
      <path d={tail} fill="none" stroke={INK} strokeWidth={15} strokeLinecap="round" />
      <path d={tail} fill="none" stroke={tri ? "#2e2a2b" : main} strokeWidth={10} strokeLinecap="round" />
      {/* body */}
      <path d={small ? "M60 186 C56 160 70 124 100 120 C130 124 144 160 140 186 Z" : "M62 186 C58 152 72 112 100 108 C128 112 142 152 138 186 Z"} fill={tri ? "#2e2a2b" : main} stroke={INK} strokeWidth={3} />
      {coat === "brindle" && <g stroke={dark} strokeWidth={3} opacity={0.6}>{[120, 132, 144, 156, 168].map((y) => <path key={y} d={`M68 ${y} q10 4 18 -2 M114 ${y} q10 4 18 -2`} />)}</g>}
      <ellipse cx={100} cy={152} rx={20} ry={28} fill={tri ? "#f6efe4" : light} />
      {/* legs */}
      {[86, 114].map((x) => (
        <g key={x}>
          <rect x={x - 7} y={small ? 150 : 140} width={14} height={small ? 34 : 44} rx={7} fill={tri ? "#f6efe4" : main} stroke={INK} strokeWidth={3} />
          <ellipse cx={x} cy={185} rx={9} ry={5} fill={tri ? "#f6efe4" : light} stroke={INK} strokeWidth={2.6} />
        </g>
      ))}
      {/* collar */}
      <path d="M76 112 Q100 124 124 112" fill="none" stroke="#d84a5a" strokeWidth={7} strokeLinecap="round" />
      <circle cx={100} cy={124} r={5} fill="#f2c14e" stroke={INK} strokeWidth={1.6} />
      {/* ears (behind head) */}
      <path d={earL} fill={tri ? "#2e2a2b" : pointed ? main : dark} stroke={INK} strokeWidth={3} strokeLinejoin="round" />
      <path d={earR2} fill={tri ? "#2e2a2b" : (pointed || (mix && !down)) ? main : dark} stroke={INK} strokeWidth={3} strokeLinejoin="round" />
      {pointed && !down && <><path d="M75 60 L70 40 L86 54 Z" fill="#e7a7a0" /><path d="M125 60 L130 40 L114 54 Z" fill="#e7a7a0" /></>}
      {/* head */}
      <path d="M100 46 C124 46 136 62 136 82 C136 102 122 114 100 114 C78 114 64 102 64 82 C64 62 76 46 100 46 Z" fill={tri ? "#8a5a35" : main} stroke={INK} strokeWidth={3} />
      {tri && <path d="M88 48 Q100 44 112 48 L106 84 L94 84 Z" fill="#f6efe4" />}
      {/^german/.test(b) && <path d="M70 70 Q100 50 130 70 Q122 58 100 54 Q78 58 70 70 Z" fill="#2e2a2b" opacity={0.8} />}
      {curly && <g fill={main} stroke={INK} strokeWidth={2.4}>{[[78, 54], [90, 46], [104, 44], [118, 50], [126, 60]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r={9} />)}</g>}
      {/* muzzle */}
      <ellipse cx={100} cy={boxer ? 96 : 97} rx={boxer ? 18 : 16} ry={boxer ? 11 : 13} fill={tri || coat === "black" || coat === "chocolate" ? "#f2e6d4" : light} />
      <g color={tri ? "#8a5a35" : main}><Eyes y={78} dx={14} mood={mood} /></g>
      <path d="M93 89 Q100 85 107 89 Q106 95 100 96 Q94 95 93 89 Z" fill="#2a1c18" />
      <ellipse cx={98} cy={88.5} rx={2} ry={1.2} fill="#fff" opacity={0.6} />
      <path d="M100 96 V100 M100 100 Q94 106 88 102 M100 100 Q106 106 112 102" fill="none" stroke={INK} strokeWidth={2.4} strokeLinecap="round" />
      {happy && <path d="M95 103 Q100 118 105 103 Z" fill="#ec7a86" stroke={INK} strokeWidth={1.8} />}
      {mood === "thrilled" && <g fill="#ffd166">{[[52, 40], [150, 36], [160, 70]].map(([x, y], i) => <path key={i} d={`M${x} ${y - 6} L${x + 2} ${y - 2} L${x + 6} ${y} L${x + 2} ${y + 2} L${x} ${y + 6} L${x - 2} ${y + 2} L${x - 6} ${y} L${x - 2} ${y - 2} Z`} />)}</g>}
    </g>
  );
}

function Cat({ coat, mood }: { coat: string; mood: Mood }) {
  const [main, light] = COAT[coat] || COAT.gray;
  const down = mood === "mopey" || mood === "miserable";
  const happy = mood === "happy" || mood === "thrilled";
  const body = coat === "calico" ? "#f6efe4" : main;
  const stripe = coat === "tabby" ? "#6b5a48" : coat === "orange" ? "#c46a22" : coat === "gray" ? "#6f737a" : null;
  const tail = happy ? "M132 176 Q170 170 164 118 Q162 104 152 102" : "M132 182 Q176 186 168 160";
  return (
    <g color={body}>
      <path d={tail} fill="none" stroke={INK} strokeWidth={13} strokeLinecap="round" />
      <path d={tail} fill="none" stroke={coat === "calico" ? "#2e2a2b" : main} strokeWidth={8} strokeLinecap="round" />
      <path d="M66 188 C60 150 74 112 100 108 C126 112 140 150 134 188 Z" fill={body} stroke={INK} strokeWidth={3} />
      {coat === "calico" && <><path d="M70 150 Q80 128 98 132 Q92 160 70 170 Z" fill="#e38b3c" /><path d="M110 140 Q130 136 132 160 Q120 168 108 158 Z" fill="#2e2a2b" /></>}
      {stripe && <g stroke={stripe} strokeWidth={3.4} strokeLinecap="round" opacity={0.75}>{[128, 142, 156].map((y) => <path key={y} d={`M70 ${y} q8 3 14 -1 M116 ${y} q8 3 14 -1`} />)}</g>}
      <ellipse cx={100} cy={156} rx={16} ry={24} fill={coat === "black" ? "#3f3a3b" : light} />
      {[88, 112].map((x) => (
        <g key={x}>
          <rect x={x - 6} y={146} width={12} height={40} rx={6} fill={body} stroke={INK} strokeWidth={3} />
          <ellipse cx={x} cy={186} rx={8} ry={4.5} fill={light} stroke={INK} strokeWidth={2.4} />
        </g>
      ))}
      {/* ears */}
      {down ? (
        <>
          <path d="M72 64 L44 54 L74 84 Z" fill={body} stroke={INK} strokeWidth={3} strokeLinejoin="round" />
          <path d="M128 64 L156 54 L126 84 Z" fill={coat === "calico" ? "#2e2a2b" : body} stroke={INK} strokeWidth={3} strokeLinejoin="round" />
        </>
      ) : (
        <>
          <path d="M70 70 L68 30 L96 52 Z" fill={body} stroke={INK} strokeWidth={3} strokeLinejoin="round" />
          <path d="M130 70 L132 30 L104 52 Z" fill={coat === "calico" ? "#2e2a2b" : body} stroke={INK} strokeWidth={3} strokeLinejoin="round" />
          <path d="M74 62 L73 40 L88 52 Z" fill="#f2a7b0" /><path d="M126 62 L127 40 L112 52 Z" fill="#f2a7b0" />
        </>
      )}
      <path d="M100 46 C126 46 138 62 138 82 C138 102 122 114 100 114 C78 114 62 102 62 82 C62 62 74 46 100 46 Z" fill={body} stroke={INK} strokeWidth={3} />
      {coat === "calico" && <path d="M64 76 Q70 52 94 50 Q88 70 64 84 Z" fill="#e38b3c" />}
      {stripe && <g stroke={stripe} strokeWidth={3} strokeLinecap="round" opacity={0.8}><path d="M92 52 V62 M100 50 V62 M108 52 V62" /><path d="M64 84 h8 M128 84 h8" /></g>}
      <ellipse cx={100} cy={96} rx={15} ry={10} fill={coat === "black" ? "#4a4445" : light} />
      <Eyes y={80} dx={15} mood={mood} iris={coat === "black" ? "#e8c84a" : "#7bbf5a"} cat />
      <path d="M96 90 L104 90 L100 95 Z" fill="#e88f9a" stroke={INK} strokeWidth={1.4} strokeLinejoin="round" />
      <path d="M100 95 Q96 101 91 99 M100 95 Q104 101 109 99" fill="none" stroke={INK} strokeWidth={2.2} strokeLinecap="round" />
      <g stroke={coat === "black" ? "#bbb" : INK} strokeWidth={1.4} strokeLinecap="round" opacity={0.7}>
        <path d="M84 94 L62 90 M84 98 L62 100 M116 94 L138 90 M116 98 L138 100" />
      </g>
    </g>
  );
}

function Rabbit({ coat, breed, mood }: { coat: string; breed: string; mood: Mood }) {
  const [main, light] = COAT[coat] || COAT.white;
  const down = mood === "mopey" || mood === "miserable" || /lop/i.test(breed);
  return (
    <g color={main}>
      <circle cx={140} cy={170} r={12} fill="#fff" stroke={INK} strokeWidth={3} />
      <path d="M64 188 C54 152 70 116 100 112 C130 116 146 152 136 188 Z" fill={main} stroke={INK} strokeWidth={3} />
      {coat === "spotted" && <><ellipse cx={80} cy={150} rx={12} ry={16} fill="#5a4a42" /><ellipse cx={118} cy={168} rx={10} ry={8} fill="#5a4a42" /></>}
      <ellipse cx={100} cy={160} rx={18} ry={22} fill={light} />
      {[88, 112].map((x) => <ellipse key={x} cx={x} cy={184} rx={10} ry={6} fill={light} stroke={INK} strokeWidth={2.6} />)}
      {/* ears */}
      {down ? (
        <>
          <path d="M76 64 C56 66 46 100 54 120 C62 120 72 96 84 70 Z" fill={main} stroke={INK} strokeWidth={3} />
          <path d="M124 64 C144 66 154 100 146 120 C138 120 128 96 116 70 Z" fill={main} stroke={INK} strokeWidth={3} />
        </>
      ) : (
        <>
          <path d="M84 58 C74 30 76 6 86 4 C96 4 98 30 94 58 Z" fill={main} stroke={INK} strokeWidth={3} />
          <path d="M116 58 C126 30 124 6 114 4 C104 4 102 30 106 58 Z" fill={main} stroke={INK} strokeWidth={3} />
          <path d="M86 52 C80 30 82 14 86 12 C90 14 92 30 90 52 Z" fill="#f2a7b0" />
          <path d="M114 52 C120 30 118 14 114 12 C110 14 108 30 110 52 Z" fill="#f2a7b0" />
        </>
      )}
      <ellipse cx={100} cy={84} rx={34} ry={30} fill={main} stroke={INK} strokeWidth={3} />
      {coat === "spotted" && <ellipse cx={86} cy={76} rx={10} ry={12} fill="#5a4a42" />}
      <ellipse cx={100} cy={96} rx={12} ry={9} fill={light} />
      <Eyes y={80} dx={14} mood={mood} />
      <path d="M96 90 L104 90 L100 94 Z" fill="#e88f9a" stroke={INK} strokeWidth={1.4} />
      <path d="M100 94 Q96 99 92 97 M100 94 Q104 99 108 97" fill="none" stroke={INK} strokeWidth={2} strokeLinecap="round" />
      <rect x={97} y={98} width={6} height={5} rx={1} fill="#fff" stroke={INK} strokeWidth={1} />
    </g>
  );
}

export function PetArt({ species, coat, breed = "", mood, size = 96 }: PetArtProps) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const m = moodOf(mood);
  const defCoat = species === "cat" ? "tabby" : species === "rabbit" ? "white" : "golden";
  return (
    <svg width={size} height={size} viewBox="0 0 200 200" role="img" aria-label={`${species}`} style={{ display: "block", flexShrink: 0 }}>
      <defs>
        <radialGradient id={`ps${uid}`}><stop offset="0" stopColor="#000" stopOpacity={0.18} /><stop offset="1" stopColor="#000" stopOpacity={0} /></radialGradient>
      </defs>
      <ellipse cx={100} cy={190} rx={64} ry={9} fill={`url(#ps${uid})`} />
      {species === "cat" ? <Cat coat={coat || defCoat} mood={m} /> : species === "rabbit" ? <Rabbit coat={coat || defCoat} breed={breed} mood={m} /> : <Dog coat={coat || defCoat} breed={breed} mood={m} />}
    </svg>
  );
}
