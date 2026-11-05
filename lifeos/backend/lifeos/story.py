"""Story mode: you, your family, the people you choose, and a generated town around them.

A story spec describes the protagonist, their household and siblings (twins included), any
number of custom characters with their relationships, and how many generated students fill out
each grade. create_story() turns it into a world that starts on the first day of freshman year.
Every custom value is validated; anything left blank is generated from the archetype.
"""
from __future__ import annotations

import datetime as dt

from . import appearance
from . import calendar as calm
from .catalogs import APTITUDES, MOTIVES, TRAITS, Catalogs
from .history import History
from .model import World, pair_key
from .rng import clamp, derive_seed
from .rules import schema
from .worldgen import Generator, _groups, _staff, initial_relationships, pronouns_for, start_gpa

MAX_PER_GRADE = 40   # kids per grade the town starts with (a big school plays slower, more so on a phone)
MAX_CAST = 120       # people you make yourself
FUTURE_GRADES = (6, 7, 8)  # younger kids you make: they start high school as freshmen 1 to 3 years in
COACHABLE = ("football", "basketball", "basketball_girls", "baseball", "softball", "soccer", "soccer_girls")  # high school team ids


def future(p: dict) -> bool:
    """Someone you made who's still in middle school when the story starts."""
    return p.get("role", "student") == "student" and int(p.get("grade", 9) or 9) in FUTURE_GRADES


REL_PRESETS = {
    "twin": {"label": "Twin", "both": {"familiarity": 100, "affection": 60, "trust": 75}, "bond": "twin"},
    "sibling": {"label": "Sibling", "both": {"familiarity": 95, "affection": 42, "trust": 60}, "bond": "sibling"},
    "best_friend": {"label": "Best friend", "both": {"familiarity": 90, "affection": 85, "trust": 82}},
    "close_friend": {"label": "Close friend", "both": {"familiarity": 75, "affection": 62, "trust": 62}},
    "friend": {"label": "Friend", "both": {"familiarity": 55, "affection": 40, "trust": 48}},
    "acquaintance": {"label": "Know each other", "both": {"familiarity": 25, "affection": 8, "trust": 32}},
    "crush": {"label": "Has a crush on them", "ab": {"familiarity": 40, "affection": 30, "attraction": 70, "perceived": 15},
              "ba": {"familiarity": 30, "affection": 15}},
    "admirer": {"label": "They have a crush on this person", "ab": {"familiarity": 30, "affection": 15},
                "ba": {"familiarity": 40, "affection": 30, "attraction": 70, "perceived": 15}},
    "mutual_crush": {"label": "We like each other", "both": {"familiarity": 45, "affection": 35, "attraction": 66, "perceived": 20}},
    "dating": {"label": "Dating", "both": {"familiarity": 85, "affection": 65, "attraction": 72, "trust": 60, "perceived": 60}, "bond": "partner"},
    "ex": {"label": "Ex", "both": {"familiarity": 75, "affection": -10, "attraction": 30, "trust": 20}, "bond": "ex"},
    "rival": {"label": "Rivals", "both": {"familiarity": 60, "affection": -10, "respect": 35, "rivalry": 62}},
    "enemy": {"label": "Can't stand each other", "both": {"familiarity": 60, "affection": -50, "trust": 5, "rivalry": 40}},
    "teammate": {"label": "Teammates growing up", "both": {"familiarity": 60, "affection": 28, "respect": 25, "trust": 45}},
    "neighbor": {"label": "Neighbors", "both": {"familiarity": 50, "affection": 20, "trust": 40}},
    "mentor": {"label": "Looks up to them", "ab": {"familiarity": 50, "affection": 40, "respect": 55, "trust": 60},
               "ba": {"familiarity": 50, "affection": 35, "respect": 30, "trust": 50}},
}
FIELDS = {"familiarity", "affection", "respect", "attraction", "trust", "rivalry", "perceived"}
GUARDIAN_STYLES = ("warm", "strict", "permissive", "distant", "overbearing")
INCOMES = ("low", "middle", "high")
BUILDS = ("slight", "average", "athletic", "strong")


class StoryError(ValueError):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


# --- validation --------------------------------------------------------------------------

def _num(v, lo, hi, path, errors):
    try:
        x = float(v)
    except (TypeError, ValueError):
        errors.append(f"{path} must be a number")
        return None
    if not lo <= x <= hi:
        errors.append(f"{path} must be between {lo} and {hi}")
        return None
    return x


