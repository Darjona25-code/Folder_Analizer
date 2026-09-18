"""Deterministic synthetic fixture generator for Folder Analyzer benchmarks.

This generator is a REUSABLE project asset, not a one-off test helper. It builds
a reproducible ~50,000-file directory tree (fixed seed) used to establish and
track the performance baseline across phases.

Usage:
    python benchmarks/gen_fixture.py --out benchmarks/generated/fixture
    python benchmarks/gen_fixture.py --out <dir> --files 50000 --seed 20260101

The output path is gitignored (benchmarks/generated/).
"""

from __future__ import annotations

import argparse
import os
import random
import sys

EXTENSIONS = [
    ".tmp", ".log", ".cache", ".dat", ".txt", ".jpg", ".png", ".zip",
    ".dll", ".exe", ".json", ".csv", ".html", ".pyc", ".bin", ".bak",
]

DIR_NAMES = [
    "appdata", "cache", "temp", "logs", "downloads", "documents", "media",
    "projects", "backups", "config", "build", "node_modules", "packages",
    "export", "import", "data", "metadata", "reports", "sessions", "objects",
]


def _random_size(rng: random.Random) -> int:
    """Deterministic size distribution: many small files, some large ones."""
    roll = rng.random()
    if roll < 0.65:
        return rng.randint(0, 64 * 1024)
    if roll < 0.85:
        return rng.randint(64 * 1024, 512 * 1024)
    if roll < 0.97:
        return rng.randint(512 * 1024, 4 * 1024 * 1024)
    return rng.randint(4 * 1024 * 1024, 32 * 1024 * 1024)


def build_fixture(out_dir: str, files_count: int, seed: int) -> dict:
    """Create the deterministic tree and return a summary."""
    rng = random.Random(seed)
    os.makedirs(out_dir, exist_ok=True)

    dirs = [out_dir]
    for depth in range(1, 4):
        parent_levels = [d for d in dirs if d.count(os.sep) <= out_dir.count(os.sep) + depth - 1]
        parents = parent_levels[:]
        for _ in range(12):
            parent = rng.choice(parents)
            new_dir = os.path.join(parent, f"{rng.choice(DIR_NAMES)}_{rng.randint(1, 99999)}")
            os.makedirs(new_dir, exist_ok=True)
            dirs.append(new_dir)

    total_bytes = 0
    created = 0
    while created < files_count:
        parent = rng.choice(dirs)
        size = _random_size(rng)
        filename = f"f{created:06d}_{rng.randint(1000, 9999)}{rng.choice(EXTENSIONS)}"
        path = os.path.join(parent, filename)
        with open(path, "wb") as f:
            f.truncate(size)
        total_bytes += size
        created += 1

    summary = {
        "seed": seed,
        "files": created,
        "dirs": len(dirs) - 1,
        "total_bytes": total_bytes,
        "out_dir": os.path.abspath(out_dir),
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="benchmarks/generated/fixture", help="Output directory")
    parser.add_argument("--files", type=int, default=50000, help="Approximate file count")
    parser.add_argument("--seed", type=int, default=20260101, help="Random seed")
    args = parser.parse_args()

    summary = build_fixture(args.out, args.files, args.seed)
    print(json_dumps(summary))
    print(
        f"Fixture ready: {summary['files']:,} files, {summary['dirs']:,} dirs, "
        f"{summary['total_bytes'] / (1024 * 1024):.1f} MiB at {summary['out_dir']}"
    )


def json_dumps(data: dict) -> str:
    import json
    return json.dumps(data, indent=2)


if __name__ == "__main__":
    sys.exit(main())