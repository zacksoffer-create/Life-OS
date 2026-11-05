"""Autonomous decision making: a transparent utility model with a softmax draw.

For each decision slot a character:
  1. enumerates candidate (action, target) pairs from the action catalog, with the reason
     each one is available (requirements and target selectors);
  2. scores each candidate as a sum of named terms (needs, motives, traits, interests,
     feelings toward the target, goals, memories, learned experience, habit, peers, risk,
     obligations, situation) — every term multiplied by its Workshop weight;
  3. draws one by softmax with a personal temperature (impulsive people are noisier),
     recording the uniform roll.
The trace keeps the full term breakdown for the top candidates, so any decision can be
re-read later exactly as it was computed. Nothing in a trace is written after the fact.
"""
from __future__ import annotations

import math

from . import calendar as calm
from .rng import clamp, softmax_pick
from .social import grudge_score, is_friend, memory_pull, romance_ok, satisfaction, best_rumor_for

TRACE_TOP = 5


class Cand:
    __slots__ = ("a", "target", "extra", "why", "u", "terms", "prob")

    def __init__(self, a, target, extra, why):
        self.a = a
        self.target = target
        self.extra = extra
        self.why = why
        self.u = 0.0
        self.terms = None
        self.prob = 0.0


# --- requirements -------------------------------------------------------------

def requirement(sim, c, req: str, ctx) -> str | None:
    """Return a human reason if the requirement is met, else None."""
    w = sim.w
    if req == "not_grounded":
        return "not grounded" if not c.flags.get("grounded_until", -1) >= w.day else None
    if req == "grounded":
        g = c.flags.get("grounded_until", -1)
        return f"grounded until day {g}" if g >= w.day else None
    if req.startswith("money:"):
        need = float(req.split(":")[1])
        return f"has ${c.money:.0f}" if c.money >= need else None
    if req == "romance":
        return "romance enabled" if w.rules["romance.enabled"] else None
    if req == "single":
        return "single" if not c.flags.get("partner") else None
    if req == "weekend":
        return "weekend" if calm.weekday(w.day) >= 5 else None
    if req == "can_host":
        h = w.households.get(c.household_id)
        if h and h.get("away_weekend") == w.day // 7:
            return f"{h['name']} is away this weekend"
        if h and h["style"] == "permissive":
            return "guardians don't mind parties"
        return None
    if req == "healthy":
        g = c.flags.get("injured_until", -1)
        return "healthy" if g < w.day else None
    if req == "has_pet":
        h = w.households.get(c.household_id)
        return f"household has {h['pet']['name']}" if h and h.get("pet") else None
    if req == "pet_home":
        if c.location != "hollow_creek" or not c.household_id:
            return None
        from .pets import household_pets
        hp = household_pets(w, c.household_id)
        return f"{hp[0]['name']} is home" if hp else None
    if req == "dance_window":
        return f"{ctx['dance']['name']} is coming up" if ctx.get("dance") and _dance_ok(w, c, ctx["dance"]) else None
    if req == "no_dance_date":
        d = ctx.get("dance")
        return "no date yet" if d and c.id not in w.dance_dates.get(d["key"], {}) else None
    return None


def _dance_ok(w, c, dance) -> bool:
    return c.role == "student" and (not dance.get("grades") or c.grade in dance["grades"])


# --- target selectors ----------------------------------------------------------

def _present(sim, c, other_id, slot) -> bool:
    o = sim.w.chars.get(other_id)
    if o is None or o.status != "active" or o.id == c.id or o.location != c.location:
        return False
    if slot == "lunch":
        return o.role == "student"
    if c.role == "staff":
        return o.role == "staff"
    return o.role in ("student", "alumni")


def _shortlist(sim, c, rels, key, k, rng):
    rels.sort(key=lambda r: (-key(r), r.dst))
    top = rels[:max(1, k - 1)]
    rest = rels[max(1, k - 1):]
    if rest:
        top.append(rest[int(rng.random() * len(rest))])
    return top


