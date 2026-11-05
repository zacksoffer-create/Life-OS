"""Action resolvers: what happens when a chosen action is carried out.

Every resolver follows the same contract: evaluate circumstances, draw from the actor's
resolution stream for uncertainty, record each factor in ev['calc'], apply state changes
through Effects (which logs them), create memories and rumors, and schedule any delayed
consequences. Text is rendered afterwards from the event's structured outcome.
"""
from __future__ import annotations

from . import social
from .rng import clamp, sigmoid
from .social import grudge_score, is_friend, make_rumor, witnesses
from .worldgen import orientation_ok

RESOLVERS = {}

FAKE_RUMORS = [
    "{b} cheated on the last chem test", "{b} talks about their friends behind their backs",
    "{b} only hangs out with people who are useful to them", "{b} got caught lying to a teacher",
    "{b} has a fake account to stalk people", "{b} said something awful about the freshmen",
]


def resolver(name):
    def deco(fn):
        RESOLVERS[name] = fn
        return fn
    return deco


def _calc(ev, step, **kw):
    if ev.get("calc") is not None:
        d = {"step": step}
        d.update(kw)
        ev["calc"].append(d)


def _round_terms(terms):
    return [[k, round(v, 3)] for k, v in terms]


# --- solo activities ---------------------------------------------------------

@resolver("solo")
def r_solo(sim, c, cand, ev, fx, rng, ctx):
    w, R = sim.w, sim.w.rules
    a = cand.a
    p = a["params"]
    aid = a["id"]
    skill = p.get("skill")
    if skill == "@target":
        skill = cand.target
    elif skill == "@hobby_skill":
        skill = sim.cat.hobbies[cand.target]["skill"] if cand.target in sim.cat.hobbies else None
    energy_f = 0.5 + c.needs["energy"] / 200
    if aid in ("study", "study_at_lunch", "practice_skill"):
        terms = [("baseline", 0.6), ("discipline", (c.traits["discipline"] - 50) / 100 * R["dev.discipline_focus"]),
                 ("energy", 0), ("stress", -max(0.0, c.needs["stress"] - 70) / 100), ("luck", rng.gauss(0, 0.15))]
        focus = (terms[0][1] + terms[1][1]) * energy_f + terms[3][1] + terms[4][1]
        terms[2] = ("energy multiplier", energy_f)
    else:
        iv = c.interests.get(cand.target, 50) if cand.target else 50
        terms = [("baseline", 0.5), ("enjoys it", (iv - 50) / 100), ("stress", -max(0.0, c.needs["stress"] - 75) / 100),
                 ("luck", rng.gauss(0, 0.15))]
        focus = sum(t[1] for t in terms)
    outcome = "focused" if focus >= 0.45 else "distracted"
    _calc(ev, "session quality", terms=_round_terms(terms), total=round(focus, 3), outcome=outcome,
          rule="focused if quality >= 0.45")
    if p.get("enjoy_trait") == "curiosity":
        enjoy = c.traits["curiosity"] / 100 * 0.6 + 0.2
    elif p.get("enjoy_trait") == "interest":
        enjoy = c.interests.get(cand.target if aid == "hobby" else skill or "", 40) / 100
    else:
        enjoy = 0.5
    if aid == "practice_skill" and skill:
        c.counters["skillpractice:" + skill] = c.counters.get("skillpractice:" + skill, 0) + 1
    if skill:
        gain = skill_gain(sim, c, skill, p.get("gain", 1.0) * max(0.2, focus), ev)
        fx.skill(c.id, skill, gain, f"{a['label'].lower()} ({outcome})")
    if p.get("study_points"):
        c.study_ema += p["study_points"] * max(0.2, focus)
    for need in ("energy", "fun", "stress", "social"):
        v = p.get(need, 0)
        if need == "fun" and v > 0:
            v *= 0.5 + enjoy
        if v:
            fx.need(c.id, need, v, a["label"].lower())
    fx.mood(c.id, (enjoy - 0.4) * 4 + (focus - 0.45) * 2, a["label"].lower())
    if aid in ("practice_skill", "hobby") and cand.target:
        key = cand.target
        fx.interest(c.id, key, R["dev.interest_drift"] * (enjoy - 0.45) * 1.2 + (focus - 0.45), "enjoyment")
    sim.expect(c.id, aid, clamp((focus - 0.45) + (enjoy - 0.4), -1, 1))
    ev["outcome"] = outcome
    ev["data"].update({"skill": skill, "focus": round(focus, 2)})
    if aid == "hobby" and cand.target in sim.cat.hobbies:
        ev["data"]["verb"] = sim.cat.hobbies[cand.target]["verb"]


def skill_gain(sim, c, skill, base, ev=None) -> float:
    R = sim.w.rules
    apt_key = sim.cat.skills[skill]["aptitude"]
    apt = c.aptitudes.get(apt_key, 50)
    tw = R["dev.talent_cap_weight"]
    cap = (1 - tw) * 100 + tw * apt
    cur = c.skills.get(skill, 0)
    apt_f = 0.4 + apt / 100 * 1.2
    curve = R["dev.sport_ceiling_curve"] if sim.cat.skills[skill].get("kind") == "sport" else 0.8
    ceil_f = max(0.03, (cap - cur) / cap) ** curve if cur < cap else 0.03
    g = base * 0.55 * R["dev.skill_rate"] * apt_f * ceil_f
    if ev is not None:
        _calc(ev, f"{skill} skill gain", terms=[["base x session quality", round(base, 3)], ["skill rate", R["dev.skill_rate"]],
                                                   [f"aptitude ({apt_key} {apt:.0f})", round(apt_f, 3)],
                                                   [f"room under ceiling {cap:.0f}", round(ceil_f, 3)]],
              total=round(g, 3), rule="gain = base x 0.55 x rate x aptitude factor x ceiling factor")
    return g


