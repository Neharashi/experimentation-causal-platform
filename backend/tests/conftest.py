import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.simulate import simulate_ab, simulate_did, simulate_observational  # noqa: E402


@pytest.fixture(scope="session")
def ab():
    return simulate_ab(n_per_group=20000, seed=42)


@pytest.fixture(scope="session")
def ab_null():
    return simulate_ab(n_per_group=5000, relative_lift=0.0, revenue_lift=0.0, seed=3)


@pytest.fixture(scope="session")
def panel():
    return simulate_did(effect=5.0)


@pytest.fixture(scope="session")
def obs():
    return simulate_observational(ate=2.0)
