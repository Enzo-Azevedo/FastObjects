import pytest

from fastobjects import Window, _context


def test_window_registers_as_current():
    win = Window(320, 240, "ctx", visible=False)
    assert _context.get_current() is win
    win.close()
    assert _context.get_current() is None


def test_second_window_becomes_current():
    a = Window(320, 240, "a", visible=False)
    b = Window(320, 240, "b", visible=False)
    assert _context.get_current() is b
    b.close()
    a.close()


def test_close_non_current_window_keeps_current():
    a = Window(320, 240, "a", visible=False)
    b = Window(320, 240, "b", visible=False)
    a.close()  # a não é a atual; b continua registrada
    assert _context.get_current() is b
    b.close()


def test_require_current_raises_actionable():
    _context.set_current(None)
    with pytest.raises(RuntimeError, match="fo.Window"):
        _context.require_current()


def test_resolve_uses_current_window():
    win = Window(320, 240, "res", visible=False)
    ctx, view_size = _context.resolve(None, None)
    assert ctx is win.ctx
    assert view_size == (320, 240)
    win.close()


def test_resolve_explicit_args_pass_through():
    _context.set_current(None)
    sentinel = object()
    ctx, view_size = _context.resolve(sentinel, (64, 64))
    assert ctx is sentinel
    assert view_size == (64, 64)
