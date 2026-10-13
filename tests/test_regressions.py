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
