"""Smoke benchmark runner for Folder Analyzer (Phase 1 baseline).

Measures core scanner metrics on the deterministic fixture so every later phase
can be compared against a documented baseline.

Corrected methodology (Phase 5, benchmark tooling only):

- **Affinity pinning.** On hybrid P/E/LP-E machines (Intel Core Ultra, Apple
  M-series, etc.) the OS freely places the scan across cores with
  multi-x throughput differences, so phase-over-phase time numbers are
  incomparable otherwise. This harness probes every logical CPU with a fixed
  CPU-bound loop, picks the ``--pinned-cores`` fastest (default 2 = the
  P-cores), and pins the whole process to that set for the entire run
  (``SetProcessAffinityMask`` / ``os.sched_setaffinity``). After the run the
  original affinity is restored in the parent process; subprocess-invoked runs
  exit anyway.
- **Gate metrics.** The deterministic, code-attributable regression metrics
  are ``python_alloc_peak_mib`` (tracemalloc alloc peak) and
  ``retained_records``. Peak RSS remains reported as an *envelope* metric only
  (informational): its +/-30% working-set sampling noise on this hardware
  exceeds the 20% tolerance, so it is NOT a hard gate (see Phase 4 evidence).
- When pinned, the scan worker count is capped at ``--pinned-cores`` so the
  pool does not oversubscribe the pinned set.

Metrics recorded:
- total scan time (seconds)
- files/second
- analysis/composition time (filled by later phases)
- gate: python alloc peak (MiB) + retained records
- peak memory envelope (MiB, max RSS delta during scan)
- cancellation responsiveness (Phase 1: n/a; filled by Phase 8)

Regression gate: a >20% regression versus the baseline in docs/ARCHITECTURE.md
is a phase-closing gate (see docs/ROADMAP.md §15/§22), evaluated on the gate
metrics above, not on RSS.

Usage:
    python benchmarks/gen_fixture.py --out benchmarks/generated/fixture
    python benchmarks/run_smoke.py --path benchmarks/generated/fixture --json benchmarks/results/smoke.json
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import threading
import time
import tracemalloc
from typing import List, Tuple

from folder_analyzer.scanner import Scanner


def _rss_mb() -> float:
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0


_POSIX_AFFINITY = hasattr(os, "sched_setaffinity")


def _read_affinity() -> int:
    if _POSIX_AFFINITY:
        return int(sum(1 << c for c in os.sched_getaffinity(0)))
    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    k32.GetProcessAffinityMask.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    k32.GetProcessAffinityMask.restype = ctypes.c_bool
    proc = k32.GetCurrentProcess()
    pmask = ctypes.c_size_t()
    smask = ctypes.c_size_t()
    try:
        ok = k32.GetProcessAffinityMask(proc, ctypes.byref(pmask), ctypes.byref(smask))
    except (AttributeError, OSError):
        return (2**os.cpu_count()) - 1
    return pmask.value if ok else (2**os.cpu_count()) - 1


def _set_affinity(mask: int) -> bool:
    if _POSIX_AFFINITY:
        os.sched_setaffinity(0, {c for c in range(64) if mask & (1 << c)})
        return True
    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    k32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    k32.SetProcessAffinityMask.restype = ctypes.c_bool
    try:
        return bool(k32.SetProcessAffinityMask(k32.GetCurrentProcess(), mask))
    except (AttributeError, OSError):
        return False


def _cpu_burn(iterations: int) -> None:
    """Run a fixed CPU-bound workload so faster cores finish in less time."""
    acc = 0
    for _ in range(iterations):
        acc = (acc * 48271 + 1) % 2147483647
    return acc if acc else None


def _probe_fast_cores(count: int = 2, iterations: int = 6_000_000) -> Tuple[int, ...]:
    """Probe every logical CPU and return the ``count`` fastest (P-cores).

    Uses GetProcessAffinityMask / os.sched_getaffinity to enumerate the
    available logical processors, times a fixed CPU-bound workload on each one,
    and returns their indices sorted fastest-first.
    """
    available = [c for c in range(64) if _read_affinity() & (1 << c)]
    timeline: List[Tuple[float, int]] = []
    original = _read_affinity()
    try:
        for cpu in available:
            if _POSIX_AFFINITY:
                os.sched_setaffinity(0, {cpu})
            else:
                _set_affinity(1 << cpu)
            start = time.perf_counter()
            _cpu_burn(iterations)
            elapsed = time.perf_counter() - start
            timeline.append((elapsed, cpu))
    finally:
        _set_affinity(original)
    timeline.sort()
    return tuple(cpu for _, cpu in timeline[:count])


def build_affinity_mask(count: int = 2) -> int:
    """Return the affinity bitmask of the ``count`` fastest logical CPUs."""
    mask = 0
    for cpu in _probe_fast_cores(count=count):
        mask |= 1 << cpu
    return mask


def pin_to_fast_cores(count: int = 2) -> int:
    """Pin this process to the fastest cores; returns the applied mask."""
    mask = build_affinity_mask(count)
    _set_affinity(mask)
    return mask


def run_smoke(
    path: str,
    max_workers: int = 16,
    pinned: bool = True,
    pinned_cores: int = 2,
) -> dict:
    affinity_mask = 0
    if pinned:
        affinity_mask = pin_to_fast_cores(pinned_cores)
        max_workers = min(max_workers, pinned_cores)
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
        "affinity": {
            "pinned": bool(affinity_mask),
            "mask": hex(affinity_mask) if affinity_mask else None,
            "cpus": sorted(
                c for c in range(64) if affinity_mask & (1 << c)
            ) if affinity_mask else None,
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
        "gate": {
            "metric_rss_envelope_mib": round(max(peak_rss["value"] - rss_before, 0.0), 2),
            "metric_alloc_peak_mib": round(mem_peak / (1024 * 1024), 2),
            "metric_retained_records": scanner.records_retained,
            "note": (
                "regression gate metrics = python_alloc_peak_mib + "
                "retained_records; RSS is an informational envelope only"
            ),
        },
        "cancellation_responsiveness_ms": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="benchmarks/generated/fixture")
    parser.add_argument("--json", default=None, help="Write results JSON to this path")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--no-pin", action="store_true",
                        help="Disable P-core affinity pinning (non-comparable runs)")
    parser.add_argument("--pinned-cores", type=int, default=2,
                        help="Number of fastest (P) cores to pin to")
    args = parser.parse_args()

    result = run_smoke(
        args.path,
        max_workers=args.workers,
        pinned=not args.no_pin,
        pinned_cores=args.pinned_cores,
    )

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
        ("GATE: alloc peak (MiB)", result["python_alloc_peak_mib"]),
        ("GATE: retained records", result["retained_records"]),
        ("envelope: RSS (MiB)", result["peak_memory_mib"]),
        ("cancellation (ms)", result["cancellation_responsiveness_ms"]),
    ]
    print(f"SMOKE BENCHMARK - {result['path']}")
    print(header)
    for name, value in rows:
        if value is None:
            print(f"{name:<28}{'n/a':>14}")
        else:
            print(f"{name:<28}{value:>14}")
    affinity = result["affinity"]
    if affinity["pinned"]:
        print(f"\nPinned to P-cores: {affinity['cpus']} (mask {affinity['mask']})")
    else:
        print("\nNot pinned (default affinity)")
    print(f"\nOS: {result['environment']['platform']}")

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"\nJSON result: {args.json}")


if __name__ == "__main__":
    main()