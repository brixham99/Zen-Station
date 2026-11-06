"""Load or generate game tile images."""
from __future__ import annotations

from pathlib import Path

import pygame

from .config import ROOT, GameEntry, bundled_thumbnail


TILE_W, TILE_H = 280, 158  # 16:9-ish cards


def name_card(name: str, size: tuple[int, int] = (TILE_W, TILE_H)) -> pygame.Surface:
    w, h = size
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    # gradient card
    for y in range(h):
        t = y / max(1, h - 1)
        col = (
            int(28 + 20 * t),
            int(34 + 18 * t),
            int(58 + 10 * (1 - t)),
            255,
        )
        pygame.draw.line(s, col, (0, y), (w, y))
    pygame.draw.rect(s, (220, 200, 140, 80), s.get_rect(), 2, border_radius=10)
    font = _font(36)
    # wrap name
    words = name.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if font.size(trial)[0] <= w - 24:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    total_h = sum(font.size(ln)[1] for ln in lines)
    y = (h - total_h) // 2
    for ln in lines:
        img = font.render(ln, True, (240, 230, 210))
        s.blit(img, ((w - img.get_width()) // 2, y))
        y += img.get_height()
    return s


def load_tile(game: GameEntry, games_dir: Path) -> pygame.Surface:
    candidates: list[Path] = []
    if game.thumbnail:
        bundled = bundled_thumbnail(game.thumbnail)
        if bundled:
            candidates.append(bundled)
        # also allow absolute / games-dir relative
        p = Path(game.thumbnail)
        if not p.is_absolute():
            candidates.append(ROOT / game.thumbnail)
            candidates.append(games_dir / game.folder / game.thumbnail)
        else:
            candidates.append(p)
    # Common title-art locations inside the game repo
    gp = game.path_under(games_dir)
    candidates.extend(
        [
            gp / "assets" / "art" / "title.jpg",
            gp / "assets" / "art" / "title.png",
            gp / "assets" / "art" / "title_backdrop.jpg",
            gp / "assets" / "title.png",
        ]
    )
    for path in candidates:
        if path.is_file():
            try:
                img = pygame.image.load(str(path)).convert()
                return _fit(img, (TILE_W, TILE_H))
            except pygame.error:
                continue
    return name_card(game.name)


def _fit(img: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
    tw, th = size
    iw, ih = img.get_size()
    scale = max(tw / iw, th / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    scaled = pygame.transform.smoothscale(img, (nw, nh))
    out = pygame.Surface((tw, th))
    out.blit(scaled, ((tw - nw) // 2, (th - nh) // 2))
    return out


_font_cache: dict[int, pygame.font.Font] = {}


def clear_font_cache() -> None:
    _font_cache.clear()


def _font(size: int) -> pygame.font.Font:
    if not pygame.font.get_init():
        pygame.font.init()
        _font_cache.clear()
    font = _font_cache.get(size)
    if font is not None:
        try:
            font.size("A")
            return font
        except pygame.error:
            _font_cache.clear()
    font = pygame.font.SysFont("dejavusans", size, bold=True)
    _font_cache[size] = font
    return font
