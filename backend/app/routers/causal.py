from fastapi import APIRouter

from ..core.store import store
from ..schemas import DiDRequest, DMLRequest, PSMRequest, SynthRequest
from ..services import causal

router = APIRouter(prefix="/api/causal", tags=["Causal inference (observational)"])


def _args(req):
    return req.model_dump(exclude={"dataset_id"})


@router.post("/psm")
def psm(req: PSMRequest):
    return causal.psm(store.get(req.dataset_id), **_args(req))


@router.post("/dml")
def dml(req: DMLRequest):
    return causal.dml(store.get(req.dataset_id), **_args(req))


@router.post("/did")
def did(req: DiDRequest):
    return causal.did(store.get(req.dataset_id), **_args(req))


@router.post("/synthetic-control")
def synthetic_control(req: SynthRequest):
    return causal.synthetic_control(store.get(req.dataset_id), **_args(req))
