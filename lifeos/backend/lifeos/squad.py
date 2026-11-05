"""Your group: the friends you actually spend your time with ("the boys", "the girls", "the crew").

Zero maintenance. The group forms on its own from your closest friends and changes as friendships do. In your free time
it shows up as one choice for what you'd really do ("Hop on the game with the boys", "Park with the boys", "Food run"),
and whoever's free comes. Some days they make plans themselves ("on at 8?") and you can join or not; skipping now and
then costs nothing. Their group chat is there to read and never needs an answer.
"""
from __future__ import annotations

from . import calendar as calm
from .catalogs import _base
from .rng import clamp

_DATA = None


def D() -> dict:
    global _DATA
    if _DATA is None:
        _DATA = _base("squad.json")
    return _DATA


def _h(*parts) -> int:
    from .messages import _h as h
    return h(*parts)


def _me(sim):
    p = sim.w.meta.get("protagonist")
    return sim.w.chars.get(p) if p else None


def state(sim) -> dict | None:
    """Your group as it stands this week (recomputed weekly, members kept while they're still friends)."""
    w = sim.w
    me = _me(sim)
    if not me:
        return None
    s = w.meta.setdefault("squad", {"ids": [], "cohesion": 50.0, "formed": None, "updated": -99, "last_you": None, "jokes": []})
    if w.day - s.get("updated", -99) >= 7 or (s["ids"] and any(i not in w.chars for i in s["ids"])):
        _refresh(sim, me, s)
    return s if len(s["ids"]) >= 2 else None


def _pal(sim, me, o, bar):
    w = sim.w
    x = w.chars.get(o)
    if not x or x.status != "active" or x.role not in ("student", "alumni") or x.location != me.location:
        return False
    if o in sim.siblings(me.id) or o == me.flags.get("partner"):
        return False
    a, b = w.rels.get((me.id, o)), w.rels.get((o, me.id))
    return bool(a and b and a.affection >= bar and b.affection >= bar - 10)


def _refresh(sim, me, s):
    w = sim.w
    keep = [o for o in s["ids"] if _pal(sim, me, o, 25)]
    cands = sorted((o for o in w.out.get(me.id, {}) if o not in keep and _pal(sim, me, o, 38)),
                   key=lambda o: (-(w.rels[(me.id, o)].affection + w.rels[(o, me.id)].affection), o))
    ids = (keep + cands)[:4]
    if len(ids) >= 2 and len(s["ids"]) < 2:
        s["formed"] = w.day
    s["ids"] = ids
    s["updated"] = w.day
    genders = {w.chars[i].gender for i in ids} | {me.gender}
    s["name"] = "the boys" if genders == {"m"} else "the girls" if genders == {"f"} else "the crew"


def names(sim, ids) -> tuple[str, str]:
    w = sim.w
    firsts = [w.chars[i].first for i in ids if i in w.chars]
    a = firsts[0] if firsts else "someone"
    b = firsts[1] if len(firsts) > 1 else a
    return a, b


def acts_now(sim, slot) -> list:
    """Group things that fit this part of today (the season, the day, the weather in your town)."""
    s = state(sim)
    if not s:
        return []
    return acts_for(sim, slot, s["ids"])


def acts_for(sim, slot, ids) -> list:
    """Group things these people could do in this part of today."""
    w = sim.w
    me = _me(sim)
    if not me:
        return []
    d = calm.date_of(w.day)
    cal = sim.cat.world["calendar"]
    weekend = calm.weekday(w.day) >= 5
    school = calm.is_school_day(w.day, cal)
    out = []
    for aid, a in D()["acts"].items():
        if slot not in a["slots"]:
            continue
        if a.get("not_winter") and d.month in (12, 1, 2):
            continue
        if a.get("summer") and d.month not in (6, 7, 8):
            continue
        if a.get("weekend") and not weekend:
            continue
        if a.get("school_night") and not (school and calm.is_school_day(w.day + 1, cal)):
            continue
        if a.get("likes") and max([me.interests.get(a["likes"], 0)] + [w.chars[i].interests.get(a["likes"], 0) for i in ids if i in w.chars]) < 50:
            continue
        if a.get("cost", 0) and me.money < a["cost"]:
            continue
        out.append(aid)
    return out


