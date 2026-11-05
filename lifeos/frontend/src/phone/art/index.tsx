// Illustration components for the phone app: portraits, scenes and pets (all hand-drawn SVG).
import "./art.css";

export { Portrait } from "./portrait";
export type { PortraitProps } from "./portrait";
export { Scene, SceneArt, SCENE_KEYS, timeOf } from "./scenes";
export type { SceneProps } from "./scenes";
export { PetArt } from "./pets";
export type { PetArtProps } from "./pets";
export { defaultLook, fullLook, SKIN, HAIR_STYLES, HAIR_COLORS, EYES, FACIAL_HAIR, LABELS as LOOK_LABELS } from "./looks";
