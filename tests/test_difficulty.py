"""Difficulty profiles align with legacy defaults for medium."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from domain.difficulty import GameDifficulty, profile_for
from settings import MISS_GRACE_SEC


def test_medium_matches_settings() -> None:
    p = profile_for(GameDifficulty.MEDIUM)
    assert p.wtol_ms == 115.0
    assert p.miss_grace_sec == MISS_GRACE_SEC
    assert p.tempo_offset == 0.0
    assert p.density_offset == 0.0
    assert p.boredom_accw_threshold == 0.73
    assert p.boredom_jitter_epsilon == 0.025


def test_easy_is_more_forgiving_than_medium() -> None:
    easy = profile_for(GameDifficulty.EASY)
    mid = profile_for(GameDifficulty.MEDIUM)
    assert easy.wtol_ms > mid.wtol_ms
    assert easy.miss_grace_sec > mid.miss_grace_sec
    assert easy.tempo_offset < mid.tempo_offset
    assert easy.density_offset < mid.density_offset
    assert easy.boredom_accw_threshold < mid.boredom_accw_threshold
    assert easy.boredom_jitter_epsilon > mid.boredom_jitter_epsilon


def test_hard_is_stricter_than_medium() -> None:
    hard = profile_for(GameDifficulty.HARD)
    mid = profile_for(GameDifficulty.MEDIUM)
    assert hard.wtol_ms < mid.wtol_ms
    assert hard.miss_grace_sec < mid.miss_grace_sec
    assert hard.tempo_offset > mid.tempo_offset
    assert hard.density_offset > mid.density_offset
    assert hard.boredom_accw_threshold > mid.boredom_accw_threshold
    assert hard.boredom_jitter_epsilon < mid.boredom_jitter_epsilon
