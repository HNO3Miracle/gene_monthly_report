#!/usr/bin/env python3
"""月报生成器 CLI 入口。

用法示例：
    python3 main.py                          # 从远端拉日期范围，当前 gh 账号，repos.txt 仓库列表
    python3 main.py --start 20260501 --end 20260531
    python3 main.py --year 2026 --month 5
    python3 main.py --user KimmyXYC
    python3 main.py --repos openRuyi-Project/linux,openRuyi-Project/abaci-bot
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
    load_repos,
    year_month_to_range,
)
from report_gen.providers.github_gh import GithubGhProvider
from report_gen.render import render_report, RepoData


def _parse_yyyymmdd(s: str) -> datetime.date:
    s = s.strip()
    if len(s) != 8 or not s.isdigit():
        raise argparse.ArgumentTypeError(f"日期格式应为 YYYYMMDD，收到：{s!r}")
    return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="生成 openRuyi-Project 个人贡献月报（Markdown 格式）",
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
        help="仓库列表，逗号分隔，格式 org/repo（覆盖 repos.txt）",
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

    # --- Repos ---
    if args.repos:
        repos = [r.strip() for r in args.repos.split(",") if r.strip()]
    else:
        repos = load_repos()
    print(f"📦 仓库列表：{', '.join(repos)}", file=sys.stderr)

    # --- Output path ---
    if not args.stdout:
        if args.output:
            output_path = Path(args.output).expanduser()
        else:
            output_path = Path(f"{start.year:04d}-{start.month:02d}.md")
    else:
        output_path = None

    # --- Fetch data per repo ---
    repo_data: RepoData = {}

    for full_repo in repos:
        parts = full_repo.split("/", 1)
        if len(parts) != 2:
            print(f"⚠️  跳过格式错误的仓库：{full_repo!r}", file=sys.stderr)
            continue
        org, repo = parts
        provider = GithubGhProvider(org=org, repo=repo)

        print(f"\n📂 {full_repo}", file=sys.stderr)

        print(f"   ⬇️  已合并 PR ({start} → {end})...", file=sys.stderr)
        merged = provider.get_merged_prs(username, start, end)
        print(f"      → {len(merged)} 个", file=sys.stderr)

        print(f"   ⬇️  已 Approved 待合并 PR...", file=sys.stderr)
        open_prs = provider.get_approved_open_prs(username)
        print(f"      → {len(open_prs)} 个", file=sys.stderr)

        print(f"   ⬇️  新建 issue ({start} → {end})...", file=sys.stderr)
        created = provider.get_created_issues(username, start, end)
        print(f"      → {len(created)} 个", file=sys.stderr)

        closed = provider.get_closed_issues_via_prs(merged)
        print(f"   ✔️  解决 issue (via merged PRs)：{len(closed)} 个", file=sys.stderr)

        repo_data[full_repo] = {
            "merged":  merged,
            "open":    open_prs,
            "created": created,
            "closed":  closed,
        }

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
