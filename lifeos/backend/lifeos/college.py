"""Life after high school: graduates' paths, the protagonist's college, offscreen lives, breaks at home.

Every graduate gets a path during senior spring: play a sport in college, go to college as a
regular student, or stay in town and work. On Sept 1 the paths take effect:
  - the protagonist's college is built the first time anyone from town arrives there: teams,
    clubs, a campus job, coaches, a professor, a roommate and a cohort of classmates;
  - graduates going to other colleges move offscreen (lightweight weekly updates, no daily
    decisions) and come home for Thanksgiving, winter, spring and summer breaks;
  - graduates who stay start full-time jobs in town and keep their relationships.
"""
from __future__ import annotations

import copy

from . import calendar as calm
from .history import Effects
from .rng import clamp

COLLEGE_TEAMS = {"football": {"capacity": 22, "starters": 11, "tryout": [9, 2], "season": {"start": [9, 1], "end": [11, 21]}, "game_day": 5},
                 "basketball": {"capacity": 13, "starters": 5, "tryout": [10, 27], "season": {"start": [10, 27], "end": [3, 6]}, "game_day": 5},
                 "baseball": {"capacity": 18, "starters": 9, "tryout": [2, 3], "season": {"start": [2, 2], "end": [5, 15]}, "game_day": 5},
                 "soccer": {"capacity": 24, "starters": 11, "tryout": [9, 2], "season": {"start": [9, 1], "end": [11, 14]}, "game_day": 4},
                 "softball": {"capacity": 18, "starters": 9, "tryout": [2, 3], "season": {"start": [2, 7], "end": [5, 15]}, "game_day": 6}}
ATHLETES = {"football": 4, "basketball": 3, "baseball": 3, "soccer": 3, "softball": 3}


def sides(col) -> list:
    """The college's teams as side keys: 'basketball' (men's), 'basketball_w' (women's), 'softball', ..."""
    return [k for k in col.get("programs", {}) if (k[:-2] if k.endswith("_w") else k) in COLLEGE_TEAMS]


def side_sport(sd: str) -> str:
    return sd[:-2] if sd.endswith("_w") else sd


def side_gender(sd: str) -> str:
    from .sports import ONLY
    return "f" if sd.endswith("_w") else ONLY.get(sd, "m")


def team_id(w, c, sport):
    """The college team this person would play on (men's or women's), if the college has one."""
    from .sports import team_for
    return team_for(w, c, sport, "college") if sport else None


def college_meta(w):
    return w.meta.get("college")


