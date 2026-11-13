"""Young players: what a player's first seasons say about where his career goes.

Learned from every rookie class since 2002-03 whose years 3 to 5 have been played, scored with the league's formula.
Two stages, because a player's evidence grows:
- stage 1: his first season (this season's sophomores before year 2 fills in, and rookies once they have a sample)
- stage 2: his first two seasons

The outcome is his best season in years 3-5: a top-100 fantasy season (a starter in a 10-team league) or a top-30 one
(a star), ranking each season by FP/G among players with 40+ games so eras with different scoring compare fairly.
Fantasy points are measured against that season's league-wide FP per minute for the same reason.

What the research behind it found: the year-2 average carries most of the signal; beyond it, a rolling-10 FP per
minute that keeps climbing, producing efficiently on limited minutes, the year 1 to year 2 jump, and youth predict a
better career. Hot 10-game stretches, finishing strong and consistency add nothing.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import model, page

STAGE_FEATURES = {
    1: ["fpg_y1", "mpg_y1", "fpm_y1", "growth", "end_r10", "stlp", "usg", "age"],
    2: ["fpg_y1", "fpg_y2", "mpg_y1", "mpg_y2", "fpm_y1", "fpm_y2", "growth", "end_r10", "stlp", "usg", "age"],
}
# How much each feature counts when finding a player's closest matches
COMP_WEIGHTS = {"fpg_y1": 1.5, "fpg_y2": 2.0, "mpg_y1": 0.8, "mpg_y2": 1.0, "fpm_y1": 1.2, "fpm_y2": 1.5, "growth": 1.0,
                "end_r10": 0.5, "stlp": 0.5, "usg": 0.7, "age": 1.5}
MIN_SAMPLE = {1: (20, 300), 2: (40, 600)}  # games and minutes in the stage's seasons, for training
STARTER, STAR = 100, 30


# ---- the data ----------------------------------------------------------------------------------------------------

def prepare(df: pd.DataFrame, birthdates: dict[int, str]) -> dict:
    """Season lines, ranks, debuts and ages for everyone, from cleaned player-games (all seasons, with advanced)."""
    played = df[df.played].copy()
    lg = played.groupby("season").apply(lambda g: g.fp_m.sum() / max(g.mp.sum(), 1), include_groups=False)
    played["lg_fpm"] = played.season.map(lg)
    lines = model.rates(played.groupby(["player_id", "season"])[model.COMPONENTS].sum()).reset_index()
    q = lines[lines.gp >= 40].copy()
    q["rank"] = q.groupby("season").fpg.rank(ascending=False, method="min")
    lines = lines.merge(q[["player_id", "season", "rank"]], on=["player_id", "season"], how="left")
    debut = played.groupby("player_id").season.min()
    lines["debut"] = lines.player_id.map(debut)
    lines["yr"] = lines.season - lines.debut + 1
    played["debut"] = played.player_id.map(debut)
    played["yr"] = played.season - played.debut + 1
    ages = {}
    for pid, d in debut.items():
        dob = birthdates.get(str(pid)) or birthdates.get(pid)
        if dob:  # age on February 1 of his rookie season, the usual "season age"
            ages[pid] = (pd.Timestamp(year=int(d), month=2, day=1) - pd.Timestamp(dob)).days / 365.25
    return {"played": played, "lines": lines, "debut": debut, "ages": ages, "lg": lg,
            "names": played.groupby("player_id").name.last(), "team": played.groupby("player_id").team_id.last(),
            "pos": played.groupby("player_id").pos.last()}


def features(g: pd.DataFrame, age: float | None) -> dict:
    """One player's early-career signals from his games in years 1 (and 2), in league-relative units."""
    g = g.sort_values("date")
    fp, mp, fpm_n, lg = (g.fp.to_numpy(float), g.mp.to_numpy(float), g.fp_m.to_numpy(float), g.lg_fpm.to_numpy(float))
    yr = g.yr.to_numpy()
    out = {"gp": len(g), "min": float(mp.sum()), "age": age}
    for k in (1, 2):
        sel = yr == k
        if sel.sum() >= 10:
            out[f"fpg_y{k}"] = float((fp[sel] / lg[sel]).mean())
            out[f"mpg_y{k}"] = float(mp[sel].mean())
            out[f"fpm_y{k}"] = float(fpm_n[sel].sum() / max(mp[sel].sum(), 1) / lg[sel].mean())
    if len(g) >= 10:
        r_fp = pd.Series(fp / lg).rolling(10).mean().to_numpy()
        r_mp = pd.Series(mp).rolling(10).sum().to_numpy()
        r_fpm = pd.Series(fpm_n / lg).rolling(10).sum().to_numpy() / np.where(r_mp > 0, r_mp, np.nan)
        out["growth"] = float(r_fpm[-1] - r_fpm[9])  # rolling-10 FP per minute: where he is now vs his first 10 games
        out["end_r10"] = float(r_fp[-1])
    sums = g[model.COMPONENTS].sum()
    r = model.rates(sums)
    out["stlp"], out["usg"] = float(r["stlp"]), float(r["usg"])
    return out


