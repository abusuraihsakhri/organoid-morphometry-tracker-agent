"""Focused regression coverage for integrity, input handling and browser delivery."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from agents.api import app
from agents.base import AuditTrail, SecurityException, ResourceLimitExceededException
from agents.models import SystemTaskPayload

KEY = "test-signing-key-only-for-regression-123"

def test_hmac_detects_tampering():
    trail = AuditTrail(secret_key=KEY)
    trail.log("worker", "system", "CREATED", {"status": "OK"})
    trail.log("worker", "system", "UPDATED", {"status": "OK"})
    assert trail.verify_integrity()
    trail.logs[1]["actor"] = "imposter"
    assert not trail.verify_integrity()

def test_hmac_detects_first_entry_edit():
    trail = AuditTrail(secret_key=KEY)
    trail.log("worker", "system", "CREATED", {"status": "OK"})
    trail.logs[0]["payload_hash"] = "0" * 64
    assert not trail.verify_integrity()

def test_audit_getter_is_defensive_copy():
    trail = AuditTrail(secret_key=KEY)
    trail.log("worker", "system", "CREATED", {"status": "OK"})
    trail.get_trail()[0]["actor"] = "changed"
    assert trail.verify_integrity()

def test_audit_actor_cannot_contain_phi():
    with pytest.raises(SecurityException):
        AuditTrail(secret_key=KEY).log("MRN-123456", "system", "CREATED", {"status": "OK"})

def test_attributes_cannot_contain_sensitive_identifiers():
    with pytest.raises(ValueError):
        SystemTaskPayload(task_id="SYNTH", target_identifier="SYNTH", primary_metric=1,
                          attributes={"contact": "person@example.org"})

def test_reject_bool_metric():
    with pytest.raises(ResourceLimitExceededException):
        SystemTaskPayload(task_id="SYNTH", target_identifier="SYNTH", primary_metric=True)

def test_browser_app_served_at_root():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "Organoid Metric Screening" in response.text

def test_phi_audit_api_rejected_cleanly():
    response = TestClient(app).post("/api/audit", json={"task_id": "MRN-123456",
                "target_identifier": "SYNTH", "primary_metric": 1.0})
    assert response.status_code == 400

def test_pages_copy_matches_api_page():
    root = Path(__file__).parent.parent
    assert (root / "docs/index.html").read_bytes() == (root / "web/index.html").read_bytes()
    assert (root / "web/index.html").read_bytes() == (root / "agents/static/index.html").read_bytes()

def test_protected_api_endpoints(monkeypatch):
    monkeypatch.setenv("AUDIT_API_TOKEN", "test-private-token")
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/api/audit/logs").status_code == 401
    assert client.get("/metrics/prometheus").status_code == 401
    response = client.get("/metrics/prometheus", headers={"Authorization": "Bearer test-private-token"})
    assert response.status_code == 200
    assert "system_tasks_total" in response.text


def test_batch_skips_phi_and_invalid_values(tmp_path):
    from cli import main
    input_file = tmp_path / "input.csv"
    output_file = tmp_path / "result.csv"
    input_file.write_text("task_id,target_identifier,primary_metric,secondary_metric,status_descriptor\n"
                          "GOOD,ORG-01,20,3,NOMINAL\n"
                          "BAD,MRN-123456,20,3,NOMINAL\n"
                          "HUGE,ORG-02,10000000000,1,NOMINAL\n", encoding="utf-8")
    assert main(["batch", "-i", str(input_file), "-o", str(output_file)]) == 0
    data = output_file.read_text(encoding="utf-8")
    assert "GOOD" in data and "BAD" not in data and "HUGE" not in data


def test_optional_real_llm_provider_never_silently_mocked():
    from agents.llm_factory import LLMFactory
    with pytest.raises(ValueError, match="Only the deterministic mock"):
        LLMFactory.create("openai")


def test_frontier_payload_phi_guard():
    from organoid_vision.models import FrontierPayload
    with pytest.raises(SecurityException):
        FrontierPayload("SYNTH", "MRN-123456", 1, 2, "NOMINAL")

def test_container_healthcheck_needs_no_curl():
    root = Path(__file__).parent.parent
    assert "curl" not in (root / "docker-compose.yml").read_text(encoding="utf-8")
    assert "urllib.request" in (root / "Dockerfile").read_text(encoding="utf-8")
