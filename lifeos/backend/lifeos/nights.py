"""Big nights: a party or a dance plays out as a few short scenes, built around who's actually there.

When you go to a party, throw one, or go to Homecoming, the Snow Ball or prom, the night doesn't just happen to you. It's
an opening (walking in, or getting ready with your date or your friends), two things that happen in the middle, and the
end of the night. The middle depends on who came: your crush alone on the porch, cups on the ping-pong table, your rival
looking for trouble, two people about to fight, somebody with a secret (a real one: who likes who), your partner talking
to someone a little too long, the dance-off circle, the slow song. If the cops show up, that's how it ends.

Every choice does real things (who likes you, who you met, a kiss that turns into dating, your parents finding out),
and the night ends with a one-line recap and a memory. When you skip ahead, your character plays the night for you.
"""
from __future__ import annotations

import random
import zlib

from .catalogs import _base
from .history import Effects
from .rng import clamp

START = ("arrive", "host", "getready_date", "getready_group")
_DATA = None


def D() -> dict:
    global _DATA
    if _DATA is None:
        _DATA = _base("nights.json")
    return _DATA


def _h(*p) -> int:
    return zlib.crc32(":".join(str(x) for x in p).encode())


def is_night(kind: str) -> bool:
    return kind.startswith("night_")


def register(moments: dict):
    """Every beat becomes a story moment night_<beat>; each choice ends by moving the night along."""
    for bid, b in D()["beats"].items():
        choices = []
        for ch in b.get("choices") or []:
            ops = list(ch["ops"])
            if ch.get("did"):
                ops.append(["night", "did", ch["did"]])
            ops.append(["night", "end" if bid == "end" else "next"])
            choices.append({"label": ch["label"], "hint": ch.get("hint", ""), "ops": ops, "fits": ch.get("fits", {}),
                            **({"requires": ch["requires"]} if ch.get("requires") else {})})
        moments[f"night_{bid}"] = {"title": b["title"], "text": b["text"], "choices": choices, "night": True,
                                   "no_episode": bid not in START, **({"dynamic": "night_people"} if b.get("dynamic") else {})}


def state(w) -> dict | None:
    st = w.meta.get("night")
    return st if st and st.get("day", -9) >= w.day - 1 else None


# ------------------------------------------------------------------------------------------------ who's there

def _cast(sim, me, came, host, date) -> dict:
    w, R = sim.w, sim.w.rules
    present = [x for x in came if x != me.id and x in w.chars and w.chars[x].status == "active"]
    rel = lambda a, b: w.rels.get((a, b))  # noqa: E731
    partner = me.flags.get("partner") if me.flags.get("partner") in present else None
    date = date if date in present else None
    fr = sorted((x for x in present if rel(me.id, x) and rel(me.id, x).affection >= R["rel.friend_threshold"]),
                key=lambda x: (-rel(me.id, x).affection, x))
    friend = next((x for x in fr if x not in (partner, date)), None) or (host if host and host != me.id else None) \
        or (present[0] if present else None)
    crushes = sorted((x for x in present if x not in (partner, date) and rel(me.id, x)
                      and (rel(me.id, x).crush or rel(me.id, x).attraction >= 45)), key=lambda x: (-rel(me.id, x).attraction, x))
    crush = crushes[0] if crushes else None
    rivals = sorted((x for x in present if rel(me.id, x) and (rel(me.id, x).rivalry >= 40 or rel(me.id, x).affection <= -25)),
                    key=lambda x: (-(rel(me.id, x).rivalry - rel(me.id, x).affection), x))
    rival = rivals[0] if rivals else None
    others = [x for x in present if x not in (partner, date)]
    fight = None
    for i, a in enumerate(others):
        for b in others[i + 1:]:
            ra = rel(a, b)
            if ra and (ra.rivalry >= 40 or ra.affection <= -30):
                fight = (a, b)
                break
        if fight:
            break
    # a real secret: somebody here likes somebody here (best if it's you)
    secret = None
    for x in present:
        r = rel(x, me.id)
        if r and r.crush and x != partner:
            secret = (x, me.id)
            break
    if not secret:
        for x in present:
            for y, r in w.out.get(x, {}).items():
                if r.crush and y in present and y != x and x != me.id and y not in (partner,):
                    secret = (x, y)
                    break
            if secret:
                break
    gossip = next((x for x in sorted(present, key=lambda x: (-w.chars[x].traits.get("sociability", 50), x))
                   if secret and x not in secret and x != me.id), None)
    other = None
    if partner:
        cands = sorted((x for x in present if x not in (partner, me.id) and rel(partner, x) and rel(partner, x).attraction >= 30),
                       key=lambda x: (-rel(partner, x).attraction, x))
        other = cands[0] if cands else None
    challenger = rival or next((x for x in present if x not in (friend, crush, partner, date)), friend)
    after = max(present, key=lambda x: (w.chars[x].popularity, x)) if present else host
    return {"friend": friend, "crush": crush, "partner": partner, "date": date, "rival": rival, "host": host if host != me.id else None,
            "a": fight[0] if fight else None, "b": fight[1] if fight else None, "gossip": gossip if secret else None,
            "secret_x": secret[0] if secret else None, "secret_y": secret[1] if secret else None, "other": other,
            "challenger": challenger, "after": after, "present": present}


