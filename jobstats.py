#!/usr/bin/env python3
"""Query a GitLab project for CI/CD job statistics."""

import argparse
import csv
import json
import logging
import os
import sys
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Set, Tuple, Union


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
        "project",
        help="The full group/project path, or a project ID",
    )
    parser.add_argument(
        "output",
        help="Output CSV file path. Will append to existing file if present.",
    )

    group = parser.add_argument_group()
    group.add_argument(
        "--requests-per-second",
        "-r",
        type=float,
        default=40,
        help="Limit API requests to this many per second.",
    )

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
    filter_limit = group.add_mutually_exclusive_group()
    filter_limit.add_argument(
        "--max-pipelines",
        type=int,
        default=20,
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
    rate_limit_delay = 1.0 / args.requests_per_second
    token = get_token(args)
    endpoint = f"https://{args.domain}/api/v4"

    # Read existing data to enable incremental updates
    known_pipeline_ids, max_date = read_existing_csv(args.output)
    append_mode = len(known_pipeline_ids) > 0

    # Auto-set --since from existing data if not provided
    since = args.since
    if since is None and max_date is not None:
        since = max_date
        logging.info("Auto-set --since to %s based on existing data", since)

    pipelines = get_pipelines(
        token,
        endpoint,
        args.project,
        args.branch,
        args.max_pipelines,
        since,
        rate_limit_delay,
        known_pipeline_ids=known_pipeline_ids,
    )
    logging.info("Found %d new pipelines for %s", len(pipelines), args.project)

    if not pipelines:
        logging.info("No new pipelines to fetch, exiting")
        return

    jobs = []
    for pipeline in pipelines:
        pipeline_jobs = get_jobs_for_pipeline(token, endpoint, args.project, pipeline["id"])
        jobs += pipeline_jobs
        time.sleep(rate_limit_delay)
    logging.info("Found %d new jobs for %s", len(jobs), args.project)

    jobs2csv(args.output, jobs, append=append_mode)


def http_get_json(token: str, url: str) -> Union[List, Dict]:
    """Make the given HTTP GET request with the given auth token."""
    logging.debug("GET %s ...", url)
    request = urllib.request.Request(url)
    request.add_header("PRIVATE-TOKEN", token)
    with urllib.request.urlopen(request) as response:
        if response.status != 200:
            logging.error("Request '%s' failed: %d", url, response.status)
            sys.exit(1)
        data = response.read()
        data = data.decode(response.info().get_param("charset") or "utf-8")
        data = json.loads(data)
        return data


def read_existing_csv(path: str) -> Tuple[Set[int], Optional[str]]:
    """Read an existing CSV file and return known pipeline IDs and max created date.

    Returns a tuple of (set of pipeline IDs, max created_at date string or None)
    """
    if not os.path.exists(path):
        return set(), None

    pipeline_ids = set()
    max_date = None

    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pipeline_ids.add(int(row["pipeline-id"]))
            created = row["created-date"]
            if max_date is None or created > max_date:
                max_date = created

    logging.info(
        "Read %d existing pipeline IDs from %s (max date: %s)", len(pipeline_ids), path, max_date
    )
    return pipeline_ids, max_date


def get_pipelines(
    token: str,
    endpoint: str,
    project: str,
    branch: Optional[str],
    max_pipelines: Optional[int],
    since: Optional[str],
    rate_limit_delay: float,
    known_pipeline_ids: Optional[Set[int]] = None,
) -> List[Dict]:
    """Get the most recent CI/CD pipelines for the given project.

    If known_pipeline_ids is provided, stops fetching as soon as a known pipeline
    is encountered (assumes pipelines are returned newest-first).
    """
    project = urllib.parse.quote_plus(project)
    if since:
        # If we're limiting via the creation date, we don't want to limit the number of pipelines
        max_pipelines = None
    per_page = max_pipelines or 100
    known_pipeline_ids = known_pipeline_ids or set()

    page_num = 1
    url = f"{endpoint}/projects/{project}/pipelines?per_page={per_page}"
    if branch:
        url += f"&ref={branch}"
    if since:
        url += f"&created_after={since}"

    pipelines = []
    stop_early = False
    while True:
        page = http_get_json(token, f"{url}&page={page_num}")

        for pipeline in page:
            if pipeline["id"] in known_pipeline_ids:
                logging.info("Reached known pipeline %d, stopping pagination", pipeline["id"])
                stop_early = True
                break
            pipelines.append(pipeline)

        page_num += 1

        if (
            stop_early
            or not page
            or len(page) < per_page
            or (max_pipelines and len(pipelines) >= max_pipelines)
        ):
            break
        time.sleep(rate_limit_delay)
    return pipelines


def get_jobs_for_pipeline(token: str, endpoint: str, project: str, pipeline_id: int) -> List[Dict]:
    """Get the jobs for the given pipeline."""
    project = urllib.parse.quote_plus(project)
    # Assume that no pipeline has more than the pagination limit number of jobs. Include retried
    # jobs, because the purpose of this project is to get statistics for flaky CI/CD jobs
    url = f"{endpoint}/projects/{project}/pipelines/{pipeline_id}/jobs?include_retried=true"
    jobs = http_get_json(token, url)
    return jobs


def jobs2csv(path: str, jobs: List[Dict], append: bool = False):
    """Write each job's details to a CSV file for future analysis."""
    mode = "a" if append else "w"
    with open(path, mode, newline="") as output:
        if not append:
            output.write(
                "job-id,pipeline-id,job-url,created-date,name,branch,status,coverage,duration,queued-duration\n"
            )
        for job in jobs:
            output.write(f"{job['id']},")
            output.write(f"{job['pipeline']['id']},")
            output.write(f"{job['web_url']},")
            output.write(f"{job['created_at']},")
            output.write(f'"{job["name"]}",')
            output.write(f"{job['ref']},")
            output.write(f"{job['status']},")
            output.write(f"{job['coverage']},")
            output.write(f"{job['duration']},")
            output.write(f"{job['queued_duration']}")
            output.write("\n")


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
