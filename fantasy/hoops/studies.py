"""What nine seasons of box scores say about the numbers on the page. Each study tests one idea.

1. Year to year: which numbers carry over from one season to the next (is FP per minute steadier than minutes?)
2. Windows: what best predicts a player's next 10 games (L5, L10, L20, the season so far, or a blend)?
3. Streaks: when a player's last 10 run hot, how much of it lasts, and does it matter whether the jump came from
   minutes or from per-minute production?
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import model


def _corr(a: pd.Series, b: pd.Series) -> float:
    return float(np.corrcoef(a, b)[0, 1])


def year_to_year(df: pd.DataFrame, min_gp: int = 40, min_mpg: float = 15) -> dict:
    """Correlation of each number between consecutive seasons, for players with real roles in both."""
    played = df[df.played]
    sums = played.groupby(["player_id", "season"])[model.COMPONENTS].sum()
    r = model.rates(sums).reset_index()
    r = r[(r.gp >= min_gp) & (r.mpg >= min_mpg)]
    nxt = r.copy()
    nxt["season"] -= 1
    pairs = r.merge(nxt, on=["player_id", "season"], suffixes=("", "_next"))
    out = {"pairs": int(len(pairs)), "corr": {}}
    for k in ("fpg", "mpg", "fpm", "usg", "ts", "astp", "rebp"):
        out["corr"][k] = round(_corr(pairs[k], pairs[k + "_next"]), 3)
    # How much of next season's FP/G each piece explains on its own
    out["explains_next_fpg"] = {k: round(_corr(pairs[k], pairs["fpg_next"]) ** 2, 3) for k in ("fpg", "mpg", "fpm")}
    # Typical change: median absolute change of each, as a share of its level
    out["typical_change"] = {k: round(float(((pairs[k + "_next"] - pairs[k]).abs() / pairs[k]).median()), 3)
                             for k in ("fpg", "mpg", "fpm")}
    return out


def _windows(g: pd.DataFrame) -> pd.DataFrame:
    """For one player-season, at each game: the trailing windows and what the next 10 games actually were."""
    fp, mn = g.fp.to_numpy(float), g.mp.to_numpy(float)
    fpm_n = g.fp_m.to_numpy(float)
    n = len(fp)
    cs = np.concatenate([[0], np.cumsum(fp)])
    cm = np.concatenate([[0], np.cumsum(mn)])
    cfm = np.concatenate([[0], np.cumsum(fpm_n)])
    rows = []
    for i in range(20, n - 10 + 1):  # at least 20 games in, 10 still to come
        def avg(k):
            return (cs[i] - cs[i - k]) / k
        nxt = (cs[i + 10] - cs[i]) / 10
        nxt_min = (cm[i + 10] - cm[i]) / 10
        nxt_fpm = (cfm[i + 10] - cfm[i]) / max(cm[i + 10] - cm[i], 1e-9)
        rows.append((avg(5), avg(10), avg(20), cs[i] / i, nxt,
                     (cm[i] - cm[i - 10]) / 10, cm[i] / i, nxt_min,
                     (cfm[i] - cfm[i - 10]) / max(cm[i] - cm[i - 10], 1e-9), cfm[i] / max(cm[i], 1e-9), nxt_fpm))
    return pd.DataFrame(rows, columns=["l5", "l10", "l20", "szn", "next", "l10_min", "szn_min", "next_min",
                                       "l10_fpm", "szn_fpm", "next_fpm"])


def window_backtest(df: pd.DataFrame, min_fpg: float = 15) -> dict:
    """Mean error predicting a player's next 10 games from each window (players averaging min_fpg or more)."""
    played = df[df.played].sort_values(["player_id", "date"])
    parts = [_windows(g) for _, g in played.groupby(["player_id", "season"]) if len(g) >= 30]
    w = pd.concat(parts, ignore_index=True)
    w = w[w.szn >= min_fpg]
    w["blend"] = 0.3 * w.l10 + 0.7 * w.szn
    err = {k: round(float((w[k] - w.next).abs().mean()), 2) for k in ("l5", "l10", "l20", "szn", "blend")}
    # Best blend of L10 and the season so far, on a grid
    grid = {round(a, 1): float(((a * w.l10 + (1 - a) * w.szn) - w.next).abs().mean()) for a in np.arange(0, 1.01, 0.1)}
    best = min(grid, key=grid.get)
    return {"cases": int(len(w)), "mae": err, "best_l10_weight": best, "best_mae": round(grid[best], 2),
            "minutes_mae": {"l10": round(float((w.l10_min - w.next_min).abs().mean()), 2),
                            "szn": round(float((w.szn_min - w.next_min).abs().mean()), 2)},
            "fpm_mae": {"l10": round(float((w.l10_fpm - w.next_fpm).abs().mean()), 3),
                        "szn": round(float((w.szn_fpm - w.next_fpm).abs().mean()), 3)},
            "_frame": w}


def streaks(w: pd.DataFrame, jump: float = 5.0) -> dict:
    """When L10 runs `jump`+ FP/G above the season so far: how much of the gap shows up in the next 10 games?

    Split by where the jump came from: more minutes (role) or more per minute (production).
    """
    w = w.copy()
    w["gap"] = w.l10 - w.szn
    w["kept"] = (w.next - w.szn) / w.gap
    w["from_min"] = (w.l10_min - w.szn_min) * w.szn_fpm  # the decomposition from the player card
    w["from_rate"] = w.l10_min * (w.l10_fpm - w.szn_fpm)
    out = {}
    for name, sel in (("hot", w.gap >= jump), ("cold", w.gap <= -jump)):
        s = w[sel]
        mins = s[s.from_min.abs() >= s.from_rate.abs()]
        rate = s[s.from_min.abs() < s.from_rate.abs()]
        out[name] = {"cases": int(len(s)), "kept": round(float(s.kept.median()), 2),
                     "minutes_driven": {"cases": int(len(mins)), "kept": round(float(mins.kept.median()), 2)},
                     "rate_driven": {"cases": int(len(rate)), "kept": round(float(rate.kept.median()), 2)}}
    return out


def run(df: pd.DataFrame) -> dict:
    yy = year_to_year(df)
    bt = window_backtest(df)
    st = streaks(bt.pop("_frame"))
    return {"yearToYear": yy, "windows": bt, "streaks": st}
