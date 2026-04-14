"""Generates rhythmic note patterns and inserts them into engine lanes."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from engine.components import Note
from settings import BASE_BPM, FALL_DURATION, LANE_COUNT

if TYPE_CHECKING:
    from engine.game_engine import GameEngine

# ── Patterns: each sub-list is one beat; values are lane indices to activate ───
_SIMPLE: list[list[int]] = [
    [0], [2], [1], [3], [0], [2], [1], [3],
]
_MEDIUM: list[list[int]] = [
    [0, 2], [1], [3], [0], [1, 3], [2], [0], [2, 3],
]
_DENSE: list[list[int]] = [
    [0, 1], [2, 3], [0, 2], [1, 3], [0], [1, 2, 3], [0, 2], [1],
]


class NoteSpawner:
    def __init__(self, engine: GameEngine) -> None:
        self.engine        = engine
        self._beat_index   = 0
        # First note arrives 2 s after game start so the player can orient
        self._next_t_ideal = 2.0

    # ── Main update (called every frame) ──────────────────────────────────────
    def update(
        self,
        song_time:        float,
        tempo_multiplier: float,
        density:          float,
    ) -> None:
        beat_interval = (60.0 / BASE_BPM) / tempo_multiplier
        fall_duration = FALL_DURATION / tempo_multiplier

        # Spawn ahead until the next ideal time is farther than one fall-window
        while self._next_t_ideal - song_time <= fall_duration:
            self._spawn_beat(
                t_ideal=self._next_t_ideal,
                fall_duration=fall_duration,
                density=density,
            )
            self._next_t_ideal += beat_interval
            self._beat_index   += 1

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _spawn_beat(
        self,
        t_ideal:       float,
        fall_duration: float,
        density:       float,
    ) -> None:
        pattern = _pick_pattern(density)
        lanes   = list(pattern[self._beat_index % len(pattern)])

        # At high density probabilistically add an extra lane
        if density >= 1.1 and random.random() < 0.35:
            candidates = [l for l in range(LANE_COUNT) if l not in lanes]
            if candidates:
                lanes.append(random.choice(candidates))

        spawn_time = max(0.0, t_ideal - fall_duration)
        for lane_id in lanes:
            self.engine.lanes[lane_id].add_note(
                Note(lane_id=lane_id, t_ideal=t_ideal, spawn_time=spawn_time)
            )


# ── Pattern selector ──────────────────────────────────────────────────────────
def _pick_pattern(density: float) -> list[list[int]]:
    if density < 0.9:
        return _SIMPLE
    if density < 1.1:
        return _MEDIUM
    return _DENSE