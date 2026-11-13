"""From raw box scores to the numbers: regular-season games, fantasy points, advanced stats, rolling windows.

Advanced stats follow Basketball-Reference's box-score formulas. Over any stretch of games (a window, a season) a rate is
the sum of its numerator over the sum of its denominator, never an average of single-game percentages, so a 4-minute
cameo doesn't count as much as a 40-minute start.
"""
from __future__ import annotations

import pandas as pd

from . import config

RENAME = {
    "minutes": "min",
    "points": "pts",
    "rebounds": "reb",
    "offensive_rebounds": "oreb",
    "defensive_rebounds": "dreb",
    "assists": "ast",
    "steals": "stl",
    "blocks": "blk",
    "turnovers": "tov",
    "fouls": "pf",
    "field_goals_made": "fgm",
    "field_goals_attempted": "fga",
    "three_point_field_goals_made": "tpm",
    "three_point_field_goals_attempted": "tpa",
    "free_throws_made": "ftm",
    "free_throws_attempted": "fta",
}
STATS = list(RENAME.values())
COUNTING = [s for s in STATS if s != "min"]

# Summed over a stretch of games, these give every rate on the page (see rates()).
COMPONENTS = ["gp", "mp", "fp", "fp_m", "pts", "reb", "oreb", "dreb", "ast", "stl", "blk", "tov", "fgm", "fga", "tpm",
              "tpa", "ftm", "fta", "usg_n", "usg_d", "ast_n", "ast_d", "reb_n", "reb_d", "oreb_n", "oreb_d", "dreb_n",
              "dreb_d", "stl_n", "stl_d", "blk_n", "blk_d"]

NBA_TEAM_IDS = set(range(1, 31))  # ESPN's ids for the 30 teams; All-Star teams have others
NOT_REGULAR = {"ALLSTAR", "CC"}  # CC is the NBA Cup championship game, which doesn't count in regular-season stats


def fantasy_points(df: pd.DataFrame, scoring: dict | None = None) -> pd.Series:
    s = scoring or config.SCORING
    return (s["points"] * df.pts + s["rebounds"] * df.reb + s["assists"] * df.ast + s["steals"] * df.stl
            + s["blocks"] * df.blk + s["turnovers"] * df.tov
            + s["fg_made"] * df.fgm + s["fg_missed"] * (df.fga - df.fgm)
            + s["ft_made"] * df.ftm + s["ft_missed"] * (df.fta - df.ftm))


def regular_season(box: pd.DataFrame, sched: pd.DataFrame) -> pd.DataFrame:
    """Regular-season NBA games only: no playoffs, play-in, All-Star games or the NBA Cup final."""
    excluded = set(sched.loc[sched.type_abbreviation.isin(NOT_REGULAR), "game_id"].astype(int))
    keep = ((box.season_type == 2) & box.team_id.isin(NBA_TEAM_IDS) & box.opponent_team_id.isin(NBA_TEAM_IDS)
            & ~box.game_id.astype(int).isin(excluded))
    return box[keep]


def clean(box: pd.DataFrame) -> pd.DataFrame:
    """One row per player per team game, with short stat names, a played flag and fantasy points."""
    df = box[box.athlete_id.notna()].rename(columns=RENAME)  # ESPN has a few blank placeholder rows
    df = df[["game_id", "season", "game_date", "athlete_id", "athlete_display_name", "athlete_position_abbreviation",
             "team_id", "team_abbreviation", "opponent_team_id", "opponent_team_abbreviation", "home_away", "starter",
             "did_not_play", "reason", *STATS]].copy()
    df = df.rename(columns={"athlete_id": "player_id", "athlete_display_name": "name",
                            "athlete_position_abbreviation": "pos", "team_abbreviation": "team",
                            "opponent_team_abbreviation": "opp"})
    df["player_id"] = df.player_id.astype("int64")
    df["game_id"] = df.game_id.astype("int64")
    df["team_id"] = df.team_id.astype("int64")
    df["opponent_team_id"] = df.opponent_team_id.astype("int64")
    df["season"] = df.season.astype("int64")
    df["date"] = pd.to_datetime(df.game_date)
    df[STATS] = df[STATS].astype(float).fillna(0.0)
    # ESPN lists everyone in uniform; a player counts as having played if he logged minutes or any stat.
    df["played"] = ~df.did_not_play.fillna(False).astype(bool) & ((df["min"] > 0) | (df[COUNTING].abs().sum(axis=1) > 0))
    df["fp"] = fantasy_points(df)
    return df.drop(columns=["game_date"]).sort_values(["player_id", "date", "game_id"]).reset_index(drop=True)


