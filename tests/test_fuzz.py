"""Fuzz tests for the redactor using Hypothesis."""

from hypothesis import given, strategies as st

from redact_mcp.redactor import RedactorEngine


@given(st.text())
def test_redactor_handles_arbitrary_text(input_text: str):
    engine = RedactorEngine()
    redacted, mapping = engine.redact(input_text)

    assert isinstance(redacted, str)
    for original, replacement in mapping.items():
        assert original != replacement
        assert original not in redacted
