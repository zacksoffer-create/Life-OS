"""Boys' and girls' teams, and bringing a save made before them up to date.

Soccer (a boys' team and a girls' team, in the fall), girls' basketball and softball (the girls' spring sport) came after
the first saves. A save from before gets them once, the first time it loads:
  - the new teams join the world with this year's tryouts, games and season ends still ahead of today;
  - the boys' teams are marked as boys' teams;
  - a girl already on a boys' team moves to the girls' team for her season (basketball to girls' basketball, baseball to
    softball, football to girls' soccer), keeping her varsity or JV spot;
  - a girl's baseball becomes softball (interest, skill, position), and some kids pick up soccer, so the new teams have
    people to try out;
  - a college that's already built gets its women's teams (and soccer and softball where it has them).
"""
from __future__ import annotations

import copy

from . import calendar as calm
from . import sports
from .history import Effects
from .rng import clamp

VERSION = 1
MOVE = {"basketball": "basketball_girls", "baseball": "softball", "football": "soccer_girls"}


def upgrade(sim) -> dict | None:
    """Run once per save. Returns what changed (or None when the save is already current)."""
    w = sim.w
    if w.meta.get("teams_version", 0) >= VERSION:
        return None
    # a brand-new world already has every team: just mark it
    have = {g["id"] for g in w.groups.values()}
    want = [g for g in sim.cat.world["groups"] if g["kind"] == "team"]
    if all(g["id"] in have for g in want) and all(w.groups[g["id"]].get("gender") == g.get("gender") for g in want):
        w.meta["teams_version"] = VERSION
        return None
    out = {"added": [], "moved": [], "softball": [], "soccer": [], "college": []}
    added = set()
    for gd in want:
        g = w.groups.get(gd["id"])
        if g is None:
            g = copy.deepcopy(gd)
            g.update({"members": [], "leaders": [], "absences": {}, "cut": [], "record": {"w": 0, "l": 0}, "production": None,
                      "joined": {}, "history": [], "streak": 0})
            w.groups[g["id"]] = g
            added.add(g["id"])
            out["added"].append(g["id"])
        else:
            g["gender"] = gd.get("gender")
            if g["name"] == "Guilford Basketball":
                g["name"] = gd["name"]
    _staff(sim)
    _calendar(sim, added)
    rng = sim.streams.get("upgrade-teams")
    for c in sorted(w.chars.values(), key=lambda c: c.id):
        for s in sports.SPORTS:
            if s not in c.skills and c.role == "student":
                a = c.aptitudes.get("athletic", 50)
                c.skills[s] = round(clamp(a * 0.3 + c.interests.get(s, 0) * 0.28 + ((c.grade or 9) - 9) * 2.5, 0, 70), 1)
        if c.status != "active":
            continue
        for a, b in sports.fit_to_side(c):
            out["softball"].append(c.id)
        _move(sim, c, out)
        if c.role == "student" and c.school == "hchs" and "soccer" not in c.interests and c.gender in ("m", "f", "nb"):
            sporty = any(c.interests.get(s, 0) >= 50 for s in sports.SPORTS)
            p = (0.28 if c.gender == "f" else 0.18) + (0.12 if sporty else 0)
            if rng.random() < p:
                c.interests["soccer"] = round(clamp(rng.gauss(60 if sporty else 50, 12), 25, 92), 1)
                c.skills["soccer"] = round(max(c.skills.get("soccer", 0),
                                               clamp(c.aptitudes.get("athletic", 50) * 0.3 + c.interests["soccer"] * 0.28
                                                     + ((c.grade or 9) - 9) * 2.5, 0, 70)), 1)
                out["soccer"].append(c.id)
    _college(sim, out)
    w.meta["teams_version"] = VERSION
    return out