def _plan(sim, kind, cast, hosting, busted, rng) -> list:
    if kind == "dance":
        opening = "getready_date" if cast["date"] else "getready_group"
        pool = {"slow": 2.0 if (cast["date"] or cast["crush"]) else 0, "talk": 0.8, "porch": 1.0 if cast["crush"] and not cast["date"] else 0,
                "secret": 0.9 if cast["secret_x"] and cast["gossip"] else 0, "jealous": 1.3 if cast["other"] else 0,
                "beef": 0.8 if cast["rival"] else 0}
        if cast["date"] or cast["crush"]:
            mids = ["dancefloor", "slow"]  # with a date (or your crush there), the slow song is the night
        else:
            pool.pop("slow", None)
            mids = ["dancefloor", _pick(pool, rng)]
        return [opening] + [m for m in mids if m] + ["end"]
    opening = "host" if hosting else "arrive"
    pool = {"game": 1.0, "talk": 0.9, "porch": 1.6 if cast["crush"] else 0, "fight": 1.0 if cast["a"] else 0,
            "beef": 1.2 if cast["rival"] else 0, "secret": 1.0 if cast["secret_x"] and cast["gossip"] else 0,
            "jealous": 1.4 if cast["other"] else 0}
    first = _pick(pool, rng)
    pool.pop(first, None)
    second = _pick(pool, rng)
    return [opening, first, second, "busted" if busted else "end"]


def _pick(pool, rng):
    items = [(k, v) for k, v in pool.items() if v > 0]
    if not items:
        return None
    tot = sum(v for _, v in items)
    x = rng.random() * tot
    for k, v in items:
        x -= v
        if x <= 0:
            return k
    return items[-1][0]


def start(sim, kind: str, key: str, event: str, came: list, host=None, date=None, busted=False):
    """The protagonist is at a party or a dance: plan tonight and start the first scene."""
    w = sim.w
    me = w.chars.get(w.meta.get("protagonist") or "")
    if not me or me.id not in came:
        return
    rng = random.Random(_h(w.seed, key, "night"))
    cast = _cast(sim, me, came, host, date)
    if not cast["present"]:
        return
    hosting = host == me.id
    st = {"key": key, "kind": kind, "day": w.day, "i": 0, "did": [], "met": [], "busted": bool(busted), "n": len(came),
          "event": event, "hosting": hosting, "cast": {k: v for k, v in cast.items() if k != "present"}, "present": cast["present"],
          "plan": _plan(sim, kind, cast, hosting, busted, rng), "kissed": None}
    w.meta["night"] = st
    _trigger(sim, st)


