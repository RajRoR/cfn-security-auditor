"""Provider interface + factory selector.

The :class:`RemediationProvider` Protocol is the narrow seam the advisor
endpoint depends on. The factory (:func:`get_provider`) reads config and
returns the active provider. Today supports:

  * No LLM configured → :class:`StaticRemediationProvider`.
  * ``CFN_AUDITOR_LLM_PROVIDER`` = ``anthropic`` + ``CFN_AUDITOR_LLM_API_KEY``
    set → :class:`AnthropicRemediationProvider`.

Construction failures (e.g. invalid SDK init) fall back to the static
provider; the API never breaks because the LLM is misconfigured.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from cfn_auditor.advisor.dto import AdviceItem, FindingInput
from cfn_auditor.advisor.static import StaticRemediationProvider
from cfn_auditor.config import get_settings

__all__ = ["RemediationProvider", "get_provider"]

logger = logging.getLogger(__name__)


@runtime_checkable
class RemediationProvider(Protocol):
    """Returns one remediation per finding."""

    name: str

    def advise(self, findings: Iterable[FindingInput]) -> list[AdviceItem]:
        """Produce :class:`AdviceItem` for each finding, preserving order."""
        ...


def get_provider() -> RemediationProvider:
    """Return the active provider for the current configuration.

    Selection rules:

    * No LLM provider/key configured → :class:`StaticRemediationProvider`.
    * ``CFN_AUDITOR_LLM_PROVIDER`` = ``anthropic`` + key present →
      :class:`AnthropicRemediationProvider`. Construction failure (missing
      SDK, invalid key shape) is logged and falls back to static.
    """
    settings = get_settings()
    llm_provider_name: str | None = settings.llm_provider
    llm_api_key: str | None = settings.llm_api_key
    if not llm_provider_name or not llm_api_key:
        return StaticRemediationProvider()

    if llm_provider_name.lower() == "anthropic":
        try:
            from cfn_auditor.advisor.anthropic import AnthropicRemediationProvider

            return AnthropicRemediationProvider(
                api_key=llm_api_key,
                model=settings.llm_model,
            )
        except Exception as exc:
            logger.warning(
                "Failed to construct AnthropicRemediationProvider (%s); " "falling back to static.",
                type(exc).__name__,
            )
            return StaticRemediationProvider()

    logger.warning(
        "Unknown CFN_AUDITOR_LLM_PROVIDER %r; falling back to static.",
        llm_provider_name,
    )
    return StaticRemediationProvider()