def add_advanced(df: pd.DataFrame) -> pd.DataFrame:
    """Per-game numerators and denominators for usage, AST%, REB%, STL%, BLK% (team and opponent context)."""
    team = df.groupby(["game_id", "team_id"])[["min", "fga", "fgm", "fta", "tov", "reb", "oreb", "dreb", "tpa"]].sum()
    team = team.add_prefix("tm_").reset_index()
    # ESPN rounds minutes, so the team total drifts; snap it to 240 plus 25 per overtime.
    team["tm_min"] = 240 + 25 * ((team.tm_min - 240) / 25).round().clip(lower=0)
    opp = team.rename(columns={c: "op_" + c[3:] for c in team.columns if c.startswith("tm_")})
    opp = opp.rename(columns={"team_id": "opponent_team_id"})
    ctx = team.merge(opp, on="game_id")
    ctx = ctx[ctx.team_id != ctx.opponent_team_id]

    def poss(a: str, b: str) -> pd.Series:
        orb_share = ctx[f"{a}_oreb"] / (ctx[f"{a}_oreb"] + ctx[f"{b}_dreb"]).replace(0, 1)
        return ctx[f"{a}_fga"] + 0.4 * ctx[f"{a}_fta"] - 1.07 * orb_share * (ctx[f"{a}_fga"] - ctx[f"{a}_fgm"]) + ctx[f"{a}_tov"]

    ctx["op_poss"] = 0.5 * (poss("tm", "op") + poss("op", "tm"))
    df = df.merge(ctx, on=["game_id", "team_id", "opponent_team_id"], how="left")

    on = df.played & (df["min"] > 0)
    mp = df["min"].where(on, 0.0)
    five = df.tm_min / 5
    df["gp"] = df.played.astype(int)
    df["mp"] = mp
    df["fp_m"] = df.fp.where(on, 0.0)  # fantasy points from games with minutes on record, for FP per minute
    df["usg_n"] = ((df.fga + 0.44 * df.fta + df.tov) * five).where(on, 0.0)
    df["usg_d"] = mp * (df.tm_fga + 0.44 * df.tm_fta + df.tm_tov)
    df["ast_n"] = df.ast.where(on, 0.0)
    df["ast_d"] = ((mp / five) * df.tm_fgm - df.fgm).where(on, 0.0)
    df["reb_n"] = (df.reb * five).where(on, 0.0)
    df["reb_d"] = mp * (df.tm_reb + df.op_reb)
    df["oreb_n"] = (df.oreb * five).where(on, 0.0)
    df["oreb_d"] = mp * (df.tm_oreb + df.op_dreb)
    df["dreb_n"] = (df.dreb * five).where(on, 0.0)
    df["dreb_d"] = mp * (df.tm_dreb + df.op_oreb)
    df["stl_n"] = (df.stl * five).where(on, 0.0)
    df["stl_d"] = mp * df.op_poss
    df["blk_n"] = (df.blk * five).where(on, 0.0)
    df["blk_d"] = mp * (df.op_fga - df.op_tpa)
    ctx_cols = [c for c in df.columns if c.startswith(("tm_", "op_"))]
    return df.drop(columns=ctx_cols)


