"""Runner do benchmark multi-imagem (um subprocesso por lib) + tabela markdown."""

from __future__ import annotations

import argparse
import datetime
import json
import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
RESULTS_MD = HERE.parent / "RESULTS.md"
BENCHES = ["bench_fastobjects.py", "bench_arcade.py", "bench_pyglet.py"]


def parse_bench_output(stdout: str) -> dict:
    lines = [ln for ln in stdout.strip().splitlines() if ln.strip()]
    return json.loads(lines[-1])


def format_table(results: list[dict]) -> str:
    rows = sorted(results, key=lambda r: r["sprites_at_60fps"], reverse=True)
    out = [
        "| Framework | Sprites @ 60fps | avg ms | p99 ms |",
        "|---|---|---|---|",
    ]
    for r in rows:
        best = next(
            (t for t in reversed(r["trials"]) if t["n"] == r["sprites_at_60fps"]),
            {"avg_ms": "-", "p99_ms": "-"},
        )
        out.append(
            f"| {r['framework']} | {r['sprites_at_60fps']:,} | "
            f"{best['avg_ms']} | {best['p99_ms']} |"
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
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    # garante os assets
    subprocess.run([sys.executable, str(HERE / "gen_images.py")], check=True)

    results = []
    for bench in BENCHES:
        print(f"== rodando {bench} ==", flush=True)
        try:
            proc = subprocess.run(
                [sys.executable, str(HERE / bench)],
                capture_output=True, text=True, cwd=str(HERE), timeout=600,
            )
        except subprocess.TimeoutExpired:
            print(f"TIMEOUT: {bench}", file=sys.stderr)
            continue
        if proc.returncode != 0:
            print(f"FALHOU ({proc.returncode}):\n{proc.stderr}", file=sys.stderr)
            continue
        results.append(parse_bench_output(proc.stdout))

    table = format_table(results)
    print(table)

    if args.save:
        stamp = datetime.date.today().isoformat()
        header = (
            f"\n## Multi-imagem {stamp} (N sprites de 8 imagens diferentes)\n\n"
            f"- Hardware: {platform.processor()} | GPU: {gpu_name()}\n"
            f"- Python {platform.python_version()} | {platform.system()} "
            f"{platform.release()}\n\n"
        )
        with open(RESULTS_MD, "a", encoding="utf-8") as f:
            f.write(header + table + "\n")
        print(f"\nsalvo em {RESULTS_MD}")


if __name__ == "__main__":
    main()