def validate_person(p: dict, path: str, cat: Catalogs, errors: list, allow_staff=False, allow_future=False):
    if not isinstance(p, dict):
        errors.append(f"{path} must be an object")
        return
    if not str(p.get("first", "")).strip():
        errors.append(f"{path}: a first name is required")
    if p.get("gender") not in ("f", "m", "nb"):
        errors.append(f"{path}: gender must be f, m or nb")
    role = p.get("role", "student")
    if role == "staff" and not allow_staff:
        errors.append(f"{path}: only cast members can be staff")
    if role == "student":
        g = p.get("grade", 9)
        if allow_future and g in FUTURE_GRADES:
            pass  # still in middle school: starts at the high school with a later freshman class
        elif g not in (9, 10, 11, 12):
            errors.append(f"{path}: grade must be 9, 10, 11 or 12" + (" (or 6, 7 or 8 for someone who starts high school later)" if allow_future else ""))
    elif role != "staff":
        errors.append(f"{path}: role must be student or staff")
    arch = p.get("archetype")
    if arch and arch not in {a["id"] for a in cat.people["archetypes"]}:
        errors.append(f"{path}: unknown archetype {arch}")
    for layer, keys in (("traits", TRAITS), ("aptitudes", APTITUDES), ("motives", MOTIVES)):
        for k, v in (p.get(layer) or {}).items():
            if k not in keys:
                errors.append(f"{path}.{layer}: unknown {k}")
            else:
                _num(v, 0, 100, f"{path}.{layer}.{k}", errors)
    known = set(cat.skills) | set(cat.hobbies)
    for layer in ("interests", "skills"):
        for k, v in (p.get(layer) or {}).items():
            if k not in (cat.skills if layer == "skills" else known):
                errors.append(f"{path}.{layer}: unknown {k}")
            else:
                _num(v, 0, 100, f"{path}.{layer}.{k}", errors)
    for k in p.get("attracted_to") or []:
        if k not in ("f", "m", "nb"):
            errors.append(f"{path}.attracted_to: {k} must be f, m or nb")
    body = p.get("body") or {}
    if "height_in" in body:
        _num(body["height_in"], 54, 90, f"{path}.body.height_in", errors)
    if body.get("build") and body["build"] not in BUILDS:
        errors.append(f"{path}.body.build must be one of {', '.join(BUILDS)}")
    sp = cat.sports["sports"]
    for s, pos in (p.get("positions") or {}).items():
        if s not in sp:
            errors.append(f"{path}.positions: unknown sport {s}")
        elif pos and pos not in sp[s]["positions"]:
            errors.append(f"{path}.positions.{s}: {pos} isn't a {s} position")
    if p.get("jersey") not in (None, "", 0):
        _num(p["jersey"], 0, 99, f"{path}.jersey", errors)
    bd = p.get("birthday")
    if bd:
        try:
            dt.date(2000, int(bd[0]), int(bd[1]))
        except (TypeError, ValueError, IndexError):
            errors.append(f"{path}.birthday must be [month, day]")
    for r in p.get("relationships") or []:
        if r.get("type") not in REL_PRESETS:
            errors.append(f"{path}.relationships: unknown type {r.get('type')}")
        if "strength" in r:
            _num(r["strength"], -40, 40, f"{path}.relationships.strength", errors)
    if len(str(p.get("bio", ""))) > 500:
        errors.append(f"{path}.bio is longer than 500 characters")
    from . import appearance
    appearance.validate(p.get("look"), path, errors)
    pp = p.get("path")
    if pp:
        if not isinstance(pp, dict):
            errors.append(f"{path}.path must be an object")
        elif pp.get("kind", "college") == "work":
            pass
        elif pp.get("college") not in cat.college_by_id:
            errors.append(f"{path}.path: unknown college {pp.get('college')}")
        elif pp.get("sport"):
            from . import sports as sp_
            col = cat.college_by_id[pp["college"]]
            gender = p.get("gender") or "m"
            fit = sp_.fit_sport(pp["sport"], gender)
            if pp["sport"] not in sp_.SPORTS:
                errors.append(f"{path}.path: unknown sport {pp['sport']}")
            elif not sp_.offers_side(col, fit, gender) or fit not in sp_.sports_for(gender):
                who = {"m": "men's ", "f": "women's "}.get(gender, "") if fit not in sp_.ONLY else ""
                errors.append(f"{path}.path: {col['short']} doesn't have a {who}{fit} team here")
        if role == "staff":
            errors.append(f"{path}.path: staff don't go to college")


