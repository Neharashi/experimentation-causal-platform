import pytest

from app.core.datasets import LALONDE_COVS, load_sample
from app.services import causal


def test_psm_recovers_effect(obs):
    r = causal.psm(obs, "treatment", "outcome", ["x1", "x2", "x3"], estimand="ate", refute=False)
    assert abs(r["naive_difference"] - 2.0) > 1.0
    assert r["estimate"] == pytest.approx(2.0, abs=0.4)
    assert r["dml"]["ate"]["ci"][0] < 2.0 < r["dml"]["ate"]["ci"][1]
    assert r["max_smd_after"] < 0.1


def test_psm_lalonde_close_to_experimental_benchmark():
    r = causal.psm(load_sample("lalonde_observational"), "treat", "re78", LALONDE_COVS, refute=False, dml=False)
    assert r["naive_difference"] < -8000
    assert 800 < r["estimate"] < 2800


def test_psm_refutations(obs):
    r = causal.psm(obs, "treatment", "outcome", ["x1", "x2", "x3"], estimand="ate", dml=False)
    placebo = next(x for x in r["refutations"] if x["test"].startswith("Placebo"))
    assert abs(placebo["new_effect"]) < 0.5


def test_dml_heterogeneity(obs):
    r = causal.dml(obs, "treatment", "outcome", ["x1", "x2", "x3"], modifier_col="x3")
    assert r["ate"]["estimate"] == pytest.approx(2.0, abs=0.3)
    assert len(r["by_group"]) == 2


def test_did_twfe_and_pretrends(panel):
    r = causal.did(panel, "outcome", "treated", "period", post_col="post", unit_col="unit")
    assert r["ci"][0] < 5.0 < r["ci"][1]
    assert r["pretrend_p_value"] > 0.05
    assert any(e["post"] for e in r["event_study"])


def test_did_treatment_time(panel):
    r = causal.did(panel.drop(columns="post"), "outcome", "treated", "period", treatment_time=8)
    assert r["estimate"] == pytest.approx(5.0, abs=1.0)


def test_synthetic_control_prop99():
    r = causal.synthetic_control(load_sample("prop99"), "state", "year", "cigsale", "California", 1989)
    assert sum(w["weight"] for w in r["weights"]) == pytest.approx(1.0, abs=1e-3)
    assert -30 < r["att"] < -10
    assert r["pre_rmspe"] < 3 and r["placebo_p_value"] <= 0.1


def test_synthetic_control_validation():
    with pytest.raises(ValueError):
        causal.synthetic_control(load_sample("prop99"), "state", "year", "cigsale", "Atlantis", 1989)
