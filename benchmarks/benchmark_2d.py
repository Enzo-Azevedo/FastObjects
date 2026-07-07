"""
Benchmark de renderização 2D: FastObjects vs Pygame vs Pyglet vs moderngl
===========================================================================

O QUE ESSE SCRIPT FAZ
----------------------
Para cada biblioteca instalada, cria N retângulos/sprites se movendo dentro
de uma janela e mede quantos frames por segundo (FPS) a biblioteca consegue
sustentar, para vários valores de N (escalabilidade).

Cada medição roda num SUBPROCESSO isolado (mesmo protocolo da arena do
FastObjects): a janela abre e fecha por medição, o pyglet ganha um processo
novo a cada rodada (o app.run() dele não é re-executável) e nenhuma
biblioteca herda estado de GL/janela de outra.

No final, salva:
  - benchmark_results.csv  (tabela com os números)
  - benchmark_results.png  (gráfico objetos x FPS, escala log)

COMO INSTALAR AS DEPENDÊNCIAS
------------------------------
    pip install fastobjects pygame-ce pyglet moderngl glfw numpy matplotlib

(Se alguma não instalar, o script simplesmente pula essa biblioteca e avisa
no terminal — os testes das outras continuam.)

COMO RODAR
----------
    python benchmarks/benchmark_2d.py
    python benchmarks/benchmark_2d.py --sizes 100 1000 5000 10000 50000 --duration 3
    python benchmarks/benchmark_2d.py --libs pygame pyglet moderngl fastobjects

SOBRE A SEÇÃO DO FASTOBJECTS
-----------------------------
Implementada com a API real (v0.2.0): `fo.Window` + `fo.ShapeBatch.rects()`
retornando um grupo vetorizado — a física opera direto nas views NumPy do
batch, e o lote inteiro é desenhado em um draw call instanciado. É o uso
idiomático da biblioteca, do mesmo modo que as seções de pygame/pyglet usam
o caminho idiomático delas (objetos por sprite + draw por objeto).
"""

import argparse
import csv
import importlib.util
import random
import subprocess
import sys
import time

WIDTH, HEIGHT = 800, 600


def lib_available(name):
    return importlib.util.find_spec(name) is not None


# ---------------------------------------------------------------------------
# PYGAME (pygame-ce ou pygame clássico)
# ---------------------------------------------------------------------------
def bench_pygame(n_objects, duration):
    import pygame

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    objs = []
    for _ in range(n_objects):
        x = random.uniform(0, WIDTH)
        y = random.uniform(0, HEIGHT)
        vx = random.uniform(-120, 120)
        vy = random.uniform(-120, 120)
        color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
        objs.append([x, y, vx, vy, color])

    frames = 0
    start = time.perf_counter()
    while time.perf_counter() - start < duration:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                break

        dt = clock.tick(0) / 1000.0
        screen.fill((15, 15, 20))
        for o in objs:
            o[0] += o[2] * dt
            o[1] += o[3] * dt
            if o[0] < 0 or o[0] > WIDTH:
                o[2] *= -1
            if o[1] < 0 or o[1] > HEIGHT:
                o[3] *= -1
            pygame.draw.rect(screen, o[4], (o[0], o[1], 6, 6))
        pygame.display.flip()
        frames += 1

    elapsed = time.perf_counter() - start
    pygame.quit()
    return frames / elapsed


# ---------------------------------------------------------------------------
# PYGLET
# ---------------------------------------------------------------------------
def bench_pyglet(n_objects, duration):
    import pyglet
    from pyglet import shapes

    window = pyglet.window.Window(WIDTH, HEIGHT, visible=True)
    batch = pyglet.graphics.Batch()

    objs = []
    rects = []
    for _ in range(n_objects):
        x = random.uniform(0, WIDTH)
        y = random.uniform(0, HEIGHT)
        vx = random.uniform(-120, 120)
        vy = random.uniform(-120, 120)
        r = shapes.Rectangle(x, y, 6, 6,
                             color=(random.randint(50, 255),
                                    random.randint(50, 255),
                                    random.randint(50, 255)),
                             batch=batch)
        objs.append([vx, vy])
        rects.append(r)

    state = {"frames": 0, "start": time.perf_counter(), "running": True}

    def update(dt):
        for o, r in zip(objs, rects):
            r.x += o[0] * dt
            r.y += o[1] * dt
            if r.x < 0 or r.x > WIDTH:
                o[0] *= -1
            if r.y < 0 or r.y > HEIGHT:
                o[1] *= -1
        state["frames"] += 1
        if time.perf_counter() - state["start"] >= duration:
            state["running"] = False
            window.close()

    @window.event
    def on_draw():
        window.clear()
        batch.draw()

    pyglet.clock.schedule_interval(update, 1 / 240.0)

    def stop_check(dt):
        if not state["running"]:
            pyglet.app.exit()

    pyglet.clock.schedule_interval(stop_check, 0.05)
    pyglet.app.run()

    elapsed = time.perf_counter() - state["start"]
    return state["frames"] / elapsed


