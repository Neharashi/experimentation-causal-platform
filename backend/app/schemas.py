from typing import Literal, Optional

from pydantic import BaseModel, Field

Alternative = Literal["two-sided", "larger", "smaller"]


class PowerBase(BaseModel):
    metric_type: Literal["proportion", "mean"] = "proportion"
    baseline: float = Field(0.10, description="Baseline conversion rate or mean")
    mde: float = Field(0.10, description="Minimum detectable effect")
    mde_type: Literal["relative", "absolute"] = "relative"
    std: Optional[float] = Field(None, gt=0, description="Standard deviation (mean metrics)")
    alpha: float = Field(0.05, gt=0, lt=0.5)
    ratio: float = Field(1.0, gt=0, description="Treatment / control size ratio")
    alternative: Alternative = "two-sided"


class SampleSizeRequest(PowerBase):
    power: float = Field(0.8, gt=0.5, lt=1)
    daily_traffic: Optional[int] = Field(None, gt=0)


class PowerRequest(PowerBase):
    n_per_group: int = Field(1000, gt=1)


class SimulateRequest(BaseModel):
    kind: Literal["ab", "did", "observational"] = "ab"
    n_per_group: int = Field(5000, ge=50, le=500_000)
    baseline_rate: float = Field(0.10, gt=0, lt=1)
    relative_lift: float = Field(0.10, ge=-0.9, le=5)
    n_days: int = Field(14, ge=1, le=120)
    effect: float = 5.0
    seed: int = 42


class GroupRequest(BaseModel):
    dataset_id: str
    group_col: str
    control: Optional[str] = None
    treatment: Optional[str] = None
    alpha: float = Field(0.05, gt=0, lt=0.5)


class TwoGroupRequest(GroupRequest):
    metric_col: str


class TTestRequest(TwoGroupRequest):
    alternative: Alternative = "two-sided"


class MultiMetricRequest(GroupRequest):
    metric_cols: list[str]
    correction: Literal["bonferroni", "fdr_bh"] = "fdr_bh"


class CorrectionRequest(BaseModel):
    p_values: list[float]
    alpha: float = Field(0.05, gt=0, lt=0.5)
    method: Literal["bonferroni", "fdr_bh"] = "fdr_bh"


class SequentialRequest(TwoGroupRequest):
    procedure: Literal["msprt", "obrien_fleming"] = "msprt"
    time_col: Optional[str] = None
    looks: int = Field(50, ge=2, le=500)
    tau: Optional[float] = Field(None, gt=0)


class BayesianRequest(TwoGroupRequest):
    draws: int = Field(2000, ge=200, le=20000)
    prior_alpha: float = Field(1.0, gt=0)
    prior_beta: float = Field(1.0, gt=0)
    loss_threshold: float = Field(0.01, gt=0)


class CausalBase(BaseModel):
    dataset_id: str
    treatment_col: str
    outcome_col: str
    covariates: list[str]
    alpha: float = Field(0.05, gt=0, lt=0.5)


class PSMRequest(CausalBase):
    estimand: Literal["att", "ate"] = "att"
    refute: bool = True
    dml: bool = True


class DMLRequest(CausalBase):
    modifier_col: Optional[str] = None


class DiDRequest(BaseModel):
    dataset_id: str
    outcome_col: str
    treated_col: str
    time_col: str
    post_col: Optional[str] = None
    treatment_time: Optional[float] = None
    unit_col: Optional[str] = None
    alpha: float = Field(0.05, gt=0, lt=0.5)


class SynthRequest(BaseModel):
    dataset_id: str
    unit_col: str
    time_col: str
    outcome_col: str
    treated_unit: str
    treatment_time: float
    placebo: bool = True
