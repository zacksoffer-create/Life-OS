"""World generation: a small town, its high school, households, staff and students.

Generation uses its own seed (gen_seed) and streams, separate from the simulation seed,
so the same population can be run forward under many different simulation seeds.
"""
from __future__ import annotations

import colorsys
import copy

from . import calendar as calm
from .catalogs import APTITUDES, MOTIVES, TRAITS, Catalogs
from .history import History
from .model import Character, World, pair_key
from .rng import Streams, clamp, derive_seed, unit_hash
from .rules import schema
from .sports import sports_for

SPORTS = ["football", "basketball", "baseball", "soccer", "softball"]
FIRST_PICK = {"m": "football", "f": "soccer"}  # the sport most likely to come first, by side


def _color(rng) -> str:
    h = rng.random()
    r, g, b = colorsys.hls_to_rgb(h, 0.62, 0.62)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def _pick_weighted(rng, items, key="weight"):
    tot = sum(i.get(key, 1) for i in items)
    x = rng.random() * tot
    for i in items:
        x -= i.get(key, 1)
        if x <= 0:
            return i
    return items[-1]


def start_gpa(academics: float, aptitude: float, discipline: float, noise: float = 0.0) -> float:
    """Starting GPA on the 4.0 scale, matched to where exams settle (an average student lands around 3.0-3.3)."""
    return round(clamp(3.6 + 0.03 * (academics - 50) + 0.025 * (aptitude - 50) + (discipline - 50) / 150 + noise, 1.0, 4.0), 2)


def pronouns_for(g: str) -> str:
    return {"f": "she/her", "m": "he/him"}.get(g, "they/them")


def chemistry(w: World, a: str, b: str) -> float:
    """Latent pair chemistry in [-1, 1]; fixed by the generation seed."""
    return unit_hash(w.gen_seed, "chem", pair_key(a, b)) * 2 - 1


def compatibility(w: World, a: Character, b: Character) -> float:
    ta, tb = a.traits, b.traits
    diff = (abs(ta["sociability"] - tb["sociability"]) + abs(ta["impulsivity"] - tb["impulsivity"])
            + abs(ta["empathy"] - tb["empathy"]) + abs(ta["curiosity"] - tb["curiosity"])
            + abs(ta["competitiveness"] - tb["competitiveness"]) * 0.5)
    sim = 1 - diff / 300.0
    shared = 0.0
    ia, ib = a.interests, b.interests
    for k, v in ia.items():
        if v > 40:
            u = ib.get(k, 0)
            if u > 40:
                shared += min(v, u) / 100.0
    shared = min(shared, 1.6) / 1.6
    return 0.45 * (sim * 2 - 1) + 0.4 * shared + 0.25 * chemistry(w, a.id, b.id) - 0.05


def orientation_ok(a: Character, b: Character) -> bool:
    return b.gender in a.attracted_to


def stage_ok(a: Character, b: Character) -> bool:
    """Right age for each other: both in high school (or both in college) and at most two grades apart; across high
    school and college only a year apart (a senior and a college freshman). Middle schoolers, staff and adults: no."""
    ga, gb = a.grade or 0, b.grade or 0
    if ga < 9 or gb < 9 or a.role != "student" or b.role != "student":
        return False
    gap = abs(ga - gb)
    return gap <= (1 if (ga <= 12) != (gb <= 12) else 2)


def _attracted(rng, gender: str) -> list:
    x = rng.random()
    if gender == "f":
        return ["m"] if x < 0.8 else (["f", "m", "nb"] if x < 0.93 else ["f", "nb"])
    if gender == "m":
        return ["f"] if x < 0.8 else (["f", "m", "nb"] if x < 0.92 else ["m", "nb"])
    return ["f", "m", "nb"] if x < 0.6 else (["f", "nb"] if x < 0.8 else ["m", "nb"])


