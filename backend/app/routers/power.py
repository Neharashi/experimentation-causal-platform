from fastapi import APIRouter

from ..schemas import PowerRequest, SampleSizeRequest
from ..services import power

router = APIRouter(prefix="/api/power", tags=["Design: power & sample size"])


@router.post("/sample-size")
def sample_size(req: SampleSizeRequest):
    return power.sample_size(**req.model_dump())


@router.post("/power")
def achieved_power(req: PowerRequest):
    return power.achieved_power(**req.model_dump())
