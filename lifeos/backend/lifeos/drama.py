"""Drama and gossip: rumors you can watch spread, friends fighting and you picking sides, triangles, falling out and
making up. Other people's drama happens too, and you hear about it.

- **Gossip finds you.** Most days, a friend texts you the juiciest thing going around that you haven't heard ("ok you
  can't say anything but..."). Phone → Scene → What people are saying lists everything you've heard: who it's about, who
  told you, and how far it's spread (a few people, your grade, half the school).
- **What you do with it.** About someone else: warn them, pass it on, or keep it to yourself. About you: set the record
  straight, own it, or find out who started it. Once per rumor; it's free, like texting.
- **Drama comes to you** as story moments, at most one every few days:
  - two of your friends fall out (over a screenshot, an ex, a party invite...) and both want you on their side;
  - someone's into your partner, or your partner's into someone (ask them, warn them off, or let it go: sometimes you
    hear about it later);
  - your crush gets with someone else (be happy for them, tell them anyway, or move on);
  - a friend goes cold on you (apologize, give it time, or write them off), and later, maybe, they reach out to fix it.
"""
from __future__ import annotations

import random
import zlib

from . import calendar as calm
from .catalogs import _base
from .history import Effects
from .rng import clamp

COOLDOWN = 5  # days between drama moments
_DATA = None


def D() -> dict:
    global _DATA
    if _DATA is None:
        _DATA = _base("drama.json")
    return _DATA


def _h(*p) -> int:
    return zlib.crc32(":".join(str(x) for x in p).encode())


def state(w) -> dict:
    s = w.meta.setdefault("drama", {})
    s.setdefault("last", -99)
    s.setdefault("acted", {})       # rumor id -> what you did
    s.setdefault("fallouts", [])    # [{a, b, day, reason, fixed}] between your friends
    s.setdefault("cold", {})        # friend id -> day they went cold on you
    s.setdefault("makeup", {})      # friend id -> day they might reach out
    s.setdefault("seen", {})        # what triggered recently (no repeats)
    return s


def register(moments: dict):
    for sid, sc in D()["scenes"].items():
        moments[f"drama_{sid}"] = {"title": sc["title"], "text": sc["text"], "drama": True,
                                   "choices": [{"label": ch["label"], "hint": ch.get("hint", ""), "fits": ch.get("fits", {}),
                                                "ops": [["drama", ch["op"]]]} for ch in sc["choices"]]}


def _me(sim):
    p = sim.w.meta.get("protagonist")
    return sim.w.chars.get(p) if p else None


def _friends(sim, me) -> list:
    w = sim.w
    fam = set(sim.siblings(me.id))
    return sorted((o for o, r in w.out.get(me.id, {}).items() if o in w.chars and w.chars[o].status == "active" and w.chars[o].role == "student"
                   and o not in fam and r.affection >= w.rules["rel.friend_threshold"]), key=lambda o: (-w.rels[(me.id, o)].affection, o))


def _first(w, cid):
    return w.chars[cid].first if cid in w.chars else "someone"


# ------------------------------------------------------------------------------------------------ what people are saying

def spread_word(n: int, school: int) -> str:
    q = n / max(1, school)
    return ("just a few people" if n <= 4 else "your friends know" if q < 0.15 else "your grade's talking" if q < 0.35
            else "half the school" if q < 0.7 else "everyone")


def view(sim) -> list:
    """Every rumor you've heard: about you first, then the freshest."""
    from .appearance import look_of
    w = sim.w
    me = _me(sim)
    st = state(w)
    school = sum(1 for c in w.chars.values() if c.role == "student" and c.status == "active" and c.school == me.school)
    out = []
    for rid, r in w.rumors.items():
        kb = r["known_by"].get(me.id)
        if not kb or w.day - r["day"] > 45:
            continue
        about = r["about"] if r["about"] in w.chars else None
        mine = about == me.id or me.id in (r.get("involves") or [])
        teller = kb[1] if len(kb) > 1 and kb[1] in w.chars and kb[1] != me.id else None
        n = len(r["known_by"])
        out.append({"id": rid, "text": r["text"], "about_you": mine, "true": r["truth"] if mine else None,
                    "about": about and {"id": about, "first": w.chars[about].first, "color": w.chars[about].color, "look": look_of(w.chars[about])},
                    "from": _first(w, teller) if teller else None, "known": n, "spread": spread_word(n, school),
                    "when": calm.label(kb[0]), "new": w.day - kb[0] <= 1, "acted": st["acted"].get(rid),
                    "origin": _first(w, r["origin"]) if st["acted"].get(rid) == "find" and r.get("origin") in w.chars else None,
                    "day": kb[0]})
    out.sort(key=lambda x: (not x["about_you"], -x["day"]))
    return out[:25]


