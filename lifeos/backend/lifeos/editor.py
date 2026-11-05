"""The editor: change anyone, and anything between any two people.

For setting a story up the way you want it (or fixing it later). On the phone it's a switch on the Me tab (on to start):
every person gets an Edit button, and the editor lists everyone in your world. For a person you can change their name,
bio and look, their personality, talents, what drives them, skills, interests, and how they're doing right now (mood,
energy, stress, popularity, money, GPA). For any two people you can set how each feels about the other (closeness,
attraction, trust, respect, rivalry, how well they know each other) or pick a preset (friends, best friends, a crush,
dating, exes, rivals...). Dating is real: it ends whoever they were with before.

Edits are quiet: no texts, no "you became friends" news, nothing in your feed. Labels and crushes just update to match.
Each save is one small event in the lab's history, so you can see what was changed.
"""
from __future__ import annotations

from .catalogs import APTITUDES, MOTIVES, NEEDS, TRAITS
from .history import Effects
from .model import REL_FIELDS
from .rng import clamp

REL_LABELS = {"affection": "Closeness", "attraction": "Attraction", "trust": "Trust", "respect": "Respect", "rivalry": "Rivalry",
              "familiarity": "Know each other", "perceived": "Think the other likes them"}
REL_ORDER = ["affection", "attraction", "trust", "respect", "rivalry", "familiarity"]
PRESETS = [("strangers", "Strangers"), ("acquaintance", "Know each other"), ("friend", "Friends"), ("close_friend", "Close friends"),
           ("best_friend", "Best friends"), ("crush", "{a} has a crush"), ("admirer", "{b} has a crush"), ("mutual_crush", "Like each other"),
           ("dating", "Dating"), ("ex", "Exes"), ("rival", "Rivals"), ("enemy", "Can't stand each other"), ("mentor", "{a} looks up to {b}")]
SCALARS = {"mood": (0, 100), "popularity": (0, 100), "money": (0, 100000), "gpa": (0, 4)}


class EditorError(ValueError):
    pass


def on(w) -> bool:
    from .moments import control
    return bool(control(w).get("editor", True))


def _mini(w, cid) -> dict:
    from .appearance import look_of
    c = w.chars[cid]
    return {"id": c.id, "name": c.name, "first": c.first, "color": c.color, "look": look_of(c), "year": c.year_label, "role": c.role}


def schema(sim) -> dict:
    """What can be edited, with labels (the phone uses its own words for personality and drives)."""
    cat = sim.cat
    return {"traits": TRAITS, "aptitudes": APTITUDES, "motives": MOTIVES, "needs": NEEDS,
            "skills": [{"id": k, "label": v["label"]} for k, v in cat.skills.items()],
            "interests": [{"id": k, "label": v["label"]} for k, v in cat.skills.items()] +
                         [{"id": k, "label": v["label"][0].upper() + v["label"][1:]} for k, v in cat.hobbies.items()],
            "rel_fields": [{"id": f, "label": REL_LABELS[f], "min": REL_FIELDS[f][0], "max": REL_FIELDS[f][1]} for f in REL_ORDER],
            "crush_at": sim.w.rules["rel.crush_threshold"], "friend_at": sim.w.rules["rel.friend_threshold"],
            "scalars": {k: list(v) for k, v in SCALARS.items()}}


def people(sim) -> list:
    """Everyone in the world, closest to you first, then your grade, then everyone else."""
    w = sim.w
    me = w.meta.get("protagonist")
    sibs = set(sim.siblings(me)) if me else set()
    out = []
    for c in w.chars.values():
        if c.status not in ("active",) and c.id != me:
            continue
        r = w.rels.get((me, c.id)) if me else None
        same_home = bool(c.household_id and me and c.household_id == w.chars[me].household_id)
        out.append({**_mini(w, c.id), "grade": c.grade, "me": c.id == me, "family": c.id in sibs or same_home,
                    "known": bool(r and r.familiarity > 0), "label": r.label if r else None,
                    "close": round((r.affection + r.familiarity) if r else -999, 1)})
    mg = w.chars[me].grade if me else None
    out.sort(key=lambda x: (not x["me"], not x["family"], not x["known"], -x["close"] if x["known"] else 0, x["grade"] != mg, x["name"]))
    return out


