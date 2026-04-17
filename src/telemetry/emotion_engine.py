"""Sliding-window telemetry — computes Acc_w, Jitter and P(F) from recent input.

Acc_w is a bias-corrected Exponentially Weighted Moving Average (EWMA) of the
per-sample accuracy contribution. This is more responsive than a flat mean:
a player recovering from a long miss streak sees their accuracy climb as soon
as they start hitting notes again, instead of waiting for the fixed window to
flush out the old misses.

Jitter is kept as the standard deviation over the recent window (unchanged).
"""

from __future__ import annotations

from collections import deque

import numpy as np

from domain.models import EmotionSnapshot, TelemetrySample
from settings import ACCW_EWMA_ALPHA, MISS_GRACE_SEC

_MIN_SAMPLES_FOR_JITTER = 2


class EmotionEngine:
    def __init__(
        self,
        window_size: int,
        accw_alpha: float = ACCW_EWMA_ALPHA,
    ) -> None:
        if not 0.0 < accw_alpha <= 1.0:
            raise ValueError("accw_alpha must lie in (0, 1]")
        self._window_size = window_size
        self._samples: deque[TelemetrySample] = deque(maxlen=window_size)
        self._accw_alpha = accw_alpha
        self._accw_ewma: float = 0.0
        self._ewma_weight: float = 0.0
        self._miss_streak = 0
        self._hit_streak = 0

    @property
    def miss_streak(self) -> int:
        return self._miss_streak

    @property
    def hit_streak(self) -> int:
        return self._hit_streak

    def clear(self) -> None:
        """Drop all state so a new session starts from a clean slate."""
        self._samples.clear()
        self._accw_ewma = 0.0
        self._ewma_weight = 0.0
        self._miss_streak = 0
        self._hit_streak = 0

    def record_hit(self, t_ideal: float, t_real: float) -> None:
        error = abs(t_real - t_ideal)
        self._append_sample(t_ideal=t_ideal, t_real=t_real, is_miss=False, error=error)
        self._hit_streak += 1
        self._miss_streak = 0

    def record_miss(self, t_ideal: float, t_real: float | None = None) -> None:
        # A miss must represent an error outside the timing tolerance so that
        # Acc_w reflects the real accuracy. Using MISS_GRACE_SEC (the actual
        # engine cutoff) as a lower bound on the stored error achieves that.
        real_time = t_real if t_real is not None else t_ideal
        raw_error = abs(real_time - t_ideal)
        error = max(raw_error, MISS_GRACE_SEC)
        self._append_sample(t_ideal=t_ideal, t_real=real_time, is_miss=True, error=error)
        self._miss_streak += 1
        self._hit_streak = 0

    def snapshot(self, wtol_ms: float, beta: float, gamma: float) -> EmotionSnapshot:
        errors = self._error_array()
        return EmotionSnapshot(
            accw=self._compute_accw(wtol_ms),
            jitter=self._compute_jitter(errors),
            frustration_risk=self._compute_frustration_risk(beta, gamma),
            miss_streak=self._miss_streak,
            hit_streak=self._hit_streak,
            sample_count=errors.size,
        )

    # -- internal bookkeeping -------------------------------------------------

    def _append_sample(
        self,
        t_ideal: float,
        t_real: float,
        is_miss: bool,
        error: float,
    ) -> None:
        self._samples.append(
            TelemetrySample(
                t_ideal=t_ideal,
                t_real=t_real,
                is_miss=is_miss,
                absolute_error=error,
            ),
        )

    def _contribution(self, error_sec: float, wtol_ms: float) -> float:
        error_ms = error_sec * 1000.0
        return max(0.0, 1.0 - error_ms / wtol_ms)

    # -- pure computations ----------------------------------------------------

    def _compute_accw(self, wtol_ms: float) -> float:
        # Bias-corrected EWMA: dividing by the accumulated weight makes the
        # first few samples behave like a plain average, so a constant input
        # of c returns c from the first sample onward.
        if not self._samples:
            return 0.0
        self._refresh_ewma(wtol_ms)
        if self._ewma_weight <= 0.0:
            return 0.0
        return float(self._accw_ewma / self._ewma_weight)

    def _refresh_ewma(self, wtol_ms: float) -> None:
        # Recompute from the stored samples so the EWMA is consistent with the
        # caller-provided wtol_ms (which might change between snapshots) and
        # with the bounded sample window.
        self._accw_ewma = 0.0
        self._ewma_weight = 0.0
        alpha = self._accw_alpha
        one_minus_alpha = 1.0 - alpha
        for sample in self._samples:
            contrib = self._contribution(sample.absolute_error, wtol_ms)
            self._accw_ewma = one_minus_alpha * self._accw_ewma + alpha * contrib
            self._ewma_weight = one_minus_alpha * self._ewma_weight + alpha

    def _compute_jitter(self, errors: np.ndarray) -> float:
        if errors.size < _MIN_SAMPLES_FOR_JITTER:
            return 0.0
        return float(np.sqrt(np.sum((errors - np.mean(errors)) ** 2) / (errors.size - 1)))

    def _compute_frustration_risk(self, beta: float, gamma: float) -> float:
        return float(1.0 / (1.0 + np.exp(-beta * (self._miss_streak - gamma))))

    def _error_array(self) -> np.ndarray:
        if not self._samples:
            return np.array([], dtype=float)
        return np.array([s.absolute_error for s in self._samples], dtype=float)
