import numpy as np

from app.services import sequential
from app.services.simulate import simulate_ab


def test_msprt_stops_on_real_effect(ab):
    r = sequential.msprt(ab, "group", "converted", time_col="day")
    assert r["stopped"] and r["stop_n"] < len(ab)
    p = [x["p_always_valid"] for x in r["looks"]]
    assert all(np.diff(p) <= 1e-12)


def test_msprt_controls_false_positives():
    hits = sum(sequential.msprt(simulate_ab(2000, relative_lift=0, seed=s), "group", "converted")["stopped"]
               for s in range(40))
    assert hits <= 5


def test_obf_constant_reference_value():
    assert abs(sequential.obf_constant(5, 0.05) - 2.04) < 0.03


def test_group_sequential(ab):
    r = sequential.group_sequential(ab, "group", "converted", time_col="day", looks=5)
    assert r["stopped"] and len(r["looks"]) == 5
    assert r["looks"][0]["boundary"] > r["looks"][-1]["boundary"]
