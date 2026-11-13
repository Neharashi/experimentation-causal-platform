import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import confint_proportions_2indep, proportion_confint

from .common import histogram, is_binary, num, pct, pval, require_columns, resolve_groups, split_groups

SCIPY_ALT = {"two-sided": "two-sided", "larger": "greater", "smaller": "less"}


def srm_check(n_a: int, n_b: int, expected_ratio: float = 1.0) -> dict:
    total = n_a + n_b
    expected = [total / (1 + expected_ratio), total * expected_ratio / (1 + expected_ratio)]
    p = float(stats.chisquare([n_a, n_b], expected).pvalue)
    return {"p_value": p, "mismatch": p < 0.001}


def _welch(a, b, alpha, alternative):
    res = stats.ttest_ind(b, a, equal_var=False, alternative=SCIPY_ALT[alternative])
    ci = res.confidence_interval(1 - alpha)
    diff = b.mean() - a.mean()
    pooled_sd = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    return {
        "statistic": float(res.statistic), "p_value": float(res.pvalue), "df": float(res.df),
        "diff": float(diff), "ci": [float(ci.low), float(ci.high)],
        "relative_lift": float(diff / a.mean()) if a.mean() else None,
        "cohens_d": float(diff / pooled_sd) if pooled_sd else 0.0,
    }


def _two_prop(a, b, alpha):
    xa, xb, na, nb = a.sum(), b.sum(), len(a), len(b)
    table = np.array([[xa, na - xa], [xb, nb - xb]])
    chi2, p, dof, _ = stats.chi2_contingency(table, correction=False)
    low, high = confint_proportions_2indep(xb, nb, xa, na, method="newcomb", alpha=alpha)
    pa, pb = xa / na, xb / nb
    return {
        "statistic": float(chi2), "p_value": float(p), "dof": int(dof),
        "diff": float(pb - pa), "ci": [float(low), float(high)],
        "relative_lift": float(pb / pa - 1) if pa else None,
        "contingency_table": table.astype(int).tolist(),
    }


