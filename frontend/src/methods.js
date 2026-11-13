const alpha = { key: "alpha", type: "number", label: "Significance level (α)", default: 0.05, step: 0.01 };
const groups = [
  { key: "group_col", type: "column", label: "Group / variant column" },
  { key: "control", type: "groupValue", label: "Control label", optional: true },
  { key: "treatment", type: "groupValue", label: "Treatment label", optional: true },
];
const causalBase = [
  { key: "treatment_col", type: "column", label: "Treatment column (0/1)", binary: true },
  { key: "outcome_col", type: "column", label: "Outcome column", numeric: true },
  { key: "covariates", type: "columns", label: "Confounders (covariates)" },
];

export const METHODS = {
  chisquare: {
    label: "Chi-square test", family: "experiment", endpoint: "/api/experiments/chisquare",
    blurb: "Compare conversion rates (binary 0/1 metric) between two variants.",
    fields: [...groups, { key: "metric_col", type: "column", label: "Binary metric (0/1)", binary: true }, alpha],
  },
  ttest: {
    label: "Welch t-test", family: "experiment", endpoint: "/api/experiments/ttest",
    blurb: "Compare the mean of a continuous metric (revenue, time on page) between two variants.",
    fields: [...groups, { key: "metric_col", type: "column", label: "Metric", numeric: true },
      { key: "alternative", type: "select", label: "Alternative hypothesis", default: "two-sided",
        options: [["two-sided", "Two-sided"], ["larger", "Treatment larger"], ["smaller", "Treatment smaller"]] }, alpha],
  },
  multi_metric: {
    label: "Multiple metrics + correction", family: "experiment", endpoint: "/api/experiments/multi-metric",
    blurb: "Test many metrics at once and control false discoveries with Bonferroni or Benjamini-Hochberg.",
    fields: [...groups, { key: "metric_cols", type: "columns", label: "Metrics to test", numeric: true },
      { key: "correction", type: "select", label: "Correction", default: "fdr_bh",
        options: [["fdr_bh", "Benjamini-Hochberg (FDR)"], ["bonferroni", "Bonferroni (FWER)"]] }, alpha],
  },
  sequential: {
    label: "Sequential test (safe peeking)", family: "experiment", endpoint: "/api/experiments/sequential",
    blurb: "Monitor results continuously without inflating the false-positive rate.",
    fields: [...groups, { key: "metric_col", type: "column", label: "Metric", numeric: true },
      { key: "time_col", type: "column", label: "Time / order column", optional: true },
      { key: "procedure", type: "select", label: "Procedure", default: "msprt",
        options: [["msprt", "mSPRT (always-valid p-values)"], ["obrien_fleming", "O'Brien-Fleming group sequential"]] },
      { key: "looks", type: "number", label: "Number of looks", default: 50, step: 1 },
      { key: "tau", type: "number", label: "mSPRT mixing scale τ (blank = auto)", optional: true, step: 0.001 }, alpha],
  },
  bayesian: {
    label: "Bayesian A/B (PyMC)", family: "experiment", endpoint: "/api/experiments/bayesian",
    blurb: "Probability that B beats A, expected loss and credible interval for the lift.",
    fields: [...groups, { key: "metric_col", type: "column", label: "Metric", numeric: true },
      { key: "draws", type: "number", label: "Posterior draws per chain", default: 2000, step: 500 },
      { key: "loss_threshold", type: "number", label: "Loss threshold (share of baseline)", default: 0.01, step: 0.005 }],
  },
  psm: {
    label: "Propensity score matching", family: "causal", endpoint: "/api/causal/psm",
    blurb: "Match treated units to similar untreated units (DoWhy), with refutation tests and an EconML cross-check.",
    fields: [...causalBase,
      { key: "estimand", type: "select", label: "Estimand", default: "att", options: [["att", "ATT (effect on treated)"], ["ate", "ATE (average effect)"]] },
      { key: "refute", type: "boolean", label: "Run refutation tests", default: true },
      { key: "dml", type: "boolean", label: "Cross-check with EconML DML", default: true }, alpha],
  },
  dml: {
    label: "Double ML (heterogeneous effects)", family: "causal", endpoint: "/api/causal/dml",
    blurb: "EconML LinearDML: average effect plus how the effect varies across segments.",
    fields: [...causalBase, { key: "modifier_col", type: "column", label: "Segment by (effect modifier)", optional: true }, alpha],
  },
  did: {
    label: "Difference-in-differences", family: "causal", endpoint: "/api/causal/did",
    blurb: "Compare the before/after change of a treated group with a control group, plus a parallel-trends check.",
    fields: [
      { key: "outcome_col", type: "column", label: "Outcome column", numeric: true },
      { key: "treated_col", type: "column", label: "Treated-group indicator (0/1)", binary: true },
      { key: "time_col", type: "column", label: "Time column" },
      { key: "post_col", type: "column", label: "Post-period indicator (or use start time)", optional: true },
      { key: "treatment_time", type: "number", label: "Treatment start time", optional: true, step: 1 },
      { key: "unit_col", type: "column", label: "Unit id (for fixed effects & clustering)", optional: true }, alpha],
  },
  synthetic_control: {
    label: "Synthetic control", family: "causal", endpoint: "/api/causal/synthetic-control",
    blurb: "Build a weighted combination of control units that mimics the treated unit before treatment.",
    fields: [
      { key: "unit_col", type: "column", label: "Unit column" },
      { key: "time_col", type: "column", label: "Time column" },
      { key: "outcome_col", type: "column", label: "Outcome column", numeric: true },
      { key: "treated_unit", type: "unitValue", label: "Treated unit" },
      { key: "treatment_time", type: "number", label: "Treatment start time", step: 1 },
      { key: "placebo", type: "boolean", label: "Run placebo (permutation) tests", default: true }],
  },
};

export const FAMILIES = { experiment: "Randomized experiments", causal: "Observational causal inference" };