@resolver("pet_time")
def r_pet(sim, c, cand, ev, fx, rng, ctx):
    h = sim.w.households.get(c.household_id)
    pet = h["pet"]
    p = cand.a["params"]
    q = 0.5 + (c.traits["empathy"] - 50) / 200 + rng.gauss(0, 0.15)
    ev["outcome"] = "focused" if q >= 0.4 else "distracted"
    _calc(ev, "time with pet", terms=[["baseline", 0.5], ["empathy", round((c.traits["empathy"] - 50) / 200, 3)]], total=round(q, 3))
    for need in ("energy", "fun", "stress", "social"):
        if p.get(need):
            fx.need(c.id, need, p[need] * (0.6 + q * 0.8), f"time with {pet['name']}")
    fx.mood(c.id, 3 * q, f"time with {pet['name']}")
    sim.expect(c.id, "pet_time", clamp(q - 0.3, -1, 1))
    ev["data"]["pet"] = pet["name"]


@resolver("pet_activity")
def r_pet_activity(sim, c, cand, ev, fx, rng, ctx):
    from .pets import timed_resolve
    timed_resolve(sim, c, cand, ev, fx, rng, ctx)


# --- two-person interactions ----------------------------------------------------

def pick_place(sim, a_id, b_id, rng):
    w = sim.w
    budget = min(w.chars[a_id].money, w.chars[b_id].money)
    opts = [p for p in sim.cat.world["places"] if p["cost"] <= budget]
    opts.sort(key=lambda p: p["id"])
    return opts[int(rng.random() * len(opts))] if opts else sim.cat.places["park"]


@resolver("interact")
def r_interact(sim, c, cand, ev, fx, rng, ctx):
    w = sim.w
    a = cand.a
    p = a["params"]
    b = cand.target
    kind = p["kind"]
    ev["data"]["kind"] = kind
    ev["type"] = f"interact.{kind}"
    invite = cand.extra.get("invite") if isinstance(cand.extra, dict) else None
    if invite:
        inv = next((i for i in w.meta.get("inbox", []) if i["id"] == invite), None)
        if inv:
            inv["status"] = "accepted"
        if b in sim.slot.engaged:
            ev["outcome"] = "busy"
            ev["type"] = f"interact.{kind}"
            fx.mood(c.id, -2, "they made other plans")
            return
        plan = sim.slot.planned.get(b)
        if b not in sim.slot.done and plan:
            sim.cancel_plan(b, f"{c.short} said yes to their invite")
        sim.engage(b, c.id)
    elif p.get("needs_acceptance"):
        resp = sim.respond(b, c.id, cand, rng, ev)
        if resp in ("busy", "declined") and kind == "hang_out" and c.id == w.meta.get("protagonist"):
            alt = _backup_friend(sim, c, b, cand, rng, ev)  # your pick was busy: you text someone else instead of wasting the afternoon
            if alt:
                ev["data"]["swap"] = (f"{w.chars[b].first} {'already had plans' if resp == 'busy' else 'passed'}, "
                                      f"so you hung out with {w.chars[alt].first} instead.")
                b, resp = alt, "accepted"
                ev["targets"] = [alt]
        if resp == "invited":
            ev["outcome"] = "invited"
            ev["importance"] = 16
            return
        if resp != "accepted":
            ev["outcome"] = resp
            fx.mood(c.id, -3 if resp == "declined" else -1, f"{w.chars[b].short} said no")
            if resp == "declined":
                fx.rel(c.id, b, "perceived", -6, "invite declined")
                fx.rel(c.id, b, "affection", -1.5, "invite declined")
                sim.expect(c.id, a["id"], -0.35)
            fx.touch(c.id, b, f"{kind}_declined", -0.2)
            ev["importance"] = max(4, a["importance"] - 2)
            return
        sim.engage(b, c.id)
    sim.engage(c.id, b)
    act = None
    if kind == "hang_out" and c.id == w.meta.get("protagonist"):
        from . import squad
        act = squad.pending_act(sim)  # the group thing you picked: the boys on the game, the park, a food run
    if p.get("place"):
        from . import squad
        place = squad.place_for(sim, act, b) if act else pick_place(sim, c.id, b, rng)
        ev["data"]["place"] = place["name"]
        if place["cost"]:
            fx.money(c.id, -place["cost"], place["name"])
            fx.money(b, -place["cost"], place["name"])
    calc = ev["calc"] if ev.get("calc") is not None else None
    res = social.interact(sim, fx, ev, c.id, b, p, rng, calc)
    ev["outcome"] = res["outcome"]
    ev["data"]["quality"] = round(res["quality"], 3)
    sim.expect(c.id, a["id"], clamp(res["qa"], -1, 1))
    if res["outcome"] == "great":
        ev["importance"] = a["importance"] + 6
    crew = []
    if kind == "hang_out" and c.id == w.meta.get("protagonist"):
        crew = _bring_crew(sim, c, b, p, ev, fx, rng)
        if act:
            from . import squad
            squad.after(sim, c, b, crew, act, ev, fx, rng)
    if kind in ("flirt", "date", "hang_out") and c.id == w.meta.get("protagonist"):
        from .chat import why_interact
        why = why_interact(res["terms"], True)  # say why it went the way it did, in words
        if why:
            ev["data"]["why"] = why
        # a hangout you picked plays out: a quick scene with one choice
        if kind in ("date", "hang_out") and res["outcome"] != "bad" and sim.slot.planned.get(c.id, {}).get("player"):
            from . import hangouts
            hangouts.maybe_scene(sim, c.id, b, hangouts.kind_for(sim, c.id, b, kind, crew), crew, ev["data"].get("place"), act=act)
    if kind == "flirt":
        _flirt_side_effects(sim, c, b, res, ev, fx, rng, ctx)
    if kind == "support":
        fx.rep(c.id, "kind", 2.5, "helped a friend")


def _backup_friend(sim, c, b, cand, rng, ev):
    """Someone else you're close with who's around and says yes."""
    w = sim.w
    crew = (w.meta.get("control", {}).get("crew") or {}).get("ids", [])
    cands = []
    for o, r in w.out.get(c.id, {}).items():
        x = w.chars.get(o)
        if (o == b or not x or x.status != "active" or x.role not in ("student", "alumni") or x.location != c.location
                or r.affection < 25 or o in sim.slot.engaged or o in sim.slot.done or o in sim.siblings(c.id)
                or sim.committed(o, sim.slot.slot)):
            continue
        cands.append((0 if o in crew else 1, -r.affection, o))  # the crew you asked steps up first
    for _, _, o in sorted(cands)[:3]:
        if sim.respond(o, c.id, cand, rng, ev) == "accepted":
            return o
    return None