def validate_story(spec: dict) -> dict:
    cat = Catalogs()
    errors = []
    if not isinstance(spec, dict):
        raise StoryError(["the story must be an object"])
    me = spec.get("protagonist")
    if not me:
        errors.append("protagonist: required")
    else:
        validate_person(me, "protagonist", cat, errors)
    fam = spec.get("family") or {}
    if fam.get("style") and fam["style"] not in GUARDIAN_STYLES:
        errors.append(f"family.style must be one of {', '.join(GUARDIAN_STYLES)}")
    if fam.get("income") and fam["income"] not in INCOMES:
        errors.append(f"family.income must be one of {', '.join(INCOMES)}")
    pet = fam.get("pet")
    if isinstance(pet, dict) and pet:
        from .pets import SPECIES
        sp = SPECIES.get(pet.get("species") or "dog")
        if not sp:
            errors.append(f"family.pet.species must be one of {', '.join(SPECIES)}")
        else:
            if not str(pet.get("name") or "").strip():
                errors.append("family.pet.name: your pet needs a name")
            if pet.get("breed") and pet["breed"] not in sp["breeds"]:
                errors.append(f"family.pet.breed must be one of {', '.join(sp['breeds'])}")
            if pet.get("coat") and pet["coat"] not in sp["coats"]:
                errors.append(f"family.pet.coat must be one of {', '.join(sp['coats'])}")
    sibs = spec.get("siblings") or []
    if len(sibs) > 6:
        errors.append("at most 6 siblings")
    for i, s in enumerate(sibs):
        validate_person(s, f"siblings[{i}]", cat, errors, allow_future=True)
    cast = spec.get("cast") or []
    if len(cast) > MAX_CAST:
        errors.append(f"at most {MAX_CAST} custom characters")
    keys = {"me"} | {s.get("key") for s in sibs if s.get("key")} | {c.get("key") for c in cast if c.get("key")}
    for i, c in enumerate(cast):
        validate_person(c, f"cast[{i}]", cat, errors, allow_staff=True, allow_future=True)
        if c.get("role") == "staff" and c.get("coach_of") and c["coach_of"] not in COACHABLE:
            errors.append(f"cast[{i}].coach_of must be one of {', '.join(COACHABLE)}")
        for r in c.get("relationships") or []:
            if r.get("to") not in keys:
                errors.append(f"cast[{i}].relationships: '{r.get('to')}' isn't anyone in the story (use 'me' for you)")
    n = spec.get("students_per_grade", 12)
    _num(n, 6, MAX_PER_GRADE, "students_per_grade", errors)
    if errors:
        raise StoryError(errors)
    return spec


# --- building ------------------------------------------------------------------------------

def _birth_day(grade, birthday, rng):
    year = calm.START.year - (grade + 5)
    if birthday:
        m, d = int(birthday[0]), int(birthday[1])
        if m >= 9:
            year -= 1
        try:
            return calm.day_of(dt.date(year, m, d))
        except ValueError:
            return calm.day_of(dt.date(year, m, 28))
    return -int((grade + 5) * 365.25 + rng.uniform(0, 364))


def build_person(w, gen, rng, p: dict, household: dict, day: int = 0):
    """One custom character from a builder spec. Blank fields come from the archetype."""
    grade = int(p.get("grade", 9))
    c = gen.make_student(w, rng, grade, household, archetype=p.get("archetype") or None, first=p["first"].strip(),
                         gender=p["gender"], day=day)
    if p.get("last"):
        c.last = p["last"].strip()
    for layer in ("traits", "aptitudes", "motives"):
        for k, v in (p.get(layer) or {}).items():
            getattr(c, layer)[k] = float(v)
    if p.get("interests"):
        c.interests.update({k: float(v) for k, v in p["interests"].items()})
    sk = p.get("skills") or {}
    for s in gen.cat.world["skills"]:
        sid = s["id"]
        if sid in sk:
            c.skills[sid] = float(sk[sid])
        elif p.get("interests") or p.get("aptitudes"):
            a = c.aptitudes[s["aptitude"]]
            iv = c.interests.get(sid, 0)
            c.skills[sid] = round(clamp(a * 0.3 + iv * 0.28 + (grade - 9) * 2.5, 0, 70), 1)
    if p.get("attracted_to"):
        c.attracted_to = list(p["attracted_to"])
    if p.get("pronouns"):
        c.pronouns = str(p["pronouns"])[:20]
    from . import sports
    body = dict(sports.default_body(c, rng))
    body.update({k: (int(v) if k == "height_in" else v) for k, v in (p.get("body") or {}).items() if v not in (None, "")})
    c.body = body
    c.positions = {k: v for k, v in (p.get("positions") or {}).items() if v}
    sports.fit_to_side(c)  # a girl's baseball is softball; boys and girls play on separate teams
    if p.get("jersey"):
        c.jersey = int(p["jersey"])
    if p.get("color"):
        c.color = str(p["color"])[:9]
    if p.get("bio"):
        c.bio = str(p["bio"]).strip()
    if p.get("look"):
        c.look = {k: v for k, v in p["look"].items() if v not in (None, "")}
    c.birth_day = _birth_day(grade, p.get("birthday"), rng)
    c.gpa = start_gpa(c.skills["academics"], c.aptitudes["academic"], c.traits["discipline"], 0.0)
    pp = p.get("path")
    if pp:
        preset = {"kind": "work"} if pp.get("kind") == "work" else {"kind": "college", "college": pp["college"],
                                                                     "sport": sports.fit_sport(pp.get("sport"), c.gender) or None}
        c.flags["preset_path"] = preset
        sp = preset.get("sport")
        if sp:
            # a recruited athlete plays the sport and is good at it by the time the offer comes
            c.interests[sp] = max(c.interests.get(sp, 0), 82.0)
            col = gen.cat.college_by_id[preset["college"]]
            target = 48 + 0.3 * col["programs"].get(sports.side(sp, c.gender), 60) + (grade - 9) * 2
            if sp not in sk:
                c.skills[sp] = round(max(c.skills.get(sp, 0), target), 1)
            c.aptitudes["athletic"] = max(c.aptitudes["athletic"], 70.0) if "athletic" not in (p.get("aptitudes") or {}) else c.aptitudes["athletic"]
            c.skills["fitness"] = max(c.skills.get("fitness", 0), 55.0)
    c.custom = True
    c.featured = True
    c.flags["confidence_base"] = c.traits["confidence"]
    return c


