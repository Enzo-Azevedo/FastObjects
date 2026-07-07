"""Estado de input por polling (teclado/mouse), alimentado por callbacks glfw."""

from __future__ import annotations

import glfw
import numpy as np


class Keyboard:
    """Estado do teclado: keys[fo.KEY_SPACE] -> bool (True enquanto pressionada)."""

    def __init__(self) -> None:
        self._state = np.zeros(glfw.KEY_LAST + 1, dtype=bool)

    def __getitem__(self, key: int) -> bool:
        return bool(self._state[key])

    def _on_key(self, window, key: int, scancode: int, action: int, mods: int) -> None:
        if key < 0:  # glfw.KEY_UNKNOWN
            return
        if action == glfw.PRESS:
            self._state[key] = True
        elif action == glfw.RELEASE:
            self._state[key] = False
        # glfw.REPEAT não muda o estado: a tecla já está pressionada.


class Mouse:
    """Posição do cursor (pixels, y para baixo — igual ao renderer) e botões."""

    def __init__(self) -> None:
        self.x = 0.0
        self.y = 0.0
        self.left = False
        self.right = False
        self.middle = False

    def _on_move(self, window, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def _on_button(self, window, button: int, action: int, mods: int) -> None:
        pressed = action == glfw.PRESS
        if button == glfw.MOUSE_BUTTON_LEFT:
            self.left = pressed
        elif button == glfw.MOUSE_BUTTON_RIGHT:
            self.right = pressed
        elif button == glfw.MOUSE_BUTTON_MIDDLE:
            self.middle = pressed
