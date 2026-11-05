"""Social engine: interaction outcomes, perception, relationship labels, popularity, cliques, rumors.

The core idea: an interaction has one true quality, but each participant experiences it
with their own noise, and each forms a *belief* about how the other felt. Affection is
updated from your own experience; 'perceived' (your estimate of their affection for you)
is updated from a noisy, confidence-biased reading of them. That is how one person ends
up thinking they're close friends while the other thinks they're acquaintances.
"""
from __future__ import annotations

from .model import pair_key
from .rng import clamp
from .worldgen import chemistry, compatibility, orientation_ok, stage_ok


FAMILY_ROLES = ("sibling", "twin", "parent", "child", "guardian")


def family(w, x: str, y: str) -> bool:
    """Same household (siblings, parents) or a family bond."""
    X, Y = w.chars.get(x), w.chars.get(y)
    if X is None or Y is None:
        return False
    if X.household_id and X.household_id == Y.household_id:
        return True
    bd = w.bonds.get(pair_key(x, y))
    return bool(bd and any(r in bd["roles"] for r in FAMILY_ROLES))


def can_be_into(w, x: str, y: str) -> bool:
    """Whether x could ever be into y at all: x is into y's gender, they aren't family, and it isn't a teacher or coach
    with a student. Attraction never goes up where this is False, whatever raised it (history.Effects.rel): a party, a
    hangout, a flirt, a storyline's `into +`."""
    X, Y = w.chars.get(x), w.chars.get(y)
    if X is None or Y is None or x == y:
        return False
    if not orientation_ok(X, Y) or family(w, x, y):
        return False
    return (X.role == "staff") == (Y.role == "staff")


def tidy_romance(sim) -> int:
    """Saves made before the rule above: attraction and crushes toward family, a teacher, or someone outside who they're
    into go back to nothing, along with dance dates and asks that came from them. Runs once per save. How many it fixed."""
    w = sim.w
    if w.meta.get("romance_rules", 0) >= 1:
        return 0
    n = 0
    for (a, b), r in w.rels.items():
        if (r.attraction > 0 or r.crush) and not can_be_into(w, a, b):
            r.attraction = 0.0
            r.crush = False
            n += 1
    for cid, c in w.chars.items():
        p = c.flags.get("partner")
        if p in w.chars and (family(w, cid, p) or (c.role == "staff") != (w.chars[p].role == "staff")):
            c.flags.pop("partner", None)
            w.chars[p].flags.pop("partner", None)
            n += 1
    for key, dd in (getattr(w, "dance_dates", None) or {}).items():
        for a in list(dd):
            b = dd.get(a)
            if b in w.chars and a in w.chars and not (can_be_into(w, a, b) or can_be_into(w, b, a)) \
                    and w.chars[a].flags.get("partner") != b:
                dd.pop(a, None)
                dd.pop(b, None)
                n += 1
    for m in w.meta.get("moments", []):
        o = (m.get("ctx") or {}).get("other")
        if m.get("status") == "pending" and m.get("kind") in ("asked_out", "asked_to_dance") and o in w.chars \
                and not can_be_into(w, o, m.get("char") or w.meta.get("protagonist")):
            m["status"] = "resolved"
            m["dropped"] = "they were never into you that way"
            if "phone" in w.meta:
                from .messages import answered_elsewhere
                answered_elsewhere(sim, "moment", m["id"], None)  # the text stays, without its answer buttons
            n += 1
    w.meta["romance_rules"] = 1
    return n


def romance_ok(w, x: str, y: str, chosen: bool = False) -> bool:
    """Whether x could fall for y at all: x is into y's gender, they aren't family, and they're the right age for each
    other (stage_ok). Every place attraction grows on its own or a crush forms asks this. `chosen`: you picked them
    yourself (you flirted, you asked them out), so the age rule doesn't decide your feelings for you; family still does."""
    X, Y = w.chars.get(x), w.chars.get(y)
    if X is None or Y is None or not w.rules["romance.enabled"]:
        return False
    if not orientation_ok(X, Y) or family(w, x, y):
        return False
    if chosen:
        return X.role == Y.role == "student"
    return stage_ok(X, Y)

