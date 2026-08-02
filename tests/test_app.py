"""Smoke tests for the generated application.

These exist so a freshly created project has a green test suite to build on,
and so a broken bootstrap is caught immediately rather than at the first
request.
"""

from __future__ import annotations



def test_health_endpoint_reports_ok(client):
    """The health probe returns 200 with every dependency reachable."""
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["app"] == "ok"
    assert payload["checks"]["database"] == "ok"


def test_api_root_describes_the_service(client):
    """The API root returns the service name and version."""
    response = client.get("/api/")

    assert response.status_code == 200
    assert response.json()["name"] == "Starter"


def test_openapi_schema_is_served(client):
    """The generated OpenAPI document is available and lists our routes."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/health" in response.json()["paths"]
