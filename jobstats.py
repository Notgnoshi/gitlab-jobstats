#!/usr/bin/env python3
"""Query a GitLab project for CI/CD job statistics."""
import argparse
import json
import logging
import sys
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Union


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
    token = get_token(args)
    endpoint = f"https://{args.domain}/api/v4"

    pipelines = get_pipelines(
        token, endpoint, args.project, args.branch, args.max_pipelines, args.since
    )
    logging.info("Found %d total pipelines for %s", len(pipelines), args.project)
    jobs = []
    for pipeline in pipelines:
        pipeline_jobs = get_jobs_for_pipeline(token, endpoint, args.project, pipeline["id"])
        jobs += pipeline_jobs
    logging.info("Found %d total jobs for %s", len(jobs), args.project)

    jobs2csv(args.output, jobs)


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


def get_pipelines(
    token: str,
    endpoint: str,
    project: str,
    branch: Optional[str],
    max_pipelines: Optional[int],
    since: Optional[str],
) -> List[Dict]:
    """Get the most recent CI/CD pipelines for the given project."""
    project = urllib.parse.quote_plus(project)
    if since:
        # If we're limiting via the creation date, we don't want to limit the number of pipelines
        max_pipelines = None
    per_page = max_pipelines or 100

    page_num = 1
    url = f"{endpoint}/projects/{project}/pipelines?per_page={per_page}"
    if branch:
        url += f"&ref={branch}"
    if since:
        url += f"&created_after={since}"

    pipelines = []
    while True:
        page = http_get_json(token, f"{url}&page={page_num}")

        page_num += 1
        pipelines += page

        if not page or len(page) < per_page or max_pipelines and len(pipelines) >= max_pipelines:
            break
    return pipelines


def get_jobs_for_pipeline(token: str, endpoint: str, project: str, pipeline_id: int) -> List[Dict]:
    """Get the jobs for the given pipeline."""
    project = urllib.parse.quote_plus(project)
    # Assume that no pipeline has more than the pagination limit number of jobs. Include retried
    # jobs, because the purpose of this project is to get statistics for flaky CI/CD jobs
    url = f"{endpoint}/projects/{project}/pipelines/{pipeline_id}/jobs?include_retried=true"
    jobs = http_get_json(token, url)
    return jobs


def jobs2csv(output, jobs: List[Dict]):
    """Write each job's details to a CSV file for future analysis."""
    output.write("job-id,pipeline-id,job-url,created-date,name,status,duration,queued-duration\n")
    for job in jobs:
        output.write(f"{job['id']},")
        output.write(f"{job['pipeline']['id']},")
        output.write(f"{job['web_url']},")
        output.write(f"{job['created_at']},")
        output.write(f"\"{job['name']}\",")
        output.write(f"{job['status']},")
        output.write(f"{job['duration']},")
        output.write(f"{job['queued_duration']},")
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
