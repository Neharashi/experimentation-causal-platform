from fastapi import APIRouter, File, UploadFile

from ..core.datasets import list_samples, load_sample
from ..core.store import store
from ..schemas import SimulateRequest
from ..services.simulate import simulate_ab, simulate_did, simulate_observational

router = APIRouter(prefix="/api/datasets", tags=["Datasets"])


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise ValueError("Only .csv files are supported.")
    dataset_id = store.add_csv(await file.read(), file.filename)
    return store.summary(dataset_id)


@router.get("/samples")
def samples():
    return list_samples()


@router.post("/samples/{key}")
def load(key: str):
    return store.summary(store.add(load_sample(key), key))


@router.post("/simulate")
def simulate(req: SimulateRequest):
    if req.kind == "ab":
        df = simulate_ab(req.n_per_group, req.baseline_rate, req.relative_lift, n_days=req.n_days, seed=req.seed)
    elif req.kind == "did":
        df = simulate_did(effect=req.effect, seed=req.seed)
    else:
        df = simulate_observational(n=2 * req.n_per_group, ate=req.effect, seed=req.seed)
    return store.summary(store.add(df, f"simulated_{req.kind}"))


@router.get("/{dataset_id}")
def summary(dataset_id: str):
    return store.summary(dataset_id)
