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
        default="DEBUG",
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

    group = parser.add_argument_group()

    tokens = group.add_mutually_exclusive_group(required=True)
    tokens.add_argument(
        "--token",
        "-t",
        help="A GitLab PAT with API read access. Consider using --token-file instead",
    )
    tokens.add_argument(
        "--token-file",
        "-f",
        type=argparse.FileType("r"),
        help="Read the GitLab PAT from the given file",
    )

    group.add_argument(
        "--domain",
        "-d",
        default="gitlab.cnh.com",
        help="The domain for your GitLab instance. Defaults to gitlab.cnh.com",
    )
    group.add_argument(
        "--project",
        "-p",
        required=True,
        help="The full group/project path, or a project ID",
    )
    filter_limit = group.add_mutually_exclusive_group()
    filter_limit.add_argument(
        "--max-pipelines",
        type=int,
        default=2,  # TODO: Increase once finished
        help="The maximum number of jobs to query",
    )
    filter_limit.add_argument(
        "--since",
        default=None,
        help="An ISO-8061 date to query pipelines created since",
    )
    group.add_argument(
        "--branch",
        "-b",
        default=None,
        help="Filter jobs to the specified branch",
    )

    return parser.parse_args()


def main(args):
    token = get_token(args)


def get_token(args) -> str:
    """Get the GitLab PAT token using the method defined by the CLI args."""
    if args.token:
        return args.token
    if args.token_file:
        return args.token_file.read().strip()
    # TODO: Add an option to read the token from stdin
    raise RuntimeError("Failed to find GitLab PAT")


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
