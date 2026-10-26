"""Live smoke check against real model APIs (run with: pytest -m live -s)."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.live
def test_live_smoke():
    spec = importlib.util.spec_from_file_location("smoke_models", ROOT / "scripts" / "smoke_models.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(["--roster", str(ROOT / "roster.example.yaml")]) == 0
