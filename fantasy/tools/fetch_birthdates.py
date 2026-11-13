"""Fetch NBA players' birthdates from ESPN into fantasy/seasons/birthdates.json (committed; birthdates never change).

    python3 fantasy/tools/fetch_birthdates.py

Covers everyone who played since 2002-03 (the young-player model trains on rookies back to then). Only players not
already in the file are fetched, so it can run again each season to pick up the new rookies. ESPN's API isn't
reachable from Claude's cloud sessions; run it from the Actions tab (Rolling 10 data > Run workflow > birthdates).
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from hoops import config, fetch  # noqa: E402
from hoops.espn import birthdate  # noqa: E402

OUT = os.path.join(HERE, "..", "seasons", "birthdates.json")


def main() -> int:
    raw = os.path.join(HERE, "..", "data", "raw")
    last = fetch.download(raw, config.YOUNG_FIRST_SEASON, fetch.season_for(pd.Timestamp.today().date()), log=lambda *a: None)
    ids = set()
    for season in range(config.YOUNG_FIRST_SEASON, last + 1):
        b = pd.read_parquet(fetch.local_path(raw, "player_box", season), columns=["athlete_id", "minutes"])
        ids |= set(b[b.minutes.fillna(0) > 0].athlete_id.dropna().astype(int))
    known = {}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            known = json.load(f)
    todo = sorted(i for i in ids if str(i) not in known)
    print(f"{len(ids)} players since {config.YOUNG_FIRST_SEASON - 1}-{str(config.YOUNG_FIRST_SEASON)[2:]}; "
          f"{len(known)} already known; fetching {len(todo)}")
    found = 0
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        for pid, dob in zip(todo, pool.map(birthdate, todo)):
            if dob:
                known[str(pid)] = dob
                found += 1
    print(f"  found {found} of {len(todo)}; {len(known)} birthdates in all")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(known.items(), key=lambda kv: int(kv[0]))), f, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