LABEL_ORDER = ["dislikes", "stranger", "acquaintance", "friend", "close friend", "best friend"]


def label_for(r, R) -> str:
    a = r.affection
    if r.familiarity < 8 and a > R["rel.enemy_threshold"]:
        return "stranger"
    if r.rivalry >= R["rel.rival_threshold"] and a < R["rel.close_threshold"]:
        return "rival"
    if a <= R["rel.enemy_threshold"]:
        return "dislikes"
    if a >= R["rel.best_threshold"] and r.trust >= 60:
        return "best friend"
    if a >= R["rel.close_threshold"]:
        return "close friend"
    if a >= R["rel.friend_threshold"]:
        return "friend"
    if r.familiarity >= 15:
        return "acquaintance"
    return "stranger"


def is_friend(r, R) -> bool:
    return r is not None and r.affection >= R["rel.friend_threshold"]


def grudge_score(w, r, day) -> float:
    """How much src holds against dst: dislike, rivalry and recent bad memories."""
    if r is None:
        return 0.0
    g = max(0.0, -r.affection) * 0.6 + r.rivalry * 0.25
    src = w.chars[r.src]
    hl = w.rules["dev.memory_half_life"]
    mem = 0.0
    for m in src.memories[-25:]:
        if r.dst in m["with"] and m["valence"] < 0:
            age = day - m["day"]
            mem += -m["valence"] * m["intensity"] * 0.5 ** (age / hl) * 0.4
    return min(100.0, g + min(25.0, mem))


def memory_pull(w, cid: str, other: str, day: int) -> float:
    """Signed, decayed sum of memories cid has involving other (positive = good memories)."""
    c = w.chars[cid]
    hl = w.rules["dev.memory_half_life"]
    tot = 0.0
    for m in c.memories[-30:]:
        if other in m["with"]:
            age = day - m["day"]
            tot += m["valence"] * (m["intensity"] / 100.0) * 0.5 ** (age / (hl * (1 + m["intensity"] / 80)))
    return clamp(tot, -1.2, 1.2)


def satisfaction(w, a: str, b: str) -> float:
    """a's satisfaction with their romantic relationship with b (0-100)."""
    r = w.rel(a, b)
    if r is None:
        return 0.0
    s = 35 + r.affection * 0.35 + r.attraction * 0.3 + r.trust * 0.15 - r.rivalry * 0.3
    recent = [x[2] for x in r.recent[-5:]]
    if recent:
        s += sum(recent) / len(recent) * 20
    days = w.day - r.last_day
    if days > 7:
        s -= min(25, (days - 7) * 1.5)
    return clamp(s, 0, 100)


