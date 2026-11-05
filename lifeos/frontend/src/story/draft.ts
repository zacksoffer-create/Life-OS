// A story draft (you, your family, your people, the town) and how it becomes the API's story spec.
// Shared by the lab's story wizard and the phone app's story creator.
import { Person, SPORTS, cleanPerson, friendlyError } from "../components/CharacterBuilder";

export const DRAFT_KEY = "lifeos.storyDraft.v1";

export interface Family {
  last: string;
  guardians: string[];
  style: string;
  income: string;
  petMode: "chance" | "none" | "random" | "pick";
  pet: { species: string; name: string; breed?: string; coat?: string };
}
export interface Draft {
  title: string;
  step: number;
  protagonist: Person;
  family: Family;
  siblings: Person[];
  cast: Person[];
  students_per_grade: number;
  gen_seed: number | "";
  sim_seed: number | "";
  seq: number;
}

export const newSeed = () => 1 + Math.floor(Math.random() * 99998);

export function defaultDraft(): Draft {
  return {
    title: "",
    step: 0,
    protagonist: {
      first: "", last: "", gender: "m", grade: 9, archetype: "athlete", attracted_to: ["f"], color: "#57d9c3",
      traits: { competitiveness: 82, discipline: 68, confidence: 64 }, aptitudes: { athletic: 82 },
      interests: { football: 85, basketball: 82, baseball: 88 }, skills: { football: 42, basketball: 44, baseball: 48 },
      body: { height_in: 70, build: "athletic" }, positions: { football: "WR", basketball: "SG", baseball: "SS" }, jersey: 2,
    },
    family: { last: "", guardians: ["", ""], style: "warm", income: "middle", petMode: "chance", pet: { species: "dog", name: "" } },
    siblings: [],
    cast: [],
    students_per_grade: 12,
    gen_seed: newSeed(),
    sim_seed: "",
    seq: 1,
  };
}

export function loadDraft(key: string = DRAFT_KEY): Draft {
  try {
    const raw = window.localStorage.getItem(key);
    if (raw) {
      const d = JSON.parse(raw);
      if (d && d.protagonist && d.family) return { ...defaultDraft(), ...d };
    }
  } catch {
    /* no storage */
  }
  return defaultDraft();
}

// ------------------------------------------------------------------ spec building
export function familyLast(d: Draft) {
  return (d.family.last || d.protagonist.last || "").trim();
}

export function buildSpec(d: Draft): { spec: any; sibOrder: string[] } {
  const last = familyLast(d);
  const fam: any = { style: d.family.style, income: d.family.income };
  if (last) fam.last = last;
  const g = d.family.guardians.map((x) => x.trim()).filter(Boolean).map((x) => (x.includes(" ") || !last ? x : `${x} ${last}`));
  if (g.length) fam.guardians = g;
  if (d.family.petMode === "random") fam.pet = true;
  if (d.family.petMode === "none") fam.pet = null;
  if (d.family.petMode === "pick" && d.family.pet.name.trim()) {
    const { species, name, breed, coat } = d.family.pet;
    fam.pet = { species, name: name.trim(), ...(breed ? { breed } : {}), ...(coat ? { coat } : {}) };
  }
  // a twin's partner has to be built first
  const sibKeys = new Set(d.siblings.map((s) => s.key));
  const first = d.siblings.filter((s) => !s.twin_of || !sibKeys.has(s.twin_of));
  const later = d.siblings.filter((s) => s.twin_of && sibKeys.has(s.twin_of));
  const ordered = [...first, ...later];
  const spec: any = {
    title: d.title.trim() || (last ? `The ${last} Years` : "My Story"),
    protagonist: cleanPerson(d.protagonist, "protagonist"),
    family: fam,
    siblings: ordered.map((s) => cleanPerson(s, "sibling")),
    cast: d.cast.map((c) => cleanPerson(c, "cast")),
    students_per_grade: d.students_per_grade,
  };
  if (d.gen_seed !== "" && d.gen_seed !== null) spec.gen_seed = Number(d.gen_seed);
  if (d.sim_seed !== "" && d.sim_seed !== null) spec.sim_seed = Number(d.sim_seed);
  return { spec, sibOrder: ordered.map((s) => s.key!) };
}

