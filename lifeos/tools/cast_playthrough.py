"""A seeded playthrough with an identity log: who every brother scene is about, from your freshman year into college.

    python lifeos/tools/cast_playthrough.py [PACK.json ...] [--days 430] [--slot lead_brother]

The family is the one from the brothers handoff: you (grade 9), twin sisters (grade 10), an older brother (grade 12) who
plays basketball. Pass your own pack files (already locked with pack_cast.py, or not: older_sibling scenes are locked to
the slot first); with none, it uses the small stand-in packs from the tests.
"""
import argparse
import copy
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("packs", nargs="*")
    ap.add_argument("--days", type=int, default=430)
    ap.add_argument("--slot", default="lead_brother")
    a = ap.parse_args()
    os.environ["LIFEOS_DIALOGUE"] = tempfile.mkdtemp(prefix="lifeos-cast-")
    from lifeos import dialogue, moments, calendar as calm
    dialogue.USER_DIR = os.environ["LIFEOS_DIALOGUE"]
    dialogue.reload()
    from tests import test_cast_slots as T
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    from tests.test_story import spec
    packs = [json.load(open(p, encoding="utf-8")) for p in a.packs] or [copy.deepcopy(T.BROTHERS), copy.deepcopy(T.FRIDAY)]
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    c.post("/api/story/new", json={"spec": spec(per=6, siblings=[T.BROTHER] + T.TWINS)})
    w, sim = api.lab.w, api.lab.sim
    for m in moments.pending(w):
        moments.resolve(sim, m["id"], None)
    lock = dict(T.LOCK, slot=a.slot)
    for p in packs:
        r = c.post("/api/dialogue/packs", json={"pack": p})
        pid = r.json()["added"]
        if any(isinstance(s, dict) and s.get("who") in lock["replace"] for s in p.get("scenes", [])):
            c.post(f"/api/dialogue/packs/{pid}/lock-cast", json=lock)
    names = {pid: w.chars[pid].name for pid in w.chars}
    me = w.chars[w.meta["protagonist"]]
    print(f"you: {me.name} (grade {me.grade}); siblings: " + ", ".join(f"{w.chars[s].name} (grade {w.chars[s].grade})" for s in sim.siblings(me.id)))
    print(f"{a.slot} bound to: {names.get(dialogue.bound(sim, a.slot))}  log: {w.meta.get('cast_log')}")
    print(f"{'date':<16}{'you':>4}{'him':>5}  {'where':<8}{'scene':<34}them")
    slot_scenes = {sid for sid, m in sim.cat.moments.items() if (m.get("scene") or {}).get("who") == f"cast:{a.slot}"}
    rows = 0
    for _ in range(a.days * 6):
        for m in moments.pending(w):
            if m["kind"] in slot_scenes or (sim.cat.moments.get(m["kind"]) or {}).get("beat_of") in slot_scenes:
                b = w.chars.get(dialogue.bound(sim, a.slot) or "")
                print(f"{calm.label(m['day']):<16}{me.grade or '-':>4}{(b.grade if b else '-') or '-':>5}  {(b.location if b else '-')[:7]:<8}"
                      f"{m['kind'][:33]:<34}{names.get(m['ctx'].get('them'))}")
                rows += 1
            moments.resolve(sim, m["id"], None)
        sim.step()
    print(f"{rows} scene(s); remembered: {sorted(w.meta.get('remembered', {}))}")
    print(f"cast log: {w.meta.get('cast_log')}")


if __name__ == "__main__":
    main()
