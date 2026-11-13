import numpy as np
import pandas as pd


def simulate_ab(n_per_group=20000, baseline_rate=0.10, relative_lift=0.10, revenue_lift=0.05,
                n_days=14, seed=42) -> pd.DataFrame:
    """A/B test with several metrics: some have a true effect, some do not."""
    rng = np.random.default_rng(seed)
    n = 2 * n_per_group
    group = np.repeat(["control", "treatment"], n_per_group)
    is_t = group == "treatment"
    p = np.where(is_t, baseline_rate * (1 + relative_lift), baseline_rate)
    converted = rng.binomial(1, p)
    revenue = converted * rng.lognormal(np.log(40), 0.6, n) * np.where(is_t, 1 + revenue_lift, 1)
    df = pd.DataFrame({
        "user_id": np.arange(1, n + 1),
        "group": group,
        "day": rng.integers(1, n_days + 1, n),
        "converted": converted,
        "revenue": revenue.round(2),
        "time_on_page": rng.normal(120, 40, n).clip(0).round(1),
        "pages_viewed": rng.poisson(4, n),
        "clicked_banner": rng.binomial(1, 0.05, n),
    })
    df = df.sample(frac=1, random_state=seed).sort_values("day", kind="stable")
    return df.reset_index(drop=True)


def simulate_did(n_units=60, n_periods=12, treatment_period=8, effect=5.0, seed=7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    unit = np.repeat(np.arange(n_units), n_periods)
    period = np.tile(np.arange(1, n_periods + 1), n_units)
    treated = (unit < n_units // 2).astype(int)
    unit_fe = rng.normal(0, 3, n_units)[unit] + 4 * treated
    trend = 1.5 * period
    post = (period >= treatment_period).astype(int)
    y = 50 + unit_fe + trend + effect * treated * post + rng.normal(0, 2, len(unit))
    return pd.DataFrame({"unit": unit, "period": period, "treated": treated, "post": post,
                         "outcome": y.round(3)})


def simulate_observational(n=4000, ate=2.0, seed=11) -> pd.DataFrame:
    """Confounded treatment: x1/x2 drive both treatment and outcome."""
    rng = np.random.default_rng(seed)
    x1, x2 = rng.normal(size=n), rng.normal(size=n)
    x3 = rng.binomial(1, 0.4, n)
    logit = -0.3 + 1.2 * x1 - 0.8 * x2 + 0.5 * x3
    t = rng.binomial(1, 1 / (1 + np.exp(-logit)))
    y = 1 + ate * t + 3 * x1 + 2 * x2 + 1.5 * x3 + rng.normal(0, 1, n)
    return pd.DataFrame({"treatment": t, "x1": x1, "x2": x2, "x3": x3, "outcome": y})