def build_staff(w, rng, p: dict):
    from .model import Character
    cid = f"staff-{p['first']}-{p.get('last', 'x')}".lower().replace(" ", "-")
    n = 2
    while cid in w.chars:
        cid = f"{cid}-{n}"
        n += 1
    traits = {t: float((p.get("traits") or {}).get(t, rng.gauss(60, 12))) for t in TRAITS}
    c = Character(id=cid, first=p["first"].strip(), last=(p.get("last") or "").strip() or "Smith", gender=p["gender"],
                  pronouns=pronouns_for(p["gender"]), role="staff", grade=None, birth_day=-int(rng.uniform(28, 60) * 365.25),
                  household_id=None, archetype="staff", title=p.get("title") or ("Coach" if p.get("coach_of") else "Mr." if p["gender"] == "m" else "Ms."),
                  role_label=p.get("role_label") or (f"{p['coach_of'].title()} coach" if p.get("coach_of") else "Teacher"),
                  traits={k: clamp(v, 0, 100) for k, v in traits.items()}, aptitudes={a: 55.0 for a in APTITUDES},
                  motives={"achievement": 60.0, "approval": 35.0, "belonging": 50.0, "pleasure": 40.0, "altruism": 60.0, "mastery": 55.0},
                  needs={"energy": 70.0, "social": 60.0, "fun": 55.0, "stress": 30.0}, mood=62.0, money=200.0,
                  bio=p.get("bio") or "", custom=True, featured=True, color=p.get("color") or "#9aa1c4")
    if p.get("look"):
        c.look = {k: v for k, v in p["look"].items() if v not in (None, "")}
    w.chars[cid] = c
    if p.get("coach_of"):
        # a team id ("basketball_girls") or a sport, which means its first team ("basketball" is the boys' team)
        for g in w.groups.values():
            if g["id"] == p["coach_of"] and g["kind"] == "team" and g.get("school") == "hchs":
                g["staff"] = cid
    return c


def apply_relationship(w, a: str, b: str, rtype: str, strength: float = 0.0, day: int = 0):
    pre = REL_PRESETS[rtype]
    A, B = w.chars[a], w.chars[b]
    if rtype in ("crush", "mutual_crush", "dating", "ex") and B.gender not in A.attracted_to:
        A.attracted_to = sorted(set(A.attracted_to) | {B.gender})
    if rtype in ("admirer", "mutual_crush", "dating", "ex") and A.gender not in B.attracted_to:
        B.attracted_to = sorted(set(B.attracted_to) | {A.gender})
    for (x, y, spec) in ((a, b, pre.get("ab", pre.get("both"))), (b, a, pre.get("ba", pre.get("both")))):
        if not spec:
            continue
        r = w.ensure_rel(x, y, day - 400)
        for k, v in spec.items():
            setattr(r, k, float(v))
        if strength:
            r.affection = clamp(r.affection + strength, -100, 100)
            r.trust = clamp(r.trust + strength * 0.5, 0, 100)
        r.peak_affection = max(r.peak_affection, r.affection)
        r.met_day = min(r.met_day, day - 400)
    w.rels[(a, b)].perceived = pre.get("ab", pre.get("both", {})).get("perceived", w.rels[(b, a)].affection)
    w.rels[(b, a)].perceived = pre.get("ba", pre.get("both", {})).get("perceived", w.rels[(a, b)].affection)
    bond = pre.get("bond")
    if bond:
        bd = w.bonds.setdefault(pair_key(a, b), {"roles": [], "since": {}})
        roles = ["sibling", "twin"] if bond == "twin" else [bond]
        for role in roles:
            if role not in bd["roles"]:
                bd["roles"].append(role)
                bd["since"][role] = day - 400
        if bond == "partner":
            w.chars[a].flags["partner"] = b
            w.chars[b].flags["partner"] = a


def _pet(fam: dict):
    """Missing = leave it to chance; null or "none" = no pet; true = a random pet; {species, name} = that pet."""
    if "pet" not in fam:
        return False
    pet = fam["pet"]
    if pet is None or pet == "none" or pet == {}:
        return None
    return pet


