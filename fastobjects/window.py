"""Janela glfw + contexto moderngl. A camada mais fina possível."""

from __future__ import annotations

import time
from typing import Callable

import glfw
import moderngl

from fastobjects import _context
from fastobjects.input import Keyboard, Mouse


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
        self._update: Callable[[float], None] | None = None
        self.keys = Keyboard()
        self.mouse = Mouse()
        glfw.set_key_callback(self._win, self.keys._on_key)
        glfw.set_cursor_pos_callback(self._win, self.mouse._on_move)
        glfw.set_mouse_button_callback(self._win, self.mouse._on_button)
        _context.set_current(self)

    def _require_open(self) -> None:
        if self._win is None:
            raise RuntimeError(
                "Janela já fechada — crie uma nova fo.Window(...) antes de usá-la."
            )

    @property
    def should_close(self) -> bool:
        self._require_open()
        return bool(glfw.window_should_close(self._win))

    def poll(self) -> None:
        glfw.poll_events()

    def clear(self, r: float, g: float, b: float) -> None:
        self.ctx.clear(r, g, b, 1.0)

    def swap(self) -> None:
        self._require_open()
        glfw.swap_buffers(self._win)

    def frame(self, fn: Callable[[float], None]) -> Callable[[float], None]:
        """Decorator: registra fn(dt) como o update chamado por run().

        Registrar uma nova função substitui a anterior.
        """
        self._update = fn
        return fn

    def draw(self, *batches) -> None:
        """Desenha cada batch na ordem dada (açúcar para batch.draw())."""
        for batch in batches:
            batch.draw()

    def request_close(self) -> None:
        """Pede o fim do loop: should_close passa a True e run() retorna."""
        self._require_open()
        glfw.set_window_should_close(self._win, True)

    def run(self) -> None:
        """Executa o loop de frames até a janela fechar.

        Por frame: poll de eventos, dt real (perf_counter), update(dt), swap.

        Raises:
            RuntimeError: se nenhuma função foi registrada com @win.frame.
        """
        self._require_open()
        if self._update is None:
            raise RuntimeError(
                "Nenhuma função de frame registrada — decore seu update com "
                "@win.frame antes de chamar win.run()."
            )
        last = time.perf_counter()
        while not self.should_close:
            self.poll()
            now = time.perf_counter()
            dt = now - last
            last = now
            self._update(dt)
            self.swap()

    def close(self) -> None:
        if _context.get_current() is self:
            _context.set_current(None)
        if self._win is not None:
            glfw.destroy_window(self._win)
            self._win = None
