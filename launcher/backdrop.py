"""Launcher backdrops: brushed-metal industrial (default) and the older night sky."""
from __future__ import annotations

import math
import random

import numpy as np
import pygame


def build_night_backdrop(w: int, h: int, seed: int = 42) -> pygame.Surface:
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


def build_backdrop(w: int, h: int, seed: int = 7) -> pygame.Surface:
    return build_metal_backdrop(w, h, seed)


def _blur_x(a: np.ndarray, k: int) -> np.ndarray:
    """Box blur along x (wrap), repeated for a softer streak."""
    out = a
    for _ in range(3):
        c = np.cumsum(np.concatenate([out[:, -k:], out, out[:, :k]], axis=1), axis=1)
        out = (c[:, 2 * k:] - c[:, :-2 * k])[:, : a.shape[1]] / (2 * k)
    return out


def build_metal_backdrop(w: int, h: int, seed: int = 7) -> pygame.Surface:
    """Muted grey, industrial abstract: brushed steel panels, bevelled seams,
    rivets, a diagonal sheen and a soft vignette. No bright colours."""
    rng = np.random.RandomState(seed)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)

    # Base: dark gunmetal with a faint cool tint
    base = 46.0 + 10.0 * (1.0 - ys / h)

    # Brushed grain: noise smeared along x
    grain = _blur_x(rng.normal(0, 1, (h, w)).astype(np.float32), 60)
    grain = grain / (np.abs(grain).max() or 1.0)
    fine = rng.normal(0, 1, (h, w)).astype(np.float32) * 0.6

    # Large abstract panels: diagonal plates at two angles, each a little
    # lighter or darker, with brushing direction implied by the sheen.
    lum = base + grain * 7.0 + fine
    plates = [
        # (normal angle deg, offset px, shade)
        (62, 0.18, +7), (62, 0.47, -5), (62, 0.80, +4),
        (-28, 0.30, -6), (-28, 0.68, +5),
    ]
    seams = np.zeros((h, w), np.float32)
    shade = np.zeros((h, w), np.float32)
    diag = np.hypot(w, h)
    for ang, off, sh in plates:
        a = np.radians(ang)
        d = xs * np.cos(a) + ys * np.sin(a)
        d0 = off * diag * (1 if np.cos(a) + np.sin(a) > 0 else 0)
        d = d - d0 if np.cos(a) + np.sin(a) > 0 else d - (off * w * np.cos(a))
        shade += np.where(d > 0, sh, 0.0)
        # bevel: dark groove with a lit edge 2 px further on
        seams += -26.0 * np.exp(-(d / 1.6) ** 2) + 14.0 * np.exp(-((d - 3.0) / 1.4) ** 2)
    lum += shade * 0.8 + seams

    # Diagonal sheen sweeping across, like light on steel
    sheen = np.exp(-(((xs - ys * 1.2) - w * 0.55) / (w * 0.22)) ** 2) * 16.0
    sheen += np.exp(-(((xs - ys * 1.2) - w * 0.05) / (w * 0.10)) ** 2) * 6.0
    lum += sheen

    # Vignette
    cx, cy = w / 2, h * 0.45
    r = np.hypot((xs - cx) / (w * 0.75), (ys - cy) / (h * 0.85))
    lum *= np.clip(1.08 - 0.55 * r ** 2, 0.45, 1.0)

    # Bottom band behind the hints: a darker brushed strip with a lit lip
    band_top = int(h * 0.88)
    lum[band_top:] *= 0.62
    lum[band_top:band_top + 1] += 22
    lum[band_top + 1:band_top + 3] -= 10

    lum = np.clip(lum, 0, 255)
    rgb = np.stack([lum * 0.97, lum * 0.99, lum * 1.04], axis=-1)
    rgb += rng.uniform(-0.5, 0.5, rgb.shape)  # dither against banding
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)

    surf = pygame.surfarray.make_surface(np.transpose(rgb, (1, 0, 2)))
    try:
        surf = surf.convert()
    except pygame.error:
        pass

    # Rivets along the bottom band and in two corners
    def rivet(x: int, y: int) -> None:
        pygame.draw.circle(surf, (22, 23, 26), (x + 1, y + 1), 4)
        pygame.draw.circle(surf, (78, 80, 86), (x, y), 4)
        pygame.draw.circle(surf, (120, 122, 128), (x - 1, y - 1), 2)

    ry = band_top + (h - band_top) // 2
    for x in (24, w - 24):
        rivet(x, ry)
    for x, y in ((24, 24), (w - 24, 24)):
        rivet(x, y)
    return surf
