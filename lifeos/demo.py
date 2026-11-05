"""Demonstration scenario: python demo.py [--days 180] [--seeds 3] [--no-experiment]

1. Generates the Hollow Creek demo world (same population every time) and lives through it.
2. Tells the story of the featured characters from the recorded history: who they became
   close to, what they tried out for, what went wrong, how their skills moved.
3. Runs the social-approval experiment (baseline vs approval x2.5, paired seeds) and prints
   the comparison with its uncertainty.
Everything printed comes from recorded simulation state; nothing is written after the fact.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from lifeos import calendar as calm  # noqa: E402
from lifeos import metrics  # noqa: E402
from lifeos.engine import Simulation  # noqa: E402
from lifeos.experiments import analyze, run_one, validate_spec  # noqa: E402
from lifeos.storage import world_to_json  # noqa: E402
from lifeos.worldgen import generate  # noqa: E402

FEATURED = ["devon-park", "marcus-bell", "priya-raman", "lena-kowalski", "theo-marsh", "rosa-delgado", "sienna-cole", "ava-thompson"]


def story(w, cid, start):
    c = w.chars[cid]
    R = w.rules
    print(f"\n== {c.name} ({c.role}{', grade ' + str(c.grade) if c.grade else ''}) - {c.bio}")
    t = c.traits
    print(f"   discipline {t['discipline']:.0f} · impulsivity {t['impulsivity']:.0f} · sociability {t['sociability']:.0f} · confidence {t['confidence']:.0f}")
    moved = sorted(((k, c.skills[k] - start['skills'].get(k, 0)) for k in c.skills), key=lambda x: -abs(x[1]))[:3]
    print("   skills: " + ", ".join(f"{k} {start['skills'].get(k, 0):.0f}->{c.skills[k]:.0f}" for k, d in moved if abs(d) >= 1))
    print(f"   how they spent their time: practiced {c.counters.get('practice_skill', 0)}x, studied {c.counters.get('study', 0)}x, "
          f"hung out {c.counters.get('hang_out', 0)}x, team/club sessions {c.counters.get('attend_practice', 0)}x")
    friends = sorted(((r.affection, o) for o, r in w.out.get(cid, {}).items() if r.affection >= R["rel.friend_threshold"]), reverse=True)[:4]
    if friends:
        print("   closest: " + ", ".join(f"{w.chars[o].name} ({r:.0f}, they feel {w.rels[(o, cid)].affection:.0f})" for r, o in friends if (o, cid) in w.rels))
    groups = [w.groups[g]["name"] for g in c.memberships] + [p["name"] + " (left: " + p["why"] + ")" for p in c.past_memberships[-3:]]
    if groups:
        print("   groups: " + "; ".join(groups))
    if c.flags.get("partner"):
        print(f"   dating {w.chars[c.flags['partner']].name}")
    evs = [w.history.events[e] for e in w.history.by_char.get(cid, []) if e in w.history.events]
    big = [e for e in evs if e["importance"] >= 28][:9]
    for e in big:
        print(f"   - {calm.label(e['day'])}: {e['text']}")
    goals = [g for g in c.goals if g["status"] == "active"][:3]
    if goals:
        print("   now working toward: " + "; ".join(g["label"] for g in goals))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--exp-days", type=int, default=120)
    ap.add_argument("--no-experiment", action="store_true")
    a = ap.parse_args()

    w = generate(1234, 36, True)
    sim = Simulation(w)
    start = {cid: {"skills": dict(w.chars[cid].skills)} for cid in FEATURED}
    t0 = time.time()
    print(f"Living through {a.days} days in Hollow Creek (seed {w.seed})...")
    sim.advance_days(a.days)
    print(f"done in {time.time() - t0:.1f}s; {len(w.history.events)} events on record, now {calm.label(w.day)}")
    m = metrics.compute(w)
    print(f"\nThe town: {m['mutual_friendships']} mutual friendships, {m['couples']} couples, {m['cliques']} cliques, "
          f"{m['conflicts']} conflicts, {m['exclusions']} exclusions, avg mood {m['avg_mood']:.0f}, avg GPA {m['avg_gpa']:.2f}")
    for cid in FEATURED:
        story(w, cid, start[cid])

    d, mk = w.chars["devon-park"], w.chars["marcus-bell"]
    print("\nTalent vs discipline: Marcus (athletic aptitude %.0f, discipline %.0f) vs Devon (athletic %.0f, discipline %.0f)"
          % (mk.aptitudes["athletic"], mk.traits["discipline"], d.aptitudes["athletic"], d.traits["discipline"]))
    print("   basketball skill: Marcus %.0f -> %.0f, Devon %.0f -> %.0f"
          % (start["marcus-bell"]["skills"]["basketball"], mk.skills["basketball"], start["devon-park"]["skills"]["basketball"], d.skills["basketball"]))

    if a.no_experiment:
        return
    print(f"\nExperiment: does social approval reshape the school? ({a.seeds} paired seeds x {a.exp_days} days)")
    base = generate(1234, 36, True)
    Simulation(base)
    bj = world_to_json(base)
    spec = validate_spec({"name": "approval", "days": a.exp_days, "seeds": list(range(11, 11 + a.seeds)),
                          "variants": [{"name": "Baseline", "rules": {}}, {"name": "Approval x2.5", "rules": {"motive.approval": 2.5}}]})
    jobs = [{"variant": v["name"], "rules": v["rules"], "seed": s, "days": spec["days"], "base": bj} for v in spec["variants"] for s in spec["seeds"]]
    from concurrent.futures import ProcessPoolExecutor
    t0 = time.time()
    with ProcessPoolExecutor() as ex:
        runs = list(ex.map(run_one, jobs))
    res = analyze(spec, runs)
    print(f"({time.time() - t0:.1f}s) mode: {res['mode']}")
    for note in res["notes"]:
        print("   note: " + note)
    comp = res["comparisons"][0]["metrics"]
    for k in ["mutual_friendships", "cliques", "exclusions", "teasing", "popularity_gini", "conflicts", "rumors", "avg_stress"]:
        x = comp[k]
        base_m = res["variants"][0]["metrics"][k]["mean"]
        ci = f"[{x['ci95'][0]:+.2f}, {x['ci95'][1]:+.2f}]" if x["ci95"] else "n/a"
        flag = "  <- interval excludes 0" if x.get("interval_excludes_zero") else ""
        print(f"   {k:22s} baseline {base_m:8.2f}   change {x['mean']:+8.2f}  95% CI {ci:22s} {x['direction']}{flag}")


if __name__ == "__main__":
    main()
