import pytest

from app.services import power


def test_sample_size_matches_reference():
    r = power.sample_size("proportion", baseline=0.10, mde=0.10, alpha=0.05, power=0.8)
    assert 14_500 < r["n_control"] < 15_000
    assert r["total"] == r["n_control"] + r["n_treatment"]


def test_mean_metric_matches_cohens_d():
    r = power.sample_size("mean", baseline=100, mde=5, mde_type="absolute", std=20)
    assert 250 <= r["n_control"] <= 255


def test_power_roundtrip():
    n = power.sample_size(baseline=0.2, mde=0.05)["n_control"]
    assert power.achieved_power(baseline=0.2, mde=0.05, n_per_group=n)["power"] == pytest.approx(0.8, abs=0.01)


def test_unequal_allocation_and_duration():
    r = power.sample_size(baseline=0.1, mde=0.2, ratio=2.0, daily_traffic=1000)
    assert r["n_treatment"] >= 2 * r["n_control"] - 1
    assert r["duration_days"] == -(-r["total"] // 1000)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        power.sample_size(baseline=0.95, mde=0.2)
    with pytest.raises(ValueError):
        power.sample_size("mean", baseline=10, mde=0.1)
