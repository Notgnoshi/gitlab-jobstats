#!/usr/bin/env python3
"""Convert GitLab CI job logs with log section markers into Chrome JSON tracing format."""

import argparse
import json
import re
import sys

SECTION_BRACKET = re.compile(r"section_(start|end):(\d+):([^\[\s\x00-\x1f]+)")


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    group = parser.add_argument_group()
    group.add_argument(
        "--input",
        "-i",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="Script input. Defaults to stdin.",
    )
    group.add_argument(
        "--output",
        "-o",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="Script output. Defaults to stdout.",
    )

    return parser.parse_args()


def main(args):
    # Handle non-utf8 data
    args.input.reconfigure(errors="replace")
    start_time = None
    events = []
    for line in args.input:
        for match in SECTION_BRACKET.finditer(line):
            bracket, timestamp, name = match.groups()
            timestamp = int(timestamp)
            if not start_time:
                start_time = timestamp

            elapsed = timestamp - start_time  # seconds
            elapsed *= 1_000_000  # microseconds
            marker = "B" if bracket == "start" else "E"
            event = {
                "name": name,
                "ph": marker,
                "ts": elapsed,
                "pid": 1,
                "tid": 1,
            }
            events.append(event)
    json.dump(events, args.output)


if __name__ == "__main__":
    args = parse_args()
    main(args)
