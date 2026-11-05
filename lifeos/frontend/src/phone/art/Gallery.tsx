// Art gallery (#/m/gallery): every portrait option, every scene in every season and time of day, every pet.
import React, { useState } from "react";
import type { Look, Mood } from "../api";
import { PetArt } from "./pets";
import { Portrait } from "./portrait";
import { SCENE_KEYS, Scene } from "./scenes";
import { EYES, FACIAL_HAIR, HAIR_COLORS, HAIR_STYLES, LABELS, SKIN, defaultLook } from "./looks";

const MOODS: Mood[] = ["neutral", "happy", "sad", "angry", "flirty", "surprised", "tired"];
const PHASES = ["dawn", "lunch", "after_school", "evening", "night"];
const SEASONS = ["fall", "winter", "spring", "summer"];
const COATS: Record<string, string[]> = {
  dog: ["golden", "black", "chocolate", "cream", "tricolor", "brindle", "gray", "white"],
  cat: ["orange", "gray", "black", "white", "calico", "tabby"],
  rabbit: ["white", "brown", "gray", "black", "spotted"],
};
const BREEDS = ["Golden Retriever", "Labrador", "Beagle", "Goldendoodle", "German Shepherd", "Border Collie", "Boxer", "Corgi", "Bernese Mountain Dog", "Rescue mix"];
const NAMES = ["Zack Soffer", "Sophie Lane", "Danny Kim", "Mike Soffer", "Ally Soffer", "Jen Soffer", "Coach Duda", "Theo Mbeki", "Ines Park", "Kofi Abernathy",
  "Hana Sato", "Declan Rourke", "Mei Chen", "Omar Haddad", "Sage Winters", "Daphne Carmichael", "Isaac Brooks", "Nia Johnson", "Petra Novak", "Rafael Cruz"];

const box: React.CSSProperties = { display: "flex", flexWrap: "wrap", gap: 10, alignItems: "flex-end" };
const cell: React.CSSProperties = { textAlign: "center", fontSize: 11, color: "#6b5a55", width: 84 };
const h2: React.CSSProperties = { font: "700 18px Fredoka, Nunito, system-ui, sans-serif", margin: "26px 0 10px", color: "#3a2b2f" };

