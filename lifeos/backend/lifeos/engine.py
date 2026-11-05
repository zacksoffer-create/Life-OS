"""The simulation orchestrator: one authoritative world, advanced phase by phase.

A slot runs in three steps:
  1. every acting character decides from the same start-of-slot state (simultaneous choice,
     each with their own random stream);
  2. choices are resolved one by one in a seeded order: invitations can be accepted or
     declined by the target, who may drop their own plan;
  3. collective events resolve (lunch tables, practices, tryouts, games, parties...).
Night handles recovery and the daily/weekly/yearly bookkeeping.
"""
from __future__ import annotations

import zlib

from . import calendar as calm
from . import development, households, metrics, social
from .actions import RESOLVERS
from .catalogs import APTITUDES, MOTIVES, NEEDS, TRAITS, Catalogs
from .decision import Cand, decide, prepare, requirement, score, temperature
from .history import Effects, History
from .institutions import Institutions
from .model import World
from .narrative import render
from .rng import Streams, clamp, sigmoid
from .rules import RulesError, rules_hash, schema


class SlotState:
    def __init__(self, slot):
        self.slot = slot
        self.planned: dict = {}
        self.done: set = set()
        self.engaged: dict = {}
        self.attend: dict = {}
        self.tables: list = []
        self.traces: dict = {}
        self.cancelled: dict = {}
        self.agreed: set = set()

    def engaged_in_event(self, cid) -> bool:
        for (what, key), ids in self.attend.items():
            if what == "event" and cid in ids:
                return True
        return False


class EditError(ValueError):
    pass