def _rel_view(r) -> dict | None:
    if r is None:
        return None
    return {**{f: round(getattr(r, f), 1) for f in REL_ORDER + ["perceived"]}, "label": r.label, "crush": r.crush}


def person(sim, cid) -> dict:
    w = sim.w
    c = w.chars.get(cid)
    if c is None:
        raise EditorError("no such person")
    me = w.meta.get("protagonist")
    rels = []
    for o, r in w.out.get(cid, {}).items():
        if o not in w.chars or w.chars[o].status != "active":
            continue
        back = w.rels.get((o, cid))
        bond = w.bond(cid, o)
        rels.append({**_mini(w, o), "roles": (bond or {}).get("roles", []), "ab": _rel_view(r), "ba": _rel_view(back),
                     "score": abs(r.affection) + r.familiarity + (200 if bond and bond.get("roles") else 0) + (300 if o == me else 0)})
    rels.sort(key=lambda x: -x["score"])
    from . import calendar as calm
    bd = calm.date_of(c.birth_day)
    return {**_mini(w, cid), "last": c.last, "bio": c.bio, "gender": c.gender, "grade": c.grade, "is_me": cid == me,
            "pronouns": c.pronouns, "attracted_to": list(c.attracted_to or []), "birthday": [bd.month, bd.day],
            "archetype": c.archetype, "body": dict(c.body or {}), "positions": dict(c.positions or {}), "jersey": c.jersey or None,
            "path": dict(c.path or {}), "staff": c.role == "staff",
            "look_locked": dict(c.look or {}), "traits": _round(c.traits), "aptitudes": _round(c.aptitudes), "motives": _round(c.motives),
            "skills": _round(c.skills), "interests": _round(c.interests), "needs": _round(c.needs),
            "mood": round(c.mood, 1), "popularity": round(c.popularity, 1), "money": round(c.money, 2), "gpa": round(c.gpa, 2),
            "student": c.role in ("student", "alumni"), "partner": c.flags.get("partner"), "flirt": flirt_view(c),
            "with_me": None if cid == me or not me else {"ab": _rel_view(w.rels.get((me, cid))), "ba": _rel_view(w.rels.get((cid, me)))},
            "rels": rels[:24]}


def _round(d: dict) -> dict:
    return {k: round(v, 1) for k, v in d.items()}


def _num(v, lo, hi, what, errors):
    try:
        x = float(v)
    except (TypeError, ValueError):
        errors.append(f"{what} must be a number")
        return None
    if not lo <= x <= hi:
        errors.append(f"{what} must be between {lo:g} and {hi:g}")
        return None
    return x


def _event(sim, actors, label):
    ev = sim.new_event("lab", "edit", actors, [], 3, {"label": label, "by": "editor"})
    ev["text"] = label
    return ev


