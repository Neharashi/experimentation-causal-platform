# Experimentation & Causal Inference Platform

An internal tool that helps teams **design A/B tests, analyze them correctly, and estimate cause and effect when
experiments are not possible**. Upload a CSV, pick a method, and get a statistically sound result with charts and a
plain-English conclusion.

**Stack:** FastAPI · statsmodels · SciPy · PyMC · DoWhy · EconML · React (Vite + Recharts) · Docker · GitHub Actions

## Features

| Area | What it does |
|---|---|
| **Test design** | Sample-size and power calculator for conversion rates and means, unequal allocation, one/two-sided tests, test-duration estimate, power curve |
| **Classic analysis** | Welch t-test, chi-square test, confidence intervals, relative lift, effect size, automatic **sample-ratio-mismatch** check |
| **Multiple testing** | Bonferroni (family-wise error) and Benjamini-Hochberg (false discovery rate) across many metrics |
| **Sequential testing** | Safe peeking with **mSPRT always-valid p-values** and confidence sequences, plus **O'Brien-Fleming** group sequential boundaries |
| **Bayesian A/B** | PyMC Beta-Binomial and Normal models: P(B beats A), expected loss, credible interval for lift, ship/keep/continue recommendation, R-hat check |
| **Propensity score matching** | DoWhy estimate, bootstrap CI, covariate balance (SMD), overlap plot, three DoWhy **refutation tests**, EconML cross-check |
| **Double ML** | EconML LinearDML: ATE, ATT and heterogeneous effects by segment |
| **Difference-in-differences** | 2×2 or two-way fixed effects with clustered SEs, **event study** and parallel-trends test |
| **Synthetic control** | Constrained donor weights, actual vs synthetic, **placebo-in-space permutation test** |
| **Plain English** | Every result ships a written conclusion and warnings (e.g. weak balance, violated parallel trends) |

### Bundled datasets
Simulated A/B (Option 1), **LaLonde NSW** randomized and observational versions (Option 4), **California Proposition 99**
(Option 7), plus simulated panel and confounded datasets with known true effects. Any CSV can be uploaded — e.g. Cookie
Cats, Hillstrom or Card & Krueger data from Kaggle.

## Headline results

Full tables in [`docs/results.md`](docs/results.md) (reproduce with `python scripts/evaluate.py`).

- **Peeking:** checking a naive p-value 20 times gives a **29% false-positive rate**; mSPRT keeps it at **1%**, O'Brien-Fleming at ~5% with 92% power.
- **Power calculator:** empirical power within ±2 points of the 80% target in simulation.
- **LaLonde:** the naive observational estimate is **−$8,498**; propensity matching gives **+$1,707**, close to the experimental benchmark of **$1,794**.
- **Prop 99:** synthetic control estimates **−19.5 packs per capita (−24%)** after 1989 (placebo p = 0.077); DiD's parallel-trends test fails (p ≈ 1e-49), showing why synthetic control is the right tool.
- **Simulated confounding (true effect 2.0):** naive 3.55 → PSM 2.09 → DML 1.99.

## Quick start

### Option A — Docker (one command)
```bash
docker compose up --build
```
Open http://localhost:8000 (UI) and http://localhost:8000/docs (API docs).

### Option B — Local development

**Backend** (Python 3.11 – 3.12 recommended)
```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate     macOS/Linux: source venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

**Frontend** (Node 18+), in a second terminal
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173. The Vite dev server proxies `/api` to the backend on port 8000.

To serve everything from FastAPI instead, run `npm run build` once; the backend automatically serves `frontend/dist`.

> **Windows note:** PyMC compiles models with a C++ compiler. Without one it still works but the Bayesian endpoint is
> slower. Installing PyMC via `conda install -c conda-forge pymc` gives the fastest setup.

### Tests and validation
```bash
cd backend && pytest -q                # 31 unit + API tests
cd .. && python scripts/evaluate.py    # simulation study → docs/results.md
```

## Using the tool
1. **Analyze → Choose data:** load a sample dataset or upload a CSV (see `examples/`).
2. **Pick a method:** methods suited to the selected sample are highlighted; column mappings are pre-filled.
3. **Run analysis:** read the conclusion, check the warnings, explore the charts, download the JSON.
4. **Design a test:** plan sample size and duration before launching an experiment.
5. **Method guide:** which method fits which situation.

## Project structure
```
backend/
  app/
    main.py            FastAPI app, error handling, static UI hosting
    schemas.py         Pydantic request models
    core/              dataset store + bundled datasets
    routers/           power, datasets, experiments, causal
    services/          power, frequentist, sequential, bayesian, causal, simulate
    data/              LaLonde and Prop 99 CSVs
  tests/               pytest suite
frontend/src/
  methods.js           method → form configuration
  components/          Analyze, PowerCalculator, Results (all charts), Guide
scripts/evaluate.py    simulation-based validation
docs/                  architecture, API reference, results
examples/              sample CSVs to upload
```

## Documentation
- [Architecture & design decisions](docs/architecture.md)
- [API reference](docs/api.md)
- [Validation results](docs/results.md)

## Methods and references
- Kohavi, Tang & Xu — *Trustworthy Online Controlled Experiments* (2020)
- Johari, Pekelis & Walsh — *Always Valid Inference: Continuous Monitoring of A/B Tests* (2017) — mSPRT
- O'Brien & Fleming (1979); Lan & DeMets (1983) — group sequential designs
- Benjamini & Hochberg (1995) — false discovery rate
- Rosenbaum & Rubin (1983); Dehejia & Wahba (1999) — propensity scores, LaLonde data
- Chernozhukov et al. (2018) — double/debiased machine learning
- Abadie, Diamond & Hainmueller (2010) — synthetic control, Proposition 99

## Next steps
- Persist datasets and results (PostgreSQL / S3) and add user accounts
- CUPED variance reduction and ratio metrics (delta method)
- Multi-arm tests and Thompson-sampling bandits
- Covariate-augmented synthetic control and staggered-adoption DiD (Callaway-Sant'Anna)
