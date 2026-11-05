"""Development: goals, skill decay, interest drift, confidence, habits and learned expectations.

Goals are generated from circumstances (interests, upcoming tryouts, crushes, grudges, GPA,
loneliness), held with a priority, advanced by the actions listed in goals.json, and closed as
achieved, failed or abandoned. A goal only changes behavior through the 'goal' utility term.
"""
from __future__ import annotations

from .history import Effects
from .rng import clamp
from . import sports
from .social import grudge_score, is_friend


def add_goal(sim, c, gtype, target, target_label, priority, skill=None, deadline=None, fx=None, cause=None, note=None):
    w = sim.w
    for g in c.goals:
        if g["status"] == "active" and g["type"] == gtype and g.get("target") == target and g.get("skill") == skill:
            g["priority"] = max(g["priority"], priority)
            return g
    active = [g for g in c.goals if g["status"] == "active"]
    if len(active) >= w.rules["dev.max_goals"]:
        weakest = min(active, key=lambda g: g["priority"])
        if weakest["priority"] >= priority:
            return None
        weakest["status"] = "abandoned"
        weakest["closed"] = w.day
    label = sim.cat.goals[gtype]["label"].replace("{target}", target_label or "")
    if note == "retry":
        label = f"Make {target_label} next time"
    g = {"id": f"g{w.next_id('goal')}", "type": gtype, "target": target, "skill": skill, "label": label,
         "priority": round(clamp(priority, 5, 100), 1), "status": "active", "created": w.day, "deadline": deadline,
         "closed": None, "origin": cause.get("id") if cause else None, "note": note,
         "start_skill": c.skills.get(skill, 0) if skill else None}
    c.goals.append(g)
    if len(c.goals) > 30:
        c.goals = [x for x in c.goals if x["status"] == "active"] + [x for x in c.goals if x["status"] != "active"][-20:]
    if c.role == "student" and priority >= 45:
        ev = sim.new_event("goal", "created", [c.id], [target] if target in w.chars else [], 10 if priority < 70 else 18,
                           {"label": label, "goal": g["id"], "priority": g["priority"]})
        if cause and cause.get("id"):
            ev["causes"] = [cause["id"]]
        sim.finish(ev, Effects(w, ev))
    return g


def review_goals(sim, c, rng):
    """Weekly: close finished goals, decay stale ones, generate new ones from circumstances."""
    w, R = sim.w, sim.w.rules
    day = w.day
    for g in c.goals:
        if g["status"] != "active":
            continue
        t = g["type"]
        tgt = g.get("target")
        age = day - g["created"]
        status = None
        if t == "make_group":
            if tgt in c.memberships:
                status = "achieved"
            elif age > 200:
                status = "abandoned"
        elif t == "improve_skill":
            if c.skills.get(g["skill"], 0) >= (g.get("start_skill") or 0) + 8:
                status = "achieved"
            elif age > 150:
                status = "abandoned"
        elif t == "befriend":
            r = w.rels.get((c.id, tgt))
            if r and is_friend(r, R):
                status = "achieved"
            elif age > 90 or tgt not in w.chars or w.chars[tgt].status != "active":
                status = "abandoned"
        elif t == "romance":
            if c.flags.get("partner") == tgt:
                status = "achieved"
            else:
                r = w.rels.get((c.id, tgt))
                if age > 120 or (r and not r.crush) or (tgt in w.chars and w.chars[tgt].flags.get("partner")):
                    status = "abandoned"
        elif t == "grades":
            if c.gpa >= g.get("deadline_target", 0) and age > 14:
                status = "achieved"
            elif age > 160:
                status = "abandoned"
        elif t == "popularity":
            if c.popularity >= 62:
                status = "achieved"
            elif age > 150:
                status = "abandoned"
        elif t == "get_even":
            r = w.rels.get((c.id, tgt))
            hurt = tgt in w.chars and any(c.id in m["with"] and m["valence"] < 0 and m["day"] >= g["created"]
                                          for m in w.chars[tgt].memories[-20:])
            if hurt:
                status = "achieved"
            elif not r or grudge_score(w, r, day) < 15 or age > 90:
                status = "abandoned"
        elif t == "make_amends":
            if age > 45:
                status = "abandoned"
        elif t == "belonging":
            if friend_count(w, c) >= 2:
                status = "achieved"
            elif age > 120:
                status = "abandoned"
        elif t == "earn_money":
            if any(w.groups[m]["kind"] == "job" for m in c.memberships) or c.money >= 120:
                status = "achieved"
            elif age > 120:
                status = "abandoned"
        elif t == "win_election":
            if g.get("deadline") is not None and day > g["deadline"] + 1:
                status = "abandoned"
        if status is None:
            g["priority"] = round(g["priority"] - 1.0, 1)
            if g["priority"] < 15:
                status = "abandoned"
        if status:
            g["status"] = status
            g["closed"] = day
            if c.role == "student" and status in ("achieved", "abandoned") and g["priority"] >= 30:
                imp = {"befriend": 14, "belonging": 16, "earn_money": 14}.get(t, 28) if status == "achieved" else 10
                ev = sim.new_event("goal", status, [c.id], [tgt] if tgt in w.chars else [], imp,
                                   {"label": g["label"], "goal": g["id"]})
                fx = Effects(w, ev)
                if status == "achieved":
                    fx.mood(c.id, 6, "achieved a goal")
                    sim.confidence(c.id, 1.0, fx, "achieved a goal")
                    c.achievements.append({"day": day, "label": g["label"], "event": None})
                sim.finish(ev, fx)
    if c.role != "student" or c.status != "active":
        return
    for gtype, target, label, prio, skill, deadline in generate(sim, c, rng):
        g = add_goal(sim, c, gtype, target, label, prio, skill=skill, deadline=deadline)
        if g is not None and gtype == "grades":
            g["deadline_target"] = deadline


