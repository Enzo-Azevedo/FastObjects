import pytest

from fastobjects import Window


@pytest.fixture
def window():
    win = Window(320, 240, "test", visible=False)
    yield win
    win.close()


def test_window_creates_gl_context(window):
    assert window.ctx.version_code >= 330
    assert window.width == 320
    assert window.height == 240


def test_window_frame_cycle(window):
    window.poll()
    window.clear(0.1, 0.1, 0.1)
    window.swap()
    assert not window.should_close
