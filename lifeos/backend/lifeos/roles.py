"""Roles: everything your storylines need from your story, in one place.

A storyline names people (`cast: kayla = older sister, soccer`), its scenes are about kinds of people (your older sister,
a teammate, your girlfriend or boyfriend), and some need things about you (that you're dating someone, have a pet, are on
a team). This lists each role once, with every storyline that uses it: who fills it now, or if nobody does, who's close
and what they're missing ("Ally: doesn't play soccer"), with a one-tap fix where there is one, or someone made to fit.
What you pick, fix or add here is groundwork: it comes back when you start over.
"""
from __future__ import annotations

from . import dialogue, groundwork

SINGLE = ("best_friend", "crush", "partner", "rival")  # who it is follows your life: the closest, the one you like...
PAIR_FIX = {"friend": "friend", "best_friend": "best_friend", "crush": "crush", "partner": "dating", "ex": "ex", "rival": "rival"}
REQ = {"dating": "You're dating someone", "has_pet": "Your family has a pet", "has_sibling": "You have a brother or sister",
       "plays_sport": "You're on a team"}
KIND_LABEL = {"partner": "Your girlfriend or boyfriend", "crush": "Your crush", "best_friend": "Your best friend",
              "friend": "A friend", "rival": "Your rival", "ex": "An ex", "teammate": "A teammate", "classmate": "A classmate",
              "coach": "A coach", "twin": "Your twin"}
WAITS = {"teammate": "comes when you make a team (tryouts)", "coach": "comes with a team you're on",
         "classmate": "anyone in your grade you barely know"}


def _me(sim):
    w = sim.w
    return w.chars.get(w.meta.get("protagonist") or "")


def _mini(w, cid, why=None, fix=None):
    c = w.chars[cid]
    d = {"id": cid, "name": c.name, "first": c.first, "year": c.year_label}
    if why:
        d["why"] = why
    if fix:
        d["fix"] = fix
    return d


def _uses(sim) -> dict:
    """role key -> {"storylines": {pack id: scenes}}: from the scenes of every storyline that's on."""
    on = {p["id"]: p for p in dialogue.packs() if p.get("enabled")}
    out: dict = {}
    for sid, mm in sim.cat.moments.items():
        sc = mm.get("scene")
        if not sc or sc.get("pack") not in on:
            continue
        pk = sc["pack"]
        keys = []
        who = sc.get("who")
        if who and who.startswith("cast:"):
            keys.append(f"slot:{who[5:]}")
        elif who and who in dialogue.WHO:
            keys.append(f"kind:{who}")
        if set(sc.get("needs") or []) & {"partner", "partner_first"}:
            keys.append("kind:partner")
        for r in (sc.get("when") or {}).get("requires") or []:
            if r in REQ:
                keys.append(f"req:{r}")
        for k in set(keys):
            u = out.setdefault(k, {})
            u[pk] = u.get(pk, 0) + 1
    names = {pid: p["pack"].get("name") or pid for pid, p in on.items()}
    return {k: [{"id": pk, "name": names[pk], "scenes": n} for pk, n in sorted(v.items(), key=lambda x: names[x[0]])]
            for k, v in out.items()}


def _slot_near(sim, me, spec) -> list:
    """People who almost fit a storyline person, and what they're missing (with a fix when it's a quick one)."""
    w = sim.w
    who = spec.get("who")
    if who == "named":
        return []
    if spec.get("of"):
        base = dialogue.bound(sim, spec["of"])
        pool = dialogue._people_of(sim, me, who, base) if base else []
    elif who in dialogue.SIBLING_KINDS:
        pool = [s for s in sim.siblings(me.id) if s in w.chars and w.chars[s].status == "active"]
    else:
        pool = dialogue.candidates(sim, me, who)
    out = []
    for o in pool[:30]:
        c = w.chars[o]
        whys, fix = [], None
        if who in dialogue.SIBLING_KINDS and o not in dialogue.candidates(sim, me, who):
            whys.append(f"is your {'brother' if c.gender == 'm' else 'sister' if c.gender == 'f' else 'sibling'}, "
                        f"{'older' if (c.grade or 0) > (me.grade or 0) else 'younger' if (c.grade or 0) < (me.grade or 0) else 'same age'}")
        if spec.get("gender") and c.gender != spec["gender"] and not (whys and who in dialogue.SIBLING_KINDS):
            whys.append("is a guy" if c.gender == "m" else "is a girl" if c.gender == "f" else "is nonbinary")
        off = spec.get("grade_offset")
        if off is not None and me.grade and c.grade is not None and c.grade - me.grade != off:
            whys.append(f"is in {c.grade}th grade (it needs {me.grade + off}th)")
        if spec.get("sport") and not dialogue.plays(sim, c, spec["sport"]):
            whys.append(f"doesn't play {spec['sport']}")
            fix = {"sport": spec["sport"], "label": f"Make {c.first} play {spec['sport']}"}
        if whys:
            out.append(_mini(w, o, "; ".join(whys), fix if len(whys) == 1 else None))
    return sorted(out, key=lambda x: (not x.get("fix"), x["name"]))[:5]


