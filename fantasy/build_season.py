"""Build the page for a finished season: docs/fantasy/<2025-26>/ (committed; a finished season never changes).

    python3 fantasy/build_season.py 2026        # 2026 = the 2025-26 season

Needs the box scores (downloaded by build.py, or here if missing) and the league's ESPN import in
fantasy/seasons/<season>/espn/ (tools/import_season.py, run once from the Actions tab). Without the import it still
builds the player side, with no league.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from build import load  # noqa: E402
from hoops import config, fetch, model, page, season  # noqa: E402


def live_ages() -> dict[int, int]:
    """Ages, today, from the live page's numbers (they come from ESPN's NBA rosters). Optional."""
    try:
        with urllib.request.urlopen(config.DATA_URL, timeout=30) as r:
            return {p["id"]: p["age"] for p in json.load(r)["players"] if p.get("age") is not None}
    except Exception as e:  # noqa: BLE001
        print(f"  (no ages: {e})")
        return {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("season", type=int, help="the year the season ends, e.g. 2026 for 2025-26")
    ap.add_argument("--data", default=os.path.join(HERE, "data"))
    args = ap.parse_args(argv)

    t0 = time.time()
    raw = os.path.join(args.data, "raw")
    for s in (args.season - 1, args.season):
        if not os.path.exists(fetch.local_path(raw, "player_box", s)):
            fetch.download(raw, s, s)
    box, sched = load(raw, args.season - 1, args.season)
    df = model.add_advanced(model.clean(model.regular_season(box, sched)))
    label = f"{args.season - 1}-{str(args.season)[2:]}"

    espn = season.load_espn(os.path.join(HERE, "seasons", str(args.season)))
    print(f"{label}: {int(df[(df.season == args.season) & df.played].shape[0]):,} games played; "
          + ("league import found" if espn else "no league import (player side only)"))
    payload = season.build(df, args.season, espn, live_ages())
    if espn:
        opening = df[(df.season == args.season) & df.played].date.min()
        same, total = season.check_against_espn(payload, espn, opening)
        payload["meta"]["check"] = [same, total]
        print(f"  Team scores rebuilt from the daily lineups match ESPN's on {same:,} of {total:,} team-days")
        me = payload["meta"]["league"]["me"]
        print(f"  {len(payload['teams'])} teams (yours: {me}), {len(payload['matchups'])} matchups, "
              f"{len(payload['draft'])} picks, {len(payload['moves'])} roster moves, {len(payload['weeks'])} weeks")

    out = os.path.join(HERE, "..", "docs", "fantasy", label)
    os.makedirs(out, exist_ok=True)
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    with open(os.path.join(out, "data.json"), "w", encoding="utf-8") as f:
        f.write(data)
    template = page.read_template(os.path.join(HERE, "web", "season.html"))
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write(page._document(template.replace(page.URL_MARK, json.dumps("data.json"))))
    page.icon(os.path.join(out, "apple-touch-icon.png"))
    print(f"Page: {len(payload['players'])} players, data {len(data) / 1e6:.1f} MB -> docs/fantasy/{label}/ "
          f"({time.time() - t0:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