def act(sim, rid: str, what: str) -> dict:
    """Do something with a rumor you've heard. Once per rumor."""
    from .actions import hear_rumor
    w = sim.w
    me = _me(sim)
    st = state(w)
    r = w.rumors.get(rid)
    if not r or me.id not in r["known_by"]:
        raise ValueError("you haven't heard that one")
    if st["acted"].get(rid):
        raise ValueError("you already dealt with that one")
    mine = r["about"] == me.id or me.id in (r.get("involves") or [])
    allowed = ("deny", "own", "find") if mine else ("tell", "pass", "drop")
    if what not in allowed:
        raise ValueError(f"pick one of: {', '.join(allowed)}")
    rng = random.Random(_h(w.seed, rid, what))
    about = r["about"] if r["about"] in w.chars else None
    ev = sim.new_event("gossip_choice", what, [me.id], [about] if about and about != me.id else [], 14, {"about": r["text"], "rumor": rid})
    fx = Effects(w, ev)
    knowers = [k for k in r["known_by"] if k != me.id and k in w.chars][:10]
    if what == "deny":
        charm = (me.aptitudes.get("charisma", 50) + me.popularity) / 2
        p = clamp(0.35 + (charm - 50) / 120 - (0.25 if r["truth"] else 0), 0.08, 0.9)
        if rng.random() < p:
            r["juice"] = round(max(0.05, r["juice"] - 0.4), 3)
            for k in knowers:
                fx.rel(k, me.id, "affection", 2.5, "set the record straight")
            ev["text"] = f"{me.short} set the record straight, and people believed it."
        else:
            r["juice"] = round(min(1.0, r["juice"] + 0.15), 3)
            fx.need(me.id, "stress", 6, "denying it made it worse")
            ev["text"] = f"{me.short} tried to set the record straight. It made people talk more."
    elif what == "own":
        r["juice"] = round(max(0.05, r["juice"] - 0.3), 3)
        fx.scalar(me.id, "popularity", clamp(me.popularity + (1.5 if me.traits.get("confidence", 50) >= 50 else -1), 0, 100), "owned it")
        fx.mood(me.id, 2, "owned it")
        ev["text"] = f"{me.short} owned it. Hard to gossip about someone who doesn't care."
    elif what == "find":
        o = r.get("origin")
        if o in w.chars and o != me.id and rng.random() < 0.7:
            fx.rel(me.id, o, "affection", -12, "started a rumor about them")
            fx.rel(me.id, o, "trust", -15, "started a rumor about them")
            ev["text"] = f"{me.short} found out who started it: {w.chars[o].name}."
        else:
            ev["text"] = f"{me.short} asked around about who started it. Nobody's saying."
    elif what == "tell":
        if about and about != me.id:
            r["known_by"][about] = [w.day, me.id, True]
            fx.rel(about, me.id, "trust", 6, "warned them about a rumor")
            fx.rel(about, me.id, "affection", 3, "warned them about a rumor")
            fx.mood(about, -4, "heard what people are saying")
            ev["text"] = f"{me.short} gave {w.chars[about].first} a heads-up about what people are saying."
    elif what == "pass":
        fr = [f for f in _friends(sim, me) if f not in r["known_by"] and f != about][:2]
        for f in fr:
            hear_rumor(sim, f, me.id, rid, ev, fx, rng, base_p=0.7)
            fx.rel(f, me.id, "affection", 1.5, "shared gossip")
        fx.rep(me.id, "gossip", 2, "spread a rumor")
        fx.need(me.id, "fun", 4, "gossip")
        caught = about and about in w.chars and r["valence"] < 0 and rng.random() < 0.3
        if caught:
            fx.rel(about, me.id, "affection", -8, "heard you were spreading it")
            fx.rel(about, me.id, "trust", -10, "heard you were spreading it")
        names = " and ".join(w.chars[f].first for f in fr) or "nobody new"
        ev["text"] = f"{me.short} passed it on to {names}." + (f" {w.chars[about].first} heard it came from {me.short}." if caught else "")
    else:
        ev["text"] = f"{me.short} kept it to themselves."
    st["acted"][rid] = what
    sim.finish(ev, fx)
    return ev