def rates(s: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Per-game averages and rates from summed components (works on one row of sums or a frame of them)."""
    def div(a, b, k=1.0):
        return (k * a / b.where(b != 0)) if isinstance(b, pd.Series) else (k * a / b if b else float("nan"))

    out = {
        "gp": s["gp"],
        "fpg": div(s["fp"], s["gp"]),
        "mpg": div(s["mp"], s["gp"]),
        "fpm": div(s["fp_m"], s["mp"]),
        "ppg": div(s["pts"], s["gp"]),
        "rpg": div(s["reb"], s["gp"]),
        "apg": div(s["ast"], s["gp"]),
        "spg": div(s["stl"], s["gp"]),
        "bpg": div(s["blk"], s["gp"]),
        "tpg": div(s["tov"], s["gp"]),
        "ts": div(s["pts"], 2 * (s["fga"] + 0.44 * s["fta"]), 100),
        "efg": div(s["fgm"] + 0.5 * s["tpm"], s["fga"], 100),
        "usg": div(s["usg_n"], s["usg_d"], 100),
        "astp": div(s["ast_n"], s["ast_d"], 100),
        "rebp": div(s["reb_n"], s["reb_d"], 100),
        "orebp": div(s["oreb_n"], s["oreb_d"], 100),
        "drebp": div(s["dreb_n"], s["dreb_d"], 100),
        "tovp": div(s["tov"], s["fga"] + 0.44 * s["fta"] + s["tov"], 100),
        "stlp": div(s["stl_n"], s["stl_d"], 100),
        "blkp": div(s["blk_n"], s["blk_d"], 100),
    }
    return pd.DataFrame(out) if isinstance(s, pd.DataFrame) else pd.Series(out)


def add_rolling(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Rolling n-game FP/G and FP per minute on every game played (needs n games; crosses seasons)."""
    played = df[df.played]
    g = played.groupby("player_id")
    fp = g.fp.rolling(n, min_periods=n).sum().reset_index(level=0, drop=True)
    fpm_n = g.fp_m.rolling(n, min_periods=n).sum().reset_index(level=0, drop=True)
    mp = g.mp.rolling(n, min_periods=n).sum().reset_index(level=0, drop=True)
    df[f"r{n}_fpg"] = fp / n
    df[f"r{n}_fpm"] = fpm_n / mp.where(mp > 0)
    return df


def windows(df: pd.DataFrame, season: int) -> dict[str, pd.DataFrame]:
    """Sums of the components per player over each window, as of the last game in the data."""
    played = df[df.played].copy()
    played["back"] = played.groupby("player_id").cumcount(ascending=False)  # 0 = his most recent game
    out = {}
    for key, n in config.WINDOWS.items():
        out[key] = played[played.back < n].groupby("player_id")[COMPONENTS].sum()
    t, b = config.TREND_WINDOW, config.BASELINE_GAMES
    out["base"] = played[(played.back >= t) & (played.back < t + b)].groupby("player_id")[COMPONENTS].sum()
    out["season"] = played[played.season == season].groupby("player_id")[COMPONENTS].sum()
    out["last"] = played[played.season == season - 1].groupby("player_id")[COMPONENTS].sum()
    return out


def seasons(df: pd.DataFrame) -> pd.DataFrame:
    """One row per player per season: sums, rates and the teams he played for, in order."""
    played = df[df.played]
    sums = played.groupby(["player_id", "season"])[COMPONENTS].sum()
    out = rates(sums)
    teams = played.groupby(["player_id", "season"]).team.agg(lambda s: "/".join(dict.fromkeys(s)))
    return out.join(teams).reset_index()


def missed_games(df: pd.DataFrame, season: int) -> pd.DataFrame:
    """For each player: his last game, his team then, and how many of that team's games he's missed since."""
    played = df[df.played]
    last = played.groupby("player_id").tail(1)[["player_id", "date", "team_id", "season"]]
    team_games = df[df.season == season][["team_id", "game_id", "date"]].drop_duplicates()
    m = last.merge(team_games, on="team_id", how="left", suffixes=("", "_t"))
    missed = m[m.date_t > m.date].groupby("player_id").game_id.nunique()
    last = last.set_index("player_id")
    last["missed"] = missed.reindex(last.index).fillna(0).astype(int)
    return last
