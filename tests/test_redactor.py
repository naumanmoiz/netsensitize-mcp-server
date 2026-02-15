"""Unit tests for the redaction engine."""

import re

import pytest

from redact_mcp.models import RedactMode
from redact_mcp.redactor import IPV4_RE, IPV6_RE, MAC_RE, RedactorEngine


DETERMINISTIC_SECRET = b"unit-test-deterministic-secret-000000"


# --- IPv4 Tests ---


class TestIPv4Replacement:
    def test_single_ipv4(self):
        engine = RedactorEngine()
        result, mapping = engine.redact("Host 192.168.1.10 is up")
        assert "192.168.1.10" not in result
        assert len(mapping) == 1
        assert "192.168.1.10" in mapping

    def test_multiple_different_ipv4(self):
        engine = RedactorEngine()
        result, mapping = engine.redact("10.0.0.1 and 10.0.0.2")
        assert "10.0.0.1" not in result
        assert "10.0.0.2" not in result
        assert len(mapping) == 2

    def test_duplicate_ipv4_same_replacement(self):
        engine = RedactorEngine()
        result, mapping = engine.redact("10.0.0.1 then 10.0.0.1 again")
        assert len(mapping) == 1
        replacements = IPV4_RE.findall(result)
        assert len(replacements) == 2
        assert replacements[0] == replacements[1]

    def test_boundary_ipv4_values(self):
        engine = RedactorEngine()
        result, mapping = engine.redact("from 0.0.0.0 to 255.255.255.255")
        assert "0.0.0.0" not in result
        assert "255.255.255.255" not in result
        assert len(mapping) == 2


# --- MAC Tests ---


class TestMACReplacement:
    def test_colon_separated_mac(self):
        engine = RedactorEngine()
        result, mapping = engine.redact("MAC 00:11:22:33:44:55")
        assert "00:11:22:33:44:55" not in result
        assert len(mapping) == 1

    def test_hyphen_separated_mac(self):
        engine = RedactorEngine()
        result, mapping = engine.redact("MAC AA-BB-CC-DD-EE-FF")
        assert "AA-BB-CC-DD-EE-FF" not in result
        assert len(mapping) == 1


# --- IPv6 Tests ---


class TestIPv6Replacement:
    def test_full_ipv6(self):
        engine = RedactorEngine()
        addr = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
        result, mapping = engine.redact(f"Host {addr} is up")
        assert addr not in result
        assert len(mapping) == 1

    def test_compressed_ipv6(self):
        engine = RedactorEngine()
        result, mapping = engine.redact("Link-local fe80::1 detected")
        assert "fe80::1" not in result
        assert len(mapping) == 1

    def test_loopback_ipv6(self):
        engine = RedactorEngine()
        result, mapping = engine.redact("Loopback ::1 active")
        assert "::1" not in result
        assert len(mapping) == 1


# --- Deterministic Mode Tests ---


class TestDeterministicMode:
    def test_same_input_same_output(self):
        engine = RedactorEngine(
            mode=RedactMode.deterministic,
            deterministic_secret=DETERMINISTIC_SECRET,
        )
        result1, _ = engine.redact("192.168.1.1")
        result2, _ = engine.redact("192.168.1.1")
        assert result1 == result2

    def test_different_requests_same_output(self):
        engine1 = RedactorEngine(
            mode=RedactMode.deterministic,
            deterministic_secret=DETERMINISTIC_SECRET,
        )
        engine2 = RedactorEngine(
            mode=RedactMode.deterministic,
            deterministic_secret=DETERMINISTIC_SECRET,
        )
        result1, _ = engine1.redact("192.168.1.1")
        result2, _ = engine2.redact("192.168.1.1")
        assert result1 == result2

    def test_replacement_is_valid_ipv4(self):
        engine = RedactorEngine(
            mode=RedactMode.deterministic,
            deterministic_secret=DETERMINISTIC_SECRET,
        )
        result, _ = engine.redact("192.168.1.1")
        assert IPV4_RE.fullmatch(result)


# --- No Mutation / Isolation Tests ---


class TestNoMutation:
    def test_no_cross_request_leakage(self):
        engine1 = RedactorEngine()
        engine1.redact("192.168.1.1")
        engine2 = RedactorEngine()
        _, mapping2 = engine2.redact("10.0.0.1")
        assert "192.168.1.1" not in mapping2

    def test_text_without_sensitive_data_unchanged(self):
        engine = RedactorEngine()
        text = "Hello, this is plain text with no addresses."
        result, mapping = engine.redact(text)
        assert result == text
        assert len(mapping) == 0


class TestSecurityProperties:
    def test_deterministic_requires_secret(self):
        with pytest.raises(ValueError):
            RedactorEngine(mode=RedactMode.deterministic, deterministic_secret=None)


# --- Mixed Pattern Tests ---


class TestMixedPatterns:
    def test_ipv4_and_mac_in_same_text(self):
        engine = RedactorEngine()
        text = "Server 192.168.1.10 has MAC 00:11:22:33:44:55"
        result, mapping = engine.redact(text)
        assert "192.168.1.10" not in result
        assert "00:11:22:33:44:55" not in result
        assert len(mapping) == 2