export default function Gallery() {
  const [season, setSeason] = useState("fall");
  const [phase, setPhase] = useState("lunch");
  const base: Look = { skin: "light", hair: "short", hair_color: "brown", eyes: "brown", facial_hair: "none", glasses: false, freckles: false };
  const chip = (on: boolean): React.CSSProperties => ({ padding: "6px 10px", borderRadius: 999, border: "1px solid #d9c9b6", background: on ? "#1f6b3c" : "#fff", color: on ? "#fff" : "#3a2b2f", fontSize: 12 });
  return (
    <div style={{ padding: 16, background: "#fff8ef", minHeight: "100vh", fontFamily: "Nunito, system-ui, sans-serif", color: "#3a2b2f" }}>
      <h1 style={{ ...h2, fontSize: 24, marginTop: 0 }}>Art gallery</h1>

      <h2 style={h2}>A class photo (generated looks)</h2>
      <div style={box}>{NAMES.map((n, i) => <div key={n} style={cell}><Portrait size={72} name={n} look={defaultLook(n, i % 2 ? "f" : "m", n.startsWith("Coach"))} mood={MOODS[i % MOODS.length]} />{n.split(" ")[0]}</div>)}</div>

      <h2 style={h2}>Hair styles</h2>
      <div style={box}>{HAIR_STYLES.map((h, i) => <div key={h} style={cell}><Portrait size={76} look={{ ...base, hair: h, skin: SKIN[(i * 3) % 8], hair_color: HAIR_COLORS[(i * 7) % 10] }} />{LABELS[h]}</div>)}</div>

      <h2 style={h2}>Skin</h2>
      <div style={box}>{SKIN.map((s) => <div key={s} style={cell}><Portrait size={76} look={{ ...base, skin: s, hair: "long_wavy", hair_color: SKIN.indexOf(s) > 4 ? "black" : "brown" }} mood="happy" />{LABELS[s]}</div>)}</div>

      <h2 style={h2}>Hair color</h2>
      <div style={box}>{HAIR_COLORS.map((c) => <div key={c} style={cell}><Portrait size={76} look={{ ...base, hair_color: c, hair: "side_part" }} />{LABELS[c]}</div>)}</div>

      <h2 style={h2}>Eyes, facial hair, glasses, freckles</h2>
      <div style={box}>
        {EYES.map((e) => <div key={e} style={cell}><Portrait size={76} look={{ ...base, eyes: e, hair: "ponytail" }} />{LABELS[e]}</div>)}
        {FACIAL_HAIR.map((f) => <div key={f} style={cell}><Portrait size={76} look={{ ...base, facial_hair: f, hair: "crew", skin: "tan", hair_color: "dark_brown" }} />{LABELS[f]}</div>)}
        <div style={cell}><Portrait size={76} look={{ ...base, glasses: true, hair: "bob", hair_color: "auburn" }} />Glasses</div>
        <div style={cell}><Portrait size={76} look={{ ...base, freckles: true, hair: "curly_long", hair_color: "red", skin: "fair" }} />Freckles</div>
      </div>

      <h2 style={h2}>Moods</h2>
      <div style={box}>{MOODS.map((m) => <div key={m} style={cell}><Portrait size={76} look={{ ...base, hair: "messy", skin: "medium", hair_color: "black", eyes: "dark_brown" }} mood={m} />{m}</div>)}</div>

      <h2 style={h2}>Sizes, rings and jerseys</h2>
      <div style={box}>
        {[32, 44, 56, 72, 96].map((s) => <Portrait key={s} size={s} name="Zack Soffer" look={defaultLook("Zack Soffer", "m")} />)}
        <Portrait size={96} name="Sophie Lane" look={defaultLook("Sophie Lane", "f")} ring="#ff6b8a" mood="flirty" />
        <Portrait size={96} name="Zack Soffer" look={{ ...base, hair: "fade", skin: "brown", hair_color: "black", eyes: "dark_brown" }} jersey={2} mood="happy" />
        <Portrait size={180} name="Mike Soffer" look={defaultLook("Mike Soffer", "m")} jersey={23} />
      </div>

      <h2 style={h2}>Scenes</h2>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 6 }}>{SEASONS.map((s) => <button key={s} style={chip(s === season)} onClick={() => setSeason(s)}>{s}</button>)}</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>{PHASES.map((p) => <button key={p} style={chip(p === phase)} onClick={() => setPhase(p)}>{p}</button>)}</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 10 }}>
        {SCENE_KEYS.map((k) => (
          <div key={k}>
            <Scene art={k} season={season} phase={phase} className="gal-scene">
              <div style={{ height: 220 }} />
            </Scene>
            <div style={{ fontSize: 12, marginTop: 4 }}>{k}</div>
          </div>
        ))}
      </div>
      <h2 style={h2}>One place through the day</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: 8 }}>
        {PHASES.map((p) => <div key={p}><Scene art="town_green" season={season} phase={p}><div style={{ height: 160 }} /></Scene><div style={{ fontSize: 11 }}>{p}</div></div>)}
      </div>
      <h2 style={h2}>With a character on top</h2>
      <Scene art="cafeteria" season={season} phase={phase}>
        <div style={{ height: 300, display: "flex", alignItems: "flex-end", justifyContent: "center", paddingBottom: 12 }}>
          <Portrait size={140} name="Danny Kim" look={defaultLook("Danny Kim", "m")} mood="happy" ring="#fff" />
        </div>
      </Scene>

      <h2 style={h2}>Pets</h2>
      {Object.entries(COATS).map(([sp, coats]) => (
        <div key={sp} style={{ ...box, marginBottom: 12 }}>
          {coats.map((c) => <div key={c} style={cell}><PetArt species={sp} coat={c} size={84} mood="happy" />{sp} · {c}</div>)}
        </div>
      ))}
      <div style={{ ...box, marginBottom: 12 }}>{BREEDS.map((b, i) => <div key={b} style={cell}><PetArt species="dog" breed={b} coat={COATS.dog[i % 8]} size={84} />{b}</div>)}</div>
      {["dog", "cat", "rabbit"].map((sp) => (
        <div key={sp} style={{ ...box, marginBottom: 12 }}>
          {["thrilled", "happy", "okay", "mopey", "miserable"].map((m) => <div key={m} style={cell}><PetArt species={sp} mood={m} size={84} breed={sp === "rabbit" ? "Holland Lop" : ""} />{m}</div>)}
        </div>
      ))}
    </div>
  );
}
