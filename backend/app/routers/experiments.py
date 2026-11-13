from fastapi import APIRouter

from ..core.store import store
from ..schemas import (BayesianRequest, CorrectionRequest, MultiMetricRequest, SequentialRequest,
                       TTestRequest, TwoGroupRequest)
from ..services import bayesian, frequentist, sequential

router = APIRouter(prefix="/api/experiments", tags=["Experiment analysis"])


def _args(req, *exclude):
    return req.model_dump(exclude={"dataset_id", *exclude})


@router.post("/ttest")
def ttest(req: TTestRequest):
    return frequentist.ttest(store.get(req.dataset_id), **_args(req))


@router.post("/chisquare")
def chisquare(req: TwoGroupRequest):
    return frequentist.chisquare(store.get(req.dataset_id), **_args(req))


@router.post("/multi-metric")
def multi_metric(req: MultiMetricRequest):
    return frequentist.multi_metric(store.get(req.dataset_id), **_args(req))


@router.post("/correct")
def correct(req: CorrectionRequest):
    return frequentist.correct_pvalues(req.p_values, req.alpha, req.method)


@router.post("/sequential")
def run_sequential(req: SequentialRequest):
    df = store.get(req.dataset_id)
    if req.procedure == "obrien_fleming":
        return sequential.group_sequential(df, **_args(req, "procedure", "tau"),)
    return sequential.msprt(df, **_args(req, "procedure"))


@router.post("/bayesian")
def run_bayesian(req: BayesianRequest):
    return bayesian.bayesian_ab(store.get(req.dataset_id), **_args(req, "alpha"))