def ensure_college(sim, college_id: str):
    """Build the protagonist's college the first time it is needed."""
    from .worldgen import Generator, initial_relationships
    w = sim.w
    if w.meta.get("college"):
        return w.meta["college"]
    from .sports import team_level
    col = sim.cat.college_by_id[college_id]
    levels = {s: round(team_level(col, s), 1) for s in sides(col)}
    meta = {"id": col["id"], "name": col["name"], "short": col.get("short", col["name"]), "tier": col["tier"],
            "conference": col.get("conference"), "location": col.get("location"), "levels": levels,
            "level": round(sum(levels.values()) / len(levels), 1) if levels else 65.0, "mascot": col.get("mascot", ""), "created": w.day}
    w.meta["college"] = meta
    gen = Generator(w.gen_seed)
    gen.used_names = {(c.first, c.last) for c in w.chars.values()}
    gen.used_last = {h["last"] for h in w.households.values()}
    rng = gen.streams.get("gen", "college", col["id"])
    # staff and teams: men's and women's sides
    from .model import Character
    from .catalogs import APTITUDES
    staff = [add_team(sim, meta, sd, rng) for sd in sides(col)]
    staff.append(Character(id="col_prof", first="Helen", last="Marwick", gender="f", pronouns="she/her", role="staff", grade=None,
                           birth_day=w.day - 19000, household_id=None, archetype="staff", title="Prof.", role_label=f"Professor at {meta['short']}",
                           school="college", location="college",
                           traits={"sociability": 55.0, "confidence": 70.0, "discipline": 80.0, "ambition": 60.0, "impulsivity": 25.0, "empathy": 70.0,
                                   "competitiveness": 40.0, "curiosity": 90.0, "volatility": 30.0, "loyalty": 60.0},
                           aptitudes={a: 60.0 for a in APTITUDES}, motives={"achievement": 60.0, "approval": 30.0, "belonging": 45.0, "pleasure": 40.0, "altruism": 75.0, "mastery": 80.0},
                           needs={"energy": 70.0, "social": 60.0, "fun": 55.0, "stress": 30.0}, mood=62.0, money=500.0,
                           bio="Teaches the intro seminar every freshman takes."))
    for s in staff:
        from .worldgen import pronouns_for
        s.pronouns = s.pronouns or pronouns_for(s.gender)
        s.color = "#9aa1c4"
        w.chars[s.id] = s
    extra = [("col_intramurals", "Intramural League", "club", "fitness", "open", 30, [1, 3]),
             ("col_media", "Campus Radio & Paper", "club", "writing", "open", 20, [2])]
    for gid, name, kind, skill, sel, cap, days in extra:
        w.groups[gid] = {"id": gid, "name": name, "kind": kind, "skill": skill, "selection": sel, "capacity": cap, "practice_days": days,
                         "prestige": 20, "school": "college", "members": [], "leaders": [], "absences": {}, "cut": [],
                         "record": {"w": 0, "l": 0}, "production": None, "joined": {}, "history": [], "streak": 0}
    # townies who were already here (an older sibling, a teammate from home) are now on campus with you
    for c in sorted(w.chars.values(), key=lambda c: c.id):
        if c.status == "active" and c.school == f"away:{col['id']}":
            c.school = "college"
            if c.flags.get("term_location"):
                c.flags["term_location"] = "college"
            else:
                c.location = "college"
            gid = team_id(w, c, (c.path or {}).get("sport"))
            if gid:
                Effects(w, None).join(c.id, gid, "already on the roster")
    w.groups["col_job"] = {"id": "col_job", "name": f"{meta['short']} Dining Hall", "kind": "job", "skill": None, "selection": "hire",
                           "capacity": 8, "shift_days": [1, 3], "pay": 55, "min_age": 17, "prestige": 5, "school": None, "location": "college",
                           "members": [], "leaders": [], "absences": {}, "cut": [], "record": {"w": 0, "l": 0}, "production": None,
                           "joined": {}, "history": [], "streak": 0}
    # classmates
    cohort = add_college_students(sim, rng, {13: 7, 14: 5, 15: 5, 16: 5}, col)
    initial_relationships(gen, w, gen.streams.get("gen", "college-rels", col["id"]), day=w.day, only={c.id for c in cohort})
    for s in staff:
        for c in cohort:
            for x, y in ((s.id, c.id), (c.id, s.id)):
                r = w.ensure_rel(x, y, w.day)
                r.familiarity = 25.0 if c.grade > 13 else 5.0
    add_calendar(sim, calm.school_year_of(w.day))
    return meta