def _first(w, cid):
    return w.chars[cid].first if cid in w.chars else ""


def _ctx(sim, st, beat) -> dict:
    w = sim.w
    cast = st["cast"]
    ctx = {"event": st["event"], "n": st["n"], "night": st["key"], "night_step": st["i"] + 1, "night_len": len(st["plan"]), "mg_label": st["event"]}
    for k in ("friend", "crush", "partner", "date", "rival", "host", "a", "b", "gossip", "other", "challenger", "after"):
        v = cast.get(k)
        if v and v in w.chars:
            ctx[k] = v
            ctx[f"{k}_first"] = _first(w, v)
    if not ctx.get("host_first"):
        ctx["host_first"] = "your"
    if cast.get("secret_x"):
        x, y = cast["secret_x"], cast["secret_y"]
        me = w.meta.get("protagonist")
        ctx["secret"] = (f"{_first(w, x)} has a thing for you. Like, a real thing." if y == me
                         else f"{_first(w, x)} likes {_first(w, y)}. Has for months.")
    spec = D()["beats"].get(beat, {})
    who = spec.get("them")
    if who and ctx.get(who):
        ctx["them"] = ctx[who]
        ctx["them_first"] = ctx[f"{who}_first"]
    if beat == "dancefloor":  # the dance-off is the "Stop it" game, on the beat
        ctx.update({"cg_skin": "beat", "cg_title": "Dance-off", "cg_how": "Tap when the needle hits the beat."})
    return ctx


def _trigger(sim, st):
    beat = st["plan"][st["i"]]
    sim.moment_trigger(f"night_{beat}", sim.w.meta["protagonist"], _ctx(sim, st, beat))


def label(m) -> str | None:
    c = m.get("ctx") or {}
    if not c.get("night"):
        return None
    return f"{c.get('event')} · {c.get('night_step')} of {c.get('night_len')}"


# ------------------------------------------------------------------------------------------------ the scenes

def people_choices(sim, c, ctx) -> list:
    """"Who do you end up with?": the people here who matter to you, and somebody new."""
    w = sim.w
    st = state(w)
    if not st:
        return []
    cast = st["cast"]
    picks = []
    for k, hint in (("crush", "you know why"), ("partner", "your person"), ("date", "your date"), ("friend", "your friend"), ("rival", "you two have history")):
        v = cast.get(k)
        if v and v in w.chars and v not in [p for p, _ in picks]:
            picks.append((v, hint))
    new = sorted((x for x in st["present"] if x not in [p for p, _ in picks] and (not w.rels.get((c.id, x)) or w.rels[(c.id, x)].familiarity < 20)),
                 key=lambda x: (-w.chars[x].popularity, x))
    if new:
        picks.append((new[_h(w.day, "new") % min(3, len(new))], "someone new"))
    out = []
    for cid, hint in picks[:4]:
        o = w.chars[cid]
        out.append({"label": f"{o.first} {o.last}", "hint": hint, "fits": {},
                    "ops": [["night", "talk", cid], ["night", "next"]]})
    out.append({"label": "Nobody. Find the bathroom line.", "hint": "regroup", "fits": {"sociability": -0.6},
                "ops": [["need", "stress", -2], ["night", "did", "hid in the bathroom line"], ["night", "next"]]})
    return out


