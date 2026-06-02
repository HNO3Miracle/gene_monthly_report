"""Abstract base class for contribution data providers."""

import datetime
from abc import ABC, abstractmethod

from report_gen.models import PRRecord, IssueRecord


class Provider(ABC):
    """Abstract provider — fetch contribution data from a hosting platform."""

    @abstractmethod
    def get_merged_prs(
        self, username: str, start: datetime.date, end: datetime.date
    ) -> list[PRRecord]: ...

    @abstractmethod
    def get_approved_open_prs(self, username: str) -> list[PRRecord]: ...

    @abstractmethod
    def get_created_issues(
        self, username: str, start: datetime.date, end: datetime.date
    ) -> list[IssueRecord]: ...

    def get_closed_issues_via_prs(self, merged_prs: list[PRRecord]) -> list[IssueRecord]:
        """Deduplicate and collect issues closed by the given merged PRs."""
        seen: set[int] = set()
        result: list[IssueRecord] = []
        for pr in merged_prs:
            for issue in pr.closing_issues:
                if issue.number not in seen:
                    seen.add(issue.number)
                    result.append(issue)
        return result