def targets(sim, c, a, slot, ctx, rng) -> list:
    w, R = sim.w, sim.w.rules
    sel = a["target"]
    K = R["decision.shortlist_size"]
    out = []
    if sel is None:
        return [(None, None, "always available")]
    if sel == "skill":
        opts = []
        for sid in sim.cat.skills:
            if sid == "academics":
                continue
            iv = c.interests.get(sid, 0)
            goal = any(g["status"] == "active" and g.get("skill") == sid for g in c.goals)
            if iv >= 30 or goal:
                opts.append((iv + (30 if goal else 0), sid))
        opts.sort(key=lambda x: (-x[0], x[1]))
        return [(sid, None, f"interested in {sim.cat.skills[sid]['label'].lower()} ({c.interests.get(sid, 0):.0f})"
                 + (" + a goal" if v - c.interests.get(sid, 0) >= 30 else "")) for v, sid in opts[:2]]
    if sel == "hobby":
        opts = sorted(((c.interests.get(h, 0), h) for h in sim.cat.hobbies if c.interests.get(h, 0) >= 25),
                      key=lambda x: (-x[0], x[1]))[:2]
        if not opts:
            opts = [(20, "shows")]
        return [(h, None, f"enjoys {sim.cat.hobbies[h]['label']} ({v:.0f})") for v, h in opts]
    rels_out = sim.w.out.get(c.id, {})
    known = ctx["known"]
    if sel in ("known", "listener", "tease_target", "colleague"):
        pool = ctx["known_remote"] if a["id"] == "chat_online" else known
        cand = [r for oid, r in pool if r.familiarity >= 10]
        prot = w.meta.get("protagonist")
        if a["id"] == "hang_out" and prot and c.id != prot and any(r.dst == prot for r in cand):
            from .squad import can_ask  # one on one is for people you're close to, when neither of you is busy
            if not can_ask(sim, c.id, slot):
                cand = [r for r in cand if r.dst != prot]
        if sel == "colleague":
            cand = [r for r in cand if w.chars[r.dst].role == "staff"]
        if sel == "listener":
            cand = [r for r in cand if r.affection >= 12]
        if sel == "tease_target":
            gr = ctx["grudge"]
            cand = [r for r in cand if w.chars[r.dst].role == "student" and
                    (w.chars[r.dst].popularity < c.popularity - 10 or gr.get(r.dst, 0) > 25)]
        if not cand:
            return []
        appr = c.motives["approval"] / 100
        def key(r):
            o = w.chars[r.dst]
            return r.affection + 0.3 * r.familiarity + 0.3 * r.attraction + appr * o.popularity * 0.4 - r.rivalry * 0.3
        if sel == "tease_target":
            key = lambda r: (c.popularity - w.chars[r.dst].popularity) + ctx["grudge"].get(r.dst, 0)
        top = _shortlist(sim, c, cand, key, K, rng)
        if a["id"] == "hang_out" and c.id == prot:
            from .squad import must_list  # your group (and whoever invited you) are always an option
            must = set(must_list(sim, slot))
            top += [r for r in cand if r.dst in must and r not in top]
        for r in top:
            o = w.chars[r.dst]
            why = f"knows {o.short} ({r.label}, affection {r.affection:.0f})"
            extra = None
            if sel == "listener":
                rum = best_rumor_for(w, c.id, r.dst, R, ctx.get("rumors_by", {}).get(c.id, []) if "rumors_by" in ctx else ctx.get("rumors"))
                if rum is None:
                    continue
                extra = rum["id"]
                why += f"; has gossip: {rum['text']}"
            out.append((r.dst, extra, why))
        return out
    if sel == "stranger":
        pool = []
        for o in sim.w.students():
            if o.id == c.id or o.location != c.location or o.school != c.school:
                continue
            r = rels_out.get(o.id)
            if r is not None and r.familiarity >= 15:
                continue
            near = (o.grade == c.grade) or bool(set(o.memberships) & set(c.memberships))
            if near or rng.random() < 0.25:
                pool.append(o.id)
        pool.sort()
        rng.shuffle(pool)
        return [(oid, None, f"barely knows {w.chars[oid].short}" + (" (same grade)" if w.chars[oid].grade == c.grade else ""))
                for oid in pool[:max(1, K // 2)]]
    if sel in ("crush", "dance_date"):
        if not R["romance.enabled"]:
            return []
        cand = []
        for oid, r in known:
            if w.chars[oid].role != "student":
                continue
            if oid == c.flags.get("partner") and sel == "crush":
                continue
            if sel == "crush" and r.crush:
                cand.append(r)
            elif sel == "dance_date":
                # a date to the dance: their partner, or someone they're actually into (never family, never just a friend:
                # friends go to the dance together anyway, as a group)
                d = ctx.get("dance")
                if d and _dance_ok(w, w.chars[oid], d) and oid not in w.dance_dates.get(d["key"], {}) and \
                        (oid == c.flags.get("partner") or (romance_ok(w, c.id, oid, chosen=True) and (r.crush or r.attraction >= 30))):
                    cand.append(r)
        cand.sort(key=lambda r: (-(r.attraction + r.affection * 0.3), r.dst))
        return [(r.dst, None, f"attraction to {w.chars[r.dst].short} {r.attraction:.0f}" +
                 (" (crush)" if r.crush else "")) for r in cand[:2]]
    if sel == "partner":
        p = c.flags.get("partner")
        if p and _present(sim, c, p, slot):
            return [(p, None, f"dating {w.chars[p].short}")]
        return []
    if sel == "grudge":
        cand = [(ctx["grudge"].get(oid, 0), r) for oid, r in known if r.affection < 0 or r.rivalry > 30]
        cand = [x for x in cand if x[0] >= 25]
        cand.sort(key=lambda x: (-x[0], x[1].dst))
        return [(r.dst, None, f"holds a grudge against {w.chars[r.dst].short} ({g:.0f})") for g, r in cand[:2]]
    if sel == "rumor_victim":
        cand = []
        for oid, r in known:
            if w.chars[oid].role != "student":
                continue
            g = ctx["grudge"].get(oid, 0)
            threat = w.chars[oid].popularity - c.popularity
            if g >= 20 or r.rivalry >= 30 or (threat > 15 and r.familiarity > 20 and c.motives["approval"] > 60):
                cand.append((g + max(0, threat) * 0.5, r))
        cand.sort(key=lambda x: (-x[0], x[1].dst))
        return [(r.dst, None, f"resents or envies {w.chars[r.dst].short}") for g, r in cand[:2]]
    if sel == "conflict":
        cand = []
        for m in c.memories[-25:]:
            if m["kind"] in ("argument", "falling_out", "betrayed", "rejected_apology", "exclusion_by", "humiliated_by", "broke_up") \
                    and w.day - m["day"] <= 45:
                for oid in m["with"]:
                    r = rels_out.get(oid)
                    if r and _present(sim, c, oid, slot) and r.peak_affection >= R["rel.friend_threshold"] and \
                            r.affection < r.peak_affection - 12 and oid not in [x[0] for x in cand]:
                        cand.append((oid, m["text"]))
        return [(oid, None, f"falling-out with {w.chars[oid].short}: {txt}") for oid, txt in cand[:2]]
    if sel == "needy_friend":
        cand = [r for oid, r in known if is_friend(r, R) and w.chars[oid].needs["stress"] >= 58 and r.familiarity >= 35]
        cand.sort(key=lambda r: (-w.chars[r.dst].needs["stress"], r.dst))
        return [(r.dst, None, f"friend {w.chars[r.dst].short} seems stressed ({w.chars[r.dst].needs['stress']:.0f})")
                for r in cand[:2]]
    if sel == "practice":
        return [(gid, None, f"member of {w.groups[gid]['name']}, meets today") for gid in ctx["practices"]
                if gid in c.memberships]
    if sel == "event":
        res = []
        hurt = c.flags.get("injured_until", -1) >= w.day
        for it in ctx["events"]:
            k = it["kind"]
            if hurt and k in ("tryout", "game"):
                continue
            if k in ("tryout", "audition") and c.id in w.registrations.get(it["key"], []):
                res.append((it["key"], it, f"signed up for {it['name']}"))
            elif k == "game" and c.id in w.groups[it["group"]]["members"]:
                res.append((it["key"], it, f"on the roster for {it['name']}"))
            elif k == "show" and c.id in (w.groups[it["group"]].get("production") or {}).get("cast", []):
                res.append((it["key"], it, f"in the cast of {it['name']}"))
            elif k == "dance" and _dance_ok(w, c, it):
                d = w.dance_dates.get(it["key"], {}).get(c.id)
                res.append((it["key"], it, f"{it['name']} tonight" + (f", going with {w.chars[d].short}" if d else "")))
        return res
    if sel == "spectate":
        res = []
        for it in ctx["events"]:
            if it["kind"] in ("game", "show"):
                g = w.groups[it["group"]]
                perf = g["members"] if it["kind"] == "game" else (g.get("production") or {}).get("cast", [])
                if c.id in perf or not perf:
                    continue
                res.append((it["key"], it, f"{it['name']} is today"))
        return res
    if sel == "opportunity":
        return [(gid, it, why) for gid, it, why in ctx["opps"](c)]
    if sel == "membership":
        return [(gid, None, f"member of {w.groups[gid]['name']}") for gid in c.memberships]
    if sel == "shift":
        return [(gid, None, f"has a shift at {w.groups[gid]['name']}") for gid in c.memberships
                if w.groups[gid]["kind"] == "job" and calm.weekday(w.day) in w.groups[gid]["shift_days"]]
    if sel == "party":
        res = []
        for pk, p in w.parties.items():
            if p["day"] != w.day or p["host"] == c.id:
                continue
            if c.id in p["invited"]:
                res.append((pk, p, f"invited to {w.chars[p['host']].short}'s party"))
            else:
                friends_in = [i for i in p["invited"] if is_friend(w.rels.get((c.id, i)), R)]
                if friends_in and (c.traits["sociability"] > 55 or c.id == w.meta.get("protagonist")):
                    res.append((pk, p, f"heard about {w.chars[p['host']].short}'s party from friends"))
        return res
    if sel == "sibling":
        sibs = [oid for oid in sim.siblings(c.id) if _present(sim, c, oid, "day")]
        return [(s, None, f"sibling {w.chars[s].short}") for s in sibs[:2]]
    if sel == "inbox":
        res = []
        for inv in sim.w.meta.get("inbox", []):
            if inv["to"] == c.id and inv["status"] == "pending" and inv["from"] in sim.w.chars and _present(sim, c, inv["from"], slot):
                res.append((inv["from"], {"invite": inv["id"]}, f"{sim.w.chars[inv['from']].short} asked you to hang out"))
        return res
    if sel in ("pet_entity", "pet_entity_dog"):
        from .pets import household_pets
        hp = [p for p in household_pets(w, c.household_id) if sel == "pet_entity" or p["species"] == "dog"]
        return [(None, {"pet": p["id"], "name": p["name"]}, f"{p['name']} the {p['species']}") for p in hp]
    if sel == "pet":
        h = w.households.get(c.household_id)
        return [(None, None, f"{h['pet']['name']} the {h['pet']['species']}")] if h and h.get("pet") else []
    if sel == "mentee":
        cand = []
        for oid, r in rels_out.items():
            o = w.chars.get(oid)
            if o is None or o.role != "student" or o.status != "active":
                continue
            mine = any(w.groups[g].get("staff") == c.id for g in o.memberships)
            if mine or r.affection > 20:
                cand.append(r)
        cand.sort(key=lambda r: (-(r.affection + r.respect + w.chars[r.dst].needs["stress"] * 0.3), r.dst))
        return [(r.dst, None, f"knows {w.chars[r.dst].short} ({'own group' if any(w.groups[g].get('staff') == c.id for g in w.chars[r.dst].memberships) else 'student'})")
                for r in cand[:K]]
    return out


# --- scoring -------------------------------------------------------------------

def _urgency(c, need):
    v = c.needs[need]
    d = v if need == "stress" else 100 - v
    return (d / 100.0) ** 1.5


def score(sim, c, cand: Cand, ctx, terms: list | None) -> float:
    return action_score(sim, c, cand.a, ctx, terms) + target_score(sim, c, cand, ctx, terms)


def action_score(sim, c, a, ctx, terms: list | None) -> float:
    """Terms that depend only on the person and the action (shared by all its targets)."""
    R = sim.w.rules
    aid = a["id"]
    u = a["base"]
    if terms is not None:
        terms.append(("base appeal of action", u, "catalog base"))
    Wn = R["decision.need_weight"]
    for need, coef in a["needs"].items():
        v = coef * _urgency(c, need) * 30 * Wn
        u += v
        if terms is not None and abs(v) >= 0.05:
            terms.append((f"need: {need}", v, f"{need} {c.needs[need]:.0f}, coef {coef:+}, weight {Wn}"))
    for m, coef in a["motives"].items():
        Wm = R[f"motive.{m}"]
        v = coef * c.motives[m] / 100 * 15 * Wm
        u += v
        if terms is not None and abs(v) >= 0.05:
            terms.append((f"motive: {m}", v, f"{m} {c.motives[m]:.0f}, coef {coef:+}, weight {Wm}"))
    Wt = R["decision.trait_weight"]
    for t, coef in a["traits"].items():
        v = coef * (c.traits[t] - 50) / 50 * 10 * Wt
        u += v
        if terms is not None and abs(v) >= 0.05:
            terms.append((f"trait: {t}", v, f"{t} {c.traits[t]:.0f}, coef {coef:+}, weight {Wt}"))
    ex = c.expectations.get(aid)
    if ex:
        k = (1.5 - c.traits["confidence"] / 100) if ex < 0 else 1.0
        v = ex * 12 * k * R["decision.learning_weight"]
        u += v
        if terms is not None and abs(v) >= 0.05:
            terms.append(("how this has gone before", v, f"expected outcome {ex:+.2f}" + (" (amplified by low confidence)" if ex < 0 else "")))
    hb = c.habits.get(aid)
    if hb:
        v = hb * 8 * R["decision.habit_weight"]
        u += v
        if terms is not None and abs(v) >= 0.05:
            terms.append(("habit", v, f"habit strength {hb:.2f}"))
    conf = ctx["peer"].get(aid, 0.0)
    if conf:
        v = conf * 10 * c.motives["belonging"] / 100 * R["decision.conformity_weight"]
        u += v
        if terms is not None and abs(v) >= 0.05:
            terms.append(("what friends have been doing", v, f"{conf:.0%} of friends did this recently"))
    if a["risk"]:
        ra = clamp(1.3 - c.traits["impulsivity"] / 100 - c.traits["confidence"] / 250, 0.1, 1.3)
        v = -a["risk"] * 20 * ra * R["decision.risk_aversion"]
        u += v
        if terms is not None:
            terms.append(("risk", v, f"risk {a['risk']}, personal aversion {ra:.2f}"))
    if a["obligation"]:
        k = 0.4 + c.traits["discipline"] / 250 + c.traits["loyalty"] / 250
        v = a["obligation"] * 18 * k * R["decision.obligation_weight"]
        u += v
        if terms is not None:
            terms.append(("commitment", v, f"discipline/loyalty factor {k:.2f}"))
    return u


def target_score(sim, c, cand: Cand, ctx, terms: list | None) -> float:
    """Terms that depend on the specific target (person, group, skill, event)."""
    w, R = sim.w, sim.w.rules
    a = cand.a
    aid = a["id"]
    u = 0.0
    if a["interest"]:
        iv = _interest_for(sim, c, cand)
        v = a["interest"] * iv / 100 * 15 * R["decision.interest_weight"]
        u += v
        if terms is not None and abs(v) >= 0.05:
            terms.append(("interest", v, f"interest {iv:.0f}, coef {a['interest']}, weight {R['decision.interest_weight']}"))
    tgt = cand.target
    Wr = R["decision.relationship_weight"]
    if a["target_terms"]:
        r = w.rels.get((c.id, tgt)) if isinstance(tgt, str) and tgt in w.chars else None
        o = w.chars.get(tgt) if isinstance(tgt, str) else None
        for key, coef in a["target_terms"].items():
            v, note = _target_term(sim, c, cand, key, coef, r, o, R)
            v *= R["motive.approval"] if key == "popularity_approval" else Wr
            u += v
            if terms is not None and abs(v) >= 0.05:
                terms.append((f"toward target: {key}", v, note))
    if isinstance(tgt, str) and tgt in w.chars and tgt != c.id:
        mp = memory_pull(w, c.id, tgt, w.day)
        if mp:
            sign = -1.0 if aid in ("confront", "spread_rumor", "tease") else 1.0
            v = sign * mp * 15 * R["decision.memory_weight"]
            u += v
            if terms is not None and abs(v) >= 0.05:
                terms.append(("memories with target", v, f"memory pull {mp:+.2f}{' (reversed for conflict)' if sign < 0 else ''}"))
    Wg = R["decision.goal_weight"]
    for g, adv in ctx["goal_adv"].get(aid, ()):
        wt, match = adv
        if not _goal_match(sim, c, cand, g, match):
            continue
        v = wt * g["priority"] / 100 * 18 * Wg
        u += v
        if terms is not None:
            terms.append((f"goal: {g['label']}", v, f"priority {g['priority']:.0f}, advance {wt}"))
    for label, v, note in _context(sim, c, cand, ctx):
        u += v
        if terms is not None and abs(v) >= 0.05:
            terms.append((label, v, note))
    return u


def _interest_for(sim, c, cand) -> float:
    a, t = cand.a, cand.target
    aid = a["id"]
    if aid in ("study", "study_at_lunch"):
        return c.interests.get("academics", 30)
    if aid == "train":
        return max([c.interests.get(s, 0) for s in ("football", "basketball", "baseball", "soccer", "softball", "fitness")] + [20])
    if aid in ("practice_skill",):
        return c.interests.get(t, 0)
    if aid == "hobby":
        return c.interests.get(t, 0)
    if aid in ("attend_practice", "sign_up"):
        g = sim.w.groups.get(t)
        if g is None:
            return 40
        if g.get("skill"):
            return c.interests.get(g["skill"], 0)
        return 40 if g["kind"] == "job" else 45
    return 50


def _target_term(sim, c, cand, key, coef, r, o, R):
    w = sim.w
    if key in ("affection", "familiarity", "attraction", "rivalry", "respect", "perceived"):
        val = getattr(r, key) if r is not None else 0.0
        return coef * val / 100 * 12, f"{key} {val:.0f} x coef {coef:+}"
    if key == "popularity_approval":
        if o is None:
            return 0.0, ""
        v = coef * (o.popularity - 50) / 50 * c.motives["approval"] / 100 * 12
        return v, f"{o.short}'s popularity {o.popularity:.0f}, approval motive {c.motives['approval']:.0f}"
    if key == "target_stress" and o is not None:
        return coef * (o.needs["stress"] - 50) / 50 * 10, f"{o.short}'s stress {o.needs['stress']:.0f}"
    if key == "grudge" and r is not None:
        g = grudge_score(w, r, w.day)
        return coef * g / 100 * 15, f"grudge {g:.0f}"
    if key == "past_affection" and r is not None:
        v = coef * ((r.peak_affection - r.affection) / 100 * 12 + r.peak_affection / 100 * 10)
        return v, f"used to be at {r.peak_affection:.0f}, now {r.affection:.0f}"
    if key == "dissatisfaction" and o is not None:
        s = satisfaction(w, c.id, o.id)
        return coef * (R["romance.breakup_threshold"] - s) / 30 * 15, f"satisfaction {s:.0f} vs threshold {R['romance.breakup_threshold']}"
    if key == "rumor_juice" and cand.extra:
        rum = w.rumors[cand.extra]
        return coef * rum["juice"] * 10, f"juiciness {rum['juice']:.2f}"
    if key == "popularity_threat" and o is not None:
        v = coef * (o.popularity - c.popularity) / 50 * c.motives["approval"] / 100 * 15
        return v, f"{o.short} {o.popularity:.0f} vs self {c.popularity:.0f}"
    if key == "low_status" and o is not None:
        return coef * (c.popularity - o.popularity) / 50 * 10, f"self {c.popularity:.0f} vs {o.short} {o.popularity:.0f}"
    if key == "host_affection" and cand.extra:
        hr = w.rels.get((c.id, cand.extra["host"]))
        v = hr.affection if hr else 0.0
        return coef * v / 100 * 20, f"feelings toward host {v:.0f}"
    if key == "friends_performing" and cand.extra:
        g = w.groups[cand.extra["group"]]
        perf = g["members"] if cand.extra["kind"] == "game" else (g.get("production") or {}).get("cast", [])
        n = sum(1 for p in perf if is_friend(w.rels.get((c.id, p)), R))
        return coef * min(n, 3) * 4, f"{n} friends performing"
    if key == "group_discontent":
        g = w.groups.get(cand.target)
        if g is None:
            return 0.0, ""
        iv = c.interests.get(g["skill"], 50) if g.get("skill") else 45
        aff = [w.rels[(c.id, m)].affection for m in g["members"] if m != c.id and (c.id, m) in w.rels]
        avg = sum(aff) / len(aff) if aff else 0
        disc = (50 - iv) / 50 * 8 + max(0, c.needs["stress"] - 60) / 40 * 6 - avg / 25
        return coef * disc, f"interest {iv:.0f}, stress {c.needs['stress']:.0f}, avg feeling toward members {avg:.0f}"
    if key == "mentee_need" and o is not None:
        mine = any(w.groups[x].get("staff") == c.id for x in o.memberships)
        v = coef * ((o.needs["stress"] - 50) / 50 * 5 + (5 if mine else 0))
        return v, f"{o.short}'s stress {o.needs['stress']:.0f}" + (", in their group" if mine else "")
    return 0.0, ""


def _goal_match(sim, c, cand, g, match) -> bool:
    if match == "any":
        return True
    if match == "goal_target":
        if isinstance(cand.extra, dict) and cand.extra.get("group"):
            return cand.extra["group"] == g.get("target")
        return cand.target == g.get("target")
    if match == "goal_skill":
        t = cand.target
        if cand.a["id"] == "practice_skill":
            return t == g.get("skill")
        grp = sim.w.groups.get(t) if isinstance(t, str) else None
        return bool(grp and grp.get("skill") == g.get("skill"))
    if match == "popular":
        o = sim.w.chars.get(cand.target) if isinstance(cand.target, str) else None
        return bool(o and o.popularity >= 60)
    if match == "job":
        grp = sim.w.groups.get(cand.target) if isinstance(cand.target, str) else None
        return bool(grp and grp["kind"] == "job")
    return False


def _context(sim, c, cand, ctx):
    """Situation-specific terms. Each returns (label, value, note)."""
    w, R = sim.w, sim.w.rules
    aid = cand.a["id"]
    out = []
    if aid in ("study", "study_at_lunch", "practice_skill", "train", "hobby") and ctx["events"]:
        if any(it["kind"] in ("game", "show") and (c.id in w.groups[it["group"]]["members"]) for it in ctx["events"] if it.get("group")):
            out.append(("game tonight", -12.0, "you're on the roster"))
    if aid in ("study", "study_at_lunch"):
        if ctx["slot"] == "after_school" and aid == "study":
            out.append(("homework due tomorrow", 4 + 6 * c.traits["discipline"] / 100, "school night"))
        if c.flags.get("pressure_until", -1) >= w.day:
            out.append(("pushed by family to study", 6.0, "guardian pressure is active"))
        ex = ctx["exam_soon"]
        if ex:
            out.append((f"{ex['name']} coming up", 8 * c.motives["achievement"] / 100 * R["motive.achievement"],
                        f"in {ex['day'] - w.day} days"))
    elif aid == "attend_practice":
        g = w.groups[cand.target]
        out.append(("the coach takes attendance" if g["kind"] in ("team", "production") else "it's a regular commitment",
                    26.0 if g["kind"] in ("team", "production") else 8.0, g["kind"]))
        if g["kind"] == "club" and any(w.groups[x]["kind"] in ("team", "production") for x in ctx["practices"] if x in c.memberships):
            out.append(("team practice is the same day", -12.0, "the team comes first"))
        ab = g["absences"].get(c.id)
        ab = sum(ab) if isinstance(ab, list) else 0
        if ab:
            v = min(8.0, ab * 1.5 * (c.traits["discipline"] + c.traits["ambition"]) / 100)
            out.append(("worried about missed practices", v, f"missed {ab} of the last 8 (limit {R['inst.absence_tolerance']})"))
        st = g.get("staff")
        if st and (c.id, st) in w.rels:
            v = w.rels[(c.id, st)].affection / 100 * 6
            out.append(("feelings about the coach/advisor", v, f"affection {w.rels[(c.id, st)].affection:.0f}"))
    elif aid == "attend_event" and cand.extra:
        it = cand.extra
        if it["kind"] in ("tryout", "audition"):
            out.append(("signed up for this", 20.0, "your name is on the list"))
            nerves = (c.traits["volatility"] - 50) / 50 * 5 - (c.traits["confidence"] - 50) / 50 * 5 + (c.needs["stress"] - 50) / 50 * 4
            out.append(("nerves", -nerves, f"volatility {c.traits['volatility']:.0f}, confidence {c.traits['confidence']:.0f}, stress {c.needs['stress']:.0f}"))
        if it["kind"] == "dance":
            d = w.dance_dates.get(it["key"], {}).get(c.id)
            if d:
                out.append(("has a date", 14.0, f"going with {w.chars[d].short}"))
            else:
                out.append(("no date", (c.traits["confidence"] - 60) / 50 * 6 + (c.traits["sociability"] - 50) / 50 * 4,
                            "going solo depends on nerve"))
        if it["kind"] in ("game", "show"):
            out.append(("the team is counting on you", 40.0, "players are expected at games"))
    elif aid == "sign_up" and cand.extra:
        it = cand.extra
        g = w.groups[cand.target]
        cut = [m for m in c.memories if m["kind"] == "cut_from_team" and (not m.get("tags") or g["id"] in m.get("tags", []) or "backstory" in m.get("tags", []))]
        if cut and g["kind"] == "team":
            resolve = (c.traits["competitiveness"] + c.traits["discipline"] + c.traits["ambition"]) / 3
            v = (resolve - 55) / 45 * 8 - (55 - c.traits["confidence"]) / 45 * 4
            out.append(("history of getting cut", v, f"resolve {resolve:.0f}, confidence {c.traits['confidence']:.0f}"))
        if g["kind"] in ("team", "production"):
            sk = c.skills.get(g["skill"], 0)
            out.append(("sense of own level", (sk - 40) / 40 * 5 + (c.traits["confidence"] - 50) / 50 * 4,
                        f"{g['skill']} skill {sk:.0f}"))
        if g["kind"] == "council":
            out.append(("would they win?", (c.popularity - 50) / 50 * 6 + (c.motives["approval"] - 50) / 50 * 5,
                        f"popularity {c.popularity:.0f}"))
        if g["kind"] == "job":
            out.append(("wants money", max(0.0, (40 - c.money) / 40) * 6 - 2, f"has ${c.money:.0f}"))
        if g["kind"] == "club":
            iv = c.interests.get(g["skill"], 0)
            out.append(("actually into it?", (iv - 45) / 50 * 8, f"{g['skill']} interest {iv:.0f}"))
        if g["kind"] == "club" and len(c.memberships) >= 2:
            out.append(("already busy", -6.0 * (len(c.memberships) - 1), f"in {len(c.memberships)} groups"))
    elif aid in ("ask_out", "ask_to_dance"):
        r = w.rels.get((c.id, cand.target))
        if r is not None:
            hope = r.perceived / 100 * 10 + (c.traits["confidence"] - 50) / 50 * 5
            out.append(("thinks they might say yes", hope, f"believes their affection is {r.perceived:.0f}"))
            rej = [m for m in c.memories if m["kind"] == "rejected" and cand.target in m["with"] and w.day - m["day"] < 120]
            if rej:
                out.append(("was turned down before", -12.0, rej[-1]["text"]))
            T = w.chars.get(cand.target)
            bar = float(w.rules.get("romance.girl_asks_guy", 1.0))
            if bar > 0 and c.gender == "f" and T is not None and T.gender == "m":
                # it takes more for a girl to make the move on a guy: she has to be really into him, and pretty sure he's
                # into her too. Short of that she waits for him to ask.
                need = 60 + 15 * bar
                sure = r.perceived / 100
                v = -6.0 * bar - max(0.0, need - r.attraction) / 10 * 3 * bar + (sure - 0.5) * 4 * bar
                out.append(("she'd rather he asked", v, f"her attraction {r.attraction:.0f} (it takes about {need:.0f}), "
                                                       f"how sure she is he likes her {r.perceived:.0f}"))
    elif aid == "break_up":
        other = [r for oid, r in w.out.get(c.id, {}).items() if r.crush and oid != cand.target]
        if other:
            out.append(("interested in someone else", 7 * (1 - c.traits["loyalty"] / 100) * 2,
                        f"crush on {w.chars[other[0].dst].short}"))
    elif aid == "confront":
        out.append(("stress boiling over", max(0.0, c.needs["stress"] - 55) / 45 * 6, f"stress {c.needs['stress']:.0f}"))
        recent = [m for m in c.memories[-20:] if m["kind"] in ("argument", "falling_out", "cleared_air")
                  and cand.target in m["with"] and w.day - m["day"] <= 30]
        if recent:
            out.append(("already had it out recently", -25.0, f"{len(recent)} confrontation(s) in the last month"))
    elif aid == "spread_rumor":
        mine = sum(1 for r in ctx.get("rumors", []) if r["origin"] == c.id and r["about"] == cand.target)
        if mine:
            out.append(("already started one about them", -12.0 * mine, f"{mine} recent rumor(s)"))
    elif aid == "practice_skill":
        if any(w.groups[g].get("skill") == cand.target for g in ctx["practices"] if g in c.memberships):
            out.append(("team practice covers this today", -10.0, "practice with the group instead"))
        for it in ctx["events"]:
            if it["kind"] in ("tryout", "audition") and c.id in w.registrations.get(it["key"], []) \
                    and w.groups[it["group"]].get("skill") == cand.target:
                out.append(("tryouts are today", -15.0, f"{it['name']} is right now"))
    elif aid == "throw_party":
        out.append(("party appetite", (R["social.party_frequency"] - 1) * 10, f"party frequency {R['social.party_frequency']}"))
        if c.popularity < 35:
            out.append(("worried nobody will come", -6.0, f"popularity {c.popularity:.0f}"))
    elif aid == "go_to_party" and cand.extra:
        p = cand.extra
        n = sum(1 for i in p["invited"] if is_friend(w.rels.get((c.id, i)), R))
        out.append(("friends invited", min(n, 4) * 2.0, f"{n} friends on the invite list"))
        if c.id not in p["invited"]:
            out.append(("not technically invited", -5.0 + (c.traits["confidence"] - 50) / 10, "crashing"))
    elif aid == "work_shift":
        out.append(("the manager expects you", 40.0, "scheduled shift"))
        out.append(("needs money", max(0.0, (60 - c.money) / 60) * 6, f"has ${c.money:.0f}"))
    elif aid == "family_time":
        h = w.households.get(c.household_id)
        if h:
            out.append(("home atmosphere", (h["warmth"] - 50) / 50 * 5, f"{h['style_label']}"))
    elif aid in ("hang_out", "date") and cand.target in w.chars:
        if calm.weekday(w.day) >= 5:
            out.append(("weekend", 3.0, "more time free"))
        busy = [w.groups[g]["name"] for g in c.memberships if (g in ctx["practices"] and w.groups[g]["kind"] in ("team", "production"))
                or (w.groups[g]["kind"] == "job" and calm.weekday(w.day) in w.groups[g]["shift_days"])]
        if busy:
            out.append(("already has plans", -8.0, f"{busy[0]} today"))
    elif aid == "rest" and ctx["slot"] == "evening":
        out.append(("it's late", 3.0, "evenings favor winding down"))
    if c.id == w.meta.get("protagonist"):
        focus = w.meta.get("control", {}).get("focus", "balanced")
        if aid in FOCUS.get(focus, ()):
            if aid not in ("attend_event", "sign_up") or focus != "athletics" or _sporty(w, cand):
                out.append((f"your focus: {focus}", 7.0, "set by you"))
    return out


FOCUS = {
    "athletics": ("practice_skill", "train", "attend_practice", "attend_event", "sign_up"),
    "academics": ("study", "study_at_lunch"),
    "social": ("hang_out", "sit_with", "introduce", "chat_online", "go_to_party", "throw_party", "reply_invite"),
    "romance": ("flirt", "ask_out", "date", "ask_to_dance", "reply_invite"),
    "family": ("family_time", "pet_time", "help_friend", "pet_walk", "pet_park", "pet_play", "pet_train"),
    "rest": ("rest", "hobby", "sit_alone", "pet_time", "pet_play"),
    "work": ("work_shift", "sign_up"),
}


def _sporty(w, cand) -> bool:
    t = cand.target
    if isinstance(cand.extra, dict) and cand.extra.get("group"):
        t = cand.extra["group"]
    g = w.groups.get(t) if isinstance(t, str) else None
    return bool(g and g["kind"] == "team")


# --- the decision ------------------------------------------------------------------

def temperature(sim, c) -> float:
    R = sim.w.rules
    t = R["decision.temperature"] * (1 + R["decision.impulsivity_noise"] * (c.traits["impulsivity"] - 50) / 100
                                     + max(0.0, c.needs["stress"] - 70) / 100)
    return max(0.3, t)


def prepare(sim, c, slot, ctx):
    """Per-person, per-slot lookups shared by every candidate: who is around, which goals each action serves."""
    w = sim.w
    chars = w.chars
    loc = c.location
    lunch = slot == "lunch"
    staff = c.role == "staff"
    known, remote = [], []
    for oid, r in w.out.get(c.id, {}).items():
        o = chars.get(oid)
        if o is None or o.status != "active" or oid == c.id:
            continue
        if o.location == loc and ((o.role == "student") if lunch else (o.role == "staff") if staff else (o.role in ("student", "alumni"))):
            known.append((oid, r))
        if r.familiarity >= 25 and o.role in ("student", "alumni"):
            remote.append((oid, r))
    ctx["known"] = known
    ctx["known_remote"] = remote
    ctx["grudge"] = {oid: grudge_score(w, r, w.day) for oid, r in ctx["known"] if r.affection < 0 or r.rivalry > 20}
    ga: dict = {}
    for g in c.goals:
        if g["status"] == "active":
            for aid, adv in sim.cat.goals[g["type"]]["advances"].items():
                ga.setdefault(aid, []).append((g, adv))
    ctx["goal_adv"] = ga
    return ctx


def decide(sim, c, slot, ctx, rng, trace: bool):
    cat = sim.cat
    role = c.role
    w = sim.w
    prepare(sim, c, slot, ctx)
    T = temperature(sim, c)
    cands: list[Cand] = []
    shares: dict = {}
    for a in cat.by_slot.get(slot, []):
        if role not in a["roles"]:
            continue
        reasons = []
        ok = True
        for req in a["requires"]:
            rs = requirement(sim, c, req, ctx)
            if rs is None:
                ok = False
                break
            reasons.append(rs)
        if not ok:
            continue
        tl = targets(sim, c, a, slot, ctx, rng)
        if not tl:
            continue
        au = action_score(sim, c, a, ctx, None)
        share = -T * math.log(len(tl)) if len(tl) > 1 else 0.0
        shares[a["id"]] = (share, len(tl))
        for tgt, extra, why in tl:
            cd = Cand(a, tgt, extra, "; ".join(reasons + [why]))
            cd.u = au + target_score(sim, c, cd, ctx, None) + share
            cands.append(cd)
    if not cands:
        return None
    roll = rng.random()
    idx, probs = softmax_pick([cd.u for cd in cands], T, roll)
    for cd, p in zip(cands, probs):
        cd.prob = p
    chosen = cands[idx]
    tr = None
    if trace:
        order = sorted(range(len(cands)), key=lambda i: -cands[i].u)
        rows = []
        for rank, i in enumerate(order):
            cd = cands[i]
            row = {"action": cd.a["id"], "label": cd.a["label"], "target": cd.target if not isinstance(cd.target, dict) else None,
                   "why": cd.why, "utility": round(cd.u, 2), "prob": round(cd.prob, 4), "chosen": i == idx}
            if rank < TRACE_TOP or i == idx:
                terms = []
                score(sim, c, cd, ctx, terms)
                sh, n = shares[cd.a["id"]]
                if sh:
                    terms.append((f"shared among {n} possible targets", sh, "-temperature x ln(n): an action's options split one share of probability"))
                row["terms"] = [[t[0], round(t[1], 2), t[2]] for t in terms]
                row["target_name"] = sim.target_name(cd)
            rows.append(row)
        tr = {"day": w.day, "slot": slot, "char": c.id, "temperature": round(T, 3), "roll": round(roll, 5),
              "n": len(cands), "candidates": rows, "chosen": chosen.a["id"], "rules_version": sim.rules_version}
    return {"char": c.id, "slot": slot, "cands": cands, "chosen": chosen, "T": T, "roll": roll, "trace": tr}
