"""Simulation-based validation: writes docs/results.md and docs/results.json."""
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
warnings.filterwarnings("ignore")

from app.core.datasets import LALONDE_COVS, load_sample  # noqa: E402
from app.services import causal, frequentist, power, sequential  # noqa: E402
from app.services.simulate import simulate_did, simulate_observational  # noqa: E402

rng = np.random.default_rng(2026)
results = {}


def power_calibration(sims=2000):
    rows = []
    for base, mde in [(0.05, 0.2), (0.10, 0.10), (0.30, 0.05)]:
        n = power.sample_size(baseline=base, mde=mde)["n_control"]
        xa, xb = rng.binomial(n, base, sims), rng.binomial(n, base * (1 + mde), sims)
        p_pool = (xa + xb) / (2 * n)
        z = (xb - xa) / n / np.sqrt(p_pool * (1 - p_pool) * 2 / n)
        rows.append({"baseline": base, "relative_mde": mde, "n_per_group": n, "target_power": 0.8,
                     "empirical_power": float(np.mean(np.abs(z) > 1.96))})
    return rows


def ab_frame(n, p_a, p_b, seed):
    r = np.random.default_rng(seed)
    g = r.permutation(np.repeat(["control", "treatment"], n))
    y = r.binomial(1, np.where(g == "treatment", p_b, p_a))
    return pd.DataFrame({"group": g, "y": y})


def peeking(sims=300, n=10000):
    out = {}
    for label, p_b in [("null", 0.10), ("effect", 0.115)]:
        naive = ms = obf = fixed = 0
        stop_n = []
        for s in range(sims):
            df = ab_frame(n, 0.10, p_b, s)
            r = sequential.msprt(df, "group", "y", looks=20)
            naive += r["naive_stop_look"] is not None
            fixed += r["looks"][-1]["p_naive"] < 0.05
            ms += r["stopped"]
            if r["stopped"]:
                stop_n.append(r["stop_n"])
            obf += sequential.group_sequential(df, "group", "y", looks=5)["stopped"]
        out[label] = {"fixed_horizon_1_look": fixed / sims, "naive_peeking_20_looks": naive / sims, "msprt_20_looks": ms / sims,
                      "obrien_fleming_5_looks": obf / sims,
                      "msprt_avg_sample_when_stopped": float(np.mean(stop_n)) if stop_n else None}
    out["fixed_sample_n"] = 2 * n
    return out


def multiple_testing(sims=1000, m=20, true=5, z_effect=3.0):
    acc = {k: {"fwer": 0, "fdp": [], "power": []} for k in ("none", "bonferroni", "fdr_bh")}
    is_true = np.arange(m) < true
    for _ in range(sims):
        z = rng.normal(size=m) + z_effect * is_true
        p = 2 * stats.norm.sf(np.abs(z))
        c = frequentist.correct_pvalues(p)
        for k, rej in [("none", p < 0.05), ("bonferroni", np.array(c["bonferroni"]["reject"])),
                       ("fdr_bh", np.array(c["fdr_bh"]["reject"]))]:
            fp = (rej & ~is_true).sum()
            acc[k]["fwer"] += fp > 0
            acc[k]["fdp"].append(fp / max(rej.sum(), 1))
            acc[k]["power"].append((rej & is_true).sum() / true)
    return {k: {"family_wise_error": v["fwer"] / sims, "false_discovery_rate": float(np.mean(v["fdp"])),
                "power": float(np.mean(v["power"]))} for k, v in acc.items()}


def causal_recovery(seeds=20):
    est = {"naive": [], "psm": [], "dml": []}
    cover = {"psm": 0, "dml": 0}
    for s in range(seeds):
        df = simulate_observational(n=3000, ate=2.0, seed=100 + s)
        r = causal.psm(df, "treatment", "outcome", ["x1", "x2", "x3"], estimand="ate", refute=False)
        est["naive"].append(r["naive_difference"])
        est["psm"].append(r["estimate"])
        est["dml"].append(r["dml"]["ate"]["estimate"])
        cover["psm"] += r["ci"][0] <= 2 <= r["ci"][1]
        cover["dml"] += r["dml"]["ate"]["ci"][0] <= 2 <= r["dml"]["ate"]["ci"][1]
    out = {k: {"mean_estimate": float(np.mean(v)), "bias": float(np.mean(v) - 2),
               "rmse": float(np.sqrt(np.mean((np.array(v) - 2) ** 2)))} for k, v in est.items()}
    for k in cover:
        out[k]["ci_coverage"] = cover[k] / seeds
    did_est, did_cov = [], 0
    for s in range(seeds):
        r = causal.did(simulate_did(effect=5.0, seed=200 + s), "outcome", "treated", "period",
                       post_col="post", unit_col="unit")
        did_est.append(r["estimate"])
        did_cov += r["ci"][0] <= 5 <= r["ci"][1]
    out["did"] = {"true_effect": 5.0, "mean_estimate": float(np.mean(did_est)),
                  "bias": float(np.mean(did_est) - 5), "ci_coverage": did_cov / seeds}
    return out


