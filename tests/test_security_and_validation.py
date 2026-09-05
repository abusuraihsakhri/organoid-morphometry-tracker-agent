"""
Security and input validation tests for organoid-morphometry-tracker-agent.
"""
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from agents.base import (
    PHIGuard,
    AuditTrail,
    SecurityException,
    ResourceLimitExceededException,
    validate_input_string,
    validate_metric_value,
)
from agents.models import SystemTaskPayload


class TestAuditSecretKey:
    """Tests for AUDIT_SECRET_KEY enforcement."""

    def test_audit_trail_requires_key(self):
        """AuditTrail should raise RuntimeError when no key is provided."""
        original_key = os.environ.pop("AUDIT_SECRET_KEY", None)
        try:
            with pytest.raises(RuntimeError, match="AUDIT_SECRET_KEY environment variable must be set"):
                AuditTrail()
        finally:
            if original_key is not None:
                os.environ["AUDIT_SECRET_KEY"] = original_key

    def test_audit_trail_rejects_short_key(self):
        """AuditTrail should reject keys shorter than 16 characters."""
        with pytest.raises(RuntimeError, match="at least 16 characters"):
            AuditTrail(secret_key="short")

    def test_audit_trail_accepts_valid_key(self):
        """AuditTrail should accept a key of sufficient length."""
        trail = AuditTrail(secret_key="test-key-that-is-long-enough-32chars")
        assert trail is not None

    def test_audit_trail_uses_env_var(self):
        """AuditTrail should read key from environment variable."""
        os.environ["AUDIT_SECRET_KEY"] = "env-based-test-key-that-is-long-enough"
        try:
            trail = AuditTrail()
            assert trail is not None
        finally:
            os.environ.pop("AUDIT_SECRET_KEY", None)


class TestInputValidation:
    """Tests for input validation functions."""

    def test_validate_input_string_rejects_long_strings(self):
        """Should reject strings exceeding maximum length."""
        with pytest.raises(ResourceLimitExceededException, match="exceeds maximum allowed length"):
            validate_input_string("x" * 1001)

    def test_validate_input_string_accepts_valid(self):
        """Should accept strings within limits."""
        result = validate_input_string("valid-input")
        assert result == "valid-input"

    def test_validate_input_string_rejects_non_string(self):
        """Should reject non-string inputs."""
        with pytest.raises(SecurityException, match="must be a string"):
            validate_input_string(12345)

    def test_validate_metric_value_rejects_nan(self):
        """Should reject NaN values."""
        import math
        with pytest.raises(ResourceLimitExceededException, match="must be a finite number"):
            validate_metric_value(float("nan"))

    def test_validate_metric_value_rejects_infinity(self):
        """Should reject infinity values."""
        with pytest.raises(ResourceLimitExceededException, match="must be a finite number"):
            validate_metric_value(float("inf"))

    def test_validate_metric_value_rejects_huge_values(self):
        """Should reject values exceeding maximum magnitude."""
        with pytest.raises(ResourceLimitExceededException, match="exceeds maximum allowed value"):
            validate_metric_value(1e10)

    def test_validate_metric_value_accepts_valid(self):
        """Should accept normal numeric values."""
        result = validate_metric_value(42.5)
        assert result == 42.5


class TestSystemTaskPayloadValidation:
    """Tests for SystemTaskPayload input validation."""

    def test_valid_payload(self):
        """Should accept valid payload data."""
        payload = SystemTaskPayload(
            task_id="TASK-001",
            target_identifier="KEY-01",
            primary_metric=25.0,
            secondary_metric=10.0,
        )
        assert payload.task_id == "TASK-001"
        assert payload.primary_metric == 25.0

    def test_rejects_nan_metric(self):
        """Should reject NaN metric values."""
        with pytest.raises(Exception):
            SystemTaskPayload(
                task_id="TASK-001",
                target_identifier="KEY-01",
                primary_metric=float("nan"),
            )

    def test_rejects_infinite_metric(self):
        """Should reject infinite metric values."""
        with pytest.raises(Exception):
            SystemTaskPayload(
                task_id="TASK-001",
                target_identifier="KEY-01",
                primary_metric=float("inf"),
            )


class TestPHIGuardRedaction:
    """Tests for PHI guard redaction functionality."""

    def test_redact_phi_mrn(self):
        """Should redact MRN patterns."""
        result = PHIGuard.redact_phi("Patient MRN-12345678")
        assert "MRN-12345678" not in result
        assert "[REDACTED_IDENTIFIER]" in result

    def test_redact_phi_ssn(self):
        """Should redact SSN patterns."""
        result = PHIGuard.redact_phi("SSN: 123-45-6789")
        assert "123-45-6789" not in result
        assert "[REDACTED_IDENTIFIER]" in result

    def test_clean_text_unchanged(self):
        """Should not modify clean text."""
        clean = "Analytical specimen KEY-001 within normal parameters"
        result = PHIGuard.redact_phi(clean)
        assert result == clean