def add_team(sim, meta, sd, rng):
    """One college team (a side: 'soccer' is men's soccer, 'soccer_w' women's) and its coach. Returns the coach
    (not yet in the world: the caller adds them)."""
    from .model import Character
    from .catalogs import APTITUDES
    from .sports import side_label
    w = sim.w
    sport = side_sport(sd)
    label = side_label(sport, side_gender(sd), sim.cat.sports["sports"])
    sid = f"col_coach_{sd}"
    first = rng.choice(["Rob", "Teresa", "Marcus", "Dana", "Glenn", "Alicia", "Vic", "Pam"])
    last = rng.choice(["Hollister", "Vance", "Okonkwo", "Brandt", "Salazar", "Whitcomb", "Pruitt", "Lindgren"])
    coach = Character(id=sid, first=first, last=last, gender="m" if first in ("Rob", "Marcus", "Glenn", "Vic") else "f",
                      pronouns="", role="staff", grade=None, birth_day=w.day - 16000, household_id=None, archetype="staff",
                      title="Coach", role_label=f"{meta['short']} {label.lower()} coach", school="college", location="college",
                      traits={t: round(clamp(rng.gauss(60, 12), 20, 95), 1) for t in ("sociability", "confidence", "discipline", "ambition", "impulsivity", "empathy", "competitiveness", "curiosity", "volatility", "loyalty")},
                      aptitudes={a: 55.0 for a in APTITUDES}, motives={"achievement": 70.0, "approval": 40.0, "belonging": 45.0, "pleasure": 35.0, "altruism": 50.0, "mastery": 60.0},
                      needs={"energy": 70.0, "social": 60.0, "fun": 55.0, "stress": 30.0}, mood=60.0, money=500.0,
                      bio=f"Runs the {label.lower()} program at {meta['name']}.")
    spec = COLLEGE_TEAMS[sport]
    gid = f"col_{sd}"
    gd = spec["game_day"]
    w.groups[gid] = {"id": gid, "name": f"{meta['short']} {label}", "kind": "team", "skill": sport, "side": sd, "gender": side_gender(sd),
                     "selection": "tryout", "capacity": spec["capacity"], "jv_capacity": 0, "starters": spec["starters"],
                     "season": copy.deepcopy(spec["season"]), "tryout": spec["tryout"],
                     "practice_days": [d for d in (0, 1, 2, 3, 4) if d != gd][:4],
                     "game_day": gd, "staff": sid, "prestige": 80, "school": "college",
                     "members": [], "leaders": [], "absences": {}, "cut": [], "record": {"w": 0, "l": 0}, "production": None,
                     "joined": {}, "history": [], "streak": 0, "levels": {}}
    return coach


def add_college_students(sim, rng, per_grade: dict, col):
    """College classmates. Some are recruited athletes with college-level skills."""
    from .worldgen import Generator
    from . import sports
    w = sim.w
    gen = Generator(w.gen_seed)
    gen.used_names = {(c.first, c.last) for c in w.chars.values()}
    gen.used_last = {h["last"] for h in w.households.values()}
    out = []
    from .sports import team_level
    athletes_left = {sd: ATHLETES[side_sport(sd)] for sd in sides(col)}
    for grade, n in sorted(per_grade.items()):
        for _ in range(n):
            h = {"id": None, "last": None, "income": "middle", "members": []}
            last = rng.choice(sim.cat.people["names"]["last"])
            h["last"] = last
            c = gen.make_student(w, rng, 12, h, day=w.day)
            c.grade = grade
            c.birth_day -= int((grade - 12) * 365.25)
            c.household_id = None
            c.school = "college"
            c.location = "college"
            c.bio = c.bio.replace("type;", "type, here from out of state;", 1)
            for k in c.skills:
                c.skills[k] = round(clamp(c.skills[k] + 6 + (grade - 13) * 3, 0, 85), 1)
            from .sports import side as side_of
            sd = next((x for x, k in athletes_left.items() if k > 0 and side_of(side_sport(x), c.gender) == x
                       and rng.random() < 0.5), None)
            sport = side_sport(sd) if sd else None
            if sport:
                athletes_left[sd] -= 1
                c.interests[sport] = round(clamp(rng.gauss(85, 6), 60, 99), 1)
                c.aptitudes["athletic"] = round(clamp(rng.gauss(75, 8), 55, 98), 1)
                c.skills[sport] = round(clamp(rng.gauss(team_level(col, sd) - 2 + (grade - 13) * 3, 5), 45, 92), 1)
                c.skills["fitness"] = round(clamp(rng.gauss(70, 8), 40, 95), 1)
                c.path = {"kind": "college", "college": col["id"], "sport": sport, "scholarship": True}
                sports.ensure_athlete(c, sport, rng)
            out.append(c)
    return out


