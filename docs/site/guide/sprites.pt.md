# Sprites & Grupos

## O batch

Um `SpriteBatch` é um pool de capacidade fixa de sprites que compartilham
uma textura e são desenhados com **um draw call instanciado**:

```python
import fastobjects as fo

win = fo.Window(800, 600)
batch = fo.SpriteBatch("player.png", capacity=10_000)
```

- `capacity` é o máximo de sprites vivos; exceder levanta `CapacityError`
  dizendo a capacity exata de que você precisa.
- A textura é qualquer imagem que o Pillow abra. Um batch = uma textura —
  se precisar de várias imagens hoje, crie um batch por imagem (texture
  atlas está no roadmap).
- `ctx`/`view_size` vêm da janela atual; passe-os explicitamente só para
  render offscreen ou testes.

## Spawn — sempre vetorizado

`spawn(n, ...)` cria `n` sprites em uma chamada. Todo parâmetro aceita um
escalar (aplicado a todos) ou um array de tamanho `n`:

```python
import numpy as np

rng = np.random.default_rng()
bunnies = batch.spawn(
    5000,
    x=rng.uniform(0, 800, 5000),
    y=100.0,                      # escalar: igual para todos
    rot=0.0,
    color=(1.0, 1.0, 1.0, 1.0),  # ou um array (n, 4)
)
```

O retorno é um `SpriteGroup` — um objeto Python leve para o *grupo inteiro*,
nunca um por sprite.

## Grupos: views, não cópias

As propriedades de um grupo são **views** NumPy do armazenamento do batch.
Escrever nelas é escrever nos sprites:

```python
bunnies.pos += velocity * dt          # move todos, uma operação de array
bunnies.color = (1.0, 0.2, 0.2, 1.0)  # tinge todos de vermelho
bunnies.rot += 0.5 * dt               # gira todos
bunnies[100:200].y = 0.0              # sub-slice: linhas 100..199
```

Propriedades disponíveis: `x`, `y`, `w`, `h`, `rot` (arrays 1D), `pos`
(n, 2), `size` (n, 2), `color` (n, 4). `len(grupo)` dá a contagem;
`grupo[a:b]` retorna um sub-grupo sobre o mesmo armazenamento.

!!! note "Como funcionam os uploads — você paga pela mudança, não pela existência"
    Todo sprite sempre tem todas as propriedades, na CPU e na GPU. O que é
    otimizado é o **upload por frame**: posições sobem todo frame (mudam em
    qualquer app real); tamanho, rotação e cor sobem apenas nos frames em
    que você as toca. O rastreamento é automático e conservador — *acessar*
    a propriedade marca a coluna para upload, então uma mudança nunca deixa
    de aparecer na tela silenciosamente.

    Uma regra: **não guarde uma view de propriedade entre frames** para
    escrever nela depois. Reacesse a cada frame
    (`grupo.color[...] = ...`) — o acesso é O(1) e é ele que mantém o
    rastreamento correto.

## Despawn

`despawn(grupo)` remove os sprites do grupo, compacta o batch com uma cópia
vetorizada por coluna e devolve a capacity:

```python
a = batch.spawn(100)
b = batch.spawn(50)
batch.despawn(a)
len(b)          # ainda 50 — o handle de b foi realocado automaticamente
batch.spawn(80)  # a capacity de a está disponível de novo
```

Handles sobreviventes continuam funcionando. O grupo removido — e qualquer
sub-grupo que o sobreponha — fica inválido: tocá-lo levanta `RuntimeError`
mandando fazer spawn de novo. `batch.clear()` remove tudo e invalida todos
os handles.

## Várias imagens (atlas)

Um batch pode guardar **mais de uma imagem** e ainda desenhar tudo em uma
chamada. Passe uma lista (selecionada por índice) ou um dict (selecionado por
nome); o FastObjects empacota tudo num único texture atlas na criação:

```python
batch = fo.SpriteBatch(["heroi.png", "moeda.png", "inimigo.png"], capacity=10_000)

heroi  = batch.spawn(1, x=400, y=300, image=0)
moedas = batch.spawn(50, x=xs, y=ys, image=1)        # todas moedas
misto  = batch.spawn(100, x=xs, y=ys, image=np.arange(100) % 3)  # vetorizado

nomeado = fo.SpriteBatch({"heroi": "heroi.png", "moeda": "moeda.png"}, capacity=100)
nomeado.spawn(1, image="heroi")
```

`spawn(..., image=i)` aceita escalar ou array de tamanho `n` (índices/nomes).
Quando `w`/`h` ficam em `None`, cada sprite usa o tamanho em pixels **da sua
própria imagem**.

**Animação de spritesheet** — reatribua `group.image` para re-texturar um grupo
no lugar (ainda um draw call; `image` é uma coluna fria que só re-sobe quando
você muda):

```python
frames = fo.SpriteBatch([f"walk{i}.png" for i in range(8)], capacity=100)
player = frames.spawn(1, x=400, y=300)

@win.frame
def update(dt):
    player.image = (tick // 6) % 8   # avança a animação
    ...
```

O atlas é **estático**: montado uma vez a partir das imagens passadas. Todas
precisam caber numa textura (`GL_MAX_TEXTURE_SIZE`, tipicamente ≥ 8192); se não
couberem, você recebe um `AtlasOverflowError` acionável. Add/remove em runtime
ainda não é suportado. Veja
[`examples/atlas_animation.py`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/examples/atlas_animation.py).

## Um exemplo completo

```python
import numpy as np

import fastobjects as fo

win = fo.Window(800, 600, title="guia de sprites")
batch = fo.SpriteBatch("player.png", capacity=5000)

rng = np.random.default_rng(7)
n = 2000
group = batch.spawn(n, x=rng.uniform(0, 800, n), y=rng.uniform(0, 300, n))
vel = rng.uniform(-120, 120, (n, 2)).astype("f4")

@win.frame
def update(dt: float) -> None:
    vel[:, 1] += 980.0 * dt          # gravidade
    group.pos += vel * dt
    floor = group.y > 600
    vel[floor, 1] *= -0.85           # quique
    group.y = np.minimum(group.y, 600)

    win.clear(0.08, 0.08, 0.10)
    win.draw(batch)
    if win.keys[fo.KEY_ESCAPE]:
        win.request_close()

win.run()
```