def real_data():
    lo = load_sample("lalonde_observational")
    r = causal.psm(lo, "treat", "re78", LALONDE_COVS, refute=False)
    p99 = load_sample("prop99")
    sc = causal.synthetic_control(p99, "state", "year", "cigsale", "California", 1989)
    d = causal.did(p99, "cigsale", "california", "year", treatment_time=1989, unit_col="state")
    return {"lalonde": {"experimental_benchmark": 1794, "naive": r["naive_difference"], "psm_att": r["estimate"],
                        "psm_ci": r["ci"], "dml_att": r["dml"]["att"]["estimate"]},
            "prop99": {"synthetic_control_att": sc["att"], "relative": sc["relative_effect"],
                       "pre_rmspe": sc["pre_rmspe"], "placebo_p": sc["placebo_p_value"],
                       "did_twfe": d["estimate"], "did_pretrend_p": d["pretrend_p_value"]}}


def latency():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    ab = c.post("/api/datasets/samples/simulated_ab").json()["dataset_id"]
    lo = c.post("/api/datasets/samples/lalonde_observational").json()["dataset_id"]
    p99 = c.post("/api/datasets/samples/prop99").json()["dataset_id"]
    g = {"dataset_id": ab, "group_col": "group", "metric_col": "converted"}
    calls = {
        "power/sample-size": ("/api/power/sample-size", {"baseline": 0.1, "mde": 0.1}),
        "experiments/chisquare (40k rows)": ("/api/experiments/chisquare", g),
        "experiments/sequential mSPRT": ("/api/experiments/sequential", {**g, "time_col": "day"}),
        "experiments/bayesian (PyMC)": ("/api/experiments/bayesian", g),
        "causal/psm (16k rows, refuters + DML)": ("/api/causal/psm", {"dataset_id": lo, "treatment_col": "treat",
                                                  "outcome_col": "re78", "covariates": LALONDE_COVS}),
        "causal/synthetic-control (+38 placebos)": ("/api/causal/synthetic-control", {
            "dataset_id": p99, "unit_col": "state", "time_col": "year", "outcome_col": "cigsale",
            "treated_unit": "California", "treatment_time": 1989}),
    }
    out = {}
    for name, (url, body) in calls.items():
        times = []
        for _ in range(3):
            t = time.perf_counter()
            assert c.post(url, json=body).status_code == 200
            times.append(time.perf_counter() - t)
        out[name] = float(np.median(times))
    return out