def _bring_crew(sim, c, b, p, ev, fx, rng):
    """You asked the crew: the friends you picked come too (if they're free), and everyone gets closer."""
    from .institutions import ambient
    w = sim.w
    ask = w.meta.get("control", {}).get("crew") or {}
    if ask.get("day") != w.day or ask.get("slot") != sim.slot.slot:
        return []
    w.meta["control"].pop("crew", None)
    came = []
    for o in ask.get("ids", []):
        x = w.chars.get(o)
        if o in (b, c.id) or not x or x.status != "active" or x.location != c.location or o in sim.slot.engaged \
                or sim.committed(o, sim.slot.slot):  # they're at practice
            continue
        if o not in sim.slot.done and sim.slot.planned.get(o):
            sim.cancel_plan(o, f"went with {c.short} and the crew")
        sim.slot.done.add(o)
        sim.engage(o, c.id)
        social.interact(sim, fx, ev, c.id, o, dict(p, affection=p.get("affection", 5) * 0.6, familiarity=p.get("familiarity", 4) * 0.7,
                                                   place=False), rng, None)
        came.append(o)
    for i, x in enumerate([b] + came):
        for y in came[i:]:
            if x != y:
                ambient(sim, fx, x, y, 0.4, "hung out with the crew")
    if came:
        ev["involved"] = list(dict.fromkeys((ev.get("involved") or []) + came))
        ev["data"]["crew"] = came
        firsts = [w.chars[x].first for x in came]
        ev["data"]["crew_line"] = (" and ".join(firsts) if len(firsts) <= 2 else ", ".join(firsts[:-1]) + " and " + firsts[-1]) + \
            (" came too." if len(firsts) > 1 else " came too.")
    return came


def _flirt_side_effects(sim, c, b, res, ev, fx, rng, ctx):
    w = sim.w
    if ctx["slot"] != "lunch":
        return
    seen = witnesses(sim, rng, {c.id, b}, 2)
    if not seen:
        return
    who = c.flags.get("partner") or w.chars[b].flags.get("partner")
    if who or res["outcome"] == "great":
        about = c.id
        phrase = f"{c.name} was flirting with {w.chars[b].name}"
        make_rumor(sim, about, "flirting", phrase, True, -0.15 if who else 0.0, 0.55 if who else 0.35, None,
                   seen, ev.get("id"), involves=[c.id, b])


# --- romance -----------------------------------------------------------------

@resolver("ask_out")
def r_ask_out(sim, c, cand, ev, fx, rng, ctx):
    w, R = sim.w, sim.w.rules
    b = cand.target
    B = w.chars[b]
    dance = cand.a["params"].get("context") == "dance"
    from .moments import control
    if b == w.meta.get("protagonist") and control(w).get("ask_romance"):
        d = ctx.get("dance") if dance else None
        ev["type"] = "ask_to_dance" if dance else "ask_out"
        ev["outcome"] = "pending"
        ev["targets"] = [b]
        if d:
            ev["data"]["event"] = d["name"]
        sim.moment_trigger("asked_to_dance" if dance else "asked_out", b,
                           {"other": c.id, "event": d["name"] if d else "", "dance_key": d["key"] if d else None, "extra": ""})
        return
    rba = w.ensure_rel(b, c.id, w.day)
    others = [r for oid, r in w.out.get(b, {}).items() if r.crush and oid != c.id]
    terms = [
        (f"{B.short}'s attraction to {c.short}", (rba.attraction - 60) / 10 if orientation_ok(B, c) else -8.0),
        (f"{B.short}'s affection for {c.short}", (rba.affection - 30) / 40),
        ("timing and nerves", -0.5),
        ("status gap x their approval motive", (c.popularity - B.popularity) / 60 * B.motives["approval"] / 100),
        (f"{B.short}'s mood", (B.mood - 50) / 50 * 0.5),
        ("already taken", -3.5 * (0.5 + B.traits["loyalty"] / 100) if B.flags.get("partner") and B.flags["partner"] != c.id else 0.0),
        ("likes someone else", -0.8 if others else 0.0),
        ("luck", rng.gauss(0, 0.5)),
    ]
    told = B.flags.get("told_to_ask") or {}
    if not dance and told.get("by") == c.id and w.day - told.get("day", -99) <= 7:
        terms.append(("they told you to ask them in person", 3.0))  # they meant it
        B.flags.pop("told_to_ask", None)
    if dance:
        terms.append(("just a dance (friends can say yes)", (rba.affection - 30) / 25))
        if B.flags.get("partner") == c.id:
            terms.append(("asked by their partner", 4.0))
    x = sum(t[1] for t in terms)
    pr = sigmoid(x)
    roll = rng.random()
    yes = roll < pr
    _calc(ev, f"{B.short}'s answer", terms=_round_terms(terms), total=round(x, 3), p=round(pr, 3), roll=round(roll, 4),
          outcome="yes" if yes else "no", rule="P(yes) = sigmoid(total)")
    ev["targets"] = [b]
    if dance:
        d = ctx.get("dance")
        ev["type"] = "ask_to_dance"
        ev["data"]["event"] = d["name"]
        if yes:
            dd = w.dance_dates.setdefault(d["key"], {})
            dd[c.id] = b
            dd[b] = c.id
            ev["outcome"] = "yes"
            fx.mood(c.id, 8, "dance date")
            fx.mood(b, 5, "asked to the dance")
            fx.rel(b, c.id, "affection", 4, "asked to the dance")
            fx.rel(b, c.id, "attraction", 3 if orientation_ok(B, c) else 0, "asked to the dance")
            fx.memory(c.id, "dance_yes", [b], 0.6, 45, f"{B.name} said yes to {d['name']}")
        else:
            ev["outcome"] = "no"
            _rejected(sim, c, b, ev, fx, rng, ctx, dance=True)
        sim.expect(c.id, "ask_to_dance", 0.6 if yes else -0.5)
        return
    ev["type"] = "ask_out"
    if c.id == w.meta.get("protagonist"):
        from .chat import why_ask_out
        ev["data"]["why"] = why_ask_out(terms, yes)
    if yes:
        ev["outcome"] = "yes"
        start_dating(sim, c.id, b, ev, fx)
    else:
        harsh = ctx["slot"] == "lunch" and B.traits["empathy"] < 35 and B.popularity > c.popularity + 15
        ev["outcome"] = "no_harsh" if harsh else "no"
        _rejected(sim, c, b, ev, fx, rng, ctx, harsh=harsh)
    sim.expect(c.id, "ask_out", 0.7 if yes else -0.6)


