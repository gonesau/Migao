"""Main entry point for the Adaptive Harmony prototype."""

import time

from audio.audio_manager import AudioManager
from dda.dda_controller import DDAController
from engine.game_engine import GameEngine
from settings import BETA, DDA_EVAL_INTERVAL_SEC, FPS, GAMMA, WINDOW_SIZE, WTOL_MS
from telemetry.emotion_engine import EmotionEngine


def run() -> None:
    engine = GameEngine()
    audio = AudioManager()
    emotion_engine = EmotionEngine(window_size=WINDOW_SIZE)
    dda = DDAController(engine=engine, audio=audio, emotion_engine=emotion_engine)

    audio.load_tracks()
    audio.play()

    dt = 1.0 / FPS
    elapsed_for_dda = 0.0
    start = time.perf_counter()

    # Minimal finite loop for skeleton integration.
    for _ in range(FPS * 2):
        song_time = time.perf_counter() - start
        engine.process_input(events=[], song_time=song_time)
        engine.update(dt)

        for event in engine.pop_events():
            if event.kind == "hit" and event.t_real is not None:
                emotion_engine.record_hit(t_ideal=event.t_ideal, t_real=event.t_real)
            elif event.kind == "miss":
                emotion_engine.record_miss(t_ideal=event.t_ideal)

        elapsed_for_dda += dt
        if elapsed_for_dda >= DDA_EVAL_INTERVAL_SEC:
            elapsed_for_dda = 0.0
            snapshot = emotion_engine.snapshot(wtol_ms=WTOL_MS, beta=BETA, gamma=GAMMA)
            dda.evaluate(snapshot)

    audio.stop()


if __name__ == "__main__":
    run()
