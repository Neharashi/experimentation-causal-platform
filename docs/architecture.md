# Architecture

## System overview

![Architecture](architecture.png)


```mermaid
flowchart LR
    U[User / analyst] -->|upload CSV, pick method| FE

    subgraph FE[React frontend · Vite + Recharts]
        P[Design a test<br/>power calculator]
        A[Analyze<br/>data → method → results]
        G[Method guide]
    end

    FE -->|JSON over HTTP /api| API

    subgraph API[FastAPI backend]
        R1[routers/power]
        R2[routers/datasets]
        R3[routers/experiments]
        R4[routers/causal]
        ST[(In-memory<br/>DatasetStore · LRU)]
        R2 --> ST
        R3 --> ST
        R4 --> ST
    end

    subgraph SV[Service layer · pure Python, unit-tested]
        S1[power.py<br/>statsmodels]
        S2[frequentist.py<br/>scipy · statsmodels]
        S3[sequential.py<br/>mSPRT · O'Brien-Fleming]
        S4[bayesian.py<br/>PyMC NUTS]
        S5[causal.py<br/>DoWhy · EconML · statsmodels · scipy]
        S6[simulate.py]
    end

    R1 --> S1
    R3 --> S2 & S3 & S4
    R4 --> S5
    R2 --> S6
    DATA[(Bundled datasets<br/>LaLonde · Prop 99)] --> R2
```

## Request flow

```mermaid
sequenceDiagram
    participant UI as React UI
    participant API as FastAPI
    participant Store as DatasetStore
    participant Svc as Service
    UI->>API: POST /api/datasets/upload (CSV)
    API->>Store: parse + store DataFrame
    API-->>UI: dataset_id, columns, preview
    UI->>API: POST /api/causal/psm {dataset_id, columns...}
    API->>Store: get(dataset_id)
    API->>Svc: psm(df, ...)
    Svc-->>API: estimate, CI, balance, refutations, conclusion
    API-->>UI: JSON result
    UI->>UI: render stats, charts, plain-English conclusion
```

## Design decisions

| Decision | Why |
|---|---|
| Routers are thin; all statistics live in `services/` | Services are pure functions of a DataFrame, so they are unit-tested without HTTP and reusable from notebooks or scripts. |
| Every result includes a `conclusion` string and `warnings` | The "plain-English" requirement is met on the server, so any client (UI, notebook, Slack bot) gets the same interpretation. |
| `ValueError` → HTTP 422 with a readable message | Users see "Column 'x' not found" instead of a stack trace. |
| In-memory LRU dataset store (30 datasets) | Keeps the internal tool stateless and simple; swap for Redis/S3 when multi-instance. |
| DoWhy is the primary PSM estimator, a fast in-house matcher reproduces it | DoWhy gives identification + refuters; the in-house matcher (same propensity model) provides bootstrap CIs and balance diagnostics quickly. |
| DML nuisance models: EconML auto-selection ≤ 5k rows, gradient boosting above | Auto-selection gave correct CI coverage in simulation but is ~20× slower on large data. |
| Synthetic control implemented with `scipy.optimize` (SLSQP) | DoWhy/EconML do not ship synthetic control; the constrained least-squares problem is small and transparent. |
| O'Brien-Fleming constant found by Monte Carlo (cached) | Exact for any number of looks without extra dependencies; matches published tables (K=5: 2.04). |
| Frontend method forms are driven by `methods.js` config | Adding a method = one service, one route, one config entry, one result view. |
| One Docker image serves API and built UI | Single deploy target (Render, Railway, Fly, any VM). |
