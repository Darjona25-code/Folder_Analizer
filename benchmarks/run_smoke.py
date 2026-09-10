"""Smoke benchmark runner for Folder Analyzer (Phase 1 baseline).

Measures core scanner metrics on the deterministic fixture so every later phase
can be compared against a documented baseline.

Metrics recorded:
- total scan time (seconds)
- files/second
- analysis/composition time (Phase 1: 0.0; filled by later phases)
- peak memory (MiB, max RSS delta during scan + tracemalloc Python peak)
- retained records (Phase 1: 0; Phase 3: bounded retention store result)
- cancellation responsiveness (Phase 1: n/a; filled by Phase 8)

Regression gate: a >20% regression versus the baseline in docs/ARCHITECTURE.md
is a phase-closing gate (see docs/ROADMAP.md §15/§22).

Usage:
    python benchmarks/gen_fixture.py --out benchmarks/generated/fixture
    python benchmarks/run_smoke.py --path benchmarks/generated/fixture --json benchmarks/results/smoke.json
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import tracemalloc

from folder_analyzer.scanner import Scanner


def _rss_mb() -> float:
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0


def run_smoke(path: str, max_workers: int = 16) -> dict:
    scanner = Scanner(max_workers=max_workers)

    rss_before = _rss_mb()

    def _watch():
        peak = rss_before
        while not done["flag"]:
            current = _rss_mb()
            if current > peak:
                peak = current
            time.sleep(0.05)
        peak_rss["value"] = peak

    done = {"flag": False}
    peak_rss = {"value": rss_before}
    watcher = threading.Thread(target=_watch, daemon=True)

    tracemalloc.start()
    start = time.perf_counter()
    watcher.start()
    root = scanner.scan(path)
    elapsed = time.perf_counter() - start
    done["flag"] = True
    watcher.join(timeout=1.0)
    _, mem_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    files = scanner.scanned_files
    folders = scanner.scanned_folders
    files_per_second = round(files / elapsed, 1) if elapsed > 0 else 0.0

    return {
        "path": os.path.abspath(path),
        "environment": {
            "os": os.name,
            "python": os.sys.version.split()[0],
            "platform": __import__("platform").platform(),
        },
        "total_scan_time_s": round(elapsed, 3),
        "files_per_second": files_per_second,
        "analysis_time_s": 0.0,
        "composition_time_s": 0.0,
        "file_count": files,
        "folder_count": folders,
        "total_size_bytes": root.total_size,
        "peak_memory_mib": round(max(peak_rss["value"] - rss_before, 0.0), 2),
        "python_alloc_peak_mib": round(mem_peak / (1024 * 1024), 2),
        "retained_records": scanner.records_retained,
        "cancellation_responsiveness_ms": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="benchmarks/generated/fixture")
    parser.add_argument("--json", default=None, help="Write results JSON to this path")
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    result = run_smoke(args.path, max_workers=args.workers)

    header = (
        f"{'metric':<28}{'value':>14}\n"
        f"{'-' * 42}"
    )
    rows = [
        ("total scan time (s)", result["total_scan_time_s"]),
        ("files/sec", result["files_per_second"]),
        ("file count", result["file_count"]),
        ("folder count", result["folder_count"]),
        ("analysis time (s)", result["analysis_time_s"]),
        ("composition time (s)", result["composition_time_s"]),
        ("peak memory (MiB)", result["peak_memory_mib"]),
        ("python alloc peak (MiB)", result["python_alloc_peak_mib"]),
        ("retained records", result["retained_records"]),
        ("cancellation (ms)", result["cancellation_responsiveness_ms"]),
    ]
    print(f"SMOKE BENCHMARK - {result['path']}")
    print(header)
    for name, value in rows:
        if value is None:
            print(f"{name:<28}{'n/a':>14}")
        else:
            print(f"{name:<28}{value:>14}")
    print(f"\nOS: {result['environment']['platform']}")

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"\nJSON result: {args.json}")


if __name__ == "__main__":
    main()