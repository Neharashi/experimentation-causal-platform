import logging
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from scipy.optimize import minimize
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .common import histogram, is_binary, num, numeric, pct, pval, require_columns

logging.getLogger("dowhy").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", module="dowhy")
warnings.filterwarnings("ignore", module="econml")
warnings.filterwarnings("ignore", module="sklearn")


def _prep(df, treatment_col, outcome_col, covariates):
    if not covariates:
        raise ValueError("Select at least one covariate (confounder).")
    require_columns(df, treatment_col, outcome_col, *covariates)
    d = df[[treatment_col, outcome_col, *covariates]].dropna()
    t = numeric(d[treatment_col], treatment_col)
    if not is_binary(t):
        raise ValueError(f"Treatment column '{treatment_col}' must be binary 0/1.")
    X = pd.get_dummies(d[covariates], drop_first=True).astype(float)
    t, y = t.astype(int).to_numpy(), numeric(d[outcome_col], outcome_col).to_numpy(float)
    if t.sum() < 5 or (1 - t).sum() < 5:
        raise ValueError("Need at least 5 treated and 5 control units.")
    return t, y, X


def _ps_model():
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000, C=1e4))


def _propensity(X, t):
    clf = _ps_model().fit(X, t)
    return np.clip(clf.predict_proba(X)[:, 1], 1e-6, 1 - 1e-6)


def _smd(X, t, control_idx=None):
    xt = X[t == 1]
    xc = X[t == 0] if control_idx is None else X[t == 0].iloc[control_idx]
    pooled = np.sqrt((X[t == 1].var() + X[t == 0].var()) / 2).replace(0, 1)
    return (xt.mean() - xc.mean()) / pooled


def _match(ps, t, y, estimand):
    logit = np.log(ps / (1 - ps)).reshape(-1, 1)
    tr, co = np.nonzero(t == 1)[0], np.nonzero(t == 0)[0]
    nn_c = NearestNeighbors(n_neighbors=1).fit(logit[co])
    idx_c = nn_c.kneighbors(logit[tr], return_distance=False)[:, 0]
    att = float(np.mean(y[tr] - y[co][idx_c]))
    if estimand == "att":
        return att, idx_c
    nn_t = NearestNeighbors(n_neighbors=1).fit(logit[tr])
    idx_t = nn_t.kneighbors(logit[co], return_distance=False)[:, 0]
    atc = float(np.mean(y[tr][idx_t] - y[co]))
    return (att * len(tr) + atc * len(co)) / len(t), idx_c


def _bootstrap(ps, t, y, estimand, reps=200, seed=0):
    rng = np.random.default_rng(seed)
    tr, co = np.nonzero(t == 1)[0], np.nonzero(t == 0)[0]
    est = []
    for _ in range(reps):
        i = np.concatenate([rng.choice(tr, len(tr)), rng.choice(co, len(co))])
        est.append(_match(ps[i], t[i], y[i], estimand)[0])
    est = np.asarray(est)
    p = float(min(1.0, 2 * min((est <= 0).mean(), (est >= 0).mean())))
    return np.percentile(est, [2.5, 97.5]).tolist(), float(np.std(est, ddof=1)), p


def _dowhy_psm(X, t, y, estimand, refute):
    from dowhy import CausalModel

    names = [f"c{i}" for i in range(X.shape[1])]
    Z = X.to_numpy()
    data = pd.DataFrame((Z - Z.mean(0)) / np.where(Z.std(0) > 0, Z.std(0), 1), columns=names)
    data["T"], data["Y"] = t.astype(bool), y
    model = CausalModel(data=data, treatment="T", outcome="Y", common_causes=names)
    ident = model.identify_effect(proceed_when_unidentifiable=True)
    est = model.estimate_effect(ident, method_name="backdoor.propensity_score_matching", target_units=estimand,
                                method_params={"init_params": {"propensity_score_model": _ps_model()}})
    out = {"estimate": float(est.value), "refutations": []}
    if refute:
        for method, label, kw in [
            ("placebo_treatment_refuter", "Placebo treatment (should be ≈ 0)", {"placebo_type": "permute"}),
            ("random_common_cause", "Add random confounder (should be unchanged)", {}),
            ("data_subset_refuter", "Random 80% subset (should be unchanged)", {"subset_fraction": 0.8}),
        ]:
            r = model.refute_estimate(ident, est, method_name=method, num_simulations=10,
                                      random_seed=1, **kw)
            out["refutations"].append({"test": label, "original": float(est.value),
                                       "new_effect": float(np.mean(r.new_effect))})
    return out


