"""Institutions: the school day, groups, and every collective event.

Collective events resolve after individual actions in a slot: lunch tables, practices and
meetings, tryouts and auditions (results post the next morning), games, shows, dances,
parties, elections. Scheduled calendar items (exams, report cards, graduation) and the
school-year rollover live here too. Selection decisions (coaches, directors, employers,
voters) are computed from their own traits and relationships and recorded in ev['calc'].
"""
from __future__ import annotations

from . import calendar as calm
from . import social, sports
from .actions import hear_rumor, skill_gain, start_dating
from .history import Effects
from .rng import clamp, sigmoid
from .social import is_friend, make_rumor
from .worldgen import compatibility


def ambient(sim, fx, a, b, q, kind):
    """A light two-way contact (sharing a table, a practice, a party)."""
    w, R = sim.w, sim.w.rules
    gain = R["rel.affection_gain"]
    for x, y in ((a, b), (b, a)):
        r = w.ensure_rel(x, y, w.day)
        d = 3.5 * q * gain
        d *= (1 - max(0.0, r.affection) / 130) if d > 0 else 1.0
        fx.rel(x, y, "affection", d, kind)
        fx.rel(x, y, "familiarity", 3 * (1 - r.familiarity / 120), kind)
        if q > 0:
            fx.rel(x, y, "trust", 0.8 * q, kind)
        X, Y = w.chars[x], w.chars[y]
        if social.romance_ok(w, x, y):
            from .worldgen import chemistry
            chem = chemistry(w, x, y) * R["romance.chemistry_spread"]
            fx.rel(x, y, "attraction", 0.5 * R["romance.attraction_rate"] * (chem * 0.8 + 0.1 + q * 0.3) * (1 - r.attraction / 110), kind)
        ryx = w.ensure_rel(y, x, w.day)
        fx.rel(x, y, "perceived", 0.15 * (ryx.affection + (X.traits["confidence"] - 50) * 0.3 - r.perceived), kind)
        fx.touch(x, y, kind, q)


def mark(g, cid, attended: bool, window: int = 8):
    """Rolling attendance record: the last `window` sessions, 1 = missed."""
    rec = g["absences"].get(cid)
    if not isinstance(rec, list):
        rec = []
    rec.append(0 if attended else 1)
    del rec[:-window]
    g["absences"][cid] = rec


def misses(g, cid) -> int:
    rec = g["absences"].get(cid)
    return sum(rec) if isinstance(rec, list) else 0


