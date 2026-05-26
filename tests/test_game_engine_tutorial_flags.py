"""Tests for GameEngine tutorial flags (auto-miss and screen shake)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from engine.components import Note
from engine.game_engine import GameEngine


@pytest.fixture()
def engine() -> GameEngine:
    eng = GameEngine()
    eng.configure_session_timing(wtol_ms=100.0, miss_grace_sec=0.18)
    eng.lanes[0].add_note(
        Note(lane_id=0, t_ideal=2.0, spawn_time=0.0),
    )
    return eng


class TestAutoMissEnabled:
    def test_disabled_skips_auto_miss(self, engine: GameEngine) -> None:
        engine.set_auto_miss_enabled(False)
        engine.tick(song_time=5.0)
        note = engine.lanes[0].notes[0]
        assert not note.is_missed
        assert engine.stats.total_misses == 0

    def test_enabled_marks_miss_after_grace(self, engine: GameEngine) -> None:
        engine.set_auto_miss_enabled(True)
        engine.tick(song_time=2.5)
        note = engine.lanes[0].notes[0]
        assert note.is_missed
        assert engine.stats.total_misses == 1


class TestScreenShakeEnabled:
    def test_disabled_miss_does_not_increase_shake(self, engine: GameEngine) -> None:
        engine.set_screen_shake_enabled(False)
        engine.set_auto_miss_enabled(True)
        engine.tick(song_time=2.5)
        assert engine._shake_amp == pytest.approx(0.0)

    def test_clear_visual_feedback_resets_shake(self, engine: GameEngine) -> None:
        engine.set_screen_shake_enabled(True)
        engine.set_auto_miss_enabled(True)
        engine.tick(song_time=2.5)
        assert engine._shake_amp > 0.0
        engine.clear_visual_feedback()
        assert engine._shake_amp == pytest.approx(0.0)
        assert engine.shake_offset == (0, 0)