def create_story(spec: dict) -> World:
    spec = validate_story(spec)
    seed = int(spec.get("gen_seed") or derive_seed(spec["protagonist"]["first"], "story") % 100000)
    gen = Generator(seed)
    w = World()
    w.gen_seed = seed
    w.seed = int(spec.get("sim_seed") or derive_seed(seed, "sim") % 1_000_000)
    w.name = spec.get("town_name") or gen.cat.world["town"]["name"]
    w.rules = schema().defaults()
    w.rules["history.trace_everyone"] = False
    w.history = History()
    _groups(gen, w)
    _staff(gen, w, gen.streams.get("gen", "staff"))
    rng = gen.streams.get("gen", "story")
    me = spec["protagonist"]
    fam = spec.get("family") or {}
    last = (fam.get("last") or me.get("last") or "Rivera").strip()
    hh = gen.household(w, rng, last=last, style=fam.get("style") or "warm", income=fam.get("income") or "middle",
                       guardians=fam.get("guardians") or None, pet=_pet(fam), key="family")
    keymap = {}
    pc = build_person(w, gen, rng, dict(me, grade=me.get("grade", 9)), hh)
    keymap["me"] = pc.id
    sib_specs = spec.get("siblings") or []
    twins_bd = {}
    incoming = []  # younger siblings and people you made who start high school in a later year
    for i, s in enumerate(sib_specs):
        s = dict(s)
        if future(s):
            incoming.append({"key": s.get("key") or f"sib{i}", "kind": "sibling", "first": s["first"].strip(), "grade": int(s["grade"]),
                             "year": 9 - int(s["grade"]), "spec": s})
            continue
        if s.get("twin_of") and s["twin_of"] in twins_bd and not s.get("birthday"):
            s["birthday"] = twins_bd[s["twin_of"]]
        c = build_person(w, gen, rng, s, hh)
        k = s.get("key") or f"sib{i}"
        keymap[k] = c.id
        if s.get("twin_of") in keymap:
            c.birth_day = w.chars[keymap[s["twin_of"]]].birth_day
        twins_bd[k] = s.get("birthday")
        # siblings on auto look like you when you picked your look
        fam_look = appearance.resemble(c, me.get("look") or {})
        if fam_look:
            c.look = {**(c.look or {}), **fam_look}
    for i, cs in enumerate(spec.get("cast") or []):
        if future(cs):
            incoming.append({"key": cs.get("key") or f"cast{i}", "kind": "cast", "first": cs["first"].strip(), "grade": int(cs["grade"]),
                             "year": 9 - int(cs["grade"]), "spec": cs})
            continue
        if cs.get("role") == "staff":
            c = build_staff(w, rng, cs)
        else:
            hkey = cs.get("household")
            if hkey and hkey in keymap and w.chars[keymap[hkey]].household_id:
                h = w.households[w.chars[keymap[hkey]].household_id]
            else:
                h = gen.household(w, rng, last=(cs.get("last") or None))
            c = build_person(w, gen, rng, cs, h)
        if cs.get("key"):
            keymap[cs["key"]] = c.id
    # generated students to fill each grade
    per = int(spec.get("students_per_grade", 12))
    counts = {g: sum(1 for c in w.students() if c.grade == g) for g in (9, 10, 11, 12)}
    srng = gen.streams.get("gen", "students")
    solo = []
    for grade in (12, 11, 10, 9):
        for _ in range(max(0, per - counts[grade])):
            h = None
            if solo and srng.random() < 0.2:
                cands = [x for x in solo if all(w.chars[m].grade != grade for m in x["members"])]
                if cands:
                    h = srng.choice(cands)
                    solo.remove(h)
            if h is None:
                h = gen.household(w, srng)
                solo.append(h)
            gen.make_student(w, srng, grade, h)
    initial_relationships(gen, w, gen.streams.get("gen", "rels"))
    # the relationships the user described
    for i, s in enumerate(sib_specs):
        k = s.get("key") or f"sib{i}"
        if k not in keymap:
            continue  # not in high school yet: that comes when they arrive
        rtype = "twin" if s.get("twin_of") == "me" else "sibling"
        apply_relationship(w, pc.id, keymap[k], s.get("relationship", rtype) if s.get("relationship") in REL_PRESETS else rtype,
                           float(s.get("strength", 0) or 0))
        if s.get("twin_of") and s["twin_of"] in keymap and s["twin_of"] != "me":
            apply_relationship(w, keymap[k], keymap[s["twin_of"]], "twin")
    for s in sib_specs + (spec.get("cast") or []):
        src = keymap.get(s.get("key")) if s.get("key") else None
        for r in s.get("relationships") or []:
            if src and r.get("to") in keymap and keymap[r["to"]] != src:
                apply_relationship(w, src, keymap[r["to"]], r["type"], float(r.get("strength", 0) or 0))
    for r in me.get("relationships") or []:
        if r.get("to") in keymap and keymap[r["to"]] != pc.id:
            apply_relationship(w, pc.id, keymap[r["to"]], r["type"], float(r.get("strength", 0) or 0))
    # people who know your older siblings know of you
    for sid in [keymap[k] for k in keymap if k != "me" and w.chars[keymap[k]].household_id == pc.household_id]:
        for (x, y), r in list(w.rels.items()):
            if y == sid and x != pc.id and r.familiarity > 30 and w.chars[x].role in ("student", "staff"):
                mine = w.ensure_rel(x, pc.id, -200)
                mine.familiarity = max(mine.familiarity, round(r.familiarity * 0.35, 1))
                back = w.ensure_rel(pc.id, x, -200)
                back.familiarity = max(back.familiarity, round(r.familiarity * 0.25, 1))
    crng = gen.streams.get("gen", "clubs")
    for c in sorted(w.students(), key=lambda x: x.id):
        if c.grade == 9:
            continue
        joined = 0
        for g in w.groups.values():
            if g["selection"] != "open" or joined >= 2 or g.get("adult") or g.get("school") != "hchs":
                continue
            iv = c.interests.get(g["skill"], 0)
            if iv >= 50 and crng.random() < (iv - 35) / 60:
                g["members"].append(c.id)
                g["joined"][c.id] = -30
                c.memberships.append(g["id"])
                joined += 1
    w.calendar = calm.build_year(w, gen.cat, 0)
    w.meta = {"generated": {"gen_seed": seed, "students": per * 4, "featured": False},
              "protagonist": pc.id, "story": {"title": spec.get("title") or f"The {last} Years", "start_day": 0, "years": 7,
                                              "spec": spec, "keys": keymap},
              "control": {"focus": "balanced", "ask_invites": False, "ask_romance": True, "stop_before_games": True, "stop_on_big": True},
              "incoming": incoming}
    _scale_rosters(w, per)
    return w


