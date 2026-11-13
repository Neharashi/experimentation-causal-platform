import math

import numpy as np
from statsmodels.stats.power import NormalIndPower, TTestIndPower
from statsmodels.stats.proportion import proportion_effectsize

from .common import num, pct


def _target(metric_type, baseline, mde, mde_type, std):
    delta = baseline * mde if mde_type == "relative" else mde
    if delta == 0:
        raise ValueError("Minimum detectable effect must be non-zero.")
    target = baseline + delta
    if metric_type == "proportion":
        if not 0 < baseline < 1 or not 0 < target < 1:
            raise ValueError("Baseline and target conversion rates must be between 0 and 1.")
        return abs(proportion_effectsize(target, baseline)), target
    if not std or std <= 0:
        raise ValueError("Standard deviation must be positive for a mean metric.")
    return abs(delta) / std, target


def _solver(metric_type):
    return NormalIndPower() if metric_type == "proportion" else TTestIndPower()


def _es_to_target(metric_type, baseline, es, std):
    if metric_type == "proportion":
        phi = 2 * math.asin(math.sqrt(baseline)) + es
        return math.sin(min(phi, math.pi) / 2) ** 2
    return baseline + es * std


def sample_size(metric_type="proportion", baseline=0.1, mde=0.1, mde_type="relative", std=None,
                alpha=0.05, power=0.8, ratio=1.0, alternative="two-sided", daily_traffic=None):
    es, target = _target(metric_type, baseline, mde, mde_type, std)
    solver = _solver(metric_type)
    n1 = math.ceil(solver.solve_power(effect_size=es, alpha=alpha, power=power, ratio=ratio,
                                      alternative=alternative))
    n2 = math.ceil(n1 * ratio)
    ns = np.unique(np.linspace(max(5, n1 * 0.05), n1 * 2.5, 50).astype(int))
    curve = [{"n_per_group": int(n), "power": float(solver.power(es, n, alpha, ratio=ratio,
                                                                 alternative=alternative))} for n in ns]
    days = math.ceil((n1 + n2) / daily_traffic) if daily_traffic else None
    fmt = pct if metric_type == "proportion" else num
    conclusion = (
        f"To detect a change from {fmt(baseline)} to {fmt(target)} with {power:.0%} power at "
        f"a {alpha:.0%} significance level, you need {n1:,} users in control and {n2:,} in treatment "
        f"({n1 + n2:,} total)."
    )
    if days:
        conclusion += f" At {daily_traffic:,} users per day the test should run about {days} days."
        if days < 7:
            conclusion += " Run it for at least one full week to cover weekly seasonality."
    return {
        "n_control": n1, "n_treatment": n2, "total": n1 + n2,
        "effect_size": float(es), "baseline": baseline, "target": float(target),
        "duration_days": days, "power_curve": curve, "conclusion": conclusion,
    }


def achieved_power(metric_type="proportion", baseline=0.1, mde=0.1, mde_type="relative", std=None,
                   alpha=0.05, n_per_group=1000, ratio=1.0, alternative="two-sided"):
    es, target = _target(metric_type, baseline, mde, mde_type, std)
    solver = _solver(metric_type)
    pw = float(solver.power(es, n_per_group, alpha, ratio=ratio, alternative=alternative))
    min_es = float(solver.solve_power(nobs1=n_per_group, alpha=alpha, power=0.8, ratio=ratio,
                                      alternative=alternative))
    mde_target = _es_to_target(metric_type, baseline, min_es, std)
    fmt = pct if metric_type == "proportion" else num
    verdict = "adequately powered" if pw >= 0.8 else "underpowered"
    conclusion = (
        f"With {n_per_group:,} users per group the test has {pw:.0%} power to detect a move from "
        f"{fmt(baseline)} to {fmt(target)}, so it is {verdict}. The smallest effect it can detect "
        f"with 80% power is {fmt(baseline)} → {fmt(mde_target)}."
    )
    return {"power": pw, "effect_size": float(es), "min_detectable_target": float(mde_target),
            "min_detectable_relative": float(mde_target / baseline - 1) if baseline else None,
            "conclusion": conclusion}
