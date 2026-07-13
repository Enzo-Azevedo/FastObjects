# Texto

O FastObjects desenha texto como sprites de um **atlas de glifos** — cada
caractere é um quad texturizado, e um `TextBatch` inteiro sai em uma chamada. O
texto é construído sobre o mesmo atlas/renderer dos sprites, então é rápido e
batched.

## Uma fonte e um batch de texto

```python
import fastobjects as fo

win = fo.Window(800, 600)
font = fo.Font(size=28)              # fonte embutida escalável
labels = fo.TextBatch(font, capacity=500)

labels.write("Olá, FastObjects!", x=20, y=20)
labels.write("Acentos: ação!", x=20, y=60, color=(0.6, 0.9, 1.0, 1.0))
```

- `Font(size)` rasteriza um conjunto de caracteres num atlas de glifos, uma vez.
  O conjunto padrão cobre ASCII imprimível **e Latin-1** (acentos como á, ç, ã,
  é funcionam por padrão). Passe `chars="..."` para um conjunto custom.
- `TextBatch(font, capacity)` — `capacity` é o máximo de glifos somando todos os
  `write` vivos.
- `write(text, x, y, color=(1,1,1,1), anchor="topleft")` retorna um
  `SpriteGroup` sobre os quads dos glifos, então você move ou recolore a string
  inteira: `label.pos += (0, 5)`, `label.color = (1, 0, 0, 1)`.

Quebras de linha (`\n`) começam uma nova linha; `anchor="center"` centraliza o
bloco de texto em `(x, y)`.

## Texto dinâmico (score, FPS)

Para texto que muda todo frame, `clear()` e `write()` de novo — sem surface por
string, sem realocação:

```python
hud = fo.TextBatch(font, capacity=200)

@win.frame
def update(dt):
    hud.clear()
    hud.write(f"Score: {score}", x=20, y=20)
    win.clear(0.1, 0.1, 0.1)
    win.draw(hud)
```

## Medindo

`font.measure(text)` retorna a `(largura, altura)` do bloco de uma string sem
desenhar — útil para posicionar ou centralizar por conta própria:

```python
w, h = font.measure("Game Over")
label.write("Game Over", x=(800 - w) / 2, y=(600 - h) / 2)
```

## Fontes customizadas

`Font` recebe a fonte primeiro, estilo pygame — um caminho `.ttf`/`.otf` ou o
nome de uma fonte instalada no sistema. `None` (o padrão) usa a fonte embutida
do Pillow.

```python
hud = fo.Font("assets/PressStart2P.ttf", 16)
sistema = fo.Font("arial.ttf", 24)         # procurada nos diretórios do sistema
```

## Conjuntos de caracteres

O atlas rasteriza um conjunto fixo de caracteres, escolhido na construção:

```python
fo.Font("arial.ttf", 24)                            # "latin" (padrão): ASCII + Latin-1
fo.Font("arial.ttf", 24, charset="cyrillic")        # só Ѐ-џ — sem ASCII
fo.Font("arial.ttf", 24, charset=("latin", "greek", "cyrillic"))  # texto misto
fo.Font("arial.ttf", 24, chars="0123456789/:")      # controle total (vence charset)
```

Presets: `"ascii"`, `"latin"`, `"latin-ext"`, `"greek"`, `"cyrillic"`.
Presets são independentes — combine-os numa tupla para texto misto. Um
caractere que o *arquivo da fonte* não cobre renderiza o tofu da própria
fonte; um caractere fora do *charset do atlas* é pulado (avança como espaço).

## Texto complexo: RTL, kerning, ligaturas

Instale o extra opcional de shaping e o `Font` se atualiza sozinho — árabe e
hebraico saem conectados e na ordem certa, e pares de kerning se aplicam:

```bash
pip install fastobjects[shaping]
```

```python
font = fo.Font("arial.ttf", 24)
font.shaped        # True com o extra instalado (False = layout simples)
labels.write("سلام عليكم", x=20, y=20)   # formas contextuais corretas + RTL
```

Com o shaping ativo o atlas contém **todos os glifos da fonte** (ligaturas e
formas contextuais não têm caractere próprio), então `charset`/`chars` só
escolhem quais caracteres aparecem no dict público `font.glyphs`. Linha que
mistura LTR e RTL usa a direção dominante detectada pelo HarfBuzz — bidi
completo é um limite conhecido. Sem o extra, o `Font` cai no layout simples
por caractere (suficiente para latim/grego/cirílico).

## Um exemplo completo

Veja [`examples/text_hud.py`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/examples/text_hud.py)
(labels estáticos + um contador de FPS ao vivo).
