import glfw

import fastobjects as fo
from fastobjects import Window
from fastobjects.input import Keyboard, Mouse


def test_key_press_release_cycle():
    kb = Keyboard()
    assert not kb[glfw.KEY_SPACE]
    kb._on_key(None, glfw.KEY_SPACE, 0, glfw.PRESS, 0)
    assert kb[glfw.KEY_SPACE]
    kb._on_key(None, glfw.KEY_SPACE, 0, glfw.RELEASE, 0)
    assert not kb[glfw.KEY_SPACE]


def test_key_repeat_keeps_pressed():
    kb = Keyboard()
    kb._on_key(None, glfw.KEY_A, 0, glfw.PRESS, 0)
    kb._on_key(None, glfw.KEY_A, 0, glfw.REPEAT, 0)
    assert kb[glfw.KEY_A]


def test_unknown_key_is_ignored():
    kb = Keyboard()
    kb._on_key(None, glfw.KEY_UNKNOWN, 0, glfw.PRESS, 0)  # -1: não pode explodir
    assert not kb[glfw.KEY_SPACE]


def test_mouse_move_and_buttons():
    m = Mouse()
    m._on_move(None, 100.5, 200.25)
    assert m.x == 100.5
    assert m.y == 200.25
    m._on_button(None, glfw.MOUSE_BUTTON_LEFT, glfw.PRESS, 0)
    assert m.left and not m.right and not m.middle
    m._on_button(None, glfw.MOUSE_BUTTON_RIGHT, glfw.PRESS, 0)
    m._on_button(None, glfw.MOUSE_BUTTON_MIDDLE, glfw.PRESS, 0)
    assert m.left and m.right and m.middle
    m._on_button(None, glfw.MOUSE_BUTTON_LEFT, glfw.RELEASE, 0)
    assert not m.left and m.right


def test_constants_reexported():
    assert fo.KEY_SPACE == glfw.KEY_SPACE
    assert fo.KEY_ESCAPE == glfw.KEY_ESCAPE
    assert fo.MOUSE_BUTTON_LEFT == glfw.MOUSE_BUTTON_LEFT


def test_window_wires_input():
    win = Window(320, 240, "input", visible=False)
    assert not win.keys[fo.KEY_SPACE]
    assert win.mouse.x == 0.0
    assert not win.mouse.left
    win.close()
