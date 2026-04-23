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
    hit_streak: int = 0,
    sample_count: int = 10,
) -> EmotionSnapshot:
    return EmotionSnapshot(
        accw=accw,
        jitter=jitter,
        frustration_risk=frustration_risk,
        miss_streak=miss_streak,
        hit_streak=hit_streak,
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

    def test_profile_boredom_thresholds_are_respected(self) -> None:
        custom = DDAController(
            engine=_FakeGameAdapter(),
            audio=_FakeAudioAdapter(),
            boredom_accw_threshold=0.89,
            boredom_jitter_epsilon=0.02,
        )
        snap = _make_snapshot(accw=0.87, jitter=0.019, frustration_risk=0.0)
        assert custom._classify(snap) == EmotionState.FLOW


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
        assert dda._pending_state == EmotionState.FLOW
        assert dda._transition_score == pytest.approx(0.0)

    def test_exits_frustration_when_metrics_recover(self, dda: DDAController) -> None:
        frustration_snap = _make_snapshot(accw=0.30, frustration_risk=0.9)
        dda.evaluate(frustration_snap, dt_since_last=7.0)
        dda.evaluate(frustration_snap, dt_since_last=5.0)
        assert dda.current_state == EmotionState.FRUSTRATION

        # Player recovers with an isolated FRUSTRATION blip in between. The
        # score-based hysteresis must accumulate evidence rather than wiping
        # it on the blip.
        flow_snap = _make_snapshot(accw=0.75, jitter=0.03, frustration_risk=0.1)
        dda.evaluate(flow_snap, dt_since_last=5.0)
        dda.evaluate(frustration_snap, dt_since_last=5.0)
        dda.evaluate(flow_snap, dt_since_last=5.0)
        dda.evaluate(flow_snap, dt_since_last=5.0)

        assert dda.current_state == EmotionState.FLOW

    def test_blip_during_recovery_does_not_penalise_player(
        self, dda: DDAController,
    ) -> None:
        frustration_snap = _make_snapshot(accw=0.30, frustration_risk=0.9)
        dda.evaluate(frustration_snap, dt_since_last=7.0)
        dda.evaluate(frustration_snap, dt_since_last=5.0)
        assert dda.current_state == EmotionState.FRUSTRATION

        flow_snap = _make_snapshot(accw=0.75, frustration_risk=0.1)
        dda.evaluate(flow_snap, dt_since_last=5.0)
        score_after_flow = dda._transition_score
        dda.evaluate(frustration_snap, dt_since_last=5.0)
        score_after_blip = dda._transition_score

        # A single FRUSTRATION reading during recovery may zero out the score,
        # but must never push it below zero or drive additional punishment.
        assert score_after_flow > 0.0
        assert score_after_blip == pytest.approx(0.0)
        assert dda.current_state == EmotionState.FRUSTRATION


class TestFastRecovery:
    def test_hit_streak_override_exits_frustration(self, dda: DDAController) -> None:
        frustration_snap = _make_snapshot(accw=0.30, frustration_risk=0.9)
        dda.evaluate(frustration_snap, dt_since_last=7.0)
        dda.evaluate(frustration_snap, dt_since_last=5.0)
        assert dda.current_state == EmotionState.FRUSTRATION

        # Metrics still look rough (Acc_w below exit band, P(F) also high),
        # but the player has chained enough hits and cleared the miss streak.
        # That is the clearest behavioural signal of recovery and must bypass
        # the score accumulation.
        recovery_snap = _make_snapshot(
            accw=0.40,
            frustration_risk=0.6,
            miss_streak=0,
            hit_streak=8,
        )
        dda.evaluate(recovery_snap, dt_since_last=7.0)
        assert dda.current_state == EmotionState.FLOW

    def test_override_respects_cooldown(self, dda: DDAController) -> None:
        frustration_snap = _make_snapshot(accw=0.30, frustration_risk=0.9)
        dda.evaluate(frustration_snap, dt_since_last=7.0)
        dda.evaluate(frustration_snap, dt_since_last=5.0)

        # Cooldown not yet satisfied (time_in_state resets on transition).
        recovery_snap = _make_snapshot(
            accw=0.40, frustration_risk=0.6,
            miss_streak=0, hit_streak=10,
        )
        dda.evaluate(recovery_snap, dt_since_last=2.0)
        assert dda.current_state == EmotionState.FRUSTRATION

    def test_override_requires_clean_miss_streak(self, dda: DDAController) -> None:
        frustration_snap = _make_snapshot(accw=0.30, frustration_risk=0.9)
        dda.evaluate(frustration_snap, dt_since_last=7.0)
        dda.evaluate(frustration_snap, dt_since_last=5.0)

        # Hit streak is high but a recent miss disqualifies the override; the
        # normal score-based transition still has to play out.
        noisy_snap = _make_snapshot(
            accw=0.40, frustration_risk=0.6,
            miss_streak=1, hit_streak=8,
        )
        dda.evaluate(noisy_snap, dt_since_last=7.0)
        assert dda.current_state == EmotionState.FRUSTRATION


class TestExitBand:
    def test_mid_band_accw_does_not_flip_back_to_frustration(
        self, dda: DDAController,
    ) -> None:
        frustration_snap = _make_snapshot(accw=0.30, frustration_risk=0.9)
        dda.evaluate(frustration_snap, dt_since_last=7.0)
        dda.evaluate(frustration_snap, dt_since_last=5.0)

        flow_snap = _make_snapshot(accw=0.75, frustration_risk=0.1)
        for _ in range(4):
            dda.evaluate(flow_snap, dt_since_last=5.0)
        assert dda.current_state == EmotionState.FLOW

        # 0.55 sits inside the hysteresis band (enter=0.50, exit=0.60). While
        # in FLOW the classifier must not consider this as frustration since
        # it is above the entry threshold.
        mid_snap = _make_snapshot(accw=0.55, frustration_risk=0.2)
        for _ in range(3):
            dda.evaluate(mid_snap, dt_since_last=5.0)
        assert dda.current_state == EmotionState.FLOW

    def test_entry_threshold_is_still_reactive(self, dda: DDAController) -> None:
        # Entering FRUSTRATION must keep working at the lower (enter) bound.
        low_snap = _make_snapshot(accw=0.45, frustration_risk=0.2)
        dda.evaluate(low_snap, dt_since_last=7.0)
        dda.evaluate(low_snap, dt_since_last=5.0)
        assert dda.current_state == EmotionState.FRUSTRATION


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
