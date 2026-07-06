"""Executa todos os benches da arena (um subprocesso cada) e gera a tabela."""

from __future__ import annotations

import argparse
import datetime
import json
import platform
import subprocess
import sys
from pathlib import Path

ARENA = Path(__file__).parent
RESULTS_MD = ARENA.parent / "RESULTS.md"

BENCHES = [
    "bench_pygame.py",
    "bench_arcade.py",
    "bench_pyglet.py",
    "bench_raylib.py",
    "bench_fastobjects.py",
]


def parse_bench_output(stdout: str) -> dict:
    """A última linha não-vazia do stdout do bench é o JSON do resultado."""
    lines = [ln for ln in stdout.strip().splitlines() if ln.strip()]
    return json.loads(lines[-1])


def format_table(results: list[dict]) -> str:
    rows = sorted(results, key=lambda r: r["sprites_at_60fps"], reverse=True)
    out = [
        "| Framework | Sprites @ 60fps | avg ms (último trial ok) | p99 ms |",
        "|---|---|---|---|",
    ]
    for r in rows:
        best = next(
            (t for t in reversed(r["trials"]) if t["n"] == r["sprites_at_60fps"]),
            {"avg_ms": "-", "p99_ms": "-"},
        )
        out.append(
            f"| {r['framework']} | {r['sprites_at_60fps']:,} | {best['avg_ms']} | {best['p99_ms']} |"
        )
    return "\n".join(out)


def gpu_name() -> str:
    try:
        import moderngl

        ctx = moderngl.create_standalone_context()
        name = ctx.info["GL_RENDERER"]
        ctx.release()
        return name
    except Exception:
        return "desconhecida"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true", help="anexa em benchmarks/RESULTS.md")
    args = parser.parse_args()

    results = []
    for bench in BENCHES:
        print(f"== rodando {bench} ==", flush=True)
        proc = subprocess.run(
            [sys.executable, str(ARENA / bench)],
            capture_output=True,
            text=True,
            cwd=str(ARENA),
        )
        if proc.returncode != 0:
            print(f"FALHOU ({proc.returncode}):\n{proc.stderr}", file=sys.stderr)
            continue
        results.append(parse_bench_output(proc.stdout))

    table = format_table(results)
    print(table)

    if args.save:
        stamp = datetime.date.today().isoformat()
        header = (
            f"\n## Arena {stamp}\n\n"
            f"- Hardware: {platform.processor()} | GPU: {gpu_name()}\n"
            f"- Python {platform.python_version()} | {platform.system()} {platform.release()}\n\n"
        )
        with open(RESULTS_MD, "a", encoding="utf-8") as f:
            f.write(header + table + "\n")
        print(f"\nsalvo em {RESULTS_MD}")


if __name__ == "__main__":
    main()
