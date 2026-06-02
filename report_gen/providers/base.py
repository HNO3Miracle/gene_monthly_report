"""Abstract base class for contribution data providers."""

from abc import ABC, abstractmethod

from report_gen.models import PRRecord, IssueRecord


class Provider(ABC):
    """Abstract provider — fetch contribution data from a hosting platform."""

    @abstractmethod
    def get_merged_prs(self, username: str, year: int, month: int) -> list[PRRecord]:
        """PRs authored by *username* that were merged in the given month."""

    @abstractmethod
    def get_approved_open_prs(self, username: str) -> list[PRRecord]:
        """Open PRs authored by *username* that have at least one approval.

        These represent PRs held in the approval queue (e.g. during a freeze
        period) and map to the "未合并 PR" section of the report.
        """

    @abstractmethod
    def get_created_issues(self, username: str, year: int, month: int) -> list[IssueRecord]:
        """Issues created by *username* in the given month."""

    def get_closed_issues_via_prs(self, merged_prs: list[PRRecord]) -> list[IssueRecord]:
        """Collect and deduplicate issues closed by the given merged PRs.

        Each PRRecord is expected to have its ``closing_issues`` field already
        populated (done by the concrete provider inside ``get_merged_prs``).
        """
        seen: set[int] = set()
        result: list[IssueRecord] = []
        for pr in merged_prs:
            for issue in pr.closing_issues:
                if issue.number not in seen:
                    seen.add(issue.number)
                    result.append(issue)
        return result
