"""Group chats that talk. Your crew, your team and your family have little conversations of their own (roasting someone's
haircut, the night before a game, who ate the leftovers): they talk to each other, the messages land one at a time, and
you can jump in with one of a few things to say. What you say has effects (who's happy with you, a laugh, a calmer
night), and sometimes someone DMs you about it after.

The conversations are in data/groupchat.json. Storage: each group thread keeps the conversations it's had in
thread["bursts"] (by instance id, for your answer), and phone["bursts_seen"] keeps the last few so they don't repeat.
"""
from __future__ import annotations

import json
import os

from . import calendar as calm
from .rng import clamp

_DATA = None
CREW_ROLES = ("A", "B", "C")
FAMILY_ROLES = ("P", "Q", "S", "T")
# how often a group chat starts up on its own (the team chat also does around your games)
P_CREW, P_CREW_WEEKEND, P_FAMILY, P_PRACTICE = 0.35, 0.45, 0.12, 0.08


def D() -> dict:
    """The built-in conversations plus the ones from your packs (`group chat crew:` blocks in a script)."""
    global _DATA
    if _DATA is None:
        from .catalogs import DATA_DIR
        with open(os.path.join(DATA_DIR, "groupchat.json"), encoding="utf-8") as f:
            _DATA = json.load(f)
    from . import dialogue
    extra = dialogue.merged().get("groupchat") or []
    return {**_DATA, "bursts": _DATA["bursts"] + extra} if extra else _DATA


def _h(*parts) -> int:
    from .messages import _h as h
    return h(*parts)


def _fill(s: str, kw: dict) -> str:
    from .messages import _fill as f
    return f(s, kw)


def _roles_in(b) -> set:
    rs = {r for r, _ in b["lines"]}
    for o in b.get("you", []):
        rs |= {r for r, _ in o.get("then", [])}
    if b.get("side"):
        rs.add(b["side"]["from"])
    return rs


def tags(sim) -> set:
    """What's true today, for which conversations fit."""
    w = sim.w
    cal = sim.cat.world["calendar"]
    out = set()
    school = calm.is_school_day(w.day, cal)
    out.add("school_day" if school else "weekend")
    if calm.is_school_day(w.day + 1, cal):
        out.add("school_night")
    if calm.date_of(w.day).month in (12, 1, 2, 3):
        out.add("winter")
    from .messages import prot
    me = prot(w)
    if me and (w.households.get(me.household_id) or {}).get("pet"):
        out.add("has_pet")
    return out


# --- who's in it -------------------------------------------------------------------------------

def _crew(sim):
    from . import squad
    s = squad.state(sim)
    if not s:
        return None
    ids = [i for i in s["ids"] if i in sim.w.chars]
    if len(ids) < 2:
        return None
    rot = _h(sim.w.day, "crew-roles") % len(ids)
    title = s["name"][0].upper() + s["name"][1:]
    return {"tid": "squad", "title": title, "members": list(s["ids"]), "cast": dict(zip(CREW_ROLES, ids[rot:] + ids[:rot]))}


def _team(sim, g):
    from .messages import prot
    w = sim.w
    me = prot(w)
    mates = [m for m in g["members"] if m != me.id and m in w.chars and w.chars[m].status == "active"]
    if len(mates) < 2:
        return None

    def close(m):
        r = w.rels.get((m, me.id))
        return (r.affection if r else 0) + w.chars[m].traits["sociability"] * 0.3
    top = sorted(mates, key=lambda m: (-close(m), m))[:5]
    rot = _h(w.day, g["id"], "team-roles") % len(top)
    top = top[rot:] + top[:rot]
    return {"tid": f"team:{g['id']}", "title": g["name"], "members": [m for m in g["members"] if m != me.id],
            "cast": dict(zip(CREW_ROLES, top)), "team": g["name"]}


def _family(sim):
    from .messages import parent_names, prot
    w = sim.w
    me = prot(w)
    parents = [p["id"] for p in parent_names(sim)]
    sibs = [s for s in sim.siblings(me.id) if w.chars[s].status == "active"]
    if not parents:
        return None
    cast = {"P": parents[0]}
    if len(parents) > 1:
        cast["Q"] = parents[1]
    for role, sid in zip(("S", "T"), sorted(sibs, key=lambda s: _h(w.day, s, "fam"))):
        cast[role] = sid
    return {"tid": "family", "title": None, "members": None, "cast": cast}


def _names(sim, cast) -> dict:
    from .messages import sender_name, prot
    out = {r: sender_name(sim, cid) for r, cid in cast.items()}
    out["me"] = prot(sim.w).first
    return out


# --- a conversation starts ---------------------------------------------------------------------