def save_person(sim, cid, body: dict) -> dict:
    """Apply a batch of changes to one person. Everything is checked first; nothing changes if anything's wrong."""
    from . import appearance
    w = sim.w
    c = w.chars.get(cid)
    if c is None:
        raise EditorError("no such person")
    errors, plan = [], []
    allowed = {"traits": TRAITS, "aptitudes": APTITUDES, "motives": MOTIVES, "needs": NEEDS, "skills": list(sim.cat.skills),
               "interests": list(sim.cat.skills) + list(sim.cat.hobbies)}
    for key, val in body.items():
        if key in allowed:
            if not isinstance(val, dict):
                errors.append(f"{key} must be an object")
                continue
            for k, v in val.items():
                if k not in allowed[key]:
                    errors.append(f"{key}.{k} isn't something people have")
                    continue
                x = _num(v, 0, 100, f"{key}.{k}", errors)
                if x is not None:
                    plan.append((key, k, x))
        elif key in SCALARS:
            lo, hi = SCALARS[key]
            x = _num(val, lo, hi, key, errors)
            if x is not None:
                plan.append((key, None, x))
        elif key in ("first", "last"):
            if not isinstance(val, str) or not val.strip() or len(val.strip()) > 40:
                errors.append(f"{key} name must be 1 to 40 characters")
            else:
                plan.append((key, None, val.strip()))
        elif key == "bio":
            if not isinstance(val, str) or len(val) > 500:
                errors.append("bio must be text under 500 characters")
            else:
                plan.append((key, None, val.strip()))
        elif key == "look":
            if val in (None, {}):
                plan.append(("look", None, {}))
            else:
                appearance.validate(val, "look", errors)
                plan.append(("look", None, dict(val)))
        elif key == "flirt":
            x = _flirt(c, val, errors)
            if x is not None:
                plan.append(("flirt", None, x))
        elif key in WHO:
            x = _who(sim, c, key, val, body, errors)
            if x is not None:
                plan.append((key, None, x))
        else:
            errors.append(f"{key} can't be edited here")
    if errors:
        raise EditorError("; ".join(errors))
    if not plan:
        return person(sim, cid)
    ev = _event(sim, [cid], f"Editor: changed {c.name} ({', '.join(sorted({k for k, _, _ in plan}))})")
    fx = Effects(w, ev)
    for key, k, v in plan:
        if k is not None:
            before = getattr(c, key).get(k, 0.0)
            if abs(v - before) > 1e-9:
                fx.attr(cid, key, k, v - before, "editor")
            if key == "traits" and k == "confidence":
                c.flags["confidence_base"] = v
        elif key == "flirt":
            if w.tracing:
                ev["changes"].append([cid, "tastes", dict(c.flags.get("tastes") or {}), v, "editor"])
            if v:
                c.flags["tastes"] = v
            else:
                c.flags.pop("tastes", None)
            from .chat import tastes
            from .messages import phone
            known = phone(w).get("tastes", {}).get(cid)
            if known:  # what you'd learned about them is what's true now
                now = tastes(c)
                for k in list(known):
                    if k in now:
                        known[k] = now[k]
        elif key in ("first", "last", "bio", "look") or key in WHO:
            attr = {"birthday": "birth_day"}.get(key, key)
            if w.tracing:
                ev["changes"].append([cid, attr, getattr(c, attr), v, "editor"])
            setattr(c, attr, v)
            if key == "gender" and "pronouns" not in body:
                from .worldgen import pronouns_for
                c.pronouns = pronouns_for(v)
        else:
            fx.scalar(cid, key, v, "editor")
    if {"gender", "attracted_to"} & {k for k, _, _ in plan}:  # who can be into who changed: what no longer fits goes
        from . import social
        w.meta["romance_rules"] = 0
        social.tidy_romance(sim)
    from . import groundwork
    groundwork.note_person(w, cid, body)
    ev["text"] = ev["data"]["label"] = f"Editor: changed {c.name} ({', '.join(sorted({k for k, _, _ in plan}))})"  # the new name, if it changed
    sim.finish(ev, fx)
    return person(sim, cid)


# --- what works when you flirt with them ---------------------------------------------------------------------------

FLIRT_SAY = {1: "Loves it", 0: "It's fine", -1: "Not into it"}


def flirt_view(c) -> dict:
    """Each style: how it goes over with them, and whether that's you (set in the editor) or their personality."""
    from .chat import STYLE_WORD, STYLES, personality_tastes, tastes
    now, base, mine = tastes(c), personality_tastes(c), (c.flags or {}).get("tastes") or {}
    return {"styles": [{"style": k, "label": STYLE_WORD[k][0], "value": now[k], "say": FLIRT_SAY[now[k]], "set": k in mine,
                        "personality": base[k]} for k in STYLES], "custom": bool(mine)}


def _flirt(c, val, errors):
    """{"tease": 1, "sweet": -1, ...} on top of what's set; a style set to null goes back to their personality, and null
    for the whole thing puts every style back. -> the new set (None: something's wrong, said in errors)."""
    from .chat import STYLES
    if val is None:
        return {}
    if not isinstance(val, dict):
        errors.append("flirt must be an object of style: 1, 0 or -1")
        return None
    out = dict((c.flags or {}).get("tastes") or {})
    bad = False
    for k, v in val.items():
        if k not in STYLES:
            errors.append(f"{k} isn't a way to flirt (use {', '.join(STYLES)})")
            bad = True
        elif v is None:
            out.pop(k, None)
        elif isinstance(v, bool) or v not in (-1, 0, 1):
            errors.append(f"flirt.{k} must be 1 (loves it), 0 (fine) or -1 (not into it)")
            bad = True
        else:
            out[k] = int(v)
    return None if bad else out


