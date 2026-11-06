"""Painted night-sky backdrop. Cosy living-room TV feel. No moon anywhere."""
from __future__ import annotations

import random

import pygame


def build_backdrop(w: int, h: int, seed: int = 42) -> pygame.Surface:
    rng = random.Random(seed)
    surf = pygame.Surface((w, h)).convert()

    # Deep indigo → warm amber near the bottom (lamp glow)
    for y in range(h):
        t = y / max(1, h - 1)
        # sky
        r = int(8 + 18 * t + 40 * max(0, t - 0.55) ** 2 * 255 / 40)
        g = int(12 + 22 * t + 25 * max(0, t - 0.6) ** 2 * 8)
        b = int(28 + 40 * (1 - t) * 0.6 + 10 * t)
        # warm floor wash
        if t > 0.62:
            u = (t - 0.62) / 0.38
            r = int(r * (1 - u) + (70 + 60 * u) * u + r * (1 - u) * 0.3)
            g = int(g * (1 - 0.5 * u) + 35 * u)
            b = int(b * (1 - 0.7 * u) + 18 * u)
            r = min(255, int(12 + 55 * u + 8))
            g = min(255, int(14 + 28 * u))
            b = min(255, int(32 + 8 * (1 - u)))
        # recompute cleaner gradient
        top = (10, 14, 36)
        mid = (18, 22, 48)
        warm = (58, 36, 22)
        floor = (32, 22, 16)
        if t < 0.45:
            u = t / 0.45
            col = _lerp(top, mid, u)
        elif t < 0.72:
            u = (t - 0.45) / 0.27
            col = _lerp(mid, warm, u * u)
        else:
            u = (t - 0.72) / 0.28
            col = _lerp(warm, floor, u)
        pygame.draw.line(surf, col, (0, y), (w, y))

    # Soft star field (no moon)
    star_layer = pygame.Surface((w, h), pygame.SRCALPHA)
    for _ in range(160):
        x = rng.randint(0, w - 1)
        y = rng.randint(0, int(h * 0.62))
        a = rng.randint(60, 200)
        size = 1 if rng.random() < 0.85 else 2
        col = (230, 235, 255, a)
        if size == 1:
            star_layer.set_at((x, y), col)
        else:
            pygame.draw.circle(star_layer, col, (x, y), 1)
    # a few brighter twinkles
    for _ in range(18):
        x = rng.randint(0, w - 1)
        y = rng.randint(0, int(h * 0.5))
        pygame.draw.circle(star_layer, (255, 250, 230, 180), (x, y), 1)
        pygame.draw.circle(star_layer, (255, 250, 230, 60), (x, y), 2)
    surf.blit(star_layer, (0, 0))

    # Soft horizon haze
    haze = pygame.Surface((w, 120), pygame.SRCALPHA)
    for i in range(120):
        a = int(40 * (1 - abs(i - 80) / 80) ** 2)
        pygame.draw.line(haze, (90, 55, 30, max(0, a)), (0, i), (w, i))
    surf.blit(haze, (0, h - 200))

    # Gentle vignette — soft darkening toward the edges (no hard rings)
    vignette = pygame.Surface((w, h), pygame.SRCALPHA)
    edge = 110
    for i in range(edge):
        a = int(90 * ((edge - 1 - i) / edge) ** 2)
        # top / bottom bands
        pygame.draw.line(vignette, (0, 0, 0, a), (0, i), (w, i))
        pygame.draw.line(vignette, (0, 0, 0, a), (0, h - 1 - i), (w, h - 1 - i))
        # left / right bands
        pygame.draw.line(vignette, (0, 0, 0, a), (i, 0), (i, h))
        pygame.draw.line(vignette, (0, 0, 0, a), (w - 1 - i, 0), (w - 1 - i, h))
    surf.blit(vignette, (0, 0))

    # Cosy side lamp glow (left)
    glow = pygame.Surface((w, h), pygame.SRCALPHA)
    for r in range(220, 0, -8):
        a = int(18 * (r / 220) ** 2)
        pygame.draw.circle(glow, (255, 170, 80, a), (90, h - 40), r)
    surf.blit(glow, (0, 0))

    return surf


def _lerp(a, b, t: float):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