export function specToDraft(spec: any): Draft {
  const base = defaultDraft();
  const fam = spec.family || {};
  const pet = fam.pet;
  const sibs = (spec.siblings || []).map((s: any, i: number) => ({ ...s, key: s.key || `sib${i + 1}` }));
  const cast = (spec.cast || []).map((c: any, i: number) => ({ ...c, key: c.key || `p${i + 1}` }));
  return {
    ...base,
    title: spec.title || "",
    step: 5,
    protagonist: { ...spec.protagonist },
    family: {
      last: fam.last || "", guardians: [fam.guardians?.[0] || "", fam.guardians?.[1] || ""], style: fam.style || "warm", income: fam.income || "middle",
      petMode: pet === true ? "random" : pet && pet.name ? "pick" : pet === null ? "none" : "chance", pet: pet && pet.name ? { species: pet.species || "dog", name: pet.name, breed: pet.breed, coat: pet.coat } : base.family.pet,
    },
    siblings: sibs,
    cast,
    students_per_grade: spec.students_per_grade ?? 12,
    gen_seed: spec.gen_seed ?? "",
    sim_seed: spec.sim_seed ?? "",
    seq: sibs.length + cast.length + 1,
  };
}

export interface Problem { who: string; msg: string }
export function parseErrors(errs: string[], sibOrder: string[], cast: Person[]): Problem[] {
  return errs.map((e) => {
    let m = e.match(/^protagonist(.*)$/);
    if (m) return { who: "me", msg: friendlyError(m[1]) };
    m = e.match(/^siblings\[(\d+)\](.*)$/);
    if (m) return { who: sibOrder[Number(m[1])] || "family", msg: friendlyError(m[2]) };
    m = e.match(/^cast\[(\d+)\](.*)$/);
    if (m) return { who: cast[Number(m[1])]?.key || "people", msg: friendlyError(m[2]) };
    if (/^family/.test(e)) return { who: "family", msg: friendlyError(e.replace(/^family\.?/, "")) };
    if (/students_per_grade/.test(e)) return { who: "town", msg: e.replace(/_/g, " ") };
    if (/siblings/.test(e)) return { who: "family", msg: e };
    if (/custom characters/.test(e)) return { who: "people", msg: e };
    return { who: "other", msg: e };
  });
}

// ------------------------------------------------------------------ templates for your people
export const TEMPLATES: { id: string; label: string; icon: string; make: (me: Person, d: Draft) => Partial<Person> }[] = [
  { id: "best_friend", label: "Best friend", icon: "🤝", make: (me) => ({ gender: me.gender || "m", grade: me.grade, relationships: [{ to: "me", type: "best_friend" }] }) },
  {
    id: "crush", label: "Crush", icon: "💘",
    make: (me) => ({ gender: (me.attracted_to?.[0] as any) || (me.gender === "f" ? "m" : "f"), grade: me.grade, attracted_to: me.gender ? [me.gender as any] : undefined, relationships: [{ to: "me", type: "admirer" }] }),
  },
  { id: "rival", label: "Rival", icon: "⚔️", make: (me) => ({ gender: me.gender || "m", grade: me.grade, archetype: "athlete", traits: { competitiveness: 86 }, relationships: [{ to: "me", type: "rival" }] }) },
  {
    id: "teammate", label: "Teammate", icon: "🏈",
    make: (me) => {
      const plays = SPORTS.filter((s) => me.positions?.[s] || (me.interests?.[s] ?? 0) >= 40);
      return { gender: me.gender || "m", grade: me.grade, archetype: "athlete", interests: Object.fromEntries(plays.map((s) => [s, 78])), relationships: [{ to: "me", type: "teammate" }] };
    },
  },
  { id: "friend", label: "Friend", icon: "🙂", make: (me) => ({ gender: me.gender || "m", grade: me.grade, relationships: [{ to: "me", type: "friend" }] }) },
  {
    id: "coach", label: "Coach", icon: "📋",
    make: (me, d) => {
      const taken = new Set(d.cast.filter((c) => c.role === "staff").map((c) => c.coach_of));
      const sport = SPORTS.find((s) => (me.positions?.[s] || (me.interests?.[s] ?? 0) >= 40) && !taken.has(s)) || "football";
      return { role: "staff", title: "Coach", gender: "m", coach_of: sport };
    },
  },
  { id: "custom", label: "Someone else", icon: "✨", make: (me) => ({ gender: me.gender || "m", grade: me.grade }) },
  { id: "future", label: "Future freshman", icon: "🎒", make: (me) => ({ gender: me.gender || "m", grade: 8, relationships: [{ to: "me", type: "neighbor" }] }) },
];

export function saveDraft(d: Draft, key: string = DRAFT_KEY) {
  try {
    window.localStorage.setItem(key, JSON.stringify(d));
  } catch {
    /* storage unavailable */
  }
}