class Institutions:
    def __init__(self, sim):
        self.sim = sim

    # --- helpers --------------------------------------------------------------
    def event(self, etype, outcome, actors, targets=None, importance=5, group=None, data=None, involved=None):
        return self.sim.new_event(etype, outcome, actors, targets or [], importance, data or {}, group=group,
                                  involved=involved)

    def practices_today(self) -> list:
        w = self.sim.w
        if not calm.is_school_day(w.day, self.sim.cat.world["calendar"]):
            return []
        wd = calm.weekday(w.day)
        out = []
        for g in w.groups.values():
            if not g["members"] or wd not in g.get("practice_days", []):
                continue
            if g["kind"] == "team" and not self.in_season(g):
                continue
            if g["kind"] == "production" and not g.get("production"):
                continue
            if g["kind"] == "job":
                continue
            out.append(g["id"])
        return sorted(out)

    def in_season(self, g) -> bool:
        w = self.sim.w
        y = calm.school_year_of(w.day)
        a = calm.md_to_day(y, g["season"]["start"])
        b = calm.md_to_day(y, g["season"]["end"])
        return a <= w.day <= b

    def opportunities(self, c):
        """Open sign-ups for this character right now."""
        w = self.sim.w
        out = []
        if c.role not in ("student", "alumni") or c.location == "away":
            return out
        for g in sorted(w.groups.values(), key=lambda g: g["id"]):
            if g["id"] in c.memberships:
                continue
            gs, gl = g.get("school"), g.get("location")
            if gs is not None and gs != c.school:
                continue
            if gs is None and gl is not None and gl != c.location:
                continue
            if g.get("adult") and c.role != "alumni":
                continue
            if c.role == "alumni" and not g.get("adult") and g["kind"] != "job":
                continue
            if g["selection"] == "open":
                if len(g["members"]) < g["capacity"]:
                    out.append((g["id"], None, f"{g['name']} is open to anyone"))
            elif g["selection"] == "hire":
                if c.age(w.day) >= g.get("min_age", 15) and not any(w.groups[m]["kind"] == "job" for m in c.memberships) \
                        and len(g["members"]) < g["capacity"] and w.day - c.flags.get("applied_" + g["id"], -999) > 30:
                    out.append((g["id"], None, f"{g['name']} is hiring"))
        for it in self.sim.upcoming:
            if it["kind"] in ("tryout", "audition", "election") and it.get("signup_from", 0) <= w.day < it["day"] + (1 if it["kind"] != "election" else 0):
                if it["kind"] == "election" and w.day >= it["day"]:
                    continue
                if c.id in w.registrations.get(it["key"], []):
                    continue
                g = w.groups[it["group"]]
                if it["kind"] == "tryout" and g["id"] in c.memberships:
                    continue
                if g.get("school") != c.school:
                    continue
                if g["kind"] == "team" and (not sports.can_play(c, g) or sports.clash(w, c, g)):
                    continue  # boys' and girls' teams; one sport a season
                if c.school == "college" and g["kind"] == "team" and c.path.get("sport") and g["skill"] != c.path["sport"]:
                    continue
                out.append((g["id"], it, f"{it['name']} on {calm.label(it['day'])}"))
        return out

    # --- the school day ---------------------------------------------------------
    def classes(self, rng):
        sim = self.sim
        w, R = sim.w, sim.w.rules
        studs = sorted((c for c in w.students() if c.location != "away" and c.school in ("hchs", "college")), key=lambda c: c.id)
        ev = self.event("classes", "day", [], importance=1, data={"n": len(studs)})
        fx = Effects(w, ev)
        by_grade: dict = {}
        for c in studs:
            by_grade.setdefault((c.school, c.grade), []).append(c.id)
            g = skill_gain(sim, c, "academics", 0.12 * (0.6 + c.traits["discipline"] / 200) * (0.5 + c.needs["energy"] / 200))
            fx.skill(c.id, "academics", g, "class")
            c.study_ema += 0.15 + c.traits["discipline"] / 450  # homework done in study hall
            fx.need(c.id, "stress", R["needs.school_stress"] * (0.6 + c.traits["volatility"] / 125), "school day")
            load = sum(1.2 if w.groups[g]["kind"] in ("team", "production") else 0.6 for g in c.memberships)
            if load:
                fx.need(c.id, "stress", load, "juggling commitments")
            fx.need(c.id, "energy", -8, "school day")
            fx.need(c.id, "social", 4, "around people at school")
        k = int(R["rel.class_contacts"])
        for grade, ids in sorted(by_grade.items()):
            for cid in ids:
                for _ in range(k):
                    o = ids[int(rng.random() * len(ids))]
                    if o == cid:
                        continue
                    A, B = w.chars[cid], w.chars[o]
                    q = 0.1 + 0.3 * compatibility(w, A, B) + rng.gauss(0, 0.25)
                    for x, y in ((cid, o), (o, cid)):
                        r = w.ensure_rel(x, y, w.day)
                        fx.rel(x, y, "familiarity", 2.2 * (1 - r.familiarity / 110), "classmates")
                        fx.rel(x, y, "affection", 1.2 * q * R["rel.affection_gain"], "classmates")
                        r.last_day = w.day
        sim.finish(ev, fx)
        for it in sim.today("classes"):
            if it["kind"] == "exam":
                self.exam(it, rng)
            elif it["kind"] == "report_card":
                self.report_cards(it, rng)

    def exam(self, it, rng):
        sim = self.sim
        w, R = sim.w, sim.w.rules
        school = it.get("school", "hchs")
        studs = sorted((c for c in w.students() if c.school == school and c.location != "away"), key=lambda c: c.id)
        if not studs:
            return
        major = it["weight"] >= 2
        ev = self.event("exam", "held", [c.id for c in studs] if major else [], importance=8 if major else 3,
                        data={"event": it["name"], "weight": it["weight"]})
        fx = Effects(w, ev)
        scores = {}
        for c in studs:
            terms = [("baseline", 81.0), ("academic skill", 0.35 * (c.skills.get("academics", 0) - 50)),
                     ("academic aptitude", 0.25 * (c.aptitudes["academic"] - 50)),
                     ("recent studying", 12 * min(1.5, c.study_ema / 5) * R["inst.study_effect"]),
                     ("difficulty", -(R["inst.exam_difficulty"] - 50) * 0.4), ("mood", (c.mood - 50) * 0.1),
                     ("stress", -max(0.0, c.needs["stress"] - 55) * 0.25), ("luck", rng.gauss(0, 7))]
            if school == "college":
                terms.append(("college coursework", -3.0))
            s = clamp(sum(t[1] for t in terms), 0, 100)
            from . import classes
            played = classes.blend_exam(c, w.day, s)
            if played:  # you took this one yourself: your round counts, blended with your preparation
                s, terms = played[0], terms + [("(you played it) " + t[0], t[1]) for t in played[1]]
                qp = c.flags.get("quiz_played") or {}
                classes.record(w, qp.get("class") or "all", qp.get("pct", 0), it["name"])
            scores[c.id] = round(s, 1)
            gp = clamp((s - 50) / 10, 0.0, 4.0)
            wt = 0.08 * it["weight"]
            fx.scalar(c.id, "gpa", round(c.gpa * (1 - wt) + min(4.0, gp) * wt, 3), it["name"])
            expected = 60 + c.traits["ambition"] * 0.3
            d = (s - expected) / 10
            fx.mood(c.id, d * (1.5 if major else 0.7), it["name"])
            fx.need(c.id, "stress", -d * (1.5 if major else 0.6) + (3 if major else 0), it["name"])
            if major and (s >= 92 or s <= 58):
                aced = s >= 92
                e2 = self.event("exam", "aced" if aced else "bombed", [c.id], importance=18,
                                data={"event": it["name"], "score": f"{s:.0f}"})
                e2["causes"] = [ev["id"]] if ev.get("id") else []
                f2 = Effects(w, e2)
                e2["calc"] = [{"step": "exam score", "terms": [[t[0], round(t[1], 2)] for t in terms], "total": round(s, 1)}] if w.tracing else None
                f2.memory(c.id, "aced_exam" if aced else "bombed_exam", [], 0.5 if aced else -0.55, 45,
                          f"{'Aced' if aced else 'Bombed'} {it['name']} ({s:.0f})")
                if aced:
                    f2.rep(c.id, "brain", 3, "aced an exam")
                sim.confidence(c.id, 1.0 if aced else -1.0, f2, it["name"])
                sim.finish(e2, f2)
        if w.tracing:
            ev["data"]["scores"] = scores
            ev["data"]["average"] = round(sum(scores.values()) / max(1, len(scores)), 1)
        for c in studs:
            c.study_ema *= 0.6
        sim.finish(ev, fx)

    def report_cards(self, it, rng):
        from .households import report_card_reaction
        for c in sorted(self.sim.w.students(), key=lambda c: c.id):
            if c.school == "hchs":
                c.gpa_history.append([self.sim.w.day, round(c.gpa, 2)])
                report_card_reaction(self.sim, c, it, rng)

    # --- collective resolution after a slot ----------------------------------------------
    def after_slot(self, slot, rng):
        sim = self.sim
        if slot == "lunch":
            self.lunch_tables(rng)
            for it in sim.today("lunch"):
                if it["kind"] == "election":
                    self.election(it, rng)
        for gid in (sim.ctx_practices if slot in ("after_school",) else []):
            self.practice(gid, rng)
        for it in sim.today(slot):
            k = it["kind"]
            if k in ("tryout", "audition"):
                self.selection(it, rng)
            elif k == "game":
                self.game(it, rng)
            elif k == "show":
                self.show(it, rng)
            elif k == "dance":
                self.dance(it, rng)
        if slot == "evening":
            for key in sorted(k for k, p in sim.w.parties.items() if p["day"] == sim.w.day):
                self.party(key, rng)
        if slot in ("after_school", "day"):
            self.missed_shifts(rng)

    def lunch_tables(self, rng):
        sim = self.sim
        w, R = sim.w, sim.w.rules
        joins = sim.slot.tables
        if not joins:
            return
        planned = sim.slot.planned
        absent = {cid for cid, d in planned.items() if d and d["chosen"].a["id"] in ("sit_alone", "study_at_lunch")}
        parent: dict[str, str] = {}

        def find(x):
            while parent.setdefault(x, x) != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        joiners: dict[str, str] = {}
        size: dict[str, int] = {}
        for a, b in joins:
            if b in absent or w.chars[b].role != "student":
                continue
            ra, rb = find(a), find(b)
            if ra == rb:
                joiners[a] = b
                continue
            sa, sb = size.get(ra, 1), size.get(rb, 1)
            if sa + sb > 8:
                continue  # the table is full
            joiners[a] = b
            root, other = min(ra, rb), max(ra, rb)
            parent[other] = root
            size[root] = sa + sb
        tables: dict[str, list] = {}
        for x in list(parent):
            tables.setdefault(find(x), []).append(x)
        for root in sorted(tables):
            members = sorted(tables[root])
            excluded = []
            if len(members) >= 3:
                for m in list(members):
                    if m not in joiners:
                        continue
                    others = [o for o in members if o != m and o not in excluded]
                    if len(others) < 2:
                        continue
                    aff = [w.rels[(o, m)].affection if (o, m) in w.rels else 0.0 for o in others]
                    avg_aff = sum(aff) / len(aff)
                    if avg_aff >= 8:
                        continue
                    O = [w.chars[o] for o in others]
                    emp = sum(o.traits["empathy"] for o in O) / len(O)
                    pop = sum(o.popularity for o in O) / len(O)
                    appr = sum(o.motives["approval"] for o in O) / len(O) * R["motive.approval"]
                    tgt = joiners[m]
                    vouch = w.rels[(tgt, m)].affection if (tgt, m) in w.rels else 0.0
                    terms = [("how much the table likes them", -avg_aff / 25),
                             ("status gap x table's approval motive", (pop - w.chars[m].popularity) / 50 * appr / 100 * 1.5),
                             ("table's empathy", -(emp - 50) / 50),
                             (f"{w.chars[tgt].short} vouches for them", -max(0.0, vouch) / 40),
                             ("baseline", -1.6)]
                    x = sum(t[1] for t in terms) * R["social.exclusion_tendency"]
                    p = sigmoid(x * 1.5)
                    roll = rng.random()
                    if roll < p:
                        excluded.append(m)
                        self.exclusion(m, joiners[m], others, terms, p, roll, rng)
                members = [m for m in members if m not in excluded]
            if len(members) < 2:
                continue
            ev = self.event("lunch_table", "good", members, importance=4, data={"members": members})
            fx = Effects(w, ev)
            pairs = [(members[i], members[j]) for i in range(len(members)) for j in range(i + 1, len(members))]
            rng.shuffle(pairs)
            qs = []
            for a, b in pairs[:12]:
                q = 0.18 + 0.3 * compatibility(w, w.chars[a], w.chars[b]) + rng.gauss(0, 0.22)
                qs.append(q)
                ambient(sim, fx, a, b, q, "lunch table")
            avg = sum(qs) / len(qs)
            for m in members:
                fx.need(m, "social", 6 + 1.5 * min(len(members), 5), "lunch with friends")
                fx.need(m, "fun", 5, "lunch with friends")
                fx.mood(m, avg * 2, "lunch table")
                sim.expect(m, "sit_with", clamp(avg, -1, 1))
            ev["outcome"] = "great" if avg > 0.45 else "good" if avg > 0.05 else "flat"
            ev["data"]["quality"] = round(avg, 3)
            ev["calc"] = [{"step": "table mood", "total": round(avg, 3), "pairs": len(qs),
                           "rule": "average of pair qualities (0.18 + 0.3 x compatibility + luck)"}] if w.tracing else None
            sim.attach_traces(ev, [m for m in members if m in joiners])
            sim.finish(ev, fx)

    def exclusion(self, m, target, others, terms, p, roll, rng):
        sim = self.sim
        w = sim.w
        ev = self.event("exclusion", "excluded", [m], [target], importance=26, involved=others,
                        data={"table": others})
        fx = Effects(w, ev)
        ev["calc"] = [{"step": "does the table freeze them out?", "terms": [[t[0], round(t[1], 3)] for t in terms],
                       "p": round(p, 3), "roll": round(roll, 4), "outcome": "excluded",
                       "rule": "P = sigmoid(1.5 x total x exclusion tendency)"}] if w.tracing else None
        fx.mood(m, -9, "frozen out at lunch")
        fx.need(m, "stress", 8, "frozen out at lunch")
        fx.need(m, "social", -6, "frozen out at lunch")
        for o in others:
            fx.rel(m, o, "affection", -6, "froze them out")
            fx.rel(o, m, "familiarity", 1, "turned them away")
        fx.memory(m, "exclusion_by", others[:4], -0.65, 55, f"Got frozen out of {w.chars[target].short}'s lunch table")
        sim.expect(m, "sit_with", -0.6)
        seen = others[:3]
        make_rumor(sim, m, "excluded", f"{w.chars[m].name} tried to sit with {w.chars[target].name}'s table and got iced out",
                   True, -0.15, 0.45, None, seen, ev.get("id"), involves=[m, target])
        sim.attach_traces(ev, [m])
        sim.finish(ev, fx)

    def practice(self, gid, rng):
        sim = self.sim
        w, R = sim.w, sim.w.rules
        g = w.groups[gid]
        att = sorted(set(sim.slot.attend.get(("practice", gid), [])) & set(g["members"]))
        absent = sorted(set(g["members"]) - set(att))
        ev = self.event("practice", "session", att, importance=3, group=gid,
                        data={"group": g["name"], "n": len(att), "absent": absent})
        fx = Effects(w, ev)
        coach = g.get("staff")
        for cid in att:
            c = w.chars[cid]
            hurt = c.flags.get("injured_until", -1) >= w.day
            if g["kind"] == "team" and not hurt:
                fx.skill(cid, "fitness", skill_gain(sim, c, "fitness", 0.35), "team conditioning")
                if rng.random() < sports.INJURY_RATE.get(g["skill"], 0) * 0.15 * (1.35 - c.skills.get("fitness", 30) / 100):
                    sports.injure(self, cid, g["skill"], rng, ev, during="practice")
            if g.get("skill") and not hurt:
                focus = (0.7 + (c.traits["discipline"] - 50) / 100 * R["dev.discipline_focus"]) * (0.5 + c.needs["energy"] / 200)
                coach_q = 1.0 + ((w.chars[coach].traits["discipline"] - 50) / 250 if coach else 0)
                if g.get("school") == "college":
                    coach_q *= 1.8  # college programs: full-time coaches, strength staff, film, more reps
                fx.skill(cid, g["skill"], skill_gain(sim, c, g["skill"], 1.1 * max(0.2, focus) * coach_q), f"{g['name']} practice")
                c.counters["skillpractice:" + g["skill"]] = c.counters.get("skillpractice:" + g["skill"], 0) + 1
                fx.interest(cid, g["skill"], R["dev.interest_drift"] * 0.3, "practice")
            fx.need(cid, "energy", -10 if g["kind"] == "team" else -5, "practice")
            fx.need(cid, "social", 8, "practice")
            fx.need(cid, "fun", 4 + c.interests.get(g.get("skill") or "", 40) / 25, "practice")
            fx.need(cid, "stress", -2, "practice")
            if coach:
                fx.rel(coach, cid, "respect", 1.5, "showed up")
                fx.rel(coach, cid, "familiarity", 1.5, "practice")
            mark(g, cid, True)
        pairs = [(att[i], att[j]) for i in range(len(att)) for j in range(i + 1, len(att))]
        rng.shuffle(pairs)
        for a, b in pairs[:10]:
            q = 0.15 + 0.25 * compatibility(w, w.chars[a], w.chars[b]) + rng.gauss(0, 0.2)
            ambient(sim, fx, a, b, q, f"{g['name']} practice")
            if g["kind"] == "team" and g.get("skill"):
                A, B = w.chars[a], w.chars[b]
                if abs(A.skills.get(g["skill"], 0) - B.skills.get(g["skill"], 0)) < 8:
                    if A.traits["competitiveness"] > 60:
                        fx.rel(a, b, "rivalry", 1.5, "competing for minutes")
                    if B.traits["competitiveness"] > 60:
                        fx.rel(b, a, "rivalry", 1.5, "competing for minutes")
        tol = R["inst.absence_tolerance"]
        dropped = []
        elsewhere = {c for (what, key), ids in sim.slot.attend.items() if what in ("practice", "event", "shift") and key != gid
                     for c in ids}
        for cid in absent:
            if cid in elsewhere:
                continue  # excused: at another practice, tryout, game or shift
            mark(g, cid, False)
            if coach:
                fx.rel(coach, cid, "respect", -4, "missed practice")
            if g["kind"] in ("team", "production") and misses(g, cid) > tol:
                dropped.append((cid, "dropped"))
            elif g["kind"] == "club" and misses(g, cid) >= 7:
                dropped.append((cid, "drifted"))
        sim.attach_traces(ev, att)
        sim.finish(ev, fx)
        for cid, how in dropped:
            self.drop(gid, cid, how, ev, rng)

    def drop(self, gid, cid, how, cause, rng):
        sim = self.sim
        w = sim.w
        g = w.groups[gid]
        ev = self.event("practice", how, [cid], importance=30 if how == "dropped" else 14, group=gid,
                        data={"group": g["name"], "absences": misses(g, cid),
                              "rule": f"missed {misses(g, cid)} of the last {len(g['absences'].get(cid) or [])} sessions"})
        if cause and cause.get("id"):
            ev["causes"] = [cause["id"]]
        fx = Effects(w, ev)
        fx.leave(cid, gid, "dropped for missed practices" if how == "dropped" else "stopped showing up")
        if how == "dropped":
            fx.mood(cid, -8, f"dropped from {g['name']}")
            fx.memory(cid, "dropped", [g["staff"]] if g.get("staff") else [], -0.6, 60, f"Got dropped from {g['name']}", tags=[gid])
            fx.rep(cid, "flaky", 6, "dropped from a team")
            sim.confidence(cid, -1.5, fx, "dropped")
            sim.schedule(w.day + 1, "parents_find_out", {"char": cid, "what": f"getting dropped from {g['name']}"}, ev.get("id"))
        sim.finish(ev, fx)
        if g["kind"] == "team" and how == "dropped":
            self.call_up(gid, ev, None, rng)

    def call_up(self, gid, cause, fx_unused, rng):
        sim = self.sim
        w = sim.w
        g = w.groups[gid]
        if g["kind"] != "team" or not self.in_season(g) or len(g["members"]) >= g["capacity"]:
            return
        for entry in sorted(g["cut"], key=lambda e: -e[1]):
            cid = entry[0]
            c = w.chars.get(cid)
            if c is None or c.status != "active" or c.role != "student" or gid in c.memberships:
                continue
            if c.interests.get(g["skill"], 0) < 40 or not sports.can_play(c, g) or sports.clash(w, c, g):
                continue
            g["cut"] = [e for e in g["cut"] if e[0] != cid]
            ev = self.event("practice", "called_up", [cid], importance=40, group=gid, data={"group": g["name"]})
            if cause and cause.get("id"):
                ev["causes"] = [cause["id"]]
            fx = Effects(w, ev)
            fx.join(cid, gid, "called up")
            g.setdefault("levels", {})[cid] = "varsity"
            sports.ensure_athlete(c, g["skill"], rng) if rng else None
            fx.mood(cid, 12, f"called up to {g['name']}")
            fx.memory(cid, "made_team", [g.get("staff")] if g.get("staff") else [], 0.85, 75, f"Got called up to {g['name']}", tags=[gid])
            sim.confidence(cid, 2.5, fx, "called up")
            for go in c.goals:
                if go["type"] == "make_group" and go.get("target") == gid and go["status"] in ("active", "failed"):
                    go["status"] = "achieved"
                    go["closed"] = w.day
            sim.finish(ev, fx)
            return

    # --- tryouts & auditions ---------------------------------------------------------
    def selection(self, it, rng):
        sim = self.sim
        w, R = sim.w, sim.w.rules
        g = w.groups[it["group"]]
        reg = list(w.registrations.get(it["key"], []))
        if g["kind"] == "team":
            reg = [cid for cid in reg if cid in w.chars and sports.can_play(w.chars[cid], g)]
        came = sorted(set(sim.slot.attend.get(("event", it["key"]), [])) & set(reg))
        noshow = sorted(set(reg) - set(came))
        coach = w.chars.get(g.get("staff"))
        ev = self.event("tryout", "held", came, importance=20, group=g["id"],
                        data={"group": g["name"], "n": len(came), "event": it.get("production_name", it["name"])})
        fx = Effects(w, ev)
        rows = []
        sk = g["skill"]
        apt_key = sim.cat.skills[sk]["aptitude"]
        wt = R["inst.coach_talent_weight"] * (0.6 + (coach.traits["competitiveness"] if coach else 50) / 250)
        we = R["inst.coach_effort_weight"] * (0.3 + (coach.traits["discipline"] if coach else 50) / 200)
        wf = R["inst.coach_favoritism"]
        is_team = g["kind"] == "team"
        for cid in came:
            c = w.chars[cid]
            if is_team:
                sports.ensure_athlete(c, sk, rng)
                perf = (sports.rating(c, sk) + 0.05 * (c.needs["energy"] - 60) - max(0.0, c.needs["stress"] - 60) * 0.3
                        + rng.gauss(0, 6))
            else:
                perf = (0.55 * c.skills.get(sk, 0) + 0.25 * c.aptitudes[apt_key] + 0.10 * c.traits["confidence"]
                        + 0.10 * c.needs["energy"] - max(0.0, c.needs["stress"] - 60) * 0.3 + rng.gauss(0, 8))
            effort = 0.5 * c.traits["discipline"] + min(50.0, c.counters.get("skillpractice:" + sk, 0) * 4)
            fav = wf * ((w.rels[(coach.id, cid)].affection + w.rels[(coach.id, cid)].respect * 0.5) / 100 * 20
                        if coach and (coach.id, cid) in w.rels else 0)
            sen = ((c.grade or 9) - 9) * (3 if is_team else 2)
            if c.flags.get("injured_until", -1) >= w.day:
                perf -= 25
            if g.get("school") == "college" and c.path.get("scholarship") and c.path.get("sport") == sk:
                sen += 40  # recruited: the roster spot is theirs to lose
            score = wt * perf + we * effort * 0.6 + fav + sen
            rows.append({"char": cid, "performance": round(perf, 1), "effort": round(effort, 1), "favor": round(fav, 1),
                         "seniority": sen, "score": round(score, 2)})
            fx.need(cid, "stress", 6, "tryout nerves")
            fx.need(cid, "energy", -10, "tryout")
        rows.sort(key=lambda r: (-r["score"], r["char"]))
        cap = g["capacity"]
        jv_cap = g.get("jv_capacity", 0)
        jv_used = 0
        for i, r in enumerate(rows):
            r["made"] = i < cap
            r["level"] = "varsity" if i < cap else None
            if not r["made"] and jv_used < jv_cap and (w.chars[r["char"]].grade or 12) <= 11:
                r["made"] = True
                r["level"] = "jv"
                jv_used += 1
        ev["calc"] = [{"step": f"{coach.name if coach else 'Selection'}'s evaluation",
                       "weights": {"talent": round(wt, 3), "effort": round(we * 0.6, 3), "favoritism": wf,
                                   "coach_competitiveness": coach.traits["competitiveness"] if coach else None,
                                   "coach_discipline": coach.traits["discipline"] if coach else None},
                       "rule": f"score = talent x performance + effort weight x effort + favoritism + seniority; top {cap} make it"
                               + (f", the next {jv_cap} (grades 9-11) make JV" if jv_cap else ""),
                       "rows": rows}] if w.tracing else None
        ev["data"]["rows"] = rows
        for cid in noshow:
            e2 = self.event("tryout", "no_show", [cid], importance=16, group=g["id"], data={"group": g["name"]})
            f2 = Effects(w, e2)
            f2.memory(cid, "no_show", [], -0.35, 40, f"Signed up for {it['name']} and didn't go", tags=[g["id"]])
            f2.interest(cid, sk, -5 * R["dev.interest_drift"], "lost nerve")
            for go in w.chars[cid].goals:
                if go["type"] == "make_group" and go.get("target") == g["id"] and go["status"] == "active":
                    go["status"] = "failed"
                    go["closed"] = w.day
            sim.finish(e2, f2)
        sim.attach_traces(ev, came)
        sim.finish(ev, fx)
        w.registrations.pop(it["key"], None)
        sim.schedule(w.day + 1, "selection_results", {"item": it, "rows": rows}, ev.get("id"))

    def selection_results(self, payload, cause_id, rng):
        sim = self.sim
        w, R = sim.w, sim.w.rules
        it = payload["item"]
        rows = payload["rows"]
        g = w.groups[it["group"]]
        sk = g["skill"]
        is_prod = g["kind"] == "production"
        if is_prod:
            for m in list(g["members"]):
                fx0 = Effects(w, None)
                fx0.leave(m, g["id"], "new production")
            g["production"] = {"id": it["production"], "name": it["production_name"], "cast": [], "lead": None,
                               "show_key": it["key"].replace("audition", "show")}
        else:
            g["cut"] = []
            g["absences"] = {}
        made = [r for r in rows if r["made"]]
        for i, r in enumerate(rows):
            cid = r["char"]
            c = w.chars.get(cid)
            if c is None or c.status != "active":
                continue
            lead = is_prod and i == 0
            if r["made"]:
                out = "lead" if lead else "made"
                etype = "audition" if is_prod else "tryout"
                lvl = r.get("level") or "varsity"
                ev = self.event(etype, out, [cid], importance=(45 if lead else 34) if lvl == "varsity" else 26, group=g["id"],
                                data={"group": g["name"], "event": it.get("production_name", it["name"]), "score": r["score"],
                                      "level": lvl})
                if g["kind"] == "team":
                    ev["text"] = f"{c.short} made {g['name']}" + (" (JV)." if lvl == "jv" else " varsity!")
            else:
                ev = self.event("audition" if is_prod else "tryout", "cut", [cid], importance=36, group=g["id"],
                                data={"group": g["name"], "event": it.get("production_name", it["name"]), "score": r["score"]})
            ev["causes"] = [cause_id] if cause_id else []
            ev["calc"] = [{"step": "selection", "row": r, "rank": i + 1, "capacity": g["capacity"]}] if w.tracing else None
            fx = Effects(w, ev)
            if r["made"]:
                fx.join(cid, g["id"], "made the cut")
                if g["kind"] == "team":
                    g.setdefault("levels", {})[cid] = r.get("level") or "varsity"
                    sports.ensure_athlete(c, sk, rng)
                if is_prod:
                    g["production"]["cast"].append(cid)
                    if lead:
                        g["production"]["lead"] = cid
                fx.mood(cid, 10, "made it")
                fx.interest(cid, sk, 3, "made it")
                sim.confidence(cid, 2.0, fx, "made it")
                fx.rep(cid, "athlete" if g["kind"] == "team" else "performer", 5, f"made {g['name']}")
                fx.memory(cid, "made_team", [g.get("staff")] if g.get("staff") else [], 0.8, 70,
                          f"Made {g['name'] if not is_prod else it['production_name']}" + (" (the lead)" if lead else ""), tags=[g["id"]])
                for go in c.goals:
                    if go["type"] == "make_group" and go.get("target") == g["id"] and go["status"] == "active":
                        go["status"] = "achieved"
                        go["closed"] = w.day
            else:
                g["cut"].append([cid, r["score"]])
                sim.moment_trigger("cut", cid, {"group": g["id"]})
                fx.mood(cid, -10, "cut")
                fx.need(cid, "stress", 8, "cut")
                sim.confidence(cid, -2.5 * (0.5 + c.traits["volatility"] / 100), fx, "cut")
                fx.memory(cid, "cut_from_team", [g.get("staff")] if g.get("staff") else [], -0.75, 65,
                          f"Got cut from {g['name'] if not is_prod else it['production_name']}", tags=[g["id"]])
                resolve_terms = [("competitiveness", c.traits["competitiveness"] / 3), ("discipline", c.traits["discipline"] / 3),
                                 ("ambition", c.traits["ambition"] / 3), ("volatility", -c.traits["volatility"] / 3),
                                 ("confidence", c.traits["confidence"] / 4)]
                resolve = sum(t[1] for t in resolve_terms)
                bounce = resolve >= 48
                if w.tracing:
                    ev["calc"].append({"step": "how they respond to being cut", "terms": [[t[0], round(t[1], 2)] for t in resolve_terms],
                                       "total": round(resolve, 2), "outcome": "doubles down" if bounce else "loses interest",
                                       "rule": "doubles down if resolve >= 48"})
                for go in c.goals:
                    if go["type"] == "make_group" and go.get("target") == g["id"] and go["status"] == "active":
                        go["status"] = "failed"
                        go["closed"] = w.day
                if bounce:
                    sim.add_goal(c, "improve_skill", None, sim.cat.skills[sk]["label"].lower(), 72, skill=sk, fx=fx, cause=ev)
                    if not is_prod:
                        sim.add_goal(c, "make_group", g["id"], g["name"], 75, skill=sk, fx=fx, cause=ev, note="retry")
                    fx.interest(cid, sk, 2, "wants to prove them wrong")
                else:
                    fx.interest(cid, sk, -10 * R["dev.interest_drift"], "discouraged")
            sim.finish(ev, fx)
        if g["kind"] == "team":
            self.walk_ons(g, rng)
        if g["kind"] == "team" and made:
            varsity = [r for r in made if r.get("level", "varsity") == "varsity"]
            cands = sorted([r for r in varsity if (w.chars[r["char"]].grade or 0) >= 11], key=lambda r: -r["score"]) or varsity
            if cands:
                g["leaders"] = [cands[0]["char"]]
                cap_c = w.chars[cands[0]["char"]]
                e4 = self.event("tryout", "captain", [cap_c.id], importance=34, group=g["id"], data={"group": g["name"]})
                e4["text"] = f"{cap_c.short} was named captain of {g['name']}."
                f4 = Effects(w, e4)
                f4.rep(cap_c.id, "leader", 5, "named captain")
                f4.memory(cap_c.id, "captain", [], 0.8, 70, f"Named captain of {g['name']}")
                cap_c.achievements.append({"day": w.day, "label": f"Captain, {g['name']}", "event": None})
                sim.finish(e4, f4)
        if made:
            for i in range(len(made)):
                for j in range(i + 1, len(made)):
                    a, b = made[i]["char"], made[j]["char"]
                    fx2 = Effects(w, None)
                    fx2.add_bond(a, b, f"teammate:{g['id']}")

    def walk_ons(self, g, rng):
        """Small schools: a coach short of a lineup talks interested students into joining."""
        sim = self.sim
        w = sim.w
        need = g.get("starters", 5) + 3 - len(g["members"])
        if need <= 0:
            return
        sk = g["skill"]

        def free(c):
            return (c.school == g.get("school", "hchs") and g["id"] not in c.memberships and c.flags.get("injured_until", -1) < w.day
                    and sports.can_play(c, g) and not sports.clash(w, c, g)
                    and not (g.get("school") == "college" and (c.path or {}).get("sport") and c.path["sport"] != sk)
                    and not any(w.groups[m]["kind"] == "team" and self.in_season(w.groups[m]) for m in c.memberships))
        pool = sorted((c for c in w.students() if c.interests.get(sk, 0) >= 30 and free(c)),
                      key=lambda c: (-(sports.rating(c, sk) + c.interests.get(sk, 0) * 0.3), c.id))[:need]
        short = g.get("starters", 5) - len(g["members"]) - len(pool)
        if short > 0 and g.get("school") != "college":
            # still not enough for a lineup: the coach works the hallways for athletic kids who aren't playing anything now
            taken = {c.id for c in pool}
            extra = sorted((c for c in w.students() if c.id not in taken and free(c) and c.id != w.meta.get("protagonist")
                            and (c.aptitudes.get("athletic", 50) >= 58 or max((c.interests.get(s, 0) for s in sports.SPORTS), default=0) >= 45)),
                           key=lambda c: (-(c.aptitudes.get("athletic", 50) + c.interests.get(sk, 0) * 0.5), c.id))
            pool += extra[:short]
        for c in pool:
            ev = self.event("tryout", "walk_on", [c.id], importance=24, group=g["id"], data={"group": g["name"]})
            ev["text"] = f"{w.chars[g['staff']].short if g.get('staff') in w.chars else 'The coach'} talked {c.short} into joining {g['name']}."
            fx = Effects(w, ev)
            fx.interest(c.id, sk, max(0.0, 32 - c.interests.get(sk, 0)), "talked into it")
            fx.join(c.id, g["id"], "walked on")
            g.setdefault("levels", {})[c.id] = "varsity" if (c.grade or 9) >= 11 or not g.get("jv_capacity") else "jv"
            sports.ensure_athlete(c, sk, rng)
            sim.finish(ev, fx)

    def game(self, it, rng):
        if self.sim.w.groups[it["group"]].get("levels") is not None or self.sim.w.groups[it["group"]]["kind"] == "team":
            return sports.play_game(self, it, rng)
        sim = self.sim
        w = sim.w
        g = w.groups[it["group"]]
        players = sorted(set(sim.slot.attend.get(("event", it["key"]), [])) & set(g["members"]))
        missing = sorted(set(g["members"]) - set(players))
        fans = sorted(set(sim.slot.attend.get(("spectate", it["key"]), [])))
        if not g["members"]:
            return
        sk = g["skill"]
        perf = {}
        for cid in players:
            c = w.chars[cid]
            perf[cid] = 0.6 * c.skills.get(sk, 0) + 0.25 * c.aptitudes["athletic"] + 0.15 * c.needs["energy"] + rng.gauss(0, 6)
        top = sorted(perf.values(), reverse=True)[:max(5, len(players) // 2)]
        strength = sum(top) / len(top) if top else 20
        opp = 52 + rng.gauss(0, 9)
        margin = strength - opp + rng.gauss(0, 6) + (2 if fans else 0)
        win = margin > 0
        score = self.score_line(sk, margin, rng)
        ev = self.event("game", "win" if win else "loss", players, importance=14, group=g["id"], involved=fans,
                        data={"group": g["name"], "score": score, "fans": len(fans)})
        ev["calc"] = [{"step": "game result", "terms": [["team strength (avg of top players)", round(strength, 2)],
                                                         ["opponent strength", round(opp, 2)], ["home crowd", 2 if fans else 0]],
                       "total": round(margin, 2), "outcome": "win" if win else "loss",
                       "performances": {k: round(v, 1) for k, v in perf.items()}}] if w.tracing else None
        fx = Effects(w, ev)
        g["record"]["w" if win else "l"] += 1
        g["streak"] = g.get("streak", 0) + 1 if win and g.get("streak", 0) >= 0 else (1 if win else min(-1, g.get("streak", 0) - 1))
        for cid in players:
            fx.mood(cid, 6 if win else -4, "game")
            fx.need(cid, "energy", -14, "game")
            fx.need(cid, "fun", 10 if win else 3, "game")
            fx.rep(cid, "athlete", 1.0 if win else 0.4, "played")
        for i in range(len(players)):
            for j in range(i + 1, min(len(players), i + 4)):
                ambient(sim, fx, players[i], players[j], 0.3 if win else 0.05, f"{g['name']} game")
        for cid in fans:
            fx.need(cid, "social", 10, "watched the game")
            fx.need(cid, "fun", 9 if win else 5, "watched the game")
            for p_ in players:
                r = w.rels.get((cid, p_))
                if r and r.familiarity > 20:
                    fx.rel(cid, p_, "respect", 1.5 if win else 0.5, "watched them play")
        coach = g.get("staff")
        for cid in players:
            mark(g, cid, True)
        for cid in missing:
            mark(g, cid, False)
            if coach:
                fx.rel(coach, cid, "respect", -8, "missed a game")
        sim.attach_traces(ev, players + fans)
        sim.finish(ev, fx)
        if players:
            star = max(players, key=lambda k: (perf[k], k))
            if abs(margin) < 25:
                e2 = self.event("game", "star", [star], importance=26, group=g["id"], data={"group": g["name"], "score": score})
                e2["causes"] = [ev["id"]] if ev.get("id") else []
                f2 = Effects(w, e2)
                f2.rep(star, "star", 4, "standout game")
                f2.mood(star, 6, "standout game")
                sim.confidence(star, 1.0, f2, "standout game")
                if win:
                    f2.memory(star, "star_game", [], 0.55, 45, f"Carried {g['name']} to a {score} win")
                sim.finish(e2, f2)
        for cid in missing:
            if misses(g, cid) > w.rules["inst.absence_tolerance"] and cid in g["members"]:
                self.drop(g["id"], cid, "dropped", ev, rng)

    def score_line(self, sk, margin, rng):
        if sk == "basketball":
            base = 48 + int(rng.random() * 18)
            d = max(1, int(abs(margin) / 2.2) + 1)
            a, b = base + d, base
        elif sk in ("baseball", "softball"):
            base = int(rng.random() * 4)
            d = max(1, int(abs(margin) / 6) + 1)
            a, b = base + d, base
        elif sk == "soccer":
            base = int(rng.random() * 2.4)
            d = min(5, max(1, int(abs(margin) / 8) + 1))
            a, b = base + d, base
        else:
            base = int(rng.random() * 2)
            d = max(1, int(abs(margin) / 9) + 1)
            a, b = base + d, base
        return f"{a}-{b}" if margin > 0 else f"{b}-{a}"

    def show(self, it, rng):
        sim = self.sim
        w = sim.w
        g = w.groups[it["group"]]
        prod = g.get("production")
        if not prod or not prod.get("cast"):
            return
        cast = sorted(set(sim.slot.attend.get(("event", it["key"]), [])) & set(prod["cast"]))
        fans = sorted(set(sim.slot.attend.get(("spectate", it["key"]), [])))
        sk = g["skill"]
        q = (sum(w.chars[c].skills.get(sk, 0) for c in cast) / max(1, len(cast))) + rng.gauss(0, 7) - (len(prod["cast"]) - len(cast)) * 4
        label = "a triumph" if q >= 58 else "solid" if q >= 42 else "rough"
        ev = self.event("show", "performed", cast, importance=28, group=g["id"], involved=fans,
                        data={"group": g["name"], "event": prod["name"], "label": label, "fans": len(fans)})
        ev["calc"] = [{"step": "show quality", "total": round(q, 1), "outcome": label,
                       "rule": "average cast acting skill + luck - 4 per missing cast member; triumph >= 58, solid >= 42"}] if w.tracing else None
        fx = Effects(w, ev)
        for cid in cast:
            fx.mood(cid, 10 if label != "rough" else 2, "opening night")
            fx.rep(cid, "performer", 3 if label != "rough" else 1, "performed")
            fx.memory(cid, "performed", [], 0.6 if label != "rough" else 0.1, 50, f"Performed in {prod['name']} ({label})", tags=[g["id"]])
        for cid in fans:
            fx.need(cid, "fun", 10, "watched the show")
            fx.need(cid, "social", 8, "watched the show")
        sim.attach_traces(ev, cast + fans)
        sim.finish(ev, fx)
        lead = prod.get("lead")
        if lead in cast and label != "rough":
            e2 = self.event("show", "star", [lead], importance=30, group=g["id"], data={"event": prod["name"]})
            e2["causes"] = [ev["id"]] if ev.get("id") else []
            f2 = Effects(w, e2)
            f2.rep(lead, "star", 5, "stole the show")
            sim.confidence(lead, 2.0, f2, "stole the show")
            sim.finish(e2, f2)
        for m in list(g["members"]):
            Effects(w, None).leave(m, g["id"], f"{prod['name']} closed")
        g["production"] = None

    def dance(self, it, rng):
        sim = self.sim
        w = sim.w
        came = sorted(set(sim.slot.attend.get(("event", it["key"]), [])))
        if not came:
            return
        dates = w.dance_dates.get(it["key"], {})
        ev = self.event("dance", "held", came, importance=16, data={"event": it["name"], "n": len(came)})
        fx = Effects(w, ev)
        for cid in came:
            fx.need(cid, "social", 14, it["name"])
            fx.need(cid, "fun", 12, it["name"])
            fx.need(cid, "energy", -10, it["name"])
        sim.attach_traces(ev, came)
        sim.finish(ev, fx)
        done = set()
        prot = w.meta.get("protagonist")
        for a in came:
            b = dates.get(a)
            if prot in (a, b):
                continue  # you play your own night (nights.py)
            if b and b in came and (b, a) not in done and a < b:
                done.add((a, b))
                e2 = self.event("dance", "moment", [a], [b], importance=24, data={"event": it["name"]})
                e2["causes"] = [ev["id"]] if ev.get("id") else []
                f2 = Effects(w, e2)
                p = {"kind": "date", "quality_bias": 0.3, "familiarity": 6, "affection": 9, "trust": 4, "attraction": 3.0,
                     "social": 10, "fun": 10, "romantic": True}
                res = social.interact(sim, f2, e2, a, b, p, rng, e2["calc"] if e2.get("calc") is not None else None)
                e2["data"]["quality"] = round(res["quality"], 3)
                if res["outcome"] in ("great",):
                    for x, y in ((a, b), (b, a)):
                        f2.memory(x, "dance_night", [y], 0.7, 60, f"Danced with {w.chars[y].name} at {it['name']}")
                    ra, rb = w.rels[(a, b)], w.rels[(b, a)]
                    if w.rules["romance.enabled"] and ra.attraction > 50 and rb.attraction > 50 and \
                            not w.chars[a].flags.get("partner") and not w.chars[b].flags.get("partner"):
                        start_dating(sim, a, b, e2, f2)
                sim.finish(e2, f2)
        singles = [c for c in came if c not in dates]
        pairs = [(singles[i], singles[j]) for i in range(len(singles)) for j in range(i + 1, len(singles))]
        rng.shuffle(pairs)
        fx3 = Effects(w, None)
        for a, b in pairs[:16]:
            q = 0.2 + 0.3 * compatibility(w, w.chars[a], w.chars[b]) + rng.gauss(0, 0.25)
            ambient(sim, fx3, a, b, q, it["name"])
        for cid in singles:
            c = w.chars[cid]
            if c.traits["sociability"] < 35 and rng.random() < 0.5 and cid != prot:
                e4 = self.event("dance", "alone", [cid], importance=10, data={"event": it["name"]})
                f4 = Effects(w, e4)
                f4.mood(cid, -4, "wallflower")
                sim.finish(e4, f4)
        if prot in came:
            from . import nights
            nights.start(sim, "dance", it["key"], it["name"], came, date=dates.get(prot))

    def party(self, key, rng):
        sim = self.sim
        w, R = sim.w, sim.w.rules
        p = w.parties.pop(key)
        host = p["host"]
        came = sorted(set(sim.slot.attend.get(("party", key), [])) | {host})
        prot = w.meta.get("protagonist")
        if prot in came and len(came) < 7:  # you're there: more of the invite list drifts in as the night goes on
            extra = [i for i in p["invited"] if i not in came and i in w.chars and w.chars[i].status == "active"
                     and w.chars[i].location == w.chars[host].location and not sim.committed(i, "evening")]
            came = sorted(set(came) | set(extra[:7 - len(came)]))
        H = w.chars[host]
        if len(came) <= 3:
            ev = self.event("party", "flop", [host], importance=26, data={"n": len(came) - 1})
            fx = Effects(w, ev)
            fx.mood(host, -10, "party flopped")
            fx.memory(host, "party_flop", [], -0.6, 55, "Threw a party nobody came to")
            fx.rep(host, "embarrassed", 4, "party flopped")
            sim.attach_traces(ev, came)
            sim.finish(ev, fx)
            return
        ev = self.event("party", "thrown", [host], came[:], importance=24, data={"n": len(came) - 1, "attendees": came})
        fx = Effects(w, ev)
        fx.rep(host, "host", 5, "threw a party")
        for cid in came:
            fx.need(cid, "fun", 20, "party")
            fx.need(cid, "social", 20, "party")
            fx.need(cid, "energy", -15, "party")
            fx.flag(cid, "late_night", w.day, "party")
            if cid != host:
                fx.rel(cid, host, "affection", 3, "good party")
        pairs = [(came[i], came[j]) for i in range(len(came)) for j in range(i + 1, len(came))]
        rng.shuffle(pairs)
        for a, b in pairs[:min(24, len(came) * 2)]:
            q = 0.25 + 0.3 * compatibility(w, w.chars[a], w.chars[b]) + rng.gauss(0, 0.3)
            ambient(sim, fx, a, b, q, "party")
        sim.attach_traces(ev, came)
        sim.finish(ev, fx)
        # incidents
        incidents = 0
        prot = w.meta.get("protagonist")
        for a, b in pairs:
            if incidents >= 2:
                break
            if prot in (a, b):
                continue  # your night is yours to play (nights.py)
            ra, rb = w.rels.get((a, b)), w.rels.get((b, a))
            if not ra or not rb:
                continue
            if R["romance.enabled"] and ra.attraction >= 45 and rb.attraction >= 45 and rng.random() < 0.3:
                incidents += 1
                cheat = bool(w.chars[a].flags.get("partner") or w.chars[b].flags.get("partner"))
                e2 = self.event("party", "kiss", [a], [b], importance=34, data={})
                e2["causes"] = [ev["id"]] if ev.get("id") else []
                f2 = Effects(w, e2)
                for x, y in ((a, b), (b, a)):
                    f2.rel(x, y, "attraction", 10, "kissed at a party")
                    f2.rel(x, y, "affection", 5, "kissed at a party")
                    f2.memory(x, "kiss", [y], 0.6, 60, f"Kissed {w.chars[y].name} at a party")
                seen = [c for c in came if c not in (a, b)][:5]
                rid = make_rumor(sim, a, "kiss", f"{w.chars[a].name} and {w.chars[b].name} kissed at {H.first}'s party", True,
                                 -0.3 if cheat else 0.05, 0.9 if cheat else 0.7, None, seen, e2.get("id"), involves=[a, b])
                for x in (a, b):
                    pt = w.chars[x].flags.get("partner")
                    if pt and pt not in (a, b):
                        sim.schedule(w.day + 1, "tell_subject", {"rumor": rid, "teller": seen[0] if seen else None,
                                                                 "jealous": pt}, e2.get("id"))
                sim.finish(e2, f2)
            elif (ra.rivalry >= 40 or ra.affection <= -30) and rng.random() < 0.3 * (w.chars[a].traits["volatility"] / 60):
                incidents += 1
                e3 = self.event("party", "fight", [a], [b], importance=30, data={})
                e3["causes"] = [ev["id"]] if ev.get("id") else []
                f3 = Effects(w, e3)
                for x, y in ((a, b), (b, a)):
                    f3.rel(x, y, "affection", -10, "fight at a party")
                    f3.rel(x, y, "rivalry", 8, "fight at a party")
                    f3.memory(x, "argument", [y], -0.6, 55, f"Got into it with {w.chars[y].name} at a party")
                sim.finish(e3, f3)
        pb = clamp(0.06 + 0.02 * (len(came) - 6), 0.02, 0.4)
        roll = rng.random()
        if prot in came:
            from . import nights
            nights.start(sim, "party", key, "Your party" if prot == host else f"{H.first}'s party", came, host=host, busted=roll < pb)
        if roll < pb:
            e5 = self.event("party", "busted", [host], came, importance=36, data={})
            e5["causes"] = [ev["id"]] if ev.get("id") else []
            e5["calc"] = [{"step": "neighbors call it in", "p": round(pb, 3), "roll": round(roll, 4)}] if w.tracing else None
            f5 = Effects(w, e5)
            sim.schedule(w.day + 1, "parents_find_out", {"char": host, "what": "throwing a party that got busted"}, e5.get("id"))
            for cid in came:
                if cid != host and rng.random() < 0.3 and cid != prot:  # (yours plays out in your night)
                    sim.schedule(w.day + 1, "parents_find_out", {"char": cid, "what": "being at a busted party"}, e5.get("id"))
            f5.rep(host, "troublemaker", 5, "busted party")
            sim.finish(e5, f5)
        # people who thought they were friends with the host and weren't invited
        for o, r in sorted(w.out.items()):
            if o in came or o in p["invited"] or w.chars[o].role != "student" or w.chars[o].status != "active":
                continue
            rr = r.get(host)
            if rr and rr.affection >= R["rel.friend_threshold"] and rng.random() < 0.45:
                e6 = self.event("party", "not_invited", [o], [host], importance=20, data={})
                e6["causes"] = [ev["id"]] if ev.get("id") else []
                f6 = Effects(w, e6)
                f6.rel(o, host, "affection", -6, "wasn't invited")
                f6.rel(o, host, "perceived", -10, "wasn't invited")
                f6.mood(o, -4, "left out")
                f6.memory(o, "exclusion_by", [host], -0.45, 45, f"Wasn't invited to {H.name}'s party")
                sim.finish(e6, f6)

    def missed_shifts(self, rng):
        sim = self.sim
        w = sim.w
        wd = calm.weekday(w.day)
        for g in sorted(w.groups.values(), key=lambda g: g["id"]):
            if g["kind"] != "job" or wd not in g["shift_days"]:
                continue
            worked = set(sim.slot.attend.get(("shift", g["id"]), []))
            elsewhere = {c for (what, key), ids in sim.slot.attend.items() if what in ("practice", "event") for c in ids}
            for cid in worked:
                mark(g, cid, True, 6)
            for cid in sorted(set(g["members"]) - worked - elsewhere):
                mark(g, cid, False, 6)
                if misses(g, cid) >= 4:
                    ev = self.event("job", "fired", [cid], importance=30, group=g["id"], data={"group": g["name"]})
                    fx = Effects(w, ev)
                    fx.leave(cid, g["id"], "fired for missing shifts")
                    fx.mood(cid, -6, "fired")
                    fx.memory(cid, "fired", [], -0.5, 50, f"Got fired from {g['name']}")
                    fx.rep(cid, "flaky", 4, "fired")
                    sim.finish(ev, fx)

    def hire_decision(self, payload, cause_id, rng):
        sim = self.sim
        w = sim.w
        c = w.chars.get(payload["char"])
        g = w.groups[payload["group"]]
        if c is None or c.status != "active":
            return
        terms = [("discipline", c.traits["discipline"] * 0.5), ("charm", c.aptitudes["charisma"] * 0.2),
                 ("reputation: troublemaker", -c.reputation.get("troublemaker", 0) * 0.8),
                 ("reputation: flaky", -c.reputation.get("flaky", 0) * 0.8), ("luck", rng.gauss(0, 10))]
        s = sum(t[1] for t in terms)
        hired = s >= 32 and len(g["members"]) < g["capacity"]
        ev = self.event("job", "hired" if hired else "rejected", [c.id], importance=24 if hired else 14, group=g["id"],
                        data={"group": g["name"]})
        ev["causes"] = [cause_id] if cause_id else []
        ev["calc"] = [{"step": "hiring decision", "terms": [[t[0], round(t[1], 2)] for t in terms], "total": round(s, 2),
                       "rule": "hired if score >= 32 and a spot is open", "outcome": "hired" if hired else "rejected"}] if w.tracing else None
        fx = Effects(w, ev)
        if hired:
            fx.join(c.id, g["id"], "hired")
            g["absences"][c.id] = []
            fx.mood(c.id, 6, "got a job")
            fx.memory(c.id, "hired", [], 0.5, 40, f"Got hired at {g['name']}")
            for go in c.goals:
                if go["type"] == "earn_money" and go["status"] == "active":
                    go["status"] = "achieved"
                    go["closed"] = w.day
        else:
            fx.mood(c.id, -4, "didn't get the job")
        sim.finish(ev, fx)

    def election(self, it, rng):
        sim = self.sim
        w = sim.w
        g = w.groups[it["group"]]
        cands = sorted(w.registrations.get(it["key"], []))
        w.registrations.pop(it["key"], None)
        cands = [c for c in cands if w.chars[c].status == "active" and w.chars[c].role == "student" and w.chars[c].school == "hchs"]
        if not cands:
            return
        votes = {c: 0 for c in cands}
        for v in sorted((x for x in w.students() if x.school == "hchs"), key=lambda c: c.id):
            best, bs = None, -1e9
            for c in cands:
                if c == v.id:
                    s = 40
                else:
                    r = w.rels.get((v.id, c))
                    s = (r.affection * 0.5 + r.respect * 0.3) if r else 0
                    s += w.chars[c].popularity * 0.2 * (v.motives["approval"] / 50) * w.rules["motive.approval"]
                    if v.flags.get("clique") and v.flags.get("clique") == w.chars[c].flags.get("clique"):
                        s += 15
                s += rng.gauss(0, 10)
                if s > bs:
                    best, bs = c, s
            votes[best] += 1
        order = sorted(cands, key=lambda c: (-votes[c], c))
        winners = order[:g["capacity"]]
        for m in list(g["members"]):
            Effects(w, None).leave(m, g["id"], "new council elected")
        ev = self.event("election", "result", cands, importance=34, group=g["id"],
                        data={"members": winners, "votes": votes})
        ev["calc"] = [{"step": "votes", "votes": votes,
                       "rule": "each student votes for the candidate they rate highest: 0.5 affection + 0.3 respect + popularity x approval + same clique 15 + noise"}] if w.tracing else None
        fx = Effects(w, ev)
        sim.finish(ev, fx)
        for i, c in enumerate(order):
            won = c in winners
            pres = i == 0
            e2 = self.event("election", "president" if pres else "won" if won else "lost", [c], importance=40 if pres else 30,
                            group=g["id"], data={"votes": votes[c]})
            e2["causes"] = [ev["id"]] if ev.get("id") else []
            f2 = Effects(w, e2)
            if won:
                f2.join(c, g["id"], "elected")
                f2.rep(c, "leader", 8 if pres else 5, "elected")
                f2.mood(c, 10, "won the election")
                f2.memory(c, "elected", [], 0.8, 70, "Elected student council president" if pres else "Won a student council seat")
                sim.confidence(c, 2.0, f2, "won")
            else:
                f2.mood(c, -8, "lost the election")
                f2.memory(c, "lost_election", [winners[0]], -0.5, 55, f"Lost the student council election to {w.chars[winners[0]].name}")
                f2.rel(c, winners[0], "rivalry", 6, "lost to them")
            for go in w.chars[c].goals:
                if go["type"] == "win_election" and go["status"] == "active":
                    go["status"] = "achieved" if won else "failed"
                    go["closed"] = w.day
            sim.finish(e2, f2)
        if winners:
            g["leaders"] = [winners[0]]

    # --- calendar transitions ------------------------------------------------------
    def season_end(self, it):
        w = self.sim.w
        g = w.groups[it["group"]]
        rec = dict(g["record"])
        awards = sports.season_awards(self, g) if g["kind"] == "team" else []
        if g["kind"] == "team":
            from . import league
            league.season_end(self.sim, g)  # the regular-season title, and what the season did for the team's standing
        rng = self.sim.streams.get("season_end", w.day, g["id"])
        if g["kind"] == "team":
            for m in sorted(g["members"]):
                if g.get("levels", {}).get(m, "varsity") == "varsity":
                    sports.recruiting_update(self, w.chars[m], g["skill"], rng)
        g["history"].append({"year": calm.school_year_of(w.day), "record": rec, "roster": list(g["members"]),
                             "levels": dict(g.get("levels", {})), "awards": [[a, b] for a, b in awards]})
        ev = self.event("season_end", "ended", list(g["members"]), importance=12, group=g["id"],
                        data={"group": g["name"], "record": f"{rec['w']}-{rec['l']}"})
        ev["text"] = f"{g['name']} finished the season {rec['w']}-{rec['l']}."
        fx = Effects(w, ev)
        for m in list(g["members"]):
            fx.leave(m, g["id"], "season ended")
        g["record"] = {"w": 0, "l": 0}
        g["record_jv"] = {"w": 0, "l": 0}
        g["absences"] = {}
        g["cut"] = []
        g["leaders"] = []
        g["levels"] = {}
        self.sim.finish(ev, fx)

    def graduation(self, it):
        sim = self.sim
        w = sim.w
        seniors = sorted(c.id for c in w.students() if c.grade == 12 and c.school == "hchs")
        rng = sim.streams.get("graduation", w.day)
        for cid in seniors:
            c = w.chars[cid]
            if not c.path:
                sports.choose_path(self, c, rng)
            ev = self.event("graduation", "graduated", [cid], importance=40)
            fx = Effects(w, ev)
            for gid in list(c.memberships):
                if w.groups[gid]["kind"] != "job":
                    fx.leave(cid, gid, "graduated")
            fx.scalar(cid, "role", "alumni", "graduated")
            c.grade = None
            c.school = None
            fx.memory(cid, "graduated", [], 0.8, 80, f"Graduated from {sim.cat.world['school']['name']}")
            c.achievements.append({"day": w.day, "label": "Graduated", "event": ev.get("id")})
            for go in c.goals:
                if go["status"] == "active" and go["type"] in ("make_group", "grades", "win_election", "improve_skill"):
                    go["status"] = "abandoned"
                    go["closed"] = w.day
            sim.finish(ev, fx)
            if cid == w.meta.get("protagonist"):
                p = c.path or {}
                line = (f"Next: {p.get('sport') + ' at ' if p.get('sport') else ''}{p.get('name')}." if p.get("kind") == "college"
                        else f"Next: staying in {sim.cat.world['town']['name']} and working.")
                sim.moment_trigger("graduation", cid, {"path_line": line})
        w.meta["graduated_last"] = len(seniors)

    def welcome(self, yours):
        """Someone you made starts high school: it's in your feed, and if they're family or a friend, they text you."""
        sim = self.sim
        w = sim.w
        prot = w.meta.get("protagonist")
        pc = w.chars.get(prot or "")
        school = sim.cat.world["school"]["name"]
        for c in yours:
            r = w.rels.get((c.id, prot)) if pc else None
            fam = pc is not None and c.household_id == pc.household_id
            word = {"m": "brother", "f": "sister"}.get(c.gender, "sibling")
            ev = self.event("new_year", "arrived", [c.id], importance=34 if (fam or r) else 22, involved=[prot] if pc else None,
                            data={"yours": True, "family": fam})
            ev["text"] = (f"{pc.short}'s little {word} {c.first} starts at {school} as a freshman." if fam
                          else f"{c.short} starts at {school} as a freshman.")
            sim.finish(ev, Effects(w, ev))
            sim.review_goals_for(c)
            if pc and "phone" in w.meta and pc.location != "away" and (fam or (r and r.affection >= 30)):
                from . import messages
                messages.add_contact(sim, c.id, "new_year")
                line = ("ok i'm officially in high school. don't act like you don't know me" if fam
                        else "first day at " + sim.cat.world["school"]["short"] + " tomorrow. save me a seat at lunch?")
                messages.later(sim, c.id, "scene", delay_phases=1, text=line)

    def new_year(self):
        """Sept 1: everyone moves up a grade, new freshmen arrive, the calendar rebuilds."""
        from .worldgen import new_freshmen
        sim = self.sim
        w = sim.w
        y = calm.school_year_of(w.day)
        w.year = y
        from . import college
        for c in sorted(w.students(), key=lambda c: c.id):
            if c.school == "hchs":
                c.grade += 1
        college.new_college_year(sim, sim.streams.get("college-year", w.day))
        college.depart(sim, sim.streams.get("depart", w.day))
        n = w.meta.get("graduated_last", 0) or 0
        n = n if n else w.meta.get("generated", {}).get("students", 36) // 4
        from .story import arrive
        yours = arrive(sim, y)  # the younger kids you made: this is their freshman year
        fresh = new_freshmen(w, y, max(0, n - len(yours)), w.day)
        for c in fresh:
            ev = self.event("new_year", "arrived", [c.id], importance=22)
            sim.finish(ev, Effects(w, ev))
            sim.review_goals_for(c)
        self.welcome(yours)
        fresh = yours + fresh
        for g in w.groups.values():
            if g["kind"] == "council":
                for m in list(g["members"]):
                    Effects(w, None).leave(m, g["id"], "new school year")
                g["leaders"] = []
        w.calendar = [i for i in w.calendar if i["day"] >= w.day] + calm.build_year(w, sim.cat, y)
        w.calendar.sort(key=lambda i: (i["day"], i["kind"], i.get("group") or "", i["key"]))
        ev = self.event("new_year", "started", [], importance=30, data={"year": y + 1, "freshmen": [c.id for c in fresh]})
        ev["text"] = f"A new school year begins at {sim.cat.world['school']['name']}. {len(fresh)} freshmen arrive."
        sim.finish(ev, Effects(w, ev))
