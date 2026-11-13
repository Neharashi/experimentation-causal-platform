import numpy as np
import pandas as pd
import pytest
from statsmodels.stats.multitest import multipletests

from app.services import frequentist


def test_chisquare_detects_lift(ab):
    r = frequentist.chisquare(ab, "group", "converted")
    assert r["significant"] and r["ci"][0] < r["diff"] < r["ci"][1]
    assert not r["srm"]["mismatch"]


def test_ttest_null_not_significant(ab_null):
    r = frequentist.ttest(ab_null, "group", "time_on_page")
    assert not r["significant"] and r["ci"][0] < 0 < r["ci"][1]


def test_chisquare_rejects_non_binary(ab):
    with pytest.raises(ValueError):
        frequentist.chisquare(ab, "group", "revenue")


def test_srm_flags_imbalance():
    df = pd.DataFrame({"g": ["a"] * 6000 + ["b"] * 4000, "y": np.ones(10000)})
    r = frequentist.ttest(df.assign(y=np.random.default_rng(0).normal(size=10000)), "g", "y")
    assert r["srm"]["mismatch"] and r["warnings"]


def test_corrections_match_statsmodels():
    p = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205]
    r = frequentist.correct_pvalues(p)
    np.testing.assert_allclose(r["fdr_bh"]["adjusted"], multipletests(p, method="fdr_bh")[1])
    assert r["n_significant_bonferroni"] <= r["n_significant_fdr_bh"] <= r["n_significant_raw"]


def test_multi_metric_finds_true_effects_only(ab):
    r = frequentist.multi_metric(ab, "group", ["converted", "revenue", "time_on_page", "pages_viewed"])
    sig = {x["metric"] for x in r["results"] if x["significant"]}
    assert sig == {"converted", "revenue"}
