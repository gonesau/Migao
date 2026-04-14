"""Punto de entrada — Armonía Adaptativa."""

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


def run() -> None:
    # ── Init ──────────────────────────────────────────────────────────────────
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    pygame.display.set_caption("Armonía Adaptativa  –  Sistema DDA")

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock  = pygame.time.Clock()

    # ── Core objects ──────────────────────────────────────────────────────────
    engine         = GameEngine()
    engine.init_fonts()                              # needs pygame.init() first

    audio          = AudioManager()
    emotion_engine = EmotionEngine(window_size=WINDOW_SIZE)
    dda            = DDAController(
        engine=engine, audio=audio, emotion_engine=emotion_engine
    )
    spawner        = NoteSpawner(engine=engine)

    audio.load_tracks()   # synthesise SFX sounds
    audio.play()

    # ── Timing ────────────────────────────────────────────────────────────────
    start_time      = time.perf_counter()
    elapsed_for_dda = 0.0

    # ── Game loop ─────────────────────────────────────────────────────────────
    running = True
    while running:
        dt        = clock.tick(FPS) / 1000.0
        song_time = time.perf_counter() - start_time

        # Events
        raw_events = pygame.event.get()
        for evt in raw_events:
            if evt.type == pygame.QUIT:
                running = False
            elif evt.type == pygame.KEYDOWN and evt.key == pygame.K_ESCAPE:
                running = False

        # ── Update ────────────────────────────────────────────────────────────
        spawner.update(song_time, engine.tempo_multiplier, engine.note_density)
        engine.tick(song_time)                  # advance clock + detect auto-misses
        engine.process_input(raw_events, song_time)
        engine.update(dt)

        # ── Feed events into emotion engine ───────────────────────────────────
        for game_evt in engine.pop_events():
            if game_evt.kind == "hit" and game_evt.t_real is not None:
                emotion_engine.record_hit(
                    t_ideal=game_evt.t_ideal, t_real=game_evt.t_real
                )
                audio.play_hit()
            elif game_evt.kind == "miss":
                emotion_engine.record_miss(t_ideal=game_evt.t_ideal)
                audio.play_miss()

        # ── DDA evaluation every N seconds ────────────────────────────────────
        elapsed_for_dda += dt
        if elapsed_for_dda >= DDA_EVAL_INTERVAL_SEC:
            elapsed_for_dda = 0.0
            snap = emotion_engine.snapshot(wtol_ms=WTOL_MS, beta=BETA, gamma=GAMMA)
            dda.evaluate(snap)

        # ── Render ────────────────────────────────────────────────────────────
        engine.render(screen)
        snap_live = emotion_engine.snapshot(wtol_ms=WTOL_MS, beta=BETA, gamma=GAMMA)
        engine.render_hud(screen, snap_live, dda.current_state)

        pygame.display.flip()

    # ── Cleanup ───────────────────────────────────────────────────────────────
    audio.stop()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    run()