AUTO_NUISANCE_MAX_ROWS = 5000


def dml_effects(t, y, X, modifier=None, alpha=0.05, nuisance=None, seed=0):
    from econml.dml import LinearDML

    nuisance = nuisance or ("auto" if len(t) <= AUTO_NUISANCE_MAX_ROWS else "boosting")
    if nuisance == "auto":
        model_y, model_t = "auto", "auto"
    else:
        model_y = HistGradientBoostingRegressor(max_iter=150, random_state=seed)
        model_t = HistGradientBoostingClassifier(max_iter=150, random_state=seed)
    est = LinearDML(model_y=model_y, model_t=model_t, discrete_treatment=True, cv=3, random_state=seed)
    est.fit(y, t, X=X.to_numpy())
    cate = est.effect(X.to_numpy())

    def summary(mask):
        s = est.effect_inference(X.to_numpy()[mask]).population_summary(alpha=alpha)
        lo, hi = s.conf_int_mean()
        return {"estimate": float(s.mean_point), "ci": [float(np.ravel(lo)[0]), float(np.ravel(hi)[0])]}

    out = {"nuisance_models": "EconML automatic model selection" if nuisance == "auto" else "Gradient boosting",
           "ate": summary(np.ones(len(t), bool)), "att": summary(t == 1),
           "cate_distribution": histogram({"cate": cate}, bins=30)}
    if modifier is not None:
        groups = []
        for label, mask in modifier:
            if mask.sum() >= 10:
                groups.append({"group": label, "n": int(mask.sum()), **summary(mask)})
        out["by_group"] = groups
    return out


def psm(df, treatment_col, outcome_col, covariates, estimand="att", refute=True, dml=True, alpha=0.05):
    estimand = estimand.lower()
    t, y, X = _prep(df, treatment_col, outcome_col, covariates)
    ps = _propensity(X, t)
    naive = float(y[t == 1].mean() - y[t == 0].mean())
    own, idx_c = _match(ps, t, y, estimand)
    ci, se, p_boot = _bootstrap(ps, t, y, estimand)
    dw = _dowhy_psm(X, t, y, estimand, refute)
    before, after = _smd(X, t), _smd(X, t, idx_c)
    balance = [{"covariate": c, "smd_before": float(before[c]), "smd_after": float(after[c])}
               for c in X.columns]
    overlap_lo, overlap_hi = max(ps[t == 1].min(), ps[t == 0].min()), min(ps[t == 1].max(), ps[t == 0].max())
    outside = float(np.mean((ps[t == 1] < overlap_lo) | (ps[t == 1] > overlap_hi)))
    result = {
        "method": "psm", "estimand": estimand.upper(), "treatment": treatment_col, "outcome": outcome_col,
        "n_treated": int(t.sum()), "n_control": int((1 - t).sum()),
        "naive_difference": naive, "estimate": dw["estimate"], "matching_estimate": own,
        "ci": ci, "se": se, "p_value": p_boot,
        "refutations": dw["refutations"], "balance": balance,
        "max_smd_after": float(after.abs().max()),
        "propensity_overlap": histogram({"treated": ps[t == 1], "control": ps[t == 0]}, bins=30),
        "warnings": [],
    }
    if result["max_smd_after"] > 0.1:
        result["warnings"].append("Some covariates still have |SMD| > 0.1 after matching; balance is imperfect.")
    if outside > 0.05:
        result["warnings"].append(f"{outside:.0%} of treated units fall outside the region of common support.")
    if dml:
        result["dml"] = dml_effects(t, y, X, alpha=alpha)
    sig = not (ci[0] <= 0 <= ci[1])
    result["conclusion"] = (
        f"A simple comparison suggests the treatment changes {outcome_col} by {num(naive)}, but treated and "
        f"control units differ in their covariates. After propensity score matching on "
        f"{len(covariates)} covariates, the estimated effect ({estimand.upper()}) is {num(dw['estimate'])} "
        f"(95% bootstrap CI {num(ci[0])} to {num(ci[1])}), which is "
        + ("statistically significant." if sig else "not statistically significant.")
        + (f" Double machine learning (EconML) gives a comparable {estimand.upper()} of "
           f"{num(result['dml'][estimand]['estimate'])}." if dml else "")
    )
    return result