# --- who they are: what the story builder sets (gender, who they're into, birthday, body, sports, what's next) ----------

WHO = ("gender", "pronouns", "attracted_to", "birthday", "archetype", "body", "positions", "jersey", "path")
GENDERS = ("f", "m", "nb")


def _who(sim, c, key, val, body, errors):
    """One of WHO, checked the way the story builder checks it -> the value to set (None: something's wrong, said in errors)."""
    import datetime as dt
    from . import calendar as calm
    from .story import BUILDS
    cat = sim.cat
    if key == "gender":
        if val not in GENDERS:
            errors.append("gender must be f, m or nb")
            return None
        return val
    if key == "pronouns":
        if not isinstance(val, str) or not val.strip() or len(val) > 20:
            errors.append("pronouns must be 1 to 20 characters")
            return None
        return val.strip()
    if key == "attracted_to":
        if not isinstance(val, list) or any(x not in GENDERS for x in val):
            errors.append("attracted_to must be a list of f, m, nb (or empty)")
            return None
        return sorted(set(val))
    if key == "birthday":
        try:
            m, d = int(val[0]), int(val[1])
            dt.date(2000, m, d)
        except (TypeError, ValueError, IndexError):
            errors.append("birthday must be [month, day]")
            return None
        old = calm.date_of(c.birth_day)
        cohort = old.year + (1 if old.month >= 9 else 0)  # (they stay in their own class)
        year = cohort - (1 if m >= 9 else 0)
        try:
            return calm.day_of(dt.date(year, m, d))
        except ValueError:
            return calm.day_of(dt.date(year, m, 28))
    if key == "archetype":
        if val not in {a["id"] for a in cat.people["archetypes"]}:
            errors.append(f"unknown type {val}")
            return None
        return val
    if key == "body":
        if not isinstance(val, dict):
            errors.append("body must be an object")
            return None
        out = dict(c.body or {})
        for k, v in val.items():
            if k == "height_in":
                if v in (None, ""):
                    out.pop(k, None)
                    continue
                x = _num(v, 54, 90, "height", errors)
                if x is not None:
                    out[k] = int(round(x))
            elif k == "build":
                if v in (None, ""):
                    out.pop(k, None)
                elif v not in BUILDS:
                    errors.append(f"build must be one of {', '.join(BUILDS)}")
                else:
                    out[k] = v
            else:
                errors.append(f"body.{k} can't be edited")
        return out
    if key == "positions":
        if not isinstance(val, dict):
            errors.append("positions must be an object")
            return None
        sp = cat.sports["sports"]
        out = dict(c.positions or {})
        for sport, pos in val.items():
            if sport not in sp:
                errors.append(f"unknown sport {sport}")
            elif pos in (None, ""):
                out.pop(sport, None)
            elif pos not in sp[sport]["positions"]:
                errors.append(f"{pos} isn't a {sport} position")
            else:
                out[sport] = pos
        return out
    if key == "jersey":
        if val in (None, ""):
            return 0
        x = _num(val, 0, 99, "jersey", errors)
        return None if x is None else int(x)
    if key == "path":
        if c.role == "staff":
            errors.append("staff don't go to college")
            return None
        if not val:
            return {}
        if not isinstance(val, dict):
            errors.append("path must be an object")
            return None
        if val.get("kind") == "work":
            return {"kind": "work"}
        if val.get("college") not in cat.college_by_id:
            errors.append(f"unknown college {val.get('college')}")
            return None
        out = {"kind": "college", "college": val["college"]}
        if val.get("sport"):
            from . import sports as sp_
            gender = body.get("gender") or c.gender or "m"
            col = cat.college_by_id[val["college"]]
            fit = sp_.fit_sport(val["sport"], gender)
            if val["sport"] not in sp_.SPORTS:
                errors.append(f"unknown sport {val['sport']}")
                return None
            if not sp_.offers_side(col, fit, gender) or fit not in sp_.sports_for(gender):
                errors.append(f"{col['short']} doesn't have that {fit} team")
                return None
            out["sport"] = val["sport"]
        return out
    return None


