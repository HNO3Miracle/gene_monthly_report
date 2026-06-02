"""Render the monthly report as Markdown."""

from .models import PRRecord, IssueRecord
from .parse import packages_from_commits


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _br(items: list[str]) -> str:
    """Join a list into a single table cell, using <br> as separator."""
    return "<br>".join(items)


def _pkg_cell(pr: PRRecord) -> str:
    """Build the '包名' cell for a PR."""
    msgs = [c.message for c in pr.commits]
    pkgs = packages_from_commits(msgs)
    if pkgs:
        return _br(pkgs)
    # fall back to PR title if no SPECS pattern matched
    return pr.title


def _pr_link_cell(pr: PRRecord) -> str:
    return f"[#{pr.number}]({pr.url})"


def _commit_cell(pr: PRRecord) -> str:
    """Build the '对应 commit' cell: each commit on its own <br>-line."""
    parts = []
    for c in pr.commits:
        parts.append(f"[{c.sha7}]({c.url}): {c.message}")
    if not parts:
        return ""
    return _br(parts)


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
    pkg  = _pkg_cell(pr)
    link = _pr_link_cell(pr)
    cmts = _commit_cell(pr)
    return f"| {pkg} | {link} | {cmts} |  |  |"


def _pr_row_open(pr: PRRecord) -> str:
    pkg  = _pkg_cell(pr)
    link = _pr_link_cell(pr)
    cmts = _commit_cell(pr)
    return f"| {pkg} | {link} | {cmts} |  |  |  |"


# ---------------------------------------------------------------------------
# Top-level renderer
# ---------------------------------------------------------------------------

def render_report(
    username: str,
    year: int,
    month: int,
    merged_prs: list[PRRecord],
    open_prs: list[PRRecord],
    created_issues: list[IssueRecord],
    closed_issues: list[IssueRecord],
) -> str:
    """Return the full Markdown report as a string."""
    lines: list[str] = []

    # Title
    lines.append(f"# {year:04d}-{month:02d}")
    lines.append("")
    lines.append("实习生工作月度总结。")
    lines.append("")

    # Section header (GitHub login only, as agreed)
    lines.append(f"## {username}")
    lines.append("")

    # --- Summary table ---
    lines.append("### 外部可见产出")
    lines.append("")
    lines.append("| 总计       | 数量 | 积分 |")
    lines.append("| ---------- | ---- | ---- |")
    lines.append(f"| 已合并 PR  | {len(merged_prs)}    |      |")
    lines.append(f"| 未合并 PR  | {len(open_prs)}    |      |")
    lines.append(f"| 新建 issue | {len(created_issues)}    |      |")
    lines.append(f"| 解决 issue | {len(closed_issues)}    |      |")
    lines.append("")

    # --- Merged PRs table ---
    lines.append("#### 已合并 PR")
    lines.append("")
    lines.extend(_table_header_merged())
    if merged_prs:
        for pr in merged_prs:
            lines.append(_pr_row_merged(pr))
    else:
        lines.append("| 无 |  |  |  |  |")
    lines.append("")

    # --- Approved-but-open PRs table ---
    lines.append("#### 未合并 PR")
    lines.append("")
    lines.extend(_table_header_open())
    if open_prs:
        for pr in open_prs:
            lines.append(_pr_row_open(pr))
    else:
        lines.append("| 无 |  |  |  |  |  |")
    lines.append("")

    # --- Placeholder sections ---
    lines.append("### 本月总结")
    lines.append("")
    lines.append("（请在此填写本月工作内容、心得感悟等，大约 100~200 字）")
    lines.append("")
    lines.append("### 次月计划")
    lines.append("")
    lines.append("（请在此填写次月工作方向及计划）")
    lines.append("")

    return "\n".join(lines)
