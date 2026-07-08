# Começando

## Instalação

```bash
pip install fastobjects
```

Requisitos: Python ≥ 3.11 e GPU/driver com OpenGL 3.3 core (qualquer GPU de
desktop da última década). As dependências do core são só `numpy`,
`moderngl`, `glfw` e `pillow`.

Para desenvolvimento (testes, linter, benchmarks dos concorrentes):

```bash
pip install "fastobjects[dev,bench]"
```

## Seu primeiro programa

Salve qualquer imagem como `player.png` ao lado do script e rode:

```python
import numpy as np

import fastobjects as fo

win = fo.Window(800, 600, title="Meu primeiro programa FastObjects")

# Um batch = uma textura = um draw call.
sprites = fo.SpriteBatch("player.png", capacity=2000)

# Spawn vetorizado: 1.000 sprites em uma chamada, posições de arrays.
rng = np.random.default_rng()
group = sprites.spawn(
    1000,
    x=rng.uniform(0, 800, 1000),
    y=rng.uniform(0, 600, 1000),
)
velocity = rng.uniform(-100, 100, (1000, 2)).astype("f4")

@win.frame
def update(dt: float) -> None:
    # Física nas views NumPy do grupo — sem loop por sprite.
    group.pos += velocity * dt

    win.clear(0.1, 0.1, 0.1)
    win.draw(sprites)

    if win.keys[fo.KEY_ESCAPE]:
        win.request_close()

win.run()
```

O que aconteceu:

1. `fo.Window(...)` abriu uma janela nativa com contexto OpenGL 3.3 core e
   registrou-se como a *janela atual* — batches criados depois dela se
   conectam automaticamente.
2. `sprites.spawn(1000, x=..., y=...)` criou 1.000 sprites **em uma chamada
   vetorizada** e retornou um `SpriteGroup` — um handle leve cujas
   propriedades são views NumPy do batch.
3. `group.pos += velocity * dt` moveu os 1.000 sprites com uma operação de
   array. Esse é o idioma do FastObjects: atualize *grupos*, nunca sprites
   individuais num loop Python.
4. `win.run()` comandou o loop de frames, chamando sua função `@win.frame`
   com o `dt` real a cada frame.

## Próximos passos

- As coordenadas são **pixels com y para baixo** (origem no canto superior
  esquerdo), como na maioria das ferramentas 2D.
- Leia [Sprites & Grupos](guide/sprites.md) para despawn, cores, rotação e
  o modelo de custos de upload.
- Já tem um projeto pygame? Veja
  [Usando dentro do pygame](guide/interop.md).
