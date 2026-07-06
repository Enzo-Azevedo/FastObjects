"""FastObjects: the fastest 2D object rendering library for Python."""

from fastobjects.batch import SpriteBatch
from fastobjects.errors import CapacityError
from fastobjects.window import Window

__version__ = "0.1.0"
__all__ = ["CapacityError", "SpriteBatch", "Window", "__version__"]
