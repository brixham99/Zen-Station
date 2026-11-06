"""Games Box launcher entry point."""
from __future__ import annotations

import argparse
import os
import sys
import threading
from pathlib import Path

# Headless / selftest may set dummy drivers before import
import pygame

from . import __version__
from .config import ROOT, load_config
from .controllers import (
    ACT_BACK,
    ACT_CONFIRM,
    ACT_LEFT,
    ACT_RIGHT,
    ACT_UPDATE,
    ControllerHub,
)
from .launch import launch_game, launch_kodi, power_off
from .ui import EXIT_ID, POWER_ID, TV_ID, HomeScreen
from .thumbnails import clear_font_cache
from .updates import UpdateService


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Games Box home screen")
    p.add_argument("--windowed", action="store_true", help="Run in a window (for testing)")
    p.add_argument("--fullscreen", action="store_true", help="Force full screen")
    p.add_argument("--config", type=Path, default=None, help="Path to games.json")
    p.add_argument("--games-dir", type=Path, default=None, help="Override games directory")
    p.add_argument("--once", action="store_true", help="Draw one frame and exit (selftest)")
    p.add_argument("--screenshot", type=Path, default=None, help="Save a PNG and exit")
    p.add_argument("--select", type=int, default=None, help="Select tile index before shot")
    p.add_argument("--fake-update", action="append", default=[], help="Mark game id as having an update")
    p.add_argument("--confirm-power", action="store_true", help="Show power-off confirm (for shots)")
    p.add_argument("--no-updates", action="store_true", help="Skip background git checks")
    p.add_argument("--fake-pad", choices=("xbox", "playstation", "keyboard"), default=None,
                   help="Force on-screen button hints as if this pad were connected")
    p.add_argument("--version", action="version", version=f"Games Box {__version__}")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config)
    if args.games_dir:
        config.settings.games_dir = Path(args.games_dir).expanduser().resolve()

    pygame.init()
    pygame.font.init()
    clear_font_cache()
    pygame.display.set_caption("Games Box")
    flags = 0
    if args.windowed:
        flags = 0
    elif args.fullscreen or not args.windowed:
        # On the Pi we want fullscreen scaled; windowed only when asked
        if not args.screenshot and not args.once and not os.environ.get("SDL_VIDEODRIVER") == "dummy":
            flags = pygame.FULLSCREEN | pygame.SCALED
        else:
            flags = 0
    # Screenshots / dummy: always plain window size
    if args.screenshot or args.once or os.environ.get("SDL_VIDEODRIVER") == "dummy":
        flags = 0
        args.windowed = True

    screen = pygame.display.set_mode((config.settings.width, config.settings.height), flags)
    clock = pygame.time.Clock()

    hub = ControllerHub()
    if args.fake_pad:
        hub.force_family(args.fake_pad)
    ui = HomeScreen(config)
    for gid in args.fake_update:
        ui.state.fake_updates.add(gid)
    ui.reload_tiles()

    updates = UpdateService(config)
    if not args.no_updates and not args.screenshot and not args.once:
        # Clone any missing games in a background thread, then start checks
        def boot() -> None:
            updates.ensure_all_cloned()
            updates.start()

        threading.Thread(target=boot, name="gb-boot", daemon=True).start()

    if args.select is not None:
        ui.state.selected = max(0, min(args.select, len(ui.tiles) - 1))
        ui._ensure_visible()
    if args.confirm_power:
        ui.state.confirm_power = True

    running = True
    pending_action = None  # set when leaving to launch something

    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue
            for act in hub.handle_event(event):
                pending_action = _handle_action(act, ui, updates, hub) or pending_action

        for act in hub.poll_sticks(dt):
            pending_action = _handle_action(act, ui, updates, hub) or pending_action

        # Refresh update badges
        ui.set_update_flags(updates.status.available)

        status = updates.status.message
        if updates.status.offline and not status:
            status = "Offline"
        ui.draw(screen, hub.hints, status_msg=status)
        pygame.display.flip()

        if args.screenshot:
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(screen, str(args.screenshot))
            running = False
        elif args.once:
            running = False

        if pending_action:
            action = pending_action
            pending_action = None
            if action == "quit":
                running = False
            elif action == "power":
                pygame.quit()
                power_off()
                return 0
            elif action == "tv":
                _suspend_display()
                try:
                    launch_kodi()
                except FileNotFoundError:
                    ui.flash("Kodi is not installed")
                _resume_display(screen, config, args)
                hub.refresh()
            elif isinstance(action, tuple) and action[0] == "game":
                game = action[1]
                _suspend_display()
                try:
                    launch_game(game, config.settings.games_dir)
                except FileNotFoundError:
                    ui.flash(f"{game.name} is not installed yet")
                except Exception as e:  # noqa: BLE001
                    ui.flash(f"Could not start {game.name}")
                    print(e, file=sys.stderr)
                _resume_display(screen, config, args)
                hub.refresh()

    pygame.quit()
    updates.stop()
    return 0


def _handle_action(act: str, ui: HomeScreen, updates: UpdateService, hub: ControllerHub):
    if ui.state.confirm_power:
        if act == ACT_CONFIRM:
            return "power"
        if act == ACT_BACK:
            ui.state.confirm_power = False
        return None

    if act == ACT_LEFT:
        ui.move(-1)
    elif act == ACT_RIGHT:
        ui.move(1)
    elif act == ACT_BACK:
        # ignore on home
        pass
    elif act == ACT_UPDATE:
        tile = ui.current()
        if not tile:
            return None
        if tile.kind == "game" and tile.entry:
            if updates.status.offline:
                ui.flash("Offline")
                return None

            def do_pull() -> None:
                msg = updates.pull_game(tile.entry)
                if msg == "ok":
                    ui.flash(f"{tile.name} updated")
                elif msg == "offline":
                    ui.flash("Offline")
                else:
                    ui.flash(msg)

            threading.Thread(target=do_pull, daemon=True).start()
        elif tile.id == TV_ID:
            ui.flash("Nothing to update for TV")
        else:
            # Try launcher self-update when on an action tile with Y
            def do_self() -> None:
                msg = updates.pull_launcher()
                if msg == "ok":
                    ui.flash("Games Box updated — restart to apply")
                elif msg == "offline":
                    ui.flash("Offline")
                else:
                    ui.flash(msg)

            threading.Thread(target=do_self, daemon=True).start()
    elif act == ACT_CONFIRM:
        tile = ui.current()
        if not tile or not tile.enabled:
            if tile and tile.id == TV_ID:
                ui.flash("Install Kodi to use TV")
            return None
        if tile.id == POWER_ID:
            ui.state.confirm_power = True
            return None
        if tile.id == EXIT_ID:
            return "quit"
        if tile.id == TV_ID:
            return "tv"
        if tile.kind == "game" and tile.entry:
            return ("game", tile.entry)
    return None


def _suspend_display() -> None:
    pygame.display.quit()


def _resume_display(screen_holder, config, args) -> None:
    pygame.display.init()
    flags = 0
    if not args.windowed and os.environ.get("SDL_VIDEODRIVER") != "dummy":
        flags = pygame.FULLSCREEN | pygame.SCALED
    pygame.display.set_mode((config.settings.width, config.settings.height), flags)
    pygame.display.set_caption("Games Box")


if __name__ == "__main__":
    raise SystemExit(main())
