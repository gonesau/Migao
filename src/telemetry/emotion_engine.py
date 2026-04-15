"""Sliding-window telemetry — computes Acc_w, Jitter and P(F) from recent input."""

from __future__ import annotations

from collections import deque

import numpy as np

from domain.models import EmotionSnapshot, TelemetrySample

_MIN_SAMPLES_FOR_JITTER = 2


class EmotionEngine:
    def __init__(self, window_size: int) -> None:
        self._window_size = window_size
        self._samples: deque[TelemetrySample] = deque(maxlen=window_size)
        self._miss_streak = 0

    @property
    def miss_streak(self) -> int:
        return self._miss_streak

    def record_hit(self, t_ideal: float, t_real: float) -> None:
        error = abs(t_real - t_ideal)
        self._samples.append(
            TelemetrySample(
                t_ideal=t_ideal, t_real=t_real,
                is_miss=False, absolute_error=error,
            )
        )
        self._miss_streak = 0

    def record_miss(self, t_ideal: float, t_real: float | None = None) -> None:
        real_time = t_real if t_real is not None else t_ideal
        error = abs(real_time - t_ideal)
        self._samples.append(
            TelemetrySample(
                t_ideal=t_ideal, t_real=real_time,
                is_miss=True, absolute_error=error,
            )
        )
        self._miss_streak += 1

    def snapshot(self, wtol_ms: float, beta: float, gamma: float) -> EmotionSnapshot:
        errors = self._error_array()
        return EmotionSnapshot(
            accw=self._compute_accw(errors, wtol_ms),
            jitter=self._compute_jitter(errors),
            frustration_risk=self._compute_frustration_risk(beta, gamma),
            miss_streak=self._miss_streak,
            sample_count=errors.size,
        )

    # -- pure computations ----------------------------------------------------

    def _compute_accw(self, errors: np.ndarray, wtol_ms: float) -> float:
        if errors.size == 0:
            return 0.0
        errors_ms = errors * 1000.0
        return float(np.mean(np.maximum(0.0, 1.0 - (errors_ms / wtol_ms))))

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
