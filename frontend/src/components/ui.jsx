export const fmt = (v, d = 3) => {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  if (Math.abs(v) >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
  return Number(v).toPrecision(d).replace(/\.?0+$/, "") || "0";
};
export const pct = (v, d = 1) => (v === null || v === undefined ? "–" : `${(v * 100).toFixed(d)}%`);
export const pv = (p) => (p === null || p === undefined ? "–" : p < 0.001 ? "< 0.001" : p.toFixed(3));

export function Card({ title, children, actions, className = "" }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-head">
          {title && <h3>{title}</h3>}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, sub, tone }) {
  return (
    <div className={`stat ${tone || ""}`}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {sub && <span className="stat-sub">{sub}</span>}
    </div>
  );
}

export function Field({ label, hint, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

export function ErrorBox({ error }) {
  return error ? <div className="error">{error}</div> : null;
}

export function Table({ columns, rows }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>{columns.map((c) => <td key={c.key}>{c.render ? c.render(r) : r[c.key]}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const COLORS = {
  control: "var(--series-1)",
  treatment: "var(--series-2)",
  third: "var(--series-3)",
  muted: "var(--placebo)",
  grid: "var(--grid)",
  axis: "var(--text-muted)",
};

export const axisProps = {
  tick: { fill: "var(--text-muted)", fontSize: 12 },
  stroke: "var(--axis)",
  tickLine: false,
};

export const tooltipProps = {
  contentStyle: {
    background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 8,
    color: "var(--text-primary)", fontSize: 12,
  },
  labelStyle: { color: "var(--text-secondary)" },
};