def op(sim, c, op, ctx, fx, ev, rng, m, render):
    w = sim.w
    st = state(w)
    what = op[1]
    say = lambda s: ev["data"].setdefault("say", []).append(render(s))  # noqa: E731
    if not st:
        return
    cast = st["cast"]
    if what == "did":
        did = render(op[2])
        st["did"].append(did)
        ev["text"] = f"{c.short} {did}."  # the feed says what you did ("You stuck with Danny.")
    elif what == "next":
        st["i"] += 1
        if st["i"] < len(st["plan"]):
            _trigger(sim, st)
        else:
            _end(sim, c, st, fx, ev, render)
    elif what == "end":
        _end(sim, c, st, fx, ev, render)
    elif what == "focus":
        beat = op[2]
        ok = (beat == "porch" and cast.get("crush")) or (beat == "secret" and cast.get("secret_x") and cast.get("gossip"))
        nxt = st["i"] + 1
        if ok and nxt < len(st["plan"]) - 1 and beat not in st["plan"][nxt:]:
            st["plan"][nxt] = beat  # you went looking: that's what happens next
        elif ok and beat in st["plan"][nxt:]:
            st["plan"].remove(beat)
            st["plan"].insert(nxt, beat)
    elif what == "meet":
        _meet(sim, c, st, int(op[2]), fx, rng, say)
    elif what == "crew":
        fr = [x for x in st["present"] if w.rels.get((c.id, x)) and w.rels[(c.id, x)].affection >= w.rules["rel.friend_threshold"]][:5]
        for x in fr:
            fx.rel(x, c.id, "affection", 1.5 * float(op[2]), st["event"])
            fx.rel(c.id, x, "affection", 1.0 * float(op[2]), st["event"])
    elif what == "popular":
        fx.scalar(c.id, "popularity", clamp(c.popularity + float(op[2]), 0, 100), st["event"])
    elif what == "talk":
        _talk(sim, c, st, op[2], fx, ev, rng, say)
    elif what == "romance":
        _romance(sim, c, st, op[2], op[3], ctx, fx, ev, rng, say)
    elif what == "secret":
        _secret(sim, c, st, op[2], fx, ev, rng, say)
    elif what == "jealous":
        _jealous(sim, c, st, op[2], fx, rng, say)
    elif what == "trouble":
        sim.schedule(w.day + 1, "parents_find_out", {"char": c.id, "what": op[2]}, ev.get("id"))
    elif what == "curfew":
        p = clamp(0.25 + (0.25 if _school_tomorrow(sim) else 0) - (c.traits.get("discipline", 50) - 50) / 200, 0.05, 0.7)
        if rng.random() < p:
            sim.schedule(w.day + 1, "parents_find_out", {"char": c.id, "what": "coming home way after curfew"}, ev.get("id"))
            say("You sneak in at 2am. The kitchen light is on. Busted.")
        else:
            say("Pancakes at 1am, then you sneak in without a sound. Legend.")


def _school_tomorrow(sim) -> bool:
    from . import calendar as calm
    return calm.is_school_day(sim.w.day + 1, sim.cat.world["calendar"])


def _meet(sim, c, st, n, fx, rng, say):
    w = sim.w
    new = sorted((x for x in st["present"] if not w.rels.get((c.id, x)) or w.rels[(c.id, x)].familiarity < 20),
                 key=lambda x: (-w.chars[x].traits.get("sociability", 50), x))
    rng.shuffle(new)
    met = new[:n]
    if not met:
        say("You already know basically everyone here. You make the rounds anyway.")
        fx.need(c.id, "social", 6, st["event"])
        return
    charm = (c.aptitudes.get("charisma", 50) + c.traits.get("sociability", 50)) / 2
    for x in met:
        good = rng.random() < clamp(0.45 + (charm - 50) / 100, 0.15, 0.9)
        for a, b in ((c.id, x), (x, c.id)):
            fx.rel(a, b, "familiarity", 14, st["event"])
            fx.rel(a, b, "affection", 6 if good else 2, st["event"])
        if "phone" in w.meta and good:
            from . import messages
            messages.add_contact(sim, x, "party")
    st["met"] += met
    names = [w.chars[x].first for x in met]
    say(f"You meet {' and '.join(names)}." + (" You swap numbers." if "phone" in w.meta else ""))
    fx.need(c.id, "social", 8, st["event"])
    fx.scalar(c.id, "popularity", clamp(c.popularity + 1.5, 0, 100), st["event"])


