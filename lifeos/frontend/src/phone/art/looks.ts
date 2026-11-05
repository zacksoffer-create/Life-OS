// Appearance options and palettes shared by the portraits and the character builder.
// Option ids match the backend (lifeos/backend/lifeos/appearance.py).
import type { Look } from "../api";

export const SKIN = ["porcelain", "fair", "light", "medium", "tan", "olive", "brown", "deep"] as const;
export const HAIR_STYLES = ["buzz", "short", "crew", "side_part", "messy", "curly_short", "fade", "afro",
  "bob", "long_straight", "long_wavy", "ponytail", "bun", "curly_long", "braids", "locs", "bald"] as const;
export const HAIR_COLORS = ["black", "dark_brown", "brown", "light_brown", "auburn", "red", "strawberry", "blonde", "platinum", "gray"] as const;
export const EYES = ["dark_brown", "brown", "hazel", "green", "blue", "gray"] as const;
export const FACIAL_HAIR = ["none", "stubble", "mustache", "goatee", "beard"] as const;

export const LABELS: Record<string, string> = {
  porcelain: "Porcelain", fair: "Fair", light: "Light", medium: "Medium", tan: "Tan", olive: "Olive", brown: "Brown", deep: "Deep",
  buzz: "Buzz cut", short: "Short", crew: "Crew cut", side_part: "Side part", messy: "Messy", curly_short: "Short curls", fade: "Fade",
  afro: "Afro", bob: "Bob", long_straight: "Long & straight", long_wavy: "Long & wavy", ponytail: "Ponytail", bun: "Bun",
  curly_long: "Long curls", braids: "Braids", locs: "Locs", bald: "Bald",
  black: "Black", dark_brown: "Dark brown", light_brown: "Light brown", auburn: "Auburn", red: "Red", strawberry: "Strawberry",
  blonde: "Blonde", platinum: "Platinum", gray: "Gray", hazel: "Hazel", green: "Green", blue: "Blue",
  none: "None", stubble: "Stubble", mustache: "Mustache", goatee: "Goatee", beard: "Beard",
};

// skin: [base, shade, line, blush]
export const SKIN_PAL: Record<string, [string, string, string, string]> = {
  porcelain: ["#fde6d9", "#f0c7b5", "#a8705f", "#ff9a9a"],
  fair: ["#f8d5bf", "#e8b59c", "#a16a52", "#f79190"],
  light: ["#f0c4a2", "#dca582", "#9a6346", "#ef8a7f"],
  medium: ["#dea77d", "#c58960", "#8a5536", "#e47f6e"],
  tan: ["#cb9162", "#ae7447", "#7a4a2b", "#d9705e"],
  olive: ["#c29466", "#a3784c", "#734d2d", "#cf7560"],
  brown: ["#9c6641", "#80502f", "#4f2f1a", "#b9584a"],
  deep: ["#6e4229", "#56321d", "#2e1a0e", "#9a4a3e"],
};
// hair: [base, shade, highlight]
export const HAIR_PAL: Record<string, [string, string, string]> = {
  black: ["#25201f", "#141111", "#4a4140"],
  dark_brown: ["#3d2719", "#25170e", "#62432e"],
  brown: ["#5e3b22", "#3f2614", "#87593a"],
  light_brown: ["#8c5f37", "#6a4524", "#b4855a"],
  auburn: ["#8e3d1f", "#6a2a12", "#b5603a"],
  red: ["#b84d22", "#8e3613", "#e07a44"],
  strawberry: ["#d38d5c", "#b06c40", "#efb183"],
  blonde: ["#e3c06f", "#c49c4b", "#f6dc9a"],
  platinum: ["#efe3c5", "#d3c49f", "#fffaf0"],
  gray: ["#a9a6a2", "#85827e", "#d2d0cc"],
};
export const EYE_PAL: Record<string, string> = {
  dark_brown: "#3b2316", brown: "#6c4426", hazel: "#8b6d3a", green: "#4e7f48", blue: "#3f7cbf", gray: "#7a8892",
};
export const LONG_STYLES = new Set(["bob", "long_straight", "long_wavy", "ponytail", "bun", "curly_long", "braids", "locs"]);

export function hashStr(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function pickW<T>(h: number, opts: readonly T[], w?: number[]): T {
  const x = (h % 10000) / 10000;
  if (!w) return opts[Math.floor(x * opts.length)];
  const tot = w.reduce((a, b) => a + b, 0);
  let acc = 0;
  for (let i = 0; i < opts.length; i++) {
    acc += w[i] / tot;
    if (x < acc) return opts[i];
  }
  return opts[opts.length - 1];
}

const MASC = ["short", "crew", "side_part", "messy", "curly_short", "fade", "buzz", "afro", "locs"];
const FEM = ["long_straight", "long_wavy", "ponytail", "bun", "bob", "curly_long", "braids", "long_straight", "long_wavy"];
const NEUTRAL = ["short", "messy", "bob", "curly_short", "long_wavy", "side_part", "curly_long"];

/** A deterministic look from any seed string (a name, a key). Mirrors the backend's generated looks. */
export function defaultLook(seed: string, gender?: string | null, adult = false): Look {
  const H = (k: string) => hashStr(`${seed}:${k}`);
  const skin = pickW(H("skin"), SKIN, [6, 14, 16, 16, 12, 10, 14, 12]);
  const dark = SKIN.indexOf(skin as any) >= 5;
  const styles = gender === "m" ? MASC : gender === "f" ? FEM : gender === "nb" ? NEUTRAL : [...MASC, ...FEM];
  let hair = pickW(H("hair"), styles);
  if (dark && ["long_straight", "messy", "side_part"].includes(hair) && H("texture") % 3 === 0) {
    hair = ({ long_straight: "braids", messy: "curly_short", side_part: "fade" } as any)[hair];
  }
  const hair_color = pickW(H("hair_color"), HAIR_COLORS, dark ? [40, 30, 14, 6, 3, 1, 1, 4, 1, 0] : [10, 22, 22, 14, 6, 4, 3, 15, 3, 1]);
  const eyes = pickW(H("eyes"), EYES, dark ? [60, 30, 8, 1, 1, 0] : [34, 22, 14, 8, 16, 6]);
  let facial_hair = "none";
  if (gender === "m" && adult) facial_hair = pickW(H("facial"), FACIAL_HAIR, [40, 15, 10, 15, 20]);
  return {
    skin, hair, hair_color: adult && H("gray") % 3 === 0 ? "gray" : hair_color, eyes, facial_hair,
    glasses: H("glasses") % 100 < (adult ? 22 : 14), freckles: !dark && H("freckles") % 100 < 12,
  } as Look;
}

/** Fill any missing fields of a partial look from a seed. */
export function fullLook(partial: Partial<Look> | null | undefined, seed: string, gender?: string | null, adult = false): Look {
  const base = defaultLook(seed, gender, adult);
  const out: any = { ...base };
  for (const [k, v] of Object.entries(partial || {})) if (v !== undefined && v !== null && v !== "") out[k] = v;
  return out as Look;
}

/** Lighten (amt > 0) or darken (amt < 0) a hex color. */
export function shade(hex: string, amt: number): string {
  const m = hex.replace("#", "");
  const full = m.length === 3 ? m.split("").map((c) => c + c).join("") : m.slice(0, 6);
  const n = parseInt(full, 16);
  let r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const t = amt < 0 ? 0 : 255;
  const p = Math.abs(amt);
  r = Math.round((t - r) * p + r);
  g = Math.round((t - g) * p + g);
  b = Math.round((t - b) * p + b);
  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
}
