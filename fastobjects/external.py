"""Attach a janelas de hosts externos (pygame, pyglet, ...) via contexto GL corrente."""

from __future__ import annotations

import moderngl

from fastobjects import _context


class ExternalWindow:
    """Janela de um host externo à qual o FastObjects se conectou.

    O host é dono do loop, dos eventos, do input e do swap/flip; este objeto
    expõe apenas o contexto GL e utilitários de render.

    Args:
        ctx: contexto moderngl conectado ao contexto GL do host.
        width: largura da área de render do host, em pixels.
        height: altura da área de render do host, em pixels.
    """

    def __init__(self, ctx: moderngl.Context, width: int, height: int) -> None:
        self.ctx = ctx
        self.width = width
        self.height = height

    def clear(self, r: float, g: float, b: float) -> None:
        """Limpa o alvo de render atual com a cor dada."""
        self.ctx.clear(r, g, b, 1.0)

    def close(self) -> None:
        """Desregistra esta janela como atual (o host continua dono da janela)."""
        if _context.get_current() is self:
            _context.set_current(None)


def attach(view_size: tuple[int, int]) -> ExternalWindow:
    """Conecta o FastObjects ao contexto OpenGL corrente do host.

    Chame DEPOIS de o host criar a janela com contexto OpenGL. A janela
    externa vira a "atual": batches criados sem ctx explícito passam a
    usá-la, como no modo nativo.

    Chame UMA vez por janela do host: attaches repetidos criam wrappers
    moderngl independentes sobre o mesmo contexto GL e podem dessincronizar
    o estado entre eles.

    Args:
        view_size: (largura, altura) da área de render do host, em pixels.

    Returns:
        ExternalWindow registrado como janela atual.

    Raises:
        RuntimeError: se não houver contexto OpenGL ativo no processo.
    """
    try:
        ctx = moderngl.create_context()
    except Exception as exc:
        raise RuntimeError(
            "Nenhum contexto OpenGL ativo. Crie a janela do host com OpenGL "
            "antes de fo.attach() — ex.: pygame.display.set_mode((w, h), "
            "pygame.OPENGL | pygame.DOUBLEBUF)."
        ) from exc
    ctx.enable(moderngl.BLEND)
    window = ExternalWindow(ctx, view_size[0], view_size[1])
    _context.set_current(window)
    return window
