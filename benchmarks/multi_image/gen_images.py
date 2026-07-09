"""Gera M imagens 32x32 distintas para o benchmark multi-imagem (determinístico)."""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).parent / "assets"
M = 8
COLORS = [
    (230, 60, 60), (60, 200, 90), (70, 120, 240), (240, 200, 50),
    (200, 80, 220), (60, 210, 210), (240, 140, 40), (180, 180, 180),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for i in range(M):
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((2, 2, 29, 29), fill=(*COLORS[i], 255))
        d.rectangle((13, 13, 18, 18), fill=(255, 255, 255, 255))  # marca central
        img.save(OUT / f"img{i}.png")
    print(f"gerou {M} imagens em {OUT}")


if __name__ == "__main__":
    main()
