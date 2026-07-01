#!/usr/bin/env python3
"""月报生成器 CLI 入口。

用法示例：
    python3 main.py                          # 从远端拉日期范围，当前 gh 账号，所有 authored PR
    python3 main.py --start 20260501 --end 20260531
    python3 main.py --year 2026 --month 5
    python3 main.py --user KimmyXYC
    python3 main.py --output ~/report.md
    python3 main.py --stdout
"""

import argparse
import datetime
import sys
from pathlib import Path

from report_gen.config import (
    fetch_default_date_range,
    get_current_gh_user,
    year_month_to_range,
)
from report_gen.providers.github_gh import GithubGhGlobalProvider
from report_gen.render import render_report, RepoData


ISRC_EMAIL_DOMAIN = "@isrc.iscas.ac.cn"


def _parse_yyyymmdd(s: str) -> datetime.date:
    s = s.strip()
    if len(s) != 8 or not s.isdigit():
        raise argparse.ArgumentTypeError(f"日期格式应为 YYYYMMDD，收到：{s!r}")
    return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="生成 GitHub 个人贡献月报（Markdown 格式）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--user", "-u", default=None,
                        help="GitHub 用户名（默认：当前 gh 登录账号）")

    # Date range: either --start/--end (absolute) or --year/--month (shortcut)
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument("--start", type=_parse_yyyymmdd, default=None,
                            metavar="YYYYMMDD",
                            help="报告开始日期（与 --end 配对使用，覆盖远端默认范围）")
    parser.add_argument("--end", type=_parse_yyyymmdd, default=None,
                        metavar="YYYYMMDD",
                        help="报告结束日期（与 --start 配对使用）")
    date_group.add_argument("--year", "-y", type=int, default=None,
                            help="报告年份（与 --month 配对，快捷指定整月）")
    parser.add_argument("--month", "-m", type=int, default=None,
                        help="报告月份 1-12（与 --year 配对）")

    parser.add_argument(
        "--repos", "-r", default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--output", "-o", default=None,
                        help="输出文件路径（默认：./YYYY-MM.md）")
    parser.add_argument("--stdout", action="store_true",
                        help="输出到标准输出")
    return parser


def resolve_date_range(args) -> tuple[datetime.date, datetime.date]:
    """Return (start, end) based on CLI args, falling back to remote URL."""
    if args.year and args.month:
        return year_month_to_range(args.year, args.month)
    if args.year or args.month:
        sys.exit("错误：--year 和 --month 必须同时指定")

    if args.start:
        if not args.end:
            sys.exit("错误：--start 需要同时指定 --end")
        return args.start, args.end

    # Default: fetch from remote
    print("🌐 从远端拉取默认日期范围...", file=sys.stderr)
    start, end = fetch_default_date_range()
    print(f"   范围：{start} → {end}", file=sys.stderr)
    return start, end


def _repo_names_in_order(*repo_maps: dict[str, list]) -> list[str]:
    seen: set[str] = set()
    repos: list[str] = []
    for repo_map in repo_maps:
        for repo in repo_map:
            if repo not in seen:
                seen.add(repo)
                repos.append(repo)
    return repos


def _count_repo_map(repo_map: dict[str, list]) -> int:
    return sum(len(items) for items in repo_map.values())


def _warn_non_isrc_commit_emails(repo_data: RepoData) -> None:
    bad: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()
    for full_repo, data in repo_data.items():
        for pr in data["merged"] + data["open"]:
            for commit in pr.commits:
                key = commit.url or f"{full_repo}:{commit.sha7}"
                if key in seen:
                    continue
                seen.add(key)
                email = commit.author_email.strip()
                if not email.lower().endswith(ISRC_EMAIL_DOMAIN):
                    bad.append((full_repo, commit.sha7, email or "<empty>", commit.message))

    if not bad:
        print(f"✅ 邮箱校验通过：所有 PR commit 均为 {ISRC_EMAIL_DOMAIN}", file=sys.stderr)
        return

    print(
        f"⚠️  邮箱校验：发现 {len(bad)} 个 PR commit 不是 {ISRC_EMAIL_DOMAIN}",
        file=sys.stderr,
    )
    for full_repo, sha7, email, message in bad[:20]:
        print(f"   - {full_repo} {sha7} {email}: {message}", file=sys.stderr)
    if len(bad) > 20:
        print(f"   ... 还有 {len(bad) - 20} 个未列出", file=sys.stderr)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # --- User ---
    if args.user:
        username = args.user
    else:
        print("🔍 获取当前 gh 登录用户...", file=sys.stderr)
        username = get_current_gh_user()
        print(f"   用户：{username}", file=sys.stderr)

    # --- Date range ---
    start, end = resolve_date_range(args)
    print(f"📅 报告范围：{start} → {end}", file=sys.stderr)

    if args.repos:
        print("⚠️  --repos 已忽略：现在默认获取当前用户 authored 的所有 PR", file=sys.stderr)

    # --- Output path ---
    if not args.stdout:
        if args.output:
            output_path = Path(args.output).expanduser()
        else:
            output_path = Path(f"{start.year:04d}-{start.month:02d}.md")
    else:
        output_path = None

    # --- Fetch data globally, then group by repo ---
    provider = GithubGhGlobalProvider()
    print("\n🔎 全局获取当前用户 authored 的贡献记录...", file=sys.stderr)

    print(f"   ⬇️  已合并 PR ({start} → {end})...", file=sys.stderr)
    merged_by_repo = provider.get_merged_prs_by_repo(username, start, end)
    print(f"      → {_count_repo_map(merged_by_repo)} 个", file=sys.stderr)

    print("   ⬇️  已 Approved 待合并 PR...", file=sys.stderr)
    open_by_repo = provider.get_approved_open_prs_by_repo(username)
    print(f"      → {_count_repo_map(open_by_repo)} 个", file=sys.stderr)

    print(f"   ⬇️  新建 issue ({start} → {end})...", file=sys.stderr)
    created_by_repo = provider.get_created_issues_by_repo(username, start, end)
    print(f"      → {_count_repo_map(created_by_repo)} 个", file=sys.stderr)

    repo_data: RepoData = {}
    for full_repo in _repo_names_in_order(merged_by_repo, open_by_repo, created_by_repo):
        merged = merged_by_repo.get(full_repo, [])
        closed = provider.get_closed_issues_via_prs(merged)
        repo_data[full_repo] = {
            "merged":  merged,
            "open":    open_by_repo.get(full_repo, []),
            "created": created_by_repo.get(full_repo, []),
            "closed":  closed,
        }

    total_closed = sum(len(data["closed"]) for data in repo_data.values())
    print(f"   ✔️  解决 issue (via merged PRs)：{total_closed} 个", file=sys.stderr)
    print(f"📦 涉及仓库：{', '.join(repo_data) if repo_data else '无'}", file=sys.stderr)
    _warn_non_isrc_commit_emails(repo_data)

    # --- Render ---
    print("\n✍️  渲染月报...", file=sys.stderr)
    report = render_report(
        username=username,
        start=start,
        end=end,
        repo_data=repo_data,
    )

    # --- Output ---
    if output_path is None:
        print(report)
    else:
        output_path.write_text(report, encoding="utf-8")
        print(f"✅  月报已写入：{output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
