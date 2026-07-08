import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "benchmarks" / "arena"))

from run_all import format_table, make_heading, parse_bench_output  # noqa: E402


def test_make_heading_with_and_without_label():
    assert make_heading("2026-07-08", "") == "## Arena 2026-07-08"
    assert make_heading("2026-07-08", "pós-X") == "## Arena 2026-07-08 (pós-X)"


def test_parse_bench_output_takes_last_json_line():
    stdout = "lixo do driver\n{\"framework\": \"x\", \"sprites_at_60fps\": 100, \"trials\": []}\n"
    result = parse_bench_output(stdout)
    assert result["framework"] == "x"
    assert result["sprites_at_60fps"] == 100


def test_format_table_sorted_desc():
    results = [
        {"framework": "a", "sprites_at_60fps": 100, "trials": [{"n": 100, "avg_ms": 10.0, "p99_ms": 11.0}]},
        {"framework": "b", "sprites_at_60fps": 900, "trials": [{"n": 900, "avg_ms": 15.0, "p99_ms": 16.0}]},
    ]
    table = format_table(results)
    lines = table.splitlines()
    assert "| Framework |" in lines[0]
    assert lines[2].startswith("| b |")  # maior primeiro
    assert "900" in lines[2]