def _talk(sim, c, st, cid, fx, ev, rng, say):
    from .worldgen import compatibility
    w = sim.w
    if cid not in w.chars:
        return
    o = w.chars[cid]
    rab = w.ensure_rel(c.id, cid, w.day)
    rba = w.ensure_rel(cid, c.id, w.day)
    q = 0.15 + 0.35 * compatibility(w, c, o) + 0.2 * rba.affection / 100 + (c.aptitudes.get("charisma", 50) - 50) / 250 + rng.gauss(0, 0.25)
    if rab.rivalry >= 40 or rab.affection <= -25:
        q -= 0.25
    tier = "great" if q >= 0.45 else "good" if q >= 0.1 else "bad"
    gain = {"great": 6, "good": 3, "bad": -2}[tier]
    for a, b in ((c.id, cid), (cid, c.id)):
        fx.rel(a, b, "familiarity", 8, st["event"])
        fx.rel(a, b, "affection", gain, st["event"])
    if tier == "great" and (rba.attraction >= 30 or rab.crush):
        fx.rel(cid, c.id, "attraction", 4, st["event"])
    if rab.rivalry >= 40 and tier != "bad":
        fx.rel(c.id, cid, "rivalry", -6, st["event"])
        fx.rel(cid, c.id, "rivalry", -6, st["event"])
    lines = {"great": [f"You and {o.first} end up on the back steps talking for an hour. It's the best part of the night.",
                       f"{o.first} is way funnier than you knew. You lose track of time."],
             "good": [f"You and {o.first} talk for a while. It's easy.", f"Good talk with {o.first}, until somebody drags them away."],
             "bad": [f"It's a short, awkward chat. {o.first} keeps looking past you.", f"You and {o.first} run out of things to say fast."]}[tier]
    say(lines[_h(w.day, cid, tier) % len(lines)])
    did = f"talked with {o.first}" if tier != "bad" else f"had an awkward talk with {o.first}"
    st["did"].append(did)
    ev["text"] = f"{c.short} {did}."


def _romance(sim, c, st, who, kind, ctx, fx, ev, rng, say):
    from .actions import start_dating
    from .social import make_rumor
    w = sim.w
    cid = st["cast"].get(who)
    if not cid or cid not in w.chars:
        return
    o = w.chars[cid]
    rba = w.ensure_rel(cid, c.id, w.day)
    rab = w.ensure_rel(c.id, cid, w.day)
    together = c.flags.get("partner") == cid
    bias = {"slow": 0.3, "door": 0.25, "porch": 0.05, "walk": 0.1, "ask": 0.0}.get(kind, 0.0) + (0.2 if together or who == "date" else 0)
    q = bias + 0.45 * (rba.attraction - 40) / 60 + 0.2 * rba.affection / 100 + (c.aptitudes.get("charisma", 50) - 50) / 250 + rng.gauss(0, 0.2)
    from .worldgen import orientation_ok
    if not orientation_ok(o, c):
        q = min(q, -0.1)  # they're just not into that
    tier = "great" if q >= 0.4 else "good" if q >= 0.0 else "bad"
    lines = D()["romance"].get(kind, {}).get(tier) or []
    if lines:
        say(lines[_h(w.day, cid, kind) % len(lines)].replace("{them_first}", o.first).replace("{host_first}", ctx.get("host_first", "the")))
    if tier == "bad":
        fx.mood(c.id, -3, st["event"])
        fx.rel(cid, c.id, "attraction", -2, st["event"])
        return
    up = 8 if tier == "great" else 4
    for a, b in ((c.id, cid), (cid, c.id)):
        fx.rel(a, b, "attraction", up, st["event"])
        fx.rel(a, b, "affection", up * 0.75, st["event"])
    fx.mood(c.id, 8 if tier == "great" else 4, st["event"])
    if tier == "great":
        st["kissed"] = cid
        st["did"].append(f"kissed {o.first}")
        for a, b in ((c.id, cid), (cid, c.id)):
            fx.memory(a, "kiss", [b], 0.8, 70, f"Kissed {w.chars[b].name} at {st['event']}")
        seen = [x for x in st["present"] if x != cid][:6]
        make_rumor(sim, c.id, "kiss", f"{c.name} and {o.name} kissed at {st['event']}", True, 0.05, 0.75, None, seen, ev.get("id"), involves=[c.id, cid])
        if not together and w.rules["romance.enabled"] and not o.flags.get("partner") and rab.attraction >= 45:
            start_dating(sim, c.id, cid, ev, fx)
            say(f"By the end of the night, it's official: you and {o.first} are together.")