class Generator:
    def __init__(self, gen_seed: int):
        self.cat = Catalogs()
        self.streams = Streams(gen_seed)
        self.gen_seed = gen_seed
        self.used_names: set = set()
        self.used_last: set = set()

    def unique_id(self, w: World, first: str, last: str) -> str:
        base = f"{first}-{last}".lower().replace(" ", "-").replace("'", "")
        cid, n = base, 2
        while cid in w.chars:
            cid = f"{base}-{n}"
            n += 1
        return cid

    def make_student(self, w: World, rng, grade: int, household: dict, archetype: str | None = None,
                     first: str | None = None, gender: str | None = None, day: int = 0) -> Character:
        ppl = self.cat.people
        arch = next(a for a in ppl["archetypes"] if a["id"] == archetype) if archetype else _pick_weighted(rng, ppl["archetypes"])
        if gender is None:
            x = rng.random()
            gender = "f" if x < 0.47 else ("m" if x < 0.94 else "nb")
        if first is None:
            pool = ppl["names"]["female" if gender == "f" else "male" if gender == "m" else "nonbinary"]
            for _ in range(50):
                first = rng.choice(pool)
                if (first, household["last"]) not in self.used_names:
                    break
        self.used_names.add((first, household["last"]))
        traits = {t: round(clamp(rng.gauss(arch["traits"][t], 13), 3, 97), 1) for t in TRAITS}
        apt = {a: round(clamp(rng.gauss(arch["aptitudes"][a], 14), 5, 98), 1) for a in APTITUDES}
        mot = {m: round(clamp(rng.gauss(arch["motives"][m], 12), 5, 95), 1) for m in MOTIVES}
        interests: dict = {}
        for k, v in arch["interests"].items():
            if k == "sport":
                sports = sports_for(gender)
                rng.shuffle(sports)
                top = FIRST_PICK.get(gender)
                if top and rng.random() < 0.45:
                    sports.remove(top)
                    sports.insert(0, top)
                interests[sports[0]] = round(clamp(rng.gauss(v, 10), 20, 98), 1)
                if rng.random() < 0.5:
                    interests[sports[1]] = round(clamp(rng.gauss(v - 22, 12), 10, 90), 1)
            else:
                interests[k] = round(clamp(rng.gauss(v, 12), 5, 98), 1)
        if not any(k in interests for k in SPORTS) and rng.random() < 0.45:
            mine = sports_for(gender)
            top = FIRST_PICK.get(gender) or mine[0]
            rest = [x for x in mine if x != top]
            pick = top if rng.random() < 0.5 else rest[int(rng.random() * len(rest))]
            interests[pick] = round(clamp(rng.gauss(58, 12), 25, 90), 1)
        if "drama" not in interests and rng.random() < 0.15:
            interests["drama"] = round(clamp(rng.gauss(55, 12), 25, 90), 1)
        playable = set(sports_for(gender))
        extras = [s["id"] for s in self.cat.world["skills"] if s["id"] not in SPORTS or s["id"] in playable] + list(self.cat.hobbies)
        for _ in range(2):
            k = rng.choice(extras)
            if k not in interests:
                interests[k] = round(clamp(rng.gauss(38, 14), 5, 80), 1)
        interests.setdefault("academics", round(clamp(rng.gauss(30 + traits["discipline"] * 0.3, 10), 5, 90), 1))
        skills = {}
        for s in self.cat.world["skills"]:
            sid = s["id"]
            a = apt[s["aptitude"]]
            iv = interests.get(sid, 0)
            base = a * 0.3 + iv * 0.28 + (grade - 9) * 2.5 + rng.gauss(0, 5)
            if sid == "academics":
                base = a * 0.45 + traits["discipline"] * 0.15 + (grade - 9) * 2 + rng.gauss(0, 5)
            skills[sid] = round(clamp(base, 0, 70), 1)
        cid = self.unique_id(w, first, household["last"])
        income_money = {"low": 10, "middle": 25, "high": 50}[household["income"]]
        c = Character(
            id=cid, first=first, last=household["last"], gender=gender, pronouns=pronouns_for(gender),
            role="student", grade=grade, birth_day=day - int((grade + 5) * 365.25 + rng.uniform(0, 364)),
            household_id=household["id"], archetype=arch["id"], attracted_to=_attracted(rng, gender),
            color=_color(rng), traits=traits, aptitudes=apt, skills=skills, motives=mot,
            needs={"energy": round(clamp(rng.gauss(70, 10), 30, 100), 1), "social": round(clamp(rng.gauss(60, 12), 20, 100), 1),
                   "fun": round(clamp(rng.gauss(60, 12), 20, 100), 1),
                   "stress": round(clamp(25 + traits["volatility"] * 0.2 + rng.gauss(0, 8), 5, 80), 1)},
            mood=round(clamp(rng.gauss(62, 8), 30, 90), 1), interests=interests,
            money=float(income_money), gpa=start_gpa(skills["academics"], apt["academic"], traits["discipline"], rng.gauss(0, 0.22)),
        )
        c.bio = self.bio(c, arch)
        household["members"].append(cid)
        w.chars[cid] = c
        return c

    def bio(self, c: Character, arch: dict) -> str:
        t = c.traits
        bits = []
        top_int = sorted(c.interests.items(), key=lambda x: -x[1])[:2]
        names = []
        for k, _ in top_int:
            if k in self.cat.skills:
                names.append(self.cat.skills[k]["label"].lower())
            elif k in self.cat.hobbies:
                names.append(self.cat.hobbies[k]["label"])
        if t["sociability"] > 70:
            bits.append("knows everyone's name")
        elif t["sociability"] < 30:
            bits.append("keeps to a small orbit")
        if t["discipline"] > 72:
            bits.append("does the work")
        elif t["discipline"] < 30:
            bits.append("allergic to routines")
        if t["empathy"] > 75:
            bits.append("notices when people are off")
        if t["impulsivity"] > 72:
            bits.append("decides first, thinks later")
        if t["ambition"] > 75:
            bits.append("has plans")
        lead = f"{arch['label']} type"
        tail = ("; " + ", ".join(bits[:2])) if bits else ""
        return f"{lead}{tail}. Into {' and '.join(names)}."

    def household(self, w: World, rng, last: str | None = None, style: str | None = None,
                  income: str | None = None, guardians: list | None = None, pet=False, key: str | None = None) -> dict:
        ppl = self.cat.people
        if last is None:
            avail = [n for n in ppl["names"]["last"] if n not in self.used_last]
            if not avail:  # a big school: more family names, then (like real life) two families can share one
                avail = [n for n in ppl["names"].get("last_more", []) if n not in self.used_last] or list(ppl["names"]["last"])
            last = rng.choice(avail)
        self.used_last.add(last)
        styles = {s["id"]: s for s in ppl["guardian_styles"]}
        if style is None:
            style = _pick_weighted(rng, [{"id": "warm", "weight": 3}, {"id": "strict", "weight": 2},
                                         {"id": "permissive", "weight": 2}, {"id": "distant", "weight": 1.5},
                                         {"id": "overbearing", "weight": 1.5}])["id"]
        if income is None:
            income = _pick_weighted(rng, [{"id": "low", "weight": 3}, {"id": "middle", "weight": 5}, {"id": "high", "weight": 2}])["id"]
        if guardians is None:
            n = 1 if rng.random() < 0.35 else 2
            pool = ppl["names"]["female"] + ppl["names"]["male"]
            guardians = [f"{rng.choice(pool)} {last}" for _ in range(n)]
        if pet is True or (pet is False and rng.random() < 0.4):
            sp = rng.choice(ppl["pets"])
            pet = {"species": sp["species"], "name": rng.choice(sp["names"])}
        elif pet is False:
            pet = None
        hid = f"h-{(key or last).lower()}"
        n = 2
        while hid in w.households:
            hid = f"h-{(key or last).lower()}-{n}"
            n += 1
        st = styles[style]
        h = {"id": hid, "last": last, "name": f"The {last} household", "style": style, "style_label": st["label"],
             "warmth": st["warmth"], "strictness": st["strictness"], "expectations": st["expectations"],
             "permissive": st["permissive"], "income": income, "guardians": guardians, "pet": pet, "members": [],
             "away_weekend": None}
        w.households[hid] = h
        return h


