import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finanz" / "app"))

import konfig  # noqa: E402


@pytest.fixture
def k():
    """Erfundener Musterhaushalt aus der Vorlage (keine echten Daten)."""
    return copy.deepcopy(konfig.vorlage())


@pytest.fixture
def daten(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANZ_DATA", str(tmp_path))
    return tmp_path