def label(sim, aid, s=None) -> str:
    s = s or state(sim)
    host = sim.w.chars[s["ids"][0]].first if s else "someone"
    return D()["acts"][aid]["label"].format(group=s["name"] if s else "the crew", host=host)


def plan(sim) -> dict | None:
    """What the group has going today, if anything."""
    s = state(sim)
    p = (s or {}).get("plan")
    return p if p and p.get("day") == sim.w.day else None


def dawn(sim):
    """Mornings: sometimes the group makes plans for later today. They post in their chat; you don't have to answer."""
    w = sim.w
    s = state(sim)
    if not s:
        return
    last = s.get("last_you")
    if last is not None and w.day - last > 5:
        s["cohesion"] = clamp(s["cohesion"] - 1.0, 0, 100)
    weekend = calm.weekday(w.day) >= 5
    p_plan = 0.25 + s["cohesion"] / 250 + (0.2 if weekend else 0.0)
    if _h(w.day, "squad") % 1000 / 1000 >= p_plan:
        return
    slots = ["day", "evening"] if not calm.is_school_day(w.day, sim.cat.world["calendar"]) else ["evening", "after_school"]
    for slot in slots:
        opts = acts_now(sim, slot)
        if opts:
            aid = opts[_h(w.day, "squad-act") % len(opts)]
            s["plan"] = {"day": w.day, "slot": slot, "act": aid}
            _chat(sim, s, "plan", aid)
            return


def _chat(sim, s, kind, aid=None):
    """A line or two in the group chat. It's quiet: it never needs an answer and never counts as unread."""
    from .messages import post
    w = sim.w
    if "phone" not in w.meta:
        return
    host = w.chars[s["ids"][0]].first
    a, b = names(sim, s["ids"][1:] + s["ids"][:1])
    fill = {"group": s["name"], "host": host, "a": a, "b": b}
    pool = D()["chat"][kind][aid] if kind == "plan" else D()["chat"][kind]
    who = s["ids"][_h(w.day, kind) % len(s["ids"])]
    title = s["name"][0].upper() + s["name"][1:]
    post(sim, "squad", who, pool[_h(w.day, kind, "l") % len(pool)].format(**fill), kind="squad", unread=False, title=title,
         members=list(s["ids"]), tkind="group")
    if kind == "plan":
        other = next((i for i in s["ids"] if i != who), who)
        agree = D()["chat"]["agree"]
        post(sim, "squad", other, agree[_h(w.day, "agree") % len(agree)], kind="squad", unread=False, title=title,
             members=list(s["ids"]), tkind="group")


def night(sim):
    """If they had plans and you didn't come, they went without you (and you hear about it, a little)."""
    w = sim.w
    s = state(sim)
    p = plan(sim)
    if not s or not p or p.get("joined"):
        return
    s["cohesion"] = clamp(s["cohesion"] - 1.5, 0, 100)
    _chat(sim, s, "fomo")
    s["plan"] = None