def add_calendar(sim, year: int):
    """Tryouts, games and exams for the college's groups in this school year."""
    w = sim.w
    cal = sim.cat.world["calendar"]
    groups = {gid: g for gid, g in w.groups.items() if g.get("school") == "college"}
    have = {i["key"] for i in w.calendar}
    items = calm.build_year(w, sim.cat, year, only=set(groups))
    for ev in cal["events"]:
        if ev["kind"] == "exam":
            d = calm.md_to_day(year, ev["date"])
            d = d if calm.is_school_day(d, cal) else calm.next_school_day(d, cal)
            items.append({"day": d, "kind": "exam", "slot": "classes", "name": f"College {ev['name'].lower()}", "id": "col_" + ev["id"],
                          "weight": ev.get("weight", 1), "school": "college", "key": f"exam:col_{ev['id']}:{year}"})
    items = [i for i in items if i["key"] not in have and i["day"] >= w.day]
    w.calendar.extend(items)
    w.calendar.sort(key=lambda i: (i["day"], i["kind"], i.get("group") or "", i["key"]))


# --- paths take effect ------------------------------------------------------------------

def depart(sim, rng):
    """Sept 1: graduates with a path leave (or start working). Runs inside new_year."""
    w = sim.w
    prot = w.meta.get("protagonist")
    leaving = [c for c in sorted(w.chars.values(), key=lambda c: c.id)
               if c.status == "active" and c.role == "alumni" and c.path and not c.path.get("started")]
    pc = w.chars.get(prot) if prot else None
    if pc and pc in leaving and pc.path.get("kind") == "college":
        ensure_college(sim, pc.path["college"])
    col = w.meta.get("college")
    for c in leaving:
        p = c.path
        p["started"] = w.day
        if p["kind"] == "college":
            c.role = "student"
            c.grade = 13
            for gid in list(c.memberships):
                if w.groups[gid].get("location") == "hollow_creek" and w.groups[gid]["kind"] == "job":
                    Effects(w, None).leave(c.id, gid, "left for college")
            if col and p["college"] == col["id"]:
                c.school = "college"
                c.location = "college"
                where = col["name"]
            else:
                c.school = f"away:{p['college']}"
                c.location = "away"
                where = p.get("name") or "college"
            c.flags.pop("term_location", None)
            ev = sim.new_event("path", "left", [c.id], [], 32 if c.id != prot else 45, {"label": where})
            ev["text"] = f"{c.short} left {sim.cat.world['town']['name']} for {where}."
            fx = Effects(w, ev)
            fx.memory(c.id, "left_home", [], 0.5, 70, f"Left home for {where}")
            for sib in sim.siblings(c.id):
                fx.mood(sib, -4, f"{c.short} left for college")
                fx.memory(sib, "sibling_left", [c.id], -0.2, 50, f"{c.short} left for {where}")
                if sib == prot:
                    sim.moment_trigger("sibling_leaves", sib, {"sibling": c.id, "place": where})
            sim.finish(ev, fx)
        else:
            c.school = None
            c.location = "hollow_creek"
            job = "job_builders" if c.aptitudes.get("technical", 50) + c.aptitudes.get("athletic", 50) > 105 else "job_auto"
            ev = sim.new_event("path", "working", [c.id], [], 26 if c.id != prot else 40, {"label": w.groups[job]["name"]})
            ev["text"] = f"{c.short} started working full-time at {w.groups[job]['name']}."
            fx = Effects(w, ev)
            for gid in list(c.memberships):
                if w.groups[gid]["kind"] == "job":
                    fx.leave(c.id, gid, "took a full-time job")
            fx.join(c.id, job, "hired full-time")
            sim.finish(ev, fx)
        if p["kind"] == "college" and col and p["college"] == col["id"] and team_id(w, c, p.get("sport")):
            gid = team_id(w, c, p.get("sport"))
            if p.get("scholarship"):
                # recruited: they're on the roster from day one
                Effects(w, None).join(c.id, gid, "recruited")
                w.groups[gid].setdefault("levels", {})[c.id] = "varsity"
            else:
                it = next((i for i in w.calendar if i.get("group") == gid and i["kind"] == "tryout" and i["day"] >= w.day), None)
                if it:
                    w.registrations.setdefault(it["key"], []).append(c.id)
        if c.id == prot and p["kind"] == "college" and col and p["college"] == col["id"]:
            arrive(sim, c, rng)