def start_dating(sim, a, b, ev, fx):
    w = sim.w
    A, B = w.chars[a], w.chars[b]
    for x, y in ((a, b), (b, a)):
        old = w.chars[x].flags.get("partner")
        if old and old != y:
            end_relationship(sim, x, old, ev, fx, reason=f"started dating {w.chars[y].short}")
    fx.add_bond(a, b, "partner", "said yes")
    fx.flag(a, "partner", b, "started dating")
    fx.flag(b, "partner", a, "started dating")
    for x, y in ((a, b), (b, a)):
        fx.rel(x, y, "affection", 8, "started dating")
        fx.rel(x, y, "trust", 6, "started dating")
        fx.mood(x, 10, "started dating")
        fx.memory(x, "started_dating", [y], 0.85, 75, f"Started dating {w.chars[y].name}")
    for g in A.goals + B.goals:
        if g["type"] == "romance" and g["status"] == "active" and g.get("target") in (a, b):
            g["status"] = "achieved"
            g["closed"] = w.day
    friends = [o for o in sorted(w.out.get(a, {})) if is_friend(w.rels.get((o, a)), w.rules)][:6] + \
              [o for o in sorted(w.out.get(b, {})) if is_friend(w.rels.get((o, b)), w.rules)][:6]
    make_rumor(sim, a, "dating", f"{A.name} and {B.name} are together now", True, 0.1, 0.6, None,
               sorted(set(friends) - {a, b}), ev.get("id"), involves=[a, b])
    w.rels[(a, b)].milestones.append([w.day, "dating", ev.get("id")])
    w.rels[(b, a)].milestones.append([w.day, "dating", ev.get("id")])
    sim.milestone_event("dating", a, b, ev, 48)


def _rejected(sim, c, b, ev, fx, rng, ctx, harsh=False, dance=False):
    w, R = sim.w, sim.w.rules
    B = w.chars[b]
    sting = 1.4 if harsh else 1.0
    fx.mood(c.id, -8 * sting, "turned down")
    fx.need(c.id, "stress", 6 * sting, "turned down")
    sim.confidence(c.id, -1.5 * sting, fx, "turned down")
    fx.memory(c.id, "rejected", [b], -0.7 * sting, 60 * sting, f"Asked {B.name} out{' to the dance' if dance else ''} and got turned down")
    fx.rel(c.id, b, "perceived", -15, "they said no")
    fx.rel(c.id, b, "attraction", -4 - rng.random() * 8, "they said no")
    fx.rel(b, c.id, "familiarity", 3, "was asked out")
    fx.touch(c.id, b, "rejected", -0.5)
    if ctx["slot"] == "lunch" or harsh:
        seen = witnesses(sim, rng, {c.id, b}, 3)
        make_rumor(sim, c.id, "rejected", f"{c.name} asked {B.name} out and got shut down", True, -0.25,
                   0.7 if harsh else 0.5, None, seen + [b], ev.get("id"), involves=[c.id, b])
        if harsh:
            fx.rep(c.id, "embarrassed", 8, "public rejection")
            fx.rep(b, "mean", 4, "laughed at someone")


def end_relationship(sim, a, b, ev, fx, reason="broke up"):
    w = sim.w
    if reason.startswith("started dating"):
        # a is leaving b for someone new: b gets a breakup of their own
        e2 = sim.new_event("break_up", "left_for", [a], [b], 40, {"label": reason})
        e2["causes"] = [ev["id"]] if ev and ev.get("id") else []
        e2["text"] = f"{w.chars[a].short} left {w.chars[b].short} for someone new ({reason.replace('started dating ', '')})."
        f2 = type(fx)(w, e2)
        f2.rel(b, a, "affection", -25, "left for someone else")
        f2.rel(b, a, "trust", -25, "left for someone else")
        f2.mood(b, -14, "left for someone else")
        f2.memory(b, "broke_up", [a], -0.85, 80, f"{w.chars[a].name} left them for someone else")
        f2.drop_bond(a, b, "partner", reason)
        f2.add_bond(a, b, "ex", reason)
        if w.chars[b].flags.get("partner") == a:
            f2.flag(b, "partner", None, reason)
        sim.finish(e2, f2)
    fx.drop_bond(a, b, "partner", reason)
    fx.add_bond(a, b, "ex", reason)
    if w.chars[a].flags.get("partner") == b:
        fx.flag(a, "partner", None, reason)
    if w.chars[b].flags.get("partner") == a:
        fx.flag(b, "partner", None, reason)


@resolver("break_up")
def r_break_up(sim, c, cand, ev, fx, rng, ctx):
    w, R = sim.w, sim.w.rules
    b = cand.target
    B = w.chars[b]
    sat_b = social.satisfaction(w, b, c.id)
    mutual = sat_b < R["romance.breakup_threshold"] + 10
    ev["outcome"] = "mutual" if mutual else "messy"
    _calc(ev, f"how {B.short} takes it", terms=[[f"{B.short}'s satisfaction", round(sat_b, 1)],
                                                ["threshold + 10", R["romance.breakup_threshold"] + 10]],
          outcome=ev["outcome"], rule="mutual if their satisfaction is below threshold + 10")
    end_relationship(sim, c.id, b, ev, fx)
    hurt = 0.4 if mutual else 1.0
    fx.rel(b, c.id, "affection", -22 * hurt, "got dumped")
    fx.rel(b, c.id, "trust", -15 * hurt, "got dumped")
    fx.mood(b, -14 * hurt, "breakup")
    fx.need(b, "stress", 10 * hurt, "breakup")
    fx.mood(c.id, -3 if mutual else 1, "breakup")
    fx.rel(c.id, b, "attraction", -8, "broke up")
    fx.memory(b, "broke_up", [c.id], -0.8 * hurt, 75 * hurt + 10, f"{c.name} broke up with them")
    sim.moment_trigger("heartbreak", b, {"other": c.id})
    fx.memory(c.id, "broke_up", [b], -0.3, 50, f"Broke up with {B.name}")
    friends = sorted(o for o in w.out.get(b, {}) if is_friend(w.rels.get((o, b)), R))[:8]
    make_rumor(sim, b, "breakup", f"{c.name} dumped {B.name}", True, -0.1, 0.65, None,
               friends, ev.get("id"), involves=[c.id, b])
    ev["importance"] = 42 if not mutual else 34