def option(sim, opts, slot) -> list:
    """Your group, as choices for right now: what they've got going first, then one more idea."""
    w = sim.w
    s = state(sim)
    if not s:
        return []
    hang = {o["target"]: o for o in opts if o["action"] == "hang_out" and o.get("target")}
    present = [i for i in s["ids"] if not sim.committed(i, slot)]
    main = next((i for i in present if i in hang), None)
    if main is None:
        return []
    rest = [i for i in present if i != main]
    if not rest:
        return []
    avail = acts_now(sim, slot)
    p = plan(sim)
    picks = []
    if p and p["slot"] == slot and p["act"] in avail:
        picks.append((p["act"], f"{s['name'].capitalize()} are on {'tonight' if slot == 'evening' else 'today'}" if p["act"] == "game"
                      else f"{s['name'].capitalize()} made plans"))
    others = [a for a in avail if a not in [x for x, _ in picks]]
    if others:
        picks.append((others[_h(w.day, slot, "alt") % len(others)], "Your group"))
    firsts = [w.chars[main].first] + [w.chars[i].first for i in rest]
    out = []
    for aid, why in picks[:2]:
        base = hang[main]
        out.append(dict(base, key=f"squad:{aid}", action="squad", act=aid, crew=rest, text=label(sim, aid, s),
                        reason=why, who=", ".join(firsts), group="want", section="people", later=None, gut=False, icon="people"))
    return out


def pending_act(sim):
    """The group thing you just picked for this part of the day, if any."""
    ask = sim.w.meta.get("control", {}).get("crew") or {}
    if ask.get("day") != sim.w.day or ask.get("slot") != (sim.slot.slot if sim.slot else None):
        return None
    return ask.get("act")


def place_for(sim, aid, host_id) -> dict:
    a = D()["acts"][aid]
    host = sim.w.chars[host_id].first if host_id in sim.w.chars else "someone"
    return {"name": a["place"].format(host=host), "cost": a.get("cost", 0)}


def after(sim, c, b, came, aid, ev, fx, rng):
    """You did the group thing: it reads like what it was, it does what it does, and the group gets tighter."""
    w = sim.w
    s = state(sim)
    a = D()["acts"][aid]
    everyone = [b] + list(came)
    x, y = names(sim, everyone)
    host = w.chars[b].first
    lines = a["lines"]
    ev["text"] = lines[_h(w.day, aid, b) % len(lines)].format(group=(s["name"] if s else "the crew"), a=x, b=y, host=host)
    ev["data"]["act"] = aid
    ev["data"].pop("crew_line", None)  # the line already says who was there
    ev["data"].pop("why", None)  # and the scene that comes next says how it went
    if a.get("sport"):
        sport = a["sport"] if isinstance(a["sport"], str) else max(("football", "basketball", "baseball", "soccer", "softball"), key=lambda k: c.interests.get(k, 0))
        fx.skill(c.id, sport, 0.25, label(sim, aid, s))
        fx.skill(c.id, "fitness", 0.1, label(sim, aid, s))
    if aid == "study":
        fx.skill(c.id, "academics", 0.25, "homework on FaceTime")
    if aid == "game":
        fx.need(c.id, "energy", 5, "stayed home")  # gaming from your room is easier than going out
    if s:
        s["cohesion"] = clamp(s["cohesion"] + 5, 0, 100)
        s["last_you"] = w.day
        p = plan(sim)
        if p and p["act"] == aid:
            p["joined"] = True
        if rng.random() < 0.5:
            _chat(sim, s, "after")


def remember_joke(sim, text):
    s = state(sim)
    if s and text:
        s["jokes"] = (s.get("jokes", []) + [text])[-5:]


def view(sim) -> dict | None:
    """Your group for the Me tab: who, how tight, when you last hung out, what's planned. Nothing to manage."""
    from .appearance import look_of
    w = sim.w
    s = state(sim)
    if not s:
        return None
    last = s.get("last_you")
    p = plan(sim)
    return {"name": s["name"], "members": [{"id": i, "first": w.chars[i].first, "look": look_of(w.chars[i])} for i in s["ids"]],
            "cohesion": round(s["cohesion"]),
            "last": None if last is None else "today" if last == w.day else "yesterday" if w.day - last == 1 else f"{w.day - last} days ago",
            "plan": p and {"label": label(sim, p["act"], s), "when": {"evening": "tonight", "after_school": "after school", "day": "today"}.get(p["slot"], p["slot"]),
                           "joined": bool(p.get("joined"))},
            "jokes": s.get("jokes", [])[-3:]}


