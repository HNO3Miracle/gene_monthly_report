#!/usr/bin/env python3
"""月报生成器 CLI 入口。

用法示例：
    python main.py                            # 自动推算年月，当前 gh 账号
    python main.py --year 2026 --month 5
    python main.py --user KimmyXYC --year 2026 --month 5
    python main.py --output ~/report.md
"""

import argparse
import sys
from pathlib import Path

from report_gen.config import default_year_month, get_current_gh_user, DEFAULT_ORG, DEFAULT_REPO
from report_gen.providers.github_gh import GithubGhProvider
from report_gen.render import render_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="生成 openRuyi 仓库个人贡献月报（Markdown 格式）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--user", "-u",
        default=None,
        help="GitHub 用户名（默认：当前 gh 登录账号）",
    )
    parser.add_argument(
        "--year", "-y",
        type=int,
        default=None,
        help="报告年份（默认：按日期自动推算）",
    )
    parser.add_argument(
        "--month", "-m",
        type=int,
        default=None,
        help="报告月份 1-12（默认：按日期自动推算）",
    )
    parser.add_argument(
        "--repo", "-r",
        default=f"{DEFAULT_ORG}/{DEFAULT_REPO}",
        help=f"目标仓库，格式 org/repo（默认：{DEFAULT_ORG}/{DEFAULT_REPO}）",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="输出文件路径（默认：./YYYY-MM.md）",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="输出到标准输出而不是文件",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # --- Resolve user ---
    if args.user:
        username = args.user
    else:
        print("🔍 获取当前 gh 登录用户...", file=sys.stderr)
        username = get_current_gh_user()
        print(f"   用户：{username}", file=sys.stderr)

    # --- Resolve year/month ---
    if args.year and args.month:
        year, month = args.year, args.month
    elif args.year or args.month:
        parser.error("--year 和 --month 必须同时指定，或都不指定")
    else:
        year, month = default_year_month()
    print(f"📅 报告期间：{year:04d}-{month:02d}", file=sys.stderr)

    # --- Resolve repo ---
    parts = args.repo.split("/", 1)
    if len(parts) != 2:
        parser.error(f"--repo 格式应为 org/repo，收到：{args.repo!r}")
    org, repo = parts

    # --- Resolve output path ---
    if args.stdout:
        output_path = None
    else:
        if args.output:
            output_path = Path(args.output).expanduser()
        else:
            output_path = Path(f"{year:04d}-{month:02d}.md")

    # --- Fetch data ---
    provider = GithubGhProvider(org=org, repo=repo)

    print(f"⬇️  拉取已合并 PR（{year:04d}-{month:02d}）...", file=sys.stderr)
    merged_prs = provider.get_merged_prs(username, year, month)
    print(f"   → {len(merged_prs)} 个已合并 PR", file=sys.stderr)

    print("⬇️  拉取已 Approved 待合并 PR...", file=sys.stderr)
    open_prs = provider.get_approved_open_prs(username)
    print(f"   → {len(open_prs)} 个待合并 PR", file=sys.stderr)

    print(f"⬇️  拉取新建 issue（{year:04d}-{month:02d}）...", file=sys.stderr)
    created_issues = provider.get_created_issues(username, year, month)
    print(f"   → {len(created_issues)} 个新建 issue", file=sys.stderr)

    print("⬇️  汇总解决的 issue（来自已合并 PR）...", file=sys.stderr)
    closed_issues = provider.get_closed_issues_via_prs(merged_prs)
    print(f"   → {len(closed_issues)} 个解决 issue", file=sys.stderr)

    # --- Render ---
    print("✍️  渲染月报...", file=sys.stderr)
    report = render_report(
        username=username,
        year=year,
        month=month,
        merged_prs=merged_prs,
        open_prs=open_prs,
        created_issues=created_issues,
        closed_issues=closed_issues,
    )

    # --- Output ---
    if output_path is None:
        print(report)
    else:
        output_path.write_text(report, encoding="utf-8")
        print(f"✅  月报已写入：{output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
