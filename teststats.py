#!/usr/bin/env python3
"""Identify failing tests by pattern from failing job output."""
import argparse
import collections
import logging
import re
import sys
from typing import List

FAILING_TEST_PATTERNS = [
    # GTest: '[  FAILED  ] TestSuite.TestCase'
    re.compile(r"^\s*\[\s+FAILED\s+\]\s+(\w+\.\w+)$"),
    # cargo-test: 'test qualified::test::name ... FAILED'
    re.compile(r"test ([a-zA-Z0-9:_]+) ... FAILED"),
    # cargo-nextest: 'FAIL [ 0.5s] library_name qualified::test::name'
    re.compile(r"FAIL\b.* ([a-zA-Z0-9:_]+)$"),
]
ANSI_ESCAPE_SEQ = re.compile(r"\x1b\[([0-9,A-Z]{1,2}(;[0-9]{1,2})?(;[0-9]{3})?)?[m|K]?")


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
        help="Output file to write results to. Defaults to stdout",
    )
    parser.add_argument(
        "input",
        nargs="+",
        type=argparse.FileType("r"),
        help="Job output files to scrape through",
    )
    parser.add_argument(
        "--pattern",
        "-p",
        nargs="*",
        default=[],
        help="A Python RegEx for the name of a failing test. The name must be the last capture group.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List paths to job output for each test failure",
    )

    return parser.parse_args()


def main(args):
    patterns = FAILING_TEST_PATTERNS + [re.compile(p) for p in args.pattern]
    counter = collections.Counter()
    file_map = collections.defaultdict(list)
    for file in args.input:
        results = scrape_file(file, patterns)
        if results:
            logging.debug("%s: %s", file.name, results)
            counter.update(results)
            for result in results:
                file_map[result].append(file.name)
    for test, num_failures in counter.most_common():
        print(f"{test}:", file=args.output)
        print(f"\tfailures: {num_failures}", file=args.output)
        if args.list:
            files = " ".join(file_map[test])
            print(f"\tlogs: {files}", file=args.output)


def scrape_file(file, patterns: List[re.Pattern]) -> List[str]:
    # Use a set for each file, because the same job can't fail multiple times in the same run (not
    # actually true, but going to assume as much). GTest at least prints the name of failing tests
    # multiple times in one invocation (once as the test was run, and once again at the end) so we
    # don't want to double-count.
    results = set()
    for line in file:
        line = strip_ansi_codes(line).strip()
        for pattern in patterns:
            match = pattern.match(line)
            if match:
                # If there's capture groups, the test name is the inner-most
                g = match.groups()
                if g:
                    results.add(g[-1])

    return list(results)


def strip_ansi_codes(s):
    return re.sub(ANSI_ESCAPE_SEQ, "", s)


if __name__ == "__main__":
    args = parse_args()
    fmt = "%(asctime)s %(module)s %(levelname)s: %(message)s"
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