def arrive(sim, c, rng):
    """The protagonist's first day at college: a roommate and a moment."""
    w = sim.w
    col = w.meta["college"]
    fresh = sorted((x for x in w.chars.values() if x.school == "college" and x.grade == 13 and x.id != c.id and x.role == "student"
                    and not x.household_id), key=lambda x: x.id)
    same = [x for x in fresh if x.gender == c.gender] or fresh
    room = same[int(rng.random() * len(same))] if same else None
    ctx = {"college": col["id"], "college_name": col["name"], "team_line": ""}
    if room:
        ev = sim.new_event("path", "roommate", [c.id], [room.id], 30, {"label": room.name})
        ev["text"] = f"{c.short} moved into the dorms at {col['short']}. Roommate: {room.name}."
        fx = Effects(w, ev)
        fx.add_bond(c.id, room.id, "roommate", "assigned roommates")
        for x, y in ((c.id, room.id), (room.id, c.id)):
            r = w.ensure_rel(x, y, w.day)
            r.familiarity = max(r.familiarity, 20.0)
        sim.finish(ev, fx)
        ctx["roommate"] = room.id
    sport = c.path.get("sport")
    gid = team_id(w, c, sport)
    if gid:
        ctx["coach"] = w.groups[gid]["staff"]
        ctx["team_line"] = f" {w.chars[ctx['coach']].name} wants the {sport} recruits at the facility by six."
    sim.moment_trigger("college_arrival", c.id, ctx)


def new_college_year(sim, rng):
    """College students move up a year; seniors finish; a new freshman class arrives."""
    w = sim.w
    col = w.meta.get("college")
    for c in sorted(w.chars.values(), key=lambda c: c.id):
        if c.status != "active" or c.role != "student" or c.school is None or c.school == "hchs":
            continue
        if c.path.get("started") == w.day:
            continue
        c.grade = (c.grade or 13) + 1
        if c.grade > 16:
            c.role = "alumni"
            c.grade = None
            if c.school == "college" and not c.household_id:
                c.status = "moved"
            c.school = None
            if c.location in ("away", "college") and c.household_id:
                c.location = "away"
    if col:
        add_college_students(sim, rng, {13: 5}, sim.cat.college_by_id[col["id"]])
        add_calendar(sim, calm.school_year_of(w.day))


def daily(sim):
    """Breaks: college students from town come home, then go back. Offscreen seasons wrap up."""
    w = sim.w
    d = calm.date_of(w.day)
    for sport, spec in COLLEGE_TEAMS.items():
        if (d.month, d.day) == tuple(spec["season"]["end"]):
            offscreen_season(sim, sport)
    on = calm.break_name(w.day, sim.cat.world["calendar"]) is not None
    was = w.meta.get("on_break", False)
    if on == was:
        return
    w.meta["on_break"] = on
    name = calm.break_name(w.day, sim.cat.world["calendar"]) or "the break"
    prot = w.meta.get("protagonist")
    for c in sorted(w.chars.values(), key=lambda c: c.id):
        if c.status != "active" or not c.household_id or c.household_id not in w.households:
            continue
        if on and c.location in ("away", "college"):
            c.flags["term_location"] = c.location
            c.location = "hollow_creek"
            near = c.id == prot or prot in sim.siblings(c.id)
            ev = sim.new_event("path", "home", [c.id], [], 20 if near else 6, {"label": name})
            ev["text"] = f"{c.short} is home for {name.lower()}."
            sim.finish(ev, Effects(w, ev))
        elif not on and c.flags.get("term_location"):
            c.location = c.flags.pop("term_location")