def _kind_near(sim, me, kind) -> list:
    """For a kind nobody fits: the people closest to being it, and the relationship that would make them it."""
    w = sim.w
    from . import social
    fam = dialogue._family(sim, me)
    if kind in PAIR_FIX:
        pool = [o for o in w.out.get(me.id, {}) if o in w.chars and w.chars[o].status == "active" and o not in fam
                and w.chars[o].role != "staff" and o != me.id]
        if kind in ("crush", "partner"):
            pool = [o for o in pool if social.can_be_into(w, me.id, o) and (kind == "crush" or social.can_be_into(w, o, me.id))]
        pool.sort(key=lambda o: (-(dialogue._rel(w, me.id, o, "affection") + dialogue._rel(w, me.id, o, "familiarity") * 0.5), o))
        verb = {"friend": "Make you friends", "best_friend": "Make them your best friend", "crush": "Give you a crush on them",
                "partner": "Start dating", "ex": "Make them your ex", "rival": "Make them your rival"}[kind]
        return [_mini(w, o, f"you know them ({w.rels[(me.id, o)].label})", {"pair": PAIR_FIX[kind], "label": verb}) for o in pool[:4]]
    if kind in dialogue.SIBLING_KINDS:
        return _slot_near(sim, me, {"who": kind})
    return []


def board(sim) -> dict:
    """Every role your storylines use: {"roles": [...], "open": how many nobody fills}."""
    w = sim.w
    me = _me(sim)
    if not me:
        return {"roles": [], "open": 0}
    uses = _uses(sim)
    cast = dialogue.merged().get("cast") or {}
    slots_by_you = {k for k, v in (w.meta.get("cast_slots") or {}).items() if isinstance(v, dict) and v.get("by") == "you"}
    roles = []
    for key, sl in uses.items():
        kind, _, name = key.partition(":")
        r = {"key": key, "type": kind, "storylines": sl, "scenes": sum(x["scenes"] for x in sl), "options": [], "near": [],
             "who": None, "by": None, "can_add": False, "note": None}
        if kind == "slot":
            spec = (cast.get(name) or {}).get("spec")
            if not spec:
                continue
            r["title"] = name.replace("_", " ").title()
            r["label"] = dialogue.slot_label(spec)
            cur = dialogue.bound(sim, name)
            opts = dialogue.slot_candidates(sim, me, spec)
            if cur and cur not in opts:
                opts = [cur] + opts
            r["options"] = [_mini(w, o) for o in opts]
            if cur:
                r["who"], r["by"] = _mini(w, cur), "you" if name in slots_by_you else "game"
            r["status"] = "set" if cur else "open" if opts else "missing"
            if r["status"] == "open":
                r["note"] = "the game picks the best fit when its first scene comes, or pick now"
            if not cur:
                r["near"] = _slot_near(sim, me, spec) if not opts else []
            r["can_add"] = spec.get("who") not in ("coach",)
            if spec.get("of") and not dialogue.bound(sim, spec["of"]):  # someone in Kayla's life: who's Kayla first
                r["can_add"] = False
                r["after"] = f"slot:{spec['of']}"
                r["note"] = f"first fill {spec['of'].replace('_', ' ').title()}: this is someone in their life"
        elif kind == "kind":
            r["title"] = KIND_LABEL.get(name) or dialogue.WHO.get(name, name)[:-1]
            r["label"] = dialogue.WHO.get(name, "")[:-1].lower()
            cands = dialogue.candidates(sim, me, name)
            r["options"] = [_mini(w, o) for o in cands[:20]]
            if name in dialogue.CASTABLE:
                mine = {groundwork.my_pick(w, s["id"], name) for s in sl} - {None}
                kept = {dialogue.cast_of(w, s["id"], name) for s in sl} - {None}
                one = sorted(mine or kept)
                pick = one[0] if len(one) == 1 else None
                if pick in w.chars:
                    r["who"], r["by"] = _mini(w, pick), "you" if mine else "game"
            elif cands:
                r["who"], r["by"] = _mini(w, cands[0]), "life"
            r["status"] = "set" if r["who"] else "open" if cands else "missing"
            if name in SINGLE and r["who"]:
                r["note"] = "who it is follows your life (the person it is now)"
            if r["status"] == "open":
                r["note"] = "the game picks for each storyline, or pick one person for all of them"
            if not cands:
                r["near"] = _kind_near(sim, me, name)
                r["note"] = WAITS.get(name)
            r["can_add"] = name not in ("coach", "teammate", "classmate")
            r["single"] = name in SINGLE
        else:  # something about you
            r["title"] = REQ[name]
            r["label"] = "something about you"
            ok, how = _req(sim, me, name)
            r["status"] = "set" if ok else "missing"
            r["note"] = how
            if name == "dating" and not ok:
                r["near"] = _kind_near(sim, me, "partner")
            r["can_add"] = name in ("has_sibling", "dating") and not ok
        roles.append(r)
    order = {"missing": 0, "open": 1, "set": 2}
    roles.sort(key=lambda r: (order[r["status"]], bool(r.get("after")), -r["scenes"], r["title"]))
    return {"roles": roles, "open": sum(1 for r in roles if r["status"] == "missing")}