def friend_count(w, c) -> int:
    R = w.rules
    n = 0
    for oid, r in w.out.get(c.id, {}).items():
        if r.affection >= R["rel.friend_threshold"] and w.chars[oid].role in ("student", "alumni"):
            n += 1
    return n


def generate(sim, c, rng):
    w, R = sim.w, sim.w.rules
    tr, mo = c.traits, c.motives
    out = []
    have = {(g["type"], g.get("target")) for g in c.goals if g["status"] == "active"
            or (g.get("closed") is not None and w.day - g["closed"] < 60)}
    cut_before = {t for m in c.memories if m["kind"] == "cut_from_team" for t in m.get("tags", [])}
    for it in sim.upcoming:
        if it["kind"] not in ("tryout", "audition") or it["day"] - w.day > 60 or it["day"] < w.day:
            continue
        g = w.groups[it["group"]]
        if g["id"] in c.memberships:
            continue
        if g["kind"] == "team" and (not sports.can_play(c, g) or sports.clash(w, c, g)):
            continue  # the other side's team, or a second sport the same season
        iv = c.interests.get(g["skill"], 0)
        if iv < 55:
            continue
        if g["kind"] == "team" and any(o is not g and o["kind"] == "team" and o.get("school") == g.get("school") and sports.can_play(c, o)
                                       and sports.seasons_overlap(o, g) and c.interests.get(o["skill"], 0) > iv
                                       and any(i.get("group") == o["id"] and i["kind"] == "tryout" and i["day"] >= w.day for i in sim.upcoming)
                                       for o in w.groups.values()):
            continue  # one goal a season: the sport they like more
        pr = 0.45 * iv + 0.25 * tr["ambition"] + 0.2 * tr["competitiveness"]
        if g["id"] in cut_before or (g["kind"] == "team" and "backstory" in {t for m in c.memories for t in m.get("tags", [])}
                                     and any(m["kind"] == "cut_from_team" for m in c.memories)):
            pr += 15 * (tr["discipline"] + tr["competitiveness"]) / 150
        if ("make_group", g["id"]) not in have:
            out.append(("make_group", g["id"], g["name"] if g["kind"] == "team" else it["production_name"], pr, g["skill"], it["day"]))
    for sid in sorted(c.interests):
        if sid in sim.cat.skills and sid != "academics":
            iv = c.interests[sid]
            if iv >= 62 and c.skills.get(sid, 0) < 45 and ("improve_skill", None) not in have:
                out.append(("improve_skill", None, sim.cat.skills[sid]["label"].lower(), (iv + mo["mastery"]) / 2 * 0.85, sid, None))
                break
    best_b, best_bs = None, 0
    for oid, r in w.out.get(c.id, {}).items():
        o = w.chars[oid]
        if o.role != "student" or o.status != "active":
            continue
        if 12 <= r.affection < R["rel.friend_threshold"] and r.familiarity >= 25:
            s = 0.4 * mo["belonging"] + 0.3 * mo["approval"] * o.popularity / 100 + 0.3 * r.affection
            if s > best_bs:
                best_b, best_bs = oid, s
        if r.crush and ("romance", oid) not in have and not c.flags.get("partner"):
            out.append(("romance", oid, o.name, r.attraction * 0.6 + mo["pleasure"] * 0.2, None, None))
        g = grudge_score(w, r, w.day)
        if g >= 40 and tr["empathy"] < 50 and ("get_even", oid) not in have:
            out.append(("get_even", oid, o.name, g * 0.5 + (50 - tr["empathy"]) * 0.5, None, None))
    if best_b and ("befriend", best_b) not in have:
        out.append(("befriend", best_b, w.chars[best_b].name, best_bs, None, None))
    for m in c.memories[-15:]:
        if m["kind"] in ("argument", "falling_out") and w.day - m["day"] <= 30 and tr["empathy"] + tr["loyalty"] >= 100:
            for oid in m["with"]:
                r = w.rels.get((c.id, oid))
                if r and r.peak_affection >= R["rel.friend_threshold"] and ("make_amends", oid) not in have:
                    out.append(("make_amends", oid, w.chars[oid].name, (tr["empathy"] + tr["loyalty"]) / 2 * 0.75, None, None))
    standard = 1.5 + tr["ambition"] * 0.025
    h = w.households.get(c.household_id)
    if h:
        standard = max(standard, 1.4 + h["expectations"] * 0.02)
    if c.gpa < standard - 0.15 and ("grades", None) not in have:
        out.append(("grades", None, "", mo["achievement"] * 0.5 + (h["expectations"] if h else 50) * 0.25, None, round(min(4.0, standard), 2)))
    if mo["approval"] >= 65 and c.popularity < 50 and ("popularity", None) not in have:
        out.append(("popularity", None, "", mo["approval"] * 0.65, None, None))
    if friend_count(w, c) < 2 and mo["belonging"] >= 45 and ("belonging", None) not in have:
        out.append(("belonging", None, "", mo["belonging"] * 0.8, None, None))
    if c.money < 25 and c.age(w.day) >= 15 and not any(w.groups[m]["kind"] == "job" for m in c.memberships) \
            and (mo["pleasure"] >= 50 or tr["ambition"] >= 60) and ("earn_money", None) not in have:
        out.append(("earn_money", None, "", 42.0, None, None))
    out = [o for o in out if o[3] >= 35]
    out.sort(key=lambda o: (-o[3], o[0], str(o[1])))
    return out[:2]


