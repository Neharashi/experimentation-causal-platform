import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { FAMILIES, METHODS } from "../methods";
import Results from "./Results.jsx";
import { Card, ErrorBox, Field } from "./ui";

function defaultsFor(method, dataset, sampleDefaults) {
  const cols = dataset?.columns || [];
  const params = {};
  for (const f of METHODS[method].fields) {
    const scoped = `${method}:${f.key}`;
    if (sampleDefaults && scoped in sampleDefaults) params[f.key] = sampleDefaults[scoped];
    else if (sampleDefaults && f.key in sampleDefaults) params[f.key] = sampleDefaults[f.key];
    else if (f.default !== undefined) params[f.key] = f.default;
    else if (f.type === "columns") params[f.key] = [];
    else if (f.type === "column" && !f.optional) {
      const pick = cols.find((c) => (f.binary ? c.is_binary : f.numeric ? c.is_numeric : true));
      params[f.key] = pick?.name ?? "";
    } else params[f.key] = "";
  }
  if (method === "sequential" && params.procedure === "obrien_fleming") params.looks = 5;
  return params;
}

export default function Analyze() {
  const [samples, setSamples] = useState([]);
  const [dataset, setDataset] = useState(null);
  const [sampleKey, setSampleKey] = useState(null);
  const [method, setMethod] = useState("chisquare");
  const [params, setParams] = useState({});
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const sample = samples.find((s) => s.key === sampleKey);

  useEffect(() => {
    api.get("/api/datasets/samples").then(setSamples).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (dataset) setParams(defaultsFor(method, dataset, sample?.defaults));
    setResult(null);
  }, [method, dataset]);

  const loadSample = async (s) => {
    setBusy("data"); setError("");
    try {
      setDataset(await api.post(`/api/datasets/samples/${s.key}`));
      setSampleKey(s.key);
      if (!s.methods.includes(method)) setMethod(s.methods[0]);
    } catch (e) { setError(e.message); }
    setBusy("");
  };

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy("data"); setError("");
    try {
      setDataset(await api.upload(file));
      setSampleKey(null);
    } catch (err) { setError(err.message); }
    setBusy("");
    e.target.value = "";
  };

  const run = async () => {
    setBusy("run"); setError(""); setResult(null);
    const payload = { dataset_id: dataset.dataset_id };
    for (const f of METHODS[method].fields) {
      let v = params[f.key];
      if (v === "" || v === null || v === undefined || (Array.isArray(v) && !v.length && f.optional)) continue;
      if (f.type === "number") v = Number(v);
      if (f.type === "unitValue" || f.type === "groupValue") v = String(v);
      payload[f.key] = v;
    }
    try {
      setResult(await api.post(METHODS[method].endpoint, payload));
    } catch (e) { setError(e.message); }
    setBusy("");
  };

  const set = (k, v) => setParams((p) => ({ ...p, [k]: v }));
  const recommended = sample?.methods || [];

  return (
    <div className="stack">
      <Card title="1 · Choose data">
        <div className="sample-grid">
          {samples.map((s) => (
            <button key={s.key} className={`sample ${sampleKey === s.key ? "selected" : ""}`} onClick={() => loadSample(s)}>
              <strong>{s.title}</strong>
              <span>{s.description}</span>
            </button>
          ))}
          <label className="sample upload">
            <strong>Upload your own CSV</strong>
            <span>One row per user (experiments) or per unit / unit-period (observational).</span>
            <input type="file" accept=".csv" onChange={upload} />
          </label>
        </div>
        {busy === "data" && <p className="muted">Loading dataset…</p>}
        {dataset && <DatasetPreview dataset={dataset} />}
      </Card>

      {dataset && (
        <Card title="2 · Pick a method and map columns">
          <div className="method-picker">
            {Object.entries(FAMILIES).map(([fam, label]) => (
              <div key={fam}>
                <h4>{label}</h4>
                <div className="chips">
                  {Object.entries(METHODS).filter(([, m]) => m.family === fam).map(([key, m]) => (
                    <button key={key} className={`chip ${method === key ? "active" : ""} ${recommended.includes(key) ? "rec" : ""}`}
                      onClick={() => setMethod(key)} title={m.blurb}>
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <p className="muted">{METHODS[method].blurb}{recommended.length > 0 && " Highlighted methods suit this sample dataset."}</p>
          <div className="form-grid">
            {METHODS[method].fields.map((f) => (
              <ParamInput key={f.key} field={f} value={params[f.key]} dataset={dataset} params={params} onChange={(v) => set(f.key, v)} />
            ))}
          </div>
          <button className="primary" onClick={run} disabled={busy === "run"}>
            {busy === "run" ? "Running analysis…" : "Run analysis"}
          </button>
          {busy === "run" && ["bayesian", "psm", "dml"].includes(method) && (
            <p className="muted">MCMC sampling / model fitting can take a few seconds.</p>
          )}
          <ErrorBox error={error} />
        </Card>
      )}
      {!dataset && <ErrorBox error={error} />}
      {result && <Results result={result} />}
    </div>
  );
}

function ParamInput({ field: f, value, dataset, params, onChange }) {
  const cols = dataset.columns;
  const label = f.label + (f.optional ? " (optional)" : "");
  if (f.type === "column") {
    return (
      <Field label={label}>
        <select value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
          {f.optional && <option value="">— none —</option>}
          {cols.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
        </select>
      </Field>
    );
  }
  if (f.type === "columns") {
    const sel = value || [];
    return (
      <Field label={label}>
        <div className="checks">
          {cols.filter((c) => c.is_numeric || !f.numeric).map((c) => (
            <label key={c.name} className={sel.includes(c.name) ? "on" : ""}>
              <input type="checkbox" checked={sel.includes(c.name)}
                onChange={(e) => onChange(e.target.checked ? [...sel, c.name] : sel.filter((x) => x !== c.name))} />
              {c.name}
            </label>
          ))}
        </div>
      </Field>
    );
  }
  if (f.type === "groupValue" || f.type === "unitValue") {
    const src = f.type === "groupValue" ? params.group_col : params.unit_col;
    const options = cols.find((c) => c.name === src)?.sample_values || [];
    return (
      <Field label={label} hint={f.type === "groupValue" ? "Blank = detect automatically" : ""}>
        <input list={`dl-${f.key}`} value={value ?? ""} onChange={(e) => onChange(e.target.value)} />
        <datalist id={`dl-${f.key}`}>{options.map((o) => <option key={String(o)} value={String(o)} />)}</datalist>
      </Field>
    );
  }
  if (f.type === "select") {
    return (
      <Field label={label}>
        <select value={value} onChange={(e) => onChange(e.target.value)}>
          {f.options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </Field>
    );
  }
  if (f.type === "boolean") {
    return (
      <label className="toggle">
        <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />
        {f.label}
      </label>
    );
  }
  return (
    <Field label={label}>
      <input type="number" step={f.step || "any"} value={value ?? ""} onChange={(e) => onChange(e.target.value)} />
    </Field>
  );
}

function DatasetPreview({ dataset }) {
  const cols = useMemo(() => dataset.columns.slice(0, 12), [dataset]);
  return (
    <div className="preview">
      <p className="muted">
        <strong>{dataset.name}</strong> · {dataset.rows.toLocaleString()} rows · {dataset.columns.length} columns
      </p>
      <div className="table-wrap">
        <table>
          <thead><tr>{cols.map((c) => <th key={c.name}>{c.name}<small>{c.is_binary ? "binary" : c.dtype}</small></th>)}</tr></thead>
          <tbody>
            {dataset.preview.slice(0, 5).map((r, i) => (
              <tr key={i}>{cols.map((c) => <td key={c.name}>{typeof r[c.name] === "number" ? +r[c.name].toFixed(3) : String(r[c.name] ?? "")}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
