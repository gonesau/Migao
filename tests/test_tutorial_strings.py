"""Tests for Spanish tutorial string mappings."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from domain.models import EmotionState
from ui import tutorial_strings as ts


def test_hit_labels_are_spanish() -> None:
    assert ts.hit_label_es("PERFECT!") == "Perfecto"
    assert ts.hit_label_es("MISS") == "Fallo"
    assert "PERFECT" not in ts.hit_label_es("PERFECT!")


def test_state_labels_are_spanish() -> None:
    assert ts.state_label_es(EmotionState.FLOW) == "Flujo"
    assert ts.state_label_es(EmotionState.FRUSTRATION) == "Frustración"


def test_adaptation_messages_non_empty() -> None:
    for state in EmotionState:
        msg = ts.adaptation_message_es(state)
        assert msg
        assert "tempo_multiplier" not in msg
