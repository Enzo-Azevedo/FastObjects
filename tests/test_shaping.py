"""Backend de shaping: HarfBuzz + FreeType (extra fastobjects[shaping])."""

from pathlib import Path

import pytest

from fastobjects import shaping

_ARIAL = Path("C:/Windows/Fonts/arial.ttf")
needs = pytest.mark.skipif(
    not (shaping.available() and _ARIAL.exists()),
    reason="extra shaping ou arial.ttf ausentes",
)


def test_available_reports_extra():
    assert shaping.available() is True  # extra instalado no ambiente de dev


@needs
def test_backend_rasterizes_whole_font():
    b = shaping.ShapedBackend(str(_ARIAL), 24)
    assert len(b.glyphs) > 1000  # arial tem milhares de glifos
    assert b.line_height > 0
    assert len(b.atlas_pixels) == b.atlas_size[0] * b.atlas_size[1] * 4
    gid_a = b.char_index("A")
    assert gid_a != 0 and b.glyphs[gid_a].uv is not None


@needs
def test_shape_line_applies_kerning():
    b = shaping.ShapedBackend(str(_ARIAL), 32)
    solo = sum(adv for _, adv, _, _ in b.shape_line("A")) + sum(
        adv for _, adv, _, _ in b.shape_line("V")
    )
    together = sum(adv for _, adv, _, _ in b.shape_line("AV"))
    assert together < solo - 0.5  # kern do par AV


@needs
def test_shape_line_lam_alef_ligature():
    b = shaping.ShapedBackend(str(_ARIAL), 32)
    assert len(b.shape_line("لا")) == 1  # lam+alef => 1 glifo (ligatura)


@needs
def test_shape_line_contextual_forms_differ():
    b = shaping.ShapedBackend(str(_ARIAL), 32)
    gids = [gid for gid, _, _, _ in b.shape_line("بب")]
    assert len(gids) == 2 and gids[0] != gids[1]  # forma final != inicial
