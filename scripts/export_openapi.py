"""Export the live FastAPI OpenAPI spec to ``docs/openapi.json``.

Run with:

    uv run python scripts/export_openapi.py
    # or:
    make openapi

Re-run whenever an endpoint, schema, or error envelope changes. CI does NOT
auto-regenerate the file — keeping it committed makes API drift visible in
review.
"""

from __future__ import annotations

import json
from pathlib import Path

from cfn_auditor.api import create_app

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"


def export() -> Path:
    """Generate the spec and write it to :data:`OUTPUT_PATH`. Returns the path."""
    spec = create_app().openapi()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return OUTPUT_PATH


if __name__ == "__main__":  # pragma: no cover
    path = export()
    print(f"Wrote OpenAPI spec to {path}")
