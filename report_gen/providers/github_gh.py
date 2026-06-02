"""GitHub contribution provider backed by the `gh` CLI."""

import calendar
import json
import subprocess
import time
from typing import Any

from report_gen.models import CommitRecord, IssueRecord, PRRecord
from report_gen.providers.base import Provider

_RETRY_COUNT = 3
_RETRY_DELAY = 2.0  # seconds between retries (network is occasionally flaky)


def _gh(*args: str, retries: int = _RETRY_COUNT) -> Any:
    """Run `gh` with the given arguments and return parsed JSON.

    Retries up to *retries* times on transient errors (EOF / network failures).
    Raises ``subprocess.CalledProcessError`` or ``RuntimeError`` on final failure.
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
        except subprocess.CalledProcessError as exc:
            # gh exits non-zero on HTTP errors; re-raise immediately
            raise
        except (json.JSONDecodeError, OSError) as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(_RETRY_DELAY)
    raise RuntimeError(f"gh command failed after {retries} attempts: {cmd}") from last_exc


def _gh_search_prs(query: str) -> list[dict]:
    """Run a GitHub Search query and return all matching issue/PR items,
    handling pagination automatically (up to 1000 results, 100 per page).
    """
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


def _fetch_pr_commits(org: str, repo: str, pr_number: int, merged: bool) -> list[CommitRecord]:
    """Fetch all commits for a PR, returning CommitRecord list.

    Merged PR commits link to /commit/{sha};
    open/unmerged PR commits link to /pull/{n}/commits/{sha}.
    """
    data = _gh(
        "api",
        f"repos/{org}/{repo}/pulls/{pr_number}/commits",
        "--paginate",
    )
    # --paginate concatenates multiple JSON arrays; gh returns one array here
    if isinstance(data, dict):
        # single-page result wrapped as dict (shouldn't happen for this endpoint)
        data = data.get("items", [])

    records: list[CommitRecord] = []
    for commit in data:
        sha = commit.get("sha", "")
        sha7 = sha[:7]
        msg_full = commit.get("commit", {}).get("message", "")
        # Use only the first line of the commit message
        message = msg_full.split("\n")[0].strip()
        if merged:
            url = f"https://github.com/{org}/{repo}/commit/{sha}"
        else:
            url = f"https://github.com/{org}/{repo}/pull/{pr_number}/commits/{sha}"
        records.append(CommitRecord(sha7=sha7, message=message, url=url))
    return records


def _fetch_closing_issues(org: str, repo: str, pr_number: int) -> list[IssueRecord]:
    """Return issues that will be closed when this PR is merged (via GraphQL)."""
    query = """
query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      closingIssuesReferences(first: 50) {
        nodes {
          number
          title
          url
        }
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


class GithubGhProvider(Provider):
    """Fetches contribution data from GitHub using the `gh` CLI."""

    def __init__(self, org: str, repo: str):
        self.org = org
        self.repo = repo
        self._full_repo = f"{org}/{repo}"

    def _build_pr(self, item: dict, merged: bool) -> PRRecord:
        number = item["number"]
        commits = _fetch_pr_commits(self.org, self.repo, number, merged=merged)
        closing: list[IssueRecord] = []
        if merged:
            closing = _fetch_closing_issues(self.org, self.repo, number)
        return PRRecord(
            number=number,
            title=item.get("title", ""),
            url=item.get("html_url", f"https://github.com/{self._full_repo}/pull/{number}"),
            state="merged" if merged else item.get("state", "open"),
            commits=commits,
            closing_issues=closing,
            approved=not merged,  # approved-open PRs are flagged True
        )

    def get_merged_prs(self, username: str, year: int, month: int) -> list[PRRecord]:
        last_day = calendar.monthrange(year, month)[1]
        date_range = f"{year}-{month:02d}-01..{year}-{month:02d}-{last_day:02d}"
        query = (
            f"repo:{self._full_repo} is:pr author:{username} "
            f"is:merged merged:{date_range}"
        )
        items = _gh_search_prs(query)
        return [self._build_pr(item, merged=True) for item in items]

    def get_approved_open_prs(self, username: str) -> list[PRRecord]:
        """Return open PRs by *username* that have at least one approval.

        These represent "未合并 PR" in the report — PRs stuck in the approval
        queue (e.g. repo freeze) but already reviewed and approved.
        No date filter: we want the current approval queue state.
        """
        query = (
            f"repo:{self._full_repo} is:pr author:{username} "
            f"is:open review:approved"
        )
        items = _gh_search_prs(query)
        return [self._build_pr(item, merged=False) for item in items]

    def get_created_issues(self, username: str, year: int, month: int) -> list[IssueRecord]:
        last_day = calendar.monthrange(year, month)[1]
        date_range = f"{year}-{month:02d}-01..{year}-{month:02d}-{last_day:02d}"
        query = (
            f"repo:{self._full_repo} is:issue author:{username} "
            f"created:{date_range}"
        )
        items = _gh_search_prs(query)  # same search endpoint, different type filter
        return [
            IssueRecord(
                number=item["number"],
                title=item.get("title", ""),
                url=item.get("html_url", ""),
            )
            for item in items
        ]