def create_person(sim, body: dict) -> dict:
    """Someone new, in the middle of the story: a student (a grade) or a teacher/coach (staff), who they are to you, and
    their type. Everything else is generated, then editable like anyone. {"id", "name"}"""
    from .story import REL_PRESETS
    errors = []
    first = str(body.get("first") or "").strip()
    if not first or len(first) > 40:
        errors.append("a first name (up to 40 characters) is needed")
    if body.get("gender") not in GENDERS:
        errors.append("pick a gender")
    staff = body.get("role") == "staff"
    spec = {"first": first, "last": str(body.get("last") or "").strip()[:40], "gender": body.get("gender"),
            "role": "staff" if staff else "student"}
    if not staff:
        try:
            g = int(body.get("grade", 9))
        except (TypeError, ValueError):
            g = 0
        if g not in (9, 10, 11, 12):
            errors.append("grade must be 9, 10, 11 or 12")
        spec["grade"] = g
        if body.get("family"):
            spec["household"] = "family"
    if body.get("archetype"):
        spec["archetype"] = body["archetype"]
    rel = body.get("to_me")
    if rel:
        if rel not in REL_PRESETS:
            errors.append(f"unknown relationship {rel}")
        else:
            spec["relationships"] = [{"to": "me", "type": rel}]
    if errors:
        raise EditorError("; ".join(errors))
    c = make_person(sim, spec)
    from . import groundwork
    groundwork.note_added(sim.w, c.id, spec)
    return {"id": c.id, "name": c.name}


def make_person(sim, spec: dict, extra: dict | None = None):
    """Make someone from a builder spec, then what comes with it (extra): {"rel_with": [[id, kind]], "team": group id}."""
    from .engine import EditError
    from .story import apply_relationship
    w = sim.w
    try:
        c = sim.create_custom(dict(spec))
    except EditError as e:
        raise EditorError(str(e))
    extra = extra or {}
    for other, kind in extra.get("rel_with") or []:
        if other in w.chars and other != c.id:
            apply_relationship(w, c.id, other, kind, day=w.day)
    gid = extra.get("team")
    if gid in w.groups and c.id not in w.groups[gid]["members"]:
        w.groups[gid]["members"].append(c.id)
        c.memberships.append(gid)
    if extra.get("rel_with") or gid:
        from . import social
        for (x, y), r in w.rels.items():
            if c.id in (x, y):
                r.label = social.label_for(r, w.rules)
    return c


SLOT_TO_ME = {"friend": "friend", "best_friend": "best_friend", "crush": "admirer", "partner": "dating", "ex": "ex", "rival": "rival"}
SLOT_OF = {"friend": "friend", "best_friend": "best_friend", "teammate": "teammate", "partner": "dating"}


def create_for_slot(sim, slot: str) -> dict:
    """Someone who fits a storyline's person when nobody in your story does: made to fit (their grade, gender, sport, who
    they are to you or to the person they go with), and picked for it. Then they're editable like anyone. {"id", "name"}"""
    from . import dialogue
    d = dialogue.merged()["cast"].get(slot)
    if not d:
        raise EditorError("that storyline person isn't in any of your storylines")
    return create_fit(sim, d["spec"], slot=slot)


