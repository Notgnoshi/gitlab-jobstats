#!/usr/bin/env python3
"""Download job output for CI jobs."""

import argparse
import csv
import fnmatch
import logging
import pathlib
import sys
import time
import urllib.parse
import urllib.request
from typing import Dict, Tuple


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
    group = parser.add_argument_group()
    group.add_argument(
        "csv",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="CSV file of jobs to look at",
    )
    group.add_argument(
        "--output",
        "-o",
        type=pathlib.Path,
        help="Output directory to save job output in",
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
    parser.add_argument(
        "--requests-per-second",
        "-r",
        type=float,
        default=40,
        help="Limit API requests to this many per second.",
    )

    parser.add_argument(
        "--status",
        "-s",
        default="failed",
        help="Job status to download (default: failed)",
    )

    parser.add_argument(
        "--jobs",
        "-j",
        nargs="*",
        default="*",
        help="Job name globs to include. May be given multiple times",
    )

    return parser.parse_args()


def main(args):
    token = get_token(args)

    if not args.output:
        csv_path = pathlib.Path(args.csv.name)
        csv_dir = csv_path.parent
        args.output = csv_dir / csv_path.stem
    logging.debug("Saving job output to %s ...", args.output)

    jobs = csv.DictReader(args.csv)
    # Look at jobs matching the user-defined name patterns
    jobs = (j for j in jobs if any(fnmatch.fnmatchcase(j["name"], pat) for pat in args.jobs))
    # Filter out any jobs whose output we already downloaded
    jobs = (j for j in jobs if not (args.output / f"{j['job-id']}.txt").exists())
    jobs = [j for j in jobs if j["status"] == args.status]

    rate_limit_delay = 1.0 / args.requests_per_second
    logging.info("Found %d %s jobs. Downloading traces ...", len(jobs), args.status)
    for job in jobs:
        get_job_trace(token, args.output, job)
        time.sleep(rate_limit_delay)


def get_token(args) -> str:
    """Get the GitLab PAT token using the method defined by the CLI args."""
    if args.token:
        return args.token
    if args.token_file:
        return args.token_file.read().strip()
    # TODO: Add an option to read the token from stdin
    raise RuntimeError("Failed to find GitLab PAT")


def get_endpoint(job: Dict) -> Tuple[str, str]:
    """Get the API endpoint and project ID from one of the jobs.

    It would be frustrating to have to provide these details *again* from the CLI. We could add them
    to the CSV, but the job-url already contains all of that information.
    """
    result = urllib.parse.urlparse(job["job-url"])
    endpoint = f"{result.scheme}://{result.netloc}"
    project = result.path.split("/-/")[0].strip("/")
    logging.debug("Found endpoint: %s project: %s", endpoint, project)
    project = urllib.parse.quote_plus(project)
    return endpoint, project


def http_get_file(token: str, url: str, outfile: pathlib.Path):
    logging.debug("GET %s ...", url)
    request = urllib.request.Request(url)
    request.add_header("PRIVATE-TOKEN", token)
    with urllib.request.urlopen(request) as response:
        if response.status != 200:
            logging.error("Request '%s' failed: %d", url, response.status)
            sys.exit(1)
        data = response.read()
        with outfile.open("wb") as f:
            f.write(data)


def get_job_trace(token: str, outdir: pathlib.Path, job: Dict):
    if not outdir.exists():
        outdir.mkdir(exist_ok=True, parents=True)
    job_id = job["job-id"]
    trace_file = outdir / f"{job_id}.txt"
    endpoint, project = get_endpoint(job)
    url = f"{endpoint}/api/v4/projects/{project}/jobs/{job_id}/trace"
    http_get_file(token, url, trace_file)


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
