"""#30 / API-1 / G3: Schemathesis against the host's OpenAPI schema. Skips when schemathesis is not installed.

Two runs: (1) receivers healthy (fake ptys): every check, including no 5xx; (2) no receivers at all: the declared
degraded statuses (503/504) are the only 5xx allowed. Responses must always match the schema.
"""
import os
import sys

import pytest

if os.environ.get("CI"):
    import schemathesis  # CI must run this, never skip it
else:
    schemathesis = pytest.importorskip("schemathesis")
from schemathesis.specs.openapi.checks import positive_data_acceptance  # noqa: E402
from schemathesis.checks import not_a_server_error  # noqa: E402
from hypothesis import HealthCheck, settings  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from host.app import app  # noqa: E402
from test_host_resilience import GOOD, Fake  # noqa: E402

pytestmark = pytest.mark.timeout(300)

schema = schemathesis.openapi.from_asgi("/openapi.json", app)
CFG = settings(max_examples=200, deadline=None, suppress_health_check=list(HealthCheck))


def declared_degraded(ctx, response, case):
    """Allow only the 5xx the schema documents for this operation (a dead or absent receiver)."""
    if response.status_code >= 500 and response.status_code not in (502, 503, 504):
        raise AssertionError(f"undocumented server error {response.status_code}")
    if response.status_code >= 500:
        declared = case.operation.definition.raw.get("responses", {})
        assert str(response.status_code) in declared, f"{response.status_code} not declared"


@pytest.fixture(scope="module")
def healthy():
    mods = [Fake(replies={**GOOD, "status": "ok locked=0 rssi=-60 loss=0.000 batt=90 peak=-12 clip=0 temp=0"}) for _ in range(8)]
    old = app.state.ports
    app.state.ports = [m.path for m in mods]
    yield
    app.state.ports = old
    for m in mods:
        m.alive = False


def semantic(case):
    """PUT /rx/{n}/pair must match channel_plan.yaml (API-3): a schema-valid body is legitimately 422 (and n > 8 is 404)."""
    return [positive_data_acceptance] if case.operation.label == "PUT /rx/{n}/pair" else []


@schema.parametrize()
@CFG
def test_healthy_receivers(case, healthy):
    app.state.scan_cache = None
    case.call_and_validate(excluded_checks=semantic(case))  # all checks: not_a_server_error, status/content-type/schema conformance, ...


@schema.parametrize()
@CFG
def test_no_receivers(case):
    old = app.state.ports
    app.state.ports, app.state.scan_cache = [], None
    try:
        case.call_and_validate(additional_checks=[declared_degraded], excluded_checks=[not_a_server_error, *semantic(case)])
    finally:
        app.state.ports = old