def create_fit(sim, sp: dict, slot: str | None = None, role: str | None = None) -> dict:
    """Someone made to fit a description ({who, gender, sport, grade_offset, of, name}, as a storyline person has): a
    named storyline person (slot: then picked for it) or a kind of person your storylines use (role, like older_sister).
    {"id", "name", "fits"}"""
    import random
    from . import dialogue, groundwork
    w = sim.w
    me = w.chars.get(w.meta.get("protagonist") or "")
    if not me:
        raise EditorError("there's no story")
    who = sp.get("who")
    rng = random.Random(f"{w.gen_seed}:{slot or role}:{w.day}:{len(w.chars)}")
    g = me.grade or 9
    grade = g + sp["grade_offset"] if sp.get("grade_offset") is not None else g
    gender = sp.get("gender")
    spec: dict = {"role": "student"}
    extra: dict = {"rel_with": []}
    if slot:
        extra["slot"] = slot
    if role:
        extra["role"] = role
    if who in dialogue.SIBLING_KINDS:
        spec["household"] = "family"
        if who.endswith("brother"):
            gender = "m"
        elif who.endswith("sister"):
            gender = "f"
        if who.startswith("older_") and sp.get("grade_offset") is None:
            grade = g + 1
        if who.startswith("younger_") and sp.get("grade_offset") is None:
            grade = g - 1
        if who == "twin":
            grade = g
            extra["rel_with"].append([me.id, "twin"])
        if grade < 9:
            raise EditorError("a younger brother or sister can't join while you're the youngest in high school: add them in "
                              "your setup instead (they start high school a year after you)")
        if grade > 12:
            raise EditorError("an older brother or sister would be past high school: add them in your setup instead")
    elif who == "coach":
        raise EditorError("a coach comes with a team: edit one of your coaches instead")
    elif who == "teammate":
        teams = [gid for gid in me.memberships if (w.groups.get(gid) or {}).get("skill") in sim.cat.sports["sports"]
                 and (not sp.get("sport") or w.groups[gid].get("skill") == sp["sport"])]
        if not teams:
            raise EditorError("you're not on a team yet" + (f" ({sp['sport']})" if sp.get("sport") else "") + ": make one first")
        extra["team"] = teams[0]
        gender = w.groups[teams[0]].get("gender") or gender or me.gender
    elif sp.get("of"):
        base = dialogue.bound(sim, sp["of"])
        if not base:
            raise EditorError(f"first pick who {sp['of'].replace('_', ' ')} is")
        extra["rel_with"].append([base, SLOT_OF.get(who, "friend")])
        if w.chars[base].grade:
            grade = w.chars[base].grade
    elif who == "named":
        name = str(sp.get("name") or (slot or "someone").replace("_", " ").title())
        first, _, last = name.partition(" ")
        spec.update({"first": first, "last": last})
    elif who in SLOT_TO_ME:
        spec["relationships"] = [{"to": "me", "type": SLOT_TO_ME[who]}]
        if who in ("crush", "partner") and not gender:
            into = [x for x in (me.attracted_to or []) if x in GENDERS] or (["f"] if me.gender == "m" else ["m"])
            gender = into[0]
    elif who != "classmate":
        raise EditorError(f"the game can't make someone for '{who}'")
    if who == "partner" and me.flags.get("partner"):
        raise EditorError("you're already dating someone: they're who this storyline is about")
    grade = max(9, min(12, grade))
    spec["grade"] = grade
    gender = gender if gender in GENDERS else rng.choice(["f", "m"])
    spec["gender"] = gender
    if not spec.get("first"):
        names = sim.cat.people["names"]
        pool = names["female" if gender == "f" else "male" if gender == "m" else "nonbinary"]
        used = {c.first for c in w.chars.values()}
        spec["first"] = next((n for n in rng.sample(pool, len(pool)) if n not in used), rng.choice(pool))
    if sp.get("sport"):
        spec["interests"] = {sp["sport"]: 85}
        spec["skills"] = {sp["sport"]: 58}
    c = make_person(sim, spec, extra)
    fits = c.id in dialogue.slot_candidates(sim, me, sp)  # (before the pick: a picked person counts as taken)
    groundwork.note_added(w, c.id, spec, extra)
    if slot:
        dialogue.bind(sim, me, slot, c.id, by="you")
        groundwork.note_slot(w, slot, c.id)
    return {"id": c.id, "name": c.name, "fits": fits}


def pair(sim, a, b) -> dict:
    w = sim.w
    if a not in w.chars or b not in w.chars or a == b:
        raise EditorError("pick two different people")
    bond = w.bond(a, b) or {}
    return {"a": _mini(w, a), "b": _mini(w, b), "ab": _rel_view(w.rels.get((a, b))), "ba": _rel_view(w.rels.get((b, a))),
            "roles": bond.get("roles", []), "dating": w.chars[a].flags.get("partner") == b,
            "presets": [{"id": p, "label": lbl.format(a=w.chars[a].first, b=w.chars[b].first)} for p, lbl in PRESETS]}