def _secret(sim, c, st, mode, fx, ev, rng, say):
    from .social import make_rumor
    w = sim.w
    x, y = st["cast"].get("secret_x"), st["cast"].get("secret_y")
    if not x or x not in w.chars or y not in w.chars:
        return
    if y == c.id:
        fx.rel(c.id, x, "perceived", 25, "found out they like you")  # now you know
    if mode == "spread":
        make_rumor(sim, x, "crush", f"{w.chars[x].name} has a thing for {w.chars[y].name}", True, -0.05, 0.7, c.id,
                   [c.id, st["cast"].get("friend")] if st["cast"].get("friend") else [c.id], ev.get("id"), involves=[x, y])
        fx.rel(x, c.id, "trust", -4, "spread their secret")
        say(f"{st['cast'].get('friend') and w.chars[st['cast']['friend']].first or 'Your friend'} gasps. By Monday, half the school will know.")
    elif mode == "dig":
        others = [o for o, r in w.out.get(x, {}).items() if r.crush and o != y and o in w.chars][:1]
        say(f"\"Only me and like three people. And apparently {w.chars[x].first} told {w.chars[others[0]].first} too.\""
            if others else "\"Nobody else. Yet.\" You both know that won't last.")
    else:
        say("You zip your lips. You're the vault. It feels kind of good.")


def _jealous(sim, c, st, mode, fx, rng, say):
    w = sim.w
    p, o = st["cast"].get("partner"), st["cast"].get("other")
    if not p or p not in w.chars:
        return
    pf = w.chars[p].first
    att = w.rels.get((p, o)).attraction if o and w.rels.get((p, o)) else 0
    if mode == "join":
        fx.rel(p, c.id, "affection", 2, st["event"])
        say(f"You slide in next to {pf}. They put an arm around you without missing a beat.")
    elif mode == "trust":
        if att >= 50 and rng.random() < 0.5:
            fx.rel(c.id, p, "trust", -8, st["event"])
            fx.mood(c.id, -6, st["event"])
            say(f"Later you hear {pf} and {w.chars[o].first} were 'just talking' in the backyard for an hour. Everyone else heard too.")
            st["did"].append(f"heard about {pf} and {w.chars[o].first}")
        else:
            fx.rel(p, c.id, "trust", 5, st["event"])
            fx.rel(p, c.id, "affection", 3, st["event"])
            say(f"{pf} finds you later. \"Thanks for not being weird about that.\"")
    else:
        if att >= 50:
            fx.rel(p, c.id, "trust", -3, st["event"])
            fx.rel(c.id, p, "trust", -5, st["event"])
            say(f"{pf} gets defensive fast. Too fast. The rest of the night is quiet between you.")
        else:
            fx.rel(p, c.id, "affection", -4, st["event"])
            say(f"\"Seriously? We were talking about chem homework.\" {pf} is annoyed, and kind of has a point.")


