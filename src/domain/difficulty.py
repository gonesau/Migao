"""Selectable game difficulty — timing feel and DDA target offsets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from settings import MISS_GRACE_SEC, WTOL_MS


class GameDifficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass(frozen=True)
class DifficultyProfile:
    """Per-session tuning. Medium matches legacy globals in settings."""

    wtol_ms: float
    miss_grace_sec: float
    tempo_offset: float
    density_offset: float
    boredom_accw_threshold: float
    boredom_jitter_epsilon: float


def profile_for(difficulty: GameDifficulty) -> DifficultyProfile:
    """Map difficulty to concrete parameters (offsets applied in DDA with global clamp)."""
    if difficulty is GameDifficulty.EASY:
        return DifficultyProfile(
            wtol_ms=155.0,
            miss_grace_sec=0.28,
            tempo_offset=-0.08,
            density_offset=-0.18,
            boredom_accw_threshold=0.71,
            boredom_jitter_epsilon=0.030,
        )
    if difficulty is GameDifficulty.HARD:
        return DifficultyProfile(
            wtol_ms=98.0,
            miss_grace_sec=0.12,
            tempo_offset=0.06,
            density_offset=0.12,
            boredom_accw_threshold=0.76,
            boredom_jitter_epsilon=0.020,
        )
    return DifficultyProfile(
        wtol_ms=115.0,
        miss_grace_sec=MISS_GRACE_SEC,
        tempo_offset=0.0,
        density_offset=0.0,
        boredom_accw_threshold=0.73,
        boredom_jitter_epsilon=0.025,
    )
