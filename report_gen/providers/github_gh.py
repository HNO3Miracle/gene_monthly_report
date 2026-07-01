"""GitHub contribution provider backed by the `gh` CLI."""

import datetime
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from report_gen.models import CommitRecord, IssueRecord, PRRecord
from report_gen.providers.base import Provider

_RETRY_COUNT = 3
_RETRY_DELAY = 2.0  # seconds between retries (network is occasionally flaky)


def _gh(*args: str, retries: int = _RETRY_COUNT) -> Any:
    """Run `gh` with the given arguments and return parsed JSON.

    Retries up to *retries* times on transient errors (EOF / network failures).
    Raises ``subprocess.CalledProcessError`` on HTTP errors (no retry).
    """
    cmd = ["gh"] + list(args)
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(result.stdout) if result.stdout.strip() else {}
        except subprocess.CalledProcessError:
            raise
        except (json.JSONDecodeError, OSError) as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(_RETRY_DELAY)
    raise RuntimeError(f"gh command failed after {retries} attempts: {cmd}") from last_exc


def _gh_search(query: str) -> list[dict]:
    """Run an issue/PR GitHub Search query and return all matching items."""
    items: list[dict] = []
    page = 1
    while True:
        data = _gh(
            "api", "--method", "GET", "search/issues",
            "-f", f"q={query}",
            "-f", "per_page=100",
            "-f", f"page={page}",
        )
        batch = data.get("items", [])
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return items


def _date_range_str(start: datetime.date, end: datetime.date) -> str:
    return f"{start.isoformat()}..{end.isoformat()}"


def _split_full_repo(full_repo: str) -> tuple[str, str]:
    owner, repo = full_repo.split("/", 1)
    return owner, repo


def _repo_from_search_item(item: dict) -> str:
    repo_url = item.get("repository_url", "")
    marker = "/repos/"
    if marker not in repo_url:
        raise ValueError(f"GitHub search item missing repository_url: {item!r}")
    return repo_url.rsplit(marker, 1)[1]


def _fetch_pr_commits(org: str, repo: str, pr_number: int, merged: bool) -> list[CommitRecord]:
    """Fetch all commits for a PR."""
    data = _gh("api", f"repos/{org}/{repo}/pulls/{pr_number}/commits", "--paginate")
    if isinstance(data, dict):
        data = []

    records: list[CommitRecord] = []
    for commit in data:
        sha = commit.get("sha", "")
        sha7 = sha[:7]
        commit_data = commit.get("commit", {})
        message = commit_data.get("message", "").split("\n")[0].strip()
        author_email = commit_data.get("author", {}).get("email", "")
        if merged:
            url = f"https://github.com/{org}/{repo}/commit/{sha}"
        else:
            url = f"https://github.com/{org}/{repo}/pull/{pr_number}/commits/{sha}"
        records.append(
            CommitRecord(
                sha7=sha7,
                message=message,
                url=url,
                author_email=author_email,
            )
        )
    return records


def _fetch_closing_issues(org: str, repo: str, pr_number: int) -> list[IssueRecord]:
    """Return issues closed by this PR via GraphQL."""
    query = """
query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      closingIssuesReferences(first: 50) {
        nodes { number title url }
      }
    }
  }
}
"""
    data = _gh(
        "api", "graphql",
        "-f", f"query={query}",
        "-f", f"owner={org}",
        "-f", f"repo={repo}",
        "-F", f"pr={pr_number}",
    )
    nodes = (
        data.get("data", {})
            .get("repository", {})
            .get("pullRequest", {})
            .get("closingIssuesReferences", {})
            .get("nodes", [])
    )
    return [IssueRecord(number=n["number"], title=n["title"], url=n["url"]) for n in nodes]


def _build_pr_from_item(org: str, repo: str, item: dict, merged: bool) -> PRRecord:
    """Build a PRRecord for a single PR search result."""
    number = item["number"]
    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_commits = ex.submit(_fetch_pr_commits, org, repo, number, merged)
        fut_closing = (
            ex.submit(_fetch_closing_issues, org, repo, number)
            if merged
            else None
        )

        commits = fut_commits.result()
        closing: list[IssueRecord] = fut_closing.result() if fut_closing else []

    full_repo = f"{org}/{repo}"
    return PRRecord(
        number=number,
        title=item.get("title", ""),
        url=item.get("html_url", f"https://github.com/{full_repo}/pull/{number}"),
        state="merged" if merged else item.get("state", "open"),
        commits=commits,
        closing_issues=closing,
        approved=not merged,
    )