# --- conflict ------------------------------------------------------------------

@resolver("confront")
def r_confront(sim, c, cand, ev, fx, rng, ctx):
    w, R = sim.w, sim.w.rules
    b = cand.target
    B = w.chars[b]
    gba = grudge_score(w, w.rels.get((b, c.id)), w.day)
    terms = [
        ("tempers (avg volatility)", (c.traits["volatility"] + B.traits["volatility"] - 100) / 100 + 0.25),
        ("stress (avg)", (c.needs["stress"] + B.needs["stress"]) / 200 - 0.4),
        ("empathy (avg)", -(c.traits["empathy"] + B.traits["empathy"]) / 200 + 0.3),
        (f"{B.short}'s own grudge", gba / 220),
        ("luck", rng.gauss(0, 0.3)),
    ]
    esc = sum(t[1] for t in terms)
    out = "cleared_air" if esc < 0.2 else ("argument" if esc < 0.85 else "falling_out")
    ev["outcome"] = out
    ev["data"]["place"] = "in the hallway" if ctx["slot"] == "lunch" else "in the parking lot"
    _calc(ev, "escalation", terms=_round_terms(terms), total=round(esc, 3), outcome=out,
          rule="cleared the air < 0.2 <= argument < 0.85 <= falling out")
    for x, y in ((c.id, b), (b, c.id)):
        if out == "cleared_air":
            fx.rel(x, y, "rivalry", -10, "cleared the air")
            fx.rel(x, y, "affection", 7, "cleared the air")
            fx.rel(x, y, "trust", 4, "cleared the air")
            fx.need(x, "stress", -5, "cleared the air")
        elif out == "argument":
            fx.rel(x, y, "affection", -9, "argument")
            fx.rel(x, y, "rivalry", 7, "argument")
            fx.need(x, "stress", 8, "argument")
            fx.mood(x, -5, "argument")
            fx.memory(x, "argument", [y], -0.5, 50, f"Argued with {w.chars[y].name}")
        else:
            fx.rel(x, y, "affection", -20, "falling out")
            fx.rel(x, y, "trust", -18, "falling out")
            fx.rel(x, y, "rivalry", 14, "falling out")
            fx.need(x, "stress", 12, "falling out")
            fx.mood(x, -9, "falling out")
            fx.memory(x, "falling_out", [y], -0.8, 75, f"Had a blowout with {w.chars[y].name}")
        fx.touch(x, y, "confront", 0.3 if out == "cleared_air" else -0.6)
    if out == "cleared_air":
        fx.memory(c.id, "cleared_air", [b], 0.4, 40, f"Cleared the air with {B.name}")
    if out == "falling_out" or ctx["slot"] == "lunch":
        seen = witnesses(sim, rng, {c.id, b}, 3)
        if out != "cleared_air":
            make_rumor(sim, c.id, "fight", f"{c.name} and {B.name} got into a huge fight", True, -0.1, 0.6, None,
                       seen, ev.get("id"), involves=[c.id, b])
    sim.expect(c.id, "confront", 0.3 if out == "cleared_air" else -0.2 if out == "argument" else -0.5)
    ev["importance"] = {"cleared_air": 22, "argument": 28, "falling_out": 40}[out]


@resolver("apologize")
def r_apologize(sim, c, cand, ev, fx, rng, ctx):
    w = sim.w
    b = cand.target
    B = w.chars[b]
    rba = w.ensure_rel(b, c.id, w.day)
    terms = [
        (f"{B.short}'s empathy", (B.traits["empathy"] - 50) / 50 * 0.8),
        ("how close they used to be", rba.peak_affection / 100 * 1.2),
        ("good memories together", social.memory_pull(w, b, c.id, w.day)),
        (f"{B.short}'s grudge", -grudge_score(w, rba, w.day) / 50),
        (f"{c.short}'s charm", (c.aptitudes["charisma"] - 50) / 100),
        ("luck", rng.gauss(0, 0.5)),
    ]
    x = sum(t[1] for t in terms)
    out = "forgiven" if x > 0.5 else "partial" if x > 0 else "rebuffed"
    ev["outcome"] = out
    _calc(ev, "forgiveness", terms=_round_terms(terms), total=round(x, 3), outcome=out,
          rule="forgiven > 0.5, partial > 0, else rebuffed")
    if out == "forgiven":
        for x_, y in ((c.id, b), (b, c.id)):
            fx.rel(x_, y, "affection", 15, "made up")
            fx.rel(x_, y, "trust", 8, "made up")
            fx.rel(x_, y, "rivalry", -10, "made up")
            fx.need(x_, "stress", -8, "made up")
            fx.mood(x_, 6, "made up")
            fx.memory(x_, "reconciled", [y], 0.65, 55, f"Made up with {w.chars[y].name}")
        for g in c.goals:
            if g["type"] == "make_amends" and g.get("target") == b and g["status"] == "active":
                g["status"] = "achieved"
                g["closed"] = w.day
    elif out == "partial":
        fx.rel(b, c.id, "affection", 5, "apology")
        fx.rel(c.id, b, "affection", 3, "apology")
        fx.rel(b, c.id, "trust", 2, "apology")
    else:
        fx.mood(c.id, -5, "apology rejected")
        fx.rel(c.id, b, "affection", -4, "apology rejected")
        fx.memory(c.id, "rejected_apology", [b], -0.4, 40, f"{B.name} rejected their apology")
    for x_, y in ((c.id, b), (b, c.id)):
        fx.touch(x_, y, "apology", 0.5 if out == "forgiven" else 0.0 if out == "partial" else -0.3)
    sim.expect(c.id, "apologize", 0.6 if out == "forgiven" else 0.0 if out == "partial" else -0.5)
    ev["importance"] = {"forgiven": 32, "partial": 18, "rebuffed": 22}[out]


