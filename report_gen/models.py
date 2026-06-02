"""Data models for the monthly report generator."""

from dataclasses import dataclass, field


@dataclass
class CommitRecord:
    sha7: str       # first 7 characters of commit SHA
    message: str    # first line of commit message
    url: str


@dataclass
class IssueRecord:
    number: int
    title: str
    url: str


@dataclass
class PRRecord:
    number: int
    title: str
    url: str
    state: str                          # "merged" | "open" | "closed"
    commits: list[CommitRecord] = field(default_factory=list)
    closing_issues: list[IssueRecord] = field(default_factory=list)
    # For approved-but-not-merged PRs, track approval state
    approved: bool = False
