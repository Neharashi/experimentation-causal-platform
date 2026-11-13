# API reference

Interactive docs (Swagger) are served at **`/docs`** when the backend runs. All endpoints accept and return JSON
unless noted. Errors return `{"detail": "<readable message>"}` with status 422 (bad input) or 404 (unknown dataset).

Every analysis response contains `method`, `conclusion` (plain English) and `warnings` (list of strings).

## Design

| Method | Path | Body |
|---|---|---|
| POST | `/api/power/sample-size` | `metric_type` (`proportion`/`mean`), `baseline`, `mde`, `mde_type` (`relative`/`absolute`), `std` (mean only), `alpha`, `power`, `ratio`, `alternative`, `daily_traffic` |
| POST | `/api/power/power` | same as above but `n_per_group` instead of `power` → achieved power and minimum detectable effect |

Example:

```bash
curl -X POST localhost:8000/api/power/sample-size -H "Content-Type: application/json" \
  -d '{"baseline": 0.10, "mde": 0.10, "daily_traffic": 2000}'
```
```json
{"n_control": 14745, "n_treatment": 14745, "total": 29490, "duration_days": 15, "effect_size": 0.0326,
 "power_curve": [{"n_per_group": 737, "power": 0.08}, "..."],
 "conclusion": "To detect a change from 10.0% to 11.0% with 80% power ... about 15 days."}
```

## Datasets

| Method | Path | Notes |
|---|---|---|
| POST | `/api/datasets/upload` | multipart form, field `file` (CSV ≤ 50 MB) |
| GET | `/api/datasets/samples` | bundled datasets with suggested methods and default column mappings |
| POST | `/api/datasets/samples/{key}` | load a bundled dataset: `simulated_ab`, `lalonde_experimental`, `lalonde_observational`, `prop99`, `simulated_did`, `simulated_observational` |
| POST | `/api/datasets/simulate` | `kind` (`ab`/`did`/`observational`), `n_per_group`, `baseline_rate`, `relative_lift`, `n_days`, `effect`, `seed` |
| GET | `/api/datasets/{dataset_id}` | column summary + preview |

All return `{dataset_id, name, rows, columns: [{name, dtype, is_numeric, is_binary, n_unique, sample_values}], preview}`.

## Experiment analysis

Common fields: `dataset_id`, `group_col`, optional `control` / `treatment` labels (auto-detected when the column has exactly two values), `alpha`.

| Path | Extra fields | Key outputs |
|---|---|---|
| `/api/experiments/ttest` | `metric_col`, `alternative` | Welch t, p, diff, CI, relative lift, Cohen's d, group means + CIs, SRM check, distribution |
| `/api/experiments/chisquare` | `metric_col` (binary) | χ², p, diff in proportions with Newcombe CI, contingency table, SRM check |
| `/api/experiments/multi-metric` | `metric_cols[]`, `correction` (`bonferroni`/`fdr_bh`) | per-metric test (auto chi-square or t), raw, Bonferroni and BH-adjusted p |
| `/api/experiments/correct` | `p_values[]`, `method` | raw vs adjusted p-values for both corrections |
| `/api/experiments/sequential` | `metric_col`, `procedure` (`msprt`/`obrien_fleming`), `time_col`, `looks`, `tau` | per-look always-valid p (or z vs boundary), naive p, stop decision |
| `/api/experiments/bayesian` | `metric_col`, `draws`, `prior_alpha`, `prior_beta`, `loss_threshold` | P(B > A), expected loss, lift mean + 95% HDI, posterior densities, R-hat |

## Causal inference

| Path | Fields | Key outputs |
|---|---|---|
| `/api/causal/psm` | `treatment_col`, `outcome_col`, `covariates[]`, `estimand` (`att`/`ate`), `refute`, `dml` | naive diff, DoWhy matching estimate, bootstrap CI, SMD balance table, propensity overlap, refutation results, EconML cross-check |
| `/api/causal/dml` | `treatment_col`, `outcome_col`, `covariates[]`, `modifier_col` | ATE / ATT with CIs, CATE by segment, CATE distribution |
| `/api/causal/did` | `outcome_col`, `treated_col`, `time_col`, `post_col` **or** `treatment_time`, `unit_col` | DiD estimate (2×2 or two-way FE, clustered SE), 2×2 means, group trends, event-study coefficients, parallel-trends test |
| `/api/causal/synthetic-control` | `unit_col`, `time_col`, `outcome_col`, `treated_unit`, `treatment_time`, `placebo` | donor weights, actual vs synthetic series, ATT, RMSPE, placebo gaps and permutation p-value |

## Data formats

- **Experiments:** one row per user — `group`, metric columns, optional `day`/timestamp for sequential analysis.
- **PSM / DML:** one row per unit — binary treatment, outcome, pre-treatment covariates (categoricals are one-hot encoded).
- **DiD / synthetic control:** long panel — one row per unit per period.

See `examples/` for ready-to-upload CSVs.
