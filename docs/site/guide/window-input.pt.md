# Janela & Input

## A janela

```python
import fastobjects as fo

win = fo.Window(1280, 720, title="meu jogo", vsync=False, visible=True)
```

`Window` abre uma janela GLFW nativa com contexto OpenGL 3.3 core. Criá-la a
registra como *janela atual*: batches criados depois se conectam a ela
automaticamente. `vsync` vem desligado por padrão (os benchmarks exigem);
passe `vsync=True` para limitar à taxa de atualização do monitor.
`visible=False` dá uma janela estilo offscreen, usada pela suíte de testes.

As coordenadas em todo lugar são **pixels, y para baixo**, origem no canto
superior esquerdo.

## O loop de frames

```python
@win.frame
def update(dt: float) -> None:
    ...                       # sua lógica por frame
    win.clear(0.1, 0.1, 0.1)  # cor de fundo
    win.draw(batch_a, batch_b)  # um draw call por batch, na ordem

win.run()
```

- `@win.frame` registra a função de update (registrar de novo substitui).
- `win.run()` roda até a janela fechar: poll de eventos → mede o `dt` real
  (segundos) → chama sua função → troca os buffers.
- `win.request_close()` encerra o loop de dentro do update — o caminho de
  saída usual (`if win.keys[fo.KEY_ESCAPE]: win.request_close()`).
- Prefere controle manual? `poll()`, `clear()`, `swap()` e `should_close`
  são públicos — a arena de benchmarks usa exatamente esse loop.
- Usar a janela após `close()` levanta um `RuntimeError` claro (em vez de
  travar o interpretador).

## Input por polling

O input é estado consultado dentro da função de frame — sem callbacks para
conectar:

```python
@win.frame
def update(dt: float) -> None:
    if win.keys[fo.KEY_RIGHT]:          # pressionada agora?
        player.x += 200 * dt
    if win.mouse.left:                   # botão esquerdo pressionado?
        cursor.x = win.mouse.x           # posição em pixels, y para baixo
        cursor.y = win.mouse.y
```

- `win.keys[keycode]` — `True` enquanto a tecla está pressionada. Os
  keycodes são as constantes do glfw re-exportadas como `fo.KEY_*` (ex.:
  `fo.KEY_SPACE`, `fo.KEY_W`, `fo.KEY_ESCAPE`).
- `win.mouse` — `.x`, `.y` (pixels), `.left`, `.right`, `.middle` (bools).

## Um exemplo completo

Este é o [`examples/shapes_input.py`](https://github.com/Enzo-Azevedo/FastObjects/blob/main/examples/shapes_input.py)
em miniatura:

```python
import fastobjects as fo

win = fo.Window(800, 600, title="janela & input")
shapes = fo.ShapeBatch(capacity=8)
cursor = shapes.circles(1, x=400.0, y=300.0, radius=16.0,
                        color=(1.0, 0.7, 0.1, 0.9))
player = shapes.rects(1, x=400.0, y=300.0, w=48.0, h=48.0,
                      color=(0.2, 0.9, 0.4, 1.0))

@win.frame
def update(dt: float) -> None:
    cursor.x = win.mouse.x
    cursor.y = win.mouse.y
    if win.keys[fo.KEY_RIGHT]:
        player.x += 300 * dt
    if win.keys[fo.KEY_LEFT]:
        player.x -= 300 * dt

    win.clear(0.08, 0.08, 0.10)
    win.draw(shapes)
    if win.keys[fo.KEY_ESCAPE]:
        win.request_close()

win.run()
```
