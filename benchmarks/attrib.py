"""Stage-level attribution for the Phase-5 per-file classification cost.

Pinned, uninstrumented timings over the generated 50k fixture. Reports the
wall cost of each pipeline stage in isolation vs. the full classify_scan, so an
optimization target is chosen from evidence, not guesses.
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from folder_analyzer.engine import classifier
from folder_analyzer.engine.kb import apps, categories, env_paths, known_paths, registry
from folder_analyzer.engine.kb import classify as kb_classify, reset_session_caches as kb_reset
from folder_analyzer.engine.kb import classify_scan_path, prepare_scan_folder
from folder_analyzer.engine.kb._norm import components as kb_components, norm as kb_norm

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(PROJECT_ROOT, "benchmarks", "generated", "fixture")


def pin_to_fast_cores() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        mask = 0
        N = os.cpu_count() or 1
        for i in range(N):
            if i < 8 and i != 0 and i != 4:
                mask |= 1 << i
        kernel32 = ctypes.windll.kernel32
        kernel32.SetThreadAffinityMask(kernel32.GetCurrentThread(), mask)
    except Exception:
        pass


def load_paths() -> list[str]:
    paths: list[str] = []
    for root, _dirs, files in os.walk(FIXTURE):
        for name in files:
            paths.append(os.path.join(root, name))
    return paths


def best_of(func, paths: list[str], rounds: int = 3) -> float:
    best = float("inf")
    for _ in range(rounds):
        start = time.perf_counter()
        func(paths)
        best = min(best, time.perf_counter() - start)
    return best


def run(stages):
    def make(fn):
        def run_all(paths):
            for p in paths:
                fn(p)
        return run_all

    def folder_grouped(background_fn):
        def run_all(paths):
            ctxs = {}
            for p in paths:
                folder = os.path.dirname(p)
                ctx = ctxs.get(folder)
                if ctx is None:
                    ctx = prepare_scan_folder(folder)
                    ctxs[folder] = ctx
                background_fn(ctx, os.path.basename(p), folder)
        return run_all

    def co_grouped(fn):
        return folder_grouped(
            lambda ctx, name, folder: fn(ctx, name, folder)
        )

    def classify_scan_grouped(paths):
        ctxs = {}
        for p in paths:
            folder = os.path.dirname(p)
            ctx = ctxs.get(folder)
            if ctx is None:
                ctx = prepare_scan_folder(folder)
                ctxs[folder] = ctx
            classifier.classify_scan(p, filename=os.path.basename(p), _ctx=ctx)

    def classify_scan_nogroup(paths):
        for p in paths:
            classifier.classify_scan(p, filename=os.path.basename(p))

    def scan_path_only(ctx, name, tag):
        key = ctx.folder_key
        classify_scan_path(ctx, file_key=key, file_name=name)

    scan_assessment = classifier.ScanAssessment

    def make_assessment(paths):
        for p in paths:
            scan_assessment(
                impact="none", confidence="high",
                reason_key="disposable_positive_evidence",
                recommendation="safe_to_delete",
                reason_params=None, detected_category="temp", app_id=None,
                is_user_data=False, is_temporary=True,
                bucket="disposable",
            )

    layers = {
        "none (loop only)": lambda paths: None,
        "norm": make(kb_norm),
        "norm+components": make(lambda p: kb_components(kb_norm(p))),
        "categories.classify": make(lambda p: categories.classify(p)),
        "apps.classify": make(lambda p: apps.classify(p)),
        "known_paths.classify": make(lambda p: known_paths.classify(p)),
        "env_paths.classify": make(lambda p: env_paths.classify(p)),
        "registry.classify": make(lambda p: registry.classify(p)),
        "kb_classify (all tiers)": make(lambda p: kb_classify(p)),
        "classify_scan (no ctx)": classify_scan_nogroup,
        "classify_scan (ctx)": classify_scan_grouped,
        "classify_scan_path only (ctx)": co_grouped(scan_path_only),
        "ScanAssessment ctor only": make_assessment,
    }
    for name, fn in layers.items():
        t = best_of(fn, paths)
        print(f"{name:34s} {t * 1000:8.1f} ms  ({t / len(paths) * 1e6:6.1f} us/file)")
    print(f"\npaths: {len(paths)}")


if __name__ == "__main__":
    pin_to_fast_cores()
    paths = load_paths()
    kb_reset()
    first = classifier.classify_scan(paths[0])  # warm imports
    print(f"first verdict sanity: {first.reason_key}/{first.detected_category}")
    run(paths)