"""Lightweight in-repo RAG retriever.

Loads the curated corpus under :mod:`cfn_auditor.advisor.corpus` and scores
passages against a :class:`FindingInput` using:

  * +10 if the passage's frontmatter ``rule_ids`` list contains the finding's
    ``rule_id`` (exact match).
  * +1 per overlapping token between the passage's keyword set and the
    union of the finding's ``rule_id`` / ``resource_type`` / ``message``.

The retriever is **deterministic** — same input, same output. No embeddings,
no network. Production swap: replace ``rank_passages`` with an embedding-
backed vector index keyed on the same passage IDs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from cfn_auditor.advisor.dto import FindingInput

__all__ = [
    "Passage",
    "load_corpus",
    "rank_passages",
    "retrieve",
]


_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<header>.*?)\n---\s*\n(?P<body>.*)\Z",
    re.DOTALL,
)
_TOKEN_RE = re.compile(r"[A-Za-z0-9:_]+")


@dataclass(frozen=True)
class Passage:
    """One corpus snippet plus its keyed metadata."""

    id: str
    rule_ids: frozenset[str]
    keywords: frozenset[str]
    body: str


def _parse_list_value(raw: str) -> list[str]:
    """Parse ``[a, b, c]`` style lists out of the YAML-ish frontmatter."""
    inner = raw.strip()
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1]
    return [item.strip() for item in inner.split(",") if item.strip()]


def _parse_passage(text: str, passage_id: str) -> Passage:
    """Split a corpus markdown file into metadata + body."""
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return Passage(
            id=passage_id,
            rule_ids=frozenset(),
            keywords=frozenset(),
            body=text.strip(),
        )

    header = match.group("header")
    body = match.group("body").strip()
    rule_ids: list[str] = []
    keywords: list[str] = []
    for line in header.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        if key == "rule_ids":
            rule_ids = _parse_list_value(value)
        elif key == "keywords":
            keywords = [k.lower() for k in _parse_list_value(value)]
    return Passage(
        id=passage_id,
        rule_ids=frozenset(rule_ids),
        keywords=frozenset(keywords),
        body=body,
    )


def load_corpus(corpus_dir: Path | None = None) -> list[Passage]:
    """Load every ``*.md`` file from the corpus directory into :class:`Passage`.

    The README is skipped. Files without frontmatter survive (their metadata
    sets are empty) so authoring mistakes do not crash retrieval.
    """
    if corpus_dir is None:
        corpus_root = files("cfn_auditor.advisor.corpus")
        return _load_from_traversable(corpus_root)
    return _load_from_path(corpus_dir)


def _load_from_path(corpus_dir: Path) -> list[Passage]:
    """Load markdown passages from a filesystem directory."""
    passages: list[Passage] = []
    for path in sorted(corpus_dir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        passages.append(_parse_passage(path.read_text(encoding="utf-8"), path.stem))
    return passages


def _load_from_traversable(corpus_root: object) -> list[Passage]:
    """Load markdown passages from an ``importlib.resources`` traversable.

    Prefer this path so the corpus works when installed as a wheel.
    """
    passages: list[Passage] = []
    for entry in sorted(corpus_root.iterdir(), key=lambda e: e.name):  # type: ignore[attr-defined]
        if not entry.name.endswith(".md") or entry.name.lower() == "readme.md":
            continue
        passages.append(_parse_passage(entry.read_text(encoding="utf-8"), entry.name[:-3]))
    return passages


def _finding_tokens(finding: FindingInput) -> frozenset[str]:
    """Lower-cased token set drawn from the finding's identifying fields."""
    blob = " ".join((finding.rule_id, finding.resource_type, finding.message))
    return frozenset(token.lower() for token in _TOKEN_RE.findall(blob))


def rank_passages(finding: FindingInput, passages: list[Passage]) -> list[Passage]:
    """Return passages sorted by relevance score (descending), then id ascending."""
    finding_tokens = _finding_tokens(finding)
    scored: list[tuple[int, str, Passage]] = []
    for passage in passages:
        score = 0
        if finding.rule_id in passage.rule_ids:
            score += 10
        score += len(passage.keywords & finding_tokens)
        if score > 0:
            scored.append((score, passage.id, passage))
    scored.sort(key=lambda triple: (-triple[0], triple[1]))
    return [passage for _, _, passage in scored]


def retrieve(
    finding: FindingInput,
    *,
    corpus_dir: Path | None = None,
    top_k: int = 1,
) -> list[Passage]:
    """Retrieve the top-``top_k`` passages relevant to ``finding``."""
    return rank_passages(finding, load_corpus(corpus_dir))[:top_k]
