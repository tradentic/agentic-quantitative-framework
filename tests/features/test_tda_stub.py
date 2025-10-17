from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_tda_and_hmm_stubs_are_importable() -> None:
    hmm = importlib.import_module("features.hmm_change_points")
    schema = hmm.planned_feature_schema()
    assert "hmm_state" in schema
    assert hmm.describe_feature_strategy()

    tda = importlib.import_module("features.tda_persistence")
    planned = tda.planned_persistence_features()
    assert "lifespan_max" in planned
    assert tda.persistence_feature_notes()
