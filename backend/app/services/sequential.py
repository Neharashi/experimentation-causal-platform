from functools import lru_cache

import numpy as np
from scipy import stats

from .common import num, numeric, require_columns, resolve_groups


def _cumulative(df, group_col, metric_col, control, treatment, time_col):
    require_columns(df, group_col, metric_col, time_col)
    control, treatment = resolve_groups(df, group_col, control, treatment)
    cols = [group_col, metric_col] + ([time_col] if time_col else [])
    d = df[cols].dropna()
    if time_col:
        d = d.sort_values(time_col, kind="stable")
    g = d[group_col].astype(str)
    d = d[g.isin([control, treatment])]
    is_b = (d[group_col].astype(str) == treatment).to_numpy()
    y = numeric(d[metric_col], metric_col).to_numpy(float)
    ya, yb = np.where(is_b, 0, y), np.where(is_b, y, 0)
    c = {
        "na": np.cumsum(~is_b), "nb": np.cumsum(is_b),
        "sa": np.cumsum(ya), "sb": np.cumsum(yb),
        "qa": np.cumsum(ya ** 2), "qb": np.cumsum(yb ** 2),
    }
    return c, control, treatment


def _stats_at(c, idx):
    na, nb = c["na"][idx].astype(float), c["nb"][idx].astype(float)
    ma, mb = c["sa"][idx] / na, c["sb"][idx] / nb
    va = np.maximum((c["qa"][idx] - na * ma ** 2) / (na - 1), 1e-12)
    vb = np.maximum((c["qb"][idx] - nb * mb ** 2) / (nb - 1), 1e-12)
    return na, nb, ma, mb, mb - ma, va / na + vb / nb


def _look_indices(c, looks, min_per_group=20):
    ok = np.nonzero((c["na"] >= min_per_group) & (c["nb"] >= min_per_group))[0]
    if len(ok) == 0:
        raise ValueError(f"Need at least {min_per_group} observations per group.")
    return np.unique(np.linspace(ok[0], len(c["na"]) - 1, looks).astype(int))


def msprt(df, group_col, metric_col, control=None, treatment=None, time_col=None, alpha=0.05,
          tau=None, looks=50):
    """Mixture SPRT (Johari et al., 2017): always-valid p-values for a difference in means."""
    c, control, treatment = _cumulative(df, group_col, metric_col, control, treatment, time_col)
    idx = _look_indices(c, looks)
    na, nb, ma, mb, diff, V = _stats_at(c, idx)
    if tau is None:
        tau = 0.1 * abs(ma[-1]) if abs(ma[-1]) > 1e-9 else 0.1 * np.sqrt(V[-1] * na[-1])
    tau2 = tau ** 2
    log_lam = 0.5 * np.log(V / (V + tau2)) + diff ** 2 * tau2 / (2 * V * (V + tau2))
    p_av = np.minimum.accumulate(np.minimum(1.0, np.exp(-log_lam)))
    p_naive = 2 * stats.norm.sf(np.abs(diff) / np.sqrt(V))
    ci_half = np.sqrt((V + tau2) / tau2 * (V * (2 * np.log(1 / alpha) + np.log((V + tau2) / V))))
    rows = [{"look": i + 1, "n": int(na[i] + nb[i]), "control_mean": float(ma[i]),
             "treatment_mean": float(mb[i]), "diff": float(diff[i]),
             "ci": [float(diff[i] - ci_half[i]), float(diff[i] + ci_half[i])],
             "p_always_valid": float(p_av[i]), "p_naive": float(p_naive[i])} for i in range(len(idx))]
    stop = next((r for r in rows if r["p_always_valid"] < alpha), None)
    naive_stop = next((r for r in rows if r["p_naive"] < alpha), None)
    final = rows[-1]
    if stop:
        direction = "higher" if stop["diff"] > 0 else "lower"
        conclusion = (f"Safe to stop: after {stop['n']:,} observations (look {stop['look']} of {len(rows)}) "
                      f"the always-valid p-value fell below {alpha}. '{treatment}' has a {direction} "
                      f"{metric_col} than '{control}' (difference {num(stop['diff'])}). This conclusion "
                      "stays valid even though results were checked repeatedly.")
    else:
        conclusion = (f"Not conclusive yet: after {final['n']:,} observations the always-valid p-value is "
                      f"{final['p_always_valid']:.3f}. Keep the experiment running; peeking at this "
                      "dashboard does not inflate the false-positive rate.")
    if naive_stop and not stop:
        conclusion += (f" Note: a naive p-value checked at every look would have (wrongly) declared "
                       f"significance at look {naive_stop['look']} — exactly the peeking trap this method avoids.")
    return {"method": "sequential", "procedure": "mSPRT (always-valid p-values)", "metric": metric_col,
            "control": control, "treatment": treatment, "alpha": alpha, "tau": float(tau),
            "looks": rows, "stopped": stop is not None, "stop_look": stop["look"] if stop else None,
            "stop_n": stop["n"] if stop else None, "naive_stop_look": naive_stop["look"] if naive_stop else None,
            "conclusion": conclusion, "warnings": []}