def training_set(prep: dict, stage: int, last_complete: int) -> pd.DataFrame:
    """Every past player with a real stage sample whose years 3-5 are all played, with his features and outcome."""
    played, lines, debut, ages = prep["played"], prep["lines"], prep["debut"], prep["ages"]
    classes = debut[(debut >= 2003) & (debut <= last_complete - 4)].index
    early = played[played.player_id.isin(classes) & (played.yr <= stage)]
    rows = {}
    games, minutes = MIN_SAMPLE[stage]
    for pid, g in early.groupby("player_id"):
        if len(g) < games or g.mp.sum() < minutes or (stage == 2 and (g.yr == 2).sum() < 10):
            continue
        rows[pid] = features(g, ages.get(pid))
    t = pd.DataFrame.from_dict(rows, orient="index")
    later = lines[lines.player_id.isin(t.index) & lines.yr.between(3, 5) & (lines.season <= last_complete)]
    t["best_rank"] = later.groupby("player_id")["rank"].min().reindex(t.index)
    best = later[later.gp >= 40].sort_values("fpg", ascending=False).groupby("player_id").head(1).set_index("player_id")
    t["best_fpg"] = best.fpg.reindex(t.index)
    t["best_season"] = best.season.reindex(t.index)
    t["starter"] = (t.best_rank <= STARTER).astype(int)
    t["star"] = (t.best_rank <= STAR).astype(int)
    t["debut"] = debut.reindex(t.index)
    return t


# ---- the model: L2 logistic regression, in numpy -----------------------------------------------------------------

class Logit:
    def __init__(self, cols: list[str], l2: float = 1.0):
        self.cols, self.l2 = cols, l2

    def _x(self, df: pd.DataFrame) -> np.ndarray:
        x = df.reindex(columns=self.cols).astype(float).to_numpy()
        x = np.where(np.isnan(x), self.med, x)
        return np.column_stack([np.ones(len(x)), (x - self.mu) / self.sd])

    def fit(self, df: pd.DataFrame, y: np.ndarray) -> "Logit":
        raw = df.reindex(columns=self.cols).astype(float)
        self.med = raw.median().to_numpy()
        filled = raw.fillna(raw.median())
        self.mu, self.sd = filled.mean().to_numpy(), filled.std().replace(0, 1).to_numpy()
        x = self._x(df)
        w = np.zeros(x.shape[1])
        pen = np.full(x.shape[1], self.l2)
        pen[0] = 0
        for _ in range(50):  # Newton steps
            p = 1 / (1 + np.exp(-x @ w))
            grad = x.T @ (p - y) + pen * w
            hess = (x * (p * (1 - p))[:, None]).T @ x + np.diag(pen)
            step = np.linalg.solve(hess, grad)
            w -= step
            if np.abs(step).max() < 1e-8:
                break
        self.w = w
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return 1 / (1 + np.exp(-self._x(df) @ self.w))

    def drivers(self, row: pd.DataFrame) -> dict[str, float]:
        """Each feature's push on the odds for one player (in log-odds, relative to an average player)."""
        x = self._x(row)[0, 1:]
        return dict(zip(self.cols, (x * self.w[1:]).round(3)))


def auc(y: np.ndarray, p: np.ndarray) -> float:
    pos, neg = p[y == 1], p[y == 0]
    if not len(pos) or not len(neg):
        return float("nan")
    ranks = pd.Series(np.concatenate([pos, neg])).rank().to_numpy()
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def track_record(t: pd.DataFrame, cols: list[str], target: str, folds: int = 5) -> dict:
    """Out-of-sample check, holding out whole rookie classes: AUC and how often each odds band came true."""
    classes = np.array(sorted(t.debut.unique()))
    fold_of = {c: i % folds for i, c in enumerate(classes)}
    pred = np.zeros(len(t))
    for k in range(folds):
        test = t.debut.map(fold_of).to_numpy() == k
        m = Logit(cols).fit(t[~test], t[target].to_numpy()[~test])
        pred[test] = m.predict(t[test])
    y = t[target].to_numpy()
    bands = []
    for lo, hi in ((0, 0.1), (0.1, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.01)):
        sel = (pred >= lo) & (pred < hi)
        if sel.sum():
            bands.append([lo, min(hi, 1.0), int(sel.sum()), round(float(y[sel].mean()), 3)])
    return {"auc": round(auc(y, pred), 3), "bands": bands, "n": int(len(t)), "rate": round(float(y.mean()), 3)}


# ---- putting it together -------------------------------------------------------------------------------------------

