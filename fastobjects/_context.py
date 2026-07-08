"""Registro interno da janela 'atual' para criação implícita de batches.

Estado global de thread única: todo uso de GL do FastObjects assume a main
thread (contextos OpenGL são thread-afins; não compartilhe janelas/batches
entre threads).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import moderngl

    from fastobjects.external import ExternalWindow
    from fastobjects.window import Window

    CurrentWindow = Window | ExternalWindow

_current: CurrentWindow | None = None


def set_current(win: CurrentWindow | None) -> None:
    """Define a janela atual (chamado por Window.__init__/close e attach)."""
    global _current
    _current = win


def get_current() -> CurrentWindow | None:
    """Retorna a janela atual, ou None se nenhuma foi criada."""
    return _current


def require_current() -> CurrentWindow:
    """Retorna a janela atual ou levanta um erro acionável."""
    if _current is None:
        raise RuntimeError(
            "Nenhuma janela ativa. Crie fo.Window(...), conecte-se ao host com "
            "fo.attach(...), ou passe ctx= e view_size= explicitamente."
        )
    return _current


def resolve(
    ctx: moderngl.Context | None,
    view_size: tuple[int, int] | None,
) -> tuple[moderngl.Context, tuple[int, int]]:
    """Completa ctx/view_size com a janela atual quando não fornecidos."""
    if ctx is not None and view_size is not None:
        return ctx, view_size
    win = require_current()
    return (
        ctx if ctx is not None else win.ctx,
        view_size if view_size is not None else (win.width, win.height),
    )