@lru_cache(maxsize=64)
def obf_constant(k: int, alpha: float, sims: int = 200_000) -> float:
    """O'Brien-Fleming constant c with boundaries c*sqrt(K/k), found by Monte Carlo."""
    rng = np.random.default_rng(2024)
    s = np.cumsum(rng.standard_normal((sims, k)), axis=1)
    return float(np.quantile(np.abs(s).max(axis=1) / np.sqrt(k), 1 - alpha))


def group_sequential(df, group_col, metric_col, control=None, treatment=None, time_col=None,
                     alpha=0.05, looks=5):
    if not 2 <= looks <= 20:
        raise ValueError("Group sequential design supports 2 to 20 looks.")
    c, control, treatment = _cumulative(df, group_col, metric_col, control, treatment, time_col)
    n = len(c["na"])
    idx = np.array([int(n * (k + 1) / looks) - 1 for k in range(looks)])
    if c["na"][idx[0]] < 10 or c["nb"][idx[0]] < 10:
        raise ValueError("Too few observations for the first interim look; use fewer looks.")
    na, nb, ma, mb, diff, V = _stats_at(c, idx)
    z = diff / np.sqrt(V)
    const = obf_constant(looks, alpha)
    bounds = const * np.sqrt(looks / np.arange(1, looks + 1))
    rows = [{"look": i + 1, "n": int(na[i] + nb[i]), "info_fraction": (i + 1) / looks,
             "diff": float(diff[i]), "z": float(z[i]), "boundary": float(bounds[i]),
             "nominal_alpha": float(2 * stats.norm.sf(bounds[i])),
             "p_naive": float(2 * stats.norm.sf(abs(z[i])))} for i in range(looks)]
    stop = next((r for r in rows if abs(r["z"]) >= r["boundary"]), None)
    if stop:
        direction = "higher" if stop["diff"] > 0 else "lower"
        conclusion = (f"The O'Brien-Fleming boundary was crossed at interim look {stop['look']} of {looks} "
                      f"({stop['n']:,} observations, |z| = {abs(stop['z']):.2f} ≥ {stop['boundary']:.2f}). "
                      f"'{treatment}' has a {direction} {metric_col}; the experiment can stop early with "
                      f"overall false-positive rate held at {alpha:.0%}.")
    else:
        conclusion = (f"No boundary was crossed across {looks} planned looks, so there is no significant "
                      f"difference at the {alpha:.0%} level after accounting for interim analyses.")
    return {"method": "sequential", "procedure": "Group sequential (O'Brien-Fleming)", "metric": metric_col,
            "control": control, "treatment": treatment, "alpha": alpha, "obf_constant": const,
            "looks": rows, "stopped": stop is not None, "stop_look": stop["look"] if stop else None,
            "stop_n": stop["n"] if stop else None, "conclusion": conclusion, "warnings": []}
