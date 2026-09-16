"""Desktop entry point: ``python -m desktop_app`` (Phase 11 adds ``--selftest``)."""

import argparse
import sys


def _parse_args(argv):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--selftest", metavar="REPORT_JSON", default=None)
    args, _ = parser.parse_known_args(argv)
    return args


if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])
    if args.selftest:
        from desktop_app.selftest import run_selftest

        sys.exit(run_selftest(args.selftest))
    from desktop_app.app import main

    sys.exit(main())