def interact(sim, fx, ev, a: str, b: str, p: dict, rng, calc: list | None) -> dict:
    """Resolve a two-person interaction. p holds the action's resolver params."""
    w, R = sim.w, sim.w.rules
    A, B = w.chars[a], w.chars[b]
    first = w.rel(a, b) is None or w.rel(a, b).familiarity < 10
    rab = w.ensure_rel(a, b, w.day)
    rba = w.ensure_rel(b, a, w.day)
    comp = compatibility(w, A, B)
    charm = (A.aptitudes["charisma"] + A.traits["sociability"]) / 2
    noise = rng.gauss(0, R["rel.interaction_noise"])
    terms = [
        ("action baseline", p.get("quality_bias", 0.0)),
        ("compatibility", 0.35 * comp),
        (f"{A.short}'s charm", 0.25 * (charm - 50) / 50),
        (f"{B.short}'s mood", 0.2 * (B.mood - 50) / 50),
        (f"{B.short}'s feelings toward {A.short}", 0.15 * rba.affection / 100),
        (f"{B.short}'s stress", -0.15 * max(0.0, B.needs["stress"] - 60) / 40),
        (f"{A.short}'s mood", 0.1 * (A.mood - 50) / 50),
        ("luck (random)", noise),
    ]
    if p.get("romantic"):
        chem = chemistry(w, a, b) * R["romance.chemistry_spread"]
        terms.append(("chemistry", 0.15 * chem))
    q = sum(t[1] for t in terms)
    outcome = "great" if q >= 0.55 else "good" if q >= 0.15 else "awkward" if q >= -0.2 else "bad"
    if calc is not None:
        calc.append({"step": "interaction quality", "terms": [[t[0], round(t[1], 3)] for t in terms],
                     "total": round(q, 3), "outcome": outcome,
                     "rule": "great >= 0.55, good >= 0.15, awkward >= -0.2, else bad"})
    qa = clamp(q + rng.gauss(0, 0.15), -1.5, 1.5)
    qb = clamp(q + rng.gauss(0, 0.15), -1.5, 1.5)
    gain = R["rel.affection_gain"]
    fi = (1 + 0.6 * R["rel.first_impression"]) if first else 1.0
    kind = p.get("kind", "chat")
    why = f"{kind} went {outcome}"
    for (x, y, rxy, qq) in ((a, b, rab, qa), (b, a, rba, qb)):
        d_aff = p.get("affection", 5) * qq * gain * fi
        if d_aff > 0:
            d_aff *= 1 - max(0.0, rxy.affection) / 130
        else:
            d_aff *= 1.3 - rxy.trust / 200
        if y == b:
            pass
        fx.rel(x, y, "affection", d_aff, why)
        fx.rel(x, y, "familiarity", p.get("familiarity", 4) * (1 - rxy.familiarity / 120), why)
        fx.rel(x, y, "trust", p.get("trust", 2) * (qq if qq > 0 else 2 * qq), why)
        X, Y = w.chars[x], w.chars[y]
        if p.get("attraction", 0) and romance_ok(w, x, y):
            chem = chemistry(w, x, y) * R["romance.chemistry_spread"]
            d_att = p["attraction"] * R["romance.attraction_rate"] * (chem * 0.8 + 0.1 + qq * 0.4) * (1 - rxy.attraction / 110)
            fx.rel(x, y, "attraction", d_att, why)
        fx.touch(x, y, kind, qq)
    # beliefs about the other side
    for (x, y, rxy, ryx) in ((a, b, rab, rba), (b, a, rba, rab)):
        X = w.chars[x]
        sd = R["rel.perception_noise"] * (1.3 - X.traits["empathy"] / 100) * 30
        signal = ryx.affection + rng.gauss(0, sd) + (X.traits["confidence"] - 50) * 0.3
        fx.rel(x, y, "perceived", 0.35 * (signal - rxy.perceived), f"read of {w.chars[y].short} during {kind}")
    for n, k in (("social", "social"), ("fun", "fun"), ("energy", "energy"), ("stress", "stress")):
        v = p.get(k, 0)
        if v:
            fx.need(a, n, v * (1 if n in ("energy", "stress") else (0.6 + 0.4 * clamp(qa + 0.5, 0, 1.5))), kind)
            if n in ("social", "fun"):
                fx.need(b, n, v * 0.6 * (0.6 + 0.4 * clamp(qb + 0.5, 0, 1.5)), kind)
    fx.mood(a, qa * 4, kind)
    fx.mood(b, qb * 3, kind)
    if p.get("target_stress"):
        fx.need(b, "stress", p["target_stress"] * clamp(qb + 0.6, 0.1, 1.5), f"support from {A.short}")
    if p.get("target_mood"):
        fx.mood(b, p["target_mood"] * clamp(qb + 0.6, 0.1, 1.5), f"support from {A.short}")
    if outcome == "great" and (first or rab.familiarity < 45 or p.get("romantic")):
        fx.memory(a, f"{kind}_great", [b], 0.6, 45, f"Great {kind.replace('_', ' ')} with {B.name}")
        fx.memory(b, f"{kind}_great", [a], 0.55, 40, f"Great {kind.replace('_', ' ')} with {A.name}")
    elif outcome == "bad":
        fx.memory(a, f"{kind}_bad", [b], -0.5, 35, f"Bad {kind.replace('_', ' ')} with {B.name}")
        fx.memory(b, f"{kind}_bad", [a], -0.45, 30, f"Bad {kind.replace('_', ' ')} with {A.name}")
    return {"quality": q, "qa": qa, "qb": qb, "outcome": outcome, "first": first, "terms": [[t[0], round(t[1], 3)] for t in terms]}


