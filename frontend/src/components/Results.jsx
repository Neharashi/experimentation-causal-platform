import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, ErrorBar, Legend, Line, LineChart,
  ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis,
} from "recharts";
import { Card, COLORS, Stat, Table, axisProps, fmt, pct, pv, tooltipProps } from "./ui";

const H = 280;

export default function Results({ result }) {
  const View = VIEWS[result.method];
  const download = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${result.method}_result.json`;
    a.click();
  };
  return (
    <div className="stack">
      <Card title="3 · Conclusion" className="highlight"
        actions={<button className="ghost" onClick={download}>Download JSON</button>}>
        <p className="conclusion">{result.conclusion}</p>
        {result.warnings?.map((w) => <div key={w} className="warning">⚠ {w}</div>)}
      </Card>
      {View && <View r={result} />}
    </div>
  );
}

function Legendless({ children }) {
  return <ResponsiveContainer width="100%" height={H}>{children}</ResponsiveContainer>;
}

function GroupMeans({ r, asPct }) {
  const data = r.groups.map((g) => ({ ...g, err: [g.mean - g.ci[0], g.ci[1] - g.mean] }));
  return (
    <Legendless>
      <BarChart data={data} margin={{ top: 16, right: 16, left: 0, bottom: 0 }} barCategoryGap="35%">
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis dataKey="group" {...axisProps} />
        <YAxis {...axisProps} width={56} tickFormatter={(v) => (asPct ? pct(v, 1) : fmt(v))} />
        <Tooltip {...tooltipProps} formatter={(v) => (asPct ? pct(v, 2) : fmt(v, 4))} />
        <Bar dataKey="mean" name="Mean" radius={[4, 4, 0, 0]}>
          {data.map((_, i) => <Cell key={i} fill={i === 0 ? COLORS.control : COLORS.treatment} />)}
          <ErrorBar dataKey="err" width={10} stroke="var(--text-primary)" strokeWidth={1.5} />
        </Bar>
      </BarChart>
    </Legendless>
  );
}

function TwoGroup({ r }) {
  const asPct = r.method === "chisquare";
  return (
    <>
      <div className="stats">
        <Stat label={`Control · ${r.control}`} value={asPct ? pct(r.groups[0].mean, 2) : fmt(r.groups[0].mean)} sub={`n = ${r.groups[0].n.toLocaleString()}`} />
        <Stat label={`Treatment · ${r.treatment}`} value={asPct ? pct(r.groups[1].mean, 2) : fmt(r.groups[1].mean)} sub={`n = ${r.groups[1].n.toLocaleString()}`} />
        <Stat label="Relative lift" value={pct(r.relative_lift)} sub={`Δ ${asPct ? pct(r.diff, 2) : fmt(r.diff)}`} />
        <Stat label="p-value" value={pv(r.p_value)} tone={r.significant ? "good" : ""} sub={r.significant ? "significant" : "not significant"} />
        <Stat label={`${Math.round((1 - r.alpha) * 100)}% CI of difference`} value={asPct ? `${pct(r.ci[0], 2)} … ${pct(r.ci[1], 2)}` : `${fmt(r.ci[0])} … ${fmt(r.ci[1])}`} />
      </div>
      <div className="grid-2">
        <Card title={`Group ${asPct ? "rates" : "means"} with ${Math.round((1 - r.alpha) * 100)}% CI`}>
          <GroupMeans r={r} asPct={asPct} />
        </Card>
        {r.distribution ? (
          <Card title={`Distribution of ${r.metric}`}>
            <Legendless>
              <AreaChart data={r.distribution} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="x" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(v) => fmt(v)} {...axisProps} />
                <YAxis hide />
                <Tooltip {...tooltipProps} formatter={(v) => fmt(v)} labelFormatter={(v) => `${r.metric} ≈ ${fmt(v)}`} />
                <Legend />
                <Area dataKey={r.control} stroke={COLORS.control} fill={COLORS.control} fillOpacity={0.15} strokeWidth={2} />
                <Area dataKey={r.treatment} stroke={COLORS.treatment} fill={COLORS.treatment} fillOpacity={0.15} strokeWidth={2} />
              </AreaChart>
            </Legendless>
          </Card>
        ) : (
          <Card title="Contingency table">
            <Table columns={[{ key: "g", label: "Group" }, { key: "y", label: `${r.metric} = 1` }, { key: "n", label: `${r.metric} = 0` }, { key: "rate", label: "Rate" }]}
              rows={[r.control, r.treatment].map((g, i) => ({ g, y: r.contingency_table[i][0].toLocaleString(), n: r.contingency_table[i][1].toLocaleString(), rate: pct(r.groups[i].mean, 2) }))} />
            <p className="muted">χ² = {fmt(r.statistic)}, df = {r.dof}. Sample-ratio check p = {pv(r.srm.p_value)}.</p>
          </Card>
        )}
      </div>
    </>
  );
}

function MultiMetric({ r }) {
  const data = r.results.map((x) => ({ metric: x.metric, raw: x.p_value, bh: x.p_fdr_bh, bonf: x.p_bonferroni }));
  return (
    <>
      <div className="stats">
        <Stat label="Metrics tested" value={r.results.length} />
        <Stat label="Significant (raw)" value={r.summary.n_significant_raw} />
        <Stat label="After Bonferroni" value={r.summary.n_significant_bonferroni} />
        <Stat label="After Benjamini-Hochberg" value={r.summary.n_significant_fdr_bh} />
      </div>
      <div className="grid-2">
        <Card title="p-values before and after correction">
          <Legendless>
            <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="metric" {...axisProps} interval={0} fontSize={11} />
              <YAxis domain={[0, 1]} {...axisProps} width={40} />
              <Tooltip {...tooltipProps} formatter={(v) => pv(v)} />
              <Legend />
              <ReferenceLine y={r.alpha} stroke="var(--text-muted)" strokeDasharray="4 4" label={{ value: `α = ${r.alpha}`, fill: "var(--text-muted)", fontSize: 11, position: "right" }} />
              <Bar dataKey="raw" name="Raw" fill="var(--series-1)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="bh" name="Benjamini-Hochberg" fill="var(--series-2)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="bonf" name="Bonferroni" fill="var(--series-3)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </Legendless>
        </Card>
        <Card title="Per-metric results">
          <Table columns={[
            { key: "metric", label: "Metric" }, { key: "test", label: "Test" },
            { key: "lift", label: "Lift", render: (x) => pct(x.relative_lift) },
            { key: "p", label: "Raw p", render: (x) => pv(x.p_value) },
            { key: "adj", label: "Adjusted p", render: (x) => pv(r.correction === "bonferroni" ? x.p_bonferroni : x.p_fdr_bh) },
            { key: "sig", label: "Decision", render: (x) => <span className={x.significant ? "pill good" : "pill"}>{x.significant ? "Significant" : "Not significant"}</span> },
          ]} rows={r.results} />
        </Card>
      </div>
    </>
  );
}

function Sequential({ r }) {
  const msprt = r.procedure.startsWith("mSPRT");
  return (
    <>
      <div className="stats">
        <Stat label="Procedure" value={msprt ? "mSPRT" : "O'Brien-Fleming"} />
        <Stat label="Decision" value={r.stopped ? `Stop at look ${r.stop_look}` : "Continue"} tone={r.stopped ? "good" : ""} />
        <Stat label="Sample at decision" value={r.stopped ? r.stop_n.toLocaleString() : "–"} sub={`of ${r.looks.at(-1).n.toLocaleString()}`} />
        {msprt ? <Stat label="Final always-valid p" value={pv(r.looks.at(-1).p_always_valid)} />
          : <Stat label="OBF constant" value={fmt(r.obf_constant)} />}
        {msprt && <Stat label="Naive peeking would stop at" value={r.naive_stop_look ? `look ${r.naive_stop_look}` : "never"} />}
      </div>
      {msprt ? (
        <div className="grid-2">
          <Card title="Always-valid vs naive p-value as data arrives">
            <Legendless>
              <LineChart data={r.looks} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="n" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(v) => v.toLocaleString()} {...axisProps} />
                <YAxis scale="log" domain={[1e-4, 1]} allowDataOverflow ticks={[1e-4, 1e-3, 0.01, 0.05, 0.2, 1]} {...axisProps} width={50} />
                <Tooltip {...tooltipProps} formatter={(v) => pv(v)} labelFormatter={(v) => `n = ${v.toLocaleString()}`} />
                <Legend />
                <ReferenceLine y={r.alpha} stroke="var(--critical)" strokeDasharray="4 4" />
                <Line dataKey="p_always_valid" name="Always-valid p (mSPRT)" stroke="var(--series-1)" strokeWidth={2} dot={false} />
                <Line dataKey="p_naive" name="Naive p-value" stroke="var(--series-2)" strokeWidth={2} dot={false} strokeDasharray="5 3" />
              </LineChart>
            </Legendless>
          </Card>
          <Card title="Estimated difference with always-valid confidence sequence">
            <Legendless>
              <ComposedChart data={r.looks.map((l) => ({ ...l, band: l.ci }))} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="n" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(v) => v.toLocaleString()} {...axisProps} />
                <YAxis {...axisProps} width={60} tickFormatter={(v) => fmt(v, 2)} />
                <Tooltip {...tooltipProps} formatter={(v) => (Array.isArray(v) ? `${fmt(v[0])} … ${fmt(v[1])}` : fmt(v))} />
                <ReferenceLine y={0} stroke="var(--text-muted)" />
                <Area dataKey="band" name="Confidence sequence" stroke="none" fill="var(--series-1)" fillOpacity={0.15} />
                <Line dataKey="diff" name="Difference" stroke="var(--series-1)" strokeWidth={2} dot={false} />
              </ComposedChart>
            </Legendless>
          </Card>
        </div>
      ) : (
        <Card title="z-statistic vs O'Brien-Fleming boundaries">
          <Legendless>
            <ComposedChart data={r.looks.map((l) => ({ ...l, absz: Math.abs(l.z) }))} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="look" {...axisProps} />
              <YAxis {...axisProps} width={40} />
              <Tooltip {...tooltipProps} formatter={(v) => fmt(v)} />
              <Legend />
              <Line dataKey="boundary" name="Efficacy boundary" stroke="var(--critical)" strokeWidth={2} strokeDasharray="5 3" />
              <Line dataKey="absz" name="|z| observed" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 4 }} />
            </ComposedChart>
          </Legendless>
        </Card>
      )}
    </>
  );
}

function Bayesian({ r }) {
  return (
    <>
      <div className="stats">
        <Stat label={`P(${r.treatment} beats ${r.control})`} value={pct(r.prob_treatment_better)} tone={r.prob_treatment_better > 0.95 ? "good" : ""} />
        <Stat label="Expected lift" value={pct(r.lift_mean)} sub={`95% HDI ${pct(r.lift_hdi[0])} … ${pct(r.lift_hdi[1])}`} />
        <Stat label="Expected loss if ship" value={fmt(r.expected_loss_treatment)} sub={`threshold ${fmt(r.loss_threshold)}`} />
        <Stat label="Recommendation" value={r.decision} />
        <Stat label="Model" value={r.model} sub={`R-hat ${r.diagnostics.r_hat.toFixed(3)} · ${r.diagnostics.draws.toLocaleString()} draws`} />
      </div>
      <div className="grid-2">
        <Card title="Posterior distributions">
          <Legendless>
            <AreaChart data={r.posterior_density} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="x" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(v) => fmt(v)} {...axisProps} />
              <YAxis hide />
              <Tooltip {...tooltipProps} formatter={(v) => fmt(v)} labelFormatter={(v) => fmt(v, 4)} />
              <Legend />
              <Area dataKey={r.control} stroke={COLORS.control} fill={COLORS.control} fillOpacity={0.2} strokeWidth={2} />
              <Area dataKey={r.treatment} stroke={COLORS.treatment} fill={COLORS.treatment} fillOpacity={0.2} strokeWidth={2} />
            </AreaChart>
          </Legendless>
        </Card>
        <Card title="Posterior of relative lift">
          <Legendless>
            <AreaChart data={r.lift_density} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="x" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(v) => pct(v, 0)} {...axisProps} />
              <YAxis hide />
              <Tooltip {...tooltipProps} formatter={(v) => fmt(v)} labelFormatter={(v) => `lift ${pct(v)}`} />
              <ReferenceLine x={0} stroke="var(--text-primary)" strokeDasharray="4 4" />
              <Area dataKey="lift" stroke="var(--series-3)" fill="var(--series-3)" fillOpacity={0.25} strokeWidth={2} />
            </AreaChart>
          </Legendless>
        </Card>
      </div>
    </>
  );
}

function EffectBars({ data, label = "estimate" }) {
  const rows = data.map((d) => ({ ...d, err: [d.estimate - d.ci[0], d.ci[1] - d.estimate] }));
  return (
    <Legendless>
      <BarChart data={rows} margin={{ top: 16, right: 16, left: 0, bottom: 0 }} barCategoryGap="30%">
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis dataKey="group" {...axisProps} interval={0} fontSize={11} />
        <YAxis {...axisProps} width={60} tickFormatter={(v) => fmt(v)} />
        <Tooltip {...tooltipProps} formatter={(v) => (Array.isArray(v) ? "" : fmt(v))} />
        <ReferenceLine y={0} stroke="var(--text-muted)" />
        <Bar dataKey="estimate" name={label} fill="var(--series-1)" radius={[4, 4, 0, 0]}>
          <ErrorBar dataKey="err" width={8} stroke="var(--text-primary)" />
        </Bar>
      </BarChart>
    </Legendless>
  );
}

function PSM({ r }) {
  const balance = [...r.balance].sort((a, b) => Math.abs(b.smd_before) - Math.abs(a.smd_before));
  const compare = [
    { group: "Naive difference", estimate: r.naive_difference, ci: [r.naive_difference, r.naive_difference] },
    { group: `Matching ${r.estimand}`, estimate: r.estimate, ci: r.ci },
    ...(r.dml ? [{ group: `DML ${r.estimand}`, ...r.dml[r.estimand.toLowerCase()] }] : []),
  ];
  return (
    <>
      <div className="stats">
        <Stat label="Naive difference" value={fmt(r.naive_difference)} tone="bad" />
        <Stat label={`Matched ${r.estimand} (DoWhy)`} value={fmt(r.estimate)} sub={`95% CI ${fmt(r.ci[0])} … ${fmt(r.ci[1])}`} tone="good" />
        {r.dml && <Stat label={`EconML DML ${r.estimand}`} value={fmt(r.dml[r.estimand.toLowerCase()].estimate)} />}
        <Stat label="Treated / control" value={`${r.n_treated.toLocaleString()} / ${r.n_control.toLocaleString()}`} />
        <Stat label="Max |SMD| after" value={r.max_smd_after.toFixed(3)} tone={r.max_smd_after < 0.1 ? "good" : "warn"} sub="< 0.1 is balanced" />
      </div>
      <div className="grid-2">
        <Card title="Covariate balance (standardized mean difference)">
          <ResponsiveContainer width="100%" height={Math.max(H, balance.length * 28)}>
            <ComposedChart layout="vertical" data={balance.map((b) => ({ ...b, before: Math.abs(b.smd_before), after: Math.abs(b.smd_after) }))}
              margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" horizontal={false} />
              <XAxis type="number" {...axisProps} tickFormatter={(v) => v.toFixed(1)} />
              <YAxis type="category" dataKey="covariate" {...axisProps} width={80} interval={0} padding={{ top: 12, bottom: 12 }} />
              <Tooltip {...tooltipProps} formatter={(v) => v.toFixed(3)} />
              <Legend />
              <ReferenceLine x={0.1} stroke="var(--text-muted)" strokeDasharray="4 4" />
              <Scatter dataKey="before" name="Before matching" fill="var(--series-2)" />
              <Scatter dataKey="after" name="After matching" fill="var(--series-1)" />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Propensity score overlap">
          <Legendless>
            <AreaChart data={r.propensity_overlap} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="x" type="number" domain={[0, 1]} tickFormatter={(v) => v.toFixed(1)} {...axisProps} />
              <YAxis hide scale="sqrt" />
              <Tooltip {...tooltipProps} formatter={(v) => fmt(v)} labelFormatter={(v) => `propensity ${v.toFixed(2)}`} />
              <Legend />
              <Area dataKey="control" stroke={COLORS.control} fill={COLORS.control} fillOpacity={0.2} strokeWidth={2} />
              <Area dataKey="treated" stroke={COLORS.treatment} fill={COLORS.treatment} fillOpacity={0.2} strokeWidth={2} />
            </AreaChart>
          </Legendless>
        </Card>
        <Card title="Estimates compared">
          <EffectBars data={compare} />
        </Card>
        {r.refutations?.length > 0 && (
          <Card title="Refutation tests (DoWhy)">
            <Table columns={[{ key: "test", label: "Test" }, { key: "o", label: "Original", render: (x) => fmt(x.original) },
              { key: "n", label: "New effect", render: (x) => fmt(x.new_effect) }]} rows={r.refutations} />
            <p className="muted">A robust estimate collapses to ≈ 0 under a placebo treatment and stays stable when a random confounder or subset is used.</p>
          </Card>
        )}
      </div>
    </>
  );
}

function DML({ r }) {
  return (
    <>
      <div className="stats">
        <Stat label="Naive difference" value={fmt(r.naive_difference)} />
        <Stat label="ATE" value={fmt(r.ate.estimate)} sub={`95% CI ${fmt(r.ate.ci[0])} … ${fmt(r.ate.ci[1])}`} tone="good" />
        <Stat label="ATT" value={fmt(r.att.estimate)} sub={`95% CI ${fmt(r.att.ci[0])} … ${fmt(r.att.ci[1])}`} />
        <Stat label="Nuisance models" value={r.nuisance_models} />
      </div>
      <div className="grid-2">
        {r.by_group && (
          <Card title={`Effect by ${r.modifier}`}>
            <EffectBars data={r.by_group} />
          </Card>
        )}
        <Card title="Distribution of individual effects (CATE)">
          <Legendless>
            <AreaChart data={r.cate_distribution} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="x" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(v) => fmt(v)} {...axisProps} />
              <YAxis hide />
              <Tooltip {...tooltipProps} formatter={(v) => fmt(v)} labelFormatter={(v) => `effect ${fmt(v)}`} />
              <ReferenceLine x={0} stroke="var(--text-muted)" strokeDasharray="4 4" />
              <Area dataKey="cate" stroke="var(--series-1)" fill="var(--series-1)" fillOpacity={0.2} strokeWidth={2} />
            </AreaChart>
          </Legendless>
        </Card>
      </div>
    </>
  );
}

function DiD({ r }) {
  const m = r.means;
  const firstPost = r.event_study?.find((e) => e.post)?.time;
  return (
    <>
      <div className="stats">
        <Stat label="DiD estimate" value={fmt(r.estimate)} sub={`95% CI ${fmt(r.ci[0])} … ${fmt(r.ci[1])}`} tone={r.significant ? "good" : ""} />
        <Stat label="p-value" value={pv(r.p_value)} />
        <Stat label="Parallel trends test" value={r.pretrend_p_value == null ? "n/a" : pv(r.pretrend_p_value)} tone={r.pretrend_p_value != null && r.pretrend_p_value < 0.05 ? "warn" : ""} sub="p > 0.05 supports design" />
        <Stat label="Specification" value={r.specification} sub={`${r.n_obs.toLocaleString()} observations`} />
      </div>
      <div className="grid-2">
        <Card title="Average outcome over time">
          <Legendless>
            <LineChart data={r.trends} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="time" {...axisProps} />
              <YAxis {...axisProps} width={50} tickFormatter={(v) => fmt(v)} domain={["auto", "auto"]} />
              <Tooltip {...tooltipProps} formatter={(v) => fmt(v)} />
              <Legend />
              {firstPost !== undefined && <ReferenceLine x={firstPost} stroke="var(--text-muted)" strokeDasharray="4 4" label={{ value: "treatment", fill: "var(--text-muted)", fontSize: 11, position: "insideTopLeft" }} />}
              <Line dataKey="control" name="Control group" stroke={COLORS.control} strokeWidth={2} dot={false} />
              <Line dataKey="treated" name="Treated group" stroke={COLORS.treatment} strokeWidth={2} dot={false} />
            </LineChart>
          </Legendless>
        </Card>
        {r.event_study?.length > 0 ? (
          <Card title="Event study: effect relative to last pre-period">
            <Legendless>
              <ComposedChart data={r.event_study.map((e) => ({ ...e, err: [e.coef - e.ci[0], e.ci[1] - e.coef] }))} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="time" {...axisProps} />
                <YAxis {...axisProps} width={50} tickFormatter={(v) => fmt(v)} />
                <Tooltip {...tooltipProps} formatter={(v) => (Array.isArray(v) ? "" : fmt(v))} />
                <ReferenceLine y={0} stroke="var(--text-muted)" />
                {firstPost !== undefined && <ReferenceLine x={firstPost} stroke="var(--text-muted)" strokeDasharray="4 4" />}
                <Scatter dataKey="coef" name="Coefficient" fill="var(--series-1)">
                  <ErrorBar dataKey="err" width={4} stroke="var(--series-1)" direction="y" />
                </Scatter>
              </ComposedChart>
            </Legendless>
          </Card>
        ) : (
          <Card title="2 × 2 means">
            <Table columns={[{ key: "g", label: "" }, { key: "pre", label: "Pre" }, { key: "post", label: "Post" }, { key: "d", label: "Change" }]}
              rows={[{ g: "Treated", pre: fmt(m.treated_pre), post: fmt(m.treated_post), d: fmt(m.treated_post - m.treated_pre) },
                { g: "Control", pre: fmt(m.control_pre), post: fmt(m.control_post), d: fmt(m.control_post - m.control_pre) }]} />
          </Card>
        )}
      </div>
    </>
  );
}

function Synth({ r }) {
  const placeboRows = r.placebo_gaps || [];
  return (
    <>
      <div className="stats">
        <Stat label="Average effect after treatment" value={fmt(r.att)} sub={r.relative_effect != null ? pct(r.relative_effect) : ""} tone="good" />
        <Stat label="Pre-treatment RMSPE" value={fmt(r.pre_rmspe)} sub="lower = better fit" />
        <Stat label="Post / pre RMSPE" value={fmt(r.rmspe_ratio)} />
        {r.placebo_p_value != null && <Stat label="Placebo p-value" value={r.placebo_p_value.toFixed(3)} tone={r.placebo_p_value <= 0.1 ? "good" : ""} />}
      </div>
      <div className="grid-2">
        <Card title={`${r.treated_unit}: actual vs synthetic`}>
          <Legendless>
            <LineChart data={r.series} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="time" {...axisProps} />
              <YAxis {...axisProps} width={50} domain={["auto", "auto"]} tickFormatter={(v) => fmt(v)} />
              <Tooltip {...tooltipProps} formatter={(v) => fmt(v)} />
              <Legend />
              <ReferenceLine x={r.treatment_time} stroke="var(--text-muted)" strokeDasharray="4 4" />
              <Line dataKey="actual" name={`Actual ${r.treated_unit}`} stroke={COLORS.treatment} strokeWidth={2} dot={false} />
              <Line dataKey="synthetic" name="Synthetic control" stroke={COLORS.control} strokeWidth={2} strokeDasharray="6 3" dot={false} />
            </LineChart>
          </Legendless>
        </Card>
        <Card title="Donor weights">
          <ResponsiveContainer width="100%" height={Math.max(H, r.weights.length * 28)}>
            <BarChart layout="vertical" data={r.weights} margin={{ top: 8, right: 24, left: 8, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" horizontal={false} />
              <XAxis type="number" {...axisProps} tickFormatter={(v) => pct(v, 0)} />
              <YAxis type="category" dataKey="unit" {...axisProps} width={110} />
              <Tooltip {...tooltipProps} formatter={(v) => pct(v)} />
              <Bar dataKey="weight" fill="var(--series-1)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        {placeboRows.length > 0 && (
          <Card title="Placebo test: gap for treated unit vs every control unit" className="span-2">
            <Legendless>
              <LineChart data={placeboRows} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="time" {...axisProps} />
                <YAxis {...axisProps} width={50} tickFormatter={(v) => fmt(v)} />
                <Tooltip {...tooltipProps} formatter={(v) => fmt(v)} itemSorter={(i) => (i.dataKey === "treated" ? -1 : 1)} />
                <ReferenceLine y={0} stroke="var(--text-muted)" />
                <ReferenceLine x={r.treatment_time} stroke="var(--text-muted)" strokeDasharray="4 4" />
                {r.placebo_units.map((u) => <Line key={u} dataKey={u} stroke={COLORS.muted} strokeWidth={1} dot={false} isAnimationActive={false} legendType="none" />)}
                <Line dataKey="treated" name={r.treated_unit} stroke={COLORS.treatment} strokeWidth={3} dot={false} />
              </LineChart>
            </Legendless>
            <p className="muted">Grey lines are placebo gaps for control units (poorly fitted placebos with pre-RMSPE &gt; 5× the treated unit are hidden).</p>
          </Card>
        )}
      </div>
    </>
  );
}

const VIEWS = {
  ttest: TwoGroup, chisquare: TwoGroup, multi_metric: MultiMetric, sequential: Sequential,
  bayesian: Bayesian, psm: PSM, dml: DML, did: DiD, synthetic_control: Synth,
};