# ------------------------------------------------------------------------------------------------ every morning

def dawn(sim):
    w = sim.w
    me = _me(sim)
    if not me or me.status != "active" or me.role not in ("student",):
        return
    st = state(w)
    rng = random.Random(_h(w.seed, w.day, "drama"))
    _gossip_reaches_you(sim, me, st, rng)
    _notice_cold(sim, me, st)
    if w.day - st["last"] < COOLDOWN or any(m["kind"].startswith("drama_") and m["status"] == "pending" for m in w.meta.get("moments", [])):
        return
    for fn in (_makeup, _crush_taken, _partner, _friends_fight, _fallout):
        if fn(sim, me, st, rng):
            st["last"] = w.day
            return


def _gossip_reaches_you(sim, me, st, rng):
    """A friend texts you the juiciest thing going around that you haven't heard."""
    w = sim.w
    if "phone" not in w.meta or rng.random() > 0.4:
        return
    fr = _friends(sim, me)
    best, score = None, 0.0
    for rid, r in w.rumors.items():
        if me.id in r["known_by"] or w.day - r["day"] > 20 or r["about"] == me.id or me.id in (r.get("involves") or []):
            continue
        tellers = [f for f in fr if f in r["known_by"] and f != r["about"]]
        if not tellers:
            continue
        s = r["juice"] * (1 - (w.day - r["day"]) / 25)
        if s > score:
            best, score = (rid, tellers[0]), s
    if not best:
        return
    rid, teller = best
    r = w.rumors[rid]
    r["known_by"][me.id] = [w.day, teller, True]
    r["spread"] += 1
    opener = D()["open"][_h(w.day, rid) % len(D()["open"])]
    from . import messages
    messages.later(sim, teller, "scene", delay_phases=1, text=f"{opener} {r['text'][0].lower() + r['text'][1:]}")


def _notice_cold(sim, me, st):
    """Remember when a friend goes cold on you (so a fallout can come up, and maybe a make-up later)."""
    w = sim.w
    for o, r in list(w.out.items()):
        rr = r.get(me.id) if isinstance(r, dict) else None
        if not rr or o not in w.chars or w.chars[o].status != "active":
            continue
        if rr.peak_affection >= w.rules["rel.friend_threshold"] + 10 and rr.affection < 5 and o not in st["cold"]:
            st["cold"][o] = w.day
        elif o in st["cold"] and rr.affection >= w.rules["rel.friend_threshold"]:
            st["cold"].pop(o, None)


def _trigger(sim, kind, ctx):
    who = D()["scenes"][kind].get("them")
    if who and ctx.get(who) and who != "them":
        ctx["them"] = ctx[who]  # whose face is on the card
    sim.moment_trigger(f"drama_{kind}", sim.w.meta["protagonist"], ctx)


DID = {"side_a": "took {a_first}'s side", "side_b": "took {b_first}'s side", "stay_out": "stayed out of {a_first} and {b_first}'s fight",
       "mediate": "tried to get {a_first} and {b_first} to make up", "ask_partner": "asked {partner_first} about {other_first}",
       "warn_other": "warned {other_first} off", "let_go": "let the {other_first} thing go", "happy_for": "was happy for {crush_first} and {other_first}",
       "confess": "told {crush_first} how they feel", "move_on": "moved on from {crush_first}", "apologize": "apologized to {them_first}",
       "give_time": "gave {them_first} some space", "write_off": "wrote {them_first} off", "hear_out": "made up with {them_first}",
       "leave_it": "left {them_first} on read"}


