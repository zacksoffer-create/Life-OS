"""Print the shape of ESPN's fantasy API answers for the league, to debug reading it. Never prints league members' names.

    python3 fantasy/tools/espn_probe.py [season]

Checks: where the rosters are, what the player pool holds, and which reading of the league's FGM/FGA scoring matches
ESPN's own fantasy-point totals.
"""
from __future__ import annotations

import collections
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from hoops import config, espn  # noqa: E402


def get(url, headers=None):
    req = urllib.request.Request(url, headers={**espn.UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except Exception as e:  # noqa: BLE001
        print(f"    request failed: {e}")
        return None


def rosters(d, label):
    if not d:
        return
    teams = d.get("teams") or []
    print(f"  {label}: top keys {sorted(d)[:20]}; teams {len(teams)}")
    if teams:
        print(f"    team keys: {sorted(teams[0])}")
        counts = [(t.get("id"), len(((t.get("roster") or {}).get("entries")) or [])) for t in teams]
        print(f"    roster entries per team: {counts}")
        e = next((x for t in teams for x in ((t.get("roster") or {}).get("entries") or [])), None)
        if e:
            print(f"    entry keys: {sorted(e)}; playerPoolEntry keys: {sorted(e.get('playerPoolEntry') or {})}")


def main():
    season = int(sys.argv[1]) if len(sys.argv) > 1 else 2027
    base = espn.API.format(season=season, league=config.ESPN_LEAGUE_ID)
    status = get(base + "?view=mStatus") or {}
    st = status.get("status") or {}
    print(f"status: {json.dumps({k: st.get(k) for k in ['currentMatchupPeriod', 'firstScoringPeriod', 'latestScoringPeriod', 'isActive', 'previousSeasons']})}")
    print(f"scoringPeriodId: {status.get('scoringPeriodId')}; seasonId: {status.get('seasonId')}")
    sp = status.get("scoringPeriodId") or st.get("latestScoringPeriod")
    rosters(get(base + "?view=mTeam&view=mRoster&view=mSettings&view=mStatus"), "combined views")
    rosters(get(base + "?view=mRoster"), "mRoster alone")
    if sp:
        rosters(get(base + f"?view=mRoster&scoringPeriodId={sp}"), f"mRoster, scoringPeriodId={sp}")
    rosters(get(base + "?view=mRoster&view=mTeam&view=mMatchup&view=mSettings&view=mStandings"), "espn-api style")

    for label, flt in [
        ("pool, FA+WAIVERS+ONTEAM", {"players": {"filterStatus": {"value": ["FREEAGENT", "WAIVERS", "ONTEAM"]}, "limit": 1500, "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}}),
        ("pool, ONTEAM only", {"players": {"filterStatus": {"value": ["ONTEAM"]}, "limit": 500}}),
        ("pool, no filter", {"players": {"limit": 1500, "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}}),
    ]:
        d = get(base + "?view=kona_player_info", {"X-Fantasy-Filter": json.dumps(flt)})
        ps = (d or {}).get("players") or []
        print(f"  {label}: {len(ps)} players; status {dict(collections.Counter(p.get('status') for p in ps))}; "
              f"onTeamId {dict(collections.Counter(p.get('onTeamId') for p in ps).most_common(12))}")
        if ps:
            print(f"    entry keys: {sorted(ps[0])}; player keys: {sorted(ps[0].get('player') or {})}")

    # Scoring check: ESPN's own fantasy average vs. both readings of FGM/FGA, from ESPN's own stat lines
    d = get(base + "?view=kona_player_info", {"X-Fantasy-Filter": json.dumps(
        {"players": {"limit": 15, "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}})})
    print("  scoring check (this season's per-game averages): ESPN | made=+1,miss=-1 | FGM+1,FGA-1")
    for p in (d or {}).get("players") or []:
        pl = p.get("player") or {}
        for s in pl.get("stats") or []:
            if s.get("seasonId") == season and s.get("statSourceId") == 0 and s.get("statSplitTypeId") == 0:
                v = {int(k): float(x) for k, x in (s.get("averageStats") or {}).items()}
                if not v:
                    continue
                base_pts = v.get(0, 0) + v.get(6, 0) + v.get(3, 0) + v.get(2, 0) + v.get(1, 0) - v.get(11, 0)
                ours = base_pts + v.get(13, 0) - (v.get(14, 0) - v.get(13, 0)) + v.get(15, 0) - (v.get(16, 0) - v.get(15, 0))
                espn_style = base_pts + v.get(13, 0) - v.get(14, 0) + v.get(15, 0) - v.get(16, 0)
                print(f"    {pl.get('fullName')}: {s.get('appliedAverage')} | {ours:.1f} | {espn_style:.1f}")
                break


if __name__ == "__main__":
    main()
