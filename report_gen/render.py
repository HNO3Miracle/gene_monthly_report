"""Render the monthly report as Markdown."""

import datetime
from .models import PRRecord, IssueRecord
from .parse import packages_from_commits


# ---------------------------------------------------------------------------
# Cell helpers
# ---------------------------------------------------------------------------

def _br(items: list[str]) -> str:
    return "<br>".join(items)


def _pkg_cell(pr: PRRecord) -> str:
    msgs = [c.message for c in pr.commits]
    pkgs = packages_from_commits(msgs)
    return _br(pkgs) if pkgs else pr.title


def _pr_link_cell(pr: PRRecord) -> str:
    return f"[#{pr.number}]({pr.url})"


def _commit_cell(pr: PRRecord) -> str:
    parts = [f"[{c.sha7}]({c.url}): {c.message}" for c in pr.commits]
    return _br(parts) if parts else ""


# ---------------------------------------------------------------------------
# Table builders
# ---------------------------------------------------------------------------

def _table_header_merged() -> list[str]:
    return [
        "| 包名 | issue/PR 链接 | 对应 commit | 任务类型 | 积分 |",
        "| ---- | ------------- | ----------- | -------- | ---- |",
    ]


def _table_header_open() -> list[str]:
    return [
        "| 包名 | issue/PR 链接 | 对应 commit | 任务类型 | 积分 | 备注 |",
        "| ---- | ------------- | ----------- | -------- | ---- | ---- |",
    ]


def _pr_row_merged(pr: PRRecord) -> str:
    return f"| {_pkg_cell(pr)} | {_pr_link_cell(pr)} | {_commit_cell(pr)} |  |  |"


def _pr_row_open(pr: PRRecord) -> str:
    return f"| {_pkg_cell(pr)} | {_pr_link_cell(pr)} | {_commit_cell(pr)} |  |  |  |"


# ---------------------------------------------------------------------------
# Per-repo section helpers
# ---------------------------------------------------------------------------

# RepoData: dict keyed by repo full name (e.g. "openRuyi-Project/openRuyi")
# value: {"merged": list[PRRecord], "open": list[PRRecord],
#         "created": list[IssueRecord], "closed": list[IssueRecord]}
RepoData = dict[str, dict[str, list]]


def _render_merged_section(repo_data: RepoData) -> list[str]:
    """Render '#### 已合并 PR' section, split by repo with ##### headings."""
    lines: list[str] = []
    lines.append("#### 已合并 PR")
    lines.append("")

    has_any = any(d["merged"] for d in repo_data.values())

    for repo, data in repo_data.items():
        prs = data["merged"]
        lines.append(f"##### {repo}")
        lines.append("")
        lines.extend(_table_header_merged())
        if prs:
            for pr in prs:
                lines.append(_pr_row_merged(pr))
        else:
            lines.append("| 无 |  |  |  |  |")
        lines.append("")

    return lines


def _render_open_section(repo_data: RepoData) -> list[str]:
    """Render '#### 未合并 PR' section, split by repo."""
    lines: list[str] = []
    lines.append("#### 未合并 PR")
    lines.append("")

    for repo, data in repo_data.items():
        prs = data["open"]
        lines.append(f"##### {repo}")
        lines.append("")
        lines.extend(_table_header_open())
        if prs:
            for pr in prs:
                lines.append(_pr_row_open(pr))
        else:
            lines.append("| 无 |  |  |  |  |  |")
        lines.append("")

    return lines


# ---------------------------------------------------------------------------
# Top-level renderer
# ---------------------------------------------------------------------------

def render_report(
    username: str,
    start: datetime.date,
    end: datetime.date,
    repo_data: RepoData,
) -> str:
    """Return the full Markdown report as a string.

    *repo_data* maps repo full name → dict with keys:
        merged, open, created, closed  (each a list)
    """
    # Aggregate totals across all repos
    total_merged  = sum(len(d["merged"])  for d in repo_data.values())
    total_open    = sum(len(d["open"])    for d in repo_data.values())
    total_created = sum(len(d["created"]) for d in repo_data.values())
    total_closed  = sum(len(d["closed"])  for d in repo_data.values())

    # Use start month as the report title (e.g. 2026-05)
    title = f"{start.year:04d}-{start.month:02d}"

    lines: list[str] = []

    lines.append(f"# {title}")
    lines.append("")
    lines.append("实习生工作月度总结。")
    lines.append("")
    lines.append(f"## {username}")
    lines.append("")

    # Summary table
    lines.append("### 外部可见产出")
    lines.append("")
    lines.append("| 总计       | 数量 | 积分 |")
    lines.append("| ---------- | ---- | ---- |")
    lines.append(f"| 已合并 PR  | {total_merged}    |      |")
    lines.append(f"| 未合并 PR  | {total_open}    |      |")
    lines.append(f"| 新建 issue | {total_created}    |      |")
    lines.append(f"| 解决 issue | {total_closed}    |      |")
    lines.append("")

    # Merged PR section (per repo)
    lines.extend(_render_merged_section(repo_data))

    # Open (approved) PR section (per repo)
    lines.extend(_render_open_section(repo_data))

    # Placeholders
    lines.append("### 本月总结")
    lines.append("")
    lines.append("（请在此填写本月工作内容、心得感悟等，大约 100~200 字）")
    lines.append("")
    lines.append("### 次月计划")
    lines.append("")
    lines.append("（请在此填写次月工作方向及计划）")
    lines.append("")

    return "\n".join(lines)