def update_labels(sim, fx, cause_ev):
    """After an event, re-derive labels for touched pairs and log milestones."""
    w, R = sim.w, sim.w.rules
    for (a, b) in sorted(fx.pairs):
        r = w.rels.get((a, b))
        if r is None:
            continue
        A, B = w.chars[a], w.chars[b]
        new = label_for(r, R)
        old = r.label
        ok = romance_ok(w, a, b, chosen=a == w.meta.get("protagonist"))  # your own feelings are yours
        crush = ok and r.attraction >= R["rel.crush_threshold"]
        if crush and not r.crush:
            r.crush = True
            r.milestones.append([w.day, "crush", cause_ev["id"] if cause_ev else None])
            if A.role == "student":
                sim.milestone_event("crush", a, b, cause_ev, 18)
        elif not crush and r.crush and (r.attraction < R["rel.crush_threshold"] - 10 or not ok):
            r.crush = False
        if new == old:
            continue
        r.label = new
        kind = None
        if new in ("friend", "close friend", "best friend") and LABEL_ORDER.index(new) > LABEL_ORDER.index(old if old in LABEL_ORDER else "stranger"):
            kind = {"friend": "friends", "close friend": "close_friends", "best friend": "best_friends"}[new]
        elif new == "rival":
            kind = "rivals"
        elif new == "dislikes" and old != "dislikes":
            kind = "dislike"
        elif old in ("friend", "close friend", "best friend") and new in ("acquaintance", "stranger"):
            kind = "drifted"
        if kind and any(m[1] == kind and w.day - m[0] < 90 for m in r.milestones):
            kind = None  # back-and-forth across a threshold is not news
        if kind:
            r.milestones.append([w.day, kind, cause_ev["id"] if cause_ev else None])
            if A.role in ("student", "alumni") and B.role in ("student", "alumni"):
                imp = {"friends": 22, "close_friends": 32, "best_friends": 45, "rivals": 30, "dislike": 26, "drifted": 20}[kind]
                sim.milestone_event(kind, a, b, cause_ev, imp)


# --- popularity -------------------------------------------------------------

def recompute_popularity(sim, fx):
    w = sim.w
    by_school: dict = {}
    for c in w.students():
        if c.location != "away":
            by_school.setdefault(c.school, []).append(c)
    raw_all = {}
    for school, studs in sorted(by_school.items(), key=lambda x: str(x[0])):
        raw_all.update(_popularity(sim, fx, sorted(studs, key=lambda c: c.id)))
    w.meta["popularity_raw"] = raw_all


def _popularity(sim, fx, studs):
    w, R = sim.w, sim.w.rules
    if not studs:
        return {}
    vis = R["social.popularity_visibility"]
    prev = {c.id: c.popularity for c in studs}
    raw = {}
    for s in studs:
        tot = 0.0
        for t in studs:
            if t.id == s.id:
                continue
            r = w.rels.get((t.id, s.id))
            if r is None:
                continue
            f = r.familiarity / 100
            like = max(r.affection, 0) * 0.6 + max(r.respect, 0) * 0.4 - max(-r.affection, 0) * 0.5
            tot += f * (like + vis * 12) * (0.5 + prev[t.id] / 100)
        for gid in s.memberships:
            tot += w.groups[gid].get("prestige", 0) * 0.6
        tot += (s.reputation.get("star", 0) + s.reputation.get("leader", 0)) * 0.4
        raw[s.id] = tot
    order = sorted(raw, key=lambda k: (raw[k], k))
    n = len(order)
    for i, cid in enumerate(order):
        pct = 100.0 * i / max(1, n - 1)
        new = 0.5 * prev[cid] + 0.5 * pct
        fx.scalar(cid, "popularity", round(new, 2), "weekly popularity")
    return {k: round(v, 2) for k, v in raw.items()}


# --- cliques ----------------------------------------------------------------

