#!/usr/bin/env python3
"""Query a GitLab project for CI/CD job statistics."""
import argparse
import logging
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--log-level",
        "-l",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging output level. Defaults to INFO.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="Script output. Defaults to stdout.",
    )

    return parser.parse_args()


def main(args):
    pass


if __name__ == "__main__":
    args = parse_args()
    fmt = "%(asctime)s - %(module)s - %(levelname)s: %(message)s"
    logging.basicConfig(
        format=fmt,
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        level=args.log_level,
        stream=sys.stderr,
    )
    # Color log output if possible, because I'm a sucker
    try:
        import coloredlogs

        coloredlogs.install(fmt=fmt, level=args.log_level, datefmt="%Y-%m-%dT%H:%M:%S%z")
    except ImportError:
        pass
    main(args)
