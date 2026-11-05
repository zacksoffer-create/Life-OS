"""World statistics: used by the overview, the weekly time series, and experiments."""
from __future__ import annotations

from .calendar import label

METRIC_INFO = {
    "mutual_friendships": "Pairs of students who both count the other as a friend",
    "one_sided_friendships": "Pairs where only one of the two counts the other as a friend",
    "avg_friends": "Average number of people each student counts as a friend",
    "isolated_students": "Students with no mutual friendships",
    "rivalries": "Directed rival relationships (A sees B as a rival)",
    "dislikes": "Directed relationships below the dislike threshold",
    "couples": "Current couples",
    "cliques": "Active cliques",
    "clique_coverage": "Share of students in a clique",
    "avg_clique_size": "Average clique size",
    "popularity_gini": "Inequality of social standing (0 = equal, 1 = one person has it all)",
    "avg_mood": "Average mood", "avg_stress": "Average stress", "avg_gpa": "Average GPA",
    "asymmetry": "Average gap between how A feels about B and how B feels about A",
    "perception_error": "Average gap between what people believe others feel about them and the truth",
    "conflicts": "Arguments, falling-outs and fights so far",
    "exclusions": "Times someone was frozen out at lunch or left out of a party",
    "teasing": "Public mockery incidents",
    "rumors": "Rumors created", "rumor_spreads": "Times a rumor was passed on",
    "reconciliations": "Successful apologies",
    "friendships_formed": "New friendships (milestones)",
    "relationships_started": "Couples formed", "breakups": "Breakups",
    "parties": "Parties thrown", "team_spots": "Students on a team or in a cast",
    "club_members": "Club memberships",
}


def gini(xs):
    xs = sorted(max(0.0, x) for x in xs)
    n = len(xs)
    s = sum(xs)
    if n == 0 or s == 0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(xs))
    return round((2 * cum) / (n * s) - (n + 1) / n, 4)


def compute(w) -> dict:
    R = w.rules
    studs = sorted(c.id for c in w.chars.values() if c.role == "student" and c.status == "active" and c.school == "hchs")
    sset = set(studs)
    ft = R["rel.friend_threshold"]
    mutual = one = 0
    friends = {s: 0 for s in studs}
    mutual_of = {s: 0 for s in studs}
    asym, perr, nasym = 0.0, 0.0, 0
    rivals = dislikes = 0
    for (a, b), r in w.rels.items():
        if a not in sset or b not in sset:
            continue
        if r.affection >= ft:
            friends[a] += 1
        if r.label == "rival":
            rivals += 1
        if r.affection <= R["rel.enemy_threshold"]:
            dislikes += 1
        if a < b:
            r2 = w.rels.get((b, a))
            if r2 is None:
                continue
            fa, fb = r.affection >= ft, r2.affection >= ft
            if fa and fb:
                mutual += 1
                mutual_of[a] += 1
                mutual_of[b] += 1
            elif fa or fb:
                one += 1
            if r.familiarity >= 20 and r2.familiarity >= 20:
                asym += abs(r.affection - r2.affection)
                perr += (abs(r.perceived - r2.affection) + abs(r2.perceived - r.affection)) / 2
                nasym += 1
    n = max(1, len(studs))
    cl = [c for c in w.cliques.values() if c.get("active")]
    in_cl = sum(len(c["members"]) for c in cl)
    t = w.meta.get("tally", {})

    def tsum(*keys):
        return sum(v for k, v in t.items() if any(k == x or (x.endswith(".") and k.startswith(x)) for x in keys))

    raw = w.meta.get("popularity_raw", {})
    m = {
        "day": w.day,
        "students": len(studs),
        "mutual_friendships": mutual,
        "one_sided_friendships": one,
        "avg_friends": round(sum(friends.values()) / n, 3),
        "isolated_students": sum(1 for s in studs if mutual_of[s] == 0),
        "rivalries": rivals,
        "dislikes": dislikes,
        "couples": sum(1 for b in w.bonds.values() if "partner" in b["roles"]),
        "cliques": len(cl),
        "clique_coverage": round(in_cl / n, 3),
        "avg_clique_size": round(in_cl / len(cl), 2) if cl else 0.0,
        "popularity_gini": gini([raw.get(s, 0) for s in studs]) if raw else 0.0,
        "avg_mood": round(sum(w.chars[s].mood for s in studs) / n, 2),
        "avg_stress": round(sum(w.chars[s].needs["stress"] for s in studs) / n, 2),
        "avg_gpa": round(sum(w.chars[s].gpa for s in studs) / n, 3),
        "asymmetry": round(asym / nasym, 2) if nasym else 0.0,
        "perception_error": round(perr / nasym, 2) if nasym else 0.0,
        "conflicts": tsum("confront.argument", "confront.falling_out", "party.fight"),
        "exclusions": tsum("exclusion.excluded", "party.not_invited"),
        "teasing": tsum("tease.landed", "tease.backfired"),
        "rumors": len(w.rumors),
        "rumor_spreads": sum(r["spread"] for r in w.rumors.values()),
        "reconciliations": tsum("apologize.forgiven"),
        "friendships_formed": tsum("milestone.friends"),
        "relationships_started": tsum("milestone.dating"),
        "breakups": tsum("break_up."),
        "parties": tsum("party.thrown", "party.flop"),
        "team_spots": sum(len(g["members"]) for g in w.groups.values() if g["kind"] in ("team", "production")),
        "club_members": sum(len(g["members"]) for g in w.groups.values() if g["kind"] == "club"),
    }
    return m


SERIES_KEYS = ["mutual_friendships", "avg_friends", "isolated_students", "rivalries", "couples", "cliques",
               "popularity_gini", "avg_mood", "avg_stress", "avg_gpa", "conflicts", "exclusions", "rumors"]


def snapshot(w) -> dict:
    m = compute(w)
    s = {k: m[k] for k in SERIES_KEYS}
    s["day"] = w.day
    s["label"] = label(w.day)
    return s


def character_summary(w, cid) -> dict:
    """Compact per-character outcome used for deterministic experiment comparisons."""
    c = w.chars[cid]
    R = w.rules
    fr = sorted(o for o, r in w.out.get(cid, {}).items() if r.affection >= R["rel.friend_threshold"]
                and w.chars[o].role in ("student", "alumni"))
    return {"id": cid, "name": c.name, "role": c.role, "friends": len(fr), "friend_ids": fr,
            "popularity": round(c.popularity, 1), "mood": round(c.mood, 1), "stress": round(c.needs["stress"], 1),
            "gpa": round(c.gpa, 2), "memberships": sorted(c.memberships), "partner": c.flags.get("partner"),
            "clique": c.flags.get("clique"), "confidence": round(c.traits["confidence"], 1),
            "top_skill": max(c.skills.items(), key=lambda x: x[1])[0] if c.skills else None,
            "skills": {k: round(v, 1) for k, v in c.skills.items()}}