# ---------------------------------------------------------------------------
# MODERNGL (instancing manual — o "teto" teórico da técnica, sem biblioteca)
# ---------------------------------------------------------------------------
def bench_moderngl(n_objects, duration):
    import glfw
    import moderngl
    import numpy as np

    if not glfw.init():
        raise RuntimeError("glfw não inicializou")

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)

    window = glfw.create_window(WIDTH, HEIGHT, "moderngl benchmark", None, None)
    if not window:
        glfw.terminate()
        raise RuntimeError("Falha ao criar janela GLFW")
    glfw.make_context_current(window)
    glfw.swap_interval(0)

    ctx = moderngl.create_context()

    prog = ctx.program(
        vertex_shader="""
        #version 330
        in vec2 in_pos;
        in vec2 in_offset;
        in vec3 in_color;
        out vec3 v_color;
        void main() {
            vec2 pos = in_pos + in_offset;
            vec2 clip = (pos / vec2(%d, %d)) * 2.0 - 1.0;
            gl_Position = vec4(clip.x, -clip.y, 0.0, 1.0);
            v_color = in_color;
        }
        """ % (WIDTH, HEIGHT),
        fragment_shader="""
        #version 330
        in vec3 v_color;
        out vec4 f_color;
        void main() { f_color = vec4(v_color, 1.0); }
        """,
    )

    quad = np.array([0, 0, 6, 0, 0, 6, 6, 0, 6, 6, 0, 6], dtype="f4")
    quad_vbo = ctx.buffer(quad.tobytes())

    offsets = np.random.uniform(0, [WIDTH, HEIGHT], (n_objects, 2)).astype("f4")
    velocities = np.random.uniform(-120, 120, (n_objects, 2)).astype("f4")
    colors = np.random.uniform(0.2, 1.0, (n_objects, 3)).astype("f4")

    offset_vbo = ctx.buffer(offsets.tobytes(), dynamic=True)
    color_vbo = ctx.buffer(colors.tobytes())

    vao = ctx.vertex_array(
        prog,
        [
            (quad_vbo, "2f", "in_pos"),
            (offset_vbo, "2f/i", "in_offset"),
            (color_vbo, "3f/i", "in_color"),
        ],
    )

    frames = 0
    start = time.perf_counter()
    last = start
    while time.perf_counter() - start < duration and not glfw.window_should_close(window):
        now = time.perf_counter()
        dt = now - last
        last = now

        offsets += velocities * dt
        bounce_x = (offsets[:, 0] < 0) | (offsets[:, 0] > WIDTH)
        bounce_y = (offsets[:, 1] < 0) | (offsets[:, 1] > HEIGHT)
        velocities[bounce_x, 0] *= -1
        velocities[bounce_y, 1] *= -1
        offset_vbo.write(offsets.astype("f4").tobytes())

        ctx.clear(0.06, 0.06, 0.08)
        vao.render(moderngl.TRIANGLES, instances=n_objects)

        glfw.swap_buffers(window)
        glfw.poll_events()
        frames += 1

    elapsed = time.perf_counter() - start
    glfw.terminate()
    return frames / elapsed


# ---------------------------------------------------------------------------
# FASTOBJECTS (API real v0.2.0: Window + ShapeBatch.rects vetorizado)
# ---------------------------------------------------------------------------
def bench_fastobjects(n_objects, duration):
    import numpy as np

    import fastobjects as fo

    win = fo.Window(WIDTH, HEIGHT, "fastobjects benchmark", vsync=False)
    batch = fo.ShapeBatch(capacity=n_objects)

    xs = np.random.uniform(0, WIDTH, n_objects).astype("f4")
    ys = np.random.uniform(0, HEIGHT, n_objects).astype("f4")
    colors = np.empty((n_objects, 4), dtype="f4")
    colors[:, :3] = np.random.uniform(0.2, 1.0, (n_objects, 3))
    colors[:, 3] = 1.0
    rects = batch.rects(n_objects, x=xs, y=ys, w=6.0, h=6.0, color=colors)
    velocities = np.random.uniform(-120, 120, (n_objects, 2)).astype("f4")

    frames = 0
    start = time.perf_counter()
    last = start
    while time.perf_counter() - start < duration and not win.should_close:
        now = time.perf_counter()
        dt = now - last
        last = now

        win.poll()

        # física vetorizada direto nas views do grupo (zero cópia)
        rects.pos += velocities * dt
        bounce_x = (rects.x < 0) | (rects.x > WIDTH)
        bounce_y = (rects.y < 0) | (rects.y > HEIGHT)
        velocities[bounce_x, 0] *= -1
        velocities[bounce_y, 1] *= -1

        win.clear(0.06, 0.06, 0.08)
        batch.draw()  # 1 upload + 1 draw call instanciado
        win.swap()
        frames += 1

    elapsed = time.perf_counter() - start
    win.close()
    return frames / elapsed