def _end(sim, c, st, fx, ev, render):
    w = sim.w
    did = [d for d in st["did"] if d]
    if did:
        lst = ", ".join(did[:-1]) + (", and " if len(did) > 2 else " and ") + did[-1] if len(did) > 1 else did[0]
        ev["data"].setdefault("say", []).append(D()["recap"].replace("{list}", lst))
    withs = [x for x in (st["cast"].get("date"), st["kissed"], st["cast"].get("friend")) if x and x in w.chars][:3]
    fx.memory(c.id, "night", withs, 0.7 if st["kissed"] else 0.45, 55 if st["kissed"] else 40, f"{st['event']}: " + (", ".join(did[:3]) or "a long night"))
    fx.need(c.id, "fun", 6, st["event"])
    fx.flag(c.id, "late_night", w.day, st["event"])
    w.meta.pop("night", None)


# ------------------------------------------------------------------------------------------------ the weekend calendar

def dawn(sim):
    """Most Fridays and Saturdays somebody has people over. If you're friends with the host, or a friend of yours is
    going, you hear about it that morning, and "Go to Mike's party" is one of your choices tonight."""
    from . import calendar as calm
    w = sim.w
    me = w.chars.get(w.meta.get("protagonist") or "")
    if not me or me.status != "active" or me.role != "student":
        return
    wd = calm.weekday(w.day)
    if wd not in (4, 5) or any(p["day"] == w.day for p in w.parties.values()):
        return
    rng = random.Random(_h(w.seed, w.day, "weekend-party"))
    if rng.random() > (0.4 if wd == 4 else 0.6):
        return
    R = w.rules
    recent = w.meta.setdefault("party_hosts", {})
    pool = [c for c in w.chars.values() if c.role == "student" and c.status == "active" and c.id != me.id and c.location == me.location
            and c.school == me.school and c.money >= 15 and c.flags.get("grounded_until", -1) < w.day
            and w.day - recent.get(c.id, -99) > 21 and (c.traits.get("sociability", 50) >= 50 or c.popularity >= 55)]
    if not pool:
        return
    pool.sort(key=lambda c: c.id)
    weights = [max(1.0, c.popularity + c.traits.get("sociability", 50) - 60) for c in pool]
    x = rng.random() * sum(weights)
    host = pool[-1]
    for c, wt in zip(pool, weights):
        x -= wt
        if x <= 0:
            host = c
            break
    friends = sorted((o for o, r in w.out.get(host.id, {}).items() if r.affection >= R["rel.friend_threshold"] - 8 and o in w.chars
                      and w.chars[o].role == "student" and w.chars[o].status == "active"), key=lambda o: (-w.rels[(host.id, o)].affection, o))
    popular = sorted((o for o, r in w.out.get(host.id, {}).items() if r.familiarity >= 20 and o in w.chars and w.chars[o].role == "student"
                      and w.chars[o].popularity >= 60 and o not in friends), key=lambda o: (-w.chars[o].popularity, o))
    invited = (friends[:12] + popular[:6])[:16]
    key = f"party:{host.id}:{w.day}"
    w.parties[key] = {"key": key, "day": w.day, "host": host.id, "invited": invited, "slot": "evening"}
    recent[host.id] = w.day
    ev = sim.new_event("throw_party", "planned", [host.id], [], 14, {"invited": invited, "party": key})
    ev["involved"] = invited
    ev["text"] = f"{host.name} is having people over tonight."
    fx = Effects(w, ev)
    fx.money(host.id, -15, "party supplies")
    sim.finish(ev, fx)
    if "phone" not in w.meta:
        return
    from . import messages
    mine = [o for o in invited if w.rels.get((me.id, o)) and w.rels[(me.id, o)].affection >= R["rel.friend_threshold"]]
    if me.id in invited:
        messages.later(sim, host.id, "scene", delay_phases=1, text=["people coming over tonight. you in?", "party at mine tonight. bring whoever",
                                                                    "my parents are gone this weekend. tonight. you're coming"][_h(w.day, host.id) % 3])
    elif mine:
        messages.later(sim, mine[0], "scene", delay_phases=1, text=[f"{host.first}'s having people over tonight. you coming?",
                                                                    f"you going to {host.first}'s tonight??", f"{host.first}'s party tonight. pull up"][_h(w.day, mine[0]) % 3])