def outcome_label(rank) -> str:
    if pd.isna(rank):
        return "Didn't stick"
    return "Star" if rank <= STAR else "Starter" if rank <= STARTER else "Rotation" if rank <= 200 else "Fringe"


def build(df: pd.DataFrame, current: int, birthdates: dict, log=print) -> dict:
    """The Young Players page's data: everyone in his first three seasons now, his odds, signals, arc and comps."""
    prep = prepare(df, birthdates)
    last_complete = current - 1
    have_age = len(prep["ages"]) > 0.8 * len(prep["debut"][prep["debut"] >= 2003])
    stages, models, train = {}, {}, {}
    for stage, cols in STAGE_FEATURES.items():
        cols = [c for c in cols if c != "age" or have_age]
        t = training_set(prep, stage, last_complete)
        models[stage] = {k: Logit(cols).fit(t, t[k].to_numpy()) for k in ("starter", "star")}
        train[stage] = t
        stages[stage] = {"features": cols, "classes": [int(t.debut.min()), int(t.debut.max())],
                         "starter": track_record(t, cols, "starter"), "star": track_record(t, cols, "star")}
        log(f"  stage {stage}: {len(t)} past players; out-of-sample AUC starter {stages[stage]['starter']['auc']}, "
            f"star {stages[stage]['star']['auc']}" + ("" if have_age else " (no ages yet)"))

    played, debut, names = prep["played"], prep["debut"], prep["names"]
    young_ids = debut[debut >= current - 2].index
    players = []
    for pid in young_ids:
        g = played[played.player_id == pid]
        yr_now = int(current - debut[pid] + 1)
        y2 = g[g.yr == 2]
        stage = 2 if (g.yr == 1).any() and len(y2) >= 10 else 1
        window = g[g.yr <= stage]
        if len(window) < 10 or window.mp.sum() < 150:
            continue
        f = features(window, prep["ages"].get(pid))
        row = pd.DataFrame([f], index=[pid])
        cols = stages[stage]["features"]
        ps, pst = models[stage]["starter"].predict(row)[0], models[stage]["star"].predict(row)[0]
        # Closest past players at the same stage
        t = train[stage]
        m = models[stage]["starter"]
        z = lambda d: (d.reindex(columns=cols).astype(float).fillna(pd.Series(m.med, index=cols)) - m.mu) / m.sd
        w = np.array([COMP_WEIGHTS.get(c, 1.0) for c in cols])
        dist = np.sqrt((((z(t) - z(row).iloc[0]) ** 2) * w).sum(axis=1)).sort_values()
        comps = []
        for cid, dd in dist.head(5).items():
            c = t.loc[cid]
            comps.append([names.get(cid, str(cid)), int(c.debut), page._num(c.age), page._num(c.best_rank, 0),
                          page._num(c.best_fpg), outcome_label(c.best_rank), round(float(dd), 2)])
        # Where he stands against past players at the same stage (percentiles)
        pct = {k: round(float((t[k] < f[k]).mean()), 2) for k in cols if k in f and f[k] is not None and k in t}
        if f.get("age") is not None and "age" in t:
            pct["age"] = round(float((t["age"] > f["age"]).mean()), 2)  # younger = higher
        lines = prep["lines"][prep["lines"].player_id == pid].sort_values("season")
        players.append({
            "id": int(pid), "n": names.get(pid, str(pid)), "tm": int(prep["team"].get(pid, 0)), "pos": prep["pos"].get(pid) or "",
            "debut": int(debut[pid]), "yr": yr_now, "stage": stage, "early": bool(stage == 1 and yr_now == 1),
            "age": page._num(f.get("age")), "p": round(float(ps), 3), "pStar": round(float(pst), 3),
            "f": {k: page._num(v, 3) for k, v in f.items() if k in cols or k in ("gp", "min")},
            "pct": pct, "drivers": models[stage]["starter"].drivers(row), "comps": comps,
            "seasons": [[int(r.season), int(r.gp), page._num(r.mpg), page._num(r.fpg), page._num(r.fpm, 3), page._num(r.usg),
                         page._num(r.ts), page._num(r["rank"], 0)] for _, r in lines.iterrows()],
            "arc": [[int(d), int(round(mn)), int(round(fp))] for d, mn, fp in
                    zip((g.date - page.EPOCH).dt.days, g.mp, g.fp)],
        })
    players.sort(key=lambda p: -p["p"])
    log(f"  {len(players)} young players now (debuts {current - 2} on)")
    return {
        "meta": {"current": current, "currentLabel": f"{current - 1}-{str(current)[2:]}", "stages": stages,
                 "haveAge": have_age, "starter": STARTER, "star": STAR},
        "teams": {int(t): a for t, a in df.groupby("team_id").team.last().items()},
        "players": players,
    }
