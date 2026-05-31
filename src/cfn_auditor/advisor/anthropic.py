"""Anthropic-backed remediation provider, grounded by the in-repo RAG corpus.

Implements :class:`cfn_auditor.advisor.RemediationProvider`. For every
finding:

  1. Retrieve the top corpus passage(s) keyed to the rule.
  2. Build a prompt that pins the model to the retrieved control context
     and the finding, with an explicit instruction not to invent material
     beyond what was provided.
  3. Call Anthropic with the configured model.
  4. Parse the response text into the remediation string for an
     :class:`AdviceItem` whose ``source`` reflects actual provenance
     (``"llm:{model}"``).

Resilience (fail-open, non-negotiable):

  * Per-finding LLM/parse failures fall back to the canonical static
    remediation for that finding, with ``source = "static"``. The advice
    call as a whole still returns successfully.
  * Construction failures (missing key, SDK init error) are raised so the
    factory can fall back to the static provider — see :func:`get_provider`.

The Anthropic SDK is imported at module top-level. Tests mock the module-
level ``Anthropic`` symbol via ``monkeypatch`` so the network is never
touched.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from anthropic import Anthropic

from cfn_auditor.advisor.dto import AdviceItem, FindingInput
from cfn_auditor.advisor.rag import Passage, retrieve
from cfn_auditor.rules.remediation import REMEDIATION_BY_RULE_ID

__all__ = ["AnthropicRemediationProvider", "build_prompt"]

logger = logging.getLogger(__name__)


_FALLBACK_STATIC = (
    "Review this finding manually — no static remediation is registered "
    "for the rule that produced it."
)

_SYSTEM_PROMPT = (
    "You are a senior cloud-security engineer. Produce concise, actionable "
    "remediation guidance for the given CloudFormation finding. You MUST "
    "ground every recommendation in the provided control context. Do NOT "
    "invent CloudFormation properties, CIS controls, or AWS service names "
    "that are not present in the context or finding. Reply with the "
    "remediation only — no preamble, no markdown headings, no code fences."
)


def build_prompt(finding: FindingInput, passages: list[Passage]) -> str:
    """Render the user-message body for one finding."""
    if passages:
        context_blocks = "\n\n".join(f"[{p.id}]\n{p.body}" for p in passages)
    else:
        context_blocks = "(no passages retrieved — rely strictly on the finding fields below)"
    return (
        "Control context (use ONLY this material to ground your guidance):\n\n"
        f"{context_blocks}\n\n"
        "Finding:\n"
        f"- Rule ID: {finding.rule_id}\n"
        f"- Severity: {finding.severity.value}\n"
        f"- Resource type: {finding.resource_type}\n"
        f"- Resource logical ID: {finding.resource_logical_id}\n"
        f"- Message: {finding.message}\n\n"
        "Remediation:"
    )


def _extract_text(response: Any) -> str:
    """Pull the first text block out of an Anthropic ``Message`` response.

    Robust against simple shape drift between SDK minor versions: tries the
    typed attribute path first, then falls back to dict-style access.
    """
    content = getattr(response, "content", None)
    if not content:
        raise ValueError("Anthropic response has no content blocks.")
    for block in content:
        text_attr = getattr(block, "text", None)
        if text_attr:
            return str(text_attr).strip()
        if isinstance(block, dict):
            text_value = block.get("text")
            if isinstance(text_value, str) and text_value:
                return text_value.strip()
    raise ValueError("Anthropic response has no usable text block.")


class AnthropicRemediationProvider:
    """LLM-backed provider grounded by the in-repo corpus."""

    name: str = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        client: Any = None,
        max_tokens: int = 512,
        top_k: int = 2,
    ) -> None:
        if not api_key:
            raise ValueError("AnthropicRemediationProvider requires an api_key.")
        self._model = model
        self._max_tokens = max_tokens
        self._top_k = top_k
        self._client = client if client is not None else Anthropic(api_key=api_key)

    def advise(self, findings: Iterable[FindingInput]) -> list[AdviceItem]:
        """Produce one :class:`AdviceItem` per finding, preserving order."""
        return [self._advise_one(f) for f in findings]

    def _advise_one(self, finding: FindingInput) -> AdviceItem:
        passages = retrieve(finding, top_k=self._top_k)
        prompt = build_prompt(finding, passages)
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            remediation = _extract_text(response)
            source = f"llm:{self._model}"
        except Exception as exc:
            logger.warning(
                "Anthropic remediation failed for finding %s rule %s (%s); "
                "falling back to static remediation for this finding.",
                finding.finding_id,
                finding.rule_id,
                type(exc).__name__,
            )
            remediation = REMEDIATION_BY_RULE_ID.get(finding.rule_id, _FALLBACK_STATIC)
            source = "static"

        return AdviceItem(
            finding_id=finding.finding_id,
            rule_id=finding.rule_id,
            severity=finding.severity,
            resource_logical_id=finding.resource_logical_id,
            message=finding.message,
            remediation=remediation,
            source=source,
        )
