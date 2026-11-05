"""Hangouts that play out.

After a hangout, a date or a crew hangout you picked, a quick scene comes up (data/hangouts.json): Danny dares you to jump
off the dock, the diner's empty and they want you to rate their placemat art, it starts pouring on the walk home. One
choice. Each choice is a style (teasing, sweet, being direct, funny, cheesy, or a safe pick), and how it goes depends on
what that person likes (chat.tastes): the same thing you're learning by texting them. Trying a style teaches you how it
goes over, and their contact page keeps track.
"""
from __future__ import annotations

from .catalogs import _base

STYLE_HINT = {"tease": "Teasing", "sweet": "Sweet", "bold": "Being direct", "funny": "Funny", "cheesy": "Cheesy", "chill": "Play it safe"}
_SCENES = None


def scenes() -> list:
    global _SCENES
    if _SCENES is None:
        _SCENES = _base("hangouts.json")["scenes"]
    return _SCENES


def register(moments: dict):
    """Every hangout scene becomes a story moment: hang_<id>."""
    for sc in scenes():
        choices = []
        for ch in sc["choices"]:
            outs = {k: ch[k] for k in ("good", "meh", "bad") if k in ch}
            choices.append({"label": ch["label"], "hint": STYLE_HINT.get(ch["style"], ""), "ops": [["vibe", ch["style"], outs]], "fits": {}})
        moments[f"hang_{sc['id']}"] = {"title": sc["title"], "text": sc["text"], "choices": choices, "hangout": sc["kind"]}


def _fits(sim, sc, me, o) -> bool:
    likes = [k for k in sc.get("likes", []) if k in sim.cat.skills or k in sim.cat.hobbies]
    if not likes:
        return True
    return any(me.interests.get(k, 0) >= 45 or o.interests.get(k, 0) >= 45 for k in likes)


def names(w, ids) -> str:
    firsts = [w.chars[i].first for i in ids if i in w.chars]
    if not firsts:
        return "everyone else"
    return firsts[0] if len(firsts) == 1 else ", ".join(firsts[:-1]) + " and " + firsts[-1]


def kind_for(sim, me_id, them, action, crew) -> str:
    if crew:
        return "group"
    if action == "date":
        return "date"
    w = sim.w
    a, b = w.rels.get((me_id, them)), w.rels.get((them, me_id))
    if a and b and a.attraction >= 40 and b.attraction >= 40:
        return "date"
    return "hang"


def maybe_scene(sim, me_id, them, kind, crew=None, place=None, act=None):
    """Bring up a hangout scene with them (one a day, not one you've had lately)."""
    w = sim.w
    if them not in w.chars or me_id != w.meta.get("protagonist") or them in sim.siblings(me_id):
        return None
    if any(m["kind"].startswith("hang_") and m["day"] == w.day for m in w.meta.get("moments", [])):
        return None
    me, o = w.chars[me_id], w.chars[them]
    seen = w.meta.setdefault("hang_seen", {})
    every = [sc for sc in scenes() if kind in sc["kind"]]
    if act:  # a group thing: scenes that fit what you're doing (no dock dares over voice chat)
        every = [sc for sc in every if act in sc.get("acts", [])]
    elif kind == "group":
        every = [sc for sc in every if sc.get("acts") != ["game"]]
    pool = [sc for sc in every if w.day - seen.get(sc["id"], -999) > 20 and _fits(sim, sc, me, o)] or every
    if not pool:
        return None
    rng = sim.streams.get("hangout", w.day, them)
    sc = pool[int(rng.random() * len(pool))]
    from . import squad
    sq = squad.state(sim)
    ctx = {"them": them, "them_first": o.first, "place": place or "", "kind": kind, "crew": list(crew or []),
           "crew_first": names(w, crew or []), "other_first": w.chars[crew[0]].first if crew else o.first,
           "group": sq["name"] if sq and kind == "group" else "everyone"}
    before = len(w.meta.get("moments", []))
    sim.moment_trigger(f"hang_{sc['id']}", me_id, ctx)
    if len(w.meta.get("moments", [])) == before:
        return None
    seen[sc["id"]] = w.day
    m = w.meta["moments"][-1]
    # say what you already know about them next to each style
    from .messages import phone
    known = phone(w).get("tastes", {}).get(them, {}) if "phone" in w.meta else {}
    for ch, spec in zip(m["choices"], m["_choices"]):
        style = spec["ops"][0][1]
        if style in known:
            ch["hint"] = f"{ch['hint']} · {o.first} {'loves it' if known[style] > 0 else 'is not into it' if known[style] < 0 else 'is fine with it'}"
    return m


def vibe(sim, c, op, ctx, fx, ev, rng, m, render):
    """A hangout choice: how it goes over with them depends on their taste (plus a little luck)."""
    from . import chat
    w = sim.w
    them = ctx.get("them")
    if them not in w.chars:
        return
    style = op[1]
    outs = op[2] if len(op) > 2 and isinstance(op[2], dict) else {}
    o = w.chars[them]
    if style in chat.STYLES:
        taste = chat.tastes(o)[style]
        roll = taste + (0.7 if rng.random() < 0.2 else 0.0) - (0.7 if rng.random() < 0.12 else 0.0)
        res = "good" if roll >= 0.6 else "bad" if roll <= -0.6 else "meh"
        if "phone" in w.meta:
            chat._learn(sim, them, style)
    else:
        taste, res = 0, "good" if rng.random() < 0.5 else "meh"  # the safe pick: always fine
    gain = {"good": 4.0, "meh": 1.5, "bad": -2.0}[res]
    fx.rel(them, c.id, "affection", gain, m["title"])
    fx.rel(c.id, them, "affection", max(0.5, gain * 0.6), m["title"])
    r = w.rels.get((them, c.id))
    if res == "good" and (ctx.get("kind") == "date" or (r and r.attraction >= 35)):
        fx.rel(them, c.id, "attraction", 3.0, m["title"])
        fx.rel(c.id, them, "attraction", 1.5, m["title"])
    fx.mood(c.id, {"good": 4, "meh": 1, "bad": -2}[res], m["title"])
    fx.need(c.id, "fun", {"good": 6, "meh": 3, "bad": 0}[res], m["title"])
    for x in ctx.get("crew") or []:
        if x in w.chars and x != them:
            fx.rel(x, c.id, "affection", {"good": 2.0, "meh": 1.0, "bad": -0.5}[res], m["title"])
    lines = outs.get(res) or outs.get("good") or []
    if lines:
        from . import lines as L
        ev["data"].setdefault("say", []).append(render(L.variant(sim, f"hang:{m['kind']}:{res}", lines, f"{m['id']}:v")))
    ev["data"]["vibe"] = res
    if style in chat.STYLES:
        word = chat.STYLE_WORD[style][1]
        ev["data"]["why"] = (f"{o.first} loves {word}." if taste > 0 else f"{o.first} isn't into {word}." if taste < 0
                             else f"{o.first} is fine with {word}, but it's not their thing.") + (" A little luck, too." if res == "good" and taste <= 0 else "")
    else:
        ev["data"]["why"] = "The safe pick: always fine, never the best."
