# gene_monthly_report

一个自动生成 openRuyi intern 月报的工具。

## 环境要求

- Python 3.10+
- [gh CLI](https://cli.github.com/) 已安装并登录（`gh auth login`）
- PyYAML：`pip install PyYAML==6.0.1`

## 快速开始

```bash
python3 main.py
```

默认行为：
- 用户：当前 `gh` 登录账号
- 日期范围：从远端 `default-time-range.txt` 拉取。
- PR 范围：当前用户 authored 的所有 GitHub PR，不限制仓库
- 输出：当前目录下的 `./YYYY-MM.md`

## CLI 参数

| 参数 | 说明 |
|---|---|
| `--user USER` | 指定 GitHub 用户名 |
| `--start YYYYMMDD --end YYYYMMDD` | 覆盖日期范围 |
| `--year YEAR --month MONTH` | 快捷指定整月 |
| `--output PATH` | 指定输出文件路径 |
| `--stdout` | 输出到标准输出 |

示例：

```bash
# 指定月份
python3 main.py --year 2026 --month 5

# 为其他用户生成
python3 main.py --user KimmyXYC --year 2026 --month 5

# 输出到指定路径
python3 main.py --output ~/intern/contributions/2026-05/MY.md
```

## 项目结构

```
gene_monthly_report/
├── main.py                        # CLI 入口
├── requirements.txt
└── report_gen/
    ├── config.py                  # 日期推算、当前 gh 用户
    ├── models.py                  # 数据类
    ├── parse.py                   # commit message 包名解析
    ├── render.py                  # Markdown 渲染
    └── providers/
        ├── base.py                # Provider 抽象
        └── github_gh.py           # gh CLI 实现（并发请求）
```

## 月报格式说明

- 已合并 PR：全局查询当前用户 authored、`is:merged` 且 `merged:` 落在日期范围内的 PR
- 未合并 PR：全局查询当前用户 authored、`review:approved` + `is:open` 的 PR
- 新建 issue：全局查询当前用户 authored 且 `created:` 落在日期范围内的 issue
- 解决 issue：当期已合并 PR 的 `closingIssuesReferences` 去重汇总
- 包名从 commit message 的 `SPECS: xxx:` 或 `SPECS: Add xxx` 解析
- 多仓库在同一小节内以 `#####` 分节；空表不输出
- 邮箱校验：拉取完成后检查 PR commit author email 是否为 `@isrc.iscas.ac.cn`，仅告警，不参与筛选
