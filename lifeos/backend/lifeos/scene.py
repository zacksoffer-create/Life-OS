"""The social scene: your school's world, from where you're standing.

The game already knows the groups (friend groups that form and break up on their own: the Court Crew, the Honor Roll, the
In-Crowd...), who's dating who, who's popular, and what people say about everyone. This puts it on the phone (Phone →
Scene): where you stand (your rank, your group, your reputation), every group and your way in (a friend who's in it),
who's together and who just broke up, the most popular people, and people you could meet: friends of your friends.

Meeting people through the ones you know: ask a friend to introduce you. It's free like texting (one a day), and how it
goes depends on you, them, and how close your friend is with them. Getting into a group works the way it does in real
life: hang out with your friend who's in it, get close to the rest, and the next time groups shift, you're in.
"""
from __future__ import annotations

import random
import zlib

from . import calendar as calm
from .history import Effects
from .rng import clamp

REP_WORDS = {"legend": "a legend", "host": "throws the best parties", "tough": "not someone to mess with", "gossip": "knows everyone's business",
             "kind": "genuinely nice", "troublemaker": "trouble", "embarrassed": "that embarrassing thing", "mean": "kind of mean",
             "star": "a star", "performer": "a performer", "athlete": "an athlete", "leader": "a leader", "flaky": "flaky",
             "brain": "a brain"}
INTEREST_WORDS = {"gaming": "games", "pickup_games": "pickup ball", "batting_cage": "the cages", "shows": "shows", "fitness": "the gym",
                  "academics": "grades", "outdoors": "the outdoors", "fashion": "fashion"}


def _h(*p) -> int:
    return zlib.crc32(":".join(str(x) for x in p).encode())


def _me(sim):
    p = sim.w.meta.get("protagonist")
    return sim.w.chars.get(p) if p else None


def _mini(w, cid) -> dict:
    from .appearance import look_of
    c = w.chars[cid]
    return {"id": cid, "name": c.name, "first": c.first, "color": c.color, "look": look_of(c), "year": c.year_label}


def students(sim, me) -> list:
    w = sim.w
    return [c for c in w.chars.values() if c.role == "student" and c.status == "active" and c.school == me.school
            and c.location == me.location]


def _friend(w, a, b) -> bool:
    r = w.rels.get((a, b))
    return bool(r and r.affection >= w.rules["rel.friend_threshold"])


def tier(rank: int, of: int) -> str:
    q = rank / max(1, of)
    return ("Everybody knows you" if q <= 0.1 else "Well known" if q <= 0.3 else "People know your name" if q <= 0.6
            else "Under the radar")


def reputation(c) -> list:
    tags = sorted(((k, v) for k, v in (c.reputation or {}).items() if v >= 4), key=lambda x: -x[1])
    return [REP_WORDS.get(k, k.replace("_", " ")) for k, _ in tags[:3]]


def _vibe(sim, cl) -> str:
    labels = []
    for k, v in cl.get("interests") or []:
        if v < 35:
            continue
        lab = INTEREST_WORDS.get(k) or (sim.cat.skills.get(k) or sim.cat.hobbies.get(k) or {}).get("label") or k
        labels.append(lab.lower())
    return ", ".join(labels[:3])


def view(sim) -> dict:
    from . import drama
    w = sim.w
    me = _me(sim)
    studs = students(sim, me)
    ids = {c.id for c in studs}
    ranked = sorted(studs, key=lambda c: (-c.popularity, c.id))
    rank = next((i + 1 for i, c in enumerate(ranked) if c.id == me.id), len(ranked))
    grade = [c for c in ranked if c.grade == me.grade]
    grank = next((i + 1 for i, c in enumerate(grade) if c.id == me.id), len(grade))
    friends = [o for o in w.out.get(me.id, {}) if o in w.chars and _friend(w, me.id, o) and w.chars[o].status == "active"]
    mine = me.flags.get("clique")
    fam = set(sim.siblings(me.id))
    groups = []
    for cid, cl in w.cliques.items():
        if not cl.get("active"):
            continue
        members = [m for m in cl["members"] if m in ids or m == me.id]
        if len(members) < 2:
            continue
        fr = [m for m in members if m in friends]
        way = max(fr, key=lambda m: (w.rels[(me.id, m)].affection, m)) if fr else None
        members.sort(key=lambda m: (m != me.id, m not in fr, -w.chars[m].popularity, m))
        pop = cl.get("popularity") or sum(w.chars[m].popularity for m in members) / len(members)
        groups.append({"id": cid, "name": cl["name"], "size": len(members), "mine": cid == mine or me.id in members,
                       "members": [{**_mini(w, m), "friend": m in fr, "me": m == me.id, "family": m in fam} for m in members[:12]],
                       "friends": len(fr), "way_in": way and _mini(w, way), "vibe": _vibe(sim, cl),
                       "standing": "popular" if pop >= 65 else "well known" if pop >= 50 else "low key",
                       "since": calm.label(cl.get("formed", w.day))})
    groups.sort(key=lambda g: (not g["mine"], -g["friends"], -g["size"], g["name"]))
    couples, breakups = [], []
    seen = set()
    for key, bd in w.bonds.items():
        a, b = (key.split("|") + [None])[:2] if isinstance(key, str) else key
        if a not in ids and a != me.id or b not in ids and b != me.id:
            continue
        if "partner" in bd.get("roles", []) and (a, b) not in seen:
            seen.add((a, b))
            since = bd.get("since", {}).get("partner", 0)
            couples.append({"a": _mini(w, a), "b": _mini(w, b), "since": calm.label(since), "new": w.day - since <= 7,
                            "you": me.id in (a, b), "day": since})
        elif "ex" in bd.get("roles", []) and w.day - bd.get("since", {}).get("ex", -999) <= 21:
            breakups.append({"a": _mini(w, a), "b": _mini(w, b), "when": calm.label(bd["since"]["ex"]), "day": bd["since"]["ex"]})
    couples.sort(key=lambda x: (not x["you"], -x["day"]))
    breakups.sort(key=lambda x: -x["day"])
    st = w.meta.get("scene") or {}
    return {"me": {"rank": rank, "of": len(ranked), "grade_rank": grank, "grade_of": len(grade), "tier": tier(rank, len(ranked)),
                   "popularity": round(me.popularity), "group": next((g["name"] for g in groups if g["mine"]), None),
                   "reputation": reputation(me), "friends": len(friends)},
            "groups": groups[:14], "couples": couples[:20], "breakups": breakups[:8],
            "popular": [{**_mini(w, c.id), "you": c.id == me.id} for c in ranked[:6]],
            "meet": meet(sim, me, friends, ids), "intro_today": st.get("intro_day") == w.day,
            "talk": drama.view(sim), "fights": drama.fights(sim)}


