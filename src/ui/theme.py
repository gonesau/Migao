"""UI theme tokens for neon minimal presentation."""

from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class UITheme:
    panel_alpha: int = 150
    panel_border_alpha: int = 110
    overlay_alpha: int = 96
    accent: tuple[int, int, int] = (70, 205, 255)
    base_bg_top: tuple[int, int, int] = (10, 9, 28)
    base_bg_bottom: tuple[int, int, int] = (24, 8, 42)
    lane_glow: tuple[int, int, int] = (150, 58, 255)
    text_primary: tuple[int, int, int] = (236, 240, 250)
    text_muted: tuple[int, int, int] = (170, 182, 206)
    button_radius: int = 12


THEME = UITheme()
