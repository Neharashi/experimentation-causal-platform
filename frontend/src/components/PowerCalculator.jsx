import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { Card, ErrorBox, Field, Stat, axisProps, pct, tooltipProps } from "./ui";

const INITIAL = {
  metric_type: "proportion", baseline: 0.1, mde: 0.1, mde_type: "relative", std: "", alpha: 0.05,
  power: 0.8, ratio: 1, alternative: "two-sided", daily_traffic: 2000, n_per_group: 5000,
};

export default function PowerCalculator() {
  const [form, setForm] = useState(INITIAL);
  const [result, setResult] = useState(null);
  const [check, setCheck] = useState(null);
  const [error, setError] = useState("");
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === "number" ? e.target.value : e.target.value });

  const payload = () => {
    const p = {};
    for (const [k, v] of Object.entries(form)) {
      if (v === "" || v === null) continue;
      p[k] = ["metric_type", "mde_type", "alternative"].includes(k) ? v : Number(v);
    }
    return p;
  };

  const run = async () => {
    setError("");
    try {
      const p = payload();
      const { n_per_group, ...rest } = p;
      const [ss, pw] = await Promise.all([
        api.post("/api/power/sample-size", rest),
        api.post("/api/power/power", { ...rest, n_per_group }),
      ]);
      setResult(ss);
      setCheck(pw);
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => { run(); }, []);
  const isProp = form.metric_type === "proportion";

  return (
    <div className="grid-2">
      <Card title="Test design inputs">
        <div className="form-grid">
          <Field label="Metric type">
            <select value={form.metric_type} onChange={set("metric_type")}>
              <option value="proportion">Conversion rate (proportion)</option>
              <option value="mean">Continuous mean</option>
            </select>
          </Field>
          <Field label={isProp ? "Baseline conversion rate" : "Baseline mean"} hint={isProp ? "e.g. 0.10 = 10%" : ""}>
            <input type="number" step="0.01" value={form.baseline} onChange={set("baseline")} />
          </Field>
          {!isProp && (
            <Field label="Standard deviation">
              <input type="number" step="any" value={form.std} onChange={set("std")} />
            </Field>
          )}
          <Field label="Minimum detectable effect" hint={form.mde_type === "relative" ? "0.10 = +10% relative" : "absolute change"}>
            <input type="number" step="0.01" value={form.mde} onChange={set("mde")} />
          </Field>
          <Field label="MDE type">
            <select value={form.mde_type} onChange={set("mde_type")}>
              <option value="relative">Relative</option>
              <option value="absolute">Absolute</option>
            </select>
          </Field>
          <Field label="Significance (α)">
            <input type="number" step="0.01" value={form.alpha} onChange={set("alpha")} />
          </Field>
          <Field label="Power (1 − β)">
            <input type="number" step="0.05" value={form.power} onChange={set("power")} />
          </Field>
          <Field label="Treatment : control ratio">
            <input type="number" step="0.1" value={form.ratio} onChange={set("ratio")} />
          </Field>
          <Field label="Alternative">
            <select value={form.alternative} onChange={set("alternative")}>
              <option value="two-sided">Two-sided</option>
              <option value="larger">One-sided (increase)</option>
              <option value="smaller">One-sided (decrease)</option>
            </select>
          </Field>
          <Field label="Daily traffic (optional)">
            <input type="number" value={form.daily_traffic} onChange={set("daily_traffic")} />
          </Field>
          <Field label="Check power at n per group">
            <input type="number" value={form.n_per_group} onChange={set("n_per_group")} />
          </Field>
        </div>
        <button className="primary" onClick={run}>Calculate</button>
        <ErrorBox error={error} />
      </Card>

      {result && (
        <div className="stack">
          <Card title="Required sample size" className="highlight">
            <div className="stats">
              <Stat label="Control" value={result.n_control.toLocaleString()} />
              <Stat label="Treatment" value={result.n_treatment.toLocaleString()} />
              <Stat label="Total" value={result.total.toLocaleString()} />
              {result.duration_days && <Stat label="Duration" value={`${result.duration_days} days`} />}
            </div>
            <p className="conclusion">{result.conclusion}</p>
            {check && <p className="conclusion secondary">{check.conclusion}</p>}
          </Card>
          <Card title="Power vs. sample size per group">
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={result.power_curve} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="n_per_group" type="number" domain={["dataMin", "dataMax"]} {...axisProps}
                  tickFormatter={(v) => v.toLocaleString()} />
                <YAxis domain={[0, 1]} tickFormatter={(v) => pct(v, 0)} {...axisProps} width={44} />
                <Tooltip {...tooltipProps} formatter={(v) => pct(v)} labelFormatter={(v) => `n = ${v.toLocaleString()} per group`} />
                <ReferenceLine y={Number(form.power)} stroke="var(--text-muted)" strokeDasharray="4 4" />
                <ReferenceLine x={result.n_control} stroke="var(--text-muted)" strokeDasharray="4 4" />
                <Line dataKey="power" name="Power" stroke="var(--series-1)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </div>
      )}
    </div>
  );
}
