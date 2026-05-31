"""AnthropicRemediationProvider tests with the SDK mocked at the seam.

No live network. The provider takes an injected ``client`` for tests, so we
never touch ``Anthropic(...)``.
"""

from __future__ import annotations

from typing import Any

import pytest

from cfn_auditor.advisor.anthropic import (
    AnthropicRemediationProvider,
    build_prompt,
)
from cfn_auditor.advisor.dto import FindingInput
from cfn_auditor.advisor.rag import retrieve
from cfn_auditor.models import Severity
from cfn_auditor.rules.remediation import REMEDIATION_BY_RULE_ID

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _TextBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class _Message:
    def __init__(self, text: str) -> None:
        self.content = [_TextBlock(text)]


class _MessagesAPI:
    def __init__(self, response_text: str | None = None, error: Exception | None = None) -> None:
        self._text = response_text
        self._error = error
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _Message:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        assert self._text is not None
        return _Message(self._text)


class _FakeClient:
    def __init__(self, response_text: str | None = None, error: Exception | None = None) -> None:
        self.messages = _MessagesAPI(response_text=response_text, error=error)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _finding(
    rule_id: str = "CFN_S3_001",
    resource_type: str = "AWS::S3::Bucket",
    *,
    finding_id: int = 11,
    message: str = "S3 bucket has no encryption.",
) -> FindingInput:
    return FindingInput(
        finding_id=finding_id,
        rule_id=rule_id,
        severity=Severity.HIGH,
        resource_logical_id="MyBucket",
        resource_type=resource_type,
        message=message,
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_constructor_requires_api_key() -> None:
    """Empty api_key raises so the factory can fall back to static."""
    with pytest.raises(ValueError, match="api_key"):
        AnthropicRemediationProvider(api_key="", model="claude-test")


# ---------------------------------------------------------------------------
# Prompt grounding
# ---------------------------------------------------------------------------


def test_built_prompt_contains_retrieved_grounding_context() -> None:
    """The user prompt embeds the retrieved corpus passage(s) verbatim."""
    finding = _finding()
    passages = retrieve(finding, top_k=1)
    prompt = build_prompt(finding, passages)
    assert passages, "fixture sanity: corpus should yield at least one passage"
    assert passages[0].body[:60] in prompt
    assert "Rule ID: CFN_S3_001" in prompt
    assert "AWS::S3::Bucket" in prompt
    assert "Resource logical ID: MyBucket" in prompt


def test_provider_prompt_is_grounded_on_call() -> None:
    """The actual SDK call carries the grounded user message."""
    client = _FakeClient(response_text="Use SSE-KMS with a customer-managed key.")
    provider = AnthropicRemediationProvider(
        api_key="key",
        model="claude-test",
        client=client,
    )
    provider.advise([_finding()])
    assert len(client.messages.calls) == 1
    call = client.messages.calls[0]
    assert call["model"] == "claude-test"
    user_message = call["messages"][0]["content"]
    assert "Control context" in user_message
    assert "BucketEncryption" in user_message  # from the s3.md corpus passage


# ---------------------------------------------------------------------------
# Happy path: AdviceItem with source "llm:{model}"
# ---------------------------------------------------------------------------


def test_advise_returns_llm_text_with_model_source() -> None:
    """Mocked LLM text is parsed into the AdviceItem; source labels the model."""
    client = _FakeClient(response_text="  Set BucketEncryption to AES256.  ")
    provider = AnthropicRemediationProvider(
        api_key="key",
        model="claude-sonnet-4-5",
        client=client,
    )
    items = provider.advise([_finding()])
    assert len(items) == 1
    item = items[0]
    assert item.remediation == "Set BucketEncryption to AES256."
    assert item.source == "llm:claude-sonnet-4-5"
    assert item.finding_id == 11


def test_advise_preserves_input_order_across_multiple_findings() -> None:
    """Order of findings → order of items, regardless of rule_id."""
    client = _FakeClient(response_text="ok")
    provider = AnthropicRemediationProvider(api_key="key", model="claude-test", client=client)
    inputs = [
        _finding("CFN_RDS_002", "AWS::RDS::DBInstance", finding_id=1),
        _finding("CFN_S3_001", "AWS::S3::Bucket", finding_id=2),
        _finding("CFN_CT_001", "AWS::CloudTrail::Trail", finding_id=3),
    ]
    items = provider.advise(inputs)
    assert [i.finding_id for i in items] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Per-finding fail-open to static
# ---------------------------------------------------------------------------


def test_llm_failure_falls_back_to_static_for_that_finding() -> None:
    """A raised exception during the SDK call → static remediation, source 'static'."""
    client = _FakeClient(error=RuntimeError("rate-limited"))
    provider = AnthropicRemediationProvider(api_key="key", model="claude-test", client=client)
    items = provider.advise([_finding()])
    assert len(items) == 1
    item = items[0]
    assert item.remediation == REMEDIATION_BY_RULE_ID["CFN_S3_001"]
    assert item.source == "static"


def test_llm_partial_failure_does_not_abort_call() -> None:
    """One failing finding does not break the others — fail-open per finding.

    We swap the messages API after the first call so the first item
    succeeds (LLM source) and the second errors (static fallback).
    """

    class _Flaky(_MessagesAPI):
        def __init__(self) -> None:
            super().__init__(response_text="grounded llm output")
            self._calls = 0

        def create(self, **kwargs: Any) -> _Message:
            self._calls += 1
            self.calls.append(kwargs)
            if self._calls == 2:
                raise RuntimeError("boom")
            return _Message("grounded llm output")

    class _ClientWithFlaky:
        def __init__(self) -> None:
            self.messages = _Flaky()

    provider = AnthropicRemediationProvider(
        api_key="key",
        model="claude-test",
        client=_ClientWithFlaky(),
    )
    items = provider.advise(
        [
            _finding("CFN_S3_001", "AWS::S3::Bucket", finding_id=1),
            _finding("CFN_RDS_002", "AWS::RDS::DBInstance", finding_id=2),
        ]
    )
    assert len(items) == 2
    assert items[0].source == "llm:claude-test"
    assert items[0].remediation == "grounded llm output"
    assert items[1].source == "static"
    assert items[1].remediation == REMEDIATION_BY_RULE_ID["CFN_RDS_002"]


def test_response_with_no_text_block_falls_back_to_static() -> None:
    """A malformed response → static fallback for that finding."""

    class _EmptyMessages:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def create(self, **kwargs: Any) -> Any:
            self.calls.append(kwargs)
            return _Message("")  # one block but empty text after strip → falsy

    class _Client:
        def __init__(self) -> None:
            self.messages = _EmptyMessages()

    provider = AnthropicRemediationProvider(api_key="key", model="claude-test", client=_Client())
    item = provider.advise([_finding()])[0]
    assert item.source == "static"
    assert item.remediation == REMEDIATION_BY_RULE_ID["CFN_S3_001"]
