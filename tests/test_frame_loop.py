import pytest

from fastobjects import Window


@pytest.fixture
def win():
    w = Window(320, 240, "loop", visible=False)
    yield w
    w.close()


def test_run_calls_update_until_close(win):
    dts = []

    @win.frame
    def update(dt):
        dts.append(dt)
        if len(dts) >= 3:
            win.request_close()

    win.run()
    assert len(dts) == 3
    assert all(dt >= 0.0 for dt in dts)  # perf_counter é monotônico


def test_frame_reregister_replaces(win):
    calls = []

    @win.frame
    def a(dt):
        calls.append("a")
        win.request_close()

    @win.frame
    def b(dt):
        calls.append("b")
        win.request_close()

    win.run()
    assert calls == ["b"]


def test_run_without_frame_raises_actionable(win):
    with pytest.raises(RuntimeError, match="win.frame"):
        win.run()


def test_draw_calls_batches_in_order(win):
    calls = []

    class Fake:
        def __init__(self, tag):
            self.tag = tag

        def draw(self):
            calls.append(self.tag)

    win.draw(Fake("a"), Fake("b"))
    assert calls == ["a", "b"]