def _friends_fight(sim, me, st, rng):
    """Two of your friends fall out, and both want you on their side."""
    w = sim.w
    fr = _friends(sim, me)
    if len(fr) < 2 or rng.random() > 0.1:
        return False
    pairs = [(a, b) for i, a in enumerate(fr) for b in fr[i + 1:]
             if w.rels.get((a, b)) and w.rels.get((b, a)) and w.rels[(a, b)].affection >= w.rules["rel.friend_threshold"] - 5
             and w.day - st["seen"].get(f"{a}|{b}", -99) > 45]
    if not pairs:
        return False
    a, b = pairs[_h(w.day, "pair") % len(pairs)]
    reason = D()["reasons"][_h(w.day, a, b) % len(D()["reasons"])].replace("{a_first}", _first(w, a)).replace("{b_first}", _first(w, b))
    ev = sim.new_event("falling_out", "friends", [a], [b], 26, {"reason": reason})
    ev["text"] = f"{w.chars[a].name} and {w.chars[b].name} fell out over {reason}."
    fx = Effects(w, ev)
    for x, y in ((a, b), (b, a)):
        fx.rel(x, y, "affection", -40, "fell out")
        fx.rel(x, y, "trust", -15, "fell out")
        fx.rel(x, y, "rivalry", 12, "fell out")
        fx.memory(x, "argument", [y], -0.6, 50, f"Fell out with {w.chars[y].name} over {reason}")
    sim.finish(ev, fx)
    st["seen"][f"{a}|{b}"] = w.day
    st["fallouts"].append({"a": a, "b": b, "day": w.day, "reason": reason, "fixed": False})
    st["fallouts"] = st["fallouts"][-12:]
    _trigger(sim, "sides", {"a": a, "b": b, "a_first": _first(w, a), "b_first": _first(w, b), "reason": reason})
    return True


def _partner(sim, me, st, rng):
    """Someone's into your partner, or your partner's into someone."""
    w = sim.w
    p = me.flags.get("partner")
    if not p or p not in w.chars or w.day - st["seen"].get("partner", -99) < 21:
        return False
    cands = []
    for o in w.chars.values():
        if o.id in (me.id, p) or o.status != "active" or o.role != "student":
            continue
        a, b = w.rels.get((p, o.id)), w.rels.get((o.id, p))
        if (a and a.attraction >= 50) or (b and b.crush and b.attraction >= 55):
            cands.append((max(a.attraction if a else 0, b.attraction if b else 0), o.id))
    if not cands or rng.random() > 0.35:
        return False
    other = max(cands)[1]
    st["seen"]["partner"] = w.day
    _trigger(sim, "partner", {"partner": p, "other": other, "partner_first": _first(w, p), "other_first": _first(w, other)})
    return True


def _crush_taken(sim, me, st, rng):
    """Your crush just got with someone else."""
    w = sim.w
    for o, r in w.out.get(me.id, {}).items():
        if not (r.crush or r.attraction >= 55) or o not in w.chars or o == me.flags.get("partner"):
            continue
        x = w.chars[o].flags.get("partner")
        bd = w.bond(o, x) if x else None
        since = (bd or {}).get("since", {}).get("partner", -99)
        if x and x != me.id and x in w.chars and w.day - since <= 7 and st["seen"].get(f"taken:{o}:{x}") is None:
            st["seen"][f"taken:{o}:{x}"] = w.day
            _trigger(sim, "crush_taken", {"crush": o, "other": x, "crush_first": _first(w, o), "other_first": _first(w, x)})
            return True
    return False


def _fallout(sim, me, st, rng):
    """A friend has gone cold on you."""
    w = sim.w
    for o, day in sorted(st["cold"].items(), key=lambda x: x[1]):
        if w.day - st["seen"].get(f"cold:{o}", -99) < 30 or o not in w.chars:
            continue
        mem = next((m for m in reversed(w.chars[o].memories) if me.id in m.get("with", []) and m.get("valence", 0) < 0), None)
        reason = (mem["text"][0].lower() + mem["text"][1:]) if mem else "that whole thing"
        reason = reason if len(reason) < 80 else "that whole thing"
        st["seen"][f"cold:{o}"] = w.day
        _trigger(sim, "fallout", {"them": o, "them_first": _first(w, o), "reason": reason})
        return True
    return False


def _makeup(sim, me, st, rng):
    """Someone you fell out with reaches out to fix it."""
    w = sim.w
    for o, day in list(st["makeup"].items()):
        if w.day >= day and o in w.chars and rng.random() < 0.5:
            st["makeup"].pop(o, None)
            if "phone" in w.meta:
                from . import messages
                messages.later(sim, o, "scene", delay_phases=0, text="hey. can we talk?")
            _trigger(sim, "makeup", {"them": o, "them_first": _first(w, o)})
            return True
    return False


# ------------------------------------------------------------------------------------------------ your calls

