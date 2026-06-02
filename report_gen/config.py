"""Configuration for the monthly report generator."""

import datetime
import subprocess
import urllib.request
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# GitHub user
# ---------------------------------------------------------------------------

def get_current_gh_user() -> str:
    """Get the currently logged-in GitHub username via gh CLI."""
    result = subprocess.run(
        ["gh", "api", "user", "--jq", ".login"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Date range
# ---------------------------------------------------------------------------

DEFAULT_TIME_RANGE_URL = (
    "https://raw.githubusercontent.com/HNO3Miracle/gene_monthly_report"
    "/master/default-time-range.txt"
)


def _parse_date(s: str) -> datetime.date:
    """Parse YYYYMMDD string to date."""
    s = s.strip()
    return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def fetch_default_date_range() -> tuple[datetime.date, datetime.date]:
    """Fetch start/end dates from the remote default-time-range.txt.

    Format: ``YYYYMMDD - YYYYMMDD``
    Falls back to the old day-15 heuristic if the URL is unreachable.
    """
    try:
        with urllib.request.urlopen(DEFAULT_TIME_RANGE_URL, timeout=10) as resp:
            text = resp.read().decode().strip()
        parts = text.split("-")
        # Format is "YYYYMMDD - YYYYMMDD", split by " - " to be safe
        parts = [p.strip() for p in text.split("-") if p.strip()]
        # parts: ['20260507', '', '20260603']  — after plain split('-')
        # better: split on ' - '
        left, right = text.split(" - ")
        return _parse_date(left), _parse_date(right)
    except Exception:
        # fall back to old heuristic
        start, end = _default_month_range()
        return start, end


def _default_month_range() -> tuple[datetime.date, datetime.date]:
    """day ≤ 15 → last month; day ≥ 16 → current month."""
    today = datetime.date.today()
    if today.day <= 15:
        first_of_this = today.replace(day=1)
        last_month_end = first_of_this - datetime.timedelta(days=1)
        start = last_month_end.replace(day=1)
        return start, last_month_end
    else:
        start = today.replace(day=1)
        # last day of current month
        if today.month == 12:
            end = today.replace(month=12, day=31)
        else:
            end = today.replace(month=today.month + 1, day=1) - datetime.timedelta(days=1)
        return start, end


def year_month_to_range(year: int, month: int) -> tuple[datetime.date, datetime.date]:
    """Convert year/month to a full-month date range."""
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    return datetime.date(year, month, 1), datetime.date(year, month, last_day)


# ---------------------------------------------------------------------------
# Repository list
# ---------------------------------------------------------------------------

# Default repos always included (in order), not listed in custom_github_repos.yml
DEFAULT_REPOS: list[str] = [
    "openRuyi-Project/openRuyi",
    "openRuyi-Project/homepage",
]

CUSTOM_REPOS_FILE = Path(__file__).parent.parent / "custom_github_repos.yml"


def load_repos() -> list[str]:
    """Return DEFAULT_REPOS plus any extras from custom_github_repos.yml.

    The YAML file is expected to have the structure::

        repos:
          - org/repo
          - org/repo2
    """
    extra: list[str] = []
    if CUSTOM_REPOS_FILE.exists():
        data = yaml.safe_load(CUSTOM_REPOS_FILE.read_text(encoding="utf-8")) or {}
        raw = data.get("repos") or []
        extra = [r for r in raw if isinstance(r, str) and r.strip()]

    # Merge: defaults first, then extras (deduplicated, preserving order)
    seen: set[str] = set()
    result: list[str] = []
    for repo in DEFAULT_REPOS + extra:
        if repo not in seen:
            seen.add(repo)
            result.append(repo)
    return result