# ------------------------------------------------------------------------------------------------ how hanging out really works
# Mostly in small groups. One on one is for the people you're actually close to, and it doesn't happen every day.
# Nobody asks while they have practice, or while you do.

VERB = {"game": "hopping on the game", "park": "going to the park", "hoops": "shooting around", "food": "getting food",
        "movie": "catching a movie", "beach": "going to the beach", "study": "doing homework together"}
WHEN = {"after_school": "after school", "evening": "tonight", "day": "today"}
MAX_ASKS = 2  # one-on-one invites to you in a week (your partner doesn't count)


def can_ask(sim, asker, slot) -> bool:
    """Would this person really ask you to hang out, just the two of you, right now?"""
    w = sim.w
    me = w.meta.get("protagonist")
    if not me or asker == me or me not in w.chars:
        return False
    if sim.committed(me, slot) or sim.committed(asker, slot):
        return False  # one of you has practice (or a game, or a show)
    a, b = w.rels.get((asker, me)), w.rels.get((me, asker))
    if not a or not b:
        return False
    if w.chars[me].flags.get("partner") == asker:
        return True
    thr = w.rules["rel.friend_threshold"]
    close = a.familiarity >= 40 and a.affection >= thr and b.familiarity >= 30
    keen = a.attraction >= 55 and a.familiarity >= 30
    family = asker in sim.siblings(me)
    if not (close or keen or family):
        return False  # they barely know you: they'd ask you along with the group, not alone
    return sum(1 for d in w.meta.get("asks", []) if w.day - d < 7) < MAX_ASKS


def note_ask(w):
    w.meta["asks"] = (w.meta.get("asks", []) + [w.day])[-10:]


def close_to(sim, me, o) -> bool:
    """People you'd hang out with one on one."""
    w = sim.w
    r = w.rels.get((me.id, o))
    if not r:
        return False
    return (o == me.flags.get("partner") or o in sim.siblings(me.id) or r.affection >= w.rules["rel.close_threshold"]
            or r.attraction >= 45)


def busy_friends(sim, slot) -> list:
    """Your friends who are at practice, a game or a show right now."""
    w = sim.w
    me = _me(sim)
    out = []
    for o, r in w.out.get(me.id, {}).items():
        if o in w.chars and r.affection >= w.rules["rel.friend_threshold"] and w.chars[o].status == "active":
            k = sim.committed(o, slot)
            if k:
                out.append({"id": o, "first": w.chars[o].first, "what": k["kind"]})
    return sorted(out, key=lambda x: x["first"])[:6]


def invite(sim) -> dict | None:
    gi = sim.w.meta.get("group_invite")
    return gi if gi and gi.get("day") == sim.w.day else None