def meet(sim, me, friends, ids) -> list:
    """Friends of your friends you don't really know yet, with who you have in common."""
    w = sim.w
    cand: dict = {}
    for f in friends:
        for x, r in w.out.get(f, {}).items():
            if x == me.id or x not in ids or r.affection < w.rules["rel.friend_threshold"]:
                continue
            mine = w.rels.get((me.id, x))
            if mine and mine.familiarity >= 15:
                continue
            cand.setdefault(x, []).append(f)
    out = []
    for x, via in cand.items():
        via.sort(key=lambda f: (-w.rels[(f, x)].affection, f))
        out.append({**_mini(w, x), "mutual": [w.chars[f].first for f in via[:3]], "n": len(via), "via": _mini(w, via[0])})
    out.sort(key=lambda p: (-p["n"], -w.chars[p["id"]].popularity, p["id"]))
    return out[:10]


def intro(sim, via: str, to: str) -> dict:
    """Ask a friend to introduce you to someone they know. Free, once a day."""
    from .worldgen import compatibility
    w = sim.w
    me = _me(sim)
    if via not in w.chars or to not in w.chars or to == me.id or via == to:
        raise ValueError("pick a friend and someone they know")
    st = w.meta.setdefault("scene", {})
    if st.get("intro_day") == w.day:
        raise ValueError("One introduction a day. Ask again tomorrow.")
    if not _friend(w, me.id, via) or not _friend(w, via, to):
        raise ValueError(f"{w.chars[via].first} would need to be friends with both of you")
    st["intro_day"] = w.day
    V, T = w.chars[via], w.chars[to]
    rng = random.Random(_h(w.seed, w.day, via, to))
    charm = (me.aptitudes.get("charisma", 50) + me.traits.get("sociability", 50)) / 2
    q = 0.1 + 0.35 * compatibility(w, me, T) + (charm - 50) / 200 + 0.2 * w.rels[(via, to)].affection / 100 + rng.gauss(0, 0.2)
    res = "great" if q >= 0.4 else "good" if q >= 0.1 else "meh"
    ev = sim.new_event("introduce", "through_friend", [me.id], [to, via], 14, {"via": via, "quality": round(q, 3)})
    fx = Effects(w, ev)
    for a, b in ((me.id, to), (to, me.id)):
        fx.rel(a, b, "familiarity", 18, f"{V.first} introduced them")
        fx.rel(a, b, "affection", {"great": 9, "good": 5, "meh": 1}[res], f"{V.first} introduced them")
    fx.rel(via, me.id, "affection", 1, "made an introduction")
    fx.need(me.id, "social", 5, "met someone new")
    place = ["by the lockers", "after class", "at lunch", "in the parking lot"][_h(w.day, to) % 4]
    ev["text"] = {"great": f"{V.first} introduced {me.short} to {T.first} {place}. They hit it off right away.",
                  "good": f"{V.first} introduced {me.short} to {T.first} {place}. Easy, friendly, nice to meet.",
                  "meh": f"{V.first} introduced {me.short} to {T.first} {place}. A little awkward, but now they know each other."}[res]
    ev["outcome"] = res
    sim.finish(ev, fx)
    if "phone" in w.meta and res != "meh":
        from . import messages
        messages.add_contact(sim, to, "introduced")
    return ev


def plan(sim, with_id: str) -> str:
    """Plan to hang out with someone at your next free time (your way into their group)."""
    from .moments import control
    w = sim.w
    me = _me(sim)
    if with_id not in w.chars or with_id == me.id:
        raise ValueError("pick someone")
    control(w)["queued"] = {"action": "hang_out", "target": with_id, "agreed": True, "day": w.day, "expires": w.day + 3,
                            "label": f"Hang out with {w.chars[with_id].first}"}
    return f"Planned: hang out with {w.chars[with_id].first} next time you're free."
