"""Configuration for the monthly report generator."""

import datetime
import subprocess


def get_current_gh_user() -> str:
    """Get the currently logged-in GitHub username via gh CLI."""
    result = subprocess.run(
        ["gh", "api", "user", "--jq", ".login"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def default_year_month() -> tuple[int, int]:
    """
    Determine the default (year, month) to report on.
    If today is the 15th or earlier → last month.
    If today is the 16th or later   → current month.
    """
    today = datetime.date.today()
    if today.day <= 15:
        # go back one month
        first_of_this = today.replace(day=1)
        last_month = first_of_this - datetime.timedelta(days=1)
        return last_month.year, last_month.month
    else:
        return today.year, today.month


# Default repository to query
DEFAULT_ORG = "openRuyi-Project"
DEFAULT_REPO = "openRuyi"
DEFAULT_FULL_REPO = f"{DEFAULT_ORG}/{DEFAULT_REPO}"
