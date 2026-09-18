# Benchmarks — Folder Analyzer

This directory holds the performance tooling for Folder Analyzer v3.0.

## Purpose

- `gen_fixture.py` — deterministic, reusable synthetic fixture generator
  (~50,000 files, fixed seed) used for regression/performance checks **every
  phase**, not a one-off test.
- `run_smoke.py` — smoke benchmark runner that establishes the Phase 1 baseline
  and is re-run at the end of every phase.
- `results/` — JSON outputs of each run (gitignored).
- `generated/` — fixture output (gitignored).

Phase 8 extends this into the full benchmark suite (analysis/composition times,
cancellation responsiveness). This Phase 1 tooling is the baseline reference.

## Usage

```powershell
python benchmarks/gen_fixture.py --out benchmarks/generated/fixture
python benchmarks/run_smoke.py --path benchmarks/generated/fixture --json benchmarks/results/smoke-phase1.json
```

To change scale: `--files 200000` and/or `--seed <n>` (structure stays
deterministic for a given seed).

## Metrics recorded (Phase 1)

- total scan time (s)
- files/second
- analysis time (s) — 0.0 until Phase 3
- composition time (s) — 0.0 until Phase 5
- file / folder counts
- peak memory (MiB, RSS delta during scan) and Python allocation peak (tracemalloc)
- retained records — 0 until Phase 3 retention
- cancellation responsiveness (ms) — n/a until Phase 8

## Environment assumptions (reference)

The baseline is documented for the development machine (see
`docs/ARCHITECTURE.md §6`). Any environment change that legitimately shifts the
baseline must be documented, never silently re-baselined.

## Regression gate

A **>20% regression** of any phase run versus the documented baseline is a
**phase-closing gate** (stop → investigate → fix/justify → re-run; do not close
the phase until resolved or explicitly user-overridden and documented).
See `docs/ROADMAP.md §15/§22`. These are engineering targets derived from
measured results, not universal performance guarantees.

## Baseline (Phase 1)

See `docs/ARCHITECTURE.md §6` for the authoritative per-phase table and the
recorded Phase 1 numbers.