import io

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(scope="module")
def ab_id():
    return client.post("/api/datasets/samples/simulated_ab").json()["dataset_id"]


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_power_endpoint():
    r = client.post("/api/power/sample-size", json={"baseline": 0.1, "mde": 0.1, "daily_traffic": 1000})
    assert r.status_code == 200 and r.json()["n_control"] > 14000


def test_upload_and_ttest():
    csv = "group,y\n" + "\n".join(f"{'A' if i % 2 else 'B'},{i % 7}" for i in range(200))
    up = client.post("/api/datasets/upload", files={"file": ("d.csv", io.BytesIO(csv.encode()), "text/csv")})
    assert up.status_code == 200 and up.json()["rows"] == 200
    r = client.post("/api/experiments/ttest", json={"dataset_id": up.json()["dataset_id"], "group_col": "group",
                                                     "metric_col": "y"})
    assert r.status_code == 200 and "conclusion" in r.json()


def test_experiment_endpoints(ab_id):
    base = {"dataset_id": ab_id, "group_col": "group", "metric_col": "converted"}
    assert client.post("/api/experiments/chisquare", json=base).json()["significant"]
    assert client.post("/api/experiments/sequential", json={**base, "time_col": "day"}).json()["stopped"]
    r = client.post("/api/experiments/sequential", json={**base, "procedure": "obrien_fleming", "looks": 4})
    assert len(r.json()["looks"]) == 4
    r = client.post("/api/experiments/multi-metric", json={"dataset_id": ab_id, "group_col": "group",
                                                            "metric_cols": ["converted", "revenue"]})
    assert len(r.json()["results"]) == 2


def test_causal_endpoints():
    pid = client.post("/api/datasets/samples/prop99").json()["dataset_id"]
    r = client.post("/api/causal/synthetic-control", json={"dataset_id": pid, "unit_col": "state",
                    "time_col": "year", "outcome_col": "cigsale", "treated_unit": "California",
                    "treatment_time": 1989, "placebo": False})
    assert r.status_code == 200 and r.json()["att"] < 0
    r = client.post("/api/causal/did", json={"dataset_id": pid, "outcome_col": "cigsale", "treated_col": "california",
                    "time_col": "year", "treatment_time": 1989, "unit_col": "state"})
    assert r.status_code == 200 and r.json()["estimate"] < 0


def test_errors_are_readable(ab_id):
    r = client.post("/api/experiments/ttest", json={"dataset_id": ab_id, "group_col": "nope", "metric_col": "x"})
    assert r.status_code == 422 and "not found" in r.json()["detail"]
    assert client.post("/api/experiments/ttest", json={"dataset_id": "missing", "group_col": "g",
                                                       "metric_col": "y"}).status_code == 404