# --- information ---------------------------------------------------------------

def hear_rumor(sim, listener: str, teller: str, rid: str, ev, fx, rng, base_p: float | None = None) -> str:
    """listener hears rumor rid from teller. Returns 'known', 'believed' or 'doubted'."""
    w, R = sim.w, sim.w.rules
    rum = w.rumors[rid]
    if listener in rum["known_by"]:
        return "known"
    L = w.chars[listener]
    about = rum["about"]
    trust = w.rels[(listener, teller)].trust if (listener, teller) in w.rels else 30
    ra = w.rels.get((listener, about))
    loyal = max(0.0, ra.affection) / 150 if (ra and rum["valence"] < 0) else 0.0
    p = (base_p if base_p is not None else R["social.gossip_spread"]) * (trust / 100 + 0.5) * (1 - loyal) * (0.7 + rum["juice"] * 0.6)
    p = clamp(p, 0.02, 0.97)
    roll = rng.random()
    believed = roll < p
    rum["known_by"][listener] = [w.day, teller, believed]
    rum["spread"] += 1
    _calc(ev, f"does {L.short} believe it?", terms=[["gossip appetite", R["social.gossip_spread"]],
                                                     [f"trust in {w.chars[teller].short}", round(trust, 1)],
                                                     ["loyalty to subject", round(loyal, 3)], ["juiciness", rum["juice"]]],
          p=round(p, 3), roll=round(roll, 4), outcome="believed" if believed else "doubted")
    if believed and rum["valence"] and about in w.chars and about != listener:
        fam = ra.familiarity if ra else 0
        d = rum["valence"] * 12 * R["social.rumor_credibility"] * (1 - fam / 200)
        fx.rel(listener, about, "affection", d, f"heard: {rum['text']}")
        fx.rel(listener, about, "respect", d * 0.7, f"heard: {rum['text']}")
    if R["social.rumor_distortion"] and rng.random() < R["social.rumor_distortion"]:
        rum["juice"] = round(min(1.0, rum["juice"] + 0.1), 3)
        rum["valence"] = round(clamp(rum["valence"] * 1.25, -1, 1), 3)
        rum["exaggerated"] = True
    # a loyal friend of the subject may pass it on to them
    if rum["valence"] < 0 and about in w.chars and about not in rum["known_by"] and ra and \
            ra.affection >= R["rel.close_threshold"] and rng.random() < L.traits["loyalty"] / 100:
        sim.schedule(w.day + 1, "tell_subject", {"rumor": rid, "teller": listener}, ev.get("id"))
    return "believed" if believed else "doubted"


@resolver("gossip")
def r_gossip(sim, c, cand, ev, fx, rng, ctx):
    w = sim.w
    b = cand.target
    rid = cand.extra
    rum = w.rumors[rid]
    ev["data"]["about"] = rum["text"]
    ev["data"]["rumor"] = rid
    ev["involved"] = [rum["about"]] if rum["about"] in w.chars else []
    res = hear_rumor(sim, b, c.id, rid, ev, fx, rng)
    ev["outcome"] = "spread" if res == "believed" else res
    if res != "known":
        B = w.chars[b]
        bond = 2.5 * (1 - B.traits["empathy"] / 120)
        fx.rel(b, c.id, "affection", bond, "shared gossip")
        fx.rel(c.id, b, "affection", 1.5, "shared gossip")
        fx.need(c.id, "fun", 6, "gossip")
        fx.need(c.id, "social", 6, "gossip")
        fx.rep(c.id, "gossip", 2, "spread a rumor")
        if B.traits["empathy"] > 70 and rum["valence"] < 0:
            fx.rel(b, c.id, "respect", -3, "spreads rumors")
    fx.touch(c.id, b, "gossip", 0.2)
    sim.expect(c.id, "gossip", 0.3 if res == "believed" else 0.0)


@resolver("spread_rumor")
def r_spread_rumor(sim, c, cand, ev, fx, rng, ctx):
    w = sim.w
    b = cand.target
    B = w.chars[b]
    phrase = FAKE_RUMORS[int(rng.random() * len(FAKE_RUMORS))].format(b=B.name)
    friends = sorted([o for o, r in w.out.get(c.id, {}).items() if is_friend(r, w.rules) and o != b
                      and w.chars[o].role == "student"], key=lambda o: -w.rels[(c.id, o)].affection)
    rid = make_rumor(sim, b, "fabricated", phrase, False, -0.6, 0.75, c.id, [c.id], ev.get("id"))
    ev["data"]["about"] = phrase
    ev["data"]["rumor"] = rid
    ev["outcome"] = "started"
    ev["targets"] = [b]
    if friends:
        listener = friends[0]
        ev["involved"] = [listener]
        hear_rumor(sim, listener, c.id, rid, ev, fx, rng)
        ev["data"]["listener"] = listener
    if c.traits["empathy"] > 45:
        fx.need(c.id, "stress", (c.traits["empathy"] - 45) / 8, "guilt")
    fx.rep(c.id, "gossip", 4, "started a rumor")
    sim.expect(c.id, "spread_rumor", 0.2)


