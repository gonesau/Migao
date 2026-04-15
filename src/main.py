"""Entry point — Armonia Adaptativa."""

from __future__ import annotations

import sys
import time

import pygame

from audio.audio_manager import AudioManager
from dda.dda_controller import DDAController
from engine.game_engine import GameEngine
from engine.note_spawner import NoteSpawner
from settings import (
    BETA,
    DDA_EVAL_INTERVAL_SEC,
    FPS,
    GAMMA,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WINDOW_SIZE,
    WTOL_MS,
)
from telemetry.emotion_engine import EmotionEngine

SONG_DURATION_SEC = 90.0


def run() -> None:
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    pygame.display.set_caption("Armonia Adaptativa  -  Sistema DDA")

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()

    engine = GameEngine()
    engine.init_fonts()

    audio = AudioManager()
    emotion_engine = EmotionEngine(window_size=WINDOW_SIZE)
    dda = DDAController(engine=engine, audio=audio)
    spawner = NoteSpawner(engine=engine)

    audio.load_tracks()
    audio.play()

    start_time = time.perf_counter()
    time_since_dda_eval = 0.0

    playing = True
    while playing:
        dt = clock.tick(FPS) / 1000.0
        song_time = time.perf_counter() - start_time

        raw_events = pygame.event.get()
        for evt in raw_events:
            if evt.type == pygame.QUIT:
                _shutdown(audio)
            elif evt.type == pygame.KEYDOWN and evt.key == pygame.K_ESCAPE:
                playing = False
                continue

        if song_time >= SONG_DURATION_SEC:
            playing = False
            continue

        # -- update simulation ------------------------------------------------
        spawner.update(song_time, engine.tempo_multiplier, engine.note_density)
        engine.tick(song_time)
        engine.process_input(raw_events, song_time)
        engine.update(dt)

        # -- feed telemetry ---------------------------------------------------
        for game_evt in engine.pop_events():
            if game_evt.kind == "hit" and game_evt.t_real is not None:
                emotion_engine.record_hit(
                    t_ideal=game_evt.t_ideal, t_real=game_evt.t_real,
                )
                audio.play_hit()
            elif game_evt.kind == "miss":
                emotion_engine.record_miss(t_ideal=game_evt.t_ideal)
                audio.play_miss()

        # -- DDA evaluation ---------------------------------------------------
        time_since_dda_eval += dt
        engine.accumulate_state_time(dda.current_state, dt)

        if time_since_dda_eval >= DDA_EVAL_INTERVAL_SEC:
            snap = emotion_engine.snapshot(
                wtol_ms=WTOL_MS, beta=BETA, gamma=GAMMA,
            )
            dda.evaluate(snap, dt_since_last=time_since_dda_eval)
            time_since_dda_eval = 0.0

        # -- render -----------------------------------------------------------
        engine.render(screen)
        snap_live = emotion_engine.snapshot(
            wtol_ms=WTOL_MS, beta=BETA, gamma=GAMMA,
        )
        engine.render_hud(screen, snap_live, dda.current_state)
        pygame.display.flip()

    # -- summary screen -------------------------------------------------------
    _show_summary(screen, clock, engine, audio)


def _show_summary(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    engine: GameEngine,
    audio: AudioManager,
) -> None:
    engine.render_summary(screen)
    pygame.display.flip()

    waiting = True
    while waiting:
        clock.tick(30)
        for evt in pygame.event.get():
            if evt.type == pygame.QUIT:
                waiting = False
            elif evt.type == pygame.KEYDOWN and evt.key == pygame.K_ESCAPE:
                waiting = False

    _shutdown(audio)


def _shutdown(audio: AudioManager) -> None:
    audio.stop()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    run()