def op(sim, c, op, ctx, fx, ev, rng, m, render):
    from .actions import end_relationship, start_dating
    from .social import make_rumor
    w = sim.w
    st = state(w)
    what = op[1]
    fill = {**{k: v for k, v in ctx.items() if isinstance(v, str)}}

    def say(key):
        lines = D()["say"].get(key) or []
        if lines:
            s = lines[_h(w.day, key, m["id"]) % len(lines)]
            for k, v in fill.items():
                s = s.replace("{" + k + "}", v)
            ev["data"].setdefault("say", []).append(s)

    def chance(base, **pull):
        p = base + sum(coef * (c.traits.get(k, c.aptitudes.get(k, 50)) - 50) / 100 for k, coef in pull.items())
        return rng.random() < clamp(p, 0.05, 0.95)

    a, b = ctx.get("a"), ctx.get("b")
    did = DID.get(what)
    if did:
        for k, v in fill.items():
            did = did.replace("{" + k + "}", v)
        ev["text"] = f"{c.short} {did}."  # the feed says what you did
    if what in ("side_a", "side_b"):
        win, lose = (a, b) if what == "side_a" else (b, a)
        fx.rel(win, c.id, "affection", 8, "took their side")
        fx.rel(win, c.id, "trust", 6, "took their side")
        fx.rel(lose, c.id, "affection", -10, "took the other side")
        fx.rel(lose, c.id, "trust", -8, "took the other side")
        say(what)
    elif what == "stay_out":
        for x in (a, b):
            fx.rel(x, c.id, "affection", -2, "stayed out of it")
        say("stay_out")
    elif what == "mediate":
        if chance(0.42, charisma=0.3, empathy=0.25):
            for x, y in ((a, b), (b, a)):
                fx.rel(x, y, "affection", 24, "made up")
                fx.rel(x, y, "rivalry", -12, "made up")
                fx.rel(x, c.id, "affection", 5, "got them talking again")
            for f in st["fallouts"]:
                if {f["a"], f["b"]} == {a, b}:
                    f["fixed"] = True
            fx.rep(c.id, "kind", 2, "fixed a fight")
            say("mediate_ok")
        else:
            for x in (a, b):
                fx.rel(x, c.id, "affection", -3, "made it worse")
            say("mediate_bad")
    elif what == "ask_partner":
        p, o = ctx.get("partner"), ctx.get("other")
        att = w.rels[(p, o)].attraction if (p, o) in w.rels else 0
        if att < 55 or chance(0.5, charisma=0.2):
            fx.rel(p, c.id, "trust", 4, "talked it through")
            fx.rel(c.id, p, "trust", 4, "talked it through")
            say("ask_partner_ok")
        else:
            fx.rel(p, c.id, "affection", -3, "got questioned")
            fx.rel(c.id, p, "trust", -6, "got defensive")
            say("ask_partner_bad")
    elif what == "warn_other":
        p, o = ctx.get("partner"), ctx.get("other")
        fx.rel(c.id, o, "rivalry", 10, "warned them off")
        fx.rel(o, c.id, "rivalry", 8, "got warned off")
        att = w.rels[(p, o)].attraction if (p, o) in w.rels else 0
        if att < 50:
            fx.rel(o, p, "attraction", -10, "got warned off")
            fx.rel(p, c.id, "affection", 2, "kind of cute")
            say("warn_other_ok")
        else:
            fx.rel(p, c.id, "affection", -4, "embarrassed them")
            say("warn_other_bad")
    elif what == "let_go":
        p, o = ctx.get("partner"), ctx.get("other")
        att = w.rels[(p, o)].attraction if (p, o) in w.rels else 0
        if att >= 60 and rng.random() < 0.4:
            friend = next((f for f in _friends(sim, w.chars[c.id]) if f not in (p, o)), None)
            rid = make_rumor(sim, p, "kiss", f"{w.chars[p].name} and {w.chars[o].name} were all over each other at {w.chars[o].first}'s",
                             True, -0.4, 0.9, None, [x for x in (friend, o) if x], ev.get("id"), involves=[p, o])
            for x, y in ((p, o), (o, p)):
                fx.rel(x, y, "attraction", 8, "got close")
            sim.schedule(w.day + 2, "tell_subject", {"rumor": rid, "teller": friend, "jealous": c.id}, ev.get("id"))
            say("let_go_bad")
        else:
            fx.rel(p, c.id, "trust", 3, "trusted them")
            say("let_go_ok")
    elif what == "happy_for":
        cr = ctx.get("crush")
        fx.mood(c.id, -3, "your crush is taken")
        fx.rel(c.id, cr, "attraction", -10, "they're taken")
        fx.rel(cr, c.id, "affection", 3, "was happy for them")
        say("happy_for")
    elif what == "confess":
        cr, o = ctx.get("crush"), ctx.get("other")
        back = w.rels[(cr, c.id)].attraction if (cr, c.id) in w.rels else 0
        mine_now = w.rels[(cr, o)].affection if (cr, o) in w.rels else 50
        if back >= 55 and rng.random() < clamp(0.35 + (back - mine_now) / 150, 0.1, 0.7):
            if w.chars[cr].flags.get("partner") == o:
                end_relationship(sim, cr, o, ev, fx, reason=f"started dating {w.chars[c.id].short}")
            start_dating(sim, c.id, cr, ev, fx)
            make_rumor(sim, cr, "breakup", f"{w.chars[cr].name} left {w.chars[o].name} for {w.chars[c.id].name}", True, -0.2, 0.95, None,
                       [o], ev.get("id"), involves=[cr, o, c.id])
            fx.rel(o, c.id, "affection", -30, "stole their partner")
            fx.rel(o, c.id, "rivalry", 30, "stole their partner")
            say("confess_ok")
        else:
            fx.rel(cr, c.id, "affection", -4, "awkward confession")
            fx.mood(c.id, -6, "turned down")
            make_rumor(sim, c.id, "confession", f"{w.chars[c.id].name} told {w.chars[cr].name} they like them, even though {w.chars[cr].first}'s with {w.chars[o].first}",
                       True, -0.25, 0.8, None, [cr, o], ev.get("id"), involves=[c.id, cr])
            say("confess_bad")
    elif what == "move_on":
        cr = ctx.get("crush")
        fx.rel(c.id, cr, "attraction", -25, "moved on")
        fx.need(c.id, "stress", -3, "moved on")
        say("move_on")
    elif what == "apologize":
        t = ctx.get("them")
        if chance(0.5, empathy=0.3, charisma=0.2):
            fx.rel(t, c.id, "affection", 18, "apologized")
            fx.rel(t, c.id, "trust", 10, "apologized")
            fx.rel(c.id, t, "affection", 8, "made up")
            st["cold"].pop(t, None)
            say("apologize_ok")
        else:
            fx.rel(t, c.id, "affection", 3, "apologized")
            st["makeup"][t] = w.day + 10
            say("apologize_bad")
    elif what == "give_time":
        t = ctx.get("them")
        st["makeup"][t] = w.day + 7 + _h(w.day, t) % 8
        say("give_time")
    elif what == "write_off":
        t = ctx.get("them")
        fx.rel(c.id, t, "affection", -15, "wrote them off")
        fx.memory(c.id, "falling_out", [t], -0.4, 45, f"Stopped being friends with {w.chars[t].name}")
        st["cold"].pop(t, None)
        say("write_off")
    elif what == "hear_out":
        t = ctx.get("them")
        for x, y in ((t, c.id), (c.id, t)):
            fx.rel(x, y, "affection", 14, "made up")
            fx.rel(x, y, "trust", 8, "made up")
        fx.mood(c.id, 4, "made up")
        fx.memory(c.id, "made_up", [t], 0.5, 45, f"Made up with {w.chars[t].name}")
        st["cold"].pop(t, None)
        say("hear_out")
    elif what == "leave_it":
        t = ctx.get("them")
        fx.rel(t, c.id, "affection", -5, "left on read")
        say("leave_it")


def fights(sim) -> list:
    """Your friends who still aren't speaking."""
    w = sim.w
    st = state(w)
    out = []
    for f in st["fallouts"][::-1]:
        a, b = f["a"], f["b"]
        if f["fixed"] or a not in w.chars or b not in w.chars:
            continue
        r1, r2 = w.rels.get((a, b)), w.rels.get((b, a))
        if r1 and r2 and w.day - f["day"] <= 30 and min(r1.affection, r2.affection) < w.rules["rel.friend_threshold"] + 10:
            out.append({"a": _first(w, a), "b": _first(w, b), "reason": f["reason"], "when": calm.label(f["day"])})
    return out[:5]
