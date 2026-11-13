import { Card } from "./ui";

const ROWS = [
  ["Plan a test", "Power calculator", "How many users and days you need before launching, given baseline, minimum effect, α and power."],
  ["Binary metric (converted yes/no)", "Chi-square", "Compares two proportions; reports lift, Newcombe CI and a sample-ratio-mismatch check."],
  ["Continuous metric (revenue, time)", "Welch t-test", "Compares means without assuming equal variances."],
  ["Many metrics or variants", "Bonferroni / Benjamini-Hochberg", "Bonferroni controls the chance of any false positive; BH controls the share of false discoveries and keeps more power."],
  ["Checking results while the test runs", "mSPRT or O'Brien-Fleming", "Naive repeated p-values inflate false positives (≈30% with 20 looks). Sequential methods keep α honest."],
  ["Business wants 'chance B is better'", "Bayesian A/B (PyMC)", "Posterior probability B beats A, expected loss of a wrong decision, credible interval for lift."],
  ["No randomization, rich covariates", "Propensity score matching / Double ML", "Adjusts for observed confounders. Check balance, overlap and refutation tests."],
  ["Policy hits one group at a known time", "Difference-in-differences", "Uses a control group's change as the counterfactual; needs parallel pre-trends."],
  ["One treated unit (a state, a market)", "Synthetic control", "Builds a weighted combination of untreated units that matches the pre-period, then compares after."],
];

export default function Guide() {
  return (
    <div className="stack">
      <Card title="Which method should I use?">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Situation</th><th>Method</th><th>What it does</th></tr></thead>
            <tbody>{ROWS.map((r) => <tr key={r[0]}><td>{r[0]}</td><td><strong>{r[1]}</strong></td><td>{r[2]}</td></tr>)}</tbody>
          </table>
        </div>
      </Card>
      <div className="grid-2">
        <Card title="Data format">
          <ul className="list">
            <li><strong>Experiments:</strong> one row per user with a group column (e.g. control / treatment) and metric columns. Add a day or timestamp column for sequential analysis.</li>
            <li><strong>Matching / DML:</strong> one row per unit with a 0/1 treatment, an outcome and pre-treatment covariates.</li>
            <li><strong>DiD / synthetic control:</strong> panel data, one row per unit per period, with unit, time and outcome columns.</li>
          </ul>
        </Card>
        <Card title="Reading the results responsibly">
          <ul className="list">
            <li>Statistical significance is not business significance: always look at the size of the effect and its interval.</li>
            <li>Observational methods only remove bias from confounders you measured. Refutation and placebo tests probe, but cannot prove, the assumptions.</li>
            <li>Decide the metric, sample size and stopping rule before launch.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