# ---------------------------------------------------------------------------
# ORQUESTRAÇÃO
# ---------------------------------------------------------------------------
BENCHMARKS = {
    "pygame": (bench_pygame, "pygame"),
    "pyglet": (bench_pyglet, "pyglet"),
    "moderngl": (bench_moderngl, "moderngl"),
    "fastobjects": (bench_fastobjects, "fastobjects"),
}


def run_trial_isolated(lib, n, duration):
    """Roda UMA medição num subprocesso próprio (mesmo protocolo da arena).

    Isolamento por medição garante que: a janela sempre fecha ao fim do
    subprocesso (sem janelas-zumbi), o app.run() do pyglet funciona em toda
    medição (ele não é re-executável no mesmo processo), e nenhuma biblioteca
    herda estado de GL/janela de outra.
    """
    proc = subprocess.run(
        [sys.executable, __file__, "--_single", lib, str(n), str(duration)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout).strip()
        raise RuntimeError(err.splitlines()[-1] if err else f"exit {proc.returncode}")
    for line in proc.stdout.splitlines():
        if line.startswith("__RESULT__"):
            return float(line.split()[1])
    raise RuntimeError("subprocesso não reportou resultado")


def run(sizes, duration, libs):
    results = {lib: [] for lib in libs}

    for lib in libs:
        _, module_name = BENCHMARKS[lib]
        if not lib_available(module_name):
            print(f"[AVISO] '{module_name}' não está instalado — pulando '{lib}'.")
            continue

        for n in sizes:
            print(f"Testando {lib} com {n} objetos...", end=" ", flush=True)
            try:
                fps = run_trial_isolated(lib, n, duration)
                print(f"{fps:.1f} FPS")
                results[lib].append((n, fps))
            except Exception as e:
                print(f"FALHOU ({e})")
                results[lib].append((n, None))

    return results


def save_csv(results, path="benchmark_results.csv"):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["biblioteca", "n_objetos", "fps"])
        for lib, points in results.items():
            for n, fps in points:
                writer.writerow([lib, n, fps if fps is not None else ""])
    print(f"\nCSV salvo em {path}")


def save_plot(results, path="benchmark_results.png"):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib não instalado — pulando geração do gráfico.")
        return

    plt.figure(figsize=(9, 6))
    for lib, points in results.items():
        pts = [(n, fps) for n, fps in points if fps is not None]
        if not pts:
            continue
        xs, ys = zip(*pts)
        plt.plot(xs, ys, marker="o", label=lib)

    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("Número de objetos (escala log)")
    plt.ylabel("FPS (escala log)")
    plt.title("Benchmark de renderização 2D")
    plt.legend()
    plt.grid(True, which="both", alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    print(f"Gráfico salvo em {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark de bibliotecas de renderização 2D em Python"
    )
    parser.add_argument("--sizes", nargs="+", type=int,
                        default=[100, 1000, 5000, 10000, 50000, 100000],
                        help="Quantidades de objetos a testar")
    parser.add_argument("--duration", type=float, default=3.0,
                        help="Segundos de medição por teste")
    parser.add_argument("--libs", nargs="+",
                        choices=list(BENCHMARKS.keys()),
                        default=list(BENCHMARKS.keys()),
                        help="Quais bibliotecas testar")
    parser.add_argument("--_single", nargs=3, metavar=("LIB", "N", "DUR"),
                        help=argparse.SUPPRESS)  # modo interno: uma medição
    args = parser.parse_args()

    if args._single:
        lib, n, dur = args._single
        func, _ = BENCHMARKS[lib]
        fps = func(int(n), float(dur))
        print(f"__RESULT__ {fps}")
        return

    print(f"Testando: {args.libs}")
    print(f"Tamanhos: {args.sizes}")
    print(f"Duração por teste: {args.duration}s\n")

    results = run(args.sizes, args.duration, args.libs)
    save_csv(results)
    save_plot(results)


if __name__ == "__main__":
    main()