CLIQUE_NAMES = {
    "football": ["the Friday Night Crew", "the Linemen"], "fitness": ["the Gym Rats"], "basketball": ["the Court Crew", "the Hoopers"],
    "baseball": ["the Dugout", "the Bullpen"], "soccer": ["the Pitch", "the Back Line"], "softball": ["the Bat Girls", "the Diamond"],
    "drama": ["the Theater Kids", "the Understudies"],
    "art": ["the Sketchbook Circle", "the Paint-Stained"], "music": ["the Band Room", "the Garage Band"],
    "tech": ["the Lab Rats", "the Robot Garage"], "writing": ["the Herald Desk", "the Margins"],
    "academics": ["the Honor Roll", "the Study Hall"], "gaming": ["the Respawn Club", "the Couch Co-op"],
    "reading": ["the Back Table"], "sketching": ["the Doodlers"], "guitar": ["the Basement Sessions"],
    "pickup_games": ["the Rec Center Regulars"], "batting_cage": ["the Cage Rats"], "shows": ["the Couch Critics"],
    "fashion": ["the Thrift Squad"], "outdoors": ["the Trail Crew"], "coding": ["the Hackers"],
    "cooking": ["the Potluck"], "journaling": ["the Quiet Ones"],
}


def detect_cliques(sim, rng):
    w, R = sim.w, sim.w.rules
    thr = R["social.clique_threshold"]
    studs = sorted(c.id for c in w.chars.values() if c.role == "student" and c.status == "active" and c.location != "away")
    adj: dict[str, dict[str, float]] = {s: {} for s in studs}
    for a in studs:
        for b, r in w.out.get(a, {}).items():
            if b in adj and a < b and w.chars[a].school == w.chars[b].school:
                r2 = w.rels.get((b, a))
                if r2 is None:
                    continue
                m = min(r.affection, r2.affection)
                if m >= thr:
                    adj[a][b] = m
                    adj[b][a] = m
    labels = {s: s for s in studs}
    for _ in range(12):
        changed = False
        order = studs[:]
        rng.shuffle(order)
        for s in order:
            if not adj[s]:
                continue
            score: dict[str, float] = {}
            for nb, wt in adj[s].items():
                score[labels[nb]] = score.get(labels[nb], 0) + wt
            best = max(sorted(score), key=lambda k: score[k])
            if best != labels[s] and score[best] > score.get(labels[s], 0):
                labels[s] = best
                changed = True
        if not changed:
            break
    groups: dict[str, list] = {}
    for s, l in labels.items():
        groups.setdefault(l, []).append(s)
    found = [sorted(g) for g in groups.values() if len(g) >= R["social.clique_min_size"]]
    found.sort(key=lambda g: (-len(g), g[0]))
    old = {cid: c for cid, c in w.cliques.items() if c.get("active") or w.day - c.get("dissolved", -999) <= 28}
    used = set()
    result = {}
    events = []
    for members in found:
        ms = set(members)
        best, best_j = None, 0.0
        for cid, c in old.items():
            if cid in used:
                continue
            j = len(ms & set(c["members"])) / len(ms | set(c["members"]))
            if j > best_j:
                best, best_j = cid, j
        if best is not None and best_j >= 0.34:
            used.add(best)
            c = old[best]
            if not c.get("active"):
                c["active"] = True
                c.pop("dissolved", None)
            joined = sorted(ms - set(c["members"]))
            left = sorted(set(c["members"]) - ms)
            c["members"] = members
            c["history"].append([w.day, joined, left])
            c["history"] = c["history"][-30:]
            result[best] = c
            for j in joined:
                events.append(("joined", j, best))
            for l in left:
                events.append(("left", l, best))
        else:
            cid = f"q{w.next_id('clique')}"
            c = {"id": cid, "name": clique_name(w, members, cid), "members": members, "formed": w.day,
                 "active": True, "history": [[w.day, members, []]]}
            result[cid] = c
            events.append(("formed", None, cid))
    for cid, c in old.items():
        if cid not in used and c.get("active"):
            c["active"] = False
            c["dissolved"] = w.day
            events.append(("dissolved", None, cid))
    for cid, c in w.cliques.items():
        if cid not in result and not c.get("active"):
            result.setdefault(cid, c)
    w.cliques = dict(sorted(result.items()))
    for cid in w.cliques:
        c = w.cliques[cid]
        if c.get("active"):
            prof = clique_profile(w, c["members"])
            c.update(prof)
    for c in w.chars.values():
        c.flags.pop("clique", None)
    for cid, c in w.cliques.items():
        if c.get("active"):
            for m in c["members"]:
                w.chars[m].flags["clique"] = cid
    return events