def dml(df, treatment_col, outcome_col, covariates, modifier_col=None, alpha=0.05):
    t, y, X = _prep(df, treatment_col, outcome_col, covariates)
    modifier = None
    if modifier_col:
        require_columns(df, modifier_col)
        m = df.loc[df[[treatment_col, outcome_col, *covariates]].dropna().index, modifier_col]
        if pd.api.types.is_numeric_dtype(m) and m.nunique() > 8:
            bins = pd.qcut(m, 4, duplicates="drop")
            modifier = [(str(b), (bins == b).to_numpy()) for b in bins.cat.categories]
        else:
            modifier = [(str(v), (m == v).to_numpy()) for v in sorted(m.dropna().unique())]
    r = dml_effects(t, y, X, modifier, alpha)
    ate = r["ate"]
    sig = not (ate["ci"][0] <= 0 <= ate["ci"][1])
    conclusion = (
        f"Double machine learning (EconML LinearDML) estimates an average "
        f"effect of {num(ate['estimate'])} on {outcome_col} (95% CI {num(ate['ci'][0])} to {num(ate['ci'][1])}), "
        + ("which excludes zero." if sig else "which includes zero, so the effect is not distinguishable from none.")
        + f" The effect on the treated (ATT) is {num(r['att']['estimate'])}."
    )
    if r.get("by_group"):
        best = max(r["by_group"], key=lambda g: g["estimate"])
        worst = min(r["by_group"], key=lambda g: g["estimate"])
        conclusion += (f" Effects vary by {modifier_col}: largest for {best['group']} ({num(best['estimate'])}), "
                       f"smallest for {worst['group']} ({num(worst['estimate'])}).")
    return {"method": "dml", "treatment": treatment_col, "outcome": outcome_col,
            "naive_difference": float(y[t == 1].mean() - y[t == 0].mean()), **r,
            "modifier": modifier_col, "conclusion": conclusion, "warnings": []}


def did(df, outcome_col, treated_col, time_col, post_col=None, treatment_time=None, unit_col=None,
        alpha=0.05):
    require_columns(df, outcome_col, treated_col, time_col, post_col, unit_col)
    cols = [c for c in {outcome_col, treated_col, time_col, post_col, unit_col} if c]
    d = df[cols].dropna().copy()
    out = pd.DataFrame({"y": numeric(d[outcome_col], outcome_col),
                        "treated": numeric(d[treated_col], treated_col), "time": d[time_col]})
    if not is_binary(out["treated"]):
        raise ValueError(f"'{treated_col}' must be a binary 0/1 treated-group indicator.")
    if post_col:
        out["post"] = numeric(d[post_col], post_col)
    elif treatment_time is not None:
        out["post"] = (pd.to_numeric(out["time"]) >= float(treatment_time)).astype(int)
    else:
        raise ValueError("Provide either a post-period column or the treatment start time.")
    out["did"] = out["treated"] * out["post"]
    if unit_col:
        out["unit"] = d[unit_col].astype(str)
    if out["post"].nunique() < 2:
        raise ValueError("Data must contain both pre- and post-treatment periods.")

    n_times = out["time"].nunique()
    if unit_col and n_times > 2:
        formula, spec = "y ~ did + C(unit) + C(time)", "Two-way fixed effects (unit + time)"
    else:
        formula, spec = "y ~ treated + post + did", "Canonical 2×2 regression"
    cov = {"cov_type": "cluster", "cov_kwds": {"groups": pd.factorize(out["unit"])[0]}} if unit_col else {"cov_type": "HC1"}
    res = smf.ols(formula, data=out).fit(**cov)
    est, se, p = float(res.params["did"]), float(res.bse["did"]), float(res.pvalues["did"])
    ci = [float(x) for x in res.conf_int(alpha).loc["did"]]

    means = out.groupby(["treated", "post"])["y"].mean()
    table = {"treated_pre": float(means.loc[(1, 0)]), "treated_post": float(means.loc[(1, 1)]),
             "control_pre": float(means.loc[(0, 0)]), "control_post": float(means.loc[(0, 1)])}
    trend = out.groupby(["time", "treated"])["y"].mean().unstack()
    trends = [{"time": _jsonable(k), "treated": float(r.get(1, np.nan)), "control": float(r.get(0, np.nan))}
              for k, r in trend.iterrows()]

    event, pretrend_p = _event_study(out, unit_col, alpha) if 3 <= n_times <= 80 else ([], None)
    sig = p < alpha
    conclusion = (
        f"The treated group's {outcome_col} moved from {num(table['treated_pre'])} to {num(table['treated_post'])}, "
        f"while the control group moved from {num(table['control_pre'])} to {num(table['control_post'])}. "
        f"Netting out the common trend, the difference-in-differences estimate of the treatment effect is "
        f"{num(est)} (95% CI {num(ci[0])} to {num(ci[1])}, {pval(p)}), which is "
        + ("statistically significant." if sig else "not statistically significant.")
    )
    warnings = []
    if pretrend_p is not None:
        if pretrend_p < alpha:
            warnings.append(f"Pre-treatment trends differ (joint test {pval(pretrend_p)}): the parallel "
                            "trends assumption looks violated, so treat the estimate with caution.")
        else:
            conclusion += f" Pre-treatment trends are parallel (joint test {pval(pretrend_p)}), supporting the design."
    return {"method": "did", "specification": spec, "outcome": outcome_col, "estimate": est, "se": se,
            "p_value": p, "ci": ci, "significant": bool(sig), "means": table, "trends": trends,
            "event_study": event, "pretrend_p_value": pretrend_p, "n_obs": int(res.nobs),
            "conclusion": conclusion, "warnings": warnings}


