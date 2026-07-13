import pytest

from fastobjects.font import Font


def test_default_charset_has_ascii_and_accents():
    f = Font(size=24)
    for ch in "Aig ç ã é 9 !":
        assert ch in f.glyphs
    assert f.line_height > 0
    assert f.atlas_size[0] > 0 and f.atlas_size[1] > 0
    assert len(f.atlas_pixels) == f.atlas_size[0] * f.atlas_size[1] * 4


def test_glyph_has_uv_size_advance_offset():
    f = Font(size=24)
    g = f.glyphs["A"]
    assert g.advance > 0
    assert g.uv is not None and len(g.uv) == 4  # 'A' tem quad
    assert g.size[0] > 0 and g.size[1] > 0
    assert f.glyphs[" "].uv is None  # espaço não tem quad
    assert f.glyphs[" "].advance > 0


def test_custom_charset_respected():
    f = Font(size=20, chars="0123456789")
    assert "5" in f.glyphs
    assert "A" not in f.glyphs


def test_empty_charset_raises():
    with pytest.raises(ValueError, match="chars"):
        Font(size=20, chars="")


def test_layout_positions_and_block():
    f = Font(size=24)
    centers, sizes, uvs, block = f.layout("AB")
    assert centers.shape[0] == sizes.shape[0] == uvs.shape[0] == 2  # dois quads
    assert centers[1, 0] > centers[0, 0]  # 'B' à direita de 'A'
    assert block[0] > 0 and block[1] >= f.line_height


def test_layout_newline_adds_a_line():
    f = Font(size=24)
    _, _, _, one = f.layout("Ab")
    _, _, _, two = f.layout("A\nb")
    assert two[1] > one[1]  # duas linhas => mais alto


def test_layout_skips_unknown_char():
    f = Font(size=24, chars="AB")
    centers, *_ = f.layout("A?B")  # '?' fora do charset é pulado
    assert centers.shape[0] == 2  # só A e B viram quad


def test_measure_matches_layout_block():
    f = Font(size=24)
    assert f.measure("Hello") == pytest.approx(f.layout("Hello")[3])


def test_charset_preset_is_independent():
    f = Font(charset="cyrillic")
    assert "Д" in f.glyphs
    assert "A" not in f.glyphs  # presets não incluem ASCII implicitamente


def test_charset_combination():
    f = Font(charset=("latin", "greek"))
    assert "A" in f.glyphs and "é" in f.glyphs and "Ω" in f.glyphs


def test_charset_invalid_name_raises():
    with pytest.raises(ValueError, match="charset"):
        Font(charset="klingon")


def test_chars_overrides_charset():
    f = Font(chars="AB", charset="cyrillic")
    assert "A" in f.glyphs and "Д" not in f.glyphs
