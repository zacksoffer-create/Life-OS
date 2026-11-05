"""Build backend/data/mlb.json from the Lahman Baseball Database: real MLB from 1990 through the last finished season.

Run it when the data updates. It needs pandas and pyarrow; the game itself never does:
    pip install pylahman pyarrow        # pylahman bundles the Lahman tables as parquet files
    python3 lifeos/tools/build_mlb_data.py [--lahman DIR_WITH_PARQUET_FILES]

What it keeps (compact arrays, so the phone bundle stays small):
- teams: every franchise (keyed by Lahman's franchise id) with its current name, nickname, abbreviation, league, division
- seasons: every team-season: league, division, W, L, runs, runs allowed, finish in the division, and how it ended
- post: every postseason series
- awards: MVP, Cy Young, Rookie of the Year, World Series MVP
- people: every player in the file
- bat / pit: player-seasons per team (a player traded mid-season has a row per team) with a stat line and a value in wins
- rosters: where every player in the last season finished it (after trades), for the live seasons

The value ("wins") is an estimate in the spirit of WAR, built from what Lahman has (no play-by-play, no fielding data):
- hitters: runs above average from a wOBA-style line, steals, the park, a position adjustment from where they played,
  plus replacement level (20 runs per 600 PA)
- pitchers: runs saved against a replacement pitcher (starters and relievers have different bars), from a blend of FIP
  and runs allowed, park-adjusted, with a leverage bump for closers
- runs become wins at about 10 per win (it moves with the scoring of the era), and each season is scaled so all of MLB adds
  up to 1,000 wins per 162 games, the usual WAR convention (so a team of replacement players wins about 48)
It reads the big seasons right, but it doesn't know defense, so a glove-first shortstop reads a little low.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "backend", "data", "mlb.json")
FIRST = 1990

POS = ["c", "1b", "2b", "3b", "ss", "lf", "cf", "rf", "dh"]
POS_RUNS = {"c": 12.5, "ss": 7.5, "2b": 2.5, "3b": 2.5, "cf": 2.5, "lf": -7.5, "rf": -7.5, "1b": -12.5, "dh": -17.5}  # per 162 games
WOBA = {"ubb": 0.69, "hbp": 0.72, "b1": 0.89, "b2": 1.27, "b3": 1.62, "hr": 2.10}
ABBR = {"ANA": "LAA", "FLA": "MIA", "TBD": "TB", "KCR": "KC", "SDP": "SD", "SFG": "SF", "WSN": "WSH", "CHW": "CWS", "OAK": "ATH"}
NAME_FIX = {"Los Angeles Angels of Anaheim": "Los Angeles Angels"}
CITY_FIX = {"OAK": "Sacramento"}  # the Athletics, between Oakland and Las Vegas
AWARDS = {"Most Valuable Player": "mvp", "Cy Young Award": "cy", "Rookie of the Year": "roy", "World Series MVP": "wsmvp"}
BAT_LINE = ["G", "PA", "AB", "R", "H", "2B", "3B", "HR", "RBI", "SB", "BB", "SO"]
PIT_LINE = ["G", "GS", "IPOuts", "W", "L", "SV", "H", "ER", "HR", "BB", "SO"]


def lahman_dir(arg: str | None) -> str:
    if arg:
        return arg
    try:
        import pylahman
        return os.path.join(os.path.dirname(pylahman.__file__), "data")
    except ImportError:
        hits = glob.glob(os.path.join(os.path.expanduser("~"), "**", "pylahman", "data", "Teams.parquet"), recursive=True)
        if hits:
            return os.path.dirname(hits[0])
    raise SystemExit("Can't find the Lahman tables: pip install pylahman, or pass --lahman DIR")


def nickname(name: str) -> str:
    parts = name.split()
    return " ".join(parts[-2:]) if parts[-1] in ("Sox", "Jays") else parts[-1]


def num(x) -> float:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(x) else x


def build(D: str) -> dict:
    def rd(t):
        return pd.read_parquet(os.path.join(D, t + ".parquet"))
    T, B, P, A, PE, SP, AW = (rd(x) for x in ("Teams", "Batting", "Pitching", "Appearances", "People", "SeriesPost", "AwardsPlayers"))
    T = T[T.yearID >= FIRST]
    last = int(T.yearID.max())
    trows = T.to_dict("records")
    fr = {(int(r["yearID"]), r["teamID"]): r["franchID"] for r in trows}
    park = {(int(r["yearID"]), r["teamID"]): (num(r["BPF"]) or 100.0, num(r["PPF"]) or 100.0) for r in trows}

    # --- the league environment per season
    env = {}
    for r in trows:
        e = env.setdefault(int(r["yearID"]), {"R": 0.0, "PA": 0.0, "G": 0.0, "teams": 0, "outs": 0.0})
        e["R"] += num(r["R"])
        e["PA"] += num(r["AB"]) + num(r["BB"]) + num(r["HBP"]) + num(r["SF"])
        e["G"] += num(r["G"])
        e["teams"] += 1
        e["outs"] += num(r["IPOuts"])
    for e in env.values():
        e["r_pa"] = e["R"] / e["PA"]
        e["ra9"] = 9 * e["R"] / (e["outs"] / 3)
        e["rpw"] = 10 * math.sqrt((2 * e["R"] / e["G"]) / 9)  # ~10 runs a win at 9 runs a game (both teams)
        e["g"] = e["G"] / e["teams"]

    # --- where everyone ended the last season (the highest stint), for the live rosters
    ended = {}
    for df in (B, P):
        for r in df[df.yearID == last][["playerID", "stint", "teamID"]].to_dict("records"):
            if r["playerID"] not in ended or r["stint"] > ended[r["playerID"]][0]:
                ended[r["playerID"]] = (r["stint"], r["teamID"])

    # --- appearances: where everyone played
    app = {}
    for r in A[A.yearID >= FIRST].to_dict("records"):
        app[(r["playerID"], int(r["yearID"]), r["teamID"])] = r

    # --- pitchers
    P = P[P.yearID >= FIRST].copy()
    for c in ["HBP", "GF", "SV", "IBB", "SO", "BB", "HR", "R", "ER", "H", "W", "L", "G", "GS"]:
        P[c] = P[c].fillna(0)
    P = P.groupby(["playerID", "yearID", "teamID"], as_index=False).sum(numeric_only=True)
    P = P[P.IPOuts > 0]
    prow = P.to_dict("records")
    lg_fip = {}
    for r in prow:
        f = lg_fip.setdefault(int(r["yearID"]), [0.0, 0.0])
        f[0] += 13 * r["HR"] + 3 * (r["BB"] + r["HBP"]) - 2 * r["SO"]
        f[1] += r["IPOuts"] / 3
    outs_by = {}
    for r in prow:
        k = (r["playerID"], int(r["yearID"]))
        outs_by[k] = outs_by.get(k, 0) + r["IPOuts"]

    # --- hitters
    B = B[B.yearID >= FIRST].copy()
    for c in ["IBB", "HBP", "SF", "SH", "CS", "SB", "SO", "RBI", "BB"]:
        B[c] = B[c].fillna(0)
    B = B.groupby(["playerID", "yearID", "teamID"], as_index=False).sum(numeric_only=True)
    brow = B.to_dict("records")
    lg_w = {}
    for r in brow:
        r["PA"] = r["AB"] + r["BB"] + r["HBP"] + r["SF"] + r["SH"]
        b1 = r["H"] - r["2B"] - r["3B"] - r["HR"]
        r["num"] = (WOBA["ubb"] * (r["BB"] - r["IBB"]) + WOBA["hbp"] * r["HBP"] + WOBA["b1"] * b1 + WOBA["b2"] * r["2B"]
                    + WOBA["b3"] * r["3B"] + WOBA["hr"] * r["HR"])
        r["den"] = r["AB"] + r["BB"] - r["IBB"] + r["SF"] + r["HBP"]
        w = lg_w.setdefault(int(r["yearID"]), [0.0, 0.0])
        w[0] += r["num"]
        w[1] += r["den"]

    bat, pit = [], []
    raw = {}

    for r in brow:
        y = int(r["yearID"])
        if r["PA"] <= 0:
            continue
        e = env[y]
        woba = r["num"] / r["den"] if r["den"] else 0.0
        runs = (woba - lg_w[y][0] / lg_w[y][1]) / 1.2 * r["PA"]
        runs += 0.2 * r["SB"] - 0.4 * r["CS"]
        runs -= (park.get((y, r["teamID"]), (100, 100))[0] / 100 - 1) * e["r_pa"] * r["PA"]
        a = app.get((r["playerID"], y, r["teamID"]))
        pos = "DH"
        if a:
            gp = {p: num(a.get("G_" + p)) for p in POS}
            if not (gp["lf"] or gp["cf"] or gp["rf"]) and num(a.get("G_of")):
                gp["lf"] = num(a.get("G_of"))  # older rows don't split the outfield
            tot = sum(gp.values())
            if tot:
                scale = min(1.0, (num(a.get("G_all")) or tot) / tot)
                runs += sum(gp[p] * POS_RUNS[p] for p in POS) / 162 * scale
                pos = max(POS, key=lambda p: gp[p]).upper()
            elif num(a.get("G_p")):
                pos = "P"
        runs += 20 * r["PA"] / 600
        v = runs / e["rpw"]
        raw[y] = raw.get(y, 0.0) + v
        if r["PA"] < (30 if y >= last - 2 else 120) or outs_by.get((r["playerID"], y), 0) > r["PA"]:
            continue  # small samples, and pitchers batting, stay out of the file (their value still counts in the total)
        bat.append([r["playerID"], y, fr[(y, r["teamID"])], pos, v] + [int(num(r[k])) for k in BAT_LINE])

    for r in prow:
        y = int(r["yearID"])
        e = env[y]
        ip = r["IPOuts"] / 3
        fip = (13 * r["HR"] + 3 * (r["BB"] + r["HBP"]) - 2 * r["SO"]) / ip + (e["ra9"] - lg_fip[y][0] / lg_fip[y][1])
        ra9 = 9 * r["R"] / ip
        est = 0.6 * fip + 0.4 * ra9 - (park.get((y, r["teamID"]), (100, 100))[1] / 100 - 1) * e["ra9"]
        gs = r["GS"] / r["G"] if r["G"] else 0.0
        repl = e["ra9"] * (1.307 * gs + 1.068 * (1 - gs))  # a .380 starter / a .470 reliever
        runs = (repl - est) * ip / 9
        if gs < 0.2:
            runs *= 1 + 0.4 * min(1.0, r["GF"] / 50)  # closers pitch the innings that matter
        v = runs / e["rpw"]
        raw[y] = raw.get(y, 0.0) + v
        if r["IPOuts"] < (30 if y >= last - 2 else 120):
            continue  # the last three seasons keep everyone (they're the live rosters); older ones keep the regulars
        pit.append([r["playerID"], y, fr[(y, r["teamID"])], v] + [int(num(r[k])) for k in PIT_LINE])

    # --- scale every season to 1,000 wins per 162 games
    scale = {y: 1000 * (env[y]["g"] / 162) / raw[y] for y in raw}
    for row in bat:
        row[4] = round(row[4] * scale[row[1]], 1)
    for row in pit:
        row[3] = round(row[3] * scale[row[1]], 1)

    # --- people
    ids = sorted({r[0] for r in bat} | {r[0] for r in pit})
    idx = {p: i for i, p in enumerate(ids)}
    pe = {r["playerID"]: r for r in PE[PE.playerID.isin(ids)].to_dict("records")}
    people = []
    for p in ids:
        r = pe.get(p, {})
        debut, final = r.get("debut"), r.get("finalGame")
        people.append([p, r.get("nameFirst") or "", r.get("nameLast") or p, int(num(r.get("birthYear"))) or None,
                       r.get("bats") or "", r.get("throws") or "",
                       int(debut.year) if hasattr(debut, "year") and not pd.isna(debut) else None,
                       int(final.year) if hasattr(final, "year") and not pd.isna(final) else None])
    for row in bat + pit:
        row[0] = idx[row[0]]

    # --- teams and seasons
    latest = {}
    for r in sorted(trows, key=lambda r: r["yearID"]):
        latest[r["franchID"]] = r
    teams = {}
    for f, r in sorted(latest.items()):
        name = NAME_FIX.get(r["name"], r["name"])
        nick = nickname(name)
        city = CITY_FIX.get(f) or name[: -len(nick)].strip() or name
        teams[f] = {"name": name, "nick": nick, "city": city, "abbr": ABBR.get(f, f), "lg": r["lgID"], "div": r["divID"]}
    eras = {}  # franchise -> [[first year, name], ...] when its name changed (the Florida Marlins, the Cleveland Indians)
    for r in sorted(trows, key=lambda r: r["yearID"]):
        nm = NAME_FIX.get(r["name"], r["name"])
        e = eras.setdefault(r["franchID"], [])
        if not e or e[-1][1] != nm:
            e.append([int(r["yearID"]), nm])
    eras = {f: e for f, e in eras.items() if len(e) > 1}
    seasons = []
    for r in sorted(trows, key=lambda r: (r["yearID"], r["lgID"], r["divID"] or "", r["Rank"])):
        how = "".join(k for k, col in (("D", "DivWin"), ("W", "WCWin"), ("P", "LgWin"), ("S", "WSWin")) if r[col] == "Y")
        seasons.append([int(r["yearID"]), r["franchID"], r["lgID"], r["divID"] or "", int(r["W"]), int(r["L"]), int(r["R"]),
                        int(r["RA"]), int(r["Rank"]), how])
    post = []
    for r in SP[SP.yearID >= FIRST].sort_values(["yearID", "round"]).to_dict("records"):
        y = int(r["yearID"])
        post.append([y, r["round"], fr[(y, r["teamIDwinner"])], fr[(y, r["teamIDloser"])], int(r["wins"]), int(r["losses"])])
    awards = []
    for r in AW[(AW.yearID >= FIRST) & AW.awardID.isin(list(AWARDS))].sort_values(["yearID", "awardID", "lgID"]).to_dict("records"):
        if r["playerID"] in idx:
            awards.append([int(r["yearID"]), AWARDS[r["awardID"]], r["lgID"], idx[r["playerID"]]])

    rosters = {}
    for p, (_, t) in ended.items():
        if p in idx:
            rosters.setdefault(fr[(last, t)], []).append(idx[p])
    rosters = {t: sorted(v) for t, v in sorted(rosters.items())}

    return {"about": ("Real MLB, 1990 through the last finished season, from the Lahman Baseball Database "
                      "(seanlahman.com, CC BY-SA 3.0). Player values are LIFE OS's own estimates (see tools/build_mlb_data.py)."),
            "first": FIRST, "last": last, "bat_line": BAT_LINE, "pit_line": PIT_LINE,
            "teams": teams, "seasons": seasons, "post": post, "awards": awards, "people": people, "bat": bat, "pit": pit,
            "rosters": rosters, "names": eras}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lahman", help="the folder with Lahman's parquet files (default: the installed pylahman package)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    data = build(lahman_dir(a.lahman))
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"{a.out}: {data['first']}-{data['last']}, {len(data['people'])} players, {len(data['bat'])} batting and "
          f"{len(data['pit'])} pitching seasons, {os.path.getsize(a.out) / 1e6:.1f} MB")