def clique_profile(w, members):
    ints: dict[str, float] = {}
    pop = 0.0
    for m in members:
        c = w.chars[m]
        pop += c.popularity
        for k, v in c.interests.items():
            ints[k] = ints.get(k, 0) + v
    n = len(members)
    top = sorted(ints.items(), key=lambda x: (-x[1], x[0]))[:4]
    return {"popularity": round(pop / n, 1), "interests": [[k, round(v / n, 1)] for k, v in top]}


def _all(w, members, test) -> bool:
    cs = [w.chars[m] for m in members if m in w.chars]
    return bool(cs) and all(test(c) for c in cs)


def _most(w, members, test) -> bool:
    cs = [w.chars[m] for m in members if m in w.chars]
    return bool(cs) and sum(1 for c in cs if test(c)) * 2 > len(cs)


# names that only fit some groups: who's in it has to match
NAME_FITS = {"the Linemen": lambda w, ms: _all(w, ms, lambda c: c.gender == "m"),
             "the Bat Girls": lambda w, ms: _all(w, ms, lambda c: c.gender == "f"),
             "the Senior Lot Crowd": lambda w, ms: _most(w, ms, lambda c: c.grade == 12)}


def clique_name(w, members, cid):
    prof = clique_profile(w, members)
    taken = {c.get("name") for c in w.cliques.values() if c.get("active")}

    def fits(nm):
        return nm not in taken and NAME_FITS.get(nm, lambda w, ms: True)(w, members)
    if prof["popularity"] >= 72:
        for nm in ("the In-Crowd", "the Senior Lot Crowd", "the A-List", "the Back Booth"):
            if fits(nm):
                return nm
    ints = [k for k, v in prof["interests"] if k != "academics" or v >= 62]
    key = ints[0] if ints else "shows"
    names = CLIQUE_NAMES.get(key, ["the Regulars"])
    for nm in names:
        if fits(nm):
            return nm
    plain = [nm for nm in names if nm not in NAME_FITS] or ["the Regulars"]
    return f"{plain[0]} ({cid})"


# --- rumors -----------------------------------------------------------------

def make_rumor(sim, about: str, kind: str, phrase: str, truth: bool, valence: float, juice: float, origin: str | None,
               known_by: list, event_id: int | None, involves: list | None = None) -> str:
    w = sim.w
    rid = f"r{w.next_id('rumor')}"
    w.rumors[rid] = {"id": rid, "about": about, "kind": kind, "text": phrase, "truth": truth,
                     "valence": round(valence, 3), "juice": round(juice, 3), "origin": origin, "day": w.day,
                     "known_by": {k: [w.day, origin, True] for k in known_by}, "spread": 0, "event": event_id,
                     "involves": involves or [about], "exaggerated": False}
    return rid


def witnesses(sim, rng, exclude: set, n: int, prefer: list | None = None) -> list:
    """Random students who saw something at school (prefers people near the involved)."""
    w = sim.w
    loc = next((w.chars[x].location for x in sorted(exclude) if x in w.chars), "hollow_creek")
    pool = sorted(c.id for c in w.students() if c.id not in exclude and c.location == loc)
    out = []
    if prefer:
        for p in prefer:
            if p in pool and p not in out and rng.random() < 0.7:
                out.append(p)
    rng.shuffle(pool)
    for p in pool:
        if len(out) >= n:
            break
        if p not in out:
            out.append(p)
    return out[:n]


def best_rumor_for(w, teller: str, listener: str, R, recent=None) -> dict | None:
    best, best_s = None, 0.0
    for r in (recent if recent is not None else w.rumors.values()):
        kb = r["known_by"].get(teller)
        if kb is None or r["about"] in (teller, listener) or listener in r["known_by"] and False:
            continue
        age = w.day - r["day"]
        if age > 60:
            continue
        rel_about = w.rels.get((teller, r["about"]))
        if rel_about and rel_about.affection >= R["rel.close_threshold"] and r["valence"] < 0 \
                and w.chars[teller].traits["loyalty"] > 40:
            continue
        s = r["juice"] * (1 - age / 75) * (1 + max(0, -(rel_about.affection if rel_about else 0)) / 100)
        if s > best_s:
            best, best_s = r, s
    return best