@resolver("tease")
def r_tease(sim, c, cand, ev, fx, rng, ctx):
    w, R = sim.w, sim.w.rules
    b = cand.target
    B = w.chars[b]
    terms = [(f"{c.short}'s charm", (c.aptitudes["charisma"] - 50) / 50 * 0.5),
             ("status gap", (c.popularity - B.popularity) / 50 * 0.6),
             (f"{c.short}'s confidence", (c.traits["confidence"] - 50) / 100), ("luck", rng.gauss(0, 0.5))]
    x = sum(t[1] for t in terms)
    landed = x > 0
    ev["outcome"] = "landed" if landed else "backfired"
    _calc(ev, "does the joke land?", terms=_round_terms(terms), total=round(x, 3), outcome=ev["outcome"], rule="lands if > 0")
    seen = witnesses(sim, rng, {c.id, b}, 4, prefer=sorted(w.cliques.get(c.flags.get("clique"), {}).get("members", [])))
    ev["involved"] = seen
    if landed:
        fx.mood(b, -10, f"mocked by {c.short}")
        fx.need(b, "stress", 10, f"mocked by {c.short}")
        sim.confidence(b, -2, fx, "humiliated")
        fx.rel(b, c.id, "affection", -15, "humiliated")
        fx.rel(b, c.id, "rivalry", 10, "humiliated")
        fx.memory(b, "humiliated_by", [c.id], -0.75, 65, f"{c.name} humiliated them at lunch")
        for s in seen:
            S = w.chars[s]
            k = (50 - S.traits["empathy"]) / 50
            fx.rel(s, c.id, "respect", R["social.tease_status_gain"] * k * 6, "watched the joke")
            fx.rel(s, c.id, "affection", k * 3, "watched the joke")
            fx.rel(s, b, "respect", -2 * max(0.0, k), "watched the joke")
            if S.traits["empathy"] > 65:
                fx.rel(s, b, "affection", 2, "felt bad for them")
        fx.rep(c.id, "mean", 5, "mocked someone")
        fx.need(c.id, "fun", 8, "landed a joke")
        make_rumor(sim, b, "humiliated", f"{c.name} completely roasted {B.name} at lunch", True, -0.2, 0.55, None,
                   seen, ev.get("id"), involves=[c.id, b])
    else:
        fx.mood(c.id, -5, "joke fell flat")
        for s in seen:
            fx.rel(s, c.id, "respect", -4, "watched a joke fall flat")
            fx.rel(s, b, "affection", 1.5, "sympathy")
        fx.rel(b, c.id, "affection", -6, "tried to mock them")
        fx.rel(b, c.id, "rivalry", 5, "tried to mock them")
    fx.touch(c.id, b, "tease", -0.6)
    fx.touch(b, c.id, "tease", -0.8)
    sim.expect(c.id, "tease", 0.4 if landed else -0.5)


# --- risk ------------------------------------------------------------------------

@resolver("prank")
def r_prank(sim, c, cand, ev, fx, rng, ctx):
    w, R = sim.w, sim.w.rules
    skill = (c.aptitudes["creativity"] + c.aptitudes["charisma"]) / 200 + rng.gauss(0, 0.35)
    pc = clamp(R["inst.catch_chance"] * (1.3 - c.traits["discipline"] / 200) * (1.0 if skill > 0.3 else 1.5), 0, 0.98)
    roll = rng.random()
    caught = roll < pc
    out = "caught" if caught else ("legend" if skill > 0.55 else "dud")
    ev["outcome"] = out
    _calc(ev, "prank", terms=[["craft (creativity+charisma, luck)", round(skill, 3)]], p_caught=round(pc, 3),
          roll=round(roll, 4), outcome=out, rule="caught if roll < catch chance; legend if craft > 0.55")
    if caught:
        fx.mood(c.id, -6, "caught")
        fx.need(c.id, "stress", 10, "caught")
        fx.rep(c.id, "troublemaker", 8, "caught pranking")
        fx.flag(c.id, "detention_until", w.day + 3, "caught pranking")
        sim.schedule(w.day + 1, "parents_find_out", {"char": c.id, "what": "a prank at school"}, ev.get("id"))
        fx.memory(c.id, "caught", [], -0.5, 50, "Got caught pulling a prank")
        ev["importance"] = 30
    else:
        fx.need(c.id, "fun", 20, "pulled off a prank")
        if out == "legend":
            fx.rep(c.id, "legend", 7, "legendary prank")
            seen = witnesses(sim, rng, {c.id}, 5)
            for s in seen:
                k = (sim.w.chars[s].traits["impulsivity"] - 40) / 60
                fx.rel(s, c.id, "familiarity", 4, "saw the prank")
                fx.rel(s, c.id, "affection", 3 * k, "saw the prank")
            make_rumor(sim, c.id, "prank", f"{c.name} was behind the prank in the east hall", True, 0.15, 0.6, None,
                       seen, ev.get("id"))
            fx.memory(c.id, "legend", [], 0.6, 50, "Pulled off a legendary prank")
            ev["importance"] = 30
    sim.expect(c.id, "prank", -0.7 if caught else (0.7 if out == "legend" else 0.0))


@resolver("sneak_out")
def r_sneak_out(sim, c, cand, ev, fx, rng, ctx):
    w, R = sim.w, sim.w.rules
    h = w.households.get(c.household_id)
    strict = h["strictness"] / 100 if h else 0.5
    pc = clamp(R["inst.catch_chance"] * (strict + 0.4) * R["inst.parent_strictness"] ** 0.5, 0, 0.98)
    roll = rng.random()
    caught = roll < pc
    ev["outcome"] = "caught" if caught else "fine"
    _calc(ev, "sneaking out", terms=[["household strictness", round(strict, 2)]], p_caught=round(pc, 3),
          roll=round(roll, 4), outcome=ev["outcome"])
    if caught:
        fx.flag(c.id, "grounded_until", c.flags.get("grounded_until", w.day) + 7, "caught sneaking out")
        fx.need(c.id, "stress", 12, "caught sneaking out")
        fx.mood(c.id, -8, "caught sneaking out")
        fx.memory(c.id, "caught", [], -0.6, 55, "Got caught sneaking out while grounded")
        ev["importance"] = 30
    else:
        fx.need(c.id, "fun", 25, "snuck out")
        fx.need(c.id, "social", 15, "snuck out")
        fx.need(c.id, "energy", -12, "late night")
        fx.flag(c.id, "late_night", w.day, "snuck out")
    sim.expect(c.id, "sneak_out", -0.6 if caught else 0.5)


# --- groups, obligations, institutions ------------------------------------------------

@resolver("attend")
def r_attend(sim, c, cand, ev, fx, rng, ctx):
    what = cand.a["params"]["what"]
    key = cand.target
    sim.slot.attend.setdefault((what, key), []).append(c.id)
    ev["skip"] = True  # the collective event records this