class Simulation:
    def __init__(self, world: World):
        self.w = world
        if world.history is None:
            world.history = History()
        self.cat = Catalogs(world.action_overrides)
        self.streams = Streams(world.seed)
        self.institutions = Institutions(self)
        self.slot: SlotState | None = None
        self.ctx = None
        self.ctx_practices: list = []
        self._today: list = []
        self.upcoming: list = []
        from . import scheduler, teams
        teams.upgrade(self)  # boys' and girls' teams, soccer and softball, for saves made before them
        scheduler.migrate(self)  # the story scheduler: what already played counts as resolved
        from .social import tidy_romance
        tidy_romance(self)  # nobody's into family (or a teacher, or outside who they like), in saves made before that rule
        self._refresh_day()
        self._note_rules()
        if not world.meta.get("initialized"):
            self._initialize()

    # --- setup -----------------------------------------------------------------
    def _initialize(self):
        w = self.w
        w.meta["initialized"] = True
        w.meta.setdefault("tally", {})
        w.meta.setdefault("actions", {})
        fx = Effects(w, None)
        social.recompute_popularity(self, fx)
        social.recompute_popularity(self, fx)
        rng = self.streams.get("init")
        for (a, b), r in w.rels.items():
            r.label = social.label_for(r, w.rules)
            r.crush = bool(r.attraction >= w.rules["rel.crush_threshold"]
                           and social.romance_ok(w, a, b, chosen=a == w.meta.get("protagonist") or r.attraction >= 60))
        social.detect_cliques(self, rng)
        for c in sorted(w.active(), key=lambda c: c.id):
            development.review_goals(self, c, rng)
        if w.meta.get("protagonist"):
            from .story import story_circle
            w.meta["circle"] = sorted(story_circle(w))
        w.stats_series.append(metrics.snapshot(w))

    def _refresh_day(self):
        w = self.w
        self._today = [i for i in w.calendar if i["day"] == w.day]
        self.upcoming = [i for i in w.calendar if w.day <= i["day"] <= w.day + 60]
        self.ctx_practices = self.institutions.practices_today()

    def _note_rules(self):
        """Every distinct rule set gets a version id; traces point at it."""
        v = rules_hash(self.w.rules)
        vs = self.w.meta.setdefault("rules_versions", {})
        if v not in vs:
            vs[v] = {k: val for k, val in self.w.rules.items()}
        self.rules_version = v

    # --- time ------------------------------------------------------------------
    def phases(self):
        return calm.phases_for(self.w.day, self.cat.world["calendar"])

    def current_phase(self) -> str:
        return self.phases()[self.w.phase]

    def today(self, slot) -> list:
        return [i for i in self._today if i.get("slot") == slot]

    def step(self, overrides: dict | None = None):
        ph = self.current_phase()
        if ph == "dawn":
            self._dawn()
        elif ph == "classes":
            self.institutions.classes(self.streams.get("classes", self.w.day))
        elif ph in calm.DECISION_SLOTS:
            self.run_slot(ph, overrides or {})
        elif ph == "night":
            self._night()
        self.w.phase += 1
        if self.w.phase >= len(self.phases()):
            self.w.day += 1
            self.w.phase = 0
            self._refresh_day()
        elif "story" in self.w.meta:
            from . import scheduler
            scheduler.deliver(self)  # this part of the day's storyline scene, if one is planned for now
        if "phone" in self.w.meta:
            from . import messages
            messages.tick(self)

    def advance_days(self, n: int, progress=None):
        target = self.w.day + int(n)
        while self.w.day < target:
            self.step()
            if progress and self.w.phase == 0:
                progress(self.w.day)

    def run_until_slot_for(self, cid: str, max_days: int = 7):
        """Run phases until the next decision slot in which cid acts."""
        start = self.w.day
        while self.w.day - start <= max_days:
            ph = self.current_phase()
            if ph in calm.DECISION_SLOTS and cid in self.slot_actors(ph):
                return ph
            self.step()
        return None

    # --- dawn / night ----------------------------------------------------------
    def _dawn(self):
        w = self.w
        cal = self.cat.world["calendar"]
        if w.day > 0 and calm.date_of(w.day).month == 9 and calm.date_of(w.day).day == 1:
            self.institutions.new_year()
            self._refresh_day()
        from . import college, pets
        college.daily(self)
        pets.dawn(self)
        if w.meta.get("protagonist"):
            from . import squad
            squad.dawn(self)  # your group might make plans for later
            from . import drama, nights
            drama.dawn(self)  # gossip reaches you; sometimes drama does too
            nights.dawn(self)  # most Fridays and Saturdays, somebody has people over
            squad.invite_dawn(self)  # some mornings a friend asks you along with a few of their people
        rng = self.streams.get("dawn", w.day)
        due = [s for s in w.schedule if s["day"] <= w.day]
        w.schedule = [s for s in w.schedule if s["day"] > w.day]
        for s in due:
            self._handle(s, rng)
        for it in self.today(None):
            if it["kind"] == "season_end":
                self.institutions.season_end(it)
            elif it["kind"] == "admissions":
                from . import sports
                sports.admissions(self.institutions, rng)
            elif it["kind"] == "college_decision":
                p = w.meta.get("protagonist")
                pc = w.chars.get(p) if p else None
                if pc and pc.school == "hchs" and pc.grade == 12 and not pc.path:
                    self.moment_trigger("college_decision", p, {})
            elif it["kind"] == "decision_day":
                from . import sports
                for c in sorted(w.students(), key=lambda c: c.id):
                    if c.school == "hchs" and c.grade == 12 and not c.path and c.id != w.meta.get("protagonist"):
                        sports.choose_path(self.institutions, c, rng)
        for c in sorted(w.active(), key=lambda c: c.id):
            if (w.day - c.birth_day) % 365 == 0 and c.role in ("student", "alumni"):
                ev = self.new_event("birthday", "birthday", [c.id], [], 8, {"n": c.age(w.day)})
                fx = Effects(w, ev)
                fx.mood(c.id, 5, "birthday")
                self.finish(ev, fx)
        for c in w.chars.values():
            g = c.flags.get("grounded_until")
            if g is not None and g < w.day:
                c.flags.pop("grounded_until", None)
        d = calm.date_of(w.day)
        from . import mlb as mlb_world
        if (d.month, d.day) == tuple(mlb_world.draft_info(d.year)[0]):  # early June in the 2010s, mid-July from 2021
            from . import sports
            sports.mlb_draft(self)
        self.ctx_practices = self.institutions.practices_today() if calm.is_school_day(w.day, cal) else []
        self._story_dawn()

    def _story_dawn(self):
        """Protagonist-only checks each morning: game day, the end of a school year, stale invitations."""
        from . import moments
        w = self.w
        prot = w.meta.get("protagonist")
        if not prot or prot not in w.chars:
            return
        pc = w.chars[prot]
        if "phone" in w.meta:
            from . import messages
            messages.daily(self)
        for it in self._today:
            if it["kind"] == "game" and prot in w.groups[it["group"]]["members"] and pc.flags.get("injured_until", -1) < w.day:
                n = int(it["key"].split(":")[-1]) if it["key"].split(":")[-1].isdigit() else 1
                from .sports import opponent_name
                self.moment_trigger("game_day", prot, {"group": it["group"], "opponent": opponent_name(self, w.groups[it["group"]], n)})
        for it in self._today:
            if it["kind"] == "exam" and it.get("slot") == "classes" and it.get("school", "hchs") == pc.school and pc.location != "away":
                from . import classes
                self.moment_trigger("class_quiz", prot, classes.quiz_context(self, pc, it))
        from . import classgames
        classgames.maybe(self, pc)  # most school days: something quick in one of your classes
        cal = self.cat.world["calendar"]
        st = w.meta.get("story") or {}
        if calm.break_name(w.day, cal) == "Summer" and calm.break_name(w.day - 1, cal) != "Summer":
            self.moment_trigger("year_review", prot, {})
            if not (st and w.day - st.get("start_day", 0) >= (st.get("years", 7) - 1) * 365 + 200):
                self.moment_trigger("summer", prot, {})
        if st and not st.get("complete") and w.day - st.get("start_day", 0) >= (st.get("years", 7) - 1) * 365 + 280:
            dd = calm.date_of(w.day)
            from . import mlb as mlb_world
            after_draft = (dd.month, dd.day) > tuple(mlb_world.draft_info(dd.year)[0]) and dd.month < 9
            waiting = any(m["kind"] in ("mlb_draft", "draft_passed") for m in moments.pending(w))
            if after_draft and not waiting:
                self.moment_trigger("story_end", prot, {})
        from . import scheduler
        for m in moments.pending(w):
            if not scheduler.auto_ok(w, m):
                continue  # a storyline scene waits for you (unless you turned on Let my character decide)
            if w.day - m["day"] >= (1 if m["kind"] in ("game_day", "class_game") or m["kind"].startswith("night_") else 3):
                moments.resolve(self, m["id"], None)
        from . import dialogue
        dialogue.maybe_scene(self)  # scenes from dialogue packs
        for inv in w.meta.get("inbox", []):
            if inv["status"] == "pending" and w.day - inv["day"] >= 2:
                inv["status"] = "expired"
                if inv["from"] in w.chars:
                    fx = Effects(w, None)
                    fx.rel(inv["from"], prot, "affection", -2, "left on read")
                    fx.rel(inv["from"], prot, "perceived", -5, "left on read")
        if len(w.meta.get("inbox", [])) > 60:
            w.meta["inbox"] = [i for i in w.meta["inbox"] if i["status"] == "pending"] + \
                              [i for i in w.meta["inbox"] if i["status"] != "pending"][-30:]

    def _handle(self, s, rng):
        k = s["kind"]
        if k == "selection_results":
            self.institutions.selection_results(s["payload"], s.get("cause"), rng)
        elif k == "hire_decision":
            self.institutions.hire_decision(s["payload"], s.get("cause"), rng)
        elif k == "parents_find_out":
            households.parents_find_out(self, s["payload"], s.get("cause"), rng)
        elif k == "tell_subject":
            self._tell_subject(s["payload"], s.get("cause"), rng)

    def _tell_subject(self, payload, cause, rng):
        w, R = self.w, self.w.rules
        rum = w.rumors.get(payload["rumor"])
        if not rum:
            return
        jealous = payload.get("jealous")
        subject = jealous or rum["about"]
        S = w.chars.get(subject)
        if S is None or S.status != "active" or subject in rum["known_by"]:
            return
        teller = payload.get("teller")
        rum["known_by"][subject] = [w.day, teller, True]
        ev = self.new_event("rumor_reached", "hurt", [subject], [teller] if teller else [], 28, {"about": rum["text"]})
        ev["causes"] = [cause] if cause else []
        fx = Effects(w, ev)
        fx.mood(subject, -8 * max(0.3, abs(rum["valence"])), "heard what people are saying")
        fx.need(subject, "stress", 7, "heard what people are saying")
        if teller and teller in w.chars:
            fx.rel(subject, teller, "trust", 3, "told them the truth")
        if jealous:
            for x in rum["involves"]:
                if w.chars[subject].flags.get("partner") == x:
                    j = R["romance.jealousy"]
                    fx.rel(subject, x, "affection", -15 * j, "heard about the kiss")
                    fx.rel(subject, x, "trust", -20 * j, "heard about the kiss")
                    fx.memory(subject, "betrayed", [x], -0.85, 75, f"Found out {w.chars[x].name} kissed someone else")
        roll = rng.random()
        origin = rum.get("origin")
        found = bool(origin and origin != subject and roll < R["social.rumor_discovery"])
        ev["calc"] = [{"step": "do they find out who started it?", "p": R["social.rumor_discovery"] if origin else 0,
                       "roll": round(roll, 4), "outcome": "found the source" if found else "no"}] if w.tracing else None
        self.finish(ev, fx)
        if not jealous:
            self.moment_trigger("rumor", subject, {"about": rum["text"], "origin": origin if found else None})
        if found:
            e2 = self.new_event("rumor_reached", "source", [subject], [origin], 36, {"about": rum["text"]})
            e2["causes"] = [ev["id"]]
            f2 = Effects(w, e2)
            f2.rel(subject, origin, "affection", -25, "started a rumor about them")
            f2.rel(subject, origin, "trust", -25, "started a rumor about them")
            f2.rel(subject, origin, "rivalry", 15, "started a rumor about them")
            f2.memory(subject, "betrayed", [origin], -0.85, 75, f"Found out {w.chars[origin].name} started a rumor about them")
            f2.rep(origin, "gossip", 6, "outed as a rumor-starter")
            self.finish(e2, f2)

    def _night(self):
        w, R = self.w, self.w.rules
        for c in w.chars.values():
            if c.status != "active":
                continue
            n = c.needs
            late = c.flags.pop("late_night", None) == w.day
            n["energy"] = clamp(n["energy"] + R["needs.energy_recovery"] * (0.6 if late else 1.0), 0, 100)
            n["social"] = clamp(n["social"] - R["needs.social_decay"] * (0.5 + c.traits["sociability"] / 100), 0, 100)
            n["fun"] = clamp(n["fun"] - R["needs.fun_decay"] * (0.6 + c.traits["impulsivity"] / 150), 0, 100)
            base = 20 + c.traits["volatility"] * 0.3
            n["stress"] = clamp(n["stress"] + (base - n["stress"]) * R["needs.stress_recovery"] / 100, 0, 100)
            target = 45 + 0.2 * (n["energy"] - 50) + 0.2 * (n["social"] - 50) + 0.15 * (n["fun"] - 50) - 0.4 * (n["stress"] - 35)
            k = R["needs.mood_inertia"]
            c.mood = clamp(k * c.mood + (1 - k) * target, 0, 100)
            c.study_ema *= 0.93
        for it in self.today("night"):
            if it["kind"] == "graduation":
                self.institutions.graduation(it)
        from . import pets
        pets.night(self)
        if self.w.meta.get("protagonist"):
            from . import squad
            squad.night(self)
        if "phone" in w.meta:
            from . import messages
            messages.pregame(self)
        if calm.weekday(w.day) == 6:
            self._weekly()

    def _weekly(self):
        w, R = self.w, self.w.rules
        rng = self.streams.get("weekly", w.day)
        from . import pets
        pets.weekly(self)
        fx = Effects(w, None)
        decay = R["rel.affection_decay"] / 100
        for (a, b), r in w.rels.items():
            if w.day - r.last_day > 7:
                k = 0.5 if (w.has_role(a, b, "partner") or w.has_role(a, b, "sibling")) else 1.0
                r.affection -= r.affection * decay * k
                r.familiarity = max(0.0, r.familiarity - R["rel.familiarity_decay"] * k)
                r.attraction = max(0.0, r.attraction - r.attraction * decay * 0.5)
                fx.pairs.add((a, b))
        social.update_labels(self, fx, None)
        social.recompute_popularity(self, Effects(w, None))
        from . import ladder, league
        league.weekly(self)  # power rankings and Player of the Week (before the ladder: it's news that moves people)
        ladder.snapshot(self)  # everyone's rank this week: who's moving on the Scene tab's ladder
        from . import pro
        pro.weekly(self)  # the pro leagues in the background: MLB's season to today, and fans react to October
        for kind, cid, qid in social.detect_cliques(self, rng):
            q = w.cliques[qid]
            if kind == "formed":
                ev = self.new_event("clique", "formed", list(q["members"]), [], 30, {"label": q["name"], "members": q["members"], "clique": qid})
            elif kind == "dissolved":
                ev = self.new_event("clique", "dissolved", list(q["members"]), [], 24, {"label": q["name"], "clique": qid})
            else:
                ev = self.new_event("clique", kind, [cid], [], 16, {"label": q["name"], "clique": qid})
            self.finish(ev, Effects(w, ev))
        for c in sorted(w.active(), key=lambda c: c.id):
            development.review_goals(self, c, rng)
        households.weekly(self, rng)
        development.weekly(self, rng)
        if w.meta.get("protagonist"):
            from .story import story_circle
            w.meta["circle"] = sorted(story_circle(w))
        from . import college
        college.offscreen_weekly(self)
        w.stats_series.append(metrics.snapshot(w))
        if w.tracing:
            w.history.compact(w.day, R)

    # --- slots -------------------------------------------------------------------
    def slot_actors(self, slot) -> list:
        """Who decides in this slot. Far from the story (another place, outside your circle) people act once a day."""
        out = []
        w = self.w
        prot = w.chars.get(w.meta.get("protagonist")) if w.meta.get("protagonist") else None
        circle = set(w.meta.get("circle", [])) if prot is not None else ()
        for c in self.w.chars.values():
            if c.status != "active":
                continue
            if prot is not None and c.location != prot.location and c.id not in circle:
                if slot in ("lunch", "evening") or (w.day + zlib.crc32(c.id.encode())) % 2:
                    continue
            if slot == "lunch":
                if c.role == "student" and c.location != "away":
                    out.append(c.id)
            elif c.location == "away":
                continue
            elif slot in ("after_school", "day"):
                out.append(c.id)
            elif slot == "evening" and c.role in ("student", "alumni"):
                out.append(c.id)
        return sorted(out)

    def slot_ctx(self, slot) -> dict:
        w = self.w
        exams = [i for i in self.upcoming if i["kind"] == "exam" and i.get("weight", 1) >= 2 and 0 <= i["day"] - w.day <= 3]
        dance = next((i for i in self.upcoming if i["kind"] == "dance" and i["ask_from"] <= w.day < i["day"]), None)
        recent = [r for r in w.rumors.values() if w.day - r["day"] <= 60]
        by_knower: dict = {}
        for r in recent:
            for k in r["known_by"]:
                by_knower.setdefault(k, []).append(r)
        return {"slot": slot, "day": w.day, "practices": self.ctx_practices, "events": self.today(slot),
                "rumors": recent, "rumors_by": by_knower,
                "exam_soon": exams[0] if exams else None, "dance": dance,
                "opps": self.institutions.opportunities, "peer": {}}

    def char_ctx(self, c) -> dict:
        ctx = dict(self.ctx) if self.ctx else self.slot_ctx("day")
        w, R = self.w, self.w.rules
        fr = sorted(((r.affection, o) for o, r in w.out.get(c.id, {}).items()
                     if r.affection >= R["rel.friend_threshold"] and o in w.chars), reverse=True)[:6]
        peer: dict = {}
        if fr:
            for _, o in fr:
                for aid in set(w.chars[o].recent_actions):
                    peer[aid] = peer.get(aid, 0) + 1
            for k in peer:
                peer[k] /= len(fr)
        ctx["peer"] = peer
        return prepare(self, c, ctx["slot"], ctx)

    def decide_for(self, cid, slot, trace=True):
        c = self.w.chars[cid]
        rng = self.streams.get("decide", self.w.day, slot, cid)
        return decide(self, c, slot, self.char_ctx(c), rng, trace)

    def must_go(self, dec):
        """Your team's practice or game (or your show) in this part of the day: the index of going, or None."""
        game = practice = None
        for i, cd in enumerate(dec["cands"]):
            if cd.a["id"] == "attend_event" and isinstance(cd.extra, dict) and cd.extra.get("kind") in ("game", "show"):
                game = i if game is None else game
            elif cd.a["id"] == "attend_practice" and isinstance(cd.target, str) and cd.target in self.w.groups \
                    and self.w.groups[cd.target]["kind"] in ("team", "production"):
                practice = i if practice is None else practice
        return game if game is not None else practice

    def committed(self, cid, slot=None) -> dict | None:
        """What you're already doing in this part of the day because you're on the team (or in the show)."""
        w = self.w
        slot = slot or self.current_phase()
        c = w.chars.get(cid)
        if not c or c.flags.get("injured_until", -1) >= w.day:
            return None
        for it in self._today:
            if it.get("slot") == slot and it["kind"] in ("game", "show") and it.get("group") in c.memberships:
                if it["kind"] == "game" or cid in (w.groups[it["group"]].get("production") or {}).get("cast", []):
                    return {"kind": it["kind"], "group": it["group"], "label": it["name"]}
        if slot == "after_school":
            for gid in self.ctx_practices or []:
                g = w.groups.get(gid)
                if g and gid in c.memberships and g["kind"] in ("team", "production"):
                    return {"kind": "practice", "group": gid, "label": f"{g['name']} {'practice' if g['kind'] == 'team' else 'rehearsal'}"}
        return None

    def run_slot(self, slot, overrides: dict):
        w = self.w
        self.ctx = self.slot_ctx(slot)
        self.slot = SlotState(slot)
        actors = self.slot_actors(slot)
        everyone = w.rules.get("history.trace_everyone", True)
        circle = set(w.meta.get("circle", [])) if not everyone else None
        for cid in actors:
            dec = self.decide_for(cid, slot, w.tracing and (everyone or cid in circle))
            if dec is None:
                continue
            q = w.meta.get("control", {}).get("queued")
            if q and q.get("slot") and q.get("day") == w.day and q["slot"] != slot:
                q = None  # saved for a later part of today
            must = self.must_go(dec) if cid == w.meta.get("protagonist") else None
            if q and (must is not None or any(cd.a["id"] == "attend_event" and isinstance(cd.extra, dict) and cd.extra.get("kind") in ("game", "show")
                                              for cd in dec["cands"])):
                q = None  # your game, show or practice comes first: the plan waits for your next free time
            if must is not None and cid not in overrides:
                overrides = dict(overrides)
                overrides[cid] = must  # practice and games aren't optional: you just go
            if q and cid == w.meta.get("protagonist") and cid not in overrides:
                hit = None
                for i, cd in enumerate(dec["cands"]):
                    ex = cd.extra if isinstance(cd.extra, dict) else {}
                    if q.get("invite") and ex.get("invite") == q.get("invite"):
                        hit = i
                    elif q.get("action") and cd.a["id"] == q["action"] and (not q.get("target") or cd.target == q["target"]) \
                            and (not q.get("pet") or ex.get("pet") == q["pet"]):
                        hit = i
                    if hit is not None:
                        break
                if hit is not None:
                    overrides = dict(overrides)
                    overrides[cid] = hit
                    if q.get("trick"):
                        dec["cands"][hit].extra = dict(dec["cands"][hit].extra or {}, trick=q["trick"])
                    if q.get("agreed") and q.get("target"):
                        self.slot.agreed.add((cid, q["target"]))
                if hit is not None or q.get("invite") or w.day > q.get("expires", q.get("day", w.day) + 2):
                    w.meta["control"].pop("queued", None)
            if cid in overrides:
                i = overrides[cid]
                if 0 <= i < len(dec["cands"]):
                    dec["chosen"] = dec["cands"][i]
                    dec["player"] = True
                    if dec["trace"]:
                        dec["trace"]["player_choice"] = dec["cands"][i].a["id"]
                        for row in dec["trace"]["candidates"]:
                            row["chosen"] = row["action"] == dec["chosen"].a["id"] and row["target"] == (
                                dec["chosen"].target if not isinstance(dec["chosen"].target, dict) else None)
            self.slot.planned[cid] = dec
            if dec["trace"]:
                self.slot.traces[cid] = w.history.add_trace(dec["trace"])
        order = sorted(self.slot.planned)
        self.streams.get("order", w.day, slot).shuffle(order)
        prot = w.meta.get("protagonist")
        if prot in order and self.slot.planned[prot].get("player"):
            order.remove(prot)  # you made a plan: you texted first, so your friends aren't booked yet
            order.insert(0, prot)
        for cid in order:
            if cid in self.slot.done:
                continue
            self.resolve(self.slot.planned[cid])
        self.institutions.after_slot(slot, self.streams.get("collective", w.day, slot))
        acts = w.meta.setdefault("actions", {})
        for cid, dec in self.slot.planned.items():
            c = w.chars[cid]
            aid = dec["chosen"].a["id"] if cid not in self.slot.cancelled else "accepted_invite"
            acts[aid] = acts.get(aid, 0) + 1
            c.counters[aid] = c.counters.get(aid, 0) + 1
            c.recent_actions.append(aid)
            if len(c.recent_actions) > 6:
                del c.recent_actions[0]
            if aid != "accepted_invite":
                h = c.habits.get(aid, 0.0)
                c.habits[aid] = round(h + 0.08 * (1 - h), 4)
        self.slot = None
        self.ctx = None

    def resolve(self, dec):
        w = self.w
        cid = dec["char"]
        c = w.chars[cid]
        cand = dec["chosen"]
        a = cand.a
        tgt = cand.target if isinstance(cand.target, str) and cand.target in w.chars else None
        ev = self.new_event(a["id"], None, [cid], [tgt] if tgt else [], a["importance"], {"action": a["id"]})
        if dec.get("player"):
            ev["data"]["player"] = True
            ev["importance"] = max(ev["importance"], 20)
        fx = Effects(w, ev)
        rng = self.streams.get("resolve", w.day, self.slot.slot, cid)
        RESOLVERS[a["resolver"]](self, c, cand, ev, fx, rng, self.ctx)
        self.slot.done.add(cid)
        for g in c.goals:
            if g["status"] == "active":
                adv = self.cat.goals[g["type"]]["advances"].get(a["id"])
                if adv:
                    from .decision import _goal_match
                    if _goal_match(self, c, cand, g, adv[1]):
                        g["progress"] = round(g.get("progress", 0) + adv[0], 2)
        if ev.get("skip"):
            social.update_labels(self, fx, ev)
            return
        tid = self.slot.traces.get(cid)
        if tid:
            ev["trace"] = tid
        self.finish(ev, fx)
        if ev.get("outcome") in ("declined", "busy", "invited") and cid not in self.slot.engaged and not dec.get("fallback"):
            self._fallback(dec, ev)

    def _fallback(self, dec, failed_ev):
        """When an invitation falls through, the person does their best solo option instead."""
        solo = [cd for cd in dec["cands"] if cd.a["resolver"] in ("solo", "pet_time")]
        if not solo:
            return
        best = max(solo, key=lambda cd: cd.u)
        d2 = {"char": dec["char"], "slot": dec["slot"], "cands": dec["cands"], "chosen": best, "fallback": True,
              "trace": None}
        w = self.w
        c = w.chars[dec["char"]]
        a = best.a
        ev = self.new_event(a["id"], None, [c.id], [], a["importance"], {"action": a["id"], "fallback": True})
        ev["causes"] = [failed_ev["id"]]
        fx = Effects(w, ev)
        RESOLVERS[a["resolver"]](self, c, best, ev, fx, self.streams.get("fallback", w.day, self.slot.slot, c.id), self.ctx)
        if ev.get("calc") is not None:
            ev["calc"].insert(0, {"step": "plan B", "rule": "invitation fell through, so they did their highest-utility solo option",
                                  "outcome": a["label"], "total": round(best.u, 2)})
        ev["trace"] = self.slot.traces.get(c.id)
        self.finish(ev, fx)

    def _asked_first(self, target, inviter) -> str | None:
        """They asked you (by text, along with their people, as your group's plan): picking them from your choices is a
        yes to that, never a fresh ask they can turn down."""
        w = self.w
        if inviter != w.meta.get("protagonist"):
            return None
        slot = self.slot.slot
        for inv in w.meta.get("inbox", []):
            if inv["from"] == target and inv["to"] == inviter and inv["status"] == "pending" \
                    and inv.get("day", w.day) >= w.day - 1:
                inv["status"] = "accepted"
                return "they asked you to hang out"
        gi = w.meta.get("group_invite")
        if gi and gi.get("day") == w.day and gi.get("host") == target and gi.get("slot") == slot and gi.get("answer") != "no":
            gi["answer"] = "yes"
            return "they asked you along"
        q = w.meta.get("control", {}).get("queued") or {}
        if q.get("agreed") and q.get("target") == target and q.get("day", w.day) <= w.day:
            w.meta["control"].pop("queued", None)
            return "you already made these plans by text"
        from . import squad
        p = squad.plan(self)
        s = squad.state(self)
        if p and s and p.get("slot") == slot and target in s.get("ids", []):
            return "your group made plans for now"
        return None

    def respond(self, target, inviter, cand, rng, ev) -> str:
        """The invited person decides whether to accept, weighing it against their own plan."""
        w = self.w
        T = w.chars[target]
        from .moments import control
        mine = self.slot.planned.get(target, {}).get("player")
        if (target == w.meta.get("protagonist") and cand.a["id"] in ("hang_out", "date") and (inviter, target) not in self.slot.agreed
                and (control(w).get("ask_invites") or mine)):
            # it's your call: an invite waits for your answer. If you already picked something for now, it's a rain check:
            # they text you about later, and your pick stands.
            inv = {"id": f"in{w.next_id('invite')}", "day": w.day, "slot": self.slot.slot, "from": inviter, "to": target,
                   "action": cand.a["id"], "status": "pending", "event": ev.get("id"), "later": bool(mine)}
            w.meta.setdefault("inbox", []).append(inv)
            if cand.a["id"] == "hang_out":
                from .squad import note_ask
                note_ask(w)
            if "phone" in w.meta:
                from . import messages
                messages.invite_text(self, inv)
            if ev.get("calc") is not None:
                ev["calc"].append({"step": f"{T.short}'s answer", "outcome": "waiting for you",
                                   "rule": "invitations to your character wait in your inbox"})
            return "invited"
        asked = self._asked_first(target, inviter)
        if ((inviter, target) in self.slot.agreed or asked) and target not in self.slot.engaged:
            if ev.get("calc") is not None:
                ev["calc"].append({"step": f"{T.short}'s answer", "outcome": "accepted",
                                   "rule": asked or "you already made these plans by text"})
            if target not in self.slot.done and self.slot.planned.get(target):
                self.cancel_plan(target, f"had plans with {w.chars[inviter].short}")
            return "accepted"
        if target in self.slot.engaged:
            if ev.get("calc") is not None:
                ev["calc"].append({"step": f"{T.short}'s answer", "outcome": "busy",
                                   "rule": f"already with {w.chars[self.slot.engaged[target]].short} this slot"})
            return "busy"
        for req in cand.a["requires"]:
            if requirement(self, T, req, self.ctx) is None:
                if ev.get("calc") is not None:
                    ev["calc"].append({"step": f"{T.short}'s answer", "outcome": "declined", "rule": f"can't: fails '{req}'"})
                return "declined"
        plan = self.slot.planned.get(target)
        if plan and target in self.slot.done and plan["chosen"].a["category"] in ("social", "romance", "obligation"):
            if ev.get("calc") is not None:
                ev["calc"].append({"step": f"{T.short}'s answer", "outcome": "busy",
                                   "rule": f"already doing: {plan['chosen'].a['label']}"})
            return "busy"
        own_u = plan["chosen"].u if plan else 0.0
        own = plan["chosen"].a["label"] if plan else "nothing in particular"
        c2 = Cand(cand.a, inviter, None, "invited")
        acc_u = score(self, T, c2, self.char_ctx(T), None) + 4.0
        temp = temperature(self, T)
        p = sigmoid((acc_u - own_u) / temp)
        roll = rng.random()
        ok = roll < p
        if ev.get("calc") is not None:
            ev["calc"].append({"step": f"{T.short}'s answer", "terms": [[f"{T.short}'s own plan: {own}", round(own_u, 2)],
                                                                          [f"appeal of going with {w.chars[inviter].short} (+4 for being asked)", round(acc_u, 2)],
                                                                          [f"{T.short}'s temperature", round(temp, 2)]],
                               "p": round(p, 3), "roll": round(roll, 4), "outcome": "accepted" if ok else "declined",
                               "rule": "P(yes) = sigmoid((appeal - own plan) / temperature)"})
        if ok and target not in self.slot.done:
            self.cancel_plan(target, f"changed plans to join {w.chars[inviter].short}")
        return "accepted" if ok else "declined"

    def engage(self, cid, other):
        if self.slot is not None:
            self.slot.engaged[cid] = other

    def cancel_plan(self, cid, reason):
        self.slot.done.add(cid)
        self.slot.cancelled[cid] = reason
        tid = self.slot.traces.get(cid)
        if tid and tid in self.w.history.traces:
            self.w.history.traces[tid]["cancelled"] = reason

    def attach_traces(self, ev, cids):
        if self.slot is None or not self.w.tracing:
            return
        links = {}
        for cid in cids:
            tid = self.slot.traces.get(cid)
            if tid:
                links[cid] = tid
        if links:
            ev["traces"] = links

    # --- events --------------------------------------------------------------------
    def new_event(self, etype, outcome, actors, targets, importance, data, group=None, involved=None):
        w = self.w
        return {"id": w.history.reserve(), "day": w.day, "slot": self.current_phase(), "type": etype, "outcome": outcome,
                "actors": list(actors), "targets": [t for t in targets if t], "involved": list(involved or []),
                "group": group, "importance": importance, "data": data, "changes": [] if w.tracing else None,
                "calc": [] if w.tracing else None, "trace": None, "causes": [], "memories": [], "text": None}

    def finish(self, ev, fx, record=True):
        w = self.w
        social.update_labels(self, fx, ev)
        if "phone" in w.meta:
            from . import messages
            messages.on_event(self, ev)
        key = f"{ev['type']}.{ev.get('outcome')}"
        t = w.meta.setdefault("tally", {})
        t[key] = t.get(key, 0) + 1
        if not record or not w.tracing:
            return
        if ev.get("text") is None:
            ev["text"] = render(self, ev)
        w.history.add(ev)
        if ev.get("trace") and ev["trace"] in w.history.traces:
            w.history.traces[ev["trace"]]["event"] = ev["id"]
        for cid, tid in (ev.get("traces") or {}).items():
            if tid in w.history.traces:
                w.history.traces[tid]["event"] = ev["id"]

    def milestone_event(self, kind, a, b, cause_ev, importance):
        w = self.w
        ev = self.new_event("milestone", kind, [a], [b], importance, {})
        if cause_ev and cause_ev.get("id"):
            ev["causes"] = [cause_ev["id"]]
        r = w.rels.get((a, b))
        if r is not None:
            ev["data"]["snapshot"] = {"affection": round(r.affection, 1), "trust": round(r.trust, 1),
                                      "rivalry": round(r.rivalry, 1), "attraction": round(r.attraction, 1),
                                      "their_affection": round(w.rels[(b, a)].affection, 1) if (b, a) in w.rels else None}
        self.finish(ev, Effects(w, None))

    def schedule(self, day, kind, payload, cause):
        self.w.schedule.append({"day": day, "kind": kind, "payload": payload, "cause": cause})

    # --- character helpers ---------------------------------------------------------
    def expect(self, cid, aid, valence):
        c = self.w.chars[cid]
        e = c.expectations.get(aid, 0.0)
        c.expectations[aid] = round(e + self.w.rules["dev.learning_rate"] * (valence - e), 4)

    def confidence(self, cid, delta, fx, why):
        c = self.w.chars[cid]
        d = delta * self.w.rules["dev.confidence_drift"] * (0.6 + c.traits["volatility"] / 125)
        fx.trait(cid, "confidence", d, why)

    def siblings(self, cid) -> list:
        c = self.w.chars[cid]
        h = self.w.households.get(c.household_id)
        if not h:
            return []
        return sorted(m for m in h["members"] if m != cid and m in self.w.chars and self.w.chars[m].status == "active")

    def target_name(self, cand) -> str | None:
        w = self.w
        t = cand.target
        if t is None:
            if cand.a["id"] == "pet_time":
                h = w.households.get(w.chars[cand.extra].household_id) if isinstance(cand.extra, str) else None
                return h["pet"]["name"] if h and h.get("pet") else "the pet"
            if isinstance(cand.extra, dict) and cand.extra.get("name"):
                return cand.extra["name"]
            return None
        if isinstance(t, str):
            if t in w.chars:
                return w.chars[t].name
            if cand.a["target"] == "skill" and t in self.cat.skills:
                return self.cat.skills[t]["label"]
            if cand.a["target"] == "hobby" and t in self.cat.hobbies:
                return self.cat.hobbies[t]["label"]
            if t in w.groups:
                return w.groups[t]["name"]
            if t in self.cat.skills:
                return self.cat.skills[t]["label"]
            if t in self.cat.hobbies:
                return self.cat.hobbies[t]["label"]
            if isinstance(cand.extra, dict) and cand.extra.get("name"):
                return cand.extra["name"]
            if t.startswith("party:"):
                return f"{w.chars[t.split(':')[1]].short}'s party"
            return t
        return None

    def moment_trigger(self, kind, cid, ctx):
        """Story moments are for the protagonist; everyone else decides on their own."""
        from . import moments
        moments.trigger(self, kind, cid, ctx)

    def add_goal(self, c, gtype, target, label, priority, **kw):
        return development.add_goal(self, c, gtype, target, label, priority, **kw)

    def review_goals_for(self, c):
        development.review_goals(self, c, self.streams.get("goals", self.w.day, c.id))

    # --- player mode ----------------------------------------------------------------
    def options_for(self, cid):
        ph = self.run_until_slot_for(cid)
        if ph is None:
            return None
        self.ctx = self.slot_ctx(ph)
        dec = self.decide_for(cid, ph, trace=True)
        self.ctx = None
        return ph, dec

    def act_as(self, cid, index):
        ph = self.current_phase()
        if ph not in calm.DECISION_SLOTS or cid not in self.slot_actors(ph):
            raise EditError("it is not this character's turn; ask for options first")
        before = self.w.history.next_event
        self.step({cid: index})
        evs = [e for eid, e in self.w.history.events.items() if eid >= before and
               (cid in e["actors"] or cid in e["targets"] or cid in e.get("involved", []))]
        return evs

    # --- lab edits ------------------------------------------------------------------
    def set_rules(self, changes: dict, note: str = ""):
        sch = schema()
        clean = sch.validate(changes)
        merged = dict(self.w.rules)
        merged.update(clean)
        sch.validate_full(merged)
        diffs = [[k, self.w.rules[k], v] for k, v in clean.items() if self.w.rules[k] != v]
        if not diffs:
            return []
        self.w.rules = merged
        self._note_rules()
        self.w.rule_changes.append({"day": self.w.day, "changes": diffs, "note": note, "version": rules_hash(merged)})
        ev = self.new_event("lab", "rules", [], [], 30, {"label": ", ".join(f"{k} {o} -> {n}" for k, o, n in diffs), "changes": diffs})
        self.finish(ev, Effects(self.w, ev))
        return diffs

    def set_action_override(self, action_id: str, changes: dict):
        clean = self.cat.validate_action_override(action_id, changes)
        ov = self.w.action_overrides.setdefault(action_id, {})
        for k, v in clean.items():
            if isinstance(v, dict):
                ov.setdefault(k, {}).update(v)
            else:
                ov[k] = v
        self.cat = Catalogs(self.w.action_overrides)
        ev = self.new_event("lab", "rules", [], [], 30, {"label": f"action {action_id}: {clean}"})
        self.finish(ev, Effects(self.w, ev))
        return clean

    def reset_action(self, action_id: str):
        self.w.action_overrides.pop(action_id, None)
        self.cat = Catalogs(self.w.action_overrides)

    EDITABLE_LAYERS = {"traits": TRAITS, "aptitudes": APTITUDES, "motives": MOTIVES, "needs": NEEDS}

    def edit_character(self, cid, changes: dict):
        w = self.w
        c = w.chars.get(cid)
        if c is None:
            raise EditError(f"no character {cid}")
        errors, plan = [], []
        for layer, vals in changes.items():
            if layer in ("traits", "aptitudes", "motives", "needs", "skills", "interests"):
                if not isinstance(vals, dict):
                    errors.append(f"{layer} must be an object")
                    continue
                allowed = self.EDITABLE_LAYERS.get(layer) or (list(self.cat.skills) if layer == "skills" else list(self.cat.skills) + list(self.cat.hobbies))
                for k, v in vals.items():
                    if k not in allowed:
                        errors.append(f"{layer}.{k} is not a known attribute")
                        continue
                    try:
                        num = float(v)
                    except (TypeError, ValueError):
                        errors.append(f"{layer}.{k} must be a number")
                        continue
                    if not (0 <= num <= 100):
                        errors.append(f"{layer}.{k} must be between 0 and 100")
                        continue
                    plan.append((layer, k, num))
            elif layer in ("mood", "money", "popularity", "gpa"):
                try:
                    num = float(vals)
                except (TypeError, ValueError):
                    errors.append(f"{layer} must be a number")
                    continue
                lim = {"mood": (0, 100), "money": (0, 100000), "popularity": (0, 100), "gpa": (0, 4)}[layer]
                if not (lim[0] <= num <= lim[1]):
                    errors.append(f"{layer} must be between {lim[0]} and {lim[1]}")
                    continue
                plan.append((layer, None, num))
            elif layer in ("bio", "first", "last"):
                if not isinstance(vals, str) or not vals.strip() or len(vals) > 400:
                    errors.append(f"{layer} must be non-empty text under 400 characters")
                    continue
                plan.append((layer, None, vals.strip()))
            else:
                errors.append(f"{layer} cannot be edited")
        if errors:
            raise EditError("; ".join(errors))
        ev = self.new_event("lab", "edit", [cid], [], 30, {})
        fx = Effects(w, ev)
        for layer, k, v in plan:
            if k is not None:
                before = getattr(c, layer).get(k, 0.0)
                fx.attr(cid, layer, k, v - before, "lab edit")
                if layer == "traits" and k == "confidence":
                    c.flags["confidence_base"] = v
            elif layer in ("bio", "first", "last"):
                if w.tracing:
                    ev["changes"].append([cid, layer, getattr(c, layer), v, "lab edit"])
                setattr(c, layer, v)
            else:
                fx.scalar(cid, layer, v, "lab edit")
        ev["data"]["label"] = f"{c.name}: " + ", ".join(f"{l}{'.' + k if k else ''} = {v if isinstance(v, str) else round(v, 1)}"
                                                          for l, k, v in plan)
        self.finish(ev, fx)
        from . import groundwork
        groundwork.note_person(w, cid, changes)
        return ev

    def create_custom(self, spec: dict):
        """A fully specified character from the builder, added to the running world."""
        from .story import REL_PRESETS, StoryError, apply_relationship, build_person, build_staff, validate_person
        from .worldgen import Generator, initial_relationships
        w = self.w
        errors = []
        validate_person(spec, "character", self.cat, errors, allow_staff=True)
        prot = w.meta.get("protagonist")
        for r in spec.get("relationships") or []:
            to = prot if r.get("to") == "me" else r.get("to")
            if to not in w.chars:
                errors.append(f"relationships: {r.get('to')} isn't anyone in this world")
        if errors:
            raise EditError("; ".join(errors))
        gen = Generator(w.gen_seed)
        gen.used_names = {(c.first, c.last) for c in w.chars.values()}
        gen.used_last = {h["last"] for h in w.households.values()}
        n = w.next_id("char")
        rng = gen.streams.get("gen", "custom", n)
        if spec.get("role") == "staff":
            c = build_staff(w, rng, spec)
        else:
            hh = spec.get("household")
            if hh == "family" and prot and w.chars[prot].household_id:
                h = w.households[w.chars[prot].household_id]
            elif hh in w.households:
                h = w.households[hh]
            else:
                h = gen.household(w, rng, last=(spec.get("last") or None))
            c = build_person(w, gen, rng, spec, h, day=w.day)
            initial_relationships(gen, w, gen.streams.get("gen", "custom-rels", n), day=w.day, only={c.id})
            if hh == "family" and prot:
                apply_relationship(w, c.id, prot, "sibling", day=w.day)
        for r in spec.get("relationships") or []:
            to = prot if r.get("to") == "me" else r.get("to")
            apply_relationship(w, c.id, to, r["type"], float(r.get("strength", 0) or 0), day=w.day)
        for (a, b), r in w.rels.items():
            if c.id in (a, b):
                r.label = social.label_for(r, w.rules)
        ev = self.new_event("lab", "created", [c.id], [], 30, {})
        self.finish(ev, Effects(w, ev))
        self.review_goals_for(c)
        return c

    def create_character(self, spec: dict):
        from .worldgen import Generator, initial_relationships
        w = self.w
        grade = spec.get("grade", 9)
        if grade not in (9, 10, 11, 12):
            raise EditError("grade must be 9-12")
        arch = spec.get("archetype")
        if arch and arch not in {a["id"] for a in self.cat.people["archetypes"]}:
            raise EditError(f"unknown archetype {arch}")
        gen = Generator(w.gen_seed)
        gen.used_names = {(c.first, c.last) for c in w.chars.values()}
        gen.used_last = {h["last"] for h in w.households.values()}
        n = w.next_id("char")
        rng = gen.streams.get("gen", "lab", n, spec.get("seed", 0))
        h = w.households.get(spec.get("household")) if spec.get("household") else None
        if h is None:
            h = gen.household(w, rng, last=spec.get("last") or None)
        gender = spec.get("gender") if spec.get("gender") in ("f", "m", "nb") else None
        c = gen.make_student(w, rng, grade, h, archetype=arch, first=spec.get("first") or None, gender=gender, day=w.day)
        initial_relationships(gen, w, gen.streams.get("gen", "lab-rels", n), day=w.day, only={c.id})
        for (a, b), r in w.rels.items():
            if c.id in (a, b):
                r.label = social.label_for(r, w.rules)
        ev = self.new_event("lab", "created", [c.id], [], 30, {})
        self.finish(ev, Effects(w, ev))
        edits = {k: v for k, v in spec.items() if k in ("traits", "aptitudes", "motives", "skills", "interests", "bio")}
        if edits:
            self.edit_character(c.id, edits)
        self.review_goals_for(c)
        return c
