"""The seeded seven-year story schedule report: every scene in your packs, the day it plays or exactly why it doesn't.

    python lifeos/tools/schedule_report.py PACK.json [PACK.json ...] [--seed 1234] [--profile dense] [--years 7] [--full]
                                           [--spec story.json] [--out report]

Give it your pack files (the storylines and your "Season plan.json", exported from the phone: Me > Storylines > share, or
copied out of the app's dialogue folder). It starts a story (yours with --spec, or the handoff family: you a freshman, your
older brother a senior on the Guilford basketball team and your best friend, twin sisters a grade up), plays seven years
forward with your character answering every scene, and writes report.md and report.json: every scene id with the day it
played or the reason it didn't (not yet / unreachable: wrong season, the other branch, a prerequisite that can't happen),
deadline misses, contradictions (out of season, before a prerequisite, out of chapter order) and who every cast slot is.

--fast (default) moves only the calendar and the stories: seconds. --full simulates the whole town: accurate requirements
(dating, game weeks, who's on which team), about a minute per simulated month. With no packs, it uses the synthetic
season plan from the tests.
"""
import argparse
import copy
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

FAMILY = {
    "protagonist": {"first": "Zack", "last": "Soffer", "gender": "m", "grade": 9, "archetype": "athlete", "attracted_to": ["f"],
                    "interests": {"basketball": 90, "baseball": 90, "football": 60}, "skills": {"basketball": 60, "baseball": 58},
                    "aptitudes": {"athletic": 85}, "body": {"height_in": 71, "build": "athletic"}},
    "siblings": [{"key": "bro", "first": "Mike", "gender": "m", "grade": 12, "archetype": "athlete",
                  "interests": {"basketball": 95}, "skills": {"basketball": 80}, "positions": {"basketball": "PG"},
                  "relationships": [{"to": "me", "type": "best_friend", "strength": 30}]},
                 {"key": "ally", "first": "Ally", "gender": "f", "grade": 10},
                 {"key": "jen", "first": "Jen", "gender": "f", "grade": 10, "twin_of": "ally"}],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("packs", nargs="*")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--profile", default="dense")
    ap.add_argument("--years", type=int, default=7)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--spec")
    ap.add_argument("--out", default="schedule-report")
    a = ap.parse_args()
    os.environ["LIFEOS_DIALOGUE"] = tempfile.mkdtemp(prefix="lifeos-schedule-")
    from lifeos import dialogue, moments, scheduler
    from lifeos.engine import Simulation
    from lifeos.story import begin, create_story
    dialogue.USER_DIR = os.environ["LIFEOS_DIALOGUE"]
    dialogue.reload()
    if a.packs:
        packs = [json.load(open(p, encoding="utf-8")) for p in a.packs]
    else:
        from tests.test_scheduler import season_plan
        packs = season_plan()
    for p in packs:
        r = dialogue.add_pack(copy.deepcopy(p))
        if not r.get("ok", True):
            print(f"! {p.get('name')}: {'; '.join(r.get('errors', [])[:5])}")
    dialogue.reload()
    if a.spec:
        spec = json.load(open(a.spec, encoding="utf-8"))
    else:
        from tests.test_story import spec as base
        spec = base(per=10)
        spec["protagonist"] = FAMILY["protagonist"]
        spec["siblings"] = FAMILY["siblings"]
        spec["cast"] = [c for c in spec.get("cast", []) if c.get("role") != "staff"]
    spec["gen_seed"] = a.seed
    w = create_story(spec)
    w.seed = a.seed
    sim = Simulation(w)
    begin(sim)
    for m in moments.pending(w):
        moments.resolve(sim, m["id"], None)
    days = a.years * 365 + 10
    print(f"{len(scheduler.catalog(sim)['scenes'])} scenes, seed {a.seed}, {a.profile}, {'full' if a.full else 'fast'}, {days} days...")
    run = scheduler.dry_run(sim, days, a.profile, full=a.full, seed_note=f"seed {a.seed}")
    rep = scheduler.report(sim, run)
    rep["seed"] = a.seed
    title = f"Story schedule report: seed {a.seed}, {a.profile}, {a.years} years ({'whole town' if a.full else 'fast'})"
    with open(a.out + ".md", "w", encoding="utf-8") as f:
        f.write(scheduler.report_markdown(rep, title))
    with open(a.out + ".json", "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1, default=str)
    c = rep["counts"]
    print(f"played {c.get('played', 0)}, unreachable {c.get('unreachable', 0)}, waiting {c.get('waiting', 0)}, expired {c.get('expired', 0)}; "
          f"{len(rep['warnings'])} contradictions, {len(rep['deadline_misses'])} deadline misses")
    for r in rep["identity"]:
        print(f"  {r['slot']}: {r['name']}" + (f"  !! {'; '.join(r['problems'])}" if r["problems"] else ""))
    print(f"wrote {a.out}.md and {a.out}.json")


if __name__ == "__main__":
    main()
