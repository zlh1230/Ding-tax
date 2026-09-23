from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from etax_projects import PROJECT_ALLOWLIST, resolve_project


def test_confirmed_aliases_and_allowlist():
    assert len(PROJECT_ALLOWLIST) == 10
    assert resolve_project("审核") == "审核费"
    assert resolve_project("监督审核") == "监督审核费"
    assert resolve_project("认证费") == "认证费"


def test_unknown_project_fails_closed():
    with pytest.raises(ValueError, match="UNSUPPORTED_INVOICE_PROJECT"):
        resolve_project("未确认项目")
