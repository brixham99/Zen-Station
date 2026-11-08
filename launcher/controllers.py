"""Joystick / pad handling with hot-plug and Xbox vs PlayStation hints."""
from __future__ import annotations

from dataclasses import dataclass

import pygame

# Logical actions
ACT_LEFT = "left"
ACT_RIGHT = "right"
ACT_UP = "up"
ACT_DOWN = "down"
ACT_CONFIRM = "confirm"   # A / Cross
ACT_UPDATE = "update"     # Y / Triangle
ACT_BACK = "back"         # B / Circle
ACT_MENU = "menu"         # Start / Options


@dataclass
class PadHints:
    confirm: str
    update: str
    back: str
    navigate: str
    family: str  # "xbox" | "playstation" | "generic" | "keyboard"


def _name_family(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ("playstation", "dualshock", "dualsense", "ps4", "ps5", "sony")):
        return "playstation"
    if any(k in n for k in ("xbox", "x-box", "xinput", "microsoft")):
        return "xbox"
    return "generic"


def hints_for(family: str) -> PadHints:
    if family == "playstation":
        return PadHints("Cross", "Triangle", "Circle", "D-pad", "playstation")
    if family == "xbox":
        return PadHints("A", "Y", "B", "D-pad", "xbox")
    if family == "keyboard":
        return PadHints("Enter", "U", "Esc", "Arrows", "keyboard")
    return PadHints("A / Cross", "Y / Triangle", "B / Circle", "D-pad", "generic")


def format_hints(hints: PadHints) -> str:
    """Short on-screen legend; pad glyphs when a controller is connected."""
    if hints.family == "xbox":
        return f"{hints.navigate} move   {hints.confirm} play   {hints.update} update   {hints.back} back"
    if hints.family == "playstation":
        return f"{hints.navigate} move   {hints.confirm} play   {hints.update} update   {hints.back} back"
    if hints.family == "keyboard":
        return f"Arrow keys: move    Enter: play    U: update    Esc: back"
    return f"{hints.navigate}: move    {hints.confirm}: play    {hints.update}: update    {hints.back}: back"


class ControllerHub:
    """Tracks connected pads and maps events to logical actions."""

    def __init__(self) -> None:
        pygame.joystick.init()
        self.pads: dict[int, pygame.joystick.JoystickType] = {}
        self.family = "keyboard"
        self._hat = (0, 0)
        self._axis_cool = 0.0
        self._forced_family: str | None = None
        self.refresh()

    def refresh(self) -> None:
        self.pads.clear()
        count = pygame.joystick.get_count()
        for i in range(count):
            try:
                j = pygame.joystick.Joystick(i)
                j.init()
                self.pads[i] = j
            except pygame.error:
                continue
        if self._forced_family:
            self.family = self._forced_family
        elif self.pads:
            first = next(iter(self.pads.values()))
            self.family = _name_family(first.get_name())
        else:
            self.family = "keyboard"

    def force_family(self, family: str | None) -> None:
        """Override detected pad family (used by selftest / screenshots)."""
        self._forced_family = family
        if family:
            self.family = family

    @property
    def hints(self) -> PadHints:
        return hints_for(self._forced_family or self.family)

    def handle_event(self, event: pygame.event.Event) -> list[str]:
        actions: list[str] = []
        if event.type == pygame.JOYDEVICEADDED or event.type == pygame.JOYDEVICEREMOVED:
            self.refresh()
            return actions

        # Keyboard fallback
        if event.type == pygame.KEYDOWN:
            mapping = {
                pygame.K_LEFT: ACT_LEFT,
                pygame.K_RIGHT: ACT_RIGHT,
                pygame.K_UP: ACT_UP,
                pygame.K_DOWN: ACT_DOWN,
                pygame.K_RETURN: ACT_CONFIRM,
                pygame.K_KP_ENTER: ACT_CONFIRM,
                pygame.K_SPACE: ACT_CONFIRM,
                pygame.K_u: ACT_UPDATE,
                pygame.K_ESCAPE: ACT_BACK,
            }
            if event.key in mapping:
                actions.append(mapping[event.key])
            return actions

        # Buttons — SDL/Xbox layout: 0=A/Cross, 1=B/Circle, 2=X/Square, 3=Y/Triangle
        if event.type == pygame.JOYBUTTONDOWN:
            btn = event.button
            if btn == 0:
                actions.append(ACT_CONFIRM)
            elif btn == 3:
                actions.append(ACT_UPDATE)
            elif btn == 1:
                actions.append(ACT_BACK)
            elif btn in (7, 9):  # Start / Options (varies)
                actions.append(ACT_MENU)
            return actions

        if event.type == pygame.JOYHATMOTION:
            x, y = event.value
            if x < 0:
                actions.append(ACT_LEFT)
            elif x > 0:
                actions.append(ACT_RIGHT)
            if y > 0:
                actions.append(ACT_UP)
            elif y < 0:
                actions.append(ACT_DOWN)
            return actions

        return actions

    def buttons_held(self, *buttons: int) -> bool:
        """True while every listed button is held on any one pad."""
        for j in self.pads.values():
            try:
                if all(j.get_button(b) for b in buttons):
                    return True
            except pygame.error:
                continue
        return False

    def poll_sticks(self, dt: float) -> list[str]:
        """Edge-trigger left stick as D-pad with cooldown."""
        actions: list[str] = []
        self._axis_cool = max(0.0, self._axis_cool - dt)
        if self._axis_cool > 0 or not self.pads:
            return actions
        dead = 0.55
        for j in self.pads.values():
            try:
                if j.get_numaxes() < 2:
                    continue
                ax, ay = j.get_axis(0), j.get_axis(1)
            except pygame.error:
                continue
            if ax <= -dead:
                actions.append(ACT_LEFT)
            elif ax >= dead:
                actions.append(ACT_RIGHT)
            if ay <= -dead:
                actions.append(ACT_UP)
            elif ay >= dead:
                actions.append(ACT_DOWN)
            if actions:
                self._axis_cool = 0.28
                break
        return actions