def _settle(sim, a, b):
    """Labels and crushes follow the numbers, quietly (no news, no texts)."""
    from . import social
    from .worldgen import orientation_ok
    w, R = sim.w, sim.w.rules
    for x, y in ((a, b), (b, a)):
        r = w.rels.get((x, y))
        if r is None:
            continue
        X, Y = w.chars[x], w.chars[y]
        if r.attraction >= R["rel.crush_threshold"] and not orientation_ok(X, Y):
            X.attracted_to = sorted(set(X.attracted_to) | {Y.gender})  # you said they're into them: they are
        r.peak_affection = max(r.peak_affection, r.affection)
        r.label = social.label_for(r, R)
        r.crush = bool(R["romance.enabled"] and r.attraction >= R["rel.crush_threshold"] and orientation_ok(X, Y)
                       and X.role == "student" and Y.role == "student")


def save_pair(sim, a, b, body: dict) -> dict:
    """Set how two people feel about each other: a preset, numbers for either direction, or both (numbers win)."""
    from .actions import end_relationship
    from .story import REL_PRESETS, apply_relationship
    w = sim.w
    if a not in w.chars or b not in w.chars or a == b:
        raise EditorError("pick two different people")
    errors, sets = [], []
    preset = body.get("preset")
    if preset is not None and preset not in {p for p, _ in PRESETS}:
        errors.append(f"'{preset}' isn't a preset")
    for side, (x, y) in (("ab", (a, b)), ("ba", (b, a))):
        vals = body.get(side) or {}
        if not isinstance(vals, dict):
            errors.append(f"{side} must be an object")
            continue
        for f, v in vals.items():
            if f not in REL_FIELDS:
                errors.append(f"{f} isn't part of a relationship")
                continue
            lo, hi = REL_FIELDS[f]
            n = _num(v, lo, hi, REL_LABELS.get(f, f), errors)
            if n is not None:
                sets.append((x, y, f, n))
    if errors:
        raise EditorError("; ".join(errors))
    A, B = w.chars[a], w.chars[b]
    ev = _event(sim, [a, b], f"Editor: {A.name} and {B.name}" + (f" set to {dict(PRESETS)[preset].format(a=A.first, b=B.first).lower()}" if preset else ""))
    fx = Effects(w, ev)
    dating = A.flags.get("partner") == b
    if preset:
        if preset == "dating" and not dating:
            for x in (a, b):  # whoever they were with before, it's over
                old = w.chars[x].flags.get("partner")
                if old and old in w.chars:
                    end_relationship(sim, x, old, ev, fx, reason="the editor")
        elif preset != "dating" and dating:
            end_relationship(sim, a, b, ev, fx, reason="the editor")
            if preset != "ex":
                bd = w.bond(a, b)
                if bd and "ex" in bd["roles"]:
                    bd["roles"].remove("ex")
        if preset == "strangers":
            for x, y in ((a, b), (b, a)):
                r = w.ensure_rel(x, y, w.day)
                for f in REL_FIELDS:
                    setattr(r, f, 30.0 if f == "trust" else 0.0)
        else:
            apply_relationship(w, a, b, preset, day=w.day)
            for x, y in ((a, b), (b, a)):  # presets describe history, not today's last contact
                r = w.rels[(x, y)]
                r.last_day = max(r.last_day, w.day)
    for x, y, f, n in sets:
        r = w.ensure_rel(x, y, w.day)
        if w.tracing:
            ev["changes"].append([f"{x}>{y}", f, getattr(r, f), n, "editor"])
        setattr(r, f, n)
    _settle(sim, a, b)
    sim.finish(ev, fx)
    from . import groundwork
    groundwork.note_pair(w, a, b, body)
    me = w.meta.get("protagonist")
    if me in (a, b) and w.meta.get("squad"):
        w.meta["squad"]["updated"] = -99  # your group re-forms around who your friends are now
    return pair(sim, a, b)
