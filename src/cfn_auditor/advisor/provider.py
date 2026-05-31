"""Provider interface + factory selector.

The :class:`RemediationProvider` Protocol is the narrow seam the advisor
endpoint depends on. The factory (:func:`get_provider`) reads config and
returns the active provider; today that is always
:class:`StaticRemediationProvider` because no LLM provider is configured
yet. The LLM branch lands in part 2.
"""

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from cfn_auditor.advisor.dto import AdviceItem, FindingInput
from cfn_auditor.advisor.static import StaticRemediationProvider
from cfn_auditor.config import get_settings

__all__ = ["RemediationProvider", "get_provider"]


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
      * (Future, part 2) ``CFN_AUDITOR_LLM_PROVIDER`` set + key present →
        the configured LLM provider, falling back to static on failure.

    The settings reads are deliberately optional via ``getattr`` so adding a
    new field in part 2 does not require a migration of the in-memory
    :class:`~cfn_auditor.config.Settings` shape this turn.
    """
    settings = get_settings()
    llm_provider_name: str | None = getattr(settings, "llm_provider", None)
    llm_api_key: str | None = getattr(settings, "llm_api_key", None)
    if llm_provider_name and llm_api_key:  # pragma: no cover - LLM seam (part 2)
        # TODO(advisor part 2): construct and return the configured LLM
        # provider here, with a fall-back to static on initialisation failure.
        # Until that lands, we deliberately bail to static so this seam is
        # exercised at runtime by any caller that mistakenly enables the
        # config without the implementation.
        return StaticRemediationProvider()
    return StaticRemediationProvider()
