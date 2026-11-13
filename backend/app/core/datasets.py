from pathlib import Path

import pandas as pd

from ..services.simulate import simulate_ab, simulate_did, simulate_observational

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LALONDE_COVS = ["age", "age2", "educ", "educ2", "black", "hisp", "marr", "nodegree", "re74", "re75", "u74", "u75"]


def _lalonde(name):
    df = pd.read_csv(DATA_DIR / name)
    df["age2"], df["educ2"] = df["age"] ** 2, df["educ"] ** 2
    df["u74"], df["u75"] = (df["re74"] == 0).astype(int), (df["re75"] == 0).astype(int)
    return df


SAMPLES = {
    "simulated_ab": {
        "title": "Simulated A/B test (e-commerce)",
        "description": "40,000 users over 14 days. True +10% lift in conversion and +5% revenue per converter; "
                       "time_on_page, pages_viewed and clicked_banner have no real effect.",
        "loader": lambda: simulate_ab(),
        "methods": ["chisquare", "ttest", "multi_metric", "sequential", "bayesian"],
        "defaults": {"group_col": "group", "metric_col": "converted", "time_col": "day", "ttest:metric_col": "revenue",
                     "metric_cols": ["converted", "revenue", "time_on_page", "pages_viewed", "clicked_banner"]},
    },
    "lalonde_experimental": {
        "title": "LaLonde NSW job training (randomized)",
        "description": "445 men randomized into the National Supported Work program. Benchmark effect on 1978 "
                       "earnings ≈ $1,794.",
        "loader": lambda: _lalonde("lalonde_experimental.csv"),
        "methods": ["ttest", "bayesian"],
        "defaults": {"group_col": "treat", "metric_col": "re78"},
    },
    "lalonde_observational": {
        "title": "LaLonde NSW treated + CPS controls (observational)",
        "description": "185 NSW participants vs 15,992 non-randomized CPS survey respondents. The naive "
                       "difference is badly biased; matching should move it toward the $1,794 benchmark.",
        "loader": lambda: _lalonde("lalonde_observational.csv"),
        "methods": ["psm", "dml"],
        "defaults": {"treatment_col": "treat", "outcome_col": "re78", "covariates": LALONDE_COVS,
                     "modifier_col": "educ"},
    },
    "prop99": {
        "title": "California Proposition 99 (tobacco tax)",
        "description": "Per-capita cigarette sales for 39 US states, 1970-2000. California's tobacco control "
                       "program started in 1989.",
        "loader": lambda: pd.read_csv(DATA_DIR / "prop99.csv"),
        "methods": ["synthetic_control", "did"],
        "defaults": {"unit_col": "state", "time_col": "year", "outcome_col": "cigsale",
                     "treated_unit": "California", "treatment_time": 1989, "treated_col": "california"},
    },
    "simulated_did": {
        "title": "Simulated panel for difference-in-differences",
        "description": "60 units × 12 periods, half treated from period 8 with a true effect of +5.",
        "loader": lambda: simulate_did(),
        "methods": ["did", "synthetic_control"],
        "defaults": {"outcome_col": "outcome", "treated_col": "treated", "time_col": "period",
                     "post_col": "post", "unit_col": "unit", "treatment_time": 8, "treated_unit": "0"},
    },
    "simulated_observational": {
        "title": "Simulated confounded observational data",
        "description": "4,000 units where x1, x2, x3 drive both treatment and outcome. True effect = 2.0.",
        "loader": lambda: simulate_observational(),
        "methods": ["psm", "dml"],
        "defaults": {"treatment_col": "treatment", "outcome_col": "outcome", "covariates": ["x1", "x2", "x3"],
                     "modifier_col": "x3"},
    },
}


def list_samples():
    return [{"key": k, **{f: v[f] for f in ("title", "description", "methods", "defaults")}}
            for k, v in SAMPLES.items()]


def load_sample(key: str) -> pd.DataFrame:
    if key not in SAMPLES:
        raise ValueError(f"Unknown sample dataset '{key}'.")
    return SAMPLES[key]["loader"]()
