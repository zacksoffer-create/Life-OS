"""Experiments: run a scenario under several rule sets and seeds, then compare.

Isolation: every run starts from its own copy of the base world (deserialized from JSON in a
separate worker process), so runs never share state. Pairing: variant runs reuse the
baseline's seeds (common random numbers), so differences between a baseline run and a variant
run with the same seed come from the rule change plus how far that change has rippled.

Two kinds of result, labelled as such:
  - one seed: a deterministic paired comparison. It shows exactly what changed in that one
    world, including the first day the two histories diverged. It is not evidence of a trend.
  - several seeds: a repeated-run measurement with means, spread, 95% intervals and how many
    seeds moved in the same direction. Small samples still deserve caution.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
import traceback

from . import metrics

MAX_DAYS = 730
MAX_RUNS = 60

T95 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23, 12: 2.18, 15: 2.13,
       20: 2.09, 25: 2.06, 30: 2.04}

PRESETS = [
    {"id": "approval", "name": "What if social approval mattered more?",
     "about": "Same school, same seeds. One world runs normal motives; the other multiplies everyone's need for social approval by 2.5. Watch friendships, cliques, exclusion, teasing and how unequal popularity gets.",
     "days": 180, "seeds": [11, 12, 13, 14, 15],
     "variants": [{"name": "Baseline", "rules": {}}, {"name": "Approval x2.5", "rules": {"motive.approval": 2.5}}],
     "metrics": ["mutual_friendships", "cliques", "avg_clique_size", "exclusions", "teasing", "popularity_gini", "conflicts", "avg_stress"]},
    {"id": "grind", "name": "Does discipline beat talent?",
     "about": "Raise how much discipline improves practice and how much coaches weigh effort, and lower the talent ceiling. Compare team rosters, skills and GPA.",
     "days": 270, "seeds": [21, 22, 23],
     "variants": [{"name": "Baseline", "rules": {}},
                  {"name": "Effort world", "rules": {"dev.discipline_focus": 2.0, "inst.coach_effort_weight": 2.0, "inst.coach_talent_weight": 0.5, "dev.talent_cap_weight": 0.15}}],
     "metrics": ["team_spots", "avg_gpa", "avg_stress", "mutual_friendships"]},
    {"id": "gossip", "name": "A town that runs on gossip",
     "about": "Make rumors spread more, hit harder and get exaggerated more often.",
     "days": 120, "seeds": [31, 32, 33, 34],
     "variants": [{"name": "Baseline", "rules": {}},
                  {"name": "Gossip town", "rules": {"social.gossip_spread": 0.9, "social.rumor_credibility": 2.0, "social.rumor_distortion": 0.4}}],
     "metrics": ["rumors", "rumor_spreads", "dislikes", "mutual_friendships", "conflicts", "avg_mood"]},
    {"id": "noise", "name": "Rational vs. random characters",
     "about": "Halve and double the decision temperature. How much of the story is personality, and how much is noise?",
     "days": 120, "seeds": [41, 42, 43],
     "variants": [{"name": "Baseline", "rules": {}}, {"name": "Predictable (T x0.5)", "rules": {"decision.temperature": 3.0}},
                  {"name": "Chaotic (T x2)", "rules": {"decision.temperature": 12.0}}],
     "metrics": ["mutual_friendships", "conflicts", "couples", "avg_gpa", "avg_mood"]},
    {"id": "single", "name": "One world, one change (deterministic)",
     "about": "A single seed, paired. Shows exactly which lives changed and when the two timelines split. Good for understanding a mechanic, not for measuring it.",
     "days": 90, "seeds": [7],
     "variants": [{"name": "Baseline", "rules": {}}, {"name": "No romance", "rules": {"romance.enabled": False}}],
     "metrics": ["mutual_friendships", "couples", "avg_mood", "conflicts"]},
]


def _digest(w) -> str:
    parts = [(c.id, c.recent_actions[-2:]) for c in sorted(w.chars.values(), key=lambda c: c.id) if c.status == "active"]
    return hashlib.blake2b(json.dumps(parts).encode(), digest_size=6).hexdigest()


def run_one(job: dict) -> dict:
    """Run one (variant, seed) in isolation. Top-level so worker processes can import it."""
    from .engine import Simulation
    from .history import History
    from .storage import world_from_json
    t0 = time.time()
    w = world_from_json(job["base"])
    w.history = History()
    w.tracing = False
    w.seed = int(job["seed"])
    w.meta["tally"] = {}
    w.meta["actions"] = {}
    w.stats_series = []
    sim = Simulation(w)
    if job.get("rules"):
        sim.set_rules(job["rules"], note=f"experiment variant {job['variant']}")
    for aid, ch in (job.get("actions") or {}).items():
        sim.set_action_override(aid, ch)
    start = w.day
    digests = []
    series = [metrics.snapshot(w)]
    for i in range(job["days"]):
        sim.advance_days(1)
        digests.append(_digest(w))
        if (i + 1) % 7 == 0:
            series.append(metrics.snapshot(w))
    chars = {cid: metrics.character_summary(w, cid) for cid in sorted(w.chars) if w.chars[cid].role in ("student", "alumni")}
    return {"variant": job["variant"], "seed": job["seed"], "start_day": start, "end_day": w.day,
            "metrics": metrics.compute(w), "series": series, "digests": digests, "characters": chars,
            "actions": dict(w.meta.get("actions", {})), "tally": dict(w.meta.get("tally", {})),
            "seconds": round(time.time() - t0, 2)}


def validate_spec(spec: dict) -> dict:
    from .rules import RulesError, schema
    errors = []
    days = spec.get("days", 90)
    try:
        days = int(days)
    except (TypeError, ValueError):
        errors.append("days must be a whole number")
        days = 0
    if not (7 <= days <= MAX_DAYS):
        errors.append(f"days must be between 7 and {MAX_DAYS}")
    seeds = spec.get("seeds") or [1]
    if not isinstance(seeds, list) or not seeds or not all(isinstance(s, int) for s in seeds):
        errors.append("seeds must be a non-empty list of whole numbers")
        seeds = [1]
    if len(set(seeds)) != len(seeds):
        errors.append("seeds must be distinct")
    variants = spec.get("variants") or []
    if len(variants) < 2:
        errors.append("an experiment needs a baseline and at least one variant")
    names = set()
    for v in variants:
        if not v.get("name"):
            errors.append("every variant needs a name")
        if v.get("name") in names:
            errors.append(f"duplicate variant name {v.get('name')}")
        names.add(v.get("name"))
        try:
            schema().validate(v.get("rules") or {})
        except RulesError as e:
            errors.append(f"{v.get('name')}: " + "; ".join(e.errors))
    if len(variants) * len(seeds) > MAX_RUNS:
        errors.append(f"at most {MAX_RUNS} runs per experiment (variants x seeds)")
    base = spec.get("base") or {"kind": "fresh", "gen_seed": 1234, "students": 36}
    if base.get("kind") not in ("fresh", "current", "save"):
        errors.append("base.kind must be fresh, current or save")
    if errors:
        raise ValueError("; ".join(errors))
    return {"name": spec.get("name") or "Untitled experiment", "days": days, "seeds": seeds, "variants": variants,
            "base": base, "metrics": spec.get("metrics") or list(metrics.SERIES_KEYS), "about": spec.get("about", "")}


def _stats(xs):
    n = len(xs)
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else 0.0
    if n > 1:
        t = T95.get(n - 1) or T95[min(T95, key=lambda k: abs(k - (n - 1)))]
        h = t * sd / math.sqrt(n)
        ci = [round(m - h, 3), round(m + h, 3)]
    else:
        ci = None
    return {"mean": round(m, 3), "sd": round(sd, 3), "ci95": ci, "n": n, "values": [round(x, 3) for x in xs]}


def analyze(spec: dict, runs: list[dict]) -> dict:
    variants = [v["name"] for v in spec["variants"]]
    base = variants[0]
    by = {(r["variant"], r["seed"]): r for r in runs}
    seeds = spec["seeds"]
    n = len(seeds)
    mode = "deterministic" if n == 1 else "repeated"
    mkeys = [k for k in metrics.METRIC_INFO if k in runs[0]["metrics"]]
    out = {"mode": mode, "baseline": base, "variants": [], "comparisons": [], "series": {}, "actions": {},
           "divergence": {}, "characters": None, "metric_info": metrics.METRIC_INFO, "focus": spec["metrics"],
           "notes": []}
    for v in variants:
        vals = {k: [by[(v, s)]["metrics"][k] for s in seeds] for k in mkeys}
        out["variants"].append({"name": v, "rules": next(x for x in spec["variants"] if x["name"] == v).get("rules") or {},
                                "metrics": {k: _stats(xs) for k, xs in vals.items()},
                                "seconds": round(sum(by[(v, s)]["seconds"] for s in seeds), 1)})
        weeks = len(by[(v, seeds[0])]["series"])
        out["series"][v] = {k: [round(sum(by[(v, s)]["series"][i][k] for s in seeds) / n, 3) for i in range(weeks)]
                            for k in metrics.SERIES_KEYS}
        out["series"][v]["day"] = [by[(v, seeds[0])]["series"][i]["day"] for i in range(weeks)]
        acts: dict = {}
        for s in seeds:
            for a, cnt in by[(v, s)]["actions"].items():
                acts[a] = acts.get(a, 0) + cnt / n
        out["actions"][v] = {a: round(x, 1) for a, x in sorted(acts.items(), key=lambda x: -x[1])}
    for v in variants[1:]:
        comp = {"variant": v, "vs": base, "metrics": {}}
        for k in mkeys:
            diffs = [by[(v, s)]["metrics"][k] - by[(base, s)]["metrics"][k] for s in seeds]
            st = _stats(diffs)
            up = sum(1 for d in diffs if d > 1e-9)
            down = sum(1 for d in diffs if d < -1e-9)
            st["direction"] = f"{up} of {n} higher, {down} lower"
            sd_pool = math.sqrt((out["variants"][0]["metrics"][k]["sd"] ** 2 + next(x for x in out["variants"] if x["name"] == v)["metrics"][k]["sd"] ** 2) / 2) if n > 1 else 0
            st["effect_size"] = round(st["mean"] / sd_pool, 2) if sd_pool > 1e-9 else None
            st["interval_excludes_zero"] = bool(st["ci95"] and (st["ci95"][0] > 0 or st["ci95"][1] < 0))
            comp["metrics"][k] = st
        out["comparisons"].append(comp)
        div = {}
        for s in seeds:
            a, b = by[(base, s)]["digests"], by[(v, s)]["digests"]
            first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)
            div[str(s)] = None if first is None else by[(base, s)]["start_day"] + first
        out["divergence"][v] = div
    if mode == "deterministic":
        s = seeds[0]
        chars = []
        for cid, a in by[(base, s)]["characters"].items():
            rows = {}
            for v in variants[1:]:
                b = by[(v, s)]["characters"].get(cid)
                if b is None:
                    continue
                rows[v] = {"friends": b["friends"] - a["friends"], "popularity": round(b["popularity"] - a["popularity"], 1),
                           "mood": round(b["mood"] - a["mood"], 1), "gpa": round(b["gpa"] - a["gpa"], 2),
                           "memberships_gained": sorted(set(b["memberships"]) - set(a["memberships"])),
                           "memberships_lost": sorted(set(a["memberships"]) - set(b["memberships"])),
                           "partner": [a["partner"], b["partner"]] if a["partner"] != b["partner"] else None,
                           "friends_gained": sorted(set(b["friend_ids"]) - set(a["friend_ids"])),
                           "friends_lost": sorted(set(a["friend_ids"]) - set(b["friend_ids"]))}
            score = sum(abs(r["friends"]) * 3 + abs(r["popularity"]) / 5 + abs(r["mood"]) / 5 + len(r["friends_gained"]) + len(r["friends_lost"])
                        + (5 if r["partner"] else 0) + 3 * len(r["memberships_gained"] + r["memberships_lost"]) for r in rows.values())
            chars.append({"id": cid, "name": a["name"], "baseline": a, "diff": rows, "change_score": round(score, 1)})
        chars.sort(key=lambda x: -x["change_score"])
        out["characters"] = chars
        out["notes"].append("One seed: this is a deterministic, paired comparison of two specific timelines. "
                            "It shows what this change did in this world; it does not show what it does on average.")
    else:
        out["notes"].append(f"{n} seeds per variant, paired by seed. Intervals are 95% t-intervals on the per-seed differences. "
                            "With few seeds, treat anything whose interval crosses zero as unresolved, and even clear results as provisional.")
    out["notes"].append("Every run starts from its own copy of the same base world; runs never share state.")
    return out


class Runner:
    """Runs experiments in the background, one worker process per run (up to the CPU count)."""

    def __init__(self, store):
        self.store = store
        self.jobs: dict[int, dict] = {}

    def start(self, spec: dict, base_json: str) -> int:
        eid = self.store.create_experiment(spec["name"], spec)
        runs = [{"variant": v["name"], "rules": v.get("rules") or {}, "actions": v.get("actions") or {},
                 "seed": s, "days": spec["days"], "base": base_json} for v in spec["variants"] for s in spec["seeds"]]
        self.jobs[eid] = {"id": eid, "status": "running", "done": 0, "total": len(runs), "started": time.time(), "error": None}
        t = threading.Thread(target=self._work, args=(eid, spec, runs), daemon=True)
        t.start()
        return eid

    def _work(self, eid, spec, runs):
        job = self.jobs[eid]
        try:
            results = []
            workers = max(1, min(len(runs), os.cpu_count() or 2, 6))
            try:
                from concurrent.futures import ProcessPoolExecutor  # not available in the phone app
                with ProcessPoolExecutor(max_workers=workers) as ex:
                    for r in ex.map(run_one, runs):
                        results.append(r)
                        job["done"] += 1
            except (OSError, RuntimeError, NotImplementedError):
                results = []
                job["done"] = 0
                for r in runs:
                    results.append(run_one(r))
                    job["done"] += 1
            res = analyze(spec, results)
            res["base_info"] = spec.get("base")
            res["elapsed"] = round(time.time() - job["started"], 1)
            self.store.finish_experiment(eid, res)
            job["status"] = "done"
        except Exception as e:  # report, don't crash the server
            job["status"] = "failed"
            job["error"] = f"{type(e).__name__}: {e}"
            self.store.finish_experiment(eid, None, error=job["error"] + "\n" + traceback.format_exc()[-2000:])

    def status(self, eid) -> dict | None:
        return self.jobs.get(eid)
