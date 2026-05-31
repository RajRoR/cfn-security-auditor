"""Smoke imports for stub layer packages so coverage reflects the scaffold."""

import cfn_auditor
import cfn_auditor.api
import cfn_auditor.engine
import cfn_auditor.parser
import cfn_auditor.rules


def test_version_exposed() -> None:
    """The top-level package exposes a non-empty __version__."""
    assert isinstance(cfn_auditor.__version__, str)
    assert cfn_auditor.__version__


def test_layer_stubs_importable() -> None:
    """Each layer package is importable and exports an __all__ list."""
    for module in (cfn_auditor.api, cfn_auditor.engine, cfn_auditor.parser, cfn_auditor.rules):
        assert hasattr(module, "__all__")
        assert isinstance(module.__all__, list)
