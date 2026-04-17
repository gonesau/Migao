"""Unit tests for the EmotionEngine telemetry module."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from domain.models import EmotionSnapshot
from telemetry.emotion_engine import EmotionEngine


@pytest.fixture()
def engine() -> EmotionEngine:
    return EmotionEngine(window_size=10)


class TestRecordHit:
    def test_single_perfect_hit(self, engine: EmotionEngine) -> None:
        engine.record_hit(t_ideal=1.0, t_real=1.0)
        assert engine.miss_streak == 0

    def test_resets_miss_streak(self, engine: EmotionEngine) -> None:
        engine.record_miss(t_ideal=1.0)
        engine.record_miss(t_ideal=2.0)
        assert engine.miss_streak == 2
        engine.record_hit(t_ideal=3.0, t_real=3.01)
        assert engine.miss_streak == 0


class TestRecordMiss:
    def test_increments_streak(self, engine: EmotionEngine) -> None:
        for i in range(5):
            engine.record_miss(t_ideal=float(i))
        assert engine.miss_streak == 5

    def test_miss_uses_t_ideal_when_no_real(self, engine: EmotionEngine) -> None:
        engine.record_miss(t_ideal=2.0, t_real=None)
        snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert snap.sample_count == 1


class TestAccw:
    def test_perfect_accuracy(self, engine: EmotionEngine) -> None:
        for i in range(5):
            engine.record_hit(t_ideal=float(i), t_real=float(i))
        snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert snap.accw == pytest.approx(1.0)

    def test_zero_accuracy_on_large_errors(self, engine: EmotionEngine) -> None:
        for i in range(5):
            engine.record_hit(t_ideal=float(i), t_real=float(i) + 0.5)
        snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert snap.accw == pytest.approx(0.0)

    def test_partial_accuracy(self, engine: EmotionEngine) -> None:
        engine.record_hit(t_ideal=1.0, t_real=1.0)
        engine.record_hit(t_ideal=2.0, t_real=2.05)
        snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert 0.0 < snap.accw < 1.0

    def test_empty_engine_returns_zero(self, engine: EmotionEngine) -> None:
        snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert snap.accw == 0.0

    def test_units_contract_seconds_vs_ms(self, engine: EmotionEngine) -> None:
        # Regression: absolute_error is in seconds, wtol_ms in ms.
        # A constant error of 0.05 s with wtol_ms=100 must yield 1 - 50/100 = 0.5.
        for i in range(4):
            engine.record_hit(t_ideal=float(i), t_real=float(i) + 0.05)
        snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert snap.accw == pytest.approx(0.5, abs=1e-9)

    def test_misses_penalize_accw(self, engine: EmotionEngine) -> None:
        # Misses must push Acc_w down, not behave like perfect hits.
        for i in range(5):
            engine.record_hit(t_ideal=float(i), t_real=float(i))
        peak_accw = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0).accw
        for j in range(5, 10):
            engine.record_miss(t_ideal=float(j))
        after_accw = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0).accw
        # EWMA weights recent samples more, so after 5 consecutive misses the
        # five earlier perfect hits must not prop Acc_w up near 0.5. The
        # metric must clearly drop below the frustration threshold so the
        # DDA can react.
        assert peak_accw == pytest.approx(1.0, abs=1e-9)
        assert after_accw < 0.4
        assert after_accw < peak_accw

    def test_ewma_reacts_faster_than_flat_average(self, engine: EmotionEngine) -> None:
        # After a long miss streak, a few hits must visibly lift Acc_w.
        for j in range(10):
            engine.record_miss(t_ideal=float(j))
        low_accw = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0).accw
        for i in range(3):
            engine.record_hit(t_ideal=float(100 + i), t_real=float(100 + i))
        recovered_accw = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0).accw
        assert low_accw < 0.05
        assert recovered_accw - low_accw > 0.4


class TestJitter:
    def test_zero_jitter_on_identical_errors(self, engine: EmotionEngine) -> None:
        for i in range(5):
            engine.record_hit(t_ideal=float(i), t_real=float(i) + 0.02)
        snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert snap.jitter == pytest.approx(0.0, abs=1e-9)

    def test_positive_jitter_on_varied_errors(self, engine: EmotionEngine) -> None:
        engine.record_hit(t_ideal=1.0, t_real=1.01)
        engine.record_hit(t_ideal=2.0, t_real=2.08)
        engine.record_hit(t_ideal=3.0, t_real=3.0)
        snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert snap.jitter > 0.0

    def test_insufficient_samples_returns_zero(self, engine: EmotionEngine) -> None:
        engine.record_hit(t_ideal=1.0, t_real=1.05)
        snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert snap.jitter == 0.0


class TestFrustrationRisk:
    def test_zero_misses_low_risk(self, engine: EmotionEngine) -> None:
        snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert snap.frustration_risk < 0.05

    def test_high_miss_streak_high_risk(self, engine: EmotionEngine) -> None:
        for i in range(10):
            engine.record_miss(t_ideal=float(i))
        snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert snap.frustration_risk > 0.95

    def test_sigmoid_shape(self, engine: EmotionEngine) -> None:
        risks = []
        for i in range(8):
            engine.record_miss(t_ideal=float(i))
            snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
            risks.append(snap.frustration_risk)
        for j in range(len(risks) - 1):
            assert risks[j + 1] >= risks[j]


class TestSnapshot:
    def test_returns_emotion_snapshot(self, engine: EmotionEngine) -> None:
        engine.record_hit(t_ideal=1.0, t_real=1.02)
        snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert isinstance(snap, EmotionSnapshot)

    def test_sample_count_respects_window(self) -> None:
        small_engine = EmotionEngine(window_size=3)
        for i in range(5):
            small_engine.record_hit(t_ideal=float(i), t_real=float(i))
        snap = small_engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert snap.sample_count == 3


class TestHitStreak:
    def test_hit_streak_starts_at_zero(self, engine: EmotionEngine) -> None:
        assert engine.hit_streak == 0
        snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert snap.hit_streak == 0

    def test_hit_streak_increments_on_consecutive_hits(
        self, engine: EmotionEngine,
    ) -> None:
        for i in range(4):
            engine.record_hit(t_ideal=float(i), t_real=float(i))
        snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert snap.hit_streak == 4
        assert snap.miss_streak == 0

    def test_hit_streak_resets_on_miss(self, engine: EmotionEngine) -> None:
        for i in range(5):
            engine.record_hit(t_ideal=float(i), t_real=float(i))
        engine.record_miss(t_ideal=6.0)
        snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert snap.hit_streak == 0
        assert snap.miss_streak == 1

    def test_streaks_are_mutually_exclusive(self, engine: EmotionEngine) -> None:
        engine.record_miss(t_ideal=1.0)
        engine.record_miss(t_ideal=2.0)
        engine.record_hit(t_ideal=3.0, t_real=3.0)
        snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert snap.miss_streak == 0
        assert snap.hit_streak == 1


class TestClear:
    def test_clear_resets_all_state(self, engine: EmotionEngine) -> None:
        for i in range(3):
            engine.record_hit(t_ideal=float(i), t_real=float(i))
        engine.record_miss(t_ideal=10.0)
        engine.clear()
        snap = engine.snapshot(wtol_ms=100.0, beta=1.4, gamma=4.0)
        assert snap.sample_count == 0
        assert snap.accw == 0.0
        assert snap.miss_streak == 0
        assert snap.hit_streak == 0
