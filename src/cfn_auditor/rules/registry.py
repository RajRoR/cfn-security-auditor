"""Explicit rule registry.

Rule modules call ``@register`` at class-definition time. ``all_rules`` returns
the registered rule instances in insertion order. Duplicate ids raise at
registration time so a copy-paste mistake fails loudly.

There is no auto-discovery beyond importing the ``rules`` package — the
package's ``__init__`` imports ``rules.checks``, which in turn imports each
check module.
"""

from cfn_auditor.rules.base import Rule

__all__ = ["all_rules", "clear_registry_for_testing", "register"]


_RULES: list[Rule] = []
_IDS: set[str] = set()


def register[T: type[Rule]](cls: T) -> T:
    """Class decorator that instantiates ``cls`` and registers it.

    Raises:
        ValueError: when ``cls.id`` has already been registered.
    """
    rule = cls()
    if rule.id in _IDS:
        raise ValueError(f"Duplicate rule id: {rule.id!r}")
    _IDS.add(rule.id)
    _RULES.append(rule)
    return cls


def all_rules() -> tuple[Rule, ...]:
    """Return every registered rule, in registration order."""
    return tuple(_RULES)


def clear_registry_for_testing() -> None:
    """Reset the registry. Test-only — do not call from production code."""
    _RULES.clear()
    _IDS.clear()