def _event_study(out, unit_col, alpha):
    times = sorted(out["time"].unique())
    pre_times = sorted(out.loc[out["post"] == 0, "time"].unique())
    if not pre_times or out.groupby("time")["post"].nunique().max() > 1:
        return [], None
    ref = pre_times[-1]
    e = out.copy()
    names = []
    for i, tm in enumerate(times):
        if tm == ref:
            continue
        name = f"ev{i}"
        e[name] = ((e["time"] == tm) & (e["treated"] == 1)).astype(int)
        names.append((name, tm))
    fe = "C(unit)" if unit_col else "treated"
    res = smf.ols(f"y ~ {' + '.join(n for n, _ in names)} + {fe} + C(time)", data=e).fit(
        **({"cov_type": "cluster", "cov_kwds": {"groups": pd.factorize(e["unit"])[0]}} if unit_col else {"cov_type": "HC1"}))
    ci = res.conf_int(alpha)
    rows = [{"time": _jsonable(ref), "coef": 0.0, "ci": [0.0, 0.0], "post": False}]
    for n, tm in names:
        rows.append({"time": _jsonable(tm), "coef": float(res.params[n]),
                     "ci": [float(ci.loc[n, 0]), float(ci.loc[n, 1])], "post": bool(tm not in pre_times)})
    rows.sort(key=lambda r: r["time"])
    pre_names = [n for n, tm in names if tm in pre_times]
    pretrend_p = None
    if pre_names:
        R = np.zeros((len(pre_names), len(res.params)))
        for i, n in enumerate(pre_names):
            R[i, list(res.params.index).index(n)] = 1
        pretrend_p = float(res.wald_test(R, scalar=True).pvalue)
    return rows, pretrend_p


def _jsonable(v):
    return v.item() if hasattr(v, "item") else v


def _fit_weights(y1, Y0):
    k = Y0.shape[1]
    scale = np.std(y1) or 1.0
    y1s, Y0s = y1 / scale, Y0 / scale
    res = minimize(lambda w: np.sum((y1s - Y0s @ w) ** 2), np.full(k, 1 / k),
                   jac=lambda w: 2 * Y0s.T @ (Y0s @ w - y1s), method="SLSQP",
                   bounds=[(0, 1)] * k, constraints=({"type": "eq", "fun": lambda w: w.sum() - 1},),
                   options={"maxiter": 500, "ftol": 1e-10})
    w = np.clip(res.x, 0, None)
    return w / w.sum()


def _rmspe(gap):
    return float(np.sqrt(np.mean(gap ** 2)))