@resolver("sign_up")
def r_sign_up(sim, c, cand, ev, fx, rng, ctx):
    w = sim.w
    gid = cand.target
    g = w.groups[gid]
    it = cand.extra
    ev["group"] = gid
    ev["data"]["group"] = g["name"]
    if g["selection"] == "open":
        fx.join(c.id, gid, "signed up")
        ev["type"] = "sign_up.club"
        ev["outcome"] = "club"
        fx.mood(c.id, 3, f"joined {g['name']}")
        ev["importance"] = 16
    elif g["selection"] in ("tryout", "audition"):
        w.registrations.setdefault(it["key"], []).append(c.id)
        ev["type"] = "sign_up.tryout" if g["selection"] == "tryout" else "sign_up.audition"
        ev["outcome"] = "tryout" if g["selection"] == "tryout" else "audition"
        ev["data"]["event"] = it.get("production_name", it["name"])
        fx.need(c.id, "stress", 3, "signed up")
        ev["importance"] = 14
    elif g["selection"] == "election":
        w.registrations.setdefault(it["key"], []).append(c.id)
        ev["type"] = "sign_up.election"
        ev["outcome"] = "election"
        sim.add_goal(c, "win_election", gid, g["name"], 70, deadline=it["day"], fx=fx)
        fx.need(c.id, "stress", 4, "running for office")
        ev["importance"] = 24
    elif g["selection"] == "hire":
        ev["type"] = "sign_up.job"
        ev["outcome"] = "job"
        c.flags["applied_" + gid] = w.day
        sim.schedule(w.day + 2, "hire_decision", {"char": c.id, "group": gid}, ev.get("id"))
        ev["importance"] = 12


@resolver("quit_group")
def r_quit(sim, c, cand, ev, fx, rng, ctx):
    w = sim.w
    gid = cand.target
    g = w.groups[gid]
    fx.leave(c.id, gid, "quit")
    ev["type"] = "quit_group"
    ev["outcome"] = "quit"
    ev["group"] = gid
    ev["data"]["group"] = g["name"]
    fx.need(c.id, "stress", -8, f"quit {g['name']}")
    if g.get("staff"):
        fx.rel(g["staff"], c.id, "respect", -10, "quit the group")
    fx.memory(c.id, "quit", [], -0.1, 35, f"Quit {g['name']}", tags=[gid])
    if g["skill"]:
        fx.interest(c.id, g["skill"], -6, "walked away")
    if g["kind"] == "team":
        sim.institutions.call_up(gid, ev, fx, rng)
    ev["importance"] = 26


@resolver("work_shift")
def r_work(sim, c, cand, ev, fx, rng, ctx):
    w = sim.w
    g = w.groups[cand.target]
    ev["type"] = "job"
    ev["outcome"] = "shift"
    ev["group"] = g["id"]
    ev["data"]["group"] = g["name"]
    fx.money(c.id, g["pay"], f"shift at {g['name']}")
    fx.need(c.id, "energy", -12, "work")
    fx.need(c.id, "fun", -5, "work")
    fx.need(c.id, "stress", 2, "work")
    sim.slot.attend.setdefault(("shift", g["id"]), []).append(c.id)
    co = [m for m in g["members"] if m != c.id]
    if co:
        o = co[int(rng.random() * len(co))]
        fx.rel(c.id, o, "familiarity", 3, "coworkers")
        fx.rel(o, c.id, "familiarity", 3, "coworkers")
        fx.rel(c.id, o, "affection", 1.5, "coworkers")
    sim.expect(c.id, "work_shift", 0.1)


@resolver("throw_party")
def r_throw_party(sim, c, cand, ev, fx, rng, ctx):
    w, R = sim.w, sim.w.rules
    friends = sorted([o for o, r in w.out.get(c.id, {}).items() if r.affection >= R["rel.friend_threshold"] - 8
                      and w.chars[o].role == "student" and w.chars[o].status == "active"],
                     key=lambda o: (-w.rels[(c.id, o)].affection, o))
    popular = []
    if c.motives["approval"] >= 55:
        popular = sorted([o for o, r in w.out.get(c.id, {}).items() if r.familiarity >= 20 and w.chars[o].role == "student"
                          and w.chars[o].popularity >= 62 and o not in friends], key=lambda o: (-w.chars[o].popularity, o))
    invited = (friends[:10] + popular[:5])[:14]
    key = f"party:{c.id}:{w.day}"
    w.parties[key] = {"key": key, "day": w.day, "host": c.id, "invited": invited, "slot": "evening"}
    fx.money(c.id, -15, "party supplies")
    ev["type"] = "throw_party"
    ev["outcome"] = "planned"
    ev["data"].update({"invited": invited, "party": key})
    ev["involved"] = invited
    ev["importance"] = 18
    ev["text"] = f"{c.name} is throwing a party tonight and invited {len(invited)} people."


@resolver("mentor")
def r_mentor(sim, c, cand, ev, fx, rng, ctx):
    w = sim.w
    b = cand.target
    B = w.chars[b]
    p = {"kind": "mentor", "quality_bias": 0.15 + (c.traits["empathy"] - 50) / 200, "familiarity": 4, "affection": 6,
         "trust": 5, "attraction": 0, "social": 4}
    res = social.interact(sim, fx, ev, c.id, b, p, rng, ev["calc"] if ev.get("calc") is not None else None)
    ev["type"] = "mentor"
    ev["outcome"] = res["outcome"]
    ev["targets"] = [b]
    groups = [x for x in B.memberships if w.groups[x].get("staff") == c.id and w.groups[x].get("skill")]
    q = res["qb"]
    if groups:
        sk = w.groups[groups[0]]["skill"]
        fx.skill(b, sk, skill_gain(sim, B, sk, 1.2 * max(0.1, q + 0.5), ev), f"mentored by {c.short}")
        ev["data"]["skill"] = sk
    fx.need(b, "stress", -6 * max(0.0, q + 0.4), f"mentored by {c.short}")
    fx.rel(b, c.id, "respect", 5 * max(0.0, q + 0.3), "mentoring")
    if res["outcome"] == "great":
        fx.memory(b, "mentored", [c.id], 0.6, 50, f"{c.name} believed in them")
        sim.confidence(b, 1.5, fx, "mentored")


@resolver("lunch_table")
def r_lunch_table(sim, c, cand, ev, fx, rng, ctx):
    sim.slot.tables.append((c.id, cand.target))
    ev["skip"] = True  # the lunch-table event records this
