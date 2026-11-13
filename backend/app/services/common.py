import numpy as np
import pandas as pd


def require_columns(df: pd.DataFrame, *cols: str) -> None:
    missing = [c for c in cols if c and c not in df.columns]
    if missing:
        raise ValueError(f"Column(s) not found in dataset: {', '.join(missing)}")


def numeric(series: pd.Series, name: str) -> pd.Series:
    out = pd.to_numeric(series, errors="coerce")
    if out.notna().sum() == 0:
        raise ValueError(f"Column '{name}' has no numeric values.")
    return out


def is_binary(values) -> bool:
    uniq = pd.Series(values).dropna().unique()
    return len(uniq) <= 2 and set(np.asarray(uniq, dtype=float)).issubset({0.0, 1.0})


def resolve_groups(df, group_col, control=None, treatment=None):
    labels = [str(v) for v in df[group_col].dropna().unique()]
    if control is None or treatment is None:
        if len(labels) != 2:
            raise ValueError(
                f"Column '{group_col}' has {len(labels)} groups; specify control and treatment labels."
            )
        labels.sort(key=lambda x: (not any(k in x.lower() for k in ("control", "gate_30")), x))
        control, treatment = control or labels[0], treatment or labels[1]
    for g in (control, treatment):
        if str(g) not in labels:
            raise ValueError(f"Group '{g}' not found in column '{group_col}'. Found: {labels[:10]}")
    return str(control), str(treatment)


def split_groups(df, group_col, metric_col, control=None, treatment=None):
    require_columns(df, group_col, metric_col)
    control, treatment = resolve_groups(df, group_col, control, treatment)
    g = df[group_col].astype(str)
    y = numeric(df[metric_col], metric_col)
    a = y[g == control].dropna().to_numpy(dtype=float)
    b = y[g == treatment].dropna().to_numpy(dtype=float)
    if len(a) < 2 or len(b) < 2:
        raise ValueError("Each group needs at least 2 observations.")
    return a, b, control, treatment


def histogram(groups: dict, bins: int = 30) -> list[dict]:
    values = np.concatenate([np.asarray(v, float) for v in groups.values()])
    lo, hi = np.percentile(values, [0.5, 99.5])
    if lo == hi:
        hi = lo + 1
    edges = np.linspace(lo, hi, bins + 1)
    rows = [{"x": float((edges[i] + edges[i + 1]) / 2)} for i in range(bins)]
    for name, v in groups.items():
        counts, _ = np.histogram(np.clip(v, lo, hi), bins=edges, density=True)
        for i, c in enumerate(counts):
            rows[i][name] = float(c)
    return rows


def pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f}%"


def num(x: float, digits: int = 3) -> str:
    return f"{x:,.{digits}g}" if abs(x) < 1000 else f"{x:,.0f}"


def pval(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"