def start(sim, chat: str, extra: set | None = None, group=None, opp: str | None = None, phase: str | None = None) -> bool:
    """Start one conversation in this chat ("crew", "team" with its group, "family") that fits today. True if one did."""
    from .messages import phone, post, prot
    w = sim.w
    me = prot(w)
    if not me or "phone" not in w.meta:
        return False
    who = _crew(sim) if chat == "crew" else _team(sim, group) if chat == "team" and group else _family(sim) if chat == "family" else None
    if not who:
        return False
    now = tags(sim) | set(extra or ())
    ph = phone(w)
    seen = ph.setdefault("bursts_seen", [])
    fits = [b for b in D()["bursts"] if b["chat"] == chat and set(b.get("when", [])) <= now and _roles_in(b) <= set(who["cast"])]
    if extra:  # around a game: a conversation about the game
        fits = [b for b in fits if set(b.get("when", [])) & set(extra)] or fits
    fresh = [b for b in fits if b["id"] not in seen] or fits
    if not fresh:
        return False
    b = fresh[_h(w.day, chat, len(seen)) % len(fresh)]
    fill = _names(sim, who["cast"])
    pet = (w.households.get(me.household_id) or {}).get("pet") or {}
    fill.update({"opp": opp or "them", "team": who.get("team", "the team"), "pet": pet.get("name", "the dog")})
    inst = f"b{ph['next']}"
    n = len(b["lines"])
    first = None
    for i, (role, text) in enumerate(b["lines"]):
        last = i == n - 1
        replies = [{"label": _fill(o["say"], fill), "fx": f"burst:{inst}:{k}"} for k, o in enumerate(b["you"])] if last else None
        m = post(sim, who["tid"], who["cast"][role], _fill(text, fill), kind="burst", replies=replies, ctx={"fast": True}, phase=phase,
                 unread=True, title=who["title"], members=who["members"], tkind="group")
        first = first or m
        _after(m, first, i)
    t = ph["threads"][who["tid"]]
    keep = t.setdefault("bursts", {})
    keep[inst] = {"id": b["id"], "cast": who["cast"], "fill": fill, "day": w.day}
    for old in sorted(keep, key=lambda k: keep[k]["day"])[:-8]:
        keep.pop(old, None)
    seen.append(b["id"])
    del seen[:-15]
    return True


def _after(m, first, i):
    """A conversation's messages land a minute or two apart, in order."""
    if i == 0:
        return
    try:
        hm, ampm = first["at"].split(" ")
        hh, mm = (int(x) for x in hm.split(":"))
    except ValueError:
        return
    total = (hh % 12 + (12 if ampm == "PM" else 0)) * 60 + mm + i + i // 2
    h24, mi = divmod(total, 60)
    h24 %= 24
    m["at"] = f"{h24 % 12 or 12}:{mi:02d} {'AM' if h24 < 12 else 'PM'}"


# --- you jump in -------------------------------------------------------------------------------

def answer(sim, tid: str, inst: str, k: int, fx) -> None:
    """You said one of the things: they answer, it lands (or doesn't) with each of them, and someone might DM you after."""
    from .messages import later, phone, post, prot
    w = sim.w
    me = prot(w)
    t = phone(w)["threads"].get(tid) or {}
    bi = (t.get("bursts") or {}).get(inst)
    b = next((x for x in D()["bursts"] if bi and x["id"] == bi["id"]), None)
    if not bi or not b or not 0 <= k < len(b["you"]):
        return
    opt = b["you"][k]
    cast, fill = bi["cast"], bi["fill"]
    for role, text in opt.get("then", []):
        if role in cast:
            post(sim, tid, cast[role], _fill(text, fill), kind="burst", unread=False, ctx={"fast": True})
    why = "the group chat"
    for key, ch in (opt.get("fx") or {}).items():
        if key in cast and cast[key] in w.chars:
            for fld, n in ch.items():
                fx.rel(cast[key], me.id, fld, n, why)
        elif key == "me":
            for fld, n in ch.items():
                if fld == "mood":
                    fx.mood(me.id, n, why)
                else:
                    fx.need(me.id, fld, n, why)
        elif key == "crew":
            s = w.meta.get("squad")
            if s:
                s["cohesion"] = clamp(s.get("cohesion", 50) + ch.get("cohesion", 0), 0, 100)
        elif key == "parents":
            ph = phone(w)
            ph["parent_trust"] = clamp(ph.get("parent_trust", 60) + ch.get("trust", 0), 0, 100)
    side = opt.get("dm") or b.get("side")
    if side and (opt.get("dm") or side.get("after") is None or k in side["after"]) and cast.get(side["from"]) in w.chars:
        later(sim, cast[side["from"]], "chat_side", delay_phases=1, text=_fill(side["text"], fill))


# --- when they happen --------------------------------------------------------------------------

def plan_day(sim):
    """Mornings: decide whether a group chat starts up tonight (one a day, at most, besides game nights)."""
    from .messages import phone
    w = sim.w
    weekend = "weekend" in tags(sim)
    r = (_h(w.day, "groupchat") % 1000) / 1000
    p_crew = P_CREW_WEEKEND if weekend else P_CREW
    chat = "crew" if r < p_crew else "family" if r < p_crew + P_FAMILY else "practice" if r < p_crew + P_FAMILY + P_PRACTICE and not weekend else None
    phone(w)["burst_plan"] = {"day": w.day, "chat": chat, "done": chat is None}


def tick(sim):
    """After each part of the day: tonight's group chat, when it's evening."""
    from .messages import phone, prot
    w = sim.w
    ph = w.meta.get("phone")
    if not ph:
        return
    plan = ph.get("burst_plan")
    if not plan or plan.get("day") != w.day or plan.get("done"):
        return
    if sim.current_phase() not in ("evening", "night"):
        return
    plan["done"] = True
    if plan["chat"] == "practice":
        me = prot(w)
        teams = [w.groups[g] for g in me.memberships if g in w.groups and w.groups[g].get("kind") == "team"]
        if teams:
            start(sim, "team", {"school_day"}, group=teams[_h(w.day, "practice") % len(teams)])
        return
    if not start(sim, plan["chat"]) and plan["chat"] == "crew" and _h(w.day, "fam-fallback") % 4 == 0:
        start(sim, "family")  # no crew yet: now and then the family chat instead