def synthetic_control(df, unit_col, time_col, outcome_col, treated_unit, treatment_time, placebo=True):
    require_columns(df, unit_col, time_col, outcome_col)
    d = df[[unit_col, time_col, outcome_col]].dropna().copy()
    d[unit_col] = d[unit_col].astype(str)
    d[time_col] = pd.to_numeric(d[time_col])
    piv = d.pivot_table(index=time_col, columns=unit_col, values=outcome_col).sort_index().dropna(axis=1)
    treated_unit = str(treated_unit)
    if treated_unit not in piv.columns:
        raise ValueError(f"Treated unit '{treated_unit}' not found (or has missing periods).")
    pre = (piv.index < float(treatment_time))
    if pre.sum() < 3 or (~pre).sum() < 1:
        raise ValueError("Need at least 3 pre-treatment periods and 1 post-treatment period.")
    donors = [c for c in piv.columns if c != treated_unit]
    if len(donors) < 2:
        raise ValueError("Need at least 2 donor (control) units.")

    def run(target, pool):
        y1, Y0 = piv[target].to_numpy(), piv[pool].to_numpy()
        w = _fit_weights(y1[pre], Y0[pre])
        synth = Y0 @ w
        gap = y1 - synth
        return w, synth, gap, _rmspe(gap[pre]), _rmspe(gap[~pre])

    w, synth, gap, pre_r, post_r = run(treated_unit, donors)
    att = float(gap[~pre].mean())
    rel = att / float(synth[~pre].mean()) if synth[~pre].mean() else None
    times = [_jsonable(t) for t in piv.index]
    series = [{"time": times[i], "actual": float(piv[treated_unit].iloc[i]), "synthetic": float(synth[i]),
               "gap": float(gap[i])} for i in range(len(times))]
    weights = sorted([{"unit": u, "weight": float(x)} for u, x in zip(donors, w) if x > 0.001],
                     key=lambda r: -r["weight"])
    result = {"method": "synthetic_control", "treated_unit": treated_unit, "treatment_time": treatment_time,
              "outcome": outcome_col, "att": att, "relative_effect": rel, "pre_rmspe": pre_r,
              "post_rmspe": post_r, "rmspe_ratio": post_r / pre_r if pre_r else None,
              "weights": weights, "series": series, "warnings": []}

    if placebo:
        ratios, gaps = [{"unit": treated_unit, "ratio": result["rmspe_ratio"], "treated": True}], {}
        for u in donors:
            pool = [c for c in donors if c != u]
            _, _, g, pr, po = run(u, pool)
            ratios.append({"unit": u, "ratio": po / pr if pr else 0.0, "treated": False})
            if pr <= 5 * pre_r:
                gaps[u] = g
        ratios.sort(key=lambda r: -r["ratio"])
        rank = next(i for i, r in enumerate(ratios) if r["treated"]) + 1
        result["placebo_p_value"] = rank / len(ratios)
        result["placebo_ratios"] = ratios
        result["placebo_gaps"] = [{"time": times[i], "treated": float(gap[i]),
                                   **{u: float(g[i]) for u, g in gaps.items()}} for i in range(len(times))]
        result["placebo_units"] = list(gaps)

    top = ", ".join(f"{r['unit']} ({r['weight']:.0%})" for r in weights[:4])
    direction = "lower" if att < 0 else "higher"
    conclusion = (
        f"We built a synthetic {treated_unit} from a weighted mix of control units ({top}) that tracks its "
        f"pre-{treatment_time} {outcome_col} closely (RMSPE {num(pre_r)}). After {treatment_time}, the actual "
        f"{outcome_col} was on average {num(abs(att))} {direction} than the synthetic counterfactual"
        + (f" ({pct(abs(rel))} {direction})" if rel is not None else "") + "."
    )
    if placebo:
        p = result["placebo_p_value"]
        conclusion += (f" In placebo tests on {len(ratios) - 1} control units, {treated_unit} ranks {rank} of "
                       f"{len(ratios)} by post/pre RMSPE ratio (permutation p = {p:.3f}), so the effect is "
                       + ("unlikely to be due to chance." if p <= 0.1 else "not clearly distinguishable from noise."))
    if pre_r > 0.1 * np.std(piv[treated_unit].to_numpy()[pre]) * 3:
        result["warnings"].append("Pre-treatment fit is loose; the synthetic control may be a poor counterfactual.")
    result["conclusion"] = conclusion
    return result