def _req(sim, me, name):
    w = sim.w
    if name == "dating":
        p = me.flags.get("partner")
        return (p in w.chars), (f"dating {w.chars[p].first}" if p in w.chars else "you're not dating anyone: start dating someone (below), or it waits until you do")
    if name == "has_pet":
        from . import pets
        have = pets.household_pets(w, me.household_id)
        return bool(have), ("you have a pet" if have else "ask your parents for one (Home tab → Pets), or it waits")
    if name == "has_sibling":
        sibs = [s for s in sim.siblings(me.id) if s in w.chars and w.chars[s].status == "active"]
        return bool(sibs), ("you have " + ", ".join(w.chars[s].first for s in sibs) if sibs else "add a brother or sister (below)")
    if name == "plays_sport":
        on = [g for g in me.memberships if (w.groups.get(g) or {}).get("skill") in sim.cat.sports["sports"]]
        return bool(on), ("you're on " + ", ".join(w.groups[g]["name"] for g in on) if on else "make a team at tryouts, or it waits")
    return True, None


# --- doing something about it -----------------------------------------------------------------------

def _storylines(sim, key) -> list:
    return [s["id"] for s in _uses(sim).get(key, [])]


def pick(sim, key: str, cid: str | None) -> dict:
    """Who fills a role: a storyline person (named), or one person for a kind in every storyline that uses it (None: back
    to the game's pick)."""
    from .editor import EditorError
    w = sim.w
    me = _me(sim)
    kind, _, name = key.partition(":")
    if cid is not None and cid not in w.chars:
        raise EditorError("no such person")
    if kind == "slot":
        spec = dialogue.slot_spec(name)
        if not spec:
            raise EditorError("no such storyline person")
        if cid is None:
            w.meta.get("cast_slots", {}).pop(name, None)
        elif cid not in dialogue.slot_candidates(sim, me, spec) and cid != dialogue.bound(sim, name):
            raise EditorError(f"they don't fit: it's {dialogue.slot_label(spec)}")
        else:
            dialogue.bind(sim, me, name, cid, by="you")
        groundwork.note_slot(w, name, cid)
    elif kind == "kind" and name in dialogue.CASTABLE:
        if cid is not None and cid not in dialogue.candidates(sim, me, name):
            raise EditorError(f"they aren't {dialogue.WHO.get(name, name)[:-1].lower()} to you")
        for pk in _storylines(sim, key):
            if cid is None:
                (w.meta.get("pack_cast", {}).get(pk) or {}).pop(name, None)
            else:
                dialogue.set_cast(w, pk, name, cid)
            groundwork.note_pick(w, pk, name, cid)
    else:
        raise EditorError("that role follows your life: change how you feel about someone instead")
    return board(sim)


def fix(sim, key: str, cid: str, how: dict) -> dict:
    """Make someone fit a role: give them the sport, or set the relationship. Then they fill it."""
    from . import editor
    w = sim.w
    me = _me(sim)
    if cid not in w.chars or not me:
        raise editor.EditorError("no such person")
    if how.get("sport"):
        s = how["sport"]
        c = w.chars[cid]
        editor.save_person(sim, cid, {"interests": {s: max(85.0, c.interests.get(s, 0))}})
    elif how.get("pair"):
        editor.save_pair(sim, me.id, cid, {"preset": how["pair"]})
    else:
        raise editor.EditorError("nothing to do")
    kind, _, name = key.partition(":")
    if kind == "slot" or (kind == "kind" and name in dialogue.CASTABLE):
        try:
            return pick(sim, key, cid)
        except editor.EditorError:
            pass
    return board(sim)


def add(sim, key: str) -> dict:
    """Someone made to fit the role, and picked for it. {"id", "name", "fits", "board"}"""
    from . import editor
    kind, _, name = key.partition(":")
    if kind == "slot":
        out = editor.create_for_slot(sim, name)
    elif kind == "kind":
        out = editor.create_fit(sim, {"who": name}, role=name)
        if name in dialogue.CASTABLE:
            try:
                pick(sim, key, out["id"])
            except editor.EditorError:
                pass
    elif key == "req:has_sibling":
        out = editor.create_fit(sim, {"who": "older_sibling"}, role="sibling")
    elif key == "req:dating":
        out = editor.create_fit(sim, {"who": "partner"}, role="partner")
    else:
        raise editor.EditorError("that one comes from playing: it can't be added")
    return {**out, "board": board(sim)}
