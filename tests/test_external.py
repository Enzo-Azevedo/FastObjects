import moderngl
import numpy as np
import pytest

import fastobjects as fo
from fastobjects import Window, _context
from fastobjects.shapes import ShapeBatch


def test_attach_registers_external_window_as_current():
    host = Window(320, 240, "host", visible=False)  # host GL genérico
    ext = fo.attach(view_size=(320, 240))
    assert isinstance(ext, fo.ExternalWindow)
    assert _context.get_current() is ext
    assert (ext.width, ext.height) == (320, 240)
    ext.close()
    assert _context.get_current() is None
    host.close()


def test_attach_implicit_batch_draws_pixels():
    host = Window(320, 240, "host2", visible=False)
    ext = fo.attach(view_size=(320, 240))
    fbo = ext.ctx.framebuffer(color_attachments=[ext.ctx.texture((64, 64), 4)])
    fbo.use()
    fbo.clear(0.0, 0.0, 0.0, 1.0)
    batch = ShapeBatch(capacity=4, view_size=(64, 64))  # ctx implícito do attach
    batch.rects(1, x=32.0, y=32.0, w=20.0, h=20.0, color=(1.0, 0.0, 0.0, 1.0))
    batch.draw()
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(64, 64, 4)[::-1]
    assert raw[32, 32][0] > 200
    ext.close()
    host.close()


def test_external_window_clear_fills_target():
    host = Window(320, 240, "host3", visible=False)
    ext = fo.attach(view_size=(320, 240))
    fbo = ext.ctx.framebuffer(color_attachments=[ext.ctx.texture((8, 8), 4)])
    fbo.use()
    ext.clear(1.0, 0.0, 0.0)
    raw = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(8, 8, 4)
    assert raw[:, :, 0].min() > 200
    ext.close()
    host.close()


def test_attach_without_gl_context_raises_actionable(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("cannot detect context")

    monkeypatch.setattr(moderngl, "create_context", boom)
    with pytest.raises(RuntimeError, match="pygame.OPENGL"):
        fo.attach(view_size=(100, 100))
