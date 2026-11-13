"""Build the league history page, docs/fantasy/history/: every finished season together, plus what the box scores say.

    python3 fantasy/build_history.py

Reads each season's page data (docs/fantasy/<2025-26>/data.json, from build_season.py) and the ESPN imports
(fantasy/seasons/<season>/espn/), so build the seasons first. Managers are followed across seasons by an opaque owner
key, never by name, and shown under their latest team name.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from build import load  # noqa: E402
from build_season import my_owner  # noqa: E402
from hoops import config, model, page, studies  # noqa: E402


def team_name(t: dict) -> str:
    return (t.get("name") or f"{t.get('location', '')} {t.get('nickname', '')}").strip()


def main() -> int:
    t0 = time.time()
    seasons_dir = os.path.join(HERE, "seasons")
    years = sorted(int(d) for d in os.listdir(seasons_dir) if d.isdigit())
    me = my_owner()
    managers: dict[str, dict] = {}
    seasons, picks, h2h, names = [], [], {}, {}
    for year in years:
        label = f"{year - 1}-{str(year)[2:]}"
        path = os.path.join(HERE, "..", "docs", "fantasy", label, "data.json")
        if not os.path.exists(path):
            print(f"  {label}: no season page yet (run build_season.py {year}); skipping")
            continue
        with open(path, encoding="utf-8") as f:
            sd = json.load(f)
        with open(os.path.join(seasons_dir, str(year), "espn", "league.json"), encoding="utf-8") as f:
            lg = json.load(f)
        owner = {t["id"]: t.get("owner") or f"team{t['id']}" for t in lg["teams"]}
        for t in lg["teams"]:
            m = managers.setdefault(owner[t["id"]], {"key": owner[t["id"]], "seasons": []})
            m["seasons"].append(year)
            m["name"] = team_name(t)  # seasons run oldest to newest, so this ends on the latest name
        reg = sd["meta"]["league"]["regularWeeks"]
        # All-play and head to head, from that season's matchups
        weekly: dict[int, list] = {}
        for mp, h, hp, a, ap, win, tier in sd["matchups"]:
            if a is None or hp is None or ap is None:
                continue
            if mp <= reg:
                weekly.setdefault(mp, []).extend([(owner.get(h), hp), (owner.get(a), ap)])
            kind = "reg" if mp <= reg else "po" if tier == 1 else None
            if kind:
                for x, y, won in ((owner.get(h), owner.get(a), win == 1), (owner.get(a), owner.get(h), win == 2)):
                    rec = h2h.setdefault(x, {}).setdefault(y, {"reg": [0, 0, 0], "po": [0, 0, 0]})[kind]
                    rec[0 if won else 2 if win == 0 else 1] += 1
        allplay: dict[str, list] = {}
        for sc in weekly.values():
            for o, pts in sc:
                w = sum(1 for o2, p2 in sc if o2 != o and pts > p2)
                l = sum(1 for o2, p2 in sc if o2 != o and pts < p2)
                ap_ = allplay.setdefault(o, [0, 0, 0.0])
                ap_[0] += w
                ap_[1] += l
                ap_[2] += w / max(1, len(sc) - 1)
        teams = []
        for tid, abbrev, nm, w, l, t, pf, pa, seed, fin in sd["teams"]:
            o = owner.get(tid)
            ap_ = allplay.get(o, [0, 0, 0.0])
            teams.append([o, nm, abbrev, w, l, t, pf, pa, seed, fin, ap_[0], ap_[1], round(ap_[2], 2)])
        for overall, rnd, rp, tid, pid, keeper, total, rank, vs in sd["draft"]:
            picks.append([year, overall, rnd, owner.get(tid), pid, keeper, total, rank, vs])
        for p in sd["players"]:
            names[p["id"]] = p["n"]
        seasons.append({"year": year, "label": label, "teams": teams, "regularWeeks": reg,
                        "playoffTeams": sd["meta"]["league"]["playoffTeams"], "keepers": sd["meta"]["league"]["keepers"],
                        "weeks": len(sd["weeks"]), "check": sd["meta"].get("check")})
        print(f"  {label}: {len(teams)} teams, {len(sd['draft'])} picks")

    # What the box scores say, over every finished season
    raw = os.path.join(HERE, "data", "raw")
    box, sched = load(raw, config.FIRST_SEASON, max(years))
    df = model.add_advanced(model.clean(model.regular_season(box, sched)))
    found = studies.run(df[df.season <= max(years)])
    print(f"  studies: {found['yearToYear']['pairs']} player season pairs, {found['windows']['cases']:,} next-10 predictions")

    used = {p[4] for p in picks}
    payload = {
        "meta": {"built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "me": me,
                 "seasons": [s["label"] for s in seasons], "firstStudySeason": config.FIRST_SEASON,
                 "lastStudySeason": max(years)},
        "managers": sorted(managers.values(), key=lambda m: (-len(m["seasons"]), m["name"])),
        "seasons": seasons,
        "h2h": h2h,
        "picks": picks,
        "names": {pid: n for pid, n in names.items() if pid in used},
        "studies": found,
    }
    out = os.path.join(HERE, "..", "docs", "fantasy", "history")
    os.makedirs(out, exist_ok=True)
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    with open(os.path.join(out, "data.json"), "w", encoding="utf-8") as f:
        f.write(data)
    template = page.read_template(os.path.join(HERE, "web", "history.html"))
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write(page._document(template.replace(page.URL_MARK, json.dumps("data.json"))))
    page.icon(os.path.join(out, "apple-touch-icon.png"))
    print(f"History: {len(seasons)} seasons, {len(managers)} managers, {len(picks)} picks, data {len(data) / 1e3:.0f} KB "
          f"-> docs/fantasy/history/ ({time.time() - t0:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