def invite_dawn(sim):
    """Some mornings a friend asks you along with a few of their people ("me, Cole and Kai are getting food after
    school. you in?"). It's how you end up hanging out with friends of friends."""
    w = sim.w
    me = _me(sim)
    if not me or "phone" not in w.meta or plan(sim):
        return
    cal = sim.cat.world["calendar"]
    school = calm.is_school_day(w.day, cal)
    if _h(w.day, "group-invite") % 1000 / 1000 >= (0.3 if school else 0.45):
        return
    slot = "after_school" if school and _h(w.day, "gi-slot") % 2 else "evening" if school else "day"
    if sim.committed(me.id, slot):
        slot = "evening"
        if sim.committed(me.id, slot):
            return
    thr = w.rules["rel.friend_threshold"]
    s = state(sim)
    hosts = sorted((o for o, r in w.out.get(me.id, {}).items() if o in w.chars and w.chars[o].status == "active"
                    and w.chars[o].role in ("student", "alumni") and w.chars[o].location == me.location and r.affection >= thr
                    and w.rels.get((o, me.id)) and w.rels[(o, me.id)].affection >= thr - 5 and w.rels[(o, me.id)].familiarity >= 30
                    and o not in sim.siblings(me.id) and not sim.committed(o, slot)), key=lambda o: o)
    if not hosts:
        return
    host = hosts[_h(w.day, "gi-host") % len(hosts)]
    pals = sorted((x for x, r in w.out.get(host, {}).items() if x != me.id and x in w.chars and w.chars[x].status == "active"
                   and w.chars[x].role in ("student", "alumni") and w.chars[x].location == me.location and r.affection >= thr
                   and not sim.committed(x, slot) and x not in sim.siblings(me.id)),
                  key=lambda x: (-w.rels[(host, x)].affection, x))
    if not pals:
        return
    crew = pals[:1 + _h(w.day, "gi-n") % 2]
    acts = acts_for(sim, slot, [host] + crew)
    if not acts:
        return
    act = acts[_h(w.day, "gi-act") % len(acts)]
    gi = {"day": w.day, "slot": slot, "host": host, "crew": crew, "act": act, "id": f"gi{w.day}", "answer": None}
    w.meta["group_invite"] = gi
    names = [w.chars[x].first for x in crew]
    who = f"me and {names[0]}" if len(names) == 1 else f"me, {names[0]} and {names[1]}"
    from .messages import post
    post(sim, f"dm:{host}", host, f"{who} are {VERB.get(act, 'hanging out')} {WHEN.get(slot, 'later')}. you in?", kind="invite",
         replies=[{"label": "i'm in", "fx": f"group:{gi['id']}:yes"}, {"label": "can't today", "fx": f"group:{gi['id']}:no"}],
         ctx={"group_invite": gi["id"]})


def answer_invite(sim, gid, yes: bool) -> str | None:
    """You answered a group invite by text: it's a plan (or it isn't)."""
    from .moments import control
    w = sim.w
    gi = invite(sim)
    if not gi or gi["id"] != gid:
        return None
    gi["answer"] = "yes" if yes else "no"
    if yes:
        control(w)["queued"] = {"action": "hang_out", "target": gi["host"], "agreed": True, "day": w.day, "slot": gi["slot"],
                                "label": label_for_invite(sim, gi)}
        control(w)["crew"] = {"day": w.day, "slot": gi["slot"], "ids": list(gi["crew"]), "act": gi["act"]}
    return "react_plans_yes" if yes else None


def label_for_invite(sim, gi) -> str:
    w = sim.w
    names = [w.chars[x].first for x in [gi["host"]] + gi["crew"] if x in w.chars]
    who = ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]
    act = D()["acts"].get(gi["act"], {})
    thing = {"game": "On the game", "park": "Park", "hoops": "Hoops", "food": "Food", "movie": "Movie", "beach": "Beach",
             "study": "Homework"}.get(gi["act"], "Hanging out")
    return f"{thing} with {who}"


def invite_option(sim, opts, slot) -> list:
    """The group invite, as a choice for right now (if it's for now and you haven't said no)."""
    w = sim.w
    gi = invite(sim)
    if not gi or gi["slot"] != slot or gi.get("answer") == "no":
        return []
    hang = {o["target"]: o for o in opts if o["action"] == "hang_out" and o.get("target")}
    base = hang.get(gi["host"])
    if not base:
        return []
    crew = [x for x in gi["crew"] if not sim.committed(x, slot)]
    names = [w.chars[x].first for x in [gi["host"]] + crew]
    return [dict(base, key=f"invite:{gi['id']}", action="squad", act=gi["act"], crew=crew, text=label_for_invite(sim, dict(gi, crew=crew)),
                 reason=f"{w.chars[gi['host']].first} asked you", who=", ".join(names), group="want", section="people", later=None,
                 gut=False, icon="people")]


def must_list(sim, slot) -> list:
    """People who should be in your choices right now: your group, and whoever invited you."""
    w = sim.w
    s = state(sim)
    ids = list(s["ids"]) if s else []
    gi = invite(sim)
    if gi and gi["slot"] == slot:
        ids.append(gi["host"])
    return [i for i in ids if i in w.chars and not sim.committed(i, slot)]
