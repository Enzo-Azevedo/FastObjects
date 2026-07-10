"""FastObjects: the fastest 2D object rendering library for Python."""

import glfw as _glfw

from fastobjects.batch import SpriteBatch
from fastobjects.errors import CapacityError
from fastobjects.external import ExternalWindow, attach
from fastobjects.font import Font
from fastobjects.group import SpriteGroup
from fastobjects.layer import SurfaceLayer
from fastobjects.shapes import ShapeBatch
from fastobjects.text import TextBatch
from fastobjects.window import Window

__version__ = "0.5.0"
__all__ = [
    "CapacityError",
    "ExternalWindow",
    "Font",
    "ShapeBatch",
    "SpriteBatch",
    "SpriteGroup",
    "SurfaceLayer",
    "TextBatch",
    "Window",
    "__version__",
    "attach",
]

# Constantes de input (fo.KEY_SPACE, fo.MOUSE_BUTTON_LEFT, ...): re-export
# direto do glfw — zero manutenção própria.
for _name in dir(_glfw):
    if _name.startswith(("KEY_", "MOUSE_BUTTON_")):
        globals()[_name] = getattr(_glfw, _name)
        __all__.append(_name)
del _glfw, _name

