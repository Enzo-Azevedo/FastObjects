"""Janela glfw + contexto moderngl. A camada mais fina possível."""

from __future__ import annotations

import glfw
import moderngl


class Window:
    """Janela nativa com contexto OpenGL 3.3 core.

    Args:
        width: largura em pixels.
        height: altura em pixels.
        title: título da janela.
        vsync: sincronização vertical (OFF por padrão — benchmarks exigem).
        visible: janela visível (False para testes/offscreen).

    Raises:
        RuntimeError: se o glfw ou o contexto OpenGL não puderem ser criados.
    """

    def __init__(
        self,
        width: int,
        height: int,
        title: str = "fastobjects",
        vsync: bool = False,
        visible: bool = True,
    ) -> None:
        if not glfw.init():
            raise RuntimeError(
                "glfw.init() falhou — verifique se há um display/driver de vídeo disponível."
            )
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.VISIBLE, glfw.TRUE if visible else glfw.FALSE)
        self._win = glfw.create_window(width, height, title, None, None)
        if not self._win:
            glfw.terminate()
            raise RuntimeError(
                "Não foi possível criar a janela — driver sem suporte a OpenGL 3.3 core?"
            )
        glfw.make_context_current(self._win)
        glfw.swap_interval(1 if vsync else 0)
        self.ctx = moderngl.create_context()
        self.ctx.enable(moderngl.BLEND)
        self.width = width
        self.height = height

    @property
    def should_close(self) -> bool:
        return bool(glfw.window_should_close(self._win))

    def poll(self) -> None:
        glfw.poll_events()

    def clear(self, r: float, g: float, b: float) -> None:
        self.ctx.clear(r, g, b, 1.0)

    def swap(self) -> None:
        glfw.swap_buffers(self._win)

    def close(self) -> None:
        if self._win is not None:
            glfw.destroy_window(self._win)
            self._win = None
