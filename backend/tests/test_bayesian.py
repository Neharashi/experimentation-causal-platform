from app.services import bayesian


def test_beta_binomial(ab):
    r = bayesian.bayesian_ab(ab, "group", "converted", draws=500)
    assert r["model"] == "Beta-Binomial"
    assert r["prob_treatment_better"] > 0.95
    assert r["lift_hdi"][0] < 0.10 < r["lift_hdi"][1]
    assert r["diagnostics"]["r_hat"] < 1.05


def test_null_is_uncertain(ab_null):
    r = bayesian.bayesian_ab(ab_null, "group", "time_on_page", draws=500)
    assert r["model"].startswith("Normal")
    assert 0.02 < r["prob_treatment_better"] < 0.98
