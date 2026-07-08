import pytest

from fastobjects import _context


@pytest.fixture(autouse=True)
def restore_current_window():
    """Isola o estado da janela atual entre testes (ordem-independência)."""
    previous = _context.get_current()
    yield
    _context.set_current(previous)
