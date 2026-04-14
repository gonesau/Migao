from collections import deque
from dataclasses import dataclass
import numpy as np

@dataclass
class TelemetrySample:
    t_ideal: float
    t_real: float
    p_i: float

@dataclass
class EmotionSnapshot:
    accw: float
    jitter: float
    frustration_risk: float
    miss_streak: int
    sample_count: int

class EmotionEngine:
    def __init__(self, window_size: int) -> None:
        self.samples: deque[TelemetrySample] = deque(maxlen=window_size)
        self.miss_streak = 0

    def record_hit(self, t_ideal: float, t_real: float) -> None:
        p_i = abs(t_real - t_ideal)
        self.samples.append(TelemetrySample(t_ideal=t_ideal, t_real=t_real, p_i=p_i))
        self.miss_streak = 0

    def record_miss(self, t_ideal: float, t_real: float | None = None) -> None:
        real_time = t_real if t_real is not None else t_ideal
        p_i = abs(real_time - t_ideal)
        self.samples.append(TelemetrySample(t_ideal=t_ideal, t_real=real_time, p_i=p_i))
        self.miss_streak += 1

    def compute_accw(self, wtol_ms: float) -> float:
        p = self._p_errors()
        if p.size == 0: return 0.0
        return float(np.mean(np.maximum(0.0, 1.0 - (p / wtol_ms))))

    def compute_jitter(self) -> float:
        p = self._p_errors()
        if p.size <= 1: return 0.0
        return float(np.sqrt(np.sum((p - np.mean(p))**2) / (p.size - 1)))

    def compute_frustration_risk(self, beta: float, gamma: float) -> float:
        return float(1.0 / (1.0 + np.exp(-beta * (self.miss_streak - gamma))))

    def snapshot(self, wtol_ms: float, beta: float, gamma: float) -> EmotionSnapshot:
        return EmotionSnapshot(
            accw=self.compute_accw(wtol_ms),
            jitter=self.compute_jitter(),
            frustration_risk=self.compute_frustration_risk(beta, gamma),
            miss_streak=self.miss_streak,
            sample_count=self._p_errors().size,
        )

    def _p_errors(self) -> np.ndarray:
        if not self.samples: return np.array([], dtype=float)
        return np.array([s.p_i for s in self.samples], dtype=float)