def _group_stats(name, x, alpha, binary):
    if binary:
        lo, hi = proportion_confint(x.sum(), len(x), alpha=alpha, method="wilson")
    else:
        half = stats.t.ppf(1 - alpha / 2, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
        lo, hi = x.mean() - half, x.mean() + half
    return {"group": name, "n": int(len(x)), "mean": float(x.mean()),
            "std": float(x.std(ddof=1)), "ci": [float(lo), float(hi)]}


def ttest(df, group_col, metric_col, control=None, treatment=None, alpha=0.05,
          alternative="two-sided"):
    a, b, control, treatment = split_groups(df, group_col, metric_col, control, treatment)
    r = _welch(a, b, alpha, alternative)
    sig = r["p_value"] < alpha
    srm = srm_check(len(a), len(b))
    lift = f" ({pct(r['relative_lift'])} relative)" if r["relative_lift"] is not None else ""
    conclusion = (
        f"The average {metric_col} is {num(b.mean())} in '{treatment}' vs {num(a.mean())} in "
        f"'{control}', a difference of {num(r['diff'])}{lift}. "
        + (f"This difference is statistically significant ({pval(r['p_value'])}); the true "
           f"difference is likely between {num(r['ci'][0])} and {num(r['ci'][1])}."
           if sig else
           f"This is not statistically significant ({pval(r['p_value'])}), so the data are "
           f"consistent with no real difference (CI {num(r['ci'][0])} to {num(r['ci'][1])}).")
    )
    warnings = _warnings(srm, a, b)
    return {
        "method": "ttest", "test": "Welch's two-sample t-test", "metric": metric_col,
        "control": control, "treatment": treatment, "alpha": alpha, "significant": bool(sig),
        **r, "groups": [_group_stats(control, a, alpha, False), _group_stats(treatment, b, alpha, False)],
        "srm": srm, "distribution": histogram({control: a, treatment: b}),
        "conclusion": conclusion, "warnings": warnings,
    }


def chisquare(df, group_col, metric_col, control=None, treatment=None, alpha=0.05):
    a, b, control, treatment = split_groups(df, group_col, metric_col, control, treatment)
    if not (is_binary(a) and is_binary(b)):
        raise ValueError(f"Chi-square needs a binary 0/1 metric; '{metric_col}' is not binary.")
    r = _two_prop(a, b, alpha)
    sig = r["p_value"] < alpha
    srm = srm_check(len(a), len(b))
    conclusion = (
        f"The {metric_col} rate is {pct(b.mean(), 2)} in '{treatment}' vs {pct(a.mean(), 2)} in "
        f"'{control}' ({pct(r['relative_lift'])} relative change). "
        + (f"This is statistically significant ({pval(r['p_value'])}); the true difference is "
           f"likely between {pct(r['ci'][0], 2)} and {pct(r['ci'][1], 2)} percentage points."
           if sig else
           f"This is not statistically significant ({pval(r['p_value'])}); we cannot rule out "
           f"that the variants perform the same.")
    )
    return {
        "method": "chisquare", "test": "Pearson chi-square test of independence",
        "metric": metric_col, "control": control, "treatment": treatment, "alpha": alpha,
        "significant": bool(sig), **r,
        "groups": [_group_stats(control, a, alpha, True), _group_stats(treatment, b, alpha, True)],
        "srm": srm, "conclusion": conclusion, "warnings": _warnings(srm, a, b),
    }


def _warnings(srm, a, b):
    w = []
    if srm["mismatch"]:
        w.append(f"Sample ratio mismatch detected (p = {srm['p_value']:.2g}): group sizes differ more "
                 "than chance allows. Check assignment/logging before trusting results.")
    if min(len(a), len(b)) < 30:
        w.append("Very small groups: normal approximations may be unreliable.")
    return w


def correct_pvalues(p_values, alpha=0.05, method="fdr_bh"):
    p = np.asarray(p_values, dtype=float)
    if p.size == 0 or np.any((p < 0) | (p > 1)):
        raise ValueError("Provide p-values between 0 and 1.")
    out = {}
    for m in ("bonferroni", "fdr_bh"):
        reject, adj, _, _ = multipletests(p, alpha=alpha, method=m)
        out[m] = {"adjusted": adj.tolist(), "reject": reject.tolist()}
    return {"raw": p.tolist(), "selected": method, **out,
            "n_significant_raw": int((p < alpha).sum()),
            "n_significant_bonferroni": int(sum(out["bonferroni"]["reject"])),
            "n_significant_fdr_bh": int(sum(out["fdr_bh"]["reject"]))}


def multi_metric(df, group_col, metric_cols, control=None, treatment=None, alpha=0.05,
                 correction="fdr_bh"):
    if not metric_cols:
        raise ValueError("Select at least one metric.")
    require_columns(df, group_col, *metric_cols)
    control, treatment = resolve_groups(df, group_col, control, treatment)
    rows = []
    for m in metric_cols:
        a, b, _, _ = split_groups(df, group_col, m, control, treatment)
        binary = is_binary(a) and is_binary(b)
        r = _two_prop(a, b, alpha) if binary else _welch(a, b, alpha, "two-sided")
        rows.append({"metric": m, "test": "chi-square" if binary else "Welch t-test",
                     "control_mean": float(a.mean()), "treatment_mean": float(b.mean()),
                     "diff": r["diff"], "relative_lift": r["relative_lift"], "p_value": r["p_value"]})
    corr = correct_pvalues([r["p_value"] for r in rows], alpha, correction)
    for i, r in enumerate(rows):
        r["p_bonferroni"] = corr["bonferroni"]["adjusted"][i]
        r["p_fdr_bh"] = corr["fdr_bh"]["adjusted"][i]
        r["significant_raw"] = r["p_value"] < alpha
        r["significant"] = bool(corr[correction]["reject"][i])
    label = "Bonferroni" if correction == "bonferroni" else "Benjamini-Hochberg"
    winners = [r["metric"] for r in rows if r["significant"]]
    lost = [r["metric"] for r in rows if r["significant_raw"] and not r["significant"]]
    conclusion = (
        f"We tested {len(rows)} metrics. Without correction {corr['n_significant_raw']} look significant; "
        f"after {label} correction {len(winners)} remain"
        + (f": {', '.join(winners)}." if winners else ".")
    )
    if lost:
        conclusion += (f" {', '.join(lost)} looked significant only by chance-level evidence and "
                       "should not be reported as wins.")
    return {"method": "multi_metric", "control": control, "treatment": treatment, "alpha": alpha,
            "correction": correction, "results": rows, "summary": corr, "conclusion": conclusion,
            "warnings": []}
