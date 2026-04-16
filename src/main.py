"""Entry point — Armonia Adaptativa."""

from __future__ import annotations

import sys

import pygame

from audio.audio_manager import AudioManager
from engine.game_engine import GameEngine
from settings import SCREEN_HEIGHT, SCREEN_WIDTH
from ui.screens import (
    Intent,
    MenuScreen,
    PlayingScreen,
    SummaryScreen,
    build_fonts,
)


def run() -> None:
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    pygame.display.set_caption("Migao")

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()

    engine = GameEngine()
    engine.init_fonts()
    audio = AudioManager()
    fonts = build_fonts()

    intent = Intent.MENU
    last_stats = None

    while True:
        if intent == Intent.MENU:
            intent = MenuScreen(screen, clock, fonts).run()
        elif intent == Intent.PLAY:
            intent, last_stats = PlayingScreen(
                screen, clock, fonts, engine, audio,
            ).run()
        elif intent == Intent.SUMMARY:
            stats = last_stats if last_stats is not None else engine.stats
            intent = SummaryScreen(screen, clock, fonts, stats).run()
        elif intent == Intent.QUIT:
            break
        else:
            break

    audio.stop()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    run()