def _scale_rosters(w, per: int):
    """A bigger school has bigger teams and casts, so making the team is about as hard as it is at 12 kids a grade."""
    k = max(1.0, per / 12)
    if k == 1.0:
        return
    for g in w.groups.values():
        if g.get("school") == "hchs" and g["kind"] in ("team", "production"):
            g["capacity"] = round(g["capacity"] * k)
            if g.get("jv_capacity"):
                g["jv_capacity"] = round(g["jv_capacity"] * k)


def incoming_view(w) -> list:
    """The people you made who aren't in high school yet, for the phone and the lab."""
    from . import calendar as calm
    y = calm.school_year_of(w.day)
    out = []
    for x in w.meta.get("incoming", []):
        if x.get("arrived") is not None:
            continue
        n = x["year"] - y
        grade = 9 - n if n > 0 else 8
        out.append({"key": x["key"], "kind": x["kind"], "first": x["first"], "gender": x["spec"].get("gender"),
                    "grade": grade, "year_label": f"{grade}th grade", "years": n,
                    "starts": "Starts high school next fall" if n <= 1 else f"Starts high school in {n} years",
                    "look": x["spec"].get("look") or {}, "color": x["spec"].get("color")})
    return out


def arrive(sim, year: int) -> list:
    """Sept 1: the people you made who were still in middle school start high school with this freshman class."""
    from .worldgen import Generator, initial_relationships
    w = sim.w
    due = [x for x in w.meta.get("incoming", []) if x["year"] <= year and x.get("arrived") is None]
    if not due:
        return []
    gen = Generator(w.gen_seed)
    gen.used_names = {(c.first, c.last) for c in w.chars.values()}
    gen.used_last = {h["last"] for h in w.households.values()}
    rng = gen.streams.get("gen", "arrivals", year)
    st = w.meta.setdefault("story", {})
    keys = st.setdefault("keys", {})
    spec = st.get("spec") or {}
    pc = w.chars.get(w.meta.get("protagonist") or "")
    built = []
    for x in due:
        s = dict(x["spec"])
        hk = s.get("household")
        if x["kind"] == "sibling" and pc and pc.household_id in w.households:
            h = w.households[pc.household_id]
        elif hk in keys and w.chars[keys[hk]].household_id in w.households:
            h = w.households[w.chars[keys[hk]].household_id]
        else:
            h = gen.household(w, rng, last=(s.get("last") or None))
        c = build_person(w, gen, rng, dict(s, grade=9), h, day=w.day)
        c.birth_day = _birth_day(int(s["grade"]), s.get("birthday"), rng)
        if s.get("twin_of") in keys and s["twin_of"] != "me":
            c.birth_day = w.chars[keys[s["twin_of"]]].birth_day
        if x["kind"] == "sibling":
            fam_look = appearance.resemble(c, (spec.get("protagonist") or {}).get("look") or {})
            if fam_look:
                c.look = {**(c.look or {}), **fam_look}
        keys[x["key"]] = c.id
        x["arrived"], x["id"] = w.day, c.id
        built.append((x, c))
    initial_relationships(gen, w, gen.streams.get("gen", "arrival-rels", year), day=w.day, only={c.id for _, c in built})
    new = {x["key"] for x, _ in built}
    for x, c in built:
        s = x["spec"]
        if x["kind"] == "sibling" and pc:
            apply_relationship(w, pc.id, c.id, s["relationship"] if s.get("relationship") in REL_PRESETS else "sibling",
                               float(s.get("strength", 0) or 0), day=w.day)
        if s.get("twin_of") in keys and s["twin_of"] != "me":
            apply_relationship(w, c.id, keys[s["twin_of"]], "twin", day=w.day)
    # the relationships you described that involve someone who just arrived, in either direction
    people = [("me", spec.get("protagonist") or {})] + [(s.get("key") or f"sib{i}", s) for i, s in enumerate(spec.get("siblings") or [])] \
        + [(s.get("key") or f"cast{i}", s) for i, s in enumerate(spec.get("cast") or [])]
    for k, s in people:
        for r in s.get("relationships") or []:
            a, b = keys.get(k), keys.get(r.get("to"))
            if a and b and a != b and (k in new or r.get("to") in new) and r.get("type") in REL_PRESETS:
                apply_relationship(w, a, b, r["type"], float(r.get("strength", 0) or 0), day=w.day)
    return [c for _, c in built]


