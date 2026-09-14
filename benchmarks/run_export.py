"""Phase 6 benchmark: v2 export generation cost (JSON/CSV/HTML).

Methodology mirrors benchmarks/run_smoke.py (pinned P-cores; see its docstring):

- **Uninstrumented wall-clock (no tracemalloc) is the headline cost.**
- tracemalloc alloc-peak for the fold+export phase is the secondary gate.
- Times recorded:
    t_scan  : ``Scanner.scan`` (unchanged Phase-5 engine)
    t_fold  : ``Scanner.scan_result`` aggregation (the ONLY scan-side addition
              the v2 export path introduces — exporters themselves never scan)
    t_json / t_csv / t_html: v2 export generation to disk
The scan-side delta of Phase 6 is ``t_fold``; export generation is reported as
its own honest number (exporters consume the collected ScanResult only).

Usage:
    python benchmarks/run_export.py --path benchmarks/generated/fixture
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import tracemalloc

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from run_smoke import pin_to_fast_cores, _read_affinity, _set_affinity

from folder_analyzer.scanner import Scanner
from folder_analyzer.i18n import I18n
from folder_analyzer.exporter import export_json_v2, export_csv_v2, export_html_v2

_FIXED_SCAN_DATE = "2026-01-14T12:00:00"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="benchmarks/generated/fixture")
    parser.add_argument("--json", default=None, help="Write results JSON to this path")
    parser.add_argument("--outdir", default="benchmarks/generated/export_out")
    parser.add_argument("--pinned-cores", type=int, default=2)
    parser.add_argument("--no-pin", action="store_true")
    args = parser.parse_args()

    original_mask = _read_affinity()
    affinity_mask = 0
    max_workers = 16
    if not args.no_pin:
        affinity_mask = pin_to_fast_cores(args.pinned_cores)
        max_workers = min(max_workers, args.pinned_cores)

    os.makedirs(args.outdir, exist_ok=True)
    out_json = os.path.join(args.outdir, "report.json")
    out_csv = os.path.join(args.outdir, "report.csv")
    out_html = os.path.join(args.outdir, "report.html")

    # --- Uninstrumented headline run (no tracemalloc) ---------------------
    scanner = Scanner(max_workers=max_workers)
    t0 = time.perf_counter()
    root = scanner.scan(args.path)
    t_scan = time.perf_counter() - t0

    t0 = time.perf_counter()
    scan_result = scanner.scan_result()
    t_fold = time.perf_counter() - t0

    i18n = I18n("en")
    t0 = time.perf_counter()
    export_json_v2(root, i18n, out_json, scan_result, scan_date=_FIXED_SCAN_DATE)
    t_json = time.perf_counter() - t0
    t0 = time.perf_counter()
    export_csv_v2(root, i18n, out_csv, scan_result, scan_date=_FIXED_SCAN_DATE)
    t_csv = time.perf_counter() - t0
    t0 = time.perf_counter()
    export_html_v2(root, i18n, out_html, scan_result, scan_date=_FIXED_SCAN_DATE)
    t_html = time.perf_counter() - t0

    files = scanner.scanned_files
    folders = scanner.scanned_folders

    # --- Instrumented gate pass (tracemalloc alloc-peak over fold + export) ---
    scanner2 = Scanner(max_workers=max_workers)
    scanner2.scan(args.path)
    tree2 = scanner2._scan_tree
    tracemalloc.start()
    t0 = time.perf_counter()
    scan_result2 = scanner2.scan_result()
    export_json_v2(tree2, i18n, out_json, scan_result2, scan_date=_FIXED_SCAN_DATE)
    export_csv_v2(tree2, i18n, out_csv, scan_result2, scan_date=_FIXED_SCAN_DATE)
    export_html_v2(tree2, i18n, out_html, scan_result2, scan_date=_FIXED_SCAN_DATE)
    t_gate = time.perf_counter() - t0
    _, alloc_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    _set_affinity(original_mask)

    scan_side_delta_pct = round(t_fold / t_scan * 100, 2) if t_scan > 0 else 0.0
    result = {
        "path": os.path.abspath(args.path),
        "affinity": {
            "pinned": bool(affinity_mask),
            "mask": hex(affinity_mask) if affinity_mask else None,
            "cpus": sorted(c for c in range(64) if affinity_mask & (1 << c))
            if affinity_mask else None,
        },
        "file_count": files,
        "folder_count": folders,
        "uninstrumented_wall_clock_s": {
            "t_scan": round(t_scan, 4),
            "t_fold_scan_result": round(t_fold, 6),
            "t_json_v2": round(t_json, 4),
            "t_csv_v2": round(t_csv, 4),
            "t_html_v2": round(t_html, 4),
            "t_export_total": round(t_json + t_csv + t_html, 4),
            "t_scan_plus_fold": round(t_scan + t_fold, 4),
        },
        "scan_side_delta": {
            "delta_s": round(t_fold, 6),
            "delta_pct_vs_t_scan": scan_side_delta_pct,
        },
        "export_rates_files_per_sec": {
            "json": round(files / t_json, 1) if t_json > 0 else 0.0,
            "csv": round(files / t_csv, 1) if t_csv > 0 else 0.0,
            "html": round(files / t_html, 1) if t_html > 0 else 0.0,
        },
        "export_output_bytes": {
            "json": os.path.getsize(out_json),
            "csv": os.path.getsize(out_csv),
            "html": os.path.getsize(out_html),
        },
        "gate": {
            "instrumented_fold_plus_export_s": round(t_gate, 4),
            "python_alloc_peak_mib": round(alloc_peak / (1024 * 1024), 2),
            "retained_records": scanner.records_retained,
            "note": (
                "headline cost = uninstrumented wall-clock; alloc peak is the "
                "deterministic secondary gate; tracemalloc inflates both"
            ),
        },
    }

    print(f"PHASE 6 EXPORT BENCHMARK - {result['path']}")
    print(f"{'metric':<38}{'value':>14}")
    print("-" * 54)
    rows = [
        ("file count", files),
        ("folder count", folders),
        ("t_scan (baseline, s)", result["uninstrumented_wall_clock_s"]["t_scan"]),
        ("t_fold scan_result (s)", result["uninstrumented_wall_clock_s"]["t_fold_scan_result"]),
        ("SCAN-SIDE DELTA %", scan_side_delta_pct),
        ("t_json_v2 (s)", result["uninstrumented_wall_clock_s"]["t_json_v2"]),
        ("t_csv_v2 (s)", result["uninstrumented_wall_clock_s"]["t_csv_v2"]),
        ("t_html_v2 (s)", result["uninstrumented_wall_clock_s"]["t_html_v2"]),
        ("t_export_total (s)", result["uninstrumented_wall_clock_s"]["t_export_total"]),
        ("GATE alloc peak (MiB)", result["gate"]["python_alloc_peak_mib"]),
        ("GATE retained records", result["gate"]["retained_records"]),
        ("json/csv/html bytes", f"{result['export_output_bytes']['json']:,} / "
                               f"{result['export_output_bytes']['csv']:,} / "
                               f"{result['export_output_bytes']['html']:,}"),
    ]
    for name, value in rows:
        print(f"{name:<38}{value:>14}")
    if result["affinity"]["pinned"]:
        print(f"\nPinned to P-cores: {result['affinity']['cpus']} (mask {result['affinity']['mask']})")
    else:
        print("\nNot pinned (default affinity)")

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"\nJSON result: {args.json}")


if __name__ == "__main__":
    main()