def _staff(gen: Generator, w: World, rng):
    for s in gen.cat.people["staff"]:
        traits = {t: float(s["traits"].get(t, 50)) for t in TRAITS}
        c = Character(
            id=s["id"], first=s["first"], last=s["last"], gender=s["gender"], pronouns=pronouns_for(s["gender"]),
            role="staff", grade=None, birth_day=-int(rng.uniform(30, 58) * 365.25), household_id=None,
            archetype="staff", title=s["title"], role_label=s["role_label"], color=_color(rng), traits=traits,
            aptitudes={a: 55.0 for a in APTITUDES},
            skills={},
            motives={"achievement": 60.0, "approval": 35.0, "belonging": 50.0, "pleasure": 40.0,
                     "altruism": round(30 + traits["empathy"] * 0.6, 1), "mastery": 55.0},
            needs={"energy": 70.0, "social": 60.0, "fun": 55.0, "stress": 30.0}, mood=62.0,
            interests={"reading": 50.0, "cooking": 40.0}, money=200.0, bio=s.get("bio", s["role_label"] + "."),
        )
        w.chars[c.id] = c


def _groups(gen: Generator, w: World):
    for gd in gen.cat.world["groups"]:
        g = copy.deepcopy(gd)
        g.update({"members": [], "leaders": [], "absences": {}, "cut": [], "record": {"w": 0, "l": 0},
                  "production": None, "joined": {}, "history": [], "streak": 0})
        w.groups[g["id"]] = g


def initial_relationships(gen: Generator, w: World, rng, day: int = 0, only: set | None = None):
    studs = [c for c in w.chars.values() if c.role == "student"]
    staff = [c for c in w.chars.values() if c.role == "staff"]
    for i, a in enumerate(studs):
        for b in studs[i + 1:]:
            if only is not None and a.id not in only and b.id not in only:
                continue
            sib = a.household_id == b.household_id
            gd = abs(a.grade - b.grade)
            if sib:
                fam = 95
            elif gd == 0:
                fam = (12 + 7 * (a.grade - 9) + rng.gauss(0, 10)) if rng.random() < 0.85 else rng.uniform(0, 6)
            elif gd == 1:
                fam = rng.uniform(5, 25) if rng.random() < 0.35 else 0
            else:
                fam = rng.uniform(3, 15) if rng.random() < 0.15 else 0
            if fam <= 2:
                continue
            fam = clamp(fam, 3, 100)
            comp = compatibility(w, a, b)
            for x, y in ((a, b), (b, a)):
                r = w.ensure_rel(x.id, y.id, day - 200)
                r.familiarity = round(clamp(fam + rng.gauss(0, 4), 2, 100), 1)
                aff = comp * r.familiarity * 0.7 + rng.gauss(0, 9)
                if sib:
                    aff = 30 + comp * 30 + rng.gauss(0, 15)
                r.affection = round(clamp(aff, -60, 85), 1)
                r.peak_affection = max(r.affection, 0)
                r.respect = round(clamp((y.traits["confidence"] + y.traits["discipline"] - 100) * 0.3 * r.familiarity / 60
                                        + rng.gauss(0, 8), -50, 70), 1)
                r.trust = round(clamp(30 + r.affection * 0.4 + rng.gauss(0, 6), 0, 95), 1)
                if not sib and orientation_ok(x, y) and stage_ok(x, y) and r.familiarity > 10:
                    chem = chemistry(w, x.id, y.id)
                    r.attraction = round(clamp((chem * 0.6 + 0.25) * r.familiarity * 0.9 + rng.gauss(0, 10), 0, 80), 1)
                shared_sport = any(x.interests.get(s, 0) > 55 and y.interests.get(s, 0) > 55 for s in SPORTS)
                if shared_sport and gd <= 1:
                    r.rivalry = round(clamp(x.traits["competitiveness"] * 0.4 * r.familiarity / 70 + rng.gauss(0, 8), 0, 60), 1)
                r.met_day = day - int(rng.uniform(100, 2000))
                r.last_day = day - 1
            ra, rb = w.rels[(a.id, b.id)], w.rels[(b.id, a.id)]
            ra.perceived = round(clamp(rb.affection + rng.gauss(0, 12), -100, 100), 1)
            rb.perceived = round(clamp(ra.affection + rng.gauss(0, 12), -100, 100), 1)
            if sib:
                bd = w.bonds.setdefault(pair_key(a.id, b.id), {"roles": [], "since": {}})
                if "sibling" not in bd["roles"]:
                    bd["roles"].append("sibling")
                    bd["since"]["sibling"] = min(a.birth_day, b.birth_day)
    for s in staff:
        for c in studs:
            if only is not None and c.id not in only:
                continue
            for x, y in ((s, c), (c, s)):
                r = w.ensure_rel(x.id, y.id, day - 100)
                r.familiarity = round(clamp(12 + 6 * (c.grade - 9) + rng.gauss(0, 6), 3, 60), 1)
                r.affection = round(clamp(rng.gauss(8, 10), -30, 50), 1)
                r.respect = round(clamp(rng.gauss(15, 12), -30, 60), 1)
                r.trust = 40.0
        if only is None:
            for t in staff:
                if t.id != s.id:
                    r = w.ensure_rel(s.id, t.id, day - 1000)
                    r.familiarity = round(rng.uniform(40, 80), 1)
                    r.affection = round(rng.uniform(5, 45), 1)
                    r.trust = 50.0