def offscreen_weekly(sim):
    """People away at college don't make daily choices; they drift along."""
    w = sim.w
    for c in w.chars.values():
        if c.status != "active" or c.location != "away":
            continue
        c.skills["academics"] = clamp(c.skills.get("academics", 40) + 0.4, 0, 100)
        sp = (c.path or {}).get("sport")
        if sp and (c.path or {}).get("kind") == "college":
            ceiling = 55 + c.aptitudes.get("athletic", 50) * 0.45
            c.skills[sp] = round(clamp(c.skills.get(sp, 40) + 0.22 * max(0.0, 1 - c.skills.get(sp, 40) / max(ceiling, 1)) * 3, 0, ceiling), 2)
            c.skills["fitness"] = round(clamp(c.skills.get("fitness", 40) + 0.1, 0, 95), 2)
        c.mood += (62 - c.mood) * 0.3
        c.needs["stress"] += (30 - c.needs["stress"]) * 0.3
        c.needs["social"] = 70.0
        c.needs["fun"] = 65.0
        c.needs["energy"] = 75.0


def season_games(sport) -> int:
    spec = COLLEGE_TEAMS[sport]["season"]
    start = calm.md_to_day(0, tuple(spec["start"]))
    end = calm.md_to_day(0, tuple(spec["end"]))
    return max(1, (end - start) // 7)


def offscreen_season(sim, sport):
    """College athletes from town who play somewhere else get a season summary: games, starts, a stat line."""
    from . import sports
    w = sim.w
    games = season_games(sport)
    for c in sorted(w.chars.values(), key=lambda c: c.id):
        p = c.path or {}
        if c.status != "active" or p.get("kind") != "college" or p.get("sport") != sport or not (c.school or "").startswith("away:"):
            continue
        col = sim.cat.college_by_id.get(p.get("college"))
        if not col or not sports.offers_side(col, sport, c.gender):
            continue
        sd = sports.side(sport, c.gender)
        rng = sim.streams.get("offscreen-season", w.day, c.id)
        lvl = sports.team_level(col, sd)
        r = sports.rating(c, sport)
        starter = r + ((c.grade or 13) - 13) * 2 >= lvl + 2  # experience counts
        pos = c.positions.get(sport) or sports.default_position(c, sport, rng)
        win_p = clamp(0.3 + sports.program(col, sd) / 250, 0.2, 0.85)
        skey = sports.season_key(sport, w.day - 1, "varsity")
        st = {"sport": sport, "level": "varsity", "team": f"away:{col['id']}:{sport}", "team_name": f"{col['short']} {sports.side_label(sport, c.gender, sim.cat.sports['sports'])}",
              "school": f"away:{col['id']}", "games": 0, "starts": 0, "wins": 0, "losses": 0, "line": {}, "impact": 0.0, "offscreen": True}
        for _ in range(games):
            if rng.random() < 0.06:
                continue  # sat out
            perf = r + rng.gauss(0, 7)
            f = clamp(perf / 62, 0.25, 1.8) * (1.0 if starter else 0.35)
            sports.add_line(st["line"], sports.stat_line(sport, pos, f, starter, rng))
            st["games"] += 1
            st["starts"] += 1 if starter else 0
            st["impact"] = round(st["impact"] + perf * (1.0 if starter else 0.3), 2)
            st["wins" if rng.random() < win_p else "losses"] += 1
        if not st["games"]:
            continue
        c.stats[skey] = st
        role = "starting" if starter else "off the bench"
        ev = sim.new_event("season", "offscreen", [c.id], [], 24 if c.id in sim.siblings(w.meta.get("protagonist") or "") else 10,
                           {"label": st["team_name"], "sport": sport})
        ev["text"] = (f"{c.short} finished the season at {col['short']}: {st['games']} games {role}, "
                      f"{sports.line_text(sport, st['line'])}. The team went {st['wins']}-{st['losses']}.")
        sim.finish(ev, Effects(w, ev))