def weekly(sim, rng):
    """Skill decay, interest drift toward friends, decay of counters/habits."""
    w, R = sim.w, sim.w.rules
    fx = Effects(w, None)
    for c in sorted(w.active(), key=lambda c: c.id):
        for sk, v in list(c.skills.items()):
            used = c.counters.get("skillpractice:" + sk, 0)
            if sk != "academics" and used < 0.5 and v > 5:
                fx.skill(c.id, sk, -0.5 * R["dev.skill_decay"] * v / 100, "out of practice")
        for k in list(c.counters):
            if k.startswith("skillpractice:"):
                c.counters[k] = round(c.counters[k] * 0.85, 3)
        for k in list(c.habits):
            c.habits[k] = round(c.habits[k] * 0.85, 4)
            if c.habits[k] < 0.02:
                del c.habits[k]
        if c.role == "student":
            cl = w.cliques.get(c.flags.get("clique") or "")
            if cl and cl.get("active"):
                k = R["decision.conformity_weight"] * c.motives["belonging"] / 100 * 0.06
                for key, mean in cl.get("interests", []):
                    cur = c.interests.get(key, 0)
                    fx.interest(c.id, key, (mean - cur) * k, "friends are into it")
        # traits drift a little toward recent experience: confidence recovers toward its own baseline slowly
        base = c.flags.get("confidence_base")
        if base is None:
            c.flags["confidence_base"] = c.traits["confidence"]
        else:
            fx.trait(c.id, "confidence", (base - c.traits["confidence"]) * 0.03, "settling")
