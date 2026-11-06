"""Painted night-sky backdrop. Cosy feel. No moon / planet anywhere."""
from __future__ import annotations

import math
import random

import numpy as np
import pygame


def build_backdrop(w: int, h: int, seed: int = 42) -> pygame.Surface:
    rng = random.Random(seed)

    # Build at 2× then smoothscale down — kills 8-bit gradient banding.
    ww, hh = w * 2, h * 2
    top = np.array([8, 10, 28], dtype=np.float32)
    upper = np.array([14, 18, 42], dtype=np.float32)
    mid = np.array([24, 22, 44], dtype=np.float32)
    warm = np.array([40, 28, 26], dtype=np.float32)
    ground = np.array([18, 14, 14], dtype=np.float32)

    ys = np.linspace(0.0, 1.0, hh, dtype=np.float32)
    cols = np.zeros((hh, 3), dtype=np.float32)
    for i, t in enumerate(ys):
        if t < 0.38:
            u = _smooth(t / 0.38)
            cols[i] = top * (1 - u) + upper * u
        elif t < 0.68:
            u = _smooth((t - 0.38) / 0.30)
            cols[i] = upper * (1 - u) + mid * u
        elif t < 0.88:
            u = _smooth((t - 0.68) / 0.20)
            cols[i] = mid * (1 - u) + warm * u
        else:
            u = _smooth((t - 0.88) / 0.12)
            cols[i] = warm * (1 - u) + ground * u

    # Tiny blue-noise style dither (±0.6) so remaining quantisation is invisible
    noise = (rng.random() for _ in range(1))  # noqa — seed only
    rng2 = np.random.RandomState(seed)
    dither = rng2.uniform(-0.6, 0.6, size=(hh, 3)).astype(np.float32)
    cols = np.clip(cols + dither, 0, 255)

    big = np.zeros((hh, ww, 3), dtype=np.uint8)
    big[:, :, :] = cols[:, None, :].astype(np.uint8)

    # Stars (single pixels on the hi-res buffer)
    for _ in range(280):
        x = rng.randint(0, ww - 1)
        y = rng.randint(0, int(hh * 0.58))
        bright = rng.randint(160, 255)
        big[y, x] = (
            min(255, int(big[y, x, 0] * 0.3 + bright * 0.7)),
            min(255, int(big[y, x, 1] * 0.3 + bright * 0.7)),
            min(255, int(big[y, x, 2] * 0.3 + bright * 0.85)),
        )

    surf = pygame.surfarray.make_surface(np.transpose(big, (1, 0, 2)))
    surf = pygame.transform.smoothscale(surf, (w, h)).convert()

    # Hedge / rooftop silhouette
    sil = pygame.Surface((w, h), pygame.SRCALPHA)
    base_y = int(h * 0.82)
    pts = [(0, h)]
    x = 0
    while x <= w:
        bump = int(12 * math.sin(x * 0.011 + 0.5) + 7 * math.sin(x * 0.027))
        pts.append((x, base_y + bump))
        x += 4
    pts.append((w, h))
    pygame.draw.polygon(sil, (4, 5, 10, 240), pts)

    roofs = [
        (70, 64, 46),
        (200, 84, 60),
        (400, 56, 42),
        (760, 78, 56),
        (960, 52, 44),
        (1120, 70, 52),
    ]
    for rx, rw, rh in roofs:
        top_y = base_y - rh + int(5 * math.sin(rx * 0.01))
        pygame.draw.rect(sil, (4, 5, 10, 250), (rx, top_y, rw, h - top_y))
        pygame.draw.polygon(
            sil,
            (4, 5, 10, 255),
            [(rx - 3, top_y + 6), (rx + rw // 2, top_y - 12), (rx + rw + 3, top_y + 6)],
        )
        if rw > 40:
            pygame.draw.rect(
                sil,
                (150, 105, 50, 40),
                (rx + rw // 2 - 2, top_y + rh // 2, 5, 6),
            )

    # Soft feather: blit silhouette slightly raised with low alpha first
    feather = pygame.Surface((w, h), pygame.SRCALPHA)
    feather.blit(sil, (0, -3))
    feather.set_alpha(70)
    surf.blit(feather, (0, 0))
    surf.blit(sil, (0, 0))
    return surf


def _smooth(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)
