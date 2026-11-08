"""Home-screen layout: scrolling tiles, badges, confirms, button hints."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pygame

from .backdrop import build_backdrop
from .config import Config, GameEntry
from .controllers import PadHints, format_hints
from .launch import kodi_available
from .thumbnails import TILE_H, TILE_W, load_tile, name_card


# Synthetic tiles appended after games
TV_ID = "__tv__"
POWER_ID = "__power__"
EXIT_ID = "__exit__"
LAUNCHER_UPDATE_ID = "__launcher_update__"

# Fixed baseline for title labels (so selected scale doesn't shift text)
NAME_Y_OFFSET = 18


@dataclass
class Tile:
    id: str
    name: str
    kind: str  # game | tv | action
    entry: GameEntry | None = None
    image: pygame.Surface | None = None
    enabled: bool = True
    update_available: bool = False
    just_updated: bool = False
    up_to_date_until: float = 0.0   # a brief "Up to date" after Y found nothing new


@dataclass
class UIState:
    selected: int = 0
    scroll_x: float = 0.0
    confirm_power: bool = False
    message: str = ""
    message_until: float = 0.0
    fake_updates: set[str] = field(default_factory=set)  # for screenshots / selftest


class HomeScreen:
    GAP = 32
    TILE_SCALE_SEL = 1.10
    ROW_Y = 268
    SIDE_MARGIN = 64

    def __init__(self, config: Config, clock_fn=pygame.time.get_ticks) -> None:
        self.config = config
        self.w = config.settings.width
        self.h = config.settings.height
        self.clock_fn = clock_fn
        self.backdrop = build_backdrop(self.w, self.h)
        self.state = UIState()
        self.tiles: list[Tile] = []
        self._font_title = pygame.font.SysFont("dejavusans", 54, bold=True)
        self._font_name = pygame.font.SysFont("dejavusans", 24, bold=True)
        self._font_small = pygame.font.SysFont("dejavusans", 20)
        self._font_badge = pygame.font.SysFont("dejavusans", 16, bold=True)
        self._font_hint = pygame.font.SysFont("dejavusans", 22)
        self.reload_tiles()

    def reload_tiles(self, update_flags: dict[str, bool] | None = None) -> None:
        update_flags = update_flags or {}
        games_dir = self.config.settings.games_dir
        tiles: list[Tile] = []
        for g in self.config.games:
            img = load_tile(g, games_dir)
            tiles.append(
                Tile(
                    id=g.id,
                    name=g.name,
                    kind="game",
                    entry=g,
                    image=img,
                    enabled=True,
                    update_available=bool(update_flags.get(g.id))
                    or g.id in self.state.fake_updates,
                )
            )
        if self.config.settings.include_system_tiles:
            # TV / Kodi
            has_kodi = kodi_available()
            tv_img = name_card("TV")
            if not has_kodi:
                tv_img = tv_img.copy()
                shade = pygame.Surface(tv_img.get_size(), pygame.SRCALPHA)
                shade.fill((0, 0, 0, 120))
                tv_img.blit(shade, (0, 0))
            tiles.append(
                Tile(
                    id=TV_ID,
                    name="TV" if has_kodi else "TV (Kodi not installed)",
                    kind="tv",
                    image=tv_img,
                    enabled=has_kodi,
                )
            )
            tiles.append(
                Tile(
                    id=POWER_ID,
                    name="Power off",
                    kind="action",
                    image=name_card("Power off"),
                    enabled=True,
                )
            )
        self.tiles = tiles
        if self.state.selected >= len(self.tiles):
            self.state.selected = max(0, len(self.tiles) - 1)
        self._ensure_visible()

    def set_update_flags(self, flags: dict[str, bool], updated: set[str] | None = None) -> None:
        updated = updated or set()
        for t in self.tiles:
            if t.kind == "game":
                t.update_available = bool(flags.get(t.id)) or t.id in self.state.fake_updates
                t.just_updated = (t.id in updated) and not t.update_available

    def mark_up_to_date(self, tile_id: str, seconds: float = 2.5) -> None:
        until = self.clock_fn() / 1000.0 + seconds
        for t in self.tiles:
            if t.id == tile_id:
                t.up_to_date_until = until

    def move(self, delta: int) -> None:
        if self.state.confirm_power:
            return
        n = len(self.tiles)
        if n == 0:
            return
        self.state.selected = (self.state.selected + delta) % n
        self._ensure_visible()

    def current(self) -> Tile | None:
        if not self.tiles:
            return None
        return self.tiles[self.state.selected]

    def flash(self, msg: str, seconds: float = 2.5) -> None:
        self.state.message = msg
        self.state.message_until = self.clock_fn() / 1000.0 + seconds

    def _slot_w(self) -> float:
        return TILE_W + self.GAP

    def _content_width(self) -> float:
        if not self.tiles:
            return 0.0
        return len(self.tiles) * self._slot_w() - self.GAP

    def _all_fit(self) -> bool:
        return self._content_width() <= (self.w - 2 * self.SIDE_MARGIN)

    def _ensure_visible(self) -> None:
        """Keep selection on-screen with side margins; centre the row when it fits."""
        if not self.tiles:
            self.state.scroll_x = 0.0
            return
        slot = self._slot_w()
        content = self._content_width()
        # Extra pad so a scaled-up selected tile never kisses the screen edge
        scale_pad = int(TILE_W * (self.TILE_SCALE_SEL - 1.0) / 2) + 8
        margin = self.SIDE_MARGIN + scale_pad
        avail = self.w - 2 * margin
        if content <= avail:
            self.state.scroll_x = -(self.w - content) / 2
            return
        selected_centre = self.state.selected * slot + TILE_W / 2
        ideal = selected_centre - self.w / 2
        max_scroll = content - self.w + margin
        min_scroll = -margin
        self.state.scroll_x = max(min_scroll, min(max_scroll, ideal))

    def _tile_x(self, index: int) -> float:
        return index * self._slot_w() - self.state.scroll_x

    def draw(self, screen: pygame.Surface, hints: PadHints, status_msg: str = "") -> None:
        screen.blit(self.backdrop, (0, 0))

        title = self._font_title.render("Zen Station", True, (245, 235, 210))
        screen.blit(title, ((self.w - title.get_width()) // 2, 42))
        sub_y = 104
        for line in ("Anderson Family - Gaming Creations", "\u00a9 2026 - Made in England"):
            sub = self._font_small.render(line, True, (180, 170, 150))
            screen.blit(sub, ((self.w - sub.get_width()) // 2, sub_y))
            sub_y += sub.get_height() + 2

        base_y = self.ROW_Y
        # Fixed name baseline so selected scale doesn't push labels down
        # Shared baseline below the *scaled* selected height so every label shares one line
        name_y = base_y + int(TILE_H * self.TILE_SCALE_SEL) + NAME_Y_OFFSET

        for i, tile in enumerate(self.tiles):
            selected = i == self.state.selected
            scale = self.TILE_SCALE_SEL if selected else 1.0
            tw, th = int(TILE_W * scale), int(TILE_H * scale)
            # Centre larger selected tile on its slot
            slot_x = self._tile_x(i)
            rect = pygame.Rect(
                int(slot_x - (tw - TILE_W) / 2),
                base_y + (TILE_H - th) // 2,
                tw,
                th,
            )

            # Skip if fully off-screen (with a little margin)
            if rect.right < -40 or rect.left > self.w + 40:
                continue

            img = tile.image or name_card(tile.name)
            if img.get_size() != (tw, th):
                img = pygame.transform.smoothscale(img, (tw, th))

            # Fade tiles that sit partially off the edge (carousel feel)
            fade = 255
            edge = self.SIDE_MARGIN + 24
            if rect.centerx < edge:
                fade = int(255 * max(0.20, rect.centerx / edge))
            elif rect.centerx > self.w - edge:
                fade = int(255 * max(0.20, (self.w - rect.centerx) / edge))
            if not selected and fade < 255:
                img = img.copy()
                img.set_alpha(fade)

            shadow = pygame.Surface((tw + 8, th + 8), pygame.SRCALPHA)
            shadow.fill((0, 0, 0, 70 if selected else 50))
            screen.blit(shadow, (rect.x + 5, rect.y + 7))

            screen.blit(img, rect.topleft)
            border_col = (255, 210, 110) if selected else (90, 85, 75)
            width = 4 if selected else 2
            pygame.draw.rect(screen, border_col, rect, width, border_radius=12)

            if not tile.enabled:
                dim = pygame.Surface((tw, th), pygame.SRCALPHA)
                dim.fill((0, 0, 0, 110))
                screen.blit(dim, rect.topleft)

            if tile.update_available:
                badge = self._font_badge.render("Update available", True, (20, 20, 20))
                bw, bh = badge.get_width() + 16, badge.get_height() + 8
                br = pygame.Rect(rect.right - bw - 8, rect.top + 8, bw, bh)
                pygame.draw.rect(screen, (255, 200, 70), br, border_radius=8)
                screen.blit(badge, (br.x + 8, br.y + 4))
            elif getattr(tile, "up_to_date_until", 0.0) > self.clock_fn() / 1000.0:
                badge = self._font_badge.render("Up to date", True, (255, 255, 255))
                bw, bh = badge.get_width() + 16, badge.get_height() + 8
                br = pygame.Rect(rect.right - bw - 8, rect.top + 8, bw, bh)
                pygame.draw.rect(screen, (70, 110, 160), br, border_radius=8)
                screen.blit(badge, (br.x + 8, br.y + 4))
            elif getattr(tile, "just_updated", False):
                badge = self._font_badge.render("Updated", True, (255, 255, 255))
                bw, bh = badge.get_width() + 16, badge.get_height() + 8
                br = pygame.Rect(rect.right - bw - 8, rect.top + 8, bw, bh)
                pygame.draw.rect(screen, (46, 160, 67), br, border_radius=8)
                screen.blit(badge, (br.x + 8, br.y + 4))

            name_col = (250, 240, 220) if selected else (170, 160, 145)
            name = self._font_name.render(tile.name, True, name_col)
            if fade < 255 and not selected:
                name.set_alpha(fade)
            screen.blit(name, (rect.centerx - name.get_width() // 2, name_y))

        # Dots only when the row needs scrolling
        if not self._all_fit() and len(self.tiles) > 1:
            self._draw_scroll_hint(screen, name_y + 36)

        msg = status_msg
        now = self.clock_fn() / 1000.0
        if self.state.message and now < self.state.message_until:
            msg = self.state.message
        elif self.state.message and now >= self.state.message_until:
            self.state.message = ""
        if msg:
            banner = self._font_hint.render(msg, True, (240, 230, 200))
            bg = pygame.Surface((banner.get_width() + 28, banner.get_height() + 14), pygame.SRCALPHA)
            bg.fill((20, 16, 12, 180))
            bx = (self.w - bg.get_width()) // 2
            by = self.h - 110
            screen.blit(bg, (bx, by))
            screen.blit(banner, (bx + 14, by + 7))

        hint = format_hints(hints)
        hint_s = self._font_hint.render(hint, True, (160, 150, 135))
        screen.blit(hint_s, ((self.w - hint_s.get_width()) // 2, self.h - 48))

        if self.state.confirm_power:
            self._draw_confirm(screen, hints)

    def _draw_scroll_hint(self, screen: pygame.Surface, dot_y: int) -> None:
        n = len(self.tiles)
        total_w = n * 14
        x0 = (self.w - total_w) // 2
        for i in range(n):
            col = (255, 210, 110) if i == self.state.selected else (80, 75, 65)
            pygame.draw.circle(screen, col, (x0 + i * 14 + 5, dot_y), 4)

    def _draw_confirm(self, screen: pygame.Surface, hints: PadHints) -> None:
        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))
        box_w, box_h = 560, 220
        box = pygame.Rect((self.w - box_w) // 2, (self.h - box_h) // 2, box_w, box_h)
        pygame.draw.rect(screen, (36, 28, 22), box, border_radius=16)
        pygame.draw.rect(screen, (255, 210, 110), box, 3, border_radius=16)
        q = self._font_name.render("Power off the Pi?", True, (245, 235, 210))
        screen.blit(q, (box.centerx - q.get_width() // 2, box.y + 48))
        a = self._font_hint.render(
            f"{hints.confirm}: yes, power off     {hints.back}: cancel",
            True,
            (200, 190, 170),
        )
        screen.blit(a, (box.centerx - a.get_width() // 2, box.y + 120))
