# gitlab-jobstats
Query statistics for GitLab CI/CD jobs

# Usage

```shell
./jobstats.py \
    --token-file ~/.gitlab-pat.txt \
    --domain gitlab.com \
    --project my-group/my-project \
    --branch master \
    --since 2025-01-01 \
    --output my-project.csv
```

This will generate a CSV of jobs for all pipelines on the specified branch. Here's an example

```
job-id,pipeline-id,job-url,created-date,name,status,duration,queued-duration
7668536,1417944,https://gitlab.com/my-group/my-project-/jobs/7668536,2025-06-26T14:22:02.575-05:00,"job1",success,7.396026,0.420097,
7668535,1417944,https://gitlab.com/my-group/my-project-/jobs/7668535,2025-06-26T14:22:02.569-05:00,"job2",success,20.611112,0.49462,
7668534,1417944,https://gitlab.com/my-group/my-project-/jobs/7668534,2025-06-26T14:22:02.561-05:00,"job3",failed,8.140573,0.299714,
7668533,1417944,https://gitlab.com/my-group/my-project-/jobs/7668533,2025-06-26T14:22:02.555-05:00,"job4",success,8.651492,0.939418,
```

# TODO

* [ ] Build tooling to summarize job failures
* [ ] Build tooling to nicely visualize the job failures? (what's the right visualization for job
      failures that actually provides insight?)
* [ ] Build tooling to identify jobs that fail more frequently than other jobs
* [ ] Build tooling to help identify any systemic flaky jobs. Perhaps pass a regex to scrape job
      stderr output with? (e.g., identify names of failing tests). Or perhaps just automate opening
      the `job-url` in the browser, and prompt for a root cause?
