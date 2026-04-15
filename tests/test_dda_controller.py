"""Unit tests for the DDA controller classification and hysteresis."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from domain.models import EmotionSnapshot, EmotionState
from dda.dda_controller import DDAController, _step_toward


class _FakeGameAdapter:
    def __init__(self) -> None:
        self.tempo = 1.0
        self.density = 1.0
        self.color = (0, 0, 0)

    def set_tempo(self, multiplier: float) -> None:
        self.tempo = multiplier

    def set_density(self, density: float) -> None:
        self.density = density

    def set_theme(self, color: tuple[int, int, int]) -> None:
        self.color = color


class _FakeAudioAdapter:
    def __init__(self) -> None:
        self.profile = "flow"
        self.tempo = 1.0

    def set_profile(self, profile_name: str) -> None:
        self.profile = profile_name

    def set_tempo(self, multiplier: float) -> None:
        self.tempo = multiplier


def _make_snapshot(
    accw: float = 0.75,
    jitter: float = 0.03,
    frustration_risk: float = 0.1,
    miss_streak: int = 0,
    sample_count: int = 10,
) -> EmotionSnapshot:
    return EmotionSnapshot(
        accw=accw,
        jitter=jitter,
        frustration_risk=frustration_risk,
        miss_streak=miss_streak,
        sample_count=sample_count,
    )


@pytest.fixture()
def dda() -> DDAController:
    return DDAController(engine=_FakeGameAdapter(), audio=_FakeAudioAdapter())


class TestClassification:
    def test_flow_on_balanced_metrics(self, dda: DDAController) -> None:
        snap = _make_snapshot(accw=0.75, jitter=0.03, frustration_risk=0.1)
        state = dda._classify(snap)
        assert state == EmotionState.FLOW

    def test_frustration_on_low_accw(self, dda: DDAController) -> None:
        snap = _make_snapshot(accw=0.30, frustration_risk=0.2)
        state = dda._classify(snap)
        assert state == EmotionState.FRUSTRATION

    def test_frustration_on_high_pf(self, dda: DDAController) -> None:
        snap = _make_snapshot(accw=0.80, frustration_risk=0.85)
        state = dda._classify(snap)
        assert state == EmotionState.FRUSTRATION

    def test_boredom_on_high_accw_low_jitter(self, dda: DDAController) -> None:
        snap = _make_snapshot(accw=0.95, jitter=0.005, frustration_risk=0.0)
        state = dda._classify(snap)
        assert state == EmotionState.BOREDOM

    def test_not_bored_when_jitter_is_high(self, dda: DDAController) -> None:
        snap = _make_snapshot(accw=0.95, jitter=0.05, frustration_risk=0.0)
        state = dda._classify(snap)
        assert state == EmotionState.FLOW


class TestHysteresis:
    def test_no_immediate_transition(self, dda: DDAController) -> None:
        frustration_snap = _make_snapshot(accw=0.30, frustration_risk=0.9)
        dda.evaluate(frustration_snap, dt_since_last=5.0)
        assert dda.current_state == EmotionState.FLOW

    def test_transition_after_confirmations_and_cooldown(self, dda: DDAController) -> None:
        frustration_snap = _make_snapshot(accw=0.30, frustration_risk=0.9)

        dda.evaluate(frustration_snap, dt_since_last=7.0)
        dda.evaluate(frustration_snap, dt_since_last=5.0)

        assert dda.current_state == EmotionState.FRUSTRATION

    def test_pending_state_resets_on_different_classification(self, dda: DDAController) -> None:
        frustration_snap = _make_snapshot(accw=0.30, frustration_risk=0.9)
        dda.evaluate(frustration_snap, dt_since_last=7.0)

        flow_snap = _make_snapshot(accw=0.75, jitter=0.03, frustration_risk=0.1)
        dda.evaluate(flow_snap, dt_since_last=5.0)

        assert dda.current_state == EmotionState.FLOW
        assert dda._confirmation_count == 0


class TestStepToward:
    def test_small_step(self) -> None:
        result = _step_toward(1.0, 1.1, 0.05)
        assert result == pytest.approx(1.05)

    def test_reaches_target_within_step(self) -> None:
        result = _step_toward(1.0, 1.03, 0.05)
        assert result == pytest.approx(1.03)

    def test_negative_direction(self) -> None:
        result = _step_toward(1.0, 0.8, 0.05)
        assert result == pytest.approx(0.95)

    def test_already_at_target(self) -> None:
        result = _step_toward(1.0, 1.0, 0.05)
        assert result == pytest.approx(1.0)
