"""Reusable UI widgets and drawing helpers shared across screens."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame


def blend(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def draw_vertical_gradient(
    surface: pygame.Surface,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
    rect: pygame.Rect | None = None,
) -> None:
    if rect is None:
        rect = surface.get_rect()
    h = max(1, rect.height)
    for y in range(h):
        t = y / (h - 1) if h > 1 else 0.0
        color = blend(top, bottom, t)
        pygame.draw.line(surface, color, (rect.x, rect.y + y), (rect.right, rect.y + y))


def draw_animated_backdrop(
    surface: pygame.Surface,
    base_color: tuple[int, int, int],
    accent_color: tuple[int, int, int],
    time_sec: float,
) -> None:
    w, h = surface.get_size()
    top = blend((6, 8, 18), base_color, 0.25)
    bottom = blend((4, 6, 14), accent_color, 0.18)
    draw_vertical_gradient(surface, top, bottom)

    for i in range(3):
        radius = int(min(w, h) * (0.55 + 0.12 * i))
        cx = int(w / 2 + math.sin(time_sec * (0.35 + 0.08 * i)) * w * 0.18)
        cy = int(h * (0.72 + 0.05 * i) + math.cos(time_sec * 0.22) * 22)
        alpha = 18 - i * 4
        if alpha <= 0:
            continue
        glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            glow,
            (*accent_color, alpha),
            (radius, radius),
            radius,
        )
        surface.blit(glow, (cx - radius, cy - radius))


@dataclass
class Button:
    label: str
    rect: pygame.Rect
    primary: bool = False
    hot_key: int | None = None

    def contains(self, pos: tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)


def draw_button(
    surface: pygame.Surface,
    button: Button,
    font: pygame.font.Font,
    accent: tuple[int, int, int],
    hover: bool,
    time_sec: float,
) -> None:
    pulse = 0.5 + 0.5 * math.sin(time_sec * 3.0)

    if button.primary:
        base = blend(accent, (240, 240, 250), 0.05)
        top_col = blend(base, (255, 255, 255), 0.12 + 0.08 * pulse if hover else 0.08)
        bot_col = blend(base, (0, 0, 0), 0.35)
        border_col = blend(accent, (255, 255, 255), 0.85 if hover else 0.55)
        text_col = (12, 14, 22)
    else:
        base = (26, 30, 44)
        top_col = blend(base, accent, 0.20 if hover else 0.07)
        bot_col = blend(base, (0, 0, 0), 0.30)
        border_col = blend(accent, (255, 255, 255), 0.55 if hover else 0.25)
        text_col = blend((210, 215, 230), accent, 0.25 if hover else 0.10)

    surf = pygame.Surface(button.rect.size, pygame.SRCALPHA)
    draw_vertical_gradient(surf, top_col, bot_col, pygame.Rect(0, 0, *button.rect.size))

    mask = pygame.Surface(button.rect.size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=12)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

    surface.blit(surf, button.rect.topleft)
    pygame.draw.rect(surface, border_col, button.rect, 2, border_radius=12)

    label = font.render(button.label, True, text_col)
    surface.blit(
        label,
        (
            button.rect.centerx - label.get_width() // 2,
            button.rect.centery - label.get_height() // 2,
        ),
    )


def draw_fade_overlay(surface: pygame.Surface, alpha: int) -> None:
    if alpha <= 0:
        return
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((4, 6, 12, max(0, min(255, alpha))))
    surface.blit(overlay, (0, 0))
