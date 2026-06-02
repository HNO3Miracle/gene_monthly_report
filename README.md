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
- 仓库：`openRuyi-Project/openRuyi` + `openRuyi-Project/homepage` + `custom_github_repos.yml` 中的额外仓库
- 输出：当前目录下的 `./YYYY-MM.md`

## 自定义仓库

编辑 `custom_github_repos.yml`，添加默认列表之外的仓库：

```yaml
repos:
  - fastfetch-cli/fastfetch
  - openRuyi-Project/linux
```

## CLI 参数

| 参数 | 说明 |
|---|---|
| `--user USER` | 指定 GitHub 用户名 |
| `--start YYYYMMDD --end YYYYMMDD` | 覆盖日期范围 |
| `--year YEAR --month MONTH` | 快捷指定整月 |
| `--repos org/r1,org/r2` | 临时覆盖仓库列表 |
| `--output PATH` | 指定输出文件路径 |
| `--stdout` | 输出到标准输出 |

示例：

```bash
# 指定月份
python3 main.py --year 2026 --month 5

# 为其他用户生成
python3 main.py --user KimmyXYC --year 2026 --month 5

# 临时添加仓库
python3 main.py --repos openRuyi-Project/openRuyi,openRuyi-Project/linux

# 输出到指定路径
python3 main.py --output ~/intern/contributions/2026-05/MY.md
```

## 项目结构

```
gene_monthly_report/
├── main.py                        # CLI 入口
├── custom_github_repos.yml        # 额外仓库配置
├── requirements.txt
└── report_gen/
    ├── config.py                  # 日期推算、仓库列表
    ├── models.py                  # 数据类
    ├── parse.py                   # commit message 包名解析
    ├── render.py                  # Markdown 渲染
    └── providers/
        ├── base.py                # Provider 抽象
        └── github_gh.py           # gh CLI 实现（并发请求）
```

## 月报格式说明

- 已合并 PR：以 `merged:` 日期范围查询
- 未合并 PR：`review:approved` + `is:open`，反映仓库冻结期中已批准待合并的 PR
- 新建 issue：以 `created:` 日期范围查询
- 解决 issue：当期已合并 PR 的 `closingIssuesReferences` 去重汇总
- 包名从 commit message 的 `SPECS: xxx:` 或 `SPECS: Add xxx` 解析
- 多仓库在同一小节内以 `#####` 分节；空表不输出