def write_markdown(r):
    L = ["# Validation results", "", "Generated by `python scripts/evaluate.py`. All numbers come from simulation "
         "with a known ground truth, or from real datasets with a published benchmark.", ""]
    L += ["## 1. Power calculator calibration", "", "| Baseline | Relative MDE | n / group | Target power | Empirical power |",
          "|---|---|---|---|---|"]
    L += [f"| {x['baseline']:.0%} | {x['relative_mde']:.0%} | {x['n_per_group']:,} | 80% | {x['empirical_power']:.1%} |"
          for x in r["power_calibration"]]
    p = r["peeking"]
    L += ["", "## 2. Peeking: false-positive rate and power", "",
          f"{p['fixed_sample_n']:,} users per simulated test, 300 simulations per scenario, α = 5%.", "",
          "| Procedure | False-positive rate (no effect) | Power (+15% lift) |", "|---|---|---|",
          f"| Fixed-horizon test, single look at the end | {p['null']['fixed_horizon_1_look']:.1%} | {p['effect']['fixed_horizon_1_look']:.1%} |",
          f"| Naive p-value checked at 20 looks | **{p['null']['naive_peeking_20_looks']:.1%}** | {p['effect']['naive_peeking_20_looks']:.1%} |",
          f"| mSPRT always-valid p-value, 20 looks | {p['null']['msprt_20_looks']:.1%} | {p['effect']['msprt_20_looks']:.1%} |",
          f"| O'Brien-Fleming, 5 looks | {p['null']['obrien_fleming_5_looks']:.1%} | {p['effect']['obrien_fleming_5_looks']:.1%} |",
          "", "Peeking with a naive p-value inflates false positives several-fold. Both sequential procedures keep them "
          "near the 5% target; mSPRT buys unlimited looks with some power, O'Brien-Fleming keeps nearly full power with planned looks.",
          "", f"When mSPRT stopped on a real effect it used on average "
          f"{p['effect']['msprt_avg_sample_when_stopped']:,.0f} users instead of {p['fixed_sample_n']:,}.", ""]
    L += ["## 3. Multiple testing (20 metrics, 5 with a real effect, 1,000 simulations)", "",
          "| Correction | Family-wise error | False discovery rate | Power |", "|---|---|---|---|"]
    L += [f"| {k} | {v['family_wise_error']:.1%} | {v['false_discovery_rate']:.1%} | {v['power']:.1%} |"
          for k, v in r["multiple_testing"].items()]
    c = r["causal_recovery"]
    L += ["", "## 4. Causal effect recovery (simulated confounding, true ATE = 2.0, 20 seeds)", "",
          "| Estimator | Mean estimate | Bias | RMSE | 95% CI coverage |", "|---|---|---|---|---|",
          f"| Naive difference | {c['naive']['mean_estimate']:.2f} | {c['naive']['bias']:+.2f} | {c['naive']['rmse']:.2f} | – |",
          f"| Propensity score matching (DoWhy) | {c['psm']['mean_estimate']:.2f} | {c['psm']['bias']:+.2f} | {c['psm']['rmse']:.2f} | {c['psm']['ci_coverage']:.0%} |",
          f"| LinearDML (EconML) | {c['dml']['mean_estimate']:.2f} | {c['dml']['bias']:+.2f} | {c['dml']['rmse']:.2f} | {c['dml']['ci_coverage']:.0%} |",
          "", "Matching CIs come from a bootstrap, which is known to be conservative for nearest-neighbour matching "
          "(Abadie & Imbens, 2008).", "", f"Difference-in-differences (TWFE, true effect 5.0): mean estimate {c['did']['mean_estimate']:.2f}, "
          f"bias {c['did']['bias']:+.2f}, CI coverage {c['did']['ci_coverage']:.0%}.", ""]
    rd = r["real_data"]
    L += ["## 5. Real datasets", "", "**LaLonde (NSW treated vs CPS controls)** — experimental benchmark ATT ≈ $1,794.", "",
          f"- Naive difference: ${rd['lalonde']['naive']:,.0f}",
          f"- Propensity score matching ATT: ${rd['lalonde']['psm_att']:,.0f} (95% CI ${rd['lalonde']['psm_ci'][0]:,.0f} to ${rd['lalonde']['psm_ci'][1]:,.0f})",
          f"- LinearDML ATT: ${rd['lalonde']['dml_att']:,.0f}", "",
          "**California Proposition 99** (cigarette packs per capita, treatment from 1989)", "",
          f"- Synthetic control ATT 1989-2000: {rd['prop99']['synthetic_control_att']:.1f} packs ({rd['prop99']['relative']:.0%}), "
          f"pre-period RMSPE {rd['prop99']['pre_rmspe']:.2f}, placebo p = {rd['prop99']['placebo_p']:.3f}",
          f"- Naive DiD (TWFE): {rd['prop99']['did_twfe']:.1f}, but pre-trend test p = {rd['prop99']['did_pretrend_p']:.1g} "
          "— parallel trends fails, which is exactly why synthetic control is the right tool here.", ""]
    L += ["## 6. API latency (median of 3 calls, single process)", "", "| Endpoint | Seconds |", "|---|---|"]
    L += [f"| {k} | {v:.2f} |" for k, v in r["latency"].items()]
    (ROOT / "docs" / "results.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    for name, fn in [("power_calibration", power_calibration), ("peeking", peeking),
                     ("multiple_testing", multiple_testing), ("causal_recovery", causal_recovery),
                     ("real_data", real_data), ("latency", latency)]:
        t = time.time()
        results[name] = fn()
        print(f"{name}: {time.time() - t:.1f}s")
    (ROOT / "docs" / "results.json").write_text(json.dumps(results, indent=2))
    write_markdown(results)
    print("Wrote docs/results.md")
