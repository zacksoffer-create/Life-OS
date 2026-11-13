"""The young-player model: its logistic fit, its AUC, the early-career signals and the outcome labels."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hoops import young  # noqa: E402


def test_logit_learns_a_clear_signal_and_handles_missing_values():
    rng = np.random.default_rng(0)
    x = rng.normal(size=400)
    y = (x + rng.normal(scale=0.5, size=400) > 0).astype(int)
    df = pd.DataFrame({"a": x, "noise": rng.normal(size=400)})
    df.loc[::10, "noise"] = np.nan  # filled with the training median
    m = young.Logit(["a", "noise"]).fit(df, y)
    p = m.predict(df)
    assert young.auc(y, p) > 0.9
    assert m.predict(pd.DataFrame({"a": [2.0], "noise": [np.nan]}))[0] > 0.9
    assert m.predict(pd.DataFrame({"a": [-2.0], "noise": [0.0]}))[0] < 0.1
    d = m.drivers(pd.DataFrame({"a": [2.0], "noise": [0.0]}))
    assert d["a"] > abs(d["noise"])


def test_auc():
    assert young.auc(np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.8, 0.9])) == 1.0
    assert young.auc(np.array([0, 1]), np.array([0.9, 0.1])) == 0.0
    assert young.auc(np.array([0, 1, 0, 1]), np.array([0.5, 0.5, 0.5, 0.5])) == pytest.approx(0.5)


def test_features_measure_the_per_minute_climb():
    n = 30
    g = pd.DataFrame({
        "date": pd.date_range("2024-10-22", periods=n), "yr": [1] * 15 + [2] * 15,
        "mp": [20.0] * n, "lg_fpm": [1.0] * n,
        "fp": np.linspace(10, 30, n), "fp_m": np.linspace(10, 30, n),
    })
    for c in young.model.COMPONENTS:
        if c not in g:
            g[c] = 1.0
    f = young.features(g, age=20.0)
    assert f["growth"] > 0.5  # FP per minute went from about 0.6 to 1.4
    assert f["fpg_y2"] > f["fpg_y1"]
    assert f["age"] == 20.0 and f["gp"] == n


def test_outcome_labels():
    assert young.outcome_label(5) == "Star"
    assert young.outcome_label(80) == "Starter"
    assert young.outcome_label(150) == "Rotation"
    assert young.outcome_label(250) == "Fringe"
    assert young.outcome_label(np.nan) == "Didn't stick"