def _build_prs_by_repo_concurrent(
    items_by_repo: dict[str, list[dict]], merged: bool
) -> dict[str, list[PRRecord]]:
    """Build PRRecords for grouped search results, preserving per-repo order."""
    jobs: list[tuple[str, int, dict]] = []
    for full_repo, items in items_by_repo.items():
        for idx, item in enumerate(items):
            jobs.append((full_repo, idx, item))

    if not jobs:
        return {repo: [] for repo in items_by_repo}

    workers = min(len(jobs), 8)
    built: dict[str, dict[int, PRRecord]] = {repo: {} for repo in items_by_repo}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {}
        for full_repo, idx, item in jobs:
            org, repo = _split_full_repo(full_repo)
            fut = ex.submit(_build_pr_from_item, org, repo, item, merged)
            futures[fut] = (full_repo, idx)

        for fut in as_completed(futures):
            full_repo, idx = futures[fut]
            built[full_repo][idx] = fut.result()

    result: dict[str, list[PRRecord]] = {}
    for full_repo, items in items_by_repo.items():
        result[full_repo] = [built[full_repo][i] for i in range(len(items))]
    return result


def _group_search_items_by_repo(items: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for item in items:
        full_repo = _repo_from_search_item(item)
        grouped.setdefault(full_repo, []).append(item)
    return grouped


class GithubGhProvider(Provider):
    """Fetches contribution data from GitHub using the `gh` CLI."""

    def __init__(self, org: str, repo: str):
        self.org = org
        self.repo = repo
        self._full_repo = f"{org}/{repo}"

    def _build_pr(self, item: dict, merged: bool) -> PRRecord:
        """Build a PRRecord for a single PR, fetching commits and closing issues."""
        return _build_pr_from_item(self.org, self.repo, item, merged)

    def _build_prs_concurrent(self, items: list[dict], merged: bool) -> list[PRRecord]:
        """Build PRRecords for all items concurrently (one thread per PR)."""
        if not items:
            return []
        # Cap workers to avoid hammering the API; 8 is a reasonable ceiling
        workers = min(len(items), 8)
        results: dict[int, PRRecord] = {}
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {
                ex.submit(self._build_pr, item, merged): i
                for i, item in enumerate(items)
            }
            for fut in as_completed(futures):
                idx = futures[fut]
                results[idx] = fut.result()
        # Restore original order
        return [results[i] for i in range(len(items))]

    def get_merged_prs(
        self, username: str, start: datetime.date, end: datetime.date
    ) -> list[PRRecord]:
        dr = _date_range_str(start, end)
        query = (
            f"repo:{self._full_repo} is:pr author:{username} "
            f"is:merged merged:{dr}"
        )
        items = _gh_search(query)
        return self._build_prs_concurrent(items, merged=True)

    def get_approved_open_prs(self, username: str) -> list[PRRecord]:
        """Open PRs by *username* that have been approved (未合并 PR)."""
        query = (
            f"repo:{self._full_repo} is:pr author:{username} "
            f"is:open review:approved"
        )
        items = _gh_search(query)
        return self._build_prs_concurrent(items, merged=False)

    def get_created_issues(
        self, username: str, start: datetime.date, end: datetime.date
    ) -> list[IssueRecord]:
        dr = _date_range_str(start, end)
        query = (
            f"repo:{self._full_repo} is:issue author:{username} "
            f"created:{dr}"
        )
        items = _gh_search(query)
        return [
            IssueRecord(
                number=item["number"],
                title=item.get("title", ""),
                url=item.get("html_url", ""),
            )
            for item in items
        ]


class GithubGhGlobalProvider:
    """Fetch GitHub contribution data without restricting to configured repos."""

    def get_merged_prs_by_repo(
        self, username: str, start: datetime.date, end: datetime.date
    ) -> dict[str, list[PRRecord]]:
        dr = _date_range_str(start, end)
        query = f"is:pr author:{username} is:merged merged:{dr}"
        items = _gh_search(query)
        grouped = _group_search_items_by_repo(items)
        return _build_prs_by_repo_concurrent(grouped, merged=True)

    def get_approved_open_prs_by_repo(self, username: str) -> dict[str, list[PRRecord]]:
        query = f"is:pr author:{username} is:open review:approved"
        items = _gh_search(query)
        grouped = _group_search_items_by_repo(items)
        return _build_prs_by_repo_concurrent(grouped, merged=False)

    def get_created_issues_by_repo(
        self, username: str, start: datetime.date, end: datetime.date
    ) -> dict[str, list[IssueRecord]]:
        dr = _date_range_str(start, end)
        query = f"is:issue author:{username} created:{dr}"
        grouped = _group_search_items_by_repo(_gh_search(query))
        return {
            full_repo: [
                IssueRecord(
                    number=item["number"],
                    title=item.get("title", ""),
                    url=item.get("html_url", ""),
                )
                for item in items
            ]
            for full_repo, items in grouped.items()
        }

    def get_closed_issues_via_prs(self, merged_prs: list[PRRecord]) -> list[IssueRecord]:
        seen: set[str] = set()
        result: list[IssueRecord] = []
        for pr in merged_prs:
            for issue in pr.closing_issues:
                if issue.url not in seen:
                    seen.add(issue.url)
                    result.append(issue)
        return result