def _staff(sim):
    """The new coaches."""
    from .catalogs import APTITUDES, TRAITS
    from .model import Character
    from .worldgen import pronouns_for
    w = sim.w
    rng = sim.streams.get("upgrade-teams", "staff")
    for s in sim.cat.people["staff"]:
        if s["id"] in w.chars:
            continue
        traits = {t: float(s["traits"].get(t, 50)) for t in TRAITS}
        c = Character(id=s["id"], first=s["first"], last=s["last"], gender=s["gender"], pronouns=pronouns_for(s["gender"]),
                      role="staff", grade=None, birth_day=w.day - int(rng.uniform(30, 58) * 365.25), household_id=None,
                      archetype="staff", title=s["title"], role_label=s["role_label"], traits=traits,
                      aptitudes={a: 55.0 for a in APTITUDES}, skills={},
                      motives={"achievement": 60.0, "approval": 35.0, "belonging": 50.0, "pleasure": 40.0,
                               "altruism": round(30 + traits["empathy"] * 0.6, 1), "mastery": 55.0},
                      needs={"energy": 70.0, "social": 60.0, "fun": 55.0, "stress": 30.0}, mood=62.0,
                      interests={"reading": 50.0, "cooking": 40.0}, money=200.0, bio=s.get("bio", s["role_label"] + "."))
        c.color = "#9aa1c4"
        w.chars[c.id] = c
        for o in w.chars.values():
            if o.id == c.id or o.status != "active" or o.school != "hchs" and o.role != "staff":
                continue
            for x, y in ((c.id, o.id), (o.id, c.id)):
                r = w.ensure_rel(x, y, w.day)
                r.familiarity = max(r.familiarity, 8.0 if o.role == "student" else 40.0)


def _calendar(sim, added: set):
    """This school year's tryouts, games and season ends for the new teams, from today on."""
    w = sim.w
    if not added:
        return
    have = {i["key"] for i in w.calendar}
    items = calm.build_year(w, sim.cat, calm.school_year_of(w.day), only=added)
    w.calendar.extend(i for i in items if i["key"] not in have and i["day"] >= w.day)
    w.calendar.sort(key=lambda i: (i["day"], i["kind"], i.get("group") or "", i["key"]))


def _move(sim, c, out):
    """A girl on a boys' team moves to the girls' team for that season, keeping her level."""
    w = sim.w
    if c.gender != "f":
        return
    fx = Effects(w, None)
    for gid in list(c.memberships):
        g = w.groups.get(gid)
        if not g or g["kind"] != "team" or g.get("school") != "hchs" or sports.can_play(c, g):
            continue
        to = MOVE.get(gid)
        level = (g.get("levels") or {}).get(c.id, "varsity")
        g.get("levels", {}).pop(c.id, None)
        fx.leave(c.id, gid, "boys' and girls' teams split")
        if to and to in w.groups:
            fx.join(c.id, to, "boys' and girls' teams split")
            w.groups[to].setdefault("levels", {})[c.id] = level
            sport = w.groups[to]["skill"]
            if sport != g["skill"]:
                c.skills[sport] = round(max(c.skills.get(sport, 0), c.skills.get(g["skill"], 0) * 0.75), 1)
                c.interests[sport] = max(c.interests.get(sport, 0), c.interests.get(g["skill"], 0))
            sports.ensure_athlete(c, sport, sim.streams.get("upgrade-teams", c.id))
        out["moved"].append([c.id, gid, to])


def _college(sim, out):
    """A college built before the split gets its women's teams, soccer and softball, from today on."""
    from . import college
    w = sim.w
    meta = w.meta.get("college")
    if not meta or meta.get("id") not in sim.cat.college_by_id:
        return
    col = sim.cat.college_by_id[meta["id"]]
    rng = sim.streams.get("upgrade-teams", "college")
    new = set()
    for sd in college.sides(col):
        gid = f"col_{sd}"
        if gid in w.groups:
            g = w.groups[gid]
            g.setdefault("side", sd)
            g.setdefault("gender", college.side_gender(sd))
            continue
        coach = college.add_team(sim, meta, sd, rng)
        from .worldgen import pronouns_for
        coach.pronouns = pronouns_for(coach.gender)
        coach.color = "#9aa1c4"
        w.chars[coach.id] = coach
        meta.setdefault("levels", {})[sd] = round(sports.team_level(col, sd), 1)
        new.add(gid)
        out["college"].append(gid)
    if new:
        have = {i["key"] for i in w.calendar}
        items = calm.build_year(w, sim.cat, calm.school_year_of(w.day), only=new)
        w.calendar.extend(i for i in items if i["key"] not in have and i["day"] >= w.day)
        w.calendar.sort(key=lambda i: (i["day"], i["kind"], i.get("group") or "", i["key"]))