def begin(sim):
    """After the Simulation is built: the first moment of the story, the pets and the phone."""
    p = sim.w.meta.get("protagonist")
    if p:
        start_phone(sim)
        sim.moment_trigger("first_day", p, {})


def start_phone(sim):
    from . import messages, pets
    messages.phone(sim.w)
    messages.seed_contacts(sim)
    pets.ensure(sim)
    messages.start_texts(sim)


def story_circle(w) -> set:
    """Characters whose every decision is traced in story mode: you and the people near you."""
    p = w.meta.get("protagonist")
    if not p or p not in w.chars:
        return set()
    out = {p}
    pc = w.chars[p]
    h = w.households.get(pc.household_id)
    if h:
        out |= set(h["members"])
    out |= {c.id for c in w.chars.values() if c.custom}
    rels = sorted(((r.affection + r.attraction * 0.5 + r.familiarity * 0.3, o) for o, r in w.out.get(p, {}).items()), reverse=True)[:14]
    out |= {o for _, o in rels}
    for gid in pc.memberships:
        out |= set(w.groups[gid]["members"])
        if w.groups[gid].get("staff"):
            out.add(w.groups[gid]["staff"])
    return out


# --- the dashboard ------------------------------------------------------------------------

def progress(w) -> dict:
    st = w.meta.get("story", {})
    total = int(st.get("years", 7) * 365)
    done = w.day - st.get("start_day", 0)
    return {"day": done, "total": total, "pct": round(min(100.0, 100.0 * done / total), 1), "year": done // 365 + 1,
            "complete": bool(st.get("complete"))}


def career(c) -> dict:
    out = {}
    for k, st in c.stats.items():
        sport = st["sport"]
        o = out.setdefault(sport, {"games": 0, "starts": 0, "wins": 0, "losses": 0, "line": {}, "seasons": 0})
        o["games"] += st["games"]
        o["starts"] += st["starts"]
        o["wins"] += st["wins"]
        o["losses"] += st["losses"]
        o["seasons"] += 1
        for kk, v in st["line"].items():
            o["line"][kk] = o["line"].get(kk, 0) + v
    return out


