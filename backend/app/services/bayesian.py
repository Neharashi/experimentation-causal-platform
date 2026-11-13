import logging

import numpy as np
import pymc as pm

from .common import histogram, is_binary, num, pct, split_groups

logging.getLogger("pymc").setLevel(logging.ERROR)


def _rhat(x: np.ndarray) -> float:
    """Split R-hat for a (chains, draws) array."""
    n = x.shape[1] // 2
    chains = np.concatenate([x[:, :n], x[:, n:2 * n]])
    w = chains.var(axis=1, ddof=1).mean()
    b = n * chains.mean(axis=1).var(ddof=1)
    return float(np.sqrt(((n - 1) / n * w + b / n) / w)) if w > 0 else 1.0


def _hdi(x: np.ndarray, prob: float = 0.95) -> list[float]:
    s = np.sort(x)
    k = int(np.floor(prob * len(s)))
    widths = s[k:] - s[: len(s) - k]
    i = int(np.argmin(widths))
    return [float(s[i]), float(s[i + k])]


def _sample(model, draws, seed):
    with model:
        idata = pm.sample(draws=draws, tune=min(1000, draws), chains=2, cores=1,
                          random_seed=seed, progressbar=False, compute_convergence_checks=False)
    return idata.posterior


def _binary_model(a, b, prior_alpha, prior_beta):
    with pm.Model() as model:
        p = pm.Beta("p", alpha=prior_alpha, beta=prior_beta, shape=2)
        pm.Binomial("obs", n=[len(a), len(b)], p=p, observed=[a.sum(), b.sum()])
    return model, "p"


def _continuous_model(a, b):
    pooled = np.concatenate([a, b])
    m, s = pooled.mean(), pooled.std() or 1.0
    with pm.Model() as model:
        mu = pm.Normal("mu", mu=m, sigma=10 * s, shape=2)
        sigma = pm.HalfNormal("sigma", sigma=5 * s, shape=2)
        pm.Normal("obs_a", mu=mu[0], sigma=sigma[0], observed=a)
        pm.Normal("obs_b", mu=mu[1], sigma=sigma[1], observed=b)
    return model, "mu"


def bayesian_ab(df, group_col, metric_col, control=None, treatment=None, draws=2000,
                prior_alpha=1.0, prior_beta=1.0, loss_threshold=0.01, credible=0.95, seed=42):
    a, b, control, treatment = split_groups(df, group_col, metric_col, control, treatment)
    binary = is_binary(a) and is_binary(b)
    model, var = _binary_model(a, b, prior_alpha, prior_beta) if binary else _continuous_model(a, b)
    post = _sample(model, draws, seed)[var].values
    rhat = max(_rhat(post[..., 0]), _rhat(post[..., 1]))
    sa, sb = post[..., 0].ravel(), post[..., 1].ravel()
    diff = sb - sa
    lift = diff / np.abs(sa) if np.all(sa != 0) else diff
    prob_b = float((sb > sa).mean())
    loss_b = float(np.maximum(sa - sb, 0).mean())
    loss_a = float(np.maximum(sb - sa, 0).mean())
    threshold = loss_threshold * abs(sa.mean())
    lift_hdi = _hdi(lift, credible)
    fmt = (lambda v: pct(v, 2)) if binary else num
    if prob_b >= 0.95 and loss_b < threshold:
        decision = f"Ship '{treatment}'"
    elif prob_b <= 0.05 and loss_a < threshold:
        decision = f"Keep '{control}'"
    else:
        decision = "Keep collecting data"
    conclusion = (
        f"There is a {prob_b:.1%} probability that '{treatment}' beats '{control}' on {metric_col}. "
        f"The expected lift is {pct(float(lift.mean()))}, with a {credible:.0%} credible interval of "
        f"{pct(lift_hdi[0])} to {pct(lift_hdi[1])}. If we ship '{treatment}' and it is actually worse, "
        f"the expected loss is {fmt(loss_b)} per user. Recommendation: {decision}."
    )
    warnings = []
    if rhat > 1.01:
        warnings.append(f"Sampler convergence is weak (R-hat = {rhat:.3f}); increase draws.")
    return {
        "method": "bayesian", "model": "Beta-Binomial" if binary else "Normal (unequal variance)",
        "metric": metric_col, "control": control, "treatment": treatment,
        "prob_treatment_better": prob_b, "expected_loss_treatment": loss_b,
        "expected_loss_control": loss_a, "loss_threshold": threshold,
        "posterior_mean": {control: float(sa.mean()), treatment: float(sb.mean())},
        "posterior_hdi": {control: _hdi(sa, credible), treatment: _hdi(sb, credible)},
        "lift_mean": float(lift.mean()), "lift_hdi": lift_hdi, "decision": decision,
        "posterior_density": histogram({control: sa, treatment: sb}, bins=40),
        "lift_density": histogram({"lift": lift}, bins=40),
        "diagnostics": {"r_hat": rhat, "draws": int(sa.size), "chains": int(post.shape[0])},
        "conclusion": conclusion, "warnings": warnings,
    }
