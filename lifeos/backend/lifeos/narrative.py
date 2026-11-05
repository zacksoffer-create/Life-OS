"""Narrative: procedural text from an event's structured record.

Text is rendered from the event type, its outcome and its data. The template variant comes
from a presentation-only random stream keyed by event id, so wording never affects the
simulation. If no template matches, a plain factual sentence is generated instead.
"""
from __future__ import annotations

import string

from .rng import derive_seed


class _Safe(dict):
    def __missing__(self, key):
        return ""


def _names(w, ids):
    p = w.meta.get("protagonist")
    if p in ids:
        ids = [p] + [i for i in ids if i != p]
    ns = [w.chars[i].short if i in w.chars else i for i in ids]
    if len(ns) <= 2:
        return " and ".join(ns)
    if len(ns) > 6:
        return ", ".join(ns[:5]) + f" and {len(ns) - 5} others"
    return ", ".join(ns[:-1]) + " and " + ns[-1]


def render(sim, ev) -> str:
    w = sim.w
    t = sim.cat.templates
    key = f"{ev['type']}.{ev.get('outcome')}"
    variants = t.get(key)
    if variants is None and ev["type"].startswith("interact."):
        variants = t.get(f"interact.chat.{ev.get('outcome')}")
    if variants is None and ev["type"] in sim.cat.actions:
        variants = t.get(f"{ev['type']}.{ev.get('outcome')}")
    d = ev.get("data", {})
    actors = ev.get("actors", [])
    targets = ev.get("targets", [])
    vals = _Safe()
    vals["a"] = w.chars[actors[0]].short if actors and actors[0] in w.chars else ""
    vals["b"] = w.chars[targets[0]].short if targets and targets[0] in w.chars else ""
    vals["members"] = _names(w, d.get("members") or actors)
    for k in ("place", "group", "event", "label", "about", "score", "verb", "pet", "n"):
        if k in d:
            vals[k] = d[k]
    if "skill" in d and d["skill"] in sim.cat.skills:
        vals["skill"] = sim.cat.skills[d["skill"]]["label"].lower()
    vals["school"] = sim.cat.world["school"]["name"]
    vals["town"] = sim.cat.world["town"]["name"]
    vals["where"] = "at the library" if ev.get("slot") in ("day",) else "at home"
    if not variants:
        who = vals["a"] or vals["members"]
        extra = f" with {vals['b']}" if vals["b"] else ""
        return f"{who}: {ev['type'].replace('_', ' ').replace('.', ' ')} ({ev.get('outcome')}){extra}."
    i = derive_seed(w.seed, "text", ev.get("id", 0), key) % len(variants)
    out = string.Formatter().vformat(variants[i], (), vals)
    said = _talk(sim, ev, key, vals)
    return f"{out} {said}" if said else out


# in-person moments with you in them: the other person says something (the spoken version of a pool line)
TALK = {"interact.hang_out.great": "hang_talk", "interact.hang_out.good": "hang_talk", "interact.hang_out.awkward": "awkward_talk",
        "interact.hang_out.bad": "awkward_talk", "interact.date.great": "date_talk", "interact.date.good": "date_talk",
        "interact.date.awkward": "awkward_talk", "interact.date.bad": "awkward_talk", "interact.chat.great": "chat_talk",
        "interact.chat.good": "chat_talk", "interact.sit_with.good": "chat_talk", "interact.sit_with.great": "chat_talk",
        "interact.flirt.great": "flirt_in"}


def _talk(sim, ev, key, vals) -> str:
    w = sim.w
    pool = TALK.get(key)
    p = w.meta.get("protagonist")
    if not pool or not p:
        return ""
    actors, targets = ev.get("actors") or [], ev.get("targets") or []
    if p not in actors + targets:
        return ""
    other = next((x for x in actors + targets if x != p and x in w.chars), None)
    if not other or w.chars[other].role == "staff" or derive_seed(w.seed, "talk", ev.get("id", 0)) % 100 >= 65:
        return ""
    from . import lines
    try:
        return lines.say_from_pool(sim, pool, other, f"{ev.get('id')}:{key}", {"place": vals.get("place") or "here"})
    except Exception:  # noqa: BLE001  a line is decoration; it never breaks the story feed
        return ""
