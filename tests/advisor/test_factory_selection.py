"""Factory selection: static vs Anthropic, with construction-failure fallback."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest

from cfn_auditor.advisor import (
    AnthropicRemediationProvider,
    StaticRemediationProvider,
    get_provider,
)
from cfn_auditor.advisor.dto import AdviceItem, FindingInput
from cfn_auditor.config import get_settings


def _set_llm_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> None:
    if provider is None:
        monkeypatch.delenv("CFN_AUDITOR_LLM_PROVIDER", raising=False)
    else:
        monkeypatch.setenv("CFN_AUDITOR_LLM_PROVIDER", provider)
    if api_key is None:
        monkeypatch.delenv("CFN_AUDITOR_LLM_API_KEY", raising=False)
    else:
        monkeypatch.setenv("CFN_AUDITOR_LLM_API_KEY", api_key)
    if model is None:
        monkeypatch.delenv("CFN_AUDITOR_LLM_MODEL", raising=False)
    else:
        monkeypatch.setenv("CFN_AUDITOR_LLM_MODEL", model)
    get_settings.cache_clear()


def test_factory_returns_static_when_llm_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No env config → StaticRemediationProvider, name 'static'."""
    _set_llm_env(monkeypatch)
    try:
        provider = get_provider()
        assert isinstance(provider, StaticRemediationProvider)
        assert provider.name == "static"
    finally:
        get_settings.cache_clear()


def test_factory_returns_anthropic_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider=anthropic + key + model → AnthropicRemediationProvider."""
    _set_llm_env(
        monkeypatch,
        provider="anthropic",
        api_key="topsecret",
        model="claude-sonnet-4-5",
    )
    # Avoid hitting the real SDK by monkeypatching the symbol that the
    # factory's deferred import resolves.
    captured: dict[str, Any] = {}

    class _DummyClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("cfn_auditor.advisor.anthropic.Anthropic", _DummyClient)
    try:
        provider = get_provider()
    finally:
        get_settings.cache_clear()

    assert isinstance(provider, AnthropicRemediationProvider)
    assert provider.name == "anthropic"
    # Sanity: the key flowed through; the model is configurable, never hardcoded.
    assert captured.get("api_key") == "topsecret"


def test_factory_falls_back_to_static_on_construction_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anthropic init explosion → fallback to static; no raise reaches the caller."""
    _set_llm_env(
        monkeypatch,
        provider="anthropic",
        api_key="topsecret",
        model="claude-test",
    )

    def _explode(**_kwargs: Any) -> None:
        raise RuntimeError("network unreachable")

    monkeypatch.setattr("cfn_auditor.advisor.anthropic.Anthropic", _explode)
    try:
        provider = get_provider()
    finally:
        get_settings.cache_clear()

    assert isinstance(provider, StaticRemediationProvider)


def test_factory_falls_back_to_static_for_unknown_provider_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown CFN_AUDITOR_LLM_PROVIDER value → static, with a warning logged."""
    _set_llm_env(
        monkeypatch,
        provider="cohere",  # not implemented yet
        api_key="x",
        model="m",
    )
    try:
        provider = get_provider()
    finally:
        get_settings.cache_clear()

    assert isinstance(provider, StaticRemediationProvider)


def test_factory_falls_back_when_provider_set_but_no_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider env set without a key → still static (the contract is both-or-none)."""
    _set_llm_env(monkeypatch, provider="anthropic", api_key=None)
    try:
        provider = get_provider()
    finally:
        get_settings.cache_clear()

    assert isinstance(provider, StaticRemediationProvider)


def test_remediation_provider_protocol_is_satisfied_by_anthropic_provider() -> None:
    """The Anthropic provider implements RemediationProvider structurally."""
    from cfn_auditor.advisor.provider import RemediationProvider

    class _DummyClient:
        class _Messages:
            @staticmethod
            def create(**_kwargs: Any) -> Any:
                raise RuntimeError("unused")

        messages = _Messages()

    provider = AnthropicRemediationProvider(
        api_key="key", model="claude-test", client=_DummyClient()
    )
    assert isinstance(provider, RemediationProvider)
    # Sanity: the protocol method exists with the right shape.
    assert callable(provider.advise)
    # Avoid an unused-import warning for the typing of advise(findings).
    _ = (AdviceItem, FindingInput, Iterable)