def generate(gen_seed: int = 1234, students: int = 36, featured: bool = True, sim_seed: int | None = None,
             name: str | None = None) -> World:
    gen = Generator(gen_seed)
    w = World()
    w.gen_seed = gen_seed
    w.seed = sim_seed if sim_seed is not None else derive_seed(gen_seed, "sim") % 1_000_000
    w.name = name or gen.cat.world["town"]["name"]
    w.rules = schema().defaults()
    w.history = History()
    rng = gen.streams.get("gen", "world")
    _groups(gen, w)
    _staff(gen, w, gen.streams.get("gen", "staff"))
    per_grade = {g: students // 4 + (1 if i < students % 4 else 0) for i, g in enumerate([9, 10, 11, 12])}
    keyed: dict[str, str] = {}
    if featured:
        ppl = gen.cat.people
        hh = {}
        for fh in ppl["featured_households"]:
            hh[fh["key"]] = gen.household(w, rng, last=fh["last"], style=fh["style"], income=fh["income"],
                                          guardians=fh["guardians"], pet=fh["pet"], key=fh["key"])
        frng = gen.streams.get("gen", "featured")
        for f in ppl["featured"]:
            c = gen.make_student(w, frng, f["grade"], hh[f["household"]], archetype=f["archetype"], first=f["first"],
                                 gender=f["gender"])
            c.attracted_to = f["attracted_to"]
            for layer in ("traits", "aptitudes", "skills", "interests", "motives"):
                getattr(c, layer).update({k: float(v) for k, v in f.get(layer, {}).items()})
            c.bio = f["bio"]
            c.featured = True
            for m in f.get("memories", []):
                c.memories.append({"id": f"m{w.next_id('mem')}", "day": m["day"], "kind": m["kind"], "with": [],
                                   "valence": m["valence"], "intensity": m["intensity"], "text": m["text"],
                                   "event": None, "tags": ["backstory"]})
            keyed[f["key"]] = c.id
            per_grade[f["grade"]] -= 1
    srng = gen.streams.get("gen", "students")
    solo_households = []
    for grade in [12, 11, 10, 9]:
        for _ in range(max(0, per_grade[grade])):
            h = None
            if solo_households and srng.random() < 0.2:
                cands = [x for x in solo_households if all(w.chars[m].grade != grade for m in x["members"])]
                if cands:
                    h = srng.choice(cands)
                    solo_households.remove(h)
            if h is None:
                h = gen.household(w, srng)
                solo_households.append(h)
            gen.make_student(w, srng, grade, h)
    initial_relationships(gen, w, gen.streams.get("gen", "rels"))
    if featured:
        for fr in gen.cat.people["featured_relationships"]:
            a, b = keyed[fr["a"]], keyed[fr["b"]]
            for (x, y, spec) in ((a, b, fr.get("ab", fr.get("both"))), (b, a, fr.get("ba", fr.get("both")))):
                if spec:
                    r = w.ensure_rel(x, y, -300)
                    for k, v in spec.items():
                        setattr(r, k, float(v))
                    r.peak_affection = max(r.peak_affection, r.affection)
            w.rels[(a, b)].perceived = fr.get("ab", {}).get("perceived", w.rels[(b, a)].affection)
            w.rels[(b, a)].perceived = fr.get("ba", {}).get("perceived", w.rels[(a, b)].affection)
            if fr.get("bond") == "partner":
                bd = w.bonds.setdefault(pair_key(a, b), {"roles": [], "since": {}})
                bd["roles"].append("partner")
                bd["since"]["partner"] = -150
                w.chars[a].flags["partner"] = b
                w.chars[b].flags["partner"] = a
    crng = gen.streams.get("gen", "clubs")
    for c in sorted(w.students(), key=lambda x: x.id):
        joined = 0
        for g in w.groups.values():
            if g["selection"] != "open" or joined >= 2:
                continue
            iv = c.interests.get(g["skill"], 0)
            if iv >= 50 and crng.random() < (iv - 35) / 60:
                g["members"].append(c.id)
                g["joined"][c.id] = -30
                c.memberships.append(g["id"])
                joined += 1
    w.calendar = calm.build_year(w, gen.cat, 0)
    w.meta = {"generated": {"gen_seed": gen_seed, "students": students, "featured": featured}}
    return w


def new_freshmen(w: World, year: int, count: int, day: int) -> list[Character]:
    """Freshmen for a new school year. Some are younger siblings of current students."""
    gen = Generator(w.gen_seed)
    gen.used_names = {(c.first, c.last) for c in w.chars.values()}
    gen.used_last = {h["last"] for h in w.households.values()}
    rng = gen.streams.get("gen", "intake", year)
    out = []
    for _ in range(count):
        h = None
        cands = [x for x in sorted(w.households.values(), key=lambda x: x["id"])
                 if 1 <= len(x["members"]) <= 2 and all(w.chars[m].role == "student" for m in x["members"])]
        if cands and rng.random() < 0.25:
            h = rng.choice(cands)
        if h is None:
            h = gen.household(w, rng)
        c = gen.make_student(w, rng, 9, h, day=day)
        out.append(c)
    initial_relationships(gen, w, gen.streams.get("gen", "intake-rels", year), day=day, only={c.id for c in out})
    return out
