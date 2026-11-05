// Appearance picker for the character builder: every option shown as a small portrait.
import React from "react";
import type { Look } from "../api";
import { EYES, FACIAL_HAIR, HAIR_COLORS, HAIR_PAL, HAIR_STYLES, LABELS, SKIN, SKIN_PAL, defaultLook } from "./looks";
import { Portrait } from "./portrait";
import "./look-picker.css";

type Props = {
  value?: Partial<Look> | null;
  base: Look;
  onChange: (look: Partial<Look> | undefined) => void;
  gender?: string;
  color?: string;
  adult?: boolean;
  name?: string;
};

export default function LookPicker({ value, base, onChange, gender, color, adult, name }: Props) {
  const locked = !!value && Object.keys(value).length > 0;
  const set = (k: keyof Look, v: any) => onChange({ ...base, ...(value || {}), [k]: v });
  const shuffle = () => onChange(defaultLook(`${name || "someone"}:${Math.random()}`, gender, adult));
  const row = (k: keyof Look, opts: readonly string[], swatch?: (o: string) => string) => (
    <div className="lp-row">
      {opts.map((o) => (
        <button key={o} type="button" className={"lp-opt" + (base[k] === o ? " on" : "")} onClick={() => set(k, o)} title={LABELS[o] || o}>
          <Portrait size={56} look={{ ...base, [k]: o } as Look} color={color} />
          <span className="lp-l">{swatch && <i style={{ background: swatch(o) }} />}{LABELS[o] || o}</span>
        </button>
      ))}
    </div>
  );
  return (
    <div className="lp">
      <div className="lp-top">
        <Portrait size={120} look={base} color={color} mood="happy" />
        <div className="lp-top-r">
          <div className="lp-status">{locked ? "Locked in: this is exactly how they'll look." : "On auto: a look is picked when the story starts. Choose anything below to lock this one in."}</div>
          <div className="lp-actions">
            <button type="button" className="small" onClick={shuffle}>🎲 Shuffle</button>
            {locked && <button type="button" className="small ghost" onClick={() => onChange(undefined)}>Leave on auto</button>}
          </div>
        </div>
      </div>
      <div className="lp-h">Skin</div>
      {row("skin", SKIN, (o) => SKIN_PAL[o][0])}
      <div className="lp-h">Hair</div>
      {row("hair", HAIR_STYLES)}
      <div className="lp-h">Hair color</div>
      {row("hair_color", HAIR_COLORS, (o) => HAIR_PAL[o][0])}
      <div className="lp-h">Eyes</div>
      {row("eyes", EYES)}
      <div className="lp-h">Facial hair</div>
      {row("facial_hair", FACIAL_HAIR)}
      <div className="lp-h">Extras</div>
      <div className="lp-row">
        {([["glasses", "Glasses"], ["freckles", "Freckles"]] as [keyof Look, string][]).map(([k, label]) => (
          <button key={k} type="button" className={"lp-opt" + (base[k] ? " on" : "")} onClick={() => set(k, !base[k])}>
            <Portrait size={56} look={{ ...base, [k]: true } as Look} color={color} />
            <span className="lp-l">{label}{base[k] ? " ✓" : ""}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