def summary(sim, char_summary, rel_view, ev_out) -> dict:
    from . import moments, sports
    w = sim.w
    p = w.meta.get("protagonist")
    if not p or p not in w.chars:
        return {"active": False}
    c = w.chars[p]
    cal = sim.cat.world["calendar"]
    h = w.households.get(c.household_id) or {}
    fam = []
    for sid in sim.siblings(p):
        s = w.chars[sid]
        twin_of = next((o for o in [p] + sim.siblings(p) if o != sid and "twin" in (w.bond(sid, o) or {"roles": []})["roles"]), None)
        fam.append({"id": sid, "year_label": s.year_label, "location": s.location, "path": s.path, "twin": twin_of is not None,
                    "twin_of": twin_of,
                    "mine": rel_view(sim, w.rels[(p, sid)]) if (p, sid) in w.rels else None,
                    "theirs": rel_view(sim, w.rels[(sid, p)]) if (sid, p) in w.rels else None})
    people = []
    for oid, r in w.out.get(p, {}).items():
        o = w.chars.get(oid)
        if not o or oid in h.get("members", []) or o.status != "active":
            continue
        back = w.rels.get((oid, p))
        score = abs(r.affection) + r.attraction * 0.6 + r.rivalry * 0.4 + r.familiarity * 0.2
        people.append((score, {"id": oid, "mine": rel_view(sim, r), "theirs": rel_view(sim, back) if back else None,
                               "roles": (w.bond(p, oid) or {"roles": []})["roles"], "location": o.location}))
    people.sort(key=lambda x: -x[0])
    teams = []
    for gid in c.memberships:
        g = w.groups[gid]
        if g["kind"] != "team":
            continue
        nxt = next((i for i in w.calendar if i.get("group") == gid and i["kind"] == "game" and i["day"] >= w.day), None)
        teams.append({"id": gid, "name": g["name"], "sport": g["skill"], "level": g.get("levels", {}).get(p, "varsity"),
                      "captain": p in g.get("leaders", []), "record": g["record"], "position": c.positions.get(g["skill"]),
                      "rating": round(sports.rating(c, g["skill"]), 1), "starter": bool(c.flags.get(f"started:{gid}:{g.get('levels', {}).get(p, 'varsity')}")),
                      "bench_streak": c.flags.get("bench_streak", 0), "next_game": nxt and {"day": nxt["day"], "date": calm.label(nxt["day"]), "name": nxt["name"]},
                      "coach": g.get("staff")})
    seasons = [dict(st, key=k) for k, st in sorted(c.stats.items(), key=lambda x: (x[0].split(":")[1], x[0]))]
    feed = [ev_out(w.history.events[e]) for e in w.history.by_char.get(p, []) if e in w.history.events
            and w.history.events[e]["importance"] >= 8][::-1][:60]
    upcoming = []
    for i in w.calendar:
        if i["day"] < w.day or i["day"] > w.day + 35:
            continue
        mine = (i.get("group") in c.memberships) or (i["kind"] in ("dance", "exam", "report_card", "graduation", "admissions", "college_decision")
                                                       and i.get("school", "hchs") == c.school) or \
               (i["kind"] in ("tryout", "audition", "election") and w.groups.get(i.get("group"), {}).get("school") == c.school)
        if mine and not (i["kind"] == "exam" and i.get("weight", 1) < 2):
            upcoming.append({"day": i["day"], "date": calm.label(i["day"]), "kind": i["kind"], "name": i["name"]})
    inbox = [dict(i, from_name=w.chars[i["from"]].name) for i in w.meta.get("inbox", []) if i["to"] == p and i["status"] == "pending"]
    pend = [{k: v for k, v in m.items() if k != "_choices"} for m in moments.pending(w)]
    col = w.meta.get("college")
    return {
        "active": True, "title": w.meta["story"].get("title"), "progress": progress(w), "protagonist": p,
        "me": dict(char_summary(sim, c), year_label=c.year_label, age=c.age(w.day), needs=c.needs, money=round(c.money, 2),
                   gpa_history=c.gpa_history, location=c.location, school=c.school, body=c.body, positions=c.positions,
                   jersey=c.jersey, path=c.path, injured=c.flags.get("injured_until", -1) >= w.day,
                   injury=c.flags.get("injury") if c.flags.get("injured_until", -1) >= w.day else None,
                   injured_until=calm.label(c.flags["injured_until"]) if c.flags.get("injured_until", -1) >= w.day else None,
                   goals=[g for g in c.goals if g["status"] == "active"]),
        "date": calm.label(w.day), "term": calm.term_label(w.day, cal),
        "household": h and {k: h.get(k) for k in ("name", "guardians", "style_label", "income", "pet")},
        "family": fam, "people": [x for _, x in people[:16]],
        "teams": teams, "seasons": seasons, "career": career(c), "awards": c.awards[::-1], "incoming": incoming_view(w),
        "recruiting": {"offers": c.recruiting.get("offers", []), "admits": c.recruiting.get("admits", []),
                       "score": c.recruiting.get("score", {}),
                       "lost_offers": c.recruiting.get("lost_offers", []),
                       "interest": sorted([{"college": k.split(":")[0], "name": sim.cat.college_by_id[k.split(":")[0]]["name"],
                                            "short": sim.cat.college_by_id[k.split(":")[0]]["short"],
                                            "tier": sim.cat.college_by_id[k.split(":")[0]]["tier"],
                                            "conference": sim.cat.college_by_id[k.split(":")[0]].get("conference"),
                                            "min_gpa": sim.cat.college_by_id[k.split(":")[0]].get("athlete_min_gpa"),
                                            "sport": k.split(":")[1], "level": v}
                                           for k, v in c.recruiting.get("interest", {}).items()], key=lambda x: -x["level"])[:12]},
        "draft": {"result": c.recruiting.get("draft"),
                  "projection": sports.draft_score(sim, c) if sports.plays_college_baseball(w, c) else None},
        "setting": {"town": sim.cat.world["town"], "school": sim.cat.world["school"]},
        "college": col, "upcoming": upcoming[:12], "feed": feed, "inbox": inbox, "moments": pend,
        "control": moments.control(w), "sports_catalog": sim.cat.sports["sports"],
    }
