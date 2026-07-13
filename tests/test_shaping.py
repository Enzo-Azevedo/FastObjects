"""Backend de shaping: HarfBuzz + FreeType (extra fastobjects[shaping])."""

from pathlib import Path

import numpy as np
import pytest

from fastobjects import shaping
from fastobjects.font import Font

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


@needs
def test_font_goes_shaped_automatically():
    f = Font(str(_ARIAL), 24)
    assert f.shaped is True
    assert f.glyphs["A"].uv is not None  # visão pública por caractere preservada


def test_font_without_source_never_shaped():
    assert Font(size=16).shaped is False


@needs
def test_fallback_without_extra(monkeypatch):
    monkeypatch.setattr(shaping, "available", lambda: False)
    f = Font(str(_ARIAL), 24)
    assert f.shaped is False  # caminho 0.6.1 intacto
    assert f.glyphs["A"].uv is not None


@needs
def test_shaped_layout_rtl_order():
    # chars= define a visão pública f.glyphs; o layout shaped aceita qualquer char
    f = Font(str(_ARIAL), 32, chars="אב")
    centers, _, uvs, _ = f.layout("אב")
    alef_uv = f.glyphs["א"].uv
    idx_alef = next(i for i in range(uvs.shape[0]) if bool((uvs[i] == alef_uv).all()))
    other = 1 - idx_alef
    assert centers[idx_alef, 0] > centers[other, 0]  # 1º char lógico à direita


@needs
def test_shaped_missing_font_raises_actionable():
    with pytest.raises(ValueError, match="fonte"):
        Font("nao-existe-esta-fonte.ttf", 24)


@needs
def test_raqm_reference_width_agrees():
    from PIL import Image, ImageDraw, ImageFont, features

    if not features.check("raqm"):
        pytest.skip("Pillow sem Raqm")
    pil_font = ImageFont.truetype(str(_ARIAL), 32)
    img = Image.new("L", (400, 80), 0)
    ImageDraw.Draw(img).text((10, 10), "سلام", font=pil_font, fill=255)
    arr_w = (np.array(img) > 40).any(axis=0).sum()
    fo_w = Font(str(_ARIAL), 32).measure("سلام")[0]
    assert abs(fo_w - arr_w) / arr_w < 0.3  # mesma ordem/conexão => largura próxima
