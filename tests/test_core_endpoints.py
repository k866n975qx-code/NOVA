

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    # BaseResponse shape
    assert body["status"] == "ok"
    assert "data" in body
    assert "meta" in body

    meta = body["meta"]
    # Meta should at least carry a timestamp
    assert "timestamp" in meta
    # Version fields may be None/unknown, but keys should exist
    assert "nova_version" in meta
    assert "build" in meta


def test_status_endpoint():
    response = client.get("/status")
    assert response.status_code == 200

    body = response.json()
    # Raw dict shape, not wrapped
    for key in ["system", "version", "build", "environment", "status", "uptime_seconds"]:
        assert key in body

    assert isinstance(body["uptime_seconds"], int)
    assert body["status"] == "online"


def test_version_endpoint():
    response = client.get("/version")
    assert response.status_code == 200

    body = response.json()
    for key in ["nova_version", "build_date", "api_schema_version", "master_doc_version"]:
        assert key in body


def test_actions_handshake_endpoint():
    response = client.get("/actions/handshake")
    assert response.status_code == 200

    body = response.json()
    # BaseResponse wrapper again
    assert body["status"] == "ok"
    assert "data" in body
    assert "meta" in body

    data = body["data"]
    assert "nova_version" in data
    assert "master_doc_version" in data

    supported = data.get("supported_domains", [])
    # Should be a non-empty list of domains
    assert isinstance(supported, list)
    assert len(supported) > 0
    assert "finance